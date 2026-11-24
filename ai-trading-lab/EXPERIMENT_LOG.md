# Experiment log

All times UTC. Hashes refer to `configs/mvp.yaml` (config), `src.config.code_hash()` (code) and git commits.

| # | when | what | result / notes |
|---|---|---|---|
| L01 | 2026-11-24 | Environment: Python 3.13 venv, freqtrade 2026.10 + deps (`requirements.lock`) | ok |
| L02 | 2026-11-24 | Network: data.binance.vision allowed (new personal cloud environment); api.binance.com geo-restricted ("restricted location") | exchangeInfo unavailable → filters assumed (D13) |
| L03 | 2026-11-24 | Archive format inspection printed 3 raw rows of BTCUSDT 2026-10-01 (locked test period) | incident logged (D25); no statistics computed |
| L04 | 2026-11-24 | `download`: 39/39 monthly archives (3 symbols × 2025-10…2026-10), SHA256 verified | data/manifest.json |
| L05 | 2026-11-24 | `validate-data`: 535,680 1m rows/symbol, 0 missing, 0 duplicates, 0 invariant violations, all µs | reports/data_qa.md |
| L06 | 2026-11-24 | Freqtrade offline start-up check: E01-P 2025-11-01..03 (development) — used only to verify that the engine runs and custom_exit works (fixed `use_exit_signal`) | no parameter changes |
| L07 | 2026-11-24 | Regime thresholds computed from development features (no strategy results involved) | configs/regime_thresholds.json |
| L08 | 2026-11-24 | **Pre-registration commit** of configs, code, tests, registry and decisions before any full backtest | see git log |
