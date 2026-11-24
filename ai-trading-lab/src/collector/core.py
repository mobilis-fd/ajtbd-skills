"""Market Data Recorder v0.1 — read-only, public endpoints only, no keys, no order endpoints.

Pure (network-free) components: record schema, message parsers, 1s bookTicker sampler, staleness rules, de-duplication,
backoff, clock-skew estimate, atomic partitioned Parquet/ZSTD writer with disk quota and checksums, funding as-of join.
The asyncio service in `service.py` wires these to WebSocket/REST transports; it is NOT run in this repository's
automated tests and must not be started without an agreed runtime and scope.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

SCHEMA_VERSION = "rec-0.1"
FORBIDDEN_PATH_PARTS = ("/order", "/account", "/myTrades", "/userDataStream", "/listenKey", "/margin", "/sapi/")

RECORD_FIELDS = ["schema_version", "source", "venue", "market_type", "stream", "symbol", "event_time",
                 "local_receive_time", "available_time", "sample_time", "source_sequence", "flags", "payload"]


def assert_public_url(url: str) -> None:
    """Fail closed if any code path tries to reach an account/order endpoint."""
    for p in FORBIDDEN_PATH_PARTS:
        if p.lower() in url.lower():
            raise PermissionError(f"non-public endpoint refused: {url}")


def _ms(v) -> pd.Timestamp | None:
    return None if v is None else pd.Timestamp(int(v), unit="ms", tz="UTC")


def record(stream: str, market_type: str, symbol: str, recv: pd.Timestamp, payload: dict, *, event_time=None,
           available_time=None, sample_time=None, seq=None, flags=(), source="binance_public_ws") -> dict:
    return {"schema_version": SCHEMA_VERSION, "source": source, "venue": "binance", "market_type": market_type,
            "stream": stream, "symbol": symbol, "event_time": event_time, "local_receive_time": recv,
            "available_time": available_time if available_time is not None else recv, "sample_time": sample_time,
            "source_sequence": seq, "flags": ",".join(flags), "payload": json.dumps(payload, separators=(",", ":"))}


# ------------------------------------------------------------------ parsers

def parse_spot_kline(msg: dict, recv: pd.Timestamp) -> dict | None:
    """Closed 1m klines only (k.x == true)."""
    k = msg.get("k", {})
    if not k.get("x", False):
        return None
    return record("kline_1m", "spot", k["s"], recv, msg, event_time=_ms(msg.get("E")),
                  sample_time=_ms(k["t"]), seq=k.get("L"))


def parse_book_ticker(msg: dict, recv: pd.Timestamp) -> dict:
    """Spot bookTicker has update id `u` but may have no event time: stored as null (never invented)."""
    return record("bookTicker", "spot", msg["s"], recv, msg, event_time=_ms(msg.get("E")), seq=msg.get("u"),
                  flags=() if msg.get("E") else ("no_event_time",))


def parse_mark_price(msg: dict, recv: pd.Timestamp) -> dict:
    """Futures markPrice stream: mark p, index i, estimated settle P, indicative funding r, next funding T."""
    return record("markPrice", "usdm_futures", msg["s"], recv, msg, event_time=_ms(msg.get("E")),
                  flags=("indicative_funding_rate",))


def parse_open_interest(resp: dict, req_sent: pd.Timestamp, recv: pd.Timestamp, mark_price: float | None) -> dict:
    """OI in contracts/base units and, separately, USD value at a given mark (price changes USD without positions)."""
    oi = float(resp["openInterest"])
    payload = {**resp, "oi_units": oi, "oi_usd_at_mark": oi * mark_price if mark_price else None,
               "request_sent_time": str(req_sent)}
    return record("openInterest", "usdm_futures", resp["symbol"], recv, payload, event_time=_ms(resp.get("time")),
                  source="binance_public_rest")


def parse_funding_event(ev: dict, recv: pd.Timestamp, lag_min: int = 5) -> dict:
    """Realized funding: only AVAILABLE after publication. Historical publication time is unknown ->
    conservative available_time = fundingTime + lag (5 min primary, 15 min sensitivity); flagged."""
    ft = _ms(ev["fundingTime"])
    return record("fundingRealized", "usdm_futures", ev["symbol"], recv, ev, event_time=ft,
                  available_time=ft + pd.Timedelta(minutes=lag_min), flags=(f"assumed_publication_lag_{lag_min}m",),
                  source="binance_public_rest")


# ------------------------------------------------------------------ sampling / staleness / dedup

STALE_DEFAULTS = {"kline_1m": pd.Timedelta(seconds=90), "bookTicker": pd.Timedelta(seconds=5),
                  "markPrice": pd.Timedelta(minutes=2), "openInterest": pd.Timedelta(minutes=10)}


class BookTickerSampler:
    """Every second emit the LAST OBSERVED top of book; quote age measured from local receive time.
    Older than `stale` -> emitted as missing (no forward fill beyond threshold). Not tick history."""

    def __init__(self, stale: pd.Timedelta = STALE_DEFAULTS["bookTicker"]):
        self.last: dict[str, tuple[dict, pd.Timestamp]] = {}
        self.stale = stale

    def on_quote(self, msg: dict, recv: pd.Timestamp) -> None:
        self.last[msg["s"]] = (msg, recv)

    def sample(self, symbol: str, sample_time: pd.Timestamp) -> dict:
        if symbol not in self.last:
            return {"symbol": symbol, "sample_time": sample_time, "status": "missing", "quote_age_s": None}
        msg, recv = self.last[symbol]
        age = (sample_time - recv).total_seconds()
        if age > self.stale.total_seconds() or age < 0:
            return {"symbol": symbol, "sample_time": sample_time, "status": "missing", "quote_age_s": age}
        bid, ask = float(msg["b"]), float(msg["a"])
        return {"symbol": symbol, "sample_time": sample_time, "status": "ok", "quote_age_s": age, "bid": bid,
                "ask": ask, "spread_bps": 1e4 * (ask - bid) / ((ask + bid) / 2), "update_id": msg.get("u")}


def kline_valid_for_signal(bar_end: pd.Timestamp, received: pd.Timestamp | None, now: pd.Timestamp,
                           stale=STALE_DEFAULTS["kline_1m"]) -> bool:
    """Closed kline missing more than 90 s after bar end -> invalid for signals (fail closed)."""
    if received is None:
        return False
    return received - bar_end <= stale


class Deduper:
    def __init__(self, maxlen: int = 100_000):
        self.seen: dict[tuple, None] = {}
        self.maxlen = maxlen
        self.duplicates = 0

    def is_new(self, key: tuple) -> bool:
        if key in self.seen:
            self.duplicates += 1
            return False
        self.seen[key] = None
        if len(self.seen) > self.maxlen:
            self.seen.pop(next(iter(self.seen)))
        return True


def kline_gaps(open_times: list[pd.Timestamp]) -> list[dict]:
    """Explicit gaps between consecutive closed 1m klines (to be REST-backfilled; unrecoverable ones stay flagged)."""
    s = sorted(set(open_times))
    out = []
    for a, b in zip(s, s[1:]):
        if b - a > pd.Timedelta(minutes=1):
            out.append({"start": a + pd.Timedelta(minutes=1), "end_exclusive": b,
                        "minutes": int((b - a) / pd.Timedelta(minutes=1)) - 1})
    return out


@dataclass
class Backoff:
    base: float = 1.0
    cap: float = 60.0
    attempt: int = 0
    rng: random.Random = field(default_factory=lambda: random.Random(0))

    def next_delay(self) -> float:
        d = min(self.cap, self.base * 2 ** self.attempt)
        self.attempt += 1
        return d * (0.5 + 0.5 * self.rng.random())

    def reset(self) -> None:
        self.attempt = 0


def clock_offset(local_send: pd.Timestamp, server_time: pd.Timestamp, local_recv: pd.Timestamp) -> dict:
    """NTP-style estimate: offset = server - midpoint(local send, local recv); uncertainty = RTT/2."""
    mid = local_send + (local_recv - local_send) / 2
    return {"offset_ms": (server_time - mid).total_seconds() * 1e3,
            "rtt_ms": (local_recv - local_send).total_seconds() * 1e3}


def clock_skew_alert(offsets_ms: list[float], threshold_ms: float = 500.0) -> bool:
    return bool(offsets_ms) and abs(pd.Series(offsets_ms).median()) > threshold_ms


# ------------------------------------------------------------------ storage

class QuotaExceeded(Exception):
    pass


class PartitionWriter:
    """Parquet/ZSTD partitions venue/market/type/date/symbol, atomic rename, sha256 index, disk quota."""

    def __init__(self, root: Path, quota_bytes: int = 2 * 1024 ** 3):
        self.root = Path(root)
        self.quota = quota_bytes
        self.index_path = self.root / "_index.jsonl"
        self.gaps_path = self.root / "_gaps.jsonl"

    def used_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file()) if self.root.exists() else 0

    def write(self, rows: list[dict], part_seq: int) -> Path | None:
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=RECORD_FIELDS)
        r0 = rows[0]
        date = pd.Timestamp(r0["local_receive_time"]).strftime("%Y-%m-%d")
        d = self.root / f"venue={r0['venue']}" / f"market={r0['market_type']}" / f"type={r0['stream']}" / \
            f"date={date}" / f"symbol={r0['symbol']}"
        d.mkdir(parents=True, exist_ok=True)
        final = d / f"part-{part_seq:06d}.parquet"
        tmp = d / f".tmp-{part_seq:06d}-{os.getpid()}.parquet"
        df.to_parquet(tmp, index=False, compression="zstd")
        size = tmp.stat().st_size
        if self.used_bytes() > self.quota:
            tmp.unlink()
            self._log(self.gaps_path, {"time": str(pd.Timestamp.now(tz="UTC")), "reason": "disk_quota_exceeded",
                                       "stream": r0["stream"], "symbol": r0["symbol"], "rows_lost": len(rows)})
            raise QuotaExceeded(f"quota {self.quota} bytes exceeded")
        os.replace(tmp, final)          # atomic: readers never see partial files
        sha = hashlib.sha256(final.read_bytes()).hexdigest()
        self._log(self.index_path, {"file": str(final.relative_to(self.root)), "rows": len(rows), "bytes": size,
                                    "sha256": sha, "schema_version": SCHEMA_VERSION})
        return final

    def record_gap(self, info: dict) -> None:
        self._log(self.gaps_path, info)

    @staticmethod
    def _log(path: Path, obj: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as fh:
            fh.write(json.dumps(obj, default=str) + "\n")


# ------------------------------------------------------------------ funding as-of join

def funding_asof(decisions: pd.DatetimeIndex, events: pd.DataFrame) -> pd.Series:
    """Latest realized funding rate whose available_time <= decision time (never the future settlement)."""
    ev = events.sort_values("available_time")
    s = pd.Series(ev["fundingRate"].astype(float).to_numpy(), index=pd.DatetimeIndex(ev["available_time"]))
    s = s[~s.index.duplicated(keep="last")]
    pos = s.index.searchsorted(decisions, side="right") - 1
    vals = [s.iloc[p] if p >= 0 else float("nan") for p in pos]
    return pd.Series(vals, index=decisions, name="funding_known")
