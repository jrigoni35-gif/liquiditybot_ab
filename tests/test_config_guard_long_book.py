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
            # 0.5, not the task-C2-shipped 1.5: task C4's engine
            # integration discovered live that 1.5% (150bps) + the TH-013
            # zone-shift margin exceeded the default risk_firewall.
            # entry_collar_bps (100bps), so every long-book add was
            # unconditionally FW-050 price-collar rejected - config.json
            # was re-derived to 0.5% and this module's own price-collar
            # coherence FATAL (added the same task) pins it going forward.
            "add_offset_pct": 0.5,
            "zone_tol_pct": 0.15,      # matches the shipped default
            "zone_buffer_pct": 0.2,    # matches the shipped default
            "order_ttl_hours": 6.0,           # matches the shipped default
            "retry_backoff_minutes": 30.0,    # matches the shipped default
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
# C4 review knobs: order_ttl_hours (Critical #1a) / retry_backoff_minutes
# (Important #3a) - both strictly positive, or the accumulation book
# either submits an instantly-expiring bid (0/negative TTL) or never
# actually backs off a repeatedly-failing asset (0 = immediate retry,
# negative = no backoff at all).
# ---------------------------------------------------------------------

def test_order_ttl_hours_non_positive_fatal():
    assert _fatals(_cfg(order_ttl_hours=0.0))
    assert _fatals(_cfg(order_ttl_hours=-1.0))


def test_retry_backoff_minutes_non_positive_fatal():
    assert _fatals(_cfg(retry_backoff_minutes=0.0))
    assert _fatals(_cfg(retry_backoff_minutes=-1.0))


def test_ttl_and_backoff_shipped_defaults_clean():
    assert _fatals(_cfg(order_ttl_hours=6.0,
                        retry_backoff_minutes=30.0)) == []


# ---------------------------------------------------------------------
# TH-013 magnet-shift hygiene knobs (task C3:
# LongBookEngine.shift_off_magnets) - absent from the task-C2-shipped
# block, added by task C3.
# ---------------------------------------------------------------------

def test_zone_tol_pct_non_positive_fatal():
    assert _fatals(_cfg(zone_tol_pct=0.0))
    assert _fatals(_cfg(zone_tol_pct=-0.1))


def test_zone_buffer_pct_non_positive_fatal():
    assert _fatals(_cfg(zone_buffer_pct=0.0))
    assert _fatals(_cfg(zone_buffer_pct=-0.1))


def test_zone_buffer_pct_at_or_below_tol_pct_fatal():
    # buffer_pct must CLEAR tol_pct, or a shifted bid could still read
    # as within-tolerance of the same magnet it just moved away from.
    assert _fatals(_cfg(zone_tol_pct=0.15, zone_buffer_pct=0.15))
    assert _fatals(_cfg(zone_tol_pct=0.15, zone_buffer_pct=0.10))


def test_zone_buffer_pct_above_tol_pct_clean():
    assert _fatals(_cfg(zone_tol_pct=0.15, zone_buffer_pct=0.20)) == []


# ---------------------------------------------------------------------------
# price-collar coherence (task C4 discovery): add_offset_pct + the TH-013
# zone-shift margin must stay under the shared risk_firewall's
# entry_collar_bps, or every long-book add is unconditionally FW-050
# price-collar rejected (execution/risk_firewall.py's collar screen runs
# before purpose/post_only is even consulted - no maker exemption).
# ---------------------------------------------------------------------------

def _cfg_with_firewall(entry_collar_bps, **lb):
    cfg = _cfg(**lb)
    cfg["risk_firewall"] = {"entry_collar_bps": entry_collar_bps}
    return cfg


def test_shipped_default_clears_default_collar():
    # 0.5 + 0.2 + 0.15 = 0.85% = 85bps < the default 100bps collar
    assert _fatals(_cfg()) == []


def test_stale_c2_offset_would_have_been_fatal_against_default_collar():
    # the EXACT task-C2-shipped value this task's discovery replaced:
    # 1.5 + 0.2 + 0.15 = 1.85% = 185bps >= the default 100bps collar
    assert _fatals(_cfg(add_offset_pct=1.5))


def test_worst_case_deviation_at_collar_boundary_fatal():
    # exactly AT the collar (>=, not >): the firewall's own check is
    # `dev_bps > collar` (strictly greater rejects), so >= is the correct
    # FATAL boundary here - a config landing EXACTLY on the line still
    # means the very next float-rounding cycle can tip into rejection.
    # (C4 review, Minor #11: this used to also assert
    # `_fatals(...) == _fatals(...)` on the SAME call twice - a
    # self-comparing tautology that passes regardless of what _fatals
    # returns, even `[] == []`. Removed; the real assertion below stands.)
    assert _fatals(_cfg_with_firewall(85.0))


def test_worst_case_deviation_under_collar_clean():
    assert _fatals(_cfg_with_firewall(86.0)) == []


def test_tighter_shared_collar_can_fatal_the_coherent_default():
    # a live-tuned tighter firewall collar (e.g. 50bps) makes even the
    # NEW coherent 0.5% offset unsafe - the guard reads the SHARED block,
    # never a stale duplicate of the firewall's own bound.
    assert _fatals(_cfg_with_firewall(50.0))


def test_zone_hygiene_shipped_defaults_clean():
    assert _fatals(_cfg(zone_tol_pct=0.15, zone_buffer_pct=0.2)) == []


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
