"""Causal features and executable labels for v0.2. All series are on regular grids indexed by T = bar END.

No gap skipping: shifts are on the regular grid, so a missing bar makes every dependent value NaN.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.replay import MIN, Px


def grid(bars: pd.DataFrame, minutes: int, g0: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Reindex closed bars (column T) onto the regular grid of bar ends in (g0, end]."""
    idx = pd.date_range(g0 + pd.Timedelta(minutes=minutes), end, freq=f"{minutes}min", name="T")
    g = bars.set_index("T")[["open", "high", "low", "close", "volume", "taker_buy_base"]].reindex(idx)
    return g


def logret(close: pd.Series, lag: int) -> pd.Series:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(close / close.shift(lag))


# ------------------------------------------------------------------ G01

def g01_asset_features(g30: pd.DataFrame, lookbacks_min=(30, 60, 240), vol_bars=48, rv_bars=48) -> pd.DataFrame:
    c, v, tb = g30["close"], g30["volume"], g30["taker_buy_base"]
    f = pd.DataFrame(index=g30.index)
    for k in lookbacks_min:
        f[f"r{k}"] = logret(c, k // 30)
    r30 = logret(c, 1)
    f["vol24h"] = r30.rolling(vol_bars, min_periods=vol_bars).std(ddof=0)
    med = v.shift(1).rolling(rv_bars, min_periods=rv_bars).median()
    with np.errstate(divide="ignore", invalid="ignore"):
        lrv = np.log(v / med.where(med > 0))
    f["log_rv"] = lrv.where((v > 0) & (med > 0))
    f["imb"] = (2 * tb / v.where(v > 0) - 1)
    return f.replace([np.inf, -np.inf], np.nan)


def g01_design(asset_feats: dict[str, pd.DataFrame], target: str, lookbacks_min=(30, 60, 240)):
    """Returns (B1 frame, X frame). Rows valid only if all 9 assets' returns and target extras are valid.
    Market factor F(i,k) = mean over the OTHER eight assets (target excluded)."""
    others = [a for a in asset_feats if a != target]
    tf = asset_feats[target]
    b1 = pd.DataFrame(index=tf.index)
    for k in lookbacks_min:
        b1[f"own_r{k}"] = tf[f"r{k}"]
    F = {}
    for k in lookbacks_min:
        F[k] = pd.concat([asset_feats[a][f"r{k}"] for a in others], axis=1).mean(axis=1, skipna=False)
        b1[f"mkt_r{k}"] = F[k]
    b1["vol24h"], b1["log_rv"], b1["imb"] = tf["vol24h"], tf["log_rv"], tf["imb"]
    x = b1.copy()
    for a in others:
        for k in lookbacks_min:
            x[f"res_{a}_r{k}"] = asset_feats[a][f"r{k}"] - F[k]
    valid = x.notna().all(axis=1)
    return b1.where(valid), x.where(valid), valid


# ------------------------------------------------------------------ labels

def labels(px: Px, T: pd.DatetimeIndex, hold_min: int, delay_min: int) -> np.ndarray:
    """Executable gross simple return exit_open / entry_open - 1; NaN if either minute is missing."""
    k = ((T - px.g0) / MIN).astype("int64").to_numpy() + delay_min
    ok = (k >= 0) & (k + hold_min < px.n)
    out = np.full(len(k), np.nan)
    a = px.o[np.clip(k, 0, px.n - 1)]
    z = px.o[np.clip(k + hold_min, 0, px.n - 1)]
    out[ok] = z[ok] / a[ok] - 1
    return out


def net_label(gross_entry_open: np.ndarray, gross_exit_open: np.ndarray, fee: float, slip: float) -> np.ndarray:
    """Net executable return per unit notional (no rounding): (o_x(1-s)(1-f)) / (o_e(1+s)(1+f)) - 1."""
    return gross_exit_open * (1 - slip) * (1 - fee) / (gross_entry_open * (1 + slip) * (1 + fee)) - 1


def net_from_gross(g: np.ndarray, fee: float, slip: float) -> np.ndarray:
    return (1 + g) * (1 - slip) * (1 - fee) / ((1 + slip) * (1 + fee)) - 1


def crosses_boundary(T: pd.DatetimeIndex, horizon_min: int, delay_min: int, boundaries: list[pd.Timestamp]) -> np.ndarray:
    """True if [T, T + delay + H] contains a split boundary strictly after T (label/position would cross it)."""
    end = T + pd.Timedelta(minutes=delay_min + horizon_min)
    out = np.zeros(len(T), dtype=bool)
    for b in boundaries:
        out |= (T < b) & (end > b)
    return out


# ------------------------------------------------------------------ H01-H03 inputs, sigma, regimes

def hourly_sigma(g60_close: pd.Series, days: int = 30) -> pd.Series:
    r = logret(g60_close, 1)
    n = days * 24
    return r.rolling(n, min_periods=n).std(ddof=0)


def trend30d(g60_close: pd.Series) -> pd.Series:
    return logret(g60_close, 30 * 24)
