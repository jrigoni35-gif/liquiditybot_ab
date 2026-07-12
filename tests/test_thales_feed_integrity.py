"""TH-014 feed_integrity: THALES shades an asset's entry confidence DOWN
when its book feed shows a sustained rate of missing/sanitize-rejected data
(a hostile or unreliable venue), the market-behaviour complement to the
session's boundary hardening. Detect-and-shade only; shadow-first."""
from strategies.thales import ThalesEngine

CFG = {
    "enabled": True,
    "influence": "advise",           # so the shade actually applies in-test
    "max_conf_shade": 1.5,
    "feed_integrity": {"window": 40, "min_obs": 20,
                       "dirty_frac_thr": 0.25, "gain": 0.5},
}


def _feed(engine, asset, clean_seq):
    for i, clean in enumerate(clean_seq):
        engine.observe_feed_health(asset, clean, now=float(i))


def test_clean_feed_does_not_shade():
    t = ThalesEngine(CFG)
    _feed(t, "SUI", [True] * 30)
    out = t.shade_confidence("SUI", "long", urgency=0.0, confidence=0.6,
                             macro_label="range", now=100.0)
    assert abs(out.would_mult - 1.0) < 1e-9      # nothing to distrust


def test_dirty_feed_shades_down():
    t = ThalesEngine(CFG)
    # 50% dirty over 30 obs, well past the 25% threshold
    _feed(t, "MINA", [True, False] * 15)
    out = t.shade_confidence("MINA", "long", urgency=0.0, confidence=0.6,
                             macro_label="range", now=100.0)
    assert out.would_mult < 1.0                  # shaded DOWN, never up
    assert out.confidence < 0.6
    assert any("TH-014" in n for n in out.notes)


def test_below_min_obs_stays_neutral():
    t = ThalesEngine(CFG)
    _feed(t, "ARB", [False] * 10)                # dirty but < min_obs=20
    out = t.shade_confidence("ARB", "long", urgency=0.0, confidence=0.6,
                             macro_label="range", now=100.0)
    assert abs(out.would_mult - 1.0) < 1e-9      # not enough evidence yet


def test_shadow_mode_records_but_does_not_apply():
    t = ThalesEngine({**CFG, "influence": "shadow"})
    _feed(t, "FLOW", [True, False] * 15)
    out = t.shade_confidence("FLOW", "long", urgency=0.0, confidence=0.6,
                             macro_label="range", now=100.0)
    assert out.would_mult < 1.0                  # counterfactual computed
    assert out.confidence == 0.6                 # but confidence untouched


def test_observe_is_fail_safe_when_inactive():
    t = ThalesEngine({**CFG, "enabled": False})
    t.observe_feed_health("SUI", False, now=1.0)   # must not raise
    out = t.shade_confidence("SUI", "long", 0.0, 0.6, "range", 2.0)
    assert out.confidence == 0.6
