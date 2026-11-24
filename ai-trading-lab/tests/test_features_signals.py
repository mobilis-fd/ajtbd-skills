import numpy as np
import pandas as pd

from src.data.aggregate import to_grid
from src.features.core import compute_features, regime_label
from src.signals.rules import e01, e02, random_signal_times

E01P = {"z5_prev_max": -2.0, "r5_prev_max": -0.004, "r5_min_exclusive": 0.0, "close_gt_open": True, "rv_prev_min": 1.5}
E01F = {**E01P, "imb_prev_max": -0.20, "imb_min": 0.0}
E02P = {"r15_min": 0.005, "z15_min": 2.0, "breakout": True, "rv_min": 1.5}
E02F = {**E02P, "imb_min": 0.20}


def grid_from(close, volume=None, taker=None, start="2026-01-01T00:00Z", high=None, open_=None):
    n = len(close)
    idx = pd.date_range(start, periods=n, freq="5min", tz="UTC", name="open_time")
    c = np.asarray(close, float)
    df = pd.DataFrame({"open": open_ if open_ is not None else c, "high": high if high is not None else c,
                       "low": c, "close": c,
                       "volume": volume if volume is not None else np.ones(n),
                       "taker_buy_base": taker if taker is not None else 0.5 * np.ones(n)}, index=idx)
    return df


def test_z5_uses_previous_window_only_ddof0():
    rng = np.random.default_rng(0)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 30)))
    f = compute_features(grid_from(c), z_window=5, rv_window=3, breakout_window=2, regime_lookback=5)
    r = np.log(c[1:] / c[:-1])
    t = 12  # index in grid
    prev = r[t - 1 - 5:t - 1]  # r5 at grid t-5..t-1 (r index shifted by 1)
    exp = (r[t - 1] - prev.mean()) / prev.std(ddof=0)
    assert np.isclose(f["z5"].iloc[t], exp)
    # z15 on overlapping r15 series
    r15 = np.log(c[3:] / c[:-3])  # r15 at grid index 3..
    prev15 = r15[t - 3 - 5:t - 3]
    assert np.isclose(f["z15"].iloc[t], (r15[t - 3] - prev15.mean()) / prev15.std(ddof=0))


def test_rv_median_previous_and_imbalance_from_sums():
    vol = np.array([1, 2, 3, 10, 4, 0.0])
    tak = np.array([0.5, 1, 1.5, 9, 1, 0])
    f = compute_features(grid_from(np.full(6, 100.0), vol, tak), z_window=3, rv_window=3, breakout_window=2,
                         regime_lookback=3)
    assert np.isclose(f["rv"].iloc[3], 10 / 2)
    assert np.isclose(f["imb"].iloc[3], 2 * 9 / 10 - 1)
    assert np.isnan(f["imb"].iloc[5])  # zero volume -> no imbalance
    # zero-volume median denominator -> NaN
    f2 = compute_features(grid_from(np.full(5, 100.0), np.zeros(5)), 3, 3, 2, 3)
    assert f2["rv"].isna().all()


def test_missing_candle_kills_windows():
    rng = np.random.default_rng(1)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 40)))
    g = grid_from(c)
    m5 = g.reset_index().drop(index=[20])
    grid = to_grid(m5, g.index[0], g.index[-1] + pd.Timedelta(minutes=5))
    f = compute_features(grid, z_window=5, rv_window=3, breakout_window=2, regime_lookback=5)
    assert f["r5"].iloc[20:22].isna().all()
    assert f["z5"].iloc[21:27].isna().all()  # window covering the missing return
    assert f["rv"].iloc[21:24].isna().all()


def test_prefix_and_future_mutation_invariance_synthetic():
    rng = np.random.default_rng(2)
    n = 700
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
    g = grid_from(c, rng.uniform(1, 5, n), rng.uniform(0, 1, n), high=c * 1.001, open_=np.r_[c[0], c[:-1]])
    full = compute_features(g)
    for cut in (300, 450, 699):
        pre = compute_features(g.iloc[:cut])
        pd.testing.assert_frame_equal(pre, full.iloc[:cut])
        mut = g.copy()
        mut.iloc[cut:, :4] *= 1.3
        mut.iloc[cut:, 4] *= 7
        pd.testing.assert_frame_equal(compute_features(mut).iloc[:cut], full.iloc[:cut])


def _feat_frame(**cols):
    n = len(next(iter(cols.values())))
    base = {"present": [True] * n, "z5": [0.0] * n, "r5": [0.0] * n, "r15": [0.0] * n, "z15": [0.0] * n,
            "rv": [1.0] * n, "imb": [0.0] * n, "prev_max_high": [100.0] * n, "close": [100.0] * n, "open": [100.0] * n}
    base.update(cols)
    return pd.DataFrame(base, index=pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"))


def test_e01_rule_exact_thresholds():
    f = _feat_frame(z5=[-2.0, 0.0], r5=[-0.004, 0.001], rv=[1.5, 1.0], close=[99, 101], open=[100, 100],
                    imb=[-0.2, 0.0])
    assert list(e01(f, E01P)) == [False, True]
    assert list(e01(f, E01F)) == [False, True]
    f2 = f.copy(); f2.iloc[1, f2.columns.get_loc("imb")] = -0.01
    assert list(e01(f2, E01F)) == [False, False]
    f3 = f.copy(); f3.iloc[1, f3.columns.get_loc("close")] = 100  # C(t) > O(t) required
    assert not e01(f3, E01P).any()
    f4 = f.copy(); f4.iloc[0, f4.columns.get_loc("present")] = False
    assert not e01(f4, E01P).any()
    f5 = f.copy(); f5.iloc[0, f5.columns.get_loc("rv")] = np.nan
    assert not e01(f5, E01P).any()


def test_e02_rule_exact_thresholds():
    f = _feat_frame(r15=[0.005], z15=[2.0], close=[100.01], prev_max_high=[100.0], rv=[1.5], imb=[0.2])
    assert e02(f, E02P).all() and e02(f, E02F).all()
    assert not e02(f.assign(close=100.0), E02P).any()  # strict breakout
    assert not e02(f.assign(imb=0.19), E02F).any()
    assert not e02(f.assign(z15=np.nan), E02P).any()


def test_random_times_reproducible():
    cand = pd.date_range("2026-01-01", periods=1000, freq="5min", tz="UTC")
    a = random_signal_times(cand, 20, 42)
    b = random_signal_times(cand, 20, 42)
    c = random_signal_times(cand, 20, 43)
    assert a.equals(b) and not a.equals(c) and a.is_monotonic_increasing and len(a.unique()) == 20


def test_regime_label():
    assert regime_label(0.01, 2.0, 1.0) == "up_highvol"
    assert regime_label(-0.01, 0.5, 1.0) == "down_lowvol"
    assert regime_label(np.nan, 0.5, 1.0) == "undefined"
