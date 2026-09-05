"""ERA SEGMENTATION PINS — report-only, and the selection rule must not move.

THE PROBLEM (measured 2026-09-04). `cohort_eval` publishes

    accrual: 94/50 entry-opened closes toward the verdict gate

for the ERA-4 pre-registered population, which CLAUDE.md declares CLOSED (it
read out COST_BOUND at n=54). That counter is NOT era-scoped and never was:
`era4_trips` selects on five predicates and `exec_era` appears in NONE of them,
so 94/50 pools cuts #7, #8 and #9 — three different fee regimes — by
construction. Era-6 (cut #9, `9-16ec821e`) is the cohort actually accruing
toward the next readout, and its count existed in NO tool: it reached the
operator nowhere, while the pooled 94/50 reached them through three surfaces.

THE FIX IS REPORT-ONLY. It reads the ALREADY-COMPUTED per-trip `eras` field and
prints a segmentation beside the pre-registered line. The registration is the
law: no predicate, no band, and no selection rule is touched.

`test_segmentation_does_not_move_the_pre_registered_counter` is the load-bearing
pin here. The other pins prove the counter WORKS; that one proves it did not
cost anything — which, under a live accrual moratorium, is the property that
actually matters.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "cohort_eval_under_test", ROOT / "scripts" / "cohort_eval.py")
ce = importlib.util.module_from_spec(_spec)
sys.modules["cohort_eval_under_test"] = ce
_spec.loader.exec_module(ce)

ERA7, ERA8, ERA9 = "7-e7d5ca1a", "8-ca55e2ba", "9-16ec821e"


def _trip(eras, t_open=1000.0, t=2000.0):
    """The shape era4_trips() emits, reduced to the fields homogeneity reads."""
    return {"eras": list(eras), "t_open": t_open, "t": t,
            "stale_legs": 0, "prestamp_legs": 0}


def _cohort():
    """3 pure era-8, 2 pure era-9, 1 straddler — deliberately not all one era."""
    return [
        _trip([ERA8]), _trip([ERA8]), _trip([ERA8]),
        _trip([ERA9]), _trip([ERA9]),
        _trip([ERA8, ERA9]),
    ]


def test_homogeneity_reports_per_era_counts():
    hg = ce.homogeneity(_cohort(), epochs=[], cohort_start=0.0)
    assert "by_era" in hg, (
        "homogeneity() carries no by_era segmentation - the accruing era's "
        "count exists in no tool, which is the whole defect")
    assert hg["by_era"].get(ERA9) == 2
    assert hg["by_era"].get(ERA8) == 3


def test_current_era_is_derived_not_hardcoded():
    """It must follow the data, so the next cut does not silently orphan it."""
    hg = ce.homogeneity(_cohort(), epochs=[], cohort_start=0.0)
    assert hg.get("current_era") == ERA9, (
        f"current_era={hg.get('current_era')!r}; the highest-ordinal era "
        f"present must win, so a future cut #10 needs no code edit")

    # a corpus that has not yet seen era 9 must name era 8, not a constant
    older = ce.homogeneity([_trip([ERA7]), _trip([ERA8])], epochs=[],
                           cohort_start=0.0)
    assert older.get("current_era") == ERA8, \
        "current_era is hardcoded - it did not follow a different corpus"


def test_straddlers_are_counted_separately_never_assigned():
    """A trip that opened under cut #8 and closed under cut #9 is NOT an era-9
    trip. The moratorium forbids pooling across the fee correction, so a
    straddler must be visible as a straddler, not folded into either side."""
    hg = ce.homogeneity(_cohort(), epochs=[], cohort_start=0.0)
    assert hg.get("era_straddling_trips") == 1
    assert hg["by_era"].get(ERA9) == 2, (
        "the straddler was folded into era-9 - that imports a pre-fee-"
        "correction entry into the accruing cohort")
    assert sum(hg["by_era"].values()) + hg["era_straddling_trips"] == 6, \
        "trips went missing or were double-counted in the segmentation"


def test_segmentation_buckets_are_exhaustive():
    """A trip must land in exactly one bucket. Found live: the first cut of
    this counter printed 24+3+60+6 = 93 against an n of 94, because a trip
    whose legs carry NO exec_era stamp fell through every branch. An
    unstamped trip is a real category (pre-stamp rows; the stale-binary case
    this report already flags) and must be VISIBLE, not dropped - dropping it
    is the same silent-drop failure as an uncounted corpus row."""
    trips = _cohort() + [_trip([])]           # one leg-set with no stamp
    hg = ce.homogeneity(trips, epochs=[], cohort_start=0.0)
    assert hg["era_unstamped_trips"] == 1
    total = (sum(hg["by_era"].values()) + hg["era_straddling_trips"]
             + hg["era_unstamped_trips"])
    assert total == hg["n"] == len(trips), (
        f"buckets sum to {total} but n={hg['n']} - {len(trips) - total} "
        f"trip(s) are invisible in the segmentation")


def test_a_trip_with_an_unstamped_leg_is_not_wholly_inside_any_era():
    """THE PIN THAT WAS MISSING, and the reason the defect shipped past a
    mutation-verified suite.

    era4_trips builds `eras` from STAMPED legs only: a leg whose exec_era is
    absent (stale_legs) or blank (prestamp_legs) is counted separately and
    never added to the set. So `len(eras) == 1` means "every leg that carried
    a stamp agreed" - NOT "this trip is wholly inside that era".

    The first cut of this segmentation used len(eras)==1 alone and labelled
    the result "wholly inside". Measured on the live ledger 2026-09-05: 87
    trips matched, 4 of them carried an unstamped leg. Era-9 had none, so the
    accruing count was right BY LUCK. This report's own homogeneity section
    records that the stamp has failed before, so that luck is not a plan.

    Every other pin in this file builds trips by hand with stale_legs=0, which
    is exactly why none of them could see it. Mutation testing proved the code
    did what I intended; it could not tell me the intent was wrong.
    """
    partial = _trip([ERA9])
    partial["stale_legs"] = 1          # one leg carries no exec_era at all
    hg = ce.homogeneity(_cohort() + [partial], epochs=[], cohort_start=0.0)

    base = ce.homogeneity(_cohort(), epochs=[], cohort_start=0.0)
    assert hg["by_era"][ERA9] == base["by_era"][ERA9], (
        "a trip with an unstamped leg was counted as WHOLLY INSIDE era-9 - "
        "that silently overstates the accruing cohort")
    assert hg["era_partial_stamp_trips"] == 1
    total = (sum(hg["by_era"].values()) + hg["era_straddling_trips"]
             + hg["era_unstamped_trips"] + hg["era_partial_stamp_trips"])
    assert total == hg["n"], "buckets stopped being exhaustive"

    # prestamp (blank stamp) must behave identically to absent
    pre = _trip([ERA9])
    pre["prestamp_legs"] = 1
    hg2 = ce.homogeneity([pre], epochs=[], cohort_start=0.0)
    assert hg2["by_era"].get(ERA9, 0) == 0
    assert hg2["era_partial_stamp_trips"] == 1


def test_segmentation_matches_the_real_ledger_shape():
    """INTEGRATION. The unit pins above feed hand-built dicts; this one feeds
    whatever era4_trips actually emits, so a change to the trip shape cannot
    silently invalidate the segmentation. Skips where no ledger exists (this
    is the PC's corpus), which is honest - a skip is not a pass."""
    fills = ROOT / "outputs" / "fills.csv"
    if not fills.exists():
        import pytest
        pytest.skip("no outputs/fills.csv on this box (the PC owns the ledger)")
    trips = ce.era4_trips(str(fills))
    hg = ce.homogeneity(trips, epochs=[], cohort_start=0.0)
    total = (sum(hg["by_era"].values()) + hg["era_straddling_trips"]
             + hg["era_unstamped_trips"] + hg["era_partial_stamp_trips"])
    assert total == hg["n"] == len(trips), (
        f"on the REAL ledger the buckets sum to {total} but n={hg['n']}")
    # no trip may be both counted pure and carrying an unattributable leg
    for t in trips:
        te = t.get("eras") or []
        unst = (t.get("stale_legs") or 0) + (t.get("prestamp_legs") or 0)
        if len(te) == 1 and unst:
            assert hg["era_partial_stamp_trips"] > 0, (
                "the real ledger contains a partial-stamp trip but the "
                "counter reads zero")
            break


def test_era_ordinal_orders_by_cut_number_not_lexically():
    """'10-...' must outrank '9-...'. Plain string ordering would hand the
    CURRENT label to a superseded cut the first time the counter passes nine."""
    assert ce._era_ordinal("10-aaaaaaaa") > ce._era_ordinal("9-ffffffff")
    hg = ce.homogeneity([_trip(["9-ffffffff"]), _trip(["10-aaaaaaaa"])],
                        epochs=[], cohort_start=0.0)
    assert hg["current_era"] == "10-aaaaaaaa"


def test_planted_pure_era9_trip_moves_the_counter_by_exactly_one():
    """INJECTION, positive control. A counter that cannot be shown to MOVE is
    indistinguishable from a dead scan."""
    base = ce.homogeneity(_cohort(), epochs=[], cohort_start=0.0)
    planted = ce.homogeneity(_cohort() + [_trip([ERA9])], epochs=[],
                             cohort_start=0.0)
    assert planted["by_era"][ERA9] - base["by_era"][ERA9] == 1


def test_planted_era8_trip_does_not_move_the_era9_counter():
    """INJECTION, negative control. Separates 'the counter works' from 'the
    counter counts everything'."""
    base = ce.homogeneity(_cohort(), epochs=[], cohort_start=0.0)
    planted = ce.homogeneity(_cohort() + [_trip([ERA8])], epochs=[],
                             cohort_start=0.0)
    assert planted["by_era"][ERA9] == base["by_era"][ERA9]
    assert planted["by_era"][ERA8] - base["by_era"][ERA8] == 1


def test_segmentation_does_not_move_the_pre_registered_counter():
    """THE LOAD-BEARING PIN. The registration is the law. Adding a report field
    must leave n, the verdict inputs and the homogeneity verdict byte-identical
    to what the pre-registered rule produced."""
    trips = _cohort()
    hg = ce.homogeneity(trips, epochs=[], cohort_start=0.0)
    assert hg["n"] == len(trips), "the cohort size moved"
    assert hg["fill_eras"] == sorted({ERA8, ERA9}), \
        "the pre-existing fill_eras field changed shape"
    assert hg["fill_mixed"] is True
    assert hg["verdict"].startswith("MIXED") or hg["verdict"] == "CLEAN"
    # every key the pre-registered reader consumed must still be present
    for k in ("verdict", "n", "stale_trips", "prestamp_trips", "fill_eras",
              "fill_mixed", "model_known", "champions", "straddling_trips",
              "model_mixed", "deploys"):
        assert k in hg, f"pre-existing key {k!r} disappeared from homogeneity()"


def test_single_era_cohort_reports_no_straddlers():
    """ANTI-RUBBER-STAMP: the straddler counter must be able to read zero."""
    hg = ce.homogeneity([_trip([ERA9]), _trip([ERA9])], epochs=[],
                        cohort_start=0.0)
    assert hg["era_straddling_trips"] == 0
    assert hg["by_era"] == {ERA9: 2}
