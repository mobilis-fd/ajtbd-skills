"""Independent checks for Equity Alpha Screening v0.3-pre (written by the auditor, not by the script author).

  python -I verify.py synthetic
  python -I verify.py reconcile DATA_DIR RUN_DIR

`synthetic` runs extra synthetic tests that the original self-test does not cover (AUDIT.md A1, A2, A3).
`reconcile` recomputes events and summary statistics with an independent implementation and compares them with
the original script's output (events_exploratory.csv, summary.json). It never changes the original script.
"""
import importlib.util, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('equity_screen', HERE.parent / 'original' / 'equity_screen.py')
ES = importlib.util.module_from_spec(spec); spec.loader.exec_module(ES)
PERIODS = ES.PERIODS  # read, not redefined: reconciliation must use the frozen periods


# ---------------- independent implementation ----------------
def indep_events(cal, data):
    """Month loop written from the README text, positional indices via searchsorted."""
    cal = pd.DatetimeIndex(cal)
    out = []
    per = cal.to_period('M')
    groups = pd.Series(np.arange(len(cal)), index=cal).groupby(per)
    O = {s: data[s].adj_open.to_numpy() for s in data}; C = {s: data[s].adj_close.to_numpy() for s in data}
    r = lambda s, i, j: C[s][j] / O[s][i] - 1.0
    for m, idx in groups:
        idx = idx.to_numpy()
        first, last = idx[0], idx[-1]
        if len(idx) < 15 or first == 0 or last + 3 >= len(cal):  # same admissibility as the script
            continue
        entry5 = last - 4                       # first of the last five sessions
        # EQ01: MTD total return from prior month-end close to close before entry5
        mtd = {s: C[s][entry5 - 1] / C[s][first - 1] - 1.0 for s in ('SPY', 'IEF')}
        pick = 'SPY' if mtd['SPY'] <= mtd['IEF'] else 'IEF'
        out.append(('EQ01', str(m), pick, cal[entry5], cal[last], r(pick, entry5, last),
                    0.5 * (r('SPY', entry5, last) + r('IEF', entry5, last))))
        # EQ02: last session open -> third session close of next month; control: 4-session windows starting in month
        ctrl2 = np.mean([r('SPY', k, k + 3) for k in idx])
        out.append(('EQ02', str(m), 'SPY', cal[last], cal[last + 3], r('SPY', last, last + 3), ctrl2))
        # EQ03: TLT first of last five -> month-end close; control: 5-session windows wholly within month
        ctrl3 = np.mean([r('TLT', k, k + 4) for k in idx if k + 4 <= last])
        out.append(('EQ03', str(m), 'TLT', cal[entry5], cal[last], r('TLT', entry5, last), ctrl3))
    return pd.DataFrame(out, columns=['hypothesis', 'month', 'symbol', 'entry', 'exit', 'gross', 'control'])


def cbb_means(x, block, reps, rng):
    n = len(x); nb = -(-n // block)
    starts = rng.randint(0, n, size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n] % n
    return x[idx].mean(axis=1)


# ---------------- synthetic tests ----------------
def synthetic():
    res = []
    def info(name, detail):
        print('INFO ' + name + ' — ' + detail)
    def check(name, ok, detail=''):
        res.append((name, bool(ok), detail)); print(('PASS ' if ok else 'FAIL ') + name + (' — ' + detail if detail else ''))

    cal = pd.bdate_range('2002-12-02', '2026-11-10')
    flat = {s: pd.DataFrame({'adj_open': 100., 'adj_close': 100.}, index=cal) for s in ES.SYMS}

    # A1: discriminating look-ahead test. Lower IEF from the entry day on: a look-ahead bug would switch to IEF.
    e0 = ES.events(cal, flat); o = e0[(e0.hypothesis == 'EQ01') & (e0.month == '2024-06')].iloc[0]
    mut = {s: f.copy() for s, f in flat.items()}; mut['IEF'].loc[o.entry:, ['adj_open', 'adj_close']] = 50.
    n = ES.events(cal, mut); n = n[(n.hypothesis == 'EQ01') & (n.month == '2024-06')].iloc[0]
    check('A1 EQ01 choice unchanged when IEF falls from entry day (discriminating version)', n.symbol == o.symbol == 'SPY')
    mut2 = {s: f.copy() for s, f in flat.items()}; mut2['IEF'].loc[cal[cal.get_loc(o.entry) - 1], 'adj_close'] = 99.
    n2 = ES.events(cal, mut2); n2 = n2[(n2.hypothesis == 'EQ01') & (n2.month == '2024-06')].iloc[0]
    check('A1 EQ01 choice does switch when the signal-day close (entry-1) changes', n2.symbol == 'IEF')

    # Known answer: constant daily drift g on close-to-close, open = previous close => event return = (1+g)^n - 1
    g = 0.001; px = 100 * (1 + g) ** np.arange(len(cal))
    drift = {s: pd.DataFrame({'adj_open': np.r_[100., px[:-1]], 'adj_close': px}, index=cal) for s in ES.SYMS}
    ed = ES.events(cal, drift)
    exp = {'EQ01': (1 + g) ** 5 - 1, 'EQ02': (1 + g) ** 4 - 1, 'EQ03': (1 + g) ** 5 - 1}
    err = max(abs(ed[ed.hypothesis == h].gross - v).max() for h, v in exp.items())
    check('Known-answer drift: gross = (1+g)^sessions - 1 for all events', err < 1e-12, f'max err {err:.1e}')
    err_c = max(abs(ed[ed.hypothesis == h].control - v).max() for h, v in exp.items())
    check('Known-answer drift: control equals event under constant drift', err_c < 1e-12, f'max err {err_c:.1e}')
    s = ES.summarize(ed); r0 = s[0]
    be = 2 * exp[r0['hypothesis']] / (2 + exp[r0['hypothesis']]) * 1e4
    check('Break-even RT cost formula (net at break-even = 0)', abs(r0['break_even_rt_bps'] - be) < 1e-9)

    # Independent implementation agrees with the script on a random-walk dataset with a real NYSE-like calendar
    rng = np.random.default_rng(1)
    rw = {}
    for sy in ES.SYMS:
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(cal))))
        op = np.r_[100., c[:-1]] * np.exp(rng.normal(0, 0.003, len(cal)))
        rw[sy] = pd.DataFrame({'adj_open': op, 'adj_close': c}, index=cal)
    a = ES.events(cal, rw).reset_index(drop=True); b = indep_events(cal, rw).reset_index(drop=True)
    same = (len(a) == len(b) and (a.symbol == b.symbol).all() and (a.entry == b.entry).all() and (a.exit == b.exit).all()
            and np.allclose(a.gross, b.gross, rtol=0, atol=1e-13) and np.allclose(a.control, b.control, rtol=0, atol=1e-13))
    check('Independent event implementation == script (random walk)', same, f'{len(a)} rows')
    picks = a[a.hypothesis == 'EQ01'].symbol.value_counts().to_dict()
    check('EQ01 picks both assets on random data (not degenerate)', len(picks) == 2, str(picks))

    # A3: bootstrap behaviour under the null and at a known mean (iid normal months). Reported as INFO with the
    # measured value; there is no pass threshold, because the size of the procedure is a finding, not a test target.
    for nn in (28, 60, 160):
        rngp = np.random.default_rng(7); rej = 0; cover = 0; sims = 300
        for k in range(sims):
            x = rngp.normal(0, 1, nn)
            lo, hi, p = ES.bootstrap(x, 6, ES.SEED + 6 + k)
            rej += p < 0.05; cover += lo <= 0 <= hi
        info(f'A3 bootstrap (block 6) iid N(0,1), n={nn}, {sims} sims: one-sided rejection rate at 5% / CI coverage',
             f'{rej/sims:.3f} / {cover/sims:.3f} (nominal 0.050 / 0.950)')
    rngp = np.random.default_rng(8); x = rngp.normal(-1, 1, 60); lo, hi, p = ES.bootstrap(x, 6, ES.SEED)
    check('A3 p-value is one-sided: clearly negative mean gives p close to 1', p > 0.95, f'p={p:.3f}')
    check('Inference cutoff max(24, 2*block)', ES.bootstrap(np.ones(23), 3, 1) == (None, None, None)
          and ES.bootstrap(np.ones(23), 12, 1) == (None, None, None) and ES.bootstrap(np.ones(24), 12, 1)[0] is not None)

    # Holm: compare with a direct step-down implementation on known p-values
    fake = [{'p_6m': p} for p in (0.01, 0.04, 0.03, 0.5)]
    srt = sorted(fake, key=lambda r: r['p_6m']); prev = 0
    for i, r in enumerate(srt):
        prev = max(prev, min(1, (len(srt) - i) * r['p_6m'])); r['h'] = prev
    check('Holm step-down values', [r['h'] for r in srt] == [0.04, 0.09, 0.09, 0.5])

    # A2: a truncated final month (data ending mid-month) must not create a false month-end event
    cal2 = cal[cal <= '2024-06-21']  # June 2024 truncated at 15 sessions
    d2 = {s_: f_.loc[cal2] for s_, f_ in flat.items()}
    e2 = ES.events(pd.DatetimeIndex(cal2), d2)
    check('A2 truncated final month produces no event (guard b+3 < len)', not (e2.month == '2024-06').any()
          and e2.exit.max() <= pd.Timestamp('2024-06-21'))
    # Cost model: half on entry notional, half on exit notional
    gg = np.array([0.02]); f = 25 / 20000
    check('Cost: net = g - f(2+g) equals (1+g)(1-f) - (1+f) per unit cash? (README convention)',
          abs((gg - f * (2 + gg))[0] - ((1 + gg[0]) * (1 - f) - (1 + f))) < 1e-15)
    ok = all(r[1] for r in res)
    return ok, res


# ---------------- reconciliation on real data ----------------
def reconcile(data_dir, run_dir):
    cal, data = ES.load(Path(data_dir))
    mine = indep_events(cal, data).reset_index(drop=True)
    theirs = pd.read_csv(Path(run_dir) / 'events_exploratory.csv', parse_dates=['entry', 'exit'])
    rep = {'rows_script': len(theirs), 'rows_independent': len(mine)}
    rep['symbols_equal'] = bool((mine.symbol.values == theirs.symbol.values).all())
    rep['dates_equal'] = bool((mine.entry.values == theirs.entry.values).all() and (mine.exit.values == theirs.exit.values).all())
    rep['max_abs_diff_gross'] = float(np.abs(mine.gross.values - theirs.gross.values).max())
    rep['max_abs_diff_control'] = float(np.abs(mine.control.values - theirs.control.values).max())
    summ = json.loads((Path(run_dir) / 'summary.json').read_text())['results']
    diffs = []; boot = []
    for r in summ:
        a, b = PERIODS[r['period']]
        e = mine[(mine.hypothesis == r['hypothesis']) & (mine.entry >= a) & (mine.exit <= b)]
        g, c = e.gross.to_numpy(), e.control.to_numpy(); d = (g - c) * 1e4
        diffs.append(max(abs(len(e) - r['months']), abs(g.mean() * 1e4 - r['gross_bps']), abs(c.mean() * 1e4 - r['control_bps']),
                         abs(d.mean() - r['delta_bps']),
                         max(abs((g - 40 / 20000 * (2 + g)).mean() * 1e4 - r['net_40bps']), 0)))
        if r['p_6m'] is not None:
            m = cbb_means(d, 6, 20000, np.random.RandomState(12345))
            lo, hi = np.quantile(m, [.025, .975]); p = (1 + np.sum(m - d.mean() >= d.mean())) / (len(m) + 1)
            boot.append({'cell': f"{r['period']}/{r['hypothesis']}", 'script_ci': r['delta_ci_6m'], 'indep_ci': [float(lo), float(hi)],
                         'script_p': r['p_6m'], 'indep_p': float(p)})
    rep['max_abs_diff_summary_stats'] = float(max(diffs))
    rep['bootstrap_independent_rng_20000reps'] = boot
    return rep


if __name__ == '__main__':
    if sys.argv[1] == 'synthetic':
        ok, _ = synthetic(); sys.exit(0 if ok else 1)
    elif sys.argv[1] == 'reconcile':
        print(json.dumps(reconcile(sys.argv[2], sys.argv[3]), indent=2, default=str))
