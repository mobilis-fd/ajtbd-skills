# Decisions (MVP v0.1)

Each entry: decision, reason, consequence. Decisions D01–D22 were taken **before** any full development backtest.

| # | Decision | Reason / consequence |
|---|---|---|
| D01 | Project lives in `ai-trading-lab/` inside the session git repository (branch `ccr-481f4ca9-6sjk8p`) instead of a separate repo | Only this repository can be pushed from the cloud session; extract later with `git subtree split -P ai-trading-lab`. |
| D02 | Python 3.13 venv, `requirements.lock` = `pip freeze`; Freqtrade 2026.10 (GPLv3), pandas 3.1.1, numpy 2.5.5, pyarrow 26.0.1, pytest 9.2.0, TA-Lib 0.8.3, technical 1.7.0 (GPLv3) | Pinned, reproducible. Freqtrade/technical are GPLv3: our wrappers import them; keep the project GPL-compatible if distributed. |
| D03 | Reference engine = own replay (`src/evaluation/engine.py`); Freqtrade used as second engine for cross-check and future dry-run | Spec requires market-trigger stops with gap-to-open, adverse slippage, equity-based daily/total limits and conservative rounding, which Freqtrade backtesting does not model identically. |
| D04 | Monthly Binance archives (2025-10 … 2026-10), SHA256 verified against `.CHECKSUM` | 2025-10 provides the 7-day warmup (from 2025-10-25). |
| D05 | Timestamp unit detected per value by magnitude (ms ∈ [1e12,1e13), µs ∈ [1e15,1e16)); anything else rejected | Spot archives are µs since 2025; robust to mixed files. |
| D06 | Exact duplicate rows dropped; conflicting duplicates dropped entirely; invalid rows dropped → become gaps | Never repair or invent candles. (Observed: 0 of each.) |
| D07 | Strict windows: any missing candle in a feature window ⇒ NaN ⇒ no signal | Spec: "при пропуске ... сигнал отсутствует". |
| D08 | z15 uses the 288 previous r15 values sampled every 5m (overlapping) | Literal reading of "предыдущих 288 соответствующих доходностей". |
| D09 | Signal candle must lie inside the segment (open_time ≥ segment start); decision at its close; entry at the 1m bar whose open_time = close_time(t) (+60 s in the delay stress). If that bar is missing ⇒ reject (`missing_entry_bar`), no search forward | Conservative; data are complete so this never triggered. |
| D10 | Stop/target triggers are computed from the actual (slipped, tick-rounded) fill; stop/target fill = trigger × (1 − slip), stop gap fill = open × (1 − slip), target gap fill = trigger × (1 − slip) | Market-trigger model; slippage applied once per side. |
| D11 | Intrabar exit time = end of that minute; cooldown counts from it. Open-based exits at the open | Conservative cooldown. |
| D12 | Fees in quote currency on actual notional each side | Simplification: Binance deducts buy fees in base asset unless BNB is used; effect ≈ 1 fee on rounding. |
| D13 | Exchange filters **assumed** (tick 0.01; step BTC 1e-5, ETH 1e-4, SOL 1e-3; minNotional 5) | `api.binance.com/api/v3/exchangeInfo` answered "Service unavailable from a restricted location"; not circumvented. Sensitivity: lot step ×10. Must be verified before any demo. |
| D14 | Risk checks: mark-to-market at each 1m close while in position, and on realised equity after each exit. Breach ⇒ exit at next available 1m open, pause (daily) / stop (total). Day-start equity = equity at 00:00 UTC (MTM at the 00:00 bar open if in position) | Spec section 4. Intrabar MTM lows are not used for the portfolio limit (the per-trade stop covers intrabar moves). |
| D15 | Segment boundary: open position closed at the last available 1m close before segment end (`boundary_exit`), costs applied; each segment starts with fresh 100 USDT | No trades cross segments. |
| D16 | Cost sensitivity 0/10/40 bps RT split 80:20 fee:slip (0/0, 4/1, 16/4 bps per side) | Proportional to main 10/2.5. Hypothetical. |
| D17 | Break-even cost = Σ gross PnL / Σ entry notional of the zero-cost replay (fixed fills) | "на фиксированных сигналах". |
| D18 | Regime: sign of trailing 24h log return × trailing 24h std(r5) vs **development median per symbol** (written once to `configs/regime_thresholds.json`) | Past-only; thresholds fixed on development. |
| D19 | Bootstrap: moving-block on daily PnL (zero-PnL days included), 2000 reps, seed 20261125, blocks 7 (3/14 sensitivity); `insufficient_data` if days/block < 5; one-sided p for mean>0; Holm over 4 candidates | Preliminary only. |
| D20 | B01 = upstream `SampleStrategy` entries computed by importing the unmodified template; hold variants 30 and 60 min | Spec allows SampleStrategy adaptation; both holds to match E01/E02. |
| D21 | B03 random frequency = raw signal count per symbol of the target in the same segment | Spec: "частота/пары и длительность сопоставимы". |
| D22 | Locked test reachable only via `holdout --approval-file` (statement + current code/config sha256), creates `reports/HOLDOUT_USED.json`; split loader refuses `test` | Holdout not run in this task. |
| D23 | Freqtrade start-up needs exchange markets from api.binance.com (geo-restricted). For OFFLINE backtests only, `src/ftbridge/run_offline.py` injects static market metadata built from the assumed filters (runtime patch, no Freqtrade source change, no Binance request) | Restriction not bypassed: nothing is fetched from Binance; results labelled offline. Not usable for dry-run. |
| D24 | Freqtrade wrappers: stoploss −0.006, minimal_roi 0.009, time exit via `custom_exit` (requires `use_exit_signal=True`, exit_long always 0), fee 0.00125 per side (= fee + slip; Freqtrade has no slippage model) | Freqtrade ROI is measured on fee-adjusted profit and stops fill at the stop price — expected deviations are documented in the comparison, not "fixed" toward either result. |
| D25 | Holdout inspection incident: during archive-format inspection the first 3 raw 1m rows of BTCUSDT 2026-10-01 (locked test period) were printed. No statistics were computed | Logged for transparency; no influence on rules (already frozen in the spec). |
