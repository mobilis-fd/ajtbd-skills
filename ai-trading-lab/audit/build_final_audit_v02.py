"""Build FINAL_AUDIT_V02.md from COMMITTED v0.2 outputs only (no backtest, no refit, no download).

Usage: python -m audit.build_final_audit_v02
Inputs: reports/v02/runs/*_a5bca96b79_cf00d9bc/{metrics.json,manifest.json,trades.csv.gz},
        reports/v02/diagnostics/D1/*_8ea5177c03_cf00d9bc/{d1_results.json,manifest.json},
        reports/v02/qa_addendum/{qa_measurements.json,*_all_decisions.csv.gz,*_all_predictions.csv.gz},
        configs, git metadata.
Audit-derived statistics (clearly labelled) are computed from committed predictions/signals/trades with fixed seeds.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT, file_sha256, load_config
from src.research import stats as S
from src.research.features import net_from_gross

SPLITS = ("development", "validation")
RUN = {s: ROOT / f"reports/v02/runs/{s}_a5bca96b79_cf00d9bc" for s in SPLITS}
D1 = {s: ROOT / f"reports/v02/diagnostics/D1/{s}_8ea5177c03_cf00d9bc" for s in SPLITS}
QA = ROOT / "reports/v02/qa_addendum"
CFG = load_config(ROOT / "configs/multi_horizon_v02.yaml")
BOOT = CFG["statistics"]["bootstrap"]


def J(p):
    return json.loads(Path(p).read_text())


def f(x, nd=2):
    if x is None:
        return "н/д"
    if isinstance(x, (bool, np.bool_)):
        return "да" if x else "нет"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, (float, np.floating)):
        return "н/д" if not np.isfinite(x) else f"{x:.{nd}f}"
    return str(x)


def T(rows, hdr):
    return "\n".join(["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)] +
                     ["| " + " | ".join(c if isinstance(c, str) else f(c) for c in r) + " |" for r in rows]) + "\n"


def ci(c, nd=2, sc=1.0):
    return "н/д" if not c else f"[{f(c[0] * sc, nd)}, {f(c[1] * sc, nd)}]"


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


M = {s: J(RUN[s] / "metrics.json") for s in SPLITS}
MAN = {s: J(RUN[s] / "manifest.json") for s in SPLITS}
DR = {s: J(D1[s] / "d1_results.json") for s in SPLITS}
DMAN = {s: J(D1[s] / "manifest.json") for s in SPLITS}
QM = J(QA / "qa_measurements.json")


def fam_of(v):
    return v.split("-")[0]


# ------------------------------------------------------------------ sections

def sec_versions(L):
    L += ["## 1. Версии, коммиты, хэши, окружение", ""]
    log = git("log", "--format=%h|%cI|%s", "789683e^..HEAD")
    L.append(T([r.split("|", 2) for r in log.splitlines()], ["commit", "date", "message"]))
    L += ["", f"* Ветка исследования: `research/multi-horizon-v02`; замороженная копия: `release/multi-horizon-v0.2`.",
          "* База v0.1: передаточный коммит `789683e` (ветка `ccr-481f4ca9-6sjk8p`; аудит v0.1 `73e6d89`).",
          f"* `configs/multi_horizon_v02.yaml` sha256 `{CFG['_hash']}`.",
          f"* `requirements-v02.lock` sha256 `{file_sha256(ROOT / 'requirements-v02.lock')}`; "
          "Python 3.13.18, pandas 3.1.1, numpy 2.5.5, pyarrow 26.0.1, scikit-learn 1.9.1 (BSD-3), "
          "statsmodels 0.15.0 (BSD-3), scipy 1.18.1, pytest 9.2.0; freqtrade 2026.10/technical (GPLv3) не используются v0.2.",
          f"* Манифест сырых данных: копия `reports/v02/data_manifest_v02.json` (URL, SHA256 Binance, размер, Last-Modified/"
          f"ETag каждого из 477 архивов; сами архивы в пакет не входят).", ""]
    rows = []
    for s in SPLITS:
        m = MAN[s]
        rows.append([s, "v0.2 runs", m["git_commit"][:7], m["code_sha256"][:10], m["config_sha256"][:10],
                     m["eval_window"][0][:10] + " → " + m["eval_window"][1][:10]])
        d = DMAN[s]
        rows.append([s, "D1", d["git_commit"][:7], d["code_sha256"][:10], d["config_sha256"][:10],
                     d["eval_window"][0][:10] + " → " + d["eval_window"][1][:10]])
    L.append(T(rows, ["split", "run", "git", "code sha", "config sha", "OOS window"]))
    L += ["Хэши 1m цен (px_sha256 в manifest.json):", ""]
    L.append(T([[s, a, h[:16]] for s in SPLITS for a, h in MAN[s]["px_sha256"].items()], ["split", "symbol", "sha256[:16]"]))


def sec_data(L):
    q = J(ROOT / "reports/v02/data_qa_validation.json")
    L += ["## 2. Данные и покрытие", "",
          f"Архивы: {q['archives']['ok']}/{q['archives']['total']} с проверкой SHA256 по `.CHECKSUM` Binance; месяцы "
          "2020-08 … 2024-12; данные исторического test (2025-01..2025-11) и периода v0.1 не скачивались.", ""]
    rows = []
    for sym, v in q["symbols"].items():
        c = v["checks"]
        rows.append([sym, v["first_open_time"][:16], c["rows_in_range"], c["missing_minutes"], v["n_gaps"],
                     c["duplicate_open_time"], c["ohlc_invariant_violations"], c["taker_gt_total"],
                     c["taker_quote_gt_quote_volume"], c["bad_close_time"], str(c["ts_units"])])
    L.append(T(rows, ["symbol", "first 1m", "rows", "missing min", "gaps", "dup", "OHLC viol", "taker>vol",
                      "takerQ>quoteVol", "bad close_time (dropped)", "units"]))
    L += ["Пропуски общие для биржи (крупнейшие: 2021-04-25 284 мин, 2021-08-13 270 мин, 2023-03-24 80 мин); не "
          "заполнялись. Первая модельная подгонка 2021-10-01 (покрытие SOL с 2020-08-11 + 365 + 28 дней).", ""]


def variant_table(s, fam):
    rows = []
    for k, v in M[s]["variants"].items():
        if fam_of(k) != fam:
            continue
        d = v["scenarios"]["diag_main"]
        exl = (d["slippage_cost"] or 0)
        rows.append([k, v["n_candidates"], v["n_intents"], d["n_trades"], d["gross_pnl"], d["fees"], exl, d["net_pnl"],
                     d.get("expectancy"), d.get("win_rate"), d["turnover_x_initial"], d.get("exposure_pct_time"),
                     d["max_drawdown_usdt"], d.get("break_even_rt_bps_static")])
    return T(rows, ["variant", "signals (candidates)", "intents", "trades", "gross", "fees", "adverse+rounding", "net",
                    "net/trade", "win", "turnover x", "exposure %", "max DD", "break-even RT bps"])


def sec_results(L):
    L += ["## 3. Полные численные результаты v0.2 (диагностический replay, основной сценарий 25 bps)", "",
          "Источник: `metrics.json` прогонов. Внимание: diag-кошелёк истощается (раздел 7); значения около −90 USDT — "
          "нижняя граница, а не скорость потерь. Неискажённые оценки — D1 (разделы 7–8). Signals = все кандидаты "
          "(сигнал×актив) до выбора; intents = решения после выбора одного актива; trades = исполненные.", ""]
    for fam in ("G01", "H01", "H02", "H03"):
        for s in SPLITS:
            L += [f"### {fam}, {s}", "", variant_table(s, fam)]
    L += ["### Основные варианты: сценарии (net USDT; trades)", ""]
    for s in SPLITS:
        rows = []
        for k, v in M[s]["variants"].items():
            sc = v["scenarios"]
            if "constrained_main" not in sc:
                continue
            st = sc["diag_main"].get("static_cost_sensitivity_net", {})
            rows.append([k, f"{f(sc['diag_main']['net_pnl'])} ({sc['diag_main']['n_trades']})",
                         f"{f(sc['constrained_main']['net_pnl'])} ({sc['constrained_main']['n_trades']})",
                         f"{f(sc['diag_rt0']['net_pnl'])} ({sc['diag_rt0']['n_trades']})",
                         f"{f(sc['diag_rt10']['net_pnl'])} ({sc['diag_rt10']['n_trades']})",
                         f"{f(sc['diag_rt40']['net_pnl'])} ({sc['diag_rt40']['n_trades']})",
                         f"{f(sc['diag_delay5']['net_pnl'])} ({sc['diag_delay5']['n_trades']})",
                         f"{f(sc['diag_risk_matched']['net_pnl'])} ({sc['diag_risk_matched']['n_trades']})",
                         st.get("rt0"), st.get("rt10"), st.get("rt40"),
                         sc["constrained_main"]["max_drawdown_usdt"]])
        L += [f"**{s}**", "", T(rows, ["variant", "diag main", "constrained", "rt0", "rt10", "rt40", "delay 5m",
                                         "risk-matched", "static rt0", "static rt10", "static rt40", "constr. max DD"])]
    L += ["### Event study v0.2 (gross labels, все допустимые OOS наблюдения; HAC lags = ceil(H/grid))", ""]
    for s in SPLITS:
        rows = []
        for k, r in M[s]["event_study"].items():
            if "|ALL|" in k:
                continue
            sh, d = r["signal_hac"], r["diff_signal_vs_all_hac"]
            rows.append([k, r["n_all"], r["n_signal"], 1e4 * (r["mean_all"] or 0), 1e4 * sh.get("mean", np.nan),
                         sh.get("t_hac"), d.get("t_beta_hac"), 1e4 * (r["signal_net_expectancy_main"] or np.nan),
                         1e4 * (r["signal_gross_delay5"] or np.nan),
                         r.get("ols_future_on_r1h", {}).get("t_beta_hac")])
        L += [f"**{s}**", "", T(rows, ["family|asset|hold", "n all", "n signal", "mean all bps", "mean signal bps",
                                         "t HAC", "t HAC (signal−all)", "net bps main", "gross bps delay5",
                                         "H01 OLS β t"])]


def sec_g01(L):
    L += ["## 4. G01: ошибки прогноза B0 / B1 / X", "",
          "MSE/MAE в единицах (доходность)²; R² относительно B0; IC = Spearman. Значимость B1−X: day-block bootstrap "
          "из прогона (`metrics.json`, общий для активов ось UTC-дней, 2000 повторов, seed 42). B0−B1 и B0−X: "
          "**производный расчёт аудита** по закоммиченным прогнозам `qa_addendum/*_g01_all_predictions.csv.gz` "
          "тем же методом (без переобучения).", ""]
    for s in SPLITS:
        rows = []
        for H, per in M[s]["g01_forecast"]["per_target"].items():
            agg = M[s]["g01_forecast"]["aggregate"][H]["block_14d"]
            for a, r in per.items():
                pt = agg["per_target"][a]
                rows.append([H, a, r["n"], 1e6 * r["B0"]["mse"], 1e6 * r["B1"]["mse"], 1e6 * r["X"]["mse"],
                             1e6 * r["mse_B1_minus_X"], ci(pt.get("ci95"), 3, 1e6), pt.get("p_one_sided_gt_0"),
                             r["B1"]["r2_vs_B0"], r["X"]["r2_vs_B0"], 1e6 * r["B1"]["mae"], 1e6 * r["X"]["mae"],
                             r["B1"]["rank_ic"], r["X"]["rank_ic"]])
            rows.append([H, "AGG (equal weight)", "", "", "", "", 1e6 * agg["observed"], ci(agg.get("ci95"), 3, 1e6),
                         agg.get("p_one_sided_gt_0"), "", "", "", "", "", ""])
        L += [f"**{s}** (MSE ×1e-6)", "", T(rows, ["H", "target", "n", "MSE B0", "MSE B1", "MSE X", "B1−X",
                                                   "95% CI B1−X", "p (X лучше)", "R² B1", "R² X", "MAE B1 e-6",
                                                   "MAE X e-6", "IC B1", "IC X"])]
    # audit-derived B0 comparisons
    L += ["**Производный расчёт аудита: MSE(B0) − MSE(model), equal-weight по активам, блоки 14 дней** "
          "(положительно = модель лучше константы)", ""]
    rows = []
    for s in SPLITS:
        g = pd.read_csv(QA / f"{s}_g01_all_predictions.csv.gz", parse_dates=["T"])
        g = g[np.isfinite(g["y"]) & g[["pred_B0", "pred_B1", "pred_X"]].notna().all(axis=1)]
        g["day"] = g["T"].dt.floor("D")
        days = pd.date_range(g["day"].min(), g["day"].max(), freq="D")
        for H, gh in g.groupby("H"):
            for m in ("B1", "X"):
                d = gh.assign(d=(gh["y"] - gh["pred_B0"]) ** 2 - (gh["y"] - gh[f"pred_{m}"]) ** 2, one=1.0)
                num = d.pivot_table(index="day", columns="symbol", values="d", aggfunc="sum").reindex(days).fillna(0)
                den = d.pivot_table(index="day", columns="symbol", values="one", aggfunc="sum").reindex(days).fillna(0)
                b = S.ratio_bootstrap(num.to_numpy(), den.to_numpy(), 14, BOOT["n_boot"], BOOT["seed"], BOOT["min_blocks"])
                rows.append([s, H, f"B0−{m}", 1e6 * b["observed"], ci(b.get("ci95"), 3, 1e6), b.get("p_one_sided_gt_0")])
    L.append(T(rows, ["split", "H", "comparison", "observed ×1e-6", "95% CI ×1e-6", "p (модель лучше B0)"]))
    L += ["Коэффициенты, окна обучения и исключённые колонки — `g01_coefficients.csv`; калибровка по train-децилям — "
          "`g01_calibration_oos.csv`; по годам и режимам — `metrics.json → g01_forecast.per_target.*.by_*`.", ""]


def sec_h03(L):
    L += ["## 5. H03 против Buy & Hold и случайных входов (с учётом экспозиции и удержания)", "",
          "Нормировка на экспозицию — **производный расчёт аудита** из закоммиченных сделок (`trades.csv.gz`): "
          "USDT·дни = Σ notional × длительность удержания. B&H: 50 USDT × дни окна. Random: ≈ net / (exposure_time × "
          "дни × 50) (ноционал случайных кошельков не сохранён — приближение).", ""]
    rows = []
    for s in SPLITS:
        tr = pd.read_csv(RUN[s] / "trades.csv.gz", parse_dates=["entry_time", "exit_time"])
        days = (pd.Timestamp(MAN[s]["eval_window"][1]) - pd.Timestamp(MAN[s]["eval_window"][0])).days
        for v in ("H03-H4320-none", "H03-H1440-none", "H03-H10080-none"):
            t = tr[(tr["variant"] == v) & (tr["scenario"] == "diag_main")]
            ud = (t["notional_in"] * (t["exit_time"] - t["entry_time"]).dt.total_seconds() / 86400).sum()
            sc = M[s]["variants"][v]["scenarios"]["diag_main"]
            rows.append([s, v, len(t), sc["gross_pnl"], sc["net_pnl"], sc.get("exposure_pct_time"), ud,
                         1000 * sc["net_pnl"] / ud if ud else None, sc["max_drawdown_usdt"]])
        for k in ("BH-BTC-50|diag_main", "EW-BTC-ETH-SOL-50|diag_main"):
            c = M[s]["controls"][k]
            rows.append([s, k, c["n_positions"], "", c["net_pnl"], 100.0, 50 * days, 1000 * c["net_pnl"] / (50 * days),
                         c["max_drawdown_usdt"]])
        r = M[s]["random"]["H03"]
        ud = r["mean_exposure_time"] * days * 50
        rows.append([s, "random (median, seeds 0–99)", f(r["mean_n_trades"], 1), "", r["net_pnl_q05_q25_q50_q75_q95"][2],
                     100 * r["mean_exposure_time"], ud, 1000 * r["net_pnl_q05_q25_q50_q75_q95"][2] / ud, ""])
        ex = M[s]["controls"]["EW-exposure-matched~H03-H4320-none"]
        rows.append([s, "EW exposure-matched (analytic)", "", "", ex["net_pnl_approx"], 100 * ex["exposure_fraction"],
                     "", "", ""])
    L.append(T(rows, ["split", "variant/control", "trades", "gross", "net", "exposure % time", "USDT·days",
                      "net per 1000 USDT·days", "max DD"]))
    for s in SPLITS:
        r = M[s]["random"]["H03"]
        d1 = DR[s]["L3_random"]["H03"]
        L.append(f"* {s}: random (diag) q05/q50/q95 = {', '.join(f(x) for x in r['net_pnl_q05_q25_q50_q75_q95'][::2])}; "
                 f"доля сидов ≥ стратегии {f(r['share_seeds_ge_strategy'])}. D1 (фикс. 50): "
                 f"{', '.join(f(x) for x in d1['q05_q50_q95'])}; доля {f(d1['share_seeds_ge_strategy'])}.")
    L += ["", "Вывод: на validation H03 положителен, но на единицу экспозиции не лучше пассивного удержания и ниже медианы "
          "случайных входов с той же частотой и удержанием; на development отрицателен. Превышение доходности сигнала над "
          "безусловной (D1 L1) незначимо в обоих периодах. Эффект объясняется рыночной бетой.", ""]


def sec_h04(L):
    L += ["## 6. H04: пропущенные сделки, качество оставшихся сигналов, сравнение с cash", "",
          "Пропуски: разница сигналов/сделок между `common` (база на общей выборке доступных оценок) и фильтрами. "
          "Качество оставшихся сигналов H01–H03 — **производный расчёт аудита** по закоммиченным таблицам "
          "`*_all_decisions.csv.gz` (gross и net при 25 bps, без округления), G01 — D1 L1/L2. Cash = 0.", ""]
    c = CFG["costs"]["hurdle_c"]
    mc = CFG["costs"]["main"]
    rows = []
    for s in SPLITS:
        for fam, H in (("H01", 120), ("H02", 720), ("H03", 4320), ("H01", 60), ("H01", 240), ("H02", 240),
                       ("H02", 1440), ("H03", 1440), ("H03", 10080)):
            dec = pd.read_csv(QA / f"{s}_{fam.lower()}_all_decisions.csv.gz")
            dec = dec[(dec["H"] == H) & dec["signal"]]
            base = M[s]["variants"][f"{fam}-H{H}-common"]["scenarios"]["diag_main"]
            for k, thr in (("common", None), ("c", c), ("2c", 2 * c)):
                sel = dec[np.isfinite(dec["est"])] if thr is None else dec[np.isfinite(dec["est"]) & (dec["est"] > thr)]
                y = sel["y"].dropna().to_numpy()
                v = M[s]["variants"][f"{fam}-H{H}-{k}"]
                sc = v["scenarios"]["diag_main"]
                rows.append([s, f"{fam}-H{H}-{k}", len(sel), len(dec) - len(sel), sc["n_trades"],
                             base["n_trades"] - sc["n_trades"], 1e4 * y.mean() if len(y) else None,
                             1e4 * net_from_gross(y, mc["fee_bps"] / 1e4, mc["slip_bps"] / 1e4).mean() if len(y) else None,
                             sc["net_pnl"], sc["net_pnl"] - 0.0])
    L.append(T(rows, ["split", "variant", "signals kept", "signals skipped vs all signals", "trades",
                      "trades skipped vs common", "kept gross bps/signal", "kept net bps/signal", "net USDT (diag)",
                      "vs cash"]))
    rows = []
    for s in SPLITS:
        for th in ("0", "c", "2c"):
            for m in ("B1", "X"):
                l1 = DR[s]["L1"][f"G01-{m}-H60-thr{th}"]
                l2 = DR[s]["L2"][f"G01-{m}-H60-thr{th}"]["main"]
                l3 = DR[s]["L3"].get(f"G01-{m}-H60-thr{th}", {}).get("main", {})
                rows.append([s, f"G01-{m}-H60-θ{th}", l1["n_signals"], l1["block_14d"].get("mean"),
                             ci(l1["block_14d"].get("ci95_diff")), l2.get("mean_net_bps"),
                             M[s]["variants"][f"G01-{m}-H60-thr{th}"]["scenarios"]["diag_main"]["n_trades"],
                             M[s]["variants"][f"G01-{m}-H60-thr{th}"]["scenarios"]["diag_main"]["net_pnl"],
                             l3.get("net")])
    L.append(T(rows, ["split", "G01 population", "signals (all targets)", "gross bps", "gross−baseline 95% CI",
                      "net bps/signal", "v0.2 diag trades", "v0.2 diag net", "D1 L3 net (fixed 50)"]))
    L += ["Вывод по H04 (первичные холды): H01-c — оставшиеся сигналы отрицательны после издержек (dev −30 bps) или "
          "отсутствуют (val: 0 сделок); улучшение к базе — отказ от торговли (V24). H02-c: dev −47.9 USDT (net −52 bps/"
          "сигнал), val +12.5 USDT (+7 bps) — знак меняется между периодами. H03-c положителен относительно cash в обоих "
          "периодах (+10.2 / +1.7 USDT), но не лучше H03-common (+10.5 / +10.9), т.е. фильтр сам не улучшает результат "
          "(первичный тест H04 для H03: −0.001 / −0.013 USDT/день, незначимо), а положительность H03 объясняется рыночной "
          "бетой (раздел 5). G01-X θ=c уменьшает потери, но остаётся убыточным в обоих периодах (−40.1 / −7.2); G01-B1 θ=c "
          "меняет знак (−48.6 / +23.7); θ=2c — 12–78 сигналов, "
          "интервалы широкие. Подтверждающего эффекта H04 нет.", ""]


def sec_d1_compare(L):
    L += ["## 7. Исходные результаты против D1: что исказило истощение кошелька", "",
          "Diag-кошелёк v0.2 торгует min(50, cash) при 100 USDT; ниже minNotional (10) сделки невозможны → скрытая "
          "необратимая остановка. D1 L3 — та же логика с постоянным ноционалом 50 и виртуальной наличностью.", ""]
    rows = []
    for s in SPLITS:
        dep = QM[s]["depletion"]
        for v in ("G01-X-H60-thr0", "G01-B1-H60-thr0", "H01-H120-none", "H02-H720-none", "H03-H4320-none"):
            o = M[s]["variants"][v]["scenarios"]["diag_main"]
            d = DR[s]["L3"][v]["main"]
            dp = dep[f"{v}|diag_main"]
            rows.append([s, v, o["n_trades"], d["n_trades"], f(dp["share_of_oos_period_before_block"]),
                         o["net_pnl"], d["net"], o.get("expectancy"), d["net_per_trade"], o["gross_pnl"], d["gross"],
                         o["max_drawdown_usdt"], d["max_drawdown_usdt"]])
    L.append(T(rows, ["split", "variant", "v0.2 trades", "D1 trades", "share of window traded (v0.2)", "v0.2 net",
                      "D1 net", "v0.2 net/trade", "D1 net/trade", "v0.2 gross", "D1 gross", "v0.2 max DD", "D1 max DD"]))
    rows = []
    for s in SPLITS:
        t0 = M[s]["primary_tests"]["tests"]
        t1 = DR[s]["L3_tests_diagnostic"]["tests"]
        for k in t1:
            a, b = t0[k]["block_14d"], t1[k]["block_14d"]
            rows.append([s, k, a.get("mean_daily_pnl"), ci(a.get("ci95_mean_daily"), 3), a.get("p_one_sided_mean_gt_0"),
                         b.get("mean_daily_pnl"), ci(b.get("ci95_mean_daily"), 3), b.get("p_one_sided_mean_gt_0")])
    L += ["Первичные сравнения: v0.2 (истощающийся diag) против D1 (фикс. 50), mean daily PnL USDT, блоки 14 дней", "",
          T(rows, ["split", "comparison", "v0.2 mean", "v0.2 CI", "v0.2 p", "D1 mean", "D1 CI", "D1 p"])]
    L += ["**Искажены истощением:** (1) net PnL, net/trade, max DD, экспозиция и оборот diag-вариантов G01 и H01 "
          "(торговали 12–19 % и 36–56 % окна); (2) первичные тесты G01 economic, G01 H04, H01 net, H01 H04 — средние "
          "дневные PnL разбавлены нулевыми днями после остановки (на D1 величины в 2–15 раз больше, направление то же); "
          "(3) сравнения со случайными входами G01/H01 (все сиды ≈ −90 → неинформативны); (4) полные cost-сценарии "
          "(разные множества сделок, т.к. дешёвые сценарии истощаются позже). **Не искажены:** прогнозные метрики G01 "
          "(MSE, IC, R²), event study, H03 (оба периода) и H02 validation (результаты совпадают с D1 до цента), "
          "constrained-прогоны (там остановку задаёт общий стоп по ТЗ). **Искажён мягче:** H02 development — те же 456 "
          "сделок, но кэш падал до ~21 USDT и ноционал min(50, cash) сжимался: net −79.0 (v0.2) против −89.4 (D1). "
          "Static cost sensitivity использует фактические (сжатые) количества — для G01/H01/H02-dev она тоже "
          "занижает масштаб. Знак всех выводов не меняется; величины G01 economic на validation: v0.2 0.00 → D1 +0.22 "
          "USDT/день (оба кошелька глубоко убыточны: −1166 против −1328).", ""]


def sec_d1_evidence(L):
    L += ["## 8. Доказательства независимости D1 от состояния капитала", ""]
    rows = []
    for s in SPLITS:
        for v, x in DR[s]["L3"].items():
            m = x["main"]
            rows.append([s, v, m["n_intents"], m["n_trades"], str(m["rejections"]), m["min_equity_vs_start"]])
    L += ["1. **L1/L2 не используют кошелёк вовсе**: каждая строка — отдельный сигнал с собственной меткой "
          "(entry T+1 мин, exit +H) и ноционалом 50; позиции могут перекрываться (`execute_signals`, "
          "`src/research/diag_d1.py`). Популяции L1 содержат ВСЕ допустимые сигналы (для G01 — все активы с pred>θ, "
          "а не только выбранный), их число совпадает с числом сигналов в панелях v0.2.",
          "2. **L3**: виртуальная наличность 1 000 000 USDT, notional = min(50, cash/(1+fee)) = 50 всегда; отказов "
          "`min_notional_or_cash` нет — все отклонения только `position_open` (логика одной позиции):", "",
          T(rows, ["split", "variant", "intents", "trades", "rejections", "min equity vs start (USDT)"]),
          "3. Сигналы, выборы актива, удержания, издержки, фильтры и сплиты взяты из неизменённого кода v0.2 "
          "(`g01_panel`, `h_panel`, `intents_for`); единичная проверка назначения моделей: " +
          ", ".join(f"{s}: {DR[s]['unit_safe_fit_index_matches_v02']}" for s in SPLITS) + ".",
          "4. Тождество gross − fees − adverse − rounding = net проверяется assert-ом для каждого сигнала L2; при 0 bps "
          "остаток 0 (тест `test_execute_signals_decomposition_and_zero_cost_residual`).",
          "5. Где капитал v0.2 не ограничивал торговлю, результаты совпадают: H03 (оба периода) и H02 validation — "
          "те же сделки и net до цента; v0.2 diag_rt0 (дешёвый сценарий без истощения) имеет столько же сделок, "
          "сколько D1 L3 (напр. G01-X dev 5686 = 5686). Это подтверждает идентичность логики при снятом ограничении.", ""]
    L += ["### L1/L2 D1: все популяции (gross до исполнения; net при фиксированных 50 USDT на сигнал)", ""]
    for s in SPLITS:
        rows = []
        for k, v in DR[s]["L1"].items():
            b = v["block_14d"]
            l2 = DR[s]["L2"][k]
            m = l2.get("main", {})
            rows.append([k, v["n_signals"], f(v["signals_per_signal_day"], 1), b.get("mean"), b.get("diff"),
                         ci(b.get("ci95_diff")), m.get("gross"), m.get("fees"), m.get("adverse"), m.get("rounding"),
                         m.get("net"), m.get("mean_net_bps"), ci(m.get("block_14d", {}).get("ci95_mean")),
                         m.get("break_even_rt_bps"), l2.get("rt0", {}).get("mean_net_bps"),
                         l2.get("rt10", {}).get("mean_net_bps"), l2.get("rt40", {}).get("mean_net_bps"),
                         l2.get("delay5", {}).get("mean_net_bps")])
        L += [f"**{s}**", "", T(rows, ["population", "signals", "sig/day", "gross bps", "−baseline bps", "95% CI",
                                         "gross USDT", "fees", "adverse", "rounding", "net USDT", "net bps", "net CI",
                                         "break-even bps", "rt0 bps", "rt10 bps", "rt40 bps", "delay5 bps"])]
    for s in SPLITS:
        rows = []
        for v, x in DR[s]["L3"].items():
            m = x["main"]
            rows.append([v, m["n_trades"], m["gross"], m["fees"], m["exec_loss_adverse_plus_rounding"], m["net"],
                         m["net_per_trade"], 100 * m["exposure_time"], 2 * 50 * m["n_trades"] / 100, m["max_drawdown_usdt"],
                         x["rt0"]["net"], x["rt10"]["net"], x["rt40"]["net"], x["delay5"]["net"]])
        L += [f"**D1 L3, {s}** (turnover ≈ 2·50·trades/100, верхняя оценка)", "",
              T(rows, ["variant", "trades", "gross", "fees", "adverse+rounding", "net", "net/trade", "exposure %",
                       "turnover x", "max DD", "rt0", "rt10", "rt40", "delay5"])]


def sec_stats(L):
    L += ["## 9. Статистика, кластеризация, перекрытие горизонтов, множественные сравнения", "",
          "* Первичные тесты (9, заранее заданы в `SPEC_MULTI_HORIZON_V02.md`): moving-block bootstrap дневных рядов на "
          "общей оси UTC-дней (одни и те же дни для всех активов → сохраняется межактивная корреляция и внутридневная "
          "кластеризация); блок 14 дней (≥ 4.7× самого длинного первичного удержания 3 дня), чувствительность 7/28; "
          "2000 повторов, seed 42; односторонняя H0 «≤ 0» по центрированному распределению; Holm α=0.05 по 9 тестам.",
          "* G01 forecast: ratio-статистика Σ(дневные суммы разностей квадратов ошибок)/Σ(число) по ресэмплированным дням.",
          "* Event study: HAC (Newey–West) с lags = ceil(H/grid) по строкам сигналов; пулированные «ALL» строки "
          "без вывода (наблюдения зависимы). D1 L1/L2: тот же day-block ratio bootstrap для пулированных сигналов.",
          "* Случайные базы: 100 сидов 0–99, распределения без выбора лучшего сида.", ""]
    rows = []
    for s in SPLITS:
        for fam, c in QM[s]["clustering"].items():
            if fam == "G01":
                rows.append([s, fam, c["rows_pred_X_gt0"], "", "", f(c["share_decisions_all_3_targets_gt0"]), "", "",
                             f(c["corr_of_labels_across_targets_same_T"])])
            else:
                rows.append([s, fam, c["n_signals"], c["days_with_signal"], f(c["naive_n_over_unique_days"]),
                             f(c["share_decisions_with_>=2_assets"]), f(c["mean_later_same_asset_signals_inside_hold"]),
                             f(c["lag1_autocorr_daily_mean_label"]), ""])
    L.append(T(rows, ["split", "family", "signals", "days", "signals/day", "share T with ≥2 assets (G01: all 3 > 0)",
                      "later same-asset signals inside hold", "lag-1 autocorr daily label", "label corr across targets"]))
    for s in SPLITS:
        pt = M[s]["primary_tests"]
        rows = []
        for k, v in pt["tests"].items():
            row = [k]
            for b in ("7", "14", "28"):
                x = v[f"block_{b}d"]
                row.append(x.get("p_one_sided_gt_0", x.get("p_one_sided_mean_gt_0")) if x.get("status") == "ok"
                           else x.get("status"))
            h = pt["holm_primary_block"][k]
            row += [h.get("p_holm"), h.get("reject_h0")]
            rows.append(row)
        L += [f"**Первичные тесты v0.2, {s}** (p односторонние)", "",
              T(rows, ["test", "p 7d", "p 14d", "p 28d", "p Holm (14d)", "reject H0"])]
    L += ["Единственное отклонение H0 (validation, H01 H04) — артефакт отказа от торговли (0 сделок у фильтра). "
          "D1-тесты — справочно, не подтверждающие.", ""]


def sec_leak(L):
    L += ["## 10. Отсутствие утечки будущих данных", "",
          "| проверка | механизм в коде | автотест / доказательство |", "|---|---|---|",
          "| Признаки только из закрытых баров | бары строятся из полных 1m корзин; T = конец бара; сдвиги на регулярной "
          "сетке без пропуска гэпов (`features.py`, `data.aggregate_bars`) | `test_bar_alignment_across_utc_and_unit_boundary`, "
          "`test_incomplete_bar_dropped_and_missing_row_propagates` |",
          "| Исполнение не по цене закрытия сигнального бара | вход open минуты T+1 (стресс T+5), выход open entry+H | "
          "`test_label_uses_open_after_delay_not_close`; ручные проверки в `qa_report.md` печатают close бара (не используется) |",
          "| Зрелые метки в обучении | `train_mask`: T∈[F−365d,F) и T+1+H ≤ F; исключены метки, пересекающие границы сплитов | "
          "`test_split_purge_and_label_maturity` |",
          "| Стандартизация только на train | `RidgeFit.fit` считает μ/σ по train; колонки с нулевой дисперсией исключаются "
          "одинаково | `test_train_only_scaling` |",
          "| Условные оценки H01–H04 только из train | события в окне F, зрелые; порог q20 H01 фиксируется на fit | "
          "код `h_panel`; совпадение по префиксу (ниже) |",
          "| Модель на момент T — последняя подгонка ≤ T | `model_id_for`; D1 unit-safe проверка совпала | "
          "`test_monthly_fit_schedule_and_model_assignment`, D1 manifest |",
          "| Инвариантность к будущему (сквозная) | — | `test_end_to_end_prefix_invariance_of_predictions_and_signals` "
          "(реальные данные, все 4 семейства: усечение 2022-01-15 vs 2022-03-01 — прогнозы, сигналы, оценки, метки "
          "идентичны); синтетика `test_features_prefix_invariant_and_future_mutation` |",
          "| Purge у границ | T ≤ end − 5 мин − H_max(семейство) | `test_split_purge_and_label_maturity` |",
          "| Невидимость будущих сплитов | `load_ctx` читает только до конца сплита; test заблокирован | "
          "`test_dev_context_never_loads_beyond_split_end`, `test_locked_split_refused` |", "",
          "Ограничение: сквозной тест префиксов не ловит нарушение зрелости внутри первых 4 ч после F (оба усечения "
          "содержат эти минуты); это покрыто отдельным юнит-тестом зрелости. Окна обучения в `g01_coefficients.csv` "
          "имеют вид `F[F−365d, F)`.", ""]
    co = pd.read_csv(RUN["validation"] / "g01_coefficients.csv")
    w = co["window"].dropna().str.extract(r"(\d{4}-\d\d-\d\d)\[(\d{4}-\d\d-\d\d),(\d{4}-\d\d-\d\d)\)")
    ok = (w[0] == w[2]).all()
    L += [f"Проверка аудита по `g01_coefficients.csv` (validation): правая граница окна = дата подгонки для всех "
          f"{len(w)} записей: {'да' if ok else 'НЕТ'}; исключённые нулевой дисперсии колонки: "
          f"{sorted(set(sum([eval(x) for x in co['dropped_zero_var'].dropna()], [])))}.", ""]


def sec_reuse(L):
    L += ["## 11. Повторное использование инфраструктуры v0.1", "",
          T([["src.data.parse.parse_kline_csv", "ms/µs по значению, UTC", "тесты v0.1 + `test_bar_alignment_across_utc_and_unit_boundary`; все 477 файлов ms"],
             ["src.data.validate.check_1m / clean_1m", "целостность, удаление дублей и невалидных строк",
              "тесты v0.1; добавлена отсутствовавшая проверка taker_buy_quote ≤ quote_volume (V03)"],
             ["src.evaluation.engine.round_up/round_down, Filters", "округление к тику/шагу",
              "обёрнуты снаппингом до 1e-10 (V22) после ложного срабатывания сверки на 50220.950000000004"],
             ["src.evaluation.ledger.reconcile", "независимый пересчёт PnL и цепочки кэша",
              "0 расхождений во всех сценариях v0.2"],
             ["src.evaluation.bootstrap.block_bootstrap / holm", "блочный bootstrap, Holm", "тесты v0.1"],
             ["src.evaluation.metrics.compute_metrics / daily_pnl / trade_stats", "метрики", "тесты v0.1"],
             ["src.config (load_config, code_hash, git_commit)", "хэши, запрет live", "тесты v0.1"]],
            ["компонент v0.1", "назначение", "проверка"]),
          "Не переиспользован исполнительный движок v0.1 (стоп/цель, вход по close-времени сигнала, 5m сетка) — "
          "семантика v0.2 иная; написан `src/research/replay.py`. Перед использованием: 42/42 тестов v0.1 на ветке; "
          "прочитан восстановленный `src/data` (передаточный коммит `789683e`). Файлы v0.1 не изменены "
          "(`git diff 789683e HEAD` по путям v0.1 пуст, кроме добавления строк в `.gitignore`).", ""]


def sec_issues(L):
    L += ["## 12. Известные ошибки, ограничения, отсутствующие метрики, отклонения от ТЗ", "", "### 12.1 Ошибки и инциденты", "",
          "1. **Истощение diag-кошелька** (существенно): см. раздел 7; исправлено только диагностикой D1, первичные "
          "результаты v0.2 не переписывались.",
          "2. Smoke: падение `asof` на дублирующихся T → переписан через searchsorted (поведение строже: без ffill "
          "устаревших значений); исправлено до полных прогонов.",
          "3. Плавающая погрешность округления (1e-12) давала ложные срабатывания сверки при 0 bps → снаппинг (V22).",
          "4. Сообщение коммита `0ad6beb` упоминает «report formatting», которое не было применено (команда "
          "заблокирована); применено позже, отчёты перерендерены из неизменённых metrics.json.",
          "5. Удаление старых прогонов заблокировано проверкой безопасности → `reports/v02/runs_superseded/` "
          "(идентичные выходы, 12/12 файлов). Parquet-файлы этой папки попали в историю коммита `0ad6beb` (11 МБ) и "
          "затем были исключены из индекса.",
          "6. QA-скрипт: ошибка единиц времени (ns vs µs) найдена и исправлена до использования; основной код проверен.",
          "7. Латентный риск: `model_id_for`/`asof` сравнивают `asi8` и сломались бы молча при смешанных единицах; в "
          "прогонах единицы согласованы (проверено), в D1 используется устойчивая версия.",
          "8. `slippage_cost` смешивает adverse execution и округление (v0.1 и v0.2) — разложено в QA-дополнении и D1.",
          "9. Порядок pre-registration по git не доказуем сам по себе (опирается на журнал), как и в v0.1.", "",
          "### 12.2 Ограничения", "",
          "Допущенные фильтры биржи (tick 0.01, шаги 1e-5/1e-4/1e-3, minNotional 10); издержки — рабочее допущение, "
          "реальный спред неизвестен; комиссия в quote; округление SOL ≈ 3.4 bps/сделка при цене ~$20; фиксированный "
          "ретроспективный набор 9 активов; validation — бычий рынок 2023–24, development — медвежий 2022; общая "
          "история с 2021-10-01 (dev OOS 15 мес.); перекрывающиеся метки и кластеризация сигналов (эффективный n ≈ "
          "число дней); risk-matched sizing для H03 часто < minNotional; σ невалидна 30 дней после часового пропуска; "
          "знание модели об истории рынка 2021–2025 (ни один период не «неизвестен»).", "",
          "### 12.3 Отсутствующие метрики", "",
          "* Доверительные интервалы для Sharpe/Sortino/PF/win rate не считались.",
          "* Benchmark-relative paired returns (стратегия − B&H по дням) с CI не считались (есть exposure-matched "
          "аналитическая оценка).",
          "* Random-кошельки: ноционал, оборот, разбивка по активам не сохранены (только сводка по сидам).",
          "* D1 L3: оборот и экспозиция по активам не сохранены (оборот приближён), by-year/regime не считались.",
          "* Power analysis не выполнялся (не задан экономически значимый эффект).",
          "* B&H: gross/slippage раздельно не сохранены.", "",
          "### 12.4 Отклонения от ТЗ", "",
          T([["§6 diag fixed-size", "фактически notional=min(50,cash) с истощением", "D1 L3"],
             ["§2 common start", "OOS dev с 2021-10-01 вместо 2021-01-01 (покрытие SOL)", "заранее зафиксировано (V08)"],
             ["§9 Freqtrade/сравнение с движком v0.1", "не выполнено", "—"],
             ["§7 power analysis", "не выполнено", "—"],
             ["§6 benchmark-relative paired returns", "только аналитическое exposure-matched", "—"],
             ["§8 Track C", "код и синтетика; smoke/24ч/Tardis/L2/liquidations не выполнены", "требует согласования"],
             ["§8 futures inventory", "только схема (funding, metrics, mark/premium), без интеграции", "—"],
             ["§2 historical test", "не скачан и не запущен", "по ТЗ"]],
            ["пункт ТЗ", "отклонение", "компенсация"])]


def sec_recorder(L):
    L += ["## 13. Market Data Recorder v0.1: состояние и безопасный локальный smoke", "",
          "Состояние: реализованы `src/collector/core.py` (схема записи с event/receive/available/sample time, парсеры "
          "closed kline / bookTicker без event time → null / markPrice / OI в единицах и USD отдельно / funding с "
          "консервативной задержкой публикации 5 мин (чувствительность 15), выборка bookTicker 1 с с порогом "
          "устаревания 5 с без ffill, дедупликация, детектор пропусков kline, backoff, оценка смещения часов, "
          "атомарная запись Parquet/ZSTD по партициям venue/market/type/date/symbol с SHA256-индексом и квотой диска, "
          "funding as-of join), `service.py` (asyncio, только публичные URL, assert запрета order/account), `cli.py`. "
          "9 синтетических тестов. **Ни одного сетевого подключения не выполнялось**; доступность источников, rows/s, "
          "байты/сутки, CPU/RAM, сеть — не измерены. `api.binance.com` из облачного хоста отвечал «restricted location».", "",
          "Инструкция smoke (только на машине владельца, после согласования; 15 минут; без ключей):", "",
          "```bash", "git clone -b release/multi-horizon-v0.2 <repo> && cd <repo>/ai-trading-lab",
          "python3.13 -m venv .venv && . .venv/bin/activate && pip install -r requirements-v02.lock",
          "pytest -q tests/collector                      # 9 passed",
          "df -h . ; free -m                               # квота по умолчанию 2 GB (configs/collector_v01.yaml)",
          "python -m src.collector.cli smoke --duration 900 --out ./data/recorder --i-am-authorized",
          "cat ./data/recorder/smoke_report.json           # rows/s, bytes_on_disk, cpu_s, max_rss_mb, clock offsets, errors",
          "```", "",
          "Правила: только публичные эндпоинты (stream.binance.com, fstream.binance.com, api/fapi.binance.com для "
          "времени, OI, funding); при HTTP 403/451 или «restricted location» сервис останавливается и пишет ошибку — "
          "не обходить через VPN/прокси; не запускать дольше 900 с до разбора отчёта; 24 ч пилот — отдельное "
          "согласование; данные хранить отдельно от исследовательской истории. Ордеров и ключей в коде нет.", ""]


def sec_needs_runs(L):
    L += ["## 14. Проверки, требующие новых прогонов (НЕ выполнялись)", "",
          "1. Benchmark-relative paired bootstrap (стратегия − EW B&H и − exposure-matched random по дням) для H03 и "
          "остальных основных вариантов.",
          "2. CI для Sharpe/Sortino/PF/win rate (блочный bootstrap).",
          "3. Random-базы с сохранением ноционала/оборота/экспозиции по активам и фиксированным ноционалом 50 по всем "
          "семействам с разбивкой по годам и режимам.",
          "4. Power analysis при заранее заданном экономически значимом эффекте (например, 25 bps на сделку).",
          "5. Чувствительность к допущенным фильтрам (tick/step/minNotional для SOL 2023) и комиссии в базовом активе.",
          "6. Независимая сверка исполнения на Freqtrade или движке v0.1 с семантикой time-exit.",
          "7. Повтор всех прогонов на чистом клоне релизной ветки на машине рецензента (ожидается побайтное совпадение "
          "`outputs_sha256`).",
          "8. Внутрибаровая проверка лимитов по минимумам (сейчас по close 1m).",
          "9. Измерение реальных спредов/проскальзывания (Track C smoke → 24 ч) и пересчёт break-even.",
          "10. Исторический test 2025-01..2025-11 — только после аудита и отдельного разрешения (Gate 4); сейчас "
          "не рекомендуется (ни один вариант не прошёл Gate 3).", ""]


def main():
    L = ["# AI Trading Lab — Multi-Horizon Research v0.2: финальный аудиторский пакет", "",
         "Документ для независимого рецензента. Сгенерирован `audit/build_final_audit_v02.py` только из закоммиченных "
         "результатов (`reports/v02/runs/*_a5bca96b79_cf00d9bc`, `reports/v02/diagnostics/D1/*_8ea5177c03_cf00d9bc`, "
         "`reports/v02/qa_addendum`), конфигураций и git. Бэктесты не перезапускались, параметры не менялись, "
         "исторический test не скачивался и не запускался, торговля не запускалась. Производные расчёты аудита "
         "(помечены) выполнены по сохранённым прогнозам/сигналам/сделкам без переобучения, seed 42.", "",
         "Валюта USDT; виртуальный кошелёк 100 USDT на вариант, ноционал ≤ 50, spot long-or-cash. «н/д» — показатель "
         "не вычислялся (раздел 12.3).", "",
         "## 0. Краткое резюме", "",
         "* **G01** (межактивный lead-lag, Ridge): X хуже B1 по MSE во всех 9 комбинациях актив×горизонт на обоих "
         "периодах (в 15 из 18 CI исключает 0); X значимо хуже константы B0 во всех 6 комбинациях горизонт×период; B1 "
         "нигде значимо не лучше B0 (на dev 30/60 мин значимо хуже). Отклонено.",
         "* **H01** (часовой разворот): на validation реальный gross-эффект +3.4 bps к базе при 2 ч (CI исключает 0), "
         "на development ≈ 0; net −20…−27 bps на сигнал. Нет исполнимого преимущества. Отклонено.",
         "* **H02** (momentum 4ч/24ч): net отрицателен на обоих периодах. Отклонено.",
         "* **H03** (momentum 7д/28д): dev −17.5, val +35.1 USDT; превышение над безусловной доходностью незначимо, "
         "ниже медианы случайных входов и пассивного удержания на единицу экспозиции. Не определено (бета).",
         "* **H04**: значимые улучшения только за счёт отказа от торговли. Подтверждающего эффекта нет.",
         "* **Ни один вариант не прошёл Gate 3**; исторический test не запрашивается.",
         "* **Главный дефект**: diag-кошелёк v0.2 истощался (G01/H01 торговали 12–56 % окна, у H02 dev ноционал "
         "сжимался при cash < 50) — величины первичных тестов G01/H01 не являются оценками края; D1 (фикс. 50 USDT) "
         "подтверждает все выводы с неискажёнными величинами.",
         "* QA: 75 автотестов; сверка ledger без расхождений; побайтная воспроизводимость; чистый клон воспроизводит "
         "хэш кода прогонов; утечек не обнаружено.", ""]
    for fn in (sec_versions, sec_data, sec_results, sec_g01, sec_h03, sec_h04, sec_d1_compare, sec_d1_evidence,
               sec_stats, sec_leak, sec_reuse, sec_issues, sec_recorder, sec_needs_runs):
        fn(L)
    L += ["## 15. Состав пакета и воспроизведение", "",
          "Архив `ai-trading-lab-mh-v0.2.zip` создаётся `git archive --format=zip --prefix=ai-trading-lab/ "
          "<commit>:ai-trading-lab` из головы ветки `release/multi-horizon-v0.2` (детерминирован для коммита; SHA256 "
          "указан в `AUDIT_ARCHIVE_V02.sha256` на исследовательской ветке и в сопроводительном сообщении). Содержит: "
          "`src/` (v0.1 + v0.2 + recorder), `tests/`, `configs/`, `user_data/` (v0.1), `audit/`, все отчёты "
          "`reports/` (v0.1 и v0.2: прогоны, манифесты, QA-дополнение, D1, таблицы сигналов/прогнозов/сделок в gzip), "
          "документацию (`SPEC_MULTI_HORIZON_V02.md`, `SPEC_DIAGNOSTIC_D1.md`, `DECISIONS_V02.md`, "
          "`EXPERIMENT_LOG_V02.md`, `PROJECT_STATE_V02.md`, `README_V02.md`, этот файл), `requirements*.lock`. "
          "Не включены: архивы котировок и обработанные данные (`data/`), parquet-артефакты прогонов, виртуальные "
          "окружения, секреты (в проекте не используются).", "",
          "Воспроизведение: `README_V02.md` (download → validate-data → pytest → run development/validation → "
          "diag-d1 --confirmed → `python -m audit.qa_addendum_v02` → `python -m audit.build_final_audit_v02`). "
          "Ожидание: `outputs_sha256` в manifest.json совпадают побайтно.", ""]
    (ROOT / "FINAL_AUDIT_V02.md").write_text("\n".join(L))
    print("written FINAL_AUDIT_V02.md", len(L), "lines")


if __name__ == "__main__":
    main()
