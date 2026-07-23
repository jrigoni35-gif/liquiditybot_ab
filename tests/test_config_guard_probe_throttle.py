"""config_guard: ml.exploration probe-throttle bounds (Task 3, P3, SZ-047).

max_probe_share in (0, 1] FATAL - at 0 the share cap denies every probe
outright; 1 disables the cap. probe_share_window in [10, 500] FATAL -
below 10 admissions the share binds/releases on noise; above 500 it takes
too many admissions to react to a real change in probe demand.
corpus_decay.floor_frac in (0, 1] FATAL - at 0 a mature corpus fully
starves exploration; 1 disables the decay.

Coherence WARN: corpus_decay.corpus_target_live below ml.monitor.
deploy_min_oof means the throttle would already be decaying admission
below the model's own OOF deploy floor.
"""
import json
from pathlib import Path

from core.config_guard import validate

_ROOT = Path(__file__).resolve().parents[1]


def _cfg(max_probe_share=0.35, probe_share_window=40,
        corpus_target_live=300, floor_frac=0.25, deploy_min_oof=30,
        until_live_rows=1200):
    return {"system": {"dry_run": True},
           "ml": {"exploration": {"max_probe_share": max_probe_share,
                                  "probe_share_window": probe_share_window,
                                  "until_live_rows": until_live_rows,
                                  "corpus_decay": {
                                      "corpus_target_live": corpus_target_live,
                                      "floor_frac": floor_frac}},
                 "monitor": {"deploy_min_oof": deploy_min_oof}}}


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def test_shipped_defaults_no_fatal():
    assert not any("probe" in m or "corpus_decay" in m
                  for m in _fatals(_cfg()))


def test_default_absent_probe_throttle_no_fatal():
    assert not any("probe" in m or "corpus_decay" in m
                  for m in _fatals({"system": {"dry_run": True}}))


# --- max_probe_share -----------------------------------------------------
def test_max_probe_share_zero_is_fatal():
    assert any("max_probe_share" in m
              for m in _fatals(_cfg(max_probe_share=0.0)))


def test_max_probe_share_negative_is_fatal():
    assert any("max_probe_share" in m
              for m in _fatals(_cfg(max_probe_share=-0.1)))


def test_max_probe_share_above_1_is_fatal():
    assert any("max_probe_share" in m
              for m in _fatals(_cfg(max_probe_share=1.5)))


def test_max_probe_share_boundary_1_not_fatal():
    assert not any("max_probe_share" in m
                  for m in _fatals(_cfg(max_probe_share=1.0)))


# --- probe_share_window ---------------------------------------------------
def test_window_below_10_is_fatal():
    assert any("probe_share_window" in m
              for m in _fatals(_cfg(probe_share_window=9)))


def test_window_above_500_is_fatal():
    assert any("probe_share_window" in m
              for m in _fatals(_cfg(probe_share_window=501)))


def test_window_boundaries_10_and_500_not_fatal():
    assert not any("probe_share_window" in m
                  for m in _fatals(_cfg(probe_share_window=10)))
    assert not any("probe_share_window" in m
                  for m in _fatals(_cfg(probe_share_window=500)))


# --- corpus_decay.floor_frac -----------------------------------------------
def test_floor_frac_zero_is_fatal():
    assert any("floor_frac" in m for m in _fatals(_cfg(floor_frac=0.0)))


def test_floor_frac_negative_is_fatal():
    assert any("floor_frac" in m for m in _fatals(_cfg(floor_frac=-0.1)))


def test_floor_frac_above_1_is_fatal():
    assert any("floor_frac" in m for m in _fatals(_cfg(floor_frac=1.5)))


def test_floor_frac_boundary_1_not_fatal():
    assert not any("floor_frac" in m for m in _fatals(_cfg(floor_frac=1.0)))


# --- corpus_target_live coherence WARN -------------------------------------
def test_coherence_warn_when_corpus_target_below_deploy_min_oof():
    cfg = _cfg(corpus_target_live=20, deploy_min_oof=30)
    assert any("corpus_target_live" in m for m in _warns(cfg))


def test_no_coherence_warn_when_corpus_target_at_or_above_deploy_min_oof():
    cfg = _cfg(corpus_target_live=30, deploy_min_oof=30)
    assert not any("corpus_target_live" in m for m in _warns(cfg))
    cfg2 = _cfg(corpus_target_live=300, deploy_min_oof=30)
    assert not any("corpus_target_live" in m for m in _warns(cfg2))


# --- until_live_rows vs the decay's trickle floor (P3 review fix) ---------
# The corpus decay only reaches its floor_frac floor at
# live >= corpus_target_live / floor_frac. If until_live_rows hard-offs
# exploration before that point, the promised trickle-down-to-floor never
# happens - decay ranges only [1.0, corpus_target_live/until_live_rows]
# instead of [1.0, floor_frac].
def test_warn_when_until_live_rows_hard_offs_before_the_floor_binds():
    # threshold = 300 / 0.25 = 1200; 500 stops exploration long before that
    cfg = _cfg(until_live_rows=500, corpus_target_live=300, floor_frac=0.25)
    assert any("until_live_rows" in m for m in _warns(cfg))


def test_no_warn_when_until_live_rows_exactly_reaches_the_floor():
    # 1200 == 300 / 0.25 - the hard-off begins exactly where the decay's
    # trickle floor ends: reachable, not premature.
    cfg = _cfg(until_live_rows=1200, corpus_target_live=300, floor_frac=0.25)
    assert not any("until_live_rows" in m for m in _warns(cfg))


def test_no_warn_when_until_live_rows_exceeds_the_floor_threshold():
    cfg = _cfg(until_live_rows=1500, corpus_target_live=300, floor_frac=0.25)
    assert not any("until_live_rows" in m for m in _warns(cfg))


def test_warn_boundary_one_below_the_threshold():
    cfg = _cfg(until_live_rows=1199, corpus_target_live=300, floor_frac=0.25)
    assert any("until_live_rows" in m for m in _warns(cfg))


# --- shipped config ---------------------------------------------------------
def test_shipped_config_matches_documented_defaults():
    shipped = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))
    ex = shipped["ml"]["exploration"]
    assert ex["max_probe_share"] == 0.35
    assert ex["probe_share_window"] == 40
    assert ex["corpus_decay"]["corpus_target_live"] == 300
    assert ex["corpus_decay"]["floor_frac"] == 0.25
    # = corpus_target_live / floor_frac (300 / 0.25 = 1200) - the hard-off
    # begins exactly where the decay's trickle floor ends (P3 review fix).
    assert ex["until_live_rows"] == 1200
    fatals = [m for sev, m in validate(shipped) if sev == "FATAL"]
    assert not any("probe" in m or "corpus_decay" in m for m in fatals)
    # 300 >= deploy_min_oof (30) - shipped defaults must NOT trip the WARN
    warns = [m for sev, m in validate(shipped) if sev == "WARN"]
    assert not any("corpus_target_live" in m for m in warns)
    assert not any("until_live_rows" in m for m in warns)
