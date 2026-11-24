"""1m -> 5m aggregation (complete, aligned buckets only) and the regular 5m grid."""
from __future__ import annotations

import pandas as pd

FIVE = pd.Timedelta(minutes=5)
SUM_COLS = ["volume", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"]


def aggregate_5m(d1m: pd.DataFrame) -> pd.DataFrame:
    """A 5m candle is built only if all five 1m candles of its aligned bucket are present (once each).
    close_time = bucket open + 5m."""
    d = d1m.drop_duplicates("open_time").sort_values("open_time", kind="mergesort")
    bucket = d["open_time"].dt.floor("5min")
    g = d.groupby(bucket, sort=True)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    for c in SUM_COLS:
        if c in d:
            agg[c] = "sum"
    out = g.agg(agg)
    cnt = g.size()
    out = out[cnt == 5]
    out.index.name = "open_time"
    out = out.reset_index()
    out.insert(1, "close_time", out["open_time"] + FIVE)
    if "trades" in out:
        out["trades"] = out["trades"].astype("int64")
    return out.reset_index(drop=True)


def to_grid(m5: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Reindex 5m candles onto the regular grid [start, end); missing candles are NaN rows, present=False."""
    idx = pd.date_range(start, end, freq="5min", inclusive="left", name="open_time")
    src = m5.set_index("open_time")
    src = src[~src.index.duplicated(keep="first")]
    if "close_time" in src:
        src = src.drop(columns=["close_time"])
    g = src.reindex(idx)
    g["present"] = idx.isin(src.index)
    return g
