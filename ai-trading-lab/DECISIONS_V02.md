# Decisions — MH-v0.2

V01–V20 were taken before any v0.2 backtest output existed (pre-registration commit). Later entries are dated.

| # | Decision | Reason / consequence |
|---|---|---|
| V01 | Branch `research/multi-horizon-v02` created from v0.1 handoff `789683e`; v0.1 files untouched (only additive `.gitignore` line for v0.2 parquet) | Spec §1. |
| V02 | v0.1 infrastructure re-verified before reuse: 42/42 v0.1 tests pass on the branch. The rebuilt `src/data` was read in full. Reused: `parse_kline_csv` (ms/µs per value), `check_1m`, `clean_1m`, `Filters/round_up/round_down`, `block_bootstrap`, `holm`, `compute_metrics/daily_pnl/trade_stats` | The v0.1 engine is not reused for execution: v0.2 needs time-only exits, T+1 m entry, 7-day holds and variable stakes. A new vectorised engine `src/research/replay.py` was written. |
| V03 | Rebuilt v0.1 `check_1m` omits `taker_buy_quote ≤ quote_volume`. v0.2 adds that check plus trade-count consistency without editing v0.1 | Spec §2. |
| V04 | Dependencies: scikit-learn 1.9.1, statsmodels 0.15.0 (BSD-3) added with `pip install -c requirements.lock`. v0.1 pins unchanged. Full freeze in `requirements-v02.lock` | Spec §9. |
| V05 | Only months 2020-08 … 2024-12 downloaded; historical test months are not downloaded | Smallest exposure to the locked period. |
| V06 | Raw zips chmod read-only. A checksum change on re-download is reported (`source_changed_or_corrupt`), never overwritten. Manifest stores Last-Modified/ETag | "Хранить исходные файлы неизменяемыми; изменения источника". |
| V07 | Rows with irregular close_time (truncated candles right before exchange outages, 5–6 per symbol, e.g. 2021-04-25 04:00 close 04:00:58.146) are dropped as invalid and become 1-minute gaps | Conservative; never repaired. |
| V08 | Common OOS start 2021-10-01 for all families/targets (first fit with 365 d + 28 d history for all 9 assets; SOL from 2020-08-11) | Spec §2 coverage rule; fixed before modelling. |
| V09 | Split-boundary purge uses the 5-minute stress delay: T ≤ end − 5 min − H_max(family) | Both primary (+1 m) and stress (+5 m) executions stay inside the split. |
| V10 | Training labels that cross 2023-01-01 or 2025-01-01 are excluded from every fit | "метки ... не пересекают границы splits". |
| V11 | G01 trailing 24 h stdev includes the bar ending at T (closed); ddof = 0. log RV uses the previous 48 volumes (current excluded) | Literal reading; recorded. |
| V12 | G01 B0/B1/X samples are identical by construction (valid row requires all 33 X inputs; B1 needs all 8 others for F anyway) | Spec. |
| V13 | Calibration bins = deciles of the fit's in-sample predictions (train edges), applied to OOS predictions | "границы на train". |
| V14 | H01 conditional estimate applies the current fit's q20 to all train-window observations | Spec §4. |
| V15 | Day-start equity = equity at the last known 1m close before 00:00 UTC (MTM if a position is open) | Only known prices. |
| V16 | Risk breach checked at 1m closes; exit at the next available 1m open; prices of the following minute are never used before its open | Spec §6. |
| V17 | Random baseline: G01 categorical draw per decision with the train-window in-sample X argmax>0 frequencies; H01–H03 independent Bernoulli per symbol with train signal frequency, first hit in BTC/ETH/SOL order. RNG = `default_rng([seed, family_index])`, seeds 0–99 | Approximate matching from train only; actual exposure mismatch reported. |
| V18 | Exposure-matched passive = EW B&H daily PnL × strategy time exposure (analytic) | Disclosed approximation. |
| V19 | Historical-test command is fail-closed: even with a valid owner-written approval it refuses, because this version does not download test data. A separate session is needed after approval | No agent-generated approvals. |
| V20 | Track C recorder: code and synthetic tests only. `smoke` refuses without `--i-am-authorized`. api/fapi/stream.binance.com were geo-restricted from this host in v0.1 (api.binance.com "restricted location"). No connection was attempted here | Spec §8: stop, do not bypass. |
| V21 | (post-smoke, 2026-11-24) `asof` uses `searchsorted` on bar-end index (same semantics: last closed bar ≤ T, NaN preserved) | Bug fix; no semantic change. |
| V22 | (post-smoke) v0.2 rounding = v0.1 rounding snapped to 10 decimals | Removes 1e-12 float artefacts that the reused ledger checker correctly flagged; no economic effect. |
| V23 | Diag wallets deplete under the spec's notional = min(50, cash); reported as a limitation, not changed | The spec defines the diag replay this way; per-signal expectancy is reported separately. |
| V24 | Interpretation rule applied to H04: an improvement achieved by a variant with zero or near-zero trades is reported as abstention, not edge | Spec §5: refusing to trade is not a success metric. |
| V25 | (QA addendum, 2026-11-24) The pre-registered diag replay depletes (notional = min(50, cash)) and acts as an implicit irreversible stop. G01/H01 primary-test effect sizes are therefore not edge estimates. Verdict directions are unchanged (per-signal net < 0) | QA requirements 3–4; reported, not patched. |
| V26 | `slippage_cost` in v0.2 (and v0.1) mixes adverse execution and tick/step rounding. The addendum decomposes them. v0.1 0-bps residual = rounding of stop/target trigger exits | QA requirement 6; documentation, no result change. |
| V27 | All-signal tables (all admissible decisions, gross labels, wallet-independent) committed as deterministic gzip under reports/v02/qa_addendum/ | QA requirement 2. |
| V28 | Methodology extensions (fixed-50 portfolio without depletion, per-signal execution layer, day-block pooled inference, unit-safe fit index) are pre-registered as separate diagnostic MH-v0.2-D1 (SPEC_DIAGNOSTIC_D1.md). It is not executed before owner confirmation, and only a 19-day technical smoke ran in scratch (numbers not used). Owner confirmed on 2026-11-25; executed on development and validation | QA requirement 9. |
