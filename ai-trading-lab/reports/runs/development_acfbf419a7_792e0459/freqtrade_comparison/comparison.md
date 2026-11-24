# Freqtrade vs reference replay — development

Reference: `reports/runs/development_acfbf419a7_792e0459` scenario `signal_only_no_portfolio_stop` (Freqtrade has no equity-based daily/total limit). Freqtrade: offline markets (assumed filters), fee 0.00125/side, timeframe-detail 1m, stake 50, wallet 100; Freqtrade stops opening trades once free balance < stake (≈ −50 USDT).

| strategy | FT trades | ref trades | matched entries | only FT | only ref | entry px diff (median bps) | same exit time | FT net | ref net (signal-only) | matched FT net | matched ref net |
|---|---|---|---|---|---|---|---|---|---|---|---|
| E01-P | 395 | 759 | 374 | 21 | 385 | 0.0 | 0.5401 | -50.10 | -75.03 | -49.49 | -48.22 |
| E01-F | 338 | 334 | 333 | 5 | 1 | 0.0 | 0.6306 | -39.32 | -39.77 | -38.52 | -39.36 |
| E02-P | 438 | 667 | 364 | 74 | 303 | 0.0 | 0.4203 | -50.10 | -73.46 | -41.24 | -43.44 |
| E02-F | 478 | 544 | 406 | 72 | 138 | 0.0 | 0.4803 | -50.21 | -57.32 | -40.91 | -44.09 |

Exit pairs on matched entries (reference | Freqtrade), all strategies:

| pair | n | median exit time diff (min) | median exit price diff (bps) |
|---|---|---|---|
| stop|roi | 2 | 13.0 | 173.74 |
| stop|stop_loss | 507 | -1.0 | -2.499 |
| stop|time_exit | 28 | 22.5 | 39.121 |
| target|roi | 201 | 0.0 | 22.509 |
| target|stop_loss | 11 | 27.0 | -151.275 |
| target|time_exit | 68 | 14.0 | -31.176 |
| target_gap|time_exit | 1 | 27.0 | -21.635 |
| time_exit|time_exit | 659 | 0.0 | 0.0 |

Known causes (not resolved in favour of either engine):
1. Freqtrade `minimal_roi` is reached on fee-adjusted profit: the 0.9 % ROI needs ≈ +1.15 % price, so reference `target` exits often become Freqtrade `time_exit`/`stop_loss` and ROI exits are ≈ +22 bps higher.
2. Freqtrade stop = open_rate × 0.994 on the raw open (no slippage model); reference stop = slipped fill × 0.994, filled with −2.5 bps: ≈ −2.5 bps price difference; Freqtrade stamps the exit at the bar open (−1 min).
3. Freqtrade stops opening trades when free balance < 50 USDT stake; reference signal-only keeps trading with min(50, cash) — later trades exist only in the reference.
4. Different exits change which later signals are blocked by an open position/cooldown (path divergence).
5. Freqtrade charges 0.125 % fee per side instead of 0.10 % fee + 2.5 bps price adjustment.