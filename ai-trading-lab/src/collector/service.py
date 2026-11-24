"""Asyncio wiring of the read-only recorder to Binance PUBLIC WebSocket/REST endpoints.

NOT executed in this repository's tests or sessions. To be run only on the user's own machine after an agreed
runtime and scope (smoke 15 min, then 24 h). No API keys, no account or order endpoints (asserted per URL).
If the region/source is unavailable the service stops and reports; it never tries alternative routes.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pandas as pd

from src.collector.core import (Backoff, BookTickerSampler, Deduper, PartitionWriter, QuotaExceeded, assert_public_url,
                                clock_offset, parse_book_ticker, parse_mark_price, parse_open_interest,
                                parse_spot_kline)

SPOT_WS = "wss://stream.binance.com:9443/stream?streams="
FUT_WS = "wss://fstream.binance.com/stream?streams="
SPOT_REST = "https://api.binance.com"
FUT_REST = "https://fapi.binance.com"


def now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


class Recorder:
    def __init__(self, cfg: dict, out_dir: Path):
        self.cfg = cfg
        self.w = PartitionWriter(out_dir, int(cfg["disk_quota_gb"] * 1024 ** 3))
        self.buf: dict[tuple, list] = {}
        self.seq = 0
        self.dedup = Deduper()
        self.sampler = BookTickerSampler(pd.Timedelta(seconds=cfg["stale"]["bookTicker_s"]))
        self.stats = {"messages": 0, "rows_written": 0, "reconnects": 0, "clock": [], "errors": []}
        self.stop = asyncio.Event()

    def add(self, rec: dict | None):
        if rec is None:
            return
        key = (rec["stream"], rec["symbol"], rec["source_sequence"], str(rec["sample_time"]), str(rec["event_time"]))
        if not self.dedup.is_new(key):
            return
        self.buf.setdefault((rec["stream"], rec["symbol"]), []).append(rec)

    def flush(self):
        for k, rows in list(self.buf.items()):
            if rows:
                self.seq += 1
                try:
                    self.w.write(rows, self.seq)
                    self.stats["rows_written"] += len(rows)
                except QuotaExceeded as e:
                    self.stats["errors"].append(str(e))
                    self.stop.set()
                self.buf[k] = []

    async def ws_loop(self, url: str, handler):
        import websockets
        assert_public_url(url)
        bo = Backoff()
        while not self.stop.is_set():
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    bo.reset()
                    async for raw in ws:
                        recv = now()
                        self.stats["messages"] += 1
                        handler(json.loads(raw).get("data", {}), recv)
                        if self.stop.is_set():
                            break
            except Exception as e:  # reconnect with backoff; the gap is recorded explicitly
                self.stats["reconnects"] += 1
                self.w.record_gap({"time": str(now()), "reason": f"ws_disconnect {type(e).__name__}", "url": url})
                if "451" in str(e) or "403" in str(e):
                    self.stats["errors"].append(f"source unavailable: {e}")
                    self.stop.set()
                    return
                await asyncio.sleep(bo.next_delay())

    async def rest_get(self, session, url: str):
        assert_public_url(url)
        sent = now()
        async with session.get(url, timeout=10) as r:
            body = await r.json()
            return r.status, body, sent, now()

    async def poll_loop(self, session):
        syms = self.cfg["futures_symbols"]
        last_oi = 0.0
        while not self.stop.is_set():
            st, body, sent, recv = await self.rest_get(session, f"{SPOT_REST}/api/v3/time")
            if st == 200:
                self.stats["clock"].append(clock_offset(sent, pd.Timestamp(body["serverTime"], unit="ms", tz="UTC"),
                                                        recv))
            elif st in (403, 451):
                self.stats["errors"].append(f"source unavailable HTTP {st}")
                self.stop.set(); return
            if time.time() - last_oi >= self.cfg["oi_poll_s"]:
                for s in syms:
                    st, body, sent, recv = await self.rest_get(session, f"{FUT_REST}/fapi/v1/openInterest?symbol={s}")
                    if st == 200:
                        self.add(parse_open_interest(body, sent, recv, None))
                last_oi = time.time()
            for s in self.cfg["book_symbols"]:
                smp = self.sampler.sample(s, now())
                self.add({"schema_version": "rec-0.1", "source": "sampler", "venue": "binance", "market_type": "spot",
                          "stream": "bookTicker_1s", "symbol": s, "event_time": None, "local_receive_time": now(),
                          "available_time": now(), "sample_time": smp["sample_time"], "source_sequence": smp.get("update_id"),
                          "flags": smp["status"], "payload": json.dumps(smp, default=str)})
            self.flush()
            await asyncio.sleep(1)

    async def run(self, duration_s: int):
        import aiohttp
        spot = "/".join([f"{s.lower()}@kline_1m" for s in self.cfg["kline_symbols"]] +
                        [f"{s.lower()}@bookTicker" for s in self.cfg["book_symbols"]])
        fut = "/".join(f"{s.lower()}@markPrice@1s" for s in self.cfg["futures_symbols"])

        def on_spot(d, recv):
            if d.get("e") == "kline":
                self.add(parse_spot_kline(d, recv))
            elif "b" in d and "a" in d:
                self.sampler.on_quote(d, recv)
                self.add(parse_book_ticker(d, recv))

        def on_fut(d, recv):
            if d.get("e") == "markPriceUpdate":
                self.add(parse_mark_price(d, recv))

        async with aiohttp.ClientSession() as session:
            tasks = [asyncio.create_task(self.ws_loop(SPOT_WS + spot, on_spot)),
                     asyncio.create_task(self.ws_loop(FUT_WS + fut, on_fut)),
                     asyncio.create_task(self.poll_loop(session))]
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=duration_s)
            except asyncio.TimeoutError:
                pass
            self.stop.set()
            for t in tasks:
                t.cancel()
            self.flush()
        return self.stats
