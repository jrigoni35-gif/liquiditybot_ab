"""Pins for scripts/discard_ledger.py - the missing discard aggregator.

WHY THIS FILE EXISTS. The ledger's whole value is that it is the ONE place a
reader learns how much evidence is being thrown away, so a wrong number here
is worse than no number at all - it would be a confident aggregate nobody
cross-checks. Two of its four planes shipped WRONG in their first version,
each reproducing a share that a 2026-09-16 verification pass had already
refuted (a "92.4% of trips outside the gate" denominator error, and an
"87.87% stale geometry" classification error). Both are pinned below by the
property that was violated, not by the number that came out.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

dl = pytest.importorskip("scripts.discard_ledger")

FILL_COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
             "ordertype", "post_only", "attempt", "fill_size", "fill_price",
             "arrival_ref", "slip_bps", "fees_delta_usd", "remaining",
             "reason", "exec_era", "book"]


def _fills(tmp_path: Path, legs: list[dict]) -> Path:
    p = tmp_path / "fills.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILL_COLS)
        w.writeheader()
        for i, leg in enumerate(legs):
            row = {c: "" for c in FILL_COLS}
            row.update(leg)
            row.setdefault("order_id", f"o{i}")
            w.writerow(row)
    return p


def _trip(pid: str, era: str) -> list[dict]:
    return [{"position_id": pid, "side": "buy", "exec_era": era},
            {"position_id": pid, "side": "sell", "exec_era": era}]


# ---------------------------------------------------------------- plane 2
def test_trips_that_predate_stamping_are_not_charged_to_a_mint(tmp_path):
    """THE DENOMINATOR PIN, and the defect it guards is measured.

    The first version reported "5.9% counted by the gate" using LIFETIME
    trips as the denominator. 398 of those 543 trips carried no era stamp at
    all - they predate stamping and were never excluded BY a mint. Charging
    them to one is the exact error that produced a refuted "92.4% of trips
    outside the gate" figure. The cost of a mint is measured against STAMPED
    trips.
    """
    legs = []
    for i in range(10):                       # 10 trips, no stamp at all
        legs += _trip(f"old{i}", "")
    for i in range(3):                        # 3 in the current era
        legs += _trip(f"cur{i}", "E2")
    for i in range(2):                        # 2 in a previous era
        legs += _trip(f"prev{i}", "E1")
    res = dl.trade_cohort(_fills(tmp_path, legs), "E2")

    assert res["available"]
    assert res["closed_trips_lifetime"] == 15
    assert res["predate_stamping"] == 10
    assert res["closed_trips_stamped"] == 5, "the denominator picked up unstamped trips"
    assert res["counted_by_the_gate"] == 3
    assert res["belong_to_a_previous_era"] == 2
    # 3 of 5 STAMPED, never 3 of 15
    assert res["share_of_stamped_counted_pct"] == 60.0
    assert res["share_of_stamped_refused_pct"] == 40.0


def test_a_straddler_is_censored_not_counted(tmp_path):
    """A trip whose legs carry different stamps belongs to NO era: the
    stamp-purity rule refuses it on both sides. It is evidence that exists
    and counts for nothing, and that censoring is the cost nobody prices."""
    legs = _trip("pure", "E2")
    legs += [{"position_id": "strad", "side": "buy", "exec_era": "E1"},
             {"position_id": "strad", "side": "sell", "exec_era": "E2"}]
    res = dl.trade_cohort(_fills(tmp_path, legs), "E2")

    assert res["counted_by_the_gate"] == 1
    assert res["censored_in_flight"] == 1
    assert res["belong_to_a_previous_era"] == 0, \
        "a straddler was charged to the previous era instead of censored"


def test_a_one_sided_position_is_not_a_closed_trip(tmp_path):
    """An entry with no exit is an OPEN position, not a discarded one.
    Counting it would inflate every share on this plane."""
    legs = _trip("closed", "E2")
    legs += [{"position_id": "open", "side": "buy", "exec_era": "E2"}]
    res = dl.trade_cohort(_fills(tmp_path, legs), "E2")
    assert res["closed_trips_lifetime"] == 1


# ---------------------------------------------------------------- plane 3
def _history(tmp_path: Path, rows: list[dict], extra_cols=()) -> Path:
    cols = ["label_era", "pt_frac", "ts", "asset", "note", *extra_cols]
    p = tmp_path / "signal_history.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return p


def test_the_cost_regimes_are_partitioned_by_DATE_not_by_a_tolerance(tmp_path):
    """THE CLASSIFICATION PIN.

    barrier_geometry floors pt_frac at pt_cost_mult*cost/100, but measured
    2026-09-16 ZERO live rows sit at that value: the minimum is 0.0180030
    against a floor of 0.0180000, because 5 m crypto sigma sits right AT
    cost/2. So floor-bound vs sigma-bound is NOT separable from pt_frac and
    the answer is purely a choice of tolerance - two defensible ones gave
    34.8% and 82.9% on the same rows. The ledger must partition by WHEN a row
    was written, which needs no tolerance, and must PROVE the split by
    showing the two sides are disjoint in pt_frac.
    """
    rows = []
    for i in range(6):                   # old regime, wider floor
        rows.append({"label_era": "triple_barrier_h432", "pt_frac": "0.024003",
                     "ts": str(1_789_000_000 + i)})
    for i in range(4):                   # new regime, tighter floor
        rows.append({"label_era": "triple_barrier_h432", "pt_frac": "0.018003",
                     "ts": str(1_789_500_000 + i)})
    res = dl.label_geometry(_history(tmp_path, rows))

    assert res["available"], res.get("reason")
    assert res["rows"] == 10
    assert res["rows_under_a_retired_cost"] == 6
    assert res["rows_under_the_current_cost"] == 4
    assert res["share_under_a_retired_cost_pct"] == 60.0
    sc = res["separation_check"]
    assert sc["disjoint"] is True, \
        "the two cost regimes overlap - the date partition is not clean"
    assert sc["min_pt_before"] > sc["min_pt_after"]


def test_the_ledger_refuses_to_name_a_contaminated_share(tmp_path):
    """NEGATIVE PIN. A row whose sigma dominated the floor carries the SAME
    width today, so it is not contaminated. The contaminated subset is
    therefore somewhere in [0, share-under-retired-cost] and pt_frac cannot
    pin it. The ledger must SAY that rather than publish a number - the first
    version published 85.8% and it was wrong."""
    rows = [{"label_era": "triple_barrier_h432", "pt_frac": "0.024003",
             "ts": "1789000000"},
            {"label_era": "triple_barrier_h432", "pt_frac": "0.018003",
             "ts": "1789500000"}]
    res = dl.label_geometry(_history(tmp_path, rows))
    assert "not_established" in res
    assert "contaminated" in res["not_established"]
    for banned in ("floor_bound_rows", "sigma_bound_rows",
                   "rows_on_a_retired_floor"):
        assert banned not in res, \
            f"{banned} re-introduces the tolerance-dependent classification"


def test_embedded_commas_do_not_shift_the_columns(tmp_path):
    """Measured 2026-09-16: 4,932 rows of the live corpus carry commas inside
    quoted fields, and a plain comma split read the wrong column - 19,414
    became 14,543. Any reader of this file that is not the csv module is a
    defect. Pinned behaviourally: a row whose free-text field contains commas
    must still be parsed correctly."""
    rows = [{"label_era": "triple_barrier_h432", "pt_frac": "0.024003",
             "ts": "1789000000", "note": "a, b, c, d"},
            {"label_era": "triple_barrier_h432", "pt_frac": "0.018003",
             "ts": "1789500000", "note": "e, f, g"}]
    res = dl.label_geometry(_history(tmp_path, rows))
    assert res["available"], res.get("reason")
    assert res["rows"] == 2, "embedded commas shifted the parse"


def test_a_corpus_with_one_regime_reports_nothing_retired(tmp_path):
    """The calibration arm. One cost regime means nothing is stale, and a
    function that always found staleness would pass every pin above."""
    rows = [{"label_era": "triple_barrier_h432", "pt_frac": "0.018003",
             "ts": str(1_789_000_000 + i)} for i in range(5)]
    res = dl.label_geometry(_history(tmp_path, rows))
    assert res["rows_under_a_retired_cost"] == 0
    assert res["share_under_a_retired_cost_pct"] == 0.0


# ---------------------------------------------------------------- plane 1
def test_the_training_plane_sums_every_named_discard():
    status = {"ml": {"load_stats": {
        "dropped_parse": 1, "dropped_dirty": 2, "dropped_clash": 3,
        "epoch_excluded": 4, "rows": 100, "live_clean": 7,
        "mean_uniqueness": 0.05, "ess_kish": 55.5,
        "era_exclusion": {"armed": True, "active": True,
                          "excluded": {"total": 90}}}}}
    res = dl.training_corpus(status)
    assert res["available"]
    assert res["discard_total"] == 1 + 2 + 3 + 4 + 90
    assert res["admissible"] == 100 + 100
    assert res["n_eff_per_asset"] == 5.0        # 100 rows x 0.05 uniqueness
    assert "per-(asset" in res["n_eff_route"], \
        "the effective-n ROUTE must travel with the number"


def test_the_training_plane_degrades_closed_with_a_reason():
    """No load_stats means UNAVAILABLE and a reason - never a zero. A zero
    would read as 'nothing is being discarded', which is the opposite of the
    truth and the most expensive possible failure for this instrument."""
    for status in ({}, {"ml": {}}, {"ml": {"load_stats": {}}}, None):
        res = dl.training_corpus(status)
        assert res["available"] is False
        assert res.get("reason")
        assert "discard_total" not in res


# ---------------------------------------------------------------- contract
def test_the_ledger_writes_nothing_anywhere(tmp_path, monkeypatch):
    """REPORT-ONLY is the claim that makes this SAFE class under the era-12
    moratorium. Pinned with an audit hook rather than by inspection, because
    a write added later would be invisible to a reading review."""
    import os

    writes: list[str] = []

    def _audit(event, args):
        if event == "open" and len(args) > 1:
            mode = args[1]
            if isinstance(mode, str) and any(c in mode for c in "wxa+"):
                writes.append(str(args[0]))
        elif event in ("os.rename", "os.replace", "os.remove", "os.unlink",
                       "os.mkdir"):
            writes.append(str(args[0]))

    monkeypatch.setenv("LB_OUTPUTS", str(tmp_path))
    sys.addaudithook(_audit)
    dl.collect()
    assert not writes, f"the report-only ledger wrote: {writes[:5]}"
    assert not list(tmp_path.iterdir()), "it created files in outputs/"
    assert os.environ.get("LB_OUTPUTS") == str(tmp_path)


def test_render_never_raises_on_a_fully_unavailable_collect(tmp_path,
                                                            monkeypatch):
    """Every plane can legitimately be UNAVAILABLE (a fresh checkout has no
    outputs/). The renderer must still produce a page - an instrument that
    crashes when it has nothing to say teaches the reader to stop running
    it."""
    monkeypatch.setenv("LB_OUTPUTS", str(tmp_path))
    text = dl.render(dl.collect())
    assert "DISCARD LEDGER" in text
    assert text.count("UNAVAILABLE") >= 3
