# MH-v0.2 — QA addendum (after FINAL_AUDIT_V01.md)

Date 2026-11-24. Scope: check the 9 QA requirements against the existing v0.2 implementation and results. **Nothing was
re-run, re-parameterised or overwritten.** The measurements read the committed run outputs and local parquet artefacts
(`audit/qa_addendum_v02.py` → `reports/v02/qa_addendum/qa_measurements.json`). MVP v0.1 files were only read.
The locked historical test was not touched.

Runs checked: `reports/v02/runs/{development,validation}_a5bca96b79_cf00d9bc` (git `0ad6beb`, code `a5bca96b79`,
config `cf00d9bc`).

## Summary

| # | requirement | status | evidence / gap |
|---|---|---|---|
| 1 | Separate forecast quality, execution economics, portfolio simulation | **partial** | Forecast (G01 MSE/IC/R², OOS) and event study (gross labels of all admissible signals) are already separate from replays. Missing: an explicit per-signal **execution layer** (fixed notional, fee/adverse/rounding per signal) independent of the wallet. → D1 layer L2 |
| 2 | Keep results of ALL source signals independent of wallet state | **met for labels; fixed for storage** | Panels hold every admissible decision with gross labels y (+1 m) and y5 (+5 m), independent of any wallet. Until now only the G01 H60 predictions were committed. Now committed (gzip, deterministic): `reports/v02/qa_addendum/{split}_{h01,h02,h03}_all_decisions.csv.gz` and `{split}_g01_all_predictions.csv.gz` (all horizons, B0/B1/X) |
| 3 | Diagnostics without portfolio stop separate from risk-limited results | **formally met, materially violated** | `diag` (no kill-switch) and `constrained` are separate runs. But the pre-registered diag wallet (notional = min(50, cash), 100 USDT) **depletes**: it can no longer trade once cash < minNotional. This acts as an implicit irreversible stop (table A) |
| 4 | Do not use post-total-stop statistics as the only evidence of edge | **violated for G01 and H01 primary tests** | The primary tests use diag daily PnL over the whole OOS window. After depletion every day is a forced 0. G01-X traded in only 19 % (dev) / 13 % (val) of the window, H01 in 56 % / 36 %. Signs and verdicts are unaffected, because per-signal net is negative (event study). **Effect sizes and p-values of these tests are not interpretable as edge estimates.** Random-baseline comparisons for G01/H01 are uninformative (all seeds ≈ −90). → D1 layer L3 |
| 5 | Temporal clustering, cross-asset correlation, overlapping horizons | **partial** | Primary tests: moving-block bootstrap on the common UTC-day axis (14 d; 7/28 sensitivity) keeps cross-asset and intra-day dependence. 14-day blocks are 4.7× the longest primary hold (3 d). Per-target event-study HAC uses lags = ceil(H/grid). Gaps: pooled ("ALL") event-study rows have no inference; rank IC has no CI; the HAC lag is in rows, not time. Dependence is large (table C). → D1 layer L1 with day-block inference |
| 6 | Fees, slippage and rounding separately; residual costs at 0 bps | **met after decomposition** | v0.2 `slippage_cost` mixed adverse execution and tick/step rounding. Decomposition: table B. v0.2 0 bps: residual exactly 0 (exits at opens that are on the tick grid). v0.1 0 bps residual (audit: 0.26 USDT on E01-P dev) is fully explained by **rounding of stop/target trigger exits down to the tick**, as trigger prices are not on the grid (time exits 0; table D) |
| 7 | Freeze code/config/hypotheses/protocol before full backtests; Git tree complete | **met, with the v0.1 caveat about git evidence** | Pre-registration `a5b47c7` precedes every v0.2 backtest. A **clean clone at `0ad6beb` reproduces code hash `a5bca96b79`**, identical to the run manifests. Clean clone without data: 64 passed, 7 skipped (data-dependent). No source file is git-ignored (check-ignore over all .py/.yaml). Config and spec unchanged since `a5b47c7`. Code changes `a5b47c7 → 0ad6beb`: `asof` rewrite (the previous version crashed on smoke; the new one never forward-fills), float snapping of rounding, ledger reconciliation, manual checks, one integration test. After the runs, only `report.py`/`cli.py` (presentation). As in the v0.1 audit, git timestamps alone do not prove that no full backtest preceded `a5b47c7`; this rests on the experiment log |
| 8 | Do not change H01–H04 / G01 parameters based on results | **met** | `git diff a5b47c7 HEAD -- configs/multi_horizon_v02.yaml SPEC_MULTI_HORIZON_V02.md` is empty |
| 9 | Methodology changes only via a separate diagnostic experiment | **applied** | Items 1, 3–5 need new computations (wallet-independent replay, per-signal economics, pooled inference). They are pre-registered as **MH-v0.2-D1** (`SPEC_DIAGNOSTIC_D1.md`) and **not executed pending owner confirmation** |

Additional risk found (no effect on results): `model_id_for` and `asof` compare raw `asi8` integers. All indices are
`datetime64[us, UTC]` in the runs (checked), so assignments are correct (2021-10 → fit 0, …). Mixed ns/µs inputs would
break silently. A unit-safe version is part of D1's new code, not a patch to the v0.2 run code.

## A. Wallet depletion in the pre-registered diag replay (primary variants)

| split | variant | diag trades | cash at end | trading stopped by | share of OOS window before stop |
|---|---|---|---|---|---|
| development | G01-X-H60-thr0 | 1195 | 9.90 | cash < minNotional | 0.19 |
| development | G01-B1-H60-thr0 | 1119 | 10.01 | cash < minNotional | 0.17 |
| development | H01-H120-none | 966 | 9.93 | cash < minNotional | 0.56 |
| development | H02-H720-none | 456 | 20.96 | — | 1.00 |
| development | H03-H4320-none | 49 | 82.48 | — | 1.00 |
| validation | G01-X-H60-thr0 | 1087 | 10.01 | cash < minNotional | 0.13 |
| validation | G01-B1-H60-thr0 | 1085 | 9.96 | cash < minNotional | 0.12 |
| validation | H01-H120-none | 948 | 9.99 | cash < minNotional | 0.36 |
| validation | H02-H720-none | 805 | 78.53 | — | 1.00 |
| validation | H03-H4320-none | 118 | 135.15 | — | 1.00 |

Constrained replays: every primary variant hits the total stop early (1.7–14 % of the window), except H03 in
validation. They are risk views only, never edge estimates.

Consequences:
* The G01 economic test (X − B1) compares two wallets that both stop at about 13–19 % of the window. The diff is 0 for
  the remaining days.
* The H04 G01 and H01 tests compare a wallet that depletes with one that trades little. In validation, H01-c has 0
  trades, which was already flagged as abstention.
* The H02 and H03 primary tests are unaffected (no depletion).

## B. Cost decomposition, diag main (USDT; adverse = open × 2.5 bps per side; rounding = tick/step residual)

| split | variant | trades | gross | fees | adverse exec. | rounding | net |
|---|---|---|---|---|---|---|---|
| development | G01-X-H60-thr0 | 1195 | 15.80 | 83.75 | 20.94 | 1.21 | −90.10 |
| development | G01-B1-H60-thr0 | 1119 | 18.85 | 86.26 | 21.56 | 1.02 | −89.99 |
| development | H01-H120-none | 966 | 4.88 | 75.58 | 18.90 | 0.47 | −90.07 |
| development | H02-H720-none | 456 | −30.79 | 38.22 | 9.56 | 0.47 | −79.04 |
| development | H03-H4320-none | 49 | −11.39 | 4.87 | 1.22 | 0.04 | −17.52 |
| validation | G01-X-H60-thr0 | 1087 | 18.80 | 79.99 | 20.00 | **8.81** | −89.99 |
| validation | G01-B1-H60-thr0 | 1085 | 5.96 | 70.73 | 17.68 | **7.59** | −90.04 |
| validation | H01-H120-none | 948 | 2.07 | 69.56 | 17.39 | **5.14** | −90.01 |
| validation | H02-H720-none | 805 | 80.47 | 80.26 | 20.07 | 1.61 | −21.47 |
| validation | H03-H4320-none | 118 | 50.02 | 11.80 | 2.95 | 0.13 | 35.15 |

Identity gross − fees − adverse − rounding = net holds to < 1e-8 for every primary variant and scenario. Fees
recomputed from fills match. All raw entry opens lie on the 0.01 tick grid.

Rounding is material in validation and almost entirely SOLUSDT. For G01-X validation diag it is 8.71 of 8.81 USDT
(515 trades, median price $21.8, ≈ 3.4 bps per trade); ETH is 0.10 and BTC 0.003. A 0.01 tick on a ~$20 asset is
≈ 5 bps, and the buy price is rounded up after the adverse adjustment. In the 0 bps (rt0) and 10 bps (rt10, slip = 0) scenarios the
rounding residual is exactly 0. A rounding cost therefore exists only together with the adverse price adjustment
(round-up after × (1 + slip)).

Note: full cost-scenario replays compare **different trade sets**. Cheaper scenarios deplete later and trade more
(e.g. validation G01-X: 10 048 trades at 0 bps vs 1 087 at 25 bps). Cost sensitivity for edge assessment must use the
static fixed-signal recomputation (already in metrics.json) or D1 L2.

## C. Dependence of signals (all signals, wallet-free)

| split | family (primary hold) | signals | days with signal | signals / day (naive n per independent day) | decision times with ≥ 2 assets | later same-asset signals inside hold | lag-1 autocorr of daily mean label |
|---|---|---|---|---|---|---|---|
| development | H01 (2 h) | 5225 | 450 | 11.6 | 61 % | 0.21 | −0.06 |
| development | H02 (12 h) | 2381 | 388 | 6.1 | 66 % | 0.82 | 0.09 |
| development | H03 (3 d) | 312 | 152 | 2.1 | 70 % | 1.46 | **0.60** |
| validation | H01 (2 h) | 10294 | 725 | 14.2 | 58 % | 0.23 | −0.02 |
| validation | H02 (12 h) | 4196 | 658 | 6.4 | 60 % | 0.88 | 0.00 |
| validation | H03 (3 d) | 876 | 415 | 2.1 | 69 % | 1.60 | **0.60** |

G01 (H = 1 h): realised labels of the three targets at the same decision time are correlated at 0.80 (dev) / 0.73 (val).
All three targets have pred_X > 0 in 44 % / 53 % of decisions.

Reading: the effective number of independent observations is close to the number of distinct days (or fewer for
3-day holds), not the number of signals. Pooled per-signal t-statistics overstate evidence by roughly √(signals/day).
The day-block primary tests are the appropriate inference; pooled rows in the event study should not be read as tests.

## D. v0.1 residual at 0 bps (read-only; MVP v0.1 unchanged)

`reports/runs/*_2bff6fcca7_792e0459/trades.csv`, scenario `cost_rt0` (fee = 0, slip = 0): entry fills never differ from
the raw opens. The residual comes from exits only:

| split | exit reason | trades | residual USDT |
|---|---|---|---|
| development | stop | 1119 | 0.858 |
| development | target | 581 | 0.488 |
| development | time_exit / risk exits | 2133 | 0.000 |
| validation | stop | 193 | 0.227 |
| validation | target / target_gap | 115 | 0.117 |
| validation | time_exit | 706 | 0.000 |

Cause: `fill = round_down(trigger × (1 − 0), tick)`; stop/target triggers = fill × 0.994 / 1.009 are not on the tick grid.
This is rounding, not slippage. It was reported in v0.1 inside the `slippage` column. It is not a bug, but it is mislabelled.
