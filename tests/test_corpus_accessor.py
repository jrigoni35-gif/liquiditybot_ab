"""Pins for ml/corpus.py — the canonical corpus accessor (R1).

Each pin guards one semantic the 42 bespoke readers kept re-implementing.
A change to accessor behavior moves WITH its pin or not at all.
"""
import csv
from pathlib import Path

import pytest

from ml.corpus import (NUMERIC_OPTIONAL, gross_ret_pct, is_unknown,
                       net_ret_pct, read_frame, read_rows, row_era)

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


def test_polars_parity_with_stdlib(corpus_csv: Path):
    """The fast lane must agree with the stdlib route row-for-row: same
    count, '' -> null (not 0) in NUMERIC_OPTIONAL, same gross returns."""
    pl = pytest.importorskip("polars")
    rows = read_rows(corpus_csv)
    df = read_frame(corpus_csv)
    assert df.height == len(rows)
    for col in NUMERIC_OPTIONAL:
        if col not in df.columns:
            continue
        assert df.schema[col] == pl.Float64
    # UNKNOWN survives typing: row 3's blank confidence is null, never 0.0
    conf = df["gate_confidence"].to_list()
    assert conf[2] is None
    # gross parity on the recoverable rows, including the short sign flip
    raw = (pl.col("exit_price") - pl.col("entry_price")) \
        / pl.col("entry_price") * 100.0
    g = df.select(
        pl.when(pl.col("side") == "short").then(-raw).otherwise(raw)
        .alias("g"))["g"]
    for i in (0, 1):
        assert g[i] == pytest.approx(gross_ret_pct(rows[i]))
