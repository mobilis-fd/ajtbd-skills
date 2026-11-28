"""EQ04 unit tests on synthetic calendars/prices only (no market data)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from events import classify  # noqa: E402
from run_screen import net, build_table  # noqa: E402
from windows import blocked_mask, controls_for, event_windows, month_end_sets, window_flags  # noqa: E402

SESS = pd.bdate_range('2020-01-01', '2020-03-31').drop(pd.Timestamp('2020-01-20'))  # one holiday


def ev(dates):
    return pd.DataFrame({'cusip': [f'C{i}' for i in range(len(dates))], 'auction_date': pd.to_datetime(dates),
                         'reopening': 'No'})


def test_entry_strictly_after_auction_and_exit_5th_session():
    w = event_windows(SESS, ev(['2020-01-15']), 5)
    assert w.entry_date[0] == pd.Timestamp('2020-01-16')
    # 16, 17, 21 (20th holiday), 22, 23
    assert w.exit_date[0] == pd.Timestamp('2020-01-23')
    w1 = event_windows(SESS, ev(['2020-01-17']), 1)          # Friday auction, Monday holiday
    assert w1.entry_date[0] == pd.Timestamp('2020-01-21') and w1.exit_date[0] == w1.entry_date[0]


def test_auction_on_non_session_enters_next_session():
    w = event_windows(SESS, ev(['2020-01-20']), 3)
    assert w.entry_date[0] == pd.Timestamp('2020-01-21')


def test_incomplete_window_dropped():
    assert len(event_windows(SESS, ev(['2020-03-27']), 5)) == 0


def test_controls_same_month_weekday_no_overlap():
    w = event_windows(SESS, ev(['2020-02-11']), 5)   # entry Wed 2020-02-12
    b = blocked_mask(len(SESS), w)
    ks = controls_for(SESS, w.iloc[0], b, 5)
    ds = SESS[ks]
    assert all(d.month == 2 and d.weekday() == 2 for d in ds)
    assert pd.Timestamp('2020-02-12') not in ds
    for k in ks:
        assert not b[k:k + 5].any()
    assert set(ds) == {pd.Timestamp('2020-02-05'), pd.Timestamp('2020-02-19'), pd.Timestamp('2020-02-26')}


def test_month_end_masks():
    eq03, tom = month_end_sets(SESS)
    jan = np.flatnonzero(SESS.month == 1)
    assert eq03[jan[-5:]].all() and not eq03[jan[-6]]
    feb = np.flatnonzero(SESS.month == 2)
    assert tom[feb[:3]].all() and not tom[feb[3]]


def test_macro_release_on_entry_day_excluded_but_fomc_counted():
    eq03, tom = month_end_sets(SESS)
    e = int(np.flatnonzero(SESS == pd.Timestamp('2020-02-12'))[0])
    m = {'FOMC': {pd.Timestamp('2020-02-12')}, 'CPI': {pd.Timestamp('2020-02-12')}, 'NFP': {pd.Timestamp('2020-02-13')}}
    f = window_flags(SESS, e, e + 4, eq03, tom, m)
    assert f['has_fomc'] and not f['has_cpi'] and f['has_nfp']


def test_cost_formula_known_answer():
    assert abs(net(0.0, 10) - (-0.001)) < 1e-15
    g = 0.01
    assert abs(net(g, 40) - (g - 0.002 * (2 + g))) < 1e-15


def test_build_table_known_prices():
    n = len(SESS)
    ao = np.ones(n) * 100.0
    ac = np.ones(n) * 100.0
    e = int(np.flatnonzero(SESS == pd.Timestamp('2020-02-12'))[0])
    ac[e + 4] = 101.0                            # event window +1%
    rf = np.full(n, 0.0252)
    macro = {'FOMC': set(), 'CPI': set(), 'NFP': set()}
    t = build_table(ev(['2020-02-11']), SESS, ao, ac, rf, np.zeros(n, bool), macro, 5)
    r = t.iloc[0]
    assert abs(r.g_event - 0.01) < 1e-12 and abs(r.g_ctl_mean) < 1e-12 and abs(r.d_gross - 0.01) < 1e-12
    assert abs(r.cash - 0.0252 * 5 / 252) < 1e-15
    assert abs(r.exc_0 - (0.01 - 0.0005)) < 1e-12


def test_future_price_mutation_does_not_change_event():
    n = len(SESS)
    ao = np.linspace(100, 110, n); ac = ao + 0.1
    macro = {'FOMC': set(), 'CPI': set(), 'NFP': set()}
    t1 = build_table(ev(['2020-01-15']), SESS, ao, ac, np.zeros(n), np.zeros(n, bool), macro, 5)
    e = int(np.flatnonzero(SESS == pd.Timestamp('2020-01-23'))[0])
    ao2, ac2 = ao.copy(), ac.copy(); ao2[e + 1:] *= 3; ac2[e + 1:] *= 3
    t2 = build_table(ev(['2020-01-15']), SESS, ao2, ac2, np.zeros(n), np.zeros(n, bool), macro, 5)
    assert t1.g_event[0] == t2.g_event[0]


def test_classify_rules():
    base = dict(inflation_index_security='No', floating_rate='No', security_term='10-Year',
                announcemt_date=pd.Timestamp('2020-01-02'), auction_date=pd.Timestamp('2020-01-08'))
    R = lambda **k: pd.Series({**base, **k})  # noqa: E731
    assert classify(R()) == 'included'
    assert classify(R(security_term='9-Year 11-Month')) == 'included'
    assert classify(R(inflation_index_security='Yes')) == 'excluded_TIPS'
    assert classify(R(security_term='3-Year')) == 'excluded_offcycle_old_issue'
    assert classify(R(announcemt_date=pd.Timestamp('2020-01-08'))) == 'excluded_same_day_announced'
    assert classify(R(auction_date=pd.Timestamp('2002-11-01'), announcemt_date=pd.Timestamp('2002-10-25'))) == 'excluded_before_ief_data'
