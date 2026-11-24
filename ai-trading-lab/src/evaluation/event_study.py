"""Mechanism check: forward returns after signals vs unconditional background. Not a trading result."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.evaluation.engine import Bars, MIN_NS


def forward_returns(b: Bars, decision_times: pd.Series, horizons: list[int]) -> pd.DataFrame:
    """ln(open[t+h]/open[t]) using 1m opens; NaN if any endpoint is missing or beyond the segment."""
    k = ((decision_times - b.start).dt.total_seconds() // 60).astype("int64").to_numpy()
    out = {}
    for h in horizons:
        r = np.full(len(k), np.nan)
        ok = (k >= 0) & (k + h < b.n)
        a = np.where(ok, b.o[np.clip(k, 0, b.n - 1)], np.nan)
        z = np.where(ok, b.o[np.clip(k + h, 0, b.n - 1)], np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.log(z / a)
        out[f"fwd_{h}m"] = r
    return pd.DataFrame(out, index=decision_times.index)


def summarize(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) == 0:
        return {"n": 0}
    sd = r.std(ddof=1) if len(r) > 1 else np.nan
    return {"n": int(len(r)), "mean_bps": round(1e4 * r.mean(), 3), "median_bps": round(1e4 * r.median(), 3),
            "std_bps": round(1e4 * sd, 3) if np.isfinite(sd) else None,
            "t_stat_naive": round(r.mean() / (sd / np.sqrt(len(r))), 3) if np.isfinite(sd) and sd > 0 else None,
            "share_positive": round(float((r > 0).mean()), 4)}
