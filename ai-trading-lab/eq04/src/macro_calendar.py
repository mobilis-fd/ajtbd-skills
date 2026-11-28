"""EQ04: build FOMC decision-day, CPI and Employment Situation release-date lists from saved raw pages.

Usage: python -I macro_calendar.py RAW_CAL_DIR OUT_CSV
FOMC: last day of every item titled '... Meeting' (scheduled and unscheduled; cancelled meetings,
conference calls and notation votes excluded). Historical pages 2002-2020, current page 2021+.
CPI / Employment Situation: release dates parsed from BLS archive link filenames (mmddyyyy).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

MONTHS = {m: i for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                                      'September', 'October', 'November', 'December'], 1)}


def _last_day(year: int, month_txt: str, days_txt: str) -> pd.Timestamp:
    """Last month name (full or 3-letter, e.g. 'Jan/Feb', 'July 31-August') and last day number."""
    names = re.findall(r'[A-Za-z]{3,}', month_txt)
    mon = {k[:3]: v for k, v in MONTHS.items()}[names[-1][:3]]
    d = re.findall(r'\d+', days_txt)[-1]
    return pd.Timestamp(year, mon, int(d))


def fomc(raw: Path) -> list[pd.Timestamp]:
    out = []
    for f in sorted(raw.glob('fomc_[0-9]*.htm')):
        y = int(f.stem.split('_')[1])
        for h in re.findall(r'<h5[^>]*>([^<]*)</h5>', f.read_text()):
            if 'Meeting' not in h or 'cancelled' in h:
                continue
            head = h.split('Meeting')[0].replace('(unscheduled)', '')
            out.append(_last_day(y, head, head))
    t = (raw / 'fomc_current.htm').read_text()
    parts = re.split(r'<h4[^>]*><a[^>]*>(\d{4}) FOMC Meetings</a>', t)
    for y, body in zip(parts[1::2], parts[2::2]):
        mon = re.findall(r'fomc-meeting__month[^>]*>(?:<strong>)?([^<]*)<', body)
        day = re.findall(r'fomc-meeting__date[^>]*>([^<]*)<', body)
        for mo, da in zip(mon, day):
            if 'cancel' in da.lower() or 'notation' in da.lower():
                continue
            out.append(_last_day(int(y), mo, da))
    return sorted(set(out))


def bls(path: Path) -> list[pd.Timestamp]:
    ds = [pd.Timestamp(f'{s[4:]}-{s[:2]}-{s[2:4]}') for s in path.read_text().strip().split(',')]
    return sorted(d for d in set(ds) if d >= pd.Timestamp('2002-06-01'))


def main():
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = [('FOMC', d) for d in fomc(raw)]
    rows += [('CPI', d) for d in bls(raw / 'bls_cpi_dates_mmddyyyy.txt')]
    rows += [('NFP', d) for d in bls(raw / 'bls_empsit_dates_mmddyyyy.txt')]
    df = pd.DataFrame(rows, columns=['kind', 'date']).sort_values(['date', 'kind'])
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    df.to_csv(out, index=False)
    print(df.groupby('kind').date.agg(['count', 'min', 'max']))


if __name__ == '__main__':
    main()
