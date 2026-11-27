# AI Trading Lab — Equity Alpha Screening v0.3-pre

Exploratory event study, not an executable trading bot. This package does not contact a broker, download quotes, submit orders, or read the crypto MVP data. No strategy is declared profitable. All dates are historical exploratory periods, not untouched holdouts.

## Inputs and provenance

Provide `sessions.csv` with one `date` column (ISO YYYY-MM-DD, NYSE regular sessions, including early closes), and `SPY.csv`, `IEF.csv`, `TLT.csv` with `date,adj_open,adj_close`. Include every session from December 2002 through at least 2026-11-05. Use split- and dividend-adjusted open and close consistently; if using unadjusted OHLC plus adjusted close, apply the same daily adjustment ratio to both open and close. Check corporate actions against a second source. Save raw files, provider, download timestamp, adjustment convention, license/terms and an independently verified NYSE calendar. Do not silently fill gaps or substitute instruments. Yahoo/yfinance is one possible research source, subject to its terms. No live price feed or paid subscription required. The program checks alignment, ordering, completeness relative to the supplied calendar and positive finite prices; it cannot verify that the supplied calendar, prices or adjustments themselves are correct.

## Run

Python 3 with numpy and pandas (record exact versions in the run log). From the extracted directory:

```
python equity_screen.py --self-test
python equity_screen.py --data ./data --out ./reports/equity_screen_run01
```

Commit the untouched script, input hashes and research protocol before looking at results. Use a new output directory for each run. No automatic parameter selection.

## Fixed candidates

- EQ01 (previously SA01): SPY/IEF, choose the lower month-to-date total return measured from prior month-end close to the close preceding the last five sessions. Buy at the next session open, exit at last session close. Ties choose SPY. Compare against a fixed equal-weight basket of both instruments over the same dates. This is a long-only proxy, not replication of the institutional futures long-short strategy. Relative laggard selection is not a measurement of actual fund orders.
- EQ02 (previously SA02): SPY, buy at last session open, exit at third session close of the following month. Compare with the average of all four-session windows beginning in the anchor month. This is an executable daily-bar approximation, not the classical close-to-close effect.
- EQ03 (previously Treasury Month-End SA03): TLT, buy at the first of the last five sessions, exit at month-end close. Compare with all five-session windows wholly within the month. Control windows overlap and can include the event; inference uses monthly paired differences, not the individual windows as independent draws.

Use dates known from the exchange's announced schedule; the historical realized calendar is an approximation, potentially biased around unscheduled closures. Exclude transition months and events spanning period boundaries. Fixed periods: T3 2003–2016, T2 Oct 2017–Apr 2024, T1 Jun 2024–Oct 2026. These labels are regime proxies; transition months are deliberately omitted for clean comparisons. The output event CSV includes exploratory rows outside summary periods, which must not be pooled into the primary comparison. No post-hoc search for a best window, ETF or threshold.

## Interpretation

Event return = adjusted exit close / adjusted entry open − 1. Report gross, control, paired difference, break-even and net at 0/5/10/25/40 bps round trip (half charged on entry and half on modeled exit value). Adjusted total return is a proxy for exit notional when dividends occur; exact cash dividends and execution fees are deferred to portfolio validation. Cash baseline zero nominal return is implicit; include risk-free cash return, matched exposure, drawdowns, fractional share and broker fees, tax and FX conversion in a later portfolio stage. No wallet depletion, no risk stop in this stage. Do not infer annual ROI from event means alone.

Use paired circular monthly block bootstrap (4000 replicates, blocks 3/6/12 months; 6 primary, fixed seed). No inference for fewer than max(24, 2×block) events; even above this cutoff statistical power is not assured. Holm adjustment across estimable primary comparisons in the nine hypothesis-regime cells. Bootstrap assumes approximate within-regime stationarity and weak dependence, so reported p-values/intervals are descriptive, not proof of a prospective edge. Do not treat regime comparisons as causal; other market conditions changed simultaneously.

Gate for follow-up: positive gross, positive net under plausible costs, economically material positive paired difference and no major QA issues. If estimates are weak or uncertain, classify as inconclusive, not a winner. Only then consider portfolio replay and prospective validation; no automatic approval for trading. Costs are scenarios, not verified broker quotes.

## Status

Synthetic self-test passed: flat prices generate zero gross and losses equal to modeled costs, four-session month crossing, future mutation does not change prior EQ01 selection, constant bootstrap, split summaries. No historical dataset was available in the authoring environment; no real-market run, no independent code audit. This is a compact preliminary screen, not the full v0.3 specification. The historical calendar and data provenance still require verification. Do not change frozen v0.1/v0.2 branches or read their holdouts.

## Sources for rationale

- Harvey, Mazzoleni, Melone, The Unintended Consequences of Rebalancing: https://www.nber.org/papers/w33554
- Kayacetin, Infrequent rebalancing, risk deferral, and equity returns at the turn of the month: https://www.sciencedirect.com/science/article/pii/S1042443126000259
- The disappearing turn-of-month effect: https://www.sciencedirect.com/science/article/abs/pii/S1544612324014909
- NYSE calendars: https://www.nyse.com/trade/hours-calendars
