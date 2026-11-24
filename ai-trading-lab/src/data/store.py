"""Processed parquet store with time-bounded loaders. The locked test split is gated (DECISIONS D22)."""
from __future__ import annotations

import json
import zipfile

import pandas as pd

from src.config import ROOT, split_bounds, ts
from src.data.aggregate import aggregate_5m
from src.data.parse import parse_kline_csv
from src.data.validate import check_1m, clean_1m


def _path(cfg: dict, symbol: str, tf: str):
    return ROOT / cfg["data"]["processed_dir"] / f"{symbol}_{tf}.parquet"


def _read_raw(cfg: dict, symbol: str) -> pd.DataFrame:
    manifest = json.loads((ROOT / cfg["data"]["manifest"]).read_text())
    parts = []
    for f in sorted(manifest["files"], key=lambda r: r["file"]):
        if f.get("symbol") != symbol:
            continue
        if f.get("status") != "ok":
            raise RuntimeError(f"archive not verified: {f['file']} ({f.get('status')})")
        with zipfile.ZipFile(ROOT / cfg["data"]["raw_dir"] / f["file"]) as z:
            for n in z.namelist():
                if n.endswith(".csv"):
                    parts.append(parse_kline_csv(z.read(n)))
    if not parts:
        raise RuntimeError(f"no archives for {symbol}; run `python -m src.cli download` first")
    return pd.concat(parts, ignore_index=True)


def build_processed(cfg: dict) -> dict:
    dc = cfg["data"]
    start = ts(dc["start"]) - pd.Timedelta(days=dc["warmup_days"])
    end = ts(dc["end"])
    out_dir = ROOT / dc["processed_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    qa = {"range": [str(start), str(end)], "symbols": {}}
    for sym in dc["symbols"]:
        raw = _read_raw(cfg, sym)
        raw = raw[(raw["open_time"] >= start) & (raw["open_time"] < end)]
        checks = check_1m(raw, start, end)
        clean, log = clean_1m(raw)
        m1 = clean.drop(columns=["ts_unit"]).reset_index(drop=True)
        m5 = aggregate_5m(m1)
        m1.to_parquet(_path(cfg, sym, "1m"), index=False)
        m5.to_parquet(_path(cfg, sym, "5m"), index=False)
        qa["symbols"][sym] = {"raw_checks": checks, "clean_log": log, "rows_1m": int(len(m1)),
                              "rows_5m": int(len(m5))}
    return qa


def load(cfg: dict, symbol: str, tf: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Rows with open_time in [start, end)."""
    p = _path(cfg, symbol, tf)
    if not p.exists():
        raise FileNotFoundError(f"{p} missing; run `python -m src.cli validate-data` first")
    d = pd.read_parquet(p)
    d = d[(d["open_time"] >= start) & (d["open_time"] < end)]
    return d.sort_values("open_time", kind="mergesort").reset_index(drop=True)


def _bounds(cfg: dict, split: str):
    s, e = split_bounds(cfg, split)
    return s - pd.Timedelta(days=cfg["data"]["warmup_days"]), e


def load_for_split(cfg: dict, symbol: str, split: str, tf: str) -> pd.DataFrame:
    """Data for [split start - warmup, split end). Refuses locked splits."""
    if cfg["splits"][split].get("locked"):
        raise PermissionError(f"split '{split}' is locked; use `holdout --approval-file`")
    return load(cfg, symbol, tf, *_bounds(cfg, split))


def load_for_split_unlocked(cfg: dict, symbol: str, split: str, tf: str) -> pd.DataFrame:
    """Only called by the approved holdout path in cli.py (approval verified there)."""
    return load(cfg, symbol, tf, *_bounds(cfg, split))
