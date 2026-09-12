"""
ml/labeling.py

Triple-barrier labeling (Lopez de Prado, "Advances in Financial Machine
Learning"). Given a candidate entry, the outcome is decided by whichever
of three barriers is touched first:

  upper barrier  - profit target, pt_mult * bar vol (side-adjusted)
  lower barrier  - stop, sl_mult * bar vol
vertical       - max holding period in bars

The meta-label is 1 when the primary signal's trade would have netted
more than round-trip costs, 0 otherwise. The meta-model therefore learns
"when is the 5-gate signal actually worth taking, and how big" - the
meta-labeling architecture: primary model picks the side, ML picks the
size. It is the highest-signal, lowest-overfit way to bolt learning
onto an existing rule engine.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from risk.profit_tiers import (conviction_runner_params, conviction_trail_mult,
                              tier1_cost_floor_mult, tier1_cost_floor_pct,
                              time_stop_fires, time_stop_params)

EPS = 1e-12


def barrier_geometry(sigma_bar: float, cost_pct: float, pt_mult: float,
                     sl_mult: float, pt_cost_mult: float) -> tuple:
    """(pt_frac, sl_frac) for the triple-barrier bet, cost-floored.

    WHY the floor (spec D2, 2026-07-27): sigma-scaled barriers at typical
    5 m vol put the profit target on the same order as the round-trip cost,
    and at that point the round trip can equal or exceed the profit distance
    — the AVERAGE bracket bet is then EV-negative regardless of signal.

    NO COST FIGURE IS WRITTEN HERE ON PURPOSE (2026-09-10). This docstring
    carried "~1.2% ... at cut #8, venue-true 40/80 fees" long after cuts #9,
    #10 and #12 had re-booked the fee row; against the shipped config it was
    2.7x the live value, in the single most-cited coupling in this repo — the
    first thing a newcomer reads to learn it. The cost is a LIVE quantity that
    moves with the venue tier every re-book, so re-derive it, never quote a
    figure from prose:
        python -c "import json;print(json.load(open('config.json'))['ml']['label_round_trip_cost_pct'])"
    It tracks the booked fee row (pretrade maker+taker over 100) and moves
    with it at every cut — read both, never one.
    Flooring the SIGMA
    INPUT (never the distances) keeps pt:sl at its configured ratio by
    construction: sigma_eff = max(sigma_bar,
    pt_cost_mult * cost_frac / pt_mult), so at the floor the profit
    distance is exactly pt_cost_mult round-trip costs. pt_cost_mult=0
    disables the floor (legacy behavior). Pure function — BOTH the
    candidate labeler and the live bracket-exit engine call this, which
    is what makes the label's bet and the traded bet the same bet."""
    sigma_eff = sigma_bar
    if pt_cost_mult > 0.0 and pt_mult > 0.0:
        sigma_eff = max(sigma_bar, pt_cost_mult * (cost_pct / 100.0)
                        / pt_mult)
    return pt_mult * sigma_eff, sl_mult * sigma_eff


@dataclass
class BarrierOutcome:
    label: int          # 1 = win (net of costs), 0 = loss/scratch
    # signed trade return, %. UNIT TRAP (2026-07-29 audit, documented not
    # yet unified): triple_barrier writes this NET of cost_pct; the
    # exit_policy sim writes it GROSS (cost applies only inside its label
    # test). The two differ by exactly cost_pct — never aggregate/compare
    # ret_pct across labelers without normalizing. label is net on BOTH.
    ret_pct: float
    bars_held: int
    barrier: str        # pt | sl | time | tier | trail | floor | time_stop
    # True when the trade fully RESOLVED before running out of bars (a decisive
    # exit, not the vertical/time cutoff). The candidate labeler uses this for
    # EARLY decidability: a resolved outcome inside the available window is
    # final and can be labeled now; only a "time" outcome must wait for the
    # full horizon. Generalizes the old `barrier in ("pt","sl")` check across
    # both the triple-barrier and the exit-policy labelers.
    final: bool = True
    # (pt_frac, sl_frac): the barrier_geometry() distances this outcome was
    # labeled under (geometry-alignment T3, 2026-07-27), FRACTIONS of entry
    # (0.02 = 2%). Populated ONLY by CandidateLabeler._label's triple_barrier
    # branch - the sole call site whose output reaches the persisted corpus
    # (see that method's docstring) - via `dataclasses.replace`. Every other
    # constructor call (triple_barrier's own internal returns, the
    # exit_policy replay) leaves these at the 0.0 default: exit_policy has no
    # single fixed bracket to report, so 0.0 there means "not a fixed-
    # geometry bet", the SAME "unknown/legacy" meaning HistoryStore gives an
    # unpopulated pt_frac/sl_frac column on a pre-bump row. Row METADATA
    # only - never consumed as a feature.
    pt_frac: float = 0.0
    sl_frac: float = 0.0


@dataclass
class ExitPolicy:
    """The live exit geometry, read from config so the label and the engine
    share ONE source of truth. Distances are FRACTIONS of entry (0.02 = 2%).

    Built by `ExitPolicy.from_config(config)` from the SAME `risk` +
    `profit_taking` sections `main.py`/`risk.profit_tiers` consume, so a
    change to the live stop or tiers automatically re-shapes the labels."""
    base_stop_frac: float = 0.02          # risk.stop_loss_pct
    stop_vol_mult: float = 4.0            # risk.stop_vol_mult (× sigma_bar)
    # tiers: list of (legacy_trigger_frac, vol_mult, close_frac)
    tiers: list = field(default_factory=lambda: [
        (0.010, 8.0, 0.25), (0.020, 16.0, 0.25),
        (0.035, 28.0, 0.25), (0.050, 40.0, 0.25)])
    vol_scaled: bool = True
    be_after_tier: int = 1               # break-even floor armed after tier N
    be_buffer_frac: float = 0.0006       # be_buffer_bps
    # BE fee term (2026-07-29 unit audit): the live BE floor is
    # (2*est_fee_bps + be_buffer_bps)/1e4 (profit_tiers.py:655) — the sim
    # omitted the fee term entirely (~80bps of exit level at the shipped
    # 40bps fee). Default 0.0 matches the live engine's CODE default.
    est_fee_bps: float = 0.0
    trail_after_tier: int = 2            # trailing floor armed after tier N
    trail_frac: float = 0.010            # trailing_stop.trail_pct
    # chandelier mirror (2026-07-29 unit audit): live trail distance is
    # max(trail_pct, chandelier_k * sigma * sqrt(chandelier_bars)) — the
    # sim used the static trail_pct only (2.2x tighter at sigma 0.3%).
    # Defaults match the live engine's parse (profit_tiers.py:219-220).
    chandelier_k: float = 3.0
    chandelier_bars: int = 6
    # live-engine CODE defaults (2026-07-29 audit: these had drifted —
    # gb_enabled True vs live False, tighten 4.0 vs live 0.0=off)
    gb_enabled: bool = False
    gb_arm_frac: float = 0.015           # give_back.arm_gain_pct (fallback)
    gb_arm_vol_mult: float = 0.0         # give_back.arm_vol_mult (0 = static)
    gb_frac: float = 0.40                # give_back.giveback_frac (lock 1-frac)
    gb_tighten_frac: float = 0.0         # give_back.tighten_gain_pct (0 = off)
    gb_tight_frac: float = 0.25          # give_back.tight_frac (lock 1-frac)
    # CONVICTION RUNNER (rev 6): the live engine tightens the chandelier trail
    # multiplicatively for a low-entry-conviction position. Populated from
    # profit_taking.conviction_runner (SAME parse+clamp the engine uses, via
    # conviction_runner_params); the tighten is applied only when a per-signal
    # conviction is threaded into simulate_exit_policy. Defaults = OFF so a bare
    # ExitPolicy() and every conviction-less caller stay byte-identical.
    cr_enabled: bool = False
    cr_neutral_conf: float = 0.70
    cr_min_conf: float = 0.55
    cr_min_trail_mult: float = 0.60
    # TIER-1 COST FLOOR (P1) + TIME-STOP (P2, PT-060) parity insert (P3.5):
    # min_trigger_cost_mult is the SAME parse+clamp the live engine uses (via
    # tier1_cost_floor_mult); it floors tier 1's effective trigger (tier_index
    # 0 only, in ExitPolicy._tier_trigger) whenever a caller supplies a real
    # est_cost_bps to simulate_exit_policy. ts_* mirror profit_taking.time_stop
    # (via time_stop_params) and gate simulate_exit_policy's own PT-060 check.
    # Defaults (3.0 / disabled) match the live engine's code defaults, so a
    # bare ExitPolicy() and every legacy caller stay byte-identical.
    min_trigger_cost_mult: float = 3.0
    ts_enabled: bool = False
    ts_max_bars_no_progress: int = 36
    ts_min_mfe_frac: float = 0.5

    @staticmethod
    def from_config(config: dict) -> "ExitPolicy":
        risk = (config or {}).get("risk", {}) or {}
        pt = (config or {}).get("profit_taking", {}) or {}
        gb = pt.get("give_back", {}) or {}
        tr = pt.get("trailing_stop", {}) or {}
        cr = conviction_runner_params(pt)    # SAME parse+clamp as the live engine
        ts_enabled, ts_max_bars, ts_min_mfe = time_stop_params(pt)  # ditto (P2)
        tiers = []
        for i in range(1, 5):
            t = pt.get(f"tier_{i}")
            if not t:
                continue
            leg = float(t.get("trigger_pct_gain", 0.0)) / 100.0
            vm = float(t.get("trigger_vol_mult", 0.0))
            cf = float(t.get("close_pct_of_position", 25)) / 100.0
            if leg > 0 and cf > 0:
                tiers.append((leg, vm, cf))
        return ExitPolicy(
            base_stop_frac=float(risk.get("stop_loss_pct", 2.0)) / 100.0,
            stop_vol_mult=float(risk.get("stop_vol_mult", 4.0)),
            tiers=tiers or ExitPolicy().tiers,
            # SAME key and SAME default as the live engine reads
            # (risk/profit_tiers.py:215: cfg.get("vol_scaled", True) — the
            # live default moved to True and this mirror had gone stale at
            # False, so a config omitting the key labeled on FIXED triggers
            # while the live engine fired vol-scaled ones; 2026-07-29 audit)
            vol_scaled=bool(pt.get("vol_scaled", True)),
            be_after_tier=int(pt.get("be_after_tier", 1)),
            be_buffer_frac=float(pt.get("be_buffer_bps", 6)) / 1e4,
            est_fee_bps=max(float(pt.get("est_fee_bps", 0.0)), 0.0),
            trail_after_tier=int(tr.get("activate_after_tier", 2)),
            trail_frac=max(float(tr.get("trail_pct", 1.0)), 0.01) / 100.0,
            chandelier_k=max(float(pt.get("chandelier_k", 3.0)), 0.5),
            chandelier_bars=max(int(pt.get("chandelier_bars", 6)), 1),
            gb_enabled=bool(gb.get("enabled", False)),
            gb_arm_frac=float(gb.get("arm_gain_pct", 1.5)) / 100.0,
            gb_arm_vol_mult=float(gb.get("arm_vol_mult", 0.0)),
            gb_frac=float(gb.get("giveback_frac", 0.4)),
            gb_tighten_frac=float(gb.get("tighten_gain_pct", 0.0)) / 100.0,
            gb_tight_frac=float(gb.get("tight_frac", 0.25)),
            cr_enabled=cr[0], cr_neutral_conf=cr[1],
            cr_min_conf=cr[2], cr_min_trail_mult=cr[3],
            min_trigger_cost_mult=tier1_cost_floor_mult(pt),
            ts_enabled=ts_enabled, ts_max_bars_no_progress=ts_max_bars,
            ts_min_mfe_frac=ts_min_mfe)

    def _tier_trigger(self, legacy: float, vol_mult: float,
                      sigma_bar: float, tier_index: int = 0,
                      est_cost_bps: float = 0.0) -> float:
        """Vol-scaled tier trigger fraction, clamped to [0.5×,3×] legacy,
        THEN (tier_index == 0 only) floored at the SAME tier-1 cost-multiple
        floor the live engine applies (P1, `ProfitTierEngine._tier_trigger_pct`)
        via the shared `tier1_cost_floor_pct` helper — a TRUE mirror for every
        input this function is actually given (P3.5), never a copied formula.

        `est_cost_bps` is the candidate's entry round-trip cost estimate. The
        live engine's own estimate — execution/pretrade.py's
        `PreTradeDecision.est_cost_bps` — is genuinely UNAVAILABLE at the only
        `CandidateLabeler.register()` call site (main.py): the pretrade
        decision is computed by `PreTradeGate.evaluate()` well AFTER that
        signal has already been registered as a candidate (sizing + quoting,
        which the cost stack depends on, have not happened yet). CLOSED
        (Task 1, #103): both real callers (`CandidateLabeler._label` and
        `bootstrap_dataset`) now thread their OWN register-time cost estimate
        instead — `CandidateLabeler._cost_pct(cand)` (fee floor + the
        candidate's own capped spread) converted pct -> bps, the SAME basis
        already used for the net-of-cost label. DOCUMENTED APPROXIMATION (not
        a residual): the live `PreTradeDecision.est_cost_bps` additionally
        carries impact/queue terms computed post-sizing, structurally
        unavailable at register time — the label estimate is therefore a
        conservative LOWER BOUND on the live floor, never an over-floor, and
        it is the same cost basis the label's own net-of-cost subtraction
        already uses (one cost stack, two consumers)."""
        if not self.vol_scaled or sigma_bar <= 0 or vol_mult <= 0:
            trigger = legacy
        else:
            trigger = min(max(vol_mult * sigma_bar, 0.5 * legacy), 3.0 * legacy)
        if tier_index == 0:
            # tier1_cost_floor_pct returns a PCT number (mult × bps/100, e.g.
            # 0.6 = 0.6%); this policy's triggers are FRACTIONS (0.01 = 1%,
            # same convention `from_config` already applies to every other
            # pct-based config value) — the extra /100.0 is that conversion,
            # not a second formula.
            floor_frac = tier1_cost_floor_pct(self.min_trigger_cost_mult,
                                              est_cost_bps) / 100.0
            if floor_frac > trigger:
                trigger = floor_frac
        return trigger


def simulate_exit_policy(closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, i: int, side: int,
                         sigma_bar: float, policy: ExitPolicy,
                         max_bars: int = 96,
                         cost_pct: float = 0.5,
                         conviction: Optional[float] = None,
                         est_cost_bps: float = 0.0) -> BarrierOutcome:
    """Label a candidate by REPLAYING the live exit policy over the candles,
    instead of a single symmetric triple barrier. This makes the counterfactual
    label answer the SAME question a live trade poses (net PnL sign under the
    real stop + tiered scale-outs + give-back/trailing runner + cost floor +
    time-stop), so the predominantly-candidate training set stops being
    trained on a different bet than it is traded on.

    ``conviction`` (default None) is the candidate's entry meta p(win). When
    supplied AND the policy's conviction-runner is enabled, the trailing-floor
    distance is tightened by the SAME multiplier the live engine applies
    (``risk.profit_tiers.conviction_trail_mult``, one shared implementation),
    so a borderline-confidence signal (p_win in [min_conf, neutral_conf)) is no
    longer labeled on a wider leash than the live position gets (W2-1). None (or
    unknown/high conviction) is a full-leash no-op — every legacy caller and the
    bootstrap path (EMA-cross pseudo-signals carry no meta p(win)) are unchanged.

    ``est_cost_bps`` (default 0.0) is the candidate's entry round-trip cost
    estimate; when supplied it floors tier 1's effective trigger at
    ``min_trigger_cost_mult × est_cost_bps`` (P1), the SAME shared
    ``risk.profit_tiers.tier1_cost_floor_pct`` the live engine applies to tier
    1 only (see ``ExitPolicy._tier_trigger``). The live engine's own estimate
    — execution/pretrade.py's ``PreTradeDecision.est_cost_bps`` — is
    genuinely UNAVAILABLE at the candidate-registration call site (main.py's
    ``CandidateLabeler.register()`` runs before ``PreTradeGate.evaluate()``
    computes the cost stack) and at the bootstrap path (no pretrade decision
    exists at all for an EMA-cross pseudo-signal). CLOSED (Task 1, #103):
    both real callers now thread their OWN register-time cost estimate
    instead — ``CandidateLabeler._cost_pct(cand)`` (fee floor + the
    candidate's own capped spread) and bootstrap's ``cost_pct`` argument,
    each converted pct -> bps (``* 100.0``) — the SAME basis already used for
    the net-of-cost label (one cost stack, two consumers: the P&L
    subtraction and the trigger floor). DOCUMENTED APPROXIMATION (not a
    residual): this register-time estimate omits the impact/queue terms the
    live decision adds post-sizing (structurally unavailable this early), so
    it is a conservative LOWER BOUND on the true live floor, never an
    over-floor.

    The time-stop (P2, PT-060, ``policy.ts_enabled``) is also mirrored: a
    candidate that has not reached ``ts_min_mfe_frac`` of tier 1's EFFECTIVE
    (cost-floored) trigger within ``ts_max_bars_no_progress`` bars is scratched
    full-close, via the SAME shared ``risk.profit_tiers.time_stop_fires``
    predicate the live engine's ``_time_stop_hit`` uses. VIRGIN-ONLY GATE: a
    candidate is virgin (no tier fired) by construction the entire time this
    replay's ``tier_idx == 0`` — the identical condition the live engine's
    ``position.tier_closed == 0`` gate enforces — so once ANY tier fires in
    this replay the time-stop can never fire again for it, exactly mirroring
    the P2 review fix.

    Faithful to the dominant economics; deliberately omits three live inputs
    that cannot exist for a counterfactual signal (documented, all 2nd order):
      * time-based trail tightening (needs wall-clock bars_in_trade),
      * the signal-decay leash (needs a live signal snapshot),
      * inventory-pressure tier boost (needs live book state).
    The conviction-runner leash was a FOURTH such divergence; it is now mirrored
    wherever a conviction is threaded (candidate path) and a documented residual
    (full leash) only where the entry conviction is genuinely unavailable
    (bootstrap). The tier-1 cost floor is a FIFTH: mirrored via a shared helper,
    now fed a real register-time cost estimate at BOTH real call sites
    (candidate registration and bootstrap — Task 1, #103) — see above for why
    that estimate is a documented approximation (conservative lower bound),
    not a residual. The time-stop (P2) needed no such residual: every input
    it needs (bar index, running MFE, the cost-floored tier-1 trigger)
    already exists in this replay, so it is a TRUE mirror, not an
    approximation — with one live-only exception (a SIXTH divergence class,
    benign by direction): the live engine defers a due PT-060 by one cycle
    while a resting maker tier-1 take is open (#103 T5, main.py), a
    microstructure guard this bar replay structurally cannot model (no order
    book); it only ever converts a would-be scratch label into an honest
    profit-take. Intra-bar
    path is unknown, so — like the triple barrier — the ADVERSE extreme is
    checked before the favorable one each bar (conservative; Lopez de Prado).
    Returns net-of-cost label + realized signed return %."""
    entry = closes[i]
    if entry <= EPS:
        return BarrierOutcome(0, 0.0, 0, "time")
    stop_frac = max(policy.base_stop_frac, policy.stop_vol_mult * sigma_bar)
    triggers = [(policy._tier_trigger(leg, vm, sigma_bar, tier_index=idx,
                                      est_cost_bps=est_cost_bps), cf)
                for idx, (leg, vm, cf) in enumerate(policy.tiers)]
    # entry-conviction runner leash: a multiplicative tighten on the trailing
    # floor ONLY (mirrors the live engine, where it multiplies decay_mult into
    # _trail_distance_frac and touches neither break-even nor give-back). 1.0
    # (no-op) when conviction is None/unknown/high or the runner is disabled.
    conv_mult = (conviction_trail_mult(
        float(conviction), policy.cr_enabled, policy.cr_neutral_conf,
        policy.cr_min_conf, policy.cr_min_trail_mult)
        if conviction is not None else 1.0)
    end = min(i + max_bars, len(closes) - 1)

    remaining = 1.0                       # fraction of the position still open
    realized = 0.0                        # signed return × fraction, summed
    tier_idx = 0
    peak_gain = 0.0                       # best favorable gain fraction so far
    # stop_frac from entry -> the initial hard protective stop as a gain level
    # (a negative gain). Floors ratchet it upward (toward/into profit).
    stop_level = -stop_frac               # exit gain-level for the runner

    def _favorable_gain(px):
        return (px / entry - 1.0) if side > 0 else (1.0 - px / entry)

    for j in range(i + 1, end + 1):
        adverse = lows[j] if side > 0 else highs[j]
        favorable = highs[j] if side > 0 else lows[j]
        adverse_gain = _favorable_gain(adverse)     # signed; worst this bar
        # 1) ADVERSE first: did the bar breach the current stop/floor level?
        if adverse_gain <= stop_level:
            realized += stop_level * remaining      # exit remainder at the stop
            remaining = 0.0
            return BarrierOutcome(int(realized * 100.0 - cost_pct > 0),
                                  realized * 100.0, j - i,
                                  "sl" if tier_idx == 0 else "trail")
        # 2) FAVORABLE: ratchet peak, fire any reached tiers (one level at a
        # time, in order), then ratchet the floor.
        fav_gain = _favorable_gain(favorable)
        peak_gain = max(peak_gain, fav_gain)
        while tier_idx < len(triggers) and fav_gain >= triggers[tier_idx][0]:
            trig, close_frac = triggers[tier_idx]
            take = min(close_frac, remaining)
            realized += trig * take                 # scale-out at the trigger
            remaining -= take
            tier_idx += 1
            if remaining <= EPS:
                return BarrierOutcome(
                    int(realized * 100.0 - cost_pct > 0),
                    realized * 100.0, j - i, "tier")
        # 2.5) PT-060 time-stop (P2/P3.5 parity): checked AFTER the tier fire
        # (mirrors evaluate()'s ordering: next-tier first, time-stop second,
        # exit floor third) and BEFORE the floor ratchet below, so a
        # no-progress scratch never depends on this bar's own floor update.
        # VIRGIN-ONLY: tier_idx == 0 means no tier has fired in THIS replay
        # yet — candidates are virgin by construction for the entire window
        # this check can fire in (the identical gate the live engine's
        # position.tier_closed == 0 enforces; P2 review fix). j - i is bars
        # since entry, the same 5-minute-bar unit _bars_in_trade measures
        # live. triggers[0][0] is tier 1's effective (vol-scaled +
        # cost-floored) trigger, computed above by the SAME sub-task-A
        # helper the live engine uses — a true mirror, not a re-derivation.
        if time_stop_fires(policy.ts_enabled, tier_idx == 0, j - i,
                           policy.ts_max_bars_no_progress, peak_gain,
                           policy.ts_min_mfe_frac,
                           triggers[0][0] if triggers else float("inf")):
            realized += _favorable_gain(closes[j]) * remaining
            return BarrierOutcome(int(realized * 100.0 - cost_pct > 0),
                                  realized * 100.0, j - i, "time_stop")
        # 3) ratchet the exit floor to the tightest armed protection
        floor = stop_level
        if tier_idx >= policy.be_after_tier:
            # live BE floor = (2*fee + buffer) in gain-level terms
            # (profit_tiers.py:655) — the fee term was missing here until
            # the 2026-07-29 audit (~80bps of exit level at 40bps fees)
            floor = max(floor, 2.0 * policy.est_fee_bps / 1e4
                        + policy.be_buffer_frac)
        # vol-scaled arm mirrors the live engine (sigma_bar is a
        # fraction here, same units as peak_gain); static fallback
        _gb_arm = (policy.gb_arm_vol_mult * sigma_bar
                   if policy.gb_arm_vol_mult > 0 and sigma_bar > 0
                   else policy.gb_arm_frac)
        # 2026-07-30 ARM COST FLOOR mirror (live: profit_tiers.
        # _give_back_candidate — the SEVENTH shared-discipline mirror):
        # the arm never sits below cost / locked-share, so the sim's
        # give-back only fires where the live lock clears the entry's
        # own cost. Uses the SAME est_cost_bps the tier-1 floor mirror
        # above already threads (both 0-inert together: bootstrap and
        # trials worlds stay byte-identical).
        if est_cost_bps > 0.0:
            _gb_arm = max(_gb_arm, (est_cost_bps / 1e4)
                          / max(1.0 - policy.gb_frac, 0.05))
        if policy.gb_enabled and peak_gain >= _gb_arm:
            # live semantics (profit_tiers.py:587): tighten_gain_pct == 0
            # DISABLES the tighten rung; the old unconditional >= made 0
            # mean "always tight" — inverted (2026-07-29 audit)
            tight = (0.0 < policy.gb_tighten_frac <= peak_gain)
            lock = 1.0 - (policy.gb_tight_frac if tight else policy.gb_frac)
            floor = max(floor, lock * peak_gain)             # give-back lock
        if tier_idx >= policy.trail_after_tier:
            # live chandelier distance (profit_tiers.py:429-437):
            # max(static trail, k * sigma * sqrt(bars)), conviction-
            # tightened multiplicatively (conv_mult <= 1.0 shrinks the
            # leash). The static-only distance was 2.2x tighter than the
            # live leash at routine vol (2026-07-29 audit).
            dist = max(policy.trail_frac,
                       policy.chandelier_k * sigma_bar
                       * math.sqrt(policy.chandelier_bars))
            floor = max(floor, peak_gain - dist * conv_mult)
        stop_level = max(stop_level, floor)         # ratchet-only

    # vertical barrier: close the remainder at the final bar (NOT final — more
    # bars could still resolve the still-open remainder)
    if remaining > EPS:
        realized += _favorable_gain(closes[end]) * remaining
    return BarrierOutcome(int(realized * 100.0 - cost_pct > 0),
                          realized * 100.0, end - i, "time", final=False)


def triple_barrier(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                i: int, side: int, sigma_bar: float,
                pt_mult: float = 8.0, sl_mult: float = 6.0,
                max_bars: int = 96, cost_pct: float = 0.06) -> BarrierOutcome:
    """
    closes/highs/lows : full arrays
    i                 : entry bar index (enter at closes[i])
    side              : +1 long, -1 short
    sigma_bar         : per-bar vol (fraction), scales the barriers
    cost_pct          : round-trip cost in %, subtracted before labeling
    """
    entry = closes[i]
    if entry <= EPS:
        return BarrierOutcome(0, 0.0, 0, "time")
    pt = pt_mult * sigma_bar
    sl = sl_mult * sigma_bar
    end = min(i + max_bars, len(closes) - 1)

    for j in range(i + 1, end + 1):
        if side > 0:
            up = highs[j] / entry - 1.0
            dn = 1.0 - lows[j] / entry
            if dn >= sl:           # conservative: stop checked first
                ret = -sl * 100.0
                return BarrierOutcome(0, ret - cost_pct, j - i, "sl")
            if up >= pt:
                ret = pt * 100.0
                return BarrierOutcome(int(ret - cost_pct > 0), ret - cost_pct,
                                    j - i, "pt")
        else:
            up = highs[j] / entry - 1.0
            dn = 1.0 - lows[j] / entry
            if up >= sl:
                ret = -sl * 100.0
                return BarrierOutcome(0, ret - cost_pct, j - i, "sl")
            if dn >= pt:
                ret = pt * 100.0
                return BarrierOutcome(int(ret - cost_pct > 0), ret - cost_pct,
                                    j - i, "pt")
    ret = side * (closes[end] / entry - 1.0) * 100.0
    return BarrierOutcome(int(ret - cost_pct > 0), ret - cost_pct, end - i,
                          "time", final=False)
