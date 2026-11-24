# Strategy registry — MVP v0.1 (pre-registered)

Status: **frozen before any full backtest** (commit tagged in `EXPERIMENT_LOG.md`). Parameters are hypotheses for a first
experiment, not trading recommendations. Changing anything below requires a new strategy version and a new
experiment ID. No hyperopt, no threshold search, no cherry-picking.

Machine-readable source of truth: `configs/mvp.yaml`. Code: `src/features/core.py`, `src/signals/rules.py`,
`src/evaluation/engine.py`. Freqtrade wrappers: `user_data/strategies/mvp_strategies.py` (version `mvp-0.1`).

## Common definitions

`t` = last fully closed 5m candle (aggregated from 5 complete 1m candles; incomplete buckets are dropped and remain
gaps). `C,O,H,L,V` = close, open, high, low, base volume.

| feature | definition |
|---|---|
| r5(t) | ln(C(t)/C(t-1)) |
| r15(t) | ln(C(t)/C(t-3)) |
| z5(t) | (r5(t) − mean(r5[t-288..t-1])) / std_ddof0(r5[t-288..t-1]); current value excluded |
| z15(t) | same on the 5m-sampled (overlapping) r15 series, 288 previous values |
| RV(t) | V(t) / median(V[t-48..t-1]) |
| I(t) | 2·taker_buy_base(t)/V(t) − 1 (5m value from summed 1m volumes, never a mean of 1m I) |

Zero denominator, any missing candle inside a window or insufficient history ⇒ feature NaN ⇒ no signal.

## Candidates (4)

| id | version | rules (all must hold) | hold |
|---|---|---|---|
| E01-P | 0.1 | z5(t-1) ≤ −2; r5(t-1) ≤ −0.004; r5(t) > 0; C(t) > O(t); RV(t-1) ≥ 1.5 | 30 min |
| E01-F | 0.1 | E01-P and I(t-1) ≤ −0.20 and I(t) ≥ 0 | 30 min |
| E02-P | 0.1 | r15(t) ≥ 0.005; z15(t) ≥ 2; C(t) > max(H[t-12..t-1]); RV(t) ≥ 1.5 | 60 min |
| E02-F | 0.1 | E02-P and I(t) ≥ 0.20 | 60 min |

All: long spot only, entry at the 1m open at close_time(t) (next available minute after the signal candle closes)
with +2.5 bps adverse price adjustment; stop −0.6 % / target +0.9 % from the actual fill; time exit at the 1m open when
the hold expires (before that bar's range); stop first on same-minute conflict; gap through stop fills at the open,
gap through target at the trigger; 5 min cooldown; one position per strategy wallet; BTC > ETH > SOL priority.

## Controls

| id | description |
|---|---|
| B00 | Cash, 0 return before external costs |
| B01-h30 / B01-h60 | **Adaptation** of upstream Freqtrade `SampleStrategy` (freqtrade 2026.10, file `freqtrade/templates/sample_strategy.py`, sha256 `18d48d64b955dc9bd1b43f59115c16f2002a881c62c2851ceca64569a6f8651c`): its unmodified entry signal (RSI crosses above 30, TEMA ≤ BB middle, TEMA rising, volume > 0) with the unified exit/risk/cost rules, hold 30 or 60 min |
| B02-BH-{SYM} | One 50 USDT buy at segment start (with costs), rest cash, mark-to-market, sold at segment end. No stop / risk limits — different risk and exposure |
| B03~{target} | Random entries: 100 fixed seeds (SeedSequence([20261125, target, seed, symbol])), per symbol the same number of 5m decision times as the target's raw signals in that segment, same hold, same exit/risk/cost rules. Conditional benchmark, not a strategy |

## Dry-run availability

| id | Freqtrade backtest | Freqtrade dry-run |
|---|---|---|
| E01-P, E02-P | yes (offline markets) | technically possible, **not approved** |
| E01-F, E02-F | yes, via historical sidecar join (symbol, close_time) | **unavailable**: no live sidecar feed; strategy raises in dry_run/live |
