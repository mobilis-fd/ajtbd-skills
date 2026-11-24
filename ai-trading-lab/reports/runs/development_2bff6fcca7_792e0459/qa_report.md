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
Trade E01-F SOLUSDT signal candle open 2025-11-03 03:55:00+00:00 -> decision 2025-11-03 04:00:00+00:00
  entry bar 2025-11-03 04:00:00+00:00: raw open 177.56; x(1+0.00025) rounded up to tick = fill 177.61
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.281; notional_in = 49.90841000; fee_in = 0.04990841
  stop = fill*(1-0.006) = 176.54434; target = fill*(1+0.009) = 179.20849
  exit stop recorded at 2025-11-03 04:07:00+00:00 (intrabar stop/target = end of trigger minute; open-based exits = that bar's open): raw 176.54434; x(1-0.00025) rounded down = fill 176.5
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = -0.41141491 (ledger: -0.41141491)
  raw 1m bars (open_time, open, high, low, close):
    2025-11-03 03:59:00+00:00  177.48  177.72  177.45  177.57
    2025-11-03 04:00:00+00:00  177.56  177.57  177.23  177.28
    2025-11-03 04:01:00+00:00  177.29  177.29  176.95  177.1
    2025-11-03 04:02:00+00:00  177.09  177.51  177.07  177.32
    2025-11-03 04:03:00+00:00  177.32  177.5  177.15  177.22
    2025-11-03 04:04:00+00:00  177.22  177.33  177.11  177.15
    2025-11-03 04:05:00+00:00  177.15  177.15  176.65  176.97
    2025-11-03 04:06:00+00:00  176.96  177.02  176  176.01
    2025-11-03 04:07:00+00:00  176.01  176.84  175.88  176.77
```

```
Trade E01-F ETHUSDT signal candle open 2025-11-03 16:05:00+00:00 -> decision 2025-11-03 16:10:00+00:00
  entry bar 2025-11-03 16:10:00+00:00: raw open 3579.95; x(1+0.00025) rounded up to tick = fill 3580.85
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.0139; notional_in = 49.77381500; fee_in = 0.04977381
  stop = fill*(1-0.006) = 3559.3649; target = fill*(1+0.009) = 3613.0776
  exit target recorded at 2025-11-03 16:20:00+00:00 (intrabar stop/target = end of trigger minute; open-based exits = that bar's open): raw 3613.0776; x(1-0.00025) rounded down = fill 3612.17
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = 0.33536502 (ledger: 0.33536502)
  raw 1m bars (open_time, open, high, low, close):
    2025-11-03 16:09:00+00:00  3571.82  3581.36  3571.02  3579.95
    2025-11-03 16:10:00+00:00  3579.95  3584.64  3576.78  3584.64
    2025-11-03 16:11:00+00:00  3584.63  3599.08  3580  3594.98
    2025-11-03 16:12:00+00:00  3594.98  3600.29  3593.84  3597.89
    2025-11-03 16:13:00+00:00  3597.89  3609.92  3594  3604.13
    2025-11-03 16:14:00+00:00  3604.14  3612.09  3603.22  3607.94
    2025-11-03 16:15:00+00:00  3607.93  3610.29  3601.23  3603.01
    2025-11-03 16:16:00+00:00  3603.01  3603.39  3596.18  3598.28
    2025-11-03 16:17:00+00:00  3598.28  3606.26  3598.27  3605.21
    2025-11-03 16:18:00+00:00  3605.2  3612.76  3604.57  3611.36
    2025-11-03 16:19:00+00:00  3611.35  3622.5  3610.3  3621.35
    2025-11-03 16:20:00+00:00  3621.35  3627.49  3611.28  3612.65
```

```
Trade E01-F SOLUSDT signal candle open 2025-11-01 15:25:00+00:00 -> decision 2025-11-01 15:30:00+00:00
  entry bar 2025-11-01 15:30:00+00:00: raw open 185.4; x(1+0.00025) rounded up to tick = fill 185.45
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.269; notional_in = 49.88605000; fee_in = 0.04988605
  stop = fill*(1-0.006) = 184.3373; target = fill*(1+0.009) = 187.11905
  exit time_exit recorded at 2025-11-01 16:00:00+00:00 (intrabar stop/target = end of trigger minute; open-based exits = that bar's open): raw 186.42; x(1-0.00025) rounded down = fill 186.37
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = 0.14746042 (ledger: 0.14746042)
  raw 1m bars (open_time, open, high, low, close):
    2025-11-01 15:29:00+00:00  185.24  185.46  185.23  185.41
    2025-11-01 15:30:00+00:00  185.4  185.62  185.37  185.62
    2025-11-01 15:31:00+00:00  185.62  185.68  185.58  185.68
    2025-11-01 15:32:00+00:00  185.68  185.76  185.64  185.68
    2025-11-01 15:33:00+00:00  185.68  185.74  185.66  185.7
    2025-11-01 15:34:00+00:00  185.7  185.79  185.6  185.76
    2025-11-01 15:56:00+00:00  186.04  186.12  186.04  186.11
    2025-11-01 15:57:00+00:00  186.12  186.28  186.11  186.27
    2025-11-01 15:58:00+00:00  186.28  186.3  186.27  186.28
    2025-11-01 15:59:00+00:00  186.28  186.42  186.28  186.42
    2025-11-01 16:00:00+00:00  186.42  186.53  186.3  186.31
    2025-11-01 16:01:00+00:00  186.3  186.31  186.11  186.17
```

```
Trade E01-P ETHUSDT signal candle open 2025-11-04 20:20:00+00:00 -> decision 2025-11-04 20:25:00+00:00
  entry bar 2025-11-04 20:25:00+00:00: raw open 3176.89; x(1+0.00025) rounded up to tick = fill 3177.69
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.0157; notional_in = 49.88973300; fee_in = 0.04988973
  stop = fill*(1-0.006) = 3158.6239; target = fill*(1+0.009) = 3206.2892
  exit risk_exit_daily recorded at 2025-11-04 20:27:00+00:00 (intrabar stop/target = end of trigger minute; open-based exits = that bar's open): raw 3174.48; x(1-0.00025) rounded down = fill 3173.68
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = -0.16267351 (ledger: -0.16267351)
  raw 1m bars (open_time, open, high, low, close):
    2025-11-04 20:24:00+00:00  3173.75  3177.79  3166.98  3176.88
    2025-11-04 20:25:00+00:00  3176.89  3193.92  3173.12  3189.68
    2025-11-04 20:26:00+00:00  3189.67  3190.2  3172.76  3174.48
    2025-11-04 20:27:00+00:00  3174.48  3188.32  3174.48  3184.88
    2025-11-04 20:28:00+00:00  3184.89  3196.46  3184.89  3189.69
```
