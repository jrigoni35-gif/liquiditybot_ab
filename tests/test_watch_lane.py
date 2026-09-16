"""Pins for core/watch_lane.py - the watch-and-label lane.

The lane's whole safety argument is that four measured channels carrying a
watch row back into ENTRY DECISIONING are cut. "SAFE by construction" was
REFUTED for the naive design, so none of it is asserted in prose here: each
channel is pinned, and each pin has a negative arm.

  1. GateStats     - on_label must be None
  2. asset_counts  - a SEPARATE FILE, never signal_history.csv
  3. candidate pool- its own cap, never ml.max_open_candidates
  4. horizon shadow- shadow_store must be None

Plus the structural one: the lane holds no bot reference, and it never widens
trading_pairs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.watch_lane import WATCH_HISTORY_PATH, WatchLane

ROOT = Path(__file__).resolve().parents[1]
NOW = 1789300000.0
STEP = 300
BASE = NOW - 900 * STEP


class _Feed:
    """Deterministic fixture. The 5m window grows FORWARD from a fixed start,
    so a candidate registered on one tick has real path on the next."""

    def __init__(self, n5: int = 460):
        self.n5 = n5
        self.calls: list = []

    def get_candles(self, pair, interval=5):
        self.calls.append(("candles", pair, interval))
        if interval != 5:
            return [{"time": BASE + i * 86400, "open": 100.0, "high": 101.0,
                     "low": 99.0, "close": 100.0 + 0.1 * i, "volume": 9.0}
                    for i in range(400)]
        out = []
        for i in range(self.n5):
            px = 100.0 * (1.0 + 0.0006 * i)
            out.append({"time": BASE + i * STEP, "open": px,
                        "high": px * 1.004, "low": px * 0.998,
                        "close": px, "volume": 50.0 + i})
        return out

    def get_order_book(self, pair, depth=20):
        self.calls.append(("book", pair, depth))
        return {"bids": [[99.9, 40.0], [99.8, 60.0]],
                "asks": [[100.1, 35.0], [100.2, 55.0]]}


@pytest.fixture(scope="module")
def shipped_cfg() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _cfg(shipped, **over):
    c = json.loads(json.dumps(shipped))
    wl = {"enabled": True, "pairs": ["SOL/USD"], "eval_every_sec": 0.0}
    wl.update(over)
    c["watch_lane"] = wl
    return c


# ======================================================================
# SHIPS DISABLED
# ======================================================================

def test_the_enabled_state_is_deliberate_and_documented(shipped_cfg):
    """This pin was `assert not enabled` until 2026-09-13, when the operator
    turned the lane ON. It is REPLACED, not deleted: the property worth
    holding is no longer "off" but "whatever it is, it is a deliberate,
    documented choice" - an `enabled` flag that appeared without a rationale
    beside it is the drift this file exists to catch."""
    wl = shipped_cfg.get("watch_lane") or {}
    assert "enabled" in wl, "watch_lane carries no explicit enabled flag"
    assert isinstance(wl["enabled"], bool)
    assert (wl.get("_doc") or "").strip(), (
        "watch_lane.enabled carries no _doc explaining the choice")


def test_the_configured_pairs_are_never_traded_pairs(shipped_cfg):
    """The whole safety story is that watched != traded, and it must hold IN
    THE SHIPPED CONFIG, not only inside WatchLane.

    THE SKIP IS GONE, and removing it made this pin stronger rather than
    weaker. It used to skip whenever the lane was disabled, which meant the
    config could carry an overlapping pair list indefinitely and this file
    would say nothing - the unsafe state would only be discovered by the act
    of turning the lane on. A config that becomes unsafe the moment someone
    flips a flag is already wrong, so the overlap check now runs
    unconditionally and only the non-empty check is gated on `enabled`.

    It also fixed a red: tests/test_skip_census.py ratchets the static skip
    surface, the skip here took it 29 -> 30, and that census was not re-run
    in the commit that added it. Its own rule offers raise-with-a-reason or
    lower; lowering was available, so lowering is what happened.
    """
    wl = shipped_cfg.get("watch_lane") or {}
    pairs = wl.get("pairs") or []
    traded = set(shipped_cfg.get("exchanges", {}).get("kraken", {})
                 .get("trading_pairs") or [])
    overlap = sorted(set(pairs) & traded)
    assert not overlap, (
        f"watched pairs are also TRADED: {overlap} - unsafe whether or not "
        f"watch_lane.enabled is currently true")
    if wl.get("enabled"):
        assert pairs, "the lane is enabled with no pairs - it would do nothing"


def test_a_disabled_lane_is_still_reachable_as_a_state(shipped_cfg):
    """NEGATIVE ARM: turning it off must remain a working configuration, so
    the operator can revert without code changes."""
    c = json.loads(json.dumps(shipped_cfg))
    c["watch_lane"] = dict(c.get("watch_lane") or {}, enabled=False)
    lane = WatchLane(c, _Feed())
    assert lane.enabled is False
    assert lane.tick(NOW) == "idle"


def test_absent_config_means_disabled(shipped_cfg):
    c = json.loads(json.dumps(shipped_cfg))
    c.pop("watch_lane", None)
    lane = WatchLane(c, _Feed())
    assert lane.enabled is False
    assert lane.tick(NOW) == "idle"


def test_a_disabled_lane_makes_no_feed_calls(shipped_cfg):
    """NEGATIVE ARM: disabled must cost zero REST budget."""
    f = _Feed()
    lane = WatchLane(_cfg(shipped_cfg, enabled=False), f)
    for i in range(5):
        lane.tick(NOW + i)
    assert f.calls == []


# ======================================================================
# CHANNEL 1 - GateStats
# ======================================================================

def test_the_labeler_has_no_on_label_callback(shipped_cfg):
    """A watch row must never reach gate_stats.note_label, whose
    weighted_confidence is applied on the ENTRY PATH."""
    lane = WatchLane(_cfg(shipped_cfg), _Feed())
    assert lane._labeler is not None
    cb = getattr(lane._labeler, "on_label", getattr(lane._labeler,
                                                    "_on_label", "MISSING"))
    assert cb is None, f"on_label is {cb!r} - a watch row can move a gate weight"


# ======================================================================
# CHANNEL 2 - asset_counts / the shared corpus
# ======================================================================

def test_the_corpus_is_a_separate_file(shipped_cfg):
    lane = WatchLane(_cfg(shipped_cfg), _Feed())
    p = str(lane._store.path).replace("\\", "/")
    assert "signal_history.csv" not in p
    assert p.endswith("watch_history.csv")


def test_the_path_constant_is_not_the_shared_corpus():
    assert "signal_history" not in WATCH_HISTORY_PATH
    assert WATCH_HISTORY_PATH.endswith("watch_history.csv")


def test_ticking_never_writes_the_shared_corpus(shipped_cfg, tmp_path,
                                                monkeypatch):
    """The load-bearing one: drive a real tick and assert signal_history.csv
    is untouched. conftest redirects WATCH_HISTORY_PATH, so this also proves
    that redirection is wired."""
    import core.watch_lane as mod
    shared = tmp_path / "signal_history.csv"
    shared.write_text("header\n", encoding="utf-8")
    before = shared.read_bytes()
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH",
                        str(tmp_path / "watch_history.csv"))
    lane = mod.WatchLane(_cfg(shipped_cfg), _Feed())
    lane.tick(NOW)
    assert shared.read_bytes() == before


# ======================================================================
# CHANNEL 3 - the candidate pool
# ======================================================================

def test_the_pool_cap_is_its_own_not_the_ml_key(shipped_cfg):
    """Overflow on the shared pool drops the NEWEST pending candidate, which
    would be a real universe candidate. The lane must not share that budget."""
    c = _cfg(shipped_cfg, max_open_candidates=7)
    c.setdefault("ml", {})["max_open_candidates"] = 1801
    lane = WatchLane(c, _Feed())
    assert int(lane._labeler.max_candidates) == 7, \
        "the lane is drawing on ml.max_open_candidates"


# ======================================================================
# CHANNEL 4 - the horizon shadow corpus
# ======================================================================

def test_no_shadow_store(shipped_cfg):
    lane = WatchLane(_cfg(shipped_cfg), _Feed())
    ss = getattr(lane._labeler, "shadow_store",
                 getattr(lane._labeler, "_shadow", "MISSING"))
    assert ss in (None, "MISSING"), \
        f"shadow_store is {ss!r} - horizon_shadow.csv would gain a population"


# ======================================================================
# THE UNIVERSE - excluded by COMPUTATION, not by trust
# ======================================================================

def test_a_traded_pair_is_dropped_even_if_configured(shipped_cfg):
    traded = list((shipped_cfg.get("exchanges", {}).get("kraken", {})
                   .get("trading_pairs") or []))
    assert traded, "fixture needs a non-empty trading universe"
    c = _cfg(shipped_cfg, pairs=["SOL/USD", traded[0]])
    lane = WatchLane(c, _Feed())
    assert traded[0] not in lane.pairs
    assert traded[0] in lane.excluded


def test_the_lane_never_widens_trading_pairs(shipped_cfg):
    """The universe is a fenced axis. Watching must not touch it."""
    c = _cfg(shipped_cfg, pairs=["SOL/USD", "XRP/USD"])
    before = list(c["exchanges"]["kraken"]["trading_pairs"])
    lane = WatchLane(c, _Feed())
    for i in range(4):
        lane.tick(NOW + i)
    assert c["exchanges"]["kraken"]["trading_pairs"] == before


def test_the_lane_holds_no_bot_reference(shipped_cfg):
    """Structural isolation: config dict and a feed, nothing else."""
    lane = WatchLane(_cfg(shipped_cfg), _Feed())
    for name, val in vars(lane).items():
        assert type(val).__name__ != "LiquidityBot", f"{name} is a bot"


# ======================================================================
# IT ACTUALLY WORKS - a pin that fails if the lane silently does nothing
# ======================================================================

def test_a_watch_row_is_written_and_labeled(shipped_cfg, tmp_path,
                                            monkeypatch):
    import core.watch_lane as mod
    out = tmp_path / "watch_history.csv"
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(out))
    f = _Feed(n5=460)
    lane = mod.WatchLane(_cfg(shipped_cfg), f)
    assert "+1" in lane.tick(NOW), "no candidate registered on the first tick"
    f.n5 = 900                       # 440 bars of path arrive
    lane.tick(NOW + 1)
    assert out.exists(), "no watch corpus written"
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2, "header only - nothing was labeled"
    row = dict(zip(lines[0].split(","), lines[1].split(",")))
    assert row.get("asset") == "SOL"
    assert row.get("source") == "candidate"
    assert str(row.get("barrier", "")).startswith("tb_")
    assert lane.snapshot()["rows_labeled"] >= 1


# ======================================================================
# THE PENDING POOL SURVIVES A RESTART (2026-09-15)
#
# Before this, every restart discarded the pool. A watch candidate needs up
# to 36 h to resolve and the process does not live that long, so the ONLY
# rows that ever reached the corpus were fast barrier touches - a corpus
# selected on volatility, which is the half of the signal this repo's own
# resolution-vs-direction work says carries no directional information. The
# lane was not just slow; the rows it kept were the wrong ones.
# ======================================================================

def test_the_pending_pool_survives_a_restart(shipped_cfg, tmp_path,
                                             monkeypatch):
    """END-TO-END, and the arm that matters: a SECOND lane object - what a
    relaunch builds - must inherit the first one's pending candidates."""
    import core.watch_lane as mod
    out = tmp_path / "watch_history.csv"
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(out))

    import time
    lane = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    assert "+1" in lane.tick(NOW), "no candidate registered"
    assert lane.snapshot()["pending"] >= 1
    # SAVED AT THE WALL CLOCK, not at NOW. NOW is a fixed fixture epoch and
    # is ~2.5 days in the past, which the restore path's age gate correctly
    # refuses (the gate drops a pool older than label_max_bars x 5 m = 36 h).
    # Decoupling saved_at from the bar timestamps is a fixture convenience -
    # the gate reads only saved_at - and the gate itself is pinned below.
    lane._save_state(time.time())               # the throttle fires at 600 s
    state = Path(lane._state_path())
    assert state.exists(), "no state written"

    reborn = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    assert reborn.snapshot()["restored_on_boot"] >= 1, "pool NOT restored"
    assert reborn.snapshot()["pending"] >= 1


def test_without_the_saved_state_a_restart_starts_empty(shipped_cfg, tmp_path,
                                                        monkeypatch):
    """The NEGATIVE arm. Without this, the pin above could pass because the
    second lane re-registered the candidate itself rather than restoring it."""
    import core.watch_lane as mod
    out = tmp_path / "watch_history.csv"
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(out))
    lane = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    lane.tick(NOW)
    lane._save_state(NOW)
    Path(lane._state_path()).unlink()           # the pre-fix world
    reborn = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    assert reborn.snapshot()["restored_on_boot"] == 0
    assert reborn.snapshot()["pending"] == 0


def test_the_state_file_follows_the_corpus_and_never_lands_in_production(
        shipped_cfg, tmp_path, monkeypatch):
    """The path pin. A state path bound at __init__ does NOT follow the
    module-level redirect these tests use, and wrote
    outputs/watch_lane_state.json into the production tree - caught by
    conftest's tripwire on the first run, the ELEVENTH instance of this
    repo's QA-writes-production class."""
    import core.watch_lane as mod
    out = tmp_path / "watch_history.csv"
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(out))
    lane = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    sp = Path(lane._state_path())
    assert sp.parent == out.parent, "state file left the corpus's directory"
    assert "outputs" not in sp.parts[:-1] or str(tmp_path) in str(sp)
    lane.tick(NOW)
    lane._save_state(NOW)
    assert sp.exists() and sp.stat().st_size > 0

    # This pin's FIRST form asserted `not (ROOT/"outputs"/
    # "watch_history_state.json").exists()`, and that was wrong twice over.
    # (1) In production that file is exactly where the live lane's pool
    #     BELONGS, so the assertion goes red the day this ships and then
    #     keeps blaming this test for the bot working correctly.
    # (2) An absence check cannot tell "this test wrote it" from "anyone
    #     ever wrote it", so it misattributes whatever it does catch.
    # The WRITE claim is not this test's to make: conftest's audit hook
    # watches open / os.rename / os.replace / os.remove and fails the
    # OFFENDING test by name - it already covers the mkstemp+os.replace
    # pair _save_state uses. What is left here is a PATH claim, which is
    # deterministic, order-independent and production-independent.
    assert not sp.resolve().is_relative_to((ROOT / "outputs").resolve()),         f"state path resolves inside the production tree: {sp}"

    # The mutant this pin exists to kill: a path bound at __init__. Re-point
    # the corpus constant AFTER construction - a call-time derivation follows
    # it, a frozen one does not. Nothing else in the file probes this.
    moved = tmp_path / "moved" / "watch_history.csv"
    moved.parent.mkdir()
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(moved))
    assert Path(lane._state_path()).parent == moved.parent,         "state path frozen at construction - it does not follow the corpus"


def test_a_corrupt_state_file_leaves_the_lane_working(shipped_cfg, tmp_path,
                                                      monkeypatch):
    """Fail-soft: a torn or hand-edited file must cost the pool, never the
    lane. The pre-fix behaviour (empty pool) is the floor, not a crash."""
    import core.watch_lane as mod
    out = tmp_path / "watch_history.csv"
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(out))
    probe = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    Path(probe._state_path()).write_text("{not json", encoding="utf-8")
    lane = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    assert lane.snapshot()["ready"], "a bad state file disabled the lane"
    assert lane.snapshot()["restored_on_boot"] == 0
    assert "+1" in lane.tick(NOW), "lane cannot work after a bad restore"


def test_the_save_is_atomic_and_leaves_no_temp_behind(shipped_cfg, tmp_path,
                                                      monkeypatch):
    """A torn state file would be restored at the next boot as a PARTIAL pool
    without complaining - the silent-corruption shape the repo's snapshot
    machinery exists to prevent.

    The FIRST form of this pin asserted only "no *.tmp is left" and "the
    result parses". A plain open(p, "w") + json.dump satisfies BOTH, so a
    mutation sweep that replaced the whole mkstemp/os.replace block with a
    direct write SURVIVED all 29 tests: the pin was decorative, checking the
    mechanism's litter rather than the property the mechanism buys.

    What atomicity actually buys is that a write dying MIDWAY leaves the
    PREVIOUS file intact - and "w" truncates before the first byte is
    written. So the pin now kills a save mid-serialisation and reads the old
    pool back byte-for-byte. The failure is injected at the real seam
    (to_dict returns something json cannot encode), not by patching the
    shared json module out from under the interpreter.
    """
    import core.watch_lane as mod
    out = tmp_path / "watch_history.csv"
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(out))
    lane = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    lane.tick(NOW)

    # A good save first, so there is a previous pool to preserve.
    lane._save_state(NOW)
    sp = Path(lane._state_path())
    good = sp.read_bytes()
    assert good and json.loads(good.decode("utf-8"))
    assert not list(tmp_path.glob("*.tmp")), "temp file left behind"
    saves = lane.snapshot()["saves"]

    # Now make the NEXT save die partway through encoding.
    class _Unserialisable:
        pass

    monkeypatch.setattr(lane._labeler, "to_dict",
                        lambda: {"bars": _Unserialisable()})
    lane._save_state(NOW + 1)               # never raises, by contract

    assert sp.read_bytes() == good,         "a failed save CORRUPTED the previous pool - the write is not atomic"
    assert not list(tmp_path.glob("*.tmp")), "a failed save left a temp behind"
    assert lane.snapshot()["saves"] == saves,         "a failed save was counted as a save"
    assert "save:" in (lane.snapshot().get("last_error") or ""),         "a failed save was silent - nothing to see in the snapshot"


def test_one_asset_per_tick(shipped_cfg):
    """REST budget: the lane rides the trading loop's thread, so it evaluates
    at most one asset per tick and round-robins."""
    f = _Feed()
    lane = WatchLane(_cfg(shipped_cfg, pairs=["SOL/USD", "XRP/USD"]), f)
    lane.tick(NOW)
    pairs = {c[1] for c in f.calls}
    assert len(pairs) == 1, f"more than one asset touched in a tick: {pairs}"


def test_the_throttle_holds(shipped_cfg):
    f = _Feed()
    lane = WatchLane(_cfg(shipped_cfg, eval_every_sec=600.0), f)
    lane.tick(NOW)
    n = len(f.calls)
    lane.tick(NOW + 1)
    lane.tick(NOW + 59)
    assert len(f.calls) == n, "the lane evaluated inside its throttle window"


def test_the_throttle_boundary_is_exclusive(shipped_cfg):
    """Found by scripts/mutation_sweep.py: `<` -> `<=` SURVIVED, because the
    original throttle pin ticked at +1 and +59 of a 600 s window and never
    probed the boundary itself. A generic sweep tests what the author was not
    thinking about; the hand-picked mutants tested what he was."""
    f = _Feed()
    lane = WatchLane(_cfg(shipped_cfg, eval_every_sec=100.0), f)
    lane.tick(NOW)                       # first eval, _last_eval = NOW
    n = len(f.calls)
    lane.tick(NOW + 99.999)              # inside the window: still throttled
    assert len(f.calls) == n
    lane.tick(NOW + 100.0)               # exactly AT the window: must fire
    assert len(f.calls) > n, \
        "the throttle held at exactly eval_every_sec - the boundary is `<`"


def test_a_failed_build_leaves_the_lane_inert(shipped_cfg, monkeypatch):
    """Found by scripts/mutation_sweep.py: `_engines_ok = False` -> `True` in
    _build's except branch SURVIVED, because nothing in the file ever forced
    an init failure. The branch is marked `pragma: no cover` for coverage,
    which is exactly the kind of line a generic sweep still mutates.

    A lane whose engines failed to construct must make NO venue calls and
    label nothing - it must not limp along with half a labeler. The failure
    is injected at the real seam: _build imports lazily, so replacing
    HistoryStore makes the genuine except branch run.
    """
    import ml.history as hist

    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("engine construction failed")

    monkeypatch.setattr(hist, "HistoryStore", _Boom)
    f = _Feed()
    lane = WatchLane(_cfg(shipped_cfg), f)
    assert lane._engines_ok is False
    assert lane.snapshot()["ready"] is False
    assert "RuntimeError" in lane.snapshot()["last_error"]
    for i in range(3):
        assert lane.tick(NOW + i) == "idle",             "a lane with no engines evaluated an asset anyway"
    assert f.calls == [], "a lane with no engines still called the venue"


def test_a_feed_exception_never_escapes(shipped_cfg):
    """It rides the trading loop's thread; a watch failure must not cost a
    cycle."""
    class Bad:
        def get_candles(self, *a, **k):
            raise RuntimeError("venue down")

        def get_order_book(self, *a, **k):
            raise RuntimeError("venue down")

    lane = WatchLane(_cfg(shipped_cfg), Bad())
    assert lane.tick(NOW) == "error"
    assert lane.snapshot()["errors"] == 1


def test_snapshot_publishes_the_isolation_properties(shipped_cfg):
    snap = WatchLane(_cfg(shipped_cfg), _Feed()).snapshot()
    assert snap["feeds_model"] is False
    assert snap["separate_corpus"] is True


def test_a_disabled_lane_does_not_report_itself_ready(shipped_cfg):
    """Found by scripts/mutation_sweep.py: `self.enabled and self.pairs` ->
    `or` SURVIVED. test_a_disabled_lane_makes_no_feed_calls pins the REST
    budget, which the mutant also satisfies - _due() gates on `enabled`
    independently, so the lane stays quiet either way. What the mutant DOES
    change is that a disabled lane builds its engines and then publishes
    `ready: True` into status.json.

    That is worth a pin on this repo's own terms: CLAUDE.md's mindset section
    makes the measurement plane the first suspect, and a telemetry field
    reading READY for a lane that is switched off is exactly a confident
    instrument that is wrong. Checked before writing this: HistoryStore does
    NOT create its file at init, so the mutant leaks no corpus - the cost is
    the misleading field and wasted boot work, not a leak.
    """
    off = WatchLane(_cfg(shipped_cfg, enabled=False), _Feed()).snapshot()
    assert off["enabled"] is False
    assert off["ready"] is False,         "a switched-off lane published ready=True into status.json"

    empty = WatchLane(_cfg(shipped_cfg, pairs=[]), _Feed()).snapshot()
    assert empty["watched"] == 0
    assert empty["ready"] is False,         "a lane with nothing to watch published ready=True"


# The ONE surviving mutant in core/watch_lane.py that is NOT pinned, recorded
# here so the next sweep reader does not re-investigate it:
#
#   `self._last_eval = 0.0` -> `1.0`  (WatchLane.__init__)
#
# EQUIVALENT, not a blind spot. `_due` compares `now - self._last_eval` against
# `_eval_every`; `now` is epoch seconds (~1.79e9) and `_eval_every` is at most
# an hour, so the first tick fires under either seed and every later tick uses
# a real `now`. No test can separate them without a fabricated epoch near zero,
# which would pin the fixture rather than the lane. This is the classic
# equivalent-mutant case mutation testing has no general answer to - and the
# right response is to say so, not to delete the operator.


# ======================================================================
# THE TWO MANDATORY REGISTRATIONS
# ======================================================================

def test_the_path_is_registered_in_conftest():
    """Per this repo's leak-class rule: a module attribute naming a path under
    outputs/ is registered ON INTRODUCTION, not after the first leak."""
    src = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert '"WATCH_HISTORY_PATH"' in src


def test_the_corpus_is_never_garbage_collected():
    """It accrues slowly by design, so age is exactly the wrong signal."""
    src = (ROOT / "scripts" / "outputs_gc.py").read_text(encoding="utf-8")
    assert '"watch_history.csv"' in src

def test_a_pool_older_than_the_candidate_horizon_is_dropped_and_counted(
        shipped_cfg, tmp_path, monkeypatch):
    """A candidate resolves within label_max_bars (36 h at 432 x 5 m). Past
    that its vertical barrier has already expired in wall-clock terms, and
    restoring it resumes the labeller's bar series across a gap the size of
    the outage - silently corrupting the very rows this persistence exists
    to win. restore() checks the feature SCHEMA; nothing checked the CLOCK.

    NOT HYPOTHETICAL. A 2.5-day-old pool written by a mutation test's
    planted production-path defect was sitting in outputs/ at the moment
    this restore path was about to ship, and would have been read as live.
    """
    import time

    import core.watch_lane as mod
    out = tmp_path / "watch_history.csv"
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(out))
    lane = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    lane.tick(NOW)
    assert lane.snapshot()["pending"] >= 1
    horizon = 432 * 300.0
    lane._save_state(time.time() - (horizon + 3600.0))

    reborn = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    snap = reborn.snapshot()
    assert snap["restored_on_boot"] == 0, "a stale pool was restored"
    assert snap["stale_dropped"] >= 1,         "the drop was silent - 'no pool' and 'refused the pool' read alike"
    assert "age" in snap["last_error"], snap["last_error"]
    assert snap["ready"], "a stale pool disabled the lane"


def test_a_pool_stamped_in_the_future_is_dropped(shipped_cfg, tmp_path,
                                                 monkeypatch):
    """The other side of the gate. An hour of slack absorbs clock skew; a
    stamp further ahead than that is a fabricated or corrupt file, and a
    one-sided age check would accept every one of them."""
    import time

    import core.watch_lane as mod
    out = tmp_path / "watch_history.csv"
    monkeypatch.setattr(mod, "WATCH_HISTORY_PATH", str(out))
    lane = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    lane.tick(NOW)
    lane._save_state(time.time() + 7200.0)

    reborn = mod.WatchLane(_cfg(shipped_cfg), _Feed(n5=460))
    assert reborn.snapshot()["restored_on_boot"] == 0
    assert reborn.snapshot()["stale_dropped"] >= 1


def test_the_bar_width_here_matches_the_labellers():
    """_BAR_SEC is duplicated rather than imported (an import failure at boot
    would cost the pool the restore exists to save). A duplicated constant is
    only safe while something compares it to its source."""
    from ml.walkforward import BAR_SECONDS

    import core.watch_lane as mod
    assert mod._BAR_SEC == BAR_SECONDS, (
        f"watch_lane._BAR_SEC={mod._BAR_SEC} has drifted from "
        f"ml.walkforward.BAR_SECONDS={BAR_SECONDS} - the age gate's horizon "
        f"is wrong by that ratio")

