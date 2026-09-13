"""A cost-stack knob the code SILENTLY CLAMPS must be refused, not rewritten.

THE DEFECT THIS PINS. `execution/pretrade.py:107-111` builds three of the EV
gate's inputs with `min(max(float(cfg.get(...)), lo), hi)`. A configured value
outside that window is neither rejected nor reported - it is replaced. Set
`adverse_selection_kappa: 99` and the gate runs at 2.0; set `-5` and it runs at
0.0 with the adverse-selection charge DELETED. The operator's stated intent and
the deployed behaviour then differ permanently, and every EV number downstream
is computed against a figure that appears in no file.

`impact_eta` is the mirror image: `core/config_guard.py` fatalled only on
negative, so it had no ceiling at all.

WHY THE CLAMP ITSELF IS NOT THE BUG. A clamp is the right defence in the hot
path - the gate must not divide by zero mid-cycle. It is the wrong place to
DECIDE, because nothing there can tell the operator. The guard decides; the
clamp defends.

Zeros are WARN, not FATAL: `impact_eta: 0` and `adverse_selection_kappa: 0` are
inside every clamp and are legitimate "switch this term off" choices, but they
delete a charge from the stack that gates entries, so they must be visible. A
guard that fatals on a legitimate decision gets deleted as noise.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from core.config_guard import validate

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def shipped() -> dict:
    with open(REPO_ROOT / "config.json", encoding="utf-8") as fh:
        return json.load(fh)


def _fatals(cfg: dict, needle: str) -> list:
    return [m for s, m in validate(cfg) if s == "FATAL" and needle in m]


def _warns(cfg: dict, needle: str) -> list:
    return [m for s, m in validate(cfg) if s == "WARN" and needle in m]


def _with(shipped: dict, key: str, val) -> dict:
    c = copy.deepcopy(shipped)
    c["pretrade"][key] = val
    return c


# --------------------------------------------------------------------------
# the guard must not fire on what actually ships
# --------------------------------------------------------------------------

def test_the_shipped_config_has_no_fatal_findings(shipped):
    """Guards the guard. A check that fires on the real config would be logged
    critical on every boot and deleted as noise within a week."""
    fatal = [m for s, m in validate(shipped) if s == "FATAL"]
    assert not fatal, "shipped config has FATAL findings: " + "; ".join(fatal)


@pytest.mark.parametrize("key,lo,hi", [
    ("adverse_selection_kappa", 0.0, 2.0),
    ("maker_fill_p0", 0.01, 1.0),
    ("p_fill_floor", 0.001, 1.0),
    ("impact_eta", 0.0, 5.0),
    ("miss_cost_bps", 0.0, 20.0),
])
def test_every_shipped_value_is_interior_to_its_window(shipped, key, lo, hi):
    """Non-vacuous coverage: the key must EXIST and sit inside its bounds. If a
    key were absent the range test below would pass while guarding nothing."""
    assert key in shipped["pretrade"], f"{key} missing from config.json"
    val = float(shipped["pretrade"][key])
    assert lo <= val <= hi, f"{key}={val} outside [{lo}, {hi}]"


# --------------------------------------------------------------------------
# out of range -> FATAL, in both directions
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key,val,why", [
    ("adverse_selection_kappa", 99.0, "clamped down to 2.0, silently"),
    ("adverse_selection_kappa", -5.0, "clamped up to 0.0, term deleted"),
    ("maker_fill_p0", 0.0, "below the 0.01 clamp floor"),
    ("maker_fill_p0", 3.0, "a probability above 1.0"),
    ("p_fill_floor", 2.0, "above the 1.0 clamp ceiling"),
    ("p_fill_floor", -0.5, "a negative probability floor"),
    ("impact_eta", 8.0, "the decimal slip: 8.0 typed for 0.8"),
    ("impact_eta", -1.0, "negative would PAY for taking liquidity"),
    ("miss_cost_bps", 999.0, "red-team OBJ-16: silently became 20.0"),
    ("miss_cost_bps", -1.0, "a negative opportunity cost"),
])
def test_a_value_outside_its_window_is_FATAL(shipped, key, val, why):
    hits = _fatals(_with(shipped, key, val), key)
    assert hits, f"{key}={val} not caught ({why})"


def test_the_decimal_slip_is_actually_inside_the_fence(shipped):
    """The bound exists to catch 8.0-typed-for-0.8. Drafted at 10.0, which would
    have let that exact case through - the docstring would have claimed a fence
    the number did not build. This pins the corrected bound, so a later widening
    to 10.0 re-breaks it loudly."""
    assert _fatals(_with(shipped, "impact_eta", 8.0), "impact_eta")
    assert not _fatals(_with(shipped, "impact_eta", 1.5), "impact_eta"), (
        "1.5 is a defensible published coefficient and must still pass")


def test_a_non_numeric_value_is_FATAL_not_a_crash(shipped):
    """A typo'd string must be reported by the validator, not raise out of it
    and take the whole boot check down."""
    assert _fatals(_with(shipped, "impact_eta", "zero point eight"), "impact_eta")


def test_an_absent_key_is_not_invented(shipped):
    """Absence is pinned elsewhere; this check must stay silent on it rather
    than fatal on a default it made up."""
    c = copy.deepcopy(shipped)
    del c["pretrade"]["adverse_selection_kappa"]
    assert not _fatals(c, "adverse_selection_kappa")


# --------------------------------------------------------------------------
# zero: reported, never refused
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", ["impact_eta", "adverse_selection_kappa"])
def test_a_disabling_zero_warns_but_does_not_fatal(shipped, key):
    cfg = _with(shipped, key, 0.0)
    assert not _fatals(cfg, key), f"{key}=0 is legitimate and must not fatal"
    assert _warns(cfg, key), f"{key}=0 deletes a cost term and must be visible"


def test_the_warning_says_what_is_lost(shipped):
    """A warning that does not name the consequence gets scrolled past."""
    msg = _warns(_with(shipped, "impact_eta", 0.0), "impact_eta")[0]
    assert "DISABLES" in msg
    assert "cost term" in msg


# --------------------------------------------------------------------------
# THE META-PIN — red-team OBJ-16
#
# The first cut of this guard covered THREE of the four knobs that
# execution/pretrade.py silently clamps. Adding the fourth by hand fixes today
# and not tomorrow: a fifth clamp added to pretrade.py would be missed exactly
# the same way. This reads the clamps out of the SOURCE and requires the guard
# to cover every one, so the omission cannot recur silently.
# --------------------------------------------------------------------------

def test_every_clamped_pretrade_knob_is_guarded():
    import re

    src = (REPO_ROOT / "execution" / "pretrade.py").read_text(encoding="utf-8")
    # self.X = min(max(float(cfg.get("KEY", ...)), LO), HI)
    pat = re.compile(
        r"min\(\s*max\(\s*float\(\s*cfg\.get\(\s*[\"']([A-Za-z0-9_]+)[\"']",
        re.S)
    clamped = set(pat.findall(src))
    assert clamped, "no clamped knobs found - the scan broke, it did not pass"

    guard = (REPO_ROOT / "core" / "config_guard.py").read_text(encoding="utf-8")
    missing = [k for k in sorted(clamped)
               if f'"pretrade.{k}"' not in guard]
    assert not missing, (
        "execution/pretrade.py silently clamps these, and core/config_guard.py "
        "does not refuse an out-of-range value for them - so a typo is "
        "rewritten instead of reported: " + ", ".join(missing))


# ==========================================================================
# C1 - min_edge_cost_ratio had a FLOOR and NO CEILING (2026-09-13)
#
# Injected before fixing, which is how it was confirmed rather than guessed:
# ratio=13.0 and ratio=1000.0 BOTH validated with ZERO findings, while
# ratio=0.5 correctly FATALed. One decimal slip boots a 10x entry bar, the
# book silently stops entering, and the record reads "the market gave us
# nothing". Same shape as the 2026-09-11 `clamped` extension one key over
# (miss_cost_bps=999 -> zero findings) - and this key is NOT in that list,
# because execution/pretrade.py:89 reads it with no clamp, unlike its four
# neighbours at :110-116.
#
# THE BOUND IS DERIVED, NOT CHOSEN. PT-041 demands E[edge] >= ratio*cost; at
# the sigma floor the bet's MAXIMUM payoff is pt_cost_mult*cost
# (ml/labeling.barrier_geometry). Requiring the EXPECTED edge to reach the
# MAXIMUM payoff is an empty acceptance region. Both sides scale with cost, so
# the bound is cost-invariant and does not move at a fee re-book.
# ==========================================================================

_RATIO = "min_edge_cost_ratio"


class TestMinEdgeCostRatioCeiling:
    def test_the_shipped_config_is_clean(self, shipped):
        """NEGATIVE ARM: the live value must not trip the new bound."""
        assert _fatals(shipped, _RATIO) == []

    def test_a_decimal_slip_is_caught(self, shipped):
        hits = _fatals(_with(shipped, _RATIO, 13.0), _RATIO)
        assert hits, "1.3 -> 13.0 validated clean; the ceiling is missing"
        assert "empty acceptance region" in hits[0]

    def test_an_absurd_ratio_is_caught(self, shipped):
        assert _fatals(_with(shipped, _RATIO, 1000.0), _RATIO)

    def test_the_bound_counts_the_autonomous_bump(self, shipped):
        """execution/pretrade.py:321 adds the monitor's edge_ratio_bump, whose
        ceiling is ml.monitor.edge_ratio_bump_max. The runner log carries
        ratios in force of 1.30..1.70, so the bump HAS reached its full cap -
        the EFFECTIVE ratio is the one that must be bounded. Both arms."""
        mult = float(shipped["ml"]["label_pt_cost_mult"])
        bump = float(shipped["ml"]["monitor"]["edge_ratio_bump_max"])
        under, over = mult - bump - 0.05, mult - bump + 0.05
        # needle on THIS bound only: at  the pre-existing conviction
        # coherence check (config_guard.py:190) also fires and its message
        # names min_edge_cost_ratio too. That check is real but names the
        # WRONG remedy ("raise ev_cost_mult"), which is exactly how the audit
        # showed a decimal slip survives with one companion edit - so this pin
        # must not lean on it.
        def _ceiling_hits(v):
            return [m for m in _fatals(_with(shipped, _RATIO, v), _RATIO)
                    if "empty acceptance region" in m]
        assert _ceiling_hits(under) == [], (
            f"ratio={under} + bump={bump} < {mult} must clear THIS bound")
        assert _ceiling_hits(over), (
            f"ratio={over} + bump={bump} >= {mult} must FATAL on THIS bound")

    def test_the_bound_is_cost_invariant(self, shipped):
        """A fee re-book moves cost but not the bound - both sides scale with
        it. Halving the booked cost must not flip the verdict."""
        slipped = _with(shipped, _RATIO, 13.0)
        before = bool(_fatals(slipped, _RATIO))
        assert before is True
        slipped = copy.deepcopy(slipped)
        slipped["ml"]["label_round_trip_cost_pct"] = float(
            slipped["ml"]["label_round_trip_cost_pct"]) / 2.0
        slipped["pretrade"]["maker_fee_bps"] = 7.5
        slipped["pretrade"]["taker_fee_bps"] = 15.0
        assert bool(_fatals(slipped, _RATIO)) is before

    def test_the_original_floor_still_fires(self, shipped):
        """The fix must complete the one-sided guard, not replace it."""
        hits = _fatals(_with(shipped, _RATIO, 0.5), _RATIO)
        assert hits and "must be >= 1" in hits[0]


# ==========================================================================
# C2 - NON-FINITE VALUES FAILED OPEN THROUGH EVERY RANGE BOUND (2026-09-13)
#
# `val < lo or val > hi` is False for NaN, so all five bounds in the clamped
# list were permeable: injected, every key took a NaN with ZERO findings.
# Reachable rather than theoretical - json.loads accepts a bare NaN AND
# json.dumps EMITS one, so the era-cut stagers (which write config with
# json.dumps) can round-trip a NaN-bearing config silently.
#
# The consequence was a fail-OPEN in the DECISION PATH, measured on a live
# PreTradeGate from the shipped config: baseline approved=False cost=54.300;
# with pretrade.impact_eta=NaN, approved=TRUE cost=nan - because a NaN cost
# makes `edge < ratio*cost` False so PT-041 never fires. Same shape as RP-052
# (cut #10 B3, "NaN flowed max(nan,0)->nan through").
# ==========================================================================

_NONFINITE = [float("nan"), float("inf"), float("-inf")]


class TestNonFiniteFailsClosed:
    @pytest.mark.parametrize("key", [
        "impact_eta", "adverse_selection_kappa", "maker_fill_p0",
        "p_fill_floor", "miss_cost_bps"])
    @pytest.mark.parametrize("bad", _NONFINITE)
    def test_every_clamped_knob_refuses_a_non_finite(self, shipped, key, bad):
        hits = _fatals(_with(shipped, key, bad), key)
        assert hits, f"{key}={bad} validated clean - the bound is permeable"
        assert "not finite" in hits[0]

    def test_the_shipped_config_is_unaffected(self, shipped):
        """NEGATIVE ARM: the new check must not fire on what ships."""
        assert [m for s, m in validate(shipped) if s == "FATAL"] == []

    def test_a_finite_value_inside_the_window_still_passes(self, shipped):
        """NEGATIVE ARM: the isfinite test must not shadow the range test."""
        assert _fatals(_with(shipped, "impact_eta", 0.8), "impact_eta") == []

    def test_a_finite_value_outside_the_window_still_FATALs_on_RANGE(
            self, shipped):
        """The two checks are distinct: an out-of-range FINITE value must
        still report the RANGE failure, not be swallowed by the finite test."""
        hits = _fatals(_with(shipped, "impact_eta", 8.0), "impact_eta")
        assert hits
        assert "not finite" not in hits[0], \
            "a finite out-of-range value was reported as non-finite"

    def test_a_non_numeric_value_still_reports_NOT_A_NUMBER(self, shipped):
        """Ordering pin: the float() failure must precede the isfinite test,
        so a string still says 'is not a number' rather than 'not finite'."""
        hits = _fatals(_with(shipped, "impact_eta", "0.8x"), "impact_eta")
        assert hits and "not a number" in hits[0]

    def test_the_message_names_the_consequence_not_just_the_rule(
            self, shipped):
        """A guard message that says only 'invalid' teaches nobody why."""
        hits = _fatals(_with(shipped, "impact_eta", float("nan")),
                       "impact_eta")
        # TWO findings now fire for one bad key and both are correct: the
        # general pretrade sweep (added with C2b) reports first, the
        # clamped-list check second. Assert the consequence appears in ONE of
        # them rather than pinning an ordering nothing guarantees.
        assert any("PT-041" in m and "APPROVED" in m for m in hits), hits


# ==========================================================================
# C2b - the GENERAL non-finite sweep over the pretrade block (2026-09-13)
#
# The bounded `clamped` list covers five knobs. It did NOT cover the four
# THRESHOLDS the hard vetoes compare against, and a non-finite threshold makes
# its veto fail OPEN: measured, max_data_staleness_ms=NaN APPROVES a
# 1,000,000 ms stale book in the exploring lane. Enumerating four more keys
# would leave the same shape one key over - which is how both this defect and
# the 2026-09-11 miss_cost_bps one arrived - so the sweep closes the CLASS.
# ==========================================================================


class TestGeneralNonFiniteSweep:
    @pytest.mark.parametrize("key", [
        "max_data_staleness_ms", "min_order_usd",
        "max_participation_of_depth", "max_spread_bps"])
    def test_a_veto_threshold_refuses_a_non_finite(self, shipped, key):
        hits = [m for m in _fatals(_with(shipped, key, float("nan")), key)
                if "not finite" in m]
        assert hits, f"pretrade.{key}=NaN validated clean"

    def test_a_NESTED_numeric_is_swept_too(self, shipped):
        """The proof the sweep beats enumeration: tier_max_spread_bps is a MAP,
        and its members are thresholds PT-021 compares against."""
        c = copy.deepcopy(shipped)
        c["pretrade"]["tier_max_spread_bps"]["core"] = float("nan")
        hits = [m for s, m in validate(c)
                if s == "FATAL" and "tier_max_spread_bps.core" in m]
        assert hits, "a nested non-finite threshold was not swept"

    def test_infinities_are_swept_as_well_as_nan(self, shipped):
        for bad in (float("inf"), float("-inf")):
            assert [m for m in _fatals(
                _with(shipped, "min_order_usd", bad), "min_order_usd")
                if "not finite" in m], f"{bad} passed"

    def test_the_shipped_config_stays_clean(self, shipped):
        """NEGATIVE ARM - the sweep walks every numeric leaf under pretrade,
        so a false positive here would FATAL the live boot."""
        assert [m for s, m in validate(shipped) if s == "FATAL"] == []

    def test_a_bool_is_not_reported_as_non_finite(self, shipped):
        """bool is a subclass of int; treating True as a number would produce
        a nonsense finding on every flag in the block."""
        c = copy.deepcopy(shipped)
        c["pretrade"]["price_exit_leg"] = True
        assert [m for s, m in validate(c)
                if s == "FATAL" and "price_exit_leg" in m] == []

    def test_underscore_doc_keys_are_skipped(self, shipped):
        """The block is full of _doc strings; the sweep must not trip on them
        or start reporting prose."""
        c = copy.deepcopy(shipped)
        c["pretrade"]["_note_doc"] = "not a number"
        assert [m for s, m in validate(c)
                if s == "FATAL" and "_note_doc" in m] == []


# ==========================================================================
# THE VALIDATOR MUST NOT CRASH ON A HOSTILE CONFIG VALUE (2026-09-13)
#
# Found by an adversarial review of the non-finite sweep added the same day.
# float() raises OverflowError on an int too large to convert, and a 400-digit
# JSON integer literal parses to exactly that (only `1e400` yields inf). The
# coercion guards caught (TypeError, ValueError) only, so validate() RAISED
# instead of returning findings - and every OTHER finding was lost with it. A
# crash is worse than a wrong answer here: it is a config error that produces
# no diagnosis at all.
#
# This regresses the property commit 1d7e9e5f shipped by name ("stop a typo
# crashing the validator"), which is why it is pinned rather than just fixed.
# ==========================================================================

_HOSTILE = [
    pytest.param(10 ** 400, id="huge-positive-int"),
    pytest.param(-(10 ** 400), id="huge-negative-int"),
    pytest.param(float("inf"), id="inf"),
    pytest.param(float("-inf"), id="-inf"),
    pytest.param(float("nan"), id="nan"),
    pytest.param("0.8x", id="non-numeric-string"),
    pytest.param(None, id="none"),
    pytest.param([1, 2], id="list"),
]


@pytest.mark.parametrize("bad", _HOSTILE)
def test_validate_never_raises_on_a_hostile_value(shipped, bad):
    """It may FATAL, it may WARN, it may stay silent - it may not RAISE."""
    c = copy.deepcopy(shipped)
    c["pretrade"]["impact_eta"] = bad
    try:
        validate(c)
    except Exception as exc:            # noqa: BLE001 - that IS the assertion
        raise AssertionError(
            f"validate() raised {type(exc).__name__} on impact_eta={bad!r}; "
            f"a crash loses every other finding in the same run") from exc


def test_a_huge_int_is_reported_not_silently_dropped(shipped):
    """Non-vacuity: not raising is not enough, it must still be REPORTED."""
    c = copy.deepcopy(shipped)
    c["pretrade"]["impact_eta"] = 10 ** 400
    assert [m for s, m in validate(c)
            if s == "FATAL" and "impact_eta" in m], \
        "a 400-digit int validated clean"


def test_the_disabling_zero_WARN_still_fires(shipped):
    """NEGATIVE ARM: widening the except tuple must not swallow the legitimate
    zero-disables-a-cost-term warning that shares the same try block."""
    c = copy.deepcopy(shipped)
    c["pretrade"]["impact_eta"] = 0.0
    assert [m for s, m in validate(c)
            if s == "WARN" and "impact_eta" in m and "DISABLES" in m]
