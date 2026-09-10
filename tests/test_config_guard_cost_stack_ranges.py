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
