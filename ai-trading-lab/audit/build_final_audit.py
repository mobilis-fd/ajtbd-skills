"""Build FINAL_AUDIT_V01.md from the COMMITTED MVP v0.1 run outputs only.

Reads reports/runs/{development,validation}_2bff6fcca7_792e0459/ (metrics.json, trades.csv, signals.csv,
risk_events.csv, event_study.csv, random_benchmark.csv, reconciliation.json, manifest.json,
freqtrade_comparison/*), configs/, docs and git metadata. It does not run backtests, does not touch data/
and never reads the locked test split. Derived tables (marked as such) are plain aggregations of the
committed trades.csv / signals.csv.

Usage (from ai-trading-lab/):  python audit/build_final_audit.py   -> FINAL_AUDIT_V01.md
Only the Python standard library + pandas are needed.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN_TAG = "2bff6fcca7_792e0459"
SPLITS = ["development", "validation"]
STRATS = ["E01-P", "E01-F", "E02-P", "E02-F"]
B01 = ["B01-h30", "B01-h60"]
ALL6 = STRATS + B01
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
NA = "н/д"
OUT = ROOT / "FINAL_AUDIT_V01.md"


# ----------------------------------------------------------------- helpers

def run_dir(split: str) -> Path:
    return ROOT / "reports" / "runs" / f"{split}_{RUN_TAG}"


def f(x, nd=2, pct=False):
    if x is None:
        return NA
    try:
        if isinstance(x, str):
            return x
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return NA
        v = float(x) * (100 if pct else 1)
        return f"{v:.{nd}f}"
    except Exception:
        return str(x)


def table(header: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return out + [""]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


M = {s: json.loads((run_dir(s) / "metrics.json").read_text()) for s in SPLITS}
MAN = {s: json.loads((run_dir(s) / "manifest.json").read_text()) for s in SPLITS}
TR = {s: pd.read_csv(run_dir(s) / "trades.csv") for s in SPLITS}
SIG = {s: pd.read_csv(run_dir(s) / "signals.csv") for s in SPLITS}
RISK = {s: pd.read_csv(run_dir(s) / "risk_events.csv") for s in SPLITS}
EV = {s: pd.read_csv(run_dir(s) / "event_study.csv") for s in SPLITS}
RB = {s: pd.read_csv(run_dir(s) / "random_benchmark.csv") for s in SPLITS}
REC = {s: json.loads((run_dir(s) / "reconciliation.json").read_text()) for s in SPLITS}
FTC = {s: json.loads((run_dir(s) / "freqtrade_comparison" / "comparison.json").read_text()) for s in SPLITS}
FTM = {s: pd.read_csv(run_dir(s) / "freqtrade_comparison" / "matched_trades.csv") for s in SPLITS}


def sc(split, strat, scen="main"):
    return M[split][strat]["scenarios"][scen]


def total_stop_time(split, strat, scen="main"):
    r = RISK[split]
    r = r[(r.strategy == strat) & (r.scenario == scen) & (r.event == "total_stop")]
    return r.time.iloc[0][:16] if len(r) else "не сработал"


def segment(split):
    a, b = MAN[split]["segment"]
    return a[:10], b[:10]


# ----------------------------------------------------------------- sections

def s_header() -> list[str]:
    head = git("rev-parse", "HEAD")
    L = ["# AI Trading Lab MVP v0.1: финальный аудиторский пакет",
         "",
         "Документ для независимого рецензента. Сгенерирован скриптом `audit/build_final_audit.py` исключительно из "
         "закоммиченных результатов прогонов `reports/runs/*_" + RUN_TAG + "/`, конфигураций, документации и git. "
         "Ни один бэктест для этого документа не перезапускался, стратегии, параметры и существующие прогоны не "
         "изменялись, locked holdout (test, 2026-08-20..2026-11-01) не запускался и не читался.",
         "",
         f"* Эксперимент: `{MAN['development']['experiment_id']}`; конфигурация `configs/mvp.yaml` sha256 "
         f"`{MAN['development']['config_sha256']}`.",
         f"* Эталонные прогоны: git `{MAN['development']['git_commit'][:7]}`, code sha256 "
         f"`{MAN['development']['code_sha256'][:10]}…`.",
         f"* Документ собран на коммите `{head[:7] or NA}` (код стратегий, движка и конфигурации идентичен "
         "pre-registration коммиту `944e2b1`, см. раздел 10.3).",
         "* Денежные величины в USDT; виртуальный кошелёк 100 USDT на стратегию, ставка 50 USDT, без плеча, только long spot.",
         "* `н/д` означает, что показатель в существующих прогонах не вычислялся; такие места перечислены в разделе 12.",
         "",
         "## 0. Краткое резюме",
         "",
         "* Все четыре предрегистрированные стратегии (E01-P, E01-F, E02-P, E02-F) дают **отрицательный net PnL** в основном "
         "сценарии (25 bps за круг, риск-лимиты включены) и на development, и на validation. Ни одна не значима после "
         "поправки Холма (p Holm = 1.00 везде). Победитель не объявляется.",
         "* Во всех кошельках, кроме E01-F на validation, сработал общий стоп (-10 USDT). Поэтому net около -10 в "
         "основном сценарии отражает лимит, а не скорость потерь; для оценки края см. сценарий signal-only и cost_rt0.",
         "* До издержек край мал и положителен у E01/E02 в signal-only (gross от +0.96 до +10.20 USDT), "
         "точка безубыточности по издержкам 0.84..6.22 bps за круг при допущенных 25 bps.",
         "* Собственный движок и Freqtrade совпадают по цене входа на 100 % сопоставленных сделок; расхождения по выходам "
         "объяснены различиями семантики ROI/стопа и комиссий (раздел 8).",
         "* 42 автотеста проходят; проверка look-ahead на реальных данных 75/75; Freqtrade lookahead-analysis без bias.",
         "* Найденные при аудите проблемы (раздел 10.5): исходный пакет `src/data` не был закоммичен и восстановлен "
         "2026-11-25 с побайтной проверкой результатов; неточная ссылка на коммит в EXPERIMENT_LOG L09; git-время коммитов "
         "не доказывает порядок pre-registration само по себе.",
         ""]
    return L


def s1_2() -> list[str]:
    L = ["## 1-2. Результаты стратегий и контрольных моделей", "",
         "Метрики из `metrics.json`. Gross PnL = результат по сырым ценам 1m (до комиссий и до проскальзывания); "
         "Net = Gross - fees - slippage (проверено по `trades.csv`). Expectancy = средний net на сделку. "
         "Max DD считается по кривой капитала с mark-to-market на 1m. Turnover = суммарный оборот / начальный капитал "
         "(100). Exposure = доля времени в позиции, %.", ""]
    for sp in SPLITS:
        a, b = segment(sp)
        L += [f"### {sp} [{a}, {b}) UTC", "", "**Основной сценарий (25 bps RT, риск-лимиты включены): PnL и издержки**", ""]
        rows = []
        for s in ALL6:
            m = sc(sp, s)
            rows.append([s, M[sp][s]["n_raw_signals"], m["n_trades"], f(m["gross_pnl"]), f(m["fees"]),
                         f(m["slippage_cost"]), f(m["fees"] + m["slippage_cost"]), f(m["net_pnl"]), f(m["return_pct"]),
                         f(m["final_equity"]), total_stop_time(sp, s)])
        L += table(["strategy", "raw signals", "trades", "gross", "fees", "slippage", "costs total", "net", "return %",
                    "final equity", "total stop at (UTC)"], rows)
        L += ["**Основной сценарий: качество сделок и риск**", ""]
        rows = []
        for s in ALL6:
            m = sc(sp, s)
            rows.append([s, f(m["win_rate"], 1, pct=True), f(m["profit_factor"]), f(m["expectancy"], 3),
                         f(m["avg_win"], 3), f(m["avg_loss"], 3), f(m["max_drawdown_usdt"]), f(m["max_drawdown_pct"]),
                         f(m["turnover_x_initial"], 1), f(m["exposure_pct_time"]), f(m["avg_hold_minutes"], 1),
                         f(m["sharpe_daily_ann"]), f(m["sortino_daily_ann"]), m["n_days"]])
        L += table(["strategy", "win rate %", "PF", "expectancy", "avg win", "avg loss", "max DD USDT", "max DD %",
                    "turnover x", "exposure %", "avg hold min", "Sharpe(d, ann)", "Sortino(d, ann)", "days"], rows)
        L += ["**Диагностика signal-only (без портфельных лимитов, 25 bps RT; не оценка безопасной торговли)**", ""]
        rows = []
        for s in ALL6:
            m = sc(sp, s, "signal_only_no_portfolio_stop")
            rows.append([s, m["n_trades"], f(m["gross_pnl"]), f(m["fees"]), f(m["slippage_cost"]), f(m["net_pnl"]),
                         f(m["win_rate"], 1, pct=True), f(m["profit_factor"]), f(m["expectancy"], 3),
                         f(m["max_drawdown_usdt"]), f(m["turnover_x_initial"], 1), f(m["exposure_pct_time"])])
        L += table(["strategy", "trades", "gross", "fees", "slippage", "net", "win rate %", "PF", "expectancy",
                    "max DD", "turnover x", "exposure %"], rows)
        L += ["**Контрольные модели**", ""]
        rows = [["B00 cash", 0, "0.00", "0.00", "0.00", "0.00", NA, NA, NA, "0.00", "0.0", "0.00"]]
        for sym in SYMS:
            b = M[sp][f"B02-BH-{sym}"]
            rows.append([f"B02 buy&hold {sym} ($50)", 1, NA, f(b["fees"]), NA, f(b["net_pnl"]), NA, NA, NA,
                         f(b["max_drawdown_usdt"]), NA, f(b["exposure_pct_time"])])
        L += table(["control", "trades", "gross", "fees", "slippage", "net", "win rate %", "PF", "expectancy",
                    "max DD", "turnover x", "exposure %"], rows)
        L += ["B02 не вычислял gross, slippage, win rate, PF, expectancy и turnover (одна сделка, отчёт хранит только "
              "net, fees, max DD и exposure). B02 без стопа и риск-лимитов: другой профиль риска.", "",
              "B03 (случайные входы с той же частотой по символам, 100 фиксированных сидов на цель, те же правила "
              "выхода, риска и издержек), основной сценарий; медианы по сидам из `random_benchmark.csv`:", ""]
        rows = []
        rb = RB[sp]
        for t in STRATS:
            r = rb[rb.target == t]
            q = M[sp]["B03-random"][t]
            rows.append([f"B03~{t}", len(r), f(r.n_trades.median(), 0), f(r.gross_pnl.median()), f(r.fees.median()),
                         f(r.slippage_cost.median()), f(r.net_pnl.median()), f(r.win_rate.median(), 1, pct=True),
                         f(r.profit_factor.median()), f(r.expectancy.median(), 3), f(r.max_drawdown_usdt.median()),
                         f"[{f(q['net_pnl_quantiles_5_25_50_75_95'][0])}, {f(q['net_pnl_quantiles_5_25_50_75_95'][4])}]"])
        L += table(["control", "seeds", "trades (med)", "gross (med)", "fees (med)", "slippage (med)", "net (med)",
                    "win rate % (med)", "PF (med)", "expectancy (med)", "max DD (med)", "net p5..p95"], rows)
        L += ["Turnover и exposure для B03 в существующих прогонах не сохранены: " + NA + ".", ""]
    return L


def s3() -> list[str]:
    L = ["## 3. Результаты по отдельным активам", "",
         "Из `metrics.json` (`by_symbol`). Max DD, turnover и exposure по активам не вычислялись: кошелёк общий для "
         "трёх активов, поэтому эти показатели определены только на уровне стратегии (" + NA + ").", ""]
    for sp in SPLITS:
        for scen, title in (("main", "основной сценарий"), ("signal_only_no_portfolio_stop", "signal-only")):
            L += [f"### {sp}, {title}", ""]
            rows = []
            for s in ALL6:
                for sym in SYMS:
                    m = sc(sp, s, scen)["by_symbol"].get(sym)
                    raw = M[sp][s]["raw_signals_by_symbol"].get(sym)
                    if m is None:
                        rows.append([s, sym, raw, 0] + [NA] * 8)
                        continue
                    rows.append([s, sym, raw, m["n_trades"], f(m["gross_pnl"]), f(m["fees"]), f(m["slippage_cost"]),
                                 f(m["net_pnl"]), f(m["win_rate"], 1, pct=True), f(m["profit_factor"]),
                                 f(m["expectancy"], 3), f(m["avg_win"], 3) + " / " + f(m["avg_loss"], 3)])
            L += table(["strategy", "symbol", "raw signals", "trades", "gross", "fees", "slippage", "net", "win %",
                        "PF", "expectancy", "avg win / avg loss"], rows)
        L += [f"Buy&hold по активам ({sp}): " + ", ".join(
            f"{sym} net {f(M[sp]['B02-BH-' + sym]['net_pnl'])} (max DD {f(M[sp]['B02-BH-' + sym]['max_drawdown_usdt'])})"
            for sym in SYMS) + ".", ""]
    return L


def _gross_bps(t: pd.DataFrame) -> float:
    n = t["notional_in"].sum()
    return float(t["gross_pnl"].sum() / n * 1e4) if n else float("nan")


def s4() -> list[str]:
    L = ["## 4. Сравнение P- и F-вариантов (E01-P vs E01-F, E02-P vs E02-F)", "",
         "F-вариант = P-вариант плюс фильтр по дисбалансу taker-объёма I(t) (см. STRATEGY_REGISTRY). "
         "Сравнение на сценарии signal-only (одинаковые правила, без искажения общим стопом) и основном. "
         "Таблицы «пересечение» и «gross bps на сделку» являются производными агрегатами закоммиченных "
         "`signals.csv` / `trades.csv`; новых прогонов нет.", ""]
    for p, fv in (("E01-P", "E01-F"), ("E02-P", "E02-F")):
        L += [f"### {p} vs {fv}", ""]
        rows = []
        for sp in SPLITS:
            for s in (p, fv):
                mm, so = sc(sp, s), sc(sp, s, "signal_only_no_portfolio_stop")
                t = TR[sp][(TR[sp].strategy == s) & (TR[sp].scenario == "signal_only_no_portfolio_stop")]
                rows.append([sp, s, M[sp][s]["n_raw_signals"], so["n_trades"], f(so["gross_pnl"]), f(so["net_pnl"]),
                             f(_gross_bps(t)), f(so["expectancy"], 3), f(so["win_rate"], 1, pct=True),
                             f(so["profit_factor"]), f(mm["net_pnl"]), total_stop_time(sp, s)])
        L += table(["split", "strategy", "raw signals", "trades (sig-only)", "gross (sig-only)", "net (sig-only)",
                    "gross bps/trade (sig-only, derived)", "expectancy (sig-only)", "win % (sig-only)",
                    "PF (sig-only)", "net (main)", "total stop"], rows)
        rows = []
        for sp in SPLITS:
            sg = SIG[sp]
            sp_ = set(zip(sg[sg.strategy == p].symbol, sg[sg.strategy == p].signal_open_time))
            sf = set(zip(sg[sg.strategy == fv].symbol, sg[sg.strategy == fv].signal_open_time))
            tr = TR[sp][TR[sp].scenario == "signal_only_no_portfolio_stop"]
            tp, tf = tr[tr.strategy == p], tr[tr.strategy == fv]
            kp = set(zip(tp.symbol, tp.entry_time))
            common = tf[[k in kp for k in zip(tf.symbol, tf.entry_time)]]
            fonly = tf[[k not in kp for k in zip(tf.symbol, tf.entry_time)]]
            pnotf = tp[[k not in set(zip(tf.symbol, tf.entry_time)) for k in zip(tp.symbol, tp.entry_time)]]
            rows.append([sp, len(sf), len(sf & sp_), f(len(sf & sp_) / len(sf) * 100 if sf else float('nan'), 1),
                         len(common), f(common.net_pnl.sum()), f(_gross_bps(common)),
                         len(fonly), f(fonly.net_pnl.sum()), len(pnotf), f(pnotf.net_pnl.sum()), f(_gross_bps(pnotf))])
        L += [f"Пересечение (derived, signal-only):", ""]
        L += table(["split", f"{fv} raw signals", f"of them also {p} signals", "share %",
                    f"{fv} trades also traded by {p}", "their net", "their gross bps",
                    f"{fv}-only trades", "their net", f"{p} trades filtered out by F", "their net", "their gross bps"], rows)
        rows = []
        for sp in SPLITS:
            e = EV[sp]
            for s in (p, fv):
                for h in (15, 30, 60):
                    r = e[(e.group == s) & (e.symbol == "ALL") & (e.horizon_min == h)]
                    if len(r):
                        r = r.iloc[0]
                        rows.append([sp, s, h, int(r.n), f(r.mean_bps), f(r.median_bps), f(r.share_positive, 2),
                                     f(r.t_stat_naive)])
        L += ["Event study (форвардная лог-доходность от 1m open в момент решения, все символы вместе; naive t "
              "завышает значимость из-за кластеризации сигналов):", ""]
        L += table(["split", "strategy", "h min", "n", "mean bps", "median bps", "share > 0", "naive t"], rows)
    L += ["Вывод по данным (signal-only, без статистической проверки различий):",
          "",
          "* **E01:** F хуже P на сделку на обоих периодах (gross bps, expectancy, win rate, PF ниже). Сделки, которые "
          "F отсекает у P, имели более высокий gross bps, чем общие сделки, то есть фильтр убирает скорее лучшие входы.",
          "* **E02:** F немного лучше P на сделку на обоих периодах (gross bps, expectancy, PF выше), но разница мала "
          "относительно 25 bps издержек и не проверялась на значимость.",
          "* F уменьшает число сделок и абсолютный убыток в signal-only; ни P, ни F не покрывают 25 bps издержек "
          "(gross 0.34..7.50 bps на сделку).",
          "* Расхождение с документацией: `PROJECT_STATE.md` утверждает, что ожидание F не лучше P устойчиво; для E02 "
          "это не так (см. раздел 10.5, п. 9).", ""]
    return L


def s5() -> list[str]:
    L = ["## 5. Чувствительность к торговым издержкам и исполнению", "",
         "Полные перепрогоны с включёнными риск-лимитами (из `metrics.json`). 0/10/40 bps за круг гипотетические, "
         "деление fee:slippage 80:20; `delay60` = вход на минуту позже; `coarse_step_x10` = шаг лота x10 (фильтры биржи "
         "допущены, не проверены). Break-even = Σgross / Σentry notional в прогоне cost_rt0 (фиксированные заполнения). "
         "Важно: при включённом общем стопе значения около -10 означают срабатывание лимита.", ""]
    scen = [("cost_rt0", "0 bps"), ("cost_rt10", "10 bps"), ("main", "25 bps main"), ("cost_rt40", "40 bps"),
            ("delay60", "delay 60s"), ("coarse_step_x10", "step x10")]
    for sp in SPLITS:
        L += [f"### {sp}", ""]
        rows = []
        for s in ALL6:
            r = [s]
            for k, _ in scen:
                m = sc(sp, s, k)
                r.append(f"{f(m['net_pnl'])} ({m['n_trades']})")
            r.append(f(sc(sp, s, "cost_rt0").get("break_even_roundtrip_cost_bps")))
            rows.append(r)
        L += table(["strategy"] + [f"net (trades) {n}" for _, n in scen] + ["break-even RT bps"], rows)
        rows = []
        for s in ALL6:
            r = [s]
            for k, _ in scen:
                m = sc(sp, s, k)
                r.append(f"{f(m['gross_pnl'])} / {f(m['fees'] + m['slippage_cost'])}")
            rows.append(r)
        L += ["Gross / (fees + slippage) по сценариям:", ""]
        L += table(["strategy"] + [n for _, n in scen], rows)
        rows = []
        for s in STRATS:
            m = sc(sp, s)
            rows.append([s, f(m["net_pnl"]), f(m["conservative_gap_scenario_net_pnl"]), m["uncertain_gap_trades"]])
        L += ["Консервативный сценарий для гэпов (uncertain-gap trades); данные без пропусков, поэтому разница нулевая "
              "или почти нулевая:", ""]
        L += table(["strategy", "net main", "net conservative gaps", "uncertain-gap trades"], rows)
    L += ["Отсутствует: сценарии signal-only (без общего стопа) при 0/10/40 bps не прогонялись, поэтому чистая "
          "кривая net(издержки) без влияния лимитов доступна только через break-even и cost_rt0 (" + NA + " для "
          "остальных точек).", ""]
    return L


def s6() -> list[str]:
    L = ["## 6. Причины закрытия позиций и срабатывания риск-лимитов", "",
         "Правила: стоп -0.6 % и цель +0.9 % от фактического заполнения; time exit по удержанию (30/60 мин); при "
         "конфликте в одной минуте сначала стоп; дневной лимит 1.5 USDT от equity начала UTC-дня (пауза до следующего "
         "дня, принудительный выход на следующем 1m open); общий лимит 10 USDT (остановка кошелька).", ""]
    reasons = ["stop", "target", "target_gap", "stop_gap", "time_exit", "risk_exit_daily", "risk_exit_total",
               "boundary_exit"]
    for sp in SPLITS:
        for scen, title in (("main", "основной"), ("signal_only_no_portfolio_stop", "signal-only")):
            L += [f"### {sp}, {title}: причины выхода (число сделок)", ""]
            rows = []
            seen = set()
            for s in ALL6:
                seen |= set(sc(sp, s, scen)["exit_reasons"])
            cols = [r for r in reasons if r in seen] + sorted(seen - set(reasons))
            for s in ALL6:
                er = sc(sp, s, scen)["exit_reasons"]
                rows.append([s] + [er.get(c, 0) for c in cols] + [sum(er.values())])
            L += table(["strategy"] + cols + ["total"], rows)
        L += [f"### {sp}: отклонённые сигналы (основной сценарий)", ""]
        seen = set()
        for s in ALL6:
            seen |= set(sc(sp, s)["rejected_signals"])
        cols = sorted(seen)
        L += table(["strategy"] + cols, [[s] + [sc(sp, s)["rejected_signals"].get(c, 0) for c in cols] for s in ALL6])
        L += [f"### {sp}: события риск-лимитов (основной сценарий, `risk_events.csv`)", ""]
        rows = []
        r = RISK[sp][RISK[sp].scenario == "main"]
        for s in ALL6:
            rs = r[r.strategy == s]
            cnt = rs.event.value_counts().to_dict()
            exc = rs[rs.event.isin(["daily_pause", "total_stop"])].exceeded_by
            rows.append([s, cnt.get("daily_pause", 0), cnt.get("risk_exit_daily_triggered", 0),
                         cnt.get("risk_exit_total_triggered", 0), cnt.get("total_stop", 0),
                         total_stop_time(sp, s), f(exc.max(), 3) if len(exc) else "0"])
        L += table(["strategy", "daily pauses", "forced exits (daily)", "forced exits (total)", "total stop",
                    "total stop at", "max overshoot beyond limit USDT"], rows)
    L += ["Overshoot: лимиты проверяются по закрытиям 1m (не по внутрибаровым минимумам), поэтому фактический "
          "убыток может превысить лимит на величину движения за минуту и издержки выхода (D14, ограничение 4).", ""]
    return L


def s7() -> list[str]:
    L = ["## 7. Статистические тесты, доверительные интервалы, сравнение с контролями", "",
         "Moving-block bootstrap дневного PnL (дни без сделок включены, 2000 повторов, seed 20261125, блоки 7 дней, "
         "чувствительность 3 и 14 дней). H0: средний дневной PnL <= 0, односторонний p; поправка Холма по 4 кандидатам "
         "(7-дневные блоки). Предварительный характер: один период на split, сигналы кластеризованы.", ""]
    for sp in SPLITS:
        for scen, title in (("main", "основной"), ("signal_only_no_portfolio_stop", "signal-only")):
            L += [f"### {sp}, {title}", ""]
            rows = []
            for s in ALL6:
                bs = sc(sp, s, scen).get("bootstrap")
                if not bs:
                    rows.append([s] + [NA] * 7)
                    continue
                for k in ("block_7d", "block_3d", "block_14d"):
                    b = bs.get(k)
                    if not b:
                        continue
                    rows.append([s, k, b["n_days"], f(b["mean_daily_pnl"], 4),
                                 f"[{f(b['ci95_mean_daily'][0], 4)}, {f(b['ci95_mean_daily'][1], 4)}]",
                                 f"[{f(b['ci95_total'][0])}, {f(b['ci95_total'][1])}]",
                                 f(b["share_boot_mean_le_0"], 3), f(b["p_one_sided_mean_gt_0"], 3) + f" ({b['status']})"])
            L += table(["strategy", "block", "days", "mean daily PnL", "95% CI mean daily", "95% CI total",
                        "P(boot mean<=0)", "p one-sided"], rows)
        L += [f"Поправка Холма ({sp}, основной сценарий):", ""]
        L += table(["candidate", "p", "p Holm", "reject H0 at 5%"],
                   [[s, f(M[sp]["holm"][s]["p"]), f(M[sp]["holm"][s]["p_holm"]), M[sp]["holm"][s]["reject_h0"]]
                    for s in STRATS])
        rows = []
        for s in STRATS:
            q = M[sp]["B03-random"][s]
            qq = q["net_pnl_quantiles_5_25_50_75_95"]
            rows.append([s, f(q["strategy_net_pnl"]), f(qq[0]), f(qq[2]), f(qq[4]), f(q["mean_n_trades"], 1),
                         f(q["share_seeds_ge_strategy"])])
        L += [f"Сравнение с B03 ({sp}, основной сценарий; доля сидов с net >= стратегии):", ""]
        L += table(["strategy", "strategy net", "B03 p5", "B03 median", "B03 p95", "B03 mean trades",
                    "share seeds >= strategy"], rows)
        bh = ", ".join(f"{sym} {f(M[sp]['B02-BH-' + sym]['net_pnl'])}" for sym in SYMS)
        L += [f"Сравнение с B00/B02 ({sp}): cash 0.00; buy&hold $50: {bh}. B01 (SampleStrategy-адаптация): "
              f"h30 {f(sc(sp, 'B01-h30')['net_pnl'])}, h60 {f(sc(sp, 'B01-h60')['net_pnl'])}.", ""]
    L += ["Интерпретация в пределах теста: ни один кандидат не отвергает H0 ни на одном периоде; в основном сценарии "
          "почти все кошельки и почти все случайные сиды упираются в общий стоп, поэтому сравнение с B03 там малоинформативно "
          "(кроме E01-F на validation: 1 % сидов не хуже стратегии, но сама стратегия в минусе). Sharpe/Sortino годовые "
          "по дневным данным приведены в разделе 1-2; их доверительные интервалы не вычислялись (" + NA + ").", ""]
    return L


def s8() -> list[str]:
    L = ["## 8. Сверка собственного движка с Freqtrade", "",
         "Freqtrade 2026.10, offline-рынки со статическими допущенными фильтрами (D23: api.binance.com гео-ограничен, "
         "обход не выполнялся), `--timeframe-detail 1m`, fee 0.00125 на сторону (= 10 bps fee + 2.5 bps slippage), "
         "stake 50, wallet 100. Эталон: собственный движок, сценарий signal-only (у Freqtrade нет equity-лимитов). "
         "F-стратегии в Freqtrade получают taker-объём через sidecar-join по (symbol, close_time). B01 через Freqtrade "
         "не сверялся (" + NA + ").", ""]
    for sp in SPLITS:
        c = FTC[sp]
        L += [f"### {sp}", ""]
        rows = []
        for s in STRATS:
            x = c["strategies"][s]
            rows.append([s, x["ft_trades"], x["ref_trades"], x["matched_entries"], x["only_freqtrade"],
                         x["only_reference"], f(x["entry_price_abs_diff_bps_median"]), f(x["same_exit_time_share"] * 100, 1),
                         f(x["ft_net_pnl"]), f(x["ref_net_pnl_signal_only"]), f(x["matched_pnl_ft"]),
                         f(x["matched_pnl_ref"])])
        L += table(["strategy", "FT trades", "ref trades", "matched entries", "only FT", "only ref",
                    "entry px diff median bps", "same exit time %", "FT net", "ref net", "matched FT net",
                    "matched ref net"], rows)
        m = FTM[sp]
        b = m[m["_merge"] == "both"]
        bps = (b.open_rate / b.raw_entry - 1) * 1e4
        L += [f"Проверка аудитом по `matched_trades.csv`: сопоставлено {len(b)} входов; максимальное |разница цены "
              f"входа| = {f(bps.abs().max(), 4)} bps; доля точных совпадений {f((bps.abs() < 1e-6).mean() * 100, 1)} %.", ""]
        rows = [[k, v["n"], f(v["median_exit_time_diff_min"], 1), f(v["median_exit_price_diff_bps"], 3)]
                for k, v in sorted(c["exit_diagnostics_all_strategies"].items())]
        L += ["Пары причин выхода на сопоставленных входах (эталон | Freqtrade):", ""]
        L += table(["pair", "n", "median exit time diff, min", "median exit price diff, bps"], rows)
    L += ["### Все обнаруженные расхождения и их причины", "",
          "Ни одно расхождение не разрешалось в пользу какого-либо движка; эталоном остаётся собственный движок (D03).", "",
          "1. **ROI vs target.** Freqtrade `minimal_roi` 0.9 % считается по прибыли после комиссий, нужно около +1.15 % цены. "
          "Поэтому эталонные `target` часто становятся у Freqtrade `time_exit` или `stop_loss`, а выходы по ROI примерно "
          "на +22.5 bps выше (пары target|roi).",
          "2. **Стоп.** Freqtrade ставит стоп от сырой цены открытия без модели проскальзывания и исполняет по цене стопа; "
          "эталон считает стоп от проскальзнувшего заполнения и исполняет с -2.5 bps. Разница около -2.5 bps; Freqtrade "
          "помечает выход открытием бара (медиана -1 мин в паре stop|stop_loss).",
          "3. **Исчерпание баланса.** Freqtrade перестаёт открывать сделки, когда свободный баланс < stake 50 (около -50 USDT), "
          "эталон signal-only продолжает с min(50, cash). Отсюда большие «only ref» на development (E01-P 385, E02-P 303) "
          "и FT net около -50.",
          "4. **Расхождение траекторий.** Разные выходы меняют, какие следующие сигналы блокируются открытой позицией или "
          "cooldown; отсюда «only FT» / «only ref» и на validation, где баланс не исчерпан.",
          "5. **Комиссия.** Freqtrade берёт 0.125 % на сторону как комиссию, эталон 0.10 % комиссии + 2.5 bps к цене.",
          "6. **Редкие пары target|stop_loss (dev 11, val 2) и stop|roi (dev 2).** Следствие пп. 1-2 и разной точки отсчёта "
          "стопа/цели; разбор по сделкам в `matched_trades.csv`.",
          "",
          "Воспроизведение 2026-11-25 на машине владельца (чистый клон): offline-бэктест Freqtrade для development дал "
          "`matched_trades.csv`, побайтно идентичный закоммиченному; `comparison.md` отличался только путём к каталогу "
          "прогона. Validation-сверка через Freqtrade при воспроизведении не повторялась (" + NA + ").", ""]
    return L


def s9() -> list[str]:
    tests = {}
    for p in sorted((ROOT / "tests").glob("test_*.py")):
        tests[p.name] = re.findall(r"^def (test_\w+)", p.read_text(), re.M)
    n = sum(len(v) for v in tests.values())
    L = ["## 9. Автотесты, look-ahead проверки и ограничения методологии", "",
         f"### 9.1 Автотесты ({n} тестов)", "",
         "Результаты: 42 passed (`pytest -q`) на машине владельца 2026-11-25 с загруженными данными (Python 3.13.18, "
         "зависимости из `requirements.lock`); в облачной среде без рыночных данных 38 passed, 4 skipped (интеграционные "
         "тесты на реальных данных пропускаются при отсутствии `data/processed`). Исходная сессия разработки также "
         "фиксировала 42 passed (EXPERIMENT_LOG L09).", ""]
    for k, v in tests.items():
        L += [f"* `{k}` ({len(v)}): " + ", ".join(f"`{t}`" for t in v)]
    pc = json.loads((ROOT / "reports" / "signal_prefix_check.json").read_text())
    L += ["", "### 9.2 Look-ahead", "",
          f"* Собственная проверка на реальных development-данных (`test-signals`): {pc['n_checks']} проверок, "
          f"{pc['n_failed']} неудачных, ok = {pc['ok']}. Две проверки на каждом срезе: инвариантность к префиксу (признаки и "
          "сигналы на данных, обрезанных в момент c, равны полным для t < c) и к мутации будущего (случайное искажение "
          "свечей начиная с c не меняет значения до c); плюс то же для B01. Повторена 2026-11-25: 75/75.",
          "* Freqtrade `lookahead-analysis` (2025-11-01..2026-01-01, 30 сигналов на стратегию): has_bias = No для "
          "MvpE01P, MvpE01F, MvpE02P, MvpE02F (`reports/freqtrade_lookahead_analysis.txt`).",
          "* Freqtrade `recursive-analysis` (startup 300/400/600): различия z5/z15 только на уровне плавающей точки "
          "(в таблице 0.000 %; PROJECT_STATE: < 0.0005 %) (`reports/freqtrade_recursive_analysis.txt`).",
          "* Синтетические тесты: `test_prefix_and_future_mutation_invariance_synthetic`, "
          "`test_entry_at_next_open_after_signal_close_not_signal_close`, "
          "`test_sidecar_join_exact_close_time_no_leakage_and_fail_closed`.",
          "", "### 9.3 Сверка леджера", ""]
    rows = []
    for sp in SPLITS:
        for s, v in REC[sp].items():
            rows.append([sp, s, v["n_trades"], v["ok"], f(v["sum_net_pnl"], 6), f(v["recomputed_final_cash"], 6),
                         len(v["issues"])])
    L += table(["split", "strategy", "trades", "ok", "Σ net PnL", "recomputed final cash", "issues"], rows)
    L += ["Ручные пошаговые проверки сделок по сырым 1m барам: раздел «Manual trade checks» в каждом `qa_report.md`.", "",
          "### 9.4 Качество данных", "",
          "39/39 месячных архивов Binance (BTC/ETH/SOL, 2025-10..2026-10) с проверкой SHA256 по `.CHECKSUM`; по каждому "
          "символу 535 680 минут из 535 680 ожидаемых, 0 пропусков, 0 дублей, 0 нарушений OHLC, все метки в µs "
          "(`reports/data_qa.md`). Проверки целостности не используют цены/доходности, holdout на результативность не "
          "смотрелся.", "",
          "### 9.5 Ограничения методологии", "",
          "1. Фильтры биржи (tick/step/minNotional) допущены, не проверены (api.binance.com гео-ограничен, D13). "
          "Чувствительность step x10 меняет результат незначительно.",
          "2. Издержки - рабочее допущение (10 bps fee + 2.5 bps проскальзывания на сторону). Реальный спред из OHLCV не "
          "наблюдаем; нет моделей очереди и частичного исполнения.",
          "3. Комиссия в валюте котировки (Binance списывает комиссию покупки в базовом активе, если не BNB) (D12).",
          "4. Портфельные лимиты проверяются по закрытиям 1m, не по внутрибаровым минимумам (D14).",
          "5. Freqtrade запускался с offline-рынками; его семантика ROI/стопа отличается (D23, D24), это перекрёстная "
          "проверка, не эталон.",
          "6. В данных нет пропусков, поэтому ветки кода uncertain-gap и консервативного закрытия покрыты только "
          "юнит-тестами.",
          "7. Один период на split; validation 73 дня; bootstrap предварительный; сигналы кластеризованы по времени и "
          "символам (naive t в event study завышен).",
          "8. Основной сценарий ограничен общим стопом -10 USDT: net около -10 не является оценкой скорости потерь.",
          "9. Docker-образ не собирался; live WebSocket/REST адаптер не реализован (есть только протестированный "
          "обработчик сообщений).",
          "10. Инцидент D25: при осмотре формата напечатаны 3 сырые 1m строки 2026-10-01 (holdout); статистика не считалась.",
          "11. Результаты скользящих окон слегка зависят от начала ряда (recursive-analysis), что важно только на точных "
          "границах порогов.",
          "12. Регимные пороги зафиксированы на development (медиана vol24h), D18; на validation используются как есть.",
          ""]
    return L


def s10() -> list[str]:
    L = ["## 10. Хронология, версии, конфигурации, хэши, известные проблемы", "", "### 10.1 Коммиты", ""]
    log = git("log", "--format=%h|%ad|%s", "--date=iso-strict", "--", ".")
    rows = [line.split("|", 2) for line in reversed(log.splitlines())] if log else []
    L += table(["commit", "date", "message"], rows)
    L += ["### 10.2 Журнал экспериментов", "",
          "Полностью в `EXPERIMENT_LOG.md` (L01..L17) и `DECISIONS.md` (D01..D25). Ключевые точки: L08 pre-registration "
          "(коммит `944e2b1`); L12/L14 полные бэктесты development/validation; L13 Freqtrade и lookahead/recursive; "
          "L15 финальные прогоны на чистом `803db3a` (`*_" + RUN_TAG + "`); L16 holdout и dry-run не запускались; "
          "L17 восстановление `src/data` и побайтное воспроизведение на чистом клоне.", "",
          "### 10.3 Неизменность правил после pre-registration", "",
          "`git diff 944e2b1 HEAD -- configs STRATEGY_REGISTRY.md src/signals src/features src/evaluation/engine.py "
          "user_data/strategies` пуст: конфигурация, реестр стратегий, признаки, правила сигналов, движок и обёртки "
          "Freqtrade не менялись. Между `944e2b1` и `803db3a` менялись только отчётность (`report.py`, `compare.py`, "
          "`cli.py`), текст ручных проверок (`ledger.py`), условие Sortino (>= 2 дней, `metrics.py`) и шаблон dry-run.", "",
          "### 10.4 Версии и конфигурация", ""]
    req = (ROOT / "requirements.lock").read_text().splitlines()
    keys = ("freqtrade", "pandas", "numpy", "pyarrow", "pytest", "TA-Lib", "technical", "ccxt", "scipy", "PyYAML")
    vers = [r for r in req if r.split("==")[0] in keys]
    L += ["* Python 3.13 (воспроизведение: 3.13.18); полный pin в `requirements.lock` (" + str(len([r for r in req if '==' in r]))
          + " пакетов). Ключевые: " + ", ".join(f"`{v}`" for v in vers) + ".",
          f"* `configs/mvp.yaml` sha256 `{sha256(ROOT / 'configs' / 'mvp.yaml')}`.",
          f"* `configs/regime_thresholds.json` sha256 `{sha256(ROOT / 'configs' / 'regime_thresholds.json')}`.",
          f"* `requirements.lock` sha256 `{sha256(ROOT / 'requirements.lock')}`.",
          f"* Freqtrade SampleStrategy (B01) sha256 `{MAN['development']['freqtrade_sample_strategy_sha256']}`.",
          "* Сплиты: development [2025-11-01, 2026-06-08), validation [2026-06-08, 2026-08-20), test locked "
          "[2026-08-20, 2026-11-01); warmup 7 дней.", ""]
    rows = []
    for sp in SPLITS:
        man = MAN[sp]
        rows.append([sp, man["git_commit"][:7], man["code_sha256"][:12], man["config_sha256"][:12],
                     man["data_manifest_sha256"][:12], man["regime_thresholds_sha256"][:12]] +
                    [man["data_sha256_1m_split"][s][:12] for s in SYMS])
    L += ["Хэши эталонных прогонов (`manifest.json`):", ""]
    L += table(["split", "git", "code", "config", "data manifest", "regime thr.", "1m BTC", "1m ETH", "1m SOL"], rows)
    rows = []
    for sp in SPLITS:
        for k, v in sorted(MAN[sp]["outputs_sha256"].items()):
            rows.append([sp, k, v])
    L += ["Хэши выходных файлов (`outputs_sha256`); при воспроизведении 2026-11-25 все 9 файлов на обоих периодах "
          "совпали побайтно:", ""]
    L += table(["split", "file", "sha256"], rows)
    L += ["### 10.5 Известные проблемы (включая найденные при аудите)", "",
          "1. **`src/data` отсутствовал в git до 2026-11-25.** Правило `.gitignore` `data/` исключило и пакет кода "
          "`src/data/`; коммиты до `a9d28b0` неработоспособны из чистого клона. Пакет восстановлен по тестам, CLI и "
          "D04-D06/D22 (`a9d28b0`, `789683e`). Проверка: на чистом клоне все 9 выходных файлов обоих периодов и "
          "`data_sha256_1m_split` побайтно совпали с эталоном. Следствие: `code_sha256 2bff6fcca7…` эталонных прогонов "
          "относится к дереву с исходным (незакоммиченным) `src/data` и из git не воспроизводится; текущий код даёт "
          "`code_sha256 34817544ca…` при идентичных результатах. Рецензенту стоит учитывать, что слой данных - "
          "реконструкция, подтверждённая по выходам, а не исходный код.",
          "2. **EXPERIMENT_LOG L09** ссылается на исправление sidecar-join «commit 944e2b1 → 5f4f481», но `sidecar.py` "
          "в git существует только в виде `944e2b1` и после не менялся; `5f4f481` меняет только `metrics.py`. Вероятно, "
          "исправление сделано до pre-registration коммита, ссылка неточна. Журнал не исправлялся (исторический документ).",
          "3. **Порядок pre-registration по git не доказуем сам по себе.** Все коммиты исходной сессии созданы за ~8 минут "
          "(2026-11-24 19:20..19:27 UTC), после генерации data QA (19:13). Git подтверждает, что правила не менялись после "
          "`944e2b1`, но не то, что до него не было полных бэктестов; это утверждение опирается на EXPERIMENT_LOG.",
          "4. `data_manifest_sha256` не воспроизводится при повторной загрузке (манифест содержит время загрузки); "
          "сами архивы проверяются по SHA256 Binance.",
          "5. README: для Freqtrade каталог `user_data/backtest_results/<split>` нужно создать заранее, иначе Freqtrade "
          "пишет `<split>-<дата>.zip` рядом (исправлено в README, `789683e`).",
          "6. Фильтры биржи допущены (D13); комиссии в quote (D12); Docker не собран; live-адаптер не реализован.",
          "7. Инцидент D25 (3 строки holdout напечатаны при осмотре формата).",
          "8. `reports/SUMMARY_development_validation.md` перегенерируется командой `summary` по последнему прогону; при "
          "новом code hash меняется только строка с каталогами прогонов.",
          "9. `PROJECT_STATE.md`: фраза «F-фильтр не даёт устойчиво лучшего ожидания на сделку» верна для E01, но не "
          "для E02, где F лучше P по expectancy и gross bps на обоих периодах (раздел 4). На выводы о непригодности не "
          "влияет: ни один вариант не покрывает издержки.",
          ""]
    return L


def s11() -> list[str]:
    return ["## 11. Предлагаемые диагностические проверки (не запускались)", "",
            "Цель: понять, почему результат отрицательный, не меняя предрегистрированные правила. Все проверки только на "
            "development/validation; новые варианты правил допустимы лишь как новый эксперимент с новым ID и оценкой на "
            "более поздних данных.", "",
            "1. **Декомпозиция края против издержек.** По каждой сделке signal-only: gross bps, MFE/MAE в пределах удержания, "
            "распределение gross bps против порога 25 bps. Ответит, есть ли хвост сделок с краем, превышающим издержки.",
            "2. **Кривая затухания сигнала.** Event study на горизонтах 1, 2, 5, 10, 15, 30, 60, 120 мин с кластерно-"
            "устойчивыми ошибками (кластер по времени решения, все символы) вместо naive t; сравнение с фоном по тем же "
            "часам суток.",
            "3. **Вклад механики выхода.** На тех же входах сравнить исходный выход с чистым time exit, с только стопом, с "
            "только целью (диагностика, не новая стратегия). Показывает, теряется ли край из-за асимметрии -0.6/+0.9.",
            "4. **Задержка и точка входа.** Распределение доходности первой минуты после решения (adverse selection на "
            "next-open) и разница open против VWAP первой минуты.",
            "5. **Реальные издержки.** Оценка спреда и проскальзывания по публичным aggTrades/bookTicker на разрешённом хосте, "
            "проверка exchangeInfo и комиссий; пересчёт break-even против измеренных издержек по символам.",
            "6. **Устойчивость по времени.** Помесячная и почасовая (UTC) разбивка gross/net signal-only; концентрация PnL в "
            "отдельных днях; повтор bootstrap с кластеризацией по дням.",
            "7. **Режимы и символы.** Взаимодействие режим x символ x стратегия на signal-only с учётом малых выборок; "
            "проверка, что пороги режима (development median) не смещают validation.",
            "8. **Перекрытие сигналов.** Корреляция сигналов между символами в одну и ту же 5m свечу (эффективный размер "
            "выборки), влияние приоритета BTC > ETH > SOL на отклонённые сигналы.",
            "9. **Влияние лимитов.** Время до общего стопа и путь equity: сколько отрицательного результата основного "
            "сценария создаётся первыми N днями; сравнение с B03 до момента стопа.",
            "10. **Чувствительность к допущениям движка.** Signal-only при 0/10/40 bps (сейчас отсутствует), "
            "внутрибаровая проверка лимитов по минимумам, комиссия в базовом активе.",
            "11. **Сверка B01 через Freqtrade** и повтор validation-сверки Freqtrade на чистом клоне для полноты.",
            ""]


def s12() -> list[str]:
    return ["## 12. Отсутствующие показатели", "",
            "* B02: gross, slippage, win rate, PF, expectancy, turnover не вычислялись (одна сделка).",
            "* B03: turnover, exposure, Sharpe/Sortino, разбивка по активам не сохранялись (только сводка по сидам).",
            "* По активам: max DD, turnover, exposure, Sharpe (общий кошелёк).",
            "* Signal-only при 0/10/40 bps и delay/step-сценариях не прогонялся.",
            "* Доверительные интервалы для Sharpe/Sortino, PF и win rate не вычислялись.",
            "* Freqtrade: B01 не сверялся; validation-сверка не повторялась при воспроизведении 2026-11-25.",
            "* Holdout (test) не запускался: результаты на test отсутствуют намеренно.",
            "* Docker-сборка и dry-run не выполнялись.",
            "", "## 13. Состав пакета", "",
            "Архив `ai-trading-lab-mvp-v0.1.zip` (создан `git archive` из тега `mvp-v0.1`): исходный код `src/`, тесты "
            "`tests/`, конфигурации `configs/`, стратегии и конфиги Freqtrade `user_data/`, документация (`README.md`, "
            "`CLAUDE.md`, `DECISIONS.md`, `STRATEGY_REGISTRY.md`, `EXPERIMENT_LOG.md`, `PROJECT_STATE.md`, этот файл), "
            "отчёты `reports/` (включая все прогоны development/validation и сверку с Freqtrade), `requirements.lock`, "
            "`Dockerfile`, генератор `audit/`. Не включены: архивы котировок и обработанные данные (`data/`, "
            "`user_data/data`), результаты Freqtrade-бэктестов (`user_data/backtest_results`), виртуальные окружения, "
            "parquet-артефакты прогонов, ключи и секреты (в проекте не используются).", "",
            "Воспроизведение: `README.md` (download, validate-data, pytest, test-signals, backtest, summary, Freqtrade). "
            "Ожидаемый результат: файлы из таблицы `outputs_sha256` в разделе 10.4 совпадают побайтно.", ""]


def main():
    L = []
    for part in (s_header, s1_2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12):
        L += part()
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT} ({len(L)} lines)")


if __name__ == "__main__":
    main()
