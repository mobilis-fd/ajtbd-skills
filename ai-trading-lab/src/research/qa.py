"""Data-QA markdown (integrity and coverage only; no price/return statistics)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path


def write_data_qa_md(cfg: dict, qa: dict, path: Path) -> None:
    L = ["# MH-v0.2 data QA", "", f"Generated {qa['created_utc']}; data horizon end `{qa['horizon_end']}` (exclusive). "
         "Integrity/coverage only.", "",
         f"Archives in manifest: {qa['archives']['total']}, SHA256 ok: {qa['archives']['ok']}, not ok: "
         f"{qa['archives']['not_ok'] or 'none'}. Raw zip files are stored read-only.", "",
         "## Coverage and integrity per symbol", "",
         "| symbol | first 1m open | rows | missing min | gaps | dup open_time | OHLC viol | taker>vol | "
         "takerQ>quoteVol | neg vol | bad close_time | trades=0 & vol>0 | trades>0 & vol=0 | zero-vol rows | units | "
         "dropped rows |", "|" + "---|" * 16]
    for sym, q in qa["symbols"].items():
        if "checks" not in q:
            L.append(f"| {sym} | NO DATA |" + " |" * 15)
            continue
        c = q["checks"]
        dropped = sum(v for k, v in q["clean_log"].items())
        L.append(f"| {sym} | {q['first_open_time']} | {c['rows_in_range']} | {c['missing_minutes']} | {q['n_gaps']} | "
                 f"{c['duplicate_open_time']} | {c['ohlc_invariant_violations']} | {c['taker_gt_total']} | "
                 f"{c['taker_quote_gt_quote_volume']} | {c['negative_volume']} | {c['bad_close_time']} | "
                 f"{c['trades_zero_volume_positive']} | {c['trades_positive_volume_zero']} | {c['zero_volume_rows']} | "
                 f"{c['ts_units']} | {dropped} |")
    units = Counter()
    for v in qa["files"].values():
        for u in v.get("ts_units", {}):
            units[u] += 1
    L += ["", f"Per-file timestamp units (files containing unit): {dict(units)}.", "",
          "## Gaps (>= 1 missing minute), all symbols", ""]
    for sym, q in qa["symbols"].items():
        g = q.get("gaps", [])
        big = sorted(g, key=lambda x: -x["minutes"])[:15]
        L.append(f"- **{sym}**: {len(g)} gaps, {sum(x['minutes'] for x in g)} minutes. Largest: " +
                 "; ".join(f"{x['start']} ({x['minutes']} min)" for x in big))
    L += ["", "Gaps are never filled; affected bars/features/labels are missing (no signal / invalid observation)."]
    path.write_text("\n".join(L))
