"""v10 logistic-armed grid entry ladder (execution/grid_ladder.py).

The contract worth pinning: the ladder is an EXECUTION SHAPE on an entry the
risk stack already approved — never a new source of risk. Sizes must sum to
exactly the sizer-approved total (split, never multiplied); deeper rungs must
sit strictly further from fair value than the EV-gated rung-0 price (edge
monotone down the ladder); the ARM/DISARM hysteresis must not flap at the
bar; retraction (spoofy / manip / flip / garbage inputs) must disarm; a
disabled engine must be byte-identical to the legacy single-entry path; and
the caller-supplied rung budget (position slots / same-side cap) must bound
the rung count.
"""
import math

from core.codes import Code
from execution.grid_ladder import GridLadderEngine

CFG = {"enabled": True, "rungs": 3, "spacing_vol_mult": 0.35,
       "min_spacing_bps": 8.0, "size_decay": 0.7,
       "p_win_arm": 0.60, "p_win_disarm": 0.55}


def _eng(**over):
    return GridLadderEngine({**CFG, **over})


def _plan(eng, p_win=0.65, direction="long", quote=100.0, sigma=0.30,
          units=3.0, **kw):
    return eng.plan("SUI", direction, quote, sigma, units, p_win, **kw)


# ---- geometry ---------------------------------------------------------------

def test_sizes_sum_exactly_to_the_approved_total():
    plan = _plan(_eng())
    assert plan.armed and len(plan.rungs) == 3
    assert math.isclose(sum(r.size_units for r in plan.rungs), 3.0,
                        rel_tol=1e-12)                 # split, never multiplied
    # decay-weighted: each deeper rung is smaller
    sizes = [r.size_units for r in plan.rungs]
    assert sizes == sorted(sizes, reverse=True)


def test_long_ladders_below_short_ladders_above():
    lo = _plan(_eng(), direction="long")
    hi = _plan(_eng(), direction="short")
    assert lo.rungs[0].price == 100.0                  # rung 0 AT the quote
    assert all(lo.rungs[k].price < lo.rungs[k - 1].price
               for k in range(1, 3))                   # long: steps DOWN
    assert hi.rungs[0].price == 100.0
    assert all(hi.rungs[k].price > hi.rungs[k - 1].price
               for k in range(1, 3))                   # short: steps UP


def test_spacing_scales_with_vol_and_floors():
    # sigma_bar 0.30% -> 30bps * 0.35 = 10.5bps spacing (above the 8bps floor)
    plan = _plan(_eng(), sigma=0.30)
    assert math.isclose(plan.rungs[1].offset_bps, 10.5, rel_tol=1e-9)
    # dead-calm tape floors at min_spacing_bps, never stacks rungs
    calm = _plan(_eng(), sigma=0.001)
    assert math.isclose(calm.rungs[1].offset_bps, 8.0, rel_tol=1e-9)
    assert calm.rungs[1].price < calm.rungs[0].price


def test_rung_budget_caps_the_ladder():
    plan = _plan(_eng(), max_rungs=2)
    assert plan.armed and len(plan.rungs) == 2
    assert math.isclose(sum(r.size_units for r in plan.rungs), 3.0,
                        rel_tol=1e-12)                 # total preserved
    single = _plan(_eng(), max_rungs=1)
    assert len(single.rungs) == 1                      # degenerates to single


# ---- hysteresis -------------------------------------------------------------

def test_arm_disarm_hysteresis_does_not_flap():
    eng = _eng()
    assert not _plan(eng, p_win=0.59).armed            # below arm: single path
    assert _plan(eng, p_win=0.61).armed                # arms over the bar
    assert _plan(eng, p_win=0.57).armed                # HOLDS inside the band
    assert not _plan(eng, p_win=0.54).armed            # drops below disarm
    assert not _plan(eng, p_win=0.57).armed            # re-arm needs the BAR
    assert _plan(eng, p_win=0.61).armed


def test_direction_flip_retracts_and_requires_rearm():
    eng = _eng()
    assert _plan(eng, p_win=0.65, direction="long").armed
    # a flip with p_win in the HOLD band must NOT stay armed on the new side
    flipped = _plan(eng, p_win=0.57, direction="short")
    assert not flipped.armed
    assert Code.GL_BELOW_ARM.value in flipped.reason


# ---- retraction -------------------------------------------------------------

def test_spoofy_and_manip_retract():
    eng = _eng()
    assert _plan(eng, p_win=0.65).armed
    assert not _plan(eng, p_win=0.65, liq_label="spoofy").armed
    assert _plan(eng, p_win=0.65).armed                # re-arms (p >= bar)
    assert not _plan(eng, p_win=0.65, manip_vetoed=True).armed


def test_garbage_inputs_fail_closed():
    eng = _eng()
    assert not _plan(eng, quote=float("nan")).armed
    assert not _plan(eng, units=0.0).armed
    assert not _plan(eng, p_win=float("inf"), direction="sideways").armed


def test_disabled_engine_is_the_legacy_path():
    eng = _eng(enabled=False)
    plan = _plan(eng, p_win=0.99)
    assert not plan.armed and plan.rungs == []
    assert eng._armed == {}                            # no state accrual


def test_note_exit_requires_fresh_arm():
    eng = _eng()
    assert _plan(eng, p_win=0.61).armed
    eng.note_exit("SUI")
    assert not _plan(eng, p_win=0.57).armed            # hold band no longer holds


# ---- determinism ------------------------------------------------------------

def test_plan_is_deterministic():
    a = _plan(_eng(), p_win=0.65)
    b = _plan(_eng(), p_win=0.65)
    assert [(r.price, r.size_units, r.offset_bps) for r in a.rungs] == \
           [(r.price, r.size_units, r.offset_bps) for r in b.rungs]


# ---- config_guard coherence -------------------------------------------------

def _fatals(gl):
    from core.config_guard import validate
    cfg = {"system": {"dry_run": True}, "grid_ladder": {"enabled": True, **gl}}
    return [m for s, m in validate(cfg) if s == "FATAL" and "grid_ladder" in m]


def test_guard_accepts_shipped_defaults():
    assert _fatals(dict(CFG, enabled=True)) == []


def test_guard_rejects_inverted_hysteresis():
    assert any("hysteresis" in m
               for m in _fatals({"p_win_arm": 0.55, "p_win_disarm": 0.60}))
    assert any("hysteresis" in m
               for m in _fatals({"p_win_arm": 0.55, "p_win_disarm": 0.55}))


def test_guard_rejects_bad_decay_rungs_spacing():
    assert any("size_decay" in m for m in _fatals({"size_decay": 1.5}))
    assert any("rungs" in m for m in _fatals({"rungs": 9}))
    assert any("spacing" in m for m in _fatals({"min_spacing_bps": 0.0}))


def test_guard_silent_when_disabled():
    from core.config_guard import validate
    cfg = {"system": {"dry_run": True},
           "grid_ladder": {"enabled": False, "rungs": 99, "size_decay": 7}}
    assert not any("grid_ladder" in m for s, m in validate(cfg)
                   if s == "FATAL")
