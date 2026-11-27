"""EQ03-PV01 data layer: raw TLT prices, cash dividends, risk-free proxy, point-in-time calendar.

No network access. Reads the frozen v0.3-pre inputs (Yahoo, already explored) plus the Yahoo ^IRX file
downloaded for this experiment. Prices are UNADJUSTED (Yahoo `open`/`close`; TLT has no splits in the
period), dividends are credited explicitly as cash, so nothing is counted twice.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Unscheduled (ad hoc) NYSE closures inside the data window, from exchange_calendars XNYS.adhoc_holidays
# (cross-checked with pandas_market_calendars in v0.3-pre). Point-in-time rule: a closure is treated as
# unknown to the trader at any decision time before the closure date itself (conservative: real
# announcements came 1-6 days earlier; only the order "decision before closure" matters, see PROTOCOL §6).
ADHOC_CLOSURES = pd.DatetimeIndex(['2004-06-11', '2007-01-02', '2012-10-29', '2012-10-30',
                                   '2018-12-05', '2025-01-09'])

# US equity settlement cycle by trade date (SEC rules): T+3 until 2017-09-04, T+2 from 2017-09-05,
# T+1 from 2024-05-28. Counted in exchange sessions (approximation: bank holidays differ slightly).
def settlement_lag(trade_date: pd.Timestamp) -> int:
    if trade_date >= pd.Timestamp('2024-05-28'):
        return 1
    if trade_date >= pd.Timestamp('2017-09-05'):
        return 2
    return 3


@dataclass
class Market:
    sessions: pd.DatetimeIndex          # realised XNYS sessions
    open: np.ndarray                    # raw TLT open
    close: np.ndarray                   # raw TLT close
    div: np.ndarray                     # cash dividend per share with ex-date on this session (0 otherwise)
    rf: np.ndarray                      # annualised risk-free proxy (decimal) known at this session's close
    adj_open: np.ndarray | None = None  # v0.3-pre adjusted series, only for reconciliation
    adj_close: np.ndarray | None = None


def _read_dates(path: Path) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(pd.read_csv(path)['date'], format='%Y-%m-%d'))


def load_irx(path: Path, sessions: pd.DatetimeIndex) -> tuple[np.ndarray, dict]:
    """Yahoo ^IRX (13-week T-bill discount yield, percent) -> decimal per session.

    Missing values (6 sessions) take the last published value strictly before the session (as-of, no
    look-ahead). Negative prints (2008-2015 lows, min -0.105) are kept: they are the published index.
    """
    j = json.loads(Path(path).read_text())['chart']['result'][0]
    ts = pd.to_datetime(j['timestamp'], unit='s', utc=True).tz_convert(j['meta']['exchangeTimezoneName'])
    s = pd.Series(j['indicators']['quote'][0]['close'], index=pd.DatetimeIndex(ts.date), dtype=float)
    s = s[~s.index.duplicated(keep='last')].sort_index()
    raw = s.reindex(sessions)
    qa = {'irx_sessions_missing': int(raw.isna().sum()),
          'irx_missing_dates': [str(d.date()) for d in raw.index[raw.isna()]],
          'irx_min_pct': float(s.min()), 'irx_max_pct': float(s.max())}
    filled = raw.ffill()
    if filled.isna().any():
        raise ValueError('risk-free proxy missing at start of sample')
    return filled.to_numpy() / 100.0, qa


def load_market(data_dir: Path, rf_file: Path, variant: str = 'primary') -> tuple[Market, dict]:
    """variant 'primary' = Yahoo inputs; 'S1' = v0.3-pre S1 opens (3 TLT opens replaced by Nasdaq)."""
    data_dir = Path(data_dir)
    inp = data_dir / 'inputs'
    sessions = _read_dates(inp / 'sessions.csv')
    raw = pd.read_csv(inp / 'TLT_raw_parsed.csv', parse_dates=['date']).set_index('date')
    raw.index = pd.DatetimeIndex(raw.index)
    if not raw.index.equals(sessions):
        raise ValueError('TLT raw rows do not match the session calendar')
    o, c = raw['open'].to_numpy(float), raw['close'].to_numpy(float)
    adj = pd.read_csv(inp / 'TLT.csv', parse_dates=['date']).set_index('date')
    if variant == 'S1':
        s1 = pd.read_csv(data_dir / 'inputs_S1' / 'TLT.csv', parse_dates=['date']).set_index('date')
        ratio = raw['adjclose'].to_numpy(float) / c
        o = s1['adj_open'].to_numpy(float) / ratio  # back out the raw open; close unchanged in S1
        adj = s1
    elif variant != 'primary':
        raise ValueError(variant)
    if not (np.isfinite(o).all() and np.isfinite(c).all() and (o > 0).all() and (c > 0).all()):
        raise ValueError('invalid TLT price')
    dv = pd.read_csv(inp / 'TLT_dividends.csv', parse_dates=['date'])
    div = pd.Series(0.0, index=sessions)
    for d, a in zip(dv['date'], dv['amount']):
        d = pd.Timestamp(d)
        if d not in div.index:
            raise ValueError(f'dividend ex-date {d.date()} is not a session')
        div[d] += float(a)
    rf, qa = load_irx(rf_file, sessions)
    m = Market(sessions, o, c, div.to_numpy(), rf, adj['adj_open'].to_numpy(float), adj['adj_close'].to_numpy(float))
    qa.update({'sessions': len(sessions), 'first': str(sessions[0].date()), 'last': str(sessions[-1].date()),
               'dividend_events': int((m.div > 0).sum()), 'variant': variant})
    return m, qa


# ---------------------------------------------------------------- point-in-time calendar
def known_future_sessions(sessions: pd.DatetimeIndex, asof_idx: int, month_end: pd.Timestamp) -> int:
    """Number of sessions AFTER sessions[asof_idx] up to month_end that a trader expects at the
    decision time (before the open of sessions[asof_idx]).

    Expected = realised future sessions plus ad hoc closures not yet known (closure date > asof).
    Uses only: the realised calendar up to and including asof (known), the regular holiday schedule
    (embedded in the realised calendar for dates without an ad hoc closure), and the rule that an ad hoc
    closure is unknown before it happens. Equivalent to the exchange's announced schedule at asof.
    """
    t = sessions[asof_idx]
    fut = sessions[(sessions > t) & (sessions <= month_end)]
    hidden = ADHOC_CLOSURES[(ADHOC_CLOSURES > t) & (ADHOC_CLOSURES <= month_end)]
    return len(fut) + len(hidden)


def eq03_trades(sessions: pd.DatetimeIndex, mode: str = 'pit') -> list[tuple[int, int, str]]:
    """EQ03 trade list [(entry_idx, exit_idx, month)].

    Rule (frozen): buy at the open of the fifth-from-last session of the calendar month, sell at the
    close of the last session. mode 'pit': decisions use the point-in-time schedule (enter at the first
    session whose expected number of remaining sessions in the month is <= 4; exit at the close of the
    first session that is, as known at that close, the last expected session of the month, or the next
    session if the planned exit day was cancelled). mode 'realised': v0.3-pre convention (realised
    calendar, i = last-4, j = last), kept only for the look-ahead comparison.
    """
    months = sessions.to_period('M')
    out = []
    for m in months.unique():
        ids = np.flatnonzero(months == m)
        if len(ids) < 15:
            continue  # same guard as v0.3-pre (first/last partial months)
        a, b = int(ids[0]), int(ids[-1])
        if mode == 'realised':
            out.append((b - 4, b, str(m)))
            continue
        month_end = m.to_timestamp(how='end').normalize()
        entry = next((k for k in range(a, b + 1)
                      if known_future_sessions(sessions, k, month_end) <= 4), None)
        if entry is None:
            continue
        exit_ = None
        for k in range(entry, len(sessions)):
            # at the close of k the trader knows whether any later session in the month is still expected
            if sessions[k] > month_end or known_future_sessions(sessions, k, month_end) == 0:
                exit_ = k
                break
        if exit_ is None or exit_ >= len(sessions):
            continue
        out.append((entry, exit_, str(m)))
    return out
