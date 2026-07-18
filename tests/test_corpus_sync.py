"""tests/test_corpus_sync.py — the one-bot corpus sync pulls branch
bundles into local outputs/ through session_import (dedup, manifests,
NEVER-list). End-to-end against throwaway LOCAL repos; the real
paper-telemetry branch is never touched.
"""

import subprocess
import time
from pathlib import Path

import pytest

import scripts.corpus_sync as cs
from scripts.session_export import export


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


_HEADER = None


def _current_header() -> str:
    global _HEADER
    if _HEADER is None:
        from ml.history import HistoryStore
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            hs = HistoryStore(str(Path(td) / "h.csv"))
            _HEADER = ",".join(hs._header)
    return _HEADER


def _write_history(path: Path, ids) -> None:
    header = _current_header()
    width = len(header.split(","))
    rows = []
    for pid in ids:
        row = [pid, "ETH", "long"] + ["0.0"] * (width - 8) + \
              ["1", "1", "0.5", "live", str(time.time()), str(time.time())]
        rows.append(",".join(row))
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture()
def synced_world(tmp_path, monkeypatch):
    """bare origin with a seeded branch carrying a REAL exported bundle
    (proper manifest) whose history has rows the local corpus lacks."""
    bare = tmp_path / "origin.git"
    _git("init", "--bare", "-b", "main", str(bare), cwd=tmp_path)
    root = tmp_path / "work"
    root.mkdir()
    _git("init", "-b", "main", str(root), cwd=tmp_path)
    _git("config", "user.email", "t@t.t", cwd=root)
    _git("config", "user.name", "t", cwd=root)
    _git("config", "commit.gpgsign", "false", cwd=root)
    (root / "code.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    _git("remote", "add", "origin", str(bare), cwd=root)
    # remote bundle: exported from a fake outputs dir with 3 rows
    remote_out = tmp_path / "remote_outputs"
    remote_out.mkdir()
    _write_history(remote_out / "signal_history.csv", ["r1", "r2", "r3"])
    bundle = tmp_path / "bundle"
    export(str(remote_out), str(bundle), label="peer")
    _git("checkout", "--orphan", "paper-telemetry", cwd=root)
    _git("rm", "-rf", "--cached", ".", cwd=root)
    (root / "code.txt").unlink()
    dest = root / "sessions" / "peer"
    dest.parent.mkdir()
    import shutil
    shutil.copytree(bundle, dest)
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "peer bundle", cwd=root)
    _git("push", "origin", "paper-telemetry", cwd=root)
    _git("checkout", "main", cwd=root)
    # local corpus: overlapping r1 plus its own l1
    (root / "outputs").mkdir()
    _write_history(root / "outputs" / "signal_history.csv", ["r1", "l1"])
    monkeypatch.delenv("LB_NO_CORPUS_SYNC", raising=False)
    return root, bare


def _ids(root: Path) -> set:
    lines = (root / "outputs" / "signal_history.csv").read_text(
        encoding="utf-8").splitlines()[1:]
    return {ln.split(",", 1)[0] for ln in lines if ln.strip()}


def test_sync_merges_unseen_rows_dedup(synced_world):
    root, _ = synced_world
    out = cs.sync_once(root=root)
    assert "merged=1" in out and "refused=0" in out
    assert _ids(root) == {"r1", "l1", "r2", "r3"}
    # idempotent: second sync adds nothing and duplicates nothing
    assert "merged=1" in cs.sync_once(root=root)
    assert _ids(root) == {"r1", "l1", "r2", "r3"}


def test_sync_kill_switch(synced_world, monkeypatch):
    root, _ = synced_world
    monkeypatch.setenv("LB_NO_CORPUS_SYNC", "1")
    assert cs.sync_once(root=root) == "disabled"
    assert _ids(root) == {"r1", "l1"}


def test_sync_no_branch_is_graceful(tmp_path):
    root = tmp_path / "lonely"
    root.mkdir()
    _git("init", "-b", "main", str(root), cwd=tmp_path)
    out = cs.sync_once(root=root)
    assert out.startswith(("fetch_failed", "no_bundles"))


def test_tampered_bundle_refused(synced_world):
    # corrupt the remote bundle's history AFTER export: manifest sha no
    # longer matches -> session_import must refuse, sync must report it
    root, bare = synced_world
    wt = root.parent / "tamper"
    _git("clone", "-b", "paper-telemetry", str(bare), str(wt), cwd=root.parent)
    hist = wt / "sessions" / "peer" / "signal_history.csv"
    hist.write_text(hist.read_text(encoding="utf-8") + "evil,x,y\n",
                    encoding="utf-8")
    _git("config", "user.email", "t@t.t", cwd=wt)
    _git("config", "user.name", "t", cwd=wt)
    _git("commit", "-am", "tamper", cwd=wt)
    _git("push", "origin", "paper-telemetry", cwd=wt)
    out = cs.sync_once(root=root)
    assert "refused=1" in out
    assert _ids(root) == {"r1", "l1"}          # nothing merged from it
