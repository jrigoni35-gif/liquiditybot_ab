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


def _real_manifest(d: Path) -> None:
    """Give the fixture bundle a real-shaped manifest with a files map."""
    import hashlib
    import json
    sha = hashlib.sha256(
        (d / "signal_history.csv").read_bytes()).hexdigest()
    (d / "manifest.json").write_text(json.dumps(
        {"files": {"signal_history.csv": {"sha256": sha}}}), encoding="utf-8")


def test_consistent_manifest_pushes(repos, tmp_path):
    root, bare = repos
    b = _make_bundle(tmp_path / "b", 5)
    _real_manifest(b)
    assert "pushed 5 rows" in tb.push_bundle(_cfg(), b, root=root)


def test_inconsistent_bundle_is_refused_and_tip_untouched(repos, tmp_path):
    # the live 2026-07-17 failure: manifest hash describes an older audit
    # snapshot than the bytes in the bundle. Such a bundle is refused by the
    # restore hook, so the push side must never let it become the tip.
    root, bare = repos
    good = _make_bundle(tmp_path / "good", 5)
    _real_manifest(good)
    tb.push_bundle(_cfg(), good, root=root)
    tip_before = subprocess.run(
        ["git", "rev-parse", "paper-telemetry"], cwd=str(bare),
        check=True, capture_output=True, text=True).stdout.strip()
    bad = _make_bundle(tmp_path / "bad", 5)
    _real_manifest(bad)
    # mutate a manifest-listed file AFTER hashing (the race, distilled)
    with open(bad / "signal_history.csv", "a", encoding="utf-8") as fh:
        fh.write("p999,999\n")
    with pytest.raises(RuntimeError, match="inconsistent bundle"):
        tb.push_bundle(_cfg(), bad, root=root)
    tip_after = subprocess.run(
        ["git", "rev-parse", "paper-telemetry"], cwd=str(bare),
        check=True, capture_output=True, text=True).stdout.strip()
    assert tip_before == tip_after


def test_shrinking_bundle_is_refused(repos, tmp_path, monkeypatch):
    # a failed-restore boot exporting near-empty outputs must never replace
    # the durable tip's larger bundle (the restore hook reads only the tip)
    monkeypatch.delenv("LB_BACKUP_ALLOW_SHRINK", raising=False)
    root, bare = repos
    tb.push_bundle(_cfg(), _make_bundle(tmp_path / "big", 9), root=root)
    out = tb.push_bundle(_cfg(), _make_bundle(tmp_path / "small", 3),
                         root=root)
    assert "refusing shrink" in out
    tip = subprocess.run(
        ["git", "show", "paper-telemetry:sessions/nightshift/"
         "signal_history.csv"], cwd=str(bare), check=True,
        capture_output=True, text=True).stdout
    assert tip.count("\n") == 10                     # header + 9 rows intact
    # deliberate override still works
    monkeypatch.setenv("LB_BACKUP_ALLOW_SHRINK", "1")
    assert "pushed 3 rows" in tb.push_bundle(
        _cfg(), _make_bundle(tmp_path / "small2", 3), root=root)


def test_manifest_listed_but_missing_file_is_refused(repos, tmp_path):
    root, _ = repos
    b = _make_bundle(tmp_path / "b", 3)
    import json
    (b / "manifest.json").write_text(json.dumps(
        {"files": {"audit.jsonl": {"sha256": "0" * 64}}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing"):
        tb.push_bundle(_cfg(), b, root=root)


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


# ---------------------------------------------------------------------
# --once / --label: the PC's supervisor-driven export lane. The PC is THE
# bot, so its live corpus must reach the durable branch under its own
# label; found 2026-07-18 that only the cloud MIRROR was pushing bundles
# (stamped fresh hourly) while the canonical 1177-row file had no export
# path at all — a 54%-of-corpus single-disk durability hole.
# ---------------------------------------------------------------------
def test_once_mode_runs_single_cycle_and_exits(monkeypatch):
    calls = []
    monkeypatch.setattr(tb, "backup_once",
                        lambda cfg: calls.append(cfg) or "ok")
    assert tb.main(["--once"]) == 0
    assert len(calls) == 1                       # one cycle, no loop


def test_once_mode_label_override_beats_env(monkeypatch):
    seen = {}
    monkeypatch.setenv("LB_BACKUP_LABEL", "cloud-mirror")
    monkeypatch.setattr(tb, "backup_once",
                        lambda cfg: seen.update(cfg) or "ok")
    assert tb.main(["--once", "--label", "pc-live"]) == 0
    assert seen["label"] == "pc-live"


def test_once_mode_failure_is_one_line_nonzero(monkeypatch):
    def boom(cfg):
        raise RuntimeError("push refused")
    monkeypatch.setattr(tb, "backup_once", boom)
    assert tb.main(["--once"]) == 1              # next stamp retries; no raise


# ---------------------------------------------------------------------
# CRLF byte-exactness (the Windows-PC auto-update deploy blocker,
# 2026-07-18): a pusher with core.autocrlf=true must NOT let git
# EOL-normalize bundle blobs, or a puller reading the blob sees
# different bytes than the manifest sha and refuses the bundle as
# "tampered" — which fails test_corpus_sync and the whole battery on
# that machine. push_bundle pins the durable branch `-text`; this proves
# a CRLF-containing bundle round-trips byte-for-byte even under autocrlf.
# ---------------------------------------------------------------------
def _crlf_bundle(d, rows=5):
    d.mkdir(parents=True, exist_ok=True)
    lines = ["position_id,feature_a"] + [f"p{i},{i}" for i in range(rows)]
    # CRLF on disk, exactly what a Windows text-mode write produces
    (d / "signal_history.csv").write_bytes(
        ("\r\n".join(lines) + "\r\n").encode("utf-8"))
    (d / "manifest.json").write_text('{"rows": %d}' % rows, encoding="utf-8")
    return d


def test_crlf_bundle_survives_autocrlf_pusher_byte_exact(repos, tmp_path):
    import subprocess
    root, bare = repos
    # simulate the Windows PC: this repo's git normalizes text on commit
    _git("config", "core.autocrlf", "true", cwd=root)
    tb.push_bundle(_cfg(label="crlfcheck"),
                   _crlf_bundle(tmp_path / "b"), root=root)
    # read the RAW committed blob (cat-file applies no filters)
    blob = subprocess.run(
        ["git", "cat-file", "-p",
         "paper-telemetry:sessions/crlfcheck/signal_history.csv"],
        cwd=str(bare), check=True, capture_output=True).stdout
    assert b"\r\n" in blob                      # CRLF preserved, not normalized
    assert blob == ("\r\n".join(
        ["position_id,feature_a"] + [f"p{i},{i}" for i in range(5)])
        + "\r\n").encode("utf-8")               # byte-for-byte identical
    # and the -text pin itself is on the branch
    assert ".gitattributes" in _branch_files(bare)


# ---------------------------------------------------------------------
# Stat-blind staging (the 2026-07-27 cloud-mirror corruption): the first
# push after a container boot committed the PREVIOUS tick's manifest with
# the fresh tick's session_digest.json — an internally inconsistent bundle
# every future restore refuses. Mechanism: `git worktree add` records
# (size, mtime) per file in the fresh index; copytree/copy2 preserves the
# bundle's mtimes; and under core.checkStat=minimal (the container's
# global git config) `git add -A` trusts size+mtime-seconds alone. The
# manifest is size-STABLE across generations (fixed-width timestamp,
# 12-char sha, 64-char hashes: 3291 bytes every tick), so when the export
# and the checkout landed in the same wall-clock second, git silently kept
# the stale manifest blob while staging the (1-byte-different) digest.
# The fix is two independent layers: staging drops the index entries
# first (`git rm -r --cached`) so content is always hashed, and the
# COMMITTED tree is re-verified against its own manifest before push.
# ---------------------------------------------------------------------
def _sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _consistent_bundle(d: Path, digest_body: str, rows=5) -> Path:
    """A bundle whose manifest correctly hashes its files (passes both the
    on-disk and the committed-tree checks when unmolested)."""
    import json
    d.mkdir(parents=True, exist_ok=True)
    lines = ["position_id,feature_a"] + [f"p{i},{i}" for i in range(rows)]
    (d / "signal_history.csv").write_text("\n".join(lines) + "\n",
                                          encoding="utf-8")
    (d / "session_digest.json").write_text(digest_body, encoding="utf-8")
    files = {n: {"sha256": _sha(d / n), "bytes": (d / n).stat().st_size}
             for n in ("signal_history.csv", "session_digest.json")}
    (d / "manifest.json").write_text(
        json.dumps({"files": files}, indent=2), encoding="utf-8")
    return d


def test_same_second_same_size_swap_cannot_ship_stale_manifest(
        repos, tmp_path, monkeypatch):
    import os
    import shutil
    import time
    root, bare = repos
    # the stat mode the incident shipped under; set explicitly so the test
    # is hermetic on machines whose global config differs
    _git("config", "core.checkStat", "minimal", cwd=root)
    # v1 on the tip; v2's digest differs in SIZE (17- vs 16-char float repr,
    # exactly the live incident) while both manifests are equal-length
    v1 = _consistent_bundle(tmp_path / "v1",
                            '{"generated_at": 1785151614.9607148}\n')
    v2 = _consistent_bundle(tmp_path / "v2",
                            '{"generated_at": 1785153507.328078}\n')
    m1 = (v1 / "manifest.json").read_bytes()
    m2 = (v2 / "manifest.json").read_bytes()
    assert m1 != m2 and len(m1) == len(m2)   # the trap's precondition
    assert tb.push_bundle(_cfg(), v1, root=root).startswith("pushed")

    real_copytree = shutil.copytree

    def trap_copytree(src, dst, **kw):
        # Recreate the boot-tick timing deterministically: make the index
        # record a past mtime for the checked-out bundle, then give the
        # copied-in replacement files that SAME mtime-second.
        wt = Path(dst).parents[1]
        rel = str(Path(dst).relative_to(wt))
        _git("checkout", "--", rel, cwd=wt)          # restore tip's copy
        past = int(time.time()) - 10
        for f in Path(dst).rglob("*"):
            if f.is_file():
                os.utime(f, (past, past))
        _git("update-index", "--refresh", cwd=wt)    # index: mtime=past
        shutil.rmtree(dst)
        real_copytree(src, dst, **kw)
        for f in Path(dst).rglob("*"):
            if f.is_file():
                os.utime(f, (past, past))            # same second, same size
        return dst

    monkeypatch.setattr(tb.shutil, "copytree", trap_copytree)
    tb.push_bundle(_cfg(), v2, root=root)
    # the committed bundle must be v2 WHOLE: fresh manifest, and internally
    # consistent (extract the tip and run the same check the restore uses)
    got = subprocess.run(
        ["git", "cat-file", "-p",
         "paper-telemetry:sessions/nightshift/manifest.json"],
        cwd=str(bare), check=True, capture_output=True).stdout
    assert got == m2                       # stale-manifest mix = the incident
    ext = tmp_path / "extracted"
    ext.mkdir()
    for n in ("manifest.json", "signal_history.csv", "session_digest.json"):
        blob = subprocess.run(
            ["git", "cat-file", "-p",
             f"paper-telemetry:sessions/nightshift/{n}"],
            cwd=str(bare), check=True, capture_output=True).stdout
        (ext / n).write_bytes(blob)
    assert tb.bundle_inconsistency(ext) is None


def test_committed_verifier_reports_mixed_commit(repos, tmp_path):
    # Build the corrupt tree DIRECTLY (mutate a manifest-listed file after
    # manifest write, commit with plain git) so the verifier is judged on
    # committed bytes, independent of push_bundle's own staging.
    root, _ = repos
    b = _consistent_bundle(root / "sessions" / "mixed",
                           '{"generated_at": 1.0}\n')
    _git("add", "-A", "--", "sessions/mixed", cwd=root)
    _git("commit", "-m", "good", cwd=root)
    good_commitish = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), check=True,
        capture_output=True, text=True).stdout.strip()
    assert tb.committed_bundle_inconsistency(root, good_commitish,
                                             "mixed") is None
    (b / "session_digest.json").write_text('{"generated_at": 2.0}\n',
                                           encoding="utf-8")
    _git("add", "-A", "--", "sessions/mixed", cwd=root)
    _git("commit", "-m", "mixed", cwd=root)
    bad = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), check=True,
        capture_output=True, text=True).stdout.strip()
    reason = tb.committed_bundle_inconsistency(root, bad, "mixed")
    assert reason is not None and "session_digest.json" in reason
    # a manifest-listed file absent from the commit is also inconsistent
    _git("rm", "-q", "sessions/mixed/session_digest.json", cwd=root)
    _git("commit", "-m", "missing", cwd=root)
    gone = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), check=True,
        capture_output=True, text=True).stdout.strip()
    reason = tb.committed_bundle_inconsistency(root, gone, "mixed")
    assert reason is not None and "missing" in reason


def test_push_refused_when_committed_tree_inconsistent(
        repos, tmp_path, monkeypatch):
    root, bare = repos
    tb.push_bundle(_cfg(), _make_bundle(tmp_path / "a", 5), root=root)
    tip_before = subprocess.run(
        ["git", "rev-parse", "paper-telemetry"], cwd=str(bare),
        check=True, capture_output=True, text=True).stdout.strip()
    monkeypatch.setattr(tb, "committed_bundle_inconsistency",
                        lambda repo, rev, label: "boom")
    with pytest.raises(RuntimeError, match="boom"):
        tb.push_bundle(_cfg(), _make_bundle(tmp_path / "b", 6), root=root)
    tip_after = subprocess.run(
        ["git", "rev-parse", "paper-telemetry"], cwd=str(bare),
        check=True, capture_output=True, text=True).stdout.strip()
    assert tip_before == tip_after         # garbage never becomes the tip


def test_push_only_touches_its_own_label_never_siblings(repos, tmp_path):
    # regression (2026-07-18): push_bundle used `git add -A`, which re-staged
    # EVERY sibling bundle. Combined with the -text pin and a Windows
    # autocrlf checkout, a single push rewrote unrelated bundles' blobs and
    # broke their integrity. A push must be idempotent w.r.t. bundles it is
    # not writing. Here: land bundle A, record its committed blob; land a
    # DIFFERENT bundle B; A's blob must be byte-identical afterward.
    import subprocess
    root, bare = repos

    def blob(label, name="signal_history.csv"):
        return subprocess.run(
            ["git", "cat-file", "-p",
             f"paper-telemetry:sessions/{label}/{name}"],
            cwd=str(bare), check=True, capture_output=True).stdout

    tb.push_bundle(_cfg(label="alpha"), _make_bundle(tmp_path / "a", 5),
                   root=root)
    a_before = blob("alpha")
    tb.push_bundle(_cfg(label="beta"), _make_bundle(tmp_path / "b", 7),
                   root=root)
    assert blob("alpha") == a_before          # sibling untouched by beta push
    # and the beta commit's changed paths never reach into sessions/alpha
    names = subprocess.run(
        ["git", "show", "--name-only", "--format=", "paper-telemetry"],
        cwd=str(bare), check=True, capture_output=True, text=True).stdout
    assert "sessions/beta/" in names
    assert "sessions/alpha/" not in names
