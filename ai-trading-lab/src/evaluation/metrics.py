"""Performance metrics computed from the trade ledger and the 1m mark-to-market equity."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _r(x, nd=6):
    if x is None:
        return None
    if isinstance(x, (float, np.floating)):
        if not np.isfinite(x):
            return None
        return round(float(x), nd)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def daily_pnl(equity: pd.Series, initial: float) -> pd.Series:
    """PnL per UTC day from end-of-day mark-to-market equity (equity stamped at bar close)."""
    eod = equity.groupby((equity.index - pd.Timedelta(microseconds=1)).floor("D")).last()
    prev = eod.shift(1).fillna(initial)
    return (eod - prev).rename("pnl")


def profit_factor(net: pd.Series) -> tuple[float | None, str]:
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    if len(net) == 0:
        return None, "undefined: no trades"
    if losses == 0:
        return None, "undefined: no losing trades (would be infinite)"
    return float(wins / losses), "ok"


def trade_stats(t: pd.DataFrame) -> dict:
    if t is None or len(t) == 0:
        return {"n_trades": 0, "net_pnl": 0.0, "gross_pnl": 0.0, "fees": 0.0, "slippage_cost": 0.0,
                "win_rate": None, "expectancy": None, "profit_factor": None, "profit_factor_note": "undefined: no trades",
                "avg_win": None, "avg_loss": None}
    pf, note = profit_factor(t["net_pnl"])
    return {
        "n_trades": int(len(t)),
        "net_pnl": _r(t["net_pnl"].sum()),
        "gross_pnl": _r(t["gross_pnl"].sum()),
        "fees": _r(t["fees"].sum()),
        "slippage_cost": _r(t["slippage_cost"].sum()),
        "win_rate": _r((t["net_pnl"] > 0).mean()),
        "expectancy": _r(t["net_pnl"].mean()),
        "profit_factor": _r(pf), "profit_factor_note": note,
        "avg_win": _r(t.loc[t["net_pnl"] > 0, "net_pnl"].mean()) if (t["net_pnl"] > 0).any() else None,
        "avg_loss": _r(t.loc[t["net_pnl"] < 0, "net_pnl"].mean()) if (t["net_pnl"] < 0).any() else None,
    }


def compute_metrics(trades: pd.DataFrame, rejections: pd.DataFrame, equity: pd.Series, initial: float,
                    seg_start: pd.Timestamp, seg_end: pd.Timestamp, windows=(4, 7), rolling_days=7,
                    ann_days=365) -> dict:
    m = trade_stats(trades)
    final = float(equity.iloc[-1]) if len(equity) else initial
    m["final_equity"] = _r(final)
    m["return_pct"] = _r(100 * (final - initial) / initial)
    dd = equity - equity.cummax()
    m["max_drawdown_usdt"] = _r(-dd.min())
    m["max_drawdown_pct"] = _r(-100 * (dd / equity.cummax()).min())
    n_min = len(equity)
    if len(trades):
        held = ((trades["exit_time"] - trades["entry_time"]).dt.total_seconds() / 60).sum()
        m["exposure_pct_time"] = _r(100 * held / n_min)
        m["turnover_x_initial"] = _r((trades["notional_in"].sum() + trades["notional_out"].sum()) / initial)
        m["exit_reasons"] = {k: int(v) for k, v in trades["exit_reason"].value_counts().sort_index().items()}
        m["uncertain_gap_trades"] = int(trades["uncertain_gap"].sum())
        m["conservative_gap_scenario_net_pnl"] = _r(trades["net_pnl"].sum() + trades["conservative_net_delta"].sum())
        m["avg_hold_minutes"] = _r(trades["hold_minutes_actual"].mean())
    else:
        m.update(exposure_pct_time=0.0, turnover_x_initial=0.0, exit_reasons={}, uncertain_gap_trades=0,
                 conservative_gap_scenario_net_pnl=0.0, avg_hold_minutes=None)
    m["rejected_signals"] = ({k: int(v) for k, v in rejections["reason"].value_counts().sort_index().items()}
                             if rejections is not None and len(rejections) else {})
    dp = daily_pnl(equity, initial)
    m["n_days"] = int(len(dp))
    prev_eq = (initial + dp.cumsum().shift(1).fillna(0))
    dr = dp / prev_eq
    if len(dr) >= 2 and dr.std(ddof=1) > 0:
        m["sharpe_daily_ann"] = _r(dr.mean() / dr.std(ddof=1) * math.sqrt(ann_days))
    else:
        m["sharpe_daily_ann"] = None
    downside = np.sqrt((np.minimum(dr, 0) ** 2).mean()) if len(dr) else 0
    m["sortino_daily_ann"] = _r(dr.mean() / downside * math.sqrt(ann_days)) if downside > 0 else None
    m["windows"] = {}
    for w in windows:
        m["windows"][f"{w}d"] = window_table(equity, trades, initial, seg_start, seg_end, w)["summary"]
    roll = dp.rolling(rolling_days, min_periods=rolling_days).sum().dropna()
    m[f"rolling_{rolling_days}d_pnl"] = ({"n": int(len(roll)), "min": _r(roll.min()), "median": _r(roll.median()),
                                         "max": _r(roll.max()), "share_positive": _r((roll > 0).mean())}
                                        if len(roll) else {"n": 0})
    return m


def window_table(equity: pd.Series, trades: pd.DataFrame, initial: float, seg_start, seg_end, days: int) -> dict:
    """Non-overlapping windows of `days` from the segment start; last partial window flagged."""
    edges = list(pd.date_range(seg_start, seg_end, freq=f"{days}D"))
    if edges[-1] < seg_end:
        edges.append(seg_end)
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        e_a = initial if a == seg_start else float(equity.loc[:a].iloc[-1])
        e_b = float(equity.loc[:b].iloc[-1])
        n = int(((trades["entry_time"] >= a) & (trades["entry_time"] < b)).sum()) if len(trades) else 0
        rows.append({"start": str(a), "end": str(b), "complete": (b - a) == pd.Timedelta(days=days),
                     "pnl": round(e_b - e_a, 6), "n_trades": n})
    full = [r for r in rows if r["complete"]]
    summ = {"n_windows_complete": len(full),
            "share_positive": _r(np.mean([r["pnl"] > 0 for r in full])) if full else None,
            "share_zero_trades": _r(np.mean([r["n_trades"] == 0 for r in full])) if full else None,
            "min_pnl": _r(min(r["pnl"] for r in full)) if full else None,
            "median_pnl": _r(float(np.median([r["pnl"] for r in full]))) if full else None,
            "max_pnl": _r(max(r["pnl"] for r in full)) if full else None}
    return {"rows": rows, "summary": summ}


def group_stats(trades: pd.DataFrame, by: str) -> dict:
    if len(trades) == 0:
        return {}
    return {str(k): trade_stats(g) for k, g in trades.groupby(by, sort=True)}
