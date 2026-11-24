"""v0.2 CLI: python -m src.research.cli <command> [--config configs/multi_horizon_v02.yaml]."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from src.config import ROOT, code_hash, dumps, load_config, ts

DEFAULT = ROOT / "configs" / "multi_horizon_v02.yaml"
USED_MARKER = ROOT / "reports" / "v02" / "HISTORICAL_TEST_USED.json"


def cmd_download(cfg, a):
    from src.research.data import download, months_for_split
    m = download(cfg, months_for_split(cfg, a.split))
    bad = [k for k, v in m["files"].items() if v["status"] != "ok"]
    print(f"{len(m['files'])} archives in manifest, not ok: {bad or 'none'}")
    return 1 if bad else 0


def cmd_validate(cfg, a):
    from src.research.data import build
    end = ts(cfg["splits"][a.split]["end"])
    if cfg["splits"][a.split].get("locked"):
        print("REFUSED: locked split"); return 4
    qa = build(cfg, end)
    man = json.loads((ROOT / cfg["data"]["manifest"]).read_text())
    qa["archives"] = {"total": len(man["files"]), "ok": sum(1 for v in man["files"].values() if v["status"] == "ok"),
                      "not_ok": [k for k, v in man["files"].items() if v["status"] != "ok"]}
    qa["created_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    out = ROOT / "reports" / "v02" / f"data_qa_{a.split}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(qa))
    from src.research.qa import write_data_qa_md
    write_data_qa_md(cfg, qa, ROOT / "reports" / "v02" / f"data_qa_{a.split}.md")
    hard = sum(q["checks"][k] for q in qa["symbols"].values() if "checks" in q for k in
               ("ohlc_invariant_violations", "taker_gt_total", "taker_quote_gt_quote_volume", "negative_volume",
                "bad_close_time", "duplicate_open_time"))
    print(f"wrote {out.relative_to(ROOT)}; hard violations (dropped, reported): {hard}")
    return 0


def cmd_run(cfg, a):
    if cfg["splits"][a.split].get("locked"):
        print("REFUSED: the historical test split is locked; use `historical-test --approval-file`."); return 4
    from src.research.pipeline import run_split
    out = run_split(cfg, a.split, n_seeds=a.seeds, smoke_days=a.smoke_days)
    print(f"run directory: {out.relative_to(ROOT)}")
    return 0


def cmd_report(cfg, a):
    runs = sorted((ROOT / "reports" / "v02" / "runs").glob(f"{a.split}_*"), key=lambda p: p.stat().st_mtime)
    runs = [r for r in runs if "smoke" not in r.name]
    if not runs:
        print("no run"); return 1
    if a.rerender:  # presentation only: rebuild report.md from the run's own metrics.json/manifest.json
        from src.research.report import write_report
        write_report(cfg, runs[-1], json.loads((runs[-1] / "metrics.json").read_text()),
                     json.loads((runs[-1] / "manifest.json").read_text()))
    print(f"{runs[-1].relative_to(ROOT)}\n")
    print((runs[-1] / "report.md").read_text())
    return 0


def cmd_diag_d1(cfg, a):
    if not a.confirmed:
        print("REFUSED: MH-v0.2-D1 is a pre-registered diagnostic that runs only after owner confirmation (--confirmed).")
        return 6
    from src.research.diag_d1 import run_d1
    out = run_d1(cfg, a.split, n_seeds=a.seeds)
    print(f"D1 directory: {out.relative_to(ROOT)}")
    return 0


def verify_approval(cfg, path) -> tuple[bool, str]:
    """Fail-closed. The approval artifact must be written by the project owner, not by any script or agent."""
    if not path or not Path(path).exists():
        return False, "approval artifact missing"
    try:
        a = json.loads(Path(path).read_text())
    except Exception as e:
        return False, f"unreadable: {e}"
    need = {"approved_by", "approved_utc", "code_sha256", "config_sha256", "statement", "written_by_human"}
    if not need.issubset(a):
        return False, f"approval must contain {sorted(need)}"
    if a["written_by_human"] is not True:
        return False, "approval not confirmed as human-written"
    if a["statement"] != f"I approve one run of the MH-v0.2 historical test split 2025-01-01..2025-11-01":
        return False, "statement mismatch"
    if a["code_sha256"] != code_hash() or a["config_sha256"] != cfg["_hash"]:
        return False, "code/config hash differs from the approved hashes"
    if USED_MARKER.exists():
        return False, "historical test already used"
    return False, "historical test data are not downloaded/processed by this version; requires a separate session"


def cmd_hist_test(cfg, a):
    ok, why = verify_approval(cfg, a.approval_file)
    print(f"REFUSED: {why}" if not ok else "approved")
    return 0 if ok else 5


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.research.cli")
    p.add_argument("--config", default=str(DEFAULT))
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download"); d.add_argument("--split", required=True, choices=["development", "validation"])
    v = sub.add_parser("validate-data"); v.add_argument("--split", required=True, choices=["development", "validation"])
    r = sub.add_parser("run"); r.add_argument("--split", required=True, choices=["development", "validation", "test"])
    r.add_argument("--seeds", type=int, default=None); r.add_argument("--smoke-days", type=int, default=None)
    rp = sub.add_parser("report"); rp.add_argument("--split", required=True, choices=["development", "validation"])
    rp.add_argument("--rerender", action="store_true")
    dd = sub.add_parser("diag-d1"); dd.add_argument("--split", required=True, choices=["development", "validation"])
    dd.add_argument("--confirmed", action="store_true"); dd.add_argument("--seeds", type=int, default=None)
    h = sub.add_parser("historical-test"); h.add_argument("--approval-file", default=None)
    a = p.parse_args(argv)
    cfg = load_config(a.config)
    return {"download": cmd_download, "validate-data": cmd_validate, "run": cmd_run, "report": cmd_report,
            "historical-test": cmd_hist_test, "diag-d1": cmd_diag_d1}[a.cmd](cfg, a)


if __name__ == "__main__":
    sys.exit(main())
