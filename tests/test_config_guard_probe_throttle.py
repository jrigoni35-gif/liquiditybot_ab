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

Task 4 (#103) regime-coverage hold: corpus_decay.regime_floor_live in
[0, corpus_target_live] FATAL - 0 disables the term (byte-identical P3);
above corpus_target_live the per-regime floor could never be crossed.
Coherence WARN: regime_floor_live x 5 regime classes > until_live_rows x
floor_frac means the regime floor would still dominate the decay it
modifies even once every regime is equally represented at graduation.
"""
import json
from pathlib import Path

from core.config_guard import validate

_ROOT = Path(__file__).resolve().parents[1]


def _cfg(max_probe_share=0.35, probe_share_window=40,
        corpus_target_live=300, floor_frac=0.25, deploy_min_oof=30,
        until_live_rows=1200, regime_floor_live=60):
    return {"system": {"dry_run": True},
           "ml": {"exploration": {"max_probe_share": max_probe_share,
                                  "probe_share_window": probe_share_window,
                                  "until_live_rows": until_live_rows,
                                  "corpus_decay": {
                                      "corpus_target_live": corpus_target_live,
                                      "floor_frac": floor_frac,
                                      "regime_floor_live": regime_floor_live}},
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


# --- corpus_decay.regime_floor_live (Task 4, #103) --------------------------
def test_regime_floor_live_negative_is_fatal():
    cfg = _cfg(regime_floor_live=-1)
    assert any("regime_floor_live" in m for m in _fatals(cfg))


def test_regime_floor_live_above_corpus_target_live_is_fatal():
    cfg = _cfg(corpus_target_live=300, regime_floor_live=301)
    assert any("regime_floor_live" in m for m in _fatals(cfg))


def test_regime_floor_live_zero_boundary_not_fatal():
    # 0 disables the term (byte-identical P3 behavior) - a valid boundary
    cfg = _cfg(regime_floor_live=0)
    assert not any("regime_floor_live" in m for m in _fatals(cfg))


def test_regime_floor_live_equal_to_corpus_target_live_not_fatal():
    cfg = _cfg(corpus_target_live=300, regime_floor_live=300)
    assert not any("regime_floor_live" in m for m in _fatals(cfg))


def test_regime_floor_live_shipped_default_not_fatal():
    cfg = _cfg(corpus_target_live=300, regime_floor_live=60)
    assert not any("regime_floor_live" in m for m in _fatals(cfg))


# --- regime_floor_live x 5 vs until_live_rows x floor_frac coherence WARN ---
def test_warn_when_regime_floor_dominates_the_decay_it_modifies():
    # regime_floor_live x 5 = 500 > until_live_rows x floor_frac = 300 -
    # the regime floor would still dominate even at full regime coverage.
    cfg = _cfg(regime_floor_live=100, until_live_rows=1200, floor_frac=0.25)
    assert any("regime_floor_live" in m for m in _warns(cfg))


def test_no_warn_when_regime_floor_coherence_holds_at_the_shipped_boundary():
    # shipped: 60 x 5 = 300 == 1200 x 0.25 = 300 - boundary is coherent
    cfg = _cfg(regime_floor_live=60, until_live_rows=1200, floor_frac=0.25)
    assert not any("regime_floor_live" in m for m in _warns(cfg))


def test_no_warn_when_regime_floor_well_below_the_coherence_bound():
    cfg = _cfg(regime_floor_live=10, until_live_rows=1200, floor_frac=0.25)
    assert not any("regime_floor_live" in m for m in _warns(cfg))


# --- drought_floor (Task 1, F0b livelock repair, SZ-048) --------------------
def test_drought_floor_hours_below_one_is_fatal():
    cfg = _cfg()
    cfg["ml"]["exploration"]["drought_floor"] = {
        "enabled": True, "drought_hours": 0.5, "min_spacing_hours": 2.0}
    assert any("drought_floor.drought_hours" in m for m in _fatals(cfg))


def test_drought_floor_spacing_below_half_hour_is_fatal():
    cfg = _cfg()
    cfg["ml"]["exploration"]["drought_floor"] = {
        "enabled": True, "drought_hours": 8.0, "min_spacing_hours": 0.1}
    assert any("drought_floor.min_spacing_hours" in m for m in _fatals(cfg))


def test_drought_floor_rate_exceeding_label_horizon_is_fatal():
    # derivation: floor admits at most drought_hours/min_spacing_hours probes
    # per drought span; spacing shorter than horizon/8 would exceed the
    # <= K-per-8h-label-horizon bound the C2 verdict requires (K=4 default
    # -> spacing >= 2.0h when horizon is 8h)
    cfg = _cfg()
    cfg["ml"]["exploration"]["drought_floor"] = {
        "enabled": True, "drought_hours": 8.0, "min_spacing_hours": 0.9}
    assert any("min_spacing_hours" in m for m in _fatals(cfg))


def test_drought_floor_half_hour_spacing_floor_is_isolated():
    # ISOLATES the explicit 0.5h spacing floor: at drought_hours=2.0 the
    # derived bound (drought_hours/8) is only 0.25, so 0.3 clears it and
    # ONLY the standalone >= 0.5 check can fatal here. This test fails
    # if that check alone is deleted - the other spacing tests above all
    # trip the derived bound too and cannot catch that deletion.
    cfg = _cfg()
    cfg["ml"]["exploration"]["drought_floor"] = {
        "enabled": True, "drought_hours": 2.0, "min_spacing_hours": 0.3}
    assert any("min_spacing_hours" in m for m in _fatals(cfg))


def test_drought_floor_defaults_are_coherent():
    # the shipped defaults must produce zero fatals/warnings on this block
    cfg = _cfg()
    assert not [m for m in _fatals(cfg) if "drought_floor" in m]
    assert not [m for m in _warns(cfg) if "drought_floor" in m]


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
    # Task 4 (#103): corpus_target_live (300) / 5 regime classes = 60
    assert ex["corpus_decay"]["regime_floor_live"] == 60
    # F0b drought floor (Task 1, SZ-048) documented defaults
    assert ex["drought_floor"]["enabled"] is True
    assert ex["drought_floor"]["drought_hours"] == 8.0
    assert ex["drought_floor"]["min_spacing_hours"] == 2.0
    fatals = [m for sev, m in validate(shipped) if sev == "FATAL"]
    assert not any("probe" in m or "corpus_decay" in m for m in fatals)
    # 300 >= deploy_min_oof (30) - shipped defaults must NOT trip the WARN
    warns = [m for sev, m in validate(shipped) if sev == "WARN"]
    assert not any("corpus_target_live" in m for m in warns)
    assert not any("until_live_rows" in m for m in warns)
