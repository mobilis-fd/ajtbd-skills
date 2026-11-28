"""EQ04-A historical screen: IEF after 10-year nominal Treasury note auctions. Frozen by PROTOCOL.md.

Usage: python -I run_screen.py --events EVENTS_CSV --data V03PRE_DATA_DIR --irx IRX_JSON --macro MACRO_CSV
                               --synthetic SYNTHETIC_JSON --out OUT_DIR
Prices: total-return adjusted IEF open/close from the frozen v0.3-pre inputs (Yahoo; S1 = Nasdaq-corrected).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eq04_stats import METHODS, holm  # noqa: E402
from prereg_check import period_of  # noqa: E402
from windows import (H_DIAG, H_PRIMARY, blocked_mask, controls_for, event_windows, month_end_sets,  # noqa: E402
                     window_flags)

COSTS = (0, 5, 10, 25, 40)        # round-trip bps, half on entry, half on exit value
BASE_COST = 10
PERIODS = ('P1_2002_2009', 'P2_2010_2019', 'P3_2020_2026')
NASDAQ_VERIFIED_FROM = pd.Timestamp('2016-11-25')   # v0.3-pre second-source window (AUDIT.md D1)
B = 4999
SEED = 20261128


def net(g, c):
    f = c / 20000.0
    return g - f * (2 + g)


def load_prices(data_dir: Path, variant: str):
    base = data_dir / ('inputs' if variant == 'primary' else 'inputs_S1')
    sessions = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(data_dir / 'inputs' / 'sessions.csv')['date']))
    px = pd.read_csv(base / 'IEF.csv', parse_dates=['date']).set_index('date')
    if not pd.DatetimeIndex(px.index).equals(sessions):
        raise ValueError('IEF rows do not match the session calendar')
    raw = pd.read_csv(data_dir / 'inputs' / 'IEF_raw_parsed.csv', parse_dates=['date']).set_index('date')
    o, c = raw['open'].to_numpy(float), raw['close'].to_numpy(float)
    prev_c = np.r_[np.nan, c[:-1]]
    stale = (np.abs(o - prev_c) < 1e-9) | (np.abs(o - c) < 1e-9)   # heuristic stale-open flag (v0.3-pre data_qa)
    return sessions, px['adj_open'].to_numpy(float), px['adj_close'].to_numpy(float), stale


def load_irx(path: Path, sessions: pd.DatetimeIndex) -> np.ndarray:
    """Same rule as eq03_pv01/src/pv_data.load_irx: as-of last published value, percent -> decimal."""
    j = json.loads(Path(path).read_text())['chart']['result'][0]
    ts = pd.to_datetime(j['timestamp'], unit='s', utc=True).tz_convert(j['meta']['exchangeTimezoneName'])
    s = pd.Series(j['indicators']['quote'][0]['close'], index=pd.DatetimeIndex(ts.date), dtype=float)
    s = s[~s.index.duplicated(keep='last')].sort_index()
    return s.reindex(sessions).ffill().to_numpy() / 100.0


def build_table(events, sessions, ao, ac, rf, stale, macro, h):
    ev5 = event_windows(sessions, events, H_PRIMARY)
    blocked = blocked_mask(len(sessions), ev5)
    eq03, tom = month_end_sets(sessions)
    evh = event_windows(sessions, events, h)
    rows = []
    for r in evh.itertuples():
        e, x = r.entry_idx, r.exit_idx
        g = ac[x] / ao[e] - 1
        cash = rf[e - 1] * h / 252.0
        ctl = controls_for(sessions, r, blocked, h)
        ctl_nt = [k for k in ctl if not tom[k:k + h].any()]
        gc = np.array([ac[k + h - 1] / ao[k] - 1 for k in ctl])
        gnt = np.array([ac[k + h - 1] / ao[k] - 1 for k in ctl_nt])
        cfl = [window_flags(sessions, k, k + h - 1, eq03, tom, macro) for k in ctl]
        f = window_flags(sessions, e, x, eq03, tom, macro)
        row = {'auction_date': r.auction_date, 'cusip': r.cusip, 'reopening': r.reopening,
               'entry_date': r.entry_date, 'exit_date': r.exit_date, 'period': period_of(r.auction_date),
               'g_event': g, 'cash': cash, 'n_ctl': len(ctl), 'g_ctl_mean': gc.mean() if len(gc) else np.nan,
               'n_ctl_no_tom': len(ctl_nt), 'g_ctl_no_tom_mean': gnt.mean() if len(gnt) else np.nan,
               'ctl_share_fomc': np.mean([z['has_fomc'] for z in cfl]) if cfl else np.nan,
               'ctl_share_cpi': np.mean([z['has_cpi'] for z in cfl]) if cfl else np.nan,
               'ctl_share_nfp': np.mean([z['has_nfp'] for z in cfl]) if cfl else np.nan,
               'ctl_share_tom': np.mean([z['ovl_turn_of_month'] for z in cfl]) if cfl else np.nan,
               'entry_stale_open_flag': bool(stale[e]), 'nasdaq_verified': bool(r.entry_date >= NASDAQ_VERIFIED_FROM),
               **f}
        for c in COSTS:
            row[f'net_{c}'] = net(g, c)
            row[f'exc_{c}'] = net(g, c) - cash
            row[f'ctl_net_{c}'] = np.mean([net(v, c) for v in gc]) if len(gc) else np.nan
            row[f'd_net_{c}'] = row[f'net_{c}'] - row[f'ctl_net_{c}']
        row['d_gross'] = g - row['g_ctl_mean']
        row['d_gross_no_tom'] = g - row['g_ctl_no_tom_mean']
        rows.append(row)
    return pd.DataFrame(rows)


def test(x, method):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 12:
        return {'n': len(x), 'mean_bps': float(x.mean() * 1e4) if len(x) else None, 'p': None, 'ci_lo_bps': None, 'ci_hi_bps': None}
    kw = {'B': B, 'seed': SEED} if 'cbb' in method else {}
    p, lo, hi = METHODS[method](x, **kw)
    return {'n': int(len(x)), 'mean_bps': float(x.mean() * 1e4), 'median_bps': float(np.median(x) * 1e4),
            'hit_rate': float((x > 0).mean()), 'p': float(p), 'ci_lo_bps': float(lo * 1e4), 'ci_hi_bps': float(hi * 1e4)}


def summarise(t, method):
    out = {}
    groups = {'ALL': t, **{p: t[t.period == p] for p in PERIODS}}
    for gname, g in groups.items():
        cell = {'primary_d_gross': test(g.d_gross, method)}
        for c in COSTS:
            cell[f'cost_{c}'] = {'event_net': test(g[f'net_{c}'], method), 'event_excess_cash': test(g[f'exc_{c}'], method),
                                 'control_net_mean_bps': float(g[f'ctl_net_{c}'].mean() * 1e4),
                                 'delta_net': test(g[f'd_net_{c}'], method)}
        out[gname] = cell
    return out


def verdict(main, rob):
    a = main['ALL']
    p = a['primary_d_gross']['p']; d = a['primary_d_gross']['mean_bps']
    exc = a[f'cost_{BASE_COST}']['event_excess_cash']['mean_bps']
    per_pos = all(main[pp]['primary_d_gross']['mean_bps'] > 0 for pp in PERIODS)
    rob_pos = all(v > 0 for v in rob.values())
    if p is not None and p < 0.05 and d > 0 and exc > 0 and per_pos and rob_pos:
        v = 'CANDIDATE'
    elif (p is None or p >= 0.20) or exc <= 0:
        v = 'NEGATIVE'
    else:
        v = 'INCONCLUSIVE'
    return {'verdict': v, 'primary_p': p, 'primary_mean_d_bps': d, 'excess_cash_10bps_mean_bps': exc,
            'all_periods_d_positive': per_pos, 'robustness_d_positive': rob, 'robustness_all_positive': rob_pos}


def main():
    ap = argparse.ArgumentParser()
    for k in ('events', 'data', 'irx', 'macro', 'synthetic', 'out'):
        ap.add_argument(f'--{k}', type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    method = json.loads(a.synthetic.read_text())['selected_primary_method']
    events = pd.read_csv(a.events, parse_dates=['auction_date'])
    mc = pd.read_csv(a.macro, parse_dates=['date'])
    macro = {k: set(g.date) for k, g in mc.groupby('kind')}
    res = {'method': method, 'B': B, 'seed': SEED, 'costs_bps': COSTS, 'base_cost_bps': BASE_COST}
    tables = {}
    for variant in ('primary', 'S1'):
        sessions, ao, ac, stale = load_prices(a.data, variant)
        rf = load_irx(a.irx, sessions)
        for h in (H_PRIMARY, *H_DIAG):
            t = build_table(events, sessions, ao, ac, rf, stale, macro, h)
            tables[(variant, h)] = t
            t.to_csv(a.out / f'events_{variant}_h{h}.csv', index=False, date_format='%Y-%m-%d', float_format='%.8f')
            res[f'{variant}_h{h}'] = summarise(t, method)
    t = tables[('primary', H_PRIMARY)]
    # pre-registered robustness / diagnostics (PROTOCOL.md §7)
    nt = t[t.n_ctl_no_tom > 0]
    diag = {
        'R1_S1_nasdaq_opens': test(tables[('S1', H_PRIMARY)].d_gross, method),
        'R2_controls_without_turn_of_month': test(nt.d_gross_no_tom, method),
        'R2_events_without_tom_free_control': int((t.n_ctl_no_tom == 0).sum()),
        'R3_events_overlapping_eq03': int(t.ovl_eq03.sum()),
        'R4_events_nasdaq_verified_period': test(t[t.nasdaq_verified].d_gross, method),
        'R4_events_unverified_period': test(t[~t.nasdaq_verified].d_gross, method),
        'R5_entry_stale_open_flagged_events': int(t.entry_stale_open_flag.sum()),
        'R5_excluding_stale_flagged': test(t[~t.entry_stale_open_flag].d_gross, method),
        'M_fomc_in_window': test(t[t.has_fomc].d_gross, method),
        'M_no_fomc': test(t[~t.has_fomc].d_gross, method),
        'M_cpi_in_window': test(t[t.has_cpi].d_gross, method),
        'M_no_cpi': test(t[~t.has_cpi].d_gross, method),
        'M_no_fomc_cpi_nfp': test(t[~(t.has_fomc | t.has_cpi | t.has_nfp)].d_gross, method),
        'M_event_share': {k: float(t[k].mean()) for k in ('has_fomc', 'has_cpi', 'has_nfp')},
        'M_control_share': {k: float(t[f'ctl_share_{k[4:]}'].mean()) for k in ('has_fomc', 'has_cpi', 'has_nfp')},
        'C_control_share_tom': float(t.ctl_share_tom.mean()),
        'T_original_issues': test(t[t.reopening == 'No'].d_gross, method),
        'T_reopenings': test(t[t.reopening == 'Yes'].d_gross, method),
        'Holm_periods_primary': holm({p: res['primary_h5'][p]['primary_d_gross']['p'] for p in PERIODS}),
        'other_methods_primary': {m: dict(zip(('p', 'lo', 'hi'), METHODS[m](t.d_gross.to_numpy(), **({'B': B, 'seed': SEED} if 'cbb' in m else {}))))
                                  for m in METHODS},
    }
    res['diagnostics'] = diag
    rob = {'R1_S1': diag['R1_S1_nasdaq_opens']['mean_bps'], 'R2_no_tom_controls': diag['R2_controls_without_turn_of_month']['mean_bps'],
           'R5_no_stale': diag['R5_excluding_stale_flagged']['mean_bps']}
    res['verdict'] = verdict(res['primary_h5'], rob)
    (a.out / 'summary.json').write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res['verdict'], indent=2))


if __name__ == '__main__':
    main()
