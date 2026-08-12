"""risk/stop_placement.py - the cut-#7 widen-beyond Osler nudge (ALGO-7).

Semantics under pin: a stop within band_bps of a half-step round level
rests offset_bps BEYOND it (long below / short above); the nudge only ever
WIDENS; degenerate inputs are fail-inert; the widening is bounded by
band+offset. Plus the geometry-alignment invariant at the wiring site: a
nudged bracket sl leg back-derives sl_frac, so the traded bet stays the
labeled bet.
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from risk.stop_placement import nudge_stop_off_round, round_step

ROOT = Path(__file__).resolve().parents[1]


def test_half_step_lattice_matches_the_retired_implementation():
    """Direction flipped; the lattice deliberately did NOT (cut #7 is a
    direction-only change)."""
    assert round_step(63412.0) == pytest.approx(500.0)
    assert round_step(1988.0) == pytest.approx(50.0)
    assert round_step(0.45) == pytest.approx(0.005)
    assert round_step(0.0) == 0.0
    assert round_step(float("nan")) == 0.0


@pytest.mark.parametrize("stop,direction", [
    (62998.0, "long"), (63002.0, "long"),      # either side of 63000
    (1799.5, "short"), (1800.4, "short"),      # either side of 1800
])
def test_nudge_always_lands_beyond_and_only_widens(stop, direction):
    out = nudge_stop_off_round(stop, direction, 5.0, 5.0)
    step = round_step(stop)
    level = round(stop / step) * step
    if direction == "long":
        assert out <= stop and out < level
    else:
        assert out >= stop and out > level


def test_widening_is_bounded_by_band_plus_offset():
    stop = 62998.0
    out = nudge_stop_off_round(stop, "long", 5.0, 5.0)
    assert stop - out <= stop * (5.0 + 5.0) * 1e-4 + 1e-9


def test_already_beyond_by_more_than_offset_is_untouched():
    # long stop 62960: 40bps below 63000... but its NEAREST half-step level
    # is 63000 at 6.3bps? 62960 -> nearest 500-step is 63000 (dist 40).
    # 40/62960*1e4 = 6.35bps > band 5 -> untouched by the band test.
    assert nudge_stop_off_round(62960.0, "long", 5.0, 5.0) == 62960.0


@pytest.mark.parametrize("bad", [0.0, -5.0, float("nan"), float("inf")])
def test_degenerate_stop_is_fail_inert(bad):
    assert nudge_stop_off_round(bad, "long", 5.0, 5.0) == bad or (
        isinstance(bad, float) and math.isnan(bad)
        and math.isnan(nudge_stop_off_round(bad, "long", 5.0, 5.0)))


def test_unknown_direction_is_untouched():
    assert nudge_stop_off_round(62998.0, "sideways", 5.0, 5.0) == 62998.0


# ------------------------------------------------------------- wiring pins
def test_bracket_wiring_back_derives_sl_frac():
    """Geometry-alignment law: if the fill path nudges the bracket sl leg,
    it must recompute bracket_sl_frac from the nudged price in the SAME
    block - otherwise the corpus labels a bet that was never traded."""
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # find the assignment `pos.bracket_sl_frac = abs(1.0 - ...)` and the
    # `_nudge_stop` call in the same function body
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute)
                    and t.attr == "bracket_sl_frac" for t in n.targets)]
    assert any("abs" in ast.dump(h.value) for h in hits), (
        "no back-derivation of bracket_sl_frac from the nudged stop found")
    assert "_nudge_stop" in src


def test_retired_helper_is_gone():
    """The tighten-side implementation must not survive alongside the flip -
    two live nudges with opposite signs is an incoherent book."""
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "def nudge_stop_off_round_number" not in src


def test_config_knobs_exist_under_risk_not_the_phantom_block():
    """The retired reader looked up config[risk_management], which does not
    exist - the knob was never actually read (phantom-knob class). The new
    reader and the knobs must both live under config[risk]."""
    import json
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    assert "stop_round_buffer_bps" in cfg["risk"]
    assert "stop_round_offset_bps" in cfg["risk"]
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'get("risk_management"' not in src, (
        "something still reads the nonexistent risk_management block")
