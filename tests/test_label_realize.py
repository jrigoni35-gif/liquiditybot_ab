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

from main import effective_realize_spans, pick_label_mature_unwind

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
    regardless, so the full window costs nothing and keeps the richer label."""
    # full book (5/5 non-hedge) -> the shorter fastpath horizon
    assert effective_realize_spans(1.0, 0.5, 5, 5) == 0.5
    # over-full (hedge unwind race etc.) still fires
    assert effective_realize_spans(1.0, 0.5, 6, 5) == 0.5
    # a single free slot -> full window
    assert effective_realize_spans(1.0, 0.5, 4, 5) == 1.0
    assert effective_realize_spans(1.0, 0.5, 0, 5) == 1.0


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


def test_horizon_derives_from_label_window_default_8h():
    # default: realize_after_label_spans 1.0 * label_max_bars 96 * 300s / 3600
    from ml.walkforward import BAR_SECONDS
    mature_h = 1.0 * 96 * BAR_SECONDS / 3600.0
    assert abs(mature_h - 8.0) < 1e-9
    # a 9h position is past it, a 7h one is not
    assert pick_label_mature_unwind([_pos(9.0)], 35, 500, NOW, mature_h)
    assert pick_label_mature_unwind([_pos(7.0)], 35, 500, NOW, mature_h) is None
