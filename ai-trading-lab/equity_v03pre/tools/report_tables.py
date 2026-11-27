"""Render markdown tables for EQUITY_SCREENING_REPORT.md from summary.json files (no recomputation of results,
except the clearly labelled post-hoc descriptive diagnostics from events_exploratory.csv).

Usage: python -I report_tables.py REPORTS_DIR > tables.md
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

R = Path(sys.argv[1])
P = json.loads((R / 'run01_primary' / 'summary.json').read_text())['results']
S = {(r['period'], r['hypothesis']): r for r in json.loads((R / 'run02_S1' / 'summary.json').read_text())['results']}
f = lambda v, n=1: '—' if v is None else f'{v:.{n}f}'
ci = lambda c: '—' if c[0] is None else f'[{c[0]:.1f}; {c[1]:.1f}]'


def verdict(r):
    s = S[(r['period'], r['hypothesis'])]
    if r['delta_bps'] <= 0 or r['gross_bps'] <= 0 or r['net_10bps'] <= 0:
        return 'Не подтверждена'
    stat = (r['delta_bps'] >= 10 and r['delta_ci_6m'][0] is not None and r['delta_ci_6m'][0] > 0
            and r['holm_p_6m'] < 0.05 and s['delta_bps'] > 0)
    if stat and r['period'] == 'T3':
        return 'Неопределённо (статистика проходит; цены T3 без второго источника)'
    return 'Кандидат на продолжение' if stat else 'Неопределённо'


out = []
o = out.append
o('### Таблица 1. Основной прогон (run01_primary): доходности, контроль, издержки\n')
o('Все величины в б.п. на событие (средние по месяцам). delta = событие − контроль (gross). net_X = событие после X б.п. на круг.\n')
o('| Период | Гипотеза | N | Gross | Контроль | Delta | Доля мес. gross>0 | Break-even, б.п. RT | net 0 | net 5 | net 10 | net 25 | net 40 | delta net 10 |')
o('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for r in P:
    o(f"| {r['period']} | {r['hypothesis']} | {r['months']} | {f(r['gross_bps'])} | {f(r['control_bps'])} | {f(r['delta_bps'])} | "
      f"{r['positive_month_fraction']:.2f} | {f(r['break_even_rt_bps'])} | {f(r['net_0bps'])} | {f(r['net_5bps'])} | {f(r['net_10bps'])} | "
      f"{f(r['net_25bps'])} | {f(r['net_40bps'])} | {f(r['delta_10bps'])} |")
o('\n### Таблица 2. Интервалы и p-значения для delta (основной прогон)\n')
o('Циркулярный блочный бутстрэп по месяцам, 4000 повторов; 95% процентильный интервал; p односторонний (H1: delta > 0). Holm — по 9 ячейкам, блок 6 мес.\n')
o('| Период | Гипотеза | ДИ 3 мес | p 3 | ДИ 6 мес (основной) | p 6 | ДИ 12 мес | p 12 | Holm p 6 | Вердикт по правилу PROTOCOL §4 |')
o('|---|---|---|---|---|---|---|---|---|---|')
for r in P:
    o(f"| {r['period']} | {r['hypothesis']} | {ci(r['delta_ci_3m'])} | {f(r['p_3m'],3)} | {ci(r['delta_ci_6m'])} | {f(r['p_6m'],3)} | "
      f"{ci(r['delta_ci_12m'])} | {f(r['p_12m'],3)} | {f(r['holm_p_6m'],3)} | {verdict(r)} |")
o('\n### Таблица 3. Чувствительность S1 (исправленные данные) против основного прогона\n')
o('| Период | Гипотеза | Gross осн. / S1 | Delta осн. / S1 | ДИ 6 мес S1 | Holm p 6 S1 |')
o('|---|---|---|---|---|---|')
for r in P:
    s = S[(r['period'], r['hypothesis'])]
    o(f"| {r['period']} | {r['hypothesis']} | {f(r['gross_bps'],2)} / {f(s['gross_bps'],2)} | {f(r['delta_bps'],2)} / {f(s['delta_bps'],2)} | {ci(s['delta_ci_6m'])} | {f(s['holm_p_6m'],3)} |")
# post-hoc descriptive
e = pd.read_csv(R / 'run01_primary' / 'events_exploratory.csv', parse_dates=['entry', 'exit'])
PER = {'T3': ('2003-01-01', '2016-12-31'), 'T2': ('2017-10-01', '2024-04-30'), 'T1': ('2024-06-01', '2026-10-31')}
o('\n### Таблица 4. Описательная диагностика (post-hoc, не входит в правило решения)\n')
o('Вычислена после просмотра результатов одинаково для всех 9 ячеек; ничего не отбирает и не меняет вердикт.\n')
o('| Период | Гипотеза | Медиана delta | Delta без 3 лучших мес. | Доля мес. delta>0 | СКО delta | 3 лучших месяца (вход, б.п.) | EQ01: выбор SPY/IEF |')
o('|---|---|---|---|---|---|---|---|')
for p, (a, b) in PER.items():
    for h in ['EQ01', 'EQ02', 'EQ03']:
        x = e[(e.entry >= a) & (e.exit <= b) & (e.hypothesis == h)]
        d = (x.gross - x.control) * 1e4; t = d.sort_values(ascending=False)
        top = ', '.join(f"{x.loc[i, 'entry'].date()} ({t[i]:.0f})" for i in t.index[:3])
        pick = '' if h != 'EQ01' else f"{(x.symbol == 'SPY').sum()}/{(x.symbol == 'IEF').sum()}"
        o(f'| {p} | {h} | {d.median():.1f} | {t.iloc[3:].mean():.1f} | {(d > 0).mean():.2f} | {d.std():.1f} | {top} | {pick} |')
ins = np.zeros(len(e), bool)
for a, b in PER.values(): ins |= ((e.entry >= a) & (e.exit <= b)).to_numpy()
o(f'\nСтрок вне сводных периодов (переходные месяцы и события через границу; в сводку не входят): {int((~ins).sum())} из {len(e)}.')
print('\n'.join(out))
