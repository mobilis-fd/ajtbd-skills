"""Sidecar join of extended kline fields onto a Freqtrade OHLCV dataframe by (symbol, close_time).

Freqtrade's `date` column is the candle OPEN time; a candle's extended fields are only known at its
close_time = date + timeframe. The join is exact on close_time; a missing or inconsistent sidecar row
yields NaN (fail closed -> no F-signal). No Freqtrade source code is modified.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def join_sidecar(df: pd.DataFrame, side: pd.DataFrame, tf_minutes: int = 5, vol_rtol: float = 1e-9) -> pd.DataFrame:
    out = df.copy()
    key = pd.to_datetime(out["date"], utc=True) + pd.Timedelta(minutes=tf_minutes)
    s = side.copy()
    s["close_time"] = pd.to_datetime(s["close_time"], utc=True)
    if s["close_time"].duplicated().any():
        raise ValueError("duplicate close_time in sidecar")
    s = s.set_index("close_time")
    joined = s.reindex(pd.DatetimeIndex(key))
    out["taker_buy_base"] = joined["taker_buy_base"].to_numpy()
    out["ext_volume"] = joined["volume"].to_numpy()
    # consistency check: sidecar volume must equal the OHLCV volume of the same candle
    bad = ~np.isclose(out["ext_volume"].to_numpy(float), out["volume"].to_numpy(float), rtol=vol_rtol, atol=0)
    out.loc[bad, "taker_buy_base"] = np.nan
    out["sidecar_ok"] = ~bad
    return out


def load_sidecar(sidecar_dir: Path, symbol: str) -> pd.DataFrame:
    return pd.read_parquet(Path(sidecar_dir) / f"{symbol}_5m_ext.parquet")
