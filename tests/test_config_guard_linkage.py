"""config_guard: ml.linkage bounds (Task 6, T2.4 FS-EM record linkage).

posterior_threshold outside [0.5, 0.999] FATAL - below 0.5 would link
majority-non-match patterns (a pattern where more than half the observed
pairs are non-matches counted as "linked"); 1.0 links nothing (no
pattern's posterior can equal or exceed the max value it can even hit
short of certainty). seed must be a non-negative int - it drives the
Dirichlet init `np.random.default_rng(seed)`, so a non-castable or
negative value would crash fit() with a confusing numpy error far from
the actual misconfiguration.
"""
from core.config_guard import validate


def _cfg(posterior_threshold=0.9, seed=7):
    return {"system": {"dry_run": True},
           "ml": {"linkage": {"posterior_threshold": posterior_threshold,
                               "seed": seed}}}


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_shipped_default_no_fatal():
    assert not any("linkage" in m for m in _fatals(_cfg()))


def test_default_absent_linkage_no_fatal():
    assert not any("linkage" in m
                  for m in _fatals({"system": {"dry_run": True}}))


def test_threshold_below_0_5_is_fatal():
    fatals = _fatals(_cfg(posterior_threshold=0.3))
    assert any("linkage.posterior_threshold" in m for m in fatals)


def test_threshold_0_9_is_clean():
    assert not any("linkage" in m for m in _fatals(_cfg(posterior_threshold=0.9)))


def test_threshold_1_0_is_fatal():
    fatals = _fatals(_cfg(posterior_threshold=1.0))
    assert any("linkage.posterior_threshold" in m for m in fatals)


def test_seed_negative_is_fatal():
    fatals = _fatals(_cfg(seed=-1))
    assert any("linkage.seed" in m for m in fatals)
