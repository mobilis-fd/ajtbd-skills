# Pre-registration — Equity Alpha Screening v0.3-pre, run01

Committed **before any historical event, control or summary statistic was computed**. The only executions before
this commit: the original `--self-test` and `tools/verify.py synthetic` (synthetic prices only), data download and
data QA (`reports/data_qa.md`, which computes no strategy statistic). Branch `research/equity-screening-v03-pre`,
created from `release/multi-horizon-v0.2` (c978919) with only additive files under `equity_v03pre/`; no v0.1/v0.2 file is
changed, no v0.1/v0.2 code, holdout, demo or live mode is run. The crypto holdout in `CLAUDE.md` is not touched (no crypto data read).

## 1. Hypotheses and parameters (frozen, taken verbatim from `original/README.md`)

EQ01, EQ02, EQ03, periods T3/T2/T1, costs 0/5/10/25/40 bps RT, bootstrap 4000 reps, blocks 3/6/12 (6 primary),
seed 20261127+block, inference cutoff max(24, 2·block), Holm across the 9 cells — exactly as in `original/equity_screen.py`
(sha256 `8073ee1f…9b0b`). No parameter, window, ETF, threshold or period is changed, searched or added.

## 2. Data (frozen)

Source: Yahoo Finance v8 chart API (free, no key; research use subject to Yahoo terms), daily, `period1=2002-12-01`,
`period2=2026-11-07`, downloaded 2026-11-27 12:00 UTC. Convention: `adj_open = open × adjclose/close`, `adj_close = adjclose`.
Calendar: XNYS from exchange_calendars 4.13.3, cross-checked with pandas_market_calendars 5.7.0 (identical, 6022 sessions,
2002-12-02 … 2026-11-06). Data are cut at 2026-11-06 ("first week of November"). Raw files are read-only and not committed
(repo rule 7); copies are in the project files folder `equity_v03pre_data/`.

| file | sha256 |
|---|---|
| raw/yahoo_SPY.json | `2db1c55d56cf3c539ca119e2911c7c9c5aa919f7853c2d91568212358ed60e1a` |
| raw/yahoo_IEF.json | `e5c172fc92f67effef3969f83c80714a61f803760479acb8a432fbc8710cd6e6` |
| raw/yahoo_TLT.json | `ff946cd48723224d7e438eb1f9a37ad49d7d60fd07c211d2ea66ecfa834bec56` |
| inputs/sessions.csv | `246d18d7a72db3088311935af7681de2ade75f9a33c28d11500d128b84f57017` |
| inputs/SPY.csv | `46068a7424c689c609e098277e10ab316c96f47e6c41bf9dc30e672d75097638` |
| inputs/IEF.csv | `6da48c6ec089d8c13a816186faf4eec47b5a3702376068e1890284ad5bfeb032` |
| inputs/TLT.csv | `b9c3887d6f242fa00f012ce1796fd406b9543fd2163372d40d1cb2dc57fc7bcc` |
| inputs_S1/SPY.csv | `91315a72b9b08cbc4b533e236cc6c27e8b26c2fe2e64f2927790a40f12816e59` |
| inputs_S1/IEF.csv | `c9c8aa2d1c446687cfbab2076e01e6c16512a8b11bde5542036d806ffc8f2907` |
| inputs_S1/TLT.csv | `42b88a7134ec81fbab47e98295b090c5d0892ccfd4a47a799c987fcfdac5e50e` |
| inputs_S1/S1_changes.txt | `fdf48203d0c301746003f3bc9d0efcb1d6faeacf33fa55d45f5a214e8721f4f8` |
| nasdaq_monthsums.json | `8de446dd7d019e6b5e0c51f3fc0d400e814b40bb893633dfdb8cc8ec9de893e0` |
| nasdaq_days_mismatch_months.csv | `f4545ce4c201fdd02802b4b69bc8a96bc68e9ddc8e0ed92cbfc6850d257b02e4` |
| nasdaq_dividends.txt | `1f40a0d705f2467f52a1908a1e7710ba2ca9814579611469410d762796b1b15f` |
| open_close_discrepancies_nasdaq_vs_yahoo.csv | `7660c7c2123b6c71e1e32525d7cef958a3b9c8f85c7c464829255275381d2015` |

Environment: Python 3.13.18, numpy 2.5.3, pandas 3.0.5 (cloud container, Linux).

## 3. Runs (fixed order)

1. `python -I original/equity_screen.py --self-test` and `python -I tools/verify.py synthetic` (must pass).
2. **Primary** (the only basis for conclusions): `python -I original/equity_screen.py --data data/equity_v03pre/inputs --out equity_v03pre/reports/run01_primary`
3. **S1, data-corrected sensitivity** (descriptive): same script, `--data data/equity_v03pre/inputs_S1 --out equity_v03pre/reports/run02_S1`.
   S1 replaces 28 stale Yahoo opens (2016-12 … 2018-05) by Nasdaq opens and two IEF 2003 dividends by Nasdaq amounts (AUDIT D1, D2).
   S1 does not replace the primary; a conclusion that holds only in one of the two is reported as fragile.
4. Reconciliation: `python -I tools/verify.py reconcile <data> <run>` for both runs (independent events, summary statistics,
   bootstrap CI with an independent RNG at 20000 reps).
5. Report `EQUITY_SCREENING_REPORT.md`: every cell of both runs, including negative ones.

Not run: a scheduled-calendar variant (AUDIT A4; affected months are listed instead), any other variant.

## 4. Decision rule (fixed now; README's gate made concrete)

"Plausible cost" = **10 bps round trip** (liquid ETFs at the open; scenario, not a broker quote). "Economically material"
= paired difference **≥ +10 bps per event**. These two numbers are the auditor's operationalisation of the README wording,
fixed before results.

Per cell (period × hypothesis), primary run:

- **Candidate for follow-up** — all of: gross > 0; net at 10 bps > 0; delta ≥ +10 bps; lower bound of the 95% CI
  (6-month blocks) > 0; Holm-adjusted p (6-month) < 0.05; delta > 0 also in S1; no unresolved material QA issue for the cell.
- **Inconclusive** — gross > 0 and delta > 0, but at least one other candidate condition fails.
- **Not supported** — delta ≤ 0, or gross ≤ 0, or net at 10 bps ≤ 0.

A hypothesis may go to the portfolio stage only if at least one cell is a candidate; this is permission to design a
further test, never approval to trade. Because the bootstrap is anti-conservative at n ≈ 28–78 (AUDIT A3), even a
candidate is described as weak evidence. Regime comparisons are not causal. Annual ROI is not inferred from event means.
