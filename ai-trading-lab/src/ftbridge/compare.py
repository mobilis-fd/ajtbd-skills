"""Compare Freqtrade backtest trades against the reference replay (signal-only scenario: Freqtrade has no
equity-based daily/total loss limit). Differences are explained, not resolved in favour of either result."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import ROOT, dumps

FT_NAME = {"MvpE01P": "E01-P", "MvpE01F": "E01-F", "MvpE02P": "E02-P", "MvpE02F": "E02-F"}


def load_ft_trades(ft_dir: Path) -> pd.DataFrame:
    from freqtrade.data.btanalysis import load_backtest_data, load_backtest_stats
    df = load_backtest_data(ft_dir)
    return df


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
    (dest / "comparison.json").write_text(dumps(out))
    return out
