# MH-v0.2 run QA

Ledger reconciliation failures: none

## Manual trade checks (raw 1m data printed; recompute by hand)

```
G01-B0-H60-thr0: ETHUSDT decision T=2023-06-01 00:00:00+00:00 (bar end)
  entry minute 2023-06-01 00:01:00+00:00 open=np.float64(1874.81) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(1873.63)
  fill_entry = ceil_tick(open*(1+0.00025)) = 1875.28; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.0266
  exit minute 2023-06-01 01:01:00+00:00 open=np.float64(1873.42) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 1872.95
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.1616809180; ledger -0.1616809180
  gross label from opens = -0.00074141
```

```
G01-B1-H60-thr0: SOLUSDT decision T=2023-01-01 00:00:00+00:00 (bar end)
  entry minute 2023-01-01 00:01:00+00:00 open=np.float64(9.98) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(9.97)
  fill_entry = ceil_tick(open*(1+0.00025)) = 9.99; qty = floor_step(min(50, cash/(1+fee))/fill) = 5.005
  exit minute 2023-01-01 01:01:00+00:00 open=np.float64(9.99) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 9.98
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.1499998500; ledger -0.1499998500
  gross label from opens = 0.00100200
```

```
G01-B1-H60-thrc: SOLUSDT decision T=2023-01-02 08:00:00+00:00 (bar end)
  entry minute 2023-01-02 08:01:00+00:00 open=np.float64(11.06) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(11.09)
  fill_entry = ceil_tick(open*(1+0.00025)) = 11.07; qty = floor_step(min(50, cash/(1+fee))/fill) = 4.516
  exit minute 2023-01-02 09:01:00+00:00 open=np.float64(11.18) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 11.17
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 0.3511641600; ledger 0.3511641600
  gross label from opens = 0.01084991
```

```
G01-B1-H60-thr2c: SOLUSDT decision T=2023-07-14 01:30:00+00:00 (bar end)
  entry minute 2023-07-14 01:31:00+00:00 open=np.float64(29.49) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(29.67)
  fill_entry = ceil_tick(open*(1+0.00025)) = 29.5; qty = floor_step(min(50, cash/(1+fee))/fill) = 1.694
  exit minute 2023-07-14 02:31:00+00:00 open=np.float64(28.96) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 28.95
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -1.0307143000; ledger -1.0307143000
  gross label from opens = -0.01797219
```

```
G01-X-H60-thr0: SOLUSDT decision T=2023-01-01 01:00:00+00:00 (bar end)
  entry minute 2023-01-01 01:01:00+00:00 open=np.float64(9.99) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(9.99)
  fill_entry = ceil_tick(open*(1+0.00025)) = 10.0; qty = floor_step(min(50, cash/(1+fee))/fill) = 5.0
  exit minute 2023-01-01 02:01:00+00:00 open=np.float64(10.03) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 10.02
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.0001000000; ledger -0.0001000000
  gross label from opens = 0.00400400
```

```
G01-X-H60-thrc: ETHUSDT decision T=2023-01-02 07:30:00+00:00 (bar end)
  entry minute 2023-01-02 07:31:00+00:00 open=np.float64(1213.66) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(1212.95)
  fill_entry = ceil_tick(open*(1+0.00025)) = 1213.97; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.0411
  exit minute 2023-01-02 08:31:00+00:00 open=np.float64(1215.55) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 1215.24
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.0476435310; ledger -0.0476435310
  gross label from opens = 0.00155727
```

```
G01-X-H60-thr2c: ETHUSDT decision T=2023-01-09 02:30:00+00:00 (bar end)
  entry minute 2023-01-09 02:31:00+00:00 open=np.float64(1305.27) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(1303.84)
  fill_entry = ceil_tick(open*(1+0.00025)) = 1305.6; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.0382
  exit minute 2023-01-09 03:31:00+00:00 open=np.float64(1306.47) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 1306.14
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.0791404680; ledger -0.0791404680
  gross label from opens = 0.00091935
```

```
H01-H120-none: SOLUSDT decision T=2023-01-01 05:00:00+00:00 (bar end)
  entry minute 2023-01-01 05:01:00+00:00 open=np.float64(9.83) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(9.84)
  fill_entry = ceil_tick(open*(1+0.00025)) = 9.84; qty = floor_step(min(50, cash/(1+fee))/fill) = 5.081
  exit minute 2023-01-01 07:01:00+00:00 open=np.float64(9.8) (time_exit, hold 120 min vs H=120)
  fill_exit = floor_tick(open*(1-0.00025)) = 9.79
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.3537900300; ledger -0.3537900300
  gross label from opens = -0.00305188
```

```
H01-H120-common: SOLUSDT decision T=2023-01-01 05:00:00+00:00 (bar end)
  entry minute 2023-01-01 05:01:00+00:00 open=np.float64(9.83) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(9.84)
  fill_entry = ceil_tick(open*(1+0.00025)) = 9.84; qty = floor_step(min(50, cash/(1+fee))/fill) = 5.081
  exit minute 2023-01-01 07:01:00+00:00 open=np.float64(9.8) (time_exit, hold 120 min vs H=120)
  fill_exit = floor_tick(open*(1-0.00025)) = 9.79
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.3537900300; ledger -0.3537900300
  gross label from opens = -0.00305188
```

```
H02-H720-none: SOLUSDT decision T=2023-01-01 12:00:00+00:00 (bar end)
  entry minute 2023-01-01 12:01:00+00:00 open=np.float64(9.92) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(9.93)
  fill_entry = ceil_tick(open*(1+0.00025)) = 9.93; qty = floor_step(min(50, cash/(1+fee))/fill) = 5.035
  exit minute 2023-01-02 00:01:00+00:00 open=np.float64(9.98) (time_exit, hold 720 min vs H=720)
  fill_exit = floor_tick(open*(1-0.00025)) = 9.97
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 0.1012035000; ledger 0.1012035000
  gross label from opens = 0.00604839
```

```
H02-H720-common: SOLUSDT decision T=2023-01-01 12:00:00+00:00 (bar end)
  entry minute 2023-01-01 12:01:00+00:00 open=np.float64(9.92) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(9.93)
  fill_entry = ceil_tick(open*(1+0.00025)) = 9.93; qty = floor_step(min(50, cash/(1+fee))/fill) = 5.035
  exit minute 2023-01-02 00:01:00+00:00 open=np.float64(9.98) (time_exit, hold 720 min vs H=720)
  fill_exit = floor_tick(open*(1-0.00025)) = 9.97
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 0.1012035000; ledger 0.1012035000
  gross label from opens = 0.00604839
```

```
H02-H720-c: SOLUSDT decision T=2023-11-01 00:00:00+00:00 (bar end)
  entry minute 2023-11-01 00:01:00+00:00 open=np.float64(38.53) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(38.4)
  fill_entry = ceil_tick(open*(1+0.00025)) = 38.54; qty = floor_step(min(50, cash/(1+fee))/fill) = 1.297
  exit minute 2023-11-01 12:01:00+00:00 open=np.float64(39.21) (time_exit, hold 720 min vs H=720)
  fill_exit = floor_tick(open*(1-0.00025)) = 39.2
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 0.7551912200; ledger 0.7551912200
  gross label from opens = 0.01764859
```

```
H02-H720-2c: SOLUSDT decision T=2024-01-01 04:00:00+00:00 (bar end)
  entry minute 2024-01-01 04:01:00+00:00 open=np.float64(103.18) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(103.07)
  fill_entry = ceil_tick(open*(1+0.00025)) = 103.21; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.484
  exit minute 2024-01-01 16:01:00+00:00 open=np.float64(106.04) (time_exit, hold 720 min vs H=720)
  fill_exit = floor_tick(open*(1-0.00025)) = 106.01
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 1.2539375200; ledger 1.2539375200
  gross label from opens = 0.02771855
```

```
H03-H4320-none: BTCUSDT decision T=2023-01-05 00:00:00+00:00 (bar end)
  entry minute 2023-01-05 00:01:00+00:00 open=np.float64(16856.71) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(16850.36)
  fill_entry = ceil_tick(open*(1+0.00025)) = 16860.93; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.00296
  exit minute 2023-01-08 00:01:00+00:00 open=np.float64(16947.53) (time_exit, hold 4320 min vs H=4320)
  fill_exit = floor_tick(open*(1-0.00025)) = 16943.29
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 0.1437251088; ledger 0.1437251088
  gross label from opens = 0.00538777
```

```
H03-H4320-common: ETHUSDT decision T=2023-03-02 00:00:00+00:00 (bar end)
  entry minute 2023-03-02 00:01:00+00:00 open=np.float64(1665.21) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(1665.22)
  fill_entry = ceil_tick(open*(1+0.00025)) = 1665.63; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.03
  exit minute 2023-03-05 00:01:00+00:00 open=np.float64(1566.47) (time_exit, hold 4320 min vs H=4320)
  fill_exit = floor_tick(open*(1-0.00025)) = 1566.07
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -3.0837510000; ledger -3.0837510000
  gross label from opens = -0.05929582
```

```
H03-H4320-c: ETHUSDT decision T=2023-03-02 00:00:00+00:00 (bar end)
  entry minute 2023-03-02 00:01:00+00:00 open=np.float64(1665.21) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(1665.22)
  fill_entry = ceil_tick(open*(1+0.00025)) = 1665.63; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.03
  exit minute 2023-03-05 00:01:00+00:00 open=np.float64(1566.47) (time_exit, hold 4320 min vs H=4320)
  fill_exit = floor_tick(open*(1-0.00025)) = 1566.07
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -3.0837510000; ledger -3.0837510000
  gross label from opens = -0.05929582
```

```
H03-H4320-2c: ETHUSDT decision T=2023-03-02 00:00:00+00:00 (bar end)
  entry minute 2023-03-02 00:01:00+00:00 open=np.float64(1665.21) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(1665.22)
  fill_entry = ceil_tick(open*(1+0.00025)) = 1665.63; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.03
  exit minute 2023-03-05 00:01:00+00:00 open=np.float64(1566.47) (time_exit, hold 4320 min vs H=4320)
  fill_exit = floor_tick(open*(1-0.00025)) = 1566.07
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -3.0837510000; ledger -3.0837510000
  gross label from opens = -0.05929582
```
