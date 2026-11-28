"""Render reports/run01/summary.json into markdown tables (tables.md). No new computation."""
import json
import sys
from pathlib import Path

s = json.loads(Path(sys.argv[1]).read_text())
P = ['ALL', 'P1_2002_2009', 'P2_2010_2019', 'P3_2020_2026']
f = lambda v, d=1: '—' if v is None else f'{v:+.{d}f}'  # noqa: E731
pp = lambda v: '—' if v is None else f'{v:.3f}'  # noqa: E731
out = []
for var in ('primary', 'S1'):
    for h in (5, 3, 1):
        k = f'{var}_h{h}'
        tag = 'ОСНОВНОЙ' if (var, h) == ('primary', 5) else 'диагностика'
        out.append(f'\n### {var}, h = {h} ({tag})\n')
        out.append('| период | n | D, б.п. | 95% ДИ | p (M4) | доля D>0 | событие брутто | контроль брутто |')
        out.append('|---|---|---|---|---|---|---|---|')
        for p in P:
            c = s[k][p]; d = c['primary_d_gross']; e = c['cost_0']['event_net']
            out.append(f"| {p} | {d['n']} | {f(d['mean_bps'])} | [{f(d['ci_lo_bps'])}; {f(d['ci_hi_bps'])}] | {pp(d['p'])} | "
                       f"{d.get('hit_rate', 0):.2f} | {f(e['mean_bps'])} | {f(c['cost_0']['control_net_mean_bps'])} |")
k = 'primary_h5'
out.append('\n### Издержки и cash, h = 5, основные данные (средние, б.п. на событие)\n')
out.append('| период | издержки | событие нетто | p (нетто>0) | избыток над cash | p (избыток>0) | контроль нетто | D нетто |')
out.append('|---|---|---|---|---|---|---|---|')
for p in P:
    for c in s['costs_bps']:
        z = s[k][p][f'cost_{c}']
        out.append(f"| {p} | {c} | {f(z['event_net']['mean_bps'])} | {pp(z['event_net']['p'])} | {f(z['event_excess_cash']['mean_bps'])} | "
                   f"{pp(z['event_excess_cash']['p'])} | {f(z['control_net_mean_bps'])} | {f(z['delta_net']['mean_bps'])} |")
out.append('\n### Проверки и диагностика (h = 5, D брутто)\n')
out.append('| проверка | n | D, б.п. | 95% ДИ | p (M4) |')
out.append('|---|---|---|---|---|')
for name, v in s['diagnostics'].items():
    if isinstance(v, dict) and 'mean_bps' in v:
        out.append(f"| {name} | {v['n']} | {f(v['mean_bps'])} | [{f(v.get('ci_lo_bps'))}; {f(v.get('ci_hi_bps'))}] | {pp(v.get('p'))} |")
d = s['diagnostics']
out.append('\nПрочее: ' + json.dumps({k: d[k] for k in d if not (isinstance(d[k], dict) and 'mean_bps' in d[k])}, ensure_ascii=False, default=str))
out.append('\nВердикт: ' + json.dumps(s['verdict'], ensure_ascii=False))
Path(sys.argv[2]).write_text('\n'.join(out) + '\n')
print('\n'.join(out))
