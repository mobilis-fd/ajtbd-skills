# QA report

## Data QA (from `validate-data`)

- BTCUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}
- ETHUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}
- SOLUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}

## Ledger reconciliation (independent recomputation)

- E01-P: OK; trades 1; issues []
- E01-F: OK; trades 1; issues []
- E02-P: OK; trades 1; issues []
- E02-F: OK; trades 1; issues []
- B01-h30: OK; trades 3; issues []
- B01-h60: OK; trades 2; issues []

## Manual trade checks (raw 1m bars printed for hand verification)

```
Trade B01-h30 BTCUSDT signal candle open 2025-11-01 13:45:00+00:00 -> decision 2025-11-01 13:50:00+00:00
  entry bar 2025-11-01 13:50:00+00:00: raw open 109899.83; x(1+0.00025) rounded up to tick = fill 109927.31
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.00045; notional_in = 49.46728950; fee_in = 0.04946729
  stop = fill*(1-0.006) = 109267.75; target = fill*(1+0.009) = 110916.66
  exit time_exit at 2025-11-01 14:20:00+00:00: raw 109857.99; x(1-0.00025) rounded down = fill 109830.52
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = -0.14244652 (ledger: -0.14244652)
  raw 1m bars (open_time, open, high, low, close):
    2025-11-01 13:49:00+00:00  109899.83  109899.83  109899.82  109899.83
    2025-11-01 13:50:00+00:00  109899.83  109950.84  109899.82  109933.9
    2025-11-01 13:51:00+00:00  109933.89  109937.67  109916.36  109937.67
    2025-11-01 13:52:00+00:00  109937.66  109969.53  109937.66  109969.53
    2025-11-01 13:53:00+00:00  109969.53  109978  109969.52  109978
    2025-11-01 13:54:00+00:00  109977.99  109992.14  109974.84  109974.85
    2025-11-01 14:16:00+00:00  109759.89  109759.89  109742.11  109752.59
    2025-11-01 14:17:00+00:00  109752.59  109846.1  109748.25  109839.48
    2025-11-01 14:18:00+00:00  109839.48  109854.19  109832.88  109832.89
    2025-11-01 14:19:00+00:00  109832.88  109864.2  109832.88  109857.99
    2025-11-01 14:20:00+00:00  109857.99  109864.63  109845.63  109845.64
    2025-11-01 14:21:00+00:00  109845.64  109845.64  109828.76  109845.01
```
