"""
execution/pretrade.py — rev 2.0 (Assurance Build)

The "is this trade worth existing?" gate. Rev 2 keeps every rev-1 veto
and adds the two terms that decide whether a passive strategy makes or
loses money at Kraken's fee tier (venue-true 40/80bps as of cut #8,
2026-08-28; config.pretrade.maker_fee_bps/taker_fee_bps are authority):

  ADVERSE SELECTION (maker path). A passive fill is not a free maker
  fee — you get filled precisely when flow trades through you, so the
  conditional expected move at fill time is against you. First-order
  Glosten-Milgrom proxy:  as_kappa x sigma_bar (bps), added to the
  maker cost stack. Rev 1 priced passive fills as fee-only, which
  systematically overstated edge on every single entry.

  FILL-PROBABILITY-WEIGHTED EV (maker path). A resting limit that
  fills 8% of the time must clear its cost conditional on filling AND
  beat the small friction of the 92% of attempts that expire:

     EV = p_fill x (edge - cost) - (1 - p_fill) x miss_cost

  p_fill uses the same distance-decay FAMILY as the dry-run fill
  simulator (p0 x exp(-dist_bps / sigma_bar_bps)) — but NOT the same
  time horizon (2026-07-29 unit audit): the simulator applies that
  expression PER POLL and an order lives ~order_timeout/poll polls, so
  its per-ORDER fill rate is 1-(1-p)^n — flatter and higher than this
  gate's single application. The gate is therefore conservative
  (under-credits maker EV, over-vetoes deep rungs); it never fabricates
  edge. The honest per-order number is exactly what the A4 fill
  calibrator measures — recalibrate maker_fill_p0 from its output, not
  by matching the sim's p0. Both knobs ship gentle (miss_cost 0.5bps,
  ev_min 0) — tighten via replay sweeps, not vibes.

Everything is fail-closed: any non-finite input rejects (PT-010). All
verdicts carry codes from core.codes. Interface unchanged.
"""

import logging
import math
from dataclasses import dataclass, field


from core.codes import Code, tag
from core.sanitize import is_finite as _fin

log = logging.getLogger("liquiditybot.execution.pretrade")

EPS = 1e-9


@dataclass
class PreTradeContext:
    kraken_book: dict
    sigma_daily_pct: float
    adv_usd: float
    liq_label: str
    spread_bps: float
    staleness_ms: float
    reduce_only_ok: bool = False
    tier: str = "core"               # liquidity cap-tier from the regime engine
                                     # (core|mid|micro): scales ONLY the hard
                                     # spread-ceiling veto, never the EV test


@dataclass
class PreTradeDecision:
    approved: bool
    size_units: float
    est_cost_bps: float = 0.0
    est_edge_bps: float = 0.0
    reasons: list = field(default_factory=list)
    taker: bool = False
    p_fill: float = 1.0
    ev_bps: float = 0.0


class PreTradeGate:
    def __init__(self, config: dict):
        cfg = config or {}
        # fallback = venue-true Kraken Tier-1 (cut #8, 2026-08-28). config is
        # the authority and always carries these (config.json 40/80);
        # config_guard FATALs a start whose fee keys fall below this floor, so
        # the fallback is dead in production and fires only in bare-config test
        # construction. Kept at venue truth, never the retired 25/40 tier.
        self.maker_fee_bps = float(cfg.get("maker_fee_bps", 40.0))
        self.taker_fee_bps = float(cfg.get("taker_fee_bps", 80.0))
        self.price_exit_leg = bool(cfg.get("price_exit_leg", True))
        self.impact_eta = float(cfg.get("impact_eta", 0.8))
        self.min_edge_cost_ratio = float(cfg.get("min_edge_cost_ratio", 1.3))
        self.max_spread_bps = float(cfg.get("max_spread_bps", 15.0))
        # v9 per-tier spread CEILING (the only categorical veto that scales by
        # cap-tier). core == max_spread_bps exactly, so majors are unchanged; a
        # wider ceiling for MID/MICRO stops the flat cap from vetoing a
        # low-volume asset BEFORE the honest edge/cost EV gate — which stays
        # flat for every tier — can weigh its (wider) real spread. A missing
        # tier falls back to max_spread_bps (never looser than core by default).
        _tms = cfg.get("tier_max_spread_bps") or {}
        self.tier_max_spread_bps = {
            str(k): float(v) for k, v in _tms.items()
            if not str(k).startswith("_")}      # skip the _doc annotation
        self.tier_max_spread_bps.setdefault("core", self.max_spread_bps)
        self.max_staleness_ms = float(cfg.get("max_data_staleness_ms", 4000.0))
        self.max_participation = float(cfg.get("max_participation_of_depth",
                                               0.15))
        self.min_order_usd = float(cfg.get("min_order_usd", 15.0))
        # rev 2 profit terms (all bounded, all default-gentle)
        self.as_kappa = min(max(float(cfg.get("adverse_selection_kappa",
                                              0.35)), 0.0), 2.0)
        self.maker_fill_p0 = min(max(float(cfg.get("maker_fill_p0", 0.45)),
                                     0.01), 1.0)
        self.p_fill_floor = min(max(float(cfg.get("p_fill_floor", 0.05)),
                                    0.001), 1.0)
        self.miss_cost_bps = min(max(float(cfg.get("miss_cost_bps", 0.5)),
                                     0.0), 20.0)
        self.ev_min_bps = float(cfg.get("ev_min_bps", 0.0))

    # ------------------------------------------------------------------
    @staticmethod
    def book_walk_bps(book: dict, side: str, size_units: float) -> float:
        """Avg slippage vs touch when sweeping the live book. Invalid
        levels are skipped (fail-closed: they provide no liquidity)."""
        levels = (book.get("asks") if side == "buy"
                  else book.get("bids")) or []
        if size_units <= EPS:
            return 0.0
        if not levels:
            # a WHOLLY empty side (not just thin) provides no liquidity to
            # walk at all -- fail closed with the same 1e6 shallow-book
            # sentinel a thin-but-present side hits below, never the
            # zero-cost default (W2-26).
            return 1e6
        clean = []
        for row in levels:
            try:
                p, s = float(row[0]), float(row[1])
            except (TypeError, ValueError, IndexError):
                continue
            if _fin(p) and p > 0 and _fin(s) and s > 0:
                clean.append((p, s))
        if not clean:
            return 1e6
        touch = clean[0][0]
        remaining, cost = size_units, 0.0
        for price, avail in clean:
            take = min(remaining, avail)
            cost += take * price
            remaining -= take
            if remaining <= EPS:
                break
        if remaining > EPS:
            return 1e6
        avg = cost / size_units
        slip = (avg - touch) / touch if side == "buy" else (touch - avg) / touch
        return max(slip, 0.0) * 1e4

    @staticmethod
    def sigma_bar_bps(sigma_daily_pct: float) -> float:
        """Per-5m-bar vol in bps from a daily-vol input. Pulled out of
        evaluate() so any per-rung caller (the grid ladder, W2-10) derives
        the SAME per-bar figure the gate used at approval time instead of
        re-deriving its own (and silently drifting from it)."""
        return max(sigma_daily_pct * 100.0 / math.sqrt(288.0), 1.0)

    @staticmethod
    def maker_dist_bps(book: dict, price: float) -> float:
        """Distance in bps from the live Kraken mid to `price`. Same
        best-effort mid (0.0 / not-finite -> 0.0 distance, i.e. "at the
        money") evaluate() itself falls back to when the book can't
        produce one."""
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        mid = 0.0
        try:
            if bids and asks:
                mid = 0.5 * (float(bids[0][0]) + float(asks[0][0]))
        except (TypeError, ValueError, IndexError):
            mid = 0.0
        return abs(mid - price) / mid * 1e4 if _fin(mid) and mid > 0 else 0.0

    def maker_p_fill_ev(self, edge_bps: float, cost_bps: float,
                        dist_bps: float, sigma_bar_bps: float) -> tuple:
        """Fill-probability-weighted EV for a maker order resting
        `dist_bps` away from the current mid, given a per-bar vol estimate
        `sigma_bar_bps`. THE gate's own arithmetic (not a copy): evaluate()
        calls this for rung 0's distance and the grid ladder (W2-10) calls
        it again per deeper rung at that rung's own (larger) offset, so a
        rung's true fill-probability-weighted EV can never silently drift
        from what this exact formula would say if the gate re-evaluated it.
        Returns (p_fill, ev_bps)."""
        p_fill = max(self.maker_fill_p0 *
                     math.exp(-dist_bps / max(sigma_bar_bps, EPS)),
                     self.p_fill_floor)
        ev = p_fill * (edge_bps - cost_bps) - (1.0 - p_fill) * \
            self.miss_cost_bps
        return p_fill, ev

    def impact_bps(self, order_usd: float, sigma_daily_pct: float,
                   adv_usd: float) -> float:
        """Square-root impact: eta x sigma_daily x sqrt(Q / ADV)."""
        if adv_usd <= EPS or order_usd <= EPS:
            return 0.0
        return self.impact_eta * (sigma_daily_pct * 100.0) * \
            math.sqrt(order_usd / adv_usd)

    # ------------------------------------------------------------------
    def evaluate(self, side: str, size_units: float, ref_price: float,
                 exp_alpha_bps: float, fv_edge_bps: float,
                 ctx: PreTradeContext, taker: bool = False,
                 extra_edge_ratio: float = 0.0,
                 exploring: bool = False) -> PreTradeDecision:
        # `exploring` = a DRY-RUN active-learning entry (the caller only sets it
        # when exploration is active, which is hard-gated to dry_run). It
        # bypasses the two PROFIT gates (edge/cost ratio PT-041, EV floor
        # PT-040) so a net-thin signal can still be TAKEN to acquire a real-fill
        # label — otherwise every exploration entry dies at the cost stack and
        # the model never learns from fills. Every SAFETY gate (input, stale,
        # spread, spoofy, participation, min-order, book depth) still applies.
        d = PreTradeDecision(approved=False, size_units=0.0, taker=taker)

        # ---- fail-closed input validation (PT-010) ---------------------
        if side not in ("buy", "sell") or not _fin(size_units) \
                or not _fin(ref_price) or size_units <= EPS \
                or ref_price <= EPS:
            d.reasons.append(tag(Code.PT_INVALID_INPUT,
                                 f"side={side!r} size={size_units!r} "
                                 f"ref={ref_price!r}"))
            return d
        for name, v in ((" alpha", exp_alpha_bps), ("fv_edge", fv_edge_bps),
                        ("sigma", ctx.sigma_daily_pct), ("adv", ctx.adv_usd),
                        ("spread", ctx.spread_bps),
                        ("stale", ctx.staleness_ms)):
            if not _fin(v):
                d.reasons.append(tag(Code.PT_INVALID_INPUT,
                                     f"non-finite {name}={v!r}"))
                return d
        if ctx.spread_bps < 0.0:
            d.reasons.append(tag(Code.PT_INVALID_INPUT,
                                 f"negative spread={ctx.spread_bps!r}"))
            return d

        # ---- hard vetoes ------------------------------------------------
        # A NON-FINITE THRESHOLD MAKES EVERY VETO BELOW FAIL OPEN (2026-09-13).
        # Each veto is `value > threshold`, which is False when the THRESHOLD
        # is NaN - so the guard silently stops guarding while the config still
        # reads as configured. The :338 fence added earlier the same day does
        # not help: it inspects the derived cost/edge and runs AFTER all of
        # these. Measured on a live gate from the shipped config, in the lane
        # era-9 actually uses (exploring=True, which bypasses PT-041/PT-040 by
        # design, so these vetoes are the LAST line):
        #     stale 1e6 ms, threshold OK              -> refused (PT-020)
        #     stale 1e6 ms, max_data_staleness_ms=NaN -> APPROVED
        #     $0.01 order, min_order_usd=NaN          -> APPROVED
        # A non-finite participation cap is verdict-INVISIBLE - it does not
        # approve anything by itself, it silently drops the size clamp, so it
        # is fenced here too rather than left to be noticed later.
        # PT_INVALID_INPUT, not a new code: it already means exactly this and
        # already fires for non-finite three lines up.
        spread_cap = self.tier_max_spread_bps.get(ctx.tier, self.max_spread_bps)
        for _tn, _tv in (("max_data_staleness_ms", self.max_staleness_ms),
                         (f"max_spread_bps[{ctx.tier}]", spread_cap),
                         ("min_order_usd", self.min_order_usd),
                         ("max_participation_of_depth", self.max_participation)):
            if not _fin(_tv):
                d.reasons.append(tag(Code.PT_INVALID_INPUT,
                                     f"non-finite threshold {_tn}={_tv!r} - "
                                     f"every veto compares with '>', which is "
                                     f"False against NaN, so this guard would "
                                     f"stop guarding silently"))
                return d
        if ctx.staleness_ms > self.max_staleness_ms:
            d.reasons.append(tag(Code.PT_STALE_DATA,
                                 f"{ctx.staleness_ms:.0f}ms"))
            return d
        if ctx.spread_bps > spread_cap:
            d.reasons.append(tag(Code.PT_SPREAD_WIDE,
                                 f"{ctx.spread_bps:.1f}bps > "
                                 f"{spread_cap:.0f} ({ctx.tier})"))
            return d
        if ctx.liq_label == "spoofy" and not ctx.reduce_only_ok:
            d.reasons.append(tag(Code.PT_SPOOFY_REGIME,
                                 "new risk blocked"))
            return d

        # ---- participation cap (shrink, don't reject) --------------------
        levels = (ctx.kraken_book.get("asks") if side == "buy"
                  else ctx.kraken_book.get("bids")) or []
        depth_units = 0.0
        for row in levels[:10]:
            try:
                s = float(row[1])
            except (TypeError, ValueError, IndexError):
                continue
            if _fin(s) and s > 0:
                depth_units += s
        max_units = depth_units * self.max_participation
        size = size_units
        if max_units > EPS and size > max_units:
            d.reasons.append(tag(Code.PT_PARTICIPATION_CLAMP,
                                 f"{size:.6f} -> {max_units:.6f}"))
            size = max_units
        order_usd = size * ref_price
        if order_usd < self.min_order_usd:
            d.reasons.append(tag(Code.PT_BELOW_MIN_ORDER,
                                 f"${order_usd:,.0f}"))
            return d

        # ---- cost stack ---------------------------------------------------
        sigma_bar_bps = self.sigma_bar_bps(ctx.sigma_daily_pct)
        if taker:
            fee = self.taker_fee_bps
            spread_cost = 0.5 * ctx.spread_bps
            walk = self.book_walk_bps(ctx.kraken_book, side, size)
            if walk >= 1e6:
                d.reasons.append(tag(Code.PT_BOOK_SHALLOW, "for size"))
                return d
            as_penalty = 0.0
        else:
            fee = self.maker_fee_bps
            spread_cost = 0.0
            walk = 0.0
            # a one-sided Kraken book (empty bids or asks) cannot price a
            # maker fill: no touch to distance-decay p_fill from, and the
            # participation clamp's depth read (the trade-direction side)
            # goes to 0 and silently no-ops. Fail closed like the taker
            # path's own shallow-book veto -- same code, same meaning.
            if not (ctx.kraken_book.get("bids") and ctx.kraken_book.get("asks")):
                d.reasons.append(tag(Code.PT_BOOK_SHALLOW,
                                     "one-sided Kraken book: maker needs "
                                     "both sides to price a fill"))
                return d
            # adverse selection: conditional on a passive fill, expected
            # short-horizon move against us ~ kappa x per-bar vol
            as_penalty = self.as_kappa * sigma_bar_bps
        impact = self.impact_bps(order_usd, ctx.sigma_daily_pct, ctx.adv_usd)
        # exit leg: every entry must be unwound, and the escalation
        # ladder's common terminal case is a taker exit through the
        # current spread. Pricing entry-only is how an 86% hit rate
        # still nets red: 9/9 live postmortems showed realized costs
        # exceeding this estimate by a median 44bps - one taker leg.
        exit_leg = (self.taker_fee_bps + 0.5 * ctx.spread_bps) \
            if self.price_exit_leg else 0.0
        cost = fee + spread_cost + walk + impact + as_penalty + exit_leg

        # ---- edge stack -----------------------------------------------------
        edge = max(exp_alpha_bps, 0.0) + max(fv_edge_bps, 0.0)
        d.est_cost_bps, d.est_edge_bps = cost, edge

        # THE FENCE AT :228 GUARDS THE INPUTS; THIS GUARDS THE DERIVED TERMS
        # (2026-09-13). `cost` is a sum of six terms, two of which come from
        # config knobs never finite-checked (impact_eta, adverse_selection
        # kappa) and one of which - `impact` - is computed at RUNTIME from
        # ctx.adv_usd and ctx.sigma_daily_pct. So a config guard alone cannot
        # close this: a non-finite can enter after every input passed.
        #
        # Measured fail-OPEN, shipped config, live gate: baseline
        # approved=False cost=54.300; with impact_eta=NaN approved=TRUE
        # cost=nan. Both profit gates below are written as `x < y`, which is
        # False on NaN, so a NaN cost silently satisfies BOTH and the entry is
        # approved with an unknown cost. Refusing is the only safe direction:
        # an unknown cost is not a small cost.
        #
        # PT_INVALID_INPUT, not a new code - it already means exactly this and
        # already fires for non-finite at :233. Standing precedent for the
        # class: RP-052 (cut #10 B3).
        if not _fin(cost) or not _fin(edge):
            d.reasons.append(tag(Code.PT_INVALID_INPUT,
                                 f"non-finite cost={cost!r} edge={edge!r} - "
                                 f"the profit gates compare with '<', which "
                                 f"is False on NaN, so this would APPROVE"))
            return d

        ratio = self.min_edge_cost_ratio + max(extra_edge_ratio, 0.0)
        if edge < ratio * cost and not exploring:
            d.reasons.append(tag(Code.PT_EDGE_RATIO,
                                 f"edge {edge:.1f}bps < {ratio:.2f}x cost "
                                 f"{cost:.1f}bps"))
            return d

        # ---- fill-probability-weighted EV (maker only) ----------------------
        if taker:
            p_fill, ev = 1.0, edge - cost
        else:
            dist_bps = self.maker_dist_bps(ctx.kraken_book, ref_price)
            p_fill, ev = self.maker_p_fill_ev(edge, cost, dist_bps,
                                              sigma_bar_bps)
        d.p_fill, d.ev_bps = float(p_fill), float(ev)
        if ev < self.ev_min_bps and not exploring:
            d.reasons.append(tag(Code.PT_EV_NEGATIVE,
                                 f"EV {ev:+.2f}bps @ p_fill {p_fill:.2f} "
                                 f"< {self.ev_min_bps:.2f} floor"))
            return d

        # dry-run exploration that would have failed a profit gate is TAKEN for
        # the label, but the bypass is recorded so it is auditable and the
        # operator sees a net-thin learning trade as exactly that.
        if exploring and (edge < ratio * cost or ev < self.ev_min_bps):
            d.reasons.append(tag(Code.PT_EXPLORE_BYPASS,
                                 f"edge {edge:.1f}/cost {cost:.1f} EV {ev:+.2f} "
                                 f"bypassed for dry-run label acquisition"))

        d.approved = True
        d.size_units = size
        d.reasons.append(tag(Code.PT_APPROVED,
                             f"edge {edge:.1f} / cost {cost:.1f} "
                             f"(as={as_penalty:.1f}) EV {ev:+.2f}bps "
                             f"@ p_fill {p_fill:.2f}"))
        return d
