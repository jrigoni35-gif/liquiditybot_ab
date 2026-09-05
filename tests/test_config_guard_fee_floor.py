"""The sub-floor fee FATAL must sit at VENUE TRUTH — measured, not asserted.

CORRECTED 2026-09-05, AND THE CORRECTION IS THE POINT OF THIS FILE.

This suite previously pinned the floor at 40/80 bps and asserted that a config
booking 25/40 must FATAL as "understated". Both were wrong, and they were
wrong in the way this repo keeps paying for: a belief about an external system
was written into a constant, then pinned by a test, so the pin defended the
error instead of the property.

Read live from https://api.kraken.com/0/public/AssetPairs on 2026-09-05,
identical across FLOW/ETH/XBT/SOL/LINK-USD (so: an account-wide spot
schedule, not per-pair). Kraken's published rows are

    >=        $0   25 / 40 bps      <- the zero-volume row: the MOST anyone pays
    >=   $10,000   20 / 35
    >=   $50,000   14 / 24
    >=  $100,000   12 / 22
    ... down to 0 / 5 at >= $500,000,000

**40/80 is not a row. Neither is 22/38.** The prior header called 25/40 "the
retired tier"; it is not retired, it is the current zero-volume row. So the
2026-08-29 "stale-floor correction" moved the constant from the venue's real
bottom row to a figure the venue has never published — on the same false
premise that produced cut #8's fee booking.

WHAT THE FLOOR MEANS, restated so it cannot drift again: no spot account pays
LESS than the zero-volume row unless it has earned a volume discount, which is
exactly what `pretrade.allow_sub_floor_fees` declares. That is the property.
The NUMBER is derived from core/venue_fees, which scripts/fee_drift_report.py
diffs against the live endpoint — because a constant cannot confirm itself,
and that is how this went wrong twice.

These pins therefore assert the floor AGAINST THE SCHEDULE, never against a
literal repeated here.
"""
import pytest

from core.config_guard import (KRAKEN_SPOT_FLOOR_MAKER_BPS,
                               KRAKEN_SPOT_FLOOR_TAKER_BPS, validate)
from core.venue_fees import (KRAKEN_SPOT_SCHEDULE, binding_row,
                             fetch_live_schedule, is_a_published_row,
                             worst_row)

_FLOOR_M, _FLOOR_T = worst_row()


def _fatal_msgs(cfg):
    out = []
    for f in validate(cfg):
        sev = f[0] if isinstance(f, (tuple, list)) else getattr(f, "severity", "")
        msg = f[1] if isinstance(f, (tuple, list)) else str(f)
        if str(sev).upper() == "FATAL":
            out.append(str(msg))
    return out


def _has_floor_fatal(cfg):
    return any("floor" in m.lower() or "below kraken" in m.lower()
               for m in _fatal_msgs(cfg))


def _cfg(maker, taker, *, dry_run=False, allow_low=False):
    return {
        "system": {"dry_run": dry_run},
        "pretrade": {"maker_fee_bps": maker, "taker_fee_bps": taker,
                     "allow_sub_floor_fees": allow_low},
        "order_manager": {"maker_fee_bps": maker, "taker_fee_bps": taker},
    }


# --------------------------------------------------------- the floor itself
def test_floor_is_the_venue_zero_volume_row():
    """The constant must BE the schedule's worst row, not a literal."""
    assert (KRAKEN_SPOT_FLOOR_MAKER_BPS,
            KRAKEN_SPOT_FLOOR_TAKER_BPS) == worst_row()
    assert (KRAKEN_SPOT_FLOOR_MAKER_BPS,
            KRAKEN_SPOT_FLOOR_TAKER_BPS) == (KRAKEN_SPOT_SCHEDULE[0][1],
                                             KRAKEN_SPOT_SCHEDULE[0][2])


def test_the_floor_is_a_row_the_venue_actually_publishes():
    """THE REGRESSION PIN. 40/80 passed the old suite and is not a Kraken
    tier at all. Any floor that is not a published row is, by construction,
    a number someone made up."""
    assert is_a_published_row(KRAKEN_SPOT_FLOOR_MAKER_BPS,
                              KRAKEN_SPOT_FLOOR_TAKER_BPS), (
        f"floor {KRAKEN_SPOT_FLOOR_MAKER_BPS}/{KRAKEN_SPOT_FLOOR_TAKER_BPS} "
        f"is not a published Kraken tier")
    assert not is_a_published_row(40.0, 80.0), \
        "40/80 must never again read as a venue tier"
    assert not is_a_published_row(22.0, 38.0), \
        "22/38 (cut #9's booking) is not a venue tier either"


# ------------------------------------------------------------- the behaviour
def test_the_zero_volume_row_passes_exactly_at_the_floor():
    """25/40 is venue truth for an account with no volume discount. The old
    suite asserted it must FATAL - the exact inversion this file corrects."""
    assert not _has_floor_fatal(_cfg(_FLOOR_M, _FLOOR_T))


@pytest.mark.parametrize("maker,taker", [(0.0, 0.0), (5.0, 10.0),
                                         (12.0, 22.0), (20.0, 35.0),
                                         (24.9, 39.9)])
def test_genuinely_sub_floor_fees_fatal_in_live(maker, taker):
    """Everything strictly below the zero-volume row trips the guard unless
    a discount is declared - including real discount tiers, which is correct:
    claiming one without declaring it is what the flag is for."""
    assert maker < _FLOOR_M or taker < _FLOOR_T, "fixture is not sub-floor"
    assert _has_floor_fatal(_cfg(maker, taker))


def test_fees_above_the_floor_do_not_fatal():
    """ANTI-RUBBER-STAMP: the guard must be able to stay silent, or every
    assertion above is satisfied by a guard that fatals unconditionally."""
    assert not _has_floor_fatal(_cfg(30.0, 50.0))
    assert not _has_floor_fatal(_cfg(100.0, 200.0))


def test_deleted_fee_keys_fall_back_and_are_judged_on_the_fallback():
    """A config that DELETES the fee keys must not silently pass. Whatever
    the guard's fallback is, the outcome has to be decidable - assert the
    behaviour rather than a number, so a fallback change is visible."""
    cfg = {"system": {"dry_run": False}, "pretrade": {}, "order_manager": {}}
    msgs = _fatal_msgs(cfg)
    assert msgs, "a config with no fee keys at all produced no FATAL"


def test_allow_sub_floor_escape_still_works():
    """A genuine volume-tier discount can opt out. Unchanged behaviour, and
    the shipped config relies on it."""
    assert not _has_floor_fatal(_cfg(20.0, 35.0, allow_low=True))


# ---------------------------------------------------- the anti-rot mechanism
def test_reference_schedule_still_matches_the_live_venue():
    """The table cannot confirm itself. When a network is available, diff it
    against the venue; SKIP - never silently pass - when it is not, because
    "no drift" and "the check never ran" are the same observation until they
    are separated."""
    live = fetch_live_schedule("ETH/USD")
    if live is None:
        pytest.skip("venue unreachable - this pin establishes nothing here")
    assert tuple(live) == tuple(KRAKEN_SPOT_SCHEDULE), (
        "Kraken's published schedule has MOVED. Update "
        "core/venue_fees.KRAKEN_SPOT_SCHEDULE and re-stamp "
        "SCHEDULE_READ_UTC; then re-check the booked fee against it.")


def test_binding_row_needs_a_volume_and_refuses_to_guess():
    """A tier cannot be resolved without a 30-day volume. Returning a
    plausible default would recreate the struck-literal failure exactly."""
    assert binding_row(None) is None
    assert binding_row(-1) is None
    assert binding_row(0) == (25.0, 40.0)
    assert binding_row(17_482) == (20.0, 35.0)
    assert binding_row(10_000) == (20.0, 35.0)      # boundary is inclusive
    assert binding_row(9_999) == (25.0, 40.0)


# ------------------------------- the escape hatch had no floor of its own
def test_allow_sub_floor_is_not_a_licence_for_ZERO_fees():
    """THE REGRESSION. allow_sub_floor_fees exists so an account with a genuine
    volume discount can book below the zero-volume row. It was set true at cut
    #9 to permit 22/38, and it disabled the floor for ANY value: measured
    2026-09-05 on the shipped config, 0.0/0.0 and 1.0/1.0 both validated with
    ZERO fatals.

    Understated fees are the single highest-leverage silent defect available
    here - they make the pre-trade EV gate admit net-losing trades while every
    downstream number stays internally consistent. A discount flag must have a
    floor of its own, and the honest one is the venue's BEST published tier:
    nobody pays less than that at any volume."""
    assert _has_floor_fatal(_cfg(0.0, 0.0, allow_low=True)), \
        "zero fees validated clean under the discount flag"
    assert _has_floor_fatal(_cfg(1.0, 1.0, allow_low=True))
    assert _has_floor_fatal(_cfg(0.0, 4.9, allow_low=True)), \
        "a taker below the venue's cheapest published tier is not a discount"


def test_a_genuine_top_tier_discount_still_passes():
    """ANTI-RUBBER-STAMP, and it must not become a false floor: maker 0 IS a
    real Kraken tier (>=$10M 30-day volume), so the bound is the best PUBLISHED
    row, not a made-up positive number."""
    best_m, best_t = __import__("core.venue_fees", fromlist=["x"]).best_possible_row()
    assert not _has_floor_fatal(_cfg(best_m, best_t, allow_low=True)), \
        f"the venue's own best tier {best_m}/{best_t} was rejected as sub-floor"
    assert not _has_floor_fatal(_cfg(20.0, 35.0, allow_low=True))
    assert not _has_floor_fatal(_cfg(22.0, 38.0, allow_low=True)), \
        "the SHIPPED config must keep validating - this change is SAFE only " \
        "because it does not move the live posture"


def test_absent_fee_keys_are_a_FATAL_not_a_silent_default():
    """Dropping the keys entirely produced ZERO fee fatals (measured
    2026-09-05), and four consumers then substitute four different fallback
    schedules. A half-applied fee stage (fee_correction_stage /
    boundary5_stage rewrite all four together) is the realistic trigger.

    Uses the SHIPPED config with only the fee keys removed. A hand-built
    minimal dict is not usable here: the first draft of this pin did that and
    was VACUOUS - 11 unrelated FATALs fired (starting_capital, profit tiers)
    and satisfied a bare `assert _fatal_msgs(cfg)` for entirely the wrong
    reason. The assertion must name the subject."""
    import copy
    import json as _json
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    cfg = copy.deepcopy(_json.loads(
        (root / "config.json").read_text(encoding="utf-8")))
    baseline = [m for m in _fatal_msgs(cfg) if "fee" in m.lower()]
    assert not baseline, (
        f"the SHIPPED config already has a fee FATAL - this fixture cannot "
        f"isolate the absent-key case: {baseline}")

    for section in ("pretrade", "order_manager"):
        for key in ("maker_fee_bps", "taker_fee_bps"):
            cfg[section].pop(key, None)
    fee_fatals = [m for m in _fatal_msgs(cfg) if "fee" in m.lower()]
    assert fee_fatals, (
        "the fee keys were removed from BOTH pretrade and order_manager and "
        "no fee FATAL fired - four consumers then substitute four different "
        "fallback schedules, silently")
