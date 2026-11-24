# Project state — MVP v0.1 (as of 2026-11-24)

**Status:** implementation complete; development and validation evaluated; **locked test NOT run**; dry-run NOT
started; live trading not implemented. All four pre-registered candidates are **net negative after the assumed costs
on both development and validation**. No candidate qualifies as a demo candidate.

Generated numbers: `reports/SUMMARY_development_validation.md`. Full reports:
`reports/runs/development_2bff6fcca7_792e0459/report.md`, `reports/runs/validation_2bff6fcca7_792e0459/report.md`
(+ `qa_report.md`, `freqtrade_comparison/comparison.md` in each directory). All runs reference git commit
`803db3a` (clean), config sha256 `792e0459…`.

## Results (USDT, virtual 100 per wallet, main = 25 bps RT, portfolio limits on)

| strategy | dev net (main) | dev net signal-only | dev break-even RT bps | val net (main) | val net signal-only | val break-even RT bps |
|---|---|---|---|---|---|---|
| E01-P | −10.11 (total stop) | −75.03 (759 tr.) | 3.20 | −10.09 (total stop) | −13.93 (144 tr.) | 6.05 |
| E01-F | −10.07 (total stop) | −39.77 (334 tr.) | 1.05 | −7.39 (66 tr.) | −7.39 | 2.25 |
| E02-P | −10.01 (total stop) | −73.46 (667 tr.) | 0.84 | −10.06 (total stop) | −19.11 (190 tr.) | 3.97 |
| E02-F | −10.05 (total stop) | −57.32 (544 tr.) | 3.62 | −10.08 (total stop) | −13.26 (150 tr.) | 6.22 |
| B01-h30 / h60 | −10.07 / −10.25 | −83.80 / −80.17 | <0 | −10.03 / −10.13 | −32.98 / −29.80 | <0 |
| B02 buy&hold BTC/ETH/SOL ($50) | −20.92 / −27.92 / −32.32 | | | +4.55 / +16.44 / +14.03 | | |

Interpretation, within the limits of this test:
* Gross edge before costs is small and positive for E01/E02 in signal-only replays, but break-even all-in costs are
  1–6 bps round trip, far below the assumed 25 bps. At 10 bps RT, all candidates are still negative on validation.
* With limits on, all wallets except E01-F on validation hit the 10 USDT total stop. "Main" PnL ≈ −10 is therefore the
  limit, not an estimate of the loss rate. Random frequency-matched entries hit the same stop, so B03 comparisons in
  the main scenario carry little information.
* Bootstrap (7-day blocks): P(mean daily PnL ≤ 0) = 1.00 for every candidate on both splits. Holm-adjusted p = 1.0.
  No candidate is significant, and none is declared a winner.
* Event study (validation): mean forward returns after signals are +6 to +9 bps at 15–30 min vs a +0.3 to +0.6 bps
  background. The naive t is about 2–3 but overstates significance because signals cluster in time across symbols.
  Development shows −2 to +4 bps. The effect is inconsistent across splits and an order of magnitude below costs.
* The F (taker-flow) filter reduces the number of trades, and losses shrink roughly in proportion. Its per-trade
  expectancy is not better than P's in a stable way.

## Verification done
* 42 automated tests pass (`pytest -q`): parsing ms/µs, 5m aggregation, alignment, gaps/duplicates, zero volume,
  past-only rolling (prefix and future mutation), sidecar join without leakage, entry after close, stop/target
  conflict, gaps, time exit, cooldown, simultaneous signals, both-side fees, precision/minNotional, no overdraft,
  ledger reconciliation, daily pause/reset, total stop, restart from state, split boundary, seed reproducibility,
  zero edge + costs ⇒ no profit, stream closed-only/dedup/gap/stale fail-closed, holdout/live gates, reproducible smoke run.
* Real-data look-ahead check (`test-signals`): 75/75 cuts pass (E01/E02 features and signals, B01).
* Freqtrade `lookahead-analysis`: no bias for MvpE01P/F, MvpE02P/F (30 signals each, 2025-11-01 → 2026-01-01).
  `recursive-analysis`: only floating-point-level (<0.0005 %) differences in z5/z15 between startup 300/400/600.
* Ledger reconciliation (independent PnL recomputation, cash chain, tick/step, rounding direction): OK for all main runs.
  Manual step-by-step checks with raw 1m bars are in each `qa_report.md`.
* Reproducibility: a full validation rerun gives byte-identical outputs (`manifest.json.outputs_sha256`).
* Freqtrade vs reference: 100 % of matched entries at identical price. Time exits identical. Differences are explained
  by Freqtrade's fee-adjusted ROI (+22 bps), its stop on the raw open (−2.5 bps), its −50 USDT stake exhaustion, and
  path divergence (see `freqtrade_comparison/comparison.md`).

## Limitations
1. **Exchange filters assumed.** `api.binance.com` (exchangeInfo, fee docs) is geo-restricted from this host and was
   not bypassed. tick/step/minNotional are assumptions; the ×10 step sensitivity changes results only marginally.
2. Costs are a working assumption (10 bps fee + 2.5 bps price adjustment). The real spread or slippage cannot be
   observed from OHLCV. There are no queue or partial-fill models.
3. Fees are charged in quote currency (Binance deducts buy fees in base unless BNB is used).
4. Portfolio limit checks use 1m closes (not intrabar lows). Exceedances on the forced exit are logged (`risk_events.csv`).
5. Freqtrade ran with offline static markets (D23). Its ROI and stop semantics differ from the spec (D24), so it is a
   cross-check, not the reference.
6. The data had no gaps, so the uncertain-gap and conservative-close code paths are covered only by unit tests.
7. One split per period. The validation period (73 days) is short. The bootstrap is preliminary, and signals cluster.
8. Docker image not built (no daemon in the session). The live WebSocket/REST adapter is not implemented; only the
   message processor exists and is tested.
9. Incident D25: 3 raw 1m rows of 2026-10-01 (holdout) were printed during format inspection. No statistics were computed.
10. Rolling-window floating-point results depend slightly on the series start (recursive-analysis). This only matters at
    exact threshold ties.

## Not done / next steps (require owner decisions)
* Holdout: **not run.** Running it makes little sense for a go/no-go decision, since validation is negative for all
  candidates. If wanted for completeness: create `approvals/holdout.json` with the current code and config hashes,
  then `python -m src.cli holdout --approval-file approvals/holdout.json`.
* Demo/dry-run: not justified by the results; not started.
* Possible new pre-registered experiments (new IDs, evaluated on later data only): cost-aware variants (fewer, larger
  moves; maker-only research needs order-book data), measuring the real spread from public bookTicker/aggTrades on an
  allowed host, verifying exchangeInfo filters, and per-symbol cost estimates.
