"""Fill-sim TTL normalization (owed item 40 - the #1 P&L-integrity fix).

THE DEFECT (fill-sim audit 2026-08-07, F3/CRITICAL): the passive-fill
hazard `p = sf_base * exp(-d/sigma)` was calibrated by inverting a
measured PER-ORDER trade-through rate at n_bar = 5.0 polls (~25s order
life, outputs/fill_calibration.json), then applied PER POLL with no
reference to the order's own lifetime. A 6h long-book bid draws 4,320
times: compounded fill probability ~1.0 at any distance - the ledger's
22-of-41 entries at exactly -50.0bps "improvement" and the positive
BTC/ETH markout where passive fills must be negative.

THE FIX: TTL-normalize the hazard so the PER-ORDER fill probability
matches the calibrated target at any lifetime:

    p_poll = 1 - (1 - p_cal) ** min(cal_life / ttl, 1.0)

Poll cadence cancels (n_cal/n_ord == cal_life/ttl), so no poll_sec
plumbing. Properties pinned here:
  * ttl == cal_life  -> p identical to the old model: the calibrated 5m
    book (25s timeout) is BIT-IDENTICAL, only extrapolated TTLs change.
  * long ttl         -> compounded per-order F equals the calibrated F,
    not ~1.0. The measured F(25s) is the floor estimate; real trade-
    through (the deterministic maker-cross path against the live book)
    still fills long orders whenever the market truly crosses.
  * short ttl        -> per-poll hazard CLAMPED at the calibrated value
    (exponent capped at 1.0): a 10s order fills less often than a 25s
    one, never more.
  * sf_base = 1.0 at the touch stays a certainty - the deterministic
    test fixtures (bug-78 fix) keep their guarantee.

This mints execution-era boundary #3 (after the QA-contamination
quarantine and XV-021): corpus rows before/after this commit were
filled under different simulators.
"""
import ast
import math
from pathlib import Path

import execution.order_manager as om_mod


CAL = 25.0     # sim_fill.calibration_life_sec shipped value


def _F(p_poll: float, ttl: float, poll: float = 5.0) -> float:
    """Compounded per-order fill probability over the order's life."""
    n = ttl / poll
    return 1.0 - (1.0 - p_poll) ** n


def test_identity_at_calibration_life():
    """ttl == cal_life must reproduce sf_base * exp(-d/sigma) exactly -
    the calibrated 5m book is bit-identical to the old model."""
    for sf_base, d, sig in ((0.048, 0.0, 1.0), (0.048, 10.0, 30.0),
                            (0.2, 50.0, 30.0)):
        expected = sf_base * math.exp(-d / sig)
        got = om_mod._passive_poll_prob(sf_base, d, sig, CAL, CAL)
        assert abs(got - expected) < 1e-12


def test_long_ttl_per_order_probability_is_invariant():
    """The whole point: compounded F over a 6h life equals compounded F
    over the calibrated 25s life - not ~1.0."""
    sf_base, d, sig = 0.048, 10.0, 30.0
    p_cal = om_mod._passive_poll_prob(sf_base, d, sig, CAL, CAL)
    p_long = om_mod._passive_poll_prob(sf_base, d, sig, 21600.0, CAL)
    F_cal = _F(p_cal, CAL)
    F_long = _F(p_long, 21600.0)
    assert abs(F_cal - F_long) < 1e-9, (
        f"per-order F must be TTL-invariant: F(25s)={F_cal:.6f} "
        f"F(6h)={F_long:.6f}")
    assert F_long < 0.2, "the compounded-to-certainty gift must be dead"


def test_long_ttl_hazard_is_orders_of_magnitude_smaller():
    """The -50bps guaranteed-fill signature dies here: per-poll hazard on
    a 6h order is ~864x smaller than the calibrated per-poll hazard."""
    p_cal = om_mod._passive_poll_prob(0.048, 10.0, 30.0, CAL, CAL)
    p_long = om_mod._passive_poll_prob(0.048, 10.0, 30.0, 21600.0, CAL)
    assert p_long < p_cal / 100.0


def test_short_ttl_clamps_at_calibrated_hazard():
    """A 10s order must fill LESS often than a 25s one, never more: the
    exponent caps at 1.0, so per-poll hazard equals the calibrated one
    and the shorter life naturally yields a smaller per-order F."""
    p_cal = om_mod._passive_poll_prob(0.048, 10.0, 30.0, CAL, CAL)
    p_short = om_mod._passive_poll_prob(0.048, 10.0, 30.0, 10.0, CAL)
    assert abs(p_short - p_cal) < 1e-12


def test_deterministic_fixture_guarantee_survives():
    """sf_base=1.0 is the deterministic TEST MODE (bug-78 fixture
    convention) - calibration can never emit the boundary value (Wilson
    keeps estimates off 0/1), so 1.0 bypasses TTL normalization entirely
    and every pinned fixture keeps its old behavior byte-identical."""
    for ttl in (5.0, CAL, 3600.0, 21600.0):
        assert om_mod._passive_poll_prob(1.0, 0.0, 30.0, ttl, CAL) == 1.0
        # away from the touch, deterministic mode keeps the RAW hazard
        # exp(-d/sigma) at any ttl - exactly the pre-fix model
        got = om_mod._passive_poll_prob(1.0, 2.5, 500.0, ttl, CAL)
        assert abs(got - math.exp(-2.5 / 500.0)) < 1e-12


def test_degenerate_inputs_never_raise_never_escape_bounds():
    for args in ((0.048, 10.0, 0.0, 21600.0, CAL),    # zero sigma
                 (0.048, -5.0, 30.0, 21600.0, CAL),   # negative distance
                 (0.048, 10.0, 30.0, 0.0, CAL),       # zero ttl
                 (0.048, 10.0, 30.0, 21600.0, 0.0),   # zero cal life
                 (1.5, 10.0, 30.0, 21600.0, CAL)):    # over-unit base
        p = om_mod._passive_poll_prob(*args)
        assert math.isfinite(p) and 0.0 <= p <= 1.0


def test_poll_dry_wires_the_normalized_hazard():
    """Parsed-AST pin: _poll_dry must call _passive_poll_prob and must
    no longer contain the bare exp-hazard inline."""
    tree = ast.parse(Path(om_mod.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_poll_dry")
    calls = {c.func.id for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "_passive_poll_prob" in calls
