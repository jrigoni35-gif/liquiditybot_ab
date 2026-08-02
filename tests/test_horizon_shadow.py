"""HorizonShadowStore: the multi-horizon research dataset.

It recorded 23,826 outcomes before 2026-08-01 that were ANALYTICALLY INERT -
no sigma, no barrier fractions, and no usable join back to signal_history
(70 of 8,429 history rows carried a candidate_id, 0.83%). The horizon
question the recorder exists to answer was unanswerable from its own output.

The unit pins below matter more than they look. The first draft of the
enriched schema named the sigma column sigma_bar_pct and wrote
cand["sigma_bar"] into it - a 100x error, because the FEATURE column of that
name in signal_history.csv is a PERCENT while cand["sigma_bar"] is a
FRACTION. Same class as the CSCV label_span bars-vs-seconds bug: a research
value that parses cleanly and means something else.
"""
import csv
import math

from ml.history import HorizonShadowStore
from ml.labeling import barrier_geometry


def _read(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---- unit contract ---------------------------------------------------------
def test_all_three_quantities_share_one_unit_so_the_ratio_needs_no_scaling():
    """barrier_geometry is the ground truth for the unit: feeding it a
    FRACTION sigma reproduces the observed live minimums exactly
    (pt 0.020000 / sl 0.015000), while a PERCENT sigma reproduces nothing.
    Anything writing a percent into these columns is a 100x error."""
    pt_f, sl_f = barrier_geometry(0.001033, 0.5, 8.0, 6.0, 4.0)
    assert round(pt_f, 6) == 0.020000
    assert round(sl_f, 6) == 0.015000
    # and the ratio the whole dataset exists to support is unit-free
    ratio = pt_f / (0.001033 * math.sqrt(24))
    assert 3.9 < ratio < 4.2, "PT/(sigma*sqrt(h)) must be directly computable"


def test_append_records_sigma_and_both_barrier_fractions(tmp_path):
    p = tmp_path / "hs.csv"
    HorizonShadowStore(str(p)).append(
        "cand-1", "ETH", "long", 24, 1, -0.37, "time",
        sigma_bar_frac=0.001033, pt_frac=0.02058, sl_frac=0.01543)
    row = _read(p)[0]
    assert "sigma_bar_frac" in row, "column must NAME its unit"
    assert "sigma_bar_pct" not in row
    assert float(row["sigma_bar_frac"]) == 0.001033
    assert float(row["pt_frac"]) == 0.02058
    assert float(row["sl_frac"]) == 0.01543


# ---- sanitization rounds ---------------------------------------------------
def test_non_finite_values_are_rejected_not_written(tmp_path):
    """NaN compares false to every bound, so it survives a naive range
    check and lands in the dataset as a number-shaped hole."""
    p = tmp_path / "hs.csv"
    s = HorizonShadowStore(str(p))
    s.append("c", "ETH", "long", 24, 0, 0.1, "time",
             sigma_bar_frac=float("nan"), pt_frac=float("inf"),
             sl_frac=float("-inf"))
    row = _read(p)[0]
    assert row["sigma_bar_frac"] == ""
    assert row["pt_frac"] == ""
    assert row["sl_frac"] == ""


def test_non_positive_values_are_rejected_as_sign_errors(tmp_path):
    """A negative sigma or barrier distance is not a small number, it is a
    sign error upstream; zero cannot be divided by."""
    p = tmp_path / "hs.csv"
    HorizonShadowStore(str(p)).append(
        "c", "ETH", "long", 24, 0, 0.1, "time",
        sigma_bar_frac=-0.001, pt_frac=0.0, sl_frac=0.015)
    row = _read(p)[0]
    assert row["sigma_bar_frac"] == "" and row["pt_frac"] == ""
    assert float(row["sl_frac"]) == 0.015      # the valid one survives


def test_unparseable_types_reject_rather_than_raise(tmp_path):
    """Recording must never break labeling (the call site is best-effort)."""
    p = tmp_path / "hs.csv"
    HorizonShadowStore(str(p)).append(
        "c", "ETH", "long", 24, 0, 0.1, "time",
        sigma_bar_frac="not-a-number", pt_frac=object(), sl_frac="0.015")
    row = _read(p)[0]
    assert row["sigma_bar_frac"] == "" and row["pt_frac"] == ""
    assert float(row["sl_frac"]) == 0.015      # numeric strings still parse


def test_tiny_values_do_not_emit_scientific_notation(tmp_path):
    """A column parsed positionally downstream must not receive '1e-05'
    where a decimal is expected, and must not lose a real small sigma."""
    p = tmp_path / "hs.csv"
    HorizonShadowStore(str(p)).append(
        "c", "ETH", "long", 24, 0, 0.1, "time", sigma_bar_frac=1e-5,
        pt_frac=0.02, sl_frac=0.015)
    row = _read(p)[0]
    assert float(row["sigma_bar_frac"]) == 1e-5   # value preserved
    assert "e" not in row["pt_frac"].lower()


# ---- schema safety ---------------------------------------------------------
def test_legacy_callers_still_work_without_the_new_fields(tmp_path):
    p = tmp_path / "hs.csv"
    HorizonShadowStore(str(p)).append("c", "BTC", "short", 96, 0, 1.5, "pt")
    row = _read(p)[0]
    assert row["exit_reason"] == "pt"
    assert row["sigma_bar_frac"] == ""


def test_old_schema_file_is_rotated_not_corrupted(tmp_path):
    """Appending 11-column rows onto an 8-column file yields a dataset that
    parses cleanly and means something else. Rotate, and never delete."""
    p = tmp_path / "hs.csv"
    old = ["candidate_id", "asset", "direction", "horizon_bars",
           "label", "net_ret_pct", "exit_reason", "ts"]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(old)
        w.writerow(["c0", "SOL", "long", 24, 1, "0.5", "pt", "1780000000"])

    HorizonShadowStore(str(p)).append(
        "c1", "ETH", "long", 48, 0, -0.2, "sl",
        sigma_bar_frac=0.0011, pt_frac=0.02, sl_frac=0.015)

    baks = list(tmp_path.glob("hs.bak_*.csv"))
    assert len(baks) == 1, "old rows must be preserved by rotation"
    assert _read(baks[0])[0]["candidate_id"] == "c0"    # nothing lost

    rows = _read(p)
    assert len(rows) == 1 and rows[0]["candidate_id"] == "c1"
    assert float(rows[0]["sigma_bar_frac"]) == 0.0011   # correctly aligned
