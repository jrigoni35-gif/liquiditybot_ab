"""Advanced risk protocol stack — institutional protection/profit overlay.

Design contract
---------------
* PURE MATH LIVES IN MODULE-LEVEL FUNCTIONS that accept scalars or numpy
  arrays (arithmetic + clips only). The Monte-Carlo trial harness
  (scripts/quant_trials.py) imports and vectorizes THESE EXACT functions,
  so what is simulated is what is deployed — no parallel implementation
  to drift.
* The stateful `RiskProtocolStack` only owns anchors and rolling buffers;
  every decision is a call into the pure functions.
* Fail direction: a component with missing/insufficient/NaN inputs is
  NEUTRAL (1.0) — the base sizer's own fail-closed validation still
  governs. Components fail toward ZERO only on affirmative evidence
  (budget spent, heat at cap). Exits are never touched here: the stack
  scales ENTRY sizing only; stops/tiers always run.
* Composition is multiplicative with a floor, except hard zeros
  (exhausted budget / full heat) which are absolute.

Components
----------
vol-target   size ∝ target_vol / realized_vol (DISABLED by default: the
             base sizer already carries a 35/sigma scalar; enabling both
             would double-punish. Provided for operators who prefer this
             formulation — turn the base scalar down if you enable it.)
CVaR budget  per-trade fraction capped so the position's historical
             expected shortfall over the expected holding horizon cannot
             exceed a fixed slice of equity.
gap-at-risk  fraction capped so a configured discontinuous shock (e.g.
             a -15% gap through every stop) cannot cost more than a
             fixed slice of equity. Stops do not exist inside a gap;
             this is the sizing answer to that fact.
loss budget  daily/weekly loss budgets measured from equity anchors.
             Sizing tapers linearly once a budget is part-spent and goes
             to ZERO new risk when spent — the anti-revenge-trading
             governor. Exits unaffected.
heat guard   total open notional (corr-weighted) capped as a fraction of
             equity; new entries only get the remaining headroom.
"""
from __future__ import annotations

import logging
import math
import time
from collections import deque
from typing import Optional

import numpy as np

from core.codes import Code, tag

# This module had NO logger until 2026-09-06. Its silent-skip defects (the
# loss-budget anchor roll, the NaN taper) were therefore unreportable by
# construction: there was nothing to report them WITH. Routed through
# `logging` per CLAUDE.md, so JsonlLogHandler picks it up like everything else.
log = logging.getLogger(__name__)

EPS = 1e-12


# ---------------------------------------------------------------------------
# pure math — scalar/array polymorphic, no state, no I/O
# ---------------------------------------------------------------------------
def vol_target_mult(sigma_ann_pct, target_ann_pct: float,
                    min_mult: float, max_mult: float):
    """Classic volatility targeting: exposure ∝ target/realized."""
    sig = np.maximum(np.asarray(sigma_ann_pct, float), 5.0)
    return np.clip(target_ann_pct / sig, min_mult, max_mult)


def es_historical(returns, alpha: float = 0.975) -> float:
    """Historical expected shortfall of a return sample as a POSITIVE
    loss fraction: mean of the worst (1-alpha) tail. NaN-safe; returns
    0.0 when the sample is empty/degenerate (callers gate on min_obs)."""
    r = np.asarray(returns, float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return 0.0
    k = max(int(math.ceil((1.0 - alpha) * r.size)), 1)
    tail = np.partition(r, k - 1)[:k]          # k most negative returns
    return float(max(-tail.mean(), 0.0))


def frac_cap_mult(max_frac, proposed_frac):
    """Multiplier that caps a proposed equity fraction at max_frac.
    <=0 headroom yields 0 (hard block); ample headroom yields 1."""
    prop = np.maximum(np.asarray(proposed_frac, float), EPS)
    return np.clip(np.asarray(max_frac, float) / prop, 0.0, 1.0)


def cvar_cap_frac(es_bar: float, horizon_bars: float,
                  es_budget_frac: float) -> float:
    """Max entry fraction such that fraction * ES_holding <= budget.
    Holding-period ES scales the per-bar ES by sqrt(horizon)."""
    es_hold = float(es_bar) * math.sqrt(max(horizon_bars, 1.0))
    if es_hold <= EPS:
        return float("inf")
    return es_budget_frac / es_hold


def gap_cap_frac(gap_shock_pct: float, max_equity_loss_pct: float) -> float:
    """Max entry fraction such that a gap_shock through the stop costs
    at most max_equity_loss of equity."""
    shock = max(gap_shock_pct, EPS) / 100.0
    return (max_equity_loss_pct / 100.0) / shock


def budget_taper_mult(spent_frac, taper_start: float, floor_mult: float):
    """1.0 until taper_start of the budget is spent, then linear decay
    to floor_mult at 100% spent, then HARD ZERO past 100%."""
    s = np.asarray(spent_frac, float)
    span = max(1.0 - taper_start, EPS)
    lin = 1.0 - (1.0 - floor_mult) * (s - taper_start) / span
    m = np.where(s <= taper_start, 1.0, np.clip(lin, floor_mult, 1.0))
    return np.where(s >= 1.0, 0.0, m)


def heat_headroom_frac(open_heat_frac, max_heat_frac: float,
                       assumed_corr: float):
    """Remaining corr-weighted heat headroom available to a new entry."""
    heat = np.maximum(np.asarray(open_heat_frac, float), 0.0)
    return np.maximum(max_heat_frac - assumed_corr * heat, 0.0)


def give_back_stop(entry_price, high_water, direction_long,
                   giveback_frac: float):
    """Stop level that locks in (1 - giveback_frac) of the peak open
    move. Long: entry + (1-g)*(hw-entry); short mirrored. Array-safe."""
    e = np.asarray(entry_price, float)
    h = np.asarray(high_water, float)
    keep = 1.0 - giveback_frac
    long_stop = e + keep * np.maximum(h - e, 0.0)
    short_stop = e - keep * np.maximum(e - h, 0.0)
    return np.where(direction_long, long_stop, short_stop)


# ---------------------------------------------------------------------------
# stateful overlay
# ---------------------------------------------------------------------------
class RiskProtocolStack:
    """Owns equity anchors + per-asset return buffers; composes the pure
    functions into a single (multiplier, reasons) entry-sizing decision.
    Never raises out of observe()/entry_multiplier()."""

    def __init__(self, cfg: Optional[dict] = None):
        cfg = cfg or {}
        # Times observe() declined to roll the loss-budget anchors because
        # equity was not finite and positive. Report-only; surfaced in the
        # runner status block so a DEAD guard and a HEALTHY day stop looking
        # byte-identical on the board. Never a decision input.
        self.anchor_skips = 0
        self.enabled = bool(cfg.get("enabled", True))
        vt = cfg.get("vol_target", {}) or {}
        self.vt_enabled = bool(vt.get("enabled", False))
        self.vt_target = float(vt.get("target_ann_vol_pct", 45.0))
        self.vt_min = float(vt.get("min_mult", 0.25))
        self.vt_max = float(vt.get("max_mult", 1.15))

        cv = cfg.get("cvar", {}) or {}
        self.cv_enabled = bool(cv.get("enabled", True))
        self.cv_alpha = float(cv.get("alpha", 0.975))
        self.cv_lookback = int(cv.get("lookback_bars", 288))
        self.cv_min_obs = int(cv.get("min_obs", 120))
        self.cv_budget = float(cv.get("es_budget_frac", 0.010))
        self.cv_horizon = float(cv.get("horizon_bars", 24))
        # Return-sample bar length. Every _bars knob above is denominated
        # in 5-minute bars (lookback 288 = one day, min_obs 120 = 10h,
        # sqrt(horizon_bars) holding scale), and both CI harnesses feed
        # one observe() per 300s bar — but the LIVE caller polls every
        # ~5s, and appending per-poll returns deflated es_bar by
        # ~sqrt(60), loosening the RP-040 cap ~7.75x (2026-07-29 unit
        # audit, cross-confirmed). observe() now samples the buffer on
        # THIS bar clock regardless of poll cadence, so live and
        # simulated CVaR see the same statistic by construction.
        self.cv_bar_sec = max(float(cv.get("bar_sec", 300.0)), 1.0)

        gp = cfg.get("gap", {}) or {}
        self.gap_enabled = bool(gp.get("enabled", True))
        self.gap_shock_pct = float(gp.get("gap_shock_pct", 15.0))
        self.gap_max_loss_pct = float(gp.get("max_equity_loss_pct", 4.0))

        bd = cfg.get("budget", {}) or {}
        self.bd_enabled = bool(bd.get("enabled", True))
        self.bd_daily_pct = float(bd.get("daily_loss_budget_pct", 2.5))
        self.bd_weekly_pct = float(bd.get("weekly_loss_budget_pct", 6.0))
        self.bd_taper_start = float(bd.get("taper_start", 0.5))
        self.bd_floor = float(bd.get("floor_mult", 0.15))

        ht = cfg.get("heat", {}) or {}
        self.ht_enabled = bool(ht.get("enabled", True))
        self.ht_max = float(ht.get("max_portfolio_heat_frac", 0.35))
        self.ht_corr = float(ht.get("assumed_corr", 0.9))

        self.stack_floor = float(cfg.get("stack_floor_mult", 0.10))

        # state
        self._rets: dict[str, deque] = {}
        self._last_mark: dict[str, float] = {}
        self._bar_anchor_ts: dict[str, float] = {}
        self._day_anchor: Optional[float] = None
        self._day_key: Optional[str] = None
        self._week_anchor: Optional[float] = None
        self._week_key: Optional[str] = None

    # ---------------- state feed ----------------
    @staticmethod
    def _keys(now: float) -> tuple[str, str]:
        t = time.gmtime(now)
        iso = time.strftime("%G-W%V", t)
        return time.strftime("%Y-%m-%d", t), iso

    def observe(self, equity: float, marks: Optional[dict] = None,
                now: Optional[float] = None) -> None:
        """Feed once per cycle. Rolls day/week anchors on UTC boundaries
        and appends per-asset log returns for the CVaR estimator."""
        try:
            now = now if now is not None else time.time()
            if math.isfinite(equity) and equity > EPS:
                dk, wk = self._keys(now)
                if self._day_key != dk:
                    self._day_key, self._day_anchor = dk, float(equity)
                if self._week_key != wk:
                    self._week_key, self._week_anchor = wk, float(equity)
            else:
                # THE SKIP IS NOW VISIBLE. This is the every-cycle hot path,
                # and a non-finite or non-positive equity previously skipped
                # the anchor roll with NO return, NO log and NO reason code -
                # contrast reanchor_week a few lines down, which returns False
                # on the same predicate. The consequence is that the
                # loss-budget anchors silently stop advancing while every
                # reader is told the stack is healthy.
                #
                # Worse, the status triple is BYTE-IDENTICAL for a dead guard
                # and a healthy day: ARMED {12.0, 5.0, 0.0} vs DEAD
                # {0.0, 0.0, 1.0} vs HEALTHY {0.0, 0.0, 1.0} through
                # runner.py's status block - the Grafana board cannot tell them
                # apart. `anchors_set` below is what separates them.
                #
                # OBSERVABILITY HALF ONLY. Making the NaN path fail CLOSED
                # (multiplier 0.0 + a veto) is an entry-decisioning and sizing
                # change and needs operator sign-off (docketed B3).
                self.anchor_skips += 1
                log.warning(tag(
                    Code.RP_WARMUP,
                    f"loss-budget anchors NOT rolled: equity={equity!r} is "
                    f"not finite and positive (skip #{self.anchor_skips}); "
                    f"day/week anchors are stale and the budget taper is "
                    f"reading a frozen denominator"))
            for sym, px in (marks or {}).items():
                if not (isinstance(px, (int, float)) and math.isfinite(px)
                        and px > EPS):
                    continue
                # bar-clock sampling: _last_mark holds the anchor BAR
                # close, not the last poll tick. A return is appended
                # only once cv_bar_sec has elapsed since the anchor, and
                # it compounds the whole bar (anchor close -> this px),
                # so poll cadence cannot change the statistic. Harness
                # callers stepping exactly one bar per observe() append
                # on every call — byte-identical to the old behavior.
                anchor_ts = self._bar_anchor_ts.get(sym)
                last = self._last_mark.get(sym)
                if anchor_ts is None or last is None or last <= EPS:
                    self._bar_anchor_ts[sym] = now
                    self._last_mark[sym] = float(px)
                    continue
                if now - anchor_ts >= self.cv_bar_sec:
                    buf = self._rets.setdefault(
                        sym, deque(maxlen=self.cv_lookback))
                    buf.append(math.log(px / last))
                    self._bar_anchor_ts[sym] = now
                    self._last_mark[sym] = float(px)
        except Exception:  # fed from the hot loop; must never raise  # nosec B110
            pass

    def reanchor_week(self, equity: float,
                      now: Optional[float] = None) -> bool:
        """Operator override (2026-08-08): re-anchor the WEEK loss budget
        at `equity`. Exists for BUG-ATTRIBUTABLE consumption - first use:
        the ADA hedge-churn class (fixed 5c111962/cf454d5e/FW-070) spent
        109% of ISO week 2026-W32 on manufactured fees and taper_mult
        0.0 blocked every entry through the weekend. Touches ONLY the
        anchor: weekly_pnl, pools and the day budget are untouched, and
        the natural ISO rollover keeps working (the key is refreshed so
        the next genuine week boundary re-anchors as always). Reached
        exclusively via the audited ControlChannel verb
        budget_reanchor_week (runner.handle_command); never over REST."""
        if not (isinstance(equity, (int, float)) and math.isfinite(equity)
                and equity > EPS):
            return False
        _, wk = self._keys(now if now is not None else time.time())
        self._week_key, self._week_anchor = wk, float(equity)
        return True

    def spent_fracs(self, equity: float) -> tuple[float, float]:
        def frac(anchor, budget_pct):
            if anchor is None or anchor <= EPS or budget_pct <= EPS:
                return 0.0
            loss = max((anchor - equity) / anchor, 0.0) * 100.0
            return loss / budget_pct
        return (frac(self._day_anchor, self.bd_daily_pct),
                frac(self._week_anchor, self.bd_weekly_pct))

    # ---------------- decision ----------------
    def entry_multiplier(self, proposed_frac: float, equity: float,
                         sigma_ann_pct: float, asset_symbol: str,
                         open_heat_frac: float,
                         now: Optional[float] = None
                         ) -> tuple[float, list]:
        reasons: list = []
        if not self.enabled:
            return 1.0, reasons
        try:
            mult = 1.0
            prop = max(float(proposed_frac), EPS)

            if self.vt_enabled and math.isfinite(sigma_ann_pct):
                m = float(vol_target_mult(sigma_ann_pct, self.vt_target,
                                          self.vt_min, self.vt_max))
                mult *= m
                if abs(m - 1.0) > 1e-3:
                    reasons.append(tag(Code.RP_VOL_TARGET,
                                       f"sigma {sigma_ann_pct:.0f}% vs "
                                       f"target {self.vt_target:.0f}% "
                                       f"-> x{m:.2f}"))

            if self.cv_enabled:
                buf = self._rets.get(asset_symbol)
                if buf is None:                    # asset name vs mark key
                    for k, v in self._rets.items():
                        if asset_symbol and asset_symbol in k:
                            buf = v
                            break
                if buf is not None and len(buf) >= self.cv_min_obs:
                    es_bar = es_historical(np.asarray(buf), self.cv_alpha)
                    f_max = cvar_cap_frac(es_bar, self.cv_horizon,
                                          self.cv_budget)
                    m = float(frac_cap_mult(f_max, prop))
                    if m < 0.999:
                        mult *= m
                        reasons.append(tag(
                            Code.RP_CVAR_CAP,
                            f"ES{self.cv_alpha * 100:.1f} hold "
                            f"{es_bar * math.sqrt(max(self.cv_horizon, 1.0)) * 100:.2f}% "
                            f"caps frac at {f_max:.3f} -> x{m:.2f}"))
                else:
                    reasons.append(tag(Code.RP_WARMUP,
                                       f"cvar warmup "
                                       f"{0 if buf is None else len(buf)}/"
                                       f"{self.cv_min_obs} obs — neutral"))

            if self.gap_enabled:
                f_max = gap_cap_frac(self.gap_shock_pct,
                                     self.gap_max_loss_pct)
                m = float(frac_cap_mult(f_max, prop))
                if m < 0.999:
                    mult *= m
                    reasons.append(tag(
                        Code.RP_GAP_CAP,
                        f"{self.gap_shock_pct:.0f}% gap x frac <= "
                        f"{self.gap_max_loss_pct:.1f}% equity caps frac at "
                        f"{f_max:.3f} -> x{m:.2f}"))
        except Exception as e:                       # SOFT caps only: an error
            # here degrades the soft caps to neutral but must NOT skip the HARD
            # vetoes below — the old single try returned 1.0 and bypassed the
            # 0.0 budget/heat vetoes, sizing up a book that should be halted.
            reasons.append(tag(Code.RP_WARMUP,
                               f"protocol soft-cap error ({e!r}) — neutral"))

        # HARD vetoes: budget/heat return 0.0 = NO new risk. An error computing
        # them fails CLOSED (block new risk), never open.
        try:
            if self.bd_enabled:
                sd, sw = self.spent_fracs(equity)
                s = max(sd, sw)
                m = float(budget_taper_mult(s, self.bd_taper_start,
                                            self.bd_floor))
                if m <= EPS:
                    reasons.append(tag(
                        Code.RP_BUDGET_EXHAUSTED,
                        f"loss budget spent (day {sd * 100:.0f}%, week "
                        f"{sw * 100:.0f}%) — no new risk today; exits "
                        f"unaffected"))
                    return 0.0, reasons
                if m < 0.999:
                    mult *= m
                    reasons.append(tag(Code.RP_BUDGET_TAPER,
                                       f"budget spent day {sd * 100:.0f}% / "
                                       f"week {sw * 100:.0f}% -> x{m:.2f}"))

            if self.ht_enabled:
                head = float(heat_headroom_frac(open_heat_frac, self.ht_max,
                                                self.ht_corr))
                m = float(frac_cap_mult(head, prop))
                if m <= EPS:
                    reasons.append(tag(
                        Code.RP_HEAT_FULL,
                        f"portfolio heat {open_heat_frac:.2f} at cap "
                        f"{self.ht_max:.2f} — no new risk"))
                    return 0.0, reasons
                if m < 0.999:
                    mult *= m
                    reasons.append(tag(Code.RP_HEAT_CAP,
                                       f"heat {open_heat_frac:.2f}/"
                                       f"{self.ht_max:.2f} headroom {head:.3f}"
                                       f" -> x{m:.2f}"))

        except Exception as e:                       # HARD vetoes fail CLOSED
            reasons.append(tag(Code.RP_BUDGET_EXHAUSTED,
                               f"protocol hard-veto error ({e!r}) — failing "
                               f"closed (no new risk)"))
            return 0.0, reasons

        return max(mult, self.stack_floor), reasons

    # ---------------- persistence ----------------
    def to_dict(self) -> dict:
        return {"day_key": self._day_key, "day_anchor": self._day_anchor,
                "week_key": self._week_key, "week_anchor": self._week_anchor}

    def from_dict(self, d: dict) -> None:
        try:
            self._day_key = d.get("day_key")
            da = d.get("day_anchor")
            self._day_anchor = float(da) if da is not None else None
            self._week_key = d.get("week_key")
            wa = d.get("week_anchor")
            self._week_anchor = float(wa) if wa is not None else None
        except Exception:  # corrupt anchors degrade to warmup, never crash resume  # nosec B110
            pass
