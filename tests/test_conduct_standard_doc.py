"""Pins for docs/law/conduct_standard.md (SAFE: docs-only contract).

The conduct standard replaced the CME-benchmarked market-conduct doc on
2026-09-26. These pins keep the replacement wired: the doc exists with its
three layers, the compliance agent reviews against it, nothing tracked still
cites the deleted path, and every `path:line` citation in the doc still
lands inside an existing file (citation rot is the named decay class in
docs/HANDOFF.md's register-decay repair).
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "law" / "conduct_standard.md"
AGENT = ROOT / ".claude" / "agents" / "market-conduct-compliance.md"
# assembled so this file never matches its own needle
OLD_NEEDLE = "compliance_" + "market_conduct"


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_doc_exists_with_three_layers_and_six_floor_items():
    t = _text()
    for heading in ("## 1. FLOOR", "## 2. OPERATOR DECIDES",
                    "## 3. VENUE INTEGRITY"):
        assert heading in t, heading
    floor = t.split("## 1. FLOOR", 1)[1].split("## 2. OPERATOR DECIDES", 1)[0]
    assert re.findall(r"^\| (F\d) \|", floor, re.M) == [
        "F1", "F2", "F3", "F4", "F5", "F6"]


def test_agent_reviews_against_the_new_standard():
    a = AGENT.read_text(encoding="utf-8")
    desc = next(ln for ln in a.splitlines() if ln.startswith("description:"))
    bench = next(ln for ln in a.splitlines() if ln.startswith("Benchmark:"))
    assert "docs/law/conduct_standard.md" in desc
    assert "docs/law/conduct_standard.md" in bench
    assert OLD_NEEDLE not in a
    assert "Blocking" in a and "Report, never decide" in a


def test_no_tracked_file_cites_the_deleted_doc():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.split()
    assert files, "git ls-files returned nothing - check is vacuous"
    hits = []
    for rel in files:
        if rel.startswith(("outputs/", ".venv/")):
            continue
        p = ROOT / rel
        try:
            if OLD_NEEDLE.encode() in p.read_bytes():
                hits.append(rel)
        except OSError:
            continue
    assert not (ROOT / "docs" / (OLD_NEEDLE + ".md")).exists()
    assert hits == []


_CITE = re.compile(r"`([A-Za-z_./-]+\.(?:py|md|json)):(\d+)(?:-(\d+))?`")


def test_every_file_line_citation_lands_inside_its_file():
    cites = _CITE.findall(_text())
    assert len(cites) >= 20, f"only {len(cites)} citations parsed - regex broken?"
    bad = []
    for path, a, b in cites:
        p = ROOT / path
        if not p.is_file():
            bad.append(f"{path} missing")
            continue
        n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        last = int(b or a)
        if not (1 <= int(a) <= last <= n):
            bad.append(f"{path}:{a}-{last} beyond {n} lines")
    assert bad == []
