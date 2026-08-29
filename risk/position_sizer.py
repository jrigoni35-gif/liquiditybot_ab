"""
risk/position_sizer.py — rev 2.0 (Assurance Build)

Fractional Kelly, corrected for the two things rev 1 ignored and that
dominate at a 25/40bps fee tier and a hard 15% drawdown halt:

  COST-ADJUSTED PAYOFFS. Kelly on gross win/loss overstates f* on
  every trade because costs shrink wins and inflate losses. Rev 2
  computes  b_net = (avg_win - rt_cost) / (avg_loss + rt_cost)  and
  additionally requires p*avg_win_net > (1-p)*avg_loss_net before any
  sizing happens — a positive-gross / negative-net setup sizes to
  exactly zero instead of small.

  DRAWDOWN THROTTLE (SZ-050). The hard stop at 15% is a cliff; optimal
  behavior near a cliff is to decelerate, not to keep full speed until
  impact. Risk scales by (1 - dd/hard_stop)^dd_throttle_power
  (default 1.5, floor 0.15): at 0% drawdown full size, at half the
  halt distance ~35% size, approaching the halt ~floor. This converts
  the survival constraint into geometry the sizing already obeys —
  the standard drawdown-control modification to Kelly betting.

Everything else preserved: veto composition (regime, direction,
p-bar with counter-trend bonus, multipliers, inventory, leverage,
min ticket, cooldown), interface, and the public `.b` attribute
(now the NET payoff ratio, which is what expected-value math should
have been using everywhere downstream anyway).
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from core.codes import Code, tag
from core.sanitize import is_finite as _fin

log = logging.getLogger("liquiditybot.risk.position_sizer")

EPS = 1e-9


@dataclass
class SizeDecision:
    usd: float
    units: float
    p_win: float
    kelly_f: float
    payoff_b: float
    reasons: list = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.usd > EPS and self.units > EPS


def payoff_ratio_from_config(profit_cfg: dict, risk_cfg: dict,
                             rt_cost_pct: float = 0.0,
                             reach_decay: float = 0.65) -> float:
    """Average win / average loss implied by the tier + stop structure,
    NET of round-trip cost. Tiers fire sequentially with decaying reach:
    each next tier is `reach_decay` times as likely as the previous — a
    modeling assumption that feeds b/b_net and therefore the Kelly
    breakeven, so it is a CONFIG knob (position_sizer.tier_reach_decay),
    not a buried constant. Default preserves the historical 0.65.

    Tier weights compound in ORIGINAL-position space (2026-07-29 unit
    audit): the engine's `close_pct_of_position` contract is % of the
    CURRENT (remaining) size (risk/profit_tiers.py:191,351), so tier k
    banks `close_frac_k x prod(1-close_frac_j, j<k)` of the original
    position — 25% each = 25.0/18.75/14.06/10.55 of original, not 25
    flat. The old flat weighting silently treated the knob as
    %-of-original, overstating deep-tier mass and b_net (~0.58 vs the
    true ~0.45 on the shipped geometry) and sitting the derived p-bar
    ~0.06 too low. `reach_decay` stays likelihood-only, exactly as its
    docstring says — the size decay is a separate factor, not a re-tune
    of reach."""
    tiers = [profit_cfg.get(f"tier_{i}", {}) for i in range(1, 5)]
    reach, remaining, w_sum, p_sum = 1.0, 1.0, 0.0, 0.0
    for t in tiers:
        trig = float(t.get("trigger_pct_gain", 0.0))
        close_frac = float(t.get("close_pct_of_position", 0.0)) / 100.0
        orig_frac = remaining * close_frac
        w_sum += reach * trig * orig_frac
        p_sum += reach * orig_frac
        remaining *= max(1.0 - close_frac, 0.0)
        reach *= reach_decay
    avg_win = w_sum / p_sum if p_sum > 0 else 2.0
    avg_loss = float(risk_cfg.get("stop_loss_pct", 2.0))
    win_net = max(avg_win - rt_cost_pct, 0.0)
    loss_net = avg_loss + rt_cost_pct
    return max(win_net / max(loss_net, EPS), 0.05)


class PositionSizer:
    def __init__(self, config: dict, profit_cfg: dict, risk_cfg: dict,
                 pretrade_cfg: dict | None = None, capital_cfg: dict | None = None,
                 protocols=None):
        cfg = config or {}
        # optional advanced overlay (risk.protocols.RiskProtocolStack);
        # None preserves pre-overlay behavior exactly
        self.protocols = protocols
        self.kelly_fraction = float(cfg.get("kelly_fraction", 0.25))
        self.kelly_cap = float(cfg.get("kelly_cap", 0.12))
        self.min_p_win = float(cfg.get("min_p_win", 0.55))
        # THE cap that actually bounds a live entry (applied at :540).
        # capital_management's identically-named key feeds only
        # CapitalManager.calculate_position_size, which has no callers - so
        # this fallback IS the live cap whenever the position_sizer copy is
        # missing. It went missing once (deleted by an unrelated commit,
        # ae4b5314) and ran at 10.0 for weeks against the operator's
        # configured 25, because config_guard's parity check resolved this
        # key with the OTHER copy as its default. The default stays 10.0 for
        # interface stability (CLAUDE.md invariant 7) and the guard now uses
        # a None sentinel, so a missing key FATALs instead of reading as
        # parity - never rely on this fallback being noticed.
        self.max_position_pct = float(
            cfg.get("max_position_size_pct_of_capital", 10.0))
        self.min_ticket_usd = float(cfg.get("min_ticket_usd", 25.0))
        self.entry_cooldown_sec = float(
            cfg.get("entry_cooldown_min", 20.0)) * 60.0
        self.dd_throttle_power = max(float(
            cfg.get("dd_throttle_power", 1.5)), 0.0)
        self.dd_throttle_floor = min(max(float(
            cfg.get("dd_throttle_floor", 0.15)), 0.0), 1.0)
        self.hard_stop_dd_pct = float(
            (capital_cfg or {}).get("hard_stop_drawdown_pct", 15.0))
        # round-trip cost in % for net payoffs: maker ENTRY (resting limit,
        # OM-011) + taker EXIT. The old 2*maker under-priced the exit leg -
        # exits fill through the touch (taker), so the realized round-trip was
        # maker+taker, not 2*maker. b_net was therefore too generous and Kelly
        # allocated to marginal edges that realized as cost overruns (8/8
        # live postmortems, 35-54bps over the estimate). Sizing on the TRUE
        # net win/loss distribution (matching the pre-trade gate's exit-leg
        # convention) shrinks marginal tickets toward zero. Maker-first
        # profit exits (below) recapture part of this, but the sizer stays
        # honest-worst-case: it never assumes a fill it hasn't earned.
        pt = pretrade_cfg or {}
        maker = float(pt.get("maker_fee_bps", 25.0))
        taker = float(pt.get("taker_fee_bps", 40.0))
        self.rt_cost_pct = (maker + taker) / 100.0
        # exploration label-acquisition floor: the sizer floors at the MARK but
        # the pre-trade gate recomputes notional at the QUOTE (a maker buy rests
        # below the mark), so a ticket floored to exactly min_order_usd lands a
        # few cents under and dies PT-031. Floor exploration a margin above the
        # pretrade min-order so it clears after the quote gap + lot rounding.
        self.min_order_usd = float(pt.get("min_order_usd", 25.0))
        self.explore_floor_mult = float(cfg.get("explore_floor_mult", 1.2))
        # COST DECOMPOSITION (no double counting):
        #   .b       gross payoff ratio — main derives the alpha ESTIMATE
        #            from it, and the pre-trade gate charges execution
        #            costs against that alpha exactly once.
        #   .b_net   payoff ratio net of round-trip fees — what the
        #            realized win/loss distribution actually looks like,
        #            therefore what Kelly must size on. f* > 0 on b_net
        #            IS the net-expectancy condition (p > 1/(1+b_net)).
        self.tier_reach_decay = min(max(float(
            cfg.get("tier_reach_decay", 0.65)), 0.05), 1.0)
        self.b = payoff_ratio_from_config(profit_cfg or {}, risk_cfg or {},
                                          rt_cost_pct=0.0,
                                          reach_decay=self.tier_reach_decay)
        self.b_net = payoff_ratio_from_config(profit_cfg or {},
                                              risk_cfg or {},
                                              rt_cost_pct=self.rt_cost_pct,
                                              reach_decay=self.tier_reach_decay)
        # per-trade BRACKET reference: the legacy stop_loss_pct this rev's
        # config was tuned around. A bracket call's post-Kelly notional is
        # scaled by (stop_loss_pct_ref / sl_pct) so risk-in-size stays on
        # the same dollar-risk scale as the legacy 2%-stop geometry as the
        # per-trade stop widens or tightens (spec D3).
        self.stop_loss_pct_ref = float((risk_cfg or {}).get(
            "stop_loss_pct", 2.0))
        # DERIVED ENTRY BAR (2026-07-27 drought diagnosis, operator-directed):
        # an absolute min_p_win is geometry-blind — the shipped 0.55 sat BELOW
        # the net-Kelly breakeven (a VOLATILE number: ~0.83 at cut-#8 40/80
        # fees + 1.2% rt cost, was ~0.632 pre-cut - re-derive from the live
        # tiers/stop/fees, never cite a frozen value), a
        # phantom the config guard had been flagging: entries in
        # [bar, breakeven) passed the bar only to die SZ-030 one step later,
        # and any tier/fee change silently re-breaks an absolute number.
        # mode "derived" pins the bar to the geometry itself:
        # max(breakeven + p_bar_edge_margin, min_p_win floor). The floor is
        # min_p_win's honest remaining role. Margin ships 0.0 — pure
        # de-phantomization, no new fitted number; the exploration synthetic
        # p (0.64) must keep clearing the bar or the F0b probe trickle dies,
        # which the config guard enforces with clearance headroom.
        # mode "absolute" (code default) preserves the historical bar for
        # every existing caller (CLAUDE.md invariant 7).
        self.p_bar_mode = str(cfg.get("p_bar_mode", "absolute"))
        self.p_bar_edge_margin = float(cfg.get("p_bar_edge_margin", 0.0))
        if self.p_bar_mode == "derived":
            self.p_bar_base = max(1.0 / (1.0 + self.b_net)
                                  + self.p_bar_edge_margin, self.min_p_win)
        else:
            self.p_bar_base = self.min_p_win
        # vol scaling of the ticket: LIFTED from a buried
        # `35.0 / max(sigma, 5.0)` clamped [0.3, 1.5] — an undocumented
        # SECOND vol-targeting layer living in the sizing path (the explicit
        # one, risk_protocols.vol_target, ships disabled with a note that it
        # "overlaps"... this was the overlap). Same defaults, now visible,
        # guarded, and coherence-checked against the protocol layer.
        self.vol_target_ann_pct = max(float(
            cfg.get("vol_target_ann_pct", 35.0)), 1.0)
        self.vol_sigma_floor_pct = max(float(
            cfg.get("vol_sigma_floor_pct", 5.0)), 0.1)
        self.vol_scalar_min = max(float(cfg.get("vol_scalar_min", 0.3)), 0.0)
        self.vol_scalar_max = max(float(cfg.get("vol_scalar_max", 1.5)),
                                  self.vol_scalar_min)
        self.avg_loss_pct = float((risk_cfg or {}).get("stop_loss_pct", 2.0))
        # inventory-aware aggression: lean in when the book is light,
        # back off as short-term entry clustering or long-term gross
        # exposure builds. Bounds are clamped so misconfiguration can
        # neither zero the trade nor more-than-1.5x it.
        ia = cfg.get("inventory_aggression", {}) or {}
        self.ia_enabled = bool(ia.get("enabled", False))
        self.ia_light_boost = min(max(
            float(ia.get("light_boost", 1.10)), 1.0), 1.5)
        self.ia_heavy_cut = min(max(
            float(ia.get("heavy_cut", 0.65)), 0.2), 1.0)
        self.ia_window_s = max(
            float(ia.get("short_window_hours", 6.0)), 0.25) * 3600.0
        self.ia_max_recent = max(int(ia.get("max_recent_entries", 3)), 1)
        self.ia_full_heat = min(max(
            float(ia.get("full_book_heat_frac", 0.35)), 0.05), 1.0)
        # Avellaneda-Stoikov reservation skew, taker transplant: the A-S
        # reservation price r = s - q*gamma*sigma^2*(T-t) prices the NEXT
        # trade against current SIGNED inventory. For a taker that means:
        # an entry that INCREASES |net exposure| is scaled down linearly
        # in q (and quadratically in vol, per the sigma^2 term); an entry
        # that REDUCES it is never penalized - it IS the liquidation the
        # reservation price asks for. Empirical basis (A-S Table 1): the
        # skewed strategy gives up ~6% expected profit for >2x lower P&L
        # variance. Modes: off / shadow (log would-be multiplier, apply
        # nothing) / active. Distinct from inventory_aggression, which is
        # UNSIGNED (gross load + entry clustering) and direction-blind.
        sk = cfg.get("inventory_skew", {}) or {}
        self.sk_mode = str(sk.get("mode", "shadow")).lower()
        self.sk_gamma = max(float(sk.get("gamma", 0.5)), 0.0)
        self.sk_sigma_ref = max(float(sk.get("sigma_ref_pct", 60.0)), 1.0)
        self.sk_amp_min = max(float(sk.get("amp_min", 0.25)), 0.0)
        self.sk_amp_max = max(float(sk.get("amp_max", 4.0)), self.sk_amp_min)
        self.sk_floor = min(max(float(sk.get("floor_mult", 0.25)), 0.05), 1.0)
        self._last_entry: dict = {}
        log.info("sizer payoff b=%.2f gross / %.2f net of %.2f%% rt cost "
                 "(net p(win) breakeven %.3f), kelly_fraction=%s, "
                 "p(win) bar=%.3f (%s, floor %s), dd throttle "
                 "power=%.1f floor=%.2f",
                 self.b, self.b_net, self.rt_cost_pct,
                 1.0 / (1.0 + self.b_net), self.kelly_fraction,
                 self.p_bar_base, self.p_bar_mode, self.min_p_win,
                 self.dd_throttle_power, self.dd_throttle_floor)

    # one-shot guard for the wiring warning in _open_book below
    _warned_no_book = False

    @staticmethod
    def _open_book(state) -> list:
        """The open book, via the accessor PortfolioState actually has.

        2026-08-09 INCIDENT: the three heat/inventory readers below each
        did `getattr(state, "positions", {}).values()`. PortfolioState
        stores the book in `_positions` and exposes it as
        `open_positions()`; it has NO `positions` attribute, so the
        getattr default was taken UNCONDITIONALLY and every one of them
        read an EMPTY BOOK forever. Consequences, all measured live with
        5 open positions and 11.8% gross heat:
          * _open_heat_frac -> 0.0, so RiskProtocolStack's portfolio-heat
            veto (max_portfolio_heat_frac 0.35, RP_HEAT_FULL) could never
            fire - the branch was unreachable in production;
          * _signed_heat_frac -> 0.0, so the signed-inventory reservation
            skew (SZ-061) never applied;
          * _inventory_aggression -> u=0, pinning the multiplier at
            light_boost 1.10 - a permanent 10% size-UP as if the book
            were empty, where it should taper toward heavy_cut 0.65 as
            heat approaches full_book_heat_frac.
        Three risk controls silently dead, all in the permissive
        direction. Centralised here so one accessor serves all three and
        the class cannot recur site-by-site."""
        get = getattr(state, "open_positions", None)
        if callable(get):
            try:
                book: Any = get()        # Any: callable() narrowing would
                return list(book)        # otherwise type this `object`
            except TypeError:            # None / non-iterable return: treat
                pass                     # as unwired, fall through to warn
        # A state object that cannot report its book is a WIRING ERROR, and
        # returning [] silently is precisely how the original defect hid for
        # so long: an empty book and a dead reader produce the identical
        # benign 0.0. Keep the hot path non-raising (a sizing call must
        # never take down a cycle) but make the condition VISIBLE - a
        # never-logged risk control is indistinguishable from a satisfied
        # one. Logged once per process; the AST pin in
        # tests/test_heat_reads_the_book.py stops the class returning at
        # authoring time.
        if not PositionSizer._warned_no_book:
            PositionSizer._warned_no_book = True
            log.warning(
                "position sizer received a state with no open_positions() - "
                "heat, signed inventory and the aggression taper are all "
                "reading an EMPTY BOOK (%s). Risk controls that depend on "
                "them are inert until this is wired.", type(state).__name__)
        return []

    @staticmethod
    def _open_heat_frac(state, marks, equity) -> float:
        """Gross open notional as a fraction of equity, marked to the
        freshest price (entry price as fallback). Never raises."""
        heat = 0.0
        try:
            for p in PositionSizer._open_book(state):
                px = (marks or {}).get(getattr(p, "symbol", ""), 0.0) or \
                    getattr(p, "entry_price", 0.0)
                heat += abs(float(getattr(p, "size", 0.0) or 0.0)) * \
                    max(float(px or 0.0), 0.0)
            return heat / equity if equity > EPS else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _signed_heat_frac(state, marks, equity) -> float:
        """NET signed exposure (long +, short -) as a fraction of equity.
        Hedges count signed too - they exist to pull this toward zero.
        Never raises."""
        net = 0.0
        try:
            for p in PositionSizer._open_book(state):
                px = (marks or {}).get(getattr(p, "symbol", ""), 0.0) or \
                    getattr(p, "entry_price", 0.0)
                notional = abs(float(getattr(p, "size", 0.0) or 0.0)) * \
                    max(float(px or 0.0), 0.0)
                sign = 1.0 if getattr(p, "direction", "long") == "long" \
                    else -1.0
                net += sign * notional
            return net / equity if equity > EPS else 0.0
        except Exception:
            return 0.0

    def _inventory_skew(self, state, marks, equity, direction: str,
                        sigma_annual_pct: float) -> tuple:
        """(multiplier, q) - A-S reservation skew. q = signed net heat
        normalized by the full-book fraction, clipped to [-1, 1]; only an
        entry in the SAME direction as q is penalized:
        mult = max(floor, 1 - gamma * (q . d) * (sigma/sigma_ref)^2-amp).
        Inventory-reducing entries and an empty book are neutral (1.0)."""
        q = self._signed_heat_frac(state, marks, equity) \
            / max(self.ia_full_heat, EPS)
        q = max(-1.0, min(1.0, q))
        d_sign = 1.0 if direction == "long" else -1.0
        same = q * d_sign
        if same <= EPS:
            return 1.0, q
        s = sigma_annual_pct if _fin(sigma_annual_pct) \
            and sigma_annual_pct > 0.0 else self.sk_sigma_ref
        amp = min(max((s / self.sk_sigma_ref) ** 2, self.sk_amp_min),
                  self.sk_amp_max)
        return max(self.sk_floor, 1.0 - self.sk_gamma * same * amp), q

    def _inventory_aggression(self, state, marks, equity,
                              now: float) -> tuple:
        """(multiplier, u_long, u_short). u_long = gross open heat vs the
        full-book fraction (how loaded the book is overall); u_short =
        positions opened inside the recent window vs the clustering
        budget (how fast risk was just added). The multiplier moves
        linearly from light_boost at an empty book to heavy_cut at a
        full/fast one — monotone, bounded, never zero. Never raises."""
        u_long = min(self._open_heat_frac(state, marks, equity)
                     / max(self.ia_full_heat, EPS), 1.0)
        recent = 0
        try:
            cutoff = now - self.ia_window_s
            for p in PositionSizer._open_book(state):
                opened = getattr(p, "opened_at", None)
                if isinstance(opened, datetime):
                    o = opened if opened.tzinfo is not None \
                        else opened.replace(tzinfo=timezone.utc)
                    if o.timestamp() >= cutoff:
                        recent += 1
        except Exception:
            recent = 0
        u_short = min(recent / self.ia_max_recent, 1.0)
        u = max(u_long, u_short)
        mult = self.ia_light_boost + \
            (self.ia_heavy_cut - self.ia_light_boost) * u
        return mult, u_long, u_short

    def _vol_scalar(self, sigma_annual_pct: float) -> float:
        """Ticket multiplier from realized vol vs the configured target:
        full-ish size at/below target vol, shrinking as vol rises, clamped to
        [vol_scalar_min, vol_scalar_max]. Non-finite sigma degrades to the
        floor value (treat unknown vol as high vol, never as low)."""
        # sigma <= 0 is as uninformative as NaN — a degenerate flat-candle
        # window must get the MIN scalar, not sail through the floor into the
        # MAX boost (0 -> floored to 5% -> 35/5=7 -> clamped to max was the
        # largest size on the least information; audit MP-9 2026-07-17)
        if not _fin(sigma_annual_pct) or sigma_annual_pct <= 0.0:
            return self.vol_scalar_min
        return min(max(self.vol_target_ann_pct
                       / max(sigma_annual_pct, self.vol_sigma_floor_pct),
                       self.vol_scalar_min), self.vol_scalar_max)

    def note_entry(self, asset: str, now: Optional[float] = None):
        self._last_entry[asset] = now if now is not None else time.time()

    def in_cooldown(self, asset: str, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        last = self._last_entry.get(asset)
        return last is not None and (now - last) < self.entry_cooldown_sec

    # ------------------------------------------------------------------
    def size(self, asset: str, direction: str, price: float, p_win: float,
             equity: float, state, macro_state, vol_state, liq_state,
             sent_risk_mult: float, inventory_mgr, lev_decision,
             marks: dict, now: Optional[float] = None,
             risk_scale: float = 1.0,
             symbol: Optional[str] = None,
             floor_to_min: bool = False,
             bracket: "tuple[float, float] | None" = None) -> SizeDecision:
        d = SizeDecision(usd=0.0, units=0.0,
                         p_win=p_win if _fin(p_win) else 0.0,
                         kelly_f=0.0, payoff_b=self.b)
        now = now if now is not None else time.time()

        # ---- fail-closed input validation --------------------------------
        if not (_fin(price) and price > EPS and _fin(equity)
                and equity > EPS and _fin(p_win) and 0.0 <= p_win <= 1.0):
            d.reasons.append(tag(Code.SZ_INVALID_INPUT,
                                 f"price={price!r} equity={equity!r} "
                                 f"p={p_win!r}"))
            return d
        if self.in_cooldown(asset, now):
            d.reasons.append(tag(Code.SZ_COOLDOWN, "entry cooldown active"))
            return d
        if not macro_state.playbook.get("allow_new", True):
            d.reasons.append(tag(Code.SZ_REGIME_BLOCK,
                                 f"regime {macro_state.label}"))
            return d
        if not macro_state.allows_direction(direction):
            d.reasons.append(tag(Code.SZ_DIRECTION_BLOCK,
                                 f"regime {macro_state.label} blocks "
                                 f"{direction}"))
            return d
        # per-trade BRACKET (spec D3): when a caller passes a labeled
        # (pt_pct, sl_pct) bracket, THAT bet - not the config-average tier
        # geometry - drives the breakeven, the bar (in derived mode), the
        # Kelly f*, and the notional. None preserves self.b_net exactly,
        # so every legacy caller is byte-identical (CLAUDE.md invariant 7).
        b_net = self.b_net
        pt_pct = sl_pct = None
        if bracket is not None:
            pt_pct, sl_pct = float(bracket[0]), float(bracket[1])
            if not (_fin(pt_pct) and _fin(sl_pct) and pt_pct > EPS
                    and sl_pct > EPS):
                d.reasons.append(tag(Code.SZ_INVALID_INPUT,
                                     f"bracket={bracket!r}"))
                return d
            # the bet being sized IS the labeled bracket: worst-case costs,
            # per-trade breakeven, and dollar-risk normalized to the legacy
            # 2%-stop scale (risk lives in SIZE - operator decision, sl is
            # never capped here).
            b_net = max((pt_pct - self.rt_cost_pct)
                        / max(sl_pct + self.rt_cost_pct, EPS), EPS)
        p_bar = (max(1.0 / (1.0 + b_net) + self.p_bar_edge_margin,
                     self.min_p_win)
                 if (bracket is not None and self.p_bar_mode == "derived")
                 else self.p_bar_base)
        if macro_state.is_counter_trend(direction):
            p_bar += macro_state.playbook.get("counter_trend_conf_bonus",
                                              0.15)
        if p_win < p_bar:
            basis = (f" (net breakeven {1.0 / (1.0 + b_net):.3f}"
                     f" + margin {self.p_bar_edge_margin:.3f}, derived)"
                     if self.p_bar_mode == "derived" else "")
            if bracket is not None:
                basis += (f" [bracket pt={pt_pct:.2f}% sl={sl_pct:.2f}% "
                         f"b={b_net:.3f}]")
            d.reasons.append(tag(Code.SZ_PWIN_BAR,
                                 f"p {p_win:.2f} below bar {p_bar:.2f}"
                                 f"{basis}"))
            return d

        # ---- Kelly core on NET payoffs --------------------------------------
        # f* > 0 on the net distribution IS the net-expectancy check:
        # p must exceed 1/(1+b_net) or the structure loses money after
        # fees regardless of sizing.
        f_star = p_win - (1.0 - p_win) / b_net
        f = max(f_star, 0.0) * self.kelly_fraction
        f = min(f, self.kelly_cap)
        d.kelly_f = f
        if f <= EPS:
            d.reasons.append(tag(Code.SZ_KELLY_ZERO,
                                 f"net-Kelly f* <= 0: p {p_win:.2f} below "
                                 f"net breakeven "
                                 f"{1.0 / (1.0 + b_net):.3f} "
                                 f"(b_net={b_net:.2f})"))
            return d

        usd = equity * f
        if bracket is not None:
            # risk-in-size: normalize dollar risk to the legacy 2%-stop
            # scale so a per-trade stop that is 2x as wide sizes to half
            # the notional at the same edge (spec D3 risk-in-size).
            # sl_pct is always set here: bracket is not None only reaches
            # this point via the validated branch above, which returns
            # before here on any bad bracket (narrows for the type checker).
            assert sl_pct is not None
            usd *= (self.stop_loss_pct_ref / sl_pct)
        # payoff_b reports the bet actually priced: the bracket's own b_net
        # when one was supplied, otherwise the GROSS legacy self.b (matches
        # the dataclass default at construction) -- never the legacy NET
        # b_net, which would silently change a public field on every
        # no-bracket caller (CLAUDE.md invariant 7: byte-identical legacy
        # path; see test_no_bracket_is_byte_identical_legacy).
        d.payoff_b = b_net if bracket is not None else self.b

        # ---- drawdown throttle (SZ-050): decelerate toward the halt --------
        try:
            # MARK-TO-MARKET, peak-based drawdown (equity here is the MTM
            # sizing base): decelerate on real economic drawdown incl.
            # unrealized loss, not only realized losses.
            dd = max(float(state.drawdown_mtm_pct(equity)), 0.0)
        except Exception:
            dd = 0.0
        if self.hard_stop_dd_pct > EPS and dd > 0:
            frac = min(dd / self.hard_stop_dd_pct, 1.0)
            throttle = max((1.0 - frac) ** self.dd_throttle_power,
                           self.dd_throttle_floor)
            usd *= throttle
            if throttle < 0.999:
                d.reasons.append(tag(
                    Code.SZ_DD_THROTTLE,
                    f"dd {dd:.1f}%/{self.hard_stop_dd_pct:.0f}% "
                    f"-> x{throttle:.2f}"))

        # ---- multiplier stack ------------------------------------------------
        usd *= macro_state.playbook.get("size_mult", 1.0)
        vol_scalar = self._vol_scalar(vol_state.sigma_annual_pct)
        usd *= vol_scalar
        usd *= max(min(sent_risk_mult if _fin(sent_risk_mult) else 1.0,
                       1.2), 0.0)
        usd *= liq_state.size_mult
        if self.ia_enabled:
            ia_mult, u_l, u_s = self._inventory_aggression(
                state, marks, equity, now)
            usd *= ia_mult
            if abs(ia_mult - 1.0) > 0.01:
                d.reasons.append(tag(Code.SZ_INV_AGGRO,
                                     f"x{ia_mult:.2f} (book u_long={u_l:.2f}"
                                     f" u_short={u_s:.2f})"))
        if self.sk_mode in ("shadow", "active"):
            sk_mult, sk_q = self._inventory_skew(
                state, marks, equity, direction, vol_state.sigma_annual_pct)
            if abs(sk_mult - 1.0) > 0.01:
                if self.sk_mode == "active":
                    usd *= sk_mult
                    d.reasons.append(tag(Code.SZ_INV_SKEW,
                                         f"x{sk_mult:.2f} (q={sk_q:+.2f} "
                                         f"A-S reservation skew)"))
                else:
                    d.reasons.append(tag(Code.SZ_INV_SKEW,
                                         f"shadow: would x{sk_mult:.2f} "
                                         f"(q={sk_q:+.2f})"))
        usd *= max(min(risk_scale if _fin(risk_scale) else 1.0, 1.0), 0.0)
        if usd <= EPS:
            d.reasons.append(tag(Code.SZ_MULT_ZERO,
                                 f"a multiplier zeroed the trade "
                                 f"(liq={liq_state.label}, "
                                 f"sent={sent_risk_mult:.2f})"))
            return d

        # ---- advanced protocol overlay (RP-*): CVaR / gap / budget / heat ----
        # (heat = gross open notional / equity; the Position field is
        # `size` — an earlier draft read a nonexistent `units` attribute,
        # which made heat identically zero and RP-050/051 unreachable)
        if self.protocols is not None:
            heat = self._open_heat_frac(state, marks, equity)
            p_mult, p_reasons = self.protocols.entry_multiplier(
                proposed_frac=usd / equity, equity=equity,
                sigma_ann_pct=vol_state.sigma_annual_pct,
                asset_symbol=symbol or asset, open_heat_frac=heat,
                now=now)
            d.reasons.extend(p_reasons)
            usd *= p_mult
            if usd <= EPS:
                return d

        # ---- exploration label-acquisition floor ------------------------------
        # an exploration entry exists to BUY A LABEL; at small equity the
        # kelly x multiplier stack routinely sizes below the min ticket and
        # every learning trade dies SZ-042 (observed at $800: $1-4 tickets,
        # zero label flow, kill-switch deadlock). Floor the nonzero result at
        # the min ticket: every hard veto above (regime, p-bar, zero-mult,
        # cooldown, RP hard vetoes) has already had its say, and the caps
        # below still bound it. Dry-run only by construction: main only sets
        # floor_to_min on exploration entries, which are hard-gated dry_run.
        explore_floor = max(self.min_ticket_usd,
                            self.min_order_usd * self.explore_floor_mult)
        if floor_to_min and EPS < usd < explore_floor:
            d.reasons.append(tag(Code.SZ_EXPLORE_FLOOR,
                                 f"${usd:,.2f} -> ${explore_floor:,.2f}"
                                 f" exploration label-acquisition floor"))
            usd = explore_floor

        # ---- caps -------------------------------------------------------------
        usd = min(usd, equity * self.max_position_pct / 100.0)
        add = inventory_mgr.can_add(state, asset, direction, usd, equity,
                                    marks)
        if not add.allowed:
            d.reasons.append(tag(add.code or Code.SZ_INVENTORY, add.reason))
            return d
        usd = min(usd, add.allowed_usd)
        if lev_decision is not None:
            if lev_decision.headroom_usd <= EPS:
                d.reasons.append(tag(Code.SZ_LEVERAGE,
                                     "no leverage headroom"))
                return d
            usd = min(usd, lev_decision.headroom_usd)
        if usd < self.min_ticket_usd:
            d.reasons.append(tag(Code.SZ_MIN_TICKET,
                                 f"${usd:,.0f} below minimum"))
            return d

        d.usd = usd
        d.units = usd / price
        # NOTE (T4 scope bound): this detail string always reports the
        # legacy config-average self.b / self.b_net, even on a bracket-
        # priced approval -- it is not re-derived from the per-trade
        # bracket b_net used above for the bar/Kelly/notional math. Only
        # SZ_PWIN_BAR's detail (above) carries the bracket basis — a
        # deliberate scope bound: this approval string reports the legacy
        # config-average b/b_net even on bracket-priced approvals.
        d.reasons.append(tag(Code.SZ_APPROVED,
                             f"p={p_win:.2f} b={self.b:.2f} "
                             f"(net {self.b_net:.2f}) f={f:.3f} "
                             f"vol_scalar={vol_scalar:.2f} "
                             f"regime={macro_state.label} -> ${usd:,.0f}"))
        return d
