"""EQ03-PV01 historical portfolio replay (DIAGNOSTIC on already-explored data, not validation).

Usage: python -I run_replay.py --data ../../data/equity_v03pre --rf ../../data/eq03_pv01/raw/yahoo_IRX.json \
          --screen-events ../../equity_v03pre/reports/run01_primary/events_exploratory.csv --out ../reports/run01
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pv_stats  # noqa: E402
from pv_data import eq03_trades, load_market  # noqa: E402
from pv_engine import Scenario, run  # noqa: E402

PERIODS = {'T3': ('2003-01-01', '2016-12-31'), 'T2': ('2017-10-01', '2024-04-30'),
           'T1': ('2024-06-01', '2026-10-31'), 'FULL': ('2003-01-01', '2026-10-31')}
TESTED = ['T3', 'T2', 'T1']
BPS = [0, 5, 10, 25, 40]
FEES = [0.0, 0.01, 0.35, 1.00, 2.00, 5.00]
STEPS = [1e-4, 1.0]
BASE = Scenario()                       # 10 bps RT, $0 fee, fractional 1e-4, idle cash at rf, pay lag 3
N_RANDOM = 1000
SEED = 20261129
BOOT_B = 1999


def span(m, p):
    s, e = PERIODS[p]
    idx = np.flatnonzero((m.sessions >= s) & (m.sessions <= e))
    return int(idx[0]), int(idx[-1])


def monthly_returns(res):
    eq = pd.Series(res.equity, index=res.dates)
    last = eq.groupby(eq.index.to_period('M')).last()
    prev = last.shift(1); prev.iloc[0] = 100.0  # capital before the first session (start = open of day 1)
    return last / prev - 1


def metrics(res, cash_rf, sc_capital=100.0):
    eq = res.equity; d = res.dates
    years = (d[-1] - d[0]).days / 365.25
    r = np.diff(np.concatenate([[sc_capital], eq])) / np.concatenate([[sc_capital], eq[:-1]])
    rf = np.diff(np.concatenate([[sc_capital], cash_rf.equity])) / np.concatenate([[sc_capital], cash_rf.equity[:-1]])
    ex = r - rf
    sd = ex.std(ddof=1); dn = np.sqrt(np.mean(np.minimum(ex, 0) ** 2))
    peak = np.maximum.accumulate(np.concatenate([[sc_capital], eq]))
    dd = (np.concatenate([[sc_capital], eq]) / peak - 1).min()
    mr = monthly_returns(res)
    worst = mr.nsmallest(3)
    final = float(eq[-1])
    return {
        'final_equity': final, 'net_pnl': final - sc_capital,
        'cagr_pct': ((final / sc_capital) ** (1 / years) - 1) * 100,
        'excess_pnl_vs_cash_rf': final - float(cash_rf.equity[-1]),
        'excess_cagr_vs_cash_rf_pct': (((final / sc_capital) ** (1 / years)) -
                                       ((cash_rf.equity[-1] / sc_capital) ** (1 / years))) * 100,
        'max_drawdown_pct': dd * 100,
        'sharpe_excess_ann': float(ex.mean() / sd * np.sqrt(252)) if sd > 0 else None,
        'sortino_excess_ann': float(ex.mean() / dn * np.sqrt(252)) if dn > 0 else None,
        'exposure_sessions_pct': float((res.position_value > 0).mean() * 100),
        'avg_invested_pct_of_equity': float((res.position_value / eq).mean() * 100),
        'turnover_x_per_year': res.traded_notional / float(np.mean(eq)) / years,
        'trades': len(res.trades), 'skipped_entries': len(res.skipped), 'cash_shortfalls': res.cash_shortfalls,
        'fees_paid': res.fees_paid, 'bps_costs_paid': res.bps_paid, 'dividends_received': res.dividends_received,
        'worst_months': [[str(k), round(v * 100, 3)] for k, v in worst.items()],
        'years': years,
    }


def random_windows(m, start, end, strat_trades, n_sims, seed):
    """One random 5-session window per traded month, wholly inside the month, different from the rule's
    window (same holding length, same sizing => comparable exposure)."""
    months = m.sessions.to_period('M')
    rng = np.random.default_rng(seed)
    choices = []
    for (i, j, mon) in strat_trades:
        if i < start or j > end:
            continue
        ids = np.flatnonzero(months == pd.Period(mon))
        ks = [k for k in range(int(ids[0]), int(ids[-1]) - 3) if k != i]
        choices.append((ks, mon))
    for _ in range(n_sims):
        yield [(k, k + 4, mon) for ks, mon in choices for k in [ks[rng.integers(len(ks))]]]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True); ap.add_argument('--rf', type=Path, required=True)
    ap.add_argument('--screen-events', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--method', default=None, help='primary test; default: read from synthetic_study.json')
    ap.add_argument('--synthetic', type=Path, default=Path(__file__).resolve().parent.parent / 'reports/synthetic/synthetic_study.json')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    method = a.method or json.loads(a.synthetic.read_text())['selected_primary_method']
    m, qa = load_market(a.data, a.rf, 'primary')
    trades = eq03_trades(m.sessions, 'pit')
    trades_real = eq03_trades(m.sessions, 'realised')
    out = {'status': 'EQ03-PV01 historical portfolio replay: DIAGNOSTIC on already-explored data; not independent validation; no trading approval',
           'primary_method': method, 'base_scenario': asdict(BASE), 'data_qa': qa,
           'env': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__},
           'input_sha256': {p.name: sha(p) for p in [a.data / 'inputs/sessions.csv', a.data / 'inputs/TLT_raw_parsed.csv',
                                                     a.data / 'inputs/TLT_dividends.csv', a.data / 'inputs/TLT.csv',
                                                     a.data / 'inputs_S1/TLT.csv', a.rf]},
           'code_sha256': {p.name: sha(p) for p in sorted(Path(__file__).resolve().parent.glob('*.py'))}}

    # ---- 1. calendar look-ahead check
    diff = [{'month': t[2], 'pit_entry': str(m.sessions[t[0]].date()), 'pit_exit': str(m.sessions[t[1]].date()),
             'realised_entry': str(m.sessions[r[0]].date()), 'realised_exit': str(m.sessions[r[1]].date())}
            for t, r in zip(trades, trades_real) if t[:2] != r[:2]]
    assert [t[2] for t in trades] == [r[2] for r in trades_real]
    out['calendar_check'] = {'months': len(trades), 'months_differing': diff}

    # ---- 2. reconciliation with the v0.3-pre screen (frictionless, realised calendar)
    ev = pd.read_csv(a.screen_events); ev = ev[ev.hypothesis == 'EQ03'].set_index('month')
    fr = Scenario(bps_rt=0, fee=0, share_step=1e-12, idle_rf=False, pay_lag=0, max_position=50)
    rr = run(m, 0, len(m.sessions) - 1, trades_real, fr)
    rec = pd.DataFrame([{'month': t['month'], 'engine_ret': t['ret'], 'screen_gross': ev.loc[t['month'], 'gross'],
                         'div': t['div']} for t in rr.trades if t['month'] in ev.index])
    rec['diff'] = rec.engine_ret - rec.screen_gross
    rec.to_csv(a.out / 'reconciliation_vs_screen.csv', index=False)
    out['reconciliation'] = {'events': len(rec), 'max_abs_diff_no_div': float(rec[rec['div'] == 0]['diff'].abs().max()),
                             'events_with_div': int((rec['div'] > 0).sum()),
                             'max_abs_diff_with_div': float(rec[rec['div'] > 0]['diff'].abs().max()) if (rec['div'] > 0).any() else 0.0}

    # ---- 3. scenario grid per period
    grid_rows, trades_rows, base = [], [], {}
    for p in PERIODS:
        s, e = span(m, p)
        for idle in (True, False):
            cash = run(m, s, e, [], Scenario(idle_rf=idle))
            cash_rf = run(m, s, e, [], Scenario(idle_rf=True))
            grid_rows.append({'period': p, 'model': 'cash_rf' if idle else 'cash_0', **metrics(cash, cash_rf)})
        cash_rf = run(m, s, e, [], Scenario(idle_rf=True))
        for bps, fee, step, idle in itertools.product(BPS, FEES, STEPS, (True, False)):
            sc = replace(BASE, bps_rt=bps, fee=fee, share_step=step, idle_rf=idle)
            for model, tl in (('EQ03', trades), ('BH_TLT_50', [(s, e, 'bh')])):
                if model == 'BH_TLT_50' and (fee not in (0.0, 1.00) or step != 1e-4):
                    continue
                r = run(m, s, e, tl, sc)
                row = {'period': p, 'model': model, 'scenario': sc.label(), 'bps_rt': bps, 'fee': fee,
                       'fractional': step < 1, 'idle_rf': idle, **metrics(r, cash_rf)}
                grid_rows.append(row)
                if model == 'EQ03' and sc == BASE:
                    base[p] = (r, cash_rf)
                    trades_rows += [{'period': p, **t} for t in r.trades]
        bh100 = run(m, s, e, [(s, e, 'bh')], replace(BASE, max_position=100))
        grid_rows.append({'period': p, 'model': 'BH_TLT_100_info', 'scenario': BASE.label() + '_max100', **metrics(bh100, cash_rf)})
        out.setdefault('tlt_price_range', {})[p] = [float(m.open[s:e + 1].min()), float(m.open[s:e + 1].max())]
    grid = pd.DataFrame(grid_rows)
    grid.drop(columns=['worst_months']).to_csv(a.out / 'scenario_grid.csv', index=False, float_format='%.6g')
    pd.DataFrame(trades_rows).to_csv(a.out / 'trades_base.csv', index=False, float_format='%.8g')

    # ---- 4. primary test (base scenario, monthly excess over cash_rf), Holm over T3/T2/T1
    tests, series = {}, {}
    for p in PERIODS:
        r, c = base[p]
        x = (monthly_returns(r) - monthly_returns(c)) * 1e4  # bps of total capital per month
        series[p] = x
        row = {'months': len(x), 'mean_bps_per_month': float(x.mean()), 'sd_bps': float(x.std(ddof=1)),
               'share_positive_months': float((x > 0).mean()), 'lag1_autocorr': float(x.autocorr(1))}
        for name, f in pv_stats.METHODS.items():
            kw = {'B': BOOT_B, 'seed': SEED} if 'cbb' in name else {}
            pval, lo, hi = f(x.to_numpy(), **kw)
            row[name] = {'p_one_sided': pval, 'ci95': [lo, hi]}
        tests[p] = row
    holm = pv_stats.holm({p: tests[p][method]['p_one_sided'] for p in TESTED})
    for p in TESTED:
        tests[p]['holm_p_primary'] = holm[p]
    out['primary_test'] = tests
    pd.DataFrame(series).to_csv(a.out / 'monthly_excess_bps_base.csv', float_format='%.6g')

    # ---- 5. random windows (base scenario)
    rnd = {}
    for p in PERIODS:
        s, e = span(m, p)
        cash_rf = base[p][1]
        finals = np.array([run(m, s, e, tl, BASE).equity[-1]
                           for tl in random_windows(m, s, e, trades, N_RANDOM, SEED + s)])
        strat = base[p][0].equity[-1]
        rnd[p] = {'n_sims': N_RANDOM, 'strategy_final': float(strat), 'random_mean_final': float(finals.mean()),
                  'random_p05': float(np.quantile(finals, .05)), 'random_p50': float(np.median(finals)),
                  'random_p95': float(np.quantile(finals, .95)),
                  'strategy_percentile': float((finals < strat).mean() * 100),
                  'random_mean_excess_vs_cash_rf': float(finals.mean() - cash_rf.equity[-1])}
    out['random_windows'] = rnd

    # ---- 6. sensitivities on the base scenario (descriptive)
    sens = []
    m1, _ = load_market(a.data, a.rf, 'S1')
    for label, mk, sc, tl in [('S1_data', m1, BASE, trades), ('pay_lag_0', m, replace(BASE, pay_lag=0), trades),
                              ('pay_lag_5', m, replace(BASE, pay_lag=5), trades),
                              ('realised_calendar', m, BASE, trades_real)]:
        for p in PERIODS:
            s, e = span(mk, p)
            c = run(mk, s, e, [], Scenario(idle_rf=True))
            met = metrics(run(mk, s, e, tl, sc), c)
            sens.append({'sensitivity': label, 'period': p, 'final_equity': met['final_equity'],
                         'excess_pnl_vs_cash_rf': met['excess_pnl_vs_cash_rf'], 'cagr_pct': met['cagr_pct']})
    pd.DataFrame(sens).to_csv(a.out / 'sensitivities.csv', index=False, float_format='%.6g')
    out['sensitivities'] = sens

    # worst months for the base scenario and controls
    out['worst_months_base'] = {f"{r['period']}|{r['model']}": r['worst_months'] for r in grid_rows
                                if r.get('scenario', BASE.label()) == BASE.label() or r['model'].startswith('cash')}
    (a.out / 'summary.json').write_text(json.dumps(out, indent=2, default=float))
    print('wrote', a.out)


if __name__ == '__main__':
    main()
