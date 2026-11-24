"""Markdown report writers (report.md, qa_report.md). Reports only computed values."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT
from src.evaluation.ledger import manual_check_text

PRIMARY = ["E01-P", "E01-F", "E02-P", "E02-F"]


def _f(x, nd=2):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        if not np.isfinite(x):
            return "n/a"
        return f"{x:.{nd}f}"
    return str(x)


def _table(rows: list[list], header: list[str]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(_f(c) if not isinstance(c, str) else c for c in r) + " |" for r in rows]
    return "\n".join(out)


def write_report(cfg, out: Path, metrics: dict, manifest: dict, recon: dict, trades: pd.DataFrame,
                 rnd: pd.DataFrame, evs: pd.DataFrame, ctx: dict) -> None:
    strat_names = [k for k in metrics if k.startswith(("E0", "B01"))]
    L = [f"# Backtest report — {manifest['label']}",
         "",
         f"Experiment `{manifest['experiment_id']}`; segment `[{manifest['segment'][0]}, {manifest['segment'][1]})` UTC.",
         f"Config sha256 `{manifest['config_sha256'][:16]}…`, code sha256 `{manifest['code_sha256'][:16]}…`, "
         f"git `{manifest['git_commit']}`.",
         "",
         "Research replay with virtual capital (100 USDT per strategy wallet). No real orders. "
         "Results include negative outcomes; nothing was tuned on these data.",
         "Cost model (main): fee 10 bps/side + adverse price adjustment 2.5 bps/side = 25 bps round trip "
         "(working assumption, not the user's tariff; real spread unknown on OHLCV).",
         "",
         "## 1. Main scenario (portfolio risk limits ON)", ""]
    rows = []
    for n in strat_names:
        m = metrics[n]["scenarios"]["main"]
        rows.append([n, str(metrics[n]["n_raw_signals"]), str(m["n_trades"]), m["net_pnl"], m["gross_pnl"], m["fees"],
                     m["slippage_cost"], m["return_pct"], m["win_rate"], m["expectancy"],
                     m["profit_factor"] if m["profit_factor"] is not None else m["profit_factor_note"],
                     m["max_drawdown_usdt"], m["exposure_pct_time"], m["turnover_x_initial"],
                     m["sharpe_daily_ann"], m["sortino_daily_ann"]])
    L.append(_table(rows, ["strategy", "raw signals", "trades", "net PnL", "gross PnL", "fees", "slippage",
                           "return %", "win rate", "expectancy", "PF", "max DD", "exposure %", "turnover x",
                           "Sharpe(d)", "Sortino(d)"]))
    L += ["", "Exit reasons / rejected signals / risk events (main):", ""]
    for n in strat_names:
        m = metrics[n]["scenarios"]["main"]
        ev = [e["event"] for e in m.get("risk_events", [])]
        L.append(f"- **{n}**: exits {m['exit_reasons']}; rejected {m['rejected_signals']}; "
                 f"risk events { {str(k): int(v) for k, v in pd.Series(ev).value_counts().items()} if ev else {} }; "
                 f"uncertain-gap trades {m['uncertain_gap_trades']} "
                 f"(conservative-gap net {_f(m['conservative_gap_scenario_net_pnl'], 4)})")
    L += ["", "## 2. Baselines", ""]
    rows = [["B00 cash", "0", 0.0, 0.0, "n/a", "flat"]]
    for k in metrics:
        if k.startswith("B02"):
            m = metrics[k]
            rows.append([k, "1", m["net_pnl"], m["return_pct"], m["max_drawdown_usdt"], "100% time, $50, no stop"])
    L.append(_table(rows, ["baseline", "trades", "net PnL", "return %", "max DD", "exposure / risk"]))
    L += ["", "B01 = adaptation of upstream Freqtrade `SampleStrategy` entry signals (freqtrade 2026.10, "
          f"template sha256 `{manifest['freqtrade_sample_strategy_sha256'][:16]}…`) with the unified exit/risk/cost rules; "
          "hold 30 and 60 min variants (shown in table 1).", "",
          "### B03 random entries (frequency-matched, 100 fixed seeds per target)", ""]
    rows = []
    for tgt, r in metrics["B03-random"].items():
        q = r["net_pnl_quantiles_5_25_50_75_95"]
        rows.append([tgt, r["strategy_net_pnl"], q[0], q[1], q[2], q[3], q[4], r["mean_n_trades"],
                     r["share_seeds_ge_strategy"]])
    L.append(_table(rows, ["target", "strategy net", "rnd p5", "p25", "median", "p75", "p95", "rnd mean trades",
                           "share seeds >= strategy"]))
    L += ["", "## 3. Diagnostic: signal-only, NO portfolio stop (not a safe-trading estimate)", ""]
    rows = []
    for n in strat_names:
        m = metrics[n]["scenarios"]["signal_only_no_portfolio_stop"]
        rows.append([n, str(m["n_trades"]), m["net_pnl"], m["gross_pnl"], m["win_rate"], m["expectancy"],
                     m["profit_factor"] if m["profit_factor"] is not None else m["profit_factor_note"], m["max_drawdown_usdt"]])
    L.append(_table(rows, ["strategy", "trades", "net PnL", "gross PnL", "win rate", "expectancy", "PF", "max DD"]))
    L += ["", "## 4. Cost and execution sensitivity (full replay, risk limits ON)", "",
          "0/10/40 bps round-trip are hypothetical, split fee:slippage = 80:20. `delay60`: entry one more minute later. "
          "`coarse_step_x10`: lot step x10 (exchange filters are assumptions).", ""]
    rows = []
    for n in strat_names:
        sc = metrics[n]["scenarios"]
        be = sc["cost_rt0"].get("break_even_roundtrip_cost_bps")
        rows.append([n, sc["cost_rt0"]["net_pnl"], sc["cost_rt10"]["net_pnl"], sc["main"]["net_pnl"],
                     sc["cost_rt40"]["net_pnl"], sc["delay60"]["net_pnl"], sc["coarse_step_x10"]["net_pnl"],
                     be if be is not None else "n/a (no trades)"])
    L.append(_table(rows, ["strategy", "0 bps", "10 bps", "25 bps (main)", "40 bps", "delay 60s", "coarse step",
                           "break-even RT bps (fixed rt0 fills)"]))
    L += ["", "## 5. By asset and by regime (main scenario)", "",
          "Regime = sign of trailing 24h log return x trailing 24h r5 volatility vs development median per symbol "
          "(past-only; thresholds fixed on development).", ""]
    rows = []
    for n in strat_names:
        m = metrics[n]["scenarios"]["main"]
        for grp in ("by_symbol", "by_regime"):
            for k, v in m.get(grp, {}).items():
                rows.append([n, grp.replace("by_", ""), k, str(v["n_trades"]), v["net_pnl"], v["win_rate"], v["expectancy"]])
    L.append(_table(rows, ["strategy", "group", "key", "trades", "net PnL", "win rate", "expectancy"]) if rows
             else "_no trades_")
    L += ["", "## 6. Non-overlapping 4-day / 7-day windows and rolling 7-day (main scenario)", ""]
    rows = []
    for n in strat_names:
        m = metrics[n]["scenarios"]["main"]
        for w, s in m["windows"].items():
            rows.append([n, w, str(s["n_windows_complete"]), s["share_positive"], s["share_zero_trades"], s["min_pnl"],
                         s["median_pnl"], s["max_pnl"]])
        r7 = m.get("rolling_7d_pnl", {})
        rows.append([n, "rolling 7d", str(r7.get("n")), r7.get("share_positive"), "", r7.get("min"), r7.get("median"),
                     r7.get("max")])
    L.append(_table(rows, ["strategy", "window", "complete windows", "share > 0", "share 0 trades", "min PnL",
                           "median PnL", "max PnL"]))
    L += ["", "## 7. Uncertainty: moving-block bootstrap of daily PnL (main scenario; preliminary)", ""]
    rows = []
    for n in strat_names:
        for k, b in metrics[n]["scenarios"]["main"]["bootstrap"].items():
            if b["status"] == "ok":
                rows.append([n, k, str(b["n_days"]), b["mean_daily_pnl"], f"[{b['ci95_total'][0]:.3f}, {b['ci95_total'][1]:.3f}]",
                             b["share_boot_mean_le_0"], b["p_one_sided_mean_gt_0"]])
            else:
                rows.append([n, k, str(b["n_days"]), "insufficient data", b.get("note", ""), "", ""])
    L.append(_table(rows, ["strategy", "block", "days", "mean daily PnL", "95% CI total PnL", "P(boot mean<=0)",
                           "p one-sided"]))
    L += ["", "Holm correction across the 4 pre-registered candidates (7-day blocks):", ""]
    L.append(_table([[k, v["p"], v["p_holm"], str(v["reject_h0"])] for k, v in metrics["holm"].items()],
                    ["candidate", "p", "p Holm", "reject H0 (mean<=0) at 5%"]))
    L += ["", "No winner is declared from a single window; this report does not approve any demo or live use.", "",
          "## 8. Event study (mechanism check, not a trading result)", "",
          "Forward log returns from the 1m open at decision time; pooled across symbols (ALL).", ""]
    e = evs[evs["symbol"] == "ALL"]
    rows = [[r.group, str(r.horizon_min), str(r.n), r.mean_bps, r.median_bps, r.share_positive, r.t_stat_naive]
            for r in e.itertuples()]
    L.append(_table(rows, ["group", "h (min)", "n", "mean bps", "median bps", "share > 0", "naive t"]))
    L += ["", "## 9. Reproducibility", "", "```", json.dumps({k: manifest[k] for k in
          ("config_sha256", "code_sha256", "git_commit", "regime_thresholds_sha256", "data_manifest_sha256")}, indent=2),
          "```", "", "Ledger reconciliation (main scenario): " +
          ", ".join(f"{k}: {'OK' if v['ok'] else 'FAIL'} ({v['n_trades']} trades)" for k, v in recon.items()), ""]
    (out / "report.md").write_text("\n".join(L))
    write_qa(cfg, out, metrics, recon, trades, ctx)


def write_qa(cfg, out: Path, metrics, recon, trades: pd.DataFrame, ctx) -> None:
    L = ["# QA report", ""]
    qa_path = ROOT / "data" / "qa.json"
    if qa_path.exists():
        qa = json.loads(qa_path.read_text())
        L += ["## Data QA (from `validate-data`)", ""]
        for sym, q in qa.get("symbols", {}).items():
            r = q["raw_checks"]
            L.append(f"- {sym}: rows {r['rows_in_range']}, missing minutes {r['missing_minutes']} "
                     f"(completeness {r['completeness']:.6f}), dup open_time {r['duplicate_open_time']}, "
                     f"OHLC violations {r['ohlc_invariant_violations']}, taker>total {r['taker_gt_total']}, "
                     f"neg volume {r['negative_volume']}, bad close_time {r['bad_close_time']}, units {r['ts_units']}, "
                     f"zero-volume rows {r['zero_volume_rows']}, clean log {q['clean_log']}")
        L.append("")
    L += ["## Ledger reconciliation (independent recomputation)", ""]
    for k, v in recon.items():
        L.append(f"- {k}: {'OK' if v['ok'] else 'FAIL'}; trades {v['n_trades']}; issues {v['issues'][:5]}")
    L += ["", "## Manual trade checks (raw 1m bars printed for hand verification)", ""]
    if len(trades):
        main = trades[(trades["scenario"] == "main") & trades["strategy"].str.startswith("E0")]
        picks = []
        for reason in ("stop", "target", "time_exit", "stop_gap", "target_gap", "risk_exit_daily", "boundary_exit"):
            sub = main[main["exit_reason"] == reason]
            if len(sub):
                picks.append(sub.iloc[0])
        sc = cfg["costs"]["scenarios"]["main"]
        for t in picks[:6]:
            b = ctx["bars"][t["symbol"]]
            k0, k1 = int(t["entry_minute"]) - 1, min(int(t["exit_minute"]) + 1, b.n - 1)
            k0 = max(k0, 0)
            ks = list(range(k0, k1 + 1))
            if len(ks) > 14:
                ks = ks[:6] + ks[-6:]
            bars_df = pd.DataFrame({"open_time": [b.start + pd.Timedelta(minutes=k) for k in ks],
                                    "open": b.o[ks], "high": b.h[ks], "low": b.l[ks], "close": b.c[ks]})
            L += ["```", manual_check_text(t, bars_df, sc["fee_bps"] / 1e4, sc["slip_bps"] / 1e4), "```", ""]
    else:
        L.append("_no trades in main scenario_")
    (out / "qa_report.md").write_text("\n".join(L))


def write_summary(run_dirs: dict, dest: Path) -> str:
    """Combined development/validation summary generated from metrics.json (no hand-copied numbers)."""
    L = ["# MVP v0.1 — development & validation summary (generated)", "",
         "Generated by `python -m src.cli summary` from each run's `metrics.json`. Main = 25 bps RT costs with "
         "portfolio limits (daily 1.5 / total 10 USDT); signal-only = same without portfolio stop (diagnostic).", ""]
    hdr = ["split", "strategy", "raw signals", "trades (main)", "net main", "gross main", "fees+slip main",
           "trades (sig-only)", "net sig-only", "gross sig-only", "net 0 bps", "break-even RT bps", "PF main",
           "win rate", "max DD main"]
    rows = []
    for split, d in run_dirs.items():
        m = json.loads((d / "metrics.json").read_text())
        for n in [k for k in m if k.startswith(("E0", "B01"))]:
            sc = m[n]["scenarios"]
            mn, so = sc["main"], sc["signal_only_no_portfolio_stop"]
            rows.append([split, n, str(m[n]["n_raw_signals"]), str(mn["n_trades"]), mn["net_pnl"], mn["gross_pnl"],
                         round(mn["fees"] + mn["slippage_cost"], 4), str(so["n_trades"]), so["net_pnl"], so["gross_pnl"],
                         sc["cost_rt0"]["net_pnl"], sc["cost_rt0"].get("break_even_roundtrip_cost_bps", "n/a"),
                         mn["profit_factor"] if mn["profit_factor"] is not None else mn["profit_factor_note"],
                         mn["win_rate"], mn["max_drawdown_usdt"]])
    L.append(_table(rows, hdr))
    L += ["", "Baselines:", ""]
    rows = []
    for split, d in run_dirs.items():
        m = json.loads((d / "metrics.json").read_text())
        rows.append([split, "B00 cash", 0.0, "-"])
        for k in m:
            if k.startswith("B02"):
                rows.append([split, k, m[k]["net_pnl"], m[k]["max_drawdown_usdt"]])
        for k, r in m["B03-random"].items():
            q = r["net_pnl_quantiles_5_25_50_75_95"]
            rows.append([split, f"B03~{k} (median [p5, p95])", q[2], f"[{q[0]:.2f}, {q[4]:.2f}]; share seeds >= strategy "
                         f"{r['share_seeds_ge_strategy']}"])
    L.append(_table(rows, ["split", "baseline", "net PnL", "max DD / distribution"]))
    L += ["", "Holm-adjusted p (H0: mean daily PnL <= 0, 7-day blocks):", ""]
    rows = []
    for split, d in run_dirs.items():
        m = json.loads((d / "metrics.json").read_text())
        for k, v in m["holm"].items():
            rows.append([split, k, v["p"], v["p_holm"], str(v["reject_h0"])])
    L.append(_table(rows, ["split", "candidate", "p", "p Holm", "reject"]))
    L += ["", "Run directories: " + ", ".join(f"{k}: `{v.relative_to(ROOT)}`" for k, v in run_dirs.items()), ""]
    txt = "\n".join(L)
    dest.write_text(txt)
    return txt
