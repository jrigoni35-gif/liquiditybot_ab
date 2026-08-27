"""Trial ledger: schema round-trip, validation, measured-N semantics.

The ledger is the TRIALS-1 artifact: OF-5's deflated Sharpe will read a
MEASURED trial count from it under a ratchet. Rows must be complete and
enum-legal or the reader refuses loudly (OF-5 then falls back, also
loudly). sr/max_dd/n_eff are nullable by design in v0.1 (spec: sr stays
empty behind TRIPS_FLOOR=20)."""
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
    import json
    meta = json.loads((p.with_suffix(".meta.json")).read_text(encoding="utf-8"))
    assert meta["attempted"] == 4 and meta["refused"] == 3
    assert meta["schema_version"] == SCHEMA_VERSION
