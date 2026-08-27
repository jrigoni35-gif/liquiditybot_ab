"""docs/INDEX.md contract enforcement (the affordable reading layer).

Pin: every repo path the index references must exist, so a renamed or
deleted document breaks the suite instead of silently orphaning its
issue (INDEX contract rule 4 — an issue must never fold by pointer
rot). Runtime artifacts under outputs/ are exempt (not tracked).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "INDEX.md"

_EXTS = (".md", ".py", ".json", ".csv")


def _referenced_paths(text: str) -> list[str]:
    out = []
    for token in re.findall(r"`([^`]+)`", text):
        token = token.strip()
        if " " in token or token.startswith("--"):
            continue
        if "/" not in token and token not in ("CLAUDE.md",):
            continue
        if token.startswith("outputs/"):
            continue
        if token.endswith(_EXTS):
            out.append(token.split(" ")[0])
    return out


def test_index_exists_with_contract():
    text = INDEX.read_text(encoding="utf-8")
    assert "never substitutes for primary sources" in text
    assert "Nothing is locked out" in text
    assert "never folds" in text


def test_every_referenced_path_exists():
    text = INDEX.read_text(encoding="utf-8")
    paths = _referenced_paths(text)
    assert len(paths) >= 20, f"index references only {len(paths)} paths"
    missing = [p for p in paths if not (ROOT / p).exists()]
    assert not missing, f"index references missing paths: {missing}"
