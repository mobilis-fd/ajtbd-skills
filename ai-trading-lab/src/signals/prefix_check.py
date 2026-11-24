"""Own look-ahead checks on real development data for ALL strategies (incl. those Freqtrade cannot analyse).

1. Prefix invariance: features/signals computed on data truncated at cut c equal the full-data values for t < c.
2. Future mutation: randomly perturbing all candles at/after c leaves features/signals for t < c unchanged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import split_bounds
from src.data import store
from src.data.aggregate import to_grid
from src.features.core import compute_features
from src.signals.rules import STRATEGIES, b01_signal, strategy_signal

FEATS = ["r5", "r15", "z5", "z15", "rv", "imb", "prev_max_high", "ret24h", "vol24h"]


def _eq(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    return bool(np.allclose(a.to_numpy(float), b.to_numpy(float), rtol=0, atol=0, equal_nan=True))


def _signals(cfg, f):
    return pd.DataFrame({n: strategy_signal(f, n, cfg["strategies"][n]) for n in STRATEGIES})


def run_prefix_checks(cfg: dict, n_cuts: int = 25, seed: int = 7) -> dict:
    s, e = split_bounds(cfg, "development")
    warm = s - pd.Timedelta(days=cfg["data"]["warmup_days"])
    fc = cfg["features"]
    rng = np.random.default_rng(seed)
    details, ok = [], True
    for sym in cfg["data"]["symbols"]:
        m5 = store.load_for_split(cfg, sym, "development", "5m")
        grid = to_grid(m5, warm, e)
        args = (fc["z_window"], fc["rv_window"], fc["breakout_window"], cfg["regime"]["return_lookback_candles"])
        full = compute_features(grid, *args)
        sig_full = _signals(cfg, full)
        b01_full = b01_signal(m5, sym)
        cut_idx = np.sort(rng.choice(np.arange(400, len(grid) - 10), size=n_cuts, replace=False))
        for ci in cut_idx:
            c = grid.index[ci]
            pre = compute_features(grid.iloc[:ci], *args)
            r1 = _eq(pre[FEATS], full[FEATS].iloc[:ci]) and _signals(cfg, pre).equals(sig_full.iloc[:ci])
            mut = grid.copy()
            noise = np.exp(rng.normal(0, 0.05, size=(len(grid) - ci, 1)))
            for col in ("open", "high", "low", "close"):
                mut.iloc[ci:, mut.columns.get_loc(col)] = mut[col].iloc[ci:].to_numpy() * noise[:, 0]
            for col in ("volume", "taker_buy_base"):
                mut.iloc[ci:, mut.columns.get_loc(col)] = mut[col].iloc[ci:].to_numpy() * rng.uniform(0.1, 10, len(grid) - ci)
            fm = compute_features(mut, *args)
            r2 = _eq(fm[FEATS].iloc[:ci], full[FEATS].iloc[:ci]) and _signals(cfg, fm).iloc[:ci].equals(sig_full.iloc[:ci])
            m5_pre = m5[m5["open_time"] < c]
            b01_pre = b01_signal(m5_pre, sym)
            r3 = b01_pre.equals(b01_full.loc[b01_full.index < c])
            details.append({"symbol": sym, "cut": str(c), "prefix_invariant": r1, "future_mutation_invariant": r2,
                            "b01_prefix_invariant": bool(r3)})
            ok &= r1 and r2 and bool(r3)
    return {"ok": bool(ok), "n_checks": len(details), "n_failed": sum(1 for d in details if not (
        d["prefix_invariant"] and d["future_mutation_invariant"] and d["b01_prefix_invariant"])), "details": details}
