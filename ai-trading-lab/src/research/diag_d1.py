"""MH-v0.2-D1: wallet-independent signal diagnostics (see SPEC_DIAGNOSTIC_D1.md). Diagnostic only.

Reuses the frozen v0.2 panels/intents/replay; changes no hypothesis parameter.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT, code_hash, dumps, git_commit
from src.research import pipeline as P
from src.research import stats as S
from src.research.replay import round_down, round_up

VIRTUAL_CASH = 1_000_000.0
NOTIONAL = 50.0
L3_VARIANTS = ["G01-X-H60-thr0", "G01-B1-H60-thr0", "G01-X-H60-thrc",
               "H01-H120-none", "H01-H120-common", "H01-H120-c",
               "H02-H720-none", "H02-H720-common", "H02-H720-c",
               "H03-H4320-none", "H03-H4320-common", "H03-H4320-c"]
SCEN = {"main": "main", "rt0": "rt0", "rt10": "rt10", "rt40": "rt40", "delay5": "main"}


def fit_index_unit_safe(T, fits) -> np.ndarray:
    """Latest fit <= T, robust to ns/us resolution differences (QA addendum risk)."""
    f = pd.DatetimeIndex(fits).as_unit("ns").asi8
    t = pd.DatetimeIndex(T).as_unit("ns").asi8
    return np.searchsorted(f, t, side="right") - 1


# ------------------------------------------------------------------ L1/L2 signal populations

def signal_populations(cfg, panels) -> list[tuple[str, int, pd.DataFrame, pd.DataFrame]]:
    """(name, H, signal rows, baseline rows). Rows keep T, symbol, y, y5."""
    out = []
    c = cfg["costs"]["hurdle_c"]
    g = panels["G01"]["panel"]
    for H, gh in g.groupby("H"):
        base = gh[np.isfinite(gh["y"])]
        for m in ("B0", "B1", "X"):
            for k, thr in (("0", 0.0), ("c", c), ("2c", 2 * c)):
                p = gh[f"pred_{m}"]
                sig = gh[np.isfinite(p) & (p > thr) & np.isfinite(gh["y"])]
                out.append((f"G01-{m}-H{H}-thr{k}", int(H), sig, base))
    for fam in ("H01", "H02", "H03"):
        pan = panels[fam]["panel"]
        for H, gh in pan.groupby("H"):
            base = gh[np.isfinite(gh["y"])]
            out.append((f"{fam}-H{H}", int(H), base[base["signal"]], base))
    return out


def execute_signals(rows: pd.DataFrame, ctx, cfg, H: int, scen: str, delay: int) -> pd.DataFrame:
    """Per-signal fixed-50 execution with fee/adverse/rounding decomposition (no wallet)."""
    c = cfg["costs"][scen]
    fee, slip = c["fee_bps"] / 1e4, c["slip_bps"] / 1e4
    filt = cfg["execution"]["filters"]
    recs = []
    for sym, g in rows.groupby("symbol"):
        px = ctx["px"][sym]
        tick, step = filt[sym]["tick_size"], filt[sym]["step_size"]
        k = ((pd.DatetimeIndex(g["T"]) - px.g0) / pd.Timedelta(minutes=1)).astype("int64").to_numpy() + delay
        ok = (k >= 0) & (k + H < px.n)
        oe = np.where(ok, px.o[np.clip(k, 0, px.n - 1)], np.nan)
        ox = np.where(ok, px.o[np.clip(k + H, 0, px.n - 1)], np.nan)
        for T, a, b in zip(g["T"].to_numpy(), oe, ox):
            if not (math.isfinite(a) and math.isfinite(b)):
                continue
            fin = round_up(a * (1 + slip), tick)
            qty = round_down(NOTIONAL / fin, step)
            if qty <= 0:
                continue
            fout = round_down(b * (1 - slip), tick)
            gross = qty * (b - a)
            fees = fee * qty * (fin + fout)
            adverse = slip * qty * (a + b)
            rounding = qty * (fin - a * (1 + slip)) + qty * (b * (1 - slip) - fout)
            net = qty * fout * (1 - fee) - qty * fin * (1 + fee)
            recs.append((T, sym, qty * fin, gross, fees, adverse, rounding, net))
    df = pd.DataFrame(recs, columns=["T", "symbol", "notional", "gross", "fees", "adverse", "rounding", "net"])
    if len(df):
        assert np.allclose(df["gross"] - df["fees"] - df["adverse"] - df["rounding"], df["net"], atol=1e-9)
    return df


# ------------------------------------------------------------------ day-block inference

def daily_sums(df: pd.DataFrame, col: str, days: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    d = df.assign(day=pd.DatetimeIndex(df["T"]).floor("D"))
    s = d.groupby("day")[col].sum().reindex(days).fillna(0).to_numpy()
    n = d.groupby("day")[col].size().reindex(days).fillna(0).to_numpy()
    return s, n


def boot_diff(sig: pd.DataFrame, base: pd.DataFrame | None, col: str, days, block, n_boot, seed, min_blocks) -> dict:
    """Day-block bootstrap of mean(sig[col]) (and of mean(sig) - mean(base)) on the common UTC-day axis."""
    s1, n1 = daily_sums(sig, col, days)
    out = {"n": int(n1.sum()), "days_with_obs": int((n1 > 0).sum()), "block_days": block,
           "mean": float(s1.sum() / n1.sum()) if n1.sum() else None}
    if base is not None:
        s0, n0 = daily_sums(base, col, days)
        out["mean_baseline"] = float(s0.sum() / n0.sum()) if n0.sum() else None
        out["diff"] = (out["mean"] - out["mean_baseline"]) if out["mean"] is not None else None
    if not n1.sum() or len(days) // block < min_blocks:
        out["status"] = "insufficient_data"
        return out
    idx = S.day_blocks_index(len(days), block, n_boot, seed)
    with np.errstate(invalid="ignore", divide="ignore"):
        m1 = s1[idx].sum(1) / n1[idx].sum(1)
        out["ci95_mean"] = [float(np.nanquantile(m1, 0.025)), float(np.nanquantile(m1, 0.975))]
        out["share_boot_mean_le_0"] = float(np.nanmean(m1 <= 0))
        if base is not None:
            d = m1 - s0[idx].sum(1) / n0[idx].sum(1)
            out["ci95_diff"] = [float(np.nanquantile(d, 0.025)), float(np.nanquantile(d, 0.975))]
            out["share_boot_diff_le_0"] = float(np.nanmean(d <= 0))
    out["status"] = "ok"
    return out


# ------------------------------------------------------------------ main

def run_d1(cfg: dict, split: str, out_root: Path | None = None, n_seeds: int | None = None) -> Path:
    ctx = P.load_ctx(cfg, split)
    panels = {"G01": P.g01_panel(cfg, ctx)}
    for fam in ("H01", "H02", "H03"):
        panels[fam] = P.h_panel(cfg, ctx, fam)
    # QA check: unit-safe fit index equals the v0.2 assignment on every panel
    unit_check = {fam: bool((fit_index_unit_safe(pan["panel"]["T"], ctx["fits"]) == pan["panel"]["fit_id"].to_numpy()).all())
                  for fam, pan in panels.items()}
    st = cfg["statistics"]["bootstrap"]
    days = pd.date_range(ctx["eval_start"], ctx["end"], freq="D", inclusive="left", tz="UTC")
    res = {"unit_safe_fit_index_matches_v02": unit_check, "L1": {}, "L2": {}, "L3": {}, "L3_random": {}}
    level_rows = []
    for name, H, sig, base in signal_populations(cfg, panels):
        sig = sig.assign(gross_bps=1e4 * sig["y"])
        bas = base.assign(gross_bps=1e4 * base["y"])
        l1 = {"n_signals": int(len(sig)), "n_baseline": int(len(bas)),
              "signals_per_signal_day": round(len(sig) / max(sig["T"].dt.floor("D").nunique(), 1), 3),
              "share_gt0": float((sig["y"] > 0).mean()) if len(sig) else None}
        for b in st["blocks_days"]:
            l1[f"block_{b}d"] = boot_diff(sig, bas, "gross_bps", days, b, st["n_boot"], st["seed"], st["min_blocks"])
        l1["per_asset"] = {a: boot_diff(g, bas[bas["symbol"] == a], "gross_bps", days, st["primary_block_days"],
                                        st["n_boot"], st["seed"], st["min_blocks"]) for a, g in sig.groupby("symbol")}
        res["L1"][name] = l1
        l2 = {}
        for lab, sc in SCEN.items():
            delay = ctx["d5"] if lab == "delay5" else ctx["d1"]
            ex = execute_signals(sig, ctx, cfg, H, sc, delay)
            if not len(ex):
                l2[lab] = {"n": 0}
                continue
            ex = ex.assign(net_bps=1e4 * ex["net"] / ex["notional"])
            r = {"n": int(len(ex)), **{k: float(ex[k].sum()) for k in ("gross", "fees", "adverse", "rounding", "net")},
                 "mean_net_bps": float(ex["net_bps"].mean()),
                 "break_even_rt_bps": float(1e4 * ex["gross"].sum() / ex["notional"].sum()),
                 f"block_{st['primary_block_days']}d": boot_diff(ex, None, "net_bps", days, st["primary_block_days"],
                                                                 st["n_boot"], st["seed"], st["min_blocks"])}
            l2[lab] = r
            if lab == "main" and (name.endswith("thr0") or name.startswith("H0")):
                level_rows.append(ex.assign(population=name))
        res["L2"][name] = l2
    # ---------------- L3 fixed-50 portfolio
    specs = {s["name"]: s for s in P.variant_specs(cfg)}
    daily = {}
    for vn in L3_VARIANTS:
        sp = specs[vn]
        res["L3"][vn] = {}
        for lab, sc in SCEN.items():
            hurdle = P.rt_cost(cfg, sc)
            it, _ = P.intents_for(sp, cfg, panels, ctx, hurdle if lab.startswith("rt") else cfg["costs"]["hurdle_c"])
            p = P.params(cfg, sc, False, ctx["d5"] if lab == "delay5" else None)
            p.initial = VIRTUAL_CASH
            r = P.replay_variant(cfg, ctx, it, p, full=False)
            tr = r["trades"]
            eq = r["equity"] - VIRTUAL_CASH
            dp = S.daily_pnl(eq + VIRTUAL_CASH, VIRTUAL_CASH)
            daily[(vn, lab)] = dp
            dd = eq - eq.cummax()
            res["L3"][vn][lab] = {
                "n_intents": int(len(it)), "n_trades": int(len(tr)),
                "net": float(tr["net_pnl"].sum()) if len(tr) else 0.0,
                "gross": float(tr["gross_pnl"].sum()) if len(tr) else 0.0,
                "fees": float(tr["fees"].sum()) if len(tr) else 0.0,
                "exec_loss_adverse_plus_rounding": float(tr["slippage_cost"].sum()) if len(tr) else 0.0,
                "net_per_trade": float(tr["net_pnl"].mean()) if len(tr) else None,
                "max_drawdown_usdt": float(-dd.min()), "min_equity_vs_start": float(eq.min()),
                "exposure_time": float(((tr["exit_time"] - tr["entry_time"]).dt.total_seconds().sum() / 60) / len(eq))
                if len(tr) else 0.0,
                "rejections": {k: int(v) for k, v in pd.DataFrame(r["rejections"])["reason"].value_counts().items()}
                if len(r["rejections"]) else {}}
    # random baselines with fixed 50
    seeds = range(cfg["controls"]["random_seeds"][0], cfg["controls"]["random_seeds"][1] + 1)
    if n_seeds is not None:
        seeds = range(n_seeds)
    prim = {"G01": "G01-X-H60-thr0", "H01": "H01-H120-none", "H02": "H02-H720-none", "H03": "H03-H4320-none"}
    for fi, fam in enumerate(("G01", "H01", "H02", "H03")):
        nets = []
        for sd in seeds:
            it = P.random_intents(fam, cfg, panels, ctx, sd, fi)
            p = P.params(cfg, "main")
            p.initial = VIRTUAL_CASH
            r = P.run(it, ctx["px"], p, ctx["eval_start"], ctx["end"])
            nets.append(sum(t["net_pnl"] for t in r["trades"]))
        nets = np.array(nets)
        real = res["L3"][prim[fam]]["main"]["net"]
        res["L3_random"][fam] = {"variant": prim[fam], "n_seeds": len(nets), "strategy_net": real,
                                 "q05_q50_q95": [float(np.quantile(nets, q)) for q in (0.05, 0.5, 0.95)],
                                 "share_seeds_ge_strategy": float((nets >= real).mean())}
    # re-estimated primary comparisons (diagnostic; Holm for reference only)
    pairs = {"G01_economic_X_minus_B1_thr0": ("G01-X-H60-thr0", "G01-B1-H60-thr0"),
             "G01_H04_X_thrc_minus_thr0": ("G01-X-H60-thrc", "G01-X-H60-thr0")}
    for fam, H in (("H01", 120), ("H02", 720), ("H03", 4320)):
        pairs[f"{fam}_net_H{H}"] = (f"{fam}-H{H}-none", None)
        pairs[f"{fam}_H04_c_minus_common_H{H}"] = (f"{fam}-H{H}-c", f"{fam}-H{H}-common")
    tests = {}
    for k, (a, b) in pairs.items():
        x = daily[(a, "main")] - (daily[(b, "main")] if b else 0)
        tests[k] = {f"block_{bl}d": S.block_bootstrap(x, bl, st["n_boot"], st["seed"], st["min_blocks"])
                    for bl in st["blocks_days"]}
    B = st["primary_block_days"]
    pv = {k: (v[f"block_{B}d"].get("p_one_sided_mean_gt_0") if v[f"block_{B}d"].get("status") == "ok" else None)
          for k, v in tests.items()}
    res["L3_tests_diagnostic"] = {"tests": tests, "holm_reference_only": S.holm(pv, cfg["statistics"]["holm_alpha"]),
                                  "note": "G01 forecast test is unaffected by wallets and is not repeated (see v0.2)"}
    # ---------------- write
    chash = code_hash()
    out = (out_root or ROOT / "reports" / "v02" / "diagnostics" / "D1") / f"{split}_{chash[:10]}_{cfg['_hash'][:8]}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "d1_results.json").write_text(dumps(P._clean(res)))
    lv = pd.concat(level_rows, ignore_index=True) if level_rows else pd.DataFrame()
    with gzip.GzipFile(out / "d1_signal_level_main.csv.gz", "wb", mtime=0) as fh:
        fh.write(lv.to_csv(index=False, float_format="%.10g").encode())
    man = {"experiment_id": "MH-v0.2-D1", "split": split, "eval_window": [str(ctx["eval_start"]), str(ctx["end"])],
           "code_sha256": chash, "config_sha256": cfg["_hash"], "git_commit": git_commit(),
           "created_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    (out / "manifest.json").write_text(dumps(man))
    write_d1_report(out, res, man)
    return out


def write_d1_report(out: Path, r: dict, man: dict) -> None:
    from src.research.report import f, table
    L = [f"# MH-v0.2-D1 diagnostic report — {man['split']}", "",
         f"OOS window `{man['eval_window'][0]} → {man['eval_window'][1]}`; git `{man['git_commit']}`. DIAGNOSTIC ONLY: does "
         "not replace v0.2 primary tests or verdicts (SPEC_DIAGNOSTIC_D1.md).", "",
         f"Unit-safe fit index equals v0.2 assignment: {r['unit_safe_fit_index_matches_v02']}", "",
         "## L1 signal quality (gross bps, day-block 14 d CI) and L2 execution (fixed 50 USDT per signal, no wallet)", ""]
    rows = []
    for k, v in r["L1"].items():
        b = v["block_14d"]
        l2 = r["L2"][k]
        m = l2.get("main", {})
        rows.append([k, v["n_signals"], v["signals_per_signal_day"], b.get("mean"), b.get("mean_baseline"), b.get("diff"),
                     f"[{f(b['ci95_diff'][0], 2)}, {f(b['ci95_diff'][1], 2)}]" if "ci95_diff" in b else b.get("status"),
                     m.get("break_even_rt_bps"), m.get("mean_net_bps"),
                     f"[{f(m['block_14d']['ci95_mean'][0], 2)}, {f(m['block_14d']['ci95_mean'][1], 2)}]"
                     if m.get("block_14d", {}).get("ci95_mean") else "n/a",
                     l2.get("rt0", {}).get("mean_net_bps"), l2.get("rt40", {}).get("mean_net_bps"),
                     l2.get("delay5", {}).get("mean_net_bps")])
    L.append(table(rows, ["population", "signals", "signals/day", "mean gross bps", "baseline bps", "diff bps",
                          "diff 95% CI", "break-even RT bps", "net bps main", "net 95% CI", "net bps rt0",
                          "net bps rt40", "net bps delay5"]))
    L += ["", "Cost decomposition (USDT, main, fixed 50 per signal): see d1_results.json `L2.*.main` "
          "(gross, fees, adverse, rounding, net).", "", "## L3 one-position portfolio with constant 50 USDT notional "
          "(no depletion, no kill-switch)", ""]
    rows = []
    for k, v in r["L3"].items():
        m = v["main"]
        rows.append([k, m["n_trades"], m["gross"], m["fees"], m["exec_loss_adverse_plus_rounding"], m["net"],
                     m["net_per_trade"], m["max_drawdown_usdt"], m["exposure_time"], v["rt0"]["net"], v["rt40"]["net"],
                     v["delay5"]["net"]])
    L.append(table(rows, ["variant", "trades", "gross", "fees", "adverse+rounding", "net", "net/trade", "max DD",
                          "exposure", "net rt0", "net rt40", "net delay5"]))
    L += ["", "Random (fixed 50, seeds 0–99):", ""]
    L.append(table([[k, v["variant"], v["strategy_net"], *v["q05_q50_q95"], v["share_seeds_ge_strategy"]]
                    for k, v in r["L3_random"].items()],
                   ["family", "variant", "strategy net", "q05", "median", "q95", "share seeds ≥ strategy"]))
    L += ["", "## Re-estimated primary comparisons on fixed-50 daily PnL (diagnostic; Holm for reference only)", ""]
    t = r["L3_tests_diagnostic"]
    L.append(table([[k, v["block_14d"].get("mean_daily_pnl"), str(v["block_14d"].get("ci95_mean_daily")),
                     v["block_14d"].get("p_one_sided_mean_gt_0"), t["holm_reference_only"][k]["p_holm"]]
                    for k, v in t["tests"].items()], ["comparison", "mean daily PnL", "95% CI", "p", "p Holm (ref.)"]))
    (out / "report.md").write_text("\n".join(L))
