"""tests/test_audit_runner_state.py — whole-codebase audit, "runner-state"
group: C1, C2 (runner side), H4, H5, H6, H7, M1, M3.

Each test below fails against the pre-audit behaviour of runner.py /
core/runtime.py / core/persistence.py and passes after the fix. Where the
defect is a control-FLOW property that cannot be driven through the real
run() loop with real I/O, the pin is structural (source assertion) — the same
convention tests/test_flatten_all_isolation.py already uses for the PAUSED
maintenance slice.

Findings, in the audit's own numbering:

C1  the lock heartbeat was written once per loop iteration, before an
    unbounded cycle_once. Effective heartbeat interval = whole-iteration
    duration against a 30s stale window; measured live stalls were 48-88s, so
    a LIVE runner read as crashed and a second runner reclaimed its book
    (two audit-chain forks already in outputs/). Fixed by a daemon heartbeat
    thread + a new-risk latch at the FIRST lost heartbeat.
C2  force_dry left the runner RUNNING with a real book behind a paper engine,
    so every subsequent exit fabricated a fill against the still-live venue.
H4  force_dry poisoned the snapshot's dry_run field, so the prescribed live
    restart discarded the real book.
H5  flatten_all was a single unlatched attempt, never retried, and while
    PAUSED it was priced off frozen marks.
H6  the boot purge dropped commands the remote plane had already ledgered
    "applied".
H7  clear_fault was implemented but missing from VALID_COMMANDS — the only
    in-band path out of a latched fault was dead, silently.
M1  StateStore._seal_and_write had no Windows PermissionError retry.
M3  sim_* was gated on the mutable runtime flag, so force_dry unlocked
    simulated price shocks on a live-config bot.
"""
import json
import re
import threading
import time
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

import core.persistence as persistence
import core.runtime as rt
import runner as runner_mod
from core.fault import FaultManager, OpState, Severity
from core.persistence import StateStore
from core.runtime import VALID_COMMANDS, ControlChannel, SingleInstanceLock
from core.state import PortfolioState, Position
from runner import HANDLED_COMMANDS, BotRunner

RUNNER_SRC = (Path(__file__).resolve().parents[1] / "runner.py").read_text(
    encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
class _RecordingLock:
    """Duck-typed SingleInstanceLock: counts refreshes and can be told to
    start losing them to a 'live peer'."""

    def __init__(self):
        self.refreshes = 0
        self.lost_count = 0
        self.released = False
        self.pid = 4242
        self.losing = False

    def refresh(self):
        self.refreshes += 1
        if self.losing:
            self.lost_count += 1
            return False
        self.lost_count = 0
        return True

    @property
    def forfeited(self):
        return self.lost_count >= 3

    def release(self):
        self.released = True


def _fake_bot(dry_run=True, positions=(), fault=None):
    """Minimal duck-typed bot: only the attributes BotRunner touches on the
    startup line, the loop's error path and the dry shutdown path."""
    st = PortfolioState(starting_capital=10_000.0)
    for p in positions:
        st.add_position(p)
    return types.SimpleNamespace(
        dry_run=dry_run,
        poll_sec=0.0,
        snapshot_sec=10_000.0,
        _last_snapshot=time.time(),
        _resumed=False,
        _equity=lambda: 10_000.0,
        state=st,
        fault=fault,
        alerts=types.SimpleNamespace(fire=lambda *a, **k: None),
        orders=types.SimpleNamespace(deadman_sec=0, maker_fee_bps=16.0,
                                     taker_fee_bps=26.0, timeout_sec=25.0,
                                     dry_run=dry_run,
                                     open_orders=lambda: []),
        store=types.SimpleNamespace(snapshot=lambda b: True,
                                    path="outputs/state.json"),
        moomoo=types.SimpleNamespace(close=lambda: None),
    )


def _pos(pid="p1", symbol="ETH/USD", size=1.0):
    return Position(pid, symbol, "long", 2000.0, size, size,
                    datetime.now(timezone.utc))


def _stub_runner(**attrs):
    """BotRunner.__new__ double for handle_command-only tests (the convention
    tests/test_flatten_all_isolation.py established)."""
    r = BotRunner.__new__(BotRunner)
    r.state = "RUNNING"
    r._stop = False
    r._step_requested = False
    r._flatten_latched = False
    r._flatten_since = 0.0
    r._flatten_alerted = False
    r._lock_lost_latched = False
    r._wedge_latched = False
    r._recover_streak = 0
    r.config = {"system": {"dry_run": True}}
    r._paused_sentinel = Path("outputs") / "paused.on"
    r._entries_off_sentinel = Path("outputs") / "entries_off.on"
    r._force_dry_sentinel = runner_mod.FORCE_DRY_SENTINEL
    for k, v in attrs.items():
        setattr(r, k, v)
    return r


# ===========================================================================
# C1 — lock heartbeat off the cycle thread
# ===========================================================================
def test_c1_heartbeat_advances_while_a_cycle_stalls_past_the_stale_window(
        tmp_path, monkeypatch):
    """THE C1 regression. A single cycle_once that runs long must NOT let the
    lock heartbeat lapse. Against the old code the only refresh() call was at
    the top of the iteration, so a stalled cycle produced exactly ONE refresh
    and the lock aged past `stale_after` — which is how a second runner
    reclaimed a live book twice in outputs/audit.jsonl."""
    monkeypatch.chdir(tmp_path)
    bot = _fake_bot()
    lock = _RecordingLock()
    r = BotRunner({"system": {"polling_interval_sec": 0.01}},
                  bot=bot, lock=lock)  # type: ignore[arg-type]
    at_entry = lock.refreshes

    def stalling_cycle(now):
        time.sleep(0.35)             # ~35 heartbeat intervals of dead cycle
        r._stop = True
    bot.cycle_once = stalling_cycle
    r.run()
    # old behaviour: exactly one refresh for the whole stalled iteration.
    assert lock.refreshes - at_entry >= 5, (
        f"heartbeat did not advance during a stalled cycle "
        f"({lock.refreshes - at_entry} refreshes) - the lock ages out and a "
        f"peer takes the book")
    assert lock.released


def test_c1_run_loop_no_longer_writes_the_heartbeat_itself():
    """Structural pin: the loop must READ the verdict only. A refresh() call
    on the cycle thread reintroduces the coupling regardless of the thread."""
    body = RUNNER_SRC[RUNNER_SRC.index("while not self._stop:"):
                      RUNNER_SRC.index("finally:\n            # C1: stop the")]
    assert "_lock.refresh()" not in body, \
        "the cycle thread must not write the heartbeat (C1)"
    assert "_lock.forfeited" in body and "lost_count" in body


def test_c1_heartbeat_thread_is_a_daemon_and_stops_on_shutdown(tmp_path,
                                                               monkeypatch):
    monkeypatch.chdir(tmp_path)
    bot = _fake_bot()
    lock = _RecordingLock()
    r = BotRunner({"system": {"polling_interval_sec": 0.01}},
                  bot=bot, lock=lock)  # type: ignore[arg-type]
    assert r._hb_thread is not None and r._hb_thread.daemon
    assert r._hb_thread.is_alive()
    bot.cycle_once = lambda now: setattr(r, "_stop", True)
    r.run()
    assert not r._hb_thread.is_alive(), \
        "heartbeat thread must be joined before release() (it would recreate " \
        "a lockfile this process no longer owns)"


def test_c1_no_heartbeat_thread_without_a_lock(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = BotRunner({}, bot=_fake_bot())  # type: ignore[arg-type]
    assert r._hb_thread is None


def test_c1_first_lost_heartbeat_latches_new_risk_off(tmp_path, monkeypatch):
    """Old behaviour: the loop broke only on `forfeited` (LOST_LIMIT == 3), so
    a duplicate ran TWO more full cycle_once calls placing orders. New risk
    must be sealed at lost_count == 1 — exits still run (invariant #5)."""
    monkeypatch.chdir(tmp_path)
    fm = FaultManager()
    fm.arm()
    assert fm.allow_new_risk()
    bot = _fake_bot(fault=fm)
    lock = _RecordingLock()
    r = BotRunner({"system": {"polling_interval_sec": 0.01}},
                  bot=bot, lock=lock)  # type: ignore[arg-type]
    lock.losing = True
    seen = {}

    def cycle(now):
        seen["allow_new_risk"] = fm.allow_new_risk()
        r._stop = True
    bot.cycle_once = cycle
    # one lost heartbeat, well short of LOST_LIMIT
    lock.lost_count = 1
    r.run()
    assert runner_mod.LOCK_LOST_FAULT in fm.status()["faults"]
    assert fm.status()["state"] == OpState.HALTED.value
    # TWO legal schedules, both sealing new risk (the subject): on a quiet
    # machine the first cycle runs and observes allow_new_risk False; under
    # CPU contention the heartbeat thread latches BEFORE the first loop
    # iteration and the halted runner never cycles at all - a cycle that
    # never runs places no orders. Only observing True refutes the
    # invariant. The old `is False` assert encoded the quiet-machine
    # schedule and flaked under the battery's -n 8 load (2026-08-10).
    assert seen.get("allow_new_risk") is not True, \
        "a contended lock must refuse NEW risk on the FIRST lost heartbeat"
    assert FaultManager.allow_exits() is True, "exits are never gated"


def test_c1_boot_clears_a_stale_lock_lost_fault_because_we_hold_the_lock(
        tmp_path, monkeypatch):
    """lock_lost is not in core.fault.RECOVERABLE_FAULTS, so it re-latches from
    a snapshot. Since main() exits 3 unless acquire() succeeded, a restored
    lock_lost names a peer that provably no longer exists — booting HALTED on
    it would refuse new risk forever."""
    monkeypatch.chdir(tmp_path)
    fm = FaultManager()
    fm.arm()
    fm.latch(runner_mod.LOCK_LOST_FAULT, Severity.CRITICAL, "from last life")
    assert fm.status()["state"] == OpState.HALTED.value
    r = BotRunner({"system": {"polling_interval_sec": 0.01}},
                  bot=_fake_bot(fault=fm),
                  lock=_RecordingLock())  # type: ignore[arg-type]
    try:
        assert runner_mod.LOCK_LOST_FAULT not in fm.status()["faults"]
        assert fm.allow_new_risk()
    finally:
        r._stop_heartbeat()          # run() is what normally joins it


def test_c1_clear_fault_lock_lost_rearms_the_latch():
    fm = FaultManager()
    fm.arm()
    fm.latch(runner_mod.LOCK_LOST_FAULT, Severity.CRITICAL, "contended")
    r = _stub_runner(bot=types.SimpleNamespace(fault=fm),
                     _lock_lost_latched=True)
    r.handle_command({"cmd": "clear_fault",
                      "args": {"key": runner_mod.LOCK_LOST_FAULT}})
    assert r._lock_lost_latched is False, \
        "a later contention episode must be able to latch/alert again"


# ===========================================================================
# C2 — force_dry with an open LIVE book
# ===========================================================================
def _live_runner_for_force_dry(tmp_path, positions):
    cancelled = []
    bot = _fake_bot(dry_run=False, positions=positions)
    bot.orders.cancel_order = lambda o, reason="": cancelled.append(o) or True
    bot.live_armed = True
    fired = []
    bot.alerts = types.SimpleNamespace(
        fire=lambda key, msg, level="CRITICAL": fired.append((key, level, msg)))
    r = _stub_runner(bot=bot,
                     config={"system": {"dry_run": False}},
                     _paused_sentinel=tmp_path / "paused.on",
                     _force_dry_sentinel=tmp_path / "force_dry.on")
    return r, bot, fired, cancelled


def test_c2_force_dry_with_open_positions_pauses_and_alerts(tmp_path):
    """Old behaviour: flags flipped, runner stayed RUNNING, and every later
    exit for a LIVE-born position was simulated against the real Kraken book
    (DRY- txid, `venue calls: []`) while _handle_fill booked paper PnL and
    marked the position closed. Pausing is what stops cycle_once — the only
    caller that reaches _submit_exit — from doing that."""
    r, bot, fired, _ = _live_runner_for_force_dry(
        tmp_path, [_pos("aaaaaaaa11"), _pos("bbbbbbbb22", "BTC/USD")])
    r.handle_command({"cmd": "force_dry"})
    assert r.state == "PAUSED", \
        "a real book behind a paper engine must not keep cycling"
    assert (tmp_path / "paused.on").exists(), \
        "the pause must survive a supervisor/updater relaunch"
    assert [k for k, lvl, _ in fired
            if k == "force_dry_with_open_positions" and lvl == "CRITICAL"]
    # invariant #2: the flip itself is unchanged and still flips BOTH flags
    assert bot.dry_run and bot.orders.dry_run and not bot.live_armed


def test_c2_ack_names_the_stranded_positions_and_their_count(tmp_path, caplog):
    r, bot, _, _ = _live_runner_for_force_dry(tmp_path, [_pos("deadbeef99")])
    with caplog.at_level("WARNING"):
        r.handle_command({"cmd": "force_dry"})
    ack = [m.message for m in caplog.records if "control: force_dry" in m.message]
    assert ack and "1 OPEN LIVE position(s)" in ack[0]
    assert "deadbeef" in ack[0] and "ETH/USD" in ack[0]


def test_c2_force_dry_on_a_flat_book_does_not_pause(tmp_path):
    """The guard must be surgical: with nothing open there is no real book to
    protect, so the long-standing behaviour (flip, stay RUNNING) is kept."""
    r, bot, fired, cancelled = _live_runner_for_force_dry(tmp_path, [])
    r.handle_command({"cmd": "force_dry"})
    assert r.state == "RUNNING"
    assert not (tmp_path / "paused.on").exists()
    assert not fired
    assert bot.dry_run and bot.orders.dry_run and not bot.live_armed


def test_c2_cancel_first_ordering_is_preserved(tmp_path):
    """W2-5: resting live orders are cancelled while orders.dry_run is STILL
    False, or _poll_dry simulates fills on genuinely-resting venue orders."""
    seen = []
    r, bot, _, _ = _live_runner_for_force_dry(tmp_path, [_pos()])
    order = types.SimpleNamespace(side="sell", pair="ETHUSD", purpose="exit",
                                  txid="TX1", order_id="o1")
    bot.orders.open_orders = lambda: [order]
    bot.orders.cancel_order = lambda o, reason="": (
        seen.append(bot.orders.dry_run) or True)
    r.handle_command({"cmd": "force_dry"})
    assert seen == [False], "cancel must run on the LIVE path, before the flip"


def test_c2_force_dry_already_dry_is_still_a_noop(tmp_path):
    r, bot, fired, _ = _live_runner_for_force_dry(tmp_path, [_pos()])
    bot.dry_run = True
    r.handle_command({"cmd": "force_dry"})
    assert r.state == "RUNNING" and not fired
    assert not (tmp_path / "force_dry.on").exists()


# ===========================================================================
# H4 — durable force_dry sentinel; the restart must keep the book
# ===========================================================================
def test_h4_force_dry_writes_the_durable_sentinel(tmp_path):
    r, _, _, _ = _live_runner_for_force_dry(tmp_path, [])
    r.handle_command({"cmd": "force_dry"})
    assert (tmp_path / "force_dry.on").exists()


def test_h4_a_real_runner_always_has_the_sentinel_path(tmp_path, monkeypatch):
    """_cmd_force_dry getattr-guards the sentinel so a BotRunner.__new__ test
    double cannot leak a durable risk-off into the operator's checkout. Pin
    that the guard is never the PRODUCTION path."""
    monkeypatch.chdir(tmp_path)
    r = BotRunner({}, bot=_fake_bot())  # type: ignore[arg-type]
    assert r._force_dry_sentinel == runner_mod.FORCE_DRY_SENTINEL


def test_h4_boot_forces_dry_run_when_the_sentinel_exists(tmp_path):
    """Old behaviour: config still said dry_run:false, so restore() refused
    the snapshot ("refusing to mix paper and live state") and the bot booted
    flat with the full starting capital while the venue held the book."""
    s = tmp_path / "force_dry.on"
    s.touch()
    cfg = {"system": {"dry_run": False}}
    assert runner_mod.apply_force_dry_sentinel(cfg, sentinel=s) is True
    assert cfg["system"]["dry_run"] is True


def test_h4_boot_is_untouched_without_the_sentinel(tmp_path):
    cfg = {"system": {"dry_run": False}}
    assert runner_mod.apply_force_dry_sentinel(
        cfg, sentinel=tmp_path / "nope.on") is False
    assert cfg["system"]["dry_run"] is False


def test_h4_main_applies_the_sentinel_before_the_engine_is_built():
    """Structural pin: the override must happen in main(), BEFORE the lock and
    BotRunner/LiquidityBot construction - LiquidityBot.__init__ reads
    system.dry_run on its first line and OrderManager caches it."""
    body = RUNNER_SRC[RUNNER_SRC.index("def main()"):]
    call = body.index("apply_force_dry_sentinel(config, fresh=args.fresh)")
    build = body.index("BotRunner(config, start_paused=args.paused")
    assert call < build


def test_h4_sentinel_can_only_move_dry_run_toward_true(tmp_path):
    """Hard invariant #1: no code path may set dry_run False at runtime."""
    src = RUNNER_SRC[RUNNER_SRC.index("def apply_force_dry_sentinel"):
                     RUNNER_SRC.index("def main()")]
    assert 'sys_cfg["dry_run"] = True' in src
    assert "= False" not in src.replace("fresh: bool = False", "")


def test_h4_fresh_clears_the_sentinel(tmp_path):
    s = tmp_path / "force_dry.on"
    s.touch()
    cfg = {"system": {"dry_run": False}}
    assert runner_mod.apply_force_dry_sentinel(
        cfg, fresh=True, sentinel=s) is False
    assert not s.exists()
    assert cfg["system"]["dry_run"] is False


def test_h4_restart_under_live_config_restores_the_book(tmp_path, monkeypatch):
    """End-to-end shape of the finding: a snapshot taken after force_dry
    (dry_run:true, real positions) must LOAD on the next boot under the
    unchanged live config, instead of being discarded."""
    monkeypatch.chdir(tmp_path)
    store = StateStore(str(tmp_path / "state.json"))
    snap = {"version": persistence.SNAPSHOT_VERSION, "saved_at": time.time(),
            "dry_run": True, "portfolio": {}}
    store.write_raw(snap)
    data = store.load_raw()
    assert data is not None
    cfg = {"system": {"dry_run": False}}
    sentinel = tmp_path / "force_dry.on"
    sentinel.touch()
    runner_mod.apply_force_dry_sentinel(cfg, sentinel=sentinel)
    # restore()'s guard compares the snapshot flag against the bot's mode;
    # with the sentinel applied they now agree, so the book is kept.
    assert bool(data.get("dry_run", True)) == \
        bool(cfg["system"]["dry_run"]) is True


# ===========================================================================
# H5 — flatten_all is a latch, not one attempt
# ===========================================================================
def _flatten_runner(positions, state="RUNNING"):
    calls = []
    st = PortfolioState(starting_capital=10_000.0)
    for p in positions:
        st.add_position(p)
    bot = types.SimpleNamespace(
        state=st,
        esc_market_after=3,
        orders=types.SimpleNamespace(timeout_sec=25.0),
        alerts=types.SimpleNamespace(fire=lambda *a, **k: None),
        _submit_exit=lambda pos, pct, reason, now=None: calls.append(
            (pos.position_id, now)))
    r = _stub_runner(bot=bot)
    r.state = state
    return r, bot, calls, st


def test_h5_flatten_all_latches():
    r, _, _, _ = _flatten_runner([_pos()])
    r.handle_command({"cmd": "flatten_all"}, now=100.0)
    assert r._flatten_latched is True
    assert r._flatten_since == 100.0


def test_h5_latched_flatten_is_redriven_until_the_book_is_flat():
    """Old behaviour: one _submit_exit per position and no latch. On the 25s
    timeout _poll_live cancels and emits a zero-fill final event _handle_fill
    has no branch for, so nothing ever re-submitted — the ack claimed success
    and the position stayed open forever."""
    p = _pos()
    r, bot, calls, st = _flatten_runner([p])
    r.handle_command({"cmd": "flatten_all"}, now=100.0)
    assert len(calls) == 1
    r._drive_flatten(130.0)          # order expired, nothing filled
    r._drive_flatten(160.0)
    assert [c[0] for c in calls] == ["p1", "p1", "p1"], \
        "the latch must re-drive the exit every tick"
    st.remove_position(p.position_id)
    r._drive_flatten(190.0)
    assert r._flatten_latched is False, "a flat book clears the latch"
    assert len(calls) == 3


def test_h5_run_loop_drives_the_latch_every_tick():
    """Structural pin (the convention test_flatten_all_isolation.py uses for
    the PAUSED maintenance slice): the drive must sit in the loop body ahead
    of the RUNNING/PAUSED split, so a paused runner retries too."""
    i = RUNNER_SRC.index("if self._stop:\n                        break")
    block = RUNNER_SRC[i:i + 600]
    assert "self._drive_flatten(now)" in block


def test_h5_escalation_alert_fires_once_after_the_ladder_is_exhausted():
    fired = []
    r, bot, _, _ = _flatten_runner([_pos()])
    bot.alerts = types.SimpleNamespace(
        fire=lambda key, msg, level="CRITICAL": fired.append(key))
    r.handle_command({"cmd": "flatten_all"}, now=0.0)
    deadline = r._flatten_deadline_sec()          # 25 * (3 + 2) = 125s
    r._drive_flatten(deadline - 1.0)
    assert not fired, "must not alert while the ladder still has rungs left"
    r._drive_flatten(deadline + 1.0)
    r._drive_flatten(deadline + 60.0)
    assert fired == ["flatten_all_unresolved"], "exactly one loud alert"


def test_h5_paused_flatten_refreshes_marks_before_repricing():
    """While PAUSED, fast_cycle — the only writer of marks/kraken_books — does
    not run, so the replacement exit was priced off the touch frozen at pause
    time (and passed the firewall collar, which centers on that same frozen
    mid). The latch must refresh the affected assets first."""
    p = _pos()
    r, bot, calls, _ = _flatten_runner([p], state="PAUSED")
    fetched = {"tickers": [], "books": []}
    bot._pair_of = {"ETH": "ETHUSD"}
    bot.symbol_map = {"ETH": "ETH/USD"}
    bot._asset_of = lambda sym: "ETH"
    bot.marks = {"ETH/USD": 2000.0}
    bot._mark_ts = {"ETH/USD": 0.0}
    bot._stop_ok = {"ETH": True}
    bot.kraken_books = {}
    bot.book_ts = {}
    bot.watchdog = types.SimpleNamespace(filter_mark=lambda a, px: (px, True))
    bot.kraken = types.SimpleNamespace(
        get_tickers=lambda pairs: (fetched["tickers"].append(pairs)
                                   or {"ETHUSD": 1720.0}),
        get_order_book=lambda pair: (fetched["books"].append(pair)
                                     or {"bids": [[1719.0, 5.0]],
                                         "asks": [[1721.0, 5.0]]}))
    r._latch_flatten(2000.0)
    r._drive_flatten(2100.0)
    assert fetched["tickers"] == [["ETHUSD"]]
    assert fetched["books"] == ["ETHUSD"]
    assert bot.marks["ETH/USD"] == 1720.0, "the frozen mark must be replaced"
    assert bot._mark_ts["ETH/USD"] == 2100.0
    assert bot.book_ts["ETH"] == 2100.0


def test_h5_paused_mark_refresh_is_isolated_from_feed_faults():
    p = _pos()
    r, bot, calls, _ = _flatten_runner([p], state="PAUSED")
    bot._pair_of = {"ETH": "ETHUSD"}
    bot.symbol_map = {"ETH": "ETH/USD"}
    bot._asset_of = lambda sym: "ETH"
    bot.marks = {"ETH/USD": 2000.0}
    bot._mark_ts = {"ETH/USD": 0.0}
    bot._stop_ok = {}
    bot.kraken_books = {}
    bot.book_ts = {}
    bot.watchdog = types.SimpleNamespace(filter_mark=lambda a, px: (px, True))

    def boom(*a, **k):
        raise RuntimeError("venue down")
    bot.kraken = types.SimpleNamespace(get_tickers=boom, get_order_book=boom)
    r._latch_flatten(2000.0)
    r._drive_flatten(2100.0)                   # must not raise
    assert bot.marks["ETH/USD"] == 2000.0      # exactly as stale as before
    assert [c[0] for c in calls] == ["p1"], "the exit is still re-driven"


def test_h5_paused_ack_warns_instead_of_claiming_managed_exits():
    """The ack used to say "exits will be managed while paused" whatever the
    mark age. When the marks behind that exit are stale, say so."""
    p = _pos()
    r, bot, _, _ = _flatten_runner([p], state="PAUSED")
    bot._mark_ts = {"ETH/USD": 0.0}
    bot._mark_stale_sec = 20.0
    bot._pair_of = {}
    note = r._paused_mark_staleness_note(now=2100.0)
    assert "WARNING marks are 2100s old" in note


def test_h5_paused_ack_is_silent_when_marks_are_fresh():
    p = _pos()
    r, bot, _, _ = _flatten_runner([p], state="PAUSED")
    bot._mark_ts = {"ETH/USD": 2095.0}
    bot._mark_stale_sec = 20.0
    assert r._paused_mark_staleness_note(now=2100.0) == ""


# ===========================================================================
# H6 — boot purge keeps what arrived during startup
# ===========================================================================
def test_h6_boot_keeps_commands_sent_after_this_process_started(tmp_path,
                                                                monkeypatch):
    """The remote plane is at-most-once: it appends the id to
    remote_consumed.json and publishes result:"applied" BEFORE forwarding, and
    never retries. Engine construction takes tens of seconds, so anything
    forwarded during boot was acknowledged and then deleted unread — a
    swallowed flatten_all/stop tells the operator the book is flat when it is
    not."""
    monkeypatch.chdir(tmp_path)
    ch = ControlChannel()
    ch.send("flatten_all")                       # sent_at = now > _PROC_START
    r = BotRunner({}, bot=_fake_bot())  # type: ignore[arg-type]
    assert [c["cmd"] for c in r._boot_commands] == ["flatten_all"]


def test_h6_boot_still_purges_a_previous_life_s_leftover_stop(tmp_path,
                                                             monkeypatch):
    """The original purge exists because two stale `stop`s from a previous
    life were consumed at +1.2s and killed the fresh runner. That must hold."""
    monkeypatch.chdir(tmp_path)
    ch = ControlChannel()
    cid = ch.send("stop")
    f = Path("outputs/control") / f"cmd_{cid}.json"
    payload = json.loads(f.read_text(encoding="utf-8"))
    payload["sent_at"] = runner_mod._PROC_START - 60.0
    f.write_text(json.dumps(payload), encoding="utf-8")
    r = BotRunner({}, bot=_fake_bot())  # type: ignore[arg-type]
    assert r._boot_commands == []
    assert r._stop is False


def test_h6_unstamped_command_files_keep_the_conservative_purge(tmp_path,
                                                                monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = Path("outputs/control")
    d.mkdir(parents=True, exist_ok=True)
    (d / "cmd_manual.json").write_text(json.dumps({"cmd": "stop"}),
                                       encoding="utf-8")
    r = BotRunner({}, bot=_fake_bot())  # type: ignore[arg-type]
    assert r._boot_commands == []


def test_h6_retained_boot_commands_execute_on_the_first_iteration(tmp_path,
                                                                  monkeypatch):
    monkeypatch.chdir(tmp_path)
    ch = ControlChannel()
    ch.send("entries_off")
    bot = _fake_bot()
    bot.entries_enabled = True
    r = BotRunner({}, bot=bot)  # type: ignore[arg-type]
    bot.cycle_once = lambda now: setattr(r, "_stop", True)
    r.run()
    assert bot.entries_enabled is False
    assert r._boot_commands == [], "boot commands must run exactly once"


# ===========================================================================
# H7 — clear_fault vocabulary + bidirectional parity
# ===========================================================================
def test_h7_clear_fault_is_in_the_command_vocabulary():
    assert "clear_fault" in VALID_COMMANDS


def test_h7_clear_fault_survives_send_consume(tmp_path):
    """Both delivery paths were closed: send() raised ValueError, and
    consume() filtered on VALID_COMMANDS AFTER unlinking the file — so a
    hand-dropped command was silently deleted with no log and no ack."""
    ch = ControlChannel(str(tmp_path / "control"))
    ch.send("clear_fault", {"key": "cycle_wedged"})
    got = ch.consume()
    assert [c["cmd"] for c in got] == ["clear_fault"]
    assert got[0]["args"] == {"key": "cycle_wedged"}


def test_h7_command_vocabulary_parity_is_bidirectional():
    """The pre-existing guard only checked REMOTE_SAFE_COMMANDS ⊆
    VALID_COMMANDS and never looked at handle_command's own vocabulary."""
    dead, deaf = runner_mod.command_vocabulary_drift()
    assert not dead, (
        f"{sorted(dead)} are dispatched by handle_command but missing from "
        f"VALID_COMMANDS - send() raises and consume() DELETES them unread")
    assert not deaf, (
        f"{sorted(deaf)} are accepted by the channel but have no handler - "
        f"they ack 'ok' and do nothing")


def test_h7_handled_commands_matches_the_dispatcher_source():
    """Keeps the HANDLED_COMMANDS constant itself honest: it is compared
    against the literals in handle_command's own `cmd == "..."` branches, so
    the parity guard above cannot be satisfied by an out-of-date constant."""
    body = RUNNER_SRC[RUNNER_SRC.index("def handle_command"):
                      RUNNER_SRC.index("def _cmd_force_dry")]
    branches = set(re.findall(r'cmd == "([a-z_]+)"', body))
    prefixes = set(re.findall(r'cmd\.startswith\("([a-z_]+)"\)', body))
    # sim_* dispatches on a prefix, so its four members are enumerated by the
    # inner branches instead.
    for p in prefixes:
        assert any(h.startswith(p) for h in HANDLED_COMMANDS)
    assert branches <= set(HANDLED_COMMANDS), \
        f"handle_command dispatches {sorted(branches - set(HANDLED_COMMANDS))} " \
        f"which HANDLED_COMMANDS omits"
    covered = branches | {h for h in HANDLED_COMMANDS
                          if any(h.startswith(p) for p in prefixes)}
    assert set(HANDLED_COMMANDS) <= covered, \
        f"HANDLED_COMMANDS lists {sorted(set(HANDLED_COMMANDS) - covered)} " \
        f"with no branch in handle_command"


def test_h7_dropped_unknown_command_is_logged_not_silent(tmp_path, caplog):
    d = tmp_path / "control"
    d.mkdir()
    (d / "cmd_x.json").write_text(json.dumps({"cmd": "nonsense"}),
                                  encoding="utf-8")
    ch = ControlChannel(str(d))
    with caplog.at_level("WARNING"):
        assert ch.consume() == []
    assert any("dropped unknown/unparseable command" in m.message
               for m in caplog.records)
    assert not list(d.glob("cmd_*.json")), "the queue must still never wedge"


def test_h7_clear_fault_actually_clears_and_rearms_new_risk():
    fm = FaultManager()
    fm.arm()
    fm.latch("some_future_fault", Severity.CRITICAL, "x")
    assert not fm.allow_new_risk()
    r = _stub_runner(bot=types.SimpleNamespace(fault=fm))
    r.handle_command({"cmd": "clear_fault", "args": {"key": "some_future_fault"}})
    assert fm.allow_new_risk()


# ===========================================================================
# M1 — StateStore._seal_and_write shares the Windows retry
# ===========================================================================
def test_m1_seal_and_write_retries_a_transient_permission_error(tmp_path,
                                                                monkeypatch):
    """state.json is the BOOK OF RECORD and was the one publisher without the
    retry atomic_write_json has always had — so a reader holding it
    (session_digest under the hourly check-in, train_meta) silently dropped
    the post-fill "never lose an executed fill" snapshot."""
    store = StateStore(str(tmp_path / "state.json"))
    real = rt.os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(5, "Access is denied")
        return real(src, dst)

    monkeypatch.setattr(rt.os, "replace", flaky)
    monkeypatch.setattr(rt.time, "sleep", lambda s: None)
    assert store.write_raw({"version": persistence.SNAPSHOT_VERSION}) is True
    assert calls["n"] == 3
    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))[
        "version"] == persistence.SNAPSHOT_VERSION


def test_m1_seal_and_write_uses_the_shared_helper_not_a_reinvented_loop():
    src = (Path(__file__).resolve().parents[1] / "core"
           / "persistence.py").read_text(encoding="utf-8")
    body = src[src.index("def _seal_and_write"):src.index("def load_raw")]
    assert "replace_with_retry" in body
    assert "os.replace(" not in body, \
        "reuse core.runtime.replace_with_retry, do not reinvent the retry"


def test_m1_persistent_lock_still_fails_loudly_and_leaves_no_tmp(tmp_path,
                                                                 monkeypatch):
    """The retry must not turn a genuinely stuck destination into a silent
    success. Failure stays atomic and non-corrupting (both replaces fail
    together), and leaves no orphan tmp."""
    store = StateStore(str(tmp_path / "state.json"))

    def always_locked(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(rt.os, "replace", always_locked)
    monkeypatch.setattr(rt.time, "sleep", lambda s: None)
    assert store.write_raw({"version": persistence.SNAPSHOT_VERSION}) is False
    assert not list(tmp_path.glob("*.tmp"))


def test_m1_atomic_write_json_still_uses_the_same_helper(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = rt.os.replace

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 2:
            raise PermissionError(5, "Access is denied")
        return real(src, dst)

    monkeypatch.setattr(rt.os, "replace", flaky)
    monkeypatch.setattr(rt.time, "sleep", lambda s: None)
    rt.atomic_write_json(tmp_path / "s.json", {"ok": 1})
    assert calls["n"] == 2


# ===========================================================================
# M3 — sim_* gated on the CONFIGURED mode
# ===========================================================================
def _sim_runner(cfg_dry, runtime_dry):
    bot = types.SimpleNamespace(dry_run=runtime_dry, sim=rt.SimOverrides())
    return _stub_runner(bot=bot, config={"system": {"dry_run": cfg_dry}}), bot


def test_m3_force_dry_does_not_unlock_sims_on_a_live_config_bot():
    """THE M3 regression: the gate read the MUTABLE bot.dry_run, so after
    force_dry a live-config bot accepted simulated price shocks — and
    status.json reported "DRY_RUN", the exact signal an operator reads as
    safe. _apply_sim multiplies REAL marks in place."""
    r, bot = _sim_runner(cfg_dry=False, runtime_dry=True)   # post-force_dry
    r.handle_command({"cmd": "sim_price_shock",
                      "args": {"asset": "ETH", "pct": -25.0, "cycles": 3}})
    assert bot.sim.price_shock == {}
    r.handle_command({"cmd": "sim_force_fear", "args": {"cycles": 6}})
    assert bot.sim.force_fear == 0
    r.handle_command({"cmd": "sim_force_regime", "args": {"label": "crisis"}})
    assert bot.sim.force_regime == {}


def test_m3_sims_still_refused_when_only_the_runtime_flag_is_live():
    """A harness that flips bot.dry_run False on a dry config must keep
    getting the original refusal — the gate is conjunctive, never looser."""
    r, bot = _sim_runner(cfg_dry=True, runtime_dry=False)
    r.handle_command({"cmd": "sim_force_fear", "args": {"cycles": 6}})
    assert bot.sim.force_fear == 0


def test_m3_sims_work_on_a_genuinely_dry_bot():
    r, bot = _sim_runner(cfg_dry=True, runtime_dry=True)
    r.handle_command({"cmd": "sim_price_shock",
                      "args": {"asset": "ETH", "pct": -5.0, "cycles": 2}})
    assert bot.sim.price_shock["ETH"]["pct"] == -5.0
    r.handle_command({"cmd": "sim_clear"})
    assert bot.sim.price_shock == {}


def test_m3_refusal_ack_names_both_halves_of_the_gate(caplog):
    r, _ = _sim_runner(cfg_dry=False, runtime_dry=True)
    with caplog.at_level("WARNING"):
        r.handle_command({"cmd": "sim_force_fear", "args": {}})
    assert any("configured mode AND runtime flag" in m.message
               for m in caplog.records)


# ===========================================================================
# cross-cutting: the fix must not weaken the existing lock semantics
# ===========================================================================
def test_lock_semantics_unchanged_fresh_peer_still_wins(tmp_path):
    a = SingleInstanceLock(str(tmp_path / "r.lock"), stale_after_sec=30)
    b = SingleInstanceLock(str(tmp_path / "r.lock"), stale_after_sec=30)
    a.pid, b.pid = 111, 222
    assert a.acquire() is None
    assert b.refresh() is False
    assert a.refresh() is True


def test_heartbeat_thread_and_loop_do_not_both_write_the_lock(tmp_path,
                                                              monkeypatch):
    """Two writers of lost_count would race the forfeit verdict. Exactly one
    refresher: the daemon thread."""
    monkeypatch.chdir(tmp_path)
    lock = _RecordingLock()
    bot = _fake_bot()
    r = BotRunner({"system": {"polling_interval_sec": 100.0}},
                  bot=bot, lock=lock)  # type: ignore[arg-type]
    before = lock.refreshes
    ticks = {"n": 0}

    def cycle(now):
        ticks["n"] += 1
        if ticks["n"] >= 3:
            r._stop = True
    bot.cycle_once = cycle
    r.run()
    # heartbeat interval (100s) far exceeds the run, so the ONLY way refreshes
    # could have advanced is the loop writing them itself.
    assert lock.refreshes == before, "the loop must not refresh the lock"
    assert ticks["n"] == 3


@pytest.mark.parametrize("name", ["lock-heartbeat"])
def test_no_heartbeat_threads_leak_between_tests(name):
    alive = [t for t in threading.enumerate() if t.name == name and t.is_alive()]
    assert not alive, f"leaked heartbeat thread(s): {alive}"
