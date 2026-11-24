"""Past-only feature computation on a regular 5m grid (missing candles = NaN rows).

Definitions (MVP v0.1 spec, section 3):
  r5(t)  = ln(C(t)/C(t-1))
  r15(t) = ln(C(t)/C(t-3))
  z5(t)  = (r5(t)  - mean(r5[t-288..t-1]))  / std_ddof0(r5[t-288..t-1])
  z15(t) = (r15(t) - mean(r15[t-288..t-1])) / std_ddof0(r15[t-288..t-1])   (288 previous r15 values on the 5m grid)
  RV(t)  = V(t) / median(V[t-48..t-1])
  I(t)   = 2*taker_buy_base(t)/V(t) - 1
Any missing candle, zero denominator or short history -> NaN -> no signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rolling_prev(s: pd.Series, window: int, fn: str) -> pd.Series:
    """Statistic over the `window` values strictly before t; NaN unless all are present."""
    r = s.shift(1).rolling(window, min_periods=window)
    if fn == "mean":
        return r.mean()
    if fn == "std0":
        return r.std(ddof=0)
    if fn == "median":
        return r.median()
    if fn == "max":
        return r.max()
    raise ValueError(fn)


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    out = a / b.where(b != 0)
    return out.replace([np.inf, -np.inf], np.nan)


def compute_features(grid: pd.DataFrame, z_window: int = 288, rv_window: int = 48,
                     breakout_window: int = 12, regime_lookback: int = 288) -> pd.DataFrame:
    """grid: 5m grid indexed by open_time with columns open/high/low/close/volume/taker_buy_base (NaN if missing)."""
    C, O, H, V = grid["close"], grid["open"], grid["high"], grid["volume"]
    f = pd.DataFrame(index=grid.index)
    f["present"] = C.notna()
    with np.errstate(divide="ignore", invalid="ignore"):
        f["r5"] = np.log(C / C.shift(1))
        f["r15"] = np.log(C / C.shift(3))
    f["z5"] = _safe_div(f["r5"] - _rolling_prev(f["r5"], z_window, "mean"), _rolling_prev(f["r5"], z_window, "std0"))
    f["z15"] = _safe_div(f["r15"] - _rolling_prev(f["r15"], z_window, "mean"),
                         _rolling_prev(f["r15"], z_window, "std0"))
    f["rv"] = _safe_div(V, _rolling_prev(V, rv_window, "median"))
    if "taker_buy_base" in grid:
        f["imb"] = 2 * _safe_div(grid["taker_buy_base"], V) - 1
    else:
        f["imb"] = np.nan
    f["prev_max_high"] = _rolling_prev(H, breakout_window, "max")
    f["close"], f["open"] = C, O
    # regime inputs (past-only relative to the decision time = candle close)
    with np.errstate(divide="ignore", invalid="ignore"):
        f["ret24h"] = np.log(C / C.shift(regime_lookback))
    f["vol24h"] = f["r5"].rolling(regime_lookback, min_periods=regime_lookback).std(ddof=0)
    return f


def regime_label(ret24h: float, vol24h: float, vol_threshold: float) -> str:
    if not np.isfinite(ret24h) or not np.isfinite(vol24h) or not np.isfinite(vol_threshold):
        return "undefined"
    return ("up" if ret24h >= 0 else "down") + "_" + ("highvol" if vol24h >= vol_threshold else "lowvol")
