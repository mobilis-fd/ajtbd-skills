"""Export verified OHLCV to Freqtrade's feather format and write the extended-data sidecar.

Only development+validation range is exported (locked test candles are never written to user_data).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import ROOT, split_bounds
from src.data import store

FT_DATA = ROOT / "user_data" / "data" / "binance"
SIDECAR = ROOT / "user_data" / "data" / "sidecar"


def ft_pair(symbol: str) -> str:
    return symbol.replace("USDT", "/USDT")


def export_freqtrade_data(cfg: dict) -> dict:
    from freqtrade.data.history import get_datahandler
    from freqtrade.enums import CandleType
    dev_s, _ = split_bounds(cfg, "development")
    _, val_e = split_bounds(cfg, "validation")
    warm = dev_s - pd.Timedelta(days=cfg["data"]["warmup_days"])
    FT_DATA.mkdir(parents=True, exist_ok=True)
    SIDECAR.mkdir(parents=True, exist_ok=True)
    dh = get_datahandler(FT_DATA, "feather")
    out = {}
    for sym in cfg["data"]["symbols"]:
        for tf in ("1m", "5m"):
            d = store.load(cfg, sym, tf, warm, val_e)
            ft = pd.DataFrame({"date": d["open_time"], "open": d["open"], "high": d["high"], "low": d["low"],
                               "close": d["close"], "volume": d["volume"]})
            dh.ohlcv_store(ft_pair(sym), tf, ft, CandleType.SPOT)
            out[f"{sym}-{tf}"] = int(len(ft))
            if tf == "5m":
                side = d[["open_time", "close_time", "volume", "quote_volume", "trades", "taker_buy_base",
                          "taker_buy_quote"]].copy()
                side.to_parquet(SIDECAR / f"{sym}_5m_ext.parquet", index=False)
    out["range"] = [str(warm), str(val_e)]
    return out
