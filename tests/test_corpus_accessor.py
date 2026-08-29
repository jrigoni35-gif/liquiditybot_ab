"""Pins for ml/corpus.py — the canonical corpus accessor (R1).

Each pin guards one semantic the 42 bespoke readers kept re-implementing.
A change to accessor behavior moves WITH its pin or not at all.
"""
import csv
import math
from pathlib import Path

import pytest

from ml.corpus import (gross_log_ret, gross_ret_pct, is_unknown, net_ret_pct,
                       read_rows, row_era)

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
