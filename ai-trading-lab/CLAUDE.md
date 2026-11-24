# CLAUDE.md — working rules for AI assistants in this repository

## Hard rules
1. **No live trading.** Never enable live mode, request or store API keys, create exchange accounts, or send orders.
   `configs/*.yaml` with `mode: live` or `dry_run: false` are rejected by `src/config.py`.
2. **No long dry-run/demo** without separate written approval and launch instructions from the project owner.
3. **Locked test (holdout, 2026-08-20 → 2026-11-01)** is run only via `python -m src.cli holdout --approval-file ...`
   after explicit approval. Do not load, plot, or summarise holdout prices or returns in any other way. If the holdout has
   been used (`reports/HOLDOUT_USED.json`), any new test needs later data.
4. **Do not change rules or parameters to improve results.** `configs/mvp.yaml` and `STRATEGY_REGISTRY.md` are
   pre-registered. Any change requires a new version or experiment ID plus entries in `DECISIONS.md` and `EXPERIMENT_LOG.md`.
   No hyperopt, threshold search, or cherry-picking of seeds, windows, or assets.
5. **Never invent results.** Report only what the code produced, including negative or zero-trade outcomes.
   No placeholder or demo numbers.
6. Do not bypass access restrictions, such as geo-blocked exchange endpoints. If a market or endpoint is unavailable,
   stop and document it.
7. Never commit raw or processed data, databases, or secrets (see `.gitignore`).

## Workflow
* Tests: `pytest -q`. They must pass before any backtest whose results are reported.
* Data: `python -m src.cli download && python -m src.cli validate-data`.
* Backtests: `python -m src.cli backtest --split development|validation`. Outputs go to `reports/runs/<split>_<code>_<cfg>/`.
* The reference engine is `src/evaluation/engine.py`. Freqtrade is a cross-check. If they disagree, explain the
  cause and do not pick the more favourable result.
* Update `PROJECT_STATE.md` and `EXPERIMENT_LOG.md` after every meaningful run.
