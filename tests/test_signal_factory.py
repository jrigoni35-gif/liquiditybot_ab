"""AN AUC IS NOT MONEY, AND A GRID THAT CANNOT COUNT ITS OWN TRIALS IS A FISHING
EXPEDITION. Pins for scripts/signal_factory.py.

WHY THIS FILE EXISTS, measured 2026-09-05. The v1 grid (1,454 candidates) threw
217 raw DIRECTIONAL flags against a measured chance rate of 0.10 -- 145.4
expected from noise alone -- and 54 survived BH-FDR at q=0.05. The best of them,
`fv_edge_bps`, then REPLICATED across a time-ordered split (early 0.4634, late
0.4806, both day-block CIs excluding 0.5) and STILL could not clear its own
rake: flipped-rule P(pt) 0.4851 CI [0.4277, 0.5373] against a cost-floor
break-even of 0.5714. A tool that printed the AUC and stopped would have
promoted it.

So the pins below defend three separate things, and each is a defect this repo
has actually shipped before:
  1. the break-even band is DERIVED, never a literal (fee-schedule-asserting-
     itself, the-method recurrence #1);
  2. the interval is a DAY BLOCK, not iid (an iid CI over overlapping label
     windows is optimistic by sqrt(n/n_eff) and would manufacture exclusions);
  3. the ledger schema does not drift (the history schema-loss incident lost
     ~87 rows to exactly one silent header widening).

EVERY PIN HERE WAS MUTATION-VERIFIED: the defect it names was planted, the pin
was watched go red, and the code was restored. A pin nobody has seen fail is a
comment.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("numpy")

from scripts.signal_factory import (  # noqa: E402
    GRID_ID, LEDGER_COLUMNS, MIN_DISTINCT_FOR_PAIRING, MIN_RULE_ROWS,
    RESOLVED_PT, RESOLVED_SL, SCHEMA_VERSION, VERDICT_CANNOT, VERDICT_CLEARS,
    VERDICT_UNDET, benjamini_hochberg, break_even_band, build_grid,
    ci_to_p, cost_screen, learnable_features, rule_win_rate)

# The shipped geometry, quoted here ONLY as the input to a derivation. If
# config.json moves, the band moves with it -- that is the point of the pin
# below that feeds a DIFFERENT geometry and demands a different answer.
_SHIPPED = {"label_round_trip_cost_pct": 0.6, "label_pt_vol_mult": 8,
            "label_sl_vol_mult": 6, "label_pt_cost_mult": 4.0}
# (sl*ptc + pt) / ((pt+sl)*ptc) = (6*4 + 8) / (14*4) = 32/56
_SHIPPED_HI = 32 / 56


def _days(n, ndays, start=1_780_000_000):
    """Signal timestamps spread over exactly `ndays` calendar days."""
    per = int(np.ceil(n / ndays))
    return np.array([start + (i // per) * 86400 + (i % per)
                     for i in range(n)], dtype=float)


# --------------------------------------------------------------- the cost bar
def test_break_even_band_matches_the_hand_derivation():
    """The band is the whole verdict. Two routes must agree.

    By hand, from the shipped geometry: a win pays 8*sigma, a loss 6*sigma,
    every round trip pays 0.6%. At the cost floor sigma = 4.0*0.006/8 = 0.003,
    so pt = 2.4%, sl = 1.8% and w_be = (1.8+0.6)/4.2 = 0.5714. With barriers
    far above the floor the cost vanishes and w_be -> 6/14 = 0.4286.
    """
    lo, hi = break_even_band(_SHIPPED)
    assert lo == pytest.approx(6 / 14, abs=1e-6), (
        "the generous end of the band is not sl_mult/(pt_mult+sl_mult)")
    assert hi == pytest.approx((0.018 + 0.006) / 0.042, abs=1e-6), (
        "the hostile end does not match the cost-floored geometry")


def test_the_band_is_DERIVED_from_config_not_hardcoded():
    """THE LOAD-BEARING PIN against the-method recurrence #1: a struck fee
    schedule asserting itself as truth. Change the geometry, the band MUST
    move. A hardcoded 0.4286/0.5714 passes the test above and fails here."""
    # the ratio end follows the barrier multipliers
    assert break_even_band(dict(_SHIPPED, label_sl_vol_mult=2))[0] \
        == pytest.approx(2 / 10, abs=1e-6)
    # the floor end follows pt_cost_mult: a LOWER multiple means the profit
    # target sits closer to cost, so more of the win must go to the rake
    loose = break_even_band(dict(_SHIPPED, label_pt_cost_mult=2.0))[1]
    tight = break_even_band(dict(_SHIPPED, label_pt_cost_mult=8.0))[1]
    assert loose > _SHIPPED_HI > tight, (
        "the cost-floor end does not respond to pt_cost_mult - it is not "
        "being derived from the shipped barrier geometry")


def test_the_floor_end_is_INVARIANT_to_the_fee_level():
    """NOT A BUG - A PROPERTY, and the first draft of the test above asserted
    the opposite and failed. At the floor the barriers are DEFINED as a
    multiple of cost, so cost cancels:
        w_be(floor) = (sl*ptc + pt) / ((pt+sl)*ptc)
    Fees 5bps or 500bps give the same number. What a fee rise actually does is
    push more ROWS onto the floor, moving the corpus toward the hostile end of
    the band. Pinned so nobody 'fixes' the invariance back into a dependency,
    and so nobody reads a stable `hi` as evidence that fees are harmless."""
    cheap = break_even_band(dict(_SHIPPED, label_round_trip_cost_pct=0.05))[1]
    dear = break_even_band(dict(_SHIPPED, label_round_trip_cost_pct=5.0))[1]
    assert cheap == pytest.approx(dear, abs=1e-9) == pytest.approx(
        _SHIPPED_HI, abs=1e-9)


def test_band_is_an_ordered_probability():
    lo, hi = break_even_band(_SHIPPED)
    assert 0.0 < lo < hi < 1.0


def test_a_zero_cost_book_collapses_the_band():
    """ANTI-RUBBER-STAMP. With no cost there is nothing to clear beyond the
    barrier ratio, so both ends must meet. If they do not, one end is not
    reading cost at all."""
    free = dict(_SHIPPED, label_round_trip_cost_pct=0.0)
    lo, hi = break_even_band(free)
    assert lo == pytest.approx(hi, abs=1e-9)


# ------------------------------------------------------------- the screen
def _resolved(n=4000, seed=3):
    rng = np.random.default_rng(seed)
    b = np.where(rng.random(n) < 0.5, RESOLVED_PT, RESOLVED_SL)
    return b, _days(n, 20)


def test_a_perfect_selector_CLEARS_and_a_perfect_anti_selector_CANNOT():
    """Both arms, or the verdict is a constant wearing a function's name."""
    band = break_even_band(_SHIPPED)
    b, sig = _resolved()
    winner = np.where(b == RESOLVED_PT, 1.0, -1.0)      # auc>=.5 -> rule x>0
    assert cost_screen("w", winner, 0.99, b, sig, band)["verdict"] \
        == VERDICT_CLEARS
    loser = np.where(b == RESOLVED_SL, -1.0, 1.0)       # auc<.5  -> rule x<0
    assert cost_screen("l", loser, 0.01, b, sig, band)["verdict"] \
        == VERDICT_CANNOT


def test_a_coin_flip_rule_is_UNDETERMINED_not_an_edge():
    """THE DEFECT THIS TOOL EXISTS TO PREVENT. A rule with no edge must come
    back UNDETERMINED. Anything that reports a coin flip as CLEARS_COST would
    promote noise into a traded signal."""
    band = break_even_band(_SHIPPED)
    b, sig = _resolved()
    rng = np.random.default_rng(11)
    noise = rng.normal(size=b.size)
    assert cost_screen("n", noise, 0.5, b, sig, band)["verdict"] \
        == VERDICT_UNDET


def test_the_measured_live_case_stays_UNDETERMINED():
    """REGRESSION PIN on the real 2026-09-05 result. A rule sitting at
    P(pt)~0.485 inside a [0.4286, 0.5714] band must NOT read as clearing --
    that specific number is what the grid's best survivor actually produced
    after replicating out of sample."""
    band = break_even_band(_SHIPPED)
    rng = np.random.default_rng(5)
    n = 6000
    b = np.where(rng.random(n) < 0.485, RESOLVED_PT, RESOLVED_SL)
    sig = _days(n, 12)
    x = np.ones(n)                       # rule fires everywhere
    out = cost_screen("live-ish", x, 0.99, b, sig, band)
    assert out["p_pt"] == pytest.approx(0.485, abs=0.03)
    assert out["verdict"] == VERDICT_UNDET, (
        f"a {out['p_pt']} win rate inside the break-even band was reported as "
        f"{out['verdict']} - the screen would have promoted the very candidate "
        f"the 2026-09-05 measurement killed")


def test_the_flip_is_driven_by_the_measured_AUC():
    """An anti-predictive feature is traded by its FLIP. If the rule ignores
    the AUC sign, half of every grid is scored backwards."""
    band = break_even_band(_SHIPPED)
    b, sig = _resolved()
    x = np.where(b == RESOLVED_PT, 1.0, -1.0)
    assert cost_screen("a", x, 0.49, b, sig, band)["rule"] == "x<0"
    assert cost_screen("a", x, 0.51, b, sig, band)["rule"] == "x>0"


def test_a_thin_rule_refuses_a_verdict():
    """Below MIN_RULE_ROWS there is no win rate worth believing.

    THE FIRING ROWS ARE SPREAD ACROSS MANY DAYS ON PURPOSE. The first version
    of this pin took the first MIN_RULE_ROWS-1 rows, which all landed inside a
    single day -- so the MIN_CI_DAYS floor refused the interval and the pin
    passed even with the row guard deleted. Mutation caught it (2026-09-05).
    Spreading the rows over 20 blocks leaves the ROW count as the only thing
    that can produce the refusal."""
    from scripts.label_decomposition_report import MIN_CI_DAYS
    band = break_even_band(_SHIPPED)
    b, sig = _resolved()
    per = b.size // 20
    x = np.full(b.size, -1.0)
    fire = np.concatenate([np.arange(d * per, d * per + 4) for d in range(20)])
    x[fire] = 1.0                          # 80 rows, 20 distinct days
    out = cost_screen("thin", x, 0.99, b, sig, band)
    assert out["n"] < MIN_RULE_ROWS, "fixture no longer thin"
    assert out["ndays"] == 0, (
        "the refusal must happen on the ROW count, before any day indexing")
    assert out["ci"] is None and out["verdict"] == VERDICT_UNDET
    # and prove the day floor was NOT what saved it: the same rows, if they
    # were numerous enough, span well past MIN_CI_DAYS
    assert len(np.unique(np.floor(sig[fire] / 86400))) >= MIN_CI_DAYS


# ------------------------------------------------------ the interval itself
def test_the_interval_is_a_DAY_BLOCK_not_iid():
    """THE PIN THAT DISCRIMINATES A DAY-BLOCK BOOTSTRAP FROM AN IID ONE.

    Construct a corpus whose outcome is homogeneous WITHIN each day and wildly
    heterogeneous BETWEEN days: 20 days, ten at a 0.15 win rate and ten at
    0.85, overall exactly 0.50. The two bootstraps disagree enormously here:

      iid       resamples ROWS, is blind to the day structure, and returns
                the binomial width ~ 2*1.96*sqrt(.25/2000) ~= 0.044
      day-block resamples whole DAYS, so a draw can land 15 cheap days and 5
                dear ones, and the width blows out past 0.2

    Anything near 0.044 means the day structure is being ignored and every
    interval this tool prints is optimistic by sqrt(n/n_eff).

    (The first draft of this pin instead compared 3 blocks against 60 and
    asserted the 3-block interval would be WIDER. It is not - it COLLAPSES,
    which is the degenerate behaviour MIN_CI_DAYS exists to refuse. That
    failure is now its own pin, directly below.)
    """
    per_day, ndays = 100, 20
    n = per_day * ndays
    rng = np.random.default_rng(9)
    b = np.empty(n, dtype=object)
    for d in range(ndays):
        p = 0.15 if d < ndays // 2 else 0.85
        seg = rng.random(per_day) < p
        b[d * per_day:(d + 1) * per_day] = np.where(seg, RESOLVED_PT,
                                                    RESOLVED_SL)
    b = b.astype(str)
    out = rule_win_rate(np.ones(n), b, _days(n, ndays), flip=False,
                        reps=600, seed=1)
    assert out["ndays"] == ndays
    assert out["p_pt"] == pytest.approx(0.5, abs=0.06), "fixture drifted"
    width = out["ci"][1] - out["ci"][0]
    assert width > 0.20, (
        f"between-day heterogeneity produced a {width:.4f}-wide interval; an "
        f"iid bootstrap on these rows gives ~0.044, so this interval is not "
        f"resampling DAYS and every CI this tool prints is optimistic")


def test_too_few_blocks_REFUSES_an_interval_instead_of_collapsing():
    """THE DEFECT THIS FILE CAUGHT IN ITS OWN SUBJECT (2026-09-05).

    A percentile bootstrap over a handful of blocks does not get noisy, it
    COLLAPSES: every draw repeats the same few days so the resampled mean
    barely moves. Measured on the first version of rule_win_rate: 3 blocks
    returned width 0.0170 against 0.0347 at 60 -- the thinnest evidence
    produced the MOST confident interval, and a rule firing on three days
    could have been reported CLEARS_COST on it.

    So below MIN_CI_DAYS the function must refuse the interval outright, and
    the screen must degrade to UNDETERMINED rather than to a verdict."""
    from scripts.label_decomposition_report import MIN_CI_DAYS
    n = 3000
    rng = np.random.default_rng(9)
    b = np.where(rng.random(n) < 0.9, RESOLVED_PT, RESOLVED_SL)   # a "winner"
    sig = _days(n, MIN_CI_DAYS - 2)
    out = rule_win_rate(np.ones(n), b, sig, flip=False, reps=400, seed=1)
    assert out["ndays"] < MIN_CI_DAYS
    assert out["p_pt"] is not None, "the point estimate should still be given"
    assert out["ci"] is None, (
        f"{out['ndays']} blocks still produced an interval {out['ci']} - a "
        f"collapsed bootstrap is being reported as evidence")
    assert out.get("few_blocks") is True, "the refusal must be visible"
    screened = cost_screen("thin-days", np.ones(n), 0.99, b, sig,
                           break_even_band(_SHIPPED), reps=400)
    assert screened["verdict"] == VERDICT_UNDET, (
        "a 90%-win-rate rule measured on too few day blocks was promoted to "
        f"{screened['verdict']}")


def test_rule_win_rate_scores_only_RESOLVED_rows():
    """DIRECTION channel only. Letting tb_time rows in re-mixes RESOLUTION
    back into the number -- the exact confound the decomposition removes."""
    n = 2000
    b = np.array([RESOLVED_PT] * 500 + [RESOLVED_SL] * 500 + ["tb_time"] * 1000)
    out = rule_win_rate(np.ones(n), b, _days(n, 20), flip=False)
    assert out["n"] == 1000, "unresolved rows leaked into the win rate"
    assert out["p_pt"] == pytest.approx(0.5, abs=1e-9)


# ------------------------------------------------- multiplicity accounting
def test_bh_is_monotone_and_handles_the_edges():
    assert benjamini_hochberg([]) == []
    assert benjamini_hochberg([0.9, 0.8, 0.7]) == []
    assert len(benjamini_hochberg([1e-9] * 5)) == 5


def test_bh_is_stricter_than_no_correction():
    """A batch of 1,000 mostly-null tests with a few small p-values: BH must
    keep FEWER than the naive p<0.05 count, or the correction is absent."""
    rng = np.random.default_rng(4)
    p = list(rng.random(1000))
    p[:3] = [1e-8, 2e-8, 3e-8]
    naive = sum(1 for v in p if v < 0.05)
    assert len(benjamini_hochberg(p, q=0.05)) < naive


def test_ci_to_p_refuses_to_invent_significance():
    assert ci_to_p(None, None) == 1.0
    wide = ci_to_p(0.30, 0.70)          # straddles 0.5 by a mile
    narrow = ci_to_p(0.52, 0.54)        # excludes it
    assert wide > 0.5 and narrow < 0.05
    assert ci_to_p(0.49, 0.51) > ci_to_p(0.60, 0.62)


# ------------------------------------------------------------- the grid
def test_grid_is_deterministic_and_pre_registered():
    """The multiple-comparisons denominator cannot be chosen after the fact,
    so the grid must be a pure function of the corpus SHAPE."""
    rng = np.random.default_rng(2)
    X = rng.normal(size=(500, 4))
    names = ["a", "b", "c", "d"]
    g1, g2 = build_grid(X, names), build_grid(X, names)
    assert set(g1) == set(g2)
    # 4 sign + 4 abs + C(4,2)=6 products
    assert len(g1) == 4 + 4 + 6
    assert GRID_ID and isinstance(GRID_ID, str)


def test_flag_columns_are_not_paired():
    """Pairing a two-valued flag multiplies noise by noise. The product family
    must draw only from columns with real spread."""
    rng = np.random.default_rng(6)
    X = np.column_stack([rng.normal(size=800), rng.normal(size=800),
                         np.repeat([0.0, 1.0], 400)])          # col 2 = a flag
    names = ["x", "y", "flagcol"]
    assert "flagcol" not in learnable_features(X, names)
    grid = build_grid(X, names)
    assert not any("flagcol" in k and "*" in k for k in grid), (
        "a 2-distinct-value flag entered the interaction family")


def test_learnable_threshold_is_the_documented_one():
    """Straddle MIN_DISTINCT_FOR_PAIRING from both sides, so the pin fails if
    the threshold moves in either direction."""
    n = 600
    X = np.column_stack([
        (np.arange(n) % MIN_DISTINCT_FOR_PAIRING).astype(float),      # exactly
        (np.arange(n) % (MIN_DISTINCT_FOR_PAIRING - 1)).astype(float),  # under
    ])
    keep = learnable_features(X, ["at_threshold", "under_threshold"])
    assert "at_threshold" in keep, "a column AT the threshold was excluded"
    assert "under_threshold" not in keep, "a column UNDER it was admitted"


# ------------------------------------------------------------- the ledger
def test_ledger_schema_is_frozen():
    """THE SCHEMA-TEAR PIN. The ledger already holds >1,400 rows. Appending a
    WIDER header in place silently tears the file for every reader of the old
    rows -- the history schema-loss incident lost ~87 rows to exactly that.
    The cost screen is deliberately REPORTED, never appended. If this pin goes
    red, the change needs a NEW ledger file, not a wider one."""
    assert SCHEMA_VERSION == 1
    assert LEDGER_COLUMNS == (
        "schema_version", "run_utc", "grid_id", "signal_id", "family", "n",
        "n_resolved", "ndays", "direction_auc", "dir_lo", "dir_hi", "flag",
        "corpus_sha", "era")
    for banned in ("verdict", "p_pt", "break_even", "clears_cost"):
        assert banned not in LEDGER_COLUMNS, (
            f"cost-screen field {banned!r} was appended to the v1 ledger "
            f"header - that tears every existing row")
