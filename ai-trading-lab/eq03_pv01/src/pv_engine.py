"""EQ03-PV01 portfolio engine: one long-only cash account, daily event loop, no leverage.

Order of events on session t:
 1. settlements and dividend payments due on t become settled cash;
 2. interest on settled cash for (t-1, t] at the rate known at t-1's close (optional);
 3. OPEN: buy if a trade enters at t (budget = min(max_position, settled cash); fixed fee + half the
    round-trip bps are paid; shares rounded DOWN to the share step; no buy if < 1 step);
 4. ex-dividend: shares held at the close of t-1 earn div[t] per share, paid pay_lag sessions later;
 5. CLOSE: sell all if a trade exits at t (half bps + fixed fee); proceeds settle T+k sessions later;
 6. mark to market at the close: settled + unsettled cash + dividend receivable + shares * close.
Cash is never negative (asserted). Prices are raw; dividends are cash; adjusted prices are never used.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pv_data import Market, settlement_lag


@dataclass(frozen=True)
class Scenario:
    bps_rt: float = 10.0          # proportional round-trip cost (spread/slippage), half per side
    fee: float = 0.0              # fixed commission per order, USD
    share_step: float = 1e-4      # 1e-4 = fractional shares, 1.0 = whole shares only
    idle_rf: bool = True          # settled idle cash earns the risk-free proxy
    capital: float = 100.0
    max_position: float = 50.0
    pay_lag: int = 3              # dividend paid this many sessions after ex-date (TLT 2026: 3 sessions)

    def label(self) -> str:
        return (f"bps{self.bps_rt:g}_fee{self.fee:g}_{'frac' if self.share_step < 1 else 'whole'}"
                f"_{'rf' if self.idle_rf else 'cash0'}")


@dataclass
class Result:
    dates: pd.DatetimeIndex
    equity: np.ndarray
    position_value: np.ndarray
    trades: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    dividends_received: float = 0.0
    fees_paid: float = 0.0
    bps_paid: float = 0.0
    traded_notional: float = 0.0
    cash_shortfalls: int = 0


def run(m: Market, start: int, end: int, trades: list[tuple[int, int, str]], sc: Scenario,
        liquidate_at_end: bool = True) -> Result:
    """Replay sessions[start..end] inclusive. trades: (entry_idx, exit_idx, label); only trades fully
    inside [start, end] are used; they must not overlap."""
    tr = sorted([t for t in trades if t[0] >= start and t[1] <= end])
    for (a1, b1, _), (a2, _b2, _) in zip(tr, tr[1:]):
        if a2 <= b1:
            raise ValueError('overlapping trades')
    entries = {t[0]: t for t in tr}
    exits = {t[1]: t for t in tr}
    h = sc.bps_rt / 20000.0
    n = end - start + 1
    eq = np.empty(n)
    pv = np.zeros(n)
    settled = sc.capital
    pending: list[tuple[int, float]] = []   # (due_idx, amount): sale proceeds
    divrec: list[tuple[int, float]] = []    # (pay_idx, amount): dividend receivable
    shares = 0.0
    held_prev_close = 0.0
    res = Result(m.sessions[start:end + 1], eq, pv)
    cur = None
    for k in range(start, end + 1):
        # 1. settlements / dividend payments
        for lst in (pending, divrec):
            due = [x for x in lst if x[0] <= k]
            for x in due:
                settled += x[1]
                lst.remove(x)
            assert settled >= -1e-9, 'negative cash'
        # 2. interest
        if sc.idle_rf and k > start:
            days = (m.sessions[k] - m.sessions[k - 1]).days
            settled += settled * m.rf[k - 1] * days / 365.0
        # 3. open: buy
        if k in entries and shares == 0.0:
            # reserve the exit commission so that a cash account can never go negative (fix after run01)
            budget = min(sc.max_position, settled - sc.fee)
            if budget < sc.max_position - 1e-12:
                res.cash_shortfalls += 1
            px = m.open[k] * (1 + h)
            q = np.floor(max(budget - sc.fee, 0.0) / px / sc.share_step + 1e-9) * sc.share_step
            if q > 0 and q * px + 2 * sc.fee > settled + 1e-12:
                q = 0.0
            if q <= 0:
                res.skipped.append((str(m.sessions[k].date()), 'below one share step', budget))
            else:
                cost = q * px + sc.fee
                settled -= cost
                assert settled >= -1e-9, 'negative cash'
                shares = q
                res.fees_paid += sc.fee
                res.bps_paid += q * m.open[k] * h
                res.traded_notional += q * m.open[k]
                cur = {'month': entries[k][2], 'entry': str(m.sessions[k].date()), 'shares': q,
                       'entry_px': m.open[k], 'cost': cost, 'div': 0.0}
        # 4. ex-dividend entitlement (held at previous close)
        if m.div[k] > 0 and held_prev_close > 0:
            amt = held_prev_close * m.div[k]
            divrec.append((min(k + sc.pay_lag, len(m.sessions) + 10**6), amt))
            res.dividends_received += amt
            if cur is not None:
                cur['div'] += amt
        # 5. close: sell
        if k in exits and shares > 0:
            gross = shares * m.close[k]
            proceeds = gross * (1 - h) - sc.fee
            pending.append((k + settlement_lag(m.sessions[k]), proceeds))
            res.fees_paid += sc.fee
            res.bps_paid += gross * h
            res.traded_notional += gross
            cur.update({'exit': str(m.sessions[k].date()), 'exit_px': m.close[k], 'proceeds': proceeds,
                        'pnl': proceeds + cur['div'] - cur['cost'],
                        'ret': (proceeds + cur['div']) / cur['cost'] - 1})
            res.trades.append(cur)
            cur = None
            shares = 0.0
        # 6. mark to market
        pv[k - start] = shares * m.close[k]
        eq[k - start] = settled + sum(x[1] for x in pending) + sum(x[1] for x in divrec) + pv[k - start]
        held_prev_close = shares
    if liquidate_at_end and shares > 0:
        # open position at the end of the window: value it net of exit costs (never happens for EQ03)
        eq[-1] -= shares * m.close[end] * h + sc.fee
    return res


def buy_and_hold_trade(start: int, end: int) -> list[tuple[int, int, str]]:
    return [(start, end, 'buy&hold')]
