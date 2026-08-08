"""Latency-truth tier 1 (2026-08-07 latency audit).

Three instruments that measured nothing, made honest:

1. Cycle duration was computed every iteration (runner loop) and used
   only to size the sleep - an 88s stall left no trace anywhere. The
   runner now records last/max cycle duration and exports both.
2. marks_age_sec compared the loop-frozen `now` against stamps set to
   that same `now` - arithmetically 0.0 forever (status.json showed
   0.0 beside a 253ms feed RTT). It now measures wall-clock age of the
   oldest mark from telemetry-only wall stamps. Decision paths still
   read the injected-time stamps untouched - replay determinism holds.
3. Venue candles were age-checked by FETCH age only; a venue serving a
   stale OHLC page was undetectable. The merge path now checks the last
   bar's own timestamp and warns (FW-080, latched per asset) when it
   lags more than _STALE_BAR_SEC behind the engine clock. Detection
   only: entries are not vetoed - that change is sequenced with the
   staleness-veto resurrection (owed item 42), not rushed here.

BotRunner.__new__ stubbing follows the test_audit_runner_state.py
convention.
"""
import ast
import logging
import time
from pathlib import Path
from types import SimpleNamespace

import runner as runner_mod
import main as main_mod


# ---------------------------------------------------------------- 1. cycle
def test_note_cycle_duration_tracks_last_and_max():
    r = runner_mod.BotRunner.__new__(runner_mod.BotRunner)
    r._note_cycle_duration(7.3)
    assert r._cycle_dur_last == 7.3
    assert r._cycle_dur_max == 7.3
    r._note_cycle_duration(2.0)
    assert r._cycle_dur_last == 2.0, "last must follow the newest cycle"
    assert r._cycle_dur_max == 7.3, "max must remember the worst stall"


# ---------------------------------------------------------------- 2. marks
def test_marks_age_is_wall_clock_not_frozen_now():
    wall = time.time()
    bot = SimpleNamespace(marks={"BTC/USD": 60000.0, "ETH/USD": 1900.0},
                          _mark_wall_ts={"BTC/USD": wall - 10.0,
                                         "ETH/USD": wall - 3.0})
    age = runner_mod._marks_age_sec(bot, wall)
    assert 9.9 <= age <= 10.1, ("oldest mark is 10s old - the gauge must "
                                "say so, not 0.0")


def test_marks_age_unstamped_symbol_reads_zero_not_huge():
    """A symbol with no wall stamp yet (first cycle) must not report a
    since-epoch age - it defaults to now (age 0), matching the old
    gauge's benign cold-start behavior."""
    wall = time.time()
    bot = SimpleNamespace(marks={"XRP/USD": 0.5}, _mark_wall_ts={})
    assert runner_mod._marks_age_sec(bot, wall) == 0.0


def test_build_status_wires_the_helper_and_exports_duration():
    """Parsed-AST wiring proof (a text scan would match this docstring):
    build_status must CALL _marks_age_sec and must write both
    cycle_duration keys. Pins the wiring without a full BotRunner."""
    tree = ast.parse(Path(runner_mod.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "build_status")
    calls = {c.func.id for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "_marks_age_sec" in calls
    keys = {k.value for n in ast.walk(fn) if isinstance(n, ast.Dict)
            for k in n.keys if isinstance(k, ast.Constant)}
    assert "cycle_duration_sec" in keys
    assert "cycle_duration_max_sec" in keys


# ---------------------------------------------------------------- 3. bars
# _bar_age_check is module-level with a duck-typed bot on purpose:
# test_v8_batch.py drives _augment_view_with_kraken with a SimpleNamespace
# as `self`, so a method call there would AttributeError (caught by the
# first battery of this change - 8 failures across test_v8_batch/
# test_add_asset_pairs).

def test_stale_bars_warn_once_with_code_and_latch(caplog):
    b = SimpleNamespace()
    now = 1_786_000_000.0
    stale = [{"time": now - 2000.0, "open": 1, "high": 1, "low": 1,
              "close": 1, "volume": 0}]
    with caplog.at_level(logging.WARNING, logger="liquiditybot.main"):
        main_mod._bar_age_check(b, "ADA", stale, now)
        main_mod._bar_age_check(b, "ADA", stale, now + 5.0)
    hits = [r for r in caplog.records if "FW-080" in r.getMessage()]
    assert len(hits) == 1, "latched: one warning per stale episode, not per cycle"
    assert "ADA" in hits[0].getMessage()


def test_fresh_bars_clear_the_latch_silently(caplog):
    b = SimpleNamespace()
    now = 1_786_000_000.0
    stale = [{"time": now - 2000.0, "open": 1, "high": 1, "low": 1,
              "close": 1, "volume": 0}]
    fresh = [{"time": now - 300.0, "open": 1, "high": 1, "low": 1,
              "close": 1, "volume": 0}]
    with caplog.at_level(logging.WARNING, logger="liquiditybot.main"):
        main_mod._bar_age_check(b, "ADA", stale, now)
        main_mod._bar_age_check(b, "ADA", fresh, now + 5.0)   # recover
        main_mod._bar_age_check(b, "ADA", stale, now + 10.0)  # new episode
    hits = [r for r in caplog.records if "FW-080" in r.getMessage()]
    assert len(hits) == 2


def test_bar_age_check_never_raises_on_list_shaped_rows():
    """Telemetry must never raise: raw kraken rows are lists, and the
    SimpleNamespace fixtures feed exactly that shape."""
    main_mod._bar_age_check(SimpleNamespace(), "BTC",
                            [[1_786_000_000.0, 1, 1, 1, 1, 0]],
                            1_786_000_000.0)


def test_bar_age_check_wired_into_the_merge_path():
    """_augment_view_with_kraken is the single place venue bars enter
    self.view - the check must run there (parsed AST, not text)."""
    tree = ast.parse(Path(main_mod.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef)
              and n.name == "_augment_view_with_kraken")
    calls = {c.func.id for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "_bar_age_check" in calls
