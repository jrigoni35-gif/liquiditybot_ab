"""The sub-floor fee FATAL must sit at VENUE TRUTH, not the retired tier.

Cut #8 (2026-08-28) moved Kraken Tier-1 fees 25/40 -> 40/80 bps. The
config_guard FATAL whose sole job is "understated fees make the pre-trade
gate approve net-losing trades" kept a 25/40 floor through the cut, so a
config anywhere in [25/40, 40/80) - up to HALF the true taker leg - passed
silently. Measured 2026-08-29 (stated-vs-real audit, injection-confirmed);
corrected same day. These pins go RED if the floor ever regresses below
venue truth, so the guard can never again be understated relative to the
schedule it protects against.

The floor moving is a MEASUREMENT-STANDARD change tied to the exec era, not
a tunable - when the next era re-prices fees, this floor and these pins move
WITH it, consciously.
"""
import pytest

from core.config_guard import (KRAKEN_SPOT_FLOOR_MAKER_BPS,
                               KRAKEN_SPOT_FLOOR_TAKER_BPS, validate)


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


def test_floor_is_venue_true_40_80():
    # The constant IS the pin: regressing it to the retired 25/40 tier fails.
    assert KRAKEN_SPOT_FLOOR_MAKER_BPS == 40.0
    assert KRAKEN_SPOT_FLOOR_TAKER_BPS == 80.0


def test_venue_true_fees_pass_exactly_at_the_floor():
    # The SAFE invariant: the live 40/80 config sits exactly at the floor and
    # must NOT trip it (strict `<`). If this reddens, the fix broke startup.
    assert not _has_floor_fatal(_cfg(40.0, 80.0))


def test_understated_25_40_fatals_in_live():
    # The exact config that passed BEFORE the correction must now FATAL.
    assert _has_floor_fatal(_cfg(25.0, 40.0))


@pytest.mark.parametrize("maker,taker", [(25.0, 40.0), (30.0, 50.0),
                                         (39.9, 79.9), (40.0, 79.0)])
def test_the_whole_gap_below_venue_truth_fatals(maker, taker):
    # Anything in [old floor, new floor) - the silent-pass band the audit
    # named - is now caught.
    assert _has_floor_fatal(_cfg(maker, taker))


def test_deleted_fee_keys_fall_below_the_floor_and_fatal():
    # A config that DELETES the fee keys falls to the guard's 25/40 fallback,
    # which now sits below the 40/80 floor -> FATAL, as the comment promises.
    cfg = {"system": {"dry_run": False}, "pretrade": {}, "order_manager": {}}
    assert _has_floor_fatal(cfg)


def test_allow_sub_floor_escape_still_works():
    # A genuine volume-tier discount can still opt out (unchanged behavior).
    assert not _has_floor_fatal(_cfg(20.0, 30.0, allow_low=True))
