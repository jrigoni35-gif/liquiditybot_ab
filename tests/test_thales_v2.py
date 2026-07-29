"""THALES.V2 — evidence-weighted detector reliability (vindication loop).

V1 composed detectors with FIXED config gains: hand-crafted priors that
nothing ever validated against outcomes. V2 grades every graded trade's
firing detectors at close and scales each gain by the normalized LIFT of
the detector's vindication WilsonLCB90 over the contemporaneous outcome
BASE RATE (the __base__ ledger — 2026-07-29 A-1 correction; the original
max(0, 2*LCB - 1) coin-flip null muted honest up-detectors on a ~16%-win
stream while rewarding no-skill down-detectors). Contract under test:
  - cold start (< min_fired grades on EITHER ledger) is EXACTLY V1:
    weight 1.0, no annotation, identical multiplier;
  - a detector with no lift over the base rate is muted (weight 0: no
    shade contribution) but KEEPS BEING GRADED (probation, not a life
    sentence — the dead-mute fix);
  - a proven detector keeps MOST of its gain but never exceeds it
    (attenuate-only, honest Wilson humility);
  - note_outcome vindication accounting: "up" advice graded by wins,
    "down" advice by losses; every call also grades __base__ (one per
    closed trade, fired-or-not); junk never raises;
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
    # A-1: the null is the OUTCOME BASE RATE, not 0.5. Without a
    # populated __base__ ledger the prior keeps ruling even past
    # min_fired (no honest null exists yet).
    eng._rel["grid"] = {"fired": 40, "vindicated": 20}
    assert eng._rel_weight("grid") == 1.0        # no base ledger: prior
    # with a 50% base rate the old coin-flip numbers reproduce exactly:
    # (LCB - 0.5)/(1 - 0.5) == 2*LCB - 1
    eng._rel["__base__"] = {"fired": 100, "vindicated": 50}
    assert eng._rel_weight("grid") == 0.0        # at base rate: muted
    eng._rel["grid"] = {"fired": 40, "vindicated": 40}
    w = eng._rel_weight("grid")
    assert 0.85 < w < 1.0                        # proven, still attenuated
    off = ThalesEngine(_cfg(reliability={"enabled": False}))
    off._rel["grid"] = {"fired": 40, "vindicated": 20}
    assert off._rel_weight("grid") == 1.0        # kill switch: pure V1


def test_rel_weight_base_rate_null_a1_worked_example():
    """The A-1 worked example from the 2026-07-29 THALES audit, pinned:
    at the measured 15.8% base win rate (40/253), an 'up' detector with
    a genuine 2x win-rate lift (32% when firing) must keep a voice,
    while a zero-information 'down' detector (vindicated at the 84.2%
    base LOSS rate) must be muted. Under the old 0.5 coin-flip null the
    verdicts were exactly inverted (0.000 and ~0.443)."""
    eng = ThalesEngine(_cfg())
    eng._rel["__base__"] = {"fired": 253, "vindicated": 40}   # 15.8% wins
    # 2x-lift up detector: 32% wins over 50 grades
    eng._rel["grid"] = {"fired": 50, "vindicated": 16}
    w_up = eng._rel_weight("grid", "up")
    assert w_up > 0.0, "a genuine 2x lift must not be muted"
    # no-skill down detector: vindicated exactly at the base loss rate
    eng._rel["stop_prox"] = {"fired": 50, "vindicated": 42}   # 84%
    assert eng._rel_weight("stop_prox", "down") == 0.0, (
        "vindication at the base loss rate is zero information")
    # and a down detector genuinely better than the base loss rate keeps
    # a voice (98% vindicated vs 84.2% null)
    eng._rel["stop_prox"] = {"fired": 50, "vindicated": 49}
    assert eng._rel_weight("stop_prox", "down") > 0.0


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
def test_unvindicated_detector_loses_its_voice_but_keeps_being_graded():
    eng = ThalesEngine(_cfg())
    # 40 graded losses on "up" advice against a mixed base (30% wins on
    # closes where grid never fired) - the base ledger is what makes the
    # muting honest: grid wins 0% when the population wins 30%.
    for _ in range(40):
        eng.note_outcome([("grid", "up")], won=False)
    for i in range(40):
        eng.note_outcome([], won=(i % 10 < 3))
    now = _primed(eng)
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5, "trend", now)
    assert out.mult == 1.0                       # muted: no contribution
    # dead-mute fix (2026-07-29): a muted detector stays in the GRADING
    # ledger - w=0 is probation, not a life sentence. Pre-fix, fired
    # stopped accruing at w=0 and the detector could never redeem itself.
    assert ("grid", "up") in out.fired
    assert any("(w=0.00)" in n for n in out.notes)


def test_vindicated_detector_keeps_attenuated_gain():
    eng = ThalesEngine(_cfg())
    # grid wins 100% over 40 grades while the surrounding population
    # (60 closes with no detector fired) wins 0% - maximal honest lift
    for _ in range(40):
        eng.note_outcome([("grid", "up")], won=True)
    for _ in range(60):
        eng.note_outcome([], won=False)
    now = _primed(eng)
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5, "trend", now)
    w = eng._rel_weight("grid", "up")
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
    eng.note_outcome([], won=False)              # empty list grades base only
    # __base__ counts ONE grade per closed trade (5 calls above), and
    # vindicated == wins regardless of what fired
    assert eng._rel["__base__"] == {"fired": 5, "vindicated": 3}


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
    for _ in range(60):                          # honest base: 40% wins
        eng.note_outcome([], won=False)
    st = eng.status(0.0)
    rel = st["reliability"]
    assert rel["grid"]["fired"] == 40
    assert 0.85 < rel["grid"]["weight"] < 1.0
    # the base ledger is surfaced separately, never as a fake detector
    assert "__base__" not in rel
    assert st["reliability_base"] == {"fired": 100, "vindicated": 40}


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
