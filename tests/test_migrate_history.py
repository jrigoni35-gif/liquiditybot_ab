"""scripts/migrate_history.py: old-schema rows must migrate into the
current schema with documented neutral padding, no duplicates, and the
result must be loadable by HistoryStore.load_training_data (which skips
any row missing a feature column - the exact failure that orphaned all
pre-SMC training data on the 36->43 schema bump, 2026-07-11)."""
import csv

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore
from scripts.migrate_history import migrate_rows
from strategies.smc import NEUTRAL as SMC_NEUTRAL

OLD_FEATS = ["ret_1", "imbalance", "direction", "gate_confidence"]


def _old_file(path, n=2, id_prefix="p"):
    header = ["position_id", "asset", "side", *OLD_FEATS,
              "label", "net_pnl_usd", "source", "ts"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i in range(n):
            w.writerow([f"{id_prefix}{i}", "BTC", "long",
                        "0.100000", "0.200000", "1.000000", "0.750000",
                        str(i % 2), "5.00", "live", "1700000000"])
    return path


def test_migrated_rows_load_under_current_schema(tmp_path):
    src = _old_file(tmp_path / "old.csv", n=3)
    rows, padded = migrate_rows(str(src))

    assert len(rows) == 3
    # every current feature the old file lacked is padded
    assert set(padded) == {n for n in FEATURE_NAMES if n not in OLD_FEATS}
    # SMC features use their documented neutrals, not blanket zeros
    for name, neutral in SMC_NEUTRAL.items():
        idx = 3 + FEATURE_NAMES.index(name)
        assert float(rows[0][idx]) == neutral

    dest = tmp_path / "new.csv"
    store = HistoryStore(str(dest))
    store._ensure_schema()
    with open(dest, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    X, y, w = store.load_training_data()
    assert len(X) == 3                       # loadable, none skipped
    assert X.shape[1] == len(FEATURE_NAMES)
    assert list(y) == [0.0, 1.0, 0.0]


def test_non_history_source_refused(tmp_path):
    bad = tmp_path / "bad.csv"
    with open(bad, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a", "b", "c"])
        w.writerow(["1", "2", "3"])
    try:
        migrate_rows(str(bad))
        raise AssertionError("should have refused a non-history file")
    except SystemExit as e:
        assert "meta columns" in str(e)


def test_in_place_dest_rotation_does_not_self_dedupe(tmp_path):
    """Migrating INTO a dest still on the OLD schema (rotate-in-place
    flow) must write every row: dedupe ids are collected AFTER
    _ensure_schema rotates the old file, never from the file being
    replaced (43->46 bump regression: 22 rows skipped as duplicates of
    themselves, dest left empty)."""
    import shutil
    import subprocess
    import sys as _sys
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    src = _old_file(tmp_path / "old.csv", n=3)
    dest = tmp_path / "dest.csv"
    shutil.copy2(src, dest)             # dest starts as the SAME old file
    r = subprocess.run(
        [_sys.executable, "scripts/migrate_history.py",
         "--src", str(src), "--dest", str(dest)],
        capture_output=True, text=True, cwd=str(repo))
    assert r.returncode == 0, r.stderr
    with open(dest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3, r.stdout
    assert "duplicates skipped" not in r.stdout


def test_pattern_features_have_documented_neutral(tmp_path):
    """pat_* pads must be silent (documented neutral), not the
    'no documented neutral' warning path."""
    from scripts.migrate_history import KNOWN_NEUTRAL
    for name in ("pat_engulf", "pat_hammer", "pat_marubozu"):
        assert name in KNOWN_NEUTRAL and KNOWN_NEUTRAL[name] == 0.0
