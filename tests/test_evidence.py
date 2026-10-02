"""core/evidence.py - Turing's ledger with 2026 anytime-valid guarantees.
Written BEFORE the module (TDD): each test names a property the ledger must
have for its readings to be trusted."""
import numpy as np
import pytest

from core import evidence as ev


def test_decibans_are_turings_unit():
    assert ev.decibans(10.0) == pytest.approx(10.0)
    assert ev.decibans(20.0) == pytest.approx(13.0103, abs=1e-3)
    assert ev.decibans(1.0) == 0.0


def test_null_crossing_rate_obeys_ville():
    """Under H0 (mean <= null) the e-process may be watched every step and
    still crosses 1/alpha with probability <= alpha (Ville's inequality)."""
    rng = np.random.default_rng(1)
    crossed = 0
    paths = 600
    for _ in range(paths):
        x = rng.normal(0.0, 1.0, 300)
        e = ev.betting_eprocess(x, null_mean=0.0, bound=4.0, side="greater")
        crossed += bool((e >= 20).any())
    assert crossed / paths <= 0.07


def test_real_edge_is_found():
    rng = np.random.default_rng(2)
    x = rng.normal(0.5, 1.0, 300)
    e = ev.betting_eprocess(x, null_mean=0.0, bound=4.0, side="greater")
    assert e[-1] >= 20


def test_less_side_finds_an_edge_below_the_round_trip():
    rng = np.random.default_rng(3)
    x = rng.normal(0.0, 1.0, 300)              # true mean 0 < 2c = 1
    e = ev.betting_eprocess(x, null_mean=1.0, bound=4.0, side="less")
    assert e[-1] >= 20


def test_bets_are_predictable_no_look_ahead():
    """E at step t depends on x[:t+1] only: poisoning the future changes
    nothing before it."""
    rng = np.random.default_rng(4)
    x = rng.normal(0.2, 1.0, 200)
    e1 = ev.betting_eprocess(x, 0.0, 4.0, "greater")
    y = x.copy()
    y[120:] = 50.0
    e2 = ev.betting_eprocess(y, 0.0, 4.0, "greater")
    assert np.allclose(e1[:120], e2[:120])


def test_wealth_never_goes_negative_even_at_the_bound():
    x = np.r_[np.full(50, 4.0), np.full(50, -4.0)]
    e = ev.betting_eprocess(x, 0.0, 4.0, "greater")
    assert np.all(e > 0)


def test_status_mapping():
    T = 20.0
    assert ev.status(25, 1, T) == "LIVE"
    assert ev.status(1, 25, T) == "ELIMINATED"
    assert ev.status(25, 25, T) == "EDGE BELOW ROUND TRIP"
    assert ev.status(5, 5, T) == "UNDECIDED"


def test_e_bh_controls_the_family():
    """e-BH (Wang & Ramdas 2022): reject the k largest where e_(k) >= m/(alpha k)."""
    e = {"a": 400.0, "b": 90.0, "c": 3.0, "d": 1.0}
    assert ev.e_bh(e, alpha=0.05) == {"a", "b"}      # 4/(.05*2)=40 <= 90
    assert ev.e_bh({"a": 30.0, "b": 1.0}, alpha=0.05) == set()   # 2/.05 = 40 > 30


def test_registry_refuses_to_retry_an_eliminated_idea():
    reg = [{"id": "h1", "family": "tsmom", "signal": "tsmom_24", "horizon_h": 24,
            "status": "ELIMINATED"}]
    with pytest.raises(ev.AlreadyEliminated):
        ev.propose(reg, {"id": "h2", "family": "tsmom", "signal": "tsmom_24",
                         "horizon_h": 24}, today="2026-10-02")
    new = ev.propose(reg, {"id": "h3", "family": "tsmom", "signal": "tsmom_24",
                           "horizon_h": 168}, today="2026-10-02")
    assert new["forward_from"] == "2026-10-02"      # evidence counts only after proposal
    assert new["status"] == "UNDECIDED"
    assert ev.trials(reg + [new], "tsmom") == 2
