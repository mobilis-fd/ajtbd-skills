"""Moving-block bootstrap of daily PnL and Holm correction. Preliminary uncertainty only."""
from __future__ import annotations

import numpy as np
import pandas as pd


def block_bootstrap(daily: pd.Series, block: int, n_boot: int, seed: int, min_blocks: int) -> dict:
    x = np.asarray(daily, dtype=float)
    n = len(x)
    out = {"block_days": block, "n_days": n, "n_boot": n_boot, "seed": seed}
    if n == 0 or n // block < min_blocks:
        out.update(status="insufficient_data",
                   note=f"{n} days / block {block} = {n // block if block else 0} blocks < min_blocks {min_blocks}")
        return out
    rng = np.random.default_rng(seed)
    k = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_boot, k))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]
    means = x[idx].mean(axis=1)
    obs = float(x.mean())
    # one-sided test H0: mean daily PnL <= 0, using the centred bootstrap distribution
    p = float(((means - obs) >= obs).mean()) if obs > 0 else 1.0
    out.update(status="ok", mean_daily_pnl=round(obs, 6), total_pnl=round(float(x.sum()), 6),
               ci95_mean_daily=[round(float(np.quantile(means, 0.025)), 6), round(float(np.quantile(means, 0.975)), 6)],
               ci95_total=[round(float(np.quantile(means, 0.025) * n), 6), round(float(np.quantile(means, 0.975) * n), 6)],
               share_boot_mean_le_0=round(float((means <= 0).mean()), 6),
               p_one_sided_mean_gt_0=round(p, 6))
    return out


def holm(pvals: dict[str, float | None], alpha: float = 0.05) -> dict:
    items = [(k, v) for k, v in pvals.items() if v is not None]
    m = len(items)
    res = {k: {"p": None, "p_holm": None, "reject_h0": False, "note": "no p-value"} for k, v in pvals.items() if v is None}
    running = 0.0
    for i, (k, p) in enumerate(sorted(items, key=lambda kv: kv[1])):
        adj = min(1.0, max(running, (m - i) * p))
        running = adj
        res[k] = {"p": p, "p_holm": round(adj, 6), "reject_h0": adj <= alpha}
    return res
