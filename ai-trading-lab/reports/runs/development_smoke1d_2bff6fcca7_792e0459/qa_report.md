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
