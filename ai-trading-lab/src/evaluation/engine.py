"""Reference event-driven replay engine on 1m bars (independent of Freqtrade).

Execution model (MVP v0.1, sections 3-4):
* long spot only, one position per account, notional = min(stake, cash/(1+fee)), qty rounded down to step;
* entry at the 1m open at decision time (+ optional delay), adverse price adjustment `slip`,
  buy price rounded UP to tick; sell prices rounded DOWN to tick;
* stop = fill*(1-stop_pct), target = fill*(1+target_pct), market-trigger model;
  same-minute conflict -> stop first; gap through stop -> fill at open; gap through target -> trigger price;
* entry bar is checked after entry; time exit at the 1m open when the hold expires, before that bar's range;
* cooldown after exit; boundary_exit at the last available close of the segment;
* fees charged in quote on actual notional of each side;
* risk limits (daily/total, mark-to-market at each 1m close and at execution) unless risk disabled
  (signal-only diagnostic mode).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_NS = 60_000_000_000


@dataclass
class Filters:
    tick: float = 0.0
    step: float = 0.0
    min_notional: float = 0.0


@dataclass
class ExecParams:
    hold_minutes: int
    stop_pct: float = 0.006
    target_pct: float = 0.009
    fee: float = 0.001
    slip: float = 0.00025
    delay_minutes: int = 0
    cooldown_minutes: int = 5
    stake: float = 50.0
    filters: dict = field(default_factory=dict)  # symbol -> Filters


@dataclass
class RiskParams:
    enabled: bool = True
    initial_equity: float = 100.0
    daily_limit: float = 1.5
    total_limit: float = 10.0


@dataclass
class AccountState:
    cash: float
    cooldown_until: int = -10**9      # minute index from which entries are allowed again
    day: int | None = None            # absolute UTC day number of the current day
    day_start_equity: float | None = None
    paused_day: int | None = None     # daily stop active for this absolute day
    total_stopped: bool = False
    busy_until: int = -10**9          # minute index at which the current/last position is closed
    last_entry_decision: int = -10**9


class Bars:
    """1m bars of one symbol on the regular minute grid [start, end) of a segment."""

    def __init__(self, df1m: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp):
        n = int((end - start).value // MIN_NS)
        self.start, self.end, self.n = start, end, n
        idx = ((df1m["open_time"] - start).dt.total_seconds() // 60).astype("int64").to_numpy()
        keep = (idx >= 0) & (idx < n)
        idx = idx[keep]
        self.o = np.full(n, np.nan); self.h = np.full(n, np.nan)
        self.l = np.full(n, np.nan); self.c = np.full(n, np.nan)
        for arr, col in ((self.o, "open"), (self.h, "high"), (self.l, "low"), (self.c, "close")):
            arr[idx] = df1m[col].to_numpy()[keep]
        self.c_ffill = pd.Series(self.c).ffill().to_numpy()
        self.start_min = start.value // MIN_NS

    def present(self, k: int) -> bool:
        return 0 <= k < self.n and not math.isnan(self.o[k])


def round_up(x: float, tick: float) -> float:
    if not tick:
        return x
    return math.ceil(x / tick - 1e-9) * tick


def round_down(x: float, tick: float) -> float:
    if not tick:
        return x
    return math.floor(x / tick + 1e-9) * tick


def _day(bars: Bars, k: int) -> int:
    return (bars.start_min + k) // 1440


def run(signals: pd.DataFrame, bars: dict[str, Bars], ex: ExecParams, risk: RiskParams,
        state: AccountState | None = None) -> dict:
    """signals: columns symbol, decision_time (UTC close time of the 5m signal candle), priority,
    plus optional metadata columns (signal_open_time, regime, ...). Must be within the segment.
    Returns dict(trades, rejections, events, state)."""
    any_bars = next(iter(bars.values()))
    if state is None:
        state = AccountState(cash=risk.initial_equity)
    else:
        state = copy.deepcopy(state)
    trades, rejections, events = [], [], []
    sig = signals.sort_values(["decision_time", "priority"], kind="mergesort").reset_index(drop=True)
    for row in sig.itertuples(index=False):
        sym = row.symbol
        b = bars[sym]
        dmin = int((row.decision_time - b.start).value // MIN_NS)
        ie = dmin + ex.delay_minutes
        rec = row._asdict()

        def reject(reason):
            rejections.append({**rec, "reason": reason, "entry_minute": ie})

        if dmin < 0:
            reject("before_segment"); continue
        if ie >= b.n:
            reject("entry_after_segment_end"); continue
        day = _day(b, ie)
        if state.day is None or day != state.day:
            # flat at this point (positions are fully simulated at entry), so day-start equity = cash
            if ie >= state.busy_until:
                state.day, state.day_start_equity = day, state.cash
        if ie < state.busy_until:
            same_time = dmin == state.last_entry_decision
            reject("concurrent_signal_lower_priority" if same_time else "position_open"); continue
        if ie < state.cooldown_until:
            reject("cooldown"); continue
        if risk.enabled and state.total_stopped:
            reject("total_loss_stop"); continue
        if risk.enabled and state.paused_day == day:
            reject("daily_loss_pause"); continue
        if not b.present(ie):
            reject("missing_entry_bar"); continue
        flt = ex.filters.get(sym, Filters())
        raw_entry = b.o[ie]
        fill_entry = round_up(raw_entry * (1 + ex.slip), flt.tick)
        budget = min(ex.stake, state.cash / (1 + ex.fee))
        qty = round_down(budget / fill_entry, flt.step) if flt.step else budget / fill_entry
        notional_in = qty * fill_entry
        if qty <= 0 or notional_in < flt.min_notional:
            reject("min_notional_or_insufficient_cash"); continue
        fee_in = notional_in * ex.fee
        cash_before = state.cash
        state.cash -= notional_in + fee_in
        assert state.cash >= -1e-9, "overdraft"
        t = _simulate_position(b, ie, qty, fill_entry, ex, risk, state, flt, events, sym)
        t.update({
            **{k: v for k, v in rec.items()},
            "entry_minute": ie, "entry_time": b.start + pd.Timedelta(minutes=ie),
            "raw_entry": raw_entry, "fill_entry": fill_entry, "qty": qty,
            "notional_in": notional_in, "fee_in": fee_in, "cash_before": cash_before,
        })
        t["net_pnl"] = t["cash_after"] - cash_before
        t["gross_pnl"] = qty * (t["raw_exit"] - raw_entry)
        t["fees"] = fee_in + t["fee_out"]
        t["slippage_cost"] = qty * (fill_entry - raw_entry) + qty * (t["raw_exit"] - t["fill_exit"])
        state.last_entry_decision = dmin
        trades.append(t)
    return {"trades": trades, "rejections": rejections, "events": events, "state": state}


def _simulate_position(b: Bars, ie: int, qty: float, fill_entry: float, ex: ExecParams, risk: RiskParams,
                       state: AccountState, flt: Filters, events: list, sym: str) -> dict:
    stop = fill_entry * (1 - ex.stop_pct)
    target = fill_entry * (1 + ex.target_pct)
    deadline = ie + ex.hold_minutes
    uncertain = False
    forced = None            # (reason) pending risk exit at next available open
    forced_day = None
    last_close_k = ie
    k = ie
    exit_k = raw_exit = reason = None
    intrabar = False
    first_after_gap_low = None
    min_low = np.inf
    while True:
        if k >= b.n:
            # boundary exit at last available close of the segment
            raw_exit, reason, exit_k = b.c[last_close_k], "boundary_exit", b.n
            break
        if not b.present(k):
            uncertain = True
            k += 1
            continue
        if uncertain and first_after_gap_low is None and k > ie:
            first_after_gap_low = b.l[k]
        # new UTC day while holding: reset day-start equity at this bar's open (mark-to-market)
        dk = _day(b, k)
        if dk != state.day:
            state.day = dk
            state.day_start_equity = state.cash + qty * b.o[k]
        if forced is not None:
            raw_exit, reason, exit_k = b.o[k], forced, k
            break
        if k >= deadline:
            raw_exit, exit_k = b.o[k], k
            reason = "time_exit" if k == deadline else "time_exit_after_gap"
            break
        if k > ie:
            if b.o[k] <= stop:
                raw_exit, reason, exit_k = b.o[k], "stop_gap", k
                break
            if b.o[k] >= target:
                raw_exit, reason, exit_k = target, "target_gap", k
                break
        min_low = min(min_low, b.l[k])
        if b.l[k] <= stop:
            raw_exit, reason, exit_k, intrabar = stop, "stop", k, True
            break
        if b.h[k] >= target:
            raw_exit, reason, exit_k, intrabar = target, "target", k, True
            break
        last_close_k = k
        if risk.enabled:
            mtm = state.cash + qty * b.c[k]
            if mtm <= state.day_start_equity - risk.daily_limit + 1e-12:
                forced = "risk_exit_daily"
            if mtm <= risk.initial_equity - risk.total_limit + 1e-12:
                forced = "risk_exit_total"
            if forced:
                forced_day = dk
                events.append({"time": b.start + pd.Timedelta(minutes=k), "event": forced + "_triggered",
                               "symbol": sym, "mtm_equity": mtm, "day_start_equity": state.day_start_equity})
        k += 1
    fill_exit = round_down(raw_exit * (1 - ex.slip), flt.tick)
    proceeds = qty * fill_exit
    fee_out = proceeds * ex.fee
    cash_after_entry = state.cash
    state.cash += proceeds - fee_out
    exit_time_k = exit_k + (1 if intrabar else 0)
    state.busy_until = exit_time_k
    state.cooldown_until = exit_time_k + ex.cooldown_minutes
    # post-execution risk check on realised equity
    exit_day = _day(b, min(exit_k, b.n - 1))
    if exit_day != state.day:
        state.day = exit_day
        state.day_start_equity = cash_after_entry + qty * b.c_ffill[min(exit_k, b.n - 1)]
    if risk.enabled:
        daily_floor = state.day_start_equity - risk.daily_limit
        total_floor = risk.initial_equity - risk.total_limit
        if state.cash <= daily_floor + 1e-12:
            if state.paused_day != exit_day:
                events.append({"time": b.start + pd.Timedelta(minutes=exit_time_k), "event": "daily_pause",
                               "symbol": sym, "equity": state.cash, "day_start_equity": state.day_start_equity,
                               "exceeded_by": daily_floor - state.cash})
            state.paused_day = exit_day
        if state.cash <= total_floor + 1e-12 and not state.total_stopped:
            state.total_stopped = True
            events.append({"time": b.start + pd.Timedelta(minutes=exit_time_k), "event": "total_stop",
                           "symbol": sym, "equity": state.cash, "exceeded_by": total_floor - state.cash})
    if forced == "risk_exit_daily":
        state.paused_day = forced_day
    if forced == "risk_exit_total":
        state.total_stopped = True
    # conservative scenario for trades spanning missing data
    cons_raw = raw_exit
    if uncertain and first_after_gap_low is not None:
        cons_raw = min(raw_exit, first_after_gap_low)
    cons_fill = round_down(cons_raw * (1 - ex.slip), flt.tick)
    cons_net_delta = qty * (cons_fill - fill_exit) * (1 - ex.fee)
    return {
        "exit_minute": exit_k, "exit_time": b.start + pd.Timedelta(minutes=exit_time_k),
        "exit_reason": reason, "raw_exit": raw_exit, "fill_exit": fill_exit, "fee_out": fee_out,
        "notional_out": proceeds, "cash_after_entry": cash_after_entry, "cash_after": state.cash,
        "stop_level": stop, "target_level": target, "uncertain_gap": uncertain,
        "conservative_net_delta": cons_net_delta, "hold_minutes_actual": exit_time_k - ie,
    }


def equity_curve(trades: list[dict], bars: dict[str, Bars], initial: float) -> pd.Series:
    """1m mark-to-market equity (at each bar close) over the segment grid."""
    b0 = next(iter(bars.values()))
    eq = np.full(b0.n, initial, dtype=float)
    level = initial
    pos = 0
    for t in sorted(trades, key=lambda x: x["entry_minute"]):
        ie = t["entry_minute"]
        x = min(t["exit_minute"], b0.n)
        eq[pos:ie] = level
        mtm = t["cash_after_entry"] + t["qty"] * bars[t["symbol"]].c_ffill[ie:x]
        eq[ie:x] = mtm
        level = t["cash_after"]
        pos = x
    eq[pos:] = level
    return pd.Series(eq, index=pd.date_range(b0.start, b0.end, freq="min", inclusive="left") +
                     pd.Timedelta(minutes=1), name="equity")  # stamped at bar close
