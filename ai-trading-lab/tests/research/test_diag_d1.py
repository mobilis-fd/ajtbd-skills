import numpy as np
import pandas as pd
import pytest

from src.research.diag_d1 import boot_diff, execute_signals, fit_index_unit_safe
from src.research.replay import Px

G0 = pd.Timestamp("2023-01-02T00:00:00Z")
M = pd.Timedelta(minutes=1)


def _m1(n, prices):
    t = G0 + np.arange(n) * M
    return pd.DataFrame({"open_time": t, "open": prices, "high": prices, "low": prices, "close": prices})


CFG = {"costs": {"main": {"fee_bps": 10.0, "slip_bps": 2.5}, "rt0": {"fee_bps": 0.0, "slip_bps": 0.0}},
       "execution": {"filters": {"SOLUSDT": {"tick_size": 0.01, "step_size": 0.001, "min_notional": 10.0}}}}


def test_fit_index_unit_safe_handles_mixed_resolutions():
    fits = pd.DatetimeIndex(["2023-01-01", "2023-02-01"], tz="UTC").as_unit("ns")
    T = pd.DatetimeIndex(["2022-12-31T23:00", "2023-01-15", "2023-02-01"], tz="UTC").as_unit("us")
    assert fit_index_unit_safe(T, fits).tolist() == [-1, 0, 1]


def test_execute_signals_decomposition_and_zero_cost_residual():
    n = 300
    prices = 21.37 + 0.01 * np.arange(n)            # SOL-like price, on the 0.01 grid
    ctx = {"px": {"SOLUSDT": Px(_m1(n, prices), G0, G0 + n * M)}}
    rows = pd.DataFrame({"T": [G0 + 10 * M, G0 + 50 * M], "symbol": "SOLUSDT"})
    ex = execute_signals(rows, ctx, CFG, 60, "main", 1)
    assert len(ex) == 2
    assert np.allclose(ex["gross"] - ex["fees"] - ex["adverse"] - ex["rounding"], ex["net"])
    assert (ex["rounding"] > 0).all() and (ex["notional"] <= 50 + 1e-9).all()
    z = execute_signals(rows, ctx, CFG, 60, "rt0", 1)
    assert np.allclose(z["rounding"], 0) and np.allclose(z["fees"], 0) and np.allclose(z["net"], z["gross"])


def test_boot_diff_keeps_days_together_and_detects_shift():
    rng = np.random.default_rng(0)
    days = pd.date_range("2023-01-01", periods=200, freq="D", tz="UTC")
    T = np.repeat(days, 10) + pd.Timedelta(hours=1)
    base = pd.DataFrame({"T": T, "v": rng.normal(0, 1, len(T))})
    day_shock = np.repeat(rng.normal(0, 3, len(days)), 10)            # strong common day effect (clustering)
    base["v"] += day_shock
    sig = base.iloc[::2].copy()
    sig["v"] += 0.0
    r = boot_diff(sig, base, "v", days, 14, 500, 42, 5)
    lo, hi = r["ci95_mean"]
    naive_se = sig["v"].std() / np.sqrt(len(sig))
    assert hi - lo > 4 * naive_se                    # day-block CI is wider than the naive iid CI
    assert r["ci95_diff"][0] < 0 < r["ci95_diff"][1]
    sig2 = sig.assign(v=sig["v"] + 1.0)
    assert boot_diff(sig2, base, "v", days, 14, 500, 42, 5)["share_boot_diff_le_0"] < 0.05


def test_cli_refuses_d1_without_confirmation():
    from src.research import cli
    assert cli.main(["diag-d1", "--split", "development"]) == 6
