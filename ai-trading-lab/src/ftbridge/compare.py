"""Compare Freqtrade backtest trades against the reference replay (signal-only scenario: Freqtrade has no
equity-based daily/total loss limit). Differences are explained, not resolved in favour of either result."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import ROOT, dumps

FT_NAME = {"MvpE01P": "E01-P", "MvpE01F": "E01-F", "MvpE02P": "E02-P", "MvpE02F": "E02-F"}


def load_ft_trades(ft_dir: Path) -> pd.DataFrame:
    from freqtrade.data.btanalysis import load_backtest_data
    parts = []
    for name in FT_NAME:
        try:
            d = load_backtest_data(ft_dir, strategy=name)
        except ValueError:
            continue
        parts.append(d.assign(strategy=name))
    return pd.concat(parts, ignore_index=True)


def latest_run(split: str) -> Path:
    runs = sorted((ROOT / "reports" / "runs").glob(f"{split}_*"), key=lambda p: p.stat().st_mtime)
    runs = [r for r in runs if "smoke" not in r.name]
    return runs[-1]


def compare(cfg: dict, split: str, ft_dir: Path, ref_run: Path | None = None) -> dict:
    ref_run = ref_run or latest_run(split)
    ref = pd.read_parquet(ref_run / "trades.parquet")
    ref = ref[ref["scenario"] == "signal_only_no_portfolio_stop"]
    ft = load_ft_trades(ft_dir)
    out = {"reference_run": str(ref_run.relative_to(ROOT)), "freqtrade_results": str(ft_dir), "strategies": {}}
    rows = []
    for ft_name, name in FT_NAME.items():
        f = ft[ft["strategy"] == ft_name].copy() if "strategy" in ft else pd.DataFrame()
        r = ref[ref["strategy"] == name].copy()
        if len(f) == 0 and len(r) == 0:
            out["strategies"][name] = {"note": "no trades in either engine"}
            continue
        f["symbol"] = f["pair"].str.replace("/", "")
        f["entry_time"] = pd.to_datetime(f["open_date"], utc=True)
        f["exit_time_ft"] = pd.to_datetime(f["close_date"], utc=True)
        m = r.merge(f[["symbol", "entry_time", "exit_time_ft", "open_rate", "close_rate", "exit_reason", "profit_abs"]]
                    .rename(columns={"exit_reason": "exit_reason_ft"}), on=["symbol", "entry_time"], how="outer",
                    indicator=True)
        both = m[m["_merge"] == "both"]
        s = {
            "ft_trades": int(len(f)), "ref_trades": int(len(r)), "matched_entries": int(len(both)),
            "only_freqtrade": int((m["_merge"] == "right_only").sum()),
            "only_reference": int((m["_merge"] == "left_only").sum()),
            "ft_net_pnl": round(float(f["profit_abs"].sum()), 6) if len(f) else 0.0,
            "ref_net_pnl_signal_only": round(float(r["net_pnl"].sum()), 6) if len(r) else 0.0,
        }
        if len(both):
            s["entry_price_abs_diff_bps_median"] = round(float((1e4 * (both["open_rate"] / both["raw_entry"] - 1)).abs().median()), 4)
            s["same_exit_time_share"] = round(float((both["exit_time_ft"] == both["exit_time"]).mean()), 4)
            s["exit_reason_pairs"] = {f"{a}|{b}": int(v) for (a, b), v in
                                      both.groupby(["exit_reason", "exit_reason_ft"]).size().items()}
            s["matched_pnl_ref"] = round(float(both["net_pnl"].sum()), 6)
            s["matched_pnl_ft"] = round(float(both["profit_abs"].sum()), 6)
        out["strategies"][name] = s
        m["strategy"] = name
        rows.append(m)
    det = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    dest = ref_run / "freqtrade_comparison"
    dest.mkdir(exist_ok=True)
    keep = [c for c in ["strategy", "symbol", "entry_time", "_merge", "exit_time", "exit_time_ft", "exit_reason",
                        "exit_reason_ft", "raw_entry", "open_rate", "raw_exit", "close_rate", "net_pnl", "profit_abs"]
            if c in det]
    det[keep].to_csv(dest / "matched_trades.csv", index=False)
    out["summary"] = out["strategies"]
    b = det[det["_merge"] == "both"].copy()
    diag = {}
    if len(b):
        b["exit_dt_min"] = (pd.to_datetime(b["exit_time_ft"], utc=True) - pd.to_datetime(b["exit_time"], utc=True)
                            ).dt.total_seconds() / 60
        b["exit_px_bps"] = 1e4 * (b["close_rate"] / b["raw_exit"] - 1)
        g = b.groupby(["exit_reason", "exit_reason_ft"])
        diag = {f"{a}|{c}": {"n": int(len(x)), "median_exit_time_diff_min": float(x["exit_dt_min"].median()),
                             "median_exit_price_diff_bps": round(float(x["exit_px_bps"].median()), 3)}
                for (a, c), x in g}
    out["exit_diagnostics_all_strategies"] = diag
    (dest / "comparison.json").write_text(dumps(out))
    L = [f"# Freqtrade vs reference replay — {split}", "",
         f"Reference: `{out['reference_run']}` scenario `signal_only_no_portfolio_stop` (Freqtrade has no equity-based "
         "daily/total limit). Freqtrade: offline markets (assumed filters), fee 0.00125/side, timeframe-detail 1m, "
         "stake 50, wallet 100; Freqtrade stops opening trades once free balance < stake (≈ −50 USDT).", "",
         "| strategy | FT trades | ref trades | matched entries | only FT | only ref | entry px diff (median bps) | "
         "same exit time | FT net | ref net (signal-only) | matched FT net | matched ref net |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in out["strategies"].items():
        if "ft_trades" not in v:
            continue
        L.append(f"| {k} | {v['ft_trades']} | {v['ref_trades']} | {v['matched_entries']} | {v['only_freqtrade']} | "
                 f"{v['only_reference']} | {v.get('entry_price_abs_diff_bps_median')} | {v.get('same_exit_time_share')} | "
                 f"{v['ft_net_pnl']:.2f} | {v['ref_net_pnl_signal_only']:.2f} | {v.get('matched_pnl_ft', 0):.2f} | "
                 f"{v.get('matched_pnl_ref', 0):.2f} |")
    L += ["", "Exit pairs on matched entries (reference | Freqtrade), all strategies:", "",
          "| pair | n | median exit time diff (min) | median exit price diff (bps) |", "|---|---|---|---|"]
    for k, v in diag.items():
        L.append(f"| {k} | {v['n']} | {v['median_exit_time_diff_min']} | {v['median_exit_price_diff_bps']} |")
    L += ["", "Known causes (not resolved in favour of either engine):",
          "1. Freqtrade `minimal_roi` is reached on fee-adjusted profit: the 0.9 % ROI needs ≈ +1.15 % price, so "
          "reference `target` exits often become Freqtrade `time_exit`/`stop_loss` and ROI exits are ≈ +22 bps higher.",
          "2. Freqtrade stop = open_rate × 0.994 on the raw open (no slippage model); reference stop = slipped fill × 0.994, "
          "filled with −2.5 bps: ≈ −2.5 bps price difference; Freqtrade stamps the exit at the bar open (−1 min).",
          "3. Freqtrade stops opening trades when free balance < 50 USDT stake; reference signal-only keeps trading "
          "with min(50, cash) — later trades exist only in the reference.",
          "4. Different exits change which later signals are blocked by an open position/cooldown (path divergence).",
          "5. Freqtrade charges 0.125 % fee per side instead of 0.10 % fee + 2.5 bps price adjustment."]
    (dest / "comparison.md").write_text("\n".join(L))
    return out
