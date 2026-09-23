"""geometry-alignment T3: history rows carry their own barrier geometry.

pt_frac/sl_frac (ml/history.py HistoryStore._header, LAST two columns) are
ROW METADATA - the barrier_geometry() bracket a candidate's label was
computed under (spec D2/D6) - NEVER a ml.features.FEATURE_NAMES column.
Four guarantees, following the exact precedent of the prior schema bumps
(tests/test_migrate_history.py, tests/test_history_width_guard.py):

1. A legacy-header CSV (predates these two columns) migrates cleanly: row
   count unchanged, pt_frac/sl_frac appended with the documented 0.0 =
   "unknown/legacy geometry" default (scripts/migrate_history.py).
2. A NEW row written via CandidateLabeler.poll() -> _emit_label carries the
   REAL bracket it was labeled under (nonzero, ratio == pt_mult/sl_mult).
3. load_training_data's feature matrix width is unchanged - these are meta
   columns, never leaked into X.
4. Migrating an already-migrated file is idempotent: real geometry values
   pass through unchanged (never re-padded to the neutral default), and a
   second file-level migration pass into the same dest writes zero new
   rows (position_id-keyed dedupe, scripts/migrate_history.py main() -
   mirrors test_migrate_history.py's
   test_in_place_dest_rotation_does_not_self_dedupe).
"""
import csv
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import CandidateLabeler, HistoryStore
from scripts.migrate_history import migrate_rows

REPO = Path(__file__).resolve().parents[1]

# meta columns a genuine pre-T3 signal-history file must carry - mirrors
# tests/test_migrate_history.py's own OLD_FEATS/_old_file fixture.
_OLD_FEATS = ["ret_1", "imbalance", "direction", "gate_confidence"]

# same synthetic candle path as tests/test_barrier_geometry.py's Step 6
# wiring proof: a 5-bar horizon that resolves (any barrier) so poll()
# writes exactly one row deterministically.
def _candle(t, price, hi, lo):
    return {"time": t, "close": price, "high": hi, "low": lo, "volume": 1.0}


_PATH = [
    _candle(0, 100.0, 100.0, 100.0),
    _candle(1, 100.10, 100.15, 99.90),
    _candle(2, 100.45, 100.50, 100.10),
    _candle(3, 100.40, 100.55, 100.20),
    _candle(4, 100.50, 100.55, 100.30),
    _candle(5, 100.50, 100.55, 100.30),
]


def _legacy_file(path, n=3):
    header = ["position_id", "asset", "side", *_OLD_FEATS,
              "label", "net_pnl_usd", "source", "ts"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i in range(n):
            w.writerow([f"p{i}", "BTC", "long",
                        "0.100000", "0.200000", "1.000000", "0.750000",
                        str(i % 2), "5.00", "live", "1700000000"])
    return path


def test_legacy_csv_migrates_pt_sl_frac_with_zero_default(tmp_path):
    src = _legacy_file(tmp_path / "old.csv", n=3)
    rows, _padded = migrate_rows(str(src))

    assert len(rows) == 3                          # row count unchanged
    store = HistoryStore(str(tmp_path / "unused.csv"))
    # gate-truth instrumentation T2 appended 7 sg_* columns AFTER pt_frac/
    # sl_frac - they are no longer the last two, but order is preserved.
    # name-anchored (price anchor 2026-08-04 trails the sg block, so
    # every negative index below shifted; names never do)
    h = store._header
    ipt, isg = h.index("pt_frac"), h.index("sg_flow")
    assert h[ipt:ipt + 2] == ["pt_frac", "sl_frac"]
    assert h[isg:isg + 7] == ["sg_flow", "sg_delta", "sg_accum",
                              "sg_burst", "sg_trend", "sg_evidence",
                              "sg_conc"]
    # 41b (2026-08-08): avail_* flags trail the price pair; name-anchored
    # like everything above so the next trailing bump shifts nothing here
    iep = h.index("entry_price")
    assert h[iep:iep + 2] == ["entry_price", "exit_price"]
    assert h[-1] == "control_arm"          # schema 95 (2026-08-27, sandbox)
    assert h[-2] == "label_ret_pct"        # schema 94 (2026-08-24)
    assert h[-7:-2] == ["avail_web", "avail_equity", "avail_options",
                       "quotes_frozen", "avail_darkpool"]  # 96 (09-21, v10)
    for row in rows:
        assert len(row) == len(h)                  # full current width
        assert float(row[ipt]) == 0.0               # pt_frac default
        assert float(row[ipt + 1]) == 0.0           # sl_frac default
        assert all(float(v) == 0.0 for v in row[isg:isg + 7])  # sg_*
        assert row[iep:iep + 2] == ["0", "0"]       # price pair: absent
        # migrated legacy rows never measured availability: blank UNKNOWN
        assert row[-6:-1] == ["", "", "", "", ""]
        # control_arm: a genuinely pre-bump row predates the tag - "" =
        # not-designated, NEVER backfilled (migrate_history.py never
        # computes one for a legacy row; see its own comment for why).
        assert row[-1] == ""


def test_labeler_path_writes_real_pt_sl_frac(tmp_path):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    pt_mult, sl_mult = 8.0, 6.0
    ml_cfg = {"label_max_bars": 5, "label_pt_vol_mult": pt_mult,
              "label_sl_vol_mult": sl_mult, "label_round_trip_cost_pct": 0.5,
              "label_include_spread": False, "label_mode": "triple_barrier",
              "label_pt_cost_mult": 4.0}
    lab = CandidateLabeler(store, ml_cfg)
    feats = np.zeros(len(FEATURE_NAMES))
    lab.register("BTC", "long", feats, sigma_bar=0.0005, bar_time=0)
    lab.update_candles("BTC", _PATH)
    assert lab.poll() == 1

    with open(store.path, encoding="utf-8") as f:
        row = list(csv.DictReader(f))[0]

    pt_frac = float(row["pt_frac"])
    sl_frac = float(row["sl_frac"])
    assert pt_frac != 0.0 and sl_frac != 0.0
    assert abs(pt_frac / sl_frac - pt_mult / sl_mult) < 1e-9


def test_load_training_data_feature_width_unchanged_by_new_columns(
        tmp_path, monkeypatch):
    # freeze the wall clock (34bb82d precedent): _append_row's default ts
    # and load_training_data's recency-decay reference both read
    # time.time() - an unfrozen clock straddling the call risks a flake
    # this test's assertions don't even need (shape/count only).
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
    store = HistoryStore(str(tmp_path / "hist.csv"))
    feats = np.zeros(len(FEATURE_NAMES))
    store._append_row("p1", "BTC", "long", feats, 1, 5.0, "live",
                      pt_frac=0.02, sl_frac=0.015)
    store._append_row("p2", "ETH", "short", feats, 0, -3.0, "live")

    X, y, w = store.load_training_data()
    assert X.shape[1] == len(FEATURE_NAMES)          # metadata never leaks
    assert len(y) == 2 and len(w) == 2


def test_migrating_an_already_migrated_file_is_idempotent(tmp_path):
    store = HistoryStore(str(tmp_path / "hist.csv"))
    feats = np.zeros(len(FEATURE_NAMES))
    store._append_row("p1", "BTC", "long", feats, 1, 5.0, "live",
                      pt_frac=0.02, sl_frac=0.015)

    # migrate_rows on an ALREADY-current-schema file must pass real values
    # through unchanged - a second migration pass must never clobber real
    # geometry with the neutral default.
    rows, padded = migrate_rows(str(store.path))
    assert padded == []                              # nothing left to pad
    # gate-truth instrumentation T2 appended 7 sg_* columns AFTER pt_frac/
    # sl_frac - they are no longer the last two.
    _h = store._header
    assert float(rows[0][_h.index("pt_frac")]) == 0.02
    assert float(rows[0][_h.index("sl_frac")]) == 0.015

    # file-level idempotence: dest already holds the migrated row, a second
    # pass with the same src must skip it (dedupe by position_id) and write
    # nothing new.
    dest = tmp_path / "dest.csv"
    shutil.copy2(store.path, dest)
    r = subprocess.run(
        [sys.executable, "scripts/migrate_history.py",
         "--src", str(store.path), "--dest", str(dest)],
        capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    assert "migrated 0 rows" in r.stdout, r.stdout

    with open(dest, newline="", encoding="utf-8") as f:
        rows_after = list(csv.DictReader(f))
    assert len(rows_after) == 1
    assert rows_after[0]["pt_frac"] == "0.020000"
    assert rows_after[0]["sl_frac"] == "0.015000"
