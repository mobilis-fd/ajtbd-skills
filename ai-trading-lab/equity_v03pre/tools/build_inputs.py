"""Build equity_screen.py inputs from raw Yahoo v8 chart JSON (no network).

Usage: python -I build_inputs.py RAW_DIR OUT_DIR LAST_DATE

Adjustment convention (README of v0.3-pre): Yahoo `close` is split-adjusted only,
`adjclose` is split- and dividend-adjusted. adj_open = open * adjclose / close,
adj_close = adjclose (same daily ratio applied to open and close).
sessions.csv = XNYS regular sessions from exchange_calendars (independent of Yahoo),
cut at LAST_DATE. The program then requires every symbol to match it exactly.
Nothing is filled; a mismatch is a hard error.
"""
import json, sys
from pathlib import Path
import pandas as pd
import exchange_calendars as xcals

SYMS = ['SPY', 'IEF', 'TLT']


def parse(path):
    j = json.loads(Path(path).read_text())
    r = j['chart']['result'][0]
    tz = r['meta']['exchangeTimezoneName']
    ts = pd.to_datetime(r['timestamp'], unit='s', utc=True).tz_convert(tz)
    q = r['indicators']['quote'][0]
    df = pd.DataFrame({'open': q['open'], 'high': q['high'], 'low': q['low'], 'close': q['close'],
                       'volume': q['volume'], 'adjclose': r['indicators']['adjclose'][0]['adjclose']},
                      index=pd.DatetimeIndex(ts.date, name='date'))
    ev = r.get('events', {})
    divs = pd.DataFrame(ev.get('dividends', {}).values())
    splits = pd.DataFrame(ev.get('splits', {}).values())
    for f in (divs, splits):
        if len(f):
            f['date'] = pd.to_datetime(f['date'], unit='s', utc=True).dt.tz_convert(tz).dt.date
    return df, divs, splits, r['meta']


def main(raw, out, last):
    raw, out = Path(raw), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cal = xcals.get_calendar('XNYS', start='2002-12-01', end=last)
    sessions = pd.DatetimeIndex(cal.sessions)
    sessions = sessions[(sessions >= '2002-12-01') & (sessions <= last)]
    pd.DataFrame({'date': sessions.strftime('%Y-%m-%d')}).to_csv(out / 'sessions.csv', index=False)
    for s in SYMS:
        df, divs, splits, meta = parse(raw / f'yahoo_{s}.json')
        df = df[(df.index >= pd.Timestamp('2002-12-01')) & (df.index <= pd.Timestamp(last))]
        df.to_csv(out / f'{s}_raw_parsed.csv')
        divs.to_csv(out / f'{s}_dividends.csv', index=False)
        splits.to_csv(out / f'{s}_splits.csv', index=False)
        ratio = df.adjclose / df.close
        o = pd.DataFrame({'date': df.index.strftime('%Y-%m-%d'),
                          'adj_open': (df.open * ratio).values, 'adj_close': df.adjclose.values})
        o.to_csv(out / f'{s}.csv', index=False, float_format='%.10g')
        print(s, len(o), o.date.iloc[0], o.date.iloc[-1], 'divs', len(divs), 'splits', len(splits))
    print('sessions', len(sessions), sessions[0].date(), sessions[-1].date())


if __name__ == '__main__':
    main(*sys.argv[1:4])
