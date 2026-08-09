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
    # every current feature the old file lacked is padded, EXCEPT the
    # side-relative ones derivable from the old absolute column x the
    # direction column - those carry real values, not neutrals
    derivable = {"ret_1_dir", "imbalance_dir"}
    assert set(padded) == {n for n in FEATURE_NAMES
                           if n not in OLD_FEATS} - derivable
    # derivation: old ret_1=0.1, direction=+1 -> ret_1_dir = +0.1
    assert float(rows[0][3 + FEATURE_NAMES.index("ret_1_dir")]) == 0.1
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
    for name in ("pat_engulf_dir", "pat_hammer_dir", "pat_marubozu_dir"):
        assert name in KNOWN_NEUTRAL and KNOWN_NEUTRAL[name] == 0.0


# ---------------------------------------------------------------------
# label_era idempotence — the 2026-08-09 corpus incident
# ---------------------------------------------------------------------
def _current_file(path, rows):
    """A file already on the CURRENT schema (what a rotation's .bak is)."""
    store = HistoryStore(str(path))
    store._ensure_schema()
    hdr = store._header
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow([r.get(c, "") for c in hdr])
    return path


def _row(pid, barrier, label_era):
    r = {c: "" for c in ("position_id", "asset", "side", "label",
                         "net_pnl_usd", "source", "ts", "signal_ts",
                         "barrier", "label_era")}
    r.update({"position_id": pid, "asset": "BTC", "side": "long",
              "label": "1", "net_pnl_usd": "1.00", "source": "candidate",
              "ts": "1700000000", "signal_ts": "1700000000",
              "barrier": barrier, "label_era": label_era})
    for n in FEATURE_NAMES:
        r[n] = "0.000000"
    return r


def test_migration_preserves_persisted_label_era(tmp_path):
    """THE 2026-08-09 INCIDENT. This line was the ONLY non-idempotent
    trailing column in migrate_rows: it recomputed label_era via
    label_era_of(barrier), which has no horizon knowledge and returns the
    UNQUALIFIED "triple_barrier" for any tb_* barrier - while the writer
    persists the QUALIFIED "triple_barrier_h432". Every migration pass
    (rotation recovery, session_import, a manual re-run) silently merged
    label definitions that must never share a name.

    Downstream that is not cosmetic: the era-exclusion filter arms on the
    CURRENT-era row count, so re-tagging era rows into the pooled bucket
    collapsed that count below its threshold, disarmed the filter,
    released the whole pooled corpus into training and promoted the model
    family on a data bug instead of on evidence."""
    src = _current_file(tmp_path / "bak.csv", [
        _row("a1", "tb_pt", "triple_barrier_h432"),
        _row("a2", "tb_sl", "triple_barrier_h24"),
        _row("a3", "realized", "exit_sim"),
    ])
    rows, _padded = migrate_rows(str(src))
    store = HistoryStore(str(tmp_path / "unused.csv"))
    i = store._header.index("label_era")
    assert [r[i] for r in rows] == ["triple_barrier_h432",
                                    "triple_barrier_h24", "exit_sim"], (
        "a migration pass must never re-derive an era a row already "
        "carries - horizon qualifiers are destroyed by the derivation")


def test_migration_is_a_fixed_point_on_label_era(tmp_path):
    """Idempotence proper: migrating an already-migrated file twice must
    not drift. The live corpus is migrated on EVERY schema rotation, so a
    non-fixed-point column degrades a little more each time."""
    src = _current_file(tmp_path / "bak.csv",
                        [_row("a1", "tb_pt", "triple_barrier_h432")])
    once, _ = migrate_rows(str(src))
    store = HistoryStore(str(tmp_path / "u.csv"))
    hdr = store._header
    twice_src = tmp_path / "again.csv"
    _current_file(twice_src, [dict(zip(hdr, once[0], strict=True))])
    twice, _ = migrate_rows(str(twice_src))
    assert once == twice, "migration must be a fixed point"


def test_legacy_row_without_era_still_derives_one(tmp_path):
    """The fallback must survive: a row that genuinely predates the
    column (no value to preserve) still gets the loader's own derivation,
    so migrated legacy rows stay full-width and self-describing."""
    src = _old_file(tmp_path / "old.csv", n=1)     # pre-era schema
    rows, _ = migrate_rows(str(src))
    store = HistoryStore(str(tmp_path / "unused.csv"))
    i = store._header.index("label_era")
    assert rows[0][i] == "legacy", "empty barrier derives the legacy era"
