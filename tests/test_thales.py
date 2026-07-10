"""THALES lazy-bot insecurity model (strategies/thales.py, docs/THALES.md).

Detector bank over public books/candles with a bounded advice channel.
Contract under test:
  - each detector fires on its synthetic footprint and stays quiet on
    noise (grid ladders, clock-driven MM cadence, significance-gated
    time-of-day flow, stop-cluster sweeps);
  - shadow mode NEVER changes confidence (counterfactual recorded);
  - advise mode shading is clamped to [1/max_conf_shade, max_conf_shade]
    no matter how hot the detectors run;
  - garbage inputs degrade to neutral, never raise;
  - config_guard rejects incoherent thales configs (unknown influence,
    disabled+advise, unclamped shade, disarmed significance gate).
"""
import math

import numpy as np

from core.config_guard import validate
from strategies.thales import ThalesEngine

BASE_CFG = {
    "enabled": True,
    "influence": "advise",
    "max_conf_shade": 1.15,
    "grid": {"min_levels": 6, "skip_top": 2, "score_thr": 0.55,
             "gain": 0.5, "ewma_alpha": 0.15},
    "metronome": {"min_events": 8, "window_events": 64,
                  "min_interval_sec": 8.0, "score_thr": 0.6,
                  "gain": 0.4, "urgency_min": 0.5},
    "clockwork": {"bucket_minutes": 60, "min_obs": 3, "z_thr": 2.33,
                  "gain": 0.06, "max_history_bars": 4032},
    "stops": {"swing_lookback": 48, "zone_tol_pct": 0.15,
              "pre_gain": 0.1, "post_gain": 0.1,
              "revert_decay_sec": 1800},
}


def _cfg(**over):
    cfg = {k: (dict(v) if isinstance(v, dict) else v)
           for k, v in BASE_CFG.items()}
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def _ladder_book(mid=100.0, jitter=None, sizes=None):
    """Two churny touch levels then a textbook even grid each side."""
    rng = jitter or (lambda i: 0.0)
    sz = sizes or (lambda i: 0.7)
    bids = [[mid - 0.01, 0.3], [mid - 0.02, 0.4]]
    asks = [[mid + 0.01, 0.3], [mid + 0.02, 0.4]]
    for i in range(1, 9):
        bids.append([mid - 0.5 * i + rng(i), sz(i)])
        asks.append([mid + 0.5 * i + rng(i), sz(i)])
    return {"bids": bids, "asks": asks}


# ---------------------------------------------------------------------
# TH-010 grid ladder
# ---------------------------------------------------------------------
def test_grid_detector_fires_on_persistent_even_ladder():
    eng = ThalesEngine(_cfg())
    for k in range(14):
        eng.observe_fast("BTC", _ladder_book(), 100.0, 1000.0 + 5 * k)
    assert eng._st("BTC").grid_score > 0.6


def test_grid_detector_quiet_on_ragged_churning_book():
    eng = ThalesEngine(_cfg())
    rng = np.random.RandomState(7)
    for k in range(14):
        book = _ladder_book(jitter=lambda i: float(rng.uniform(-0.2, 0.2)),
                            sizes=lambda i: float(rng.uniform(0.1, 3.0)))
        eng.observe_fast("BTC", book, 100.0, 1000.0 + 5 * k)
    assert eng._st("BTC").grid_score < 0.3


# ---------------------------------------------------------------------
# TH-011 metronome MM
# ---------------------------------------------------------------------
def _run_metronome(eng, change_times, horizon=400):
    """Snapshot every 5s; flip the touch at the given times."""
    px = [100.0]
    for t in range(0, horizon, 5):
        if t in change_times:
            px[0] = 100.0 if px[0] != 100.0 else 100.1
        book = {"bids": [[px[0], 1.0]], "asks": [[px[0] + 0.2, 1.0]]}
        eng.observe_fast("ETH", book, 100.0, 5000.0 + t)


def test_metronome_fires_on_fixed_30s_refresh_cadence():
    eng = ThalesEngine(_cfg())
    _run_metronome(eng, set(range(30, 400, 30)))
    assert eng._st("ETH").metro_score > 0.8


def test_metronome_quiet_on_poisson_event_flow():
    eng = ThalesEngine(_cfg())
    rng = np.random.RandomState(11)
    t, times = 0, set()
    while t < 400:
        t += int(max(5, round(rng.exponential(25) / 5) * 5))
        times.add(t)
    _run_metronome(eng, times)
    assert eng._st("ETH").metro_score < 0.5


def test_metronome_neutral_when_churn_is_subinterval():
    # a change on EVERY snapshot is indistinguishable from our own
    # sampling clock - the detector must refuse to score it
    eng = ThalesEngine(_cfg())
    _run_metronome(eng, set(range(5, 400, 5)))
    assert eng._st("ETH").metro_score == 0.0


# ---------------------------------------------------------------------
# TH-012 clockwork flow (significance-gated)
# ---------------------------------------------------------------------
def _hourly_bars(days, hot_hour=None, hot_ret=0.8):
    bars, ts0 = [], 0
    for d in range(days):
        for h in range(24):
            ts = ts0 + d * 86400 + h * 3600
            o = 100.0
            if hot_hour is not None and h == hot_hour:
                c = o * (1 + hot_ret / 100.0)
            else:
                c = o * (1 + (0.05 if (d + h) % 2 else -0.05) / 100.0)
            bars.append({"ts": ts, "open": o, "close": c,
                         "high": max(o, c) + 0.2, "low": min(o, c) - 0.2})
    return bars


def test_clockwork_activates_only_inside_the_hot_bucket():
    eng = ThalesEngine(_cfg())
    eng.observe_candles("BTC", _hourly_bars(4, hot_hour=0), 400000.0)
    st = eng._st("BTC")
    score_hot, dir_hot = eng._clockwork(st, now=4 * 86400 + 600.0)
    score_cold, _ = eng._clockwork(st, now=4 * 86400 + 5 * 3600.0)
    assert score_hot > 0.0 and dir_hot == 1
    assert score_cold == 0.0


def test_clockwork_stays_zero_on_unstructured_noise():
    eng = ThalesEngine(_cfg())
    eng.observe_candles("BTC", _hourly_bars(4, hot_hour=None), 400000.0)
    st = eng._st("BTC")
    for h in range(24):
        score, _ = eng._clockwork(st, now=4 * 86400 + h * 3600 + 60.0)
        assert score == 0.0


# ---------------------------------------------------------------------
# TH-013 stop herding
# ---------------------------------------------------------------------
def test_sweep_and_revert_shades_the_fade_direction_up():
    eng = ThalesEngine(_cfg())
    bars = [{"ts": 1000.0 + 60 * i, "open": 100.0, "close": 100.0,
             "high": 100.5, "low": 99.5} for i in range(10)]
    # final bar sweeps the highs then closes back inside
    bars.append({"ts": 1000.0 + 600, "open": 100.2, "close": 100.0,
                 "high": 101.5, "low": 100.0})
    eng.observe_candles("BTC", bars, 2000.0)
    eng._st("BTC").marks.append((1660.0, 100.33))  # off round numbers
    fade = eng.shade_confidence("BTC", "short", 0.0, 0.5,
                                "range", now=1660.0)
    chase = eng.shade_confidence("BTC", "long", 0.0, 0.5,
                                 "range", now=1660.0)
    assert fade.mult > 1.0
    assert any("TH-013" in n for n in fade.notes)
    assert chase.mult <= 1.0                    # never boosts the chase


def test_stop_cluster_proximity_shades_down():
    eng = ThalesEngine(_cfg())
    eng._st("BTC").marks.append((100.0, 100.0))   # dead on a round number
    out = eng.shade_confidence("BTC", "long", 0.0, 0.5, "range", now=100.0)
    assert out.mult < 1.0
    assert any("not the lemming" in n for n in out.notes)


# ---------------------------------------------------------------------
# advice channel: clamps, shadow, off, garbage
# ---------------------------------------------------------------------
def _hot_engine(influence="advise", **over):
    """Engine with every detector running hot, gains cranked."""
    eng = ThalesEngine(_cfg(influence=influence,
                            grid={"gain": 10.0}, metronome={"gain": 10.0},
                            **over))
    for k in range(14):
        eng.observe_fast("BTC", _ladder_book(), 100.33, 1000.0 + 5 * k)
    st = eng._st("BTC")
    st.metro_score = 1.0
    return eng


def test_advise_mult_is_clamped_both_ways():
    eng = _hot_engine()
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5,
                               "trend", now=2000.0)
    assert 1.0 / 1.15 - 1e-9 <= out.mult <= 1.15 + 1e-9
    assert out.mult == 1.15                      # hot everything hits the cap
    assert math.isclose(out.confidence, 0.5 * 1.15)
    assert any("TH-020" in n for n in out.notes)


def test_shadow_records_counterfactual_but_never_touches_confidence():
    eng = _hot_engine(influence="shadow")
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5,
                               "trend", now=2000.0)
    assert out.confidence == 0.5
    assert out.mult == 1.0
    assert out.would_mult > 1.0
    assert any("TH-000" in n for n in out.notes)
    assert eng._counterfactuals and not eng._counterfactuals[-1]["applied"]


def test_disabled_engine_is_inert():
    eng = ThalesEngine(_cfg(enabled=False))
    eng.observe_fast("BTC", _ladder_book(), 100.0, 0.0)
    out = eng.shade_confidence("BTC", "long", 1.0, 0.7, "trend", now=0.0)
    assert out.confidence == 0.7 and out.mult == 1.0
    assert eng.status(0.0) == {"influence": "off"}
    assert not eng._assets                       # no state accrued


def test_garbage_inputs_never_raise():
    eng = ThalesEngine(_cfg())
    eng.observe_fast("BTC", None, float("nan"), 0.0)
    eng.observe_fast("BTC", {"bids": [["x", None]], "asks": []}, 0.0, 5.0)
    eng.observe_candles("BTC", [{"junk": 1}, None, {"ts": "bad"}], 10.0)
    out = eng.shade_confidence("BTC", "sideways", 0.0, 0.5, None, now=10.0)
    assert out.confidence == 0.5
    s = eng.status(10.0)
    assert s["influence"] == "advise"
    for scores in s["assets"].values():
        assert all(math.isfinite(v) for v in scores.values()
                   if isinstance(v, float))


# ---------------------------------------------------------------------
# config_guard coherence
# ---------------------------------------------------------------------
def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"]


def test_guard_rejects_unknown_influence():
    assert any("thales.influence" in m for m in _fatals(
        {"thales": {"enabled": True, "influence": "yolo"}}))


def test_guard_rejects_advise_while_disabled():
    assert any("incoherent" in m for m in _fatals(
        {"thales": {"enabled": False, "influence": "advise"}}))


def test_guard_rejects_unclamped_shade_and_disarmed_significance():
    assert any("max_conf_shade" in m for m in _fatals(
        {"thales": {"enabled": True, "max_conf_shade": 2.0}}))
    assert any("z_thr" in m for m in _fatals(
        {"thales": {"enabled": True, "clockwork": {"z_thr": 0.5}}}))
