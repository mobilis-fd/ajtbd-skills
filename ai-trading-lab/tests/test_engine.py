import numpy as np
import pandas as pd
import pytest

from src.evaluation.engine import AccountState, equity_curve, round_down, round_up, run
from src.evaluation.ledger import reconcile
from tests.helpers import T0, bars_dict, ex, flat_bars, make_1m, risk, sig, sigs

M = pd.Timedelta(minutes=1)
BTC, ETH = "BTCUSDT", "ETHUSDT"


def _run(ohlc_by_sym, signals, e=None, r=None, n=None, state=None):
    bars = bars_dict(ohlc_by_sym, n=n)
    return run(signals, bars, e or ex(), r or risk(), state), bars


def test_entry_at_next_open_after_signal_close_not_signal_close():
    d = flat_bars(100)
    d.loc[10, ["open", "high", "low", "close"]] = [101, 101, 101, 101]
    d.loc[9, "close"] = 99.0  # last close of the signal candle (not used for entry)
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M)), ex(slip=0))
    t = res["trades"][0]
    assert t["entry_time"] == T0 + 10 * M and t["raw_entry"] == 101


def test_delay_stress_enters_one_minute_later():
    d = flat_bars(100)
    d.loc[11, ["open", "high", "low", "close"]] = [102, 102, 102, 102]
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M)), ex(slip=0, delay=1))
    assert res["trades"][0]["raw_entry"] == 102


def test_stop_first_on_conflict_and_entry_bar_checked():
    d = flat_bars(100)
    d.loc[10, ["high", "low"]] = [102, 98]  # entry bar touches both
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M)), ex(slip=0, fee=0))
    t = res["trades"][0]
    assert t["exit_reason"] == "stop" and np.isclose(t["raw_exit"], 100 * 0.994)
    assert t["exit_time"] == T0 + 11 * M


def test_gap_through_stop_fills_at_open_and_target_gap_at_trigger():
    d = flat_bars(100)
    d.loc[12, ["open", "high", "low", "close"]] = [98, 98.5, 97, 98]
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M)), ex(slip=0, fee=0))
    t = res["trades"][0]
    assert t["exit_reason"] == "stop_gap" and t["raw_exit"] == 98 and t["exit_time"] == T0 + 12 * M
    d2 = flat_bars(100)
    d2.loc[12, ["open", "high", "low", "close"]] = [102, 103, 101.5, 102]
    t2 = _run({BTC: d2}, sigs(sig(BTC, T0 + 10 * M)), ex(slip=0, fee=0))[0]["trades"][0]
    assert t2["exit_reason"] == "target_gap" and np.isclose(t2["raw_exit"], 100.9)


def test_time_exit_at_open_before_range_of_that_bar():
    d = flat_bars(200)
    d.loc[40, ["open", "high", "low", "close"]] = [100.2, 100.3, 90, 95]  # bar at deadline crashes intrabar
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M)), ex(hold=30, slip=0, fee=0))
    t = res["trades"][0]
    assert t["exit_reason"] == "time_exit" and t["raw_exit"] == 100.2 and t["exit_time"] == T0 + 40 * M
    assert t["hold_minutes_actual"] == 30


def test_cooldown_and_position_open_rejections():
    d = flat_bars(300)
    s = sigs(sig(BTC, T0 + 10 * M), sig(BTC, T0 + 20 * M), sig(BTC, T0 + 43 * M), sig(BTC, T0 + 45 * M))
    res, _ = _run({BTC: d}, s, ex(hold=30))
    assert len(res["trades"]) == 2
    reasons = [r["reason"] for r in res["rejections"]]
    assert reasons == ["position_open", "cooldown"]
    assert res["trades"][1]["entry_time"] == T0 + 45 * M


def test_simultaneous_signals_fixed_priority():
    s = sigs(sig(ETH, T0 + 10 * M, priority=1), sig(BTC, T0 + 10 * M, priority=0))
    res, _ = _run({BTC: flat_bars(200), ETH: flat_bars(200, 50.0)}, s)
    assert res["trades"][0]["symbol"] == BTC
    assert res["rejections"][0]["symbol"] == ETH and res["rejections"][0]["reason"] == "concurrent_signal_lower_priority"


def test_fees_both_sides_on_actual_notional_and_rounding():
    d = flat_bars(100, 123.456)
    e = ex(hold=5, fee=0.001, slip=0.00025, tick=0.01, step=0.001, min_notional=5)
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M)), e)
    t = res["trades"][0]
    assert t["fill_entry"] == pytest.approx(round_up(123.456 * 1.00025, 0.01)) and t["fill_entry"] >= 123.456 * 1.00025
    assert t["fill_exit"] == pytest.approx(round_down(123.456 * 0.99975, 0.01))
    assert abs(t["qty"] / 0.001 - round(t["qty"] / 0.001)) < 1e-9
    assert t["qty"] * t["fill_entry"] <= 50.0 + 1e-9
    assert t["fee_in"] == pytest.approx(t["qty"] * t["fill_entry"] * 0.001)
    assert t["fee_out"] == pytest.approx(t["qty"] * t["fill_exit"] * 0.001)
    assert t["net_pnl"] == pytest.approx(t["qty"] * t["fill_exit"] * 0.999 - t["qty"] * t["fill_entry"] * 1.001)
    assert reconcile(pd.DataFrame(res["trades"]), 100.0, 0.001, e.filters)["ok"]


def test_min_notional_and_no_overdraft():
    d = flat_bars(100)
    e = ex(min_notional=5, step=0.001, tick=0.01)
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M)), e, state=AccountState(cash=4.0))
    assert res["trades"] == [] and res["rejections"][0]["reason"] == "min_notional_or_insufficient_cash"
    res2, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M)), e, state=AccountState(cash=30.0))
    t = res2["trades"][0]
    assert t["notional_in"] + t["fee_in"] <= 30.0 + 1e-12


def test_zero_edge_with_costs_cannot_profit():
    rng = np.random.default_rng(0)
    n = 20000
    p = 100 * np.exp(np.cumsum(rng.normal(0, 0.0005, n)))
    p = p * np.exp(-np.arange(n) * 0)  # driftless random walk
    o = np.r_[p[0], p[:-1]]
    d = make_1m(list(zip(o, np.maximum(o, p), np.minimum(o, p), p)))
    s = sigs(*[sig(BTC, T0 + k * M) for k in range(100, n - 100, 97)])
    res, _ = _run({BTC: d}, s, ex(hold=30), risk(False))
    tr = pd.DataFrame(res["trades"])
    assert (tr["net_pnl"] - tr["gross_pnl"] < 0).all()  # costs always reduce pnl
    flat = flat_bars(500)
    res2, _ = _run({BTC: flat}, sigs(*[sig(BTC, T0 + k * M) for k in range(10, 400, 40)]), ex(hold=30), risk(False))
    assert all(t["net_pnl"] < 0 for t in res2["trades"])
    res3, _ = _run({BTC: flat}, sigs(sig(BTC, T0 + 10 * M)), ex(hold=30, fee=0, slip=0), risk(False))
    assert res3["trades"][0]["net_pnl"] == 0


def test_daily_pause_and_reset_next_day():
    # each trade: entry 100, immediate drop through stop -> ~ -0.43 USDT
    n = 3000
    d = flat_bars(n)
    times = [10, 60, 110, 160, 210, 1500]
    for k in times:
        d.loc[k, "low"] = 99.0
    s = sigs(*[sig(BTC, T0 + k * M) for k in times])
    res, _ = _run({BTC: d}, s, ex(hold=30))
    n_day0 = sum(1 for t in res["trades"] if t["entry_time"] < T0 + pd.Timedelta(days=1))
    losses = [t["net_pnl"] for t in res["trades"]]
    assert all(x < 0 for x in losses)
    assert n_day0 == 4  # 4 x ~0.43 >= 1.5 -> pause
    assert [r["reason"] for r in res["rejections"]] == ["daily_loss_pause"]
    assert res["trades"][-1]["entry_time"] == T0 + 1500 * M  # next UTC day allowed
    assert any(e["event"] == "daily_pause" for e in res["events"])


def test_intrabar_mtm_breach_forces_exit_next_open_and_total_stop():
    d = flat_bars(400)
    d.loc[10:20, ["open", "high", "low", "close"]] = 100.0
    e = ex(hold=60, fee=0, slip=0)
    e.stop_pct = 0.5  # disable the trade stop to isolate the portfolio limit
    d.loc[12, "close"] = 70.0; d.loc[12, "low"] = 70.0  # MTM loss 15 USDT on 50 notional
    d.loc[13, "open"] = 71.0
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M), sig(BTC, T0 + 200 * M)), e)
    t = res["trades"][0]
    assert t["exit_reason"] == "risk_exit_total" and t["raw_exit"] == 71.0 and t["exit_time"] == T0 + 13 * M
    assert res["rejections"][0]["reason"] == "total_loss_stop"
    assert res["state"].total_stopped


def test_restart_from_state_equals_single_run():
    rng = np.random.default_rng(3)
    n = 6000
    p = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    o = np.r_[p[0], p[:-1]]
    d = make_1m(list(zip(o, np.maximum(o, p) * 1.001, np.minimum(o, p) * 0.999, p)))
    s = sigs(*[sig(BTC, T0 + k * M) for k in range(20, n - 100, 53)])
    full, _ = _run({BTC: d}, s, ex())
    half = len(s) // 2
    a, _ = _run({BTC: d}, s.iloc[:half], ex())
    b, _ = _run({BTC: d}, s.iloc[half:], ex(), state=a["state"])
    pd.testing.assert_frame_equal(pd.DataFrame(full["trades"]), pd.DataFrame(a["trades"] + b["trades"]))
    assert full["state"].cash == b["state"].cash


def test_split_boundary_exit_and_late_signal_rejected():
    d = flat_bars(100)
    d.loc[99, "close"] = 100.5
    bars = bars_dict({BTC: d}, n=100)
    res = run(sigs(sig(BTC, T0 + 90 * M), sig(BTC, T0 + 100 * M)), bars, ex(hold=30, slip=0, fee=0), risk())
    t = res["trades"][0]
    assert t["exit_reason"] == "boundary_exit" and t["raw_exit"] == 100.5 and t["exit_time"] == T0 + 100 * M
    assert res["rejections"][0]["reason"] == "entry_after_segment_end"


def test_missing_entry_bar_and_gap_during_position_flagged():
    d = flat_bars(200, missing=(10, 15, 16))
    res, _ = _run({BTC: d}, sigs(sig(BTC, T0 + 10 * M), sig(BTC, T0 + 12 * M)), ex())
    assert res["rejections"][0]["reason"] == "missing_entry_bar"
    assert res["trades"][0]["uncertain_gap"]


def test_equity_curve_matches_cash_and_mtm():
    d = flat_bars(200)
    d.loc[15, "close"] = 100.3
    bars = bars_dict({BTC: d}, n=200)
    res = run(sigs(sig(BTC, T0 + 10 * M)), bars, ex(hold=30), risk())
    eq = equity_curve(res["trades"], bars, 100.0)
    t = res["trades"][0]
    assert eq.iloc[5] == 100.0
    assert eq.iloc[15] == pytest.approx(t["cash_after_entry"] + t["qty"] * 100.3)
    assert eq.iloc[-1] == pytest.approx(t["cash_after"])
