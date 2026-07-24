"""tests/test_evidence_ladder.py — Compounder Phase C task C2:
EvidenceLadder state machine (risk/long_book.py). Pure, clock-free,
fully injectable: no wall-clock reads, no I/O. Scope is the ladder
ONLY — LongBookEngine (spacing/context/sizing decisions) is task C3.
"""
from risk.long_book import EvidenceLadder, LadderConfig, RungGate


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


def _closed_paper(ladder, n, net_usd=1.0):
    for _ in range(n):
        ladder.note_close(net_usd, is_live=False)


def _closed_live(ladder, wins, losses, win_usd=10.0, loss_usd=5.0):
    for _ in range(wins):
        ladder.note_close(win_usd, is_live=True)
    for _ in range(losses):
        ladder.note_close(-loss_usd, is_live=True)


# ---------------------------------------------------------------------
# config parsing
# ---------------------------------------------------------------------

def test_ladder_config_from_dict_matches_shipped_defaults():
    lc = LadderConfig.from_dict(_ladder_cfg())
    assert lc.r1 == RungGate(ceiling_frac=0.10, min_closed_paper=10)
    assert lc.r2 == RungGate(ceiling_frac=0.20, min_closed_live=15,
                             pf_floor=1.2)
    assert lc.r3 == RungGate(ceiling_frac=0.30, min_closed_live=30,
                             adverse_transitions_survived=1)
    assert lc.dd_downgrade_pct == 6.0


def test_ladder_config_from_empty_dict_has_defaults():
    lc = LadderConfig.from_dict(None)
    assert lc.r1.ceiling_frac > 0
    assert lc.dd_downgrade_pct > 0


# ---------------------------------------------------------------------
# rung 0 (no evidence)
# ---------------------------------------------------------------------

def test_starts_at_rung_zero():
    ladder = EvidenceLadder(_ladder_cfg())
    assert ladder.rung() == 0
    assert ladder.closed_paper == 0
    assert ladder.closed_live == 0


def test_rung_zero_live_ceiling_is_zero():
    ladder = EvidenceLadder(_ladder_cfg())
    assert ladder.live_ceiling_frac() == 0.0


def test_rung_zero_paper_ceiling_floors_at_r1():
    # paper behaves like rung 1 for realism even at earned rung 0
    ladder = EvidenceLadder(_ladder_cfg())
    assert ladder.paper_ceiling_frac() == 0.10


# ---------------------------------------------------------------------
# rung 1 (paper evidence)
# ---------------------------------------------------------------------

def test_r1_gate_below_floor_stays_rung_zero():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 9)
    assert ladder.rung() == 0


def test_r1_gate_at_floor_earns_rung_one():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    assert ladder.rung() == 1
    assert ladder.live_ceiling_frac() == 0.10
    assert ladder.paper_ceiling_frac() == 0.10


# ---------------------------------------------------------------------
# rung 2 (live evidence + profit factor)
# ---------------------------------------------------------------------

def test_r2_requires_r1_first():
    # closed_live/pf clear r2's own gate but closed_paper never did -
    # a true ladder can't skip r1
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_live(ladder, wins=20, losses=1)
    assert ladder.rung() == 0


def test_r2_below_min_closed_live_stays_rung_one():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=10, losses=1)   # 11 < 15
    assert ladder.rung() == 1


def test_r2_below_pf_floor_stays_rung_one():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    # 15 closes but pf < 1.2 (equal win/loss usd -> pf 1.0)
    _closed_live(ladder, wins=8, losses=7, win_usd=5.0, loss_usd=5.0)
    assert ladder.closed_live == 15
    assert ladder.pf_live < 1.2
    assert ladder.rung() == 1


def test_r2_clears_at_floor_earns_rung_two():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=10, losses=5, win_usd=10.0, loss_usd=5.0)
    # gross win 100 / gross loss 25 = pf 4.0 >= 1.2, closed_live 15 >= 15
    assert ladder.closed_live == 15
    assert ladder.pf_live >= 1.2
    assert ladder.rung() == 2
    assert ladder.live_ceiling_frac() == 0.20


def test_pf_live_is_inf_with_wins_and_no_losses():
    ladder = EvidenceLadder(_ladder_cfg())
    ladder.note_close(5.0, is_live=True)
    assert ladder.pf_live == float("inf")


def test_pf_live_is_zero_with_no_live_evidence():
    ladder = EvidenceLadder(_ladder_cfg())
    assert ladder.pf_live == 0.0


# ---------------------------------------------------------------------
# rung 3 (adverse-transition survival, engine-stored)
# ---------------------------------------------------------------------

def test_r3_requires_adverse_transition_survived():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=5, win_usd=10.0, loss_usd=5.0)
    assert ladder.closed_live == 25
    # r3 needs closed_live >= 30 too - not there yet regardless of survival
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 2


def test_r3_clears_all_gates_earns_rung_three():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    assert ladder.closed_live == 30
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 3
    assert ladder.live_ceiling_frac() == 0.30
    assert ladder.paper_ceiling_frac() == 0.30


def test_r3_without_survival_caps_at_rung_two():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    assert ladder.rung() == 2  # no note_adverse_transition_survived() call


# ---------------------------------------------------------------------
# downgrade: instant, one rung, sticky against immediate re-upgrade
# ---------------------------------------------------------------------

def test_maybe_downgrade_below_threshold_no_effect():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    assert ladder.rung() == 1
    assert ladder.maybe_downgrade(0.05) is False   # < 6% threshold
    assert ladder.rung() == 1


def test_maybe_downgrade_at_threshold_drops_one_rung():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 3
    assert ladder.maybe_downgrade(0.06) is True   # == 6% threshold
    assert ladder.rung() == 2


def test_downgrade_is_sticky_against_immediate_reupgrade():
    """The exact stickiness contract: a downgrade must not bounce back on
    the SAME evidence the very next time rung() (or note_close()) is
    called - the offset is a persistent counter, not a one-shot
    snapshot."""
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 3
    ladder.maybe_downgrade(0.06)
    assert ladder.rung() == 2
    # feed MORE evidence that would otherwise still earn rung 3 - the
    # downgrade offset persists, rung stays capped at 2
    ladder.note_close(1.0, is_live=False)
    assert ladder.rung() == 2
    # calling rung() repeatedly (no new evidence) must not drift either
    assert ladder.rung() == 2
    assert ladder.rung() == 2


def test_downgrade_floors_at_zero_not_negative():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    assert ladder.rung() == 1
    ladder.maybe_downgrade(0.06)
    ladder.maybe_downgrade(0.06)
    ladder.maybe_downgrade(0.06)
    assert ladder.rung() == 0     # floored, never negative


def test_downgrade_drops_live_ceiling_but_paper_floor_still_holds():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=10, losses=5, win_usd=10.0, loss_usd=5.0)
    assert ladder.rung() == 2
    ladder.maybe_downgrade(0.06)
    assert ladder.rung() == 1
    assert ladder.live_ceiling_frac() == 0.10
    assert ladder.paper_ceiling_frac() == 0.10   # floor unchanged


# ---------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------

def test_to_dict_from_dict_round_trip():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=10, losses=5, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    ladder.maybe_downgrade(0.06)
    d = ladder.to_dict()

    restored = EvidenceLadder(_ladder_cfg())
    restored.from_dict(d)
    assert restored.closed_paper == ladder.closed_paper
    assert restored.closed_live == ladder.closed_live
    assert restored.pf_live == ladder.pf_live
    assert restored.rung() == ladder.rung()
    assert restored.to_dict() == d


def test_from_dict_none_or_empty_is_a_noop():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 5)
    ladder.from_dict(None)
    assert ladder.closed_paper == 5
    ladder.from_dict({})
    assert ladder.closed_paper == 5


def test_from_dict_malformed_degrades_without_raising():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 5)
    ladder.from_dict({"closed_paper": "not-a-number!!"})
    assert ladder.closed_paper == 5   # kept prior state, did not raise


def test_to_dict_is_json_safe():
    import json
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 3)
    ladder.note_close(5.0, is_live=True)
    json.dumps(ladder.to_dict())   # must not raise


# ---------------------------------------------------------------------
# redemption (C2 review Fix 3): downgrades must be re-earnable on fresh
# evidence accrued strictly AFTER the downgrade - a forever-subtracted
# counter violates the spec's "re-earn slowly" (review found: with no
# redemption, 1000 fresh closes after one downgrade could never restore
# an already-earned rung 3).
# ---------------------------------------------------------------------

def test_downgrade_recovers_rung_three_on_fresh_live_evidence():
    """The review's exact probe, turned into a recovery assertion: earn
    rung 3, downgrade to 2, then feed fresh live closes >= r3's own
    min_closed_live at healthy pf - the rung must return to 3."""
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 3
    assert ladder.maybe_downgrade(0.06) is True
    assert ladder.rung() == 2
    # fresh evidence since the downgrade: 30 more live closes (== r3's
    # min_closed_live), pf stays healthy (4.0 >= r3's pf_floor)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    assert ladder.rung() == 3
    assert ladder.live_ceiling_frac() == 0.30


def test_downgrade_stays_capped_on_insufficient_fresh_evidence():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    ladder.maybe_downgrade(0.06)
    assert ladder.rung() == 2
    # only 29 fresh live closes - one short of r3.min_closed_live (30)
    _closed_live(ladder, wins=19, losses=10, win_usd=10.0, loss_usd=5.0)
    assert ladder.rung() == 2


def test_double_downgrade_requires_double_redemption():
    """Two stacked downgrades (rung 3 -> 2 -> 1) each record their own
    marker against the rung THEY dropped from; redeeming only the more
    recent (rung-2) marker restores rung 2, not rung 3 - the rung-3
    marker needs its own, larger, fresh-evidence bar cleared too."""
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 3
    assert ladder.maybe_downgrade(0.06) is True   # loses rung 3 -> 2
    assert ladder.rung() == 2
    assert ladder.maybe_downgrade(0.06) is True   # loses rung 2 -> 1
    assert ladder.rung() == 1
    # 15 fresh live closes clears r2's own gate (min_closed_live=15,
    # pf healthy) but not r3's (min_closed_live=30) - only ONE of the
    # two markers redeems
    _closed_live(ladder, wins=10, losses=5, win_usd=10.0, loss_usd=5.0)
    assert ladder.rung() == 2
    # another 15 fresh live closes now clears 30 total since the rung-3
    # marker's snapshot too - the second marker redeems
    _closed_live(ladder, wins=10, losses=5, win_usd=10.0, loss_usd=5.0)
    assert ladder.rung() == 3


def test_rung_one_loss_redeems_on_fresh_paper_closes():
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    assert ladder.rung() == 1
    assert ladder.maybe_downgrade(0.06) is True
    assert ladder.rung() == 0
    _closed_paper(ladder, 9)     # 9 < r1.min_closed_paper (10) - short
    assert ladder.rung() == 0
    ladder.note_close(1.0, is_live=False)   # 10th fresh paper close
    assert ladder.rung() == 1


def test_redemption_markers_round_trip_mid_redemption():
    """Persist/restore mid-redemption and prove the marker's SNAPSHOT
    (not just the live totals) survived the round trip: complete the
    redemption on the RESTORED instance and confirm it still needs the
    full fresh-evidence bar from the original downgrade point."""
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 3
    ladder.maybe_downgrade(0.06)
    assert ladder.rung() == 2
    # partial fresh evidence: 15 more live closes, short of r3's 30
    _closed_live(ladder, wins=10, losses=5, win_usd=10.0, loss_usd=5.0)
    assert ladder.rung() == 2

    d = ladder.to_dict()
    assert d["downgrade_markers"]   # marker persisted, still uncleared
    restored = EvidenceLadder(_ladder_cfg())
    restored.from_dict(d)
    assert restored.rung() == 2

    # complete the redemption on the RESTORED instance
    _closed_live(restored, wins=10, losses=5, win_usd=10.0, loss_usd=5.0)
    assert restored.rung() == 3


def test_rung_three_downgrade_stays_on_fresh_losses_below_r2_pf_floor():
    """Regression test for r3-redemption pf gate bug: rung 3 has no
    pf_floor, so its redemption quality bar must use r2.pf_floor. When a
    downgraded rung-3 marker meets fresh closed_live >= r3.min_closed_live
    (30) but the fresh pf is below r2.pf_floor (1.2), redemption must FAIL
    — the rung stays at 2, not bouncing back to 3 on volume alone."""
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 3
    assert ladder.maybe_downgrade(0.06) is True
    assert ladder.rung() == 2
    # feed exactly 30 fresh live closes (>= r3.min_closed_live) with pf
    # just below r2.pf_floor (1.2): 6 wins + 24 losses (fresh pf=60/120=0.5) -
    # must NOT redeem to rung 3, should stay at 2
    _closed_live(ladder, wins=6, losses=24, win_usd=10.0, loss_usd=5.0)
    assert ladder.closed_live >= 30
    fresh_pf = (ladder._gross_win_live - 200) / (ladder._gross_loss_live - 50)
    assert fresh_pf < 1.2, f"fresh pf must be < 1.2, got {fresh_pf}"
    assert ladder.rung() == 2, (
        "rung 3 downgrade must check fresh pf against r2.pf_floor (1.2), "
        "not r3.pf_floor (0.0); fresh pf < 1.2 must NOT redeem"
    )


def test_rung_three_downgrade_redeems_on_fresh_evidence_at_r2_pf_floor():
    """Positive: rung 3 downgrade to 2 redeems when fresh closes meet
    r3.min_closed_live AND fresh pf >= r2.pf_floor. This documents the
    quality bar: r3 carries no own pf_floor; its redemption bar is r2's."""
    ladder = EvidenceLadder(_ladder_cfg())
    _closed_paper(ladder, 10)
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    ladder.note_adverse_transition_survived()
    assert ladder.rung() == 3
    assert ladder.maybe_downgrade(0.06) is True
    assert ladder.rung() == 2
    # feed 30 fresh closes with pf >= 1.2 - should redeem back to 3
    _closed_live(ladder, wins=20, losses=10, win_usd=10.0, loss_usd=5.0)
    assert ladder.pf_live >= 1.2
    assert ladder.rung() == 3
