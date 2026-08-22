"""scripts/cost_attribution.py — the fee schedule it benchmarks against, and
the dispersion it is now required to print.

WHY THIS EXISTS. On 2026-08-21 this tool's headline line —
`mean gross +0.0733% (POSITIVE)` — was read as a measured edge and became a
session-long thesis ("fees are 10x the gross edge"). Both halves were wrong
and the tool was the proximate cause of both:

  * it benchmarked against KRAKEN 16/26, a schedule this project STRUCK on
    2026-08-07. Kraken Tier 1 (spot volume $0, which is this account) is
    40/80. So it reported the venue as CHEAPER than the configured 25/40
    when the venue is nearly twice as expensive — the flattering direction,
    which makes every counterfactual on the page optimistic; and
  * it printed an equal-weighted mean with no interval, no dollar
    weighting, and its own NEGATIVE median two sections away.

These pins are structural, not numeric: they must hold on any corpus, so
they cannot rot as fills accrue.
"""
import subprocess
import sys
from pathlib import Path

import scripts.cost_attribution as ca

ROOT = Path(__file__).resolve().parents[1]


def test_benchmarks_against_the_verified_tier_not_the_struck_one():
    """16/26 was struck 2026-08-07 and keeps being reintroduced from
    secondary fee blogs that still publish 0.25/0.40 as current."""
    assert ca.KRAKEN_T1_MAKER_BPS == 40.0
    assert ca.KRAKEN_T1_TAKER_BPS == 80.0
    assert not hasattr(ca, "KRAKEN_MAKER_BPS"), \
        "the struck 16/26 constants must not come back"
    assert not hasattr(ca, "KRAKEN_TAKER_BPS")


def test_tier1_is_the_expensive_row_not_the_conservative_one():
    """The old comment claimed base tier was the conservative check because
    'lower tiers only reduce these'. That INVERTS: T1 is the entry tier and
    the most expensive; volume buys you DOWN to T5."""
    assert ca.KRAKEN_T1_MAKER_BPS > ca.KRAKEN_T5_MAKER_BPS
    assert ca.KRAKEN_T1_TAKER_BPS > ca.KRAKEN_T5_TAKER_BPS


def _run():
    p = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "cost_attribution.py")],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    assert p.returncode in (0, 1), p.stderr[-500:]
    return p.stdout


def test_dispersion_is_printed_before_the_mean():
    """A point estimate with no dispersion beside it invites over-reading.
    The section must exist AND precede the schedule table, because reading
    order is what actually failed here."""
    out = _run()
    if "no closed positions" in out:
        return                      # empty corpus: nothing to disperse
    assert "1b. DISPERSION" in out
    assert "DOLLAR-WEIGHTED gross" in out
    assert "median" in out
    assert "day-clustered" in out, "an iid SE over concurrent trips is optimistic"
    assert "drop top 5" in out, "influence of the tail must be visible"
    assert out.index("1b. DISPERSION") < out.index("2. WHAT EACH SCHEDULE")


def test_ratio_framing_is_refused_when_the_edge_contains_zero():
    """The specific error to prevent: quoting 'fees are Nx the gross edge'
    when the denominator is not distinguishable from zero."""
    out = _run()
    if "no closed positions" in out or "INSIDE 2x" not in out:
        return                      # only asserts when the guard fires
    assert "Do NOT quote a" in out
    assert "denominator contains zero" in out
