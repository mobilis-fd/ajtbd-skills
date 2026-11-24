"""Integrity checks and conservative cleaning of 1m klines (DECISIONS D06: never repair or invent candles)."""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

ONE_MIN = pd.Timedelta(minutes=1)
PRICE = ["open", "high", "low", "close"]
VOLS = ["volume", "quote_volume", "taker_buy_base", "taker_buy_quote"]


def _ohlc_bad(d: pd.DataFrame) -> pd.Series:
    o, h, l, c = (d[k] for k in PRICE)
    return (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)


def _close_time_bad(d: pd.DataFrame) -> pd.Series:
    base = d["open_time"] + ONE_MIN
    if "ts_unit" not in d:  # unit unknown (e.g. processed data): accept either convention
        return (d["close_time"] != base - pd.Timedelta(microseconds=1)) & \
               (d["close_time"] != base - pd.Timedelta(milliseconds=1))
    eps = np.where(d["ts_unit"].to_numpy() == "us", pd.Timedelta(microseconds=1), pd.Timedelta(milliseconds=1))
    return d["close_time"] != base - pd.to_timedelta(eps)


def _not_aligned(d: pd.DataFrame) -> pd.Series:
    return d["open_time"] != d["open_time"].dt.floor("min")


def _invalid(d: pd.DataFrame) -> pd.Series:
    bad = _ohlc_bad(d) | (d[PRICE] <= 0).any(axis=1) | (d[[c for c in VOLS if c in d]] < 0).any(axis=1)
    bad |= d["taker_buy_base"] > d["volume"]
    bad |= _not_aligned(d)
    if "close_time" in d:
        bad |= _close_time_bad(d)
    return bad


def _gaps(present: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    grid = pd.date_range(start, end, freq="min", inclusive="left")
    miss = ~grid.isin(present)
    gaps, i, n = [], 0, len(grid)
    while i < n:
        if miss[i]:
            j = i
            while j < n and miss[j]:
                j += 1
            gaps.append({"start": str(grid[i]), "end_exclusive": str(grid[j - 1] + ONE_MIN), "minutes": int(j - i)})
            i = j
        else:
            i += 1
    return gaps


def check_1m(d: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Integrity report for rows with open_time in [start, end). No price/return statistics."""
    r = d[(d["open_time"] >= start) & (d["open_time"] < end)]
    expected = int((end - start) // ONE_MIN)
    uniq = pd.DatetimeIndex(r["open_time"].unique())
    aligned = uniq[uniq == uniq.floor("min")]
    ot = r["open_time"]
    steps = ot.diff().dropna()
    out = {
        "rows_in_range": int(len(r)),
        "expected_minutes": expected,
        "missing_minutes": int(expected - len(aligned)),
        "completeness": float(len(aligned) / expected) if expected else 0.0,
        "duplicate_open_time": int(ot.duplicated(keep=False).sum()),
        "duplicate_full_rows": int(r.duplicated(keep="first").sum()),
        "non_monotonic_steps": int((steps <= pd.Timedelta(0)).sum()),
        "not_minute_aligned": int(_not_aligned(r).sum()),
        "bad_close_time": int(_close_time_bad(r).sum()) if "close_time" in r else 0,
        "ohlc_invariant_violations": int(_ohlc_bad(r).sum()),
        "nonpositive_price": int((r[PRICE] <= 0).any(axis=1).sum()),
        "negative_volume": int((r[[c for c in VOLS if c in r]] < 0).any(axis=1).sum()),
        "taker_gt_total": int((r["taker_buy_base"] > r["volume"]).sum()),
        "zero_volume_rows": int((r["volume"] == 0).sum()),
        "ts_units": dict(Counter(r["ts_unit"])) if "ts_unit" in r else {},
        "gaps": _gaps(aligned, start, end),
    }
    out["ts_units"] = {str(k): int(v) for k, v in sorted(out["ts_units"].items())}
    return out


def clean_1m(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Drop exact duplicates (keep one), drop every row of a conflicting duplicate open_time, drop invalid rows.
    Missing minutes stay missing (no filling)."""
    n0 = len(d)
    d1 = d.drop_duplicates(keep="first")
    exact = n0 - len(d1)
    conflict_mask = d1["open_time"].duplicated(keep=False)
    conflicting = int(conflict_mask.sum())
    d2 = d1[~conflict_mask]
    inv = _invalid(d2)
    d3 = d2[~inv].sort_values("open_time", kind="mergesort").reset_index(drop=True)
    return d3, {"exact_duplicates_dropped": int(exact), "conflicting_duplicates_dropped": conflicting,
                "invalid_rows_dropped": int(inv.sum())}
