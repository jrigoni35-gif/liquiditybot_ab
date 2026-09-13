"""Pins for scripts/mutation_sweep.py - the tool that checks other files'
mutation claims.

It is an instrument, so CLAUDE.md's mindset section applies to it first: the
code that tells you whether the governed code works is the code nothing
governs. Both defects pinned below were found by RUNNING the sweep, not by
reading it, and both made it report confidently wrong answers:

  1. It mutated PROSE. The first cut skipped lines *starting* with `#` or a
     quote, which does nothing inside a multi-line docstring - and this repo's
     modules are heavily documented. 70% of the first sweep's mutants rewrote
     English ("per-asset sum == pooled to 1e-6" became "!=") and every one was
     faithfully reported as a SURVIVOR. A tool that cries wolf gets ignored.
  2. It invented SUBJECTS. A path merely NAMED in a string was treated as a
     module under test, because this repo's tests routinely read another file
     as text to assert a registration. Sweeping tests/test_watch_lane.py
     pulled in scripts/outputs_gc.py and tests/conftest.py, and every survivor
     reported came from files that test never claimed to pin.

Every test here is hermetic: REPO is monkeypatched to a tmp tree, so nothing
touches the real repo, and run_one is stubbed wherever a verdict is needed so
no pytest subprocess runs.
"""
from __future__ import annotations

from pathlib import Path

from scripts import mutation_sweep as ms


def _mod(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body.encode("utf-8"))       # BYTES: see scripts/mutate.py:152
    return p


# ======================================================================
# DEFECT 1 - prose is not code
# ======================================================================

PROSE_MODULE = '''"""A docstring whose FIRST line says a == b and True.

It discusses whether a == b and mentions `if not x` and True and False,
and none of that is executable.
"""
X = 0.0
MSG = "a single-line string that also says a == b"
PARTS = ("first part"
         "second part says a == b too"
         "third part")


def f(a, b):
    # a comment that says a == b and True
    if a == b:
        return True
    return False
'''


def test_docstring_INTERIOR_lines_are_excluded_by_STRUCTURE(tmp_path):
    """MECHANISM 1 of 2, and this pin is deliberately NOT about the STRING
    filter.

    Mutation testing corrected the original claim here: planting `STRING` out
    of the skip tuple left this pin PASSING, because a multi-line docstring is
    ONE token whose start is its FIRST line. Interior lines carry no token
    start at all, so tokenize's STRUCTURE excludes them and the filter never
    sees them. The pin is kept because it holds the OUTCOME that mattered -
    the 70% of mutants spent rewriting English - but it is no longer allowed
    to stand in for the filter, which is pinned on its own below.
    """
    p = _mod(tmp_path, "m.py", PROSE_MODULE)
    live = ms.code_lines(p)
    assert 3 not in live, "a docstring interior line was called code"
    assert 4 not in live, "a docstring interior line was called code"
    assert 6 in live, "`X = 0.0` is code and must be mutable"
    assert 15 in live, "`if a == b:` is code and must be mutable"


def test_the_STRING_filter_covers_lines_that_are_ONLY_string(tmp_path):
    """MECHANISM 2 of 2 - what the `STRING` entry in the skip tuple actually
    buys, isolated so a mutant that removes it goes red.

    Exactly two line shapes have no tokens except strings: the OPENING line of
    a bare docstring - which in this repo routinely carries mutable prose,
    e.g. "does this actually write anything?" - and a continuation line of an
    implicitly concatenated string. Without the filter, both are mutable
    English and every mutant planted there is noise.
    """
    live = ms.code_lines(_mod(tmp_path, "m.py", PROSE_MODULE))
    assert 1 not in live, \
        "the docstring opening line - which says `a == b` - was mutable"
    assert 9 not in live, \
        "a string continuation line - which says `a == b` - was mutable"


def test_a_line_that_merely_CONTAINS_a_string_stays_code(tmp_path):
    """NEGATIVE ARM: the filter must not over-reach. `MSG = "...a == b..."` is
    already live via its NAME and OP tokens and must STAY live. Over-excluding
    is how a sweep silently stops testing real assignments while still
    reporting a score."""
    live = ms.code_lines(_mod(tmp_path, "m.py", PROSE_MODULE))
    assert 7 in live, "a real assignment was excluded because it holds a string"

def test_a_comment_line_is_not_code(tmp_path):
    p = _mod(tmp_path, "m.py", PROSE_MODULE)
    assert 14 not in ms.code_lines(p), "a comment line was called code"


def test_no_mutant_is_ever_planted_in_prose(tmp_path, monkeypatch):
    """The end-to-end form of defect 1: given a module whose `== `, `True` and
    `if not ` also occur in prose, every mutant must come from an executable
    line."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "m.py", PROSE_MODULE)
    muts = ms.build_mutants("m.py", 10)
    assert muts, "nothing mutable at all - the operators stopped matching"
    live = ms.code_lines(tmp_path / "m.py")
    body = PROSE_MODULE.splitlines()
    for m in muts:
        idx = [i for i, ln in enumerate(body, start=1) if ln == m["old"]]
        assert idx, f"mutant anchor not found in the source: {m['old']!r}"
        assert idx[0] in live, f"mutant planted in prose: {m['old']!r}"


def test_a_file_that_will_not_tokenize_yields_nothing(tmp_path, monkeypatch):
    """Degrades to 'no applicable mutants', which main() reports as NOT a
    pass. A syntax error must never read as a clean sweep."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "broken.py", "def f(:\n    x == 1\n")
    assert ms.code_lines(tmp_path / "broken.py") == set()
    assert ms.build_mutants("broken.py", 10) == []


# ======================================================================
# DEFECT 3 - f-strings are not STRING tokens, and lines are not columns
# ======================================================================

FSTRING_MODULE = '''X = 1
MSG = f"""prose line one says a == b
prose line two says True
"""
Y = 2
'''

MIXED_MODULE = '''TABLE: dict = {}          # key -> ts, an arrow in a comment
NOTE = "a value where a == b"


def f(a, b, note):
    hint = "compare a == b"
    if "a == b" in hint and a == b:
        return True
    return a == b and note
'''


def test_an_fstring_is_not_a_STRING_token(tmp_path):
    """Python 3.12 split f-strings into FSTRING_START/MIDDLE/END, so a skip
    set naming only STRING lets f-string prose through. Measured on 3.14:
    FSTRING_MIDDLE spanned three lines of English and none was skipped,
    so a triple-quoted f-string assignment was a mutable line and the
    `==` inside its English body was in reach of the eq operator.

    The skip set resolves these names with hasattr, so this pin holds on any
    version - it just has nothing to catch before 3.12.
    """
    import tokenize
    if not hasattr(tokenize, "FSTRING_MIDDLE"):
        return                      # pre-3.12: f-strings ARE STRING tokens
    m = _mod(tmp_path, "fs.py", FSTRING_MODULE)
    spans = ms.prose_spans(m)
    assert 3 in spans, "an f-string body line was not recorded as prose"
    # The mutable English is on line 2, which ALSO holds real code (`MSG =`),
    # so a line-granular answer cannot help here - the span must cover the
    # `a == b` columns and leave the assignment alone.
    col = FSTRING_MODULE.split("\n")[1].index("a == b")
    assert any(lo <= col < hi for lo, hi in spans[2]), \
        f"the f-string span does not COVER its own text: {spans[2]}"
    assert not any(lo <= 0 < hi for lo, hi in spans[2]), \
        f"the f-string span swallowed the assignment: {spans[2]}"
    live = ms.code_lines(m)
    assert 1 in live and 5 in live, "real assignments were excluded"



def test_a_multiline_string_span_has_the_right_GEOMETRY(tmp_path):
    """A span is three shapes, and only a MULTI-line token can tell them
    apart - for a single-line token r0 == r1, so a start/end mix-up is
    invisible. It occupies the TAIL of its opening line (from the opening
    quote, not column 0 - the code before it is real), ALL of any middle
    line, and the HEAD of its closing line.

    Both halves were planted and both SURVIVED against the earlier fixture,
    which had no multi-line string at all: a span test whose fixture is one
    line deep is not testing spans.
    """
    m = _mod(tmp_path, "ml.py",
             'MSG = """tail says a == b\nmiddle says a == b\n"""\nY = 1\n')
    spans = ms.prose_spans(m)
    assert spans[1] == [(6, 10 ** 9)], \
        f"opening line span must start at the quote, not 0: {spans.get(1)}"
    assert spans[2] == [(0, 10 ** 9)], \
        f"a middle line is prose end to end: {spans.get(2)}"
    assert spans[3] == [(0, 3)], \
        f"the closing line is prose only up to the quote: {spans.get(3)}"
    assert 4 not in spans, "`Y = 1` is code and must carry no prose span"


def test_no_mutant_lands_inside_a_COMMENT_on_a_code_line(tmp_path,
                                                         monkeypatch):
    """THE LOAD-BEARING PIN for defect 3. `TABLE: dict = {}  # key -> ts` is a
    real assignment, so the LINE is code - and the `> ` the gt operator finds
    is the arrow in the comment. A line-granular check cannot see that.

    Measured repo-wide the day this was added: 37 anchors across 208 shipped
    modules sat inside comments or string bodies - `# key -> ts`,
    `# Friday == weekday() 4`, `"long" or "short"`. Every one would have been
    planted in prose and reported as a SURVIVOR, i.e. as a blind spot that is
    not there.
    """
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "mixed.py", MIXED_MODULE)
    for mu in ms.build_mutants("mixed.py", 10):
        assert "# key ->= ts" not in mu["new"], \
            f"mutated a comment arrow: {mu['new']!r}"
        assert "# key >= ts" not in mu["new"], \
            f"mutated a comment arrow: {mu['new']!r}"


def test_no_mutant_lands_inside_a_STRING_body_on_a_code_line(tmp_path,
                                                             monkeypatch):
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "mixed.py", MIXED_MODULE)
    for mu in ms.build_mutants("mixed.py", 10):
        assert "a value where a != b" not in mu["new"], \
            f"mutated string prose: {mu['new']!r}"
        assert "compare a != b" not in mu["new"], \
            f"mutated string prose: {mu['new']!r}"


def test_a_REAL_comparison_later_on_the_line_is_still_reached(tmp_path,
                                                              monkeypatch):
    """NEGATIVE ARM, and the reason the fix SCANS PAST prose instead of
    rejecting the line. `note = "compare a == b"` then `return a == b and
    note`: dropping any line that holds prose would silently stop testing the
    real comparison, which is a worse failure than the noise it removes -
    a check that tests less while still printing a score.
    """
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "mixed.py", MIXED_MODULE)
    eq = [m for m in ms.build_mutants("mixed.py", 10) if m["op"] == "eq->ne"]
    assert eq, "no real comparison was ever mutated"
    assert eq[0]["new"].strip() == 'if "a == b" in hint and a != b:', \
        f"scanned past prose and then gave up: {eq[0]['new']!r}"


def test_the_column_check_does_not_reject_everything(tmp_path, monkeypatch):
    """'0 findings' and 'the scan is broken' are the same observation until
    separated - CLAUDE.md says so, and a span check that matched every column
    would silently produce a clean sweep of nothing."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "plain.py",
         "def f(a, b):\n    ok = True\n    if a == b:\n"
         "        ok = False\n    return ok and a\n")
    ops = {m["op"] for m in ms.build_mutants("plain.py", 10)}
    assert {"eq->ne", "true->false", "false->true", "and->or"} <= ops, \
        f"the column check swallowed real code: {ops}"


# ======================================================================
# DEFECT 2 - a path NAMED in a string is not a subject
# ======================================================================

READS_AS_TEXT = '''from pathlib import Path
import core.thing


def test_registration():
    src = Path("scripts/other.py").read_text()
    assert "X" in src and core.thing
'''

LOADS_BY_PATH = '''import importlib.util

spec = importlib.util.spec_from_file_location("o", "scripts/other.py")


def test_x():
    assert spec
'''


def test_a_path_named_in_a_string_is_not_a_subject(tmp_path, monkeypatch):
    """THE LOAD-BEARING PIN for defect 2. The test file READS another file to
    assert a registration - a pattern used all over this repo. Treating that
    as a subject makes the other file's survivors look like this file's blind
    spot, which is the cry-wolf failure again."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "core/thing.py", "X = 1\n")
    _mod(tmp_path, "scripts/other.py", "X = 2\n")
    t = _mod(tmp_path, "tests/test_a.py", READS_AS_TEXT)
    subs = ms.subjects_of(t)
    assert "core/thing.py" in subs, "a real import was dropped"
    assert "scripts/other.py" not in subs, \
        "a path merely read as text was treated as a module under test"


def test_a_path_LOADED_by_spec_IS_a_subject(tmp_path, monkeypatch):
    """NEGATIVE ARM, and the reason the fix is a discriminator rather than a
    blanket ban: tests/test_verification_helpers.py really does load its
    subjects with spec_from_file_location, and those ARE subjects. A fix that
    dropped every string path would make that file unsweepable."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "scripts/other.py", "X = 2\n")
    t = _mod(tmp_path, "tests/test_b.py", LOADS_BY_PATH)
    assert "scripts/other.py" in ms.subjects_of(t)


def test_stdlib_and_third_party_imports_are_not_subjects(tmp_path,
                                                         monkeypatch):
    monkeypatch.setattr(ms, "REPO", tmp_path)
    t = _mod(tmp_path, "tests/test_c.py",
             "import json\nimport numpy as np\nimport pytest\n"
             "from pathlib import Path\n")
    assert ms.subjects_of(t) == []


def test_a_subject_must_exist_on_disk(tmp_path, monkeypatch):
    """Resolution is by FILE, not by dotted name: an import of a module this
    repo does not have is not a subject."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    t = _mod(tmp_path, "tests/test_d.py", "import core.absent\n")
    assert ms.subjects_of(t) == []


# ======================================================================
# Mutant construction
# ======================================================================

def test_an_ambiguous_anchor_is_skipped_not_guessed(tmp_path, monkeypatch):
    """A line that appears twice cannot be planted unambiguously by a string
    replace, so it is SKIPPED. Guessing which occurrence to hit is how a
    harness scores a verdict against an edit it did not make."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "dup.py",
         "def a(x):\n    if x == 1:\n        pass\n\n\n"
         "def b(x):\n    if x == 1:\n        pass\n")
    assert [m for m in ms.build_mutants("dup.py", 10)
            if m["op"] == "eq->ne"] == []


def test_import_lines_are_skipped(tmp_path, monkeypatch):
    """An import line carries no decision. Mutating it only breaks the import,
    which every test in the file catches - a free CAUGHT that proves nothing
    and inflates the score."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "imp.py", "from x import y or z\nQ = 1\n")
    assert [m for m in ms.build_mutants("imp.py", 10)
            if m["old"].startswith("from ")] == []


def test_a_mutant_actually_changes_the_line(tmp_path, monkeypatch):
    """A no-op 'mutant' is always CAUGHT-by-accident or SURVIVED-by-accident;
    either way the verdict is about nothing."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "m2.py", "def f(a, b):\n    return a == b\n")
    muts = ms.build_mutants("m2.py", 10)
    assert muts
    for m in muts:
        assert m["new"] != m["old"]
        assert m["path"] == "m2.py"


def test_the_per_module_limit_is_honoured(tmp_path, monkeypatch):
    """One operator must not flood the report from one hot file."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "m3.py",
         "def f(a, b, c, d):\n"
         "    if a == b:\n        return True\n"
         "    if c > d:\n        return False\n"
         "    if a and b:\n        return True\n"
         "    if c or d:\n        return False\n"
         "    if not a:\n        return True\n"
         "    z = 0.0\n    return z\n")
    assert len(ms.build_mutants("m3.py", 2)) <= 3


# ======================================================================
# Reporting - "nothing to mutate" is not a pass
# ======================================================================

def test_the_sweep_locks_ITS_OWN_tree_not_the_real_repo(tmp_path,
                                                        monkeypatch):
    """The working-tree lock must follow the REPO the sweep is pointed at.

    scripts/mutate.py owns the lock, so a root resolved from THAT module's
    REPO landed in the REAL outputs/ while these tests ran against a tmp tree,
    and the repo's own outputs-write guard failed three of them.

    Caught ONLY by the full suite. The lock was added to
    scripts/mutation_sweep.py and this file was not re-run afterwards - the
    single-file greens that followed were all on OTHER files. A green is only
    as big as its corpus, and the corpus here was the wrong one.

    IT PINS THE ARGUMENT, NOT THE FILE, and two earlier versions explain why.
    The lock is TRANSIENT - taken and released inside the call - so no
    after-the-fact filesystem check can see it:

      * "the real lock does not exist" was green standalone and RED under
        scripts/mutate.py, which legitimately HOLDS that lock while running
        its own child pytest. A pin that cannot survive being run by the
        harness is a pin the harness can never verify.
      * "the real lock is unchanged" then SURVIVED the mutation that removes
        the root entirely, in both directions: under the harness the sweep is
        refused outright and creates nothing, and outside it the lock is
        created and released again before the assertion runs.

    So the observable contract is the CALL: the sweep must hand tree_lock its
    own REPO. The in-the-wild detector for the real bug is tests/conftest.py's
    outputs-write guard, which is what caught it - this pin is the one that
    fails fast and names the cause.
    """
    import scripts.mutate as mut
    seen = {}
    real_lock = mut.tree_lock

    def spy(root=None):
        seen["root"] = root
        return real_lock(root)

    monkeypatch.setattr(ms, "tree_lock", spy)
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "tests/test_e.py",
         "import json\n\n\ndef test_x():\n    assert json\n")
    ms.main(["--test", "tests/test_e.py"])
    assert seen.get("root") == tmp_path, \
        f"the sweep locked {seen.get('root')} while pointed at {tmp_path}"
    assert not (tmp_path / "outputs" / ".mutating").exists(), \
        "the sweep left its own lock behind"


def test_no_applicable_mutants_is_a_FAILURE(tmp_path, monkeypatch, capsys):
    """Same class as pytest's exit 5, which scripts/checked.py exists to
    separate: a sweep that mutated nothing has established nothing. Reporting
    it as a pass is how an empty check reads as a clean one."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "tests/test_e.py",
         "import json\n\n\ndef test_x():\n    assert json\n")
    rc = ms.main(["--test", "tests/test_e.py"])
    assert rc == 1
    assert "NO APPLICABLE MUTANTS" in capsys.readouterr().out


def test_claimants_finds_prose_claims_and_only_those(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "tests/test_claims.py", '"""4/4 mutants caught."""\n')
    _mod(tmp_path, "tests/test_quiet.py", '"""Nothing asserted."""\n')
    names = [n for n, _ in ms.claimants()]
    assert "tests/test_claims.py" in names
    assert "tests/test_quiet.py" not in names


def test_survivors_make_the_run_red(tmp_path, monkeypatch):
    """A sweep with an uncaught mutant must not exit 0."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "core/s.py", "def f(a, b):\n    return a == b\n")
    _mod(tmp_path, "tests/test_f.py",
         "import core.s\n\n\ndef test_x():\n    assert core.s\n")
    monkeypatch.setattr(
        ms, "run_one",
        lambda mu, test, verbose=False: {"verdict": "SURVIVED"})
    assert ms.main(["--test", "tests/test_f.py"]) == 1


def test_an_all_caught_sweep_is_green(tmp_path, monkeypatch):
    """NEGATIVE ARM: the tool must be able to say yes, or a red means
    nothing - '0 findings' and 'the scan is broken' are the same observation
    until separated."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    _mod(tmp_path, "core/s.py", "def f(a, b):\n    return a == b\n")
    _mod(tmp_path, "tests/test_g.py",
         "import core.s\n\n\ndef test_x():\n    assert core.s\n")
    monkeypatch.setattr(
        ms, "run_one",
        lambda mu, test, verbose=False: {"verdict": ms.CAUGHT})
    assert ms.main(["--test", "tests/test_g.py"]) == 0


def test_the_per_module_tally_attributes_survivors_correctly(tmp_path,
                                                             monkeypatch):
    """Added after one `import ml.history` line in a monkeypatch test took
    tests/test_watch_lane.py from 8 mutants in one module to 18 across two.
    The 11 new survivors all landed in the module that test file was never
    about; an unlabeled pooled score reads as that file's blind spot."""
    monkeypatch.setattr(ms, "REPO", tmp_path)
    # EACH module must yield SEVERAL mutants. The first version of this
    # fixture gave one apiece, and a mutant that dropped the per-module key
    # from the accumulator still produced (1, 1) and (0, 1) - arithmetically
    # identical to the truth, so the pin SURVIVED. A tally test whose fixture
    # cannot accumulate is not testing a tally.
    body = ("def f(a, b):\n"
            "    ok = True\n"
            "    if a == b:\n"
            "        ok = False\n"
            "    return ok and a\n")
    _mod(tmp_path, "core/good.py", body)
    _mod(tmp_path, "core/bad.py", body.replace("def f(", "def g("))
    _mod(tmp_path, "tests/test_h.py",
         "import core.good\nimport core.bad\n\n\ndef test_x():\n"
         "    assert core.good and core.bad\n")
    monkeypatch.setattr(
        ms, "run_one",
        lambda mu, test, verbose=False: {
            "verdict": ms.CAUGHT if mu["path"] == "core/good.py"
            else "SURVIVED"})
    res = ms.sweep("tests/test_h.py", 10, verbose=False)
    good_c, good_n = res["by_module"]["core/good.py"]
    bad_c, bad_n = res["by_module"]["core/bad.py"]
    assert good_n > 1 and bad_n > 1, "fixture too thin to test accumulation"
    assert good_c == good_n, "a caught module was scored as blind"
    assert bad_c == 0, "a blind module was scored as caught"
    assert res["caught"] == good_c, "the pooled count lost the split"
    assert good_n + bad_n == res["n"], \
        "the tally must partition every mutant, losing and inventing none"
