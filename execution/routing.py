"""
execution/routing.py — smart order routing, rev 4

Formalizes venue selection as a scored decision instead of a hardcoded
constant — while keeping the codebase's oldest invariant loud and
intact: KRAKEN IS THE SOLE EXECUTION VENUE. OKX / Binance.US / anything
else remain read-only data sources.

What this module actually does today:
  * scores every venue it can see on the four things that decide where
    a child order should print — taker/maker fee, top-of-book spread,
    visible depth vs order size, and data staleness — using the same
    per-venue books the feeds already publish;
  * hard-filters candidates by the execution-eligibility list, which
    defaults to ["kraken"] and is guarded: any other venue appearing in
    that list is a FATAL config error in live mode (wired into
    core/config_guard.py) and a screaming warning in dry-run;
  * returns a RouteDecision carrying the winner AND the full scoreboard,
    so the audit trail shows what routing would have chosen if more
    venues were ever made eligible.

What it deliberately does not do: open connectivity to any new venue.
Adding one is a conscious act — implement the VenueAdapter contract in
docs/EXECUTION_CONNECTIVITY.md, add credentials, extend the eligibility
list, and accept the config-guard gate. Routing math being ready is not
permission; it is preparation.
"""

import logging
import math
import time
from dataclasses import dataclass, field

log = logging.getLogger("liquiditybot.execution.routing")

EXECUTION_INVARIANT_VENUE = "kraken"


def _f(x, default=0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


@dataclass
class VenueQuote:
    venue: str
    best_bid: float = 0.0
    best_ask: float = 0.0
    depth_usd: float = 0.0          # top-of-book-adjacent visible depth
    taker_fee_bps: float = 40.0
    maker_fee_bps: float = 25.0
    ts: float = 0.0                 # last book update, epoch seconds
    execution_eligible: bool = False


@dataclass
class RouteDecision:
    venue: str
    score: float
    scoreboard: dict = field(default_factory=dict)   # venue -> score detail
    reasons: list = field(default_factory=list)


class SmartOrderRouter:
    def __init__(self, config: dict):
        cfg = config or {}
        self.eligible = [str(v).lower() for v in
                         cfg.get("eligible_venues", ["kraken"])]
        self.max_staleness_ms = _f(cfg.get("max_staleness_ms", 4000.0),
                                   4000.0)
        # score weights: cost terms dominate; staleness is a gate not a
        # weight (stale books are ineligible, not merely penalized)
        w = cfg.get("weights") or {}
        self.w_fee = _f(w.get("fee", 1.0), 1.0)
        self.w_spread = _f(w.get("spread", 1.0), 1.0)
        self.w_depth = _f(w.get("depth", 0.6), 0.6)
        # penalty (bps) charged at ZERO depth cover, decaying linearly to 0 at
        # full cover — the book-walk cost proxy (lifted literal, same default)
        self.depth_penalty_bps = max(
            _f(cfg.get("depth_penalty_bps", 25.0), 25.0), 0.0)
        bad = [v for v in self.eligible if v != EXECUTION_INVARIANT_VENUE]
        if bad:
            # config_guard makes this FATAL in live; here we scream too
            log.critical("SOR-001: execution-eligible venues beyond "
                         "'%s' configured: %s — the Kraken-only "
                         "execution invariant is being overridden",
                         EXECUTION_INVARIANT_VENUE, bad)

    # ------------------------------------------------------------------
    def _score(self, q: VenueQuote, side: str, notional_usd: float,
               now: float) -> tuple:
        """Lower is better. Returns (score, detail) or (None, why-not)."""
        if (now - q.ts) * 1000.0 > self.max_staleness_ms:
            return None, "stale"
        if q.best_bid <= 0 or q.best_ask <= 0 or q.best_ask <= q.best_bid:
            return None, "bad_book"
        mid = 0.5 * (q.best_bid + q.best_ask)
        spread_bps = (q.best_ask - q.best_bid) / mid * 1e4
        # expected cost of an aggressive child: taker fee + half spread;
        # depth shortfall adds a convex penalty (walking the book)
        cover = q.depth_usd / max(notional_usd, 1.0)
        depth_pen = 0.0 if cover >= 1.0 \
            else (1.0 - cover) * self.depth_penalty_bps
        score = (self.w_fee * q.taker_fee_bps +
                 self.w_spread * 0.5 * spread_bps +
                 self.w_depth * depth_pen)
        return score, {"fee_bps": round(q.taker_fee_bps, 1),
                       "half_spread_bps": round(0.5 * spread_bps, 2),
                       "depth_cover": round(cover, 2),
                       "score": round(score, 2)}

    def route(self, side: str, notional_usd: float,
              quotes: list, now: float | None = None) -> RouteDecision:
        """Pick the cheapest ELIGIBLE venue; publish the whole
        scoreboard (ineligible venues are scored for the audit trail
        but can never win)."""
        now = now if now is not None else time.time()
        board, best = {}, None
        for q in quotes or []:
            s, detail = self._score(q, side, notional_usd, now)
            eligible = q.execution_eligible and q.venue.lower() in \
                self.eligible and q.venue.lower() == \
                EXECUTION_INVARIANT_VENUE
            board[q.venue] = {"eligible": eligible,
                              **(detail if isinstance(detail, dict)
                                 else {"skipped": detail})}
            if s is None or not eligible:
                continue
            if best is None or s < best[1]:
                best = (q.venue, s)
        if best is None:
            return RouteDecision(venue="", score=float("inf"),
                                 scoreboard=board,
                                 reasons=["SOR-010: no eligible venue "
                                          "with a fresh, sane book"])
        return RouteDecision(venue=best[0], score=best[1], scoreboard=board,
                             reasons=[])
