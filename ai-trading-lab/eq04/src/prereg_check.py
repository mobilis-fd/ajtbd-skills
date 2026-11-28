"""EQ04 pre-registration check (NO prices): event windows, control availability, overlap counts.

Usage: python -I prereg_check.py EVENTS_CSV SESSIONS_CSV MACRO_CSV OUT_DIR [DATA_END]
Run and committed before any return is computed (PROTOCOL.md §4).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from windows import (H_PRIMARY, blocked_mask, controls_for, event_windows, month_end_sets,  # noqa: E402
                     window_flags)


def load_calendar(sessions_csv, macro_csv):
    sessions = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(sessions_csv)['date']))
    mc = pd.read_csv(macro_csv, parse_dates=['date'])
    macro = {k: set(g.date) for k, g in mc.groupby('kind')}
    return sessions, macro


def period_of(d: pd.Timestamp) -> str:
    return 'P1_2002_2009' if d.year < 2010 else ('P2_2010_2019' if d.year < 2020 else 'P3_2020_2026')


def build(events_csv, sessions_csv, macro_csv):
    ev = pd.read_csv(events_csv, parse_dates=['auction_date'])
    sessions, macro = load_calendar(sessions_csv, macro_csv)
    w = event_windows(sessions, ev, H_PRIMARY)
    blocked = blocked_mask(len(sessions), w)
    eq03, tom = month_end_sets(sessions)
    rows = []
    for r in w.itertuples():
        ctl = controls_for(sessions, r, blocked, H_PRIMARY)
        ctl_clean = [k for k in ctl if not tom[k:k + H_PRIMARY].any()]
        f = window_flags(sessions, r.entry_idx, r.exit_idx, eq03, tom, macro)
        rows.append({**r._asdict(), 'period': period_of(r.auction_date), 'n_controls': len(ctl),
                     'controls': ' '.join(str(k) for k in ctl), 'n_controls_no_tom': len(ctl_clean),
                     'controls_no_tom': ' '.join(str(k) for k in ctl_clean),
                     'entry_weekday': r.entry_date.day_name(), **f})
    return pd.DataFrame(rows).drop(columns=['Index']), sessions, macro


def main():
    events_csv, sessions_csv, macro_csv, out = sys.argv[1:5]
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    t, sessions, _ = build(events_csv, sessions_csv, macro_csv)
    ev = pd.read_csv(events_csv)
    qa = {'events_in_list': len(ev), 'events_with_complete_window_h5': len(t),
          'dropped_incomplete_window': sorted(set(ev.auction_date) - set(t.auction_date.dt.strftime('%Y-%m-%d'))),
          'data_last_session': str(sessions[-1].date()),
          'auction_date_not_a_session': int((~t.auction_is_session).sum()),
          'entry_gap_sessions_max': None,
          'by_period': t.period.value_counts().sort_index().to_dict(),
          'entry_weekday': t.entry_weekday.value_counts().to_dict(),
          'controls_per_event': t.n_controls.value_counts().sort_index().to_dict(),
          'events_without_controls': t.loc[t.n_controls == 0, 'auction_date'].dt.strftime('%Y-%m-%d').tolist(),
          'controls_no_tom_per_event': t.n_controls_no_tom.value_counts().sort_index().to_dict(),
          'events_without_controls_no_tom': int((t.n_controls_no_tom == 0).sum()),
          'events_overlapping_eq03_window': int(t.ovl_eq03.sum()),
          'events_overlapping_turn_of_month': int(t.ovl_turn_of_month.sum()),
          'events_with_fomc': int(t.has_fomc.sum()), 'events_with_cpi_after_entry_open': int(t.has_cpi.sum()),
          'events_with_nfp_after_entry_open': int(t.has_nfp.sum()),
          'events_with_any_macro': int((t.has_fomc | t.has_cpi | t.has_nfp).sum()),
          'overlapping_event_windows': int((t.entry_idx.values[1:] <= t.exit_idx.values[:-1]).sum())}
    t.to_csv(out / 'event_windows_controls.csv', index=False, date_format='%Y-%m-%d')
    (out / 'prereg_check.json').write_text(json.dumps(qa, indent=2, default=str))
    print(json.dumps(qa, indent=2, default=str))


if __name__ == '__main__':
    main()
