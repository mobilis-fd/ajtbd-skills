"""EQ03-PV01 unit tests. Synthetic prices only (plus the exchange calendar library); no market data."""
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'src'))
import pv_stats  # noqa: E402
from pv_data import ADHOC_CLOSURES, Market, eq03_trades, known_future_sessions, settlement_lag  # noqa: E402
from pv_engine import Scenario, run  # noqa: E402


def market(n=60, price=40.0, start='2021-03-01', rf=0.0, sessions=None):
    s = pd.bdate_range(start, periods=n) if sessions is None else sessions
    n = len(s)
    return Market(s, np.full(n, price), np.full(n, price), np.zeros(n), np.full(n, rf))


FR = Scenario(bps_rt=0, fee=0, idle_rf=False)


def test_flat_prices_no_cost_keeps_capital():
    m = market()
    r = run(m, 0, 59, [(5, 9, 'a'), (25, 29, 'b')], FR)
    assert np.allclose(r.equity, 100.0) and len(r.trades) == 2


def test_proportional_cost_equals_bps_of_notional():
    m = market()
    r = run(m, 0, 59, [(5, 9, 'a')], replace(FR, bps_rt=10))
    t = r.trades[0]
    notional = t['shares'] * 40.0
    assert t['pnl'] == pytest.approx(-notional * 10 / 1e4, rel=1e-12)
    assert notional <= 50 and notional > 50 / 1.0005 - 40 * 1e-4


def test_fixed_fee_charged_twice_and_budget_includes_fee():
    m = market()
    r = run(m, 0, 59, [(5, 9, 'a')], replace(FR, fee=1.0))
    t = r.trades[0]
    assert t['pnl'] == pytest.approx(-2.0) and t['cost'] <= 50 + 1e-9
    assert r.equity[-1] == pytest.approx(98.0)


def test_whole_shares_above_budget_never_trade():
    m = market(price=82.0)
    r = run(m, 0, 59, [(5, 9, 'a')], replace(FR, share_step=1.0))
    assert not r.trades and len(r.skipped) == 1 and np.allclose(r.equity, 100)
    r2 = run(market(price=20.0), 0, 59, [(5, 9, 'a')], replace(FR, share_step=1.0))
    assert r2.trades[0]['shares'] == 2.0


def test_dividend_counted_once_and_only_when_held_at_prior_close():
    m = market()
    m.open[12:] = 39.0; m.close[12:] = 39.0; m.div[12] = 1.0   # ex-date 12: price drops by the dividend
    r = run(m, 0, 59, [(10, 14, 'a')], replace(FR, pay_lag=3))
    t = r.trades[0]
    assert t['div'] == pytest.approx(t['shares'] * 1.0)
    assert r.dividends_received == pytest.approx(t['div'])
    assert t['pnl'] == pytest.approx(0.0, abs=1e-9)            # price drop offset exactly once
    assert r.equity[13] == pytest.approx(100.0)                # receivable carried before payment
    # buying at the ex-date open: no entitlement
    r2 = run(m, 0, 59, [(12, 14, 'a')], FR)
    assert r2.dividends_received == 0 and r2.trades[0]['pnl'] == pytest.approx(0.0, abs=1e-9)


def test_settlement_limits_available_cash_and_cash_never_negative():
    m = market(start='2019-03-04')       # T+2 era
    sc = replace(FR, capital=50.0, max_position=50.0, bps_rt=10)
    r = run(m, 0, 59, [(5, 9, 'a'), (10, 14, 'b')], sc)   # re-entry the day after a sale
    assert r.cash_shortfalls == 1
    assert len(r.trades) == 1 and len(r.skipped) == 1      # proceeds not settled until T+2
    r2 = run(m, 0, 59, [(5, 9, 'a'), (12, 16, 'b')], sc)  # after settlement: both trades
    assert len(r2.trades) == 2 and r2.cash_shortfalls >= 1  # budget slightly < 50 after costs


def test_settlement_cycle_dates():
    assert settlement_lag(pd.Timestamp('2017-09-01')) == 3
    assert settlement_lag(pd.Timestamp('2017-09-05')) == 2
    assert settlement_lag(pd.Timestamp('2024-05-24')) == 2
    assert settlement_lag(pd.Timestamp('2024-05-28')) == 1


def test_rf_accrual_on_cash():
    m = market(n=262, rf=0.0365)
    r = run(m, 0, 261, [], replace(FR, idle_rf=True))
    days = (m.sessions[-1] - m.sessions[0]).days
    assert r.equity[-1] == pytest.approx(100 * (1 + 0.0365 * days / 365), rel=2e-3)


def test_engine_has_no_lookahead_on_prices():
    rng = np.random.default_rng(0)
    m = market(n=120)
    m.open[:] = 40 * np.exp(np.cumsum(rng.normal(0, .01, 120))); m.close[:] = m.open * 1.001
    tl = [(5, 9, 'a'), (30, 34, 'b'), (70, 74, 'c')]
    r1 = run(m, 0, 119, tl, Scenario())
    m.open[50:] *= 3; m.close[50:] *= 0.2
    r2 = run(m, 0, 119, tl, Scenario())
    assert np.array_equal(r1.equity[:50], r2.equity[:50])


def test_frictionless_trade_equals_price_ratio():
    m = market()
    m.open[5] = 40.0; m.close[9] = 41.3
    r = run(m, 0, 59, [(5, 9, 'a')], replace(FR, share_step=1e-12))
    assert r.trades[0]['ret'] == pytest.approx(41.3 / 40 - 1, abs=1e-10)


# ------------------------------------------------------------------ calendar (point in time)
xcals = pytest.importorskip('exchange_calendars')


def xnys():
    c = xcals.get_calendar('XNYS', start='2002-12-01', end='2026-11-06')
    return pd.DatetimeIndex(c.sessions).tz_localize(None), c


def test_realised_plus_adhoc_equals_regular_schedule():
    """Independent check: realised sessions + ad hoc closures == weekdays minus REGULAR holidays,
    i.e. the PIT schedule uses only rules known in advance plus the realised past."""
    ses, c = xnys()
    wd = pd.bdate_range(ses[0], ses[-1])
    reg = pd.DatetimeIndex(c.regular_holidays.holidays(ses[0], ses[-1])) if c.regular_holidays is not None else []
    sched = wd.difference(reg)
    adhoc = pd.DatetimeIndex([d for d in ADHOC_CLOSURES if ses[0] <= d <= ses[-1]])
    assert sched.equals(ses.union(adhoc))
    lib_adhoc = pd.DatetimeIndex(c.adhoc_holidays)
    assert set(lib_adhoc[(lib_adhoc >= ses[0]) & (lib_adhoc <= ses[-1])]) == set(adhoc)


def test_sandy_month_enters_on_scheduled_fifth_last_session():
    ses, _ = xnys()
    pit = {t[2]: t for t in eq03_trades(ses, 'pit')}
    real = {t[2]: t for t in eq03_trades(ses, 'realised')}
    assert ses[real['2012-10'][0]] == pd.Timestamp('2012-10-23')      # realised calendar (v0.3-pre)
    assert ses[pit['2012-10'][0]] == pd.Timestamp('2012-10-25')       # schedule known on that morning
    assert ses[pit['2012-10'][1]] == pd.Timestamp('2012-10-31')
    others = [k for k in pit if pit[k][:2] != real[k][:2]]
    assert others == ['2012-10']


def test_pit_decision_unchanged_by_hiding_future_sessions():
    """Deleting realised sessions after the decision (e.g. a later unknown closure) must not change it
    unless the removed day is itself an announced (regular) holiday — here we simulate an ad hoc one."""
    s = pd.bdate_range('2021-03-01', '2021-03-31')
    n_before = known_future_sessions(s, len(s) - 5, pd.Timestamp('2021-03-31'))
    assert n_before == 4
    # an unscheduled closure two days later: realised calendar loses that day, PIT count must not change
    import pv_data
    closed = s[-2]
    s2 = s.delete(len(s) - 2)
    old = pv_data.ADHOC_CLOSURES
    try:
        pv_data.ADHOC_CLOSURES = old.append(pd.DatetimeIndex([closed]))
        assert known_future_sessions(s2, len(s2) - 4, pd.Timestamp('2021-03-31')) == 4
        tr = pv_data.eq03_trades(s2.append(pd.bdate_range('2021-04-01', '2021-04-30')), 'pit')
        assert s2[tr[0][0]] == s[-5] and s2[tr[0][1]] == s[-1]
    finally:
        pv_data.ADHOC_CLOSURES = old


# ------------------------------------------------------------------ statistics
def _orig_bootstrap():
    spec = importlib.util.spec_from_file_location(
        'eqs', HERE.parent.parent / 'equity_v03pre' / 'original' / 'equity_screen.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.bootstrap


def test_cbb_percentile_reproduces_v03pre_bootstrap():
    x = np.random.default_rng(3).normal(0.2, 1, 79)
    lo, hi, p = _orig_bootstrap()(x, 6, 123)
    p2, lo2, hi2 = pv_stats.cbb_percentile(x, block=6, B=4000, seed=123)
    assert (p, lo, hi) == pytest.approx((p2, lo2, hi2), abs=1e-12)


def test_t_and_nw_known_values():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    p, lo, hi = pv_stats.t_iid(x)
    assert lo == pytest.approx(2.5 - 3.182446305284 * np.std(x, ddof=1) / 2, rel=1e-9)
    assert pv_stats.nw_se(x, 0) == pytest.approx(np.std(x) / 2)


def test_holm():
    assert pv_stats.holm({'a': 0.01, 'b': 0.04, 'c': 0.03}) == pytest.approx({'a': 0.03, 'b': 0.06, 'c': 0.06})


def test_studentized_bootstrap_sane():
    x = np.random.default_rng(1).normal(1.0, 1, 100)
    p, lo, hi = pv_stats.cbb_studentized(x, B=999, seed=1)
    assert p < 0.01 and lo < x.mean() < hi


def test_fixed_fees_cannot_drive_cash_negative():
    m = market(n=400, price=40.0)
    tl = [(k, k + 4, str(k)) for k in range(5, 390, 10)]
    r = run(m, 0, 399, tl, replace(FR, fee=5.0, bps_rt=40))
    assert (r.equity >= -1e-9).all() and len(r.skipped) > 0
    assert r.equity[-1] < 10.0          # fees consume the account; trading stops instead of borrowing
