"""Recorder CLI. `smoke` connects to public Binance endpoints and therefore requires explicit authorization:
it is NOT run by this project's agents; run it on your own machine after agreeing runtime and scope."""
from __future__ import annotations

import argparse
import asyncio
import json
import resource
import sys
import time
from pathlib import Path

import yaml

from src.config import ROOT

DEFAULT = ROOT / "configs" / "collector_v01.yaml"


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.collector.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke")
    s.add_argument("--duration", type=int, default=900)
    s.add_argument("--config", default=str(DEFAULT))
    s.add_argument("--out", default=str(ROOT / "data" / "recorder"))
    s.add_argument("--i-am-authorized", action="store_true",
                   help="confirm the owner approved this runtime/scope (public data only)")
    a = p.parse_args(argv)
    if not a.i_am_authorized:
        print("REFUSED: recorder runs need explicit owner authorization (--i-am-authorized). Nothing was started.")
        return 6
    if a.duration > 24 * 3600:
        print("REFUSED: duration above the 24 h pilot limit"); return 6
    cfg = yaml.safe_load(open(a.config))
    from src.collector.service import Recorder
    rec = Recorder(cfg, Path(a.out))
    t0, c0 = time.time(), resource.getrusage(resource.RUSAGE_SELF)
    stats = asyncio.run(rec.run(a.duration))
    c1 = resource.getrusage(resource.RUSAGE_SELF)
    el = time.time() - t0
    stats.update(elapsed_s=el, rows_per_s=stats["rows_written"] / el if el else None,
                 bytes_on_disk=rec.w.used_bytes(), cpu_s=c1.ru_utime + c1.ru_stime - c0.ru_utime - c0.ru_stime,
                 max_rss_mb=c1.ru_maxrss / 1024,
                 bytes_per_day_extrapolated=rec.w.used_bytes() / el * 86400 if el else None)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "smoke_report.json").write_text(json.dumps(stats, indent=2, default=str))
    print(json.dumps(stats, indent=2, default=str))
    return 0 if not stats["errors"] else 7


if __name__ == "__main__":
    sys.exit(main())
