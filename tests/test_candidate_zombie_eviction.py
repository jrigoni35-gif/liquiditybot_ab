"""Candidate-queue zombie eviction (ML-085) and restore cap-shrink
truncation (ML-086) - the two 2026-08-16 pool-liveness defects (owed
items 84/85).

DEFECT A (measured live): a candidate whose asset's bars cache went stale
was neither labeled nor dropped - the only unlabelable-drop rule was the
bar-window SLIDE (bar_time < cache head), and update_candles only appends
NEW bars, so a dead feed squatted pool slots forever (2026-08-16
state.json: 32/187 pending slots older than 38h against the 36h horizon;
DOT 17 slots with bars 156h stale). Fix: poll(now) censors a candidate
past label_max_bars + ml.candidate_evict_margin_bars whose bars provably
cannot produce its label. CENSORED means NO label row - an unresolvable
candidate is missing data, never a tb_time outcome.

DEFECT B (from code): register() holds pool size CONSTANT at the cap
(pop-then-append), so a cap DECREASE in config was never enforced against
a larger restored pool. Fix: restore() truncates to the cap, dropping the
NEWEST (register()'s own at-cap eviction direction).

Every test here plants its defect and watches the fix fire; the race pin
(healthy at-horizon candidate with a full window) watches it NOT fire.
"""
import json
import logging
import re
from pathlib import Path

import numpy as np

from core.config_guard import validate
from ml.features import FEATURE_NAMES
from ml.history import _EPOCH_CLOCK_FLOOR, CandidateLabeler, HistoryStore
from ml.walkforward import BAR_SECONDS

_ROOT = Path(__file__).resolve().parents[1]
_LOGGER = "liquiditybot.ml.history"

# any real epoch instant, comfortably above the clock-coherence floor
E = 1_755_000_000.0
HORIZON = 12
MARGIN = 6
# first instant at which the age gate admits a candidate entered at E
DEADLINE = E + (HORIZON + MARGIN) * BAR_SECONDS

CFG = {"label_max_bars": HORIZON, "candidate_evict_margin_bars": MARGIN,
       "label_mode": "triple_barrier"}


def _labeler(tmp_path, cfg=None, name="h.csv"):
    return CandidateLabeler(HistoryStore(str(tmp_path / name)), cfg or CFG)


def _candles(n, start=E, px=2000.0, drift=0.0):
    """n bars of 5m candles from `start`; drift is per-bar fractional
    close-to-close move (0.0 = dead flat, so no barrier ever touches)."""
    out = []
    c = px
    for k in range(n):
        c *= (1.0 + drift)
        out.append({"time": start + k * BAR_SECONDS, "open": c,
                    "high": c * 1.001, "low": c * 0.999, "close": c,
                    "volume": 10.0})
    return out


def _register(lab, asset="ETH", bar_time=E):
    feats = np.zeros(len(FEATURE_NAMES))
    assert lab.register(asset, "long", feats, 0.005, bar_time) is True


def _rows(lab):
    X, _y, _w = lab.store.load_training_data()
    return len(X)


# --- defect A: the zombie is evicted, censored, and coded ------------------

def test_frozen_bars_zombie_evicted_with_code_and_no_row(tmp_path, caplog):
    """THE PLANT: entry bar cached, feed then freezes (3 bars, flat), age
    pushed past horizon+margin. Pre-fix poll() continues forever; the fix
    must censor with ML-085 and write NO label row."""
    lab = _labeler(tmp_path)
    lab.update_candles("ETH", _candles(3))
    _register(lab)
    # not yet over-age: one second before the deadline keeps it pending
    assert lab.poll(DEADLINE - 1.0) == 0
    assert len(lab._cands) == 1, "age gate must hold until the deadline"
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        written = lab.poll(DEADLINE)
    assert written == 0
    assert len(lab._cands) == 0, "zombie must be evicted at the deadline"
    assert _rows(lab) == 0, \
        "censored means censored: no label row may be fabricated"
    assert "ML-085" in caplog.text and "ETH" in caplog.text


def test_absent_bars_asset_is_evicted(tmp_path, caplog):
    """A candidate whose asset never cached ANY bars is the extreme
    stale-feed case: pre-fix it squatted forever (no cache head to slide
    past); the fix censors it once over-age."""
    lab = _labeler(tmp_path)
    _register(lab, asset="DOT")
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        lab.poll(DEADLINE)
    assert len(lab._cands) == 0
    assert _rows(lab) == 0
    assert "ML-085" in caplog.text and "DOT" in caplog.text


def test_healthy_at_horizon_candidate_resolves_and_is_never_evicted(
        tmp_path, caplog):
    """THE RACE PIN: bars ARE flowing and cover the full window - even at
    an age far past the deadline the candidate must resolve normally via
    poll() (time label), never be censored. Eviction fires only when
    resolution is impossible from data on hand."""
    lab = _labeler(tmp_path)
    lab.update_candles("ETH", _candles(HORIZON + 2))   # avail >= horizon
    _register(lab)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        written = lab.poll(DEADLINE + 100 * BAR_SECONDS)
    assert written == 1, "full window on hand must label, not evict"
    assert len(lab._cands) == 0
    assert _rows(lab) == 1
    assert "ML-085" not in caplog.text


def test_sparse_bars_reaching_window_end_are_not_censored(tmp_path, caplog):
    """Time-domain stand-down pin: a gappy feed whose LATEST bar has
    reached the candidate's window end is still delivering (index count
    will catch up as bars land) - the data gate must refuse to censor
    even when the age gate is long past. Only a feed that stopped BEFORE
    the window end is provably dead."""
    lab = _labeler(tmp_path)
    bars = _candles(3)                       # E, E+300, E+600 ...
    bars.append({"time": E + (HORIZON + 1) * BAR_SECONDS, "open": 2000.0,
                 "high": 2002.0, "low": 1998.0, "close": 2000.0,
                 "volume": 10.0})            # ... then one PAST window end
    lab.update_candles("ETH", bars)
    _register(lab)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        lab.poll(DEADLINE + 100 * BAR_SECONDS)
    assert len(lab._cands) == 1, \
        "bars that reached the window end prove the feed is alive - " \
        "the candidate must be left to resolve, not censored"
    assert "ML-085" not in caplog.text


def test_shadow_retained_zombie_evicted_without_second_row(tmp_path, caplog):
    """A candidate early-labeled but retained for multi-horizon shadows
    squats just the same when its feed freezes. Censoring it must keep
    the ONE already-written row - never fabricate another."""
    cfg = dict(CFG)
    cfg["multi_horizon"] = {"enabled": True, "horizons_bars": [4]}
    lab = _labeler(tmp_path, cfg)
    # strong up-path: pt (8 x 0.005 = 4%) touched well inside 6 bars,
    # so the candidate labels early and STAYS for the shadow record
    lab.update_candles("ETH", _candles(7, drift=0.02))
    _register(lab)
    assert lab.poll(E + BAR_SECONDS) == 1, "early label expected"
    assert len(lab._cands) == 1 and lab._cands[0].get("labeled"), \
        "shadow retention must hold the slot (planted premise)"
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        assert lab.poll(DEADLINE) == 0
    assert len(lab._cands) == 0, "shadow-retained zombie must be evicted"
    assert _rows(lab) == 1, "exactly the one early row - no duplicate"
    assert "ML-085" in caplog.text


def test_legacy_poll_without_now_never_evicts(tmp_path):
    """poll() with no argument is every legacy caller (tests, smoke,
    scripts): eviction stays disarmed and behavior is byte-identical to
    the pre-fix labeler."""
    lab = _labeler(tmp_path)
    lab.update_candles("ETH", _candles(3))
    _register(lab)
    assert lab.poll() == 0
    assert len(lab._cands) == 1, "no clock, no eviction - ever"


def test_toy_bar_clock_never_arms_eviction(tmp_path):
    """Harness protection: smoke's mock feeds mint bar times 0..119 while
    cycles run on time.time(). A naive age gate would censor every such
    candidate on sight; the epoch floor must keep eviction disarmed."""
    lab = _labeler(tmp_path)
    lab.update_candles("ETH", _candles(3, start=0.0))   # toy clock
    feats = np.zeros(len(FEATURE_NAMES))
    assert lab.register("ETH", "long", feats, 0.005, 0.0) is True
    assert 0.0 < _EPOCH_CLOCK_FLOOR
    lab.poll(1.9e9)                                     # epoch wall clock
    assert len(lab._cands) == 1, \
        "toy bar clocks must never be aged against the epoch clock"


def test_margin_is_config_lifted_and_honored(tmp_path):
    """Same zombie, two margins: the small margin censors at the shared
    probe instant, the large one keeps waiting - the knob is live, not
    decorative."""
    probe = DEADLINE
    small = _labeler(tmp_path, CFG, name="s.csv")
    big_cfg = dict(CFG)
    big_cfg["candidate_evict_margin_bars"] = 600
    big = _labeler(tmp_path, big_cfg, name="b.csv")
    for lab in (small, big):
        lab.update_candles("ETH", _candles(3))
        _register(lab)
        lab.poll(probe)
    assert len(small._cands) == 0
    assert len(big._cands) == 1


def test_margin_code_default_matches_shipped_config():
    """Drift pin, same contract as the capacity guard's mirror pin: the
    undeclared-key default in ml/history.py and the shipped config value
    must move together or the 'identical default' claim silently rots."""
    src = (_ROOT / "ml" / "history.py").read_text(encoding="utf-8")
    m = re.search(r'cfg\.get\("candidate_evict_margin_bars",\s*(\d+)\)', src)
    assert m, "ml/history.py no longer reads candidate_evict_margin_bars " \
              "via cfg.get(...) - re-point this pin"
    shipped = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))
    assert int(m.group(1)) == shipped["ml"]["candidate_evict_margin_bars"]


# --- defect B: restore truncates to a shrunk cap ---------------------------

def test_restore_truncates_oversized_pool_newest_first(tmp_path, caplog):
    """THE PLANT: 10 candidates persisted under cap 10, restored under
    cap 4. Pre-fix the pool stayed at 10 forever (register only holds
    size constant); the fix truncates to 4, keeping the OLDEST (head,
    closest to resolving) and logging ML-086 with the drop count."""
    wide_cfg = {"max_open_candidates": 10, "label_max_bars": HORIZON}
    wide = _labeler(tmp_path, wide_cfg, name="w.csv")
    feats = np.zeros(len(FEATURE_NAMES))
    times = [E + k * BAR_SECONDS for k in range(10)]
    for t in times:
        assert wide.register("ETH", "long", feats, 0.005, t) is True
    snap = wide.to_dict()

    narrow_cfg = {"max_open_candidates": 4, "label_max_bars": HORIZON}
    narrow = _labeler(tmp_path, narrow_cfg, name="n.csv")
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        narrow.restore(snap)
    assert len(narrow._cands) == 4, "shrunk cap must be enforced at restore"
    kept = [c["bar_time"] for c in narrow._cands]
    assert kept == times[:4], (
        "truncation must drop the NEWEST (register's own eviction "
        f"direction), keeping the head - got {kept}")
    assert "ML-086" in caplog.text and "6" in caplog.text


def test_restore_within_cap_is_untouched(tmp_path, caplog):
    """No overflow, no truncation, no ML-086 - identical-default
    behavior preservation for every pool that fits."""
    lab = _labeler(tmp_path, {"max_open_candidates": 10,
                              "label_max_bars": HORIZON}, name="a.csv")
    feats = np.zeros(len(FEATURE_NAMES))
    for k in range(3):
        assert lab.register("ETH", "long", feats, 0.005,
                            E + k * BAR_SECONDS) is True
    snap = lab.to_dict()
    lab2 = _labeler(tmp_path, {"max_open_candidates": 10,
                               "label_max_bars": HORIZON}, name="b2.csv")
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        lab2.restore(snap)
    assert len(lab2._cands) == 3
    assert "ML-086" not in caplog.text


# --- config guard: the knob is validated, the shipped pairing is clean -----

def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_guard_margin_type_and_bounds_fatals():
    for bad in (-1, 2.5, True, "wide", 8641):
        cfg = {"system": {"dry_run": True},
               "ml": {"candidate_evict_margin_bars": bad}}
        assert [m for m in _fatals(cfg)
                if "candidate_evict_margin_bars" in m], f"{bad!r} must FATAL"


def test_guard_margin_in_bounds_is_clean():
    for ok in (0, 24, 8640):
        cfg = {"system": {"dry_run": True},
               "ml": {"candidate_evict_margin_bars": ok}}
        assert not [m for m in _fatals(cfg)
                    if "candidate_evict_margin_bars" in m], \
            f"{ok!r} must validate clean"


def test_shipped_config_declares_margin_and_validates():
    cfg = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))
    assert "candidate_evict_margin_bars" in cfg["ml"], \
        "the knob is config-owned - the shipped file must declare it"
    assert not [m for sev, m in validate(cfg)
                if "candidate_evict_margin_bars" in m]
