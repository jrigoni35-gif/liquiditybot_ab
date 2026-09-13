"""scripts/claim_check.py - a commit message is a claim. Check it.

WHY THIS EXISTS. "Never ship a claim you have not run" is a standing rule
here, and commit messages are where it is broken most often, because nothing
reads them back. A wrong file path, a stale line number or an invented test
name in a commit message outlives the code: it is the artifact a future
session greps when it is trying to find out what happened, and it is never
re-checked against anything.

Measured in this repo's own recent history, and the reason this is mechanical
rather than a habit: claims have shipped in commit messages and docstrings
that were false at the moment of writing - "read-only" for a script that
writes `outputs/horizon_report.txt`, `book="watch"` for rows tagged `"5m"`,
"nothing reads the tick tape" while `markout_report` reads it, "gates clean"
while the suite was still running. Every one of those is the same shape: a
belief written into a permanent place without being run.

WHAT IT CAN CHECK, and it is deliberately only the mechanical part:

  * Every repo path named in the message exists (in the right tree - see
    below). A path that moved is the single most common stale claim.
  * Every `path.py:NNN` reference points at a line that exists.
  * Every `test_*` name named in the message is defined somewhere in tests/.
  * Every dotted `module.symbol` in backticks resolves to a real name.

WHAT IT CANNOT CHECK, said out loud because a checker that implies more than
it verifies is itself a false claim. It cannot tell you a number is right. A
message saying "20/20 caught" or "5265 passed" is a measurement, and this tool
has no way to reproduce it - so it does not pretend to. It FLAGS such numbers
as volatile and asks for a re-derive pointer, which is the rule that applies:
if a number is volatile, name where to re-derive it rather than freezing it.

WHICH TREE. Paths resolve against the commit being checked, never the working
tree, or a commit that DELETES a file would fail its own honest message and a
commit that adds one would pass before it exists:
  --rev <sha>    -> that commit's tree (git ls-tree -r)
  --message-file -> tracked files plus the staged index (commit-msg hook)

Usage:
    python scripts/claim_check.py --rev HEAD
    python scripts/claim_check.py --message-file .git/COMMIT_EDITMSG
    python scripts/claim_check.py --rev HEAD --strict   # volatile = error

Exit: 0 clean, 1 a claim failed, 2 usage/ git error.
"""
from __future__ import annotations

import argparse
import re
import subprocess  # nosec B404 - asking git IS this tool's job
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FAIL_RC = 1
USAGE_RC = 2

# A repo-relative path: at least one directory segment, then a known text
# extension. Requiring the directory is what keeps prose words like "green."
# and version strings out; this repo's real references are always pathish.
_EXT = r"py|json|md|csv|ya?ml|txt|bat|ps1|toml|jsonl"

# A repo-relative path: at least one DIRECTORY segment, then a known text
# extension. Requiring the directory keeps prose words and version strings
# out; this repo's real references are always pathish.
#
# A directory segment may not itself end in a file extension. Without that,
# `main.py/train_meta.py` - prose meaning "and", which this repo writes often -
# matches as ONE path with `main.py/` as its directory, and gets reported as a
# file that does not exist. Measured over 60 commits of history.
_PATH = re.compile(
    r"(?<![\w/.-])("
    r"(?:(?!\w[\w.-]*\.(?:" + _EXT + r")/)[A-Za-z_][\w.-]*/)+"
    r"[\w.-]+\.(?:" + _EXT + r"))(?!/)(?::(\d+))?")

_TESTNAME = re.compile(r"(?<![\w.])(test_[A-Za-z0-9_]{3,})\b")

# `module.symbol` inside backticks only. Unbackticked dotted words are prose
# far more often than they are code ("e.g. config.json defaults"), and a
# checker that cries wolf gets turned off.
_DOTTED = re.compile(r"`([a-z_][\w]*(?:\.[A-Za-z_]\w*)+)`")

# A bare count next to a countable noun. These are measurements: this tool
# cannot reproduce them, so it asks for a pointer instead of pretending.
_VOLATILE = re.compile(
    r"(?<![\w.])(\d[\d,]*)\s*(?:/\s*\d[\d,]*\s*)?"
    r"(passed|failed|tests?|rows?|files?|mutants?|findings?|"
    r"anchors?|panels?|trips?|entries)\b",
    re.IGNORECASE)

# Phrases that name where to re-derive, which is what makes a number legal.
_POINTER = re.compile(
    r"re-?derive|reproduce with|see |run |`[^`]*\.py|scripts/|measured by",
    re.IGNORECASE)


def _git(*args: str) -> str:
    # nosec B603 B607 - argv is a fixed git verb plus a rev this tool was
    # given on its own command line; no shell. `git` is resolved from PATH
    # deliberately: this repo runs on Windows and in a venv, and hardcoding an
    # absolute git would break on both.
    r = subprocess.run(["git", *args], cwd=str(REPO),  # nosec B603 B607
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def ignored(paths) -> set:
    """Of `paths`, the ones git is told to ignore.

    WHY THIS IS NOT AN ERROR. `outputs/` is gitignored runtime state, and a
    commit message naming `outputs/watch_history.csv` or
    `outputs/horizon_report.txt` is describing a file the bot WRITES, not a
    tracked artifact that should exist in the tree. Flagging those as false
    claims was this tool's own first false-positive: run over seven of its
    author's own commits it reported three failures and ALL THREE were its own
    bug. A checker that cries wolf gets turned off, which is the failure mode
    every other tool in this directory was written to avoid.
    """
    if not paths:
        return set()
    # nosec B603 B607 - a fixed git verb; the paths go in on STDIN, never
    # into argv, so a hostile path cannot become an argument. Same PATH
    # reasoning as _git above.
    r = subprocess.run(["git", "check-ignore", "--stdin"],  # nosec B603 B607
                       cwd=str(REPO),
                       input=chr(10).join(sorted(paths)),
                       capture_output=True, text=True)
    # rc 0 = some ignored, 1 = none ignored, 128 = error. Only 128 is a
    # problem, and there the honest answer is "assume nothing is ignored".
    if r.returncode not in (0, 1):
        return set()
    return {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}


def tree_paths(rev: str | None) -> set:
    """The set of paths that EXIST for the commit under test.

    For --rev that is the commit's own tree. For a message file it is tracked
    files plus the staged index, because the commit has not been written yet
    and its new files are only in the index.
    """
    if rev:
        out = _git("ls-tree", "-r", "--name-only", "-z", rev)
    else:
        out = _git("ls-files", "-z") + _git("diff", "--cached",
                                            "--name-only", "-z")
    return {p for p in out.split("\0") if p}


def file_lines(rev: str | None, path: str) -> int:
    """Line count of `path` AS OF the commit under test, or -1 if unreadable.

    Reading the working-tree copy would validate a line number against a file
    the commit does not contain - the check would pass for the wrong reason,
    which is worse than not checking.
    """
    try:
        if rev:
            blob = _git("show", f"{rev}:{path}")
        else:
            p = REPO / path
            blob = p.read_text(encoding="utf-8", errors="replace")
    except (RuntimeError, OSError):
        return -1
    return blob.count("\n") + (0 if blob.endswith("\n") else 1)


def test_names() -> set:
    """Every `def test_*` defined under tests/. Read from source, not from a
    pytest collection: collection needs imports to succeed, and a checker that
    only works on a green tree cannot check the commit that fixes a red one.
    """
    out: set = set()
    d = REPO / "tests"
    if not d.is_dir():
        return out
    for p in d.rglob("test_*.py"):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.update(re.findall(r"^\s*(?:async\s+)?def\s+(test_\w+)",
                              txt, re.M))
    return out


def test_files() -> set:
    """Basenames of test FILES, extension stripped.

    Messages name files without their prefix or extension all the time -
    "test_windows" is `test_windows.bat`, "test_boards_stripped" is
    `tests/test_boards_stripped.py`. Neither is a test FUNCTION, and reporting
    them as invented ones accounted for most of this tool's false alarms over
    60 commits of history. The path regex only blanks a path that carries a
    DIRECTORY and an extension, so these survive it by construction.
    """
    out: set = set()
    for d in (REPO / "tests", REPO):
        if not d.is_dir():
            continue
        for pat in ("test_*.py", "test_*.bat"):
            out.update(p.stem for p in d.glob(pat))
    return out


def symbol_exists(dotted: str) -> bool:
    """Does `a.b.c` name something real? Resolved TEXTUALLY on purpose.

    Importing to find out would execute repo modules - a checker with side
    effects is not a checker - so this asks whether the module file exists and
    whether the trailing name is defined or assigned in it. A false PASS here
    is acceptable; a false FAIL would make the tool noise.
    """
    parts = dotted.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        mod = REPO / ("/".join(parts[:cut]) + ".py")
        if not mod.is_file():
            mod = REPO / "/".join(parts[:cut]) / "__init__.py"
        if not mod.is_file():
            continue
        try:
            txt = mod.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return True
        leaf = parts[cut]
        pat = (rf"^\s*(?:async\s+)?def\s+{re.escape(leaf)}\b"
               rf"|^\s*class\s+{re.escape(leaf)}\b"
               rf"|^\s*{re.escape(leaf)}\s*[:=]"
               rf"|\bself\.{re.escape(leaf)}\s*[:=]")
        return re.search(pat, txt, re.M) is not None
    return True          # module not in this repo: not ours to judge


def check(message: str, rev: str | None = None) -> list:
    """Returns a list of (severity, kind, detail). Severity is 'error' for a
    claim shown false, 'warn' for a number this tool cannot reproduce."""
    findings = []
    paths = tree_paths(rev)
    known_tests = test_names()

    named = {m.group(1) for m in _PATH.finditer(message)}
    ign = ignored(named - paths)
    # A commit that DELETES or RENAMES a file names a path absent from its own
    # tree, and that message is honest. Resolving only against the commit's
    # tree made every such commit fail its own description - measured over 60
    # commits of history, where a "dissolve the forgiveness machinery" commit
    # was reported FALSE for naming the two files it removed.
    parent_paths = tree_paths(f"{rev}^") if rev else set()
    # Top-level directories that exist at all. A path whose first segment is
    # not one of them is not a claim about THIS repo - this environment
    # carries the Obsidian vault as a second working directory, so `raw/...`
    # and `wiki/...` in a message are real files somewhere else.
    top_dirs = {p.split("/")[0] for p in paths}
    seen_paths = set()
    for m in _PATH.finditer(message):
        path, line = m.group(1), m.group(2)
        if (path, line) in seen_paths:
            continue
        seen_paths.add((path, line))
        if path not in paths:
            if path in ign:
                continue          # gitignored runtime state: not ours to find
            if path in parent_paths:
                continue          # the commit DELETED or renamed it - honest
            if path.split("/")[0] not in top_dirs:
                continue          # not a path in this repo at all (the vault
                                  # is a second working directory here, and
                                  # `raw/...` / `wiki/...` live there)
            # TWO OUTCOMES, and only one is dangerous. Measured over 60
            # commits: every absent path this tool could find was either a
            # HYPOTHETICAL in a worked example ("commit B then changes only
            # scripts/util.py's body") or a path the message EXPLICITLY
            # disclosed as never-shipped. Neither misleads anyone - the
            # message says what it is.
            #
            # What DOES mislead is a pointer that looks resolvable and is not:
            # a file that MOVED. A future session greps the name, finds it
            # somewhere else, and reads the old message against the new file.
            # So a basename that exists elsewhere in the tree is an ERROR; a
            # name the repo has never carried anywhere is a WARN.
            base = path.rsplit("/", 1)[-1]
            elsewhere = sorted(q for q in paths
                               if q.rsplit("/", 1)[-1] == base)
            if elsewhere:
                findings.append(
                    ("error", "moved-path",
                     f"{path} - the name exists at {elsewhere[0]}"))
            else:
                findings.append(("warn", "unknown-path", path))
            continue
        if line:
            n = file_lines(rev, path)
            if n >= 0 and int(line) > n:
                findings.append(
                    ("error", "line-out-of-range",
                     f"{path}:{line} but the file has {n} lines"))

    # A test FILE name is not a test FUNCTION name. `tests/test_watch_lane.py`
    # contains the substring `test_watch_lane`, and reporting that as an
    # unknown test was this tool's second false positive on its author's own
    # commits. Blank every path match before looking for function names.
    defused = _PATH.sub(lambda mm: " " * len(mm.group(0)), message)
    for m in _TESTNAME.finditer(defused):
        name = m.group(1)
        if name in known_tests or name in test_files():
            continue
        findings.append(("error", "unknown-test", name))

    for m in _DOTTED.finditer(message):
        sym = m.group(1)
        if not symbol_exists(sym):
            findings.append(("error", "unresolved-symbol", sym))

    for m in _VOLATILE.finditer(message):
        window = message[max(0, m.start() - 160):m.end() + 160]
        if _POINTER.search(window):
            continue
        findings.append(("warn", "volatile-number", m.group(0).strip()))

    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rev", help="commit to check (paths resolve in ITS tree)")
    ap.add_argument("--message-file", help="a commit-msg hook's message file")
    ap.add_argument("--strict", action="store_true",
                    help="treat volatile numbers as errors too")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if bool(args.rev) == bool(args.message_file):
        print("give exactly one of --rev or --message-file")
        return USAGE_RC

    try:
        if args.rev:
            msg = _git("log", "-1", "--format=%B", args.rev)
        else:
            msg = Path(args.message_file).read_text(encoding="utf-8",
                                                    errors="replace")
        findings = check(msg, args.rev)
    except (RuntimeError, OSError) as exc:
        print(f"[claim] cannot read the message: {exc}")
        return USAGE_RC

    errors = [f for f in findings if f[0] == "error"]
    warns = [f for f in findings if f[0] == "warn"]

    for sev, kind, detail in findings:
        mark = "FALSE " if sev == "error" else "unrun"
        print(f"[claim] {mark} {kind:<19} {detail}")

    if warns and not args.quiet:
        print("[claim] 'unrun' is not an accusation - this tool cannot "
              "reproduce a measurement. Name where to re-derive it "
              "(a script, a command) and the flag clears.")

    if not args.quiet:
        print(f"\n[claim] {len(errors)} false, {len(warns)} unrun")
    if errors:
        return FAIL_RC
    if warns and args.strict:
        return FAIL_RC
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
