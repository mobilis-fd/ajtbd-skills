"""Signal rules. Pure functions of past-only features; no parameter search.

A signal on 5m candle t is a decision available at close_time(t) = open_time(t) + 5m.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os

import numpy as np
import pandas as pd

STRATEGIES = ("E01-P", "E01-F", "E02-P", "E02-F")


def e01(f: pd.DataFrame, rules: dict) -> pd.Series:
    prev_ok = f["present"].shift(1, fill_value=False).astype(bool)
    cond = (
        f["present"] & prev_ok
        & (f["z5"].shift(1) <= rules["z5_prev_max"])
        & (f["r5"].shift(1) <= rules["r5_prev_max"])
        & (f["r5"] > rules["r5_min_exclusive"])
        & (f["close"] > f["open"])
        & (f["rv"].shift(1) >= rules["rv_prev_min"])
    )
    if "imb_prev_max" in rules:
        cond &= (f["imb"].shift(1) <= rules["imb_prev_max"]) & (f["imb"] >= rules["imb_min"])
    return cond.fillna(False).astype(bool)


def e02(f: pd.DataFrame, rules: dict) -> pd.Series:
    cond = (
        f["present"]
        & (f["r15"] >= rules["r15_min"])
        & (f["z15"] >= rules["z15_min"])
        & (f["close"] > f["prev_max_high"])
        & (f["rv"] >= rules["rv_min"])
    )
    if "imb_min" in rules:
        cond &= f["imb"] >= rules["imb_min"]
    return cond.fillna(False).astype(bool)


def strategy_signal(f: pd.DataFrame, name: str, scfg: dict) -> pd.Series:
    fam = scfg["family"]
    if fam == "E01":
        return e01(f, scfg["rules"])
    if fam == "E02":
        return e02(f, scfg["rules"])
    raise ValueError(name)


# ---------------------------------------------------------------- B01 (upstream Freqtrade SampleStrategy)

def sample_strategy_path() -> str:
    import freqtrade
    return os.path.join(os.path.dirname(freqtrade.__file__), "templates", "sample_strategy.py")


def sample_strategy_sha256() -> str:
    return hashlib.sha256(open(sample_strategy_path(), "rb").read()).hexdigest()


def b01_signal(df5: pd.DataFrame, symbol: str) -> pd.Series:
    """Entry signals of upstream freqtrade SampleStrategy (unmodified code), computed on the
    sequence of *present* 5m candles (as Freqtrade would see live). Exit rules are NOT used:
    unified stop/target/time/risk rules are applied by the replay engine (adaptation).
    Returns boolean Series indexed by open_time of present candles."""
    spec = importlib.util.spec_from_file_location("ft_sample_strategy", sample_strategy_path())
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    strat = mod.SampleStrategy(config={})
    d = pd.DataFrame({"date": df5["open_time"].reset_index(drop=True), "open": df5["open"].values, "high": df5["high"].values,
                      "low": df5["low"].values, "close": df5["close"].values, "volume": df5["volume"].values})
    meta = {"pair": symbol.replace("USDT", "/USDT")}
    d = strat.populate_indicators(d, meta)
    d = strat.populate_entry_trend(d, meta)
    sig = d["enter_long"].fillna(0).astype(int) == 1
    # Respect the strategy's own startup_candle_count (indicators unstable before it)
    sig.iloc[: strat.startup_candle_count] = False
    return pd.Series(sig.to_numpy(), index=pd.DatetimeIndex(df5["open_time"], name="open_time"))


# ---------------------------------------------------------------- B03 random entries

def random_signal_times(candidates: pd.DatetimeIndex, n: int, seed: int) -> pd.DatetimeIndex:
    """Draw n distinct 5m candle open_times uniformly from candidates with a fixed seed."""
    rng = np.random.default_rng(seed)
    n = min(n, len(candidates))
    idx = np.sort(rng.choice(len(candidates), size=n, replace=False))
    return candidates[idx]
