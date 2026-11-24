"""Download monthly Binance spot 1m kline archives from data.binance.vision and verify SHA256 (.CHECKSUM)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import urllib.request

import pandas as pd

from src.config import ROOT, dumps, ts

UA = {"User-Agent": "ai-trading-lab/0.1 (research; public data)"}


def months_needed(start: pd.Timestamp, end: pd.Timestamp, warmup_days: int) -> list[str]:
    """Months covering [start - warmup, end) as 'YYYY-MM'."""
    first = (start - pd.Timedelta(days=warmup_days))
    last = end - pd.Timedelta(microseconds=1)
    out, y, m = [], first.year, first.month
    while (y, m) <= (last.year, last.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _get(url: str, retries: int = 4, timeout: int = 60) -> bytes:
    err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # network hiccup: retry with backoff
            err = e
            time.sleep(2 ** i)
    raise RuntimeError(f"failed to download {url}: {err}")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def download_all(cfg: dict, force: bool = False) -> dict:
    dc = cfg["data"]
    base = dc["base_url"].rstrip("/")
    interval = dc["interval"]
    raw_dir = ROOT / dc["raw_dir"]
    months = months_needed(ts(dc["start"]), ts(dc["end"]), dc["warmup_days"])
    files = []
    for sym in dc["symbols"]:
        d = raw_dir / sym
        d.mkdir(parents=True, exist_ok=True)
        for mo in months:
            name = f"{sym}-{interval}-{mo}.zip"
            url = f"{base}/monthly/klines/{sym}/{interval}/{name}"
            path, ck_path = d / name, d / (name + ".CHECKSUM")
            rec = {"symbol": sym, "month": mo, "file": f"{sym}/{name}", "url": url}
            try:
                if force or not ck_path.exists():
                    ck_path.write_bytes(_get(url + ".CHECKSUM"))
                expected = ck_path.read_text().split()[0].strip().lower()
                if force or not path.exists() or _sha256(path.read_bytes()) != expected:
                    path.write_bytes(_get(url))
                data = path.read_bytes()
                actual = _sha256(data)
                ok = actual == expected
                rec.update({"sha256": actual, "expected_sha256": expected, "bytes": len(data),
                            "checksum_verified": ok, "status": "ok" if ok else "checksum_mismatch"})
            except Exception as e:
                rec.update({"checksum_verified": False, "status": f"error: {e}"})
            print(f"{rec['file']}: {rec['status']}", flush=True)
            files.append(rec)
    manifest = {"source": dc["source"], "base_url": base, "interval": interval, "months": months,
                "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "files": files}
    mp = ROOT / dc["manifest"]
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(dumps(manifest))
    return manifest
