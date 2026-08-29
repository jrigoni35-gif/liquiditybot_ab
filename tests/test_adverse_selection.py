"""Mutation-killed pins for scripts/adverse_selection.py.

THE STAKE: a mark-out sign error inverts the entire game-theoretic conclusion
(adverse <-> favourable). These pins fix the sign convention and the
effective-n deflation so a future edit that flips either is caught in CI.

Mutation evidence (run 2026-08-29, HEAD 933859f4):
  * negate raw_markout_bps -> test_buy_down_move_is_adverse FAILS (returns
    +100 where -100 is required) and test_sign_convention_self_test FAILS
    (4/7 planted cases red). Restored -> green.
  * make effective_n return len(times) (defeat the deflation) ->
    test_effective_n_full_overlap_collapses FAILS (10 != ~1). Restored ->
    green.
"""
import importlib

adv = importlib.import_module("scripts.adverse_selection")


# --- sign convention: the load-bearing invariant --------------------------
def test_sign_convention_self_test_passes():
    """All 7 planted cases in the instrument's own hook pass."""
    assert adv.self_test() == []


def test_buy_up_move_is_favorable():
    # BUY at 100, market rises to 101 -> we bought low -> POSITIVE.
    assert adv.raw_markout_bps("buy", 100.0, 101.0) == 100.0
    assert adv.alpha_bps("buy", 100.0, 101.0) == 100.0


def test_buy_down_move_is_adverse():
    # BUY at 100, market falls to 99 -> picked off -> NEGATIVE. This is the
    # exact case a sign flip inverts, so it is the primary mutation pin.
    assert adv.raw_markout_bps("buy", 100.0, 99.0) == -100.0
    assert adv.alpha_bps("buy", 100.0, 99.0) == -100.0


def test_sell_mirrors_buy():
    # SELL (short) at 100: a down-move is FAVOURABLE, an up-move ADVERSE.
    assert adv.raw_markout_bps("sell", 100.0, 99.0) == 100.0
    assert adv.raw_markout_bps("sell", 100.0, 101.0) == -100.0


def test_spread_capture_maker_buy_below_reference_is_positive():
    # A maker who buys BELOW the reference mid captures half-spread -> POS,
    # and this term must carry no forward info (it is a fill-vs-mid offset).
    assert adv.spread_capture_bps("buy", 99.5, 100.0) > 0
    assert adv.spread_capture_bps("sell", 100.5, 100.0) > 0


def test_markout_decomposes_into_spread_plus_alpha():
    # raw markout ~= spread_capture + alpha (identity up to denominators).
    side, fill, anchor, fwd = "buy", 99.5, 100.0, 101.5
    raw = adv.raw_markout_bps(side, fill, fwd)
    approx = (adv.spread_capture_bps(side, fill, anchor)
              + adv.alpha_bps(side, anchor, fwd))
    assert abs(raw - approx) < 1.0     # bps-scale denominator slack


# --- effective-n deflation: the honest denominator ------------------------
def test_effective_n_full_overlap_collapses():
    # 10 fills in the same instant, horizon 3600s: all windows overlap ->
    # each uniqueness 1/10 -> n_eff = 1. A mutation that returns nominal n
    # is killed here.
    t = [1000.0] * 10
    assert abs(adv.effective_n(t, 3600.0) - 1.0) < 1e-9


def test_effective_n_disjoint_windows_is_nominal():
    # 5 fills spaced far beyond the horizon -> no overlap -> n_eff = n.
    t = [0.0, 10000.0, 20000.0, 30000.0, 40000.0]
    assert abs(adv.effective_n(t, 3600.0) - 5.0) < 1e-9


def test_effective_n_never_exceeds_nominal():
    t = [0.0, 100.0, 3700.0, 3800.0, 50000.0]
    assert adv.effective_n(t, 3600.0) <= len(t) + 1e-9


def test_effective_n_empty():
    assert adv.effective_n([], 3600.0) == 0.0
