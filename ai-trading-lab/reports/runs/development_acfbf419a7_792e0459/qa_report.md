# QA report

## Data QA (from `validate-data`)

- BTCUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}
- ETHUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}
- SOLUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}

## Ledger reconciliation (independent recomputation)

- E01-P: OK; trades 81; issues []
- E01-F: OK; trades 79; issues []
- E02-P: OK; trades 103; issues []
- E02-F: OK; trades 94; issues []
- B01-h30: OK; trades 69; issues []
- B01-h60: OK; trades 70; issues []

## Manual trade checks (raw 1m bars printed for hand verification)

```
Trade B01-h30 ETHUSDT signal candle open 2025-11-03 02:20:00+00:00 -> decision 2025-11-03 02:25:00+00:00
  entry bar 2025-11-03 02:25:00+00:00: raw open 3832.16; x(1+0.00025) rounded up to tick = fill 3833.12
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.013; notional_in = 49.83056000; fee_in = 0.04983056
  stop = fill*(1-0.006) = 3810.1213; target = fill*(1+0.009) = 3867.6181
  exit stop at 2025-11-03 02:31:00+00:00: raw 3810.1213; x(1-0.00025) rounded down = fill 3809.16
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = -0.41082964 (ledger: -0.41082964)
  raw 1m bars (open_time, open, high, low, close):
    2025-11-03 02:24:00+00:00  3830.91  3832.44  3830.22  3832.17
    2025-11-03 02:25:00+00:00  3832.16  3833.65  3830.07  3830.95
    2025-11-03 02:26:00+00:00  3830.96  3831.83  3826.83  3826.83
    2025-11-03 02:27:00+00:00  3826.84  3827.15  3817.7  3819.99
    2025-11-03 02:28:00+00:00  3820  3820  3812.03  3816.13
    2025-11-03 02:29:00+00:00  3816.13  3816.88  3813.76  3813.76
    2025-11-03 02:30:00+00:00  3813.77  3813.77  3806.99  3807
    2025-11-03 02:31:00+00:00  3807  3810  3802.92  3804.21
```

```
Trade B01-h30 SOLUSDT signal candle open 2025-11-03 16:05:00+00:00 -> decision 2025-11-03 16:10:00+00:00
  entry bar 2025-11-03 16:10:00+00:00: raw open 166.69; x(1+0.00025) rounded up to tick = fill 166.74
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.299; notional_in = 49.85526000; fee_in = 0.04985526
  stop = fill*(1-0.006) = 165.73956; target = fill*(1+0.009) = 168.24066
  exit target at 2025-11-03 16:14:00+00:00: raw 168.24066; x(1-0.00025) rounded down = fill 168.19
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = 0.33340593 (ledger: 0.33340593)
  raw 1m bars (open_time, open, high, low, close):
    2025-11-03 16:09:00+00:00  166.18  166.76  166.18  166.68
    2025-11-03 16:10:00+00:00  166.69  167.1  166.37  167.09
    2025-11-03 16:11:00+00:00  167.1  168.05  166.88  167.78
    2025-11-03 16:12:00+00:00  167.78  168.2  167.77  168.04
    2025-11-03 16:13:00+00:00  168.05  168.53  167.79  168.32
    2025-11-03 16:14:00+00:00  168.32  168.6  168.03  168.18
```

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
