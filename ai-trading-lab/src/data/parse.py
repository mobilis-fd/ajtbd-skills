"""Parse Binance spot kline CSV (monthly archives) into a UTC DataFrame.

Timestamp unit is detected per value by magnitude (DECISIONS D05):
  ms in [1e12, 1e13), us in [1e15, 1e16); anything else is rejected.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

RAW_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"]
OUT_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ts_unit"]


def _unit_of(v: np.ndarray) -> np.ndarray:
    unit = np.full(v.shape, "", dtype=object)
    unit[(v >= 10**12) & (v < 10**13)] = "ms"
    unit[(v >= 10**15) & (v < 10**16)] = "us"
    return unit


def _to_utc(v: np.ndarray, unit: np.ndarray) -> pd.Series:
    us = np.where(unit == "ms", v * 1000, v).astype("int64")
    return pd.Series(pd.to_datetime(us, unit="us", utc=True))


def parse_kline_csv(text: str | bytes) -> pd.DataFrame:
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    first = text.lstrip().split("\n", 1)[0]
    has_header = bool(first) and not first.split(",")[0].strip().lstrip("-").isdigit()
    raw = pd.read_csv(io.StringIO(text), header=None, names=RAW_COLS, skiprows=1 if has_header else 0,
                      dtype={"open_time": "int64", "close_time": "int64", "trades": "int64"})
    ot = raw["open_time"].to_numpy("int64")
    ct = raw["close_time"].to_numpy("int64")
    u_ot, u_ct = _unit_of(ot), _unit_of(ct)
    if (u_ot == "").any() or (u_ct == "").any():
        raise ValueError("timestamp with unknown magnitude (neither ms nor us)")
    if (u_ot != u_ct).any():
        raise ValueError("open_time and close_time units differ within a row")
    out = pd.DataFrame({
        "open_time": _to_utc(ot, u_ot),
        "open": raw["open"].astype(float), "high": raw["high"].astype(float),
        "low": raw["low"].astype(float), "close": raw["close"].astype(float),
        "volume": raw["volume"].astype(float),
        "close_time": _to_utc(ct, u_ct),
        "quote_volume": raw["quote_volume"].astype(float),
        "trades": raw["trades"].astype("int64"),
        "taker_buy_base": raw["taker_buy_base"].astype(float),
        "taker_buy_quote": raw["taker_buy_quote"].astype(float),
        "ts_unit": pd.Series(u_ot, dtype=object),
    })
    return out[OUT_COLS]
