"""scripts/markov_ensemble.py + scripts/knowledge_plan.py - written before the
modules (TDD). The instrument must be honest before any partition is read."""
import numpy as np
import pytest

from scripts import knowledge_plan as kp
from scripts import markov_ensemble as me


def test_percentile_rank_is_past_only():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 600)
    r = me.percentile_rank_past(x, 100)
    assert np.all(np.isnan(r[:100]))
    for t in (150, 400, 599):
        assert r[t] == pytest.approx((x[t - 100:t] < x[t]).mean())
    y = x.copy()
    y[300:] = 99.0
    assert np.allclose(me.percentile_rank_past(y, 100)[:300], r[:300], equal_nan=True)


def test_random_partitions_are_reproducible_and_small():
    names = [f"v{i}" for i in range(11)]
    p1 = me.random_partition(np.random.default_rng(7), names)
    p2 = me.random_partition(np.random.default_rng(7), names)
    assert p1 == p2
    assert 1 <= len(p1["vars"]) <= 2
    assert me.n_states(p1) <= 9


def test_states_follow_the_cuts():
    part = {"vars": ["a"], "cuts": {"a": [0.5]}}
    ranks = {"a": np.array([0.1, 0.6, np.nan, 0.9])}
    s = me.states(part, ranks)
    assert list(s[[0, 1, 3]]) == [0, 1, 1] and s[2] == -1      # -1 = undefined


def test_circular_shift_null_is_calibrated_and_has_power():
    rng = np.random.default_rng(2)
    n, fp, sims = 1200, 0, 150
    for _ in range(sims):
        st = (np.cumsum(rng.normal(0, 1, n)) > 0).astype(int)   # persistent states
        ret = rng.normal(0, 1, n)
        fp += me.shift_pvalue(st, ret, n_shift=99, rng=rng) < 0.05
    assert fp / sims <= 0.10
    st = (np.arange(n) // 50) % 2
    ret = rng.normal(0, 1, n) + 0.6 * st                         # state moves the mean
    assert me.shift_pvalue(st, ret, n_shift=99, rng=rng) < 0.05


def test_knowledge_gradient_prefers_the_uncertain_near_boundary_hypothesis():
    hyps = {"near": {"mu": -5.0, "sd": 60.0, "obs_sd": 200.0},
            "far": {"mu": -400.0, "sd": 20.0, "obs_sd": 200.0},
            "best": {"mu": 0.0, "sd": 10.0, "obs_sd": 200.0}}
    kg = kp.knowledge_gradient(hyps)
    assert kg["near"] > kg["far"]


def test_blocks_to_decision_falls_with_effect_size():
    a = kp.blocks_to_decision(net_edge=50.0, obs_sd=200.0)
    b = kp.blocks_to_decision(net_edge=10.0, obs_sd=200.0)
    assert a < b and a > 0


def test_knowledge_value_is_per_decision_not_winner_take_all():
    """Each hypothesis is its own act-or-not decision vs doing nothing (0):
    adding an unrelated, wildly uncertain hypothesis must not change it."""
    base = {"h": {"mu": -10.0, "sd": 40.0, "obs_sd": 150.0}}
    a = kp.knowledge_gradient(base)["h"]
    b = kp.knowledge_gradient({**base, "wild": {"mu": 300.0, "sd": 400.0,
                                                 "obs_sd": 900.0}})["h"]
    assert a == pytest.approx(b) and a > 0


def test_panel_null_respects_the_common_market_factor():
    """Assets share a market move and the state is market-wide and persistent,
    with NO predictive link. Rotating each asset independently would erase the
    shared move and over-reject (measured 2026-10-02: 69% of 400 real tests
    'significant'); rotating every asset by the SAME offset must stay calibrated."""
    rng = np.random.default_rng(3)
    days, assets, sims, fp = 600, 10, 60, 0
    for _ in range(sims):
        mkt = np.convolve(rng.normal(0, 1, days + 6), np.ones(7), "valid")   # 7d overlap
        Y = mkt[:, None] + 0.3 * rng.normal(0, 1, (days, assets))
        state = (np.cumsum(rng.normal(0, 1, days)) > 0).astype(int)
        S = np.repeat(state[:, None], assets, axis=1)
        fp += me.matrix_shift_pvalue(S, Y, n_shift=99, rng=rng) < 0.05
    assert fp / sims <= 0.12


def test_maxT_family_has_power_and_stays_calibrated():
    """Westfall-Young max-T over the FULL rotation group: a planted partition
    is found; under the full null the family-wise rate stays near alpha
    (measured 5.8% over 450 null simulations when the procedure was fixed;
    150 seeded simulations here, bound ~2.5 SE)."""
    rng = np.random.default_rng(11)
    days, assets = 400, 6
    # persistent but NOT periodic: a periodic plant is re-aligned by shifts
    # that are multiples of its period, which the full group contains
    planted = ((np.cumsum(np.random.default_rng(99).normal(0, 1, days)) > 0)
               .astype(int))[:, None].repeat(assets, axis=1)
    Ss = [((np.cumsum(rng.normal(0, 1, days)) > 0).astype(int))[:, None].repeat(assets, 1)
          for _ in range(10)]
    Yp = rng.normal(0, 1, (days, assets)) + 0.5 * planted
    adj = me.maxT_adjusted([planted] + Ss, Yp, n_shift=None, rng=rng)
    assert adj[0] < 0.05
    fw, sims = 0, 150
    for _ in range(sims):
        Y0 = rng.normal(0, 1, (days, assets))
        fw += min(me.maxT_adjusted(Ss, Y0, n_shift=None, rng=rng)) < 0.05
    assert fw / sims <= 0.095


def test_block_weeks_come_from_the_series_itself():
    node = {"series": {"t": [0.0, 604800.0, 2 * 604800.0]}}
    assert kp.block_weeks(node) == pytest.approx(1.0)
    node4 = {"series": {"t": [0.0, 4 * 604800.0]}}
    assert kp.block_weeks(node4) == pytest.approx(4.0)
