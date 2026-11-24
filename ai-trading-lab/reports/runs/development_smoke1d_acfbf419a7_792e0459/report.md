# Backtest report — development_smoke1d

Experiment `MVP-v0.1-E01E02`; segment `[2025-11-01 00:00:00+00:00, 2025-11-02 00:00:00+00:00)` UTC.
Config sha256 `792e04593f9a8de8…`, code sha256 `acfbf419a708f106…`, git `2036eb977e4c7a61ecb25844d8e55bd90b5fee49`.

Research replay with virtual capital (100 USDT per strategy wallet). No real orders. Results include negative outcomes; nothing was tuned on these data.
Cost model (main): fee 10 bps/side + adverse price adjustment 2.5 bps/side = 25 bps round trip (working assumption, not the user's tariff; real spread unknown on OHLCV).

## 1. Main scenario (portfolio risk limits ON)

| strategy | raw signals | trades | net PnL | gross PnL | fees | slippage | return % | win rate | expectancy | PF | max DD | exposure % | turnover x | Sharpe(d) | Sortino(d) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E01-P | 1 | 1 | 0.15 | 0.27 | 0.10 | 0.03 | 0.15 | 1.00 | 0.15 | undefined: no losing trades (would be infinite) | 0.16 | 2.08 | 1.00 | n/a | n/a |
| E01-F | 1 | 1 | 0.15 | 0.27 | 0.10 | 0.03 | 0.15 | 1.00 | 0.15 | undefined: no losing trades (would be infinite) | 0.16 | 2.08 | 1.00 | n/a | n/a |
| E02-P | 2 | 1 | -0.11 | 0.02 | 0.10 | 0.03 | -0.11 | 0.00 | -0.11 | 0.00 | 0.26 | 4.17 | 1.00 | n/a | n/a |
| E02-F | 2 | 1 | -0.11 | 0.02 | 0.10 | 0.03 | -0.11 | 0.00 | -0.11 | 0.00 | 0.26 | 4.17 | 1.00 | n/a | n/a |
| B01-h30 | 3 | 3 | -0.21 | 0.16 | 0.30 | 0.08 | -0.21 | 0.33 | -0.07 | 0.20 | 0.21 | 6.25 | 2.98 | n/a | n/a |
| B01-h60 | 3 | 2 | -0.23 | 0.02 | 0.20 | 0.05 | -0.23 | 0.00 | -0.11 | 0.00 | 0.23 | 8.33 | 1.98 | n/a | n/a |

Exit reasons / rejected signals / risk events (main):

- **E01-P**: exits {'time_exit': 1}; rejected {}; risk events {}; uncertain-gap trades 0 (conservative-gap net 0.1475)
- **E01-F**: exits {'time_exit': 1}; rejected {}; risk events {}; uncertain-gap trades 0 (conservative-gap net 0.1475)
- **E02-P**: exits {'time_exit': 1}; rejected {'concurrent_signal_lower_priority': 1}; risk events {}; uncertain-gap trades 0 (conservative-gap net -0.1068)
- **E02-F**: exits {'time_exit': 1}; rejected {'concurrent_signal_lower_priority': 1}; risk events {}; uncertain-gap trades 0 (conservative-gap net -0.1068)
- **B01-h30**: exits {'time_exit': 3}; rejected {}; risk events {}; uncertain-gap trades 0 (conservative-gap net -0.2113)
- **B01-h60**: exits {'time_exit': 2}; rejected {'position_open': 1}; risk events {}; uncertain-gap trades 0 (conservative-gap net -0.2272)

## 2. Baselines

| baseline | trades | net PnL | return % | max DD | exposure / risk |
|---|---|---|---|---|---|
| B00 cash | 0 | 0.00 | 0.00 | n/a | flat |
| B02-BH-BTCUSDT | 1 | 0.10 | 0.10 | 0.36 | 100% time, $50, no stop |
| B02-BH-ETHUSDT | 1 | 0.21 | 0.21 | 0.47 | 100% time, $50, no stop |
| B02-BH-SOLUSDT | 1 | -0.36 | -0.36 | 0.94 | 100% time, $50, no stop |

B01 = adaptation of upstream Freqtrade `SampleStrategy` entry signals (freqtrade 2026.10, template sha256 `18d48d64b955dc9b…`) with the unified exit/risk/cost rules; hold 30 and 60 min variants (shown in table 1).

### B03 random entries (frequency-matched, 100 fixed seeds per target)

| target | strategy net | rnd p5 | p25 | median | p75 | p95 | rnd mean trades | share seeds >= strategy |
|---|---|---|---|---|---|---|---|---|
| E01-F | 0.15 | -0.21 | -0.09 | -0.04 | -0.02 | -0.02 | 1.00 | 0.00 |
| E01-P | 0.15 | -0.31 | -0.31 | -0.17 | -0.11 | -0.07 | 1.00 | 0.00 |
| E02-F | -0.11 | -0.56 | -0.54 | -0.50 | -0.31 | -0.27 | 2.00 | 0.00 |
| E02-P | -0.11 | -0.23 | -0.21 | -0.09 | -0.02 | 0.12 | 1.40 | 0.60 |

## 3. Diagnostic: signal-only, NO portfolio stop (not a safe-trading estimate)

| strategy | trades | net PnL | gross PnL | win rate | expectancy | PF | max DD |
|---|---|---|---|---|---|---|---|
| E01-P | 1 | 0.15 | 0.27 | 1.00 | 0.15 | undefined: no losing trades (would be infinite) | 0.16 |
| E01-F | 1 | 0.15 | 0.27 | 1.00 | 0.15 | undefined: no losing trades (would be infinite) | 0.16 |
| E02-P | 1 | -0.11 | 0.02 | 0.00 | -0.11 | 0.00 | 0.26 |
| E02-F | 1 | -0.11 | 0.02 | 0.00 | -0.11 | 0.00 | 0.26 |
| B01-h30 | 3 | -0.21 | 0.16 | 0.33 | -0.07 | 0.20 | 0.21 |
| B01-h60 | 2 | -0.23 | 0.02 | 0.00 | -0.11 | 0.00 | 0.23 |

## 4. Cost and execution sensitivity (full replay, risk limits ON)

0/10/40 bps round-trip are hypothetical, split fee:slippage = 80:20. `delay60`: entry one more minute later. `coarse_step_x10`: lot step x10 (exchange filters are assumptions).

| strategy | 0 bps | 10 bps | 25 bps (main) | 40 bps | delay 60s | coarse step | break-even RT bps (fixed rt0 fills) |
|---|---|---|---|---|---|---|---|
| E01-P | 0.27 | 0.22 | 0.15 | 0.07 | 0.06 | 0.14 | 55.02 |
| E01-F | 0.27 | 0.22 | 0.15 | 0.07 | 0.06 | 0.14 | 55.02 |
| E02-P | 0.02 | -0.03 | -0.11 | -0.18 | -0.16 | -0.10 | 3.62 |
| E02-F | 0.02 | -0.03 | -0.11 | -0.18 | -0.16 | -0.10 | 3.62 |
| B01-h30 | 0.16 | 0.01 | -0.21 | -0.44 | -0.10 | -0.18 | 10.95 |
| B01-h60 | 0.02 | -0.08 | -0.23 | -0.38 | -0.24 | -0.20 | 2.05 |

## 5. By asset and by regime (main scenario)

Regime = sign of trailing 24h log return x trailing 24h r5 volatility vs development median per symbol (past-only; thresholds fixed on development).

| strategy | group | key | trades | net PnL | win rate | expectancy |
|---|---|---|---|---|---|---|
| E01-P | symbol | SOLUSDT | 1 | 0.15 | 1.00 | 0.15 |
| E01-P | regime | down_lowvol | 1 | 0.15 | 1.00 | 0.15 |
| E01-F | symbol | SOLUSDT | 1 | 0.15 | 1.00 | 0.15 |
| E01-F | regime | down_lowvol | 1 | 0.15 | 1.00 | 0.15 |
| E02-P | symbol | ETHUSDT | 1 | -0.11 | 0.00 | -0.11 |
| E02-P | regime | up_lowvol | 1 | -0.11 | 0.00 | -0.11 |
| E02-F | symbol | ETHUSDT | 1 | -0.11 | 0.00 | -0.11 |
| E02-F | regime | up_lowvol | 1 | -0.11 | 0.00 | -0.11 |
| B01-h30 | symbol | BTCUSDT | 2 | -0.26 | 0.00 | -0.13 |
| B01-h30 | symbol | SOLUSDT | 1 | 0.05 | 1.00 | 0.05 |
| B01-h30 | regime | down_lowvol | 2 | -0.09 | 0.50 | -0.05 |
| B01-h30 | regime | up_lowvol | 1 | -0.12 | 0.00 | -0.12 |
| B01-h60 | symbol | BTCUSDT | 2 | -0.23 | 0.00 | -0.11 |
| B01-h60 | regime | down_lowvol | 1 | -0.11 | 0.00 | -0.11 |
| B01-h60 | regime | up_lowvol | 1 | -0.12 | 0.00 | -0.12 |

## 6. Non-overlapping 4-day / 7-day windows and rolling 7-day (main scenario)

| strategy | window | complete windows | share > 0 | share 0 trades | min PnL | median PnL | max PnL |
|---|---|---|---|---|---|---|---|
| E01-P | 4d | 0 | n/a | n/a | n/a | n/a | n/a |
| E01-P | 7d | 0 | n/a | n/a | n/a | n/a | n/a |
| E01-P | rolling 7d | 0 | n/a |  | n/a | n/a | n/a |
| E01-F | 4d | 0 | n/a | n/a | n/a | n/a | n/a |
| E01-F | 7d | 0 | n/a | n/a | n/a | n/a | n/a |
| E01-F | rolling 7d | 0 | n/a |  | n/a | n/a | n/a |
| E02-P | 4d | 0 | n/a | n/a | n/a | n/a | n/a |
| E02-P | 7d | 0 | n/a | n/a | n/a | n/a | n/a |
| E02-P | rolling 7d | 0 | n/a |  | n/a | n/a | n/a |
| E02-F | 4d | 0 | n/a | n/a | n/a | n/a | n/a |
| E02-F | 7d | 0 | n/a | n/a | n/a | n/a | n/a |
| E02-F | rolling 7d | 0 | n/a |  | n/a | n/a | n/a |
| B01-h30 | 4d | 0 | n/a | n/a | n/a | n/a | n/a |
| B01-h30 | 7d | 0 | n/a | n/a | n/a | n/a | n/a |
| B01-h30 | rolling 7d | 0 | n/a |  | n/a | n/a | n/a |
| B01-h60 | 4d | 0 | n/a | n/a | n/a | n/a | n/a |
| B01-h60 | 7d | 0 | n/a | n/a | n/a | n/a | n/a |
| B01-h60 | rolling 7d | 0 | n/a |  | n/a | n/a | n/a |

## 7. Uncertainty: moving-block bootstrap of daily PnL (main scenario; preliminary)

| strategy | block | days | mean daily PnL | 95% CI total PnL | P(boot mean<=0) | p one-sided |
|---|---|---|---|---|---|---|
| E01-P | block_7d | 1 | insufficient data | 1 days / block 7 = 0 blocks < min_blocks 5 |  |  |
| E01-P | block_3d | 1 | insufficient data | 1 days / block 3 = 0 blocks < min_blocks 5 |  |  |
| E01-P | block_14d | 1 | insufficient data | 1 days / block 14 = 0 blocks < min_blocks 5 |  |  |
| E01-F | block_7d | 1 | insufficient data | 1 days / block 7 = 0 blocks < min_blocks 5 |  |  |
| E01-F | block_3d | 1 | insufficient data | 1 days / block 3 = 0 blocks < min_blocks 5 |  |  |
| E01-F | block_14d | 1 | insufficient data | 1 days / block 14 = 0 blocks < min_blocks 5 |  |  |
| E02-P | block_7d | 1 | insufficient data | 1 days / block 7 = 0 blocks < min_blocks 5 |  |  |
| E02-P | block_3d | 1 | insufficient data | 1 days / block 3 = 0 blocks < min_blocks 5 |  |  |
| E02-P | block_14d | 1 | insufficient data | 1 days / block 14 = 0 blocks < min_blocks 5 |  |  |
| E02-F | block_7d | 1 | insufficient data | 1 days / block 7 = 0 blocks < min_blocks 5 |  |  |
| E02-F | block_3d | 1 | insufficient data | 1 days / block 3 = 0 blocks < min_blocks 5 |  |  |
| E02-F | block_14d | 1 | insufficient data | 1 days / block 14 = 0 blocks < min_blocks 5 |  |  |
| B01-h30 | block_7d | 1 | insufficient data | 1 days / block 7 = 0 blocks < min_blocks 5 |  |  |
| B01-h30 | block_3d | 1 | insufficient data | 1 days / block 3 = 0 blocks < min_blocks 5 |  |  |
| B01-h30 | block_14d | 1 | insufficient data | 1 days / block 14 = 0 blocks < min_blocks 5 |  |  |
| B01-h60 | block_7d | 1 | insufficient data | 1 days / block 7 = 0 blocks < min_blocks 5 |  |  |
| B01-h60 | block_3d | 1 | insufficient data | 1 days / block 3 = 0 blocks < min_blocks 5 |  |  |
| B01-h60 | block_14d | 1 | insufficient data | 1 days / block 14 = 0 blocks < min_blocks 5 |  |  |

Holm correction across the 4 pre-registered candidates (7-day blocks):

| candidate | p | p Holm | reject H0 (mean<=0) at 5% |
|---|---|---|---|
| E01-P | n/a | n/a | False |
| E01-F | n/a | n/a | False |
| E02-P | n/a | n/a | False |
| E02-F | n/a | n/a | False |

No winner is declared from a single window; this report does not approve any demo or live use.

## 8. Event study (mechanism check, not a trading result)

Forward log returns from the 1m open at decision time; pooled across symbols (ALL).

| group | h (min) | n | mean bps | median bps | share > 0 | naive t |
|---|---|---|---|---|---|---|
| E01-P | 15 | 1 | 10.24 | 10.24 | 1.00 | n/a |
| E01-P | 30 | 1 | 54.87 | 54.87 | 1.00 | n/a |
| E01-P | 60 | 1 | 45.20 | 45.20 | 1.00 | n/a |
| E01-F | 15 | 1 | 10.24 | 10.24 | 1.00 | n/a |
| E01-F | 30 | 1 | 54.87 | 54.87 | 1.00 | n/a |
| E01-F | 60 | 1 | 45.20 | 45.20 | 1.00 | n/a |
| E02-P | 15 | 2 | -49.00 | -49.00 | 0.00 | -5.06 |
| E02-P | 30 | 2 | -37.95 | -37.95 | 0.00 | -4.88 |
| E02-P | 60 | 2 | 17.35 | 17.35 | 1.00 | 1.26 |
| E02-F | 15 | 2 | -49.00 | -49.00 | 0.00 | -5.06 |
| E02-F | 30 | 2 | -37.95 | -37.95 | 0.00 | -4.88 |
| E02-F | 60 | 2 | 17.35 | 17.35 | 1.00 | 1.26 |
| background_all_5m | 15 | 852 | 0.39 | 1.58 | 0.55 | 0.73 |
| background_all_5m | 30 | 843 | 0.86 | 1.07 | 0.54 | 1.19 |
| background_all_5m | 60 | 825 | 1.45 | 2.42 | 0.55 | 1.38 |

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

Ledger reconciliation (main scenario): E01-P: OK (1 trades), E01-F: OK (1 trades), E02-P: OK (1 trades), E02-F: OK (1 trades), B01-h30: OK (3 trades), B01-h60: OK (2 trades)
