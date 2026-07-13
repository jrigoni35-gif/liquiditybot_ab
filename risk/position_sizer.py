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
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from core.codes import Code, tag

log = logging.getLogger("liquiditybot.risk.position_sizer")

EPS = 1e-9


def _fin(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


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
                             rt_cost_pct: float = 0.0) -> float:
    """Average win / average loss implied by the tier + stop structure,
    NET of round-trip cost. Tiers fire sequentially with decaying reach
    (each next tier ~65% as likely as the previous)."""
    tiers = [profit_cfg.get(f"tier_{i}", {}) for i in range(1, 5)]
    reach, w_sum, p_sum = 1.0, 0.0, 0.0
    for t in tiers:
        trig = float(t.get("trigger_pct_gain", 0.0))
        frac = float(t.get("close_pct_of_position", 0.0)) / 100.0
        w_sum += reach * trig * frac
        p_sum += reach * frac
        reach *= 0.65
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
        # round-trip cost in % for net payoffs: maker in + maker out at
        # the configured tier (conservative; taker exits cost more and
        # the pre-trade gate prices those separately)
        pt = pretrade_cfg or {}
        maker = float(pt.get("maker_fee_bps", 25.0))
        self.rt_cost_pct = 2.0 * maker / 100.0
        # COST DECOMPOSITION (no double counting):
        #   .b       gross payoff ratio — main derives the alpha ESTIMATE
        #            from it, and the pre-trade gate charges execution
        #            costs against that alpha exactly once.
        #   .b_net   payoff ratio net of round-trip fees — what the
        #            realized win/loss distribution actually looks like,
        #            therefore what Kelly must size on. f* > 0 on b_net
        #            IS the net-expectancy condition (p > 1/(1+b_net)).
        self.b = payoff_ratio_from_config(profit_cfg or {}, risk_cfg or {},
                                          rt_cost_pct=0.0)
        self.b_net = payoff_ratio_from_config(profit_cfg or {},
                                              risk_cfg or {},
                                              rt_cost_pct=self.rt_cost_pct)
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
        self._last_entry: dict = {}
        log.info("sizer payoff b=%.2f gross / %.2f net of %.2f%% rt cost "
                 "(net p(win) breakeven %.3f), kelly_fraction=%s, "
                 "min p(win)=%s, dd throttle power=%.1f floor=%.2f",
                 self.b, self.b_net, self.rt_cost_pct,
                 1.0 / (1.0 + self.b_net), self.kelly_fraction,
                 self.min_p_win, self.dd_throttle_power,
                 self.dd_throttle_floor)

    @staticmethod
    def _open_heat_frac(state, marks, equity) -> float:
        """Gross open notional as a fraction of equity, marked to the
        freshest price (entry price as fallback). Never raises."""
        heat = 0.0
        try:
            for p in getattr(state, "positions", {}).values():
                px = (marks or {}).get(getattr(p, "symbol", ""), 0.0) or \
                    getattr(p, "entry_price", 0.0)
                heat += abs(float(getattr(p, "size", 0.0) or 0.0)) * \
                    max(float(px or 0.0), 0.0)
            return heat / equity if equity > EPS else 0.0
        except Exception:
            return 0.0

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
            for p in getattr(state, "positions", {}).values():
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
             floor_to_min: bool = False) -> SizeDecision:
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
        p_bar = self.min_p_win
        if macro_state.is_counter_trend(direction):
            p_bar += macro_state.playbook.get("counter_trend_conf_bonus",
                                              0.15)
        if p_win < p_bar:
            d.reasons.append(tag(Code.SZ_PWIN_BAR,
                                 f"p {p_win:.2f} below bar {p_bar:.2f}"))
            return d

        # ---- Kelly core on NET payoffs --------------------------------------
        # f* > 0 on the net distribution IS the net-expectancy check:
        # p must exceed 1/(1+b_net) or the structure loses money after
        # fees regardless of sizing.
        f_star = p_win - (1.0 - p_win) / self.b_net
        f = max(f_star, 0.0) * self.kelly_fraction
        f = min(f, self.kelly_cap)
        d.kelly_f = f
        if f <= EPS:
            d.reasons.append(tag(Code.SZ_KELLY_ZERO,
                                 f"net-Kelly f* <= 0: p {p_win:.2f} below "
                                 f"net breakeven "
                                 f"{1.0 / (1.0 + self.b_net):.3f} "
                                 f"(b_net={self.b_net:.2f})"))
            return d

        usd = equity * f

        # ---- drawdown throttle (SZ-050): decelerate toward the halt --------
        try:
            dd = max(float(state.drawdown_pct()), 0.0)
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
        vol_scalar = min(max(35.0 / max(vol_state.sigma_annual_pct, 5.0),
                             0.3), 1.5)
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
        if floor_to_min and EPS < usd < self.min_ticket_usd:
            d.reasons.append(tag(Code.SZ_EXPLORE_FLOOR,
                                 f"${usd:,.2f} -> ${self.min_ticket_usd:,.2f}"
                                 f" exploration label-acquisition floor"))
            usd = self.min_ticket_usd

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
        d.reasons.append(tag(Code.SZ_APPROVED,
                             f"p={p_win:.2f} b={self.b:.2f} "
                             f"(net {self.b_net:.2f}) f={f:.3f} "
                             f"vol_scalar={vol_scalar:.2f} "
                             f"regime={macro_state.label} -> ${usd:,.0f}"))
        return d
