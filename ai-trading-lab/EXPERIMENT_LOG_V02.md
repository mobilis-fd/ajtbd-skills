# Experiment log — MH-v0.2

| # | when (UTC) | what | result / notes |
|---|---|---|---|
| X01 | 2026-11-24 | Branch from v0.1 handoff 789683e; v0.1 tests 42/42 on branch | ok |
| X02 | 2026-11-24 | Listing probe: SOLUSDT archives start 2020-08; others available 2020-07 | coverage rule ⇒ first fit 2021-10-01 |
| X03 | 2026-11-24 | `download` dev+val: 477/477 archives (9 × 2020-08…2024-12) SHA256 ok, read-only | data/v02/manifest.json |
| X04 | 2026-11-24 | `validate-data --split validation` (horizon 2025-01-01): 0 dup/OHLC/taker violations; 10–11 exchange-wide gaps (1423–1425 min) per symbol; 5–6 truncated pre-outage candles dropped per symbol; all files ms | reports/v02/data_qa_validation.md |
| X05 | 2026-11-24 | Futures archive inventory (schema only, 2020–2022 files): fundingRate monthly, metrics daily, mark/premium klines | docs in PROJECT_STATE_V02 |
| X06 | 2026-11-24 | **Pre-registration commit** (spec, config, code, tests) before any v0.2 backtest | see git log |

Previously viewed intervals in this project: v0.1 2025-10-25 → 2026-08-20 (plus 3 raw rows of 2026-10-01).
The assistant's general training knowledge includes public crypto market history of 2021–2025 (e.g. the 2022 bear
market). The test period 2025-01 → 2025-11 is therefore not "unknown"; no project statistic of it was computed.
| X07 | 2026-11-24 | Smoke development 20 d: crash in `asof` (duplicate T) → fixed; ledger checker flagged float artefact in zero-slippage fills → v0.2 rounding snapped to 1e-10 | no rule/parameter change |
| X08 | 2026-11-24 | Real-data end-to-end prefix-invariance test (G01/H01/H02/H03 panels, truncation 2022-01-15 vs 2022-03-01): identical | tests/research/test_integration_v02.py |
| X09 | 2026-11-24 | Development run (pre-commit, dirty tree) → moved to runs_superseded/ | identical outputs to X11 (12/12 files) |
| X10 | 2026-11-24 | Commit 0ad6beb. Its message mentions "report formatting" but that edit was in a blocked command and NOT applied; applied later (X13) | documentation inaccuracy recorded |
| X11 | 2026-11-24 | Final development run (code a5bca96b79, git 0ad6beb) | all primary tests non-significant; G01-X worse than B1; H01/H02 net < 0; H03 net < 0 |
| X12 | 2026-11-24 | Final validation run (same code) | only H01-H04 rejects H0, and it is an abstention artefact (H01-c: 0 trades); H03 +35.1 diag but below random median and exposure-matched B&H; others negative |
| X13 | 2026-11-24 | Report formatting fix + `report --rerender` from unchanged metrics.json | presentation only |
| X14 | 2026-11-24 | Historical test, recorder smoke/pilot, Tardis samples: NOT run | awaiting audit / approvals |

No rule, parameter, threshold, hold, split or seed was changed after any v0.2 result was seen.
| X15 | 2026-11-24 | Read FINAL_AUDIT_V01.md (branch ccr-…, 73e6d89). QA addendum measurements (read-only): clean clone @0ad6beb reproduces code hash a5bca96b79; no git-ignored sources; config/spec unchanged since a5b47c7; diag wallets deplete (G01 13–19 %, H01 36–56 % of OOS window); cost decomposition; v0.1 0-bps residual explained; signal dependence | reports/v02/QA_ADDENDUM_V02.md |
| X16 | 2026-11-24 | QA script bug found and fixed before use: minute conversion assumed ns while indices are µs (pipeline itself verified unit-consistent) | audit/qa_addendum_v02.py |
| X17 | 2026-11-24 | MH-v0.2-D1 specified + implemented + tested (75 tests pass). 19-day technical smoke in scratch only (crash check; numbers not used). **D1 not executed on development/validation** pending owner confirmation | SPEC_DIAGNOSTIC_D1.md |
| X18 | 2026-11-25 | Owner confirmed D1. `diag-d1 --confirmed` on development and validation at clean commit 295ba7c (code 8ea5177c03), 4 min | reports/v02/diagnostics/D1/*; no v0.2 verdict changes (QA addendum §E) |
| X19 | 2026-11-25 | Final audit package: `audit/build_final_audit_v02.py` → FINAL_AUDIT_V02.md from committed outputs only (no backtest/refit/download). Audit-derived statistics (B0−B1/B0−X MSE day-block bootstrap, H04 kept-signal quality, H03 PnL per exposure) from committed predictions/signals/trades. Corrections made while verifying the draft: H02 development was also distorted (notional shrink), CI count 15/18, H04/H03 wording | release branch release/multi-horizon-v0.2 |
| X20 | 2026-11-25 | Archive determinism check: `git archive <tree>:path` produced different SHA256 on two builds (current mtime). Switched to `git archive <commit> ai-trading-lab` (commit time); release branch fast-forwarded to the corrected package commit | no result change |
