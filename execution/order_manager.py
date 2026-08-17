"""
execution/order_manager.py — rev 2.0 (Assurance Build)

Non-blocking limit-order lifecycle manager, restructured as a FORMAL
STATE MACHINE. Rev 1 mutated `status` strings ad hoc; rev 2 routes
every status change through one guarded transition function with an
explicit legal-transition table:

    pending  -> partial | filled | cancelled | expired
    partial  -> partial | filled | cancelled
    filled | cancelled | expired -> (terminal; no transitions out)

An illegal transition is a code defect by definition: it is refused,
logged as OM-030, written to the audit chain, and the order is forced
to `cancelled` (the safe terminal — never fabricate a fill). This is
the mechanism that turns "a weird status bug silently corrupted the
book" into "one loud line pointing at the exact call site".

Everything else preserved exactly: submit/poll/open_orders/has_open/
refresh_deadman interface, ManagedOrder & FillEvent field names (the
persistence layer serializes them), the market-orders-are-escalated-
exits-only invariant, dead-man's switch cadence, batched QueryOrders,
and the dry-run fill simulator (crossing portion vs the real book +
distance-decayed passive fills) so paper trading exercises the same
code paths as live.

Rev 2 additions: fail-closed input validation (OM-010), audit records
for every submit/reject/terminal, bounded terminal-order history, and
venue-reject accounting surfaced in status().
"""

import decimal
import hashlib
import logging
import math
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from core.audit import get_audit
from core.codes import Code, tag
from core.sanitize import is_finite as _fin
from core.sanitize import is_finite_pos as _fin_pos, safe_float

log = logging.getLogger("liquiditybot.execution.order_manager")

EPS = 1e-12
_TERMINAL = ("filled", "cancelled", "expired")
_LEGAL = {
    "pending": {"partial", "filled", "cancelled", "expired"},
    "partial": {"partial", "filled", "cancelled"},
    "filled": set(), "cancelled": set(), "expired": set(),
}
_HISTORY_CAP = 512          # bounded terminal-order retention


def _passive_poll_prob(sf_base: float, dist_bps: float, sigma_bps: float,
                       ttl_sec: float, cal_life_sec: float) -> float:
    """TTL-normalized passive-fill hazard (owed 40, fill-sim audit
    2026-08-07 - the #1 P&L-integrity defect).

    p_cal = sf_base * exp(-d/sigma) was CALIBRATED by inverting a
    per-ORDER trade-through rate measured on ~25s order lives
    (outputs/fill_calibration.json, n_bar=5.0). Drawing that same p
    per poll over a 6h long-book life compounded to a guaranteed fill
    (1-(1-p)^4320 ~ 1.0 at any distance) - the ledger's 22/41 entries
    at exactly -50.0bps "improvement" and the positive BTC/ETH markout
    where passive maker fills must be negative.

    Normalizing the exponent by cal_life/ttl makes the per-ORDER fill
    probability TTL-invariant (poll cadence cancels: n_cal/n_ord ==
    cal_life/ttl). The exponent is clamped at 1.0 so shorter-than-
    calibrated orders keep the measured per-poll hazard and fill LESS
    over their shorter life, never more. The measured F(25s) becomes a
    conservative floor for long lives; genuine trade-through (the
    deterministic maker-cross path against the live book) still fills
    long orders whenever the market actually crosses. Execution-era
    boundary #3 (after the QA quarantine and XV-021).
    """
    sf_base = min(max(float(sf_base), 0.0), 1.0)
    d = max(float(dist_bps), 0.0)
    sig = max(float(sigma_bps), 1e-9)
    p_cal = min(max(sf_base * math.exp(-d / sig), 0.0), 1.0)
    if sf_base >= 1.0 or p_cal >= 1.0:
        # sf_base=1.0 is the DETERMINISTIC TEST MODE (bug-78 fixture
        # convention: pinned prob + queue off). Calibration can never
        # emit 1.0 (Wilson keeps estimates off the boundary), so the
        # boundary value bypasses TTL normalization and keeps every
        # deterministic fixture's guarantee byte-identical.
        return p_cal
    expo = min(max(float(cal_life_sec), 1.0) / max(float(ttl_sec), 1.0),
               1.0)
    p = 1.0 - (1.0 - p_cal) ** expo
    if not math.isfinite(p):
        return p_cal
    return min(max(p, 0.0), 1.0)


@dataclass
class ManagedOrder:
    order_id: str
    txid: Optional[str]
    asset: str
    pair: str
    symbol: str
    side: str
    price: float
    size: float
    filled: float = 0.0
    avg_price: float = 0.0
    fees_usd: float = 0.0
    status: str = "pending"   # pending | partial | filled | cancelled | expired
    purpose: str = "entry"    # entry | exit | hedge
    position_id: Optional[str] = None
    close_pct: float = 0.0
    created_ts: float = field(default_factory=time.time)
    reprices: int = 0
    post_only: bool = True
    leverage: float = 1.0
    ordertype: str = "limit"
    meta: dict = field(default_factory=dict)
    # DRY-RUN queue-position model (MP-7): resting depth AHEAD of this
    # order at its price when it first rested, ratcheted down as that
    # depth clears. -1.0 = not yet a resting order (crossing/unplaced).
    # Ignored entirely on the live path (the venue owns real queueing).
    queue_ahead: float = -1.0
    # arrival reference (implementation-shortfall benchmark): the trusted
    # mark at submit time. The slippage ledger books each fill vs THIS, not
    # vs the order's own limit — measuring vs the limit is tautological
    # (a marketable limit fills at/inside its limit, so it can never look
    # adverse; a passive limit fills AT its limit, so it is always 0). 0.0 =
    # no arrival mark recorded -> the ledger falls back to the limit price.
    arrival_ref: float = 0.0
    # per-order TTL override (C4 review, Critical #1a): None (the default)
    # means "use the shared self.timeout_sec" — byte-identical for every
    # pre-existing caller. A caller that needs a DIFFERENT resting lifetime
    # than the shared cadence (the long-horizon accumulation book's patient
    # maker bids, hours not the 5m book's 25s) passes ttl_sec= at submit()
    # instead of forcing a second OrderManager instance or a global config
    # split. Both _poll_live and _poll_dry read this the same way.
    ttl_sec: Optional[float] = None

    @property
    def remaining(self) -> float:
        return max(self.size - self.filled, 0.0)

    @property
    def fill_ratio(self) -> float:
        return self.filled / self.size if self.size > 0 else 0.0


@dataclass
class FillEvent:
    order: ManagedOrder
    fill_size: float
    fill_price: float
    final: bool


class OrderManager:
    def __init__(self, feed, config: dict, dry_run: bool = True,
                 seed: int = 42, firewall=None,
                 pair_meta: Optional[dict] = None,
                 pretrade_fee_bps: Optional[tuple[float, float]] = None):
        self.feed = feed
        self.dry_run = dry_run
        cfg = config or {}
        self.timeout_sec = float(cfg.get("order_timeout_sec", 25.0))
        self.max_reprices = int(cfg.get("max_reprices", 1))
        self.reprice_slip_bps = float(cfg.get("reprice_max_slip_bps", 8.0))
        self.min_fill_ratio = float(cfg.get("min_fill_ratio", 0.10))
        self.maker_fee_bps = float(cfg.get("maker_fee_bps", 25.0))
        self.taker_fee_bps = float(cfg.get("taker_fee_bps", 40.0))
        self.deadman_sec = int(cfg.get("deadman_timeout_sec", 60))
        # W2-9 remainder: periodic REPORT-ONLY reconciliation of the venue's
        # ACTUAL Kraken fee tier (TradeVolume) against BOTH configured bps
        # sources: order_manager.maker_fee_bps/taker_fee_bps ABOVE (what this
        # class actually books fees at) AND pretrade.maker_fee_bps/
        # taker_fee_bps (the pretrade EV gate's cost stack - the dangerous
        # side, since an underestimate there lets a net-losing trade look
        # profitable). `pretrade_fee_bps` is threaded in by main.py, which
        # has both config blocks in scope; a caller that omits it (legacy/
        # test construction) falls back to comparing the order_manager pair
        # against itself, so the pretrade dimension is inert rather than
        # silently wrong. config_guard enforces tolerance_bps in (0, 50],
        # interval_hours in [1, 168]. See check_fee_reconciliation for the
        # fail-safe contract.
        fr_cfg = cfg.get("fee_recon", {}) or {}
        self.fee_recon_enabled = bool(fr_cfg.get("enabled", True))
        self.fee_recon_tolerance_bps = float(fr_cfg.get("tolerance_bps", 1.0))
        self.fee_recon_interval_hours = float(fr_cfg.get("interval_hours", 24.0))
        if pretrade_fee_bps is not None:
            self.pretrade_maker_fee_bps = float(pretrade_fee_bps[0])
            self.pretrade_taker_fee_bps = float(pretrade_fee_bps[1])
        else:
            self.pretrade_maker_fee_bps = self.maker_fee_bps
            self.pretrade_taker_fee_bps = self.taker_fee_bps
        # None = "never run yet" (distinct from 0.0), so the very first
        # opportunity fires regardless of what `now` happens to be, then
        # every subsequent call is gated on the real elapsed interval.
        self._fee_recon_last_ts: Optional[float] = None
        self._fee_recon_result: Optional[dict] = None
        # fills booked OUTSIDE poll() (cancel-time final reconciliation)
        # queue here and are delivered by the next poll(), so every fill
        # still flows through the engine's single _handle_fill path
        self._deferred_events: list = []
        # DRY-RUN passive-fill realism (order_manager.sim_fill). The old
        # model fired a FLAT base probability regardless of how much depth
        # rested ahead of us (MP-7) — the exact Poisson-fill optimism the
        # queue-position literature (Huang-Lehalle-Rosenbaum, JASA 2015;
        # Moallemi-Yuan — the latter a working paper, not verified
        # peer-reviewed as of the 2026-07-29 literature audit)
        # shows over-credits passive fills, biasing candidate labels toward
        # entries that would never have filled. queue_aware gates the fill
        # on the depth ahead at placement clearing first; the base prob then
        # applies to the front-of-queue remainder. All literals lifted here
        # from the decision path (overfit discipline).
        sf = cfg.get("sim_fill", {}) or {}
        self.sf_base = min(max(float(sf.get("passive_base_prob", 0.45)),
                               0.0), 1.0)
        self.sf_frac_min = min(max(float(sf.get("fill_frac_min", 0.3)),
                                   0.0), 1.0)
        self.sf_frac_max = min(max(float(sf.get("fill_frac_max", 1.0)),
                                   self.sf_frac_min), 1.0)
        # OFF by default: queue-gating changes DRY-RUN fill behavior, which
        # changes the label distribution the model learns from — a conscious
        # switch (like inventory_skew's shadow default), not a silent flip.
        # Enable in config after review; it wants a quant re-baseline.
        self.sf_queue_aware = bool(sf.get("queue_aware", False))
        # front-of-queue yardstick: eligible once depth ahead has cleared to
        # within this multiple of our OWN order size (scale-free). 1.0 = "the
        # wall ahead is no bigger than us" ~ at the touch.
        self.sf_queue_tol_frac = max(float(sf.get("queue_tol_frac", 1.0)),
                                     0.0)
        # queue drains by the MAX of (observed depth-ahead shrink between
        # snapshots) and (a volatility-driven baseline turnover) — an
        # aggregate book that looks static between snapshots is still being
        # continuously traded and refilled, so a purely observed-shrink
        # ratchet would starve fills on any static-book replay. Baseline is
        # a geometric fraction of the remaining queue per poll, scaled by
        # sigma vs the reference (higher vol -> faster turnover, the
        # queue-reactive insight).
        self.sf_queue_drain = min(max(float(sf.get("queue_drain_frac",
                                                   0.20)), 0.0), 1.0)
        self.sf_sigma_ref_bps = max(float(sf.get("sigma_ref_bps", 30.0)),
                                    1.0)
        # the order life the passive hazard was CALIBRATED at (n_bar=5.0
        # polls x 5s, outputs/fill_calibration.json). _passive_poll_prob
        # normalizes each order's per-poll hazard by cal_life/ttl so the
        # per-ORDER fill probability matches calibration at ANY ttl
        # (owed 40: the 6h long-book life previously compounded
        # 0.048/poll into a guaranteed fill at -50bps).
        self.sf_cal_life_sec = max(float(sf.get("calibration_life_sec",
                                                25.0)), 1.0)
        # OWED 57 / EXECUTION-ERA BOUNDARY #4 — THE DOUBLE-COUNT.
        # The passive hazard and _sim_maker_cross model the SAME physical
        # event. calibrate_fills.py measures f = "how often the market
        # actually crossed a hypothetical resting limit within its life"
        # from recorded book frames, and core.fill_calibration.
        # invert_base_prob solves sf_base so the HAZARD ALONE reproduces f
        # over n_bar polls. But _poll_dry ALSO fills deterministically
        # whenever the live book crosses — the very event f counts — and the
        # hazard only ever runs INSIDE `if book:`, so it is purely additive
        # to an observed cross rather than a model of anything the snapshot
        # cannot see. Combined per-order rate is 1-(1-f)^2 = 2f - f^2, i.e.
        # 22.0% against an 11.66% target: 1.88x at the touch, approaching
        # 2x as f falls, and 57.2% of post-only fills rest within 5bps.
        # Default False = the book is ground truth. True restores the
        # pre-boundary behaviour so a pre-#4 cohort can be reproduced
        # exactly; it is NOT a tuning knob.
        self.sf_hazard_with_book = bool(sf.get("passive_hazard_with_book",
                                               False))
        self.firewall = firewall
        self.pair_meta = pair_meta or {}
        self.latency_ms: float = 0.0
        self.venue_rejects: int = 0
        # OM-013 telemetry: a formatted price/volume string that parses to
        # ZERO was refused before the venue call (or dry-run registration).
        # Same shape as venue_rejects/deadman_failures — a rising count means
        # some pair's precision metadata is starving orders (see submit()).
        self.zero_format_rejects: int = 0
        # OM-090 telemetry: venue CancelOrder calls that returned NO
        # confirmation while local state was forced terminal. Each one may
        # be a GTC orphan still resting at the venue and invisible to
        # open_orders() — see _note_cancel_result. Live-only; a rising
        # count is an operator signal to reconcile against the venue.
        self.cancel_unconfirmed: int = 0
        # execution-quality ledger (§3 telemetry): every fill increments a
        # maker/taker counter + notional, and books signed slippage as the
        # implementation shortfall vs the ARRIVAL mark (positive bps = adverse:
        # paid above arrival on a buy / sold below it on a sell; negative =
        # price improvement). Referencing arrival — not the order's own limit —
        # is what makes this a real slippage meter (a limit reference is
        # tautologically non-adverse). Rolling window, session-scoped like
        # venue_rejects. Telemetry only (no decision reads it).
        self.maker_fills: int = 0
        self.taker_fills: int = 0
        self.maker_notional_usd: float = 0.0
        self.taker_notional_usd: float = 0.0
        # terminal-outcome tally (2026-08-17 funnel telemetry): every order
        # that reaches a CLEAN terminal via the state machine (the same
        # branch that audits OM-000/OM-040), and the subset that died as a
        # timeout-cancel ("expired" = OM-040, the resting maker sat its
        # whole TTL unfilled). 68% of terminals in a 48h audit window were
        # OM-040 with nothing on the glass saying so. Session-scoped like
        # venue_rejects; TELEMETRY ONLY — no decision path reads these.
        self.terminal_orders: int = 0
        self.timeout_cancels: int = 0
        self._slip_bps: deque = deque(maxlen=200)
        self._orders: dict = {}
        self._terminal_seq: list = []          # bounded eviction order
        self._deadman_refreshed = 0.0
        self._deadman_failures = 0
        self._rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # state machine core — the ONLY writer of order.status
    # ------------------------------------------------------------------
    def _transition(self, order: ManagedOrder, new: str, why: str = "") -> bool:
        old = order.status
        if new == old and new == "partial":
            return True                       # partial -> partial: fills accrue
        if new not in _LEGAL.get(old, set()):
            msg = tag(Code.OM_ILLEGAL_TRANSITION,
                      f"{order.order_id} {old} -> {new} refused ({why}); "
                      f"forcing cancelled")
            log.error(msg)
            get_audit().log("order_manager", Code.OM_ILLEGAL_TRANSITION,
                            msg, {"order_id": order.order_id})
            if old not in _TERMINAL:
                order.status = "cancelled"
                self._retire(order)
            return False
        order.status = new
        if new in _TERMINAL:
            self._retire(order)
            # funnel telemetry: mirrors the OM-000/OM-040 audit split below
            # 1:1 (the forced-cancel OM-030 path above is NOT counted here —
            # these are CLEAN terminals). Counting only; the transition
            # itself is unchanged.
            self.terminal_orders += 1
            if new == "expired":
                self.timeout_cancels += 1
            get_audit().log("order_manager", Code.OM_TIMEOUT_CANCEL
                            if new == "expired" else Code.OM_CLEAN_TERMINAL,
                            f"{order.order_id} {order.side} {order.pair} "
                            f"terminal={new} fill_ratio="
                            f"{order.fill_ratio:.2f} ({why})",
                            {"purpose": order.purpose,
                             "avg_price": order.avg_price,
                             "fees_usd": round(order.fees_usd, 4),
                             # full lifecycle for the trace pusher: one
                             # OTLP span per order needs both endpoints
                             # and enough attributes for RED analysis
                             "order_id": order.order_id,
                             "pair": order.pair, "side": order.side,
                             "terminal": new,
                             "created_ts": order.created_ts,
                             "fill_ratio": round(order.fill_ratio, 4),
                             "reprices": order.reprices,
                             # fee-RATE measurability (2026-07-28 cost
                             # truth): fees_usd alone cannot yield bps —
                             # 466 historical fills were population-
                             # unmeasurable without notional, forcing the
                             # cost report onto the biased postmortem
                             # subset. Every terminal record now carries
                             # the fill's own notional.
                             "filled_units": round(order.filled, 8),
                             "notional_usd": round(
                                 order.filled * order.avg_price, 4)})
        return True

    def _retire(self, order: ManagedOrder):
        """Bounded terminal-order retention: keep the last _HISTORY_CAP."""
        self._terminal_seq.append(order.order_id)
        while len(self._terminal_seq) > _HISTORY_CAP:
            old_id = self._terminal_seq.pop(0)
            gone = self._orders.get(old_id)
            if gone is not None and gone.status in _TERMINAL:
                del self._orders[old_id]

    # ------------------------------------------------------------------
    def _fmt_price(self, pair: str, price: float,
                   side: Optional[str] = None) -> str:
        """Venue price string, SIDE-AWARE (MP-5): symmetric round-half-even
        could nudge a buy limit UP (or a sell DOWN) through the touch — a
        post-only reject live, or an unintended cross. Buys floor, sells
        ceil: rounding only ever moves the price AWAY from aggression.
        side=None keeps the legacy symmetric rounding (logs/display)."""
        d = int((self.pair_meta.get(pair) or {}).get("price_decimals", 2))
        if side in ("buy", "sell") and _fin(price):
            q = decimal.Decimal(str(price)).quantize(
                decimal.Decimal(1).scaleb(-d),
                rounding=(decimal.ROUND_FLOOR if side == "buy"
                          else decimal.ROUND_CEILING))
            return f"{q:.{d}f}"
        return f"{price:.{d}f}"

    def _fmt_volume(self, pair: str, size: float) -> str:
        """Venue volume string, ALWAYS floored (MP-5): round-half-even could
        round the submitted size UP past what the sizer approved — on an exit
        that is an oversell the venue may reject (or worse, fill). Truncation
        is safe: positions are born from fills at this same lot precision, so
        flooring a full-position exit is a no-op, never stranded dust."""
        d = int((self.pair_meta.get(pair) or {}).get("lot_decimals", 8))
        if _fin(size):
            q = decimal.Decimal(str(size)).quantize(
                decimal.Decimal(1).scaleb(-d), rounding=decimal.ROUND_FLOOR)
            return f"{q:.{d}f}"
        return f"{size:.{d}f}"

    def _ordermin(self, pair: str) -> float:
        return float((self.pair_meta.get(pair) or {}).get("ordermin", 0.0))

    @staticmethod
    def _userref(order_id: str) -> str:
        """Kraken userref (int32) derived stably from the internal order id:
        identical across processes/restarts, unlike salted str hash()."""
        digest = hashlib.sha256(order_id.encode("utf-8")).digest()
        return str(int.from_bytes(digest[:4], "big") % 2_000_000_000)

    def refresh_deadman(self, now: float):
        """Re-arm Kraken's CancelAllOrdersAfter every fast cycle (live).
        Refresh at half the timeout so one missed cycle never lets the
        switch fire spuriously. Repeated failures escalate (OM-050)."""
        if self.dry_run or self.deadman_sec <= 0:
            return
        if now - self._deadman_refreshed < self.deadman_sec / 2.0:
            return
        if self.feed.cancel_all_orders_after(self.deadman_sec):
            self._deadman_refreshed = now
            self._deadman_failures = 0
        else:
            self._deadman_failures += 1
            msg = tag(Code.OM_DEADMAN_FAIL,
                      f"refresh failed x{self._deadman_failures}; venue "
                      f"will cancel all resting orders in ~"
                      f"{self.deadman_sec}s (designed fail-safe, but "
                      f"investigate connectivity)")
            log.error(msg)
            if self._deadman_failures >= 3:
                get_audit().log("order_manager", Code.OM_DEADMAN_FAIL, msg,
                                {"failures": self._deadman_failures})

    @staticmethod
    def _timeout_for(order: ManagedOrder, default: float) -> float:
        """Effective resting-order lifetime: `order.ttl_sec` when set
        (Critical #1a's per-order override), else the shared `default`
        (self.timeout_sec) — the ONE place both _poll_live and _poll_dry
        read the timeout, so they can never drift from each other on
        which order gets which lifetime."""
        return order.ttl_sec if order.ttl_sec is not None else default

    # ------------------------------------------------------------------
    def open_orders(self) -> list:
        return [o for o in self._orders.values()
                if o.status in ("pending", "partial")]

    def has_open(self, asset: str, purpose: Optional[str] = None,
                book: Optional[str] = None) -> bool:
        """`book` (C4 review, Minor #10): filters on the STRATEGY book tag
        threaded through `meta["book"]` (defaults "5m", matching main.
        _handle_fill's own `order.meta.get("book", "5m")` convention) —
        NOT the `book` param of `submit()` (that one is the raw Kraken
        order-book dict, an unrelated same-named parameter). None (the
        default) preserves every pre-existing caller's behavior
        byte-identically: purpose-only filtering, book-blind. Needed once
        the long-horizon accumulation book's resting bids started living
        for hours instead of ~25s — without this, a resting LONG-book
        entry order silently blocked the 5m book's own has_open("entry")
        skip-check for the same asset for that entire window."""
        return any(o.asset == asset and (purpose is None
                                         or o.purpose == purpose)
                   and (book is None or o.meta.get("book", "5m") == book)
                   for o in self.open_orders())

    def _book_venue_segment(self, order: ManagedOrder, vol_exec: float,
                            avg: float, fee=None):
        """Book the venue's CUMULATIVE (vol_exec, avg price) into this order
        as one fill segment (the delta vs what's already booked). Kraken's
        `price` is the cumulative average across all fills of the order;
        recover THIS segment's own execution price from the average delta
        BEFORE overwriting, else every later segment is booked at the blend
        of earlier ones (smeared slippage, diluted worst_slip, wrong
        notional split). Fees and the FILL EVENT both use the SEGMENT price:
        booking the cumulative average smears the basis toward the earliest
        fill (buy 1@100 then 1@110 booked as entry 102.50 instead of 105.00
        — audit MP-1/MP-3 2026-07-17), corrupting stops, tiers, realized
        PnL, and every label downstream. Returns the FillEvent, or None
        when nothing new filled.

        `fee` (W2-9): Kraken's QueryOrders `fee` is ALSO a cumulative,
        USD/quote-denominated total across the order's fills — same shape
        as `vol_exec`/`price`, so `order.fees_usd` (itself a cumulative
        running total; main._handle_fill diffs it via order.meta["_fees_
        seen"/"_fees_booked"]) is overwritten with it directly, exactly
        like `order.filled = vol_exec` above. This is real fee-tier-aware
        accounting, replacing the static config-bps estimate that ignores
        Kraken's actual tier and mis-books a marketable limit's passively-
        filled remainder at taker bps. Absent/non-finite/negative `fee`
        (dry-run never passes one; a degraded venue response) falls back
        to the previous bps-estimate behavior unchanged."""
        new_fill = vol_exec - order.filled
        if new_fill <= EPS:
            return None
        prev_avg, prev_filled = order.avg_price, order.filled
        order.avg_price = avg if avg > 0 else order.price
        order.filled = vol_exec
        seg_px = order.avg_price
        if avg > 0 and prev_filled > EPS:
            cand = (vol_exec * avg - prev_filled * prev_avg) / new_fill
            if math.isfinite(cand) and cand > 0:
                seg_px = cand
        # Kraken returns numbers as STRINGS (same hardening as vol_exec/avg
        # above via safe_float): a garbage/non-finite fee must degrade to
        # the bps estimate, never poison fees_usd or silently accept a
        # negative figure (fees are never negative).
        venue_fee = safe_float(fee, default=-1.0) if fee is not None else -1.0
        if venue_fee >= 0.0:
            order.fees_usd = venue_fee
        else:
            order.fees_usd += new_fill * seg_px * \
                (self.maker_fee_bps if order.post_only
                 else self.taker_fee_bps) / 1e4
        self._note_exec(order.post_only, new_fill * seg_px,
                        seg_px, order.arrival_ref or order.price,
                        order.side,
                        # dust guard context: segment prices are recovered
                        # from cumulative-average differences, so a dust
                        # segment's slip is quantization noise (2026-07-29
                        # defect-category audit)
                        order_notional_usd=order.size * order.price)
        self._transition(order, "partial", "venue fill")
        return FillEvent(order, new_fill, seg_px, final=False)

    def _final_reconcile(self, order: ManagedOrder) -> list:
        """FINAL RECONCILIATION after a venue CancelOrder — the shared last
        look for BOTH cancel paths (explicit `cancel_order` preemption and
        `_poll_live`'s timeout expiry).

        A fill can land between the last QueryOrders snapshot and the venue
        cancel taking effect; transitioning terminal without a last look
        DROPS it permanently — the order leaves open_orders() and is never
        polled again, while `FillEvent(order, 0.0, final=True)` books nothing
        (main._handle_fill gates both accounting branches on
        `fill_size > EPS`). An entry lost that way is untracked live
        inventory with no stop/tiers; an exit lost that way is a phantom
        local position whose every escape the venue rejects.

        The window is NOT a rare race on the timeout path: poll() takes ONE
        batched QueryOrders snapshot at the top, then each timing-out order
        issues its own throttled CancelOrder round-trip afterwards, so the
        state being finalized off is already stale by construction.

        Returns the FillEvents recovered (possibly empty). When the order
        turns out to be fully filled it is transitioned to `filled` HERE, so
        callers must re-check `order.status` before forcing their own
        terminal transition. Best-effort: a failed/garbage query returns []
        and leaves last-known fill state, keeping the forced-terminal
        behavior (a blocked escape is the worse failure)."""
        if self.dry_run or not getattr(order, "txid", None):
            return []
        events: list = []
        try:
            res = self._timed_private("QueryOrders",
                                      {"txid": order.txid}) or {}
            info = res.get(order.txid) or {}
            vol_exec = safe_float(info.get("vol_exec"),
                                  default=order.filled, lo=0.0)
            avg = safe_float(info.get("price"),
                             default=order.avg_price, lo=0.0)
            ev = self._book_venue_segment(order, vol_exec, avg,
                                          fee=info.get("fee"))
            if ev is not None:
                events.append(ev)
            if order.remaining <= EPS:
                # it fully filled before the cancel took effect - that
                # is a FILL, not a cancel; finalize it as one
                self._transition(order, "filled",
                                 "venue filled before cancel")
                events.append(FillEvent(order, 0.0, order.avg_price,
                                        final=True))
        except Exception:                       # noqa: BLE001
            log.exception("final QueryOrders failed for %s — cancelling "
                          "with last-known fill state", order.txid)
        return events

    def _note_cancel_result(self, result, order: ManagedOrder,
                            path: str) -> bool:
        """Record whether a venue CancelOrder was actually CONFIRMED.

        `feed._private_post` never raises: on a rate limit, a 5xx, or a
        Kraken error payload it returns None. Both cancel paths discarded
        that result and forced the local state terminal anyway, so the
        order left open_orders() and was never queried again - while the
        real order, submitted GTC (no expiretm), kept resting at the venue.
        A healthy bot then keeps re-arming CancelAllOrdersAfter every ~30s,
        so the deadman that is supposed to back this up never fires. A
        later venue fill is invisible: an orphaned ENTRY is untracked
        inventory with no stop; an orphaned EXIT means the venue is flat
        while the book says open, and the ladder's next rung double-sells.

        The terminal transition still happens (a blocked escape is the
        worse failure, per the cancel_order contract). This makes the
        residue AUDIBLE instead of silent: an OM-090 disposition on the
        hash-chained trail plus a counter the boards can carry. Dry-run
        posts nothing, so `result is None` there is normal and ignored.
        """
        if self.dry_run:
            return True
        if result is not None:
            return True
        self.cancel_unconfirmed += 1
        detail = tag(Code.OM_CANCEL_UNCONFIRMED,
                     f"{order.txid} ({path}): venue returned no cancel "
                     f"confirmation - local state forced terminal, the "
                     f"order MAY still rest at the venue as a GTC orphan")
        log.error(detail)
        try:
            get_audit().log("execution", Code.OM_CANCEL_UNCONFIRMED, detail,
                            {"txid": order.txid, "path": path,
                             "symbol": order.symbol, "side": order.side,
                             "purpose": order.purpose,
                             "remaining": float(order.remaining)})
        except Exception:                   # noqa: BLE001 - never block a cancel
            log.exception("audit of an unconfirmed cancel failed")
        return False

    def take_deferred(self) -> list:
        """Drain and return the deferred-fill queue (fills booked OUTSIDE
        poll() by `_final_reconcile`). poll() drains the same queue at the
        top of every cycle; a caller that must OBSERVE a late fill before
        the next poll drains it here and feeds each event through the very
        same engine `_handle_fill` path, so the single-application invariant
        holds either way.

        The caller with that need is main._submit_exit: it preempts a
        resting maker profit-take via cancel_order() and then sizes the
        replacement escape off `pos.size` a few lines later — a fill
        recovered by the preemption's last look is booked into
        `order.filled` but not yet into the position, so the escape is sized
        off a stale (too large) `pos.size`. Draining here before sizing
        closes that intra-cycle window."""
        events, self._deferred_events = self._deferred_events, []
        return events

    def cancel_order(self, order: ManagedOrder, reason: str = "cancelled") -> bool:
        """Cancel ONE resting order (venue + local state), emitting no fill.
        Used to PREEMPT a non-urgent resting maker exit so a risk-off exit can
        take its place. Live-safe: a failed venue cancel still forces the local
        terminal transition — leaving the escape blocked is the worse failure,
        and the deadman switch + order timeout are the venue-side backstop. Any
        already-filled portion stands (it was booked on prior polls); only the
        resting remainder is cancelled. Returns True when the order was open and
        is now terminal."""
        if order.status not in ("pending", "partial"):
            return False
        if not self.dry_run and getattr(order, "txid", None):
            try:
                self._note_cancel_result(
                    self._timed_private("CancelOrder", {"txid": order.txid}),
                    order, "preempt")
            except Exception:                       # noqa: BLE001
                log.exception("CancelOrder failed for %s — forcing local "
                              "cancel (%s)", order.txid, reason)
                self.cancel_unconfirmed += 1
            # last look (see _final_reconcile). Recovered fills queue on
            # _deferred_events and are delivered by the next poll(), so they
            # keep flowing through the engine's single _handle_fill path;
            # take_deferred() lets a same-cycle caller observe them sooner.
            self._deferred_events.extend(self._final_reconcile(order))
            if order.status == "filled":
                return True
        return self._transition(order, "cancelled", reason)

    def _note_exec(self, maker: bool, notional_usd: float,
                   fill_price: float, ref_price: float, side: str,
                   order_notional_usd: float = 0.0) -> None:
        """Book one fill into the execution-quality ledger. Slippage is the
        signed implementation shortfall vs `ref_price` — the ARRIVAL mark at
        submit (callers pass `order.arrival_ref or order.price`): positive bps
        = adverse (paid above / sold below arrival), negative = price
        improvement. Referencing the order's own limit instead is tautological
        (a marketable limit fills inside its limit; a passive one fills at it),
        which is why this books vs arrival. Never raises."""
        try:
            n = float(notional_usd)
            # max() does NOT sanitize NaN (max(nan, 0) is nan): one bad
            # notional would poison the accumulator forever and a NaN gauge
            # invalidates the entire OTLP push batch. Finite-or-zero only.
            n = n if (math.isfinite(n) and n > 0.0) else 0.0
            if maker:
                self.maker_fills += 1
                self.maker_notional_usd += n
            else:
                self.taker_fills += 1
                self.taker_notional_usd += n
            fill, ref = float(fill_price), float(ref_price)
            if math.isfinite(fill) and math.isfinite(ref) and ref > 0 \
                    and fill > 0:
                sgn = 1.0 if side == "buy" else -1.0
                # (slip, notional) pairs: the unweighted mean stays the
                # legacy avg_slip_bps; the notional-weighted companion
                # (Cochran ch.6 / Bessembinder 2003, 2026-07-29 defect-
                # category audit) stops $10 probe fills from outvoting
                # conviction tickets 4x their size in the operator's
                # slip read. Zero-notional fills reach the ledger only
                # via the legacy call path (order_notional_usd=0 ->
                # dust_floor 0 -> everything admitted, legacy-identical);
                # with a real notional the dust guard below drops them
                # from BOTH stats (wave-2/3 verify wording fix). DUST
                # GUARD
                # (same audit, Higham-class): a segment under 1% of the
                # order recovers its price from the difference of two
                # near-equal products, amplifying venue quantization of
                # the cumulative average into bps-scale slip noise -
                # skip the LEDGER append only (fees/notional booking
                # above stay exact by construction).
                dust_floor = 0.01 * float(order_notional_usd or 0.0)
                if n >= dust_floor or dust_floor <= 0.0:
                    self._slip_bps.append(
                        (sgn * (fill - ref) / ref * 1e4, n))
        except (TypeError, ValueError):
            pass

    def status(self) -> dict:
        fills = self.maker_fills + self.taker_fills
        pairs = list(self._slip_bps)
        slips = [s for s, _ in pairs]
        w_num = sum(s * n for s, n in pairs)
        w_den = sum(n for _, n in pairs)
        return {"open": len(self.open_orders()),
                "tracked": len(self._orders),
                "latency_ms": round(self.latency_ms, 1),
                "venue_rejects": self.venue_rejects,
                "zero_format_rejects": self.zero_format_rejects,
                "cancel_unconfirmed": self.cancel_unconfirmed,
                "deadman_failures": self._deadman_failures,
                # terminal-outcome funnel (2026-08-17): clean terminals +
                # the OM-040 timeout-cancel subset, for the timeout-share
                # panel (extend-don't-break: new keys, telemetry only)
                "terminal_orders": self.terminal_orders,
                "timeout_cancels": self.timeout_cancels,
                # execution quality (§3): maker/taker split + rolling slippage
                "maker_fills": self.maker_fills,
                "taker_fills": self.taker_fills,
                "maker_share": round(self.maker_fills / fills, 4)
                if fills else None,
                "maker_notional_usd": round(self.maker_notional_usd, 2),
                "taker_notional_usd": round(self.taker_notional_usd, 2),
                "avg_slip_bps": round(sum(slips) / len(slips), 2)
                if slips else None,
                # dollar-weighted twin: what a unit of traded notional
                # actually paid (extend-don't-break: new key, old key
                # keeps its per-fill semantics)
                "slip_bps_notional_weighted": round(w_num / w_den, 2)
                if w_den > 0 else None,
                "worst_slip_bps": round(max(slips), 2) if slips else None,
                # W2-9 remainder: last fee-tier reconciliation result (None
                # until the first one runs) -> status.json -> telemetry.
                "fee_recon": self._fee_recon_result}

    def check_fee_reconciliation(self, now: float) -> None:
        """W2-9 remainder: periodic REPORT-ONLY comparison of the account's
        ACTUAL Kraken fee tier (TradeVolume) against BOTH configured bps
        sources - order_manager.maker_fee_bps/taker_fee_bps (self.*_fee_bps,
        what this class books fees at) AND pretrade.maker_fee_bps/
        taker_fee_bps (self.pretrade_*_fee_bps, the pretrade EV gate's cost
        stack - the semantically critical pair, since an underestimate there
        is what lets a net-losing trade clear the gate). A mismatch on
        EITHER source, for EITHER maker or taker, flags. Timed off `now` as
        INJECTED by main.hourly_cycle - never a wall-clock read here (EX-8).
        A mismatch only ever WARNs and emits one registered audit event
        (OM-080); it never mutates config.json at runtime (lifted-threshold
        discipline - the operator re-tunes the configured bps consciously).

        Fail-safe (never raises into hourly_cycle, never spams):
          - disabled, or still inside the interval -> silent return.
          - the interval is claimed BEFORE the venue call, so a repeated
            failure (no creds, network, garbage response) retries at most
            once per interval, never every hourly_cycle tick.
          - no resolved Kraken credentials (DRY_RUN or live, doesn't
            matter - this is a read-only account query) -> debug skip.
          - TradeVolume unreachable / unparseable -> debug skip; the last
            good result (if any) is left untouched in stats.
          - any other exception (network, malformed response, a partial
            stub in tests) -> caught here, debug-logged, skipped.
        """
        try:
            if not self.fee_recon_enabled:
                return
            interval_sec = self.fee_recon_interval_hours * 3600.0
            if (self._fee_recon_last_ts is not None
                    and now - self._fee_recon_last_ts < interval_sec):
                return
            self._fee_recon_last_ts = now
            if not self.feed.has_private_credentials():
                log.debug("fee reconciliation skipped: no Kraken API "
                         "credentials configured")
                return
            pairs = sorted(self.pair_meta.keys())
            if not pairs:
                log.debug("fee reconciliation skipped: no pairs configured")
                return
            tiers = self.feed.get_trade_fee_tiers(pairs)
            if not tiers:
                log.debug("fee reconciliation skipped: TradeVolume "
                         "unavailable or unparseable")
                return
            pair_results = {}
            mismatched = []
            worst_delta_bps = 0.0
            for pair, actual in tiers.items():
                actual_maker = actual["maker_bps"]
                actual_taker = actual["taker_bps"]
                # dangerous direction (configured < actual: the relevant
                # gate is underestimating cost) flags regardless of
                # tolerance; otherwise only a divergence PAST tolerance in
                # either direction is worth an operator's attention. Each
                # side is checked against BOTH configured sources
                # independently - a mismatch on either flags the pair.
                checks = (
                    ("maker_om", self.maker_fee_bps, actual_maker),
                    ("maker_pretrade", self.pretrade_maker_fee_bps,
                     actual_maker),
                    ("taker_om", self.taker_fee_bps, actual_taker),
                    ("taker_pretrade", self.pretrade_taker_fee_bps,
                     actual_taker),
                )
                mismatch_sources = []
                for label, configured, actual_bps in checks:
                    delta = abs(configured - actual_bps)
                    if configured < actual_bps or delta \
                            > self.fee_recon_tolerance_bps:
                        mismatch_sources.append(label)
                        worst_delta_bps = max(worst_delta_bps, delta)
                pair_results[pair] = {
                    "maker_configured_om_bps": self.maker_fee_bps,
                    "maker_configured_pretrade_bps":
                        self.pretrade_maker_fee_bps,
                    "maker_actual_bps": round(actual_maker, 4),
                    "taker_configured_om_bps": self.taker_fee_bps,
                    "taker_configured_pretrade_bps":
                        self.pretrade_taker_fee_bps,
                    "taker_actual_bps": round(actual_taker, 4),
                    "mismatch": bool(mismatch_sources),
                    "mismatch_sources": mismatch_sources,
                }
                if mismatch_sources:
                    mismatched.append(pair)
            self._fee_recon_result = {"ts": now,
                                      "verdict": "mismatch" if mismatched
                                      else "ok",
                                      "pairs": pair_results}
            if mismatched:
                # compact human summary (pair count + worst delta) - the
                # full per-pair/per-source detail lives in the audit
                # PAYLOAD only, so this line can't grow with pair count.
                msg = tag(Code.OM_FEE_RECON_MISMATCH,
                         f"configured vs actual Kraken fee tier diverged "
                         f"on {len(mismatched)} pair(s) (worst delta "
                         f"{worst_delta_bps:.2f}bps, tolerance="
                         f"{self.fee_recon_tolerance_bps}bps)")
                log.warning(msg)
                get_audit().log("order_manager", Code.OM_FEE_RECON_MISMATCH,
                                msg, {"pairs": pair_results,
                                      "tolerance_bps":
                                      self.fee_recon_tolerance_bps})
        except Exception:                            # noqa: BLE001
            log.debug("fee reconciliation skipped: unexpected error",
                     exc_info=True)

    def _timed_private(self, endpoint: str, data: dict):
        t0 = time.monotonic()
        result = self.feed._private_post(endpoint, data)
        # monotonic + clamp: a wall-clock step must not inject a negative/huge
        # RTT into the order-path latency EWMA (drives the venue-latency panel
        # and the deadman/escalation health read). Finiteness is checked on the
        # RAW sample before the clamp (max(0.0, nan) would swallow a NaN to 0).
        raw = (time.monotonic() - t0) * 1000.0
        if math.isfinite(raw):
            self.latency_ms = 0.7 * self.latency_ms + 0.3 * max(0.0, raw) \
                if self.latency_ms else max(0.0, raw)
        return result

    # ------------------------------------------------------------------
    def submit(self, asset: str, symbol: str, pair: str, side: str,
               price: float, size: float, purpose: str = "entry",
               position_id: Optional[str] = None, close_pct: float = 0.0,
               post_only: bool = True, leverage: float = 1.0,
               book: Optional[dict] = None, sigma_bar_pct: float = 0.05,
               ordertype: str = "limit", ref_price: float = 0.0,
               equity: float = 0.0,
               meta: Optional[dict] = None,
               now: Optional[float] = None,
               ttl_sec: Optional[float] = None) -> Optional[ManagedOrder]:
        # ---- fail-closed input validation (OM-010) ---------------------
        if side not in ("buy", "sell") or purpose not in ("entry", "exit",
                                                          "hedge") \
                or ordertype not in ("limit", "market"):
            log.error(tag(Code.OM_INVALID_INPUT,
                          f"side={side!r} purpose={purpose!r} "
                          f"type={ordertype!r}"))
            return None
        if not _fin_pos(size) or (ordertype == "limit"
                                  and not _fin_pos(price)):
            log.error(tag(Code.OM_INVALID_INPUT,
                          f"{pair} {side} size={size!r} price={price!r}"))
            return None
        if ordertype == "market" and purpose != "exit":
            # invariant: market orders exist ONLY as the last rung of the
            # exit-escalation ladder
            log.error(tag(Code.OM_MARKET_REFUSED,
                          f"purpose={purpose} — entries/hedges are always "
                          f"limits"))
            return None
        if not _fin_pos(price):
            price = ref_price            # market-order bookkeeping price

        # ---- risk firewall: independent last line on EVERY order --------
        requested_size = size
        if self.firewall is not None:
            # Pass ref_price THROUGH untouched — never `ref_price or price`.
            # Substituting the order's OWN price as the reference makes the
            # collar deviation identically zero (|price-price|=0), silently
            # DEFEATING both the price collar AND the firewall's fail-closed
            # entry/hedge refusal on a missing mark (FW-060). A genuinely
            # absent reference must reach the firewall as absent so it can
            # decide: refuse new risk (fail closed) / let an exit pass uncollared.
            verdict = self.firewall.check(
                pair=pair, side=side, purpose=purpose, price=price,
                size=size, ref_price=ref_price, equity=equity)
            if not verdict.allowed:
                log.error(tag(Code.OM_FIREWALL_REJECT,
                              f"{side} {size:.6f} {pair} @ {price!r} "
                              f"({purpose}): {list(verdict.reasons)}"))
                return None
            price, size = verdict.price, verdict.size

        # ---- venue minimum: below-ordermin is a guaranteed reject --------
        omin = self._ordermin(pair)
        if omin > 0 and purpose == "exit" and size < omin <= requested_size:
            # EX-4: the firewall's notional clamp shrank a VIABLE exit
            # below the venue minimum - submitting would reject, the caller
            # never escalates a None, and the position loops unexitable.
            # The venue minimum is the smallest executable escape: floor
            # back up to it (never above the caller's requested size, so an
            # oversell is impossible; the cap overshoot is ordermin-sized
            # notional - cents against an un-closeable position).
            log.warning(tag(Code.OM_BELOW_ORDERMIN,
                            f"exit clamped to {size:.8f} {pair} < venue min "
                            f"{omin} - floored back to the minimum "
                            f"executable escape"))
            size = omin
        if omin > 0 and size < omin:
            if purpose == "exit":
                log.warning(tag(Code.OM_BELOW_ORDERMIN,
                                f"exit {size:.8f} {pair} < venue min "
                                f"{omin} — dust remainder; caller treats "
                                f"position as flat"))
            else:
                log.info(tag(Code.OM_BELOW_ORDERMIN,
                             f"{size:.8f} {pair} < venue min {omin} — "
                             f"skipped"))
            return None

        # ---- post-format executable-size guard (OM-013, W2-8) -----------
        # _fmt_price/_fmt_volume FLOOR toward zero at the pair's venue
        # precision. The ordermin gates above key on the RAW float and are
        # skipped entirely when pair metadata omits ordermin (0.0 — a Kraken
        # AssetPairs gap, or a brand-new pair) — a dust-but-nonzero size/
        # price then reaches this point unrejected and formats to
        # "0.00000000"/"0.00": a guaranteed live reject, or on the DRY-RUN
        # path a phantom order the real venue could never accept. Checked
        # identically on BOTH paths (paper trading must not exercise orders
        # the venue could never place) and before either the AddOrder call
        # or the dry-run registration below.
        fmt_vol = self._fmt_volume(pair, size)
        fmt_price = self._fmt_price(pair, price, side=side) \
            if ordertype == "limit" else None
        if safe_float(fmt_vol, default=0.0) <= 0.0 or (
                fmt_price is not None
                and safe_float(fmt_price, default=0.0) <= 0.0):
            self.zero_format_rejects += 1
            msg = tag(Code.OM_ZERO_AFTER_FORMAT,
                      f"{pair} {side} {purpose} size={size!r}->{fmt_vol!r} "
                      f"price={price!r}->{fmt_price!r} formats to zero at "
                      f"venue precision (ordermin={omin}) — refused rather "
                      f"than submit a guaranteed reject/phantom fill")
            log.error(msg)
            get_audit().log("order_manager", Code.OM_ZERO_AFTER_FORMAT, msg,
                            {"pair": pair, "side": side, "purpose": purpose,
                             "size": size, "price": price, "ordermin": omin})
            return None

        # ---- adopt the QUANTITY THE VENUE ACTUALLY GETS (H2) -------------
        # `fmt_vol` is ROUND_FLOOR at the pair's lot_decimals, and it — not
        # `size` — is what goes on the wire below. Live `order.filled` mirrors
        # Kraken's `vol_exec`, i.e. that floored string, so keeping the raw
        # request in `order.size` pins `remaining` in [0, 10^-lot_decimals)
        # forever on a fully-filled order. Nothing downstream can recover:
        # main._handle_fill pops the exit-escalation counter only on
        # `order.remaining <= EPS` (1e-9) and its own final-event branch is
        # gated on `fill_size > EPS`. The counter then ratchets, silently
        # killing maker-first profit exits (which require attempts == 0 —
        # the leg whose spread bled 8/8 live trades) and arming the MARKET
        # rung with no failed fill having occurred. Flooring here is exactly
        # the truncation _fmt_volume already documents as safe, and it keeps
        # dry-run sizes identical to live so paper metrics stop overstating
        # maker capture.
        size = safe_float(fmt_vol, default=size)

        order = ManagedOrder(
            order_id=str(uuid.uuid4())[:8], txid=None, asset=asset,
            pair=pair, symbol=symbol, side=side, price=float(price),
            size=float(size), purpose=purpose, position_id=position_id,
            close_pct=close_pct,
            post_only=post_only and ordertype == "limit",
            leverage=leverage, ordertype=ordertype, meta=meta or {},
            # injected engine time when given (deterministic replay: poll()
            # compares age against the injected now, so a wall-clock stamp
            # makes historical replays never expire orders and time-travel
            # drivers expire them instantly)
            created_ts=float(now) if now is not None else time.time(),
            # implementation-shortfall benchmark: the trusted mark at submit
            # (same arrival price the algo layer books IS against). Firewall
            # may collar `price`; the arrival reference is NEVER collared.
            arrival_ref=float(ref_price) if _fin_pos(ref_price) else 0.0,
            # per-order TTL override (Critical #1a): finite-positive only,
            # else falls back to the shared self.timeout_sec — a garbage
            # caller value degrades safely rather than poisoning the
            # timeout check with a non-finite/negative comparison.
            ttl_sec=(float(ttl_sec)
                    if ttl_sec is not None and _fin_pos(ttl_sec) else None),
        )
        if self.dry_run:
            order.txid = f"DRY-{order.order_id}"
            self._orders[order.order_id] = order
            log.info("[DRY RUN] submit %s %.6f %s @ %s (%s, post_only=%s, "
                     "type=%s)", side, size, pair,
                     self._fmt_price(pair, price), purpose,
                     order.post_only, ordertype)
            return order

        data = {
            "pair": pair, "type": side, "ordertype": ordertype,
            # the exact string the OM-013 guard validated and that
            # order.size was adopted from — never re-derive it here, or the
            # two can silently drift apart again
            "volume": fmt_vol,
            # deterministic idempotency key: a retry of the same internal
            # order id maps to the same userref at the venue. sha256, not
            # hash() - str hashing is salted per process, so a post-restart
            # retry would have minted a DIFFERENT userref and not deduped.
            "userref": self._userref(order.order_id),
        }
        if ordertype == "limit":
            # side-aware (MP-5): the SUBMITTED price never rounds toward
            # crossing — buys floor, sells ceil at the pair's precision
            data["price"] = self._fmt_price(pair, price, side=side)
        if order.post_only:
            data["oflags"] = "post"
        if leverage and leverage > 1.0:
            data["leverage"] = str(int(round(leverage)))
        result = self._timed_private("AddOrder", data)
        if not result or not result.get("txid"):
            self.venue_rejects += 1
            msg = tag(Code.OM_VENUE_REJECT,
                      f"AddOrder failed for {pair} {side} {size}")
            log.error(msg)
            get_audit().log("order_manager", Code.OM_VENUE_REJECT, msg, {})
            return None
        order.txid = result["txid"][0]
        self._orders[order.order_id] = order
        log.info("submitted %s %.6f %s @ %s (%s) txid=%s", side, size,
                 pair, self._fmt_price(pair, price), ordertype, order.txid)
        return order

    # ------------------------------------------------------------------
    def poll(self, books: dict, sigma_by_asset: dict,
             now: Optional[float] = None) -> list:
        """Advance all open orders one step. Returns FillEvents."""
        now = now if now is not None else time.time()
        # deliver fills booked outside the poll loop first (cancel-time
        # final reconciliation) so _handle_fill sees them in order
        events = self._deferred_events
        self._deferred_events = []
        open_now = list(self.open_orders())
        if self.dry_run:
            for order in open_now:
                events.extend(self._poll_dry(
                    order, books.get(order.asset),
                    sigma_by_asset.get(order.asset, 0.05), now))
        else:
            # QueryOrders caps at 50 txids/call: chunk ALL open txids into
            # groups of 50 and merge, else the 51st+ resting order is polled
            # against a batch that never contained it and never updates/fills.
            batch: dict = {}
            txids = [o.txid for o in open_now if o.txid]
            for i in range(0, len(txids), 50):
                res = self._timed_private(
                    "QueryOrders", {"txid": ",".join(txids[i:i + 50])})
                if isinstance(res, dict):
                    batch.update(res)
            # empty -> None so _poll_live falls back to a per-order self-query
            merged = batch or None
            for order in open_now:
                events.extend(self._poll_live(order, now, merged))
            self.refresh_deadman(now)
        return events

    # --- live -------------------------------------------------------------
    def _poll_live(self, order: ManagedOrder, now: float,
                   batch: Optional[dict] = None) -> list:
        events = []
        result = batch if batch is not None else \
            self._timed_private("QueryOrders", {"txid": order.txid})
        if result and order.txid in result:
            info = result[order.txid]
            # Kraken returns numbers as STRINGS, so raw float("Infinity"/"NaN")
            # SUCCEEDS (they don't raise) and would inject an infinite phantom
            # fill or an infinite entry price straight into a live position.
            # safe_float's isfinite gate rejects both; a non-finite/garbage
            # field degrades to the last known good value, never a poison.
            vol_exec = safe_float(info.get("vol_exec"), default=order.filled,
                                  lo=0.0)
            avg = safe_float(info.get("price"), default=order.avg_price,
                             lo=0.0)
            status = info.get("status", "open")
            ev = self._book_venue_segment(order, vol_exec, avg,
                                          fee=info.get("fee"))
            if ev is not None:
                events.append(ev)
            if status == "closed" or order.remaining <= EPS:
                self._transition(order, "filled", "venue closed")
                events.append(FillEvent(order, 0.0, order.avg_price,
                                        final=True))
                return events
            if status in ("canceled", "expired"):
                self._transition(order, "cancelled", f"venue {status}")
                events.append(FillEvent(order, 0.0, order.avg_price,
                                        final=True))
                return events
        if now - order.created_ts > self._timeout_for(order, self.timeout_sec):
            self._note_cancel_result(
                self._timed_private("CancelOrder", {"txid": order.txid}),
                order, "timeout")
            # SAME last look cancel_order() performs (see _final_reconcile).
            # This branch — not cancel_order — is the DOMINANT lifecycle
            # terminator at order_timeout_sec=25, and it was forcing the
            # terminal transition off `batch`, a snapshot taken at the top of
            # poll() and already stale by the throttled CancelOrder round-trip
            # above. Events go straight into THIS poll's return list (rather
            # than _deferred_events) so a fill recovered here reaches
            # _handle_fill in the same cycle it was found.
            events.extend(self._final_reconcile(order))
            if order.status == "filled":
                return events           # it filled before the cancel landed
            new = "expired" if order.filled <= EPS else "cancelled"
            self._transition(order, new,
                             f"timeout at fill_ratio={order.fill_ratio:.2f}")
            log.info("order %s timed out at fill_ratio=%.2f -> %s",
                     order.txid, order.fill_ratio, order.status)
            events.append(FillEvent(order, 0.0,
                                    order.avg_price or order.price,
                                    final=True))
        return events

    # --- dry-run simulator ---------------------------------------------------
    def _sim_maker_cross(self, order: ManagedOrder, book: dict):
        """A POST-ONLY limit NEVER takes: when the opposite touch crosses the
        resting price, the market traded THROUGH us — the aggressor pays
        taker and we fill AT OUR OWN price as maker. The old model routed
        post-only orders through _sim_cross, sweeping the book at taker fees
        (wrong price, wrong fees, wrong side of the trade), which biased
        paper fills and the net_pnl labels learned from them."""
        levels = (book.get("asks") if order.side == "buy"
                  else book.get("bids")) or []
        try:
            top = float(levels[0][0])
        except (TypeError, ValueError, IndexError):
            return
        if not _fin_pos(top) or order.remaining <= EPS:
            return
        crossed = (top <= order.price if order.side == "buy"
                   else top >= order.price)
        if not crossed:
            return
        fill = order.remaining
        notional = fill * order.price
        order.avg_price = (order.avg_price * order.filled + notional) \
            / (order.filled + fill)
        order.filled += fill
        order.fees_usd += notional * self.maker_fee_bps / 1e4
        self._note_exec(True, notional, order.price,
                        order.arrival_ref or order.price, order.side)
        self._transition(order, "filled", "sim maker-cross")

    def _sim_cross(self, order: ManagedOrder, book: dict):
        """Immediate fill of the crossing portion against the live book."""
        levels = (book.get("asks") if order.side == "buy"
                  else book.get("bids")) or []
        remaining = order.remaining
        pre_filled = order.filled
        new_cost = 0.0
        for row in levels:
            try:
                price, avail = float(row[0]), float(row[1])
            except (TypeError, ValueError, IndexError):
                continue
            if not (_fin_pos(price) and _fin_pos(avail)):
                continue
            crosses = order.ordertype == "market" or (
                price <= order.price if order.side == "buy"
                else price >= order.price)
            if not crosses or remaining <= EPS:
                break
            take = min(remaining, avail)
            new_cost += take * price
            order.filled += take
            remaining -= take
        new_cross = order.filled - pre_filled
        if new_cross > EPS:
            # blend the crossed notional into the running average and ADD taker
            # fees on the NEW crossed notional only. (fix: was '='-overwriting
            # fees at taker rate on the CUMULATIVE fill every poll - it clobbered
            # maker fees from prior passive sim fills and re-ran on no-op polls,
            # corrupting paper PnL and the net_pnl labels derived from it.)
            order.avg_price = (order.avg_price * pre_filled + new_cost) \
                / order.filled
            order.fees_usd += new_cost * self.taker_fee_bps / 1e4
            # implementation shortfall on THIS crossed segment vs the arrival
            # mark (falls back to the limit only when no arrival was recorded)
            self._note_exec(False, new_cost, new_cost / new_cross,
                            order.arrival_ref or order.price, order.side)
            self._transition(order,
                             "partial" if order.remaining > EPS
                             else "filled", "sim cross")

    @staticmethod
    def _depth_ahead(order: ManagedOrder, book: dict) -> float:
        """Resting size AHEAD of a passive limit at order.price: for a buy,
        the bids priced >= our bid (better or equal fill first); for a sell,
        the asks priced <= our ask. Since our paper order is not in the book,
        the entire visible size at those levels sits ahead of us in the
        queue. Non-finite rows are skipped. Returns 0.0 when we would rest
        at the very front (order improves the touch)."""
        levels = (book.get("bids") if order.side == "buy"
                  else book.get("asks")) or []
        ahead = 0.0
        for row in levels:
            try:
                px, sz = float(row[0]), float(row[1])
            except (TypeError, ValueError, IndexError):
                continue
            if not (_fin_pos(px) and _fin_pos(sz)):
                continue
            better = px >= order.price if order.side == "buy" \
                else px <= order.price
            if better:
                ahead += sz
        return ahead

    def _queue_eligible(self, order: ManagedOrder, book: dict,
                        sigma_bar_pct: float) -> bool:
        """Queue-position gate for a resting passive order (MP-7). Records
        the depth ahead at first rest, then each poll advances our position
        by the MAX of: the observed shrink in depth ahead (live books whose
        snapshots genuinely evolve), and a volatility-scaled geometric
        turnover of the remaining queue (static-snapshot replays, where the
        aggregate depth looks stable but is continuously traded). Eligible
        once the remaining depth ahead is within queue_tol_frac of our own
        ORDER SIZE. Monotone down: new joiners ahead never push us back.

        The yardstick is `order.size`, NOT `order.remaining`: a price-time-
        priority order cannot regress in the queue just because its own
        resting quantity shrank as it filled. Using `remaining` (a review
        finding) collapsed the threshold on the first partial fill and
        stranded an at-the-front order as a never-completing partial."""
        tol = self.sf_queue_tol_frac * order.size
        ahead_now = self._depth_ahead(order, book)
        if order.queue_ahead < 0.0:            # first time resting
            order.queue_ahead = ahead_now
            return order.queue_ahead <= tol
        observed = max(order.queue_ahead - ahead_now, 0.0)
        sigma_bps = max(sigma_bar_pct * 100.0, 1.0)
        turnover = order.queue_ahead * min(
            self.sf_queue_drain * (sigma_bps / self.sf_sigma_ref_bps), 1.0)
        order.queue_ahead = max(0.0, order.queue_ahead
                                - max(observed, turnover))
        return order.queue_ahead <= tol

    def _poll_dry(self, order: ManagedOrder, book: Optional[dict],
                  sigma_bar_pct: float, now: float) -> list:
        events = []
        pre_filled = order.filled
        pre_avg = order.avg_price
        if order.status == "filled":
            events.append(FillEvent(order, 0.0, order.avg_price, final=True))
            return events
        if book:
            # post-only NEVER takes (maker-first, OM-011): crossed books fill
            # it AT ITS OWN price as maker; everything else may sweep
            if order.post_only:
                self._sim_maker_cross(order, book)
            else:
                self._sim_cross(order, book)
            if order.remaining > EPS and order.status in ("pending",
                                                          "partial"):
                bids, asks = book.get("bids") or [], book.get("asks") or []
                if bids and asks:
                    try:
                        mid = 0.5 * (float(bids[0][0]) + float(asks[0][0]))
                    except (TypeError, ValueError, IndexError):
                        mid = 0.0
                    # queue-position gate (MP-7): a resting order cannot
                    # fill until the depth ahead of it has cleared. Skipped
                    # when queue_aware is off (identical to the old model).
                    queue_ok = (not self.sf_queue_aware
                                or self._queue_eligible(order, book,
                                                        sigma_bar_pct))
                    # owed 57 / era boundary #4: with a book in hand the
                    # cross above already decided this event. Running the
                    # hazard too counts the same crossing twice.
                    if _fin_pos(mid) and queue_ok and self.sf_hazard_with_book:
                        dist_bps = abs(mid - order.price) / mid * 1e4
                        sigma_bps = max(sigma_bar_pct * 100.0, 1.0)
                        p = _passive_poll_prob(
                            self.sf_base, dist_bps, sigma_bps,
                            self._timeout_for(order, self.timeout_sec),
                            self.sf_cal_life_sec)
                        if self._rng.random() < p:
                            frac = float(self._rng.uniform(self.sf_frac_min,
                                                           self.sf_frac_max))
                            fill = order.remaining * frac
                            cost = order.avg_price * order.filled + \
                                fill * order.price
                            order.filled += fill
                            order.avg_price = cost / order.filled
                            order.fees_usd += fill * order.price * \
                                self.maker_fee_bps / 1e4
                            # passive fill AT our limit: booked vs the arrival
                            # mark, so a maker fill below/above mid shows its
                            # true (usually favourable) capture, not a hard 0
                            self._note_exec(True, fill * order.price,
                                            order.price,
                                            order.arrival_ref or order.price,
                                            order.side)
                            self._transition(
                                order, "partial" if order.remaining > EPS
                                else "filled", "sim passive")
        new_fill = order.filled - pre_filled
        if new_fill > EPS:
            # segment price for THIS poll's fills, not the cumulative blend —
            # same recovery as the live path (audit MP-1): a sweep + passive
            # mix in one poll otherwise books at a price no fill ever traded.
            seg_px = order.avg_price
            if pre_filled > EPS and order.avg_price > 0:
                cand = (order.avg_price * order.filled
                        - pre_avg * pre_filled) / new_fill
                if math.isfinite(cand) and cand > 0:
                    seg_px = cand
            events.append(FillEvent(order, new_fill, seg_px,
                                    final=False))
        if order.remaining <= EPS:
            if order.status != "filled":
                self._transition(order, "filled", "sim complete")
            events.append(FillEvent(order, 0.0, order.avg_price, final=True))
        elif now - order.created_ts > self._timeout_for(order, self.timeout_sec):
            self._transition(order, "expired" if order.filled <= EPS
                             else "cancelled", "sim timeout")
            log.info("[DRY RUN] order %s %s at fill_ratio=%.2f",
                     order.order_id, order.status, order.fill_ratio)
            events.append(FillEvent(order, 0.0,
                                    order.avg_price or order.price,
                                    final=True))
        return events
