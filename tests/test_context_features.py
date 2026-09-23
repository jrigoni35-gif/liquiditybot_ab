"""
Regression for the v3 context/THALES feature block (46->53): regime_age
(hours since macro label change, saturating at 24h), funding_dist (pure
8h-cycle clock math), venue_disloc_dir (kraken vs street mid, side-
relative), and the four THALES detector scores fed as [0,1] features -
influence-ladder rung 3, operator-enabled: the model weighs footprints
from labeled outcomes; nothing here gates or vetoes. Pins the exact
units, clips, migration neutrals, and the read-only THALES accessor.
"""
from ml.features import (CONTEXT_NEUTRAL, FEATURE_NAMES,
                         FEATURE_SCHEMA_VERSION, _funding_dist, _th)
from strategies.thales import ThalesEngine


def test_schema_is_68_wide_v10():
    # deliberate re-pin: v9 adds the ofi_dir/basis_mom_dir shadow pair
    # (62->64, version 8->9); v10 adds the dp_* dark-pool SHADOW block
    # (64->68, version 9->10)
    assert len(FEATURE_NAMES) == 68
    assert FEATURE_SCHEMA_VERSION == 10
    for n in ("regime_age", "funding_dist", "venue_disloc_dir", "th_grid",
              "th_metronome", "th_clockwork", "th_stopzone"):
        assert n in FEATURE_NAMES


def test_funding_clock_math():
    assert _funding_dist(0.0) == 0.0            # settling this instant
    assert _funding_dist(4 * 3600.0) == 0.5     # halfway through the cycle
    assert _funding_dist(16 * 3600.0) == 0.0    # every 8h boundary
    assert _funding_dist(8 * 3600.0 + 1) > 0.99  # just settled
    assert _funding_dist(
        None) == 0.5  # pyright: ignore[reportArgumentType]  # malformed


def test_thales_extras_reader_is_defensive():
    assert _th({"thales": {"grid": 0.4}}, "grid") == 0.4
    assert _th({"thales": {"grid": "bad"}}, "grid") == 0.0
    assert _th({}, "grid") == 0.0
    assert _th(None, "stop_zone") == 0.0


def test_migration_neutrals_are_documented():
    from scripts.migrate_history import KNOWN_NEUTRAL
    assert CONTEXT_NEUTRAL["regime_age"] == 0.5      # unknown, not "fresh"
    assert CONTEXT_NEUTRAL["funding_dist"] == 0.5
    assert CONTEXT_NEUTRAL["th_stopzone"] == 0.0     # no footprint
    for k, v in CONTEXT_NEUTRAL.items():
        assert KNOWN_NEUTRAL.get(k) == v


def test_thales_feature_scores_zeros_when_disabled_or_cold():
    off = ThalesEngine({"enabled": False})
    zeros = {"grid": 0.0, "metronome": 0.0, "clockwork": 0.0,
             "stop_zone": 0.0, "barclose": 0.0}
    assert off.feature_scores("BTC", 1000.0) == zeros
    on = ThalesEngine({"enabled": True, "influence": "shadow"})
    assert on.feature_scores("NEVER_SEEN", 1000.0) == zeros


def test_thales_feature_scores_bounded_from_warm_state():
    eng = ThalesEngine({"enabled": True, "influence": "shadow"})
    st = eng._st("BTC")
    st.grid_score = 1.7                # EWMA glitch beyond domain
    st.metro_score = 0.6
    out = eng.feature_scores("BTC", 1000.0)
    assert out["grid"] == 1.0          # clamped to the contract range
    assert out["metronome"] == 0.6
    assert 0.0 <= out["clockwork"] <= 1.0
    assert 0.0 <= out["stop_zone"] <= 1.0
