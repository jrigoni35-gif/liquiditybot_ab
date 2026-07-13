"""
Regression for the ML-071 learning-phase anti-wedge: a full book whose
positions can no longer produce training rows (pending vectors dropped
by a feature-schema gate) starves the row pipeline behind dead weight
(observed 2026-07-13: 5 orphaned positions held max_concurrent for
hours, zero rows possible). pick_unteachable_unwind returns the oldest
non-hedge orphan ONLY when: at capacity AND still in the learning phase
AND not one open position carries a pending vector AND the orphan is
old enough. Everything else stays with the tier engine.
"""
import time
from datetime import datetime, timezone
from types import SimpleNamespace

from main import pick_unteachable_unwind

NOW = time.time()


def _pos(pid, age_h=2.0, hedge=False):
    return SimpleNamespace(
        position_id=pid, symbol="BTC/USD", is_hedge=hedge,
        opened_at=datetime.fromtimestamp(NOW - age_h * 3600, timezone.utc))


def test_unwinds_oldest_orphan_when_book_is_dead_weight():
    positions = [_pos("a", 2.0), _pos("b", 7.5), _pos("c", 4.0)]
    got = pick_unteachable_unwind(positions, pending_ids=set(),
                                  at_capacity=True, rows=22,
                                  until_live_rows=240, now=NOW,
                                  min_age_h=1.0)
    assert got is not None and got.position_id == "b"


def test_never_fires_if_any_position_still_teaches():
    positions = [_pos("a", 5.0), _pos("b", 6.0)]
    got = pick_unteachable_unwind(positions, pending_ids={"a"},
                                  at_capacity=True, rows=22,
                                  until_live_rows=240, now=NOW,
                                  min_age_h=1.0)
    assert got is None


def test_never_fires_below_capacity_or_after_graduation():
    positions = [_pos("a", 5.0)]
    assert pick_unteachable_unwind(positions, set(), at_capacity=False,
                                   rows=22, until_live_rows=240, now=NOW,
                                   min_age_h=1.0) is None
    assert pick_unteachable_unwind(positions, set(), at_capacity=True,
                                   rows=240, until_live_rows=240, now=NOW,
                                   min_age_h=1.0) is None


def test_respects_min_age_and_skips_hedges():
    young = [_pos("a", 0.2)]
    assert pick_unteachable_unwind(young, set(), True, 22, 240, NOW,
                                   min_age_h=1.0) is None
    hedges = [_pos("a", 5.0, hedge=True)]
    assert pick_unteachable_unwind(hedges, set(), True, 22, 240, NOW,
                                   min_age_h=1.0) is None


def test_empty_book_is_a_noop():
    assert pick_unteachable_unwind([], set(), True, 22, 240, NOW,
                                   1.0) is None
