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

from dataclasses import dataclass, field

import numpy as np

EPS = 1e-12


@dataclass
class BarrierOutcome:
    label: int          # 1 = win (net of costs), 0 = loss/scratch
    ret_pct: float      # signed trade return, %
    bars_held: int
    barrier: str        # pt | sl | time | tier | trail | floor
    # True when the trade fully RESOLVED before running out of bars (a decisive
    # exit, not the vertical/time cutoff). The candidate labeler uses this for
    # EARLY decidability: a resolved outcome inside the available window is
    # final and can be labeled now; only a "time" outcome must wait for the
    # full horizon. Generalizes the old `barrier in ("pt","sl")` check across
    # both the triple-barrier and the exit-policy labelers.
    final: bool = True


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
    trail_after_tier: int = 2            # trailing floor armed after tier N
    trail_frac: float = 0.010            # trailing_stop.trail_pct
    gb_enabled: bool = True
    gb_arm_frac: float = 0.015           # give_back.arm_gain_pct (fallback)
    gb_arm_vol_mult: float = 0.0         # give_back.arm_vol_mult (0 = static)
    gb_frac: float = 0.40                # give_back.giveback_frac (lock 1-frac)
    gb_tighten_frac: float = 0.040       # give_back.tighten_gain_pct
    gb_tight_frac: float = 0.25          # give_back.tight_frac (lock 1-frac)

    @staticmethod
    def from_config(config: dict) -> "ExitPolicy":
        risk = (config or {}).get("risk", {}) or {}
        pt = (config or {}).get("profit_taking", {}) or {}
        gb = pt.get("give_back", {}) or {}
        tr = pt.get("trailing_stop", {}) or {}
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
            # (risk/profit_tiers.py: cfg.get("vol_scaled", False)) — the old
            # "vol_scaled_triggers" key does not exist in any config, so the
            # labeler could never see the knob it exists to mirror and the
            # defaults disagreed (audit LP-2 2026-07-17)
            vol_scaled=bool(pt.get("vol_scaled", False)),
            be_after_tier=int(pt.get("be_after_tier", 1)),
            be_buffer_frac=float(pt.get("be_buffer_bps", 6)) / 1e4,
            trail_after_tier=int(tr.get("activate_after_tier", 2)),
            trail_frac=max(float(tr.get("trail_pct", 1.0)), 0.01) / 100.0,
            gb_enabled=bool(gb.get("enabled", True)),
            gb_arm_frac=float(gb.get("arm_gain_pct", 1.5)) / 100.0,
            gb_arm_vol_mult=float(gb.get("arm_vol_mult", 0.0)),
            gb_frac=float(gb.get("giveback_frac", 0.4)),
            gb_tighten_frac=float(gb.get("tighten_gain_pct", 4.0)) / 100.0,
            gb_tight_frac=float(gb.get("tight_frac", 0.25)))

    def _tier_trigger(self, legacy: float, vol_mult: float,
                      sigma_bar: float) -> float:
        """Vol-scaled tier trigger fraction, clamped to [0.5×,3×] legacy —
        mirrors ProfitTierEngine._tier_trigger_pct."""
        if not self.vol_scaled or sigma_bar <= 0 or vol_mult <= 0:
            return legacy
        return min(max(vol_mult * sigma_bar, 0.5 * legacy), 3.0 * legacy)


def simulate_exit_policy(closes: np.ndarray, highs: np.ndarray,
                         lows: np.ndarray, i: int, side: int,
                         sigma_bar: float, policy: ExitPolicy,
                         max_bars: int = 96,
                         cost_pct: float = 0.5) -> BarrierOutcome:
    """Label a candidate by REPLAYING the live exit policy over the candles,
    instead of a single symmetric triple barrier. This makes the counterfactual
    label answer the SAME question a live trade poses (net PnL sign under the
    real stop + tiered scale-outs + give-back/trailing runner), so the
    predominantly-candidate training set stops being trained on a different bet
    than it is traded on.

    Faithful to the dominant economics; deliberately omits three live inputs
    that cannot exist for a counterfactual signal (documented, all 2nd order):
      * time-based trail tightening (needs wall-clock bars_in_trade),
      * the signal-decay leash (needs a live signal snapshot),
      * inventory-pressure tier boost (needs live book state).
    Intra-bar path is unknown, so — like the triple barrier — the ADVERSE
    extreme is checked before the favorable one each bar (conservative;
    Lopez de Prado). Returns net-of-cost label + realized signed return %."""
    entry = closes[i]
    if entry <= EPS:
        return BarrierOutcome(0, 0.0, 0, "time")
    stop_frac = max(policy.base_stop_frac, policy.stop_vol_mult * sigma_bar)
    triggers = [(policy._tier_trigger(leg, vm, sigma_bar), cf)
                for (leg, vm, cf) in policy.tiers]
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
        # 3) ratchet the exit floor to the tightest armed protection
        floor = stop_level
        if tier_idx >= policy.be_after_tier:
            floor = max(floor, policy.be_buffer_frac)        # break-even+buf
        # vol-scaled arm mirrors the live engine (sigma_bar is a
        # fraction here, same units as peak_gain); static fallback
        _gb_arm = (policy.gb_arm_vol_mult * sigma_bar
                   if policy.gb_arm_vol_mult > 0 and sigma_bar > 0
                   else policy.gb_arm_frac)
        if policy.gb_enabled and peak_gain >= _gb_arm:
            lock = (1.0 - (policy.gb_tight_frac
                           if peak_gain >= policy.gb_tighten_frac
                           else policy.gb_frac))
            floor = max(floor, lock * peak_gain)             # give-back lock
        if tier_idx >= policy.trail_after_tier:
            floor = max(floor, peak_gain - policy.trail_frac)  # trailing
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
