"""
execution/tactics.py — execution tactics planner (Assurance Build)

Rev-2 entries had exactly one placement style: rest at our own A-S
quote. Optimal for slow alpha; it leaks money on fast alpha, where the
edge decays before a deep passive order fills. This module ladders
placement to the signal's urgency:

  urgency < join_at      AS_QUOTE  rest at quote.bid/ask (rev-2
                                   default; maximum spread capture)
  < improve_at           JOIN      rest AT the touch — first in queue
                                   at the best price, still maker
  < taker_at             IMPROVE   step 25% of the spread inside the
                                   touch — buys queue priority with a
                                   fraction of the spread, still maker,
                                   never crosses (post-only safe)
  >= taker_at            TAKER     cross the book at the opposite
                                   touch — pay the taker stack to
                                   capture edge that won't wait

SAFETY RAILS (non-negotiable):
  * The planner PROPOSES; the pre-trade gate DISPOSES. A taker plan is
    submitted to pretrade with taker=True, so it must clear the full
    taker cost stack (fee + half spread + book walk + impact) at the
    configured edge ratio — urgency never buys its way past EV.
  * IMPROVE prices strictly inside the spread, never at/through the
    opposite touch: a post-only improve can never self-cross.
  * Any malformed input degrades to AS_QUOTE — the conservative style
    is the fail-safe style.
  * Taker entries can be disabled wholesale (allow_taker: false), and
    are auto-disabled in spoofy liquidity regimes.
"""

import logging
import math
from dataclasses import dataclass

log = logging.getLogger("liquiditybot.execution.tactics")


def _fin_pos(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0


@dataclass
class EntryPlan:
    style: str          # as_quote | join | improve | taker
    price: float
    taker: bool
    post_only: bool


class ExecutionPlanner:
    def __init__(self, config: dict):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.allow_taker = bool(cfg.get("allow_taker", True))
        self.join_at = float(cfg.get("join_at_urgency", 0.40))
        self.improve_at = float(cfg.get("improve_at_urgency", 0.70))
        self.taker_at = float(cfg.get("taker_at_urgency", 0.88))
        self.improve_frac = min(max(float(
            cfg.get("improve_spread_frac", 0.25)), 0.0), 0.49)
        if not (self.join_at <= self.improve_at <= self.taker_at):
            raise ValueError("execution_tactics: urgency ladder must be "
                             "non-decreasing (join <= improve <= taker)")

    # ------------------------------------------------------------------
    def plan_entry(self, direction: str, quote, book: dict,
                   urgency: float, liq_label: str = "liquid") -> EntryPlan:
        """quote: the A-S Quote; book: live Kraken book. Returns the
        placement plan. Never raises; failure -> AS_QUOTE."""
        long = direction == "long"
        base_price = quote.bid if long else quote.ask
        fallback = EntryPlan("as_quote", base_price, False, True)
        try:
            if not self.enabled or not isinstance(urgency, (int, float)) \
                    or not math.isfinite(urgency) or urgency < self.join_at:
                return fallback
            bids = (book or {}).get("bids") or []
            asks = (book or {}).get("asks") or []
            if not bids or not asks:
                return fallback
            best_bid, best_ask = float(bids[0][0]), float(asks[0][0])
            if not (_fin_pos(best_bid) and _fin_pos(best_ask)) \
                    or best_ask <= best_bid:
                return fallback
            spread = best_ask - best_bid

            if urgency >= self.taker_at and self.allow_taker \
                    and liq_label != "spoofy":
                # cross at the opposite touch; pretrade must approve the
                # full taker cost stack or this plan dies there
                price = best_ask if long else best_bid
                return EntryPlan("taker", price, True, False)

            if urgency >= self.improve_at:
                step = spread * self.improve_frac
                price = min(best_bid + step, best_ask - 1e-12) if long \
                    else max(best_ask - step, best_bid + 1e-12)
                return EntryPlan("improve", price, False, True)

            price = best_bid if long else best_ask
            return EntryPlan("join", price, False, True)
        except Exception:
            log.exception("tactics fault — degrading to AS quote")
            return fallback
