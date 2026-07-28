"""ML-073 learning-phase label realization: the fix for the SD-002 starvation
loop. Dry-run exploration paper trades must CLOSE to become live labels, but
in a quiet book they hit no tier/stop and sit for days, filling the book so no
new teaching entry can fire and the model stays cold. A position held past the
model's label horizon has already resolved its triple-barrier outcome, so it
is closed to bank the live label and free a teach slot.

Pure decision logic under test: pick_label_mature_unwind — the stalest
non-hedge position past mature_h, one per call, auto-off at graduation.
"""
import types
from datetime import datetime, timezone

from main import (effective_realize_spans, exit_in_flight,
                  pick_label_mature_unwind)

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc).timestamp()


def _pos(age_h, hedge=False, pid="p"):
    opened = datetime.fromtimestamp(NOW - age_h * 3600.0, tz=timezone.utc)
    return types.SimpleNamespace(
        position_id=pid, symbol="ETH/USD", is_hedge=hedge, opened_at=opened)


def test_realizes_the_stalest_position_past_the_horizon():
    positions = [_pos(2.0, pid="fresh"), _pos(9.5, pid="stale"),
                 _pos(8.5, pid="mid")]
    pick = pick_label_mature_unwind(positions, rows=35, until_live_rows=500,
                                    now=NOW, mature_h=8.0)
    assert pick is not None and pick.position_id == "stale"


def test_none_when_no_position_is_mature():
    positions = [_pos(2.0), _pos(5.0), _pos(7.9)]
    assert pick_label_mature_unwind(positions, 35, 500, NOW, 8.0) is None


def test_none_once_exploration_has_graduated():
    positions = [_pos(50.0, pid="ancient")]
    # 600 live rows >= until_live_rows 500 -> tier engine owns exits now
    assert pick_label_mature_unwind(positions, 600, 500, NOW, 8.0) is None


def test_skips_hedges():
    positions = [_pos(20.0, hedge=True, pid="hedge"),
                 _pos(9.0, pid="real")]
    pick = pick_label_mature_unwind(positions, 35, 500, NOW, 8.0)
    assert pick is not None and pick.position_id == "real"


def test_none_on_empty_book_or_nonpositive_horizon():
    assert pick_label_mature_unwind([], 35, 500, NOW, 8.0) is None
    assert pick_label_mature_unwind([_pos(50.0)], 35, 500, NOW, 0.0) is None


def test_fastpath_fires_only_when_the_book_is_full():
    """VALUE-OF-INFORMATION fast-forward: the realize horizon only throttles
    learning when the book is FULL — a free slot admits a new teach trade
    regardless, so the full window costs nothing and keeps the richer label.
    Occupancy = filled positions INCL. hedges + resting entries (entry-gate
    parity): 4 teach longs + 1 hedge short is occupancy 5, entries blocked,
    fastpath armed."""
    # occupancy at cap (e.g. 4 teach + 1 hedge) -> the shorter fastpath
    assert effective_realize_spans(1.0, 0.5, 5, 5) == 0.5
    # over-full (hedge unwind race etc.) still fires
    assert effective_realize_spans(1.0, 0.5, 6, 5) == 0.5
    # a single free slot -> full window
    assert effective_realize_spans(1.0, 0.5, 4, 5) == 1.0
    assert effective_realize_spans(1.0, 0.5, 0, 5) == 1.0


def test_fastpath_occupancy_mirrors_the_entry_gate():
    """Source contract: the engine must arm the fastpath on the SAME
    fullness the entry gate blocks on — all open positions (hedges too)
    plus resting entry orders — never the non-hedge subset (which left the
    fastpath dormant exactly when a hedge blocked the last teach slot)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    assert "len(_open) + _reserved" in src
    assert "_non_hedge" not in src               # the old subset count is gone
    # sibling finding, same commit: the exit ladder de-escalates only on a
    # COMPLETED exit order (a dribble partial must not reset the counter)
    assert ("if order.remaining <= EPS:\n"
            "                self._exit_attempts.pop") in src


def test_fastpath_zero_disables_and_never_extends():
    # 0 (engine default) disables: full book still uses the full spans
    assert effective_realize_spans(1.0, 0.0, 5, 5) == 1.0
    assert effective_realize_spans(1.0, -1.0, 5, 5) == 1.0
    # a fastpath ABOVE the full horizon can only ever shorten, never extend
    assert effective_realize_spans(1.0, 2.0, 5, 5) == 1.0


def test_fastpath_degenerate_slot_cap_is_safe():
    # slot_cap <= 0 clamps to 1 so any open position counts as "full"
    assert effective_realize_spans(1.0, 0.5, 1, 0) == 0.5
    assert effective_realize_spans(1.0, 0.5, 0, 0) == 1.0


def test_drought_arms_the_fastpath_with_free_slots():
    """SIGNAL-DROUGHT extension: the free-slot premise ('a new teach trade
    can open regardless') fails when no entry has been admitted for hours —
    then holding to the full window buys nothing and costs label latency."""
    # book 4/5 (free slot) but 1.5h since the last admitted entry > 1.0h
    assert effective_realize_spans(1.0, 0.25, 4, 5,
                                   drought_h=1.5, drought_after_h=1.0) == 0.25
    # entries flowing (drought clock below threshold) -> full window
    assert effective_realize_spans(1.0, 0.25, 4, 5,
                                   drought_h=0.4, drought_after_h=1.0) == 1.0
    # extension disabled (default) -> free slots always keep the full window
    assert effective_realize_spans(1.0, 0.25, 4, 5,
                                   drought_h=9.9, drought_after_h=0.0) == 1.0
    # full book arms regardless of the drought clock (original rule intact)
    assert effective_realize_spans(1.0, 0.25, 5, 5,
                                   drought_h=0.0, drought_after_h=1.0) == 0.25
    # fastpath off disables everything, drought included
    assert effective_realize_spans(1.0, 0.0, 4, 5,
                                   drought_h=9.9, drought_after_h=1.0) == 1.0


def test_learning_unwinds_gate_on_trusted_marks():
    """Source contract: BOTH learning unwinds (ML-071/ML-073) must consult
    the stop-eval + mark-freshness gates before closing — realizing against
    a stale cached book banks a phantom-price PnL as GROUND TRUTH, and the
    watchdog is blocking entries on the same staleness so the freed slot is
    unusable anyway. Same gate the derisk path honors."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    # derisk (1) + ML-071 (2) + ML-073 (3) all consult the freshness gate
    assert src.count("self._mark_fresh(pos.symbol, now)") >= 3
    # and both unwind exits run on injected engine time, not wall clock
    assert 'self._submit_exit(pos, 100.0, "unteachable unwind (ML-071)",' in src
    assert "self._submit_exit(pos, 100.0, reason, now=now)" in src


def _order(purpose, pid, post_only=False):
    return types.SimpleNamespace(purpose=purpose, position_id=pid,
                                 post_only=post_only)


def test_exit_in_flight_detects_only_this_positions_exit():
    orders = [_order("entry", "p1"), _order("exit", "p2"),
              _order("exit", "p3", post_only=True)]
    assert not exit_in_flight(orders, "p1")     # entry order is not an exit
    assert exit_in_flight(orders, "p2")         # marketable exit working
    assert exit_in_flight(orders, "p3")         # resting maker profit-take:
    assert not exit_in_flight([], "p2")         # it will bank the same label —
    # never preempt it for a non-urgent learning-phase close


def test_learning_unwinds_skip_positions_already_exiting():
    """Source contract: BOTH slow-tick unwinds (ML-071 unteachable, ML-073
    realize) must consult exit_in_flight before logging/submitting, so a slow
    fill cannot re-log the disposition each tick or cancel a resting maker."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    assert src.count("exit_in_flight(self.orders.open_orders()") == 2


def test_horizon_derives_from_label_window_default_8h():
    # default: realize_after_label_spans 1.0 * label_max_bars 96 * 300s / 3600
    from ml.walkforward import BAR_SECONDS
    mature_h = 1.0 * 96 * BAR_SECONDS / 3600.0
    assert abs(mature_h - 8.0) < 1e-9
    # a 9h position is past it, a 7h one is not
    assert pick_label_mature_unwind([_pos(9.0)], 35, 500, NOW, mature_h)
    assert pick_label_mature_unwind([_pos(7.0)], 35, 500, NOW, mature_h) is None


# ------------------------------------------------- bracket-aware ML-073
# Geometry-alignment follow-up (2026-07-28, live evidence SUI efc8f3e2):
# the VOI fastpath (spans 0.25 = 2h of an 8h label window) realized an
# ARMED bracket probe mid-bet with barrier="realized" — whose exit_sim
# label era the now-active era-exclusion filter drops from training. The
# teach slot was recycled for a label the trainer then threw away. A
# bracket position's bet runs to its OWN vertical barrier: before
# bracket_deadline_ts ML-073 must never touch it; past the deadline the
# close IS tb_time (the caller threads that reason so the row trains).

def _bpos(age_h, deadline_in_h, pid="b", pt=0.03):
    p = _pos(age_h, pid=pid)
    p.bracket_pt_frac = pt
    p.bracket_deadline_ts = NOW + deadline_in_h * 3600.0
    return p


def test_bracket_position_immune_to_fastpath_before_its_deadline():
    # 2.1h-old bracket probe, fastpath mature_h 2.0, deadline 5.9h out:
    # the labeled bet is unresolved - never realized early
    assert pick_label_mature_unwind([_bpos(2.1, deadline_in_h=5.9)],
                                    35, 500, NOW, 2.0) is None


def test_bracket_position_realizable_once_its_deadline_passed():
    # deadline crossed: the vertical barrier has fired; ML-073 may bank it
    pick = pick_label_mature_unwind([_bpos(8.2, deadline_in_h=-0.1)],
                                    35, 500, NOW, 2.0)
    assert pick is not None and pick.position_id == "b"


def test_legacy_positions_keep_the_exact_fastpath_clock():
    # no bracket fields at all (pre-T5 double) -> byte-identical legacy
    pick = pick_label_mature_unwind([_pos(2.1, pid="legacy")],
                                    35, 500, NOW, 2.0)
    assert pick is not None and pick.position_id == "legacy"


def test_degenerate_bracket_without_deadline_falls_back_to_legacy():
    # pt_frac armed but deadline 0 (defensive): the fast tb_time leg can
    # never fire on it, so the legacy clock must keep owning the unwind
    # or the position is immortal
    p = _pos(2.1, pid="degen")
    p.bracket_pt_frac = 0.03
    p.bracket_deadline_ts = 0.0
    pick = pick_label_mature_unwind([p], 35, 500, NOW, 2.0)
    assert pick is not None and pick.position_id == "degen"


def test_stalest_selection_respects_bracket_immunity():
    # the STALEST position is a bracket probe mid-bet; the younger legacy
    # one is the only realizable pick - staleness never overrides immunity
    positions = [_bpos(6.0, deadline_in_h=2.0, pid="mid-bet"),
                 _pos(3.0, pid="legacy")]
    pick = pick_label_mature_unwind(positions, 35, 500, NOW, 2.0)
    assert pick is not None and pick.position_id == "legacy"


def test_expired_bracket_beats_younger_legacy_on_staleness():
    # both realizable -> the established stalest-first rule still decides
    positions = [_bpos(9.0, deadline_in_h=-0.5, pid="expired-bracket"),
                 _pos(3.0, pid="legacy")]
    pick = pick_label_mature_unwind(positions, 35, 500, NOW, 2.0)
    assert pick is not None and pick.position_id == "expired-bracket"


def test_long_book_positions_are_never_teach_inventory():
    """Live evidence (ETH 15403f29, 2026-07-28 18:32Z): ML-073's fastpath
    realized a LONG-BOOK thesis position (12% structural stop, built to run
    for days) at exactly 2.0h, banking a training-dead exit_sim label and
    defeating the compounder lane - the long book shipped after ML-073 and
    was never exempted. A book=="long" position is not a teach trade: the
    recycler must never pick it, at any age."""
    p = _pos(50.0, pid="thesis")
    p.book = "long"
    assert pick_label_mature_unwind([p], 35, 500, NOW, 2.0) is None
    # and a teachable 5m sibling is still picked right past it
    positions = [p, _pos(3.0, pid="teach")]
    pick = pick_label_mature_unwind(positions, 35, 500, NOW, 2.0)
    assert pick is not None and pick.position_id == "teach"


def test_ml071_unteachable_unwind_also_skips_the_long_book():
    """Same lane rule for the anti-wedge: a long-book position is not dead
    weight blocking the row pipeline - it is the compounder holding its
    slot by design. ML-071 may still unwind unteachable 5m positions
    around it."""
    from main import pick_unteachable_unwind
    thesis = _pos(50.0, pid="thesis")
    thesis.book = "long"
    stale_5m = _pos(20.0, pid="stale-5m")
    pick = pick_unteachable_unwind([thesis, stale_5m], pending_ids=set(),
                                   at_capacity=True, rows=35,
                                   until_live_rows=500, now=NOW,
                                   min_age_h=1.0)
    assert pick is not None and pick.position_id == "stale-5m"
    # a book of ONLY long-book positions is never force-drained
    assert pick_unteachable_unwind([thesis], set(), True, 35, 500,
                                   NOW, 1.0) is None


def test_bracket_backstop_threads_tb_time_reason():
    """Source contract: when ML-073 realizes a bracket position (only ever
    past its deadline - see the picker tests above), the exit reason must
    thread "tb_time" verbatim so log_close files the row under
    LABEL_ERA_TRIPLE_BARRIER (it trains); the legacy path keeps the exact
    "label-mature realization (ML-073)" string (barrier "realized")."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    assert '"tb_time" if bracket_backstop' in src
    assert '"label-mature realization (ML-073)"' in src
    assert "self._submit_exit(pos, 100.0, reason, now=now)" in src
