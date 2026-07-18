"""THALES.V2 — evidence-weighted detector reliability (vindication loop).

V1 composed detectors with FIXED config gains: hand-crafted priors that
nothing ever validated against outcomes. V2 grades every advise-mode
trade's firing detectors at close and scales each gain by
max(0, 2*WilsonLCB90 - 1). Contract under test:
  - cold start (< min_fired grades) is EXACTLY V1: weight 1.0, no
    annotation, identical multiplier;
  - a detector that cannot beat a coin flip out-of-sample is muted
    (weight 0: no shade contribution, no new fired entry);
  - a proven detector keeps MOST of its gain but never exceeds it
    (attenuate-only, honest Wilson humility);
  - note_outcome vindication accounting: "up" advice graded by wins,
    "down" advice by losses; junk never raises;
  - reliability ledger round-trips to/from dict; malformed restores
    degrade to a warning, never raise;
  - feed integrity stays UNWEIGHTED (safety shade, exempt from grading);
  - config_guard rejects a noise-level min_fired.
"""
from core.config_guard import validate
from strategies.thales import ThalesEngine

CFG = {
    "enabled": True,
    "influence": "advise",
    "max_conf_shade": 1.15,
    "reliability": {"enabled": True, "min_fired": 20},
    "grid": {"min_levels": 6, "skip_top": 2, "score_thr": 0.55,
             "gain": 0.5, "ewma_alpha": 0.15},
    "metronome": {"min_events": 8, "window_events": 64,
                  "min_interval_sec": 8.0, "score_thr": 0.6,
                  "gain": 0.4, "urgency_min": 0.5},
    "clockwork": {"bucket_minutes": 60, "min_obs": 24, "z_thr": 2.33,
                  "gain": 0.06, "max_history_bars": 4032},
    "stops": {"swing_lookback": 48, "zone_tol_pct": 0.15,
              "pre_gain": 0.1, "post_gain": 0.1,
              "revert_decay_sec": 1800},
}


def _cfg(**over):
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in CFG.items()}
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def _primed(eng, asset="BTC", grid=0.75):
    """Steady observation cadence (no lapse), then a hot grid score.
    Mark sits OFF the round-number stop grid (100.37 is 0.37% from the
    100.0 magnet, beyond the 0.15% tolerance) so stop_prox stays quiet."""
    book = {"bids": [[100.27, 1.0]], "asks": [[100.47, 1.0]]}
    for k in range(6):
        eng.observe_fast(asset, book, 100.37, 1000.0 + 5 * k)
    eng._st(asset).grid_score = grid
    return 1030.0                                # a shade-time inside cadence


# ---------------------------------------------------------------------
# Wilson lower confidence bound
# ---------------------------------------------------------------------
def test_wilson_lcb_small_sample_humility():
    lcb = ThalesEngine._wilson_lcb
    assert lcb(0, 0) == 0.0
    assert 0.5 < lcb(3, 3) < 0.9                 # 3/3 is not "always right"
    assert lcb(30, 30) > lcb(3, 3)               # evidence tightens the bound
    assert lcb(0, 10) == 0.0                     # clamped at zero


def test_rel_weight_mapping():
    eng = ThalesEngine(_cfg())
    assert eng._rel_weight("grid") == 1.0        # unknown detector: prior
    eng._rel["grid"] = {"fired": 10, "vindicated": 0}
    assert eng._rel_weight("grid") == 1.0        # below min_fired: prior
    eng._rel["grid"] = {"fired": 40, "vindicated": 20}
    assert eng._rel_weight("grid") == 0.0        # coin flip: muted
    eng._rel["grid"] = {"fired": 40, "vindicated": 40}
    w = eng._rel_weight("grid")
    assert 0.85 < w < 1.0                        # proven, still attenuated
    off = ThalesEngine(_cfg(reliability={"enabled": False}))
    off._rel["grid"] = {"fired": 40, "vindicated": 20}
    assert off._rel_weight("grid") == 1.0        # kill switch: pure V1


# ---------------------------------------------------------------------
# cold start == V1, exactly
# ---------------------------------------------------------------------
def test_cold_start_shade_identical_to_v1():
    v2 = ThalesEngine(_cfg())
    v1 = ThalesEngine(_cfg(reliability={"enabled": False}))
    now = _primed(v2)
    _primed(v1)
    a = v2.shade_confidence("BTC", "long", 1.0, 0.5, "trend", now)
    b = v1.shade_confidence("BTC", "long", 1.0, 0.5, "trend", now)
    assert a.mult == b.mult == 1.0 + 0.5 * (0.75 - 0.55)
    assert ("grid", "up") in a.fired
    assert not any("(w=" in n for n in a.notes)  # no annotation at weight 1


# ---------------------------------------------------------------------
# vindication loop end-to-end through the public API
# ---------------------------------------------------------------------
def test_unvindicated_detector_loses_its_voice():
    eng = ThalesEngine(_cfg())
    for _ in range(40):                          # 40 graded losses on "up"
        eng.note_outcome([("grid", "up")], won=False)
    now = _primed(eng)
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5, "trend", now)
    assert out.mult == 1.0                       # muted: no contribution
    assert out.fired == []                       # a muted voice is not refired
    assert any("(w=0.00)" in n for n in out.notes)


def test_vindicated_detector_keeps_attenuated_gain():
    eng = ThalesEngine(_cfg())
    for _ in range(40):
        eng.note_outcome([("grid", "up")], won=True)
    now = _primed(eng)
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5, "trend", now)
    w = eng._rel_weight("grid")
    assert abs(out.mult - (1.0 + w * 0.5 * 0.2)) < 1e-12
    assert 1.0 < out.mult < 1.0 + 0.5 * 0.2      # attenuate-only, never amplify
    assert ("grid", "up") in out.fired


def test_note_outcome_accounting_and_junk_safety():
    eng = ThalesEngine(_cfg())
    eng.note_outcome([("grid", "up"), ("stop_prox", "down")], won=True)
    assert eng._rel["grid"] == {"fired": 1, "vindicated": 1}
    assert eng._rel["stop_prox"] == {"fired": 1, "vindicated": 0}
    eng.note_outcome([("grid", "up"), ("stop_prox", "down")], won=False)
    assert eng._rel["grid"] == {"fired": 2, "vindicated": 1}
    assert eng._rel["stop_prox"] == {"fired": 2, "vindicated": 1}
    # junk: wrong shapes, unknown advice, None — ignored, never raised
    eng.note_outcome([("grid",), "junk", ("x", "sideways"), None, 7], True)
    assert eng._rel["grid"]["fired"] == 2
    eng.note_outcome(None, True)                 # no firings at all


# ---------------------------------------------------------------------
# shadow mode: engine still reports fired (main.py drops it), conf intact
# ---------------------------------------------------------------------
def test_shadow_mode_reports_fired_without_touching_confidence():
    eng = ThalesEngine(_cfg(influence="shadow"))
    now = _primed(eng)
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5, "trend", now)
    assert out.confidence == 0.5 and out.mult == 1.0
    assert ("grid", "up") in out.fired           # advice channel gates in main


# ---------------------------------------------------------------------
# feed integrity is exempt from the reinterview
# ---------------------------------------------------------------------
def test_feed_integrity_shade_ignores_reliability_ledger():
    eng = ThalesEngine(_cfg(feed_integrity={"window": 10, "min_obs": 5,
                                            "dirty_frac_thr": 0.25,
                                            "gain": 0.5}))
    eng._rel["feed"] = {"fired": 40, "vindicated": 0}   # hostile ledger
    now = _primed(eng, grid=0.0)
    for _ in range(10):
        eng.observe_feed_health("BTC", clean=False, now=now)
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5, "range", now)
    assert out.mult < 1.0                        # still shades DOWN, unweighted
    assert out.fired == []                       # and is never graded


# ---------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------
def test_reliability_round_trip_and_malformed_restore():
    a = ThalesEngine(_cfg())
    for _ in range(40):
        a.note_outcome([("grid", "up")], won=False)
    b = ThalesEngine(_cfg())
    b.reliability_restore(a.reliability_to_dict())
    assert b._rel_weight("grid") == 0.0          # muting survives a restart
    c = ThalesEngine(_cfg())
    c.reliability_restore({"grid": "nope"})      # malformed: warn, not raise
    c.reliability_restore(None)
    assert c._rel_weight("grid") == 1.0


def test_status_exposes_ledger_with_weights():
    eng = ThalesEngine(_cfg())
    for _ in range(40):
        eng.note_outcome([("grid", "up")], won=True)
    rel = eng.status(0.0)["reliability"]
    assert rel["grid"]["fired"] == 40
    assert 0.85 < rel["grid"]["weight"] < 1.0


# ---------------------------------------------------------------------
# config_guard
# ---------------------------------------------------------------------
def test_guard_rejects_noise_level_min_fired():
    fatals = [m for s, m in validate(
        {"thales": {"enabled": True,
                    "reliability": {"min_fired": 2}}}) if s == "FATAL"]
    assert any("min_fired" in m for m in fatals)
    clean = [m for s, m in validate(
        {"thales": {"enabled": True,
                    "reliability": {"min_fired": 20}}}) if s == "FATAL"]
    assert not any("min_fired" in m for m in clean)
