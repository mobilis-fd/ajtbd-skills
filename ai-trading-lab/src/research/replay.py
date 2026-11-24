"""v0.2 portfolio replay (independent research oracle).

Semantics (SPEC_MULTI_HORIZON_V02 §2, §6):
* decision at T (end of a closed bar); entry at the 1m open starting T + delay; exit at the 1m open starting
  entry + H (fixed time exit; no stops/targets);
* one position per wallet; a new entry only at a decision time T >= exit time of the previous position;
* buy fill = open*(1+slip) rounded UP to tick; sell fill = open*(1-slip) rounded DOWN; qty rounded DOWN to step;
  notional = min(stake, cash/(1+fee)); fee = fee_rate * actual notional of each side; cash never negative;
* missing entry minute -> no trade; missing exit minute -> exit at the first available later open, `uncertain`;
  missing minutes inside the hold -> `uncertain`;
* constrained mode: mark-to-market only at known 1m closes; daily floor (UTC day-start equity - 1.5) or total
  floor (initial - 10) breached at close of minute k -> exit at the next available 1m open (> k); daily breach
  pauses entries until the next UTC day, total breach stops the run; overshoot recorded;
* split end: positions never extend past the split (decisions are purged); if no exit minute exists before the
  end, exit at the last available open before the end (`boundary_exit`).
Reuses the audited v0.1 rounding helpers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.evaluation.engine import Filters
from src.evaluation.engine import round_down as _rd, round_up as _ru


def round_up(x: float, tick: float) -> float:
    """v0.1 rounding, snapped to 10 decimals to remove float artefacts such as 50220.950000000004."""
    return round(_ru(x, tick), 10)


def round_down(x: float, tick: float) -> float:
    return round(_rd(x, tick), 10)

MIN = pd.Timedelta(minutes=1)


class Px:
    """1m OHLC arrays of one symbol on the regular minute grid [g0, end)."""

    def __init__(self, m1: pd.DataFrame, g0: pd.Timestamp, end: pd.Timestamp):
        self.g0, self.end = g0, end
        self.n = int((end - g0) / MIN)
        k = ((m1["open_time"] - g0) / MIN).astype("int64").to_numpy()
        ok = (k >= 0) & (k < self.n)
        self.o, self.h, self.l, self.c = (np.full(self.n, np.nan) for _ in range(4))
        for arr, col in ((self.o, "open"), (self.h, "high"), (self.l, "low"), (self.c, "close")):
            arr[k[ok]] = m1[col].to_numpy()[ok]
        self.present = ~np.isnan(self.o)
        self.c_ffill = pd.Series(self.c).ffill().to_numpy()

    def idx(self, t: pd.Timestamp) -> int:
        return int((t - self.g0) / MIN)

    def next_present(self, k: int, limit: int) -> int | None:
        if k >= limit:
            return None
        nz = np.flatnonzero(self.present[k:limit])
        return int(k + nz[0]) if len(nz) else None

    def prev_present(self, k: int, floor: int) -> int | None:
        nz = np.flatnonzero(self.present[floor:k])
        return int(floor + nz[-1]) if len(nz) else None


@dataclass
class Costs:
    fee: float = 0.001
    slip: float = 0.00025


@dataclass
class Params:
    costs: Costs = field(default_factory=Costs)
    delay_min: int = 1
    stake: float = 50.0
    initial: float = 100.0
    risk_on: bool = False
    daily_limit: float = 1.5
    total_limit: float = 10.0
    filters: dict = field(default_factory=dict)


@dataclass
class State:
    cash: float
    next_ok: pd.Timestamp | None = None
    day: int | None = None
    day_start: float | None = None
    paused_day: int | None = None
    stopped: bool = False


def _day(px: Px, k: int) -> int:
    return int((px.g0 + k * MIN).value // 86_400_000_000_000)


def run(intents: pd.DataFrame, px: dict[str, Px], p: Params, seg_start: pd.Timestamp, seg_end: pd.Timestamp,
        state: State | None = None) -> dict:
    """intents: one row per decision with columns T, symbol, hold_min, optional stake and metadata (already the
    single chosen candidate per T). Returns trades, rejections, events, state."""
    st = state or State(cash=p.initial)
    trades, rej, events = [], [], []
    initial = p.initial
    if len(intents) == 0:
        return {"trades": trades, "rejections": rej, "events": events, "state": st}
    for r in intents.sort_values("T", kind="mergesort").to_dict("records"):
        sym, T, H = r["symbol"], r["T"], int(r["hold_min"])
        b = px[sym]
        ie = b.idx(T) + p.delay_min
        kend = b.idx(seg_end)

        def reject(reason):
            rej.append({**r, "reason": reason})

        if T < seg_start:
            reject("before_segment"); continue
        if st.next_ok is not None and T < st.next_ok:
            reject("position_open"); continue
        if ie >= kend:
            reject("entry_after_segment_end"); continue
        day = _day(b, ie)
        if st.day != day:
            st.day, st.day_start = day, st.cash
        if p.risk_on and st.stopped:
            reject("total_loss_stop"); continue
        if p.risk_on and st.paused_day == day:
            reject("daily_loss_pause"); continue
        if not b.present[ie]:
            reject("missing_entry_bar"); continue
        stake = float(r.get("stake", p.stake)) if r.get("stake", None) is not None else p.stake
        if not np.isfinite(stake) or stake <= 0:
            reject("invalid_stake"); continue
        f = p.filters.get(sym, Filters())
        raw_in = b.o[ie]
        fill_in = round_up(raw_in * (1 + p.costs.slip), f.tick)
        budget = min(stake, st.cash / (1 + p.costs.fee))
        qty = round_down(budget / fill_in, f.step) if f.step else budget / fill_in
        notional_in = qty * fill_in
        if qty <= 0 or notional_in < f.min_notional:
            reject("min_notional_or_cash"); continue
        fee_in = notional_in * p.costs.fee
        cash_before = st.cash
        st.cash -= notional_in + fee_in
        assert st.cash >= -1e-9, "overdraft"
        cash_mid = st.cash
        xe = ie + H
        uncertain = bool((~b.present[ie:min(xe, kend)]).any())
        reason, kx, forced_day = None, None, None
        last_ds = st.day_start
        if p.risk_on:
            lo, hi = ie, min(xe, kend)
            ks = np.arange(lo, hi)
            mtm = cash_mid + qty * b.c[lo:hi]
            # day-start equity: current for the entry day; for later days, MTM at that day's first known price
            minute_of_day = ((b.g0.value // 60_000_000_000) + ks) % 1440
            ds = np.full(len(ks), st.day_start, dtype=float)
            mids = np.flatnonzero((minute_of_day == 0) & (ks > ie))
            for j in mids:
                kk = ks[j]
                ds[j:] = cash_mid + qty * b.c_ffill[kk - 1]   # equity at the last known close before 00:00
            floor_d = ds - p.daily_limit
            floor_t = initial - p.total_limit
            breach = (~np.isnan(mtm)) & ((mtm <= floor_d + 1e-12) | (mtm <= floor_t + 1e-12))
            if breach.any():
                j = int(np.argmax(breach))
                kb = ks[j]
                total = mtm[j] <= floor_t + 1e-12
                reason = "risk_exit_total" if total else "risk_exit_daily"
                forced_day = _day(b, kb)
                events.append({"time": b.g0 + (kb + 1) * MIN, "event": reason + "_triggered", "symbol": sym,
                               "mtm_equity": float(mtm[j]), "day_start_equity": float(ds[j])})
                kx = b.next_present(kb + 1, kend)
                last_ds = float(ds[j])
            elif len(mids):
                last_ds = float(ds[-1])
        if reason is None:
            if xe < kend and b.present[xe]:
                kx, reason = xe, "time_exit"
            else:
                kx = b.next_present(xe, kend) if xe < kend else None
                reason = "time_exit_after_gap"
                uncertain = True
        if kx is None:
            kx = b.prev_present(kend, ie + 1)
            if kx is None:
                kx = ie
            reason = "boundary_exit"
        raw_out = b.o[kx]
        fill_out = round_down(raw_out * (1 - p.costs.slip), f.tick)
        proceeds = qty * fill_out
        fee_out = proceeds * p.costs.fee
        st.cash += proceeds - fee_out
        exit_time = b.g0 + kx * MIN
        st.next_ok = exit_time
        exit_day = _day(b, kx)
        if exit_day != st.day:
            st.day = exit_day
            st.day_start = last_ds if p.risk_on else st.cash
        if p.risk_on:
            if reason == "risk_exit_daily":
                st.paused_day = forced_day
            if reason == "risk_exit_total":
                st.stopped = True
            if st.cash <= st.day_start - p.daily_limit + 1e-12:
                st.paused_day = exit_day
                events.append({"time": exit_time, "event": "daily_pause", "symbol": sym, "equity": st.cash,
                               "overshoot": st.day_start - p.daily_limit - st.cash})
            if st.cash <= initial - p.total_limit + 1e-12 and not st.stopped:
                st.stopped = True
            if reason == "risk_exit_total" or (st.stopped and not any(e["event"] == "total_stop" for e in events)):
                events.append({"time": exit_time, "event": "total_stop", "symbol": sym, "equity": st.cash,
                               "overshoot": initial - p.total_limit - st.cash})
        cons_raw = raw_out
        if uncertain and reason != "boundary_exit":
            cons_raw = min(raw_out, b.l[kx]) if not math.isnan(b.l[kx]) else raw_out
        cons_fill = round_down(cons_raw * (1 - p.costs.slip), f.tick)
        trades.append({**r, "entry_time": b.g0 + ie * MIN, "exit_time": exit_time, "exit_reason": reason,
                       "raw_entry": raw_in, "fill_entry": fill_in, "qty": qty, "notional_in": notional_in,
                       "fee_in": fee_in, "raw_exit": raw_out, "fill_exit": fill_out, "notional_out": proceeds,
                       "fee_out": fee_out, "fees": fee_in + fee_out,
                       "gross_pnl": qty * (raw_out - raw_in),
                       "slippage_cost": qty * (fill_in - raw_in) + qty * (raw_out - fill_out),
                       "net_pnl": st.cash - cash_before, "cash_before": cash_before, "cash_after_entry": cash_mid,
                       "cash_after": st.cash, "uncertain_gap": uncertain,
                       "conservative_net_delta": qty * (cons_fill - fill_out) * (1 - p.costs.fee),
                       "hold_minutes_actual": kx - ie, "entry_minute": ie, "exit_minute": kx})
    return {"trades": trades, "rejections": rej, "events": events, "state": st}


def equity_1m(trades: list[dict], px: dict[str, Px], start: pd.Timestamp, end: pd.Timestamp,
              initial: float) -> pd.Series:
    """Mark-to-market equity at each 1m close in [start, end), stamped at the bar close."""
    any_px = next(iter(px.values()))
    k0, k1 = any_px.idx(start), any_px.idx(end)
    eq = np.full(k1 - k0, initial, dtype=float)
    level, pos = initial, 0
    for t in sorted(trades, key=lambda x: x["entry_minute"]):
        ie, kx = t["entry_minute"] - k0, t["exit_minute"] - k0
        eq[pos:ie] = level
        seg = px[t["symbol"]].c_ffill[t["entry_minute"]:t["exit_minute"]]
        eq[ie:kx] = t["cash_after_entry"] + t["qty"] * seg
        level, pos = t["cash_after"], kx
    eq[pos:] = level
    idx = pd.date_range(start, end, freq="min", inclusive="left") + MIN
    return pd.Series(eq, index=idx, name="equity")


def passive(px: dict[str, Px], weights: dict[str, float], p: Params, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Buy-and-hold: positions bought at the 1m open start+delay (first available), sold at the last available
    1m open before `end`. Constrained mode: breach at a known close -> exit all at the next known open; no re-entry."""
    any_px = next(iter(px.values()))
    off, k1 = any_px.idx(start), any_px.idx(end)
    cash, pos = p.initial, []
    for sym, stake in weights.items():
        b = px[sym]
        ke = b.next_present(off + p.delay_min, k1)
        f = p.filters.get(sym, Filters())
        fill = round_up(b.o[ke] * (1 + p.costs.slip), f.tick)
        qty = round_down(min(stake, cash / (1 + p.costs.fee)) / fill, f.step)
        if qty * fill < f.min_notional:
            continue
        cash -= qty * fill * (1 + p.costs.fee)
        pos.append({"symbol": sym, "qty": qty, "fill_entry": fill, "entry_minute": ke})
    n = k1 - off
    mtm = np.full(n, p.initial)
    if not pos:
        return {"equity": pd.Series(mtm, index=pd.date_range(start, end, freq="min", inclusive="left") + MIN),
                "positions": [], "exit_reason": "no_position", "net_pnl": 0.0, "exposure_time": 0.0}
    kmax = max(q["entry_minute"] for q in pos)
    val = np.full(n, cash)
    for q in pos:
        val += q["qty"] * px[q["symbol"]].c_ffill[off:k1]
    mtm[kmax - off:] = val[kmax - off:]
    exit_k, reason = None, "end_of_split"
    if p.risk_on:
        ks = np.arange(off, k1)
        mod = (ks + any_px.g0.value // 60_000_000_000) % 1440
        ds = np.where(mod == 0, np.r_[p.initial, mtm[:-1]], np.nan)
        ds[0] = p.initial
        ds = pd.Series(ds).ffill().to_numpy()
        breach = (mtm <= ds - p.daily_limit + 1e-12) | (mtm <= p.initial - p.total_limit + 1e-12)
        breach[: kmax - off] = False
        if breach.any():
            j = int(np.argmax(breach))
            exit_k = off + j + 1
            reason = "risk_exit_total" if mtm[j] <= p.initial - p.total_limit + 1e-12 else "risk_exit_daily"
    final = cash
    for q in pos:
        b = px[q["symbol"]]
        kx = b.next_present(exit_k, k1) if exit_k is not None else None
        if kx is None:
            kx = b.prev_present(k1, q["entry_minute"] + 1)
        f = p.filters.get(q["symbol"], Filters())
        fo = round_down(b.o[kx] * (1 - p.costs.slip), f.tick)
        final += q["qty"] * fo * (1 - p.costs.fee)
        q.update(fill_exit=fo, exit_minute=kx,
                 net_pnl=q["qty"] * fo * (1 - p.costs.fee) - q["qty"] * q["fill_entry"] * (1 + p.costs.fee))
    kx = max(q["exit_minute"] for q in pos)
    mtm[kx - off:] = final
    return {"equity": pd.Series(mtm, index=pd.date_range(start, end, freq="min", inclusive="left") + MIN),
            "positions": pos, "exit_reason": reason, "net_pnl": final - p.initial,
            "exposure_time": (kx - kmax) / n}
