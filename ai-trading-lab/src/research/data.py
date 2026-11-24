"""v0.2 data layer: download (SHA256, immutable raw files), per-file QA, 1m store and closed-bar aggregation.

Reuses the audited v0.1 parser/cleaner (src.data.parse.parse_kline_csv, src.data.validate.check_1m/clean_1m).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import stat
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT, dumps, ts
from src.data.parse import parse_kline_csv
from src.data.validate import check_1m, clean_1m

UA = {"User-Agent": "ai-trading-lab/0.2 (research; public data)"}
SUM_COLS = ["volume", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"]


def month_range(first: str, last_exclusive: pd.Timestamp) -> list[str]:
    p = pd.Period(first, "M")
    end = (last_exclusive - pd.Timedelta(microseconds=1)).tz_convert(None).to_period("M")
    return [str(x) for x in pd.period_range(p, end, freq="M")]


def months_for_split(cfg: dict, split: str) -> list[str]:
    if cfg["splits"][split].get("locked"):
        raise PermissionError("locked split: data for it is not downloaded without approval")
    e = ts(cfg["splits"][split]["end"])
    if split == "development":
        return month_range(cfg["data"]["first_month"], e)
    s = ts(cfg["splits"][split]["start"])
    warm = s - pd.Timedelta(days=cfg["fitting"]["train_window_days"] + 28 + 2)
    return month_range(str(warm.tz_convert(None).to_period("M")), e)


def _fetch(url: str, retries: int = 4) -> tuple[bytes, dict]:
    err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read(), {"last_modified": r.headers.get("Last-Modified"), "etag": r.headers.get("ETag")}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            err = e
        except Exception as e:
            err = e
        time.sleep(2 ** i)
    raise RuntimeError(f"download failed {url}: {err}")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _make_readonly(p: Path) -> None:
    os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def download(cfg: dict, months: list[str], symbols: list[str] | None = None) -> dict:
    d = cfg["data"]
    raw = ROOT / d["raw_dir"]
    mpath = ROOT / d["manifest"]
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {"files": {}}
    for sym in symbols or d["info_assets"]:
        for mo in months:
            name = f"{sym}-{d['interval']}-{mo}.zip"
            key = f"{sym}/{name}"
            url = f"{d['base_url']}/monthly/klines/{sym}/{d['interval']}/{name}"
            dest = raw / sym / name
            rec = manifest["files"].get(key, {"symbol": sym, "month": mo, "file": key, "url": url})
            try:
                ck, hdr_ck = _fetch(url + ".CHECKSUM")
                expected = ck.decode().split()[0].lower()
            except urllib.error.HTTPError as e:
                rec.update(status="missing_archive", http_status=e.code)
                manifest["files"][key] = rec
                print(f"MISSING {key} (HTTP {e.code})")
                continue
            if dest.exists() and _sha(dest.read_bytes()) == expected:
                status = "ok"
            else:
                if dest.exists():
                    # source changed or local corruption: never overwrite silently
                    rec.update(status="source_changed_or_corrupt", expected_sha256_now=expected)
                    manifest["files"][key] = rec
                    print(f"CHANGED {key}: local file kept, investigate")
                    continue
                blob, hdr = _fetch(url)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
                _make_readonly(dest)
                rec.update(last_modified=hdr["last_modified"], etag=hdr["etag"],
                           downloaded_utc=dt.datetime.now(dt.timezone.utc).isoformat())
                status = "ok" if _sha(blob) == expected else "checksum_mismatch"
            rec.update(status=status, sha256=_sha(dest.read_bytes()), expected_sha256=expected,
                       bytes=dest.stat().st_size, checksum_file=ck.decode().strip())
            manifest["files"][key] = rec
        print(f"{sym}: {sum(1 for k, v in manifest['files'].items() if v['symbol'] == sym and v['status'] == 'ok')} ok")
    manifest["updated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(dumps(manifest))
    return manifest


# ------------------------------------------------------------------ processing / QA

def _extra_checks(r: pd.DataFrame) -> dict:
    return {
        "taker_quote_gt_quote_volume": int((r["taker_buy_quote"] > r["quote_volume"]).sum()),
        "trades_zero_volume_positive": int(((r["trades"] == 0) & (r["volume"] > 0)).sum()),
        "trades_positive_volume_zero": int(((r["trades"] > 0) & (r["volume"] == 0)).sum()),
        "negative_trades": int((r["trades"] < 0).sum()),
    }


def aggregate_bars(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Closed bars of `minutes` from complete aligned 1m buckets only. Column `T` = bar end (close instant)."""
    d = m1.sort_values("open_time", kind="mergesort")
    bucket = d["open_time"].dt.floor(f"{minutes}min")
    g = d.groupby(bucket, sort=True)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", **{c: "sum" for c in SUM_COLS}}
    out = g.agg(agg)
    out["n_1m"] = g.size()
    out["first"] = g["open_time"].min()
    out.index.name = "open_time"
    out = out.reset_index()
    out = out[(out["n_1m"] == minutes) & (out["first"] == out["open_time"])].drop(columns=["first"])
    out["T"] = out["open_time"] + pd.Timedelta(minutes=minutes)
    out["trades"] = out["trades"].astype("int64")
    return out.reset_index(drop=True)


def processed_path(cfg: dict, sym: str, tf: str) -> Path:
    return ROOT / cfg["data"]["processed_dir"] / f"{sym}_{tf}.parquet"


def build(cfg: dict, horizon_end: pd.Timestamp) -> dict:
    """Parse verified archives (only months < horizon_end), clean, store 1m + bars, per-file and per-symbol QA."""
    d = cfg["data"]
    manifest = json.loads((ROOT / d["manifest"]).read_text())
    test_start = ts(cfg["splits"]["test"]["start"])
    if horizon_end > test_start:
        raise PermissionError("processing beyond the locked test start requires approval")
    qa = {"horizon_end": str(horizon_end), "symbols": {}, "files": {}}
    for sym in d["info_assets"]:
        recs = sorted((v for v in manifest["files"].values() if v["symbol"] == sym), key=lambda v: v["month"])
        parts = []
        for r in recs:
            if pd.Timestamp(r["month"] + "-01", tz="UTC") >= horizon_end:
                continue
            if r["status"] != "ok":
                qa["files"][r["file"]] = {"status": r["status"]}
                continue
            with zipfile.ZipFile(ROOT / d["raw_dir"] / r["file"]) as z:
                names = [n for n in z.namelist() if n.endswith(".csv")]
                p = parse_kline_csv(z.read(names[0]))
            qa["files"][r["file"]] = {"status": "ok", "rows": int(len(p)),
                                      "ts_units": {k: int(v) for k, v in p["ts_unit"].value_counts().items()},
                                      "first_open": str(p["open_time"].min()), "last_open": str(p["open_time"].max())}
            parts.append(p)
        if not parts:
            qa["symbols"][sym] = {"status": "no_data"}
            continue
        raw = pd.concat(parts, ignore_index=True)
        raw = raw[raw["open_time"] < horizon_end]
        first = raw["open_time"].min().floor("min")
        chk = check_1m(raw, first, horizon_end)
        chk.update(_extra_checks(raw))
        clean, log = clean_1m(raw)
        bad_q = clean["taker_buy_quote"] > clean["quote_volume"]
        clean = clean[~bad_q].reset_index(drop=True)
        log["taker_quote_rows_dropped"] = int(bad_q.sum())
        out = processed_path(cfg, sym, "1m")
        out.parent.mkdir(parents=True, exist_ok=True)
        clean.to_parquet(out, index=False)
        bars = {}
        for m in d["bar_sizes_min"]:
            b = aggregate_bars(clean, m)
            b.to_parquet(processed_path(cfg, sym, f"{m}m"), index=False)
            bars[f"{m}m"] = int(len(b))
        gaps = chk.pop("gaps")
        qa["symbols"][sym] = {"first_open_time": str(first), "checks": chk, "clean_log": log, "bars": bars,
                              "n_gaps": len(gaps), "gaps": gaps,
                              "processed_1m_sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
        print(f"{sym}: first {first}, rows {chk['rows_in_range']}, missing {chk['missing_minutes']} in {len(gaps)} gaps")
    return qa


def load_1m(cfg: dict, sym: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    d = pd.read_parquet(processed_path(cfg, sym, "1m"), filters=[("open_time", ">=", start), ("open_time", "<", end)])
    return d.sort_values("open_time").reset_index(drop=True)


def load_bars(cfg: dict, sym: str, minutes: int, end: pd.Timestamp) -> pd.DataFrame:
    """Bars with T <= end (closed by `end`)."""
    d = pd.read_parquet(processed_path(cfg, sym, f"{minutes}m"))
    return d[d["T"] <= end].sort_values("T").reset_index(drop=True)
