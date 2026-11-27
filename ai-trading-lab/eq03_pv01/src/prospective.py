"""EQ03-PV01 prospective observation (paper record only; no broker, no orders, no demo account).

  python -I prospective.py schedule --first 2026-12 --months 24 --out schedule.csv
  python -I prospective.py evaluate --tlt-json yahoo_TLT.json --irx-json yahoo_IRX.json \
         --schedule schedule.csv --out observed.csv

`evaluate` reads free daily Yahoo data downloaded AFTER each window closed and records, for every scheduled
window whose exit session is in the data, the same quantities as the replay's base scenario:
TLT open->close with cash dividends (ex-date inside the window), 10 bps round trip, $50 position,
risk-free accrual on the same $50 for the same calendar days, and the mean of the month's other
five-session windows (the v0.3-pre control). It never changes the schedule or the rule.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pv_data import eq03_trades  # noqa: E402

FREEZE = pd.Timestamp('2026-11-27')   # date code and rules were frozen (pre-registration commit)
BPS_RT = 10.0
POSITION = 50.0


def schedule(first: str, months: int, lib_version_check=True) -> pd.DataFrame:
    import exchange_calendars as xcals
    p0 = pd.Period(first, 'M')
    end = (p0 + months).to_timestamp(how='end')
    cal = xcals.get_calendar('XNYS', start=str(p0.to_timestamp().date()), end=str(end.date()))
    ses = pd.DatetimeIndex(cal.sessions).tz_localize(None)
    rows = []
    for i, j, mon in eq03_trades(ses, 'pit'):
        if pd.Period(mon) < p0 or pd.Period(mon) >= p0 + months:
            continue
        rows.append({'month': mon, 'entry_open': ses[i].date(), 'exit_close': ses[j].date(),
                     'sessions_held': j - i + 1, 'xcals_version': xcals.__version__})
    df = pd.DataFrame(rows)
    if (pd.to_datetime(df.entry_open) <= FREEZE).any():
        raise ValueError('prospective windows must start after the freeze date')
    return df


def _parse(path):
    j = json.loads(Path(path).read_text())['chart']['result'][0]
    tz = j['meta']['exchangeTimezoneName']
    idx = pd.DatetimeIndex(pd.to_datetime(j['timestamp'], unit='s', utc=True).tz_convert(tz).date)
    q = j['indicators']['quote'][0]
    df = pd.DataFrame({'open': q['open'], 'close': q['close']}, index=idx)
    dv = pd.Series(0.0, index=idx)
    for e in j.get('events', {}).get('dividends', {}).values():
        d = pd.Timestamp(pd.to_datetime(e['date'], unit='s', utc=True).tz_convert(tz).date())
        if d in dv.index:
            dv[d] += e['amount']
    df['div'] = dv
    return df[~df.index.duplicated(keep='last')]


def evaluate(tlt_json, irx_json, sched: pd.DataFrame) -> pd.DataFrame:
    px = _parse(tlt_json)
    rf = _parse(irx_json)['close'].reindex(px.index).ffill() / 100
    h = BPS_RT / 20000
    rows = []
    for _, s in sched.iterrows():
        i, j = pd.Timestamp(s.entry_open), pd.Timestamp(s.exit_close)
        if j not in px.index or i not in px.index or i <= FREEZE:
            continue
        w = px.loc[i:j]
        if w[['open', 'close']].isna().any().any():
            raise ValueError(f'missing price in window {s.month}')
        shares = POSITION / (w.open.iloc[0] * (1 + h))
        div = shares * w['div'].iloc[1:].sum()          # ex-date after entry day => entitled
        value = shares * w.close.iloc[-1] * (1 - h) + div
        days = (j - i).days
        rf_ret = float(rf.loc[:i].iloc[-2] if len(rf.loc[:i]) > 1 else rf.loc[i]) * days / 365
        mon = px[px.index.to_period('M') == pd.Period(s.month)]
        ctrl = [mon.close.iloc[k + 4] / mon.open.iloc[k] - 1 for k in range(len(mon) - 4)
                if mon.index[k] != i]
        gross = value / POSITION - 1
        rows.append({'month': s.month, 'entry': i.date(), 'exit': j.date(), 'entry_open': w.open.iloc[0],
                     'exit_close': w.close.iloc[-1], 'div_cash': div, 'net_ret_10bps': gross,
                     'rf_same_days': rf_ret, 'excess_vs_rf': gross - rf_ret,
                     'raw_ret_no_div': w.close.iloc[-1] / w.open.iloc[0] - 1,
                     'control_other_windows': float(np.mean(ctrl)) if ctrl else np.nan,
                     'pnl_usd_on_50': value - POSITION, 'excess_usd_vs_rf': (gross - rf_ret) * POSITION})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    s1 = sub.add_parser('schedule'); s1.add_argument('--first', default='2026-12')
    s1.add_argument('--months', type=int, default=24); s1.add_argument('--out', type=Path, required=True)
    s2 = sub.add_parser('evaluate'); s2.add_argument('--tlt-json', required=True); s2.add_argument('--irx-json', required=True)
    s2.add_argument('--schedule', type=Path, required=True); s2.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == 'schedule':
        df = schedule(a.first, a.months); df.to_csv(a.out, index=False); print(df.to_string(index=False))
    else:
        df = evaluate(a.tlt_json, a.irx_json, pd.read_csv(a.schedule)); df.to_csv(a.out, index=False)
        print(df.to_string(index=False))


if __name__ == '__main__':
    main()
