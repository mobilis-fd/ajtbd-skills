# MH-v0.2-D1 — wallet-independent signal diagnostics (pre-registered, diagnostic only)

Status: **specified and implemented; NOT executed until the owner confirms** (QA requirement 9).
Motivation: `reports/v02/QA_ADDENDUM_V02.md`. The pre-registered v0.2 diag wallet depletes, so G01/H01 primary-test
statistics are dominated by forced zero days after depletion (requirements 3–4). There is no per-signal
execution-economics layer (1, 6), and the pooled signal statistics lack dependence-robust inference (5).

## What D1 is / is not
* D1 **does not change** any v0.2 hypothesis, signal rule, threshold, hold, fit schedule, split, OOS window, cost scenario,
  filter assumption or random seed. It reuses the v0.2 panels as produced by the frozen v0.2 code (`g01_panel`, `h_panel`).
* D1 **does not replace** the v0.2 primary tests or gate verdicts. Its tests are diagnostic re-estimations: reported with
  Holm for reference, never as confirmatory evidence. D1 cannot by itself move any variant to Gate 3.
* No historical-test data, no v0.1 period, no live data, no orders.

## Layers
**L1 — signal/forecast quality (gross, before execution).** Population per family and hold:
* H01–H03: every admissible OOS decision with `signal = True` and a valid label y (+1 min entry).
* G01: for each model B0/B1/X, threshold θ ∈ {0, c, 2c} and H: every (T, target) row with pred > θ and valid y
  (all targets, not only the portfolio-selected one).
* Baseline: all admissible rows of the same family/H with valid y (unconditional).
Statistics: mean gross label (bps), mean − baseline mean, share > 0; pooled over assets and per asset.

**L2 — execution economics per signal (no wallet).** Each L1 signal is executed independently with notional 50 USDT
and unlimited virtual cash (overlapping positions allowed; this is NOT a tradable portfolio). Same fill rules as v0.2:
buy = ceil_tick(open·(1+slip)), sell = floor_tick(open·(1−slip)), qty = floor_step(50/buy). Per signal:
gross = qty·(o_x − o_e); fees = fee·qty·(fill_in + fill_out); adverse = slip·qty·(o_e + o_x);
rounding = qty·(fill_in − o_e(1+slip)) + qty·(o_x(1−slip) − fill_out); net = gross − fees − adverse − rounding.
Scenarios: main, rt0, rt10, rt40 (per-side fee/slip as v0.2), and main with +5 min delay (labels y5).
Break-even RT cost (bps) = mean gross / notional.

**L3 — portfolio without depletion.** Identical one-position logic, decision grid, selection, ties and holds as the v0.2
diag replay, but notional is **always 50 USDT**: virtual cash 1,000,000, PnL measured relative to it, no kill-switch.
Variants: the 9 v0.2 primary-test inputs (G01-X/B1-H60-thr0, G01-X-H60-thrc, H01-H120 none/common/c,
H02-H720 none/common/c, H03-H4320 none/common/c). Scenarios: main, rt0, rt10, rt40 (hurdle recomputed as in v0.2)
and delay 5 min. Random baseline: the v0.2 random intents (seeds 0–99, same frequencies) with fixed 50 notional.
Reported alongside, unchanged: the v0.2 diag (depleting) and constrained results.

## Inference (requirement 5)
* All D1 inference uses the moving-block bootstrap on the **common UTC-day axis**: blocks 14 d (7/28 sensitivity),
  2000 draws, seed 42. Signal-level statistics are ratio estimators Σ(day sums)/Σ(day counts) over resampled days,
  which keeps intra-day clustering, cross-asset correlation and horizon overlap (≤ 7 d < 14 d) inside blocks.
* Per-signal naive t-statistics are not reported. Effective sample proxies (days, signals/day) are reported.
* L3 re-estimation of the 9 v0.2 primary comparisons on fixed-50 daily PnL, one-sided H0 "≤ 0", Holm for reference.

## Interpretation rules (fixed in advance)
* An L1 gross effect that does not survive L2 main costs is "no executable edge".
* An L3 improvement from trading fewer signals with zero or near-zero trades is "abstention", not edge (V24).
* D1 results cannot change v0.2 parameters. Any new rule idea is a new version evaluated only on later data.

## Implementation
`src/research/diag_d1.py`; CLI `python -m src.research.cli diag-d1 --split {development|validation} --confirmed`
(refuses without `--confirmed`). Outputs: `reports/v02/diagnostics/D1/<split>_<code>_<config>/`. Tests in
`tests/research/test_diag_d1.py`.
