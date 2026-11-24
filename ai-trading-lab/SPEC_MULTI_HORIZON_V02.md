# MH-v0.2 — Multi-Horizon Research: pre-registered specification as implemented

Source specification: "AI Trading Lab — Multi-Horizon Research v0.2" (25.11.2026). This file fixes every
interpretation decision **before** development/validation results were computed (see `EXPERIMENT_LOG_V02.md`).
Machine-readable: `configs/multi_horizon_v02.yaml`. Changing anything after results ⇒ new version id.

Predecessor MVP v0.1 is frozen. Its handoff commit is `789683e` on branch `ccr-481f4ca9-6sjk8p`. This branch
`research/multi-horizon-v02` was created from that commit and does not modify v0.1 files, configs or reports.
The v0.1 period 2025-11-01 → 2026-11-01 is never read (`load_ctx` asserts `split_end <= 2025-11-01`).

## 1. Data

* Binance spot 1m monthly archives (`data.binance.vision`), all 12 fields, SHA256 against the `.CHECKSUM` files.
  Raw zips are stored read-only. A changed checksum on re-download is reported, never overwritten.
* Information assets: BTC, ETH, SOL, BNB, XRP, ADA, DOGE, LINK, LTC (USDT). Traded: BTC, ETH, SOL (fixed order).
  The set is fixed and retrospectively known, so it is not a point-in-time universe.
* Coverage: SOLUSDT has no archive before 2020-08 (listing 2020-08-11). The other eight assets have archives
  earlier. Downloaded months: 2020-08 … 2024-12. **No historical-test months are downloaded.**
* Timestamp units are detected per value and recorded per file. All archives before 2025 are expected to be ms.
* Bars of 30m/1h/4h/1d are built only from complete aligned 1m buckets. `T` = bar END. There is no synthetic filling.
  Missing bars ⇒ NaN features and labels (no gap skipping).

## 2. Splits, effective windows, fitting

| split | range [start, end) | evaluated OOS window |
|---|---|---|
| development | 2021-01-01 → 2023-01-01 | **2021-10-01 → 2023-01-01** |
| validation | 2023-01-01 → 2025-01-01 | 2023-01-01 → 2025-01-01 |
| historical test | 2025-01-01 → 2025-11-01 | locked: not downloaded, not run |

**Pre-registered reduction (coverage):** monthly fits at 00:00 UTC on the 1st use a rolling 365-day window. The first
fit needs complete history for all 9 assets back to F − 365 d − 28 d, where 28 d is the longest feature lookback
(H03 r28d). SOL starts 2020-08-11, so the first admissible fit is **2021-10-01**. It is used as the common start for
all families and targets, so every comparison uses the same OOS window. Development data 2021-01 … 2021-09 serve
only as training history. Validation fits use the trailing 365 days, including development data (prequential OOS).

* Training rows: decision T ∈ [F − 365 d, F), label exit (T + 1 min + H) ≤ F (mature only), all inputs valid, and the
  label does not cross a split boundary (2023-01-01, 2025-01-01).
* Purge: evaluated decisions satisfy T ≤ split_end − 5 min − H_max(family). H_max is 4 h for G01 and H01, 24 h for
  H02 and 7 d for H03. Labels and positions never cross the boundary.
* Model for decision T = latest fit F ≤ T.

## 3. Timing, labels, execution

* Signal after the close of the bar ending at T. Entry at the 1m open starting T + 1 min (stress: T + 5 min). Exit at
  the 1m open starting entry + H. Label = exit_open / entry_open − 1 (gross). A missing minute ⇒ invalid observation.
* Execution: buy = open·(1+slip) rounded up to tick; sell = open·(1−slip) rounded down; qty rounded down to step;
  notional = min(stake, cash/(1+fee)); fee on the actual notional of each side; cash is never negative.
* Costs per side (fee/adverse, bps): main 10/2.5 (c = 0.0025 RT); rt0 0/0; rt10 5/0; rt40 15/5 (hypothetical).
* Filters (assumed; historical exchangeInfo unavailable): tick 0.01; step BTC 1e-5, ETH 1e-4, SOL 1e-3; minNotional 10.
* One position per wallet. A new entry is allowed only at a decision time T ≥ the previous exit time.
  Missing exit minute ⇒ exit at the first later available open, flagged `uncertain`; minutes missing inside a
  hold ⇒ `uncertain`. Conservative alternative: exit at min(open, low) of that minute.

## 4. Families

**G01 (30m decisions):** r(i,k) = ln C(T)/C(T−k), k ∈ {30m, 1h, 4h}; F(i,k) = mean of the other 8 assets.
Target extras are std(ddof=0) of the last 48 closed 30m log returns (incl. the bar ending T), log(V/median of the
previous 48 V) (V > 0, median > 0) and 2·taker/V − 1 (V > 0). Valid row ⇒ all 9 assets' returns and the target extras
are valid, so B0/B1/X use identical samples. B0 = train mean label. B1 = Ridge(α=10) on own r×3, F×3 and extras×3
(9 features). X = B1 + (r(j,k) − F(i,k)) for the 8 others × 3 k (33 features). Standardisation is train-only.
Zero-variance train columns are dropped and recorded. Separate model per target and horizon (H = 60 primary;
30 and 240 secondary). Trading: among targets with pred > θ choose the max (ties BTC, ETH, SOL); θ ∈ {0, c, 2c}.

**H01 (hourly):** signal r1h(T) ≤ q20 of r1h over [F−365 d, F), where q20 is fixed at the current fit.
Holds 2h (primary), 1h, 4h.
**H02 (every 4h):** r4h > 0 and r24h > 0. Holds 12h (primary), 4h, 24h.
**H03 (00:00 UTC):** r7d > 0 and r28d > 0. Holds 3d (primary), 1d, 7d.
For H01–H03 there is no ranking: binary signal, ties BTC > ETH > SOL.

**H04 (no-trade zone):** the conditional gross estimate is the mean label of the target's signal events in the
train window, using the current fit's threshold for H01 and only if there are ≥ 100 events. Variants:
`none` (unfiltered), `common` (unfiltered restricted to available estimates), `c` (est > c), `2c` (est > 2c).
G01: θ = c and 2c vs θ = 0. In full replays at other cost levels the hurdle is recomputed (c_s = scenario RT cost).

## 5. Replays, controls

* `diag`: fixed size ≤ 50 USDT, no kill-switch. `constrained`: daily 1.5 USDT from UTC day-start equity (equity at the
  last known close before 00:00) and total 10 USDT. A breach at a known 1m close ⇒ exit at the next available
  1m open. Daily ⇒ pause until the next UTC day; total ⇒ end of the run. Overshoot is logged.
* Risk-matched diagnostic: stake = min(50, cash, 0.50/(σ1h·√H_hours)), where σ1h is the std of closed hourly log
  returns over the trailing 30 d. Invalid σ ⇒ no trade.
* Controls: cash; BTC $50 B&H; EW BTC/ETH/SOL $50 total (3 positions); BTC all-in $100 (context, diag only);
  B&H under the constrained overlay does not re-enter. Exposure-matched passive = EW daily PnL × strategy time
  exposure (analytic, disclosed).
  Random entries: seeds 0–99, same decision grid and hold. Frequencies come from train windows only:
  per-symbol train signal frequency (H01–H03), or the train share of each target being the in-sample X argmax > 0 (G01).
* Regimes (causal, per target at T): trend = sign of the trailing 30 d log return (hourly closes). Vol = trailing 30 d
  σ1h vs the median of σ1h in the current fit's train window.

## 6. Statistics and decision gates

Primary family (Holm, α = 0.05, 14-day blocks; sensitivity 7/28; 2000 draws; seed 42; moving-block bootstrap over
the common UTC-day axis; one-sided H0 "≤ 0"):
1. G01 forecast: equal-weight mean over targets of MSE(B1) − MSE(X), H = 1h.
2. G01 economic: daily PnL(X, θ=0) − daily PnL(B1, θ=0), diag, H = 1h, main costs.
3–5. H01 (2h), H02 (12h), H03 (3d): mean daily net PnL of the diag replay, main costs.
6–9. H04: daily PnL(filter c) − daily PnL(common) for H01–H03, and G01-X θ=c − θ=0.

Everything else is secondary/exploratory: other holds, 2c, delay, rt scenarios, constrained, risk-matched, random,
per-year/asset/regime, event-study HAC t (lags = ceil(H/grid)), H01 OLS on prior return. A secondary hold that
"wins" is not a primary result.

Gates: G1 = QA/leakage/reproducibility failure blocks conclusions. G2 = no effect or net ≤ 0 at main cost ⇒ reject
**this version** (inconclusive if low power). G3/G4 need audit; there is no automatic demo or test.
