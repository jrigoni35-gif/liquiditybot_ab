"""Tests for scripts/tail_control_sim.py — the SAFE tail-control counterfactual.

The prize rests on ONE line, `stop_cap` (truncate a loser to the cap). The
mutation-kill target is that line: inverting it (max->min, or flipping the
sign of the cap) MUST turn at least one pin red. Pure-function pins do not
touch the live fills; the frozen-fills integration pins assert the delegation
to cohort_eval.era4_trips and the pct-vs-USD double-derive.
"""
import math
from pathlib import Path

import pytest

from scripts import tail_control_sim as tcs

ROOT = Path(__file__).resolve().parents[1]
FILLS = ROOT / "outputs" / "fills.csv"


# ---------------------------------------------------------------- pure pins
def test_stop_cap_truncates_downside_only():
    # a loser worse than the cap is lifted to exactly -cap
    assert tcs.stop_cap(-3.0, 0.5) == -0.5
    # a loser inside the cap is untouched
    assert tcs.stop_cap(-0.3, 0.5) == -0.3
    # a winner is never touched
    assert tcs.stop_cap(2.0, 0.5) == 2.0
    # exactly at the cap is untouched
    assert tcs.stop_cap(-0.5, 0.5) == -0.5


def test_stop_cap_mutation_kill():
    # MUTATION SENTINEL: if `stop_cap` were min() instead of max(), or the cap
    # sign flipped, capping a deep loser would NOT lift it to -cap. This pin is
    # the one that goes red under that mutation.
    capped = tcs.stop_cap(-5.0, 0.5)
    assert capped == -0.5, "cap must lift a loser UP to -cap, not down"
    assert capped > -5.0, "capping a loser must improve it"


def test_reprice_null_flat_bracket():
    trip = {"gross_pct": 1.0, "cash_usd": 10.0, "notional_usd": 1000.0}
    net_pct, net_usd = tcs.reprice_null(trip, 60)
    assert net_pct == pytest.approx(1.0 - 0.60)          # 60bps = 0.60%
    assert net_usd == pytest.approx(10.0 - 1000.0 * 60 / 1e4)  # 10 - 6 = 4


def test_gap_through_flag():
    # gap-through = null net ran past 2x the cap depth
    assert tcs.is_gap_through(-1.5, 0.5) is True   # -1.5 < -1.0
    assert tcs.is_gap_through(-1.0, 0.5) is False  # exactly at 2x, not beyond
    assert tcs.is_gap_through(-0.8, 0.5) is False
    assert tcs.is_gap_through(+2.0, 0.5) is False


def _synthetic_trips():
    # three winners, three losers of increasing depth; equal $1000 notional so
    # gross% and USD stay trivially reconcilable. Non-overlapping spans -> each
    # is fully unique (effective_n == n) so the SE math is checkable by hand.
    specs = [(2.0, 0), (1.0, 10), (0.5, 20),
             (-0.8, 30), (-2.0, 40), (-4.0, 50)]
    trips = []
    for i, (gross, t0) in enumerate(specs):
        cash = gross / 100.0 * 1000.0
        trips.append({"pid": f"p{i}", "gross_pct": gross,
                      "t_open": float(t0), "t_close": float(t0) + 5.0,
                      "cash_usd": cash, "notional_usd": 1000.0})
    return trips


def test_capping_never_worsens_and_improves_losers():
    trips = _synthetic_trips()
    m = tcs.policy_metrics(trips, 60, 1.0, neff=6.0, se_infl=1.0)
    w = m["with_capfill"]
    # paired improvement over null is non-negative and strictly positive here.
    # At 60bps net = gross-0.60, so the losers net -1.4/-2.6/-4.6 are all worse
    # than -1.0 and get capped (the -0.8 gross trip nets -1.4, past the cap).
    assert w["improvement_vs_null_pct"] > 0
    assert w["n_capped"] == 3


def test_tighter_cap_gives_higher_mean():
    trips = _synthetic_trips()
    means = [tcs.policy_metrics(trips, 60, c, 6.0, 1.0)["with_capfill"]
             ["mean_net_pct"] for c in (0.5, 1.0, 1.5, 2.0)]
    # monotone non-increasing as the cap loosens (tighter cap truncates more)
    assert means == sorted(means, reverse=True)
    # MUTATION: with stop_cap inverted this ordering breaks (looser caps would
    # not monotonically lower the mean).


def test_no_losers_means_no_improvement():
    # all winners -> nothing to cap -> delta all zero -> not distinguishable
    trips = [{"pid": f"w{i}", "gross_pct": 1.0 + i, "t_open": float(i * 10),
              "t_close": float(i * 10) + 1.0, "cash_usd": (1.0 + i) * 10.0,
              "notional_usd": 1000.0} for i in range(4)]
    w = tcs.policy_metrics(trips, 60, 0.5, 4.0, 1.0)["with_capfill"]
    assert w["improvement_vs_null_pct"] == 0.0
    assert w["distinguishable"] is False


def test_se_eff_uses_effective_n():
    trips = _synthetic_trips()
    # halving effective_n inflates SE_eff by sqrt(2); the distinguishable bar
    # therefore widens. Check the SE scales as 1/sqrt(neff).
    a = tcs.policy_metrics(trips, 60, 1.0, neff=6.0, se_infl=1.0)["with_capfill"]
    b = tcs.policy_metrics(trips, 60, 1.0, neff=3.0, se_infl=1.0)["with_capfill"]
    assert b["se_eff_delta_pct"] == pytest.approx(
        a["se_eff_delta_pct"] * math.sqrt(2.0), rel=1e-9)


# --------------------------------------------------- frozen-fills integration
@pytest.mark.skipif(not FILLS.exists(), reason="no fills.csv on this box")
def test_delegates_selection_to_era4_trips():
    from scripts.cohort_eval import era4_trips
    res = tcs.compute(str(FILLS))
    assert res["n"] == len(era4_trips(str(FILLS)))     # same population
    assert res["cut_ts"] == 1786403127.0               # registered cut
    assert res["verdict"] in ("TAIL-CONTROL-PAYS", "UNDECIDABLE-AT-N",
                              "DOESNT-PAY")


@pytest.mark.skipif(not FILLS.exists(), reason="no fills.csv on this box")
def test_double_derive_pct_and_usd_agree():
    res = tcs.compute(str(FILLS))
    dd = res["double_derive_best_mean"]
    assert dd["agree"] is True
    assert dd["route_pct"] == pytest.approx(dd["route_usd"], abs=1e-9)


@pytest.mark.skipif(not FILLS.exists(), reason="no fills.csv on this box")
def test_usd_reconstruction_matches_gross():
    # The real check is the per-trip USD==gross reconstruction (the loop) on
    # whatever the LIVE cohort is. The count is >= 63, NOT == 63: the cohort is
    # selected by close-ts>=threshold, so it grows monotonically as the live
    # dry-run bot closes more qualifying trips (host-state-dependent green — a
    # hard ==63 flaked to 64 the first time a new trip closed). The registration
    # froze n=63; the live file only grows past it.
    trips = tcs.load_cohort(str(FILLS))
    assert len(trips) >= 63
    for t in trips:
        chk = 100.0 * t["cash_usd"] / t["notional_usd"]
        assert chk == pytest.approx(t["gross_pct"], abs=1e-6)
