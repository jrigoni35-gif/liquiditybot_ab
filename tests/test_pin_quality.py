"""Pins that guard the PINS - the tautological-assertion class.

2026-08-15. The red-team docket's two BLOCKING objections (OBJ-2, OBJ-14)
were both the same shape: a test whose message named a property while its
assertion measured something else, so it passed no matter what the code
did. Then, while FIXING that class, the author wrote another one:

    assert retired not in text          # retired = "triple_barrier"

That can never fail. The deployed era is `triple_barrier_h432`, which
CONTAINS `triple_barrier` as a prefix, so the substring is always present
and `not in` is always False - the assertion is decorative. It was caught
only because the test was mutation-checked afterwards.

The lesson is not "be careful". Era names are DELIBERATELY prefix-related
(ml.history.triple_barrier_era appends `_h<N>` to a shared base so the
generations stay sortable), which makes containment between them
structurally meaningless and equality the only honest comparison. A rule
that depends on remembering that will be broken again; a test will not.

SCOPE, stated honestly: this catches the demonstrated, recurring trap -
substring comparison between horizon-qualified era names. It does NOT
catch tautological pins in general; nothing static can. The general
defence is mutation-verification (OBJ-14's own demand: "apply the
mutation and show a red test"), which is a practice, not a checker.
"""
import re
from pathlib import Path

from ml.history import LABEL_ERA_TRIPLE_BARRIER, triple_barrier_era

ROOT = Path(__file__).resolve().parents[1]

# The defective form, in BOTH spellings it actually takes:
#   assert "triple_barrier" not in text      <- era as a literal
#   assert retired not in text               <- era behind a variable
# The first draft of this guard required the literal on the same line and
# therefore MISSED the second - which is the exact spelling the author
# had just written. An anti-tautology guard that cannot fire is the
# defect it exists to catch, so it is verified by injection below, not by
# inspection. Era-suggestive identifiers are matched by name because a
# regex cannot resolve a variable to its value.
# Era VALUE identifiers only. `label_era` / `era_name` are deliberately
# NOT here: they are field and column names, and `x not in c["label_era"]`
# is a legitimate MEMBERSHIP test against a collection - flagging it was
# a false positive this guard produced on its first run against the real
# suite (tests/test_cohort_homogeneity.py:208, where label_era holds a
# set). A guard that cries wolf on correct code gets deleted, so it is
# narrowed to the values that actually carry the prefix hazard.
_ERAISH = (r'(?:"|\')triple_barrier[a-z0-9_]*(?:"|\')'
           r'|\b(?:retired|deployed|CURRENT_ERA|_ERA)\b')
_CONTAINMENT = re.compile(
    r'assert\s+[^#\n]*(?:' + _ERAISH + r')[^#\n]*\bnot\s+in\b'
    r'|assert\s+[^#\n]*\bnot\s+in\b[^#\n]*(?:' + _ERAISH + r')')


def test_era_names_are_prefix_related_so_containment_is_meaningless():
    """Prove the hazard exists rather than asserting it in prose.

    If this ever fails, the era naming scheme changed and the guard below
    can be reconsidered - but until then, containment between era names
    carries no information and only equality does.
    """
    base = LABEL_ERA_TRIPLE_BARRIER
    qualified = triple_barrier_era(432)
    assert qualified != base, "premise: the two eras must be distinct"
    # the trap, demonstrated:
    assert qualified.startswith(base)
    assert base in qualified          # <- why `base not in x` never fires
    # the honest comparison:
    assert qualified != base


def test_no_test_asserts_containment_between_era_names():
    """Fail the tautological form at authoring time.

    Equality (`==` / `!=`) on a parsed token is the correct comparison;
    `in` / `not in` between era names is always-true or always-false.
    """
    offenders = []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        if path.name == Path(__file__).name:
            continue          # this file quotes the bad form deliberately
        for n, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if _CONTAINMENT.search(line):
                offenders.append(
                    f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "containment assertion between horizon-qualified era names - it "
        "cannot fail, because triple_barrier_h<N> contains "
        "triple_barrier. Compare the PARSED token with == instead:\n  "
        + "\n  ".join(offenders))


def test_era_consumers_do_not_hardcode_the_retired_literal():
    """The 2026-08-15 era-vocabulary sweep, held in place.

    Four consumers still spoke the pre-migration vocabulary after
    7566ea88 minted `triple_barrier_h432`: gate_truth_report's filter
    (read 5,328 retired rows, 0 deployed), main.py's tb_era milestone
    (read 5,287 where the deployed era held 353), gc_pusher's era
    vocabulary (clamped the deployed era to "other", so the operator's
    series did not exist), and a Grafana panel titled "New-era outcomes"
    querying the retired era. Each must derive the era, never spell it.
    """
    must_derive = {
        "scripts/gate_truth_report.py": "triple_barrier_era(",
        "main.py": "triple_barrier_era(",
    }
    for rel, needle in must_derive.items():
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert needle in src, f"{rel} must derive its era, not spell it"
        # the retired literal may still appear in COMMENTS explaining the
        # defect; it must not appear in a comparison.
        code = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
        bad = re.findall(r'==\s*["\']triple_barrier["\']', code)
        assert not bad, f"{rel} compares against the retired era literal"


def test_era_label_cardinality_is_bounded_against_hostile_input():
    """Adversarial-review finding, 2026-08-15 (Saboteur + Security Auditor).

    `_era_label` widened to admit horizon-qualified eras and its first
    version claimed to stay bounded while `suffix.isdigit()` alone
    admitted 50,000 distinct series from 50,000 garbage values. Three
    escapes: non-ASCII digits (str.isdigit() is True for Arabic-Indic,
    Devanagari, superscript), unbounded length (a 400-digit suffix), and
    leading-zero twins of the same horizon.

    This is not hypothetical input. `label_era` is a column in
    signal_history.csv and session_import.py MERGES that file from
    bundles on the shared durable branch, so the value crosses a trust
    boundary before it becomes a Prometheus series name.
    """
    from scripts.gc_pusher import _era_label
    assert _era_label("triple_barrier_h432") == "triple_barrier_h432"
    assert _era_label("exit_sim") == "exit_sim"
    # non-ASCII digits must not mint series
    for bad in ("triple_barrier_h٤٣٢",   # Arabic-Indic 432
                "triple_barrier_h²",                # superscript two
                "triple_barrier_h५"):               # Devanagari five
        assert bad.partition("_h")[2].isdigit(), "premise: isdigit() is True"
        assert _era_label(bad) == "other", bad.encode("unicode_escape")
    # length and range bounds
    assert _era_label("triple_barrier_h" + "9" * 400) == "other"
    assert _era_label("triple_barrier_h9999") == "other"   # > 4032
    assert _era_label("triple_barrier_h0") == "other"      # 0 bars
    # leading zeros never produce a SECOND series for one horizon
    assert _era_label("triple_barrier_h0432") == _era_label(
        "triple_barrier_h432")
    assert _era_label("triple_barrier_h00432") == "other"
    # the bound itself, measured
    minted = {_era_label(f"triple_barrier_h{i}") for i in range(50000)}
    assert len(minted) <= 4033, f"cardinality escaped: {len(minted)}"
