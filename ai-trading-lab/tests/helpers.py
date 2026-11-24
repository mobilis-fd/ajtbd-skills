import numpy as np
import pandas as pd

from src.evaluation.engine import Bars, ExecParams, Filters, RiskParams

T0 = pd.Timestamp("2026-01-05T00:00:00Z")


def make_1m(ohlc, start=T0, missing=()):
    """ohlc: list of (o,h,l,c). Returns 1m DataFrame; minutes listed in `missing` are dropped."""
    rows = []
    for i, (o, h, l, c) in enumerate(ohlc):
        if i in missing:
            continue
        rows.append({"open_time": start + pd.Timedelta(minutes=i), "open": o, "high": h, "low": l, "close": c})
    return pd.DataFrame(rows)


def flat_bars(n, price=100.0, start=T0, missing=()):
    return make_1m([(price, price, price, price)] * n, start, missing)


def bars_dict(dfs: dict, start=T0, n=None):
    n = n or max(len(d) for d in dfs.values()) + 1000
    end = start + pd.Timedelta(minutes=n)
    return {s: Bars(d, start, end) for s, d in dfs.items()}


def sig(symbol, decision, priority=0, strategy="TEST"):
    return {"strategy": strategy, "symbol": symbol, "priority": priority,
            "signal_open_time": decision - pd.Timedelta(minutes=5), "decision_time": decision}


def sigs(*rows):
    return pd.DataFrame(list(rows))


def ex(hold=30, fee=0.001, slip=0.00025, delay=0, tick=0.0, step=0.0, min_notional=0.0, symbols=("BTCUSDT", "ETHUSDT")):
    return ExecParams(hold_minutes=hold, fee=fee, slip=slip, delay_minutes=delay,
                      filters={s: Filters(tick, step, min_notional) for s in symbols})


def risk(enabled=True):
    return RiskParams(enabled=enabled)


def kline_rows(start_us: int, n: int, unit="us", price=100.0):
    mult = 1 if unit == "us" else 1 / 1000
    lines = []
    for i in range(n):
        ot = int((start_us + i * 60_000_000) * mult)
        ct = int((start_us + (i + 1) * 60_000_000) * mult) - 1
        lines.append(f"{ot},{price},{price+1},{price-1},{price+0.5},10.0,{ct},1000.0,42,4.0,400.0,0")
    return "\n".join(lines) + "\n"
