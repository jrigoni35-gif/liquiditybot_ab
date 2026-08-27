"""Trial ledger: schema round-trip, validation, measured-N semantics.

The ledger is the TRIALS-1 artifact: OF-5's deflated Sharpe will read a
MEASURED trial count from it under a ratchet. Rows must be complete and
enum-legal or the reader refuses loudly (OF-5 then falls back, also
loudly). sr/max_dd/n_eff are nullable by design in v0.1 (spec: sr stays
empty behind TRIPS_FLOOR=20)."""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.trial_ledger import (LEDGER_COLUMNS, LedgerInvalid,  # noqa: E402
                                  SCHEMA_VERSION, append_rows,
                                  measured_trials, read_ledger, write_meta)


def _row(**over):
    base = {"schema_version": SCHEMA_VERSION, "strategy_id": "naive_grid",
            "source": "battery", "seed": 1, "fee_anchor": "booked",
            "harness_profile": "neutral-admission", "cycles": 60,
            "entries": 3, "exits": 2, "gross_pct": 0.41, "net_pct": -0.12,
            "sr": "", "max_dd": "", "n_eff": "", "degenerate": False,
            "exit_profile": "deployed", "count": 1}
    base.update(over)
    return base


def test_round_trip_and_columns(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row(), _row(strategy_id="buy_hold", seed=2)], p)
    rows = read_ledger(p)
    assert len(rows) == 2
    assert set(rows[0]) == set(LEDGER_COLUMNS)
    assert rows[0]["strategy_id"] == "naive_grid"
    assert rows[0]["degenerate"] is False


def test_invalid_source_refused(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row(source="vibes")], p)
    with pytest.raises(LedgerInvalid):
        read_ledger(p)


def test_measured_trials_counts_distinct_and_harvest(tmp_path):
    rows = [_row(), _row(seed=2),                        # same trial, 2 tapes
            _row(strategy_id="buy_hold"),                # second trial
            _row(source="harvest", strategy_id="tune_search",
                 harness_profile="n/a", count=57)]       # harvest N=57
    m = measured_trials(rows)
    assert m["n_trials"] == 2 + 57
    assert m["by_source"] == {"battery": 3, "harvest": 1}


def test_meta_counters(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row()], p)
    write_meta(p, attempted=4, accepted=1, refused=3,
               notes=["determinism refused 3 rows"])
    meta = json.loads((p.with_suffix(".meta.json")).read_text(encoding="utf-8"))
    assert meta["attempted"] == 4 and meta["refused"] == 3
    assert meta["schema_version"] == SCHEMA_VERSION


def test_sr_max_dd_n_eff_round_trip_to_none(tmp_path):
    # nullable-SR-behind-TRIPS_FLOOR contract: '' in CSV -> None after read.
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row(sr="", max_dd="", n_eff="")], p)
    rows = read_ledger(p)
    assert rows[0]["sr"] is None
    assert rows[0]["max_dd"] is None
    assert rows[0]["n_eff"] is None


def test_invalid_fee_anchor_battery_raises(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row(source="battery", fee_anchor="unbooked")], p)
    with pytest.raises(LedgerInvalid):
        read_ledger(p)


def test_append_rows_atomic_on_mid_batch_invalid(tmp_path):
    # finding 1: a missing-column row mid-batch must not leave earlier
    # rows of that same batch flushed to disk, and must not touch
    # pre-existing ledger content either.
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row()], p)
    before = p.read_text(encoding="utf-8")
    bad = _row(strategy_id="incomplete", seed=3)
    del bad["count"]
    with pytest.raises(LedgerInvalid):
        append_rows([_row(strategy_id="buy_hold", seed=2), bad], p)
    assert p.read_text(encoding="utf-8") == before


def test_write_meta_creates_missing_parent_dir(tmp_path):
    # finding 2: the all-refused case the sidecar exists to record can
    # land on a fresh tree with no ledger directory yet.
    p = tmp_path / "fresh" / "tree" / "trial_ledger.csv"
    assert not p.parent.exists()
    write_meta(p, attempted=3, accepted=0, refused=3, notes=["all refused"])
    meta_path = p.with_suffix(".meta.json")
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["attempted"] == 3 and meta["accepted"] == 0


@pytest.mark.parametrize("bad_value", ["garbage", "1"])
def test_degenerate_invalid_value_raises(tmp_path, bad_value):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row(degenerate=bad_value)], p)
    with pytest.raises(LedgerInvalid):
        read_ledger(p)


def test_count_truncated_row_raises(tmp_path):
    # finding 4: a row truncated mid-write (fewer fields than the
    # header) makes DictReader yield restval=None for "count", the
    # trailing column -- distinct from a present-but-blank field.
    p = tmp_path / "trial_ledger.csv"
    row = _row()
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(LEDGER_COLUMNS)
        w.writerow([row[c] for c in LEDGER_COLUMNS[:-1]])  # omit "count"
    with pytest.raises(LedgerInvalid):
        read_ledger(p)


def test_harvest_counts_and_absent(tmp_path):
    from scripts.trial_ledger import harvest
    out = tmp_path / "outputs"
    (out / "sweeps").mkdir(parents=True)
    (out / "sweeps" / "sweep_1.csv").write_text(
        "position_sizer.kelly_fraction,realized_pnl\n0.1,-1\n0.2,2\n0.3,0\n",
        encoding="utf-8")
    (out / "tune_search_state.json").write_text(
        '{"evaluated": [{"theta": [1], "objective": 0.1},'
        ' {"theta": [2], "objective": 0.2}]}', encoding="utf-8")
    rows, absent = harvest(out)
    by_id = {r["strategy_id"]: r["count"] for r in rows}
    assert by_id["sweep:sweep_1.csv"] == 3
    assert by_id["tune_search"] == 2
    assert by_id["geometry_search_grid"] == 48   # static, from module constants
    assert by_id["of3_model_space"] == 9         # ml/overfit._BASE_ORDER
    assert absent == []


def test_harvest_reports_absent_sources(tmp_path):
    from scripts.trial_ledger import harvest
    rows, absent = harvest(tmp_path / "outputs")   # dir doesn't exist
    ids = {r["strategy_id"] for r in rows}
    assert ids == {"geometry_search_grid", "of3_model_space"}
    assert set(absent) == {"tune_search_state.json", "sweeps/*.csv"}
