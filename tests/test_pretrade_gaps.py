"""tests/test_pretrade_gaps.py — characterization pins for the gaps in
execution/pretrade.py's PreTradeGate not already covered by
tests/test_liquidity_tier_isolation.py: the taker book-walk path, the
spoofy/reduce-only veto, the tier-cap fallback (unknown tier / missing
"core" entry), the exact strict-inequality boundaries on every veto, the
reason-code vocabulary (approval + participation clamp), and the single-
call-site architectural invariant that keeps invariant #5 (exits are never
gated by the entry-only pretrade check) true by construction.

Gate/context construction follows tests/test_liquidity_tier_isolation.py's
_gate()/_ctx() idiom.
"""
from pathlib import Path

import pytest

from core.codes import Code
from execution.pretrade import PreTradeContext, PreTradeGate

MAIN_PY = Path(__file__).resolve().parents[1] / "main.py"

# a deep, tight two-sided book: one huge level per side at the touch, so
# book-walk slippage is exactly 0 and impact/participation never bind
# unless a test deliberately dials them down.
DEEP_BOOK = {"bids": [[99.0, 1000.0]], "asks": [[100.0, 1000.0]]}


def _gate(**over):
    cfg = {"maker_fee_bps": 25.0, "taker_fee_bps": 40.0,
          "min_edge_cost_ratio": 1.3, "max_spread_bps": 12.0,
          "max_participation_of_depth": 1000.0, "min_order_usd": 1.0,
          "max_data_staleness_ms": 5000.0, "price_exit_leg": False,
          "ev_min_bps": 0.0}
    cfg.update(over)
    return PreTradeGate(cfg)


def _ctx(spread=10.0, tier="core", adv=0.0, book=None, liq="liquid",
        reduce_only=False, sigma=1.0):
    return PreTradeContext(kraken_book=book or DEEP_BOOK, sigma_daily_pct=sigma,
                          adv_usd=adv, liq_label=liq, spread_bps=spread,
                          staleness_ms=0.0, reduce_only_ok=reduce_only,
                          tier=tier)


def _reasons(dec):
    return " ".join(str(r) for r in dec.reasons)


# ---------------------------------------------------------------------------
# 13. taker path: book-walk cost vs the maker path; shallow book -> PT-023
# ---------------------------------------------------------------------------
def test_taker_book_walk_costs_more_than_the_maker_path():
    book = {"bids": [[99.95, 0.5], [99.9, 5.0], [99.85, 5.0], [99.8, 5.0]],
           "asks": [[100.0, 0.5], [100.05, 5.0], [100.1, 5.0], [100.15, 5.0]]}
    ctx = _ctx(spread=5.0, book=book, adv=1e6, sigma=1.0)
    gate = _gate(price_exit_leg=True)
    taker = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                          fv_edge_bps=0.0, ctx=ctx, taker=True)
    maker = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                          fv_edge_bps=0.0, ctx=ctx, taker=False)
    assert taker.approved and maker.approved
    assert taker.est_cost_bps > maker.est_cost_bps
    assert taker.est_cost_bps > 0.0


def test_taker_shallow_book_vetoes_pt023():
    thin = {"bids": [[99.0, 1000.0]], "asks": [[100.0, 0.1], [100.05, 0.1]]}
    ctx = _ctx(spread=5.0, book=thin, adv=1e6)
    d = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                        fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert not d.approved
    assert Code.PT_BOOK_SHALLOW.value in _reasons(d)


# ---------------------------------------------------------------------------
# 14. spoofy veto, waived only under reduce_only_ok
# ---------------------------------------------------------------------------
def test_spoofy_vetoes_new_risk_unless_reduce_only():
    ctx_new = _ctx(spread=5.0, liq="spoofy", reduce_only=False)
    d = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                        fv_edge_bps=0.0, ctx=ctx_new)
    assert not d.approved
    assert Code.PT_SPOOFY_REGIME.value in _reasons(d)

    ctx_ro = _ctx(spread=5.0, liq="spoofy", reduce_only=True)
    d2 = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                         fv_edge_bps=0.0, ctx=ctx_ro)
    assert Code.PT_SPOOFY_REGIME.value not in _reasons(d2)


# ---------------------------------------------------------------------------
# 15/16. tier-cap resolution: unknown tier + missing "core" entry
# ---------------------------------------------------------------------------
def test_unknown_tier_falls_back_to_the_flat_cap():
    gate = PreTradeGate({**{
        "maker_fee_bps": 25.0, "taker_fee_bps": 40.0,
        "min_edge_cost_ratio": 1.3, "max_participation_of_depth": 1000.0,
        "min_order_usd": 1.0, "max_data_staleness_ms": 5000.0},
        "max_spread_bps": 50.0,
        "tier_max_spread_bps": {"core": 10.0, "mid": 20.0, "micro": 30.0}})
    # 40bps fails every DECLARED tier cap (10/20/30) but passes the flat 50
    ctx = _ctx(spread=40.0, tier="unknown")
    d = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                      fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert Code.PT_SPREAD_WIDE.value not in _reasons(d)
    assert d.approved


def test_missing_core_tier_cap_defaults_to_the_flat_cap():
    gate = PreTradeGate({
        "maker_fee_bps": 25.0, "taker_fee_bps": 40.0,
        "min_edge_cost_ratio": 1.3, "max_participation_of_depth": 1000.0,
        "min_order_usd": 1.0, "max_data_staleness_ms": 5000.0,
        "max_spread_bps": 10.0,
        "tier_max_spread_bps": {"mid": 20.0, "micro": 30.0}})   # no "core"
    assert gate.tier_max_spread_bps["core"] == 10.0     # the setdefault
    ctx = _ctx(spread=15.0, tier="core")
    d = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                      fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert not d.approved
    assert Code.PT_SPREAD_WIDE.value in _reasons(d)


# ---------------------------------------------------------------------------
# 17. exact strict-inequality boundaries (spread cap / edge-cost / EV floor)
# ---------------------------------------------------------------------------
def test_spread_exactly_at_cap_approves_over_cap_vetoes():
    gate = _gate(max_spread_bps=12.0)
    at = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=1000.0,
                       fv_edge_bps=0.0, ctx=_ctx(spread=12.0), taker=True)
    assert at.approved
    assert Code.PT_SPREAD_WIDE.value not in _reasons(at)
    over = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=1000.0,
                         fv_edge_bps=0.0, ctx=_ctx(spread=12.001), taker=True)
    assert not over.approved
    assert Code.PT_SPREAD_WIDE.value in _reasons(over)


def test_edge_exactly_ratio_times_cost_approves_below_vetoes():
    # cost (taker, adv=0 -> impact 0, single deep level -> walk 0,
    # price_exit_leg off) = taker_fee(40) + 0.5*spread(10) = 45.0 exactly
    gate = _gate(taker_fee_bps=40.0, min_edge_cost_ratio=1.3,
                ev_min_bps=-1e6)          # EV floor can't intervene here
    ctx = _ctx(spread=10.0, adv=0.0)
    cost, ratio = 45.0, 1.3
    edge_exact = ratio * cost
    at = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=edge_exact,
                       fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert at.approved
    assert Code.PT_EDGE_RATIO.value not in _reasons(at)
    assert at.est_cost_bps == pytest.approx(cost)
    below = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=edge_exact - 0.01,
                          fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert not below.approved
    assert Code.PT_EDGE_RATIO.value in _reasons(below)


def test_ev_exactly_at_floor_approves_below_vetoes():
    gate = _gate(min_edge_cost_ratio=0.01, ev_min_bps=5.0)
    ctx = _ctx(spread=10.0, adv=0.0)
    cost, ev_min = 45.0, 5.0
    edge_exact = cost + ev_min            # taker: ev = edge - cost
    at = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=edge_exact,
                       fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert at.approved
    assert Code.PT_EV_NEGATIVE.value not in _reasons(at)
    assert at.ev_bps == pytest.approx(ev_min)
    below = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=edge_exact - 0.01,
                          fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert not below.approved
    assert Code.PT_EV_NEGATIVE.value in _reasons(below)


# ---------------------------------------------------------------------------
# 18. codes: PT-000 on approval; PT-030 + clamped size on an oversized order
# ---------------------------------------------------------------------------
def test_approved_reasons_carry_pt000():
    d = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=1000.0,
                        fv_edge_bps=0.0, ctx=_ctx(spread=5.0), taker=True)
    assert d.approved
    assert Code.PT_APPROVED.value in _reasons(d)


def test_oversized_order_against_thin_depth_clamps_with_pt030():
    gate = _gate(max_participation_of_depth=0.15)
    thin_book = {"bids": [[99.0, 5.0]], "asks": [[100.0, 5.0]]}
    # depth_units (top10) = 5.0 -> max_units = 0.75; request 2.0 units
    d = gate.evaluate("buy", 2.0, 100.0, exp_alpha_bps=1000.0,
                     fv_edge_bps=0.0, ctx=_ctx(spread=5.0, book=thin_book),
                     taker=True)
    assert Code.PT_PARTICIPATION_CLAMP.value in _reasons(d)
    assert d.approved
    assert d.size_units == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# 19. architectural pin: exactly one entry-side call site (invariant #5)
# ---------------------------------------------------------------------------
def test_pretrade_evaluate_has_a_single_call_site_in_entry_pipeline():
    """Invariant 5: exits are never gated by the entry-only PreTradeGate. A
    second `self.pretrade.evaluate(` call site anywhere near the exit path
    would silently let this entry-side EV/spread/spoofy gate block an
    escape -- disarm/faults/kill switches may block NEW risk, never exits."""
    src = MAIN_PY.read_text(encoding="utf-8")
    lines = src.splitlines()
    hits = [i for i, ln in enumerate(lines)
           if "self.pretrade.evaluate(" in ln]
    assert len(hits) == 1, (
        f"expected exactly one pretrade.evaluate() call site, found "
        f"{len(hits)} -- a second site risks gating an exit")
    call_line = hits[0]
    def_lines = [i for i, ln in enumerate(lines) if ln.startswith("    def ")]
    enclosing = max(i for i in def_lines if i < call_line)
    assert "slow_cycle" in lines[enclosing], (
        "pretrade.evaluate moved out of the entry-candidate slow_cycle "
        f"section into {lines[enclosing].strip()!r}")


# ---------------------------------------------------------------------------
# 20. W1-6: one-sided Kraken book on the MAKER path must fail closed, not
# approve with the optimistic p0 baseline / a silently-skipped participation
# clamp. Taker path is unaffected (its own book-walk veto already exists).
# ---------------------------------------------------------------------------
def test_one_sided_kraken_book_vetoes_the_maker_path():
    # bids healthy, asks EMPTY -- a buy's maker leg has no ask touch to
    # distance-decay p_fill from. Everything else is approvable (huge alpha,
    # tight nominal spread, deep ADV) so only the one-sided book can veto.
    book = {"bids": [[99.0, 1000.0]], "asks": []}
    ctx = _ctx(spread=5.0, book=book, adv=1e6)
    d = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                        fv_edge_bps=0.0, ctx=ctx, taker=False)
    assert not d.approved
    assert Code.PT_BOOK_SHALLOW.value in _reasons(d)
    # pre-fix this approved with the OPTIMISTIC baseline (mid=0.0 ->
    # dist_bps=0.0 -> p_fill == maker_fill_p0), never the honest floor.
    assert d.p_fill != pytest.approx(0.45)


def test_one_sided_kraken_book_oversized_order_is_not_left_unclamped():
    # same one-sided book, but the order is grossly oversized relative to the
    # (healthy) bid side. Pre-fix, depth_units off the EMPTY ask side is 0.0,
    # so max_units == 0.0 fails the `> EPS` test and the participation clamp
    # is silently skipped -- the size would ride through unclamped.
    book = {"bids": [[99.0, 1000.0]], "asks": []}
    ctx = _ctx(spread=5.0, book=book, adv=1e6)
    d = _gate(max_participation_of_depth=0.15).evaluate(
        "buy", 500.0, 100.0, exp_alpha_bps=500.0, fv_edge_bps=0.0,
        ctx=ctx, taker=False)
    assert not d.approved
    assert Code.PT_BOOK_SHALLOW.value in _reasons(d)
    assert d.size_units == 0.0          # never the raw 500.0 oversized request


# ---------------------------------------------------------------------------
# 21. W2-26: book_walk_bps on a WHOLLY empty side must return the 1e6
# shallow-book sentinel, never 0.0 -- a fully one-sided Kraken book gives a
# taker entry zero walk cost instead of the PT-023 veto (thin-but-present
# books already hit the sentinel via the "clean" empty-after-filter path;
# this is the "no levels at all" path, found by the W1-6 fixer).
# ---------------------------------------------------------------------------
def test_taker_wholly_empty_ask_side_vetoes_pt023_not_zero_cost():
    book = {"bids": [[99.0, 1000.0]], "asks": []}
    ctx = _ctx(spread=5.0, book=book, adv=1e6)
    d = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                        fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert not d.approved
    assert Code.PT_BOOK_SHALLOW.value in _reasons(d)


def test_taker_wholly_empty_bid_side_vetoes_pt023_not_zero_cost():
    book = {"bids": [], "asks": [[100.0, 1000.0]]}
    ctx = _ctx(spread=5.0, book=book, adv=1e6)
    d = _gate().evaluate("sell", 1.0, 100.0, exp_alpha_bps=500.0,
                        fv_edge_bps=0.0, ctx=ctx, taker=True)
    assert not d.approved
    assert Code.PT_BOOK_SHALLOW.value in _reasons(d)


def test_negative_spread_cannot_reduce_the_cost_stack():
    # a negative ctx.spread_bps (inverted/garbage book upstream) must not
    # REDUCE spread_cost or exit_leg below their spread=0 values -- fail
    # closed, either by flooring consumption or rejecting the input outright.
    gate = _gate(price_exit_leg=True)
    ctx_neg = _ctx(spread=-5.0, adv=1e6)
    ctx_zero = _ctx(spread=0.0, adv=1e6)
    d_neg = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=1000.0,
                         fv_edge_bps=0.0, ctx=ctx_neg, taker=True)
    d_zero = gate.evaluate("buy", 1.0, 100.0, exp_alpha_bps=1000.0,
                          fv_edge_bps=0.0, ctx=ctx_zero, taker=True)
    if d_neg.approved:
        assert d_neg.est_cost_bps >= d_zero.est_cost_bps
    else:
        assert Code.PT_INVALID_INPUT.value in _reasons(d_neg)


# ==========================================================================
# C2 - the derived cost/edge fence (2026-09-13)
#
# evaluate() already refused non-finite INPUTS at :228-235 under
# Code.PT_INVALID_INPUT. It did not refuse a non-finite DERIVED cost, and
# `cost` sums six terms - two from config knobs never finite-checked
# (impact_eta, adverse_selection_kappa) and one, `impact`, computed at RUNTIME
# from ctx.adv_usd and ctx.sigma_daily_pct. So a config guard alone cannot
# close it: adv_usd=NaN reaches cost with every declared input finite.
#
# Both profit gates are written `x < y`, which is False on NaN, so a NaN cost
# satisfied BOTH and the entry was APPROVED with an unknown cost. An unknown
# cost is not a small cost.
# ==========================================================================

import copy as _copy  # noqa: E402  (C2 block, kept beside its tests)
import json as _json  # noqa: E402  (C2 block, kept beside its tests)
import math as _math  # noqa: E402  (C2 block, kept beside its tests)
from pathlib import Path as _Path  # noqa: E402  (C2 block, kept beside its tests)

from execution.pretrade import PreTradeContext as _Ctx  # noqa: E402  (C2 block, kept beside its tests)
from execution.pretrade import PreTradeGate as _Gate  # noqa: E402  (C2 block, kept beside its tests)

_CFG_C2 = _json.loads(
    (_Path(__file__).resolve().parent.parent / "config.json").read_text(
        encoding="utf-8"))
_BOOK_C2 = {"bids": [[100.0, 50.0], [99.9, 80.0]],
            "asks": [[100.1, 50.0], [100.2, 80.0]]}


def _ctx_c2(**over):
    base = dict(kraken_book=_BOOK_C2, sigma_daily_pct=2.0, adv_usd=5e7,
                liq_label="liquid", spread_bps=10.0, staleness_ms=200.0,
                reduce_only_ok=True, tier=5)
    base.update(over)
    return _Ctx(**base)


def _decide_c2(pt_over=None, ctx=None, **kw):
    pt = _copy.deepcopy(_CFG_C2["pretrade"])
    if pt_over:
        pt.update(pt_over)
    args = dict(exp_alpha_bps=30.0, fv_edge_bps=10.0, taker=False)
    args.update(kw)
    return _Gate(pt).evaluate("buy", 0.6, 100.0, ctx=ctx or _ctx_c2(), **args)


class TestNonFiniteCostCannotApprove:
    @pytest.mark.parametrize("key", ["impact_eta", "adverse_selection_kappa"])
    def test_a_non_finite_config_knob_cannot_approve(self, key):
        d = _decide_c2({key: float("nan")})
        assert d.approved is False, \
            f"{key}=NaN made cost NaN and the entry was APPROVED"
        assert not _math.isfinite(d.est_cost_bps)

    def test_a_RUNTIME_non_finite_cannot_approve(self):
        """The case config_guard can never reach: adv_usd is a live input, and
        every declared input passes the :228 fence."""
        assert _decide_c2(ctx=_ctx_c2(adv_usd=float("nan"))).approved is False

    def test_the_refusal_is_a_REGISTERED_code(self):
        """CLAUDE.md invariant 6: a registered code, never a bare string."""
        from core.codes import Code
        d = _decide_c2({"impact_eta": float("nan")})
        assert any(Code.PT_INVALID_INPUT.value in str(r) for r in d.reasons)

    def test_the_shipped_decision_is_UNCHANGED_on_finite_input(self):
        """NO-OP PROOF. This is entry-decisioning code under an accrual
        moratorium, so the fence must be provably inert on every finite input.
        Sweep the reachable grid and assert the fence never fires."""
        n = 0
        for alpha in (0.0, 5.0, 30.0, 200.0):
            for fv in (0.0, 10.0, 100.0):
                for spread in (0.5, 10.0, 60.0):
                    for taker in (False, True):
                        d = _decide_c2(ctx=_ctx_c2(spread_bps=spread),
                                       exp_alpha_bps=alpha, fv_edge_bps=fv,
                                       taker=taker)
                        assert _math.isfinite(d.est_cost_bps)
                        assert _math.isfinite(d.est_edge_bps)
                        n += 1
        assert n == 72

    def test_a_FINITE_pair_that_OVERFLOWS_to_inf_is_caught(self):
        """The edge half of the fence is NOT redundant, and mutation testing
        proved it: deleting `or not _fin(edge)` initially survived every pin.

        edge = max(alpha,0) + max(fv,0), and both inputs are already fenced at
        :228 - but two FINITE floats can sum to inf (1e308 + 1e308). The input
        fence cannot see that; only a check on the DERIVED value can. Without
        it, `inf < ratio*cost` is False, PT-041 never fires, and the
        entry is approved on an INFINITE edge."""
        d = _decide_c2(exp_alpha_bps=1e308, fv_edge_bps=1e308)
        assert d.approved is False
        assert not _math.isfinite(d.est_edge_bps)
        assert _math.isfinite(d.est_cost_bps), \
            "cost must still be finite - this pin is about the EDGE half"

    def test_exploring_does_not_bypass_the_finite_fence(self):
        """exploring=True bypasses the two PROFIT gates by design. It must NOT
        bypass a non-finite refusal - an unknown cost is not a thin edge."""
        d = _decide_c2({"impact_eta": float("nan")}, exploring=True)
        assert d.approved is False
