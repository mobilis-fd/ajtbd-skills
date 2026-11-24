"""QA addendum for MH-v0.2 (read-only measurements on existing run outputs; nothing is re-run or modified).

Usage: python -m audit.qa_addendum_v02
Inputs: reports/v02/runs/{development,validation}_a5bca96b79_cf00d9bc/ (incl. local parquet artefacts) and,
read-only, the MVP v0.1 reference run CSVs. Output: reports/v02/qa_addendum/qa_measurements.json
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT, dumps, load_config

RUN = {"development": ROOT / "reports/v02/runs/development_a5bca96b79_cf00d9bc",
       "validation": ROOT / "reports/v02/runs/validation_a5bca96b79_cf00d9bc"}
OUT = ROOT / "reports/v02/qa_addendum"
PRIMARY = {"G01": "G01-X-H60-thr0", "G01-B1": "G01-B1-H60-thr0", "H01": "H01-H120-none", "H02": "H02-H720-none",
           "H03": "H03-H4320-none"}
COSTS = {"diag_main": (0.001, 0.00025), "diag_rt0": (0.0, 0.0), "diag_rt10": (0.0005, 0.0),
         "diag_rt40": (0.0015, 0.0005), "diag_delay5": (0.001, 0.00025), "constrained_main": (0.001, 0.00025),
         "diag_risk_matched": (0.001, 0.00025)}


def depletion(split: str, tr: pd.DataFrame, rj: pd.DataFrame, metrics: dict, eval_window) -> dict:
    """When did each primary diag wallet stop being able to trade (cash below minNotional incl. fees)?"""
    s, e = pd.Timestamp(eval_window[0]), pd.Timestamp(eval_window[1])
    days = (e - s).days
    out = {}
    for fam, v in PRIMARY.items():
        for sc in ("diag_main", "constrained_main"):
            t = tr[(tr["variant"] == v) & (tr["scenario"] == sc)].sort_values("entry_time")
            r = rj[(rj["variant"] == v) & (rj["scenario"] == sc)]
            if not len(t):
                continue
            last = t["exit_time"].max()
            cash_end = float(t["cash_after"].iloc[-1])
            mn = r[r["reason"].isin(["min_notional_or_cash"])]
            stop = r[r["reason"] == "total_loss_stop"]
            first_block = None
            if len(mn):
                first_block = pd.Timestamp(mn["T"].min())
            if len(stop):
                first_block = min(first_block, pd.Timestamp(stop["T"].min())) if first_block is not None \
                    else pd.Timestamp(stop["T"].min())
            n_blocked = int(len(mn) + len(stop))
            cov = ((first_block - s).total_seconds() / 86400 / days) if first_block is not None else 1.0
            out[f"{v}|{sc}"] = {
                "trades": int(len(t)), "cash_end": round(cash_end, 4), "last_exit": str(last),
                "first_blocked_intent": str(first_block) if first_block is not None else None,
                "share_of_oos_period_before_block": round(cov, 4),
                "intents_blocked_by_cash_or_total_stop": n_blocked,
                "blocked_reason": ("total_loss_stop" if len(stop) else "min_notional_or_cash" if len(mn) else None)}
    return out


def cost_decomposition(tr: pd.DataFrame) -> dict:
    """fees | adverse execution (open*slip both sides) | rounding (tick/step residual) for every scenario."""
    out = {}
    for (v, sc), t in tr.groupby(["variant", "scenario"]):
        if v not in PRIMARY.values():
            continue
        fee, slip = COSTS[sc]
        adverse = (t["qty"] * t["raw_entry"] * slip + t["qty"] * t["raw_exit"] * slip).sum()
        rounding = t["slippage_cost"].sum() - adverse
        fee_chk = (t["qty"] * t["fill_entry"] * fee + t["qty"] * t["fill_exit"] * fee).sum()
        out[f"{v}|{sc}"] = {"n": int(len(t)), "gross": round(float(t["gross_pnl"].sum()), 6),
                            "fees": round(float(t["fees"].sum()), 6), "fees_recomputed": round(float(fee_chk), 6),
                            "adverse_execution": round(float(adverse), 6), "rounding_residual": round(float(rounding), 8),
                            "net": round(float(t["net_pnl"].sum()), 6),
                            "gross_minus_costs_minus_net": round(float(t["gross_pnl"].sum() - t["fees"].sum()
                                                                       - t["slippage_cost"].sum() - t["net_pnl"].sum()), 9),
                            "entry_raw_off_tick": int((np.abs(t["raw_entry"] / 0.01 - np.round(t["raw_entry"] / 0.01))
                                                       > 1e-6).sum())}
    return out


def v01_rt0_residual() -> dict:
    """MVP v0.1 (read-only): explain non-zero 'slippage' in the cost_rt0 scenario (fee=0, slip=0)."""
    out = {}
    for split in ("development", "validation"):
        p = ROOT / f"reports/runs/{split}_2bff6fcca7_792e0459/trades.csv"
        if not p.exists():
            out[split] = "v0.1 run file not present in this checkout"
            continue
        t = pd.read_csv(p)
        t = t[t["scenario"] == "cost_rt0"]
        off_entry = np.abs(t["fill_entry"] - t["raw_entry"]) > 1e-9
        off_exit = np.abs(t["fill_exit"] - t["raw_exit"]) > 1e-9
        by_reason = t.assign(res=t["qty"] * (t["raw_exit"] - t["fill_exit"]) + t["qty"] * (t["fill_entry"] - t["raw_entry"])
                             ).groupby("exit_reason")["res"].agg(["count", "sum"]).round(6)
        out[split] = {"trades": int(len(t)), "fees": round(float(t["fees"].sum()), 9),
                      "slippage_cost_column": round(float(t["slippage_cost"].sum()), 6),
                      "entry_fill_differs_from_raw": int(off_entry.sum()), "exit_fill_differs_from_raw": int(off_exit.sum()),
                      "residual_by_exit_reason": by_reason.reset_index().to_dict("records")}
    return out


def clustering(split: str) -> dict:
    """Temporal clustering, cross-asset co-occurrence and horizon overlap of raw signals (all signals, wallet-free)."""
    out = {}
    d = RUN[split]
    for fam, H in (("H01", 120), ("H02", 720), ("H03", 4320)):
        p = pd.read_parquet(d / f"{fam.lower()}_signals.parquet")
        p = p[p["H"] == H]
        s = p[p["signal"]]
        same_T = s.groupby("T")["symbol"].nunique()
        per_day = s.groupby(s["T"].dt.floor("D")).size()
        ov = []
        for a, g in s.groupby("symbol"):
            ts_ = g["T"].sort_values()
            t = ((ts_ - ts_.iloc[0]) / pd.Timedelta(minutes=1)).to_numpy()   # unit-safe minutes
            j = np.searchsorted(t, t + H, side="left")
            ov.append(j - np.arange(len(t)) - 1)
        ov = np.concatenate(ov) if ov else np.array([0])
        lab = s.dropna(subset=["y"])
        daily = lab.groupby(lab["T"].dt.floor("D"))["y"].mean()
        out[fam] = {"hold_min": H, "n_signals": int(len(s)), "decision_times_with_signal": int(len(same_T)),
                    "share_decisions_with_>=2_assets": round(float((same_T >= 2).mean()), 4),
                    "mean_assets_per_signal_time": round(float(same_T.mean()), 3),
                    "days_with_signal": int(len(per_day)), "max_signals_per_day": int(per_day.max()),
                    "mean_later_same_asset_signals_inside_hold": round(float(ov.mean()), 3),
                    "lag1_autocorr_daily_mean_label": round(float(daily.autocorr(1)), 4) if len(daily) > 3 else None,
                    "naive_n_over_unique_days": round(len(lab) / max(len(daily), 1), 2)}
    g = pd.read_parquet(d / "g01_predictions.parquet")
    g = g[(g["H"] == 60) & g["pred_X"].notna()]
    pos = g[g["pred_X"] > 0]
    same_T = pos.groupby("T")["symbol"].nunique()
    out["G01"] = {"rows": int(len(g)), "rows_pred_X_gt0": int(len(pos)),
                  "share_decisions_all_3_targets_gt0": round(float((same_T == 3).mean()), 4),
                  "corr_of_labels_across_targets_same_T": round(float(g.pivot_table(index="T", columns="symbol", values="y")
                                                                   .corr().where(~np.eye(3, dtype=bool)).stack().mean()), 4)}
    return out


def signal_tables(split: str) -> dict:
    """Write committed, wallet-independent tables of ALL admissible signals with gross labels (y, y5)."""
    d = RUN[split]
    OUT.mkdir(parents=True, exist_ok=True)
    info = {}
    for fam in ("h01", "h02", "h03"):
        p = pd.read_parquet(d / f"{fam}_signals.parquet")
        keep = [c for c in ["T", "symbol", "H", "fit_id", "signal", "est", "y", "y5", "r1h", "r4h", "r24h", "r7d", "r28d",
                            "sigma1h", "trend_regime", "vol_regime"] if c in p]
        f = OUT / f"{split}_{fam}_all_decisions.csv.gz"
        with gzip.GzipFile(f, "wb", mtime=0) as fh:
            fh.write(p[keep].to_csv(index=False, float_format="%.8g").encode())
        info[fam] = {"rows": int(len(p)), "signals": int(p["signal"].sum()), "file": f.name}
    g = pd.read_parquet(d / "g01_predictions.parquet")
    f = OUT / f"{split}_g01_all_predictions.csv.gz"
    keep = ["T", "symbol", "H", "fit_id", "pred_B0", "pred_B1", "pred_X", "y", "y5", "sigma1h", "trend_regime", "vol_regime"]
    with gzip.GzipFile(f, "wb", mtime=0) as fh:
        fh.write(g[keep].to_csv(index=False, float_format="%.8g").encode())
    info["g01"] = {"rows": int(len(g)), "file": f.name}
    return info


def main():
    res = {"v01_rt0_residual": v01_rt0_residual()}
    for split, d in RUN.items():
        man = json.loads((d / "manifest.json").read_text())
        m = json.loads((d / "metrics.json").read_text())
        tr = pd.read_parquet(d / "trades_all.parquet")
        rj = pd.read_parquet(d / "rejections.parquet")
        res[split] = {"depletion": depletion(split, tr, rj, m, man["eval_window"]),
                      "cost_decomposition": cost_decomposition(tr), "clustering": clustering(split),
                      "signal_tables": signal_tables(split),
                      "primary_tests_inputs": {k: v["block_14d"].get("status") for k, v in
                                               m["primary_tests"]["tests"].items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "qa_measurements.json").write_text(dumps(res))
    print(dumps({k: (v if k == "v01_rt0_residual" else {"depletion": v["depletion"]}) for k, v in res.items()}))


if __name__ == "__main__":
    main()
