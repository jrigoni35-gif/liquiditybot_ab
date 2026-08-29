"""Pins for ml/corpus.py — the canonical corpus accessor (R1).

Each pin guards one semantic the 42 bespoke readers kept re-implementing.
A change to accessor behavior moves WITH its pin or not at all.
"""
import csv
import math
from pathlib import Path

import pytest

from ml.corpus import (effective_n, gross_log_ret, gross_ret_pct, is_unknown,
                       net_ret_pct, read_rows, row_era, wilson_interval,
                       wilson_on_neff)

_COLS = ["side", "entry_price", "exit_price", "gate_confidence",
         "label_ret_pct", "label_era", "barrier", "label"]

_ROWS = [
    # long +2%: (102-100)/100
    {"side": "long", "entry_price": "100.0", "exit_price": "102.0",
     "gate_confidence": "0.9", "label_ret_pct": "1.39", "label_era":
     "triple_barrier_h432", "barrier": "", "label": "1"},
    # short: price fell 2%, side-adjusted gross must be POSITIVE +2
    {"side": "short", "entry_price": "50.0", "exit_price": "49.0",
     "gate_confidence": "0.7", "label_ret_pct": "", "label_era": "exit_sim",
     "barrier": "tb_time", "label": "1"},
    # UNKNOWN prices: gross unrecoverable, never 0
    {"side": "long", "entry_price": "", "exit_price": "",
     "gate_confidence": "", "label_ret_pct": "", "label_era": "",
     "barrier": "", "label": "0"},
    # zero entry price: unrecoverable, never a ZeroDivisionError
    {"side": "long", "entry_price": "0.0", "exit_price": "10.0",
     "gate_confidence": "0.5", "label_ret_pct": "", "label_era": "legacy",
     "barrier": "", "label": "0"},
]


@pytest.fixture()
def corpus_csv(tmp_path: Path) -> Path:
    p = tmp_path / "hist.csv"
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_COLS)
        w.writeheader()
        w.writerows(_ROWS)
    return p


def test_short_side_sign_adjustment(corpus_csv: Path):
    """A reader that forgets side adjustment reads every short backwards —
    the planted-defect form this pin exists to catch."""
    rows = read_rows(corpus_csv)
    assert gross_ret_pct(rows[0]) == pytest.approx(2.0)
    assert gross_ret_pct(rows[1]) == pytest.approx(2.0)  # short, price DOWN


def test_unknown_is_none_never_zero(corpus_csv: Path):
    rows = read_rows(corpus_csv)
    assert is_unknown(rows[2]["label_ret_pct"])
    assert gross_ret_pct(rows[2]) is None      # blank prices
    assert gross_ret_pct(rows[3]) is None      # zero entry, no ZeroDivision
    assert net_ret_pct(rows[2], 1.2) is None   # None propagates, not -1.2


def test_net_requires_named_cost(corpus_csv: Path):
    rows = read_rows(corpus_csv)
    assert net_ret_pct(rows[0], 1.2) == pytest.approx(0.8)
    assert net_ret_pct(rows[0], 0.5) == pytest.approx(1.5)


def test_persisted_era_beats_derived(corpus_csv: Path):
    """Row 1 persists 'exit_sim' while its barrier ('tb_time') would derive
    differently — the persisted tag must win (era-mixing defect class)."""
    rows = read_rows(corpus_csv)
    assert row_era(rows[1]) == "exit_sim"
    assert row_era(rows[0]) == "triple_barrier_h432"


def test_era_filter_never_pools(corpus_csv: Path):
    assert len(read_rows(corpus_csv)) == 4
    assert len(read_rows(corpus_csv, era="exit_sim")) == 1
    assert len(read_rows(corpus_csv, era="triple_barrier_h432")) == 1


def test_zero_exit_price_is_unknown_never_minus_100():
    """A live row for a still-open position stores exit_price=0.0. Reading
    that as a -100% return is the exit<=0 hole (adverse-selection audit,
    2026-08-29). Both the linear and log helpers must return None, never a
    spurious ±100% / -inf."""
    open_row = {"side": "long", "entry_price": "42000.0", "exit_price": "0.0"}
    assert gross_ret_pct(open_row) is None
    assert gross_log_ret(open_row) is None
    # a non-finite price on either leg is UNKNOWN too
    assert gross_ret_pct({"entry_price": "inf", "exit_price": "10"}) is None


def test_log_return_never_raises_on_underflow_ratio():
    """gross_log_ret must honor the never-throw contract even when both legs
    pass the sign/finite guards but the RATIO underflows to 0.0 (math.log(0)
    raises). Adversarial review 2026-08-29 — verified crash, now None."""
    underflow = {"side": "long", "entry_price": "1e300", "exit_price": "1e-300"}
    assert gross_log_ret(underflow) is None          # not a ValueError
    overflow = {"side": "long", "entry_price": "1e-300", "exit_price": "1e300"}
    assert gross_log_ret(overflow) is None


def test_short_side_is_case_insensitive():
    """'SHORT'/'Short'/' short ' must flip the sign like 'short' — an exact
    lowercase match silently read them as long (adversarial review)."""
    for s in ("SHORT", "Short", " short "):
        r = {"side": s, "entry_price": "100.0", "exit_price": "102.0"}
        assert gross_ret_pct(r) == pytest.approx(-2.0)
        assert gross_log_ret(r) == pytest.approx(-math.log(1.02))


def test_log_return_matches_linear_at_small_moves_and_adds():
    """gross_log_ret = side-adjusted ln(exit/entry). Sanity + the additivity
    property that makes it the profit/edge scale: a +2% then -2% round trip
    sums to ln(1.02)+ln(0.98) != 0 (the compounding drag linear % hides)."""
    up = {"side": "long", "entry_price": "100.0", "exit_price": "102.0"}
    dn = {"side": "long", "entry_price": "100.0", "exit_price": "98.0"}
    assert gross_log_ret(up) == pytest.approx(math.log(1.02))
    # short flips sign, like the linear helper
    sh = {"side": "short", "entry_price": "50.0", "exit_price": "49.0"}
    assert gross_log_ret(sh) == pytest.approx(math.log(50.0 / 49.0))
    # additive: cumulative log return of the pair is the log of the product
    assert (gross_log_ret(up) + gross_log_ret(dn)
            == pytest.approx(math.log(1.02 * 0.98)))


# --- effective-n + Wilson-on-n_eff -------------------------------------
# The corpus concurrency statistic and the Wilson interval evaluated on it,
# RELOCATED here 2026-08-29 from scripts/gate_truth_report (the de Prado
# candidate-row uniqueness) and scripts/gate_efficacy_report (Wilson). Each
# pin below is a mutation-kill: it reds if the lifted algorithm is broken.


def _hrow(asset: str, signal_ts: int, ts: int) -> dict:
    return {"asset": asset, "signal_ts": str(signal_ts), "ts": str(ts)}


def test_effective_n_full_overlap_collapses_to_one():
    """N identical same-asset rows share ONE return path -> n_eff ~= 1.0, not
    N. MUTATION-KILL: drop the 1/concurrency division (count sum(1) per bar)
    and this reads ~10 instead of 1.0."""
    rows = [_hrow("BTC", 1000, 1000) for _ in range(10)]
    n_eff, mean_u = effective_n(rows)
    assert n_eff == pytest.approx(1.0, abs=1e-9)
    assert mean_u == pytest.approx(0.1, abs=1e-9)


def test_effective_n_disjoint_windows_is_nominal():
    """Non-overlapping windows each carry a full independent fact -> n_eff=n."""
    rows = [_hrow("BTC", t, t) for t in (0, 10000, 20000, 30000, 40000)]
    n_eff, _ = effective_n(rows)
    assert n_eff == pytest.approx(5.0, abs=1e-9)


def test_effective_n_cross_asset_never_shares():
    """Same bar, DIFFERENT asset -> no shared path. MUTATION-KILL: drop the
    asset from the concurrency key and these two collapse to 1.0."""
    rows = [_hrow("BTC", 1000, 1000), _hrow("ETH", 1000, 1000)]
    n_eff, _ = effective_n(rows)
    assert n_eff == pytest.approx(2.0, abs=1e-9)


def test_effective_n_empty_is_zero():
    assert effective_n([]) == (0.0, 0.0)


def test_effective_n_zero_signal_ts_falls_back_not_megaspan():
    """signal_ts<=0 falls back to ts (a single-bar window), NOT a [0, ts]
    mega-span overlapping everything. Two same-asset rows on the same late
    bar: with the fallback both sit on one bar -> conc 2 -> n_eff 1.0; drop
    the fallback and row1's [0, ts] span smears across ~3300 bars, lifting
    n_eff to ~1.5."""
    late = 1_000_000
    rows = [{"asset": "BTC", "signal_ts": "0", "ts": str(late)},
            {"asset": "BTC", "signal_ts": str(late), "ts": str(late)}]
    n_eff, _ = effective_n(rows)
    assert n_eff == pytest.approx(1.0, abs=1e-9)


def test_wilson_on_neff_widens_on_low_effective_n():
    """THE named mutation-kill: the interval must run on EFFECTIVE n. At the
    same rate, a low n_eff gives a WIDE interval that straddles 0.5; feeding
    the (larger) nominal n instead collapses the width -> this reds."""
    lo8, hi8 = wilson_on_neff(0.5, 8.0)          # honest few independent obs
    lo200, hi200 = wilson_on_neff(0.5, 200.0)    # as if nominal n were used
    assert lo8 < 0.30 and hi8 > 0.70             # wide, straddles by a mile
    assert lo200 > 0.42 and hi200 < 0.58         # tight
    assert (hi8 - lo8) > (hi200 - lo200)         # strictly wider on low n_eff
    # the width change never moves the point estimate (rate=0.5 -> centered)
    assert (lo8 + hi8) / 2 == pytest.approx(0.5, abs=1e-9)


def test_wilson_on_neff_is_wilson_at_k_eff():
    """Double-derive: wilson_on_neff(rate, n_eff) is exactly the base Wilson
    at k_eff = rate*n_eff of n_eff trials — the identity the gate reports
    depend on."""
    for rate, neff in ((0.06, 100.0), (0.5, 8.0), (0.4639, 583.7)):
        assert wilson_on_neff(rate, neff) == wilson_interval(rate * neff, neff)


def test_wilson_interval_guards_and_bounds():
    assert wilson_interval(0.0, 0.0) == (0.0, 0.0)   # n<=0 guard
    lo, hi = wilson_interval(0.0, 50.0)              # all-losers stays in [0,1]
    assert lo >= 0.0 and hi <= 1.0


def test_effective_n_single_home_no_divergent_copy():
    """gate_truth_report must bind the SAME effective_n object relocated
    here — one home, no second copy that can silently drift (the exact
    anti-pattern the relocation removed)."""
    from scripts.gate_truth_report import effective_n as gt_effn
    assert gt_effn is effective_n
