"""tests/test_log_hygiene.py — 2026-07-29 live-incident log hygiene (LINK
3ea2a851 events.jsonl flood):

  1. PT-060's "scratching full close" announce repeated every fast cycle
     (~5s) while the caller deferred the scratch — ~1,900 identical lines
     in one episode. The ANNOUNCE is now once per position; the ACTION is
     unchanged (returned every cycle until the close lands — exits are
     always allowed, CLAUDE.md invariant 5).
  2. "correlation shift detected" dumped the full pair->shift dict at
     INFO on every intraday update (~30s) for as long as the shift
     persisted. Now: one compact summary line on the False->True
     transition; ongoing state at DEBUG only.

(The third offender — "[X] probe THROTTLED" once per admission attempt —
is pinned in tests/test_probe_throttle.py next to its harness.)
"""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.state import Position
from regime.correlation import CorrelationEngine
from risk.profit_tiers import ProfitTierEngine

TIERS_TS = {
    "tier_1": {"trigger_pct_gain": 50.0, "close_pct_of_position": 25},
    "vol_scaled": False,
    "trailing_stop": {"enabled": False},
    "give_back": {"enabled": False},
    "time_stop": {"enabled": True, "max_bars_no_progress": 1,
                  "min_mfe_frac_of_tier1": 0.99},
}


def _pos(pid="p1"):
    p = Position(pid, "ETH/USD", "long", 100.0, 1.0, 1.0,
                 datetime.now(timezone.utc))
    p.opened_at = datetime.fromtimestamp(1000.0, tz=timezone.utc)
    return p


def test_pt060_announce_logs_once_per_position_action_every_cycle(caplog):
    eng = ProfitTierEngine(TIERS_TS)
    pos = _pos()
    with caplog.at_level(logging.INFO):
        a1 = eng.evaluate(pos, 100.1, now=1000.0 + 3600.0)
        a2 = eng.evaluate(pos, 100.1, now=1000.0 + 3605.0)
        a3 = eng.evaluate(pos, 100.1, now=1000.0 + 3610.0)
    # the ACTION fires every cycle - only the LOG is deduplicated
    for a in (a1, a2, a3):
        assert a.should_close_partial and a.close_pct == 100.0
        assert a.reason_code == "PT-060"
    msgs = [r for r in caplog.records if "PT-060" in r.getMessage()]
    assert len(msgs) == 1, "announce exactly once per position"


def test_pt060_announce_is_per_position_not_global(caplog):
    eng = ProfitTierEngine(TIERS_TS)
    with caplog.at_level(logging.INFO):
        eng.evaluate(_pos("p1"), 100.1, now=1000.0 + 3600.0)
        eng.evaluate(_pos("p2"), 100.1, now=1000.0 + 3600.0)
    msgs = [r for r in caplog.records if "PT-060" in r.getMessage()]
    assert len(msgs) == 2, "a second position gets its own announce"


def test_correlation_shift_logs_compact_summary_once_per_episode(caplog):
    eng = CorrelationEngine({"shift_threshold": 1e-6})
    with caplog.at_level(logging.INFO):
        # alternating vs trending closes force corr_fast away from
        # corr_slow within a few updates; with a ~0 threshold the shift
        # then persists for every subsequent update
        for i in range(1, 40):
            eng.update_intraday({"BTC": 100.0 + i,
                                 "ETH": 100.0 + ((-1) ** i) * 0.5 * i})
    assert eng.state.shifted is True, "fixture must actually shift"
    shifts = [r for r in caplog.records
              if "correlation shift detected" in r.getMessage()]
    assert len(shifts) == 1, "one INFO line per episode, not per update"
    # compact summary, never the raw dict dump
    assert "pair(s)" in shifts[0].getMessage()
    assert "{" not in shifts[0].getMessage()
