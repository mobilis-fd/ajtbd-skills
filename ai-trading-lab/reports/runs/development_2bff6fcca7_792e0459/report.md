# Backtest report — development

Experiment `MVP-v0.1-E01E02`; segment `[2025-11-01 00:00:00+00:00, 2026-06-08 00:00:00+00:00)` UTC.
Config sha256 `792e04593f9a8de8…`, code sha256 `2bff6fcca75416ed…`, git `803db3afbbf8b5dd428e3e629a35564460bea331`.

Research replay with virtual capital (100 USDT per strategy wallet). No real orders. Results include negative outcomes; nothing was tuned on these data.
Cost model (main): fee 10 bps/side + adverse price adjustment 2.5 bps/side = 25 bps round trip (working assumption, not the user's tariff; real spread unknown on OHLCV).

## 1. Main scenario (portfolio risk limits ON)

| strategy | raw signals | trades | net PnL | gross PnL | fees | slippage | return % | win rate | expectancy | PF | max DD | exposure % | turnover x | Sharpe(d) | Sortino(d) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E01-P | 1254 | 81 | -10.11 | 0.05 | 8.06 | 2.10 | -10.11 | 0.35 | -0.12 | 0.36 | 10.53 | 0.51 | 80.62 | -3.63 | -3.65 |
| E01-F | 425 | 79 | -10.07 | -0.16 | 7.86 | 2.05 | -10.07 | 0.35 | -0.13 | 0.37 | 10.28 | 0.54 | 78.61 | -4.66 | -4.67 |
| E02-P | 1821 | 103 | -10.01 | 2.90 | 10.25 | 2.66 | -10.01 | 0.37 | -0.10 | 0.50 | 10.01 | 1.18 | 102.48 | -4.28 | -4.37 |
| E02-F | 1098 | 94 | -10.05 | 1.74 | 9.35 | 2.44 | -10.05 | 0.37 | -0.11 | 0.47 | 10.05 | 1.09 | 93.45 | -4.13 | -4.21 |
| B01-h30 | 1491 | 69 | -10.07 | -1.47 | 6.85 | 1.75 | -10.07 | 0.22 | -0.15 | 0.21 | 10.07 | 0.50 | 68.52 | -4.10 | -4.03 |
| B01-h60 | 1491 | 70 | -10.25 | -1.50 | 6.95 | 1.80 | -10.25 | 0.26 | -0.15 | 0.32 | 10.39 | 0.82 | 69.55 | -3.94 | -3.89 |

Exit reasons / rejected signals / risk events (main):

- **E01-P**: exits {'risk_exit_daily': 2, 'stop': 31, 'target': 13, 'time_exit': 35}; rejected {'concurrent_signal_lower_priority': 43, 'cooldown': 1, 'daily_loss_pause': 7, 'position_open': 2, 'total_loss_stop': 1120}; risk events {'daily_pause': 3, 'risk_exit_daily_triggered': 2, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.1140)
- **E01-F**: exits {'risk_exit_total': 1, 'stop': 30, 'target': 13, 'time_exit': 35}; rejected {'concurrent_signal_lower_priority': 13, 'cooldown': 1, 'position_open': 3, 'total_loss_stop': 329}; risk events {'risk_exit_total_triggered': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.0720)
- **E02-P**: exits {'stop': 38, 'target': 28, 'time_exit': 37}; rejected {'concurrent_signal_lower_priority': 41, 'cooldown': 37, 'daily_loss_pause': 14, 'position_open': 87, 'total_loss_stop': 1539}; risk events {'daily_pause': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.0121)
- **E02-F**: exits {'risk_exit_daily': 1, 'stop': 37, 'target': 24, 'time_exit': 32}; rejected {'concurrent_signal_lower_priority': 23, 'cooldown': 23, 'daily_loss_pause': 1, 'position_open': 47, 'total_loss_stop': 910}; risk events {'risk_exit_daily_triggered': 1, 'daily_pause': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.0476)
- **B01-h30**: exits {'risk_exit_daily': 1, 'risk_exit_total': 1, 'stop': 17, 'target': 6, 'time_exit': 44}; rejected {'concurrent_signal_lower_priority': 29, 'cooldown': 4, 'daily_loss_pause': 3, 'position_open': 29, 'total_loss_stop': 1357}; risk events {'daily_pause': 2, 'risk_exit_daily_triggered': 1, 'risk_exit_total_triggered': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.0727)
- **B01-h60**: exits {'risk_exit_daily': 2, 'risk_exit_total': 1, 'stop': 26, 'target': 11, 'time_exit': 30}; rejected {'concurrent_signal_lower_priority': 28, 'cooldown': 2, 'daily_loss_pause': 2, 'position_open': 39, 'total_loss_stop': 1350}; risk events {'risk_exit_daily_triggered': 2, 'daily_pause': 2, 'risk_exit_total_triggered': 1, 'total_stop': 1}; uncertain-gap trades 0 (conservative-gap net -10.2481)

## 2. Baselines

| baseline | trades | net PnL | return % | max DD | exposure / risk |
|---|---|---|---|---|---|
| B00 cash | 0 | 0.00 | 0.00 | n/a | flat |
| B02-BH-BTCUSDT | 1 | -20.92 | -20.92 | 23.44 | 100% time, $50, no stop |
| B02-BH-ETHUSDT | 1 | -27.92 | -27.92 | 30.99 | 100% time, $50, no stop |
| B02-BH-SOLUSDT | 1 | -32.32 | -32.32 | 34.33 | 100% time, $50, no stop |

B01 = adaptation of upstream Freqtrade `SampleStrategy` entry signals (freqtrade 2026.10, template sha256 `18d48d64b955dc9b…`) with the unified exit/risk/cost rules; hold 30 and 60 min variants (shown in table 1).

### B03 random entries (frequency-matched, 100 fixed seeds per target)

| target | strategy net | rnd p5 | p25 | median | p75 | p95 | rnd mean trades | share seeds >= strategy |
|---|---|---|---|---|---|---|---|---|
| E01-F | -10.07 | -10.14 | -10.10 | -10.08 | -10.07 | -10.02 | 78.38 | 0.41 |
| E01-P | -10.11 | -10.22 | -10.11 | -10.08 | -10.07 | -10.02 | 71.92 | 0.77 |
| E02-F | -10.05 | -10.16 | -10.11 | -10.09 | -10.07 | -10.03 | 67.12 | 0.06 |
| E02-P | -10.01 | -10.19 | -10.11 | -10.08 | -10.07 | -10.03 | 68.07 | 0.02 |

## 3. Diagnostic: signal-only, NO portfolio stop (not a safe-trading estimate)

| strategy | trades | net PnL | gross PnL | win rate | expectancy | PF | max DD |
|---|---|---|---|---|---|---|---|
| E01-P | 759 | -75.03 | 9.56 | 0.33 | -0.10 | 0.37 | 75.72 |
| E01-F | 334 | -39.77 | 2.32 | 0.32 | -0.12 | 0.34 | 40.57 |
| E02-P | 667 | -73.46 | 1.01 | 0.33 | -0.11 | 0.41 | 73.74 |
| E02-F | 544 | -57.32 | 10.20 | 0.35 | -0.11 | 0.45 | 58.67 |
| B01-h30 | 796 | -83.80 | -3.79 | 0.22 | -0.11 | 0.21 | 83.93 |
| B01-h60 | 740 | -80.17 | -2.31 | 0.30 | -0.11 | 0.30 | 80.72 |

## 4. Cost and execution sensitivity (full replay, risk limits ON)

0/10/40 bps round-trip are hypothetical, split fee:slippage = 80:20. `delay60`: entry one more minute later. `coarse_step_x10`: lot step x10 (exchange filters are assumptions).

| strategy | 0 bps | 10 bps | 25 bps (main) | 40 bps | delay 60s | coarse step | break-even RT bps (fixed rt0 fills) |
|---|---|---|---|---|---|---|---|
| E01-P | 11.82 | -10.13 | -10.11 | -10.17 | -10.11 | -10.07 | 3.20 |
| E01-F | 1.62 | -10.04 | -10.07 | -10.15 | -10.01 | -10.11 | 1.05 |
| E02-P | 2.51 | -10.04 | -10.01 | -10.18 | -10.03 | -10.18 | 0.84 |
| E02-F | 9.61 | -10.04 | -10.05 | -10.12 | -10.10 | -10.06 | 3.62 |
| B01-h30 | -7.19 | -10.08 | -10.07 | -10.19 | -10.09 | -10.11 | -1.78 |
| B01-h60 | -3.50 | -10.02 | -10.25 | -10.07 | -10.10 | -10.06 | -0.90 |

## 5. By asset and by regime (main scenario)

Regime = sign of trailing 24h log return x trailing 24h r5 volatility vs development median per symbol (past-only; thresholds fixed on development).

| strategy | group | key | trades | net PnL | win rate | expectancy |
|---|---|---|---|---|---|---|
| E01-P | symbol | BTCUSDT | 23 | -3.12 | 0.35 | -0.14 |
| E01-P | symbol | ETHUSDT | 34 | -5.13 | 0.29 | -0.15 |
| E01-P | symbol | SOLUSDT | 24 | -1.86 | 0.42 | -0.08 |
| E01-P | regime | down_highvol | 53 | -7.52 | 0.34 | -0.14 |
| E01-P | regime | down_lowvol | 9 | -0.88 | 0.33 | -0.10 |
| E01-P | regime | up_highvol | 15 | -1.23 | 0.40 | -0.08 |
| E01-P | regime | up_lowvol | 4 | -0.48 | 0.25 | -0.12 |
| E01-F | symbol | BTCUSDT | 28 | -5.43 | 0.25 | -0.19 |
| E01-F | symbol | ETHUSDT | 29 | -3.61 | 0.38 | -0.12 |
| E01-F | symbol | SOLUSDT | 22 | -1.03 | 0.45 | -0.05 |
| E01-F | regime | down_highvol | 42 | -3.03 | 0.43 | -0.07 |
| E01-F | regime | down_lowvol | 11 | -2.19 | 0.27 | -0.20 |
| E01-F | regime | up_highvol | 25 | -5.19 | 0.24 | -0.21 |
| E01-F | regime | up_lowvol | 1 | 0.34 | 1.00 | 0.34 |
| E02-P | symbol | BTCUSDT | 32 | -4.57 | 0.28 | -0.14 |
| E02-P | symbol | ETHUSDT | 45 | -1.86 | 0.44 | -0.04 |
| E02-P | symbol | SOLUSDT | 26 | -3.58 | 0.35 | -0.14 |
| E02-P | regime | down_highvol | 45 | -3.52 | 0.44 | -0.08 |
| E02-P | regime | down_lowvol | 11 | -1.32 | 0.36 | -0.12 |
| E02-P | regime | up_highvol | 30 | -3.78 | 0.27 | -0.13 |
| E02-P | regime | up_lowvol | 17 | -1.40 | 0.35 | -0.08 |
| E02-F | symbol | BTCUSDT | 31 | -3.68 | 0.35 | -0.12 |
| E02-F | symbol | ETHUSDT | 35 | -1.12 | 0.46 | -0.03 |
| E02-F | symbol | SOLUSDT | 28 | -5.24 | 0.29 | -0.19 |
| E02-F | regime | down_highvol | 39 | -4.60 | 0.38 | -0.12 |
| E02-F | regime | down_lowvol | 9 | -0.92 | 0.44 | -0.10 |
| E02-F | regime | up_highvol | 32 | -3.18 | 0.34 | -0.10 |
| E02-F | regime | up_lowvol | 14 | -1.35 | 0.36 | -0.10 |
| B01-h30 | symbol | BTCUSDT | 37 | -5.11 | 0.16 | -0.14 |
| B01-h30 | symbol | ETHUSDT | 16 | -3.05 | 0.19 | -0.19 |
| B01-h30 | symbol | SOLUSDT | 16 | -1.91 | 0.38 | -0.12 |
| B01-h30 | regime | down_highvol | 42 | -6.85 | 0.24 | -0.16 |
| B01-h30 | regime | down_lowvol | 15 | -1.81 | 0.13 | -0.12 |
| B01-h30 | regime | up_highvol | 11 | -1.29 | 0.27 | -0.12 |
| B01-h30 | regime | up_lowvol | 1 | -0.12 | 0.00 | -0.12 |
| B01-h60 | symbol | BTCUSDT | 36 | -4.47 | 0.25 | -0.12 |
| B01-h60 | symbol | ETHUSDT | 14 | -2.08 | 0.29 | -0.15 |
| B01-h60 | symbol | SOLUSDT | 20 | -3.70 | 0.25 | -0.19 |
| B01-h60 | regime | down_highvol | 45 | -6.73 | 0.29 | -0.15 |
| B01-h60 | regime | down_lowvol | 14 | -1.64 | 0.21 | -0.12 |
| B01-h60 | regime | up_highvol | 10 | -1.76 | 0.20 | -0.18 |
| B01-h60 | regime | up_lowvol | 1 | -0.12 | 0.00 | -0.12 |

## 6. Non-overlapping 4-day / 7-day windows and rolling 7-day (main scenario)

| strategy | window | complete windows | share > 0 | share 0 trades | min PnL | median PnL | max PnL |
|---|---|---|---|---|---|---|---|
| E01-P | 4d | 54 | 0.00 | 0.91 | -2.79 | 0.00 | 0.00 |
| E01-P | 7d | 31 | 0.00 | 0.90 | -4.29 | 0.00 | 0.00 |
| E01-P | rolling 7d | 213 | 0.00 |  | -5.49 | 0.00 | 0.00 |
| E01-F | 4d | 54 | 0.02 | 0.76 | -1.96 | 0.00 | 0.05 |
| E01-F | 7d | 31 | 0.00 | 0.77 | -2.45 | 0.00 | 0.00 |
| E01-F | rolling 7d | 213 | 0.00 |  | -2.49 | 0.00 | 0.00 |
| E02-P | 4d | 54 | 0.00 | 0.85 | -2.60 | 0.00 | 0.00 |
| E02-P | 7d | 31 | 0.00 | 0.84 | -2.96 | 0.00 | 0.00 |
| E02-P | rolling 7d | 213 | 0.00 |  | -3.34 | 0.00 | 0.00 |
| E02-F | 4d | 54 | 0.00 | 0.83 | -2.32 | 0.00 | 0.00 |
| E02-F | 7d | 31 | 0.00 | 0.84 | -3.00 | 0.00 | 0.00 |
| E02-F | rolling 7d | 213 | 0.00 |  | -3.49 | 0.00 | 0.00 |
| B01-h30 | 4d | 54 | 0.00 | 0.91 | -3.69 | 0.00 | 0.00 |
| B01-h30 | 7d | 31 | 0.00 | 0.90 | -5.33 | 0.00 | 0.00 |
| B01-h30 | rolling 7d | 213 | 0.00 |  | -5.97 | 0.00 | 0.00 |
| B01-h60 | 4d | 54 | 0.00 | 0.91 | -2.85 | 0.00 | 0.00 |
| B01-h60 | 7d | 31 | 0.00 | 0.90 | -4.71 | 0.00 | 0.00 |
| B01-h60 | rolling 7d | 213 | 0.00 |  | -6.46 | 0.00 | 0.00 |

## 7. Uncertainty: moving-block bootstrap of daily PnL (main scenario; preliminary)

| strategy | block | days | mean daily PnL | 95% CI total PnL | P(boot mean<=0) | p one-sided |
|---|---|---|---|---|---|---|
| E01-P | block_7d | 219 | -0.05 | [-20.787, 0.000] | 1.00 | 1.00 |
| E01-P | block_3d | 219 | -0.05 | [-20.465, -1.954] | 1.00 | 1.00 |
| E01-P | block_14d | 219 | -0.05 | [-22.661, 0.000] | 1.00 | 1.00 |
| E01-F | block_7d | 219 | -0.05 | [-16.784, -3.235] | 1.00 | 1.00 |
| E01-F | block_3d | 219 | -0.05 | [-17.058, -4.415] | 1.00 | 1.00 |
| E01-F | block_14d | 219 | -0.05 | [-18.065, -1.870] | 1.00 | 1.00 |
| E02-P | block_7d | 219 | -0.05 | [-18.124, -1.641] | 1.00 | 1.00 |
| E02-P | block_3d | 219 | -0.05 | [-17.026, -3.705] | 1.00 | 1.00 |
| E02-P | block_14d | 219 | -0.05 | [-19.940, 0.000] | 1.00 | 1.00 |
| E02-F | block_7d | 219 | -0.05 | [-18.074, -1.741] | 1.00 | 1.00 |
| E02-F | block_3d | 219 | -0.05 | [-17.696, -3.522] | 1.00 | 1.00 |
| E02-F | block_14d | 219 | -0.05 | [-18.372, 0.000] | 1.00 | 1.00 |
| B01-h30 | block_7d | 219 | -0.05 | [-22.818, 0.000] | 1.00 | 1.00 |
| B01-h30 | block_3d | 219 | -0.05 | [-19.573, -2.408] | 1.00 | 1.00 |
| B01-h30 | block_14d | 219 | -0.05 | [-23.990, 0.000] | 1.00 | 1.00 |
| B01-h60 | block_7d | 219 | -0.05 | [-22.725, 0.000] | 1.00 | 1.00 |
| B01-h60 | block_3d | 219 | -0.05 | [-19.564, -2.631] | 1.00 | 1.00 |
| B01-h60 | block_14d | 219 | -0.05 | [-24.083, 0.000] | 1.00 | 1.00 |

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
| E01-P | 15 | 1254 | 1.15 | 4.37 | 0.54 | 0.69 |
| E01-P | 30 | 1254 | 2.69 | 6.73 | 0.55 | 1.22 |
| E01-P | 60 | 1254 | -2.32 | 5.70 | 0.52 | -0.81 |
| E01-F | 15 | 425 | -0.59 | 4.28 | 0.53 | -0.23 |
| E01-F | 30 | 425 | -4.13 | 4.40 | 0.53 | -1.19 |
| E01-F | 60 | 425 | -5.36 | 1.22 | 0.50 | -1.16 |
| E02-P | 15 | 1821 | -2.44 | -6.78 | 0.43 | -1.87 |
| E02-P | 30 | 1821 | 0.08 | -3.72 | 0.46 | 0.04 |
| E02-P | 60 | 1821 | 3.12 | -3.20 | 0.48 | 1.24 |
| E02-F | 15 | 1098 | -1.39 | -6.25 | 0.43 | -0.86 |
| E02-F | 30 | 1098 | 1.63 | -3.20 | 0.47 | 0.75 |
| E02-F | 60 | 1098 | 4.27 | -2.24 | 0.48 | 1.46 |
| background_all_5m | 15 | 189204 | -0.38 | -0.02 | 0.49 | -4.90 |
| background_all_5m | 30 | 189195 | -0.76 | 0.00 | 0.50 | -6.97 |
| background_all_5m | 60 | 189177 | -1.53 | 0.00 | 0.50 | -9.94 |

## 9. Reproducibility

```
{
  "config_sha256": "792e04593f9a8de8084dcc948b73c5651055bdc2d70b0b2e16c413a35eaba8e8",
  "code_sha256": "2bff6fcca75416ed978a2de5d52953431d33896c9fc125d967a59b8bcb64e953",
  "git_commit": "803db3afbbf8b5dd428e3e629a35564460bea331",
  "regime_thresholds_sha256": "2011718b3d3fc0254eca85827b6dac0a364cec4673202ad48f5626a2d390da93",
  "data_manifest_sha256": "4031c50d06c1662fe2e1a76d8508b1a685db1cd21331f2e4b166ddb46142c678"
}
```

Ledger reconciliation (main scenario): E01-P: OK (81 trades), E01-F: OK (79 trades), E02-P: OK (103 trades), E02-F: OK (94 trades), B01-h30: OK (69 trades), B01-h60: OK (70 trades)
