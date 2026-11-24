# Backtest report — validation

Experiment `MVP-v0.1-E01E02`; segment `[2026-06-08 00:00:00+00:00, 2026-08-20 00:00:00+00:00)` UTC.
Config sha256 `792e04593f9a8de8…`, code sha256 `acfbf419a708f106…`, git `2036eb977e4c7a61ecb25844d8e55bd90b5fee49`.

Research replay with virtual capital (100 USDT per strategy wallet). No real orders. Results include negative outcomes; nothing was tuned on these data.
Cost model (main): fee 10 bps/side + adverse price adjustment 2.5 bps/side = 25 bps round trip (working assumption, not the user's tariff; real spread unknown on OHLCV).

## 1. Main scenario (portfolio risk limits ON)

| strategy | raw signals | trades | net PnL | gross PnL | fees | slippage | return % | win rate | expectancy | PF | max DD | exposure % | turnover x | Sharpe(d) | Sortino(d) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E01-P | 239 | 95 | -10.09 | 1.96 | 9.47 | 2.58 | -10.09 | 0.32 | -0.11 | 0.31 | 10.38 | 2.25 | 94.75 | -9.09 | -8.28 |
| E01-F | 83 | 66 | -7.39 | 0.96 | 6.58 | 1.77 | -7.39 | 0.30 | -0.11 | 0.30 | 7.67 | 1.63 | 65.84 | -9.02 | -8.50 |
| E02-P | 521 | 93 | -10.06 | 1.69 | 9.27 | 2.48 | -10.06 | 0.30 | -0.11 | 0.44 | 10.06 | 3.49 | 92.73 | -6.40 | -6.58 |
| E02-F | 320 | 102 | -10.08 | 2.76 | 10.16 | 2.67 | -10.08 | 0.30 | -0.10 | 0.47 | 10.08 | 4.04 | 101.64 | -8.19 | -7.82 |
| B01-h30 | 469 | 63 | -10.03 | -2.14 | 6.27 | 1.62 | -10.03 | 0.19 | -0.16 | 0.15 | 10.03 | 1.57 | 62.70 | -7.34 | -6.90 |
| B01-h60 | 469 | 60 | -10.13 | -2.62 | 5.97 | 1.54 | -10.13 | 0.18 | -0.17 | 0.19 | 10.13 | 2.35 | 59.71 | -7.09 | -6.69 |

Exit reasons / rejected signals / risk events (main):

- **E01-P**: exits {'risk_exit_daily': 1, 'risk_exit_total': 1, 'stop': 20, 'target': 6, 'time_exit': 67}; rejected {'concurrent_signal_lower_priority': 55, 'cooldown': 3, 'daily_loss_pause': 2, 'position_open': 3, 'total_loss_stop': 81}; risk events {'risk_exit_daily_triggered': 1, 'daily_pause': 1, 'risk_exit_total_triggered': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.0927)
- **E01-F**: exits {'stop': 13, 'target': 4, 'time_exit': 49}; rejected {'concurrent_signal_lower_priority': 16, 'position_open': 1}; risk events {}; uncertain-gap trades 0 (conservative-gap net -7.3878)
- **E02-P**: exits {'risk_exit_total': 1, 'stop': 31, 'target': 22, 'time_exit': 39}; rejected {'concurrent_signal_lower_priority': 51, 'cooldown': 26, 'position_open': 95, 'total_loss_stop': 256}; risk events {'risk_exit_total_triggered': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.0647)
- **E02-F**: exits {'risk_exit_total': 1, 'stop': 30, 'target': 24, 'time_exit': 47}; rejected {'concurrent_signal_lower_priority': 41, 'cooldown': 24, 'position_open': 45, 'total_loss_stop': 108}; risk events {'risk_exit_total_triggered': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.0761)
- **B01-h30**: exits {'risk_exit_daily': 1, 'stop': 16, 'target': 3, 'time_exit': 43}; rejected {'concurrent_signal_lower_priority': 33, 'cooldown': 3, 'daily_loss_pause': 4, 'position_open': 23, 'total_loss_stop': 343}; risk events {'daily_pause': 3, 'risk_exit_daily_triggered': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.0255)
- **B01-h60**: exits {'risk_exit_daily': 3, 'risk_exit_total': 1, 'stop': 21, 'target': 5, 'time_exit': 30}; rejected {'concurrent_signal_lower_priority': 30, 'cooldown': 3, 'daily_loss_pause': 7, 'position_open': 32, 'total_loss_stop': 337}; risk events {'risk_exit_daily_triggered': 3, 'daily_pause': 3, 'risk_exit_total_triggered': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.1331)

## 2. Baselines

| baseline | trades | net PnL | return % | max DD | exposure / risk |
|---|---|---|---|---|---|
| B00 cash | 0 | 0.00 | 0.00 | n/a | flat |
| B02-BH-BTCUSDT | 1 | 4.55 | 4.55 | 7.34 | 100% time, $50, no stop |
| B02-BH-ETHUSDT | 1 | 16.44 | 16.44 | 9.90 | 100% time, $50, no stop |
| B02-BH-SOLUSDT | 1 | 14.03 | 14.03 | 10.00 | 100% time, $50, no stop |

B01 = adaptation of upstream Freqtrade `SampleStrategy` entry signals (freqtrade 2026.10, template sha256 `18d48d64b955dc9b…`) with the unified exit/risk/cost rules; hold 30 and 60 min variants (shown in table 1).

### B03 random entries (frequency-matched, 100 fixed seeds per target)

| target | strategy net | rnd p5 | p25 | median | p75 | p95 | rnd mean trades | share seeds >= strategy |
|---|---|---|---|---|---|---|---|---|
| E01-F | -7.39 | -10.12 | -10.09 | -10.06 | -9.12 | -7.97 | 75.26 | 0.01 |
| E01-P | -10.09 | -10.14 | -10.10 | -10.08 | -10.07 | -10.02 | 81.63 | 0.67 |
| E02-F | -10.08 | -10.14 | -10.09 | -10.07 | -10.06 | -10.01 | 77.43 | 0.52 |
| E02-P | -10.06 | -10.16 | -10.10 | -10.08 | -10.07 | -10.02 | 80.70 | 0.21 |

## 3. Diagnostic: signal-only, NO portfolio stop (not a safe-trading estimate)

| strategy | trades | net PnL | gross PnL | win rate | expectancy | PF | max DD |
|---|---|---|---|---|---|---|---|
| E01-P | 144 | -13.93 | 4.30 | 0.34 | -0.10 | 0.34 | 14.96 |
| E01-F | 66 | -7.39 | 0.96 | 0.30 | -0.11 | 0.30 | 7.67 |
| E02-P | 190 | -19.11 | 4.81 | 0.30 | -0.10 | 0.46 | 19.43 |
| E02-F | 150 | -13.26 | 5.60 | 0.31 | -0.09 | 0.50 | 14.39 |
| B01-h30 | 247 | -32.98 | -2.07 | 0.17 | -0.13 | 0.13 | 32.98 |
| B01-h60 | 219 | -29.80 | -2.40 | 0.20 | -0.14 | 0.19 | 29.80 |

## 4. Cost and execution sensitivity (full replay, risk limits ON)

0/10/40 bps round-trip are hypothetical, split fee:slippage = 80:20. `delay60`: entry one more minute later. `coarse_step_x10`: lot step x10 (exchange filters are assumptions).

| strategy | 0 bps | 10 bps | 25 bps (main) | 40 bps | delay 60s | coarse step | break-even RT bps (fixed rt0 fills) |
|---|---|---|---|---|---|---|---|
| E01-P | 4.28 | -3.10 | -10.09 | -10.13 | -10.10 | -10.06 | 6.05 |
| E01-F | 0.72 | -2.57 | -7.39 | -10.14 | -6.62 | -7.12 | 2.25 |
| E02-P | 3.67 | -5.42 | -10.06 | -10.15 | -10.10 | -10.07 | 3.97 |
| E02-F | 4.62 | -2.65 | -10.08 | -10.01 | -10.08 | -10.08 | 6.22 |
| B01-h30 | -2.01 | -10.04 | -10.03 | -10.04 | -10.12 | -10.07 | -1.60 |
| B01-h60 | -2.81 | -10.03 | -10.13 | -10.12 | -10.11 | -10.06 | -2.53 |

## 5. By asset and by regime (main scenario)

Regime = sign of trailing 24h log return x trailing 24h r5 volatility vs development median per symbol (past-only; thresholds fixed on development).

| strategy | group | key | trades | net PnL | win rate | expectancy |
|---|---|---|---|---|---|---|
| E01-P | symbol | BTCUSDT | 23 | -1.34 | 0.39 | -0.06 |
| E01-P | symbol | ETHUSDT | 39 | -3.08 | 0.33 | -0.08 |
| E01-P | symbol | SOLUSDT | 33 | -5.67 | 0.24 | -0.17 |
| E01-P | regime | down_highvol | 29 | -2.95 | 0.38 | -0.10 |
| E01-P | regime | down_lowvol | 20 | -0.58 | 0.40 | -0.03 |
| E01-P | regime | up_highvol | 31 | -4.31 | 0.26 | -0.14 |
| E01-P | regime | up_lowvol | 15 | -2.26 | 0.20 | -0.15 |
| E01-F | symbol | BTCUSDT | 14 | -2.01 | 0.21 | -0.14 |
| E01-F | symbol | ETHUSDT | 28 | -2.38 | 0.36 | -0.09 |
| E01-F | symbol | SOLUSDT | 24 | -2.99 | 0.29 | -0.12 |
| E01-F | regime | down_highvol | 13 | -0.97 | 0.38 | -0.07 |
| E01-F | regime | down_lowvol | 25 | -1.45 | 0.40 | -0.06 |
| E01-F | regime | up_highvol | 14 | -2.84 | 0.14 | -0.20 |
| E01-F | regime | up_lowvol | 14 | -2.14 | 0.21 | -0.15 |
| E02-P | symbol | BTCUSDT | 36 | -4.80 | 0.28 | -0.13 |
| E02-P | symbol | ETHUSDT | 30 | -4.79 | 0.20 | -0.16 |
| E02-P | symbol | SOLUSDT | 27 | -0.48 | 0.44 | -0.02 |
| E02-P | regime | down_highvol | 20 | -1.31 | 0.40 | -0.07 |
| E02-P | regime | down_lowvol | 8 | -1.10 | 0.25 | -0.14 |
| E02-P | regime | up_highvol | 31 | -2.44 | 0.35 | -0.08 |
| E02-P | regime | up_lowvol | 34 | -5.21 | 0.21 | -0.15 |
| E02-F | symbol | BTCUSDT | 45 | -6.29 | 0.27 | -0.14 |
| E02-F | symbol | ETHUSDT | 32 | -1.64 | 0.34 | -0.05 |
| E02-F | symbol | SOLUSDT | 25 | -2.15 | 0.32 | -0.09 |
| E02-F | regime | down_highvol | 18 | -1.35 | 0.39 | -0.08 |
| E02-F | regime | down_lowvol | 13 | -1.53 | 0.23 | -0.12 |
| E02-F | regime | up_highvol | 30 | -2.35 | 0.37 | -0.08 |
| E02-F | regime | up_lowvol | 41 | -4.85 | 0.24 | -0.12 |
| B01-h30 | symbol | BTCUSDT | 32 | -4.70 | 0.09 | -0.15 |
| B01-h30 | symbol | ETHUSDT | 21 | -2.81 | 0.33 | -0.13 |
| B01-h30 | symbol | SOLUSDT | 10 | -2.52 | 0.20 | -0.25 |
| B01-h30 | regime | down_highvol | 28 | -4.62 | 0.21 | -0.16 |
| B01-h30 | regime | down_lowvol | 20 | -3.32 | 0.15 | -0.17 |
| B01-h30 | regime | up_highvol | 5 | -1.26 | 0.20 | -0.25 |
| B01-h30 | regime | up_lowvol | 10 | -0.82 | 0.20 | -0.08 |
| B01-h60 | symbol | BTCUSDT | 33 | -5.68 | 0.15 | -0.17 |
| B01-h60 | symbol | ETHUSDT | 17 | -2.12 | 0.24 | -0.12 |
| B01-h60 | symbol | SOLUSDT | 10 | -2.33 | 0.20 | -0.23 |
| B01-h60 | regime | down_highvol | 27 | -4.51 | 0.19 | -0.17 |
| B01-h60 | regime | down_lowvol | 21 | -3.76 | 0.19 | -0.18 |
| B01-h60 | regime | up_highvol | 4 | -1.26 | 0.00 | -0.31 |
| B01-h60 | regime | up_lowvol | 8 | -0.61 | 0.25 | -0.08 |

## 6. Non-overlapping 4-day / 7-day windows and rolling 7-day (main scenario)

| strategy | window | complete windows | share > 0 | share 0 trades | min PnL | median PnL | max PnL |
|---|---|---|---|---|---|---|---|
| E01-P | 4d | 18 | 0.00 | 0.61 | -2.98 | 0.00 | 0.00 |
| E01-P | 7d | 10 | 0.00 | 0.60 | -4.09 | 0.00 | 0.00 |
| E01-P | rolling 7d | 67 | 0.00 |  | -4.33 | 0.00 | 0.00 |
| E01-F | 4d | 18 | 0.11 | 0.11 | -1.15 | -0.38 | 0.26 |
| E01-F | 7d | 10 | 0.20 | 0.10 | -1.70 | -0.74 | 0.37 |
| E01-F | rolling 7d | 67 | 0.06 |  | -1.70 | -0.55 | 0.37 |
| E02-P | 4d | 18 | 0.06 | 0.61 | -3.03 | 0.00 | 0.16 |
| E02-P | 7d | 10 | 0.00 | 0.60 | -4.83 | 0.00 | 0.00 |
| E02-P | rolling 7d | 67 | 0.00 |  | -5.16 | 0.00 | 0.00 |
| E02-F | 4d | 18 | 0.06 | 0.44 | -2.46 | -0.03 | 0.11 |
| E02-F | 7d | 10 | 0.00 | 0.40 | -3.80 | -0.45 | 0.00 |
| E02-F | rolling 7d | 67 | 0.00 |  | -4.27 | -0.46 | 0.00 |
| B01-h30 | 4d | 18 | 0.00 | 0.72 | -2.72 | 0.00 | 0.00 |
| B01-h30 | 7d | 10 | 0.00 | 0.70 | -5.17 | 0.00 | 0.00 |
| B01-h30 | rolling 7d | 67 | 0.00 |  | -5.90 | 0.00 | 0.00 |
| B01-h60 | 4d | 18 | 0.00 | 0.72 | -3.21 | 0.00 | 0.00 |
| B01-h60 | 7d | 10 | 0.00 | 0.70 | -5.77 | 0.00 | 0.00 |
| B01-h60 | rolling 7d | 67 | 0.00 |  | -6.18 | 0.00 | 0.00 |

## 7. Uncertainty: moving-block bootstrap of daily PnL (main scenario; preliminary)

| strategy | block | days | mean daily PnL | 95% CI total PnL | P(boot mean<=0) | p one-sided |
|---|---|---|---|---|---|---|
| E01-P | block_7d | 73 | -0.14 | [-17.283, -2.088] | 1.00 | 1.00 |
| E01-P | block_3d | 73 | -0.14 | [-17.529, -4.199] | 1.00 | 1.00 |
| E01-P | block_14d | 73 | -0.14 | [-18.297, -0.261] | 1.00 | 1.00 |
| E01-F | block_7d | 73 | -0.10 | [-10.251, -3.495] | 1.00 | 1.00 |
| E01-F | block_3d | 73 | -0.10 | [-10.403, -3.612] | 1.00 | 1.00 |
| E01-F | block_14d | 73 | -0.10 | [-9.816, -3.958] | 1.00 | 1.00 |
| E02-P | block_7d | 73 | -0.14 | [-18.899, -1.754] | 1.00 | 1.00 |
| E02-P | block_3d | 73 | -0.14 | [-18.083, -2.652] | 1.00 | 1.00 |
| E02-P | block_14d | 73 | -0.14 | [-21.101, -0.388] | 1.00 | 1.00 |
| E02-F | block_7d | 73 | -0.14 | [-17.654, -3.002] | 1.00 | 1.00 |
| E02-F | block_3d | 73 | -0.14 | [-16.366, -4.038] | 1.00 | 1.00 |
| E02-F | block_14d | 73 | -0.14 | [-20.370, -1.743] | 1.00 | 1.00 |
| B01-h30 | block_7d | 73 | -0.14 | [-21.397, 0.000] | 1.00 | 1.00 |
| B01-h30 | block_3d | 73 | -0.14 | [-18.607, -2.623] | 1.00 | 1.00 |
| B01-h30 | block_14d | 73 | -0.14 | [-23.581, 0.000] | 1.00 | 1.00 |
| B01-h60 | block_7d | 73 | -0.14 | [-21.944, -0.287] | 1.00 | 1.00 |
| B01-h60 | block_3d | 73 | -0.14 | [-19.230, -2.521] | 1.00 | 1.00 |
| B01-h60 | block_14d | 73 | -0.14 | [-24.072, 0.000] | 1.00 | 1.00 |

Holm correction across the 4 pre-registered candidates (7-day blocks):

| candidate | p | p Holm | reject H0 (mean<=0) at 5% |
|---|---|---|---|
| E01-P | 1.00 | 1.00 | False |
| E01-F | 1.00 | 1.00 | False |
| E02-P | 1.00 | 1.00 | False |
| E02-F | 1.00 | 1.00 | False |

No winner is declared from a single window; this report does not approve any demo or live use.

## 8. Event study (mechanism check, not a trading result)

Forward log returns from the 1m open at decision time; pooled across symbols (ALL).

| group | h (min) | n | mean bps | median bps | share > 0 | naive t |
|---|---|---|---|---|---|---|
| E01-P | 15 | 239 | 7.54 | 5.41 | 0.59 | 3.01 |
| E01-P | 30 | 239 | 8.28 | 5.55 | 0.56 | 2.34 |
| E01-P | 60 | 239 | 5.10 | 1.32 | 0.51 | 1.03 |
| E01-F | 15 | 83 | 6.06 | 8.18 | 0.65 | 1.65 |
| E01-F | 30 | 83 | 1.59 | 1.40 | 0.57 | 0.29 |
| E01-F | 60 | 83 | -5.89 | 3.09 | 0.51 | -0.61 |
| E02-P | 15 | 521 | 6.59 | -2.73 | 0.46 | 2.68 |
| E02-P | 30 | 521 | 8.75 | -3.78 | 0.45 | 2.51 |
| E02-P | 60 | 521 | 7.77 | -7.99 | 0.45 | 1.78 |
| E02-F | 15 | 320 | 6.78 | -1.41 | 0.47 | 2.45 |
| E02-F | 30 | 320 | 8.97 | -4.22 | 0.44 | 2.13 |
| E02-F | 60 | 320 | 7.22 | -8.34 | 0.45 | 1.33 |
| background_all_5m | 15 | 63060 | 0.30 | 0.00 | 0.49 | 3.02 |
| background_all_5m | 30 | 63051 | 0.60 | 0.00 | 0.49 | 4.21 |
| background_all_5m | 60 | 63033 | 1.18 | 0.23 | 0.50 | 5.82 |

## 9. Reproducibility

```
{
  "config_sha256": "792e04593f9a8de8084dcc948b73c5651055bdc2d70b0b2e16c413a35eaba8e8",
  "code_sha256": "acfbf419a708f10681b92d1f32f79c8381aed093380d20e2d67d8d9e8546dbd7",
  "git_commit": "2036eb977e4c7a61ecb25844d8e55bd90b5fee49",
  "regime_thresholds_sha256": "2011718b3d3fc0254eca85827b6dac0a364cec4673202ad48f5626a2d390da93",
  "data_manifest_sha256": "4031c50d06c1662fe2e1a76d8508b1a685db1cd21331f2e4b166ddb46142c678"
}
```

Ledger reconciliation (main scenario): E01-P: OK (95 trades), E01-F: OK (66 trades), E02-P: OK (93 trades), E02-F: OK (102 trades), B01-h30: OK (63 trades), B01-h60: OK (60 trades)
