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
    r"\b(currently|accru\w*\s+\*{0,2}now|now\s+is|the\s+cohort\s+accruing)\b",
    re.IGNORECASE)
# ^ `accru\w*` not `accruing` (2026-09-12). docs/HANDOFF.md:404 read "is what
# ACCRUES now" for three cuts while this suite passed 14/14. Every one of the
# original four markers was lifted verbatim from the single ONBOARDING sentence
# that motivated this file, so the byte-identical defect one file over - same
# meaning, different conjugation - was invisible. The stem covers
# accruing/accrues/accrual and deliberately does NOT fire on the PAST tense
# ("era-6 accrued from zero"), because `now` must still follow it.
#
# RESIDUAL, stated rather than papered over: this is still a BLACKLIST against
# an OPEN class. English has unboundedly many ways to assert the present, and
# each new one is a new hole. The ordinal check below narrows the gap - it makes
# the LITERAL side closed-class - but does not close it. If a THIRD instance
# slips past, widening this list again is the wrong move: invert the scan so an
# era literal in prose must justify itself, rather than a phrase having to
# incriminate itself.


def _live_era() -> str:
    from core.fill_ledger import EXEC_ERA
    return str(EXEC_ERA)


# `era-N`, the ORDINAL name. docs/HANDOFF.md:1095 read "currently era-6" with
# no stamp anywhere on the line, so ERA_LITERAL found nothing and the claim was
# invisible BY CONSTRUCTION however it was worded. Ordinals are a CLOSED class,
# which is what makes this half sound where the phrasing half is not.
ORDINAL_LITERAL = re.compile(r"\bera-(\d{1,2})\b", re.IGNORECASE)

# A window that is CORRECTING a withdrawn claim quotes it verbatim - that is
# the house standard (docs/quant/2026-09-02_spread_by_regime.md:83,
# 2026-08-22_gate_power_analysis_mintrl.md:3-12). Such a quote is a RECORD, not
# an assertion, and flagging it would punish the correction discipline this
# repo runs on. Keyed on the markers that standard actually uses.
SUPERSEDE = re.compile(
    r"(SUPERSEDED|WITHDRAWN|CORRECTED|struck|~~|previously read|this row read"
    r"|read \*|until 2026-|no longer|stale)", re.IGNORECASE)


def _live_ordinal():
    """The live era's ORDINAL, parsed from the comment beside EXEC_ERA.

    The ordinal exists nowhere executable - core/fill_ledger.py carries it only
    as `# 12-10d4d0c2: cut #12, FEE-4 (era-9)` next to the stamp. Parsing a
    comment is fragile, so this DEGRADES CLOSED: it returns None when it cannot
    find the pairing, and a test asserts None is a failure. A future cut that
    forgets the `(era-N)` therefore turns this suite RED instead of silently
    disarming the ordinal half - which is the precise failure mode (scan
    broken, suite green) this whole file exists to prevent.
    """
    try:
        src = (REPO_ROOT / "core" / "fill_ledger.py").read_text(
            encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover
        return None
    live = _live_era()
    m = re.search(
        r"^#\s*" + re.escape(live) + r"\b[^\n]*?\(era-(\d{1,2})\)",
        src, re.MULTILINE)
    return int(m.group(1)) if m else None


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
            if SUPERSEDE.search(window):
                continue      # a quoted withdrawal is a record, not a claim
            seen: set = set()
            for era in ERA_LITERAL.findall(window):
                if era != live and era not in seen:
                    seen.add(era)
                    out.append(f"{_label(path)}:{n}: claims {era} as current "
                               f"(live is {live}): {line.strip()[:90]}")
            live_ord = _live_ordinal()
            if live_ord is not None:
                for ordn in ORDINAL_LITERAL.findall(window):
                    key = f"era-{ordn}"
                    if int(ordn) != live_ord and key not in seen:
                        seen.add(key)
                        out.append(
                            f"{_label(path)}:{n}: claims era-{ordn} as current "
                            f"(live is era-{live_ord}): {line.strip()[:90]}")
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


# --------------------------------------------------------------------------
# THE 2026-09-12 MISS — two root causes, each with its own pin
#
# docs/HANDOFF.md:404 read "**Era-6 (`exec_era 9-16ec821e`) is what accrues
# now**" for THREE cuts while this suite passed 14/14, and :1095 read
# "currently era-6". Both are the defect this file exists for. Diagnosis:
#
#   RC-1  CURRENCY carried the present participle "accruing" but not the
#         third-person "accrues", and `now\s+is` cannot fire on the inverted
#         word order "...is what accrues now". Every one of the original four
#         markers was lifted verbatim from the single ONBOARDING sentence
#         that motivated the file - a blacklist derived from one instance.
#   RC-2  ERA_LITERAL matches only the STAMP (`\d{1,2}-[0-9a-f]{8}`). A claim
#         that names the era by its ORDINAL ("era-6") carries no literal, so
#         there was nothing to compare and the line was invisible BY
#         CONSTRUCTION, however the currency phrase was worded.
# --------------------------------------------------------------------------

def test_RC1_the_third_person_verb_form_is_caught(tmp_path):
    """Verbatim docs/HANDOFF.md:404 as it stood 2026-08-30..2026-09-12."""
    d = tmp_path / "HANDOFF.md"
    d.write_text(
        "**Era-6 (`exec_era 9-16ec821e`) is what accrues now** - from zero at "
        "the\ncut-#9 restart (2026-08-30T15:32:36Z), toward the same "
        "pre-registered\n", encoding="utf-8")
    assert _stale_currency_claims("12-10d4d0c2", files=[d]), (
        "the 'accrues now' verb form was missed for three cuts")


def test_RC2_an_ordinal_only_currency_claim_is_caught(tmp_path):
    """Verbatim docs/HANDOFF.md:1095. No stamp anywhere on the line."""
    d = tmp_path / "HANDOFF.md"
    d.write_text(
        "   - **When a cohort reads out** - currently era-6; run\n"
        "     `python scripts/cohort_eval.py` and read the accrual line\n",
        encoding="utf-8")
    assert _stale_currency_claims("12-10d4d0c2", files=[d]), (
        "an ordinal-only stale claim carries no stamp and was invisible")


def test_the_live_ORDINAL_is_derivable_and_the_derivation_fails_CLOSED():
    """RC-2's fix needs the live era's ORDINAL, which lives only in a comment
    beside EXEC_ERA in core/fill_ledger.py. If a future cut omits it, the
    ordinal check must go RED here rather than silently stop guarding - the
    exact 'scan is broken, suite green' failure this whole file exists for."""
    ordinal = _live_ordinal()
    assert ordinal is not None, (
        "could not derive the live era ordinal from core/fill_ledger.py - add "
        "'(era-N)' to the comment beside the EXEC_ERA stamp, or this check is "
        "vacuous")
    assert 1 <= ordinal <= 99


def test_the_live_ordinal_named_as_current_is_allowed(tmp_path):
    """Non-vacuity for RC-2: the CORRECT ordinal must not be flagged."""
    d = tmp_path / "doc.md"
    d.write_text(f"The cohort accruing now is era-{_live_ordinal()}.\n",
                 encoding="utf-8")
    assert not _stale_currency_claims("12-10d4d0c2", files=[d])


def test_a_historical_ordinal_without_a_currency_word_is_allowed(tmp_path):
    """HANDOFF's '## ERA-6 BEGINS HERE' sections are correct record."""
    d = tmp_path / "doc.md"
    d.write_text(
        "## ERA-6 BEGINS HERE - cut #9, the Tier-3 fee correction\n"
        "era-6 accrued from zero at 2026-08-30T15:32:36Z; superseded.\n",
        encoding="utf-8")
    assert not _stale_currency_claims("12-10d4d0c2", files=[d])


def test_the_real_docs_tree_is_clean_of_both_root_causes():
    """The end-to-end invariant, on the shipped corpus."""
    assert not _stale_currency_claims(_live_era())
