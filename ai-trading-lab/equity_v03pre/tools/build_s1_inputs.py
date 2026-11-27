"""Pre-registered sensitivity S1 inputs (data-corrected), built before any result was seen.

Usage: python -I build_s1_inputs.py DATA_DIR OUT_DIR

Starting from the primary Yahoo inputs, two corrections from the second source (Nasdaq):
 1. Raw open replaced by the Nasdaq open on days listed in open_close_discrepancies_nasdaq_vs_yahoo.csv
    where |Nasdaq open − Yahoo open| > 0.006 AND the Nasdaq close agrees with Yahoo (|diff| <= 0.006),
    i.e. the Nasdaq row is validated by the close. adj_open = new open × (Yahoo adjclose / close).
 2. Dividend amounts where Yahoo and Nasdaq disagree by more than 0.0006 on a common ex-date are replaced
    by the Nasdaq amount and the dividend-adjusted series is rebuilt:
    adjclose_t = close_t × Π_{ex-dates e > t} (1 − D_e / close_{e−1}).
Everything else (dates, closes) is unchanged. No filling. Coverage before 2016-11-25 has no second price source.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

SYMS = ['SPY', 'IEF', 'TLT']


def main(d, out):
    d, out = Path(d), Path(out); out.mkdir(parents=True, exist_ok=False)
    disc = pd.read_csv(d / 'open_close_discrepancies_nasdaq_vs_yahoo.csv', parse_dates=['date'])
    nq = {}
    for line in (d / 'nasdaq_dividends.txt').read_text().split('\n'):
        if line.strip():
            s, body = line.split(' ', 1)
            nq[s] = pd.Series({pd.Timestamp(a): float(b) for a, b in (z.split(':') for z in body.split(';'))})
    (out / 'sessions.csv').write_bytes((d / 'inputs' / 'sessions.csv').read_bytes())
    log = []
    for s in SYMS:
        x = pd.read_csv(d / 'inputs' / f'{s}_raw_parsed.csv', parse_dates=['date']).set_index('date')
        dv = pd.read_csv(d / 'inputs' / f'{s}_dividends.csv', parse_dates=['date']).groupby('date').amount.sum()
        adj = x.adjclose.copy()
        if s in nq:
            c = dv.index.intersection(nq[s].index)
            bad = c[(dv.loc[c] - nq[s].loc[c]).abs() > 0.0006]
            if len(bad):
                for t in bad:
                    log.append(f'{s} dividend {t.date()}: Yahoo {dv.loc[t]} -> Nasdaq {nq[s].loc[t]}')
                dv.loc[bad] = nq[s].loc[bad]
                prev_close = x.close.shift()
                k = pd.Series(1.0, index=x.index)
                on = dv.index.intersection(x.index)
                k.loc[on] = 1 - dv.loc[on].values / prev_close.loc[on].values
                if np.isnan(k.iloc[0]): k.iloc[0] = 1.0
                # factor for day t = product of k over ex-dates strictly after t
                f = k[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
                # anchor: the last day keeps Yahoo's own ratio (Yahoo adjusts to the latest close)
                adj = x.close * f * (x.adjclose.iloc[-1] / x.close.iloc[-1])
                log.append(f'{s}: adjclose rebuilt; max rel diff vs Yahoo on unaffected years after 2004: '
                           f'{float((adj / x.adjclose - 1).loc["2005":].abs().max()):.2e}')
        o = x.open.copy()
        sd = disc[(disc.sym == s) & ((disc.nq_open - disc.yh_open).abs() > 0.006) & ((disc.nq_close - disc.yh_close).abs() <= 0.006)]
        for _, r in sd.iterrows():
            log.append(f'{s} open {r.date.date()}: Yahoo {r.yh_open} -> Nasdaq {r.nq_open}')
            o.loc[r.date] = r.nq_open
        ratio = adj / x.close
        pd.DataFrame({'date': x.index.strftime('%Y-%m-%d'), 'adj_open': (o * ratio).values, 'adj_close': adj.values}) \
            .to_csv(out / f'{s}.csv', index=False, float_format='%.10g')
    (out / 'S1_changes.txt').write_text('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
