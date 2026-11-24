# AI Trading Lab — Multi-Horizon Research v0.2 (branch `research/multi-horizon-v02`)

Independent of MVP v0.1, whose files are unchanged. Read `SPEC_MULTI_HORIZON_V02.md` (pre-registered design),
`DECISIONS_V02.md`, `EXPERIMENT_LOG_V02.md` and `PROJECT_STATE_V02.md` (results, QA, limitations, NOT RUN list).

```bash
pip install -r requirements-v02.lock          # adds scikit-learn 1.9.1, statsmodels 0.15.0
python -m src.research.cli download --split development    # 2020-08..2022-12, 9 assets, SHA256, read-only raw
python -m src.research.cli download --split validation     # 2021-12..2024-12
python -m src.research.cli validate-data --split validation  # processed 1m + 30m/1h/4h/1d bars, data QA
pytest -q                                                   # 71 tests (v0.1 + v0.2 + recorder)
python -m src.research.cli run --split development --smoke-days 20 --seeds 3
python -m src.research.cli run --split development          # ~2 min
python -m src.research.cli run --split validation           # ~3 min
python -m src.research.cli report --split validation [--rerender]
python -m src.research.cli run --split test                 # REFUSED (exit 4)
python -m src.research.cli historical-test --approval-file F # fail-closed (exit 5); not run
python -m src.collector.cli smoke --duration 900            # REFUSED without --i-am-authorized; run only on your machine after approval
```
Outputs: `reports/v02/runs/<split>_<code>_<config>/` (parquet files are git-ignored; CSV/JSON/MD committed).

