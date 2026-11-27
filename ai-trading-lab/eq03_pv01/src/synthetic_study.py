"""Size / power / coverage of the candidate tests on synthetic monthly series (no market data).

Usage: python -I synthetic_study.py OUT_DIR [--nsim 2000] [--B 999]
Writes synthetic_study.csv, synthetic_study.json (incl. the selected primary method by PROTOCOL §5).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pv_stats import METHODS, SIMPLICITY_ORDER  # noqa: E402

NS = (29, 79, 168)          # sizes of T1, T2, T3 in months
EFFECT = 0.3                # power alternative: mean = 0.3 standard deviations
SEED = 20261128
SIZE_CAP = 0.065            # admissibility: max rejection rate at nominal 5% (one-sided)
TIE = 0.01


def garch(n, rng, omega=0.05, a=0.10, b=0.85, df=5, burn=200):
    z = rng.standard_t(df, n + burn) / np.sqrt(df / (df - 2))
    h = np.empty(n + burn); e = np.empty(n + burn); h[0] = omega / (1 - a - b)
    for t in range(n + burn):
        if t:
            h[t] = omega + a * e[t - 1] ** 2 + b * h[t - 1]
        e[t] = np.sqrt(h[t]) * z[t]
    return e[burn:]


def ar1(innov, phi, rng):
    x = np.empty_like(innov); x[0] = innov[0] / np.sqrt(1 - phi ** 2)
    for t in range(1, len(x)):
        x[t] = phi * x[t - 1] + innov[t]
    return x * np.sqrt(1 - phi ** 2)


def dgp(name, n, rng):
    if name == 'D1_iid_normal':
        return rng.standard_normal(n)
    if name == 'D2_ar1_0.3':
        return ar1(rng.standard_normal(n), 0.3, rng)
    if name == 'D3_iid_t3':
        return rng.standard_t(3, n) / np.sqrt(3.0)
    if name == 'D4_garch_t5':
        return garch(n, rng)
    if name == 'D5_vol_break_x3':
        s = np.where(np.arange(n) < n // 2, 0.5, 1.5)
        return rng.standard_normal(n) * s / np.sqrt(1.25)
    if name == 'D6_neg_skew_jumps':
        j = rng.random(n) < 0.05
        x = rng.standard_normal(n) * 0.8 + np.where(j, -3.0, 0.0)
        return (x + 0.15) / np.sqrt(0.64 + 0.05 * 0.95 * 9)
    if name == 'D7_ar0.2_garch_t5':
        return ar1(garch(n, rng), 0.2, rng)
    raise KeyError(name)


DGPS = ['D1_iid_normal', 'D2_ar1_0.3', 'D3_iid_t3', 'D4_garch_t5', 'D5_vol_break_x3',
        'D6_neg_skew_jumps', 'D7_ar0.2_garch_t5']


def study(nsim, B):
    rows = []
    for di, d in enumerate(DGPS):
        for n in NS:
            rng = np.random.default_rng([SEED, di, n])
            rej = {m: [0, 0] for m in METHODS}; cov = {m: 0 for m in METHODS}
            for s in range(nsim):
                x0 = dgp(d, n, rng)
                for mu_i, mu in enumerate((0.0, EFFECT)):
                    x = x0 + mu
                    for mname, f in METHODS.items():
                        kw = {'B': B, 'seed': s} if 'cbb' in mname else {}
                        p, lo, hi = f(x, **kw)
                        rej[mname][mu_i] += p < 0.05
                        if mu_i == 0:
                            cov[mname] += lo <= 0 <= hi
            for mname in METHODS:
                rows.append({'dgp': d, 'n': n, 'method': mname, 'size_5pct': rej[mname][0] / nsim,
                             'power_0.3sd': rej[mname][1] / nsim, 'ci95_coverage': cov[mname] / nsim})
            print(d, n, {m: round(rej[m][0] / nsim, 3) for m in METHODS}, flush=True)
    return pd.DataFrame(rows)


def select(df):
    agg = df.groupby('method').agg(max_size=('size_5pct', 'max'), mean_power=('power_0.3sd', 'mean'),
                                   min_coverage=('ci95_coverage', 'min')).reindex(SIMPLICITY_ORDER)
    adm = agg[agg.max_size <= SIZE_CAP]
    if len(adm):
        best = adm.mean_power.max()
        chosen = next(m for m in SIMPLICITY_ORDER if m in adm.index and adm.mean_power[m] >= best - TIE)
        reason = f'admissible (max size <= {SIZE_CAP}); highest mean power within {TIE}; simplest on ties'
    else:
        chosen = agg.max_size.idxmin()
        reason = 'no method admissible; smallest maximum size chosen, p-values flagged approximate'
    return chosen, reason, agg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out', type=Path)
    ap.add_argument('--nsim', type=int, default=2000); ap.add_argument('--B', type=int, default=999)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    df = study(a.nsim, a.B)
    df.to_csv(a.out / 'synthetic_study.csv', index=False, float_format='%.4f')
    chosen, reason, agg = select(df)
    (a.out / 'synthetic_study.json').write_text(json.dumps({
        'nsim': a.nsim, 'B': a.B, 'seed': SEED, 'sizes': NS, 'effect_sd': EFFECT, 'size_cap': SIZE_CAP,
        'selected_primary_method': chosen, 'reason': reason,
        'summary': agg.reset_index().to_dict(orient='records')}, indent=2))
    print(agg.round(3).to_string()); print('SELECTED:', chosen, '-', reason)


if __name__ == '__main__':
    main()
