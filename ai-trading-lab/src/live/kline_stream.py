"""Network-free processor for Binance spot kline WebSocket payloads (future dry-run feed).

Rules (spec section 9): accept only closed klines (k.x == true); de-duplicate by (symbol, open time);
detect gaps (=> backfill required, no signals until filled); fail closed when data is stale.
Produces rows in the same schema as the historical parser so the same aggregation/feature code applies.
The WebSocket/REST connection layer itself is NOT implemented in MVP v0.1 (public Binance API endpoints
are geo-restricted from the development host); nothing here sends orders.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

ONE_MIN = pd.Timedelta(minutes=1)


@dataclass
class KlineAssembler:
    symbol: str
    stale_after: pd.Timedelta = pd.Timedelta(seconds=90)
    rows: list = field(default_factory=list)
    last_open: pd.Timestamp | None = None
    gaps: list = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {"accepted": 0, "ignored_open": 0, "duplicates": 0,
                                                  "out_of_order": 0, "wrong_symbol": 0})

    def on_message(self, msg: dict) -> dict | None:
        k = msg.get("k", msg)
        if k.get("s", msg.get("s")) != self.symbol:
            self.stats["wrong_symbol"] += 1
            return None
        if not k.get("x", False):
            self.stats["ignored_open"] += 1
            return None
        ot = pd.to_datetime(int(k["t"]), unit="ms", utc=True)
        if self.last_open is not None:
            if ot == self.last_open or any(r["open_time"] == ot for r in self.rows[-5:]):
                self.stats["duplicates"] += 1
                return None
            if ot < self.last_open:
                self.stats["out_of_order"] += 1
                return None
            if ot > self.last_open + ONE_MIN:
                self.gaps.append({"start": self.last_open + ONE_MIN, "end_exclusive": ot})
        row = {"open_time": ot, "close_time": pd.to_datetime(int(k["T"]), unit="ms", utc=True),
               "open": float(k["o"]), "high": float(k["h"]), "low": float(k["l"]), "close": float(k["c"]),
               "volume": float(k["v"]), "quote_volume": float(k["q"]), "trades": int(k["n"]),
               "taker_buy_base": float(k["V"]), "taker_buy_quote": float(k["Q"]), "ts_unit": "ms"}
        self.rows.append(row)
        self.last_open = ot
        self.stats["accepted"] += 1
        return row

    def fill_gap(self, backfill_rows: list[dict]) -> None:
        """Insert REST-backfilled closed rows; gaps are cleared only if fully covered."""
        have = {r["open_time"] for r in self.rows}
        for r in backfill_rows:
            if r["open_time"] not in have:
                self.rows.append(r)
        self.rows.sort(key=lambda r: r["open_time"])
        have = {r["open_time"] for r in self.rows}
        self.gaps = [g for g in self.gaps
                     if not all(t in have for t in pd.date_range(g["start"], g["end_exclusive"], freq="min",
                                                                  inclusive="left"))]

    def is_stale(self, now: pd.Timestamp) -> bool:
        if self.last_open is None:
            return True
        return now - (self.last_open + ONE_MIN) > self.stale_after

    def can_signal(self, now: pd.Timestamp) -> bool:
        """Fail closed: no signals with stale data or unfilled gaps."""
        return not self.is_stale(now) and not self.gaps

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)
