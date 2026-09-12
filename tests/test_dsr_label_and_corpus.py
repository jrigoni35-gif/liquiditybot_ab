"""OF-5 must not claim to measure the sign of the edge, and must disclose
what it graded.

TWO DEFECTS, both found 2026-09-11 by a literature pass that read the code
before it read the papers.

  1. THE LABEL WAS FALSE. `ml.overfit.deflated_sharpe`'s docstring and both
     of OF-5's gate labels read "P(true SR > 0)". The function computes
     z = (sr - sr0)/denom with sr0 = the expected maximum Sharpe under the
     null across N trials, which is strictly positive for N > 1. So the
     number is P(true SR > sr0), and reading it as the sign of the edge
     overstates the evidence by the whole width of the deflation.

  2. THE CORPUS WAS UNDISCLOSED. The gate printed a bare count. Measured
     that day the "30 conviction trips" spanned 53 days and 28 of them
     closed before cut #10 - a statistic about two superseded
     configurations, presented as a verdict on the deployed one.

Neither fix moves the n=30 floor or the 0.90 threshold. Both are disclosure.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ml.overfit import deflated_sharpe                     # noqa: E402
from scripts.overfit_check import dsr_sample_span          # noqa: E402


# ---------------------------------------------------------------------------
# 1. the two quantities are DIFFERENT, and the difference is the deflation
# ---------------------------------------------------------------------------

def test_dsr_is_measured_against_a_positive_threshold_not_zero():
    """The defect in one assertion: if sr0 were 0 the gate's label would have
    been right, and this test would be vacuous. It is not."""
    d = deflated_sharpe(0.30, 30, n_trials=7)
    assert d["sr0_threshold"] > 0.0, (
        "sr0 is the expected max Sharpe under the null - a zero here means "
        "the trials deflation has been removed and 'P(true SR > 0)' would "
        "again be an accurate label for a gate that no longer deflates")
    assert d["psr_zero"] > d["dsr"], (
        "PSR at SR*=0 must exceed DSR whenever sr0 > 0; if these are equal "
        "the deflation is not being applied to the graded number")


def test_psr_zero_is_the_quantity_the_old_label_described():
    """PSR(0) must equal the DSR computed with the deflation switched off -
    i.e. n_trials=1, where the code sets e_max = 0.0 explicitly."""
    for sr in (-0.24, 0.0, 0.35, 0.80):
        deflated = deflated_sharpe(sr, 30, skew=0.4, kurtosis=2.8, n_trials=7)
        undeflated = deflated_sharpe(sr, 30, skew=0.4, kurtosis=2.8,
                                     n_trials=1)
        assert math.isclose(deflated["psr_zero"], undeflated["dsr"],
                            rel_tol=1e-12), (
            f"psr_zero at SR={sr} does not reproduce the N=1 DSR, so it is "
            f"not the SR*=0 reading it claims to be")


def test_a_negative_sharpe_does_not_read_as_proven_harm():
    """The operating characteristic that matters. At the measured shape
    (SR<0, n=30) the graded dsr is near zero, but PSR(0) must stay well
    inside the band where the sign is undetermined - the sample's own CI
    spans zero. A test asserting only `dsr < 0.9` would pass while the
    instrument still invited 'the edge is negative'."""
    d = deflated_sharpe(-0.24, 30, skew=0.49, kurtosis=2.70, n_trials=7)
    assert d["dsr"] < 0.05, "graded dsr should be far from passing here"
    assert 0.05 < d["psr_zero"] < 0.5, (
        "P(true SR > 0) must be reported as a genuinely uncertain quantity "
        "at this sample size, not as a near-zero that reads like proof")
    se = math.sqrt((1 + 0.24 ** 2 / 2) / 30)
    assert -0.24 + 1.96 * se > 0, (
        "CONTROL: the 95% CI on this Sharpe must span zero. If it ever "
        "stops spanning zero, the 'underpowered not harmful' reading in "
        "the gate's own SIGN READING line has to be revisited")


def test_psr_zero_is_monotone_in_the_observed_sharpe():
    """The pin that would have caught the ORIGINAL var_trial_sr inversion,
    now applied to the new key too. The replaced fallback scored a better
    track WORSE; no test asserted the sign of the derivative."""
    vals = [deflated_sharpe(sr, 30, n_trials=7)["psr_zero"]
            for sr in (-0.5, -0.2, 0.0, 0.2, 0.5, 0.9)]
    assert vals == sorted(vals), f"psr_zero is not monotone in SR: {vals}"
    dsrs = [deflated_sharpe(sr, 30, n_trials=7)["dsr"]
            for sr in (-0.5, -0.2, 0.0, 0.2, 0.5, 0.9)]
    assert dsrs == sorted(dsrs), f"dsr is not monotone in SR: {dsrs}"


def test_dsr_decreases_as_trials_rise():
    """More tries searched = a higher bar. Monotone DECREASING in N."""
    vals = [deflated_sharpe(0.5, 30, n_trials=N)["dsr"]
            for N in (1, 7, 25, 100, 512)]
    assert vals == sorted(vals, reverse=True), (
        f"dsr must fall as the trial count rises: {vals}")


# ---------------------------------------------------------------------------
# 2. the corpus disclosure
# ---------------------------------------------------------------------------

def _row(pnl, probe, ts):
    return {"net_pnl_usd": str(pnl), "probe": probe, "ts": str(ts)}


def test_span_covers_conviction_rows_only():
    """A probe row inside the window must not widen the reported span -
    OF-5 grades the conviction sample, so the disclosure must describe it."""
    rows = [_row(1.0, "0", 1_000_000.0),
            _row(1.0, "1", 9_000_000.0),      # probe, far in the future
            _row(1.0, "0", 1_086_400.0)]
    span = dsr_sample_span(rows)
    assert span["n"] == 2
    assert math.isclose(span["days"], 1.0, rel_tol=1e-9), (
        "a probe row leaked into the conviction span, so the gate would "
        "disclose a corpus it did not grade")


def test_span_reports_the_real_width_not_the_row_count():
    rows = [_row(1.0, "0", 1700000000.0),
            _row(1.0, "0", 1700000000.0 + 53.17 * 86400.0)]
    span = dsr_sample_span(rows)
    assert span["available"] is True
    assert 53.0 < span["days"] < 53.4


def test_span_is_unavailable_rather_than_guessed_when_ts_is_missing():
    """Pre-marker rows carry no usable ts. Inventing a span would be the
    confident-instrument failure this repo keeps paying for."""
    assert dsr_sample_span([_row(1.0, "0", "")])["available"] is False
    assert dsr_sample_span([])["available"] is False


def test_unparseable_ts_does_not_crash_the_gate():
    rows = [_row(1.0, "0", "not-a-timestamp"), _row(1.0, "0", 100.0)]
    span = dsr_sample_span(rows)
    assert span["n"] == 1


# ---------------------------------------------------------------------------
# 3. the assembled disclosure the gate actually prints
# ---------------------------------------------------------------------------

def test_disclosure_names_both_the_sign_reading_and_the_era_pooling():
    from scripts.overfit_check import dsr_disclosure
    d = deflated_sharpe(-0.24, 30, skew=0.49, kurtosis=2.70, n_trials=7)
    rows = [_row(1.0, "0", 1700000000.0),
            _row(-1.0, "0", 1700000000.0 + 53.17 * 86400.0)]
    msg = dsr_disclosure(d, rows)
    assert "PSR(SR*=0)" in msg and "P(true SR < 0)" in msg
    assert "53.2 days" in msg, "the corpus width must be stated, not implied"
    assert "exec_era" in msg, (
        "the disclosure must say WHY it cannot era-scope, or the next reader "
        "repeats the 2026-09-11 finding that label_era encodes the horizon")
    assert "2 conviction trips" in msg


def test_disclosure_degrades_honestly_when_the_span_is_unknown():
    """It must never invent a span - and must still deliver the sign reading,
    since that half does not depend on timestamps."""
    from scripts.overfit_check import dsr_disclosure
    d = deflated_sharpe(0.1, 30, n_trials=7)
    msg = dsr_disclosure(d, [_row(1.0, "0", "")])
    assert "UNKNOWN" in msg
    assert "PSR(SR*=0)" in msg


def test_disclosure_survives_a_track_too_short_for_a_dsr():
    """deflated_sharpe returns {'dsr': None, 'reason': ...} below n=3, with
    no psr_zero key. The disclosure is printed next to a verdict, so a
    KeyError here would take the whole OF-5 rung down with it."""
    from scripts.overfit_check import dsr_disclosure
    msg = dsr_disclosure(deflated_sharpe(0.5, 2), [_row(1.0, "0", 1700000000.0)])
    assert "psr_zero unavailable" in msg


# ---------------------------------------------------------------------------
# 4. THE CRASH PATH — a disclosure must never take the battery down
#
# Found by an adversarial pass on 2026-09-11, after the code above shipped.
# `float()` ACCEPTS "nan", "inf" and a millisecond stamp, so a try/except
# around it is not a validity check. Each of those reaches
# datetime.fromtimestamp() in dsr_disclosure and raises ValueError /
# OverflowError / OSError — from a call site with NO enclosing try, inside a
# DEFINITION-OF-DONE gate. One bad row would abort the whole battery with a
# traceback, which test_windows.bat renders as "OVERFIT GATES FAILED".
#
# NOT HYPOTHETICAL: ml/history.py:180 reads this same file with
# `float(row.get("ts") or "nan")` — the repo's own loader mints NaN for a
# missing ts. The corpus was clean when measured, so this was LATENT.
# ---------------------------------------------------------------------------

import pytest  # noqa: E402


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "1789142204000",
                                 "-1", "0", "1e30"])
def test_a_poisoned_ts_cannot_crash_the_disclosure(bad):
    from scripts.overfit_check import dsr_disclosure
    d = deflated_sharpe(-0.24, 30, n_trials=7)
    rows = [_row(1.0, "0", bad), _row(1.0, "0", 1_700_000_000.0)]
    msg = dsr_disclosure(d, rows)          # must not raise
    assert "PSR(SR*=0)" in msg
    assert "EXCLUDED from this span" in msg, (
        f"ts={bad!r} was silently accepted or silently dropped; an excluded "
        f"row must be COUNTED and disclosed, not hidden")


@pytest.mark.parametrize("bad", ["nan", "inf", "1789142204000"])
def test_the_span_rejects_unusable_timestamps_and_counts_them(bad):
    span = dsr_sample_span([_row(1.0, "0", bad)])
    assert span["available"] is False
    assert span["rejected"] == 1


def test_an_all_poisoned_corpus_still_produces_a_disclosure():
    """Every ts unusable: the gate must still grade and still speak."""
    from scripts.overfit_check import dsr_disclosure
    d = deflated_sharpe(-0.24, 30, n_trials=7)
    msg = dsr_disclosure(d, [_row(1.0, "0", "nan"), _row(1.0, "0", "inf")])
    assert "UNKNOWN" in msg and "PSR(SR*=0)" in msg


def test_good_rows_survive_alongside_poisoned_ones():
    span = dsr_sample_span([_row(1.0, "0", "nan"),
                            _row(1.0, "0", 1_700_000_000.0),
                            _row(1.0, "0", 1_700_086_400.0)])
    assert span["available"] is True
    assert span["n"] == 2 and span["rejected"] == 1
    assert abs(span["days"] - 1.0) < 1e-6
