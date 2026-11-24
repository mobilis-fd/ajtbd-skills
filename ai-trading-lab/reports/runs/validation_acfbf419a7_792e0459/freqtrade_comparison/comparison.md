# Freqtrade vs reference replay — validation

Reference: `reports/runs/validation_acfbf419a7_792e0459` scenario `signal_only_no_portfolio_stop` (Freqtrade has no equity-based daily/total limit). Freqtrade: offline markets (assumed filters), fee 0.00125/side, timeframe-detail 1m, stake 50, wallet 100; Freqtrade stops opening trades once free balance < stake (≈ −50 USDT).

| strategy | FT trades | ref trades | matched entries | only FT | only ref | entry px diff (median bps) | same exit time | FT net | ref net (signal-only) | matched FT net | matched ref net |
|---|---|---|---|---|---|---|---|---|---|---|---|
| E01-P | 146 | 144 | 143 | 3 | 1 | 0.0 | 0.7832 | -13.53 | -13.93 | -13.01 | -13.97 |
| E01-F | 67 | 66 | 66 | 1 | 0 | 0.0 | 0.7727 | -7.42 | -7.39 | -7.33 | -7.39 |
| E02-P | 210 | 190 | 176 | 34 | 14 | 0.0 | 0.5625 | -18.64 | -19.11 | -15.59 | -17.09 |
| E02-F | 163 | 150 | 145 | 18 | 5 | 0.0 | 0.5793 | -11.88 | -13.26 | -11.19 | -12.53 |

Exit pairs on matched entries (reference | Freqtrade), all strategies:

| pair | n | median exit time diff (min) | median exit price diff (bps) |
|---|---|---|---|
| stop|stop_loss | 115 | -1.0 | -2.499 |
| stop|time_exit | 3 | 4.0 | 15.153 |
| target|roi | 66 | 1.0 | 22.502 |
| target|stop_loss | 2 | 33.0 | -151.123 |
| target|time_exit | 21 | 19.0 | -13.986 |
| time_exit|time_exit | 323 | 0.0 | 0.0 |

Known causes (not resolved in favour of either engine):
1. Freqtrade `minimal_roi` is reached on fee-adjusted profit: the 0.9 % ROI needs ≈ +1.15 % price, so reference `target` exits often become Freqtrade `time_exit`/`stop_loss` and ROI exits are ≈ +22 bps higher.
2. Freqtrade stop = open_rate × 0.994 on the raw open (no slippage model); reference stop = slipped fill × 0.994, filled with −2.5 bps: ≈ −2.5 bps price difference; Freqtrade stamps the exit at the bar open (−1 min).
3. Freqtrade stops opening trades when free balance < 50 USDT stake; reference signal-only keeps trading with min(50, cash) — later trades exist only in the reference.
4. Different exits change which later signals are blocked by an open position/cooldown (path divergence).
5. Freqtrade charges 0.125 % fee per side instead of 0.10 % fee + 2.5 bps price adjustment.