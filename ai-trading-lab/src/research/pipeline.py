"""v0.2 research pipeline for one split (development or validation). Locked test only via approved gate."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.config import ROOT, code_hash, dumps, file_sha256, git_commit, ts
from src.evaluation.engine import Filters
from src.research import stats as S
from src.research.data import load_1m, load_bars
from src.research.features import (crosses_boundary, g01_asset_features, g01_design, grid, hourly_sigma, labels,
                                   logret, net_from_gross, trend30d)
from src.research.models import RidgeFit, calib_edges, fit_times, model_id_for, train_mask
from src.research.replay import Costs, Params, Px, equity_1m, passive, run

FAM_MAX_H = {"G01": 240, "H01": 240, "H02": 1440, "H03": 10080}
SCEN = ["main", "rt0", "rt10", "rt40"]


# ------------------------------------------------------------------ context

def split_bounds(cfg, split):
    s = cfg["splits"][split]
    return ts(s["start"]), ts(s["end"])


def load_ctx(cfg: dict, split: str, unlocked: bool = False) -> dict:
    if cfg["splits"][split].get("locked") and not unlocked:
        raise PermissionError("locked historical test split: requires an approval artifact")
    s, e = split_bounds(cfg, split)
    forb = ts(cfg["splits"]["forbidden"]["start"])
    assert e <= forb, "MVP v0.1 period must never be used"
    g0 = pd.Timestamp(cfg["data"]["first_month"] + "-01", tz="UTC")
    traded, info = cfg["data"]["traded"], cfg["data"]["info_assets"]
    px = {sym: Px(load_1m(cfg, sym, g0, e), g0, e) for sym in traded}
    bars = {30: {a: grid(load_bars(cfg, a, 30, e), 30, g0, e) for a in info}}
    for m in (60, 240, 1440):
        bars[m] = {a: grid(load_bars(cfg, a, m, e), m, g0, e) for a in traded}
    first_fit = ts(cfg["fitting"]["first_fit"])
    ctx = {"split": split, "start": s, "end": e, "g0": g0, "traded": traded, "info": info, "px": px, "bars": bars,
           "eval_start": max(s, first_fit), "fits": fit_times(first_fit, s, e),
           "boundaries": [ts(cfg["splits"]["validation"]["start"]), ts(cfg["splits"]["test"]["start"])],
           "window": cfg["fitting"]["train_window_days"], "d1": cfg["execution"]["entry_delay_min"],
           "d5": cfg["execution"]["stress_delay_min"]}
    # regime inputs (hourly, causal: value at the last closed hourly bar <= T)
    ctx["sigma1h"] = {a: hourly_sigma(bars[60][a]["close"], cfg["execution"]["sigma_lookback_days"]) for a in traded}
    ctx["trend30"] = {a: trend30d(bars[60][a]["close"]) for a in traded}
    ctx["data_sha"] = {a: hashlib.sha256(pd.util.hash_pandas_object(
        pd.DataFrame({"o": px[a].o, "c": px[a].c}), index=False).values.tobytes()).hexdigest() for a in traded}
    return ctx


def asof(series: pd.Series, T: pd.DatetimeIndex) -> np.ndarray:
    return series.reindex(series.index.union(T)).ffill().reindex(T).to_numpy()


def eval_mask(ctx, T: pd.DatetimeIndex, fam: str) -> np.ndarray:
    last = ctx["end"] - pd.Timedelta(minutes=ctx["d5"] + FAM_MAX_H[fam])
    return np.asarray((T >= ctx["eval_start"]) & (T <= last))


def vol_thresholds(ctx, F) -> dict:
    out = {}
    for a in ctx["traded"]:
        s = ctx["sigma1h"][a]
        w = s[(s.index >= F - pd.Timedelta(days=ctx["window"])) & (s.index < F)].dropna()
        out[a] = float(w.median()) if len(w) else np.nan
    return out


def _common_cols(ctx, df: pd.DataFrame, fits_vol: list[dict]) -> pd.DataFrame:
    T = pd.DatetimeIndex(df["T"])
    df["sigma1h"] = np.nan
    df["trend30"] = np.nan
    df["vol_regime"] = "undefined"
    for a in ctx["traded"]:
        m = (df["symbol"] == a).to_numpy()
        if not m.any():
            continue
        Ta = T[m]
        df.loc[m, "sigma1h"] = asof(ctx["sigma1h"][a], Ta)
        df.loc[m, "trend30"] = asof(ctx["trend30"][a], Ta)
        thr = np.array([fits_vol[i][a] if i >= 0 else np.nan for i in df.loc[m, "fit_id"].to_numpy()])
        sg = df.loc[m, "sigma1h"].to_numpy()
        df.loc[m, "vol_regime"] = np.where(~np.isfinite(sg) | ~np.isfinite(thr), "undefined",
                                           np.where(sg >= thr, "highvol", "lowvol"))
    df["trend_regime"] = np.where(~np.isfinite(df["trend30"]), "undefined",
                                  np.where(df["trend30"] >= 0, "bull", "bear"))
    df["year"] = T.year
    return df


# ------------------------------------------------------------------ G01

def g01_panel(cfg, ctx) -> dict:
    fc = cfg["families"]["G01"]
    af = {a: g01_asset_features(ctx["bars"][30][a], fc["return_lookbacks_min"], fc["vol_window_bars"],
                                fc["rv_window_bars"]) for a in ctx["info"]}
    fits = ctx["fits"]
    fits_vol = [vol_thresholds(ctx, F) for F in fits]
    rows, coefs, insample = [], [], {}
    for a in ctx["traded"]:
        b1, x, valid = g01_design(af, a, fc["return_lookbacks_min"])
        T = b1.index
        fid = model_id_for(T, fits)
        em = eval_mask(ctx, T, "G01") & valid.to_numpy() & (fid >= 0)
        for H in fc["horizons_min"]:
            y = labels(ctx["px"][a], T, H, ctx["d1"])
            y5 = labels(ctx["px"][a], T, H, ctx["d5"])
            cr = crosses_boundary(T, H, ctx["d5"], ctx["boundaries"])
            pred = {m: np.full(len(T), np.nan) for m in ("B0", "B1", "X")}
            for i, F in enumerate(fits):
                tm = np.asarray(train_mask(T, F, ctx["window"], ctx["d1"], H, cr)) & valid.to_numpy() & np.isfinite(y)
                om = em & (fid == i)
                wid = f"{F.date()}[{(F - pd.Timedelta(days=ctx['window'])).date()},{F.date()})"
                if tm.sum() < 2:
                    coefs.append({"target": a, "H": H, "fit": str(F), "window": wid, "status": "no_train"})
                    continue
                pred["B0"][om] = y[tm].mean()
                for name, X in (("B1", b1), ("X", x)):
                    rf = RidgeFit(cfg["fitting"]["ridge_alpha"]).fit(X[tm], y[tm])
                    if om.any():
                        pred[name][om] = rf.predict(X[om])
                    ins = rf.predict(X[tm])
                    edges = calib_edges(ins)
                    coefs.append({"target": a, "H": H, "model": name, "fit": str(F), "window": wid,
                                  "calib_edges": json.dumps([float(v) for v in edges]), **rf.coef_record()})
                    if name == "X" and H == fc["primary_horizon_min"]:
                        insample.setdefault(i, {})[a] = pd.Series(ins, index=T[tm])
                coefs.append({"target": a, "H": H, "model": "B0", "fit": str(F), "window": wid,
                              "intercept": float(y[tm].mean()), "n_train": int(tm.sum())})
            sel = em
            rows.append(pd.DataFrame({"T": T[sel], "symbol": a, "H": H, "fit_id": fid[sel], "y": y[sel], "y5": y5[sel],
                                      "pred_B0": pred["B0"][sel], "pred_B1": pred["B1"][sel], "pred_X": pred["X"][sel]}))
    df = pd.concat(rows, ignore_index=True)
    df = _common_cols(ctx, df, fits_vol)
    # random-baseline frequencies from TRAIN only: share of train decisions where target s is the argmax X
    # prediction above 0 (in-sample fitted values of the current fit)
    freq = {}
    for i, d in insample.items():
        m = pd.concat(d, axis=1).dropna()
        best = m.idxmax(axis=1).where(m.max(axis=1) > 0)
        freq[i] = {a: float((best == a).mean()) for a in ctx["traded"]}
    return {"panel": df, "coefs": pd.DataFrame(coefs), "rand_freq": freq, "fits_vol": fits_vol}


def g01_forecast_metrics(cfg, ctx, df: pd.DataFrame) -> dict:
    out = {"per_target": {}, "aggregate": {}}
    st = cfg["statistics"]["bootstrap"]
    coefs = None
    for H, g in df.groupby("H"):
        g = g[np.isfinite(g["y"]) & np.isfinite(g["pred_X"]) & np.isfinite(g["pred_B1"]) & np.isfinite(g["pred_B0"])]
        res = {}
        for a, ga in g.groupby("symbol"):
            y = ga["y"].to_numpy()
            r = {"n": int(len(ga))}
            for m in ("B0", "B1", "X"):
                p = ga[f"pred_{m}"].to_numpy()
                r[m] = {"mse": float(np.mean((y - p) ** 2)), "mae": float(np.mean(np.abs(y - p))),
                        "rank_ic": float(spearmanr(p, y).statistic) if m != "B0" else None,
                        "signed_return_mean": float(np.mean(np.sign(p) * y)),
                        "cond_gross_pred_gt0": float(y[p > 0].mean()) if (p > 0).any() else None,
                        "share_pred_gt0": float((p > 0).mean())}
            for m in ("B1", "X"):
                r[m]["r2_vs_B0"] = 1 - r[m]["mse"] / r["B0"]["mse"]
            r["mse_B1_minus_X"] = r["B1"]["mse"] - r["X"]["mse"]
            for yr, gy in ga.groupby(ga["T"].dt.year):
                yy = gy["y"].to_numpy()
                r.setdefault("by_year_mse_B1_minus_X", {})[str(yr)] = float(np.mean((yy - gy["pred_B1"]) ** 2) -
                                                                            np.mean((yy - gy["pred_X"]) ** 2))
            for rg, gr in ga.groupby("trend_regime"):
                yy = gr["y"].to_numpy()
                r.setdefault("by_trend_mse_B1_minus_X", {})[rg] = float(np.mean((yy - gr["pred_B1"]) ** 2) -
                                                                        np.mean((yy - gr["pred_X"]) ** 2))
            for rg, gr in ga.groupby("vol_regime"):
                yy = gr["y"].to_numpy()
                r.setdefault("by_vol_mse_B1_minus_X", {})[rg] = float(np.mean((yy - gr["pred_B1"]) ** 2) -
                                                                      np.mean((yy - gr["pred_X"]) ** 2))
            res[a] = r
        out["per_target"][str(H)] = res
        # paired day-block bootstrap on the common UTC-day axis (aggregate = equal-weight mean over targets)
        g = g.assign(day=g["T"].dt.floor("D"), d=(g["y"] - g["pred_B1"]) ** 2 - (g["y"] - g["pred_X"]) ** 2,
                     one=1.0)
        days = pd.date_range(g["day"].min(), g["day"].max(), freq="D")
        num = g.pivot_table(index="day", columns="symbol", values="d", aggfunc="sum").reindex(days).fillna(0)
        den = g.pivot_table(index="day", columns="symbol", values="one", aggfunc="sum").reindex(days).fillna(0)
        agg = {}
        for b in st["blocks_days"]:
            agg[f"block_{b}d"] = S.ratio_bootstrap(num.to_numpy(), den.to_numpy(), b, st["n_boot"], st["seed"],
                                                   st["min_blocks"])
            agg[f"block_{b}d"]["per_target"] = {
                a: S.ratio_bootstrap(num[[a]].to_numpy(), den[[a]].to_numpy(), b, st["n_boot"], st["seed"],
                                     st["min_blocks"]) for a in num.columns}
        out["aggregate"][str(H)] = agg
        # calibration on OOS with train edges is in calibration table (built by report from panel+coefs)
    return out


def calibration_table(df: pd.DataFrame, coefs: pd.DataFrame, fits: list) -> pd.DataFrame:
    rows = []
    edges = {(r.target, r.H, r.model, r.fit): json.loads(r.calib_edges) for r in coefs.itertuples()
             if isinstance(getattr(r, "calib_edges", None), str)}
    for (a, H), g in df.groupby(["symbol", "H"]):
        for m in ("B1", "X"):
            parts = []
            for fid, gf in g.groupby("fit_id"):
                e = edges.get((a, H, m, str(fits[fid])))
                if e is None:
                    continue
                parts.append(gf.assign(bin=np.searchsorted(np.array(e), gf[f"pred_{m}"].to_numpy(), side="right")))
            if not parts:
                continue
            gg = pd.concat(parts)
            gg = gg[np.isfinite(gg["y"])]
            for b, gb in gg.groupby("bin"):
                rows.append({"symbol": a, "H": H, "model": m, "train_decile_bin": int(b), "n": int(len(gb)),
                             "mean_pred": float(gb[f"pred_{m}"].mean()), "mean_realized": float(gb["y"].mean())})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ H01-H03

def h_panel(cfg, ctx, fam: str) -> dict:
    fc = cfg["families"][fam]
    gm = fc["grid_min"]
    fits = ctx["fits"]
    fits_vol = [vol_thresholds(ctx, F) for F in fits]
    rows, fitrec = [], []
    minev = cfg["fitting"]["min_events_conditional"]
    for a in ctx["traded"]:
        if fam == "H01":
            c = ctx["bars"][60][a]["close"]
            x1 = logret(c, 1)
            inputs = pd.DataFrame({"r1h": x1})
        elif fam == "H02":
            c = ctx["bars"][240][a]["close"]
            inputs = pd.DataFrame({"r4h": logret(c, 1), "r24h": logret(c, 6)})
        else:
            c = ctx["bars"][1440][a]["close"]
            inputs = pd.DataFrame({"r7d": logret(c, 7), "r28d": logret(c, 28)})
        T = inputs.index
        valid_in = inputs.notna().all(axis=1).to_numpy()
        fid = model_id_for(T, fits)
        em = eval_mask(ctx, T, fam) & valid_in & (fid >= 0)
        # signal per fit (H01 threshold is fit-specific; H02/H03 are fixed rules)
        q = np.full(len(fits), np.nan)
        if fam == "H01":
            for i, F in enumerate(fits):
                w = x1[(T >= F - pd.Timedelta(days=ctx["window"])) & (T < F)].dropna()
                q[i] = float(np.quantile(w, fc["quantile"])) if len(w) else np.nan

        def signal_with(thr):
            if fam == "H01":
                return valid_in & (inputs["r1h"].to_numpy() <= thr)
            if fam == "H02":
                return valid_in & (inputs["r4h"].to_numpy() > 0) & (inputs["r24h"].to_numpy() > 0)
            return valid_in & (inputs["r7d"].to_numpy() > 0) & (inputs["r28d"].to_numpy() > 0)

        sig_oos = np.zeros(len(T), dtype=bool)
        for i in range(len(fits)):
            m = fid == i
            sig_oos[m] = signal_with(q[i])[m]
        for H in fc["horizons_min"]:
            y = labels(ctx["px"][a], T, H, ctx["d1"])
            y5 = labels(ctx["px"][a], T, H, ctx["d5"])
            cr = crosses_boundary(T, H, ctx["d5"], ctx["boundaries"])
            est = np.full(len(T), np.nan)
            for i, F in enumerate(fits):
                s_tr = signal_with(q[i])
                tm = np.asarray(train_mask(T, F, ctx["window"], ctx["d1"], H, cr)) & s_tr & np.isfinite(y)
                n_ev = int(tm.sum())
                e_val = float(y[tm].mean()) if n_ev >= minev else np.nan
                est[(fid == i) & em] = e_val
                tm_all = np.asarray(train_mask(T, F, ctx["window"], ctx["d1"], H, cr)) & valid_in
                freq = float(s_tr[tm_all].mean()) if tm_all.any() else np.nan
                fitrec.append({"family": fam, "target": a, "H": H, "fit": str(F),
                               "window": f"[{(F - pd.Timedelta(days=ctx['window'])).date()},{F.date()})",
                               "h01_q20": q[i] if fam == "H01" else None, "train_events": n_ev,
                               "cond_gross_estimate": e_val, "train_signal_freq": freq})
            sel = em
            df = pd.DataFrame({"T": T[sel], "symbol": a, "H": H, "fit_id": fid[sel], "signal": sig_oos[sel],
                               "est": est[sel], "y": y[sel], "y5": y5[sel]})
            for col in inputs.columns:
                df[col] = inputs[col].to_numpy()[sel]
            rows.append(df)
    df = pd.concat(rows, ignore_index=True)
    df = _common_cols(ctx, df, fits_vol)
    return {"panel": df, "fits": pd.DataFrame(fitrec), "fits_vol": fits_vol}


# ------------------------------------------------------------------ intents

def choose(panel: pd.DataFrame, eligible: np.ndarray, score: np.ndarray, order: list[str], H: int,
           extra: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One candidate per decision time: max score among eligible, ties -> fixed symbol order.
    Returns (intents, candidate log)."""
    c = panel.loc[eligible].copy()
    c["score"] = score[eligible]
    c["prio"] = c["symbol"].map({s: i for i, s in enumerate(order)})
    c = c.sort_values(["T", "score", "prio"], ascending=[True, False, True], kind="mergesort")
    first = ~c["T"].duplicated(keep="first")
    c["selected"] = first.to_numpy()
    c["candidate_reason"] = np.where(c["selected"], "selected", "lower_rank_same_T")
    it = c[c["selected"]].copy()
    it["hold_min"] = H
    if extra:
        for k, v in extra.items():
            it[k] = v
    return it.reset_index(drop=True), c


def stake_risk_matched(it: pd.DataFrame, budget: float, cap: float) -> np.ndarray:
    s = it["sigma1h"].to_numpy()
    h = it["hold_min"].to_numpy() / 60
    with np.errstate(divide="ignore", invalid="ignore"):
        st = np.minimum(cap, budget / (s * np.sqrt(h)))
    return np.where(np.isfinite(st) & (s > 0), st, np.nan)


# ------------------------------------------------------------------ replays

def params(cfg, scen="main", risk_on=False, delay=None) -> Params:
    c = cfg["costs"][scen]
    ex = cfg["execution"]
    return Params(costs=Costs(c["fee_bps"] / 1e4, c["slip_bps"] / 1e4),
                  delay_min=delay if delay is not None else ex["entry_delay_min"], stake=ex["stake_usdt"],
                  initial=ex["initial_equity"], risk_on=risk_on, daily_limit=cfg["risk"]["daily_loss_limit"],
                  total_limit=cfg["risk"]["total_loss_limit"],
                  filters={s: Filters(v["tick_size"], v["step_size"], v["min_notional"])
                           for s, v in ex["filters"].items()})


def rt_cost(cfg, scen) -> float:
    c = cfg["costs"][scen]
    return 2 * (c["fee_bps"] + c["slip_bps"]) / 1e4


def replay_variant(cfg, ctx, intents: pd.DataFrame, p: Params, full: bool = True) -> dict:
    s, e = ctx["eval_start"], ctx["end"]
    res = run(intents, ctx["px"], p, s, e)
    tr = pd.DataFrame(res["trades"])
    rj = pd.DataFrame(res["rejections"])
    eq = equity_1m(res["trades"], ctx["px"], s, e, p.initial)
    out = {"trades": tr, "rejections": rj, "events": res["events"], "equity": eq}
    if full:
        m = S.compute_metrics(tr if len(tr) else pd.DataFrame(columns=["net_pnl"]), rj, eq, p.initial, s, e)
        m.update(S.extra_metrics(eq, p.initial))
        if len(tr):
            m["yearly"] = S.yearly(tr, eq, p.initial)
            for g in ("symbol", "trend_regime", "vol_regime"):
                if g in tr:
                    m[f"by_{g}"] = {str(k): S.trade_stats(v) for k, v in tr.groupby(g)}
            m["gross_expectancy"] = float(tr["gross_pnl"].mean())
            m["break_even_rt_bps_static"] = float(1e4 * tr["gross_pnl"].sum() / tr["notional_in"].sum())
            m["avg_notional"] = float(tr["notional_in"].mean())
        m["risk_events"] = [{k: str(v) if isinstance(v, pd.Timestamp) else v for k, v in ev.items()}
                            for ev in res["events"]]
        m["n_intents"] = int(len(intents))
        out["metrics"] = m
    return out


def static_costs(tr: pd.DataFrame, cfg) -> dict:
    """Static-signal sensitivity: same entries/exits/quantities, costs recomputed (no rounding effects)."""
    out = {}
    if len(tr) == 0:
        return out
    for sc in SCEN:
        c = cfg["costs"][sc]
        f, s = c["fee_bps"] / 1e4, c["slip_bps"] / 1e4
        ni = tr["qty"] * tr["raw_entry"] * (1 + s)
        no = tr["qty"] * tr["raw_exit"] * (1 - s)
        out[sc] = float((no * (1 - f) - ni * (1 + f)).sum())
    return out


# ------------------------------------------------------------------ main

def variant_specs(cfg) -> list[dict]:
    c = cfg["costs"]["hurdle_c"]
    specs = []
    g = cfg["families"]["G01"]
    for H in g["horizons_min"]:
        for m in g["models"]:
            for k, thr in (("0", 0.0), ("c", c), ("2c", 2 * c)):
                specs.append({"name": f"G01-{m}-H{H}-thr{k}", "family": "G01", "H": H, "model": m, "thr": k,
                              "primary": H == g["primary_horizon_min"]})
    for fam in ("H01", "H02", "H03"):
        hs = cfg["families"][fam]["horizons_min"]
        for H in hs:
            for k in ("none", "common", "c", "2c"):
                specs.append({"name": f"{fam}-H{H}-{k}", "family": fam, "H": H, "filter": k, "primary": H == hs[0]})
    return specs


def intents_for(spec, cfg, panels, ctx, hurdle_c: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    order = ctx["traded"]
    fam, H = spec["family"], spec["H"]
    pan = panels[fam]["panel"]
    pan = pan[pan["H"] == H].reset_index(drop=True)
    if fam == "G01":
        thr = {"0": 0.0, "c": hurdle_c, "2c": 2 * hurdle_c}[spec["thr"]]
        p = pan[f"pred_{spec['model']}"].to_numpy()
        elig = np.isfinite(p) & (p > thr)
        return choose(pan, elig, p, order, H, {"variant": spec["name"]})
    sig = pan["signal"].to_numpy()
    est = pan["est"].to_numpy()
    f = spec["filter"]
    if f == "none":
        elig = sig
    elif f == "common":
        elig = sig & np.isfinite(est)
    else:
        thr = hurdle_c if f == "c" else 2 * hurdle_c
        elig = sig & np.isfinite(est) & (est > thr)
    score = np.zeros(len(pan))  # binary signal: ties resolved by fixed BTC, ETH, SOL order
    return choose(pan, elig, score, order, H, {"variant": spec["name"]})


def random_intents(fam, cfg, panels, ctx, seed: int, fam_idx: int) -> pd.DataFrame:
    """Frequency-matched random entries on the same decision grid and hold (frequencies from TRAIN windows)."""
    order = ctx["traded"]
    H = cfg["families"][fam]["horizons_min"][0] if fam != "G01" else cfg["families"]["G01"]["primary_horizon_min"]
    pan = panels[fam]["panel"]
    pan = pan[pan["H"] == H]
    rng = np.random.default_rng([seed, fam_idx])
    Ts = pd.DatetimeIndex(sorted(pan["T"].unique()))
    fid = model_id_for(Ts, ctx["fits"])
    n = len(Ts)
    P = np.zeros((n, len(order)))
    if fam == "G01":
        fr = panels["G01"]["rand_freq"]
        for j, a in enumerate(order):
            P[:, j] = [fr.get(int(i), {}).get(a, 0.0) for i in fid]
        u = rng.random(n)
        cum = np.cumsum(P, axis=1)
        pick = (u[:, None] >= cum).sum(axis=1)          # index of the drawn category; len(order) = none
    else:
        fits = panels[fam]["fits"]
        fq = fits[fits["H"] == H].set_index(["target", "fit"])["train_signal_freq"].to_dict()
        fit_str = [str(ctx["fits"][i]) for i in fid]
        for j, a in enumerate(order):
            P[:, j] = [fq.get((a, F), 0.0) for F in fit_str]
        P = np.nan_to_num(P)
        hit = rng.random((n, len(order))) < P
        pick = np.where(hit.any(axis=1), hit.argmax(axis=1), len(order))  # first hit in BTC, ETH, SOL order
    m = pick < len(order)
    rows = list(zip(Ts[m], np.array(order)[pick[m]]))
    it = pd.DataFrame(rows, columns=["T", "symbol"])
    it["hold_min"] = H
    return it


def run_split(cfg: dict, split: str, out_root: Path | None = None, n_seeds: int | None = None,
              unlocked: bool = False, smoke_days: int | None = None) -> Path:
    ctx = load_ctx(cfg, split, unlocked)
    label = split
    if smoke_days:
        ctx["end"] = ctx["eval_start"] + pd.Timedelta(days=smoke_days)
        label = f"{split}_smoke{smoke_days}d"
    panels = {"G01": g01_panel(cfg, ctx)}
    for fam in ("H01", "H02", "H03"):
        panels[fam] = h_panel(cfg, ctx, fam)
    c = cfg["costs"]["hurdle_c"]
    specs = variant_specs(cfg)
    metrics = {"variants": {}, "controls": {}, "random": {}, "primary_tests": {}, "event_study": {}}
    trades_all, rej_all, daily = [], [], {}
    hourly = {}
    primary_daily = {}
    for sp in specs:
        it, cand = intents_for(sp, cfg, panels, ctx, c)
        is_prim_set = sp["primary"] and (sp["family"] != "G01" or sp["thr"] in ("0", "c"))
        scen_list = [("diag_main", "main", False, None)]
        if is_prim_set:
            scen_list += [("constrained_main", "main", True, None), ("diag_rt0", "rt0", False, None),
                          ("diag_rt10", "rt10", False, None), ("diag_rt40", "rt40", False, None),
                          ("diag_delay5", "main", False, ctx["d5"]), ("diag_risk_matched", "main", False, None)]
        vm = {"n_candidates": int(len(cand)), "n_intents": int(len(it)), "scenarios": {}}
        for lab, sc, risk_on, delay in scen_list:
            hurdle = rt_cost(cfg, sc)
            its = it
            if lab.startswith("diag_rt") and (sp.get("filter") in ("c", "2c") or sp.get("thr") in ("c", "2c")):
                its, _ = intents_for(sp, cfg, panels, ctx, hurdle)   # full replay with recomputed hurdle
            if lab == "diag_risk_matched":
                its = its.copy()
                its["stake"] = stake_risk_matched(its, cfg["execution"]["risk_matched_budget"],
                                                  cfg["execution"]["stake_usdt"])
            r = replay_variant(cfg, ctx, its, params(cfg, sc, risk_on, delay))
            m = r["metrics"]
            if lab == "diag_main":
                m["static_cost_sensitivity_net"] = static_costs(r["trades"], cfg)
            vm["scenarios"][lab] = m
            dp = S.daily_pnl(r["equity"], cfg["execution"]["initial_equity"])
            daily[f"{sp['name']}|{lab}"] = dp
            if sp["primary"] and lab in ("diag_main", "constrained_main"):
                hourly[f"{sp['name']}|{lab}"] = r["equity"].resample("1h", label="right", closed="right").last()
            if len(r["trades"]):
                trades_all.append(r["trades"].assign(variant=sp["name"], scenario=lab))
            if len(r["rejections"]):
                rej_all.append(r["rejections"].assign(variant=sp["name"], scenario=lab)[
                    ["T", "symbol", "variant", "scenario", "reason"]])
        metrics["variants"][sp["name"]] = vm
    # ---------------- controls
    ini = cfg["execution"]["initial_equity"]
    third = cfg["controls"]["ew_stake_total"] / 3
    ctrl = {"BH-BTC-50": {"BTCUSDT": cfg["controls"]["bh_btc_stake"]},
            "EW-BTC-ETH-SOL-50": {a: third for a in ctx["traded"]},
            "BH-BTC-allin-100-context": {"BTCUSDT": ini}}
    metrics["controls"]["cash"] = {"net_pnl": 0.0, "note": "100 USDT, no interest"}
    for name, w in ctrl.items():
        for lab, risk_on in (("diag_main", False), ("constrained_main", True)):
            if name.startswith("BH-BTC-allin") and risk_on:
                continue
            r = passive(ctx["px"], w, params(cfg, "main", risk_on), ctx["eval_start"], ctx["end"])
            dp = S.daily_pnl(r["equity"], ini)
            daily[f"{name}|{lab}"] = dp
            dd = r["equity"] - r["equity"].cummax()
            metrics["controls"][f"{name}|{lab}"] = {
                "net_pnl": float(r["net_pnl"]), "max_drawdown_usdt": float(-dd.min()), "exit_reason": r["exit_reason"],
                "exposure_time": r["exposure_time"], "n_positions": len(r["positions"]),
                **S.extra_metrics(r["equity"], ini),
                "note": "no re-entry after a risk exit" if risk_on else "unconstrained diagnostic"}
    # ---------------- random baselines (diag, main costs)
    seeds = range(cfg["controls"]["random_seeds"][0], cfg["controls"]["random_seeds"][1] + 1)
    if n_seeds is not None:
        seeds = range(n_seeds)
    rrows = []
    prim_name = {"G01": f"G01-X-H{cfg['families']['G01']['primary_horizon_min']}-thr0"}
    for fam in ("H01", "H02", "H03"):
        prim_name[fam] = f"{fam}-H{cfg['families'][fam]['horizons_min'][0]}-none"
    for fi, fam in enumerate(("G01", "H01", "H02", "H03")):
        for sd in seeds:
            it = random_intents(fam, cfg, panels, ctx, sd, fi)
            r = replay_variant(cfg, ctx, it, params(cfg, "main"), full=False)
            tr = r["trades"]
            held = ((tr["exit_time"] - tr["entry_time"]).dt.total_seconds().sum() / 60) if len(tr) else 0
            dd = r["equity"] - r["equity"].cummax()
            rrows.append({"family": fam, "seed": sd, "n_intents": len(it), "n_trades": len(tr),
                          "net_pnl": float(tr["net_pnl"].sum()) if len(tr) else 0.0,
                          "gross_pnl": float(tr["gross_pnl"].sum()) if len(tr) else 0.0,
                          "exposure_time": held / len(r["equity"]), "max_drawdown_usdt": float(-dd.min())})
    rnd = pd.DataFrame(rrows)
    for fam, g in rnd.groupby("family"):
        real = metrics["variants"][prim_name[fam]]["scenarios"]["diag_main"]
        q = g["net_pnl"].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).tolist()
        metrics["random"][fam] = {"target_variant": prim_name[fam], "n_seeds": int(len(g)),
                                  "net_pnl_q05_q25_q50_q75_q95": q, "mean_n_trades": float(g["n_trades"].mean()),
                                  "mean_exposure_time": float(g["exposure_time"].mean()),
                                  "strategy_net_pnl": real["net_pnl"], "strategy_n_trades": real["n_trades"],
                                  "strategy_exposure_pct_time": real.get("exposure_pct_time"),
                                  "share_seeds_ge_strategy": float((g["net_pnl"] >= real["net_pnl"]).mean())}
    # ---------------- exposure-matched passive (analytic approximation, disclosed)
    ew = daily.get("EW-BTC-ETH-SOL-50|diag_main")
    for fam, vn in prim_name.items():
        m = metrics["variants"][vn]["scenarios"]["diag_main"]
        e = (m.get("exposure_pct_time") or 0) / 100
        metrics["controls"][f"EW-exposure-matched~{vn}"] = {
            "net_pnl_approx": float(ew.sum() * e), "exposure_fraction": e,
            "note": "EW buy-and-hold daily PnL scaled by the strategy's time exposure; analytic approximation"}
    # ---------------- forecast metrics & event study
    metrics["g01_forecast"] = g01_forecast_metrics(cfg, ctx, panels["G01"]["panel"])
    metrics["event_study"] = event_study(cfg, ctx, panels)
    # ---------------- primary tests (pre-registered) with Holm
    st = cfg["statistics"]["bootstrap"]
    B = st["primary_block_days"]

    def dser(name):
        return daily[name]

    tests = {}
    fa = metrics["g01_forecast"]["aggregate"][str(cfg["families"]["G01"]["primary_horizon_min"])]
    for b in st["blocks_days"]:
        tests.setdefault("G01_forecast_mse_B1_minus_X_H60", {})[f"block_{b}d"] = {
            k: v for k, v in fa[f"block_{b}d"].items() if k != "per_target"}
    ph = cfg["families"]["G01"]["primary_horizon_min"]
    pairs = {"G01_economic_X_minus_B1_thr0": (f"G01-X-H{ph}-thr0|diag_main", f"G01-B1-H{ph}-thr0|diag_main"),
             "G01_H04_X_thrc_minus_thr0": (f"G01-X-H{ph}-thrc|diag_main", f"G01-X-H{ph}-thr0|diag_main")}
    for fam in ("H01", "H02", "H03"):
        H = cfg["families"][fam]["horizons_min"][0]
        pairs[f"{fam}_net_H{H}"] = (f"{fam}-H{H}-none|diag_main", None)
        pairs[f"{fam}_H04_c_minus_common_H{H}"] = (f"{fam}-H{H}-c|diag_main", f"{fam}-H{H}-common|diag_main")
    for tname, (a, bname) in pairs.items():
        x = dser(a) - (dser(bname) if bname else 0)
        tests[tname] = {f"block_{b}d": S.block_bootstrap(x, b, st["n_boot"], st["seed"], st["min_blocks"])
                        for b in st["blocks_days"]}
    pv = {k: (v[f"block_{B}d"].get("p_one_sided_mean_gt_0") if k != "G01_forecast_mse_B1_minus_X_H60"
              else v[f"block_{B}d"].get("p_one_sided_gt_0")) for k, v in tests.items()}
    pv = {k: (v if tests[k][f"block_{B}d"].get("status") == "ok" else None) for k, v in pv.items()}
    metrics["primary_tests"] = {"tests": tests, "holm_primary_block": S.holm(pv, cfg["statistics"]["holm_alpha"]),
                                "primary_block_days": B}
    # ---------------- outputs
    out = _write(cfg, ctx, label, metrics, panels, trades_all, rej_all, daily, hourly, rnd, out_root)
    return out


def event_study(cfg, ctx, panels) -> dict:
    out = {}
    mc = cfg["costs"]["main"]
    fee, slip = mc["fee_bps"] / 1e4, mc["slip_bps"] / 1e4
    for fam in ("H01", "H02", "H03"):
        pan = panels[fam]["panel"]
        gm = cfg["families"][fam]["grid_min"]
        for (a, H), g in pan.groupby(["symbol", "H"]):
            g = g[np.isfinite(g["y"])]
            lags = int(np.ceil(H / gm))
            ys, ya = g.loc[g["signal"], "y"].to_numpy(), g["y"].to_numpy()
            r = {"n_all": int(len(ya)), "n_signal": int(len(ys)),
                 "mean_all": float(ya.mean()) if len(ya) else None,
                 "signal_hac": S.hac_mean(ys, lags),
                 "diff_signal_vs_all_hac": S.hac_ols(g["y"].to_numpy(), g["signal"].astype(float).to_numpy(), lags),
                 "signal_net_expectancy_main": float(net_from_gross(ys, fee, slip).mean()) if len(ys) else None,
                 "signal_gross_delay5": float(g.loc[g["signal"], "y5"].mean()) if len(ys) else None}
            if fam == "H01":
                r["ols_future_on_r1h"] = S.hac_ols(g["y"].to_numpy(), g["r1h"].to_numpy(), lags)
            out[f"{fam}|{a}|H{H}"] = r
        # pooled over targets
        for H, g in pan.groupby("H"):
            g = g[np.isfinite(g["y"])]
            ys = g.loc[g["signal"], "y"].to_numpy()
            out[f"{fam}|ALL|H{H}"] = {"n_all": int(len(g)), "n_signal": int(len(ys)),
                                      "mean_all": float(g["y"].mean()), "mean_signal": float(ys.mean()) if len(ys) else None,
                                      "signal_net_expectancy_main": float(net_from_gross(ys, fee, slip).mean())
                                      if len(ys) else None,
                                      "note": "pooled overlapping observations; not independent"}
    return out


def _write(cfg, ctx, label, metrics, panels, trades_all, rej_all, daily, hourly, rnd, out_root) -> Path:
    chash = code_hash()
    run_id = f"{label}_{chash[:10]}_{cfg['_hash'][:8]}"
    out = (out_root or ROOT / "reports" / "v02" / "runs") / run_id
    out.mkdir(parents=True, exist_ok=True)
    tr = pd.concat(trades_all, ignore_index=True) if trades_all else pd.DataFrame()
    tr.to_parquet(out / "trades_all.parquet", index=False)
    prim = tr[tr["variant"].isin([k for k, v in metrics["variants"].items() if "constrained_main" in v["scenarios"]])
              | (tr["scenario"] == "diag_main")] if len(tr) else tr
    keep = [c for c in ["variant", "scenario", "symbol", "T", "fit_id", "entry_time", "exit_time", "exit_reason",
                        "raw_entry", "fill_entry", "qty", "notional_in", "fee_in", "raw_exit", "fill_exit",
                        "notional_out", "fee_out", "gross_pnl", "slippage_cost", "fees", "net_pnl", "cash_before",
                        "cash_after", "uncertain_gap", "hold_minutes_actual", "score", "pred_B0", "pred_B1", "pred_X",
                        "est", "y", "stake", "sigma1h", "trend_regime", "vol_regime"] if c in prim]
    prim[keep].to_csv(out / "trades.csv", index=False, float_format="%.10g")
    rj = pd.concat(rej_all, ignore_index=True) if rej_all else pd.DataFrame()
    rj.to_parquet(out / "rejections.parquet", index=False)
    if len(rj):
        rj.groupby(["variant", "scenario", "reason"]).size().rename("n").reset_index().to_csv(
            out / "rejections_summary.csv", index=False)
    pd.DataFrame(daily).to_csv(out / "equity_daily_pnl.csv", float_format="%.8f")
    pd.DataFrame(hourly).to_parquet(out / "equity_hourly_primary.parquet")
    pd.DataFrame(hourly).to_csv(out / "equity_hourly_primary.csv", float_format="%.6f")
    rnd.to_csv(out / "random_benchmark.csv", index=False, float_format="%.8g")
    g = panels["G01"]
    g["panel"].to_parquet(out / "g01_predictions.parquet", index=False)
    g["panel"][g["panel"]["H"] == cfg["families"]["G01"]["primary_horizon_min"]].to_csv(
        out / "g01_predictions_H60.csv", index=False, float_format="%.8g")
    g["coefs"].to_csv(out / "g01_coefficients.csv", index=False, float_format="%.8g")
    calibration_table(g["panel"], g["coefs"], ctx["fits"]).to_csv(out / "g01_calibration_oos.csv", index=False,
                                                                   float_format="%.8g")
    for fam in ("H01", "H02", "H03"):
        panels[fam]["panel"].to_parquet(out / f"{fam.lower()}_signals.parquet", index=False)
        panels[fam]["fits"].to_csv(out / f"{fam.lower()}_fits.csv", index=False, float_format="%.8g")
    (out / "metrics.json").write_text(dumps(_clean(metrics)))
    manifest = {"experiment_id": cfg["experiment_id"], "split": ctx["split"], "label": label,
                "eval_window": [str(ctx["eval_start"]), str(ctx["end"])],
                "fits": [str(f) for f in ctx["fits"]], "config_sha256": cfg["_hash"], "code_sha256": chash,
                "git_commit": git_commit(), "data_manifest_sha256": file_sha256(ROOT / cfg["data"]["manifest"]),
                "px_sha256": ctx["data_sha"],
                "outputs_sha256": {p.name: file_sha256(p) for p in sorted(out.iterdir())
                                   if p.suffix == ".csv" or p.name == "metrics.json"}}
    (out / "manifest.json").write_text(dumps(manifest))
    (out / "run_info.json").write_text(dumps({"created_utc": dt.datetime.now(dt.timezone.utc).isoformat()}))
    from src.research.report import write_report
    write_report(cfg, out, metrics, manifest)
    return out


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o
