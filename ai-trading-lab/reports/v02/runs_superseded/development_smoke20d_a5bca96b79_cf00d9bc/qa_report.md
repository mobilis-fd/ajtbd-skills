# MH-v0.2 run QA

Ledger reconciliation failures: none

## Manual trade checks (raw 1m data printed; recompute by hand)

```
G01-B0-H60-thr0: SOLUSDT decision T=2021-10-01 00:00:00+00:00 (bar end)
  entry minute 2021-10-01 00:01:00+00:00 open=np.float64(141.54) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(141.37)
  fill_entry = ceil_tick(open*(1+0.00025)) = 141.58; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.353
  exit minute 2021-10-01 01:01:00+00:00 open=np.float64(143.11) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 143.07
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 0.4254885500; ledger 0.4254885500
  gross label from opens = 0.01109227
```

```
G01-B1-H60-thr0: ETHUSDT decision T=2021-10-01 00:30:00+00:00 (bar end)
  entry minute 2021-10-01 00:31:00+00:00 open=np.float64(3029.38) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(3024.13)
  fill_entry = ceil_tick(open*(1+0.00025)) = 3030.14; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.0165
  exit minute 2021-10-01 01:31:00+00:00 open=np.float64(3010.56) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 3009.8
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.4352690100; ledger -0.4352690100
  gross label from opens = -0.00621249
```

```
G01-B1-H60-thrc: SOLUSDT decision T=2021-10-06 10:30:00+00:00 (bar end)
  entry minute 2021-10-06 10:31:00+00:00 open=np.float64(154.31) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(154.52)
  fill_entry = ceil_tick(open*(1+0.00025)) = 154.35; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.323
  exit minute 2021-10-06 11:31:00+00:00 open=np.float64(154.31) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 154.27
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.1255242600; ledger -0.1255242600
  gross label from opens = 0.00000000
```

```
G01-X-H60-thr0: BTCUSDT decision T=2021-10-01 00:00:00+00:00 (bar end)
  entry minute 2021-10-01 00:01:00+00:00 open=np.float64(43825.73) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(43824.1)
  fill_entry = ceil_tick(open*(1+0.00025)) = 43836.69; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.00114
  exit minute 2021-10-01 01:01:00+00:00 open=np.float64(43669.06) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 43658.14
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.3032911062; ledger -0.3032911062
  gross label from opens = -0.00357484
```

```
G01-X-H60-thrc: SOLUSDT decision T=2021-10-06 10:30:00+00:00 (bar end)
  entry minute 2021-10-06 10:31:00+00:00 open=np.float64(154.31) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(154.52)
  fill_entry = ceil_tick(open*(1+0.00025)) = 154.35; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.323
  exit minute 2021-10-06 11:31:00+00:00 open=np.float64(154.31) (time_exit, hold 60 min vs H=60)
  fill_exit = floor_tick(open*(1-0.00025)) = 154.27
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = -0.1255242600; ledger -0.1255242600
  gross label from opens = 0.00000000
```

```
H01-H120-none: BTCUSDT decision T=2021-10-01 03:00:00+00:00 (bar end)
  entry minute 2021-10-01 03:01:00+00:00 open=np.float64(43420.01) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(43379.01)
  fill_entry = ceil_tick(open*(1+0.00025)) = 43430.87; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.00115
  exit minute 2021-10-01 05:01:00+00:00 open=np.float64(43628.88) (time_exit, hold 120 min vs H=120)
  fill_exit = floor_tick(open*(1-0.00025)) = 43617.97
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 0.1150588340; ledger 0.1150588340
  gross label from opens = 0.00481045
```

```
H01-H120-common: BTCUSDT decision T=2021-10-01 03:00:00+00:00 (bar end)
  entry minute 2021-10-01 03:01:00+00:00 open=np.float64(43420.01) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(43379.01)
  fill_entry = ceil_tick(open*(1+0.00025)) = 43430.87; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.00115
  exit minute 2021-10-01 05:01:00+00:00 open=np.float64(43628.88) (time_exit, hold 120 min vs H=120)
  fill_exit = floor_tick(open*(1-0.00025)) = 43617.97
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 0.1150588340; ledger 0.1150588340
  gross label from opens = 0.00481045
```

```
H02-H720-none: BTCUSDT decision T=2021-10-01 00:00:00+00:00 (bar end)
  entry minute 2021-10-01 00:01:00+00:00 open=np.float64(43825.73) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(43824.1)
  fill_entry = ceil_tick(open*(1+0.00025)) = 43836.69; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.00114
  exit minute 2021-10-01 12:01:00+00:00 open=np.float64(47477.13) (time_exit, hold 720 min vs H=720)
  fill_exit = floor_tick(open*(1-0.00025)) = 47465.26
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 4.0324855770; ledger 4.0324855770
  gross label from opens = 0.08331635
```

```
H02-H720-common: BTCUSDT decision T=2021-10-01 00:00:00+00:00 (bar end)
  entry minute 2021-10-01 00:01:00+00:00 open=np.float64(43825.73) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(43824.1)
  fill_entry = ceil_tick(open*(1+0.00025)) = 43836.69; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.00114
  exit minute 2021-10-01 12:01:00+00:00 open=np.float64(47477.13) (time_exit, hold 720 min vs H=720)
  fill_exit = floor_tick(open*(1-0.00025)) = 47465.26
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 4.0324855770; ledger 4.0324855770
  gross label from opens = 0.08331635
```

```
H02-H720-c: SOLUSDT decision T=2021-10-01 00:00:00+00:00 (bar end)
  entry minute 2021-10-01 00:01:00+00:00 open=np.float64(141.54) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(141.37)
  fill_entry = ceil_tick(open*(1+0.00025)) = 141.58; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.353
  exit minute 2021-10-01 12:01:00+00:00 open=np.float64(153.58) (time_exit, hold 720 min vs H=720)
  fill_exit = floor_tick(open*(1-0.00025)) = 153.54
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 4.1177026400; ledger 4.1177026400
  gross label from opens = 0.08506429
```

```
H03-H4320-none: SOLUSDT decision T=2021-10-02 00:00:00+00:00 (bar end)
  entry minute 2021-10-02 00:01:00+00:00 open=np.float64(161.28) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(161.56)
  fill_entry = ceil_tick(open*(1+0.00025)) = 161.33; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.309
  exit minute 2021-10-05 00:01:00+00:00 open=np.float64(167.07) (time_exit, hold 4320 min vs H=4320)
  fill_exit = floor_tick(open*(1-0.00025)) = 167.02
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 1.6567498500; ledger 1.6567498500
  gross label from opens = 0.03590030
```

```
H03-H4320-common: SOLUSDT decision T=2021-10-02 00:00:00+00:00 (bar end)
  entry minute 2021-10-02 00:01:00+00:00 open=np.float64(161.28) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(161.56)
  fill_entry = ceil_tick(open*(1+0.00025)) = 161.33; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.309
  exit minute 2021-10-05 00:01:00+00:00 open=np.float64(167.07) (time_exit, hold 4320 min vs H=4320)
  fill_exit = floor_tick(open*(1-0.00025)) = 167.02
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 1.6567498500; ledger 1.6567498500
  gross label from opens = 0.03590030
```

```
H03-H4320-c: SOLUSDT decision T=2021-10-02 00:00:00+00:00 (bar end)
  entry minute 2021-10-02 00:01:00+00:00 open=np.float64(161.28) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(161.56)
  fill_entry = ceil_tick(open*(1+0.00025)) = 161.33; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.309
  exit minute 2021-10-05 00:01:00+00:00 open=np.float64(167.07) (time_exit, hold 4320 min vs H=4320)
  fill_exit = floor_tick(open*(1-0.00025)) = 167.02
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 1.6567498500; ledger 1.6567498500
  gross label from opens = 0.03590030
```

```
H03-H4320-2c: SOLUSDT decision T=2021-10-02 00:00:00+00:00 (bar end)
  entry minute 2021-10-02 00:01:00+00:00 open=np.float64(161.28) (decision T + 1 min)
  close of the decision bar's last minute (NOT used for execution) = np.float64(161.56)
  fill_entry = ceil_tick(open*(1+0.00025)) = 161.33; qty = floor_step(min(50, cash/(1+fee))/fill) = 0.309
  exit minute 2021-10-05 00:01:00+00:00 open=np.float64(167.07) (time_exit, hold 4320 min vs H=4320)
  fill_exit = floor_tick(open*(1-0.00025)) = 167.02
  net = qty*fill_exit*(1-0.001) - qty*fill_entry*(1+0.001) = 1.6567498500; ledger 1.6567498500
  gross label from opens = 0.03590030
```
