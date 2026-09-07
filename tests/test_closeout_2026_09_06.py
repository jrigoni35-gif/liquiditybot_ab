"""Closeout pins, 2026-09-06 (SAFE): two boot-time instruments made honest.

  1. regime.momentum_bear_max stated as the value the runtime already used.
     -0.34 sat inside the 1/(2n) tolerance band of the TSMOM lattice point
     -1/3, so MacroRegimeEngine repaired it to -0.1111 at EVERY boot and
     logged an ERROR each time. The config now says -0.1111 - the value the
     runtime has actually been using. Behaviour is unchanged versus the
     RUNNING system (NOT versus the unrepaired literal, which excluded -1/3
     by 0.0067 of rounding and never ran); the ERROR is gone.

  2. config_guard's give-back WARN compares the EFFECTIVE arm, not the raw
     knob. risk/profit_tiers has floored the arm at cost/(1-frac) since
     2026-07-30; the guard kept warning on the static 0.6% every boot while
     the arm that actually fires is 0.917% at 20/35. GB-1 was refuted at
     HEAD on exactly this; the instrument now reads what the runtime does.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cfg():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _sev(cfg, level):
    from core.config_guard import validate
    return [m for s, m in validate(cfg) if s == level]


# ------------------------------------------------------------- 1. TSMOM cut
def test_shipped_momentum_bear_max_is_lattice_safe():
    """The runtime must accept the shipped value UNCHANGED - no boot repair,
    no ERROR line. tsmom_threshold_conflict returns None when the cut sits
    outside the 1/(2n) band of every achievable TSMOM level."""
    from regime.macro_regime import tsmom_threshold_conflict
    cfg = _cfg()
    n = len(cfg["regime"]["momentum_lookbacks_days"])
    thr = float(cfg["regime"]["momentum_bear_max"])
    assert tsmom_threshold_conflict(thr, n) is None, (
        f"momentum_bear_max={thr} conflicts with the TSMOM lattice at n={n}: "
        f"the runtime will repair it at boot and log an ERROR every start")


def test_the_shipped_cut_selects_what_the_runtime_has_been_selecting():
    """ANTI-RUBBER-STAMP for 'behaviour-preserving', stated CORRECTLY.

    The first draft asserted the new cut partitions the lattice the same way
    the literal -0.34 did. It does NOT, and that is the whole defect: -1/3 <=
    -0.34 is False (-0.3333 > -0.34), so the literal EXCLUDED the 2-of-3-down
    level by 0.0067 of float rounding - while MacroRegimeEngine's boot repair
    (near + step/3 = -0.1111) INCLUDED it, on the documented reading that a
    cut written beside a lattice point was written to include it. The runtime
    has therefore been selecting {-1, -1/3} as bear since the repair shipped.
    The config now states that. Behaviour is unchanged versus the RUNNING
    system; it was never equal to the unrepaired literal."""
    from regime.macro_regime import tsmom_threshold_conflict
    cfg = _cfg()
    n = len(cfg["regime"]["momentum_lookbacks_days"])
    thr = float(cfg["regime"]["momentum_bear_max"])
    lattice = [(-n + 2 * k) / n for k in range(n + 1)]       # -1 .. +1
    # what the runtime repaired -0.34 to, by the same arithmetic it uses
    near = tsmom_threshold_conflict(-0.34, n)
    step = 2.0 / n
    runtime_fixed = min(near + step / 3.0, -1.0 / (4 * n))
    assert [lv <= thr for lv in lattice] == [lv <= runtime_fixed for lv in lattice], (
        "the shipped cut no longer partitions the lattice the way the runtime's "
        "repair did - that IS a behaviour change")
    assert (-1.0 / n) <= thr, "the 2-of-3-down level must be INCLUDED (documented intent)"
    assert not ((1.0 / n) <= thr), "the 2-of-3-up level must be EXCLUDED"


def test_shipped_regime_block_raises_no_fatal():
    assert not [m for m in _sev(_cfg(), "FATAL") if "momentum" in m]


# ------------------------------------------------------ 2. give-back WARN
def test_shipped_config_does_not_warn_on_a_floored_arm():
    """At 20/35 and giveback_frac 0.4 the EFFECTIVE arm is 0.55/0.6 = 0.917%
    against a 0.76% buffer. The old check read the raw 0.6% and warned on
    every boot; the guard must now be silent here."""
    warns = [m for m in _sev(_cfg(), "WARN") if "give_back" in m and "arms inside" in m]
    assert not warns, f"stale WARN still fires on the raw knob: {warns}"


def test_an_arm_that_is_STILL_inside_the_buffer_after_the_floor_DOES_warn():
    """ANTI-RUBBER-STAMP: the check must not have been deleted. With
    giveback_frac 0.95 the floor is 0.55/0.05 = ... capped by max(1-frac,
    0.05) -> 11%, which clears; so use a tiny cost world instead: fees 1/1
    bps -> floor 0.02/0.6 = 0.033%, raw 0.05% -> effective 0.05% <= buffer
    (2*35+6 = 76bps). The WARN must fire on the EFFECTIVE arm."""
    cfg = _cfg()
    cfg["pretrade"]["maker_fee_bps"] = 1.0
    cfg["pretrade"]["taker_fee_bps"] = 1.0
    cfg["order_manager"]["maker_fee_bps"] = 1.0
    cfg["order_manager"]["taker_fee_bps"] = 1.0
    cfg["profit_taking"]["give_back"]["arm_gain_pct"] = 0.05
    warns = [m for m in _sev(cfg, "WARN") if "give_back" in m and "arms inside" in m]
    assert warns, "an effective arm inside the buffer no longer warns"
    assert "EFFECTIVE arm" in warns[0], "the WARN does not name the effective arm"


def test_the_floor_formula_matches_the_runtime():
    """The guard mirrors risk/profit_tiers._give_back_candidate's floor. If
    the two drift, the guard is back to reading a fiction."""
    import inspect

    from risk import profit_tiers
    src = inspect.getsource(profit_tiers.ProfitTierEngine._give_back_candidate)
    assert "cost_pct / max(1.0 - self.gb_frac, 0.05)" in src, (
        "the runtime floor formula changed - update the config_guard mirror")
    gsrc = (ROOT / "core/config_guard.py").read_text(encoding="utf-8")
    assert "rt_fee_pct / max(1.0 - gbf, 0.05)" in gsrc
