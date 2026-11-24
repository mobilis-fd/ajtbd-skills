"""Independent re-computation of PnL from the trade ledger and wallet reconciliation."""
from __future__ import annotations

import math

import pandas as pd


def reconcile(trades: pd.DataFrame, initial: float, fee: float, filters: dict, tol: float = 1e-7) -> dict:
    issues = []
    cash = initial
    for i, t in enumerate(trades.sort_values("entry_minute").itertuples(index=False)):
        if abs(t.cash_before - cash) > tol:
            issues.append(f"trade {i}: cash chain break {t.cash_before} vs {cash}")
        notional_in = t.qty * t.fill_entry
        notional_out = t.qty * t.fill_exit
        net = notional_out * (1 - fee) - notional_in * (1 + fee)
        if abs(net - t.net_pnl) > tol:
            issues.append(f"trade {i}: net pnl mismatch {net} vs {t.net_pnl}")
        if notional_in * (1 + fee) > t.cash_before + tol:
            issues.append(f"trade {i}: overdraft")
        f = filters.get(t.symbol)
        if f is not None and f.step:
            if abs(t.qty / f.step - round(t.qty / f.step)) > 1e-6:
                issues.append(f"trade {i}: qty not multiple of step")
            for p in (t.fill_entry, t.fill_exit):
                if abs(p / f.tick - round(p / f.tick)) > 1e-6:
                    issues.append(f"trade {i}: price not multiple of tick")
            if notional_in + 1e-9 < f.min_notional:
                issues.append(f"trade {i}: below minNotional")
        # conservative rounding direction
        if t.fill_entry + 1e-12 < t.raw_entry:
            issues.append(f"trade {i}: entry fill better than raw price")
        if t.fill_exit > t.raw_exit + 1e-12:
            issues.append(f"trade {i}: exit fill better than raw price")
        gross = t.qty * (t.raw_exit - t.raw_entry)
        if abs(gross - t.fees - t.slippage_cost - t.net_pnl) > tol:
            issues.append(f"trade {i}: gross - fees - slippage != net")
        cash = cash - notional_in * (1 + fee) + notional_out * (1 - fee)
        if cash < -tol:
            issues.append(f"trade {i}: negative cash")
    return {"n_trades": int(len(trades)), "recomputed_final_cash": round(cash, 8),
            "sum_net_pnl": round(float(trades["net_pnl"].sum()) if len(trades) else 0.0, 8),
            "ok": not issues and abs(cash - initial - (trades["net_pnl"].sum() if len(trades) else 0)) < 1e-6,
            "issues": issues[:50]}


def manual_check_text(t: pd.Series, bars_df: pd.DataFrame, fee: float, slip: float) -> str:
    """Human-readable step-by-step recomputation of one trade with the raw 1m bars around it."""
    lines = [f"Trade {t['strategy']} {t['symbol']} signal candle open {t['signal_open_time']} "
             f"-> decision {t['decision_time']}",
             f"  entry bar {t['entry_time']}: raw open {t['raw_entry']:.8g}; x(1+{slip}) rounded up to tick "
             f"= fill {t['fill_entry']:.8g}",
             f"  qty = floor_step(min(50, cash/(1+fee)) / fill) = {t['qty']:.8g}; notional_in = {t['notional_in']:.8f}; "
             f"fee_in = {t['fee_in']:.8f}",
             f"  stop = fill*(1-0.006) = {t['stop_level']:.8g}; target = fill*(1+0.009) = {t['target_level']:.8g}",
             f"  exit {t['exit_reason']} at {t['exit_time']}: raw {t['raw_exit']:.8g}; x(1-{slip}) rounded down "
             f"= fill {t['fill_exit']:.8g}",
             f"  net = qty*fill_exit*(1-fee) - qty*fill_entry*(1+fee) = "
             f"{t['qty'] * t['fill_exit'] * (1 - fee) - t['qty'] * t['fill_entry'] * (1 + fee):.8f} "
             f"(ledger: {t['net_pnl']:.8f})",
             "  raw 1m bars (open_time, open, high, low, close):"]
    for r in bars_df.itertuples(index=False):
        lines.append(f"    {r.open_time}  {r.open:.8g}  {r.high:.8g}  {r.low:.8g}  {r.close:.8g}")
    return "\n".join(lines)
