import numpy as np
import pandas as pd
import pytest

from src.data.aggregate import aggregate_5m, to_grid
from src.data.download import months_needed
from src.data.parse import parse_kline_csv
from src.data.validate import check_1m, clean_1m
from tests.helpers import kline_rows

US0 = 1_767_225_600_000_000  # 2026-01-01T00:00:00Z in microseconds


def test_parse_us_and_ms_give_same_utc():
    a = parse_kline_csv(kline_rows(US0, 3, "us"))
    b = parse_kline_csv(kline_rows(US0, 3, "ms"))
    assert list(a["ts_unit"]) == ["us"] * 3 and list(b["ts_unit"]) == ["ms"] * 3
    assert (a["open_time"] == b["open_time"]).all()
    assert a["open_time"].iloc[0] == pd.Timestamp("2026-01-01T00:00:00Z")
    assert str(a["open_time"].dt.tz) == "UTC"
    # close time = open + 1m - 1 unit
    assert a["close_time"].iloc[0] == pd.Timestamp("2026-01-01T00:00:59.999999Z")
    assert b["close_time"].iloc[0] == pd.Timestamp("2026-01-01T00:00:59.999Z")


def test_parse_header_and_columns():
    hdr = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,"
           "taker_buy_quote_volume,ignore\n")
    d = parse_kline_csv(hdr + kline_rows(US0, 2))
    assert len(d) == 2
    for c in ["volume", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"]:
        assert c in d
    assert d["trades"].iloc[0] == 42 and d["taker_buy_base"].iloc[0] == 4.0


def test_parse_rejects_unknown_magnitude():
    with pytest.raises(ValueError):
        parse_kline_csv("12345,1,1,1,1,1,12399,1,1,1,1,0\n")


def _df(n=10):
    return parse_kline_csv(kline_rows(US0, n))


def test_validate_counts_duplicates_gaps_and_invariants():
    d = _df(10)
    d = pd.concat([d, d.iloc[[3]]], ignore_index=True)           # exact duplicate
    d = d.drop(index=[5]).reset_index(drop=True)                  # gap
    d.loc[0, "taker_buy_base"] = 99.0                             # taker > total
    d.loc[1, "high"] = 50.0                                       # OHLC violation
    d.loc[2, "volume"] = 0.0; d.loc[2, "taker_buy_base"] = 0.0    # zero volume (allowed, counted)
    s = pd.Timestamp("2026-01-01T00:00Z")
    r = check_1m(d, s, s + pd.Timedelta(minutes=10))
    assert r["missing_minutes"] == 1 and r["gaps"][0]["minutes"] == 1
    assert r["duplicate_open_time"] == 2 and r["duplicate_full_rows"] == 1
    assert r["taker_gt_total"] == 1 and r["ohlc_invariant_violations"] == 1
    assert r["zero_volume_rows"] == 1
    assert r["ts_units"] == {"us": 10}


def test_clean_drops_exact_and_conflicting_duplicates_without_filling():
    d = _df(6)
    dup = d.iloc[[2]].copy()
    conflict = d.iloc[[4]].copy(); conflict["close"] = 100.7
    d2 = pd.concat([d, dup, conflict], ignore_index=True).sample(frac=1, random_state=1)
    c, log = clean_1m(d2)
    assert log["exact_duplicates_dropped"] == 1 and log["conflicting_duplicates_dropped"] == 2
    assert len(c) == 5 and c["open_time"].is_monotonic_increasing
    assert d.iloc[4]["open_time"] not in set(c["open_time"])  # not repaired


def test_aggregate_5m_values_and_incomplete_bucket_dropped():
    d = _df(10)
    d["open"] = np.arange(10) + 100.0
    d["close"] = d["open"] + 0.5
    d["high"] = d["open"] + 2 + (np.arange(10) == 2) * 5
    d["low"] = d["open"] - 1
    d["volume"] = 1.0 + np.arange(10)
    d["taker_buy_base"] = 0.5
    m5 = aggregate_5m(d.drop(index=[7]))  # second bucket incomplete
    assert len(m5) == 1
    r = m5.iloc[0]
    assert r["open"] == 100 and r["close"] == 104.5 and r["high"] == 109 and r["low"] == 99
    assert r["volume"] == sum(range(1, 6)) and r["trades"] == 5 * 42 and r["taker_buy_base"] == 2.5
    assert r["open_time"] == pd.Timestamp("2026-01-01T00:00Z")
    assert r["close_time"] == pd.Timestamp("2026-01-01T00:05Z")
    g = to_grid(m5, pd.Timestamp("2026-01-01T00:00Z"), pd.Timestamp("2026-01-01T00:10Z"))
    assert list(g["present"]) == [True, False] and np.isnan(g["close"].iloc[1])


def test_aggregate_rejects_misaligned_bucket():
    d = _df(6).iloc[1:6].copy()  # minutes 1..5: bucket 0 has 4 rows, bucket 5 has 1
    assert len(aggregate_5m(d)) == 0


def test_months_needed_includes_warmup():
    m = months_needed(pd.Timestamp("2025-11-01T00:00Z"), pd.Timestamp("2026-11-01T00:00Z"), 7)
    assert m[0] == "2025-10" and m[-1] == "2026-10" and len(m) == 13
