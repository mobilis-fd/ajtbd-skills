"""Configuration loading, hashing and split helpers."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "mvp.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if cfg.get("mode") == "live" or not cfg.get("dry_run", True):
        raise ValueError("live mode is forbidden in MVP v0.1")
    cfg["_path"] = str(path)
    cfg["_hash"] = file_sha256(path)
    return cfg


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ts(s: str) -> pd.Timestamp:
    t = pd.Timestamp(s)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("UTC")


def split_bounds(cfg: dict, split: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    s = cfg["splits"][split]
    return ts(s["start"]), ts(s["end"])


def code_hash(root: Path = ROOT) -> str:
    """Hash of tracked source files (src/, user_data/strategies, configs/)."""
    h = hashlib.sha256()
    files = []
    for sub in ("src", "user_data/strategies", "configs"):
        files += sorted(p for p in (root / sub).rglob("*") if p.is_file() and p.suffix in {".py", ".yaml", ".json"}
                        and "__pycache__" not in p.parts)
    for p in files:
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def git_commit(root: Path = ROOT) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "configs", "user_data/strategies"],
                               cwd=root, capture_output=True, text=True).stdout.strip()
        return out.stdout.strip() + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)
