"""Statistics for v0.2: day-block (paired) bootstrap, HAC regressions, portfolio metrics extras.

Reuses audited v0.1 pieces: src.evaluation.bootstrap.block_bootstrap / holm and src.evaluation.metrics.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.evaluation.bootstrap import block_bootstrap, holm  # noqa: F401  (re-exported)
from src.evaluation.metrics import compute_metrics, daily_pnl, trade_stats  # noqa: F401


def day_blocks_index(n_days: int, block: int, n_boot: int, seed: int) -> np.ndarray:
    """Moving-block bootstrap day indices (same scheme as v0.1 block_bootstrap), shape (n_boot, n_days)."""
    rng = np.random.default_rng(seed)
    k = int(np.ceil(n_days / block))
    starts = rng.integers(0, n_days - block + 1, size=(n_boot, k))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n_days]


def ratio_bootstrap(num: np.ndarray, den: np.ndarray, block: int, n_boot: int, seed: int, min_blocks: int,
                    agg="mean_over_columns") -> dict:
    """Paired day-block bootstrap of statistic mean_j( sum_t num[t,j] / sum_t den[t,j] ).

    num/den: (n_days, n_targets) daily sums on the COMMON UTC-day axis, so resampling days keeps the
    cross-asset correlation. H0: statistic <= 0 (one-sided; centred bootstrap)."""
    n = num.shape[0]
    out = {"block_days": block, "n_days": int(n), "n_boot": n_boot, "seed": seed}
    obs = float(np.mean(num.sum(0) / den.sum(0)))
    out["observed"] = obs
    if n // block < min_blocks:
        out.update(status="insufficient_data")
        return out
    idx = day_blocks_index(n, block, n_boot, seed)
    stats = np.mean(num[idx].sum(1) / den[idx].sum(1), axis=1)
    out.update(status="ok", ci95=[float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))],
               share_le_0=float((stats <= 0).mean()),
               p_one_sided_gt_0=float(((stats - obs) >= obs).mean()) if obs > 0 else 1.0)
    return out


def hac_mean(y: np.ndarray, maxlags: int) -> dict:
    y = np.asarray(y, float)
    y = y[np.isfinite(y)]
    if len(y) < 10:
        return {"n": int(len(y)), "status": "too_few"}
    r = sm.OLS(y, np.ones((len(y), 1))).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return {"n": int(len(y)), "mean": float(r.params[0]), "se_hac": float(r.bse[0]), "t_hac": float(r.tvalues[0]),
            "maxlags": maxlags}


def hac_ols(y: np.ndarray, x: np.ndarray, maxlags: int) -> dict:
    m = np.isfinite(y) & np.isfinite(x)
    if m.sum() < 30:
        return {"n": int(m.sum()), "status": "too_few"}
    r = sm.OLS(y[m], sm.add_constant(x[m])).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return {"n": int(m.sum()), "const": float(r.params[0]), "beta": float(r.params[1]), "t_const_hac": float(r.tvalues[0]),
            "t_beta_hac": float(r.tvalues[1]), "r2": float(r.rsquared), "maxlags": maxlags}


def extra_metrics(equity: pd.Series, initial: float) -> dict:
    run_max = equity.cummax()
    under = equity < run_max - 1e-12
    longest, cur = 0, 0
    # longest underwater spell in minutes (vectorised run-length)
    if under.any():
        u = under.to_numpy().astype(np.int8)
        edges = np.flatnonzero(np.diff(np.r_[0, u, 0]))
        lens = edges[1::2] - edges[::2]
        longest = int(lens.max())
    dp = daily_pnl(equity, initial)
    q05 = float(dp.quantile(0.05)) if len(dp) else None
    es = float(dp[dp <= q05].mean()) if len(dp) and (dp <= q05).any() else None
    return {"time_underwater_share": float(under.mean()), "longest_underwater_days": round(longest / 1440, 3),
            "daily_pnl_q05": q05, "daily_pnl_es05": es, "daily_pnl_mean": float(dp.mean()) if len(dp) else None,
            "daily_pnl_median": float(dp.median()) if len(dp) else None}


def yearly(trades: pd.DataFrame, equity: pd.Series, initial: float) -> dict:
    dp = daily_pnl(equity, initial)
    out = {}
    for y, g in dp.groupby(dp.index.year):
        t = trades[trades["entry_time"].dt.year == y] if len(trades) else trades
        out[str(y)] = {"pnl": round(float(g.sum()), 6), "n_trades": int(len(t)),
                       "net_trades": round(float(t["net_pnl"].sum()), 6) if len(t) else 0.0}
    return out


def safe(x):
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(x) else float(x)
    return x
