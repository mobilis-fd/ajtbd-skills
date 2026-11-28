"""EQ04: build the 10-year nominal Treasury note auction event list (no market data used).

Usage: python -I events.py FISCALDATA_RAW_DIR TREASURYDIRECT_RAW_DIR OUT_DIR
Primary source: Fiscal Data 'Treasury Securities Auctions Data' (auctions_query), all Notes.
Second source: TreasuryDirect TA_WS securities/search (Notes + TIPS from 2002-01).
Writes events_all_10y.csv (every 10-year-original record with its inclusion decision), events.csv
(included events) and events_qa.json (counts, cross-check results).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

SAMPLE_START = pd.Timestamp('2002-12-02')   # first IEF session in the frozen v0.3-pre inputs


def load_fiscaldata(d: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(d.glob('notes_p*.json')):
        rows += json.loads(f.read_text())['data']
    df = pd.DataFrame(rows)
    for c in ['announcemt_date', 'auction_date', 'issue_date']:
        df[c] = pd.to_datetime(df[c])
    df['offering_amt'] = pd.to_numeric(df['offering_amt'], errors='coerce')
    return df


def load_td(d: Path) -> pd.DataFrame:
    df = pd.DataFrame(json.loads((d / 'td_notes.json').read_text()))
    out = pd.DataFrame({
        'cusip': df['cusip'],
        'auction_date': pd.to_datetime(df['competitiveAuctionCloseDate'].str[:10]),
        'td_announcemt_date': pd.to_datetime(df['announcementDate'].str[:10]),
        'td_issue_date': pd.to_datetime(df['issueDate'].str[:10]),
        'td_security_term': df['securityTerm'], 'td_original_term': df['originalSecurityTerm'],
        'td_reopening': df['reopening'], 'td_type': df['type'], 'td_tips': df['inflationProtected'],
        'td_offering_amt': pd.to_numeric(df['offeringAmount'], errors='coerce')})
    return out


def classify(r) -> str:
    """Inclusion decision for one record whose original term is 10-Year. Frozen in PROTOCOL.md §2."""
    if r.inflation_index_security == 'Yes':
        return 'excluded_TIPS'
    if r.floating_rate == 'Yes':
        return 'excluded_FRN'
    if not (r.security_term == '10-Year' or re.match(r'^9-Year', r.security_term)):
        return 'excluded_offcycle_old_issue'     # e.g. 2008-10 6-year, 2019-11 3-year reopenings
    if r.announcemt_date == r.auction_date:
        return 'excluded_same_day_announced'     # unscheduled / small-value test auctions
    if r.auction_date < SAMPLE_START:
        return 'excluded_before_ief_data'
    return 'included'


def main():
    fd_dir, td_dir, out = map(Path, sys.argv[1:4])
    out.mkdir(parents=True, exist_ok=True)
    fd = load_fiscaldata(fd_dir)
    qa = {'fiscaldata_note_records': len(fd),
          'fiscaldata_first_auction': str(fd.auction_date.min().date()),
          'fiscaldata_last_auction': str(fd.auction_date.max().date())}
    t = fd[fd.original_security_term.str.contains('10-Year', na=False)].copy()
    qa['records_original_term_10y'] = len(t)
    dup = t.duplicated(['cusip', 'auction_date'], keep='first')
    qa['exact_duplicates_cusip_auction_date'] = int(dup.sum())
    t = t[~dup]
    t['decision'] = t.apply(classify, axis=1)
    # consistency checks inside the primary source
    t['chk_announce_before_auction'] = t.announcemt_date < t.auction_date
    t['chk_issue_after_auction'] = t.issue_date > t.auction_date
    t['chk_reopening_flag'] = (t.security_term == '10-Year') == (t.reopening == 'No')
    # second source
    td = load_td(td_dir)
    m = t.merge(td, on=['cusip', 'auction_date'], how='left', indicator=True)
    inwin = m.auction_date >= pd.Timestamp('2002-01-01')
    m['td_found'] = m['_merge'] == 'both'
    m['td_match_announce'] = m.td_announcemt_date == m.announcemt_date
    m['td_match_issue'] = m.td_issue_date == m.issue_date
    m['td_match_reopening'] = m.td_reopening == m.reopening
    m['td_match_term'] = m.td_security_term == m.security_term
    m['td_match_offering'] = m.td_offering_amt == m.offering_amt
    m = m.drop(columns=['_merge'])
    inc = m[m.decision == 'included']
    qa['decisions'] = m.decision.value_counts().to_dict()
    qa['included_checks_failed'] = {c: int((~inc[c]).sum()) for c in
                                    ['chk_announce_before_auction', 'chk_issue_after_auction', 'chk_reopening_flag',
                                     'td_found', 'td_match_announce', 'td_match_issue', 'td_match_reopening',
                                     'td_match_term', 'td_match_offering']}
    # anything in TreasuryDirect (10-year original, nominal, regular term) missing from Fiscal Data?
    tdn = td[(td.td_original_term == '10-Year') & (td.td_tips == 'No') &
             td.td_security_term.str.match(r'^(10-Year|9-Year)') & (td.auction_date >= SAMPLE_START)]
    miss = tdn.merge(t[['cusip', 'auction_date']], on=['cusip', 'auction_date'], how='left', indicator=True)
    qa['in_treasurydirect_not_in_fiscaldata'] = miss[miss._merge == 'left_only'][['cusip', 'auction_date']] \
        .astype(str).to_dict(orient='records')
    # same-day double events (two included auctions on one date) would be duplicates of one event
    qa['included_same_auction_date_pairs'] = int(inc.auction_date.duplicated().sum())
    qa['included_by_year'] = inc.auction_date.dt.year.value_counts().sort_index().astype(int).to_dict()
    qa['included_by_type'] = {'original': int((inc.reopening == 'No').sum()), 'reopening': int((inc.reopening == 'Yes').sum())}
    cols = ['cusip', 'security_term', 'original_security_term', 'reopening', 'announcemt_date', 'auction_date',
            'issue_date', 'offering_amt', 'closing_time_comp', 'decision'] + \
           [c for c in m.columns if c.startswith('chk_') or c.startswith('td_match') or c == 'td_found']
    m = m.sort_values('auction_date')
    m[cols].to_csv(out / 'events_all_10y.csv', index=False, date_format='%Y-%m-%d')
    inc = m[m.decision == 'included'][cols[:9]].sort_values('auction_date')
    inc.to_csv(out / 'events.csv', index=False, date_format='%Y-%m-%d')
    (out / 'events_qa.json').write_text(json.dumps(qa, indent=2, default=str))
    print(json.dumps(qa, indent=2, default=str))


if __name__ == '__main__':
    main()
