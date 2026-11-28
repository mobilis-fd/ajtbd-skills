"""Copied unchanged (except this line) from eq03_pv01/src/pv_stats.py at 51ce272 for EQ04 self-containment.
Candidate tests for H0: mean(x) <= 0 vs H1: mean(x) > 0 on a monthly series (one-sided).

Every function returns (p_one_sided, ci_low_95, ci_high_95). Candidates are compared on synthetic data
in synthetic_study.py; the primary method is fixed by the rule in PROTOCOL.md §5 before any new
historical result is computed.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

BLOCK = 6


def nw_lag(n: int) -> int:
    return int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))


def t_iid(x):
    x = np.asarray(x, float); n = len(x)
    se = x.std(ddof=1) / np.sqrt(n)
    if se == 0:
        return (1.0 if x.mean() <= 0 else 0.0), x.mean(), x.mean()
    t = x.mean() / se
    q = stats.t.ppf(0.975, n - 1)
    return float(stats.t.sf(t, n - 1)), float(x.mean() - q * se), float(x.mean() + q * se)


def nw_se(x, lag):
    x = np.asarray(x, float); n = len(x); e = x - x.mean()
    v = e @ e / n
    for L in range(1, lag + 1):
        w = 1 - L / (lag + 1)
        v += 2 * w * (e[L:] @ e[:-L]) / n
    return np.sqrt(max(v, 0) / n)


def t_newey_west(x, lag=None):
    """HAC t-test, Bartlett kernel, lag floor(4(n/100)^(2/9)), Student t(n-1) reference."""
    x = np.asarray(x, float); n = len(x)
    lag = nw_lag(n) if lag is None else lag
    se = nw_se(x, lag)
    if se == 0:
        return (1.0 if x.mean() <= 0 else 0.0), x.mean(), x.mean()
    t = x.mean() / se
    q = stats.t.ppf(0.975, n - 1)
    return float(stats.t.sf(t, n - 1)), float(x.mean() - q * se), float(x.mean() + q * se)


def _cbb_index(n, block, B, rng):
    k = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(B, k))
    return ((starts[:, :, None] + np.arange(block)) % n).reshape(B, -1)[:, :n]


def cbb_percentile(x, block=BLOCK, B=1999, seed=1):
    """v0.3-pre method: circular block bootstrap, centred percentile p-value, percentile CI."""
    x = np.asarray(x, float); n = len(x)
    rng = np.random.default_rng(seed)
    means = x[_cbb_index(n, block, B, rng)].mean(axis=1)
    m = x.mean()
    p = (1 + np.count_nonzero(means - m >= m)) / (B + 1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(p), float(lo), float(hi)


def _gk_se_blocks(xb, block):
    """Goetze-Kuensch style s.e. of the mean from the blocks of one resample (rows = replicates)."""
    B, n = xb.shape
    k = n // block
    bm = xb[:, :k * block].reshape(B, k, block).mean(axis=2)
    return bm.std(axis=1, ddof=1) / np.sqrt(k)


def cbb_studentized(x, block=BLOCK, B=1999, seed=1):
    """Circular block bootstrap-t. Original s.e.: overlapping circular block means; replicate s.e.:
    the resample's own block means (Goetze & Kuensch 1996)."""
    x = np.asarray(x, float); n = len(x)
    rng = np.random.default_rng(seed)
    xb = x[_cbb_index(n, block, B, rng)]
    circ = np.concatenate([x, x[:block - 1]])
    allb = np.lib.stride_tricks.sliding_window_view(circ, block)[:n].mean(axis=1)
    se0 = allb.std(ddof=0) * np.sqrt(block / n)
    m = x.mean()
    if se0 == 0:
        return (1.0 if m <= 0 else 0.0), m, m
    se_b = _gk_se_blocks(xb, block)
    se_b = np.where(se_b > 0, se_b, np.inf)
    tb = (xb.mean(axis=1) - m) / se_b
    t0 = m / se0
    p = (1 + np.count_nonzero(tb >= t0)) / (B + 1)
    qlo, qhi = np.quantile(tb, [0.025, 0.975])
    return float(p), float(m - qhi * se0), float(m - qlo * se0)


METHODS = {
    'M1_t_iid': t_iid,
    'M2_newey_west': t_newey_west,
    'M3_cbb_percentile_b6': cbb_percentile,
    'M4_cbb_studentized_b6': cbb_studentized,
}
SIMPLICITY_ORDER = ['M1_t_iid', 'M2_newey_west', 'M3_cbb_percentile_b6', 'M4_cbb_studentized_b6']


def holm(pvals: dict) -> dict:
    items = sorted([(k, v) for k, v in pvals.items() if v is not None], key=lambda kv: kv[1])
    out, prev, m = {}, 0.0, len(items)
    for i, (k, v) in enumerate(items):
        prev = max(prev, min(1.0, (m - i) * v))
        out[k] = prev
    return out
