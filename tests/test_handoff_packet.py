"""Tests for scripts/handoff_packet.py — the token-frugal context packer.

SAFE-class developer tool: it assembles text for an agent to read; it
never touches decisioning, config, or runtime state. The contract under
test: given a task description, the packet carries (1) the working diff
as hunks, (2) an AST signature index of the touched modules (~5% of the
file's tokens), (3) only the law paragraphs that match the task — and
everything it emits is derived, never remembered.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import handoff_packet as hp  # noqa: E402


# --- 1. signature index -------------------------------------------------

def test_signature_index_lists_classes_and_defs_with_docstrings(tmp_path):
    mod = tmp_path / "sample.py"
    mod.write_text(
        '"""Module docstring."""\n\n\n'
        "class Engine:\n"
        '    """Owns the loop."""\n\n'
        "    def cycle(self, now):\n"
        '        """Step once."""\n'
        "        pass\n\n\n"
        "def helper(x):\n"
    "    \"\"\"Long docstring.\n\n"
    "    Second paragraph.\n"
    "    \"\"\"\n"
        "    return x\n")
    idx = hp.signature_index(mod)
    assert "class Engine — Owns the loop." in idx
    assert "def cycle(self, now) — Step once." in idx
    assert "def helper(x) — Long docstring." in idx      # first line only
    assert "Second paragraph." not in idx                # no essay bodies
    assert "pass" not in idx                             # no code bodies


def test_signature_index_is_small_fraction_of_source(tmp_path):
    big = tmp_path / "big.py"
    body = "\n".join(f"    x{i} = {i} + {i}" for i in range(400))
    big.write_text(f"def f():\n    \"\"\"One line.\"\"\"\n{body}\n")
    ratio = len(hp.signature_index(big)) / big.stat().st_size
    assert ratio < 0.1                                   # ~5% or better


# --- 2. law excerpts ----------------------------------------------------

def test_law_excerpts_match_task_keywords(tmp_path):
    law = tmp_path / "law"
    law.mkdir()
    (law / "fees.md").write_text("Para about fee booking and tiers.\n\n"
                                 "Unrelated para about dashboards.\n")
    (law / "sizing.md").write_text("Para about position sizing.\n")
    hits = hp.law_excerpts("fix fee booking", law)
    assert any("fee booking" in h for h in hits)
    assert not any("dashboards" in h for h in hits)


def test_law_excerpts_empty_query_is_empty(tmp_path):
    law = tmp_path / "law"
    law.mkdir()
    (law / "a.md").write_text("Something.\n")
    assert hp.law_excerpts("", law) == []


# --- 3. diff hunks ------------------------------------------------------

def test_diff_hunks_returns_patch_not_whole_files(tmp_path):
    # minimal real git repo: modify one line of a 200-line file, the diff
    # must be a hunk, not a file dump
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    f = tmp_path / "a.py"
    f.write_text("".join(f"line{i}\n" for i in range(200)))
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "base"], cwd=tmp_path, check=True)
    f.write_text("".join(f"line{i}\n" for i in range(200))
                 .replace("line100\n", "line100 changed\n"))
    out = hp.diff_hunks(tmp_path, "HEAD")
    assert "line100 changed" in out
    assert "@@" in out                                # hunk format
    assert len(out) < f.stat().st_size // 4           # nowhere near the file


# --- 4. packet assembly -------------------------------------------------

def test_packet_on_real_repo_fee_task():
    out = hp.build_packet("fee reconciliation mismatch proposal",
                          REPO, since="main")
    assert "HANDOFF PACKET" in out
    assert "execution/order_manager.py" in out        # routed module
    assert "era9_moratorium" in out or "definition_of_done" in out
    # the packet must not dump whole source files
    assert len(out) < 40000


def test_packet_derives_module_from_task_words(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "fee_engine.py").write_text(
        '"""Fee engine."""\n\n\ndef reconcile():\n'
        '    """Reconcile fees."""\n    pass\n')
    out = hp.build_packet("reconcile the fees", tmp_path, since=None)
    assert "fee_engine.py" in out


def test_packet_never_includes_source_bodies(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text(
        '"""Mod."""\n\n\ndef f():\n    """F."""\n'
        + "\n".join(f"    y{i} = {i}" for i in range(500)) + "\n")
    out = hp.build_packet("mod", tmp_path, since=None)
    assert "y499" not in out                          # bodies never emitted
