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
from ml.history import HistoryStore


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
