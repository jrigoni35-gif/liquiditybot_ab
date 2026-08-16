"""Candidate-queue capacity: the Little's-law coherence guard and the
eviction path it exists to keep dormant (2026-08-16 label-throughput fix).

The pool is a Little's-law queue: slots required = offered arrivals/h x
slot residence, and with multi_horizon shadows enabled residence is the
FULL label horizon for EVERY candidate. ml.max_open_candidates=200 was
sized for the 8h horizon and survived the 24->432 (36h) migration
unresized; measured 2026-08-16 on outputs/signal_history.csv candidate-id
seq spans (era triple_barrier_h432): peak 659 registrations inside one 36h
window vs a 200 cap, and 84% of registrations on fully-resolved launch
spans produced no labeled row. The guard makes that mis-sizing FATAL
instead of a silent training-sample bias toward quiet hours.

Every guard test here plants the defect and watches the check FIRE - a
guard that has never failed on a planted defect is unverified.
"""
import json
import math
import re
from pathlib import Path

import numpy as np

from core.config_guard import (_CAND_QUEUE_CODE_DEFAULT,
                               _CAND_REF_PEAK_ARRIVALS_PER_H, validate)
from ml.features import FEATURE_NAMES
from ml.history import CandidateLabeler, HistoryStore

_ROOT = Path(__file__).resolve().parents[1]


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def _shipped():
    return json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))


def _demand(lmb):
    return math.ceil(_CAND_REF_PEAK_ARRIVALS_PER_H * lmb * 300.0 / 3600.0)


def _labeler(tmp_path, cfg):
    return CandidateLabeler(HistoryStore(str(tmp_path / "h.csv")), cfg)


# --- runtime: config lift + eviction semantics -----------------------------

def test_cap_is_config_owned_and_default_mirrors_guard(tmp_path):
    lab = _labeler(tmp_path, {"max_open_candidates": 1200})
    assert lab.max_candidates == 1200
    bare = _labeler(tmp_path, {})
    assert bare.max_candidates == _CAND_QUEUE_CODE_DEFAULT


def test_code_default_pin_against_ml_history_source():
    """The guard sizes the cap that will ACTUALLY run when the key is
    undeclared, so its mirrored default must track ml/history.py's own
    fallback literal - this regex pin fails the moment either side moves
    alone (the same contract as the era/overfit floor mirror pin)."""
    src = (_ROOT / "ml" / "history.py").read_text(encoding="utf-8")
    m = re.search(r'cfg\.get\("max_open_candidates",\s*(\d+)\)', src)
    assert m, "ml/history.py no longer reads max_open_candidates via " \
              "cfg.get(...) - re-point the guard mirror"
    assert int(m.group(1)) == _CAND_QUEUE_CODE_DEFAULT


def test_eviction_fires_at_cap_and_pops_newest_pending(tmp_path):
    """Plant the saturation: 4 registrations into a 3-slot pool. The 4th
    append must evict the NEWEST pending (seq 3) and never the head (seq 1,
    the candidate closest to its label horizon)."""
    lab = _labeler(tmp_path, {"max_open_candidates": 3,
                              "label_max_bars": 96})
    feats = np.zeros(len(FEATURE_NAMES))
    for k in range(4):                       # distinct bars: dedup passes
        assert lab.register("BTC", "long", feats, 0.005, k * 300) is True
    assert len(lab._cands) == 3, "cap must hold"
    seqs = sorted(int(c["id"].rsplit("-", 1)[1]) for c in lab._cands)
    assert seqs == [1, 2, 4], (
        f"newest-pending eviction must keep [1, 2, 4], got {seqs} - "
        f"popping the head kills the about-to-ripen candidate")


# --- guard: the planted incoherence must FATAL -----------------------------

def test_old_shipped_shape_is_the_planted_defect_and_fatals():
    """The exact pre-fix production shape: cap 200, 432-bar horizon,
    shadows on. The guard exists because this shipped silently."""
    cfg = _shipped()
    cfg["ml"]["max_open_candidates"] = 200
    msgs = [m for m in _fatals(cfg) if "max_open_candidates" in m]
    assert msgs, "cap 200 vs 36h horizon with shadow retention must FATAL"
    msg = msgs[0]
    assert "200" in msg and "432" in msg and str(_demand(432)) in msg, \
        "the message must name the cap, the horizon, and the demand"
    assert "label_max_bars" in msg
    assert "do NOT shorten label_max_bars" in msg, \
        "the message must foreclose the wrong fix"


def test_boundary_cap_at_demand_is_clean_one_below_fatals():
    """Mutation pin on the comparison: exactly-at-demand passes, one slot
    under fails - so the inequality can never silently flip or widen."""
    d = _demand(432)
    cfg = _shipped()
    cfg["ml"]["max_open_candidates"] = d
    assert not [m for m in _fatals(cfg) if "max_open_candidates" in m]
    cfg["ml"]["max_open_candidates"] = d - 1
    assert [m for m in _fatals(cfg) if "max_open_candidates" in m]


def test_undeclared_cap_checks_the_code_default_that_will_run():
    """A config that declares the 432 horizon but never declares the cap
    runs ml/history.py's 200 fallback - the guard must size THAT, not
    silently skip (the guard reports on what will actually run)."""
    cfg = _shipped()
    del cfg["ml"]["max_open_candidates"]
    msgs = [m for m in _fatals(cfg) if "max_open_candidates" in m]
    assert msgs and "code default" in msgs[0]


def test_shadows_off_degrades_to_warn():
    """Without shadow retention, early labels release slots before the
    horizon, so under-capacity is market-dependent rather than
    structural: WARN, not FATAL, same numbers."""
    cfg = _shipped()
    cfg["ml"]["max_open_candidates"] = 200
    cfg["ml"]["multi_horizon"]["enabled"] = False
    assert not [m for m in _fatals(cfg) if "max_open_candidates" in m]
    assert [m for m in _warns(cfg) if "max_open_candidates" in m]


def test_shipped_config_is_coherent_and_clears_demand():
    """The shipped cap must clear the 36h-horizon demand with headroom -
    and produce neither FATAL nor WARN from this check."""
    cfg = _shipped()
    assert cfg["ml"]["max_open_candidates"] >= _demand(432)
    assert not [m for m in _fatals(cfg) if "max_open_candidates" in m]
    assert not [m for m in _warns(cfg) if "max_open_candidates" in m]


def test_short_horizon_leaves_the_old_cap_coherent():
    """200 was a CORRECT size for the 8h era (demand at 96 bars is under
    200) - the guard must not rewrite that history: this check is about
    the pairing, not about the number 200."""
    assert _demand(96) <= 200
    cfg = _shipped()
    cfg["ml"]["max_open_candidates"] = 200
    cfg["ml"]["label_max_bars"] = 96
    # 96 < time_stop.max_bars_no_progress (480): no clock inversion; and
    # shipped shadow horizons exceed 96, so drop them to keep the fixture
    # about THIS check
    cfg["ml"]["multi_horizon"]["horizons_bars"] = [24, 48, 96]
    assert not [m for m in _fatals(cfg) if "max_open_candidates" in m]


# --- guard: bounds on the key itself ---------------------------------------

def test_cap_bounds_and_type_fatals():
    for bad in (0, 7, 10001, True, 2.5, "many"):
        cfg = {"system": {"dry_run": True},
               "ml": {"max_open_candidates": bad}}
        assert [m for m in _fatals(cfg) if "max_open_candidates" in m], \
            f"{bad!r} must FATAL"


def test_cap_alone_in_bounds_is_clean_without_declared_horizon():
    """A fragment declaring only a sane cap makes no horizon claim - the
    coherence check must not fire through a defaulted horizon it never
    opted into (house scoping discipline)."""
    cfg = {"system": {"dry_run": True}, "ml": {"max_open_candidates": 8}}
    assert not [m for m in _fatals(cfg) if "max_open_candidates" in m]
