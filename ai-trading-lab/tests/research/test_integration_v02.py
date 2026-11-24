"""Integration tests on real downloaded v0.2 data (skipped if not built). No historical-test data involved."""
import copy

import numpy as np
import pandas as pd
import pytest

from src.config import ROOT, load_config

CFG = load_config(ROOT / "configs" / "multi_horizon_v02.yaml")
HAVE = (ROOT / CFG["data"]["processed_dir"] / "BTCUSDT_1m.parquet").exists()
pytestmark = pytest.mark.skipif(not HAVE, reason="v0.2 data not built")


def _ctx(end):
    from src.research.pipeline import load_ctx
    c = copy.deepcopy(CFG)
    c["splits"]["development"]["end"] = end
    return c, load_ctx(c, "development")


def test_end_to_end_prefix_invariance_of_predictions_and_signals():
    """Truncating ALL data at an earlier date leaves every common prediction/signal/estimate unchanged."""
    from src.research.pipeline import g01_panel, h_panel
    ca, a = _ctx("2022-01-15T00:00:00Z")
    cb, b = _ctx("2022-03-01T00:00:00Z")
    ga, gb = g01_panel(ca, a)["panel"], g01_panel(cb, b)["panel"]
    key = ["T", "symbol", "H"]
    m = ga.merge(gb, on=key, suffixes=("_a", "_b"))
    assert len(m) > 1000 and len(m) == len(ga)
    for c in ("pred_B0", "pred_B1", "pred_X", "y", "y5", "sigma1h"):
        np.testing.assert_allclose(m[c + "_a"], m[c + "_b"], rtol=0, atol=1e-12, equal_nan=True)
    for fam in ("H01", "H02", "H03"):
        ha, hb = h_panel(ca, a, fam)["panel"], h_panel(cb, b, fam)["panel"]
        mm = ha.merge(hb, on=key, suffixes=("_a", "_b"))
        assert len(mm) == len(ha) and len(mm) > 0
        assert (mm["signal_a"] == mm["signal_b"]).all()
        np.testing.assert_allclose(mm["est_a"], mm["est_b"], rtol=0, atol=1e-15, equal_nan=True)
        np.testing.assert_allclose(mm["y_a"], mm["y_b"], rtol=0, atol=0, equal_nan=True)


def test_dev_context_never_loads_beyond_split_end():
    from src.research.pipeline import load_ctx
    ctx = load_ctx(CFG, "development")
    e = pd.Timestamp(CFG["splits"]["development"]["end"])
    for p in ctx["px"].values():
        assert p.g0 + p.n * pd.Timedelta(minutes=1) == e
    for m, d in ctx["bars"].items():
        for g in d.values():
            assert g.index.max() <= e


def test_locked_split_refused():
    from src.research.pipeline import load_ctx
    from src.research import cli
    with pytest.raises(PermissionError):
        load_ctx(CFG, "test")
    assert cli.main(["run", "--split", "test"]) == 4
    assert cli.main(["historical-test"]) == 5
