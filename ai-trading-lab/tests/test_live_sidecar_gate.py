import json

import numpy as np
import pandas as pd
import pytest

from src.data.aggregate import aggregate_5m
from src.data.parse import parse_kline_csv
from src.ftbridge.sidecar import join_sidecar
from src.live.kline_stream import KlineAssembler
from tests.helpers import kline_rows

MS0 = 1_767_225_600_000  # 2026-01-01T00:00Z


def _msg(i, closed=True, sym="BTCUSDT", price=100.0):
    t = MS0 + i * 60_000
    return {"e": "kline", "s": sym, "k": {"t": t, "T": t + 59_999, "s": sym, "i": "1m", "o": str(price),
            "h": str(price + 1), "l": str(price - 1), "c": str(price + 0.5), "v": "10.0", "n": 42, "x": closed,
            "q": "1000.0", "V": "4.0", "Q": "400.0"}}


def test_stream_closed_only_dedup_gap_and_stale_fail_closed():
    a = KlineAssembler("BTCUSDT")
    assert a.on_message(_msg(0, closed=False)) is None
    a.on_message(_msg(0)); a.on_message(_msg(0)); a.on_message(_msg(1)); a.on_message(_msg(4))
    a.on_message(_msg(2))  # late/out of order
    a.on_message(_msg(5, sym="ETHUSDT"))
    assert a.stats == {"accepted": 3, "ignored_open": 1, "duplicates": 1, "out_of_order": 1, "wrong_symbol": 1}
    now = pd.Timestamp("2026-01-01T00:05:10Z")
    assert a.gaps and not a.can_signal(now)
    a.fill_gap([{**a.rows[0], "open_time": pd.Timestamp("2026-01-01T00:02Z")},
                {**a.rows[0], "open_time": pd.Timestamp("2026-01-01T00:03Z")}])
    assert not a.gaps and a.can_signal(now)
    assert a.is_stale(pd.Timestamp("2026-01-01T00:08Z")) and not a.can_signal(pd.Timestamp("2026-01-01T00:08Z"))


def test_stream_rows_match_historical_parser_and_aggregation():
    a = KlineAssembler("BTCUSDT")
    for i in range(10):
        a.on_message(_msg(i))
    live = a.frame()
    hist = parse_kline_csv(kline_rows(MS0 * 1000, 10, "ms"))
    cols = ["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote"]
    pd.testing.assert_frame_equal(live[cols].reset_index(drop=True), hist[cols].reset_index(drop=True),
                                  check_dtype=False)
    pd.testing.assert_frame_equal(aggregate_5m(live), aggregate_5m(hist), check_dtype=False)


def test_sidecar_join_exact_close_time_no_leakage_and_fail_closed():
    dates = pd.date_range("2026-01-01", periods=6, freq="5min", tz="UTC")
    ohlcv = pd.DataFrame({"date": dates, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                          "volume": [10, 20, 30, 40, 50, 60.0]})
    side = pd.DataFrame({"open_time": dates, "close_time": dates + pd.Timedelta(minutes=5),
                         "volume": [10, 20, 30, 40, 50, 60.0], "taker_buy_base": [1, 2, 3, 4, 5, 6.0]})
    side = side.drop(index=[3])            # missing sidecar row
    side.loc[4, "volume"] = 51.0           # inconsistent row
    j = join_sidecar(ohlcv, side)
    # each candle gets its OWN taker volume (closed at date+5m), never the next candle's
    assert list(j["taker_buy_base"].iloc[:3]) == [1, 2, 3]
    assert np.isnan(j["taker_buy_base"].iloc[3]) and np.isnan(j["taker_buy_base"].iloc[4])
    assert j["taker_buy_base"].iloc[5] == 6
    shifted = side.assign(close_time=side["close_time"] + pd.Timedelta(minutes=5))  # leakage attempt
    j2 = join_sidecar(ohlcv, shifted)
    assert j2["taker_buy_base"].isna().sum() >= 4  # volumes no longer agree -> fail closed
    with pytest.raises(ValueError):
        join_sidecar(ohlcv, pd.concat([side, side.iloc[[0]]]))


def test_cli_refuses_locked_test_and_bad_approvals(tmp_path):
    from src import cli
    from src.config import load_config, code_hash
    assert cli.main(["backtest", "--split", "test"]) == 4
    cfg = load_config()
    ok, why = cli.verify_approval(cfg, None)
    assert not ok
    p = tmp_path / "approval.json"
    p.write_text(json.dumps({"approved_by": "x", "approved_utc": "2026-11-25", "code_sha256": "0" * 64,
                             "config_sha256": cfg["_hash"],
                             "statement": "I approve a single run of the locked test split for experiment "
                                          + cfg["experiment_id"]}))
    ok, why = cli.verify_approval(cfg, p)
    assert not ok and "code hash" in why
    p.write_text(json.dumps({"approved_by": "x"}))
    assert not cli.verify_approval(cfg, p)[0]
    assert cli.main(["holdout"]) == 5


def test_store_gate_blocks_test_split():
    from src.config import load_config
    from src.data import store
    with pytest.raises(PermissionError):
        store.load_for_split(load_config(), "BTCUSDT", "test", "1m")


def test_live_mode_config_forbidden(tmp_path):
    from src.config import load_config, DEFAULT_CONFIG
    txt = DEFAULT_CONFIG.read_text().replace("mode: research_replay", "mode: live")
    p = tmp_path / "c.yaml"; p.write_text(txt)
    with pytest.raises(ValueError):
        load_config(p)
