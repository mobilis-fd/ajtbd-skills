# Independent audit — Equity Alpha Screening v0.3-pre

Auditor: Claude (AI assistant), 2026-11-27. Written **before any historical result was computed**; the only runs
so far are the original `--self-test` and the synthetic checks in `tools/verify.py synthetic` (synthetic prices only).
Any later entry is dated and marked "post-result".

## Package received

| item | sha256 |
|---|---|
| `Equity_Alpha_Screening_v03_pre.zip` (from the owner, hash confirmed by the owner in chat) | `22c85ceaebc30b85a752c856bce7ba6b64424439a36a5223ce5f551cefbfca91` |
| `original/README.md` | `bed79f9448f47c179f46b7dd3347248c2a0a6e46d3199a9216d8dee6aeb12657` |
| `original/equity_screen.py` | `8073ee1fa0914e400463f04f1bae3a19cbcc2e792a21814f4b296399c6689b0b` |

The original files are committed byte-for-byte and are never edited. Everything the audit adds lives in `tools/`.

## Line-by-line conclusions (code vs README)

| Area | README requirement | Code | Verdict |
|---|---|---|---|
| Inputs | sessions + SPY/IEF/TLT `date,adj_open,adj_close`, Dec 2002 … ≥ 2026-11-05, no filling | `load()`: unique sorted dates, exact index equality with calendar, finite positive prices, coverage check | Correct. Cannot check calendar/adjustment correctness (README says so) → done in `tools/data_qa.py` |
| EQ01 signal | MTD total return from prior month-end close to the close before the last five sessions; lower wins; ties → SPY | `close[i-1]/close[a-1]-1`, `i=b-4`, `min` over dict in order SPY, IEF | Correct; signal uses only closes ≤ entry−1 |
| EQ01 trade/control | buy next open (i), exit last close (b); control = fixed EW SPY+IEF over same dates | `ret(sel,i,b)`, control `(ret(SPY)+ret(IEF))/2` | Correct (mean of the two returns = EW buy-and-hold without rebalancing) |
| EQ02 | buy last session open, exit 3rd session close of next month; control = all 4-session windows starting in anchor month | `ret(SPY,b,b+3)`; control `k∈[a,b]`, `ret(k,k+3)` | Correct; control includes the event window and windows reaching into next month (README accepts) |
| EQ03 | TLT, first of last five open → month-end close; control = all 5-session windows wholly within month | `ret(TLT,i,b)`; control `k∈[a,b-4]` | Correct; includes event window (README accepts) |
| Periods | T3 2003–2016, T2 2017-10…2024-04, T1 2024-06…2026-10; exclude events crossing boundaries | `entry>=start & exit<=end` | Correct; EQ02 controls never extend beyond the event exit, so the filter also covers controls |
| Costs | 0/5/10/25/40 bps RT, half on entry, half on modelled exit value | `net = g − f(2+g)`, `f=cost/20000`; same for control | Correct; break-even `2g/(2+g)` correct (verified by known-answer test) |
| Bootstrap | paired circular monthly block bootstrap, 4000 reps, blocks 3/6/12 (6 primary), fixed seed, no inference for n < max(24, 2·block) | as specified, seed `SEED+block` | Correct implementation; see A3 for properties |
| Holm | across estimable primary comparisons in the 9 cells | step-down on `p_6m` across all cells with a p | Correct (verified on known p-values) |

## Findings

Severity: **material** = could change a conclusion; **minor** = documentation or robustness; **none** = checked, no issue.

| # | Severity | Finding | Action (decided before results) |
|---|---|---|---|
| A1 | minor (test only) | The original "future mutation" self-test is not discriminating: it raises IEF to 200 from the entry day. Under flat prices SPY wins the tie anyway, and a look-ahead bug would make IEF look *better*, so the min-rule still picks SPY. The test would pass even with look-ahead. | Not a bug in the strategy code (the code reads `close[i-1]`). Added a discriminating test (IEF falls to 50 from entry → choice must stay SPY; signal-day close changed → choice must switch). Both pass. Original untouched. |
| A2 | none | Suspected: a truncated final month with ≥ 15 sessions could create a false month-end. Not possible: the guard `b+3 >= len(cal)` skips any month whose last row is within 3 rows of the end of data, which is always true for a truncated last month. | Synthetic test added; passes. Data are cut at 2026-11-06 (5 November sessions) anyway. |
| A3 | material for interpretation | p-values are **one-sided** (H1: paired difference > 0), via centred bootstrap; the CI is a two-sided 95% percentile interval. README does not say this. Synthetic check (iid N(0,1), block 6, 300 sims): rejection rate at 5% = 0.083 (n=28), 0.083 (n=60), 0.057 (n=160); CI coverage 0.857 / 0.883 / 0.927. The procedure is **anti-conservative at the sample sizes of T1 (≈28) and T2 (≈78)**. | Not changed (README fixes the procedure). Reported; p-values and CIs are read as optimistic. The follow-up gate in PROTOCOL.md does not relax anything because of this. |
| A4 | minor | Script uses the supplied (realised) calendar. README asks for exchange-announced dates. Unscheduled closures change event dates in 4 months: 2006-12 (EQ02 exit Jan 5 vs scheduled Jan 4, 2007), 2007-01 (control windows start Jan 3 vs Jan 2), 2012-10 (EQ01/EQ03 entry Oct 23 vs Oct 25, Hurricane Sandy), 2018-11 (EQ02 exit Dec 6 vs Dec 5). | Primary unchanged; affected months listed in the report. Not re-run (≤ 1 event per affected cell). |
| A5 | minor | Paired difference and its CI are computed on **gross** returns only. Net deltas differ by `f·(g−c)`, negligible. Break-even is vs zero cash, not vs control. | Reported as is. |
| A6 | minor | Bootstrap seed depends only on block length, so cells of equal length reuse identical index draws. Harmless (paired within cell); cells are not independent anyway. | Noted. |
| A7 | minor | Self-test "split summaries" assertion only checks `months > 0`. | Covered by the reconciliation in `verify.py`. |
| A8 | minor | Package versions are not recorded by the script. | Recorded in PROTOCOL.md / run log. |
| D1 | material (data) | Yahoo **opens are stale on some days** (open = previous close or same-day close). Against Nasdaq (2016-11-25 … 2026-11-06), 21 SPY, 4 IEF, 3 TLT opens differ by > 0.6 cent with the Nasdaq close agreeing; concentrated in 2016-12 … 2018-05 (SPY open 2017-05-17: Yahoo 240.08 vs Nasdaq 238.10). Opens are the entry price of every event and control window. T3 (2003–2016) has no second source; heuristic stale-open flags exist in every year (data_qa.md §3). | Primary input not edited (README forbids silent substitution). Pre-registered sensitivity **S1** replaces validated opens with Nasdaq values. T3 residual risk reported as a limitation. |
| D2 | material (data, small scope) | Yahoo IEF dividends on 2003-09-02 (0.764) and 2003-10-01 (0.731) are ≈ 2.7× Nasdaq (0.2758, 0.2741) and ≈ 2.7× neighbouring months. If Yahoo is wrong, IEF total return is overstated by ≈ 0.55% on each of those days, which enters the EQ01 **signal** (IEF MTD return) for Sep and Oct 2003 only. | S1 uses the Nasdaq amounts and rebuilds the adjusted series. |
| D3 | minor | Stooq refused automated download from the cloud host and from a browser ("Access denied"). Not bypassed. | Nasdaq used as second source, only 10 years of prices and partial dividend history; SPY dividends only internally checked. |
| D4 | none | Calendar: XNYS (exchange_calendars 4.13.3) and NYSE (pandas_market_calendars 5.7.0) agree on all 6022 sessions; Yahoo dates match exactly for all three ETFs; no splits; Yahoo's adjustment factors match its own dividend events to < 2e-6 on every ex-date with no unexplained factor changes. | — |

## Not audited

The economic rationale and cited papers were not reviewed. Execution realism (opening auction fills, spreads, fees,
taxes, FX) is out of scope by design of the README and is deferred to a portfolio stage.
