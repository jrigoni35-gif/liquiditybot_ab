"""tests/test_session_import_migrate.py — a learning bundle on an OLDER feature
schema is auto-migrated on import, not stranded.

The leak this closes: every FEATURE_NAMES bump changed the current schema width,
so session_import refused every backup bundle written before it ("SCHEMA
MISMATCH ... route through migrate_history first") — orphaning the whole
learning-continuity chain on each bump (the recurring 64/65-vs-66-col refusals
in the session-start log). Now the importer runs the same documented migration
inline and merges the rows.
"""
import csv
import hashlib
import json
from pathlib import Path

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore
from scripts.session_import import run

OLD_HEADER = ["position_id", "asset", "side", "ret_1", "imbalance",
              "direction", "gate_confidence",
              "label", "net_pnl_usd", "source", "ts"]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _old_bundle(tmp_path, n=3):
    src = tmp_path / "bundle"
    src.mkdir()
    hist = src / "signal_history.csv"
    with open(hist, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(OLD_HEADER)
        for i in range(n):
            w.writerow([f"p{i}", "BTC", "long", "0.10", "0.20", "1.0", "0.75",
                        str(i % 2), "5.00", "candidate", "1700000000"])
    manifest = {
        "bundle_format": 1, "label": "old-schema-bundle",
        "created_at_utc": "2026-07-14T00:00:00Z", "git_sha": "deadbeef",
        "history": {"rows": n, "by_source": {"candidate": n}},
        "files": {"signal_history.csv": {"sha256": _sha256(hist)}},
    }
    (src / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return src


def test_old_schema_bundle_is_migrated_and_merged(tmp_path):
    src = _old_bundle(tmp_path, n=3)
    out = tmp_path / "outputs"
    out.mkdir()
    rc = run(str(src), str(out), apply=True)
    assert rc == 0, "an older-but-mappable bundle must import, not refuse"

    dest = out / "signal_history.csv"
    assert dest.exists()
    with open(dest, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == HistoryStore(str(dest))._header  # current
        rows = list(reader)
    assert len(rows) == 3
    # a padded-but-current row is the full width: 3 meta + features + 11
    # trailing (label, net_pnl_usd, source, ts, signal_ts, barrier, probe,
    # disp, candidate_id, book, label_era)
    assert all(len(r) == 3 + len(FEATURE_NAMES) + 11 for r in rows)
    # the labels survived the migration
    assert sorted(r["label"] for r in rows) == ["0", "0", "1"]

    # and the migrated file actually loads under the current schema
    X, y, w = HistoryStore(str(dest)).load_training_data()
    assert len(X) == 3 and X.shape[1] == len(FEATURE_NAMES)


def test_reimport_is_idempotent_no_duplicates(tmp_path):
    src = _old_bundle(tmp_path, n=3)
    out = tmp_path / "outputs"
    out.mkdir()
    assert run(str(src), str(out), apply=True) == 0
    assert run(str(src), str(out), apply=True) == 0      # second import
    with open(out / "signal_history.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3, "re-importing the same bundle must not duplicate rows"
