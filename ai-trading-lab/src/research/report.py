"""Markdown report for a v0.2 run. Only values from metrics.json; negative results included."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def f(x, nd=3):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, (int, np.integer)):
        return str(x)
    if isinstance(x, (float, np.floating)):
        return "n/a" if not np.isfinite(x) else f"{x:.{nd}f}"
    return str(x)


def table(rows, hdr):
    return "\n".join(["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)] +
                     ["| " + " | ".join(f(c) for c in r) + " |" for r in rows])


def write_report(cfg, out: Path, m: dict, man: dict) -> None:
    L = [f"# MH-v0.2 report — {man['label']}", "",
         f"Evaluation window `[{man['eval_window'][0]}, {man['eval_window'][1]})` UTC (OOS, prequential monthly fits "
         f"{man['fits'][0][:10]} … {man['fits'][-1][:10]}). Config `{man['config_sha256'][:12]}`, code "
         f"`{man['code_sha256'][:12]}`, git `{man['git_commit']}`.", "",
         "Virtual research replay (100 USDT per variant wallet, ≤50 USDT notional, spot long-or-cash). Not a trading "
         "approval. `diag` = fixed-size replay without kill-switch; `constrained` = daily 1.5 / total 10 USDT overlay.",
         "Main costs: 10 bps fee + 2.5 bps adverse execution per side (c = 25 bps round trip).", ""]
    # ---------------- primary tests
    pt = m["primary_tests"]
    B = pt["primary_block_days"]
    L += ["## 1. Pre-registered primary tests (Holm across all primary comparisons)", ""]
    rows = []
    for k, v in pt["tests"].items():
        b = v[f"block_{B}d"]
        obs = b.get("observed", b.get("mean_daily_pnl"))
        ci = b.get("ci95", b.get("ci95_mean_daily"))
        h = pt["holm_primary_block"].get(k, {})
        sc = 1e6 if k.startswith("G01_forecast") else 1.0
        obs = obs * sc if obs is not None else None
        rows.append([k + (" (×1e-6)" if sc != 1 else ""), obs,
                     f"[{f(ci[0] * sc, 4)}, {f(ci[1] * sc, 4)}]" if ci else b.get("status"),
                     b.get("p_one_sided_gt_0", b.get("p_one_sided_mean_gt_0")), h.get("p_holm"), h.get("reject_h0")])
    L.append(table(rows, ["test", f"observed (block {B}d)", "95% CI", "p one-sided", "p Holm", "reject H0 (<=0)"]))
    L += ["", "G01 forecast statistic = equal-weight mean over BTC/ETH/SOL of MSE(B1) − MSE(X) on 1h OOS "
          "(positive = X better); others = mean daily PnL (USDT) of the diag replay or of a paired daily difference.",
          "Sensitivity blocks 7/28 days are in metrics.json.", ""]
    # ---------------- G01 forecast
    L += ["## 2. G01 forecasts (OOS)", ""]
    rows = []
    for H, per in m["g01_forecast"]["per_target"].items():
        for a, r in per.items():
            rows.append([H, a, r["n"], r["B0"]["mse"] * 1e6, r["B1"]["mse"] * 1e6, r["X"]["mse"] * 1e6,
                         r["mse_B1_minus_X"] * 1e6, r["B1"]["r2_vs_B0"], r["X"]["r2_vs_B0"], r["B1"]["rank_ic"],
                         r["X"]["rank_ic"], 1e4 * r["X"]["cond_gross_pred_gt0"] if r["X"]["cond_gross_pred_gt0"]
                         is not None else None, r["X"]["share_pred_gt0"]])
    L.append(table(rows, ["H min", "target", "n", "MSE B0 e-6", "MSE B1 e-6", "MSE X e-6", "B1−X e-6", "R² B1 vs B0",
                          "R² X vs B0", "IC B1", "IC X", "mean y bps | X>0", "share X>0"]))
    L += ["", "Per-year / per-regime MSE differences and calibration bins (train edges): metrics.json, "
          "g01_calibration_oos.csv; coefficients and train windows: g01_coefficients.csv.", ""]
    # ---------------- variants
    L += ["## 3. Portfolio replays — all variants, diag main (fixed size, no kill-switch)", ""]
    rows = []
    for k, v in m["variants"].items():
        s = v["scenarios"]["diag_main"]
        rows.append([k, v["n_intents"], s["n_trades"], s["gross_pnl"], s["fees"], s["slippage_cost"], s["net_pnl"],
                     s.get("expectancy"), s.get("win_rate"), s["max_drawdown_usdt"], s.get("exposure_pct_time"),
                     s.get("break_even_rt_bps_static")])
    L.append(table(rows, ["variant", "intents", "trades", "gross", "fees", "exec loss", "net", "net/trade", "win",
                          "max DD", "exposure %", "break-even RT bps"]))
    L += ["", "## 4. Primary variants — scenarios (net PnL, USDT)", ""]
    rows = []
    for k, v in m["variants"].items():
        sc = v["scenarios"]
        if "constrained_main" not in sc:
            continue
        stat = sc["diag_main"].get("static_cost_sensitivity_net", {})
        rows.append([k, sc["diag_main"]["net_pnl"], sc["constrained_main"]["net_pnl"],
                     sc["constrained_main"]["n_trades"], sc["diag_rt0"]["net_pnl"], sc["diag_rt10"]["net_pnl"],
                     sc["diag_rt40"]["net_pnl"], sc["diag_delay5"]["net_pnl"], sc["diag_risk_matched"]["net_pnl"],
                     sc["diag_risk_matched"].get("avg_notional"), stat.get("rt0"), stat.get("rt40")])
    L.append(table(rows, ["variant", "diag main", "constrained", "constr. trades", "rt0", "rt10", "rt40", "delay 5m",
                          "risk-matched", "avg notional RM", "static rt0", "static rt40"]))
    L += ["", "Constrained risk events and per-year/asset/regime breakdowns: metrics.json.", "",
          "## 5. Controls", ""]
    rows = [[k, v.get("net_pnl", v.get("net_pnl_approx")), v.get("max_drawdown_usdt"), v.get("exposure_time",
             v.get("exposure_fraction")), v.get("exit_reason", ""), v.get("note", "")] for k, v in m["controls"].items()]
    L.append(table(rows, ["control", "net PnL", "max DD", "exposure (time share)", "exit", "note"]))
    L += ["", "### Random entries (seeds 0–99, train-estimated frequency, same grid and hold)", ""]
    rows = [[fam, r["target_variant"], r["strategy_net_pnl"], *r["net_pnl_q05_q25_q50_q75_q95"], r["mean_n_trades"],
             r["strategy_n_trades"], r["mean_exposure_time"], r["share_seeds_ge_strategy"]]
            for fam, r in m["random"].items()]
    L.append(table(rows, ["family", "variant", "strategy net", "q05", "q25", "median", "q75", "q95", "rnd trades",
                          "strategy trades", "rnd exposure", "share seeds ≥ strategy"]))
    L += ["", "## 6. Event study (gross executable labels, all admissible OOS observations)", ""]
    rows = []
    for k, r in m["event_study"].items():
        if "|ALL|" in k:
            rows.append([k, r["n_all"], r["n_signal"], 1e4 * r["mean_all"] if r["mean_all"] is not None else None,
                         1e4 * r["mean_signal"] if r["mean_signal"] is not None else None,
                         1e4 * r["signal_net_expectancy_main"] if r["signal_net_expectancy_main"] is not None else None])
    L.append(table(rows, ["family|pool|hold", "n all", "n signal", "mean all bps", "mean signal bps",
                          "signal net bps (main)"]))
    L += ["", "Per-target HAC t-statistics, H01 OLS on prior return and delay-5 labels: metrics.json "
          "(overlapping observations; HAC lags = ceil(H/grid)).", ""]
    (out / "report.md").write_text("\n".join(L))
