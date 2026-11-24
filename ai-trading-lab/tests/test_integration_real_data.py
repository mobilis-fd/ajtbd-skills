"""Integration tests on the downloaded development data (skipped if data has not been built)."""
import json

import pandas as pd
import pytest

from src.config import ROOT, load_config, split_bounds

CFG = load_config()
HAVE_DATA = (ROOT / CFG["data"]["processed_dir"] / "BTCUSDT_1m.parquet").exists()
pytestmark = pytest.mark.skipif(not HAVE_DATA, reason="processed data not built (run download + validate-data)")


def test_split_loader_never_returns_rows_beyond_split_end():
    from src.data import store
    for split in ("development", "validation"):
        s, e = split_bounds(CFG, split)
        for tf in ("1m", "5m"):
            d = store.load_for_split(CFG, "BTCUSDT", split, tf)
            assert d["open_time"].max() < e
            assert d["open_time"].min() >= s - pd.Timedelta(days=7)
            assert str(d["open_time"].dt.tz) == "UTC"


def test_splits_are_contiguous_and_non_overlapping():
    dev, val, test = (split_bounds(CFG, s) for s in ("development", "validation", "test"))
    assert dev[1] == val[0] and val[1] == test[0]
    assert dev[0] == pd.Timestamp(CFG["data"]["start"]) and test[1] == pd.Timestamp(CFG["data"]["end"])


def test_prefix_check_on_real_data_small():
    from src.signals.prefix_check import run_prefix_checks
    res = run_prefix_checks(CFG, n_cuts=3)
    assert res["ok"], res["details"]


def test_smoke_run_reproducible(tmp_path):
    from src.evaluation.pipeline import run_split
    a = run_split(CFG, "development", out_root=tmp_path / "a", smoke_days=1, n_seeds=3)
    b = run_split(CFG, "development", out_root=tmp_path / "b", smoke_days=1, n_seeds=3)
    ma = json.loads((a / "manifest.json").read_text())["outputs_sha256"]
    mb = json.loads((b / "manifest.json").read_text())["outputs_sha256"]
    assert ma == mb
    rec = json.loads((a / "reconciliation.json").read_text())
    assert all(v["ok"] for v in rec.values())
