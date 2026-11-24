"""Freqtrade wrappers for MVP v0.1 strategies (E01-P/F, E02-P/F, B01 adaptation).

Signals are computed by the project's own signal layer (src/features, src/signals) so Freqtrade and the
reference replay use one definition. Exit approximation in Freqtrade:
  stoploss -0.6 %, minimal_roi 0.9 % (Freqtrade ROI semantics, see DECISIONS.md), time exit via custom_exit.
E01-F / E02-F need taker-buy volume: provided by a sidecar join on (symbol, close_time). The sidecar exists
only for historical data, therefore the F-variants are BACKTEST-ONLY and must not be used for dry-run.
Version: mvp-0.1
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.core import compute_features  # noqa: E402
from src.ftbridge.sidecar import join_sidecar, load_sidecar  # noqa: E402
from src.signals.rules import e01, e02  # noqa: E402

E01P = {"z5_prev_max": -2.0, "r5_prev_max": -0.004, "r5_min_exclusive": 0.0, "close_gt_open": True, "rv_prev_min": 1.5}
E01F = {**E01P, "imb_prev_max": -0.20, "imb_min": 0.0}
E02P = {"r15_min": 0.005, "z15_min": 2.0, "breakout": True, "rv_min": 1.5}
E02F = {**E02P, "imb_min": 0.20}
SIDECAR_DIR = PROJECT_ROOT / "user_data" / "data" / "sidecar"


class MvpBase(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = False
    stoploss = -0.006
    minimal_roi = {"0": 0.009}
    trailing_stop = False
    use_exit_signal = True  # required for custom_exit (time exit); exit_long is always 0
    process_only_new_candles = True
    startup_candle_count = 400
    hold_minutes = 30
    family = "E01"
    rules: dict = E01P
    needs_sidecar = False
    order_types = {"entry": "market", "exit": "market", "stoploss": "market", "stoploss_on_exchange": False}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe
        if self.needs_sidecar:
            if self.dp is not None and self.dp.runmode.value in ("dry_run", "live"):
                raise RuntimeError("F-variants are backtest-only: no live sidecar feed")
            side = load_sidecar(SIDECAR_DIR, metadata["pair"].replace("/", ""))
            df = join_sidecar(df, side)
        else:
            df = df.copy()
            df["taker_buy_base"] = np.nan
        g = df.set_index(pd.to_datetime(df["date"], utc=True))[["open", "high", "low", "close", "volume",
                                                                 "taker_buy_base"]]
        f = compute_features(g)
        for c in ("z5", "z15", "r5", "r15", "rv", "imb", "prev_max_high", "present"):
            dataframe[c] = f[c].to_numpy()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        f = dataframe.copy()
        f["present"] = f["present"].astype(bool)
        sig = e01(f, self.rules) if self.family == "E01" else e02(f, self.rules)
        dataframe["enter_long"] = sig.astype(int).to_numpy()
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe

    def custom_exit(self, pair: str, trade, current_time: datetime, current_rate: float, current_profit: float,
                    **kwargs):
        if (current_time - trade.open_date_utc).total_seconds() >= self.hold_minutes * 60:
            return "time_exit"
        return None


class MvpE01P(MvpBase):
    family, rules, hold_minutes = "E01", E01P, 30


class MvpE01F(MvpBase):
    family, rules, hold_minutes, needs_sidecar = "E01", E01F, 30, True


class MvpE02P(MvpBase):
    family, rules, hold_minutes = "E02", E02P, 60


class MvpE02F(MvpBase):
    family, rules, hold_minutes, needs_sidecar = "E02", E02F, 60, True
