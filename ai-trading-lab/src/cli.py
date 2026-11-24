"""Command line interface: python -m src.cli <command> [--config configs/mvp.yaml]."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from src.config import ROOT, code_hash, dumps, load_config

HOLDOUT_MARKER = ROOT / "reports" / "HOLDOUT_USED.json"


def cmd_download(cfg, args):
    from src.data.download import download_all
    m = download_all(cfg, force=args.force)
    bad = [f for f in m["files"] if f.get("status") != "ok"]
    print(f"{len(m['files'])} archives in manifest, {len(bad)} not ok")
    return 1 if bad else 0


def cmd_validate(cfg, args):
    from src.data.store import build_processed
    from src.data.validate import check_1m
    from src.data.store import load
    from src.config import split_bounds
    qa = build_processed(cfg)
    # integrity-only checks per split on cleaned data (no price/return statistics)
    for sym in cfg["data"]["symbols"]:
        qa["symbols"][sym]["per_split_clean"] = {}
        for sp in cfg["splits"]:
            s, e = split_bounds(cfg, sp)
            d = load(cfg, sym, "1m", s, e)
            r = check_1m(d, s, e)
            qa["symbols"][sym]["per_split_clean"][sp] = {k: r[k] for k in (
                "rows_in_range", "missing_minutes", "completeness", "duplicate_open_time", "ohlc_invariant_violations",
                "taker_gt_total", "negative_volume", "zero_volume_rows", "gaps")}
            m5 = load(cfg, sym, "5m", s, e)
            exp5 = int((e - s).total_seconds() // 300)
            qa["symbols"][sym]["per_split_clean"][sp]["candles_5m"] = int(len(m5))
            qa["symbols"][sym]["per_split_clean"][sp]["missing_5m"] = exp5 - int(len(m5))
    manifest = json.loads((ROOT / cfg["data"]["manifest"]).read_text())
    qa["archives"] = {"total": len(manifest["files"]),
                      "checksum_verified": sum(1 for f in manifest["files"] if f.get("checksum_verified")),
                      "not_ok": [f["file"] for f in manifest["files"] if f.get("status") != "ok"]}
    qa["created_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    (ROOT / "data" / "qa.json").write_text(dumps(qa))
    _write_data_qa_md(qa)
    hard = 0
    for sym, q in qa["symbols"].items():
        r = q["raw_checks"]
        hard += r["ohlc_invariant_violations"] + r["taker_gt_total"] + r["negative_volume"] + r["bad_close_time"]
    print(f"archives: {qa['archives']['checksum_verified']}/{qa['archives']['total']} checksum-verified")
    for sym, q in qa["symbols"].items():
        r = q["raw_checks"]
        print(f"{sym}: rows={r['rows_in_range']} missing_min={r['missing_minutes']} dup={r['duplicate_open_time']} "
              f"ohlc_viol={r['ohlc_invariant_violations']} taker>total={r['taker_gt_total']} units={r['ts_units']} "
              f"gaps={len(r['gaps'])}")
    print("wrote data/qa.json and reports/data_qa.md")
    return 0 if hard == 0 else 2


def _write_data_qa_md(qa):
    L = ["# Data QA", "", f"Generated {qa['created_utc']}. Integrity checks only (no price or return statistics, "
         "so the locked test period is not inspected for performance).", "",
         f"Archives: {qa['archives']['checksum_verified']}/{qa['archives']['total']} SHA256-verified against "
         f"Binance .CHECKSUM files. Not ok: {qa['archives']['not_ok'] or 'none'}.", ""]
    for sym, q in qa["symbols"].items():
        r = q["raw_checks"]
        L += [f"## {sym}", "", f"- raw rows in [warmup start, end): {r['rows_in_range']} of {r['expected_minutes']} "
              f"expected minutes; missing {r['missing_minutes']}; timestamp units {r['ts_units']}",
              f"- duplicates (open_time) {r['duplicate_open_time']}, full-row duplicates {r['duplicate_full_rows']}, "
              f"non-monotonic {r['non_monotonic_steps']}, not minute-aligned {r['not_minute_aligned']}, "
              f"bad close_time {r['bad_close_time']}",
              f"- OHLC invariant violations {r['ohlc_invariant_violations']}, non-positive price {r['nonpositive_price']}, "
              f"negative volume {r['negative_volume']}, taker>total {r['taker_gt_total']}, zero-volume minutes "
              f"{r['zero_volume_rows']}",
              f"- cleaning: {q['clean_log']}",
              f"- gaps (raw): {r['gaps'] if r['gaps'] else 'none'}", ""]
        L.append("| split | 1m rows | missing 1m | completeness | 5m candles | missing 5m | zero-vol 1m |")
        L.append("|---|---|---|---|---|---|---|")
        for sp, c in q["per_split_clean"].items():
            L.append(f"| {sp} | {c['rows_in_range']} | {c['missing_minutes']} | {c['completeness']:.6f} | "
                     f"{c['candles_5m']} | {c['missing_5m']} | {c['zero_volume_rows']} |")
        L.append("")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "data_qa.md").write_text("\n".join(L))


def cmd_test_signals(cfg, args):
    from src.signals.prefix_check import run_prefix_checks
    res = run_prefix_checks(cfg, n_cuts=args.cuts)
    out = ROOT / "reports" / "signal_prefix_check.json"
    out.write_text(dumps(res))
    print(dumps({k: v for k, v in res.items() if k != "details"}))
    return 0 if res["ok"] else 3


def cmd_backtest(cfg, args):
    if args.split == "test":
        print("REFUSED: the locked test split can only be run through `holdout --approval-file`.")
        return 4
    if HOLDOUT_MARKER.exists():
        print("NOTE: holdout has been used; development/validation runs are diagnostics only.")
    from src.evaluation.pipeline import run_split
    out = run_split(cfg, args.split, smoke_days=args.smoke_days, n_seeds=args.seeds)
    print(f"run directory: {out.relative_to(ROOT)}")
    print((out / "report.md").read_text()[:4000])
    return 0


def cmd_report(cfg, args):
    runs = sorted((ROOT / "reports" / "runs").glob(f"{args.split}_*"), key=lambda p: p.stat().st_mtime)
    runs = [r for r in runs if "smoke" not in r.name]
    if not runs:
        print(f"no runs for split {args.split}; run `backtest --split {args.split}` first")
        return 1
    print(f"latest run: {runs[-1].relative_to(ROOT)}\n")
    print((runs[-1] / "report.md").read_text())
    return 0


def verify_approval(cfg, path: Path) -> tuple[bool, str]:
    if not path or not Path(path).exists():
        return False, "approval file missing"
    try:
        a = json.loads(Path(path).read_text())
    except Exception as e:
        return False, f"approval file unreadable: {e}"
    need = {"approved_by", "approved_utc", "code_sha256", "config_sha256", "statement"}
    if not need.issubset(a):
        return False, f"approval file must contain {sorted(need)}"
    if a["statement"] != "I approve a single run of the locked test split for experiment " + cfg["experiment_id"]:
        return False, "statement text does not match"
    if a["code_sha256"] != code_hash():
        return False, "code hash differs from approved hash"
    if a["config_sha256"] != cfg["_hash"]:
        return False, "config hash differs from approved hash"
    if HOLDOUT_MARKER.exists():
        return False, "holdout already used; a new test needs later data"
    return True, "ok"


def cmd_holdout(cfg, args):
    ok, why = verify_approval(cfg, Path(args.approval_file) if args.approval_file else None)
    if not ok:
        print(f"REFUSED: {why}")
        print(f"current code_sha256={code_hash()} config_sha256={cfg['_hash']}")
        return 5
    HOLDOUT_MARKER.write_text(dumps({"used_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                                     "approval_file": str(args.approval_file), "code_sha256": code_hash(),
                                     "config_sha256": cfg["_hash"]}))
    from src.evaluation.pipeline import run_split
    out = run_split(cfg, "test", unlocked=True)
    print(f"holdout run directory: {out}")
    return 0


def cmd_summary(cfg, args):
    from src.evaluation.report import write_summary
    dirs = {}
    for sp in ("development", "validation"):
        runs = [r for r in sorted((ROOT / "reports" / "runs").glob(f"{sp}_*"), key=lambda p: p.stat().st_mtime)
                if "smoke" not in r.name]
        if runs:
            dirs[sp] = runs[-1]
    print(write_summary(dirs, ROOT / "reports" / "SUMMARY_development_validation.md"))
    return 0


def cmd_ft_export(cfg, args):
    from src.ftbridge.export import export_freqtrade_data
    print(export_freqtrade_data(cfg))
    return 0


def cmd_ft_compare(cfg, args):
    from src.ftbridge.compare import compare
    res = compare(cfg, args.split, Path(args.ft_dir))
    print(dumps(res["summary"]))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cli")
    p.add_argument("--config", default=str(ROOT / "configs" / "mvp.yaml"))
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download"); d.add_argument("--force", action="store_true")
    sub.add_parser("validate-data")
    t = sub.add_parser("test-signals"); t.add_argument("--cuts", type=int, default=25)
    b = sub.add_parser("backtest"); b.add_argument("--split", required=True, choices=["development", "validation", "test"])
    b.add_argument("--smoke-days", type=int, default=None); b.add_argument("--seeds", type=int, default=None)
    r = sub.add_parser("report"); r.add_argument("--split", required=True, choices=["development", "validation"])
    h = sub.add_parser("holdout"); h.add_argument("--approval-file", default=None)
    sub.add_parser("ft-export")
    sub.add_parser("summary")
    c = sub.add_parser("ft-compare"); c.add_argument("--split", required=True, choices=["development", "validation"])
    c.add_argument("--ft-dir", required=True)
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    fn = {"download": cmd_download, "validate-data": cmd_validate, "test-signals": cmd_test_signals,
          "backtest": cmd_backtest, "report": cmd_report, "holdout": cmd_holdout, "ft-export": cmd_ft_export,
          "ft-compare": cmd_ft_compare, "summary": cmd_summary}[args.cmd]
    return fn(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
