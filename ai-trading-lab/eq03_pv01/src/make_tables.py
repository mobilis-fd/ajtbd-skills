"""Markdown tables for EQ03_PORTFOLIO_REPORT.md from a run directory. Usage: python -I make_tables.py RUN_DIR"""
import json
import sys
from pathlib import Path

import pandas as pd

run = Path(sys.argv[1])
g = pd.read_csv(run / 'scenario_grid.csv')
g['fractional'] = g['fractional'].fillna(False).astype(bool); g['idle_rf'] = g['idle_rf'].fillna(False).astype(bool)
s = json.loads((run / 'summary.json').read_text())
P = ['T3', 'T2', 'T1', 'FULL']
out = []


def md(df):
    cols = list(df.columns)
    lines = ['| ' + ' | '.join(map(str, cols)) + ' |', '|' + '---|' * len(cols)]
    for _, r in df.iterrows():
        lines.append('| ' + ' | '.join(f'{v:.2f}' if isinstance(v, float) else str(v) for v in r) + ' |')
    return '\n'.join(lines)


# 1. base scenario vs controls
rows = []
for p in P:
    for model, sc in [('EQ03', 'bps10_fee0_frac_rf'), ('cash_0', None), ('cash_rf', None),
                      ('BH_TLT_50', 'bps10_fee0_frac_rf'), ('BH_TLT_100_info', 'bps10_fee0_frac_rf_max100')]:
        r = g[(g.period == p) & (g.model == model) & ((g.scenario == sc) if sc else g.scenario.isna())].iloc[0]
        rows.append({'Период': p, 'Модель': model, 'Капитал, $': r.final_equity, 'Net PnL, $': r.net_pnl,
                     'CAGR, %': r.cagr_pct, 'Изб. PnL vs cash_rf, $': r.excess_pnl_vs_cash_rf,
                     'Изб. CAGR vs cash_rf, п.п.': r.excess_cagr_vs_cash_rf_pct, 'MaxDD, %': r.max_drawdown_pct,
                     'Sharpe': r.sharpe_excess_ann if pd.notna(r.sharpe_excess_ann) else float('nan'),
                     'Sortino': r.sortino_excess_ann if pd.notna(r.sortino_excess_ann) else float('nan'),
                     'Эксп., % сессий': r.exposure_sessions_pct, 'Ср. в позиции, %': r.avg_invested_pct_of_equity,
                     'Оборот, x/год': r.turnover_x_per_year, 'Сделок': int(r.trades)})
out.append('## T1. Базовый сценарий против контролей\n\n' + md(pd.DataFrame(rows)))

# 2. cost grid: excess PnL vs cash_rf, fractional, idle rf
for p in P:
    sub = g[(g.period == p) & (g.model == 'EQ03') & (g.fractional) & (g.idle_rf)]
    t = sub.pivot_table(index='fee', columns='bps_rt', values='excess_pnl_vs_cash_rf')
    t.columns = [f'{c:g} б.п.' for c in t.columns]
    t.insert(0, 'Комиссия, $/поручение', [f'{i:g}' for i in t.index])
    out.append(f'## T2-{p}. Избыточный PnL против cash_rf, $ (дробные доли, кэш под ^IRX)\n\n' + md(t.reset_index(drop=True)))

# 3. idle cash at 0: Net PnL vs cash_0 (= Net PnL)
rows = []
for p in P:
    for bps in [0, 5, 10, 25, 40]:
        r = g[(g.period == p) & (g.model == 'EQ03') & (g.fractional) & (~g.idle_rf) & (g.fee == 0) & (g.bps_rt == bps)].iloc[0]
        rows.append({'Период': p, 'б.п.': bps, 'Net PnL, $ (кэш без %)': r.net_pnl, 'CAGR, %': r.cagr_pct, 'MaxDD, %': r.max_drawdown_pct})
out.append('## T3. Кэш без процентов, $0 комиссия, дробные доли\n\n' + md(pd.DataFrame(rows)))

# 4. whole shares
w = g[(g.model == 'EQ03') & (~g.fractional) & (g.fee == 0) & (g.bps_rt == 10) & (g.idle_rf)]
w = w[['period', 'trades', 'skipped_entries', 'net_pnl']].rename(columns={'period': 'Период', 'trades': 'Сделок',
      'skipped_entries': 'Пропущено (меньше 1 акции)', 'net_pnl': 'Net PnL, $'})
w['Диапазон open TLT, $'] = [f"{s['tlt_price_range'][p][0]:.2f}–{s['tlt_price_range'][p][1]:.2f}" for p in w['Период']]
out.append('## T4. Только целые акции (лимит $50)\n\n' + md(w))

# 5. tests
rows = []
for p in P:
    t = s['primary_test'][p]
    row = {'Период': p, 'Месяцев': t['months'], 'Среднее, б.п./мес': t['mean_bps_per_month'], 'СКО': t['sd_bps'],
           'Доля мес. > 0': t['share_positive_months'], 'AC(1)': t['lag1_autocorr']}
    m4 = t['M4_cbb_studentized_b6']
    row['M4 p'] = m4['p_one_sided']; row['M4 95% ДИ'] = f"[{m4['ci95'][0]:.1f}; {m4['ci95'][1]:.1f}]"
    row['Holm p (M4)'] = t.get('holm_p_primary', float('nan'))
    for k in ['M1_t_iid', 'M2_newey_west', 'M3_cbb_percentile_b6']:
        row[k.split('_')[0] + ' p'] = t[k]['p_one_sided']
    rows.append(row)
out.append('## T5. Основной тест (месячная избыточная доходность против cash_rf, сценарий B)\n\n' + md(pd.DataFrame(rows)))

# 6. random windows
rows = [{'Период': p, 'Правило, $': v['strategy_final'], 'Случ.: среднее': v['random_mean_final'], 'p05': v['random_p05'],
         'p50': v['random_p50'], 'p95': v['random_p95'], 'Перцентиль правила': v['strategy_percentile'],
         'Случ.: изб. PnL vs cash_rf': v['random_mean_excess_vs_cash_rf']} for p, v in s['random_windows'].items()]
out.append('## T6. Случайные пятисессионные окна (1000 симуляций, сценарий B)\n\n' + md(pd.DataFrame(rows)))

# 7. worst months
rows = []
for p in ['T3', 'T2', 'T1']:
    for model in ['EQ03', 'BH_TLT_50']:
        wm = s['worst_months_base'].get(f'{p}|{model}')
        rows.append({'Период': p, 'Модель': model, 'Худшие месяцы (% капитала)': '; '.join(f'{a}: {b:.2f}' for a, b in wm)})
out.append('## T7. Худшие месяцы (сценарий B)\n\n' + md(pd.DataFrame(rows)))

# 8. sensitivities
sens = pd.DataFrame(s['sensitivities'])
base = g[(g.model == 'EQ03') & (g.scenario == 'bps10_fee0_frac_rf')].set_index('period').excess_pnl_vs_cash_rf
t = sens.pivot_table(index='sensitivity', columns='period', values='excess_pnl_vs_cash_rf')[P]
t.loc['base'] = base[P]
t.insert(0, 'Вариант', t.index)
out.append('## T8. Чувствительности: избыточный PnL против cash_rf, $\n\n' + md(t.reset_index(drop=True)))

# 9. break-even fixed fee
rows = []
for p in P:
    r = g[(g.period == p) & (g.model == 'EQ03') & (g.scenario == 'bps10_fee0_frac_rf')].iloc[0]
    rows.append({'Период': p, 'Изб. PnL при $0, $': r.excess_pnl_vs_cash_rf, 'Поручений': 2 * int(r.trades),
                 'Безубыточная комиссия, $/поручение (≈)': r.excess_pnl_vs_cash_rf / (2 * r.trades),
                 'Изб. PnL в год, $': r.excess_pnl_vs_cash_rf / r.years})
out.append('## T9. Безубыточная фиксированная комиссия (сценарий B, ≈ изб. PnL / число поручений)\n\n' + md(pd.DataFrame(rows)))

(run / 'tables.md').write_text('\n\n'.join(out) + '\n')
print('\n\n'.join(out))
