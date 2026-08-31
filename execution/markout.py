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

=== DECOMPOSITION (2026-08-23) — READ THIS BEFORE CALLING markout_bps AN EDGE

markout_bps above is the SUM of two things that mean opposite-ly different
things, and for a PASSIVE fill the first one dominates:

    markout   = sgn*(mid_fill - fill_price)/fill_price     SPREAD CAPTURE
              + sgn*(mark     - mid_fill  )/mid_fill       ALPHA
              (an identity, up to the differing denominators)

SPREAD CAPTURE is fixed at the instant of fill and carries NO forward
information. A maker who buys at the bid has the mid sitting half a spread
above their price *by construction* - that is revenue for providing
liquidity, and it is real, but it is not prediction. Measured in a synthetic
market with PROVABLY ZERO alpha (driftless random walk, 6000 paths): the
shipped fill rule reported markout -0.484/-0.492/-0.467 bps at 1/6/12 steps
with t=-36.7, and a price-time-priority rule reported +0.451/+0.398/+0.504
with t=+11.0. Both are exactly -/+ the half-spread. NEITHER is alpha; there
was none to find. Flatness across horizons is likewise NOT diagnostic - both
rules are flat in a market with no alpha at all.

ALPHA is the mid-to-mid remainder, and it is the half worth watching.

WHAT THIS DOES AND DOES NOT FIX - stated because the first version of this
note overclaimed it. Planting a KNOWN alpha (+0.06 bps/step) in the same
harness: the estimator has real power (recovers it, t up to 13.9) but is NOT
fill-rule invariant - at horizon 6 the true 0.360 came back as 0.275 under
the crossing rule and 0.740 under price-time priority. Removing the spread
term does NOT remove FILL-TIME SELECTION: each fill rule fills at
systematically different moments, and with drift, when you fill determines
your forward window.

So: alpha_bps is strictly better than markout_bps as an edge proxy, and it is
still NOT a clean one. Treat a nonzero alpha_bps as a hypothesis to verify by
another route, never as a measured edge.

Populated only when the caller passes mid_at_fill to record_fill(); absent
otherwise, and markout_bps is unchanged either way.
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
        # [symbol, asset, sgn, price, t0, done set, mid_at_fill|None]
        self._pending: deque = deque()
        self._obs: dict = defaultdict(lambda: deque(maxlen=self.window))  # (asset,h)->bps
        # ALPHA: the mid-to-mid component, populated only when the caller
        # supplies mid_at_fill. See the DECOMPOSITION note in the module
        # docstring. It removes the SPREAD term exactly; it does NOT remove
        # fill-time selection, and is therefore better than markout_bps as an
        # edge proxy without being a clean one. (An earlier draft of this
        # comment claimed invariance - measured false, and left corrected
        # rather than deleted.)
        self._alpha: dict = defaultdict(lambda: deque(maxlen=self.window))
        self._scap: dict = defaultdict(lambda: deque(maxlen=self.window))

    # ------------------------------------------------------------------
    def record_fill(self, symbol: str, asset: str, side: str,
                    price: float, now: float, mid_at_fill: float | None = None):
        """Enqueue a NEW-risk fill for mark-out measurement. `side` is the
        ORDER side ('buy'/'sell'); a buy is a long entry, a sell a short.

        `mid_at_fill` is OPTIONAL and backward-compatible (None -> only
        markout_bps is produced, exactly as before). Supplying it unlocks the
        decomposition documented at the top of this module, which is the only
        way to tell captured spread apart from predictive edge."""
        if not self.enabled or not self.horizons_sec:
            return
        try:
            price = float(price)
        except (TypeError, ValueError):
            return
        if not (price > 0.0):
            return
        try:
            mid0 = float(mid_at_fill) if mid_at_fill is not None else None
        except (TypeError, ValueError):
            mid0 = None
        if mid0 is not None and not (mid0 > 0.0):
            mid0 = None
        sgn = 1.0 if side == "buy" else -1.0
        self._pending.append([symbol, asset, sgn, price, float(now), set(),
                              mid0])

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
            symbol, asset, sgn, price, t0, done, mid0 = rec
            age = now - t0
            for h in self.horizons_sec:
                if h in done or age < h:
                    continue
                mark = marks.get(symbol)
                fresh = is_fresh is None or bool(is_fresh(symbol, now))
                if mark and mark > 0.0 and fresh:
                    self._obs[(asset, h)].append(sgn * (mark - price) / price * 1e4)
                    if mid0:
                        # SPREAD CAPTURE is fixed at the instant of fill and
                        # carries no forward information at all; ALPHA is the
                        # mid-to-mid remainder. Splitting them is the only way
                        # to stop a maker's captured half-spread reading as
                        # predictive edge on the summary line.
                        self._scap[(asset, h)].append(
                            sgn * (mid0 - price) / price * 1e4)
                        self._alpha[(asset, h)].append(
                            sgn * (mark - mid0) / mid0 * 1e4)
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
            cell = {"markout_bps": round(sum(dq) / len(dq), 2), "n": len(dq)}
            # Appended, never substituted: markout_bps keeps its meaning and
            # its place, so every existing reader and dashboard is unchanged.
            sc = self._scap.get((asset, h))
            al = self._alpha.get((asset, h))
            if sc and al:
                cell["spread_capture_bps"] = round(sum(sc) / len(sc), 2)
                cell["alpha_bps"] = round(sum(al) / len(al), 2)
                cell["decomposed_n"] = len(al)
            out["by_asset"].setdefault(asset, {})[key] = cell
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
                 "price": price, "t0": t0, "done": sorted(done),
                 "mid0": mid0}
                for symbol, asset, sgn, price, t0, done, mid0 in self._pending
            ],
            "obs": {f"{asset}{_OBS_KEY_SEP}{h}": list(dq)
                    for (asset, h), dq in self._obs.items() if dq},
            # DECOMPOSITION persistence (2026-08-31): _scap/_alpha were
            # computed since 2026-08-23 but omitted here, so every restart
            # destroyed the spread-neutral alpha series - measured live at
            # 0.986% coverage (1,521 obs on disk, zero alpha) because the
            # decomposition window was exactly time-since-restart. The
            # module docstring calls alpha "the half worth watching"; now
            # it survives the restarts that used to erase it.
            "scap": {f"{asset}{_OBS_KEY_SEP}{h}": list(dq)
                     for (asset, h), dq in self._scap.items() if dq},
            "alpha": {f"{asset}{_OBS_KEY_SEP}{h}": list(dq)
                      for (asset, h), dq in self._alpha.items() if dq},
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
                    set(p.get("done", [])),
                    # absent in snapshots written before the decomposition
                    # landed: an old file restores with mid0=None and simply
                    # produces no alpha for those in-flight fills.
                    (float(p["mid0"]) if p.get("mid0") is not None
                     else None)])
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
        # Decomposition series: snapshots written before 2026-08-31 have no
        # scap/alpha keys and restore clean (empty) - same tolerance as the
        # pre-decomposition mid0=None path above. Each section independent.
        for section, target in (("scap", self._scap), ("alpha", self._alpha)):
            try:
                for key, vals in (d.get(section) or {}).items():
                    asset, _sep, h_str = str(key).rpartition(_OBS_KEY_SEP)
                    if not _sep:
                        continue
                    target[(asset, float(h_str))] = deque(
                        (float(v) for v in vals), maxlen=self.window)
            except (KeyError, TypeError, ValueError):
                log.warning("markout %s section malformed - skipped", section)
