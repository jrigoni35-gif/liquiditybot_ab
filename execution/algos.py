"""
execution/algos.py — institutional execution algorithms, rev 4

Parent/child order scheduling for entries whose notional is large
enough that a single print pays unnecessary impact. Four scheduling
disciplines, all producing the same thing — a time-phased sequence of
child slice sizes — consumed by main.py, which prices and submits every
child through the UNCHANGED hardened path (AS quote -> tactics ->
pre-trade -> firewall -> order_manager). This module contains zero
network, zero order placement, zero venue awareness: pure, replayable
scheduling math.

  TWAP   equal slices over the horizon. The null hypothesis of
         execution; minimum-variance vs the interval-TWAP benchmark.
  VWAP   slices weighted by the observed volume profile of the recent
         tape (last `curve_lookback_bars` candles, bucketed onto the
         horizon). Trades when the market trades; the standard
         benchmark algo.
  POV    participation-of-volume: each step releases pov_rate x the
         market volume printed since the last step (bounded per child).
         Adaptive to activity; never dominates the tape.
  IS     implementation shortfall (Almgren-Chriss discretization):
         remaining(t) = total·sinh(kappa·(T−t))/sinh(kappa·T), kappa
         scaled by vol and signal urgency — urgent, volatile edges
         front-load; patient ones spread out. Minimizes the
         impact-vs-alpha-decay trade-off against the ARRIVAL price,
         which is also what the built-in TCA measures.

Safety contract (all enforced here, re-enforced downstream):
  * children are always LIMIT entries through order_manager (OM-011
    market-refusal invariant untouched);
  * child pacing respects the risk-firewall order budget: interval
    floor `min_interval_sec` (default 30s vs FW-020's 3/60s budget);
  * a parent ABORTS remaining slices on watchdog block, horizon
    expiry, or operator entries_off — reason-coded EX-ALGO-*;
  * parents are deliberately NOT persisted: after a restart the
    unfilled remainder is abandoned (positions from filled children
    are already independently managed by tiers/stops/inventory).

TCA: each parent records its ARRIVAL price (decision-time mark). Every
child fill updates the parent's implementation shortfall in bps
(side-signed: positive = paid worse than arrival). Exposed via
status() for the dashboard and logged at completion.
"""

import logging
import math
import time
import uuid
from dataclasses import dataclass, field

log = logging.getLogger("liquiditybot.execution.algos")

ALGOS = ("twap", "vwap", "pov", "is")


def _f(x, default=0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# schedule weight generators (pure)
# ---------------------------------------------------------------------------
def twap_weights(n: int) -> list:
    n = max(int(n), 1)
    return [1.0 / n] * n


def vwap_weights(n: int, candles: list, lookback: int = 48) -> list:
    """Bucket the last `lookback` candles' volume onto n slices. Flat
    tape (or no data) degrades to TWAP — the correct null."""
    n = max(int(n), 1)
    vols = [max(_f(c.get("volume")), 0.0) for c in (candles or [])[-lookback:]]
    if len(vols) < n or sum(vols) <= 0:
        return twap_weights(n)
    per = len(vols) / n
    buckets = []
    for k in range(n):
        lo, hi = int(k * per), int((k + 1) * per) if k < n - 1 else len(vols)
        buckets.append(sum(vols[lo:hi]))
    total = sum(buckets)
    if total <= 0:
        return twap_weights(n)
    return [b / total for b in buckets]


def is_weights(n: int, sigma_bar_pct: float, urgency: float,
               risk_aversion: float = 1.0) -> list:
    """Almgren-Chriss front-loaded schedule, discretized to n slices.
    kappa grows with vol, urgency and risk aversion; kappa -> 0
    degrades to TWAP (the closed-form limit)."""
    n = max(int(n), 1)
    kappa = max(risk_aversion, 0.05) * (0.5 + 4.0 * min(max(urgency, 0.0), 1.0)) \
        * (0.5 + min(max(_f(sigma_bar_pct), 0.0), 3.0))
    kT = min(max(kappa, 1e-6), 30.0)          # numerical guard on sinh
    rem_prev = 1.0
    w = []
    for k in range(1, n + 1):
        rem = math.sinh(kT * (1.0 - k / n)) / math.sinh(kT)
        w.append(max(rem_prev - rem, 0.0))
        rem_prev = rem
    s = sum(w)
    return [x / s for x in w] if s > 0 else twap_weights(n)


# ---------------------------------------------------------------------------
@dataclass
class ChildSlice:
    parent_id: str
    units: float
    seq: int                    # 1-based child index
    n_total: int


@dataclass
class ParentOrder:
    parent_id: str
    asset: str
    symbol: str
    side: str                   # buy | sell
    direction: str              # long | short
    algo: str
    total_units: float
    arrival_price: float        # decision-time mark: the IS benchmark
    horizon_sec: float
    created_ts: float
    urgency: float = 0.0
    submitted_units: float = 0.0
    filled_units: float = 0.0
    fill_notional: float = 0.0  # sum(px*units) over child fills
    schedule: list = field(default_factory=list)   # cumulative unit targets
    next_seq: int = 1
    last_child_ts: float = 0.0
    last_seen_volume: float = 0.0     # POV: market volume watermark
    done: bool = False
    abort_reason: str = ""
    child_ids: list = field(default_factory=list)
    reject_streak: int = 0      # consecutive structural child rejects

    # ---- TCA ---------------------------------------------------------
    def avg_fill_price(self) -> float:
        return self.fill_notional / self.filled_units \
            if self.filled_units > 0 else 0.0

    def shortfall_bps(self) -> float:
        """Implementation shortfall vs arrival, side-signed: positive =
        execution cost paid (bought above / sold below arrival)."""
        avg = self.avg_fill_price()
        if avg <= 0 or self.arrival_price <= 0:
            return 0.0
        raw = (avg / self.arrival_price - 1.0) * 1e4
        return raw if self.side == "buy" else -raw


class ExecutionScheduler:
    """Owns live parents; answers 'what child is due now?'. Pacing,
    budgets and horizons live here; pricing/submission stay in main."""

    def __init__(self, config: dict):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.default_algo = str(cfg.get("default_algo", "is")).lower()
        if self.default_algo not in ALGOS:
            self.default_algo = "is"
        self.engage_notional_usd = _f(cfg.get("engage_notional_usd", 1500.0),
                                      1500.0)
        self.max_children = min(max(int(cfg.get("max_children", 4)), 2), 12)
        self.horizon_sec = max(_f(cfg.get("horizon_sec", 600.0), 600.0), 60.0)
        # FW-020 coexistence: firewall budgets accepted orders per minute;
        # floor the child interval so slicing + exits fit inside it
        self.min_interval_sec = max(_f(cfg.get("min_interval_sec", 30.0),
                                       30.0), 10.0)
        self.pov_rate = min(max(_f(cfg.get("pov_rate", 0.10), 0.10), 0.01),
                            0.5)
        self.curve_lookback_bars = max(int(cfg.get("curve_lookback_bars", 48)),
                                       8)
        self.is_risk_aversion = _f(cfg.get("is_risk_aversion", 1.0), 1.0)
        self.min_child_units_frac = min(max(
            _f(cfg.get("min_child_units_frac", 0.10), 0.10), 0.02), 0.5)
        self.parents: dict = {}            # parent_id -> ParentOrder
        self.completed: list = []          # ring of finished parents (TCA)
        self._completed_cap = 50

    # ------------------------------------------------------------------
    def should_engage(self, notional_usd: float, algo_override=None) -> bool:
        if not self.enabled:
            return False
        if algo_override is not None and str(algo_override).lower() == "off":
            return False
        return _f(notional_usd) >= self.engage_notional_usd

    def create_parent(self, asset: str, symbol: str, side: str,
                      direction: str, total_units: float,
                      arrival_price: float, now: float,
                      sigma_bar_pct: float = 0.0, urgency: float = 0.0,
                      candles=None, algo: str | None = None) -> ParentOrder:
        algo = (algo or self.default_algo).lower()
        if algo not in ALGOS:
            algo = self.default_algo
        n = self.max_children
        if algo == "twap":
            w = twap_weights(n)
        elif algo == "vwap":
            w = vwap_weights(n, candles or [], self.curve_lookback_bars)
        elif algo == "is":
            w = is_weights(n, sigma_bar_pct, urgency, self.is_risk_aversion)
        else:                               # pov schedules dynamically
            w = twap_weights(n)             # fallback cadence if tape dies
        cum, acc = [], 0.0
        for x in w:
            acc += x
            cum.append(acc * total_units)
        cum[-1] = total_units               # exact terminal, no float drift
        p = ParentOrder(parent_id=str(uuid.uuid4())[:8], asset=asset,
                        symbol=symbol, side=side, direction=direction,
                        algo=algo, total_units=total_units,
                        arrival_price=_f(arrival_price),
                        horizon_sec=self.horizon_sec, created_ts=now,
                        urgency=min(max(_f(urgency), 0.0), 1.0),
                        schedule=cum)
        self.parents[p.parent_id] = p
        log.info("EX-ALGO-OPEN %s %s %s %s units=%.6f arrival=%.4f "
                 "algo=%s children<=%d horizon=%.0fs",
                 p.parent_id, side, symbol, direction, total_units,
                 p.arrival_price, algo, n, self.horizon_sec)
        return p

    # ------------------------------------------------------------------
    def _pov_units(self, p: ParentOrder, market_volume_cum: float) -> float:
        seen = max(_f(market_volume_cum), 0.0)
        if p.last_seen_volume <= 0.0:
            p.last_seen_volume = seen
            # first POV child: seed with an even share so the parent
            # starts working immediately instead of waiting a full bar
            return p.total_units / self.max_children
        delta = max(seen - p.last_seen_volume, 0.0)
        p.last_seen_volume = seen
        return self.pov_rate * delta

    def next_slice(self, parent_id: str, now: float,
                   market_volume_cum: float = 0.0):
        """Returns a due ChildSlice or None. Enforces pacing, schedule
        position, horizon and terminal exactness."""
        p = self.parents.get(parent_id)
        if p is None or p.done:
            return None
        if now - p.created_ts > p.horizon_sec:
            self.abort(parent_id, "EX-ALGO-HORIZON: horizon expired")
            return None
        if p.last_child_ts and now - p.last_child_ts < self.min_interval_sec:
            return None
        remaining = p.total_units - p.submitted_units
        if remaining <= 0:
            return None

        if p.algo == "pov":
            units = min(self._pov_units(p, market_volume_cum), remaining)
        else:
            target = p.schedule[min(p.next_seq - 1, len(p.schedule) - 1)]
            units = min(max(target - p.submitted_units, 0.0), remaining)
        # sweep dust into this child; skip sub-economic slivers otherwise
        floor_units = p.total_units * self.min_child_units_frac
        if remaining - units < floor_units:
            units = remaining
        if units < floor_units and units < remaining:
            return None
        if units <= 0:
            return None

        p.last_child_ts = now
        seq = p.next_seq
        p.next_seq += 1
        p.submitted_units += units
        return ChildSlice(parent_id=parent_id, units=units, seq=seq,
                          n_total=self.max_children)

    # ---- lifecycle callbacks (main wires these to order events) --------
    def note_child_order(self, parent_id: str, position_id: str):
        p = self.parents.get(parent_id)
        if p is not None:
            p.child_ids.append(position_id)
            p.reject_streak = 0            # an accepted child ends the streak

    def note_child_rejected(self, parent_id: str, units: float, reason: str):
        """A child the firewall/pre-trade refused returns to the pool;
        two consecutive structural rejects abort the parent."""
        p = self.parents.get(parent_id)
        if p is None:
            return
        p.submitted_units = max(p.submitted_units - _f(units), 0.0)
        p.next_seq = max(p.next_seq - 1, 1)
        p.reject_streak += 1
        log.warning("EX-ALGO-CHILD-REJECT %s (streak %d): %s",
                    parent_id, p.reject_streak, reason)
        if p.reject_streak >= 2:
            # a structural veto (firewall/pretrade) will not clear on the next
            # slice; stop burning the pacing budget until horizon expiry
            self.abort(parent_id,
                       "EX-ALGO-REJECTS: two consecutive child rejects")

    def note_fill(self, parent_id: str, units: float, price: float):
        p = self.parents.get(parent_id)
        if p is None:
            return
        u, px = max(_f(units), 0.0), _f(price)
        p.filled_units += u
        p.fill_notional += u * px
        if p.filled_units >= p.total_units * 0.999:
            self._finish(p, "filled")

    def abort(self, parent_id: str, reason: str):
        p = self.parents.get(parent_id)
        if p is None or p.done:
            return
        p.abort_reason = reason
        self._finish(p, reason)

    def abort_all(self, reason: str):
        for pid in list(self.parents):
            self.abort(pid, reason)

    def _finish(self, p: ParentOrder, how: str):
        p.done = True
        self.parents.pop(p.parent_id, None)
        self.completed.append(p)
        if len(self.completed) > self._completed_cap:
            self.completed.pop(0)
        log.info("EX-ALGO-DONE %s (%s): filled %.6f/%.6f avg=%.4f "
                 "arrival=%.4f IS=%+.1fbps children=%d",
                 p.parent_id, how, p.filled_units, p.total_units,
                 p.avg_fill_price(), p.arrival_price, p.shortfall_bps(),
                 len(p.child_ids))

    # ------------------------------------------------------------------
    def active_parent_for(self, asset: str):
        for p in self.parents.values():
            if p.asset == asset and not p.done:
                return p
        return None

    def status(self) -> dict:
        act = [{"id": p.parent_id, "symbol": p.symbol, "side": p.side,
                "algo": p.algo, "done_pct": round(
                    100.0 * p.filled_units / p.total_units, 1)
                if p.total_units else 0.0,
                "is_bps": round(p.shortfall_bps(), 1),
                "age_s": round(time.time() - p.created_ts, 0)}
               for p in self.parents.values()]
        hist = [{"symbol": p.symbol, "algo": p.algo,
                 "is_bps": round(p.shortfall_bps(), 1),
                 "filled_pct": round(
                     100.0 * p.filled_units / max(p.total_units, 1e-12), 1)}
                for p in self.completed[-5:]]
        return {"enabled": self.enabled, "active": act, "recent": hist}
