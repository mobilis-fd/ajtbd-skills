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
Trade E01-F ETHUSDT signal candle open 2026-06-12 15:50:00+00:00 -> decision 2026-06-12 15:55:00+00:00
  entry bar 2026-06-12 15:55:00+00:00: raw open 1669.64; x(1+0.00025) rounded up to tick = fill 1670.06
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.0299; notional_in = 49.93479400; fee_in = 0.04993479
  stop = fill*(1-0.006) = 1660.0396; target = fill*(1+0.009) = 1685.0905
  exit stop recorded at 2026-06-12 16:00:00+00:00 (intrabar stop/target = end of trigger minute; open-based exits = that bar's open): raw 1660.0396; x(1-0.00025) rounded down = fill 1659.62
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = -0.41171343 (ledger: -0.41171343)
  raw 1m bars (open_time, open, high, low, close):
    2026-06-12 15:54:00+00:00  1668.95  1670.2  1668.74  1669.62
    2026-06-12 15:55:00+00:00  1669.64  1669.64  1665.54  1665.68
    2026-06-12 15:56:00+00:00  1665.68  1666.28  1662.08  1663.72
    2026-06-12 15:57:00+00:00  1663.72  1664.1  1662.68  1663.24
    2026-06-12 15:58:00+00:00  1663.25  1663.75  1661.79  1661.85
    2026-06-12 15:59:00+00:00  1661.84  1661.84  1658.75  1660.08
    2026-06-12 16:00:00+00:00  1660.08  1663.62  1659.44  1662.73
```

```
Trade E01-F ETHUSDT signal candle open 2026-06-24 15:50:00+00:00 -> decision 2026-06-24 15:55:00+00:00
  entry bar 2026-06-24 15:55:00+00:00: raw open 1620.39; x(1+0.00025) rounded up to tick = fill 1620.8
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.0308; notional_in = 49.92064000; fee_in = 0.04992064
  stop = fill*(1-0.006) = 1611.0752; target = fill*(1+0.009) = 1635.3872
  exit target recorded at 2026-06-24 16:24:00+00:00 (intrabar stop/target = end of trigger minute; open-based exits = that bar's open): raw 1635.3872; x(1-0.00025) rounded down = fill 1634.97
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = 0.33615828 (ledger: 0.33615828)
  raw 1m bars (open_time, open, high, low, close):
    2026-06-24 15:54:00+00:00  1622.63  1622.85  1620.26  1620.4
    2026-06-24 15:55:00+00:00  1620.39  1622.13  1620.39  1620.44
    2026-06-24 15:56:00+00:00  1620.43  1620.84  1616.8  1617.32
    2026-06-24 15:57:00+00:00  1617.33  1620.26  1617.32  1620.24
    2026-06-24 15:58:00+00:00  1620.24  1620.47  1617.05  1617.43
    2026-06-24 15:59:00+00:00  1617.43  1619.12  1617.43  1618.08
    2026-06-24 16:19:00+00:00  1630.85  1632.35  1630.02  1630.64
    2026-06-24 16:20:00+00:00  1630.65  1631.51  1629.43  1629.7
    2026-06-24 16:21:00+00:00  1629.69  1629.73  1628.75  1629.02
    2026-06-24 16:22:00+00:00  1629  1632.97  1628.26  1632.7
    2026-06-24 16:23:00+00:00  1632.7  1636.08  1632.09  1633.74
    2026-06-24 16:24:00+00:00  1633.75  1634.58  1632.58  1633.09
```

```
Trade E01-F ETHUSDT signal candle open 2026-06-08 12:05:00+00:00 -> decision 2026-06-08 12:10:00+00:00
  entry bar 2026-06-08 12:10:00+00:00: raw open 1674.49; x(1+0.00025) rounded up to tick = fill 1674.91
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.0298; notional_in = 49.91231800; fee_in = 0.04991232
  stop = fill*(1-0.006) = 1664.8605; target = fill*(1+0.009) = 1689.9842
  exit time_exit recorded at 2026-06-08 12:40:00+00:00 (intrabar stop/target = end of trigger minute; open-based exits = that bar's open): raw 1684.39; x(1-0.00025) rounded down = fill 1683.96
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = 0.16959567 (ledger: 0.16959567)
  raw 1m bars (open_time, open, high, low, close):
    2026-06-08 12:09:00+00:00  1674.19  1675.11  1673.46  1674.49
    2026-06-08 12:10:00+00:00  1674.49  1675.1  1673.47  1674.19
    2026-06-08 12:11:00+00:00  1674.19  1677.46  1673.36  1676.47
    2026-06-08 12:12:00+00:00  1676.47  1676.67  1675  1675.82
    2026-06-08 12:13:00+00:00  1675.81  1675.81  1674.23  1674.78
    2026-06-08 12:14:00+00:00  1674.79  1675.43  1667.46  1668.37
    2026-06-08 12:36:00+00:00  1681.05  1686.01  1680.68  1685.56
    2026-06-08 12:37:00+00:00  1685.56  1687.05  1685.01  1686.01
    2026-06-08 12:38:00+00:00  1686.01  1686.01  1682.98  1683.43
    2026-06-08 12:39:00+00:00  1683.44  1686.34  1682.99  1684.39
    2026-06-08 12:40:00+00:00  1684.39  1684.89  1683.62  1684.04
    2026-06-08 12:41:00+00:00  1684.05  1685.68  1684.05  1685.03
```

```
Trade E01-P ETHUSDT signal candle open 2026-06-10 17:30:00+00:00 -> decision 2026-06-10 17:35:00+00:00
  entry bar 2026-06-10 17:35:00+00:00: raw open 1629.64; x(1+0.00025) rounded up to tick = fill 1630.05
  qty = floor_step(min(50, cash/(1+fee)) / fill) = 0.0306; notional_in = 49.87953000; fee_in = 0.04987953
  stop = fill*(1-0.006) = 1620.2697; target = fill*(1+0.009) = 1644.7204
  exit risk_exit_daily recorded at 2026-06-10 17:36:00+00:00 (intrabar stop/target = end of trigger minute; open-based exits = that bar's open): raw 1627.01; x(1-0.00025) rounded down = fill 1626.6
  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = -0.20522349 (ledger: -0.20522349)
  raw 1m bars (open_time, open, high, low, close):
    2026-06-10 17:34:00+00:00  1629.14  1631.75  1628.64  1629.65
    2026-06-10 17:35:00+00:00  1629.64  1630.48  1626.78  1627
    2026-06-10 17:36:00+00:00  1627.01  1627.85  1624.87  1625.12
    2026-06-10 17:37:00+00:00  1625.12  1627.53  1625.12  1627.02
```
