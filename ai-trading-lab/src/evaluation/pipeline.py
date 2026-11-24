"""End-to-end research backtest for one split: data -> features -> signals -> replay -> metrics."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT, code_hash, dumps, file_sha256, git_commit, split_bounds
from src.data import store
from src.data.aggregate import to_grid
from src.evaluation import bootstrap as bs
from src.evaluation import event_study as es
from src.evaluation.engine import AccountState, Bars, ExecParams, Filters, RiskParams, equity_curve, run
from src.evaluation.ledger import reconcile
from src.evaluation.metrics import compute_metrics, daily_pnl, group_stats, trade_stats, window_table
from src.features.core import compute_features, regime_label
from src.signals.rules import (STRATEGIES, b01_signal, random_signal_times, sample_strategy_sha256,
                               strategy_signal)

PRIMARY = list(STRATEGIES)


# ------------------------------------------------------------------ preparation

def filters_from_cfg(cfg: dict, coarse: bool = False) -> dict:
    ef = cfg["exchange_filters"]
    mult = ef.get("sensitivity_coarse_step_multiplier", 10) if coarse else 1
    return {s: Filters(tick=ef[s]["tick_size"], step=ef[s]["step_size"] * mult, min_notional=ef[s]["min_notional"])
            for s in cfg["data"]["symbols"]}


def exec_params(cfg: dict, hold: int, scenario: str, coarse: bool = False) -> ExecParams:
    ex = cfg["execution"]
    sc = cfg["costs"]["scenarios"][scenario]
    return ExecParams(hold_minutes=hold, stop_pct=ex["stop_pct"], target_pct=ex["target_pct"],
                      fee=sc["fee_bps"] / 1e4, slip=sc["slip_bps"] / 1e4,
                      delay_minutes=int(sc.get("delay_seconds", 0) // 60), cooldown_minutes=ex["cooldown_minutes"],
                      stake=ex["stake_usdt"], filters=filters_from_cfg(cfg, coarse))


def risk_params(cfg: dict, enabled: bool = True) -> RiskParams:
    r = cfg["risk"]
    return RiskParams(enabled=enabled, initial_equity=r["initial_equity"], daily_limit=r["daily_loss_limit"],
                      total_limit=r["total_loss_limit"])


def regime_thresholds(cfg: dict, feats: dict, split: str) -> dict:
    path = ROOT / cfg["regime"]["thresholds_file"]
    if path.exists():
        return json.loads(path.read_text())
    if split != "development":
        raise RuntimeError("regime thresholds must be fixed on development first")
    s, e = split_bounds(cfg, "development")
    th = {"fixed_on": "development", "statistic": "median of vol24h (std of r5 over trailing 288 candles)",
          "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "vol_threshold": {}}
    for sym, f in feats.items():
        v = f.loc[(f.index >= s) & (f.index < e), "vol24h"].dropna()
        th["vol_threshold"][sym] = float(v.median())
    path.write_text(json.dumps(th, indent=2))
    return th


def prepare(cfg: dict, split: str, unlocked: bool = False) -> dict:
    s, e = split_bounds(cfg, split)
    warm = s - pd.Timedelta(days=cfg["data"]["warmup_days"])
    loader = store.load_for_split_unlocked if unlocked else store.load_for_split
    fc = cfg["features"]
    ctx = {"split": split, "start": s, "end": e, "symbols": cfg["data"]["symbols"], "bars": {}, "feats": {},
           "m5": {}, "data_hashes": {}}
    for sym in ctx["symbols"]:
        m1 = loader(cfg, sym, split, "1m")
        m5 = loader(cfg, sym, split, "5m")
        assert m1["open_time"].max() < e and m5["open_time"].max() < e, "data beyond split end loaded"
        grid = to_grid(m5, warm, e)
        f = compute_features(grid, fc["z_window"], fc["rv_window"], fc["breakout_window"],
                             cfg["regime"]["return_lookback_candles"])
        ctx["feats"][sym] = f
        ctx["m5"][sym] = m5
        ctx["bars"][sym] = Bars(m1, s, e)
        ctx["data_hashes"][sym] = hashlib.sha256(pd.util.hash_pandas_object(m1, index=False).values.tobytes()).hexdigest()
    ctx["regime"] = regime_thresholds(cfg, ctx["feats"], split)
    return ctx


def _signal_frame(ctx: dict, sym: str, mask: pd.Series, name: str, priority: int) -> pd.DataFrame:
    s, e = ctx["start"], ctx["end"]
    f = ctx["feats"][sym]
    idx = mask.index[mask.values]
    idx = idx[(idx >= s) & (idx + pd.Timedelta(minutes=5) <= e)]
    th = ctx["regime"]["vol_threshold"].get(sym, np.nan)
    sub = f.reindex(idx)
    df = pd.DataFrame({
        "strategy": name, "symbol": sym, "priority": priority,
        "signal_open_time": idx, "decision_time": idx + pd.Timedelta(minutes=5),
        "z5": sub["z5"].values, "z15": sub["z15"].values, "r5": sub["r5"].values, "r15": sub["r15"].values,
        "rv": sub["rv"].values, "imb": sub["imb"].values,
        "regime": [regime_label(a, b, th) for a, b in zip(sub["ret24h"].values, sub["vol24h"].values)],
    })
    return df


def build_signals(cfg: dict, ctx: dict) -> dict[str, pd.DataFrame]:
    out = {}
    for name in PRIMARY:
        parts = [_signal_frame(ctx, sym, strategy_signal(ctx["feats"][sym], name, cfg["strategies"][name]), name, i)
                 for i, sym in enumerate(ctx["symbols"])]
        out[name] = pd.concat(parts, ignore_index=True)
    b01 = []
    for i, sym in enumerate(ctx["symbols"]):
        m = b01_signal(ctx["m5"][sym], sym)
        b01.append(_signal_frame(ctx, sym, m, "B01", i))
    b01 = pd.concat(b01, ignore_index=True)
    for h in cfg["baselines"]["B01"]["hold_minutes_variants"]:
        out[f"B01-h{h}"] = b01.assign(strategy=f"B01-h{h}")
    return out


def hold_for(cfg: dict, name: str) -> int:
    if name in cfg["strategies"]:
        return cfg["strategies"][name]["hold_minutes"]
    if name.startswith("B01-h"):
        return int(name.split("h")[1])
    raise ValueError(name)


# ------------------------------------------------------------------ runs

def replay(cfg, ctx, signals: pd.DataFrame, hold: int, scenario="main", risk_on=True, coarse=False):
    ex = exec_params(cfg, hold, scenario, coarse)
    rk = risk_params(cfg, risk_on)
    res = run(signals, ctx["bars"], ex, rk)
    trades = pd.DataFrame(res["trades"])
    rej = pd.DataFrame(res["rejections"])
    eq = equity_curve(res["trades"], ctx["bars"], rk.initial_equity)
    return trades, rej, pd.DataFrame(res["events"]), eq, ex


SCENARIOS = [  # (label, cost scenario, risk enabled, coarse filters)
    ("main", "main", True, False),
    ("signal_only_no_portfolio_stop", "main", False, False),
    ("cost_rt0", "rt0", True, False),
    ("cost_rt10", "rt10", True, False),
    ("cost_rt40", "rt40", True, False),
    ("delay60", "delay60", True, False),
    ("coarse_step_x10", "main", True, True),
]


def buy_and_hold(cfg, ctx, sym) -> dict:
    b = ctx["bars"][sym]
    sc = cfg["costs"]["scenarios"]["main"]
    fee, slip = sc["fee_bps"] / 1e4, sc["slip_bps"] / 1e4
    flt = filters_from_cfg(cfg)[sym]
    k0 = int(np.flatnonzero(~np.isnan(b.o))[0])
    from src.evaluation.engine import round_down, round_up
    fill_in = round_up(b.o[k0] * (1 + slip), flt.tick)
    qty = round_down(cfg["baselines"]["B02"]["stake"] / fill_in, flt.step)
    cash = cfg["risk"]["initial_equity"] - qty * fill_in * (1 + fee)
    kl = int(np.flatnonzero(~np.isnan(b.c))[-1])
    fill_out = round_down(b.c[kl] * (1 - slip), flt.tick)
    eq = cash + qty * b.c_ffill
    eq[-1] = cash + qty * fill_out * (1 - fee)
    eq = pd.Series(eq, index=pd.date_range(b.start, b.end, freq="min", inclusive="left") + pd.Timedelta(minutes=1))
    eq[: k0] = cfg["risk"]["initial_equity"]
    return {"equity": eq, "qty": qty, "fill_in": fill_in, "fill_out": fill_out,
            "net_pnl": float(eq.iloc[-1] - cfg["risk"]["initial_equity"]),
            "fees": qty * fill_in * fee + qty * fill_out * fee}


def random_benchmark(cfg, ctx, raw_signals: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bc = cfg["baselines"]["B03"]
    s, e = ctx["start"], ctx["end"]
    cands = {}
    for sym in ctx["symbols"]:
        f = ctx["feats"][sym]
        idx = f.index[f["present"].values]
        cands[sym] = idx[(idx >= s) & (idx + pd.Timedelta(minutes=5) < e)]
    rows = []
    for ti, target in enumerate(bc["match"]):
        counts = raw_signals[target]["symbol"].value_counts().to_dict()
        hold = hold_for(cfg, target)
        for i in range(bc["n_seeds"]):
            parts = []
            for si, sym in enumerate(ctx["symbols"]):
                n = int(counts.get(sym, 0))
                if n == 0:
                    continue
                times = random_signal_times(cands[sym], n, int(np.random.SeedSequence(
                    [bc["base_seed"], ti, i, si]).generate_state(1)[0]))
                parts.append(pd.DataFrame({"strategy": f"B03~{target}", "symbol": sym, "priority": si,
                                           "signal_open_time": times, "decision_time": times + pd.Timedelta(minutes=5)}))
            sig = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
                columns=["strategy", "symbol", "priority", "signal_open_time", "decision_time"])
            if len(sig) == 0:
                rows.append({"target": target, "seed_index": i, "n_signals": 0, **trade_stats(pd.DataFrame())})
                continue
            tr, rej, ev, eq, ex = replay(cfg, ctx, sig, hold)
            st = trade_stats(tr)
            dd = eq - eq.cummax()
            rows.append({"target": target, "seed_index": i, "n_signals": int(len(sig)), **st,
                         "final_equity": float(eq.iloc[-1]), "max_drawdown_usdt": float(-dd.min())})
    return pd.DataFrame(rows)


def event_study(cfg, ctx, raw_signals) -> pd.DataFrame:
    hz = cfg["evaluation"]["event_study_horizons_min"]
    rows = []
    s, e = ctx["start"], ctx["end"]
    for sym in ctx["symbols"]:
        b = ctx["bars"][sym]
        f = ctx["feats"][sym]
        idx = f.index[f["present"].values & f["z5"].notna().values]
        idx = idx[(idx >= s) & (idx + pd.Timedelta(minutes=5) <= e)]
        bg = es.forward_returns(b, pd.Series(idx + pd.Timedelta(minutes=5)), hz)
        for h in hz:
            rows.append({"group": "background_all_5m", "symbol": sym, "horizon_min": h, **es.summarize(bg[f"fwd_{h}m"])})
    for name, sig in raw_signals.items():
        if name.startswith("B01"):
            continue
        for sym, g in list(sig.groupby("symbol")) + [("ALL", sig)]:
            if len(g) == 0:
                continue
            parts = []
            for s2, g2 in g.groupby("symbol"):
                parts.append(es.forward_returns(ctx["bars"][s2], g2["decision_time"].reset_index(drop=True), hz))
            fr = pd.concat(parts, ignore_index=True)
            for h in hz:
                rows.append({"group": name, "symbol": sym, "horizon_min": h, **es.summarize(fr[f"fwd_{h}m"])})
    # pooled background
    pooled = []
    for sym in ctx["symbols"]:
        f = ctx["feats"][sym]
        idx = f.index[f["present"].values & f["z5"].notna().values]
        idx = idx[(idx >= s) & (idx + pd.Timedelta(minutes=5) <= e)]
        pooled.append(es.forward_returns(ctx["bars"][sym], pd.Series(idx + pd.Timedelta(minutes=5)), hz))
    pooled = pd.concat(pooled, ignore_index=True)
    for h in hz:
        rows.append({"group": "background_all_5m", "symbol": "ALL", "horizon_min": h, **es.summarize(pooled[f"fwd_{h}m"])})
    return pd.DataFrame(rows)


def run_split(cfg: dict, split: str, out_root: Path | None = None, smoke_days: int | None = None,
              n_seeds: int | None = None, unlocked: bool = False) -> Path:
    if split == "test" and not unlocked:
        raise PermissionError("locked test split requires the holdout gate")
    if n_seeds is not None:
        cfg = {**cfg, "baselines": {**cfg["baselines"], "B03": {**cfg["baselines"]["B03"], "n_seeds": n_seeds}}}
    ctx = prepare(cfg, split, unlocked=unlocked)
    label = split
    if smoke_days:
        # restrict the evaluated segment to the first `smoke_days` days (warmup unchanged)
        new_end = ctx["start"] + pd.Timedelta(days=smoke_days)
        ctx["end"] = new_end
        for sym in ctx["symbols"]:
            b = ctx["bars"][sym]
            nb = Bars.__new__(Bars)
            n = int((new_end - b.start).value // 60_000_000_000)
            nb.start, nb.end, nb.n, nb.start_min = b.start, new_end, n, b.start_min
            nb.o, nb.h, nb.l, nb.c, nb.c_ffill = b.o[:n], b.h[:n], b.l[:n], b.c[:n], b.c_ffill[:n]
            ctx["bars"][sym] = nb
        label = f"{split}_smoke{smoke_days}d"
    s, e = ctx["start"], ctx["end"]
    raw = build_signals(cfg, ctx)
    initial = cfg["risk"]["initial_equity"]
    ev = cfg["evaluation"]
    all_trades, all_rej, all_events, metrics, equities, recon = [], [], [], {}, {}, {}
    for name, sig in raw.items():
        hold = hold_for(cfg, name)
        metrics[name] = {"n_raw_signals": int(len(sig)),
                         "raw_signals_by_symbol": {k: int(v) for k, v in sig["symbol"].value_counts().sort_index().items()},
                         "hold_minutes": hold, "scenarios": {}}
        for lab, sc, risk_on, coarse in SCENARIOS:
            tr, rej, evts, eq, ex = replay(cfg, ctx, sig, hold, sc, risk_on, coarse)
            m = compute_metrics(tr, rej, eq, initial, s, e, ev["windows_days"], ev["rolling_days"], ev["annualization_days"])
            if lab == "main":
                m["by_symbol"] = group_stats(tr, "symbol")
                m["by_regime"] = group_stats(tr, "regime")
                m["risk_events"] = evts.assign(time=evts["time"].astype(str)).to_dict("records") if len(evts) else []
                dp = daily_pnl(eq, initial)
                m["bootstrap"] = {f"block_{b}d": bs.block_bootstrap(dp, b, ev["bootstrap"]["n_boot"], ev["bootstrap"]["seed"],
                                                                   ev["bootstrap"]["min_blocks"])
                                  for b in [ev["bootstrap"]["block_days"]] + ev["bootstrap"]["sensitivity_block_days"]}
                m["windows_detail"] = {f"{w}d": window_table(eq, tr, initial, s, e, w)["rows"] for w in ev["windows_days"]}
                equities[name] = eq
                recon[name] = reconcile(tr, initial, ex.fee, ex.filters) if len(tr) else {"n_trades": 0, "ok": True,
                                                                                              "issues": []}
            if lab == "signal_only_no_portfolio_stop":
                m["by_symbol"] = group_stats(tr, "symbol")
                m["by_regime"] = group_stats(tr, "regime")
            if lab == "cost_rt0" and len(tr):
                m["break_even_roundtrip_cost_bps"] = round(1e4 * tr["gross_pnl"].sum() / tr["notional_in"].sum(), 4)
            metrics[name]["scenarios"][lab] = m
            if len(tr):
                all_trades.append(tr.assign(scenario=lab))
            if len(rej):
                all_rej.append(rej.assign(scenario=lab))
            if len(evts):
                all_events.append(evts.assign(scenario=lab, strategy=name))
    # fixed-signal break-even on main-scenario signal set (signal-only, zero cost) for the primary candidates
    # baselines
    metrics["B00-cash"] = {"net_pnl": 0.0, "return_pct": 0.0, "n_trades": 0, "note": "cash, before any external costs"}
    for sym in ctx["symbols"]:
        bh = buy_and_hold(cfg, ctx, sym)
        dd = bh["equity"] - bh["equity"].cummax()
        metrics[f"B02-BH-{sym}"] = {"net_pnl": round(bh["net_pnl"], 6), "return_pct": round(bh["net_pnl"] / initial * 100, 6),
                                     "max_drawdown_usdt": round(float(-dd.min()), 6), "fees": round(bh["fees"], 6),
                                     "exposure_pct_time": 100.0, "stake": cfg["baselines"]["B02"]["stake"],
                                     "note": "single $50 buy at segment start, mark-to-market, sold at segment end; "
                                             "no stop/risk limits: different risk and exposure than E01/E02"}
        equities[f"B02-BH-{sym}"] = bh["equity"]
    rnd = random_benchmark(cfg, ctx, raw)
    rnd_summary = {}
    for tgt, g in rnd.groupby("target"):
        real = metrics[tgt]["scenarios"]["main"]["net_pnl"]
        q = g["net_pnl"].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).round(6).tolist()
        rnd_summary[tgt] = {"n_seeds": int(len(g)), "net_pnl_quantiles_5_25_50_75_95": q,
                            "mean_net_pnl": round(float(g["net_pnl"].mean()), 6),
                            "mean_n_trades": round(float(g["n_trades"].mean()), 3),
                            "strategy_net_pnl": real,
                            "share_seeds_ge_strategy": round(float((g["net_pnl"] >= real).mean()), 4),
                            "note": "frequency-matched random entries; a conditional benchmark, not a strategy"}
    metrics["B03-random"] = rnd_summary
    evs = event_study(cfg, ctx, raw)
    # multiple testing across the 4 candidates (main scenario, 7-day blocks)
    pv = {}
    for name in PRIMARY:
        b = metrics[name]["scenarios"]["main"]["bootstrap"][f"block_{ev['bootstrap']['block_days']}d"]
        pv[name] = b.get("p_one_sided_mean_gt_0") if b.get("status") == "ok" else None
    metrics["holm"] = bs.holm(pv)
    # ------------------------------------------------------------- write outputs
    cfg_hash, chash = cfg["_hash"], code_hash()
    run_id = f"{label}_{chash[:10]}_{cfg_hash[:8]}"
    out_root = out_root or (ROOT / "reports" / "runs")
    out = out_root / run_id
    out.mkdir(parents=True, exist_ok=True)
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    rejs = pd.concat(all_rej, ignore_index=True) if all_rej else pd.DataFrame()
    trades_cols = ["strategy", "scenario", "symbol", "priority", "signal_open_time", "decision_time", "entry_time",
                   "exit_time", "exit_reason", "raw_entry", "fill_entry", "qty", "notional_in", "fee_in", "stop_level",
                   "target_level", "raw_exit", "fill_exit", "notional_out", "fee_out", "gross_pnl", "fees",
                   "slippage_cost", "net_pnl", "cash_before", "cash_after_entry", "cash_after", "hold_minutes_actual",
                   "uncertain_gap", "conservative_net_delta", "regime", "z5", "z15", "r5", "r15", "rv", "imb",
                   "entry_minute", "exit_minute"]
    if len(trades):
        trades = trades[[c for c in trades_cols if c in trades.columns]]
        trades = trades.sort_values(["strategy", "scenario", "entry_time"], kind="mergesort").reset_index(drop=True)
    trades.to_csv(out / "trades.csv", index=False, float_format="%.10g")
    trades.to_parquet(out / "trades.parquet", index=False)
    rejs.to_csv(out / "rejected_signals.csv", index=False, float_format="%.10g")
    sig_all = pd.concat(raw.values(), ignore_index=True)
    sig_all.to_csv(out / "signals.csv", index=False, float_format="%.10g")
    eqdf = pd.DataFrame(equities)
    eqdf.index.name = "time_bar_close"
    eqdf.to_parquet(out / "equity.parquet")
    eqdf.resample("1h", label="right", closed="right").last().to_csv(out / "equity_hourly.csv", float_format="%.6f")
    rnd.to_csv(out / "random_benchmark.csv", index=False, float_format="%.8g")
    evs.to_csv(out / "event_study.csv", index=False)
    if all_events:
        pd.concat(all_events, ignore_index=True).to_csv(out / "risk_events.csv", index=False)
    (out / "metrics.json").write_text(dumps(metrics))
    (out / "reconciliation.json").write_text(dumps(recon))
    manifest = {
        "experiment_id": cfg["experiment_id"], "split": split, "label": label,
        "segment": [str(s), str(e)], "config_file": cfg["_path"], "config_sha256": cfg_hash,
        "regime_thresholds_sha256": file_sha256(ROOT / cfg["regime"]["thresholds_file"]),
        "code_sha256": chash, "git_commit": git_commit(),
        "data_sha256_1m_split": ctx["data_hashes"],
        "data_manifest_sha256": file_sha256(ROOT / cfg["data"]["manifest"]),
        "freqtrade_sample_strategy_sha256": sample_strategy_sha256(),
        "outputs_sha256": {p.name: file_sha256(p) for p in sorted(out.iterdir())
                           if p.suffix in {".csv", ".json"} and p.name not in {"manifest.json", "run_info.json"}},
    }
    (out / "manifest.json").write_text(dumps(manifest))
    (out / "run_info.json").write_text(dumps({"created_utc": dt.datetime.now(dt.timezone.utc).isoformat()}))
    from src.evaluation.report import write_report
    write_report(cfg, out, metrics, manifest, recon, trades, rnd, evs, ctx)
    return out
