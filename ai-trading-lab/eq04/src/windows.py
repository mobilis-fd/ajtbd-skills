"""EQ04 calendar layer: event windows, matched controls, overlap flags. Uses NO prices.

All windows are (entry_idx, exit_idx) in the realised XNYS session list of the frozen v0.3-pre inputs.
Entry = open of the first session strictly after the auction date; exit = close of the h-th session
counted from the entry session (entry = session 1). Primary h = 5; h = 1, 3 diagnostic only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

H_PRIMARY = 5
H_DIAG = (1, 3)


def event_windows(sessions: pd.DatetimeIndex, events: pd.DataFrame, h: int) -> pd.DataFrame:
    rows = []
    last = len(sessions) - 1
    for r in events.itertuples():
        a = pd.Timestamp(r.auction_date)
        e = int(np.searchsorted(sessions.values, np.datetime64(a), side='right'))  # first session > auction date
        x = e + h - 1
        if e > last or x > last:
            continue
        rows.append({'cusip': r.cusip, 'auction_date': a, 'reopening': r.reopening, 'entry_idx': e, 'exit_idx': x,
                     'entry_date': sessions[e], 'exit_date': sessions[x],
                     'auction_is_session': bool(a in sessions)})
    return pd.DataFrame(rows)


def blocked_mask(n_sessions: int, ev: pd.DataFrame) -> np.ndarray:
    """True for sessions inside any primary (h=5) event window."""
    b = np.zeros(n_sessions, bool)
    for e, x in zip(ev.entry_idx, ev.exit_idx):
        b[e:x + 1] = True
    return b


def controls_for(sessions: pd.DatetimeIndex, ev_row, blocked: np.ndarray, h: int) -> list[int]:
    """Control entry indices for one event: same calendar year-month and weekday of the entry date,
    same length h in sessions, window entirely inside the data, no session in any primary event window."""
    e = int(ev_row.entry_idx)
    d = sessions[e]
    ym = sessions.to_period('M')
    cand = np.flatnonzero((ym == d.to_period('M')) & (sessions.weekday == d.weekday()))
    out = []
    for k in cand:
        x = k + h - 1
        if x >= len(sessions):
            continue
        if blocked[k:x + 1].any():
            continue
        out.append(int(k))
    return out


def month_end_sets(sessions: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """(eq03_mask, turn_of_month_mask): EQ03 window = last five sessions of each calendar month (v0.3-pre
    realised convention); turn of month = last five sessions of a month plus first three of the next."""
    ym = sessions.to_period('M')
    eq03 = np.zeros(len(sessions), bool)
    tom = np.zeros(len(sessions), bool)
    for m in ym.unique():
        ids = np.flatnonzero(ym == m)
        eq03[ids[-5:]] = True
        tom[ids[-5:]] = True
        tom[ids[:3]] = True
    return eq03, tom


def window_flags(sessions: pd.DatetimeIndex, e: int, x: int, eq03: np.ndarray, tom: np.ndarray,
                 macro: dict[str, set]) -> dict:
    """Overlap flags for a window [e, x]. Macro releases count if the release date is a session in the
    window (all are 08:30 ET or 14:00 ET releases, i.e. inside the open-to-close holding period of the
    window except an 08:30 release on the entry day, which is before the entry open -> excluded on e)."""
    days = set(sessions[e:x + 1])
    pre_open = set(sessions[e + 1:x + 1])           # 08:30 releases after the entry open
    return {'ovl_eq03': bool(eq03[e:x + 1].any()), 'ovl_turn_of_month': bool(tom[e:x + 1].any()),
            'has_fomc': bool(days & macro['FOMC']), 'has_cpi': bool(pre_open & macro['CPI']),
            'has_nfp': bool(pre_open & macro['NFP'])}
