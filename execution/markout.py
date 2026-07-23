"""
execution/markout.py — post-fill mark-out: the EMPIRICAL adverse-selection meter.

The manip anti-scalp gate (main.manip_entry_scale) PREDICTS a toxic book and
shrinks/vetoes the entry. Mark-out MEASURES whether the fills we actually got
were picked off — the ground truth the gate is trying to pre-empt.

For each NEW-risk fill we record (side, price, t). At each configured horizon we
read the TRUSTED mark and compute the signed move relative to our trade
direction:

    markout_bps = side_sign * (mark - fill_price) / fill_price * 1e4
    side_sign   = +1 for a buy (long entry), -1 for a sell (short entry)

A POSITIVE mark-out means the price moved in our favour after we filled (we
bought and it rose / sold and it fell) — a healthy, non-toxic fill. A NEGATIVE
mark-out means the price moved AGAINST us right after we filled (we bought the
local top / sold the local bottom) — we were adversely selected, i.e. "scalped
by bigger fishes". A persistently negative per-asset mark-out is exactly the
condition the anti-scalp gate exists to reduce.

This module takes NO trading decision — it is measurement only, surfaced in
status.json and as metrics. It reads only the trusted mark handed in by the
caller (an is_fresh predicate defers measurement on a stale/dark feed rather
than fabricating a mark-out off a frozen price).
"""
import logging
from collections import defaultdict, deque

log = logging.getLogger("liquiditybot.execution.markout")

# separator for the (asset, horizon) obs-dict composite key on the wire - an
# asset symbol is never expected to contain this, but if one somehow did the
# rpartition below still resolves correctly (splits on the LAST occurrence).
_OBS_KEY_SEP = "\u0001"


class MarkoutTracker:
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", True))
        # de-duplicated, sorted horizons; a fill is measured once per horizon
        self.horizons_sec = sorted({float(h) for h in
                                    cfg.get("horizons_sec", [5.0, 30.0, 60.0])
                                    if float(h) > 0.0})
        self.window = int(cfg.get("window", 200))       # rolling obs per bucket
        self.grace_sec = float(cfg.get("grace_sec", 15.0))  # wait for a fresh mark
        self._pending: deque = deque()   # [symbol, asset, sgn, price, t0, done set]
        self._obs: dict = defaultdict(lambda: deque(maxlen=self.window))  # (asset,h)->bps

    # ------------------------------------------------------------------
    def record_fill(self, symbol: str, asset: str, side: str,
                    price: float, now: float):
        """Enqueue a NEW-risk fill for mark-out measurement. `side` is the
        ORDER side ('buy'/'sell'); a buy is a long entry, a sell a short."""
        if not self.enabled or not self.horizons_sec:
            return
        try:
            price = float(price)
        except (TypeError, ValueError):
            return
        if not (price > 0.0):
            return
        sgn = 1.0 if side == "buy" else -1.0
        self._pending.append([symbol, asset, sgn, price, float(now), set()])

    def poll(self, marks: dict, now: float, is_fresh=None):
        """Resolve due horizons against the trusted mark. `is_fresh(symbol,
        now)->bool`, when given, gates measurement on a fresh mark; a mark that
        never turns fresh within its horizon + grace window is dropped (no
        fabricated mark-out off a frozen price)."""
        if not self.enabled or not self._pending:
            return
        last_h = self.horizons_sec[-1]
        still: deque = deque()
        for rec in self._pending:
            symbol, asset, sgn, price, t0, done = rec
            age = now - t0
            for h in self.horizons_sec:
                if h in done or age < h:
                    continue
                mark = marks.get(symbol)
                fresh = is_fresh is None or bool(is_fresh(symbol, now))
                if mark and mark > 0.0 and fresh:
                    self._obs[(asset, h)].append(sgn * (mark - price) / price * 1e4)
                    done.add(h)
                elif age >= h + self.grace_sec:
                    done.add(h)                 # gave up: no fresh mark in time
            if len(done) < len(self.horizons_sec) and age < last_h + self.grace_sec:
                still.append(rec)               # more horizons pending; keep it
        self._pending = still

    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        """Rolling mean mark-out (bps) per asset+horizon and pooled overall.
        Negative = adverse selection (getting scalped)."""
        out: dict = {"horizons_sec": self.horizons_sec,
                     "by_asset": {}, "overall": {}, "pending": len(self._pending)}
        pooled: dict = defaultdict(list)
        for (asset, h), dq in self._obs.items():
            if not dq:
                continue
            key = str(int(h))
            out["by_asset"].setdefault(asset, {})[key] = {
                "markout_bps": round(sum(dq) / len(dq), 2), "n": len(dq)}
            pooled[h].extend(dq)
        for h, vals in pooled.items():
            out["overall"][str(int(h))] = {
                "markout_bps": round(sum(vals) / len(vals), 2), "n": len(vals)}
        return out

    def worst_asset_markout(self, horizon_sec: float | None = None):
        """The most-adverse (most negative) mean mark-out across assets at the
        given horizon (default: the longest). Returns (asset, bps) or (None,
        0.0). A single scalar the status panel / a future feedback loop can
        watch."""
        if not self._obs:
            return (None, 0.0)
        h = horizon_sec if horizon_sec is not None else self.horizons_sec[-1]
        worst_asset, worst_bps = None, 0.0
        for (asset, hh), dq in self._obs.items():
            if hh != h or not dq:
                continue
            m = sum(dq) / len(dq)
            if worst_asset is None or m < worst_bps:
                worst_asset, worst_bps = asset, m
        return (worst_asset, round(worst_bps, 2))

    # ------------------------------------------------------------------
    # W2-16: persistence. Pure telemetry (no trading decision, invariant #6
    # doesn't apply) - a deploy restart used to wipe the adverse-selection
    # window entirely, and under deploy cadence the window could never
    # accumulate. Kept separate from snapshot() (status.json telemetry).
    def to_dict(self) -> dict:
        return {
            "pending": [
                {"symbol": symbol, "asset": asset, "sgn": sgn,
                 "price": price, "t0": t0, "done": sorted(done)}
                for symbol, asset, sgn, price, t0, done in self._pending
            ],
            "obs": {f"{asset}{_OBS_KEY_SEP}{h}": list(dq)
                    for (asset, h), dq in self._obs.items() if dq},
        }

    def restore(self, d: dict | None) -> None:
        """Rebuild in-flight fills + rolling observations from a prior run.
        Best-effort, each section its own try/except (persistence.py's
        per-section pattern) - malformed input is logged and skipped, never
        raised; this module takes no trading decision so there is nothing
        unsafe about starting a section clean. Obs deques rebuild against the
        CURRENT config window: a changed window must not crash, and a
        shrunk window keeps the newest observations (deque(maxlen=) drops
        the oldest first when constructed from a longer iterable)."""
        if not d:
            return
        try:
            for p in d.get("pending", []):
                self._pending.append([
                    str(p["symbol"]), str(p["asset"]), float(p["sgn"]),
                    float(p["price"]), float(p["t0"]),
                    set(p.get("done", []))])
        except (KeyError, TypeError, ValueError):
            log.warning("markout pending section malformed - skipped")
        try:
            for key, vals in (d.get("obs") or {}).items():
                asset, _sep, h_str = str(key).rpartition(_OBS_KEY_SEP)
                if not _sep:
                    continue           # malformed key: no separator found
                self._obs[(asset, float(h_str))] = deque(
                    (float(v) for v in vals), maxlen=self.window)
        except (KeyError, TypeError, ValueError):
            log.warning("markout obs section malformed - skipped")
