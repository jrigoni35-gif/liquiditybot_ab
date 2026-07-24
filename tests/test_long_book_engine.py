"""tests/test_long_book_engine.py — Compounder Phase C task C3:
LongBookEngine decision core (risk/long_book.py) + the pure TH-013
round-number grid extraction (strategies/thales.py). Pure, clock-free,
fully injectable: every dependency is a plain argument, no wall-clock
reads, no I/O, no main/execution import.
"""
from dataclasses import dataclass

from core.state import Position
from data.context_engine import ContextState
from risk.long_book import (
    AddPlan,
    DenyReason,
    EngineConfig,
    EvidenceLadder,
    LongBookEngine,
    bid_is_stale,
    round_number_grid,
    shift_off_magnets,
    thesis_stop_price,
)
from strategies.thales import round_number_grid as thales_round_number_grid


# ---------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------

def _ladder_cfg(**overrides):
    cfg = {
        "r1": {"ceiling_frac": 0.10, "min_closed_paper": 10},
        "r2": {"ceiling_frac": 0.20, "min_closed_live": 15, "pf_floor": 1.2},
        "r3": {"ceiling_frac": 0.30, "min_closed_live": 30,
              "adverse_transitions_survived": 1},
        "dd_downgrade_pct": 6.0,
    }
    cfg.update(overrides)
    return cfg


def _engine_cfg(**overrides):
    cfg = {
        "add_usd_frac_of_ceiling": 0.2,
        "add_min_spacing_hours": 24.0,
        "add_offset_pct": 1.5,
        "thesis_stop_pct": 12.0,
        "zone_tol_pct": 0.15,
        "zone_buffer_pct": 0.20,
        "context": {
            "stress_max_for_add": 1.0,
            "require_known": True,
            "pause_in_event_window": True,
            "contraction_spacing_mult": 2.0,
        },
    }
    for k, v in overrides.items():
        if k == "context" and isinstance(v, dict):
            cfg["context"].update(v)
        else:
            cfg[k] = v
    return cfg


def _ctx(**overrides) -> ContextState:
    base = dict(halving_phase="expansion", stress=0.3, stress_known=True,
               in_event_window=False, calendar_known=True)
    base.update(overrides)
    return ContextState(**base)


def _kwargs(**overrides):
    """Baseline decide_add call that clears every gate cleanly, landing
    on a real AddPlan - each test overrides exactly the one input under
    test."""
    base = dict(
        now=1_000_000.0, asset="BTC", mark=60_123.0, sigma_bar_pct=1.2,
        context_state=_ctx(), ladder=EvidenceLadder(_ladder_cfg()),
        position=None, last_add_ts=None, dry_run=True, halted=False,
        entries_enabled=True, equity=100_000.0, book_exposure_usd=0.0,
        cfg=_engine_cfg(),
    )
    base.update(overrides)
    return base


def _ladder_at_rung1():
    """An EvidenceLadder that has earned rung 1 (paper_ceiling_frac ==
    0.10) - used wherever a test needs a concrete, non-zero ceiling."""
    ladder = EvidenceLadder(_ladder_cfg())
    for _ in range(10):
        ladder.note_close(1.0, is_live=False)
    assert ladder.paper_ceiling_frac() == 0.10
    return ladder


# =======================================================================
# Part 1: round_number_grid extraction pin
# =======================================================================

def test_round_number_grid_matches_hand_computed_brief_marks():
    # Hand-derived from the ORIGINAL inline _stop_zones formula (steps
    # {1, 2.5, 5, 10, 25, 50}x10^k landing within 0.3%-3% of mark,
    # k = 10^floor(log10(mark))), independent of the new function -
    # every one of these marks is itself already a "round" multiple at
    # its own order of magnitude, so all three valid steps round back to
    # the mark itself.
    assert round_number_grid(60000) == [60000.0, 60000.0, 60000.0]
    assert round_number_grid(1800) == [1800.0, 1800.0, 1800.0]
    assert round_number_grid(0.45) == [0.45, 0.45, 0.45]
    assert round_number_grid(0.003) == [0.003, 0.003, 0.003]


def test_round_number_grid_matches_hand_computed_nonround_marks():
    # Non-round marks exercise the actual rounding-to-nearest-step
    # arithmetic (not just an identity echo).
    assert round_number_grid(61234.56) == [61250.0, 61000.0, 61000.0]
    assert round_number_grid(1837.21) == [1840.0, 1825.0, 1850.0]
    assert round_number_grid(0.4567) == [0.4575, 0.455, 0.46]
    got = round_number_grid(0.0031234)
    assert got == [0.0031200000000000004, 0.003125, 0.0031000000000000003]


def test_round_number_grid_guards_non_positive_mark():
    assert round_number_grid(0) == []
    assert round_number_grid(-5) == []


def test_round_number_grid_guards_non_finite_mark():
    assert round_number_grid(float("nan")) == []
    assert round_number_grid(float("inf")) == []


def test_round_number_grid_same_function_object_thales_and_long_book():
    # risk/long_book.py imports the SAME module-level function
    # strategies/thales.py defines and calls internally from
    # _stop_zones - not a re-implementation.
    assert round_number_grid is thales_round_number_grid


# =======================================================================
# Part 2: LongBookEngine.decide_add — gate order decision table
# =======================================================================

def test_clean_inputs_produce_an_add_plan():
    plan = LongBookEngine.decide_add(**_kwargs())
    assert isinstance(plan, AddPlan)
    assert plan.usd > 0
    assert plan.price > 0


def test_halted_denies_before_anything_else():
    plan = LongBookEngine.decide_add(**_kwargs(halted=True))
    assert isinstance(plan, DenyReason)
    assert plan.kind == "halted"


def test_entries_disabled_denies():
    plan = LongBookEngine.decide_add(**_kwargs(entries_enabled=False))
    assert isinstance(plan, DenyReason)
    assert plan.kind == "entries_disabled"


def test_halted_shadows_entries_disabled_ordering():
    # Both conditions true at once: the EARLIER gate (halted) wins.
    plan = LongBookEngine.decide_add(
        **_kwargs(halted=True, entries_enabled=False))
    assert plan.kind == "halted"


def test_halted_shadows_every_later_gate():
    # halted=True stacked with spacing/event/context/ceiling violations
    # all at once - "halted" must still win (earliest gate).
    plan = LongBookEngine.decide_add(**_kwargs(
        halted=True,
        last_add_ts=1_000_000.0 - 3600.0,      # spacing violated
        context_state=_ctx(in_event_window=True, stress_known=False),
        book_exposure_usd=1_000_000.0,          # ceiling blown
    ))
    assert plan.kind == "halted"


def test_averaging_rule_is_documented_not_a_deny_kind():
    # An existing long position on this asset is a legitimate AVERAGING
    # add, not a denial - only the presence of `position` changes the
    # reason_detail wording, never the plan/deny outcome.
    pos = Position(position_id="p1", symbol="BTC/USD", direction="long",
                   entry_price=59000.0, size=0.1, original_size=0.1,
                   opened_at=None, book="long")
    plan = LongBookEngine.decide_add(**_kwargs(position=pos))
    assert isinstance(plan, AddPlan)
    assert "averaging" in plan.reason_detail


def test_averaging_rule_asserts_against_a_short_position():
    pos = Position(position_id="p1", symbol="BTC/USD", direction="short",
                   entry_price=59000.0, size=0.1, original_size=0.1,
                   opened_at=None, book="long")
    try:
        LongBookEngine.decide_add(**_kwargs(position=pos))
        raised = False
    except AssertionError:
        raised = True
    assert raised, "a SHORT position handed to the long book must assert"


def test_spacing_denies_when_add_min_spacing_hours_not_elapsed():
    plan = LongBookEngine.decide_add(**_kwargs(
        last_add_ts=1_000_000.0 - 3600.0))    # 1h ago, need 24h
    assert plan.kind == "spacing"


def test_spacing_clears_when_add_min_spacing_hours_elapsed():
    plan = LongBookEngine.decide_add(**_kwargs(
        last_add_ts=1_000_000.0 - 25 * 3600.0))
    assert isinstance(plan, AddPlan)


def test_spacing_no_prior_add_never_throttled():
    plan = LongBookEngine.decide_add(**_kwargs(last_add_ts=None))
    assert isinstance(plan, AddPlan)


def test_spacing_contraction_phase_doubles_required_hours():
    # 30h since last add: clears the plain 24h spacing but NOT the
    # contraction-doubled 48h spacing.
    last_add_ts = 1_000_000.0 - 30 * 3600.0
    plan_plain = LongBookEngine.decide_add(**_kwargs(last_add_ts=last_add_ts))
    assert isinstance(plan_plain, AddPlan)
    plan_contraction = LongBookEngine.decide_add(**_kwargs(
        last_add_ts=last_add_ts,
        context_state=_ctx(halving_phase="contraction")))
    assert plan_contraction.kind == "spacing"


def test_spacing_contraction_phase_still_clears_with_enough_time():
    plan = LongBookEngine.decide_add(**_kwargs(
        last_add_ts=1_000_000.0 - 49 * 3600.0,
        context_state=_ctx(halving_phase="contraction")))
    assert isinstance(plan, AddPlan)


def test_spacing_shadows_event_window_and_context_ordering():
    plan = LongBookEngine.decide_add(**_kwargs(
        last_add_ts=1_000_000.0 - 3600.0,
        context_state=_ctx(in_event_window=True, stress_known=False)))
    assert plan.kind == "spacing"


def test_event_window_denies_when_flag_true():
    plan = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(in_event_window=True)))
    assert plan.kind == "event_window"


def test_event_window_ignored_when_cfg_flag_false():
    plan = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(in_event_window=True),
        cfg=_engine_cfg(context={"pause_in_event_window": False})))
    assert isinstance(plan, AddPlan)


def test_event_window_shadows_context_gates_ordering():
    plan = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(in_event_window=True, stress_known=False)))
    assert plan.kind == "event_window"


# =======================================================================
# crisis cadence pause (task C5, C4-review adjudication item 4)
# =======================================================================

def test_crisis_regime_denies_when_flag_true():
    plan = LongBookEngine.decide_add(**_kwargs(macro_regime_label="crisis"))
    assert plan.kind == "crisis"


def test_crisis_regime_ignored_when_cfg_flag_false():
    plan = LongBookEngine.decide_add(**_kwargs(
        macro_regime_label="crisis",
        cfg=_engine_cfg(context={"pause_in_crisis": False})))
    assert isinstance(plan, AddPlan)


def test_non_crisis_regime_label_never_denies():
    plan = LongBookEngine.decide_add(**_kwargs(macro_regime_label="trend"))
    assert isinstance(plan, AddPlan)


def test_macro_regime_label_default_is_never_crisis():
    # every pre-C5 caller never heard of this parameter - the default ""
    # must never accidentally equal "crisis"
    plan = LongBookEngine.decide_add(**_kwargs())
    assert isinstance(plan, AddPlan)


def test_crisis_shadows_context_gates_ordering():
    plan = LongBookEngine.decide_add(**_kwargs(
        macro_regime_label="crisis",
        context_state=_ctx(stress_known=False)))
    assert plan.kind == "crisis"


def test_event_window_shadows_crisis_ordering():
    # event-window pause (gate 4) is checked BEFORE the crisis gate
    # (gate 5) - both true at once, event_window wins.
    plan = LongBookEngine.decide_add(**_kwargs(
        macro_regime_label="crisis",
        context_state=_ctx(in_event_window=True)))
    assert plan.kind == "event_window"


def test_spacing_shadows_crisis_ordering():
    plan = LongBookEngine.decide_add(**_kwargs(
        last_add_ts=1_000_000.0 - 3600.0, macro_regime_label="crisis"))
    assert plan.kind == "spacing"


def test_halted_shadows_crisis_ordering():
    plan = LongBookEngine.decide_add(**_kwargs(
        halted=True, macro_regime_label="crisis"))
    assert plan.kind == "halted"


def test_engine_config_pause_in_crisis_default_true():
    assert EngineConfig.from_dict({}).pause_in_crisis is True


def test_engine_config_pause_in_crisis_reads_from_cfg():
    ecfg = EngineConfig.from_dict({"context": {"pause_in_crisis": False}})
    assert ecfg.pause_in_crisis is False


def test_context_unknown_when_require_known_and_stress_unknown():
    plan = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(stress_known=False)))
    assert plan.kind == "context_unknown"


def test_context_unknown_bypassed_when_require_known_false():
    plan = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(stress_known=False, stress=None),
        cfg=_engine_cfg(context={"require_known": False})))
    assert isinstance(plan, AddPlan)


def test_context_misaligned_when_stress_over_max():
    plan = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(stress=2.5, stress_known=True)))
    assert plan.kind == "context_misaligned"


def test_context_aligned_when_stress_at_or_under_max():
    plan = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(stress=1.0, stress_known=True)))
    assert isinstance(plan, AddPlan)


def test_context_unknown_and_misaligned_are_distinct_kinds():
    unknown = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(stress_known=False)))
    misaligned = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(stress=5.0, stress_known=True)))
    assert unknown.kind == "context_unknown"
    assert misaligned.kind == "context_misaligned"
    assert unknown.kind != misaligned.kind


def test_context_shadows_ceiling_ordering():
    plan = LongBookEngine.decide_add(**_kwargs(
        context_state=_ctx(stress_known=False),
        book_exposure_usd=1_000_000.0))
    assert plan.kind == "context_unknown"


def test_ceiling_denies_with_zero_headroom():
    ladder = _ladder_at_rung1()
    # ceiling_usd = 0.10 * 100_000 = 10_000; exposure already there
    plan = LongBookEngine.decide_add(**_kwargs(
        ladder=ladder, book_exposure_usd=10_000.0))
    assert plan.kind == "ceiling"


def test_ceiling_denies_with_negative_headroom():
    ladder = _ladder_at_rung1()
    plan = LongBookEngine.decide_add(**_kwargs(
        ladder=ladder, book_exposure_usd=15_000.0))
    assert plan.kind == "ceiling"


def test_ceiling_headroom_arithmetic_uncapped():
    ladder = _ladder_at_rung1()
    # ceiling_usd = 10_000; exposure 2_000 -> headroom 8_000;
    # add_usd_frac_of_ceiling=0.2 -> raw 2_000 < headroom -> usd == 2_000
    plan = LongBookEngine.decide_add(**_kwargs(
        ladder=ladder, book_exposure_usd=2_000.0))
    assert isinstance(plan, AddPlan)
    assert plan.usd == 2_000.0


def test_ceiling_headroom_arithmetic_capped_by_remaining_headroom():
    ladder = _ladder_at_rung1()
    # ceiling_usd = 10_000; exposure 9_800 -> headroom 200;
    # raw add = 0.2 * 10_000 = 2_000 > 200 -> usd capped at 200
    plan = LongBookEngine.decide_add(**_kwargs(
        ladder=ladder, book_exposure_usd=9_800.0))
    assert isinstance(plan, AddPlan)
    assert plan.usd == 200.0


def test_ceiling_uses_live_ceiling_when_not_dry_run():
    # rung 1 earned via PAPER evidence only -> live_ceiling_frac() is
    # still 0.10 (r1 requires no live evidence) - but a book with ZERO
    # earned rung has live_ceiling_frac()==0.0 while paper floors at r1.
    fresh = EvidenceLadder(_ladder_cfg())
    assert fresh.live_ceiling_frac() == 0.0
    assert fresh.paper_ceiling_frac() == 0.10
    plan_live = LongBookEngine.decide_add(**_kwargs(
        ladder=fresh, dry_run=False, book_exposure_usd=0.0))
    assert plan_live.kind == "ceiling"      # live ceiling 0.0 -> no headroom
    plan_paper = LongBookEngine.decide_add(**_kwargs(
        ladder=fresh, dry_run=True, book_exposure_usd=0.0))
    assert isinstance(plan_paper, AddPlan)  # paper floors at r1's ceiling


# ---------------------------------------------------------------------
# bid pricing + magnet hygiene
# ---------------------------------------------------------------------

def test_bid_price_is_mark_times_one_minus_offset_when_no_magnet_nearby():
    ladder = _ladder_at_rung1()
    # mark chosen far from any round-number magnet at its own scale.
    plan = LongBookEngine.decide_add(**_kwargs(
        ladder=ladder, mark=61234.56, book_exposure_usd=0.0))
    assert isinstance(plan, AddPlan)
    expected = 61234.56 * (1.0 - 1.5 / 100.0)
    # unshifted (61234.56's offset bid at 60_316.04... isn't within
    # 0.15% of any of round_number_grid(61234.56)'s magnets)
    assert abs(plan.price - expected) < 1e-6
    assert "shifted" not in plan.reason_detail


# =======================================================================
# shift_off_magnets — direction + idempotency
# =======================================================================

def test_shift_off_magnets_moves_bid_just_above_a_magnet_below_it():
    level = 60000.0
    price = level * 1.0005          # 0.05% above the magnet, within 0.15% tol
    out, shifted = shift_off_magnets(price, [level], tol_pct=0.15,
                                     buffer_pct=0.20)
    assert shifted is True
    assert out < level
    assert abs(out - level * (1.0 - 0.20 / 100.0)) < 1e-9


def test_shift_off_magnets_leaves_far_bid_unshifted():
    level = 60000.0
    price = level * 0.95            # 5% away - far outside tol
    out, shifted = shift_off_magnets(price, [level], tol_pct=0.15,
                                     buffer_pct=0.20)
    assert shifted is False
    assert out == price


def test_shift_off_magnets_never_moves_upward():
    level = 60000.0
    # price already below the magnet by MORE than buffer_pct but still
    # within tol_pct (tol > buffer scenario) - target would land ABOVE
    # price; must be discarded, price stays put (no upward move).
    price = level * (1.0 - 0.001)    # 0.1% below the magnet
    out, shifted = shift_off_magnets(price, [level], tol_pct=0.15,
                                     buffer_pct=0.05)
    assert out <= price
    if shifted:
        assert out < price


def test_shift_off_magnets_picks_deepest_target_across_multiple_levels():
    price = 60050.0
    grid = [60000.0, 60100.0]       # price within tol of both
    out, shifted = shift_off_magnets(price, grid, tol_pct=0.5,
                                     buffer_pct=0.2)
    assert shifted is True
    # deepest = lower magnet's shifted target
    assert out == 60000.0 * (1.0 - 0.2 / 100.0)


def test_shift_off_magnets_empty_grid_never_shifts():
    out, shifted = shift_off_magnets(59000.0, [], tol_pct=0.15,
                                     buffer_pct=0.2)
    assert shifted is False
    assert out == 59000.0


def test_shift_off_magnets_guards_non_positive_price():
    out, shifted = shift_off_magnets(0.0, [60000.0], tol_pct=0.15,
                                     buffer_pct=0.2)
    assert shifted is False
    assert out == 0.0


def test_add_plan_bid_shifted_off_a_real_magnet_end_to_end():
    ladder = _ladder_at_rung1()
    # mark=16738.0 found by direct search over round_number_grid(mark):
    # the 1.5%-offset bid (16486.93) lands within 0.15% of the 16500.0
    # magnet in round_number_grid(16738.0) == [16700.0, 16750.0, 16500.0]
    # (16700/16750 are NOT within tol - only 16500 is).
    mark = 16738.0
    priced = mark * (1.0 - 1.5 / 100.0)
    assert round_number_grid(mark) == [16700.0, 16750.0, 16500.0]
    assert abs(priced - 16500.0) / priced < 0.0015
    plan = LongBookEngine.decide_add(**_kwargs(
        ladder=ladder, mark=mark, book_exposure_usd=0.0))
    assert isinstance(plan, AddPlan)
    assert plan.price < priced
    assert abs(plan.price - 16500.0 * (1.0 - 0.20 / 100.0)) < 1e-9
    assert "shifted" in plan.reason_detail


# =======================================================================
# long-only invariant
# =======================================================================

def test_decide_add_signature_has_no_direction_parameter():
    import inspect
    sig = inspect.signature(LongBookEngine.decide_add)
    assert "direction" not in sig.parameters
    assert "side" not in sig.parameters


def test_add_plan_has_no_direction_field():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(AddPlan)}
    assert "direction" not in fields
    assert "side" not in fields


def test_no_code_path_yields_a_sell_across_the_full_decision_table():
    # Exhaustively vary every gate input across a representative sweep;
    # every non-deny result must be an AddPlan (a buy plan) - there is
    # no field/branch anywhere that could express a sell.
    ladder = _ladder_at_rung1()
    for halted in (True, False):
        for entries_enabled in (True, False):
            for phase in ("expansion", "contraction"):
                for in_ew in (True, False):
                    for stress_known in (True, False):
                        for stress in (0.1, 5.0):
                            plan = LongBookEngine.decide_add(**_kwargs(
                                ladder=ladder, halted=halted,
                                entries_enabled=entries_enabled,
                                context_state=_ctx(
                                    halving_phase=phase,
                                    in_event_window=in_ew,
                                    stress_known=stress_known,
                                    stress=stress),
                                book_exposure_usd=0.0))
                            assert isinstance(plan, (AddPlan, DenyReason))
                            if isinstance(plan, AddPlan):
                                assert plan.usd > 0 or plan.usd == 0.0


# =======================================================================
# thesis_stop_price helper
# =======================================================================

def test_thesis_stop_price_is_avg_entry_times_one_minus_pct():
    assert thesis_stop_price(50000.0, 12.0) == 50000.0 * 0.88


def test_thesis_stop_price_zero_pct_equals_avg_entry():
    assert thesis_stop_price(50000.0, 0.0) == 50000.0


def test_thesis_stop_price_pure_no_state():
    # calling repeatedly with the same inputs is always the same output
    assert thesis_stop_price(123.45, 12.0) == thesis_stop_price(123.45, 12.0)


@dataclass
class _StubEngineNoDecideExits:
    """Confirms C3 deliberately ships no `decide_exits` re-implementation
    of tier logic - only the pure `thesis_stop_price` primitive."""
    pass


def test_long_book_module_ships_no_decide_exits_reimplementation():
    import risk.long_book as lb
    assert not hasattr(lb, "decide_exits"), (
        "C3 ships only pure exit helpers (thesis_stop_price); the tier "
        "engine delegation itself is task C4's decide_exits, engine-side")


# =======================================================================
# EngineConfig defaults (C4 review, Critical #1a / Minor #9)
# =======================================================================

def test_engine_config_default_add_offset_pct_is_0_5():
    # Minor #9: the code default had drifted stale at 1.5 while the
    # shipped config.json (and every other reference) has used 0.5 since
    # task C4's own price-collar discovery.
    assert EngineConfig.from_dict({}).add_offset_pct == 0.5


def test_engine_config_default_order_ttl_hours_is_6():
    assert EngineConfig.from_dict({}).order_ttl_hours == 6.0


def test_engine_config_default_retry_backoff_minutes_is_30():
    assert EngineConfig.from_dict({}).retry_backoff_minutes == 30.0


def test_engine_config_order_ttl_and_backoff_read_from_cfg():
    ecfg = EngineConfig.from_dict({"order_ttl_hours": 2.0,
                                  "retry_backoff_minutes": 15.0})
    assert ecfg.order_ttl_hours == 2.0
    assert ecfg.retry_backoff_minutes == 15.0


# =======================================================================
# bid_is_stale — cancel-and-replace staleness predicate (C4 review,
# Critical #1b)
# =======================================================================

def test_bid_is_stale_fresh_bid_within_band_is_not_stale():
    # add_offset_pct=0.5, zone_buffer_pct=0.20 -> "fresh" band is 0.70%.
    # A bid resting exactly at the intended 0.5% discount is well inside.
    mark = 60_000.0
    resting_price = mark * (1.0 - 0.005)
    assert bid_is_stale(mark, resting_price, 0.5, 0.20) is False


def test_bid_is_stale_mark_ran_up_past_the_band_is_stale():
    # mark moved up 2% since the bid was placed at the old mark's 0.5%
    # discount - drift now far exceeds the 0.70% fresh band.
    old_mark = 60_000.0
    resting_price = old_mark * (1.0 - 0.005)
    new_mark = old_mark * 1.02
    assert bid_is_stale(new_mark, resting_price, 0.5, 0.20) is True


def test_bid_is_stale_mark_fell_past_the_bid_is_stale():
    # mark fell enough that the resting bid now sits AT/ABOVE the new
    # mark (would cross / collar-reject on resubmit) - stale in the
    # other direction.
    old_mark = 60_000.0
    resting_price = old_mark * (1.0 - 0.005)
    new_mark = resting_price * 0.99   # mark now below the resting bid
    assert bid_is_stale(new_mark, resting_price, 0.5, 0.20) is True


def test_bid_is_stale_boundary_is_not_stale_strictly_greater_only():
    # drift EXACTLY at the band edge: the predicate is strictly-greater,
    # matching risk_firewall's own collar convention (dev_bps > collar).
    # Offsets chosen (10.0/15.0, band=25%) so the forward/inverse float
    # arithmetic lands EXACTLY on the boundary (powers-of-two fractions),
    # not a near-miss from float rounding.
    mark = 100.0
    resting_price = 75.0     # mark * (1 - 25/100), exact in binary float
    assert bid_is_stale(mark, resting_price, 10.0, 15.0) is False


def test_bid_is_stale_guards_non_positive_or_non_finite_mark():
    assert bid_is_stale(0.0, 100.0, 0.5, 0.20) is False
    assert bid_is_stale(-5.0, 100.0, 0.5, 0.20) is False
    assert bid_is_stale(float("nan"), 100.0, 0.5, 0.20) is False
    assert bid_is_stale(float("inf"), 100.0, 0.5, 0.20) is False


def test_bid_is_stale_guards_non_positive_or_non_finite_resting_price():
    assert bid_is_stale(100.0, 0.0, 0.5, 0.20) is False
    assert bid_is_stale(100.0, -5.0, 0.5, 0.20) is False
    assert bid_is_stale(100.0, float("nan"), 0.5, 0.20) is False


def test_bid_is_stale_zone_tol_widens_the_fresh_band_for_a_magnet_shift():
    # Phase-C whole-phase review, Important #1: a magnet-shifted bid
    # (shift_off_magnets, TH-013) can legitimately rest up to
    # add_offset_pct + zone_tol_pct + zone_buffer_pct away from mark -
    # config_guard's own collar-coherence formula (core/config_guard.py's
    # worst_dev_bps), NOT just add_offset_pct + zone_buffer_pct. Drift
    # here (0.75%) sits PAST the old (offset+buffer=0.70%) band but
    # WITHIN the full (offset+buffer+tol=0.85%) band - immediately after
    # placement this must NOT be stale.
    mark = 100_000.0
    resting_price = mark * (1.0 - 0.0075)
    assert bid_is_stale(mark, resting_price, 0.5, 0.20,
                        zone_tol_pct=0.15) is False


def test_bid_is_stale_genuine_drift_beyond_the_full_band_is_stale():
    # drift beyond the FULL band (offset+buffer+tol=0.85%) is still
    # genuinely stale.
    mark = 100_000.0
    resting_price = mark * (1.0 - 0.01)
    assert bid_is_stale(mark, resting_price, 0.5, 0.20,
                        zone_tol_pct=0.15) is True


def test_bid_is_stale_zone_tol_defaults_to_zero_preserving_old_callers():
    # a caller that omits zone_tol_pct (every pre-existing call site/test
    # above) keeps the OLD (offset+buffer)-only band, byte-identical.
    mark = 60_000.0
    resting_price = mark * (1.0 - 0.0075)   # past the 0.70% offset+buffer band
    assert bid_is_stale(mark, resting_price, 0.5, 0.20) is True
