# AI Trading Lab — research MVP v0.1

A reproducible local research setup for testing two pre-registered intraday hypotheses on Binance spot 1m data
(BTCUSDT, ETHUSDT, SOLUSDT):
**E01 Conditional Mean Reversion** and **E02 Conditional Momentum**, each in a price/volume-only variant (P) and a
taker-flow variant (F). They are compared with controls: cash, buy-and-hold, an adapted upstream Freqtrade
SampleStrategy, and 100-seed random entries.

* Virtual capital only (100 USDT per strategy wallet). **No live trading, no API keys, no orders.**
* Dry-run is not launched. The locked test (holdout) runs only through a separate approval-gated command.
* Results include negative outcomes. Nothing is tuned on the data.

Start with `STRATEGY_REGISTRY.md` (frozen rules), `DECISIONS.md` (all interpretation choices) and
`PROJECT_STATE.md` (status, results, limitations).

## Requirements

* Linux/macOS, Python 3.13 (tested 3.13.18), ~1 GB disk.
* Network access to `data.binance.vision` (public archives). `api.binance.com` is not required for research runs.

## Install

```bash
cd ai-trading-lab
python3.13 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock      # pinned: freqtrade 2026.10, pandas 3.1.1, numpy 2.5.5, pyarrow 26.0.1, pytest 9.2.0 ...
```

Docker (optional; the `Dockerfile` was written but **not built** in the development session because no Docker
daemon was available):

```bash
docker build -t ai-trading-lab .
docker run --rm -v $PWD/data:/app/data -v $PWD/reports:/app/reports ai-trading-lab validate-data
```

## Run (exact commands used)

```bash
python -m src.cli download --config configs/mvp.yaml      # 39 monthly archives + SHA256 check -> data/raw, data/manifest.json
python -m src.cli validate-data                            # parse, UTC/units, invariants, gaps, dups -> data/processed, data/qa.json, reports/data_qa.md
python -m src.cli test-signals --cuts 25                   # prefix-invariance + future-mutation check on real data (all strategies)
pytest -q                                                  # unit + integration tests
python -m src.cli backtest --split development --smoke-days 1 --seeds 5   # smoke (one day)
python -m src.cli backtest --split development             # full development
python -m src.cli backtest --split validation              # full validation
python -m src.cli report --split validation                # print latest validation report
python -m src.cli backtest --split test                    # -> REFUSED (exit 4): locked
python -m src.cli holdout --approval-file approvals/holdout.json   # separate gate; NOT run in v0.1
```

Every backtest writes `reports/runs/<split>_<code-hash>_<config-hash>/` containing:
`report.md`, `qa_report.md`, `metrics.json`, `manifest.json` (config/code/data/git hashes and output hashes),
`trades.csv|parquet` (all scenarios), `rejected_signals.csv`, `signals.csv`, `equity.parquet` (1m MTM) and
`equity_hourly.csv`, `random_benchmark.csv`, `event_study.csv`, `risk_events.csv`, `reconciliation.json`, and
`run_info.json` (wall-clock timestamp, the only non-deterministic file).
Re-running with the same inputs reproduces identical outputs. This is tested by `test_smoke_run_reproducible`
and recorded in `manifest.json.outputs_sha256`.

### Freqtrade (second engine, offline)

Freqtrade needs exchange market metadata at start-up, which it fetches from `api.binance.com`. That endpoint is
geo-restricted from the development host. For **offline backtests only**, `src.ftbridge.run_offline` supplies static
market metadata built from the assumed filters in `configs/mvp.yaml` (see DECISIONS D23). It sends no request to
Binance and does not change Freqtrade's source.

```bash
python -m src.cli ft-export      # dev+val OHLCV -> user_data/data/binance/*.feather, taker sidecar -> user_data/data/sidecar
python -m src.ftbridge.run_offline backtesting -c user_data/config_backtest.json \
    --strategy-list MvpE01P MvpE01F MvpE02P MvpE02F --timerange 20251101-20260608 \
    --timeframe-detail 1m --fee 0.00125 --export trades --backtest-directory user_data/backtest_results/development
python -m src.cli ft-compare --split development --ft-dir user_data/backtest_results/development
python -m src.ftbridge.run_offline lookahead-analysis -c user_data/config_backtest.json --strategy MvpE01P \
    --timerange 20251101-20260101 --fee 0.00125 --minimum-trade-amount 10 --targeted-trade-amount 30
python -m src.ftbridge.run_offline recursive-analysis -c user_data/config_backtest.json --strategy MvpE01P \
    --timerange 20251101-20251201 --startup-candle 300 400 600
```

With unrestricted Binance access, plain `freqtrade backtesting ...` works with the same config.
`user_data/config_dryrun_template.json` is a **template only**: dry-run is not approved, and F-variants refuse to run
in dry-run because there is no live sidecar feed.

## Layout

```
configs/mvp.yaml               pre-registered experiment configuration (+ regime_thresholds.json fixed on development)
src/data/                      download (checksums), parse (ms/us -> UTC), validate, aggregate 1m->5m, time-bounded store
src/features/core.py           r5, r15, z5, z15, RV, I, regime inputs (past-only)
src/signals/                   E01/E02 rules, B01 (upstream SampleStrategy entries), B03 random, prefix checks
src/evaluation/                replay engine, metrics, bootstrap/Holm, event study, ledger reconciliation, reports, pipeline
src/ftbridge/                  Freqtrade export, sidecar join, offline runner, comparison
src/live/kline_stream.py       closed-kline processor for a future dry-run feed (no network code)
user_data/strategies/          Freqtrade wrappers MvpE01P/F, MvpE02P/F (version mvp-0.1)
tests/                         unit + integration tests
reports/                       data QA, run reports (parquet ignored by git), Freqtrade analyses
```

Raw/processed data, Freqtrade data/results, databases and secrets are ignored by git (`.gitignore`).
