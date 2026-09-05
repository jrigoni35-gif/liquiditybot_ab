"""drift_share divides by features that CANNOT contribute to its numerator.

MEASURED 2026-09-05 against the live artifact (outputs/meta_model.json, mtime
2026-08-26T01:04:15Z): of 60 voting features, **34 (56.7%) have tied decile
edges**, and psi() returns exactly 0.0 for those - deliberately, because a
degenerate feature otherwise reports enormous PSI against an identical
distribution and pinned drift_share permanently above the trigger.

The consequence is in the DENOMINATOR, not the return value. Those 34 can never
enter `drifting`, but they are still counted in `n_voting`. So:

    drift_share ceiling = 26/60 = 0.4333   against a 0.30 threshold

Tripping 0.30 requires 19 of the 26 MEASURABLE features - 73% - while the
config's own `_drift_doc` promises "retrain only when >=30% of the MARKET
features shift". The number reaching the operator means something different
from what its name and its documentation say. That is CLAUDE.md's reading
discipline (a) verbatim: a ratio is not a number until its denominator has been
read from the code that computes it.

WHAT THIS FIXES, AND WHAT IT DELIBERATELY DOES NOT. drift_share and its trigger
are UNCHANGED. Moving them changes when ML-032 RETRAIN REQUESTED fires and
therefore when the retrain loop runs - a model-side consequence that belongs to
an operator adjudication, not to a measurement fix. These pins cover ADDITIVE
provenance only: the split denominator is now visible so the threshold can be
argued on evidence.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("numpy")

from ml.monitor import DRIFT_EXCLUDED_FEATURES, ModelMonitor  # noqa: E402


def _mon(**cfg):
    m = ModelMonitor({"drift_min_rows": 1, **cfg})
    return m


# psi() returns 0.0 below 10 samples (ml/calibration.py). The first draft of
# these fixtures fed 5 rows, so `drifting` was always EMPTY and the trigger pin
# compared 0/4 against 0/2 - it passed under the very mutation it existed to
# catch. Feed above the floor or the pin is decorative.
_PSI_MIN_ROWS = 12


def _feed(mon, ncols, value=0.0, rows=_PSI_MIN_ROWS):
    for _ in range(rows):
        mon._feat_buffer.append(np.full(ncols, value))


def test_degenerate_features_are_counted_not_silently_diluting():
    """Half the voting set can never fire. The split must be visible."""
    names = [f"f{i}" for i in range(6)]
    # three strictly-increasing (measurable), three tied (degenerate)
    deciles = [list(range(11)), list(range(11)), list(range(11)),
               [0.0] * 11, [0.0] * 11, [1.0] * 11]
    mon = _mon()
    _feed(mon, len(names))
    mon.check_drift(deciles, names)

    assert mon.drift_degenerate == 3, (
        f"expected 3 tied-edge features, got {mon.drift_degenerate} - the "
        f"denominator provenance is not being computed")
    assert mon.drift_measurable == 3
    assert mon.drift_measurable + mon.drift_degenerate == 6


def test_the_share_the_operator_reads_carries_its_denominator():
    """status() must expose the split, or the number on the board still means
    something different from what its name says."""
    names = [f"f{i}" for i in range(4)]
    deciles = [list(range(11)), list(range(11)), [0.0] * 11, [0.0] * 11]
    mon = _mon()
    _feed(mon, len(names))
    mon.check_drift(deciles, names)
    st = mon.status()
    for k in ("drift_share", "drift_measurable", "drift_degenerate",
              "drift_share_measurable"):
        assert k in st, f"status() lost {k}"
    assert st["drift_measurable"] == 2 and st["drift_degenerate"] == 2


def test_the_TRIGGER_did_not_move():
    """THE LOAD-BEARING PIN. This change is SAFE only because drift_share and
    its threshold are untouched - moving them changes when ML-032 fires and
    therefore when the retrain loop runs, which is an operator adjudication.

    With 2 of 4 voting features drifting, drift_share must still be 0.50 (over
    ALL voting features), NOT 1.00 (over the measurable two)."""
    names = [f"f{i}" for i in range(4)]
    # two measurable columns that WILL drift, two tied that cannot
    deciles = [list(range(11)), list(range(11)), [0.0] * 11, [0.0] * 11]
    mon = _mon()
    # far outside the training deciles so the measurable ones genuinely drift,
    # and ABOVE psi()'s 10-sample floor so it actually computes
    for _ in range(_PSI_MIN_ROWS):
        mon._feat_buffer.append(np.array([999.0, 999.0, 0.0, 0.0]))
    mon.check_drift(deciles, names)

    assert mon.drifting, (
        "fixture produced no drift at all - the assertions below would compare "
        "0/4 against 0/2 and pass under any implementation")
    assert mon.drift_share == pytest.approx(len(mon.drifting) / 4), (
        "drift_share is no longer computed over ALL voting features - the "
        "trigger moved, and that is a model-side change, not a measurement one")
    assert mon.drift_share_measurable == pytest.approx(
        len(mon.drifting) / 2), "the measurable share is the ADDITIVE field"


def test_no_degenerate_features_means_the_two_shares_agree():
    """ANTI-RUBBER-STAMP: with nothing degenerate the split must collapse, or
    the new field is just a second name for the old one."""
    names = [f"f{i}" for i in range(3)]
    deciles = [list(range(11))] * 3
    mon = _mon()
    _feed(mon, len(names))
    mon.check_drift(deciles, names)
    assert mon.drift_degenerate == 0
    assert mon.drift_measurable == 3
    assert mon.drift_share == pytest.approx(mon.drift_share_measurable)


def test_all_degenerate_does_not_divide_by_zero():
    """The pathological end: every feature tied. The measurable share must be
    0.0, not NaN or an exception."""
    names = [f"f{i}" for i in range(3)]
    deciles = [[0.0] * 11] * 3
    mon = _mon()
    _feed(mon, len(names))
    mon.check_drift(deciles, names)
    assert mon.drift_measurable == 0
    assert mon.drift_share_measurable == 0.0


def test_excluded_features_are_not_counted_in_either_bucket():
    """DRIFT_EXCLUDED_FEATURES were already outside the denominator; the split
    must not quietly readmit them."""
    excluded = sorted(DRIFT_EXCLUDED_FEATURES)
    if not excluded:
        pytest.skip("no excluded features configured")
    names = [excluded[0], "f_other"]
    deciles = [[0.0] * 11, list(range(11))]
    mon = _mon()
    _feed(mon, len(names))
    mon.check_drift(deciles, names)
    assert mon.drift_measurable + mon.drift_degenerate == 1, (
        "an excluded feature was counted in the drift denominator")
