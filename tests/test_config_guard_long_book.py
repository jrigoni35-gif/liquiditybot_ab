"""tests/test_config_guard_long_book.py — Compounder Phase C task C2
`long_book` block coherence: the guard refuses configs where the
evidence ladder or the accumulation config would be structurally
broken or exit-incoherent (task-C2 brief, mirrors
test_config_guard_context.py's structure)."""
from core.config_guard import validate


def _cfg(**lb):
    base = {
        "exchanges": {"kraken": {"trading_pairs": [
            "ETH/USD", "BTC/USD", "SUI/USD", "ARB/USD", "MINA/USD",
            "FLOW/USD"]}},
        "risk_protocols": {"heat": {"max_portfolio_heat_frac": 0.35}},
        "long_book": {
            "enabled": True,
            "assets": ["BTC", "ETH"],
            "add_usd_frac_of_ceiling": 0.2,
            "add_min_spacing_hours": 24.0,
            "add_offset_pct": 1.5,
            "thesis_stop_pct": 12.0,   # matches the shipped default
            "ladder": {
                "r1": {"ceiling_frac": 0.10, "min_closed_paper": 10},
                "r2": {"ceiling_frac": 0.20, "min_closed_live": 15,
                      "pf_floor": 1.2},
                "r3": {"ceiling_frac": 0.30, "min_closed_live": 30,
                      "adverse_transitions_survived": 1},
                "dd_downgrade_pct": 6.0,
            },
            "profit_taking": {
                "tier_1": {"trigger_pct_gain": 8.0, "close_pct_of_position": 20},
                "tier_2": {"trigger_pct_gain": 15.0, "close_pct_of_position": 20},
                "tier_3": {"trigger_pct_gain": 25.0, "close_pct_of_position": 25},
                "tier_4": {"trigger_pct_gain": 40.0, "close_pct_of_position": 25},
                "time_stop": {"enabled": False},
            },
        },
    }
    base["long_book"].update(lb)
    return base


def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL" and "long_book" in m]


def test_default_block_clean():
    assert _fatals(_cfg()) == []


def test_absent_block_clean():
    # module defaults apply; the guard only judges a present block
    assert _fatals({}) == []


# ---------------------------------------------------------------------
# assets
# ---------------------------------------------------------------------

def test_empty_assets_fatal():
    assert _fatals(_cfg(assets=[]))


def test_non_string_asset_fatal():
    assert _fatals(_cfg(assets=["BTC", 123]))


def test_asset_outside_kraken_universe_fatal():
    assert _fatals(_cfg(assets=["BTC", "DOGE"]))


def test_asset_inside_kraken_universe_clean():
    assert _fatals(_cfg(assets=["SUI", "ARB"])) == []


# ---------------------------------------------------------------------
# spacing / offset / frac knobs
# ---------------------------------------------------------------------

def test_add_usd_frac_of_ceiling_non_positive_fatal():
    assert _fatals(_cfg(add_usd_frac_of_ceiling=0.0))
    assert _fatals(_cfg(add_usd_frac_of_ceiling=-0.1))


def test_add_min_spacing_hours_non_positive_fatal():
    assert _fatals(_cfg(add_min_spacing_hours=0.0))


def test_add_offset_pct_non_positive_fatal():
    assert _fatals(_cfg(add_offset_pct=0.0))


# ---------------------------------------------------------------------
# ladder ceilings
# ---------------------------------------------------------------------

def test_ladder_ceilings_non_monotonic_fatal():
    ladder = {"r1": {"ceiling_frac": 0.20, "min_closed_paper": 10},
             "r2": {"ceiling_frac": 0.10, "min_closed_live": 15,
                   "pf_floor": 1.2},
             "r3": {"ceiling_frac": 0.30, "min_closed_live": 30,
                   "adverse_transitions_survived": 1},
             "dd_downgrade_pct": 6.0}
    assert _fatals(_cfg(ladder=ladder))


def test_ladder_ceilings_equal_fatal():
    ladder = {"r1": {"ceiling_frac": 0.20, "min_closed_paper": 10},
             "r2": {"ceiling_frac": 0.20, "min_closed_live": 15,
                   "pf_floor": 1.2},
             "r3": {"ceiling_frac": 0.30, "min_closed_live": 30,
                   "adverse_transitions_survived": 1},
             "dd_downgrade_pct": 6.0}
    assert _fatals(_cfg(ladder=ladder))


def test_ladder_ceiling_above_heat_cap_fatal():
    cfg = _cfg()
    cfg["risk_protocols"]["heat"]["max_portfolio_heat_frac"] = 0.25
    # r3 ceiling 0.30 > heat cap 0.25
    assert _fatals(cfg)


def test_ladder_ceiling_at_heat_cap_clean():
    cfg = _cfg()
    cfg["risk_protocols"]["heat"]["max_portfolio_heat_frac"] = 0.30
    assert _fatals(cfg) == []


def test_dd_downgrade_pct_non_positive_fatal():
    ladder = _cfg()["long_book"]["ladder"]
    ladder = dict(ladder, dd_downgrade_pct=0.0)
    assert _fatals(_cfg(ladder=ladder))
    ladder = dict(ladder, dd_downgrade_pct=-1.0)
    assert _fatals(_cfg(ladder=ladder))


# ---------------------------------------------------------------------
# thesis_stop_pct: plain bounds check, (0, 100]
#
# C2 REVIEW CORRECTION (see the matching comment in
# core/config_guard.py._long_book_checks and task-C2-report.md's
# correction note for the full writeup): the prior implementation here
# compared thesis_stop_pct against profit_taking.tier_4.trigger_pct_gain
# (a downside stop magnitude vs an unrelated upside tier-trigger
# magnitude) and FATAL'd on a coherent deep-stop config (45, well inside
# a sane spot-long stop, but >= the shipped tier_4 trigger of 40). That
# cross-block check is deleted entirely, replaced with a plain bounds
# check on thesis_stop_pct alone: a downside pct-of-entry-price cannot
# be non-positive (never/always trips) or exceed 100% (a spot long
# cannot lose more than its entry value).
# ---------------------------------------------------------------------

def test_thesis_stop_zero_fatal():
    assert _fatals(_cfg(thesis_stop_pct=0.0))


def test_thesis_stop_negative_fatal():
    assert _fatals(_cfg(thesis_stop_pct=-5.0))


def test_thesis_stop_above_100_fatal():
    assert _fatals(_cfg(thesis_stop_pct=150.0))


def test_thesis_stop_deep_stop_above_tier4_trigger_clean():
    # the exact case the old cross-check false-FATAL'd: a deep-but-sane
    # thesis stop that happens to sit above tier_4's 40.0 trigger - this
    # is the point of the fix, not an edge case to special-case around
    assert _fatals(_cfg(thesis_stop_pct=45.0)) == []


def test_thesis_stop_shipped_default_clean():
    assert _fatals(_cfg(thesis_stop_pct=12.0)) == []   # shipped default


# ---------------------------------------------------------------------
# time_stop design pin
# ---------------------------------------------------------------------

def test_time_stop_enabled_fatal():
    pt = _cfg()["long_book"]["profit_taking"]
    pt = dict(pt, time_stop={"enabled": True})
    assert _fatals(_cfg(profit_taking=pt))


def test_time_stop_disabled_clean():
    assert _fatals(_cfg()) == []
