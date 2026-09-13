"""scripts/mutation_sweep.py - is a test file's mutation claim actually true?

WHY THIS EXISTS. About thirty test files in this repo record, in prose, that
mutation verification was done ("4/4 mutants caught", "11/11 mutation-caught",
"mutation-tested and deleted"). Those claims were made by hand-rolled
harnesses, and scripts/mutate.py's own docstring lists three mechanical
defects every one of those copies had - the worst being that a stale .pyc can
survive a byte-identical restore, so a mutant's verdict may have been scored
against the PREVIOUS mutant's bytecode.

So the claims are unverified, in both directions, and re-checking them by hand
is exactly the work that produced the defects. This sweeps them instead.

METHOD. For a test file, find the modules it imports from this repo, apply
GENERIC mutation operators to each, and report how many a full run of that
test file catches. Generic operators are deliberately dumb - flip a
comparison, flip a boolean, drop a `not`, blank a return - because the point
is not to find clever bugs, it is to answer "can this file fail at all, and
where is it blind".

WHAT THIS TOOL GOT WRONG, because it is an instrument and CLAUDE.md's
mindset section applies to it first. Three defects, each found by RUNNING it
and each making it report confidently wrong answers - all three are pinned in
tests/test_mutation_sweep.py and mutation-verified through scripts/mutate.py:

  1. It mutated PROSE inside docstrings (70% of the first run's mutants).
  2. It invented SUBJECTS from paths merely NAMED in strings.
  3. It classified by LINE, not by COLUMN - so the English inside a comment or
     a string on an otherwise-real code line was still in reach. Measured
     2026-09-13 across 208 shipped modules: 37 anchors sat inside prose,
     `# key -> ts` rewritten to `>=`, `# Friday == weekday() 4`, `"long" or
     "short"` in a type comment. Every one would have been reported as a
     SURVIVOR, i.e. as a blind spot that is not there. Re-derive that count
     with the census in the same test file rather than trusting this number.

Related, same root: on Python 3.12+ an f-string is NOT a STRING token, so a
skip set naming only STRING lets f-string prose through. This runs on 3.14.

WHAT A SURVIVOR MEANS, and this is the part to read before acting. A surviving
mutant is NOT automatically a defect:
  * the mutated line may be unreachable from that test file (another file's
    tests may cover it),
  * the mutation may be semantically equivalent (a classic mutation-testing
    problem with no general solution),
  * the line may be logging, a docstring path, or a comment-adjacent default.
It IS a place where THIS file's claim to have verified itself is not supported.
Read the survivor, decide, and either add a pin or record why the line is not
worth one. Do not "fix" a survivor by deleting the operator.

Usage:
    python scripts/mutation_sweep.py --test tests/test_watch_lane.py
    python scripts/mutation_sweep.py --claims          # list the claimants
    python scripts/mutation_sweep.py --test ... --max 12 --json out.json

Exit: 0 if every applied mutant was caught, 1 otherwise. A file with no
applicable mutants exits 1 and says so - "nothing to mutate" is not a pass.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.mutate import (CAUGHT, run_one,  # noqa: E402
                          tree_lock)

# (label, pattern, replacement). Applied to the FIRST match only, one mutant
# per (module, operator, occurrence-index) so a single operator cannot flood
# the report from one hot file.
OPERATORS = [
    ("eq->ne", r"(?<![=!<>])== ", "!= "),
    ("ne->eq", r"!= ", "== "),
    ("lt->le", r"(?<![<>=])< ", "<= "),
    ("gt->ge", r"(?<![<>=])> ", ">= "),
    ("and->or", r" and ", " or "),
    ("or->and", r" or ", " and "),
    ("true->false", r"= True\b", "= False"),
    ("false->true", r"= False\b", "= True"),
    ("drop-not", r"\bif not ", "if "),
    ("zero->one", r"= 0\.0\b", "= 1.0"),
]

# Lines we never mutate even if they tokenize as code: a hit here is noise.
_SKIP_LINE = re.compile(r"^\s*(from |import |log\.|logging\.|print\()")


_PROSE_TOK_NAMES = (
    # The names that exist on every version we run. FSTRING_*/TSTRING_* are
    # resolved by name because they do NOT exist before 3.12 - and on 3.12+
    # an f-string is NOT a STRING token, which is exactly how f-string prose
    # got classified as code here. Measured on 3.14: `MSG = f"""...a == b` put
    # FSTRING_MIDDLE across three lines, none of them skipped.
    "STRING", "COMMENT", "FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END",
    "TSTRING_START", "TSTRING_MIDDLE", "TSTRING_END",
)
_STRUCT_TOK_NAMES = ("NL", "NEWLINE", "INDENT", "DEDENT", "ENCODING",
                     "ENDMARKER")


def _tok_types(names) -> set:
    import tokenize
    return {getattr(tokenize, n) for n in names if hasattr(tokenize, n)}


def prose_spans(path: Path) -> dict:
    """line number -> list of (col_start, col_end) ranges holding NON-code.

    WHY COLUMNS AND NOT LINES. The first cut classified whole LINES, which
    leaves every mixed line wide open: `MSG = "a value where a == b"` is a
    real assignment, so the line is code, so the regex happily rewrote the
    ENGLISH INSIDE THE STRING. That mutant can only ever SURVIVE, and a
    survivor is read as a blind spot - the same cry-wolf failure the
    line-level fix was meant to end, just one level down.

    A multi-line token occupies the tail of its first line, all of any middle
    lines, and the head of its last. `end_col` on a non-final line is not a
    column on that line, so the tail is spelled as an open interval.

    A file that will not tokenize returns {} - the caller pairs this with
    code_lines(), which returns an empty set there, so nothing is mutable and
    that is reported as "no applicable mutants", never as a pass.
    """
    import tokenize
    prose = _tok_types(_PROSE_TOK_NAMES)
    out: dict = {}
    try:
        with open(path, "rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type not in prose:
                    continue
                (r0, c0), (r1, c1) = tok.start, tok.end
                for row in range(r0, r1 + 1):
                    lo = c0 if row == r0 else 0
                    hi = c1 if row == r1 else 10 ** 9
                    out.setdefault(row, []).append((lo, hi))
    except (tokenize.TokenError, SyntaxError, OSError, ValueError):
        return {}
    return out


def code_lines(path: Path) -> set:
    """Line numbers that carry EXECUTABLE tokens, via tokenize.

    WHY NOT A REGEX. The first cut skipped lines *starting* with `#` or a
    quote, which does nothing for lines INSIDE a multi-line docstring - and
    this repo's modules are heavily documented, so the first sweep spent 70%
    of its mutants rewriting prose ("per-asset sum == pooled to 1e-6" became
    "!=" and was faithfully reported as a SURVIVOR). A tool that cries wolf
    gets ignored, which is the same failure mode verify_readonly.py's
    docstring warns about.

    TWO MECHANISMS, NOT ONE, and this docstring claimed the wrong one until
    mutation testing said otherwise. tests/test_mutation_sweep.py planted
    `STRING` out of the skip set and the prose pin SURVIVED - it had been
    passing for a reason that has nothing to do with the filter:

      * A multi-line docstring is ONE token whose start is its FIRST line.
        Interior lines carry no token start at all, so they are excluded by
        tokenize's STRUCTURE. The filter never sees them. That is the 70%.
      * The string entry earns its place on lines whose ONLY tokens are
        strings: the opening line of a bare docstring - which in this repo
        routinely carries mutable prose, e.g. "does this actually write
        anything?" - and continuation lines of an implicitly concatenated
        string. Without it, those lines are mutable.

    THIS ANSWER IS NOT SUFFICIENT ON ITS OWN, and that is why prose_spans()
    exists: a line can be BOTH. Pair the two - this says which lines may be
    mutated at all, prose_spans() says which columns on them may not.

    tokenize is the authority on what is a string and what is code, so ask it
    rather than pattern-matching around it. A file that will not tokenize
    (syntax error, odd encoding) returns an empty set - nothing is mutable,
    which the caller reports as "no applicable mutants" rather than as a pass.
    """
    import tokenize
    skip = _tok_types(_PROSE_TOK_NAMES) | _tok_types(_STRUCT_TOK_NAMES)
    keep: set = set()
    try:
        with open(path, "rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type in skip:
                    continue
                keep.add(tok.start[0])
    except (tokenize.TokenError, SyntaxError, OSError, ValueError):
        return set()
    return keep


_CLAIM = re.compile(
    r"mutat(?:ion|ed|ion-caught)?|mutant", re.IGNORECASE)


def claimants() -> list:
    """Test files whose prose claims mutation verification."""
    out = []
    for p in sorted((REPO / "tests").glob("test_*.py")):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        n = len(_CLAIM.findall(txt))
        if n:
            out.append((p.relative_to(REPO).as_posix(), n))
    return out


def subjects_of(test_path: Path) -> list:
    """Repo modules a test file imports. Import-derived, not name-derived: a
    test file's name is a convention, its imports are a fact."""
    txt = test_path.read_text(encoding="utf-8", errors="replace")
    mods: set = set()
    for m in re.finditer(r"^\s*(?:from|import)\s+([\w.]+)", txt, re.M):
        dotted = m.group(1)
        head = dotted.split(".")[0]
        if head in {"pytest", "json", "re", "sys", "os", "io", "math",
                    "pathlib", "typing", "importlib", "subprocess", "time",
                    "copy", "hashlib", "collections", "datetime", "tempfile",
                    "numpy", "np", "itertools", "statistics", "shutil",
                    "unittest", "random", "csv", "warnings", "__future__"}:
            continue
        cand = REPO / (dotted.replace(".", "/") + ".py")
        if cand.is_file():
            mods.add(cand.relative_to(REPO).as_posix())
    # A module LOADED by path - spec_from_file_location(...) - is a subject
    # too. But a path merely NAMED inside a string is not: this repo's tests
    # routinely read another file as TEXT to assert a registration, and
    # treating that as a subject makes every survivor in the other file look
    # like this file's blind spot. Measured: sweeping tests/test_watch_lane.py
    # pulled in scripts/outputs_gc.py and tests/conftest.py purely because two
    # pins read them as strings, and every survivor reported came from there.
    loaded = re.search(r"spec_from_file_location", txt) is not None
    if loaded:
        for m in re.finditer(r'["\']([\w/]+\.py)["\']', txt):
            cand = REPO / m.group(1)
            if cand.is_file() and "test" not in Path(m.group(1)).name:
                mods.add(m.group(1))
        for m in re.finditer(r'"(\w+)"\s*/\s*f?"(\w+)\.py"', txt):
            cand = REPO / m.group(1) / f"{m.group(2)}.py"
            if cand.is_file():
                mods.add(f"{m.group(1)}/{m.group(2)}.py")
    return sorted(mods)


def _first_code_match(rx, line: str, spans):
    """The first match of `rx` on `line` that does NOT start inside prose.

    Scanning past prose rather than rejecting the line is the whole point: a
    log call like `log.info("a == b")` may carry a REAL comparison later on
    the same line, and dropping the line would silently stop testing it.
    Measured motive: `MSG = "a value where a == b"` was being rewritten inside
    the string, producing a mutant that can only ever SURVIVE and then reads
    as a blind spot.
    """
    pos = 0
    while True:
        m = rx.search(line, pos)
        if m is None:
            return None
        if not any(lo <= m.start() < hi for lo, hi in spans):
            return m
        pos = m.start() + 1


def build_mutants(module: str, limit: int) -> list:
    """One mutant per operator per module, taken from a MUTABLE line."""
    path = REPO / module
    src = path.read_text(encoding="utf-8", errors="replace")
    lines = src.splitlines()
    live = code_lines(path)          # which LINES may be mutated at all
    spans = prose_spans(path)        # which COLUMNS on them may not
    out = []
    for label, pat, rep in OPERATORS:
        rx = re.compile(pat)
        for i, ln in enumerate(lines, start=1):
            if i not in live:
                continue             # prose: mutating it proves nothing
            if _SKIP_LINE.match(ln):
                continue
            m = _first_code_match(rx, ln, spans.get(i, ()))
            if m is None:
                continue
            new_line = ln[:m.start()] + rx.sub(rep, ln[m.start():], count=1)
            if new_line == ln or src.count(ln) != 1:
                continue          # ambiguous anchor: skip rather than guess
            out.append({"path": module, "old": ln, "new": new_line,
                        "pin": "", "op": label})
            break
        if len(out) >= limit:
            break
    return out


def sweep(test: str, limit: int = 10, verbose: bool = True) -> dict:
    tp = REPO / test
    mods = subjects_of(tp)
    mutants = []
    for m in mods:
        mutants += build_mutants(m, limit)
    if verbose:
        print(f"{test}")
        print(f"  subjects: {mods or '(none found)'}")
        print(f"  mutants : {len(mutants)}")
    results = []
    for mu in mutants:
        # pin="" runs the WHOLE file - a sweep asks whether the file catches
        # it, not whether one named test does
        r = run_one({**mu, "pin": ""}, test, verbose=False)
        r["op"] = mu["op"]
        results.append(r)
        if verbose:
            mark = "caught " if r["verdict"] == CAUGHT else "SURVIVED"
            short = Path(mu["path"]).name
            print(f"    {mark} {short:<18} {mu['op']:<12} "
                  f"{mu['old'].strip()[:50]}")
    caught = sum(1 for r in results if r["verdict"] == CAUGHT)

    # PER-MODULE TALLY, and it is not cosmetic. A test file's mutation claim
    # is about the module it pins; the other subjects come in through
    # transitive or monkeypatch imports and it never claimed them. Measured:
    # adding one `import ml.history as hist` line to a monkeypatch test took
    # tests/test_watch_lane.py from 8 mutants in one module to 18 across two,
    # and the 11 new survivors all landed in the module the file was never
    # about. An unlabeled pooled score reads as that file's blind spot.
    by_mod: dict = {}
    # strict=True is load-bearing, not lint appeasement: the tally must
    # PARTITION the mutant set, losing and inventing none, and a silent zip
    # truncation is exactly how a count goes quietly wrong. The pin
    # test_the_per_module_tally_attributes_survivors_correctly asserts
    # by_module sums back to n.
    for mu, r in zip(mutants, results, strict=True):
        c, n = by_mod.get(mu["path"], (0, 0))
        caught_here = 1 if r["verdict"] == CAUGHT else 0
        by_mod[mu["path"]] = (c + caught_here, n + 1)
    if verbose and len(by_mod) > 1:
        print("  per subject:")
        for m, (c, n) in sorted(by_mod.items()):
            print(f"    {c}/{n:<3} {m}")
    return {"test": test, "subjects": mods, "n": len(results),
            "caught": caught, "by_module": {k: list(v)
                                            for k, v in by_mod.items()},
            "_mutants": mutants, "results": results}


def sweep_all(limit: int, out_path: str, budget_sec: float = 0.0,
              only_unswept: bool = True) -> dict:
    """Sweep every claimant file, writing after EACH file so a kill is not a
    total loss.

    RESUMABLE BY CONSTRUCTION. This is a multi-hour job - 69 claimant files,
    185 resolved subject modules, ~533 mutants at limit 3, and every mutant is
    a full run of its test file. A sweep that must complete in one sitting
    would never be run at all, and an un-run checker is the same as no checker.

    `budget_sec` stops cleanly at a wall-clock ceiling and RECORDS WHAT IT DID
    NOT REACH. A partial sweep that silently looks complete is the exact
    failure this whole directory exists to prevent: the remaining files are
    UNSWEPT, which is not the same as clean.
    """
    import time as _time
    out = Path(out_path)
    done: dict = {}
    if only_unswept and out.is_file():
        try:
            done = json.loads(out.read_text(encoding="utf-8")).get("files", {})
        except (OSError, ValueError):
            done = {}

    rows = claimants()
    started = _time.time()
    stopped_early = ""
    for i, (name, _mentions) in enumerate(rows, start=1):
        if name in done:
            continue
        if budget_sec and (_time.time() - started) > budget_sec:
            stopped_early = (f"wall-clock budget {budget_sec:.0f}s reached "
                             f"after {i - 1} of {len(rows)} files")
            break
        res = sweep(name, limit, verbose=False)
        done[name] = {"n": res["n"], "caught": res["caught"],
                      "subjects": res["subjects"],
                      "by_module": res.get("by_module", {}),
                      "survivors": [
                          {"op": r.get("op"), "path": m.get("path"),
                           "old": m.get("old", "").strip()[:120]}
                          for m, r in zip(res.get("_mutants", []),
                                          res["results"], strict=True)
                          if r["verdict"] != CAUGHT]}
        unswept = [n for n, _ in rows if n not in done]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(
            {"files": done, "unswept": unswept,
             "stopped_early": stopped_early}, indent=2), encoding="utf-8")
        mark = "OK " if res["caught"] == res["n"] and res["n"] else "!! "
        print(f"  {mark}{res['caught']:>3}/{res['n']:<3} {name}", flush=True)

    unswept = [n for n, _ in rows if n not in done]
    return {"files": done, "unswept": unswept, "stopped_early": stopped_early}


def report_all(state: dict) -> int:
    """Print the sweep verdict. THREE OUTCOMES, never two.

    A file can catch every mutant, leave one alive, or produce no mutant at
    all - and the third is not a pass. It means the subject could not be
    resolved or every operator was skipped, i.e. the file claims mutation
    verification and this tool could not even try. Rolling that into "clean"
    is the same error as reading pytest's exit 5 as green, which is why
    scripts/checked.py exists. Files never reached are a FOURTH state and are
    reported as unknown, never as clean.
    """
    files = state["files"]
    blind = {k: v for k, v in files.items() if v["n"] and v["caught"] < v["n"]}
    vacuous = {k: v for k, v in files.items() if v["n"] == 0}
    clean = {k: v for k, v in files.items()
             if v["n"] and v["caught"] == v["n"]}
    tot_n = sum(v["n"] for v in files.values())
    tot_c = sum(v["caught"] for v in files.values())

    print()
    print("=" * 66)
    print(f"swept {len(files)} claimant file(s); {tot_c}/{tot_n} mutants caught")
    print(f"  {len(clean):>3} file(s) caught every mutant")
    print(f"  {len(blind):>3} file(s) left at least one alive")
    print(f"  {len(vacuous):>3} file(s) produced NO mutant at all - NOT a pass")
    if state["unswept"]:
        print(f"  {len(state['unswept']):>3} file(s) NEVER SWEPT - unknown, "
              f"not clean")
        if state.get("stopped_early"):
            print(f"      ({state['stopped_early']})")

    if vacuous:
        print()
        print("NO APPLICABLE MUTANTS - subject unresolved, or every operator")
        print("skipped. These CLAIM mutation verification and this tool could")
        print("not even try:")
        for k in sorted(vacuous):
            print(f"  {k}   subjects={files[k]['subjects'] or '(none)'}")

    if blind:
        print()
        print("SURVIVORS. Read each one: unreachable-from-here, semantically")
        print("equivalent, and genuinely unpinned are three different answers")
        print("and only the third is a defect. Do not delete the operator.")
        for k in sorted(blind,
                        key=lambda x: files[x]["caught"] - files[x]["n"]):
            v = files[k]
            print()
            print(f"  {k}  ({v['caught']}/{v['n']})")
            for m, (c, n) in sorted(v.get("by_module", {}).items()):
                if c < n:
                    print(f"      {c}/{n}  {m}")
            for s in v["survivors"][:4]:
                print(f"        {s['op']:<11} {s['old'][:62]}")
    return 1 if (blind or vacuous or state["unswept"]) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--test", help="test file to sweep")
    ap.add_argument("--claims", action="store_true",
                    help="list test files whose prose claims mutation work")
    ap.add_argument("--max", type=int, default=10,
                    help="max mutants per subject module")
    ap.add_argument("--json", help="write the full result here")
    ap.add_argument("--all", action="store_true",
                    help="sweep EVERY claimant file (hours; resumable)")
    ap.add_argument("--state", default="outputs/reports/mutation_sweep.json",
                    help="--all progress file; rerunning resumes from it")
    ap.add_argument("--budget-sec", type=float, default=0.0,
                    help="--all wall-clock ceiling; unreached files are "
                         "reported UNSWEPT, never as clean")
    ap.add_argument("--report", action="store_true",
                    help="re-print the report from --state without running")
    args = ap.parse_args(argv)

    if args.claims:
        rows = claimants()
        print(f"{len(rows)} test file(s) whose prose claims mutation work:")
        for name, n in rows:
            print(f"  {n:>3} mention(s)  {name}")
        return 0

    if args.report:
        try:
            st = json.loads(Path(args.state).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"no readable state at {args.state}: {exc}")
            return 1
        st.setdefault("unswept", [])
        return report_all(st)

    # THE LOCK COVERS THIS TOOL TOO, and that is not decoration: the incident
    # that produced the lock was caused BY THIS FILE. `--all` plants mutants in
    # repo files through run_one, and an overlapping `pytest tests/` failed on
    # one of them with neither tool saying a word. Guarding only
    # scripts/mutate.py's CLI would have left the actual offender unguarded -
    # a fix aimed at the symptom's neighbour rather than the symptom.
    try:
        lock = tree_lock()
        lock.__enter__()
    except RuntimeError as exc:
        print(f"[sweep] {exc}")
        return 2
    try:
        if args.all:
            return report_all(sweep_all(args.max, args.state, args.budget_sec))

        if not args.test:
            print("give --test, --all, --report or --claims")
            return 1

        res = sweep(args.test, args.max)
        if args.json:
            Path(args.json).write_text(json.dumps(res, indent=2),
                                       encoding="utf-8")
        print(f"\n  {res['caught']}/{res['n']} caught")
        if res["n"] == 0:
            print("  NO APPLICABLE MUTANTS - this is not a pass. Either the "
                  "subject could not be resolved from the test's imports, or "
                  "every operator was skipped.")
            return 1
        if res["caught"] < res["n"]:
            print("  Survivors are places this file's own mutation claim is not "
                  "supported. Read each one: unreachable-from-here, semantically "
                  "equivalent, and genuinely unpinned are three different "
                  "answers, and only the third is a defect.")
            return 1
        return 0
    finally:
        lock.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
