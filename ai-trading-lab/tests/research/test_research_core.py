import numpy as np
import pandas as pd
import pytest

from src.data.parse import parse_kline_csv
from src.research.data import aggregate_bars
from src.research.features import crosses_boundary, g01_asset_features, g01_design, grid, labels
from src.research.models import RidgeFit, fit_times, model_id_for, train_mask
from src.research.pipeline import choose
from src.research.replay import Costs, Params, Px, equity_1m, passive, run
from src.evaluation.engine import Filters

G0 = pd.Timestamp("2024-12-31T00:00:00Z")
M = pd.Timedelta(minutes=1)
ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT", "LTCUSDT"]


def m1(n, start=G0, price=100.0, drop=(), prices=None):
    t = start + np.arange(n) * M
    p = np.full(n, price) if prices is None else np.asarray(prices, float)
    d = pd.DataFrame({"open_time": t, "open": p, "high": p, "low": p, "close": p, "volume": 2.0,
                      "quote_volume": 2.0 * p, "trades": 3, "taker_buy_base": 1.0, "taker_buy_quote": p,
                      "close_time": t + M - pd.Timedelta(milliseconds=1)})
    return d.drop(index=list(drop)).reset_index(drop=True)


# ------------------------------------------------------------- data/bars

def test_bar_alignment_across_utc_and_unit_boundary():
    # 2024-12-31 23:58..2025-01-01 00:01: ms rows then us rows (Binance switched units on 2025-01-01)
    base_ms = int(pd.Timestamp("2024-12-31T23:58Z").value // 1_000_000)
    lines = []
    for i in range(4):
        ot = base_ms + i * 60_000
        if i < 2:
            lines.append(f"{ot},1,2,0.5,1.5,1,{ot + 59_999},1,1,0.5,0.5,0")
        else:
            lines.append(f"{ot * 1000},1,2,0.5,1.5,1,{(ot + 60_000) * 1000 - 1},1,1,0.5,0.5,0")
    d = parse_kline_csv("\n".join(lines) + "\n")
    assert list(d["ts_unit"]) == ["ms", "ms", "us", "us"]
    assert d["open_time"].iloc[2] == pd.Timestamp("2025-01-01T00:00Z")
    b = aggregate_bars(pd.concat([m1(1440 * 2 - 2, start=pd.Timestamp("2024-12-30T00:00Z")), d.iloc[:2]]), 1440)
    assert list(b["T"]) == [pd.Timestamp("2024-12-31T00:00Z"), pd.Timestamp("2025-01-01T00:00Z")]  # T = bar END


def test_incomplete_bar_dropped_and_missing_row_propagates():
    d = m1(120, drop=[45])
    b = aggregate_bars(d, 30)
    assert list(b["T"]) == [G0 + 30 * M, G0 + 90 * M, G0 + 120 * M]     # bar [30,60) incomplete -> absent
    g = grid(b, 30, G0, G0 + 120 * M)
    assert g["close"].isna().tolist() == [False, True, False, False]


# ------------------------------------------------------------- G01 features

def _assets(n=400, seed=0, missing=None):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(G0 + 30 * M, periods=n, freq="30min", name="T")
    out = {}
    for a in ASSETS:
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
        g = pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": rng.uniform(1, 3, n),
                          "taker_buy_base": rng.uniform(0, 1, n)}, index=idx)
        if missing and a == missing[0]:
            g.iloc[missing[1]] = np.nan
        out[a] = g_features(g)
    return out


def g_features(g):
    return g01_asset_features(g)


def test_nine_asset_sync_identical_sample_and_factor_excludes_target():
    af = _assets(missing=("DOGEUSDT", 200))
    b1, x, valid = g01_design(af, "BTCUSDT")
    assert not valid.iloc[200] and valid.iloc[300]
    assert (b1.notna().all(axis=1) == x.notna().all(axis=1)).all()        # identical B1/X sample
    others = [a for a in ASSETS if a != "BTCUSDT"]
    t = 300
    exp = np.mean([af[a]["r60"].iloc[t] for a in others])
    assert np.isclose(b1["mkt_r60"].iloc[t], exp)
    assert not any("BTCUSDT" in c for c in x.columns if c.startswith("res_"))
    af2 = {k: v.copy() for k, v in af.items()}
    af2["BTCUSDT"]["r60"] += 1.0                                             # target return does not move F
    b1b, _, _ = g01_design(af2, "BTCUSDT")
    assert np.allclose(b1b["mkt_r60"].dropna(), b1["mkt_r60"].dropna())


def test_features_prefix_invariant_and_future_mutation():
    rng = np.random.default_rng(1)
    n = 500
    idx = pd.date_range(G0 + 30 * M, periods=n, freq="30min", name="T")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    g = pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": rng.uniform(1, 3, n),
                      "taker_buy_base": rng.uniform(0, 1, n)}, index=idx)
    full = g01_asset_features(g)
    for cut in (100, 333, 499):
        pd.testing.assert_frame_equal(g01_asset_features(g.iloc[:cut]), full.iloc[:cut])
        mut = g.copy()
        mut.iloc[cut:] *= 1.7
        pd.testing.assert_frame_equal(g01_asset_features(mut).iloc[:cut], full.iloc[:cut])


def test_zero_volume_makes_rv_and_imbalance_missing():
    g = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": [1.0] * 60 + [0.0],
                      "taker_buy_base": 0.5}, index=pd.date_range(G0, periods=61, freq="30min"))
    f = g01_asset_features(g)
    assert np.isnan(f["imb"].iloc[-1]) and np.isnan(f["log_rv"].iloc[-1]) and np.isfinite(f["log_rv"].iloc[-2])


# ------------------------------------------------------------- labels, purge, maturity

def test_label_uses_open_after_delay_not_close():
    prices = 100 + np.arange(300.0)
    d = m1(300, prices=prices)
    d["close"] = 999.0
    px = Px(d, G0, G0 + 300 * M)
    T = pd.DatetimeIndex([G0 + 30 * M])
    assert labels(px, T, 60, 1)[0] == pytest.approx((100 + 91) / (100 + 31) - 1)
    assert labels(px, T, 60, 5)[0] == pytest.approx((100 + 95) / (100 + 35) - 1)
    px2 = Px(m1(300, prices=prices, drop=[91]), G0, G0 + 300 * M)
    assert np.isnan(labels(px2, T, 60, 1)[0])


def test_split_purge_and_label_maturity():
    b = pd.Timestamp("2023-01-01T00:00Z")
    T = pd.DatetimeIndex([b - pd.Timedelta(hours=5), b - pd.Timedelta(hours=4), b - pd.Timedelta(minutes=241)])
    cr = crosses_boundary(T, 240, 1, [b])
    assert cr.tolist() == [False, True, False]
    F = pd.Timestamp("2022-06-01T00:00Z")
    T2 = pd.DatetimeIndex([F - pd.Timedelta(minutes=61), F - pd.Timedelta(minutes=60), F - pd.Timedelta(days=366)])
    m = train_mask(T2, F, 365, 1, 60, np.zeros(3, bool))
    assert m.tolist() == [True, False, False]   # immature label (exit after F) and out-of-window excluded


def test_monthly_fit_schedule_and_model_assignment():
    fits = fit_times(pd.Timestamp("2021-10-01T00:00Z"), pd.Timestamp("2021-01-01T00:00Z"),
                     pd.Timestamp("2022-01-01T00:00Z"))
    assert [str(f.date()) for f in fits] == ["2021-10-01", "2021-11-01", "2021-12-01"]
    T = pd.DatetimeIndex(["2021-09-30T23:30Z", "2021-10-01T00:00Z", "2021-11-15T12:00Z"])
    assert model_id_for(T, fits).tolist() == [-1, 0, 1]


def test_train_only_scaling():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(200, 3)), columns=list("abc"))
    X["zero"] = 1.0
    y = rng.normal(size=200)
    a = RidgeFit(10).fit(X.iloc[:100], y[:100])
    Xm = X.copy()
    Xm.iloc[100:] *= 50                                   # future rows do not affect the fitted scaler/model
    b = RidgeFit(10).fit(Xm.iloc[:100], y[:100])
    assert np.allclose(a.mu, b.mu) and np.allclose(a.m.coef_, b.m.coef_)
    assert a.dropped == ["zero"] and "zero" not in a.cols


# ------------------------------------------------------------- planted / null lead-lag

def _leadlag(beta, seed, n=6000):
    rng = np.random.default_rng(seed)
    R = rng.normal(0, 0.01, size=(n, 9))
    y = np.r_[beta * R[:-1, 4], 0.0] + rng.normal(0, 0.01, n)   # target's next return depends on asset 4 (XRP)
    own = pd.DataFrame({"own": R[:, 0]})
    F = R[:, 1:].mean(axis=1)
    b1 = own.assign(mkt=F)
    x = b1.copy()
    for j in range(1, 9):
        x[f"res{j}"] = R[:, j] - F
    tr, te = slice(0, n // 2), slice(n // 2, n - 1)
    pb, px_ = RidgeFit(10).fit(b1.iloc[tr], y[tr]), RidgeFit(10).fit(x.iloc[tr], y[tr])
    yy = y[te]
    d = np.mean((yy - pb.predict(b1.iloc[te])) ** 2) - np.mean((yy - px_.predict(x.iloc[te])) ** 2)
    return d, px_


def test_planted_lag_recovered_with_either_sign():
    for beta in (0.4, -0.4):
        d, model = _leadlag(beta, 3)
        assert d > 0
        coef = dict(zip(model.cols, model.m.coef_))
        assert np.sign(coef["res4"]) == np.sign(beta)   # sign learned, not hard-coded


def test_null_cross_data_does_not_consistently_improve():
    ds = [_leadlag(0.0, s)[0] for s in range(12)]
    assert sum(d > 0 for d in ds) < 12 and np.mean(ds) < 1e-7


# ------------------------------------------------------------- selection

def test_choose_max_score_and_deterministic_ties():
    T = pd.Timestamp("2022-01-01T00:00Z")
    pan = pd.DataFrame({"T": [T, T, T, T + 30 * M, T + 30 * M], "symbol": ["SOLUSDT", "ETHUSDT", "BTCUSDT",
                                                                         "ETHUSDT", "SOLUSDT"]})
    score = np.array([0.1, 0.1, 0.05, 0.0, 0.0])
    it, cand = choose(pan, np.ones(5, bool), score, ["BTCUSDT", "ETHUSDT", "SOLUSDT"], 60)
    assert it["symbol"].tolist() == ["ETHUSDT", "ETHUSDT"]    # tie 0.1: ETH before SOL; tie 0: ETH before SOL
    assert (cand["candidate_reason"] == "lower_rank_same_T").sum() == 3


# ------------------------------------------------------------- replay

def _p(**kw):
    base = dict(costs=Costs(0.001, 0.00025), delay_min=1, stake=50.0, initial=100.0,
                filters={"BTCUSDT": Filters(0.01, 0.00001, 10.0), "ETHUSDT": Filters(0.01, 0.0001, 10.0)})
    base.update(kw)
    return Params(**base)


def _it(*rows):
    return pd.DataFrame([{"T": t, "symbol": s, "hold_min": h} for t, s, h in rows])


def test_time_exit_hold_expiry_fees_and_no_overlap():
    d = m1(600, prices=100 + 0.01 * np.arange(600))
    px = {"BTCUSDT": Px(d, G0, G0 + 600 * M)}
    it = _it((G0 + 30 * M, "BTCUSDT", 60), (G0 + 60 * M, "BTCUSDT", 60), (G0 + 91 * M, "BTCUSDT", 60))
    r = run(it, px, _p(), G0, G0 + 600 * M)
    t = r["trades"]
    assert [x["entry_time"] for x in t] == [G0 + 31 * M, G0 + 92 * M]
    assert t[0]["exit_time"] == G0 + 91 * M and t[0]["exit_reason"] == "time_exit"
    assert [x["reason"] for x in r["rejections"]] == ["position_open"]   # decision 60 < exit 91
    x = t[0]
    assert x["fill_entry"] >= x["raw_entry"] * 1.00025 - 1e-9 and x["fill_exit"] <= x["raw_exit"] * 0.99975 + 1e-9
    assert x["net_pnl"] == pytest.approx(x["qty"] * x["fill_exit"] * 0.999 - x["qty"] * x["fill_entry"] * 1.001)
    assert abs(x["qty"] / 1e-5 - round(x["qty"] / 1e-5)) < 1e-6 and x["notional_in"] <= 50


def test_missing_exit_minute_uncertain_and_missing_entry_rejected():
    d = m1(600, drop=[91, 92, 200])
    px = {"BTCUSDT": Px(d, G0, G0 + 600 * M)}
    r = run(_it((G0 + 30 * M, "BTCUSDT", 60), (G0 + 199 * M, "BTCUSDT", 60)), px, _p(), G0, G0 + 600 * M)
    t = r["trades"][0]
    assert t["exit_reason"] == "time_exit_after_gap" and t["exit_time"] == G0 + 93 * M and t["uncertain_gap"]
    assert r["rejections"][0]["reason"] == "missing_entry_bar"


def test_risk_breach_exits_at_next_known_open_and_mtm():
    prices = np.full(600, 100.0)
    d = m1(600, prices=prices)
    d.loc[40, ["close", "low"]] = 94.0          # close of minute 40 -> MTM loss ~3 USDT (> 1.5)
    d.loc[41, "open"] = 99.0                    # next known open
    px = {"BTCUSDT": Px(d, G0, G0 + 600 * M)}
    r = run(_it((G0 + 30 * M, "BTCUSDT", 120), (G0 + 200 * M, "BTCUSDT", 60)), px, _p(risk_on=True), G0,
            G0 + 600 * M)
    t = r["trades"][0]
    assert t["exit_reason"] == "risk_exit_daily" and t["exit_time"] == G0 + 41 * M and t["raw_exit"] == 99.0
    assert r["rejections"][0]["reason"] == "daily_loss_pause"
    eq = equity_1m(r["trades"], px, G0, G0 + 600 * M, 100.0)
    assert eq.iloc[40] == pytest.approx(t["cash_after_entry"] + t["qty"] * 94.0)   # MTM at known close
    r2 = run(_it((G0 + 30 * M, "BTCUSDT", 120)), px, _p(risk_on=False), G0, G0 + 600 * M)
    assert r2["trades"][0]["exit_reason"] == "time_exit"                            # diag: no kill-switch


def test_total_stop_ends_run_and_cash_never_negative():
    n = 4000
    prices = 100 * np.exp(-0.0002 * np.arange(n))  # steady decline
    px = {"BTCUSDT": Px(m1(n, prices=prices), G0, G0 + n * M)}
    its = _it(*[(G0 + k * M, "BTCUSDT", 600) for k in range(10, n - 700, 700)])
    p = _p(risk_on=True, daily_limit=100.0)
    r = run(its, px, p, G0, G0 + n * M)
    assert r["state"].stopped and any(x["reason"] == "total_loss_stop" for x in r["rejections"])
    assert all(x["cash_after"] >= 0 and x["cash_after_entry"] >= 0 for x in r["trades"])


def test_passive_buy_and_hold_constrained_no_reentry():
    n = 3000
    prices = np.r_[np.full(1000, 100.0), np.full(n - 1000, 90.0)]
    d = m1(n, prices=prices)
    px = {"BTCUSDT": Px(d, G0, G0 + n * M)}
    r = passive(px, {"BTCUSDT": 50.0}, _p(risk_on=True), G0, G0 + n * M)
    # breach is known at the CLOSE of minute 1000 -> exit at the next known open (minute 1001)
    assert r["exit_reason"] == "risk_exit_daily" and r["positions"][0]["exit_minute"] == 1001
    assert r["equity"].iloc[-1] == pytest.approx(100 + r["net_pnl"])
    r2 = passive(px, {"BTCUSDT": 50.0}, _p(risk_on=False), G0, G0 + n * M)
    assert r2["exit_reason"] == "end_of_split" and r2["positions"][0]["exit_minute"] == n - 1
