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

import hashlib
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from core.audit import get_audit
from core.codes import Code, tag

log = logging.getLogger("liquiditybot.execution.order_manager")

EPS = 1e-12
_TERMINAL = ("filled", "cancelled", "expired")
_LEGAL = {
    "pending": {"partial", "filled", "cancelled", "expired"},
    "partial": {"partial", "filled", "cancelled"},
    "filled": set(), "cancelled": set(), "expired": set(),
}
_HISTORY_CAP = 512          # bounded terminal-order retention


def _fin_pos(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0


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
                 pair_meta: Optional[dict] = None):
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
        self.firewall = firewall
        self.pair_meta = pair_meta or {}
        self.latency_ms: float = 0.0
        self.venue_rejects: int = 0
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
            get_audit().log("order_manager", Code.OM_TIMEOUT_CANCEL
                            if new == "expired" else "OM-000",
                            f"{order.order_id} {order.side} {order.pair} "
                            f"terminal={new} fill_ratio="
                            f"{order.fill_ratio:.2f} ({why})",
                            {"purpose": order.purpose,
                             "avg_price": order.avg_price,
                             "fees_usd": round(order.fees_usd, 4)})
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
    def _fmt_price(self, pair: str, price: float) -> str:
        d = int((self.pair_meta.get(pair) or {}).get("price_decimals", 2))
        return f"{price:.{d}f}"

    def _fmt_volume(self, pair: str, size: float) -> str:
        d = int((self.pair_meta.get(pair) or {}).get("lot_decimals", 8))
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

    # ------------------------------------------------------------------
    def open_orders(self) -> list:
        return [o for o in self._orders.values()
                if o.status in ("pending", "partial")]

    def has_open(self, asset: str, purpose: Optional[str] = None) -> bool:
        return any(o.asset == asset and (purpose is None
                                         or o.purpose == purpose)
                   for o in self.open_orders())

    def status(self) -> dict:
        return {"open": len(self.open_orders()),
                "tracked": len(self._orders),
                "latency_ms": round(self.latency_ms, 1),
                "venue_rejects": self.venue_rejects,
                "deadman_failures": self._deadman_failures}

    def _timed_private(self, endpoint: str, data: dict):
        t0 = time.time()
        result = self.feed._private_post(endpoint, data)
        rtt = (time.time() - t0) * 1000.0
        self.latency_ms = 0.7 * self.latency_ms + 0.3 * rtt \
            if self.latency_ms else rtt
        return result

    # ------------------------------------------------------------------
    def submit(self, asset: str, symbol: str, pair: str, side: str,
               price: float, size: float, purpose: str = "entry",
               position_id: Optional[str] = None, close_pct: float = 0.0,
               post_only: bool = True, leverage: float = 1.0,
               book: Optional[dict] = None, sigma_bar_pct: float = 0.05,
               ordertype: str = "limit", ref_price: float = 0.0,
               equity: float = 0.0,
               meta: Optional[dict] = None) -> Optional[ManagedOrder]:
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
        if self.firewall is not None:
            verdict = self.firewall.check(
                pair=pair, side=side, purpose=purpose, price=price,
                size=size, ref_price=ref_price or price, equity=equity)
            if not verdict.allowed:
                log.error(tag(Code.OM_FIREWALL_REJECT,
                              f"{side} {size:.6f} {pair} @ {price!r} "
                              f"({purpose}): {list(verdict.reasons)}"))
                return None
            price, size = verdict.price, verdict.size

        # ---- venue minimum: below-ordermin is a guaranteed reject --------
        omin = self._ordermin(pair)
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

        order = ManagedOrder(
            order_id=str(uuid.uuid4())[:8], txid=None, asset=asset,
            pair=pair, symbol=symbol, side=side, price=float(price),
            size=float(size), purpose=purpose, position_id=position_id,
            close_pct=close_pct,
            post_only=post_only and ordertype == "limit",
            leverage=leverage, ordertype=ordertype, meta=meta or {},
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
            "volume": self._fmt_volume(pair, size),
            # deterministic idempotency key: a retry of the same internal
            # order id maps to the same userref at the venue. sha256, not
            # hash() - str hashing is salted per process, so a post-restart
            # retry would have minted a DIFFERENT userref and not deduped.
            "userref": self._userref(order.order_id),
        }
        if ordertype == "limit":
            data["price"] = self._fmt_price(pair, price)
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
        events = []
        open_now = list(self.open_orders())
        if self.dry_run:
            for order in open_now:
                events.extend(self._poll_dry(
                    order, books.get(order.asset),
                    sigma_by_asset.get(order.asset, 0.05), now))
        else:
            batch = None
            txids = [o.txid for o in open_now if o.txid]
            if txids:
                batch = self._timed_private(
                    "QueryOrders", {"txid": ",".join(txids[:50])})
            for order in open_now:
                events.extend(self._poll_live(order, now, batch))
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
            try:
                vol_exec = float(info.get("vol_exec", 0.0))
                avg = float(info.get("price", 0.0) or 0.0)
            except (TypeError, ValueError):
                vol_exec, avg = order.filled, order.avg_price
            status = info.get("status", "open")
            new_fill = vol_exec - order.filled
            if new_fill > EPS:
                order.avg_price = avg if avg > 0 else order.price
                order.filled = vol_exec
                order.fees_usd += new_fill * order.avg_price * \
                    (self.maker_fee_bps if order.post_only
                     else self.taker_fee_bps) / 1e4
                self._transition(order, "partial", "venue fill")
                events.append(FillEvent(order, new_fill, order.avg_price,
                                        final=False))
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
        if now - order.created_ts > self.timeout_sec:
            self._timed_private("CancelOrder", {"txid": order.txid})
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
            self._transition(order,
                             "partial" if order.remaining > EPS
                             else "filled", "sim cross")

    def _poll_dry(self, order: ManagedOrder, book: Optional[dict],
                  sigma_bar_pct: float, now: float) -> list:
        events = []
        pre_filled = order.filled
        if order.status == "filled":
            events.append(FillEvent(order, 0.0, order.avg_price, final=True))
            return events
        if book:
            self._sim_cross(order, book)
            if order.remaining > EPS and order.status in ("pending",
                                                          "partial"):
                bids, asks = book.get("bids") or [], book.get("asks") or []
                if bids and asks:
                    try:
                        mid = 0.5 * (float(bids[0][0]) + float(asks[0][0]))
                    except (TypeError, ValueError, IndexError):
                        mid = 0.0
                    if _fin_pos(mid):
                        dist_bps = abs(mid - order.price) / mid * 1e4
                        sigma_bps = max(sigma_bar_pct * 100.0, 1.0)
                        p = 0.45 * float(np.exp(-dist_bps / sigma_bps))
                        if self._rng.random() < p:
                            frac = float(self._rng.uniform(0.3, 1.0))
                            fill = order.remaining * frac
                            cost = order.avg_price * order.filled + \
                                fill * order.price
                            order.filled += fill
                            order.avg_price = cost / order.filled
                            order.fees_usd += fill * order.price * \
                                self.maker_fee_bps / 1e4
                            self._transition(
                                order, "partial" if order.remaining > EPS
                                else "filled", "sim passive")
        new_fill = order.filled - pre_filled
        if new_fill > EPS:
            events.append(FillEvent(order, new_fill, order.avg_price,
                                    final=False))
        if order.remaining <= EPS:
            if order.status != "filled":
                self._transition(order, "filled", "sim complete")
            events.append(FillEvent(order, 0.0, order.avg_price, final=True))
        elif now - order.created_ts > self.timeout_sec:
            self._transition(order, "expired" if order.filled <= EPS
                             else "cancelled", "sim timeout")
            log.info("[DRY RUN] order %s %s at fill_ratio=%.2f",
                     order.order_id, order.status, order.fill_ratio)
            events.append(FillEvent(order, 0.0,
                                    order.avg_price or order.price,
                                    final=True))
        return events
