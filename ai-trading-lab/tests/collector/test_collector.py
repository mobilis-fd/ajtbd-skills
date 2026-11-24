import json

import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.collector import core as C

T0 = pd.Timestamp("2026-11-25T00:00:00Z")
MS = int(T0.value // 1_000_000)


def kline(i, x=True):
    t = MS + i * 60_000
    return {"e": "kline", "E": t + 60_100, "s": "BTCUSDT",
            "k": {"t": t, "T": t + 59_999, "s": "BTCUSDT", "i": "1m", "x": x, "L": 1000 + i, "o": "1", "c": "1",
                  "h": "1", "l": "1", "v": "1", "n": 1, "q": "1", "V": "0.5", "Q": "0.5"}}


def test_public_only_guard():
    C.assert_public_url("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT")
    for bad in ("https://api.binance.com/api/v3/order", "https://api.binance.com/api/v3/account",
                "https://api.binance.com/sapi/v1/capital/config/getall"):
        with pytest.raises(PermissionError):
            C.assert_public_url(bad)


def test_closed_kline_only_and_dedup():
    assert C.parse_spot_kline(kline(0, x=False), T0) is None
    r = C.parse_spot_kline(kline(0), T0)
    assert r["sample_time"] == T0 and r["schema_version"] == C.SCHEMA_VERSION
    d = C.Deduper()
    keys = [(r["stream"], r["symbol"], r["source_sequence"])] * 2
    assert [d.is_new(k) for k in keys] == [True, False] and d.duplicates == 1


def test_book_ticker_no_event_time_is_null_and_sampler_staleness():
    m = {"u": 42, "s": "ETHUSDT", "b": "100.0", "B": "1", "a": "100.1", "A": "1"}
    r = C.parse_book_ticker(m, T0)
    assert r["event_time"] is None and "no_event_time" in r["flags"]
    s = C.BookTickerSampler()
    assert s.sample("ETHUSDT", T0)["status"] == "missing"
    s.on_quote(m, T0)
    ok = s.sample("ETHUSDT", T0 + pd.Timedelta(seconds=3))
    assert ok["status"] == "ok" and ok["quote_age_s"] == 3 and ok["spread_bps"] == pytest.approx(9.995, rel=1e-3)
    assert s.sample("ETHUSDT", T0 + pd.Timedelta(seconds=6))["status"] == "missing"   # no ffill beyond 5 s


def test_kline_stale_rule_and_gap_detection():
    end = T0
    assert C.kline_valid_for_signal(end, end + pd.Timedelta(seconds=30), end)
    assert not C.kline_valid_for_signal(end, end + pd.Timedelta(seconds=91), end)
    assert not C.kline_valid_for_signal(end, None, end + pd.Timedelta(seconds=10))
    g = C.kline_gaps([T0, T0 + pd.Timedelta(minutes=1), T0 + pd.Timedelta(minutes=4)])
    assert g == [{"start": T0 + pd.Timedelta(minutes=2), "end_exclusive": T0 + pd.Timedelta(minutes=4), "minutes": 2}]


def test_backoff_and_clock_skew():
    b = C.Backoff(base=1, cap=8)
    d = [b.next_delay() for _ in range(6)]
    assert all(0.5 * min(8, 2 ** i) <= x <= min(8, 2 ** i) for i, x in enumerate(d))
    b.reset()
    assert b.next_delay() <= 1
    o = C.clock_offset(T0, T0 + pd.Timedelta(milliseconds=800), T0 + pd.Timedelta(milliseconds=200))
    assert o["offset_ms"] == pytest.approx(700) and o["rtt_ms"] == pytest.approx(200)
    assert C.clock_skew_alert([700, 650, 720]) and not C.clock_skew_alert([10, -20])


def test_open_interest_units_and_usd_separate():
    r = C.parse_open_interest({"symbol": "BTCUSDT", "openInterest": "1000.5", "time": MS}, T0, T0, 50_000.0)
    p = json.loads(r["payload"])
    assert p["oi_units"] == 1000.5 and p["oi_usd_at_mark"] == pytest.approx(1000.5 * 50_000)


def test_funding_asof_uses_publication_lag_not_settlement():
    evs = [C.parse_funding_event({"symbol": "BTCUSDT", "fundingTime": MS + h * 3_600_000, "fundingRate": str(r),
                                  "markPrice": "1"}, T0, lag_min=5) for h, r in ((0, 0.0001), (8, 0.0003))]
    df = pd.DataFrame([{"available_time": e["available_time"], "fundingRate": json.loads(e["payload"])["fundingRate"]}
                       for e in evs])
    dec = pd.DatetimeIndex([T0 - pd.Timedelta(minutes=1), T0 + pd.Timedelta(minutes=4), T0 + pd.Timedelta(minutes=5),
                            T0 + pd.Timedelta(hours=8, minutes=2), T0 + pd.Timedelta(hours=8, minutes=6)])
    s = C.funding_asof(dec, df)
    assert pd.isna(s.iloc[0]) and pd.isna(s.iloc[1]) and s.iloc[2] == 0.0001
    assert s.iloc[3] == 0.0001 and s.iloc[4] == 0.0003


def test_writer_atomic_partition_checksum_schema_and_quota(tmp_path):
    w = C.PartitionWriter(tmp_path, quota_bytes=10 ** 9)
    rows = [C.parse_spot_kline(kline(i), T0) for i in range(5)]
    p = w.write(rows, 1)
    assert "venue=binance/market=spot/type=kline_1m/date=2026-11-25/symbol=BTCUSDT" in str(p)
    t = pq.read_table(p)
    assert t.column_names == C.RECORD_FIELDS and t.num_rows == 5
    assert pq.ParquetFile(p).metadata.row_group(0).column(0).compression == "ZSTD"
    idx = [json.loads(x) for x in (tmp_path / "_index.jsonl").read_text().splitlines()]
    assert idx[0]["rows"] == 5 and len(idx[0]["sha256"]) == 64
    assert not list(tmp_path.rglob(".tmp-*"))
    small = C.PartitionWriter(tmp_path, quota_bytes=1)
    with pytest.raises(C.QuotaExceeded):
        small.write(rows, 2)
    gaps = (tmp_path / "_gaps.jsonl").read_text()
    assert "disk_quota_exceeded" in gaps and not list(tmp_path.rglob(".tmp-*"))


def test_cli_refuses_without_authorization():
    from src.collector.cli import main
    assert main(["smoke", "--duration", "900"]) == 6
