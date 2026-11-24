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
