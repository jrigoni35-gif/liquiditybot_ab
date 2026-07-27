"""Local-rotation recovery: rows stranded in signal_history.bak_* must be
re-imported, not lost.

A schema bump rotates the live CSV to .bak; the durable branch only holds
rows up to the last hourly backup, so labels banked in between exist ONLY in
the local .bak (observed live 2026-07-19: live labels #46/#47 + ~19
candidates stranded by the barrier-column bump). corpus_sync now migrates +
merges every .bak (dedup by position_id), then renames it .recovered —
idempotent, and the file is renamed, never deleted.
"""
import csv

import numpy as np

import scripts.corpus_sync as cs
from ml.features import FEATURE_NAMES
from ml.history import (CORPUS_ROTATION_MARKER_NAME, HistoryStore,
                        label_era_of)


def _old_schema_bak(path, rows):
    """Write a pre-barrier (66-col) rotation file: the exact shape the
    2026-07-19 bump stranded."""
    header = ["position_id", "asset", "side", *FEATURE_NAMES,
              "label", "net_pnl_usd", "source", "ts", "signal_ts"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i, (pid, label, source) in enumerate(rows):
            # distinct per-row features: identical live/candidate features
            # would (correctly) trip the loader's synthetic-twin clash guard,
            # which is not what this test measures
            feats = np.full(len(FEATURE_NAMES), 0.1 * (i + 1))
            w.writerow([pid, "ETH", "long",
                        *[f"{v:.6f}" for v in feats],
                        label, "1.00", source, "1000", "900"])


def test_stranded_bak_rows_are_recovered(tmp_path):
    out = tmp_path / "outputs"
    out.mkdir()
    hs = HistoryStore(str(out / "signal_history.csv"))
    hs._append_row("kept", "BTC", "long", np.zeros(len(FEATURE_NAMES)), 1,
                   2.0, "live", barrier="realized")
    _old_schema_bak(out / "signal_history.bak_111",
                    [("live46", 1, "live"), ("live47", 0, "live"),
                     ("cand-x", 0, "candidate"),
                     ("kept", 1, "live")])          # dup: must not double
    note = cs.recover_local_baks(tmp_path)
    assert note == "bak_recovered=3"
    with open(out / "signal_history.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ids = {r["position_id"] for r in rows}
    assert ids == {"kept", "live46", "live47", "cand-x"}
    # migrated rows are FULL current width (barrier back-filled empty)
    assert all(len(r) == len(hs._header) for r in rows)
    # the bak is renamed (kept on disk), so a second pass is a no-op
    assert not list(out.glob("signal_history.bak_111"))
    assert list(out.glob("signal_history.bak_111.recovered"))
    assert cs.recover_local_baks(tmp_path) == "no_baks"
    # and the merged corpus still loads cleanly under the current schema
    X, y, w = HistoryStore(str(out / "signal_history.csv")).load_training_data()
    assert len(X) == 4


def test_no_baks_is_quiet(tmp_path):
    (tmp_path / "outputs").mkdir()
    assert cs.recover_local_baks(tmp_path) == "no_baks"


# ---------------------------------------------------------------------
# Full rollout sequence (a063fe0 label_era column bump), reproduced
# end-to-end exactly as the reviewer found it live: a production corpus
# under the OLD header gets appended against the NEW (label_era-bearing)
# header, _ensure_schema itself rotates the whole thing to a .bak_<ts> and
# starts a near-empty file (never manually pre-staged, unlike the fixture
# above) - THIS is the path recover_local_baks had zero coverage for
# before this task. Pins: the live file really does go near-empty, the
# .bak really appears, recovery restores the ORIGINAL row count, and -
# the label_era-specific hazard - every recovered row carries the era its
# OWN barrier implies, not a blanket default.
# ---------------------------------------------------------------------

def test_rollout_rotation_end_to_end_recovers_rows_with_correct_era(tmp_path):
    out = tmp_path / "outputs"
    out.mkdir()
    dest = out / "signal_history.csv"
    hs = HistoryStore(str(dest))
    # production schema pre-label_era: drop label_era AND the two
    # geometry-alignment T3 columns that joined after it (pt_frac, sl_frac)
    old_header = hs._header[:-3]

    # known rows spanning all three label-era buckets, so a recovery that
    # silently defaulted everything to "legacy" (or dropped barrier) would
    # be caught immediately
    known = [("legacy-blank", "", 1), ("legacy-pt", "pt", 0),
             ("sim-trail", "trail", 1), ("sim-sl", "sl", 0),
             ("stop-a", "time_stop", 0)]
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(old_header)
        for i, (pid, barrier, label) in enumerate(known):
            feats = np.full(len(FEATURE_NAMES), 0.1 * (i + 1))
            w.writerow([pid, "ETH", "long", *[f"{v:.6f}" for v in feats],
                        label, "1.00", "live", "1000", "900",
                        barrier, "", "", "", "5m"])
    with open(dest, newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == len(known)   # sanity: 5 seeded

    # append under the CURRENT header -> _ensure_schema must detect the
    # mismatch itself and rotate (the reviewer's reproduction: N rows in,
    # 1 row out)
    hs._append_row("new-live", "BTC", "long", np.zeros(len(FEATURE_NAMES)),
                   1, 3.0, "live", barrier="realized")

    with open(dest, newline="", encoding="utf-8") as f:
        live_rows = list(csv.DictReader(f))
    assert len(live_rows) == 1 and live_rows[0]["position_id"] == "new-live"
    baks = list(out.glob("signal_history.bak_*"))
    assert len(baks) == 1
    marker = out / CORPUS_ROTATION_MARKER_NAME
    assert marker.exists()               # rotation left the fast-path marker

    note = cs.recover_local_baks(tmp_path)
    assert note == f"bak_recovered={len(known)}"

    with open(dest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(known) + 1   # every stranded row + the live one
    by_id = {r["position_id"]: r for r in rows}
    for pid, barrier, _ in known:
        assert by_id[pid]["label_era"] == label_era_of(barrier), pid
    assert by_id["new-live"]["label_era"] == label_era_of("realized")

    # one-shot: the .bak is renamed (never deleted), never rediscovered
    live_baks = [b for b in out.glob("signal_history.bak_*")
                if not b.name.endswith(".recovered")]
    assert not live_baks
    assert list(out.glob("signal_history.bak_*.recovered"))
    assert cs.recover_local_baks(tmp_path) == "no_baks"

    # the fully-recovered corpus still loads cleanly under the current schema
    X, y, w = HistoryStore(str(dest)).load_training_data()
    assert len(X) == len(known) + 1
