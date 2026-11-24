# QA report

## Data QA (from `validate-data`)

- BTCUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}
- ETHUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}
- SOLUSDT: rows 535680, missing minutes 0 (completeness 1.000000), dup open_time 0, OHLC violations 0, taker>total 0, neg volume 0, bad close_time 0, units {'us': 535680}, zero-volume rows 0, clean log {'conflicting_duplicates_dropped': 0, 'exact_duplicates_dropped': 0, 'invalid_rows_dropped': 0}

## Ledger reconciliation (independent recomputation)

- E01-P: OK; trades 95; issues []
- E01-F: OK; trades 66; issues []
- E02-P: OK; trades 93; issues []
- E02-F: OK; trades 102; issues []
- B01-h30: OK; trades 63; issues []
- B01-h60: OK; trades 60; issues []

## Manual trade checks (raw 1m bars printed for hand verification)

```
Trade B01-h30 ETHUSDT signal candle open 2026-06-08 04:45:00+00:00 -> decision 2026-06-08 04:50:00+00:00
  entry bar 2026-06-08 04:50:00+00:00: raw open 1662.69; x(1+0.00025) rounded up to tick = fill 1663.11
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.03; notional_in = 49.89330000; fee_in = 0.04989330
  stop = fill*(1-0.006) = 1653.1313; target = fill*(1+0.009) = 1678.078
  exit stop at 2026-06-08 05:08:00+00:00: raw 1653.1313; x(1-0.00025) rounded down = fill 1652.71
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = -0.41147460 (ledger: -0.41147460)
  raw 1m bars (open_time, open, high, low, close):
    2026-06-08 04:49:00+00:00  1661.59  1664.27  1661.55  1662.69
    2026-06-08 04:50:00+00:00  1662.69  1664.54  1662.11  1662.11
    2026-06-08 04:51:00+00:00  1662.11  1662.11  1660.33  1661.86
    2026-06-08 04:52:00+00:00  1661.85  1664.4  1661.72  1661.73
    2026-06-08 04:53:00+00:00  1661.73  1661.91  1660.81  1661.66
    2026-06-08 04:54:00+00:00  1661.66  1661.77  1659.64  1660.71
    2026-06-08 05:03:00+00:00  1659.87  1659.87  1657.73  1659.07
    2026-06-08 05:04:00+00:00  1659.06  1659.48  1657.49  1657.8
    2026-06-08 05:05:00+00:00  1657.81  1658.02  1656.31  1656.31
    2026-06-08 05:06:00+00:00  1656.31  1656.31  1653.8  1654.4
    2026-06-08 05:07:00+00:00  1654.4  1654.4  1652.86  1653.55
    2026-06-08 05:08:00+00:00  1653.55  1655.31  1653.55  1654.62
```

```
Trade B01-h30 BTCUSDT signal candle open 2026-06-20 14:15:00+00:00 -> decision 2026-06-20 14:20:00+00:00
  entry bar 2026-06-20 14:20:00+00:00: raw open 63324.7; x(1+0.00025) rounded up to tick = fill 63340.54
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.00078; notional_in = 49.40562120; fee_in = 0.04940562
  stop = fill*(1-0.006) = 62960.497; target = fill*(1+0.009) = 63910.605
  exit target at 2026-06-20 14:47:00+00:00: raw 63910.605; x(1-0.00025) rounded down = fill 63894.62
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = 0.33293898 (ledger: 0.33293898)
  raw 1m bars (open_time, open, high, low, close):
    2026-06-20 14:19:00+00:00  63280.01  63327.88  63280  63324.7
    2026-06-20 14:20:00+00:00  63324.7  63324.7  63299.99  63304
    2026-06-20 14:21:00+00:00  63304  63304.01  63292  63293.47
    2026-06-20 14:22:00+00:00  63293.47  63331.91  63293.46  63331.91
    2026-06-20 14:23:00+00:00  63331.91  63360.25  63331.9  63340.01
    2026-06-20 14:24:00+00:00  63340.01  63359.95  63340  63352
    2026-06-20 14:42:00+00:00  63412.47  63412.47  63382.5  63382.5
    2026-06-20 14:43:00+00:00  63382.25  63382.25  63360.09  63363.99
    2026-06-20 14:44:00+00:00  63364  63525  63363.99  63508
    2026-06-20 14:45:00+00:00  63508  63742.75  63496.01  63738.28
    2026-06-20 14:46:00+00:00  63738.28  64150  63721.6  63957.61
    2026-06-20 14:47:00+00:00  63957.6  63957.6  63816  63861.86
```

```
Trade B01-h30 SOLUSDT signal candle open 2026-06-09 01:05:00+00:00 -> decision 2026-06-09 01:10:00+00:00
  entry bar 2026-06-09 01:10:00+00:00: raw open 65.55; x(1+0.00025) rounded up to tick = fill 65.57
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.762; notional_in = 49.96434000; fee_in = 0.04996434
  stop = fill*(1-0.006) = 65.17658; target = fill*(1+0.009) = 66.16013
  exit time_exit at 2026-06-09 01:40:00+00:00: raw 65.92; x(1-0.00025) rounded down = fill 65.9
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = 0.15127986 (ledger: 0.15127986)
  raw 1m bars (open_time, open, high, low, close):
    2026-06-09 01:09:00+00:00  65.48  65.61  65.48  65.54
    2026-06-09 01:10:00+00:00  65.55  65.61  65.53  65.57
    2026-06-09 01:11:00+00:00  65.57  65.64  65.55  65.57
    2026-06-09 01:12:00+00:00  65.56  65.63  65.56  65.61
    2026-06-09 01:13:00+00:00  65.61  65.64  65.59  65.64
    2026-06-09 01:14:00+00:00  65.63  65.67  65.58  65.59
    2026-06-09 01:36:00+00:00  65.96  66.02  65.95  66
    2026-06-09 01:37:00+00:00  66.01  66.02  65.91  65.92
    2026-06-09 01:38:00+00:00  65.92  65.93  65.84  65.87
    2026-06-09 01:39:00+00:00  65.87  65.93  65.83  65.92
    2026-06-09 01:40:00+00:00  65.92  65.95  65.89  65.92
    2026-06-09 01:41:00+00:00  65.92  65.94  65.89  65.94
```
