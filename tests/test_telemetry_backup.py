"""scripts/telemetry_backup.py — the learning-durability sidecar.

The push path (bundle -> sessions/<label>/ on the durable branch) is the
part that prevents progress loss on restart, so it is exercised end-to-end
against throwaway LOCAL repos: a bare "origin" and a work repo. No network,
no session_export coupling, and the real paper-telemetry branch is never
touched. Covers: a bundle lands on the branch, the caller's checkout/branch
is left untouched (worktree isolation), dry-run commits but never pushes,
and an unchanged bundle is a no-op.
"""
import subprocess
from pathlib import Path

import pytest

import scripts.telemetry_backup as tb


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _make_bundle(d: Path, rows: int) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    lines = ["position_id,feature_a"] + [f"p{i},{i}" for i in range(rows)]
    (d / "signal_history.csv").write_text("\n".join(lines) + "\n",
                                          encoding="utf-8")
    (d / "manifest.json").write_text('{"rows": %d}' % rows, encoding="utf-8")
    return d


@pytest.fixture()
def repos(tmp_path):
    """A bare 'origin' with a seeded paper-telemetry branch, plus a work
    repo that has it as remote 'origin'. Returns (root, bare)."""
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
    # seed an orphan paper-telemetry branch on origin
    _git("checkout", "--orphan", "paper-telemetry", cwd=root)
    _git("rm", "-rf", "--cached", ".", cwd=root)
    (root / "README").write_text("telemetry\n", encoding="utf-8")
    # remove the working code file so the orphan branch is clean
    (root / "code.txt").unlink()
    _git("add", "README", cwd=root)
    _git("commit", "-m", "seed", cwd=root)
    _git("push", "origin", "paper-telemetry", cwd=root)
    _git("checkout", "main", cwd=root)               # back on the code branch
    return root, bare


def _cfg(label="nightshift", dry_run=False):
    return {"remote": "origin", "branch": "paper-telemetry",
            "label": label, "outputs": "outputs", "dry_run": dry_run,
            "period": 1800.0}


def _branch_files(bare: Path):
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "paper-telemetry"],
        cwd=str(bare), check=True, capture_output=True, text=True).stdout
    return set(out.split())


def test_push_lands_bundle_on_durable_branch(repos, tmp_path):
    root, bare = repos
    bundle = _make_bundle(tmp_path / "bundle", rows=5)
    msg = tb.push_bundle(_cfg(), bundle, root=root)
    assert "pushed 5 rows" in msg
    files = _branch_files(bare)
    assert "sessions/nightshift/signal_history.csv" in files
    assert "README" in files                          # seed preserved


def test_push_leaves_caller_checkout_untouched(repos, tmp_path):
    root, bare = repos
    before = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            cwd=str(root), check=True, capture_output=True,
                            text=True).stdout.strip()
    tb.push_bundle(_cfg(), _make_bundle(tmp_path / "b", 3), root=root)
    after = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           cwd=str(root), check=True, capture_output=True,
                           text=True).stdout.strip()
    assert before == after == "main"                  # never switched branch
    # no leftover worktrees registered
    wl = subprocess.run(["git", "worktree", "list"], cwd=str(root),
                        check=True, capture_output=True, text=True).stdout
    assert wl.count("\n") == 1                         # only the main checkout


def test_dry_run_commits_but_never_pushes(repos, tmp_path):
    root, bare = repos
    msg = tb.push_bundle(_cfg(dry_run=True),
                         _make_bundle(tmp_path / "b", 4), root=root)
    assert "DRY-RUN" in msg
    assert "sessions/nightshift/signal_history.csv" not in _branch_files(bare)


def test_unchanged_bundle_is_a_noop(repos, tmp_path):
    root, bare = repos
    b = _make_bundle(tmp_path / "b", 7)
    assert "pushed" in tb.push_bundle(_cfg(), b, root=root)
    # identical bundle again -> nothing to commit
    assert "no change" in tb.push_bundle(_cfg(), b, root=root)


def test_missing_history_raises(repos, tmp_path):
    root, _ = repos
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RuntimeError):
        tb.push_bundle(_cfg(), empty, root=root)


def test_bootstraps_missing_durable_branch(tmp_path):
    # fresh remote with NO paper-telemetry branch: the first backup must
    # self-seed the branch, not raise forever.
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
    # no paper-telemetry branch on origin yet
    assert "pushed 5 rows" in tb.push_bundle(
        _cfg(), _make_bundle(tmp_path / "bundle", rows=5), root=root)
    assert "sessions/nightshift/signal_history.csv" in _branch_files(bare)
