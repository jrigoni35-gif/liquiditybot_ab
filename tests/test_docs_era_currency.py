"""A document may not assert a STALE execution era as the current one.

THE RECURRENCE THIS CLOSES. This repo's most-repeated failure mode is a
confident stale number in prose. Three instances were found in one session
(2026-09-10):

  * docs/ONBOARDING.md — the newcomer entry point — said "The cohort accruing
    now is era-6, exec_era 9-16ec821e, minted by cut #9" and repeated it as
    standing fence #1. Ground truth at the time was `12-10d4d0c2` (era-9,
    cut #12). It had been wrong across THREE cuts.
  * ml/labeling.py — the docstring of barrier_geometry, the most-cited
    coupling here — quoted a round-trip cost of "~1.2%" against a live 0.45%.
  * core/config_guard.py and execution/pretrade.py assert a superseded 40/80
    fee world (docket item FEEDOC-1).

None of those was caught by anything, because prose is not executable. This
file makes ONE class of them executable: a doc that pairs a CURRENCY MARKER
("currently", "accruing now", "now is") with a hardcoded `exec_era` literal
must name the era the code actually stamps.

WHAT IT DELIBERATELY DOES NOT DO. It does not ban era literals from docs.
`docs/HANDOFF.md` carries four `## ERA-` sections whose whole purpose is
historical record, and `docs/ASSURANCE.md` opens with an explicit CURRENCY
callout declaring its figures historical and naming the re-derive command —
both are correct and must keep working. Only a literal asserted as CURRENT is
a defect, which is why the scan keys on currency markers rather than on the
era pattern alone.

THE FIX WHEN THIS GOES RED is never to update the literal — that just resets
the clock on the same failure. Replace the claim with the command that
derives it:  python -c "from core.fill_ledger import EXEC_ERA; print(EXEC_ERA)"
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

# `<cut number>-<8 hex>`, the shape core/fill_ledger.EXEC_ERA stamps.
ERA_LITERAL = re.compile(r"\b(\d{1,2}-[0-9a-f]{8})\b")

# Words that turn a historical citation into a claim about NOW.
CURRENCY = re.compile(
    r"\b(currently|accruing\s+\*{0,2}now|now\s+is|the\s+cohort\s+accruing)\b",
    re.IGNORECASE)


def _live_era() -> str:
    from core.fill_ledger import EXEC_ERA
    return str(EXEC_ERA)


# Root-level prose that is NOT under docs/ but is read at least as often.
# CLAUDE.md is the important one: red-team OBJ-10, conceded - it is loaded into
# EVERY session, it is the file whose own parenthetical says "a number written
# into it decays into a false claim", and this scanner could not see it because
# the corpus was docs/**/*.md. The file most exposed to the defect was the one
# file exempt from the check for it.
_ROOT_DOCS = ("CLAUDE.md", "README.md", "AGENTS.md")


def _doc_files() -> list[Path]:
    out = []
    if DOCS.is_dir():
        out += [p for p in DOCS.rglob("*.md") if p.is_file()]
    out += [REPO_ROOT / n for n in _ROOT_DOCS if (REPO_ROOT / n).is_file()]
    return sorted(set(out))


# Prose WRAPS. The defect this file exists for had the currency phrase and the
# era literal on ADJACENT lines:
#     ...The cohort accruing **now is era-6** —
#     `exec_era` `9-16ec821e`, minted by cut #9...
# A line-by-line scan cannot see that, and the first cut of this scanner was
# therefore vacuous against its own motivating case — caught by this file's own
# control test, not by review. Two lines of lookahead covers markdown wrapping
# at any sane column without reaching into an unrelated paragraph.
_LOOKAHEAD = 2
# Prose wraps BOTH ways. The motivating defect happened to put the literal
# AFTER the currency phrase, so the first cut looked only forward - but
# "`exec_era` `9-16ec821e` is the cohort accruing now" wraps the other way and
# was invisible (red-team OBJ-10). Symmetric window, same span.
_LOOKBEHIND = 2


def _stale_currency_claims(live: str, files=None) -> list[str]:
    """Currency marker + a non-live era literal within a small line window."""
    out: list[str] = []
    for path in (files if files is not None else _doc_files()):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:  # pragma: no cover
            continue
        for n, line in enumerate(lines, 1):
            if not CURRENCY.search(line):
                continue
            lo = max(0, n - 1 - _LOOKBEHIND)
            window = " ".join(lines[lo:n - 1 + 1 + _LOOKAHEAD])
            seen: set = set()
            for era in ERA_LITERAL.findall(window):
                if era != live and era not in seen:
                    seen.add(era)
                    out.append(f"{_label(path)}:{n}: claims {era} as current "
                               f"(live is {live}): {line.strip()[:90]}")
    return out


def _label(path: Path) -> str:
    """Repo-relative where possible, absolute otherwise.

    `_stale_currency_claims` accepts an arbitrary `files` argument, so it must
    not assume every path lives under REPO_ROOT — `relative_to` raises
    ValueError otherwise, and the crash lands in the REPORTING line, i.e. only
    on the failure path. That is the worst place for a bug: the scan works,
    and the exception only appears when it has something to say.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


# --------------------------------------------------------------------------
# the invariant
# --------------------------------------------------------------------------

def test_no_doc_asserts_a_stale_era_as_current():
    live = _live_era()
    stale = _stale_currency_claims(live)
    assert not stale, (
        "documentation claims a superseded execution era is the current one:\n  "
        + "\n  ".join(stale)
        + "\n\nDo NOT just update the literal - that resets the clock on the "
          "same failure. Replace the claim with the derivation:\n  "
          'python -c "from core.fill_ledger import EXEC_ERA; print(EXEC_ERA)"')


def test_the_live_era_is_the_shape_this_scan_expects():
    """If EXEC_ERA ever stops matching ERA_LITERAL, every comparison above
    becomes vacuously true and this file silently stops guarding anything."""
    live = _live_era()
    assert ERA_LITERAL.fullmatch(live), (
        f"EXEC_ERA={live!r} no longer matches the scanned pattern - the "
        f"currency scan would pass vacuously")


# --------------------------------------------------------------------------
# the scan must be able to fail, and must not fire on correct docs
# --------------------------------------------------------------------------

def test_the_scan_catches_the_exact_line_that_was_wrong(tmp_path):
    """Verbatim from docs/ONBOARDING.md before the 2026-09-10 correction."""
    d = tmp_path / "doc.md"
    d.write_text(
        "gate, n=50 honest-fill closes). The cohort accruing **now is era-6** "
        "-\n`exec_era` `9-16ec821e`, minted by cut #9, the Tier-3 fee "
        "correction of\n", encoding="utf-8")
    hits = _stale_currency_claims("12-10d4d0c2", files=[d])
    assert hits, "the scan missed the exact historical defect it exists for"


def test_a_historical_citation_without_a_currency_word_is_allowed(tmp_path):
    """docs/HANDOFF.md's ERA sections and ASSURANCE.md's CURRENCY callout are
    correct documentation and must not be flagged."""
    d = tmp_path / "doc.md"
    d.write_text(
        "## ERA-6 BEGINS HERE - cut #9, the Tier-3 fee correction\n"
        "minted 2026-08-30, `exec_era` `9-16ec821e`; superseded by cut #10.\n",
        encoding="utf-8")
    assert not _stale_currency_claims("12-10d4d0c2", files=[d])


def test_a_currency_word_naming_the_LIVE_era_is_allowed(tmp_path):
    d = tmp_path / "doc.md"
    d.write_text("The cohort accruing now is `12-10d4d0c2`.\n", encoding="utf-8")
    assert not _stale_currency_claims("12-10d4d0c2", files=[d])


@pytest.mark.parametrize("marker", [
    "currently", "accruing now", "now is", "the cohort accruing"])
def test_every_currency_marker_is_detected(tmp_path, marker):
    d = tmp_path / "doc.md"
    d.write_text(f"The moratorium is {marker} `9-16ec821e`.\n", encoding="utf-8")
    assert _stale_currency_claims("12-10d4d0c2", files=[d]), (
        f"marker not detected: {marker!r}")


def test_the_scan_actually_reaches_the_docs_tree():
    """A scan over an empty file list passes forever."""
    files = _doc_files()
    assert len(files) > 20, f"only {len(files)} docs scanned"
    names = {p.name for p in files}
    assert {"ONBOARDING.md", "HANDOFF.md"} <= names


# --------------------------------------------------------------------------
# CORPUS + DIRECTION — red-team OBJ-10, conceded
# --------------------------------------------------------------------------

def test_the_scan_actually_reaches_CLAUDE_md():
    """The file loaded into every session, and the one whose own parenthetical
    says a number written into it decays into a false claim, was EXEMPT from
    the check for exactly that. Non-vacuity: assert it is in the corpus, not
    merely that the suite is green."""
    names = {p.name for p in _doc_files()}
    assert "CLAUDE.md" in names, "the law file is not scanned for stale eras"


def test_a_stale_era_in_CLAUDE_md_would_be_caught(tmp_path):
    """Injection against the real shape: CLAUDE.md's accrual section pairs a
    currency phrase with an exec_era literal."""
    d = tmp_path / "CLAUDE.md"
    d.write_text(
        "## Accrual moratorium\n"
        "The cohort accruing now is `9-16ec821e`, minted by cut #9.\n",
        encoding="utf-8")
    assert _stale_currency_claims("12-10d4d0c2", files=[d])


def test_a_literal_BEFORE_the_currency_phrase_is_caught(tmp_path):
    """Prose wraps both ways. The first cut looked only FORWARD, so a line
    reading '`exec_era` `9-16ec821e` / is the cohort accruing now' was
    invisible - the same defect class the file exists for, mirrored."""
    d = tmp_path / "doc.md"
    d.write_text(
        "the stamp is `exec_era` `9-16ec821e`\n"
        "and that is the cohort accruing now on this box.\n",
        encoding="utf-8")
    hits = _stale_currency_claims("12-10d4d0c2", files=[d])
    assert hits, "a backward-wrapped stale claim was missed"


def test_the_live_era_before_the_phrase_is_still_allowed(tmp_path):
    """The widened window must not manufacture false positives."""
    d = tmp_path / "doc.md"
    d.write_text(
        "the stamp is `exec_era` `12-10d4d0c2`\n"
        "and that is the cohort accruing now.\n",
        encoding="utf-8")
    assert not _stale_currency_claims("12-10d4d0c2", files=[d])
