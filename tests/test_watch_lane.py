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


def test_if_enabled_the_pairs_are_off_universe_and_nonempty(shipped_cfg):
    """The whole safety story is that watched != traded. If the lane is on,
    that must hold IN THE SHIPPED CONFIG, not only inside WatchLane."""
    wl = shipped_cfg.get("watch_lane") or {}
    if not wl.get("enabled"):
        pytest.skip("lane disabled in the shipped config")
    pairs = wl.get("pairs") or []
    assert pairs, "the lane is enabled with no pairs - it would do nothing"
    traded = set(shipped_cfg.get("exchanges", {}).get("kraken", {})
                 .get("trading_pairs") or [])
    overlap = sorted(set(pairs) & traded)
    assert not overlap, f"watched pairs are also TRADED: {overlap}"


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
