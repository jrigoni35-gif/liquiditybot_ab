"""scripts/local_security_review.py - a security review that needs no API key.

WHY THIS EXISTS
---------------
The Anthropic `security-guidance` plugin's LLM review has never run on this
box. Measured 2026-09-13: `HAS_API_CREDENTIALS` is false (no
`ANTHROPIC_API_KEY`, no `ANTHROPIC_AUTH_TOKEN`, no 3P provider flag), so all
three of its review entry points bail, logging `detected git commit in
command` and then `LLM review disabled or no API credentials`. Restoring the
hook restored INVOCATION, not REVIEW. See
`docs/quant/2026-09-13_resume_storm_and_hook_root_cause.md` section 9a.

This reviews a diff with the LOCAL model already on this machine (Ollama; the
default is chosen by measurement - see DEFAULT_MODEL), so it needs no
credential, no network egress and no subscription. It is NOT as strong as a
frontier model. It is enormously stronger than the zero reviews that have run
to date.

The diff is reviewed ONE FILE AT A TIME. That is not a style choice: the
server's context is 4096 tokens unless `OLLAMA_CONTEXT_LENGTH` says otherwise,
and an over-long prompt is context-SHIFTED, which evicts the system prompt and
produces a confident `NONE` about code the model never saw. See CHUNK_LIMIT.

THE ONE PROPERTY THAT MATTERS
-----------------------------
"0 findings" and "the scan is broken" are the same observation until they are
separated (CLAUDE.md, THE MINDSET). So this tool never returns 0 for a run it
could not perform:

    exit 0  reviewed, nothing found
    exit 1  reviewed, findings reported
    exit 2  COULD NOT REVIEW (model unreachable, empty diff, unparseable
            reply). Never confused with a clean bill of health.

And `--self-test` plants a diff carrying three textbook vulnerabilities and
fails unless the reviewer names at least one. Run it before believing a green.

USAGE
    python scripts/local_security_review.py                 # working tree
    python scripts/local_security_review.py --staged
    python scripts/local_security_review.py --rev HEAD
    python scripts/local_security_review.py --rev abc123 --strict
    python scripts/local_security_review.py --self-test

SAFE class: reads a diff, calls localhost, prints. Touches no config, no
order path, no outputs/.
"""
from __future__ import annotations

import argparse
import re
import subprocess  # nosec B404 - git plumbing only, argv list, never shell=True
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from local_llm_mcp import (  # noqa: E402  - path set above
    build_chat_payload,
    call_endpoint,
    truncate_content,
)

DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"

# Chosen by measurement, not reputation. `scripts/local_review_eval.py` ran
# both over the same 14-case corpus twice, identically (temperature 0):
#
#   model                  recall   false-pos   format    median
#   qwen2.5:7b-instruct      8/9       2/5       10/14     0.5 s
#   qwen2.5-coder:7b         9/9       2/5       14/14     0.3 s
#
# Same 4.7 GB on disk, same VRAM class, so the upgrade is free. It is better
# or equal on every axis, and the format column is the most robust difference:
# 14/14 means the prose-drift retry shim never has to fire.
# It did NOT fix discrimination - BOTH models flag the SAFE look-alike
# controls (a list-form subprocess call and ast.literal_eval), so both are
# still partly matching vocabulary rather than reading code. Re-derive with
# `python scripts/local_review_eval.py --models a,b`.
DEFAULT_MODEL = "qwen2.5-coder:7b"

# PER-FILE budget, in characters. Derived from the SERVER's context, not from
# taste. Measured on this box 2026-09-14: `OLLAMA_CONTEXT_LENGTH` is unset in
# User, Machine and Process scope, so the server runs `n_ctx_slot = 4096` -
# and that 4096 covers prompt AND generation together.
#
#   4096 total - 1400 generated (max_tokens) - ~250 system prompt = ~2450 for
#   the diff. At a worst-case 3 chars/token that is ~7300 chars, so 6000 is
#   the budget with headroom. (Observed density is far kinder - a 19,715-char
#   diff measured 2050 tokens, ~9.6 chars/token - but budgeting on the
#   observed case rather than the worst case is how a silent overflow gets
#   shipped.)
#
# PENDING, 2026-09-14: `OLLAMA_CONTEXT_LENGTH=16384` has been written to the
# USER environment, but the RUNNING server still reports `n_ctx_slot = 4096` -
# an environment write never reaches a live process, the same lesson the hook
# PATH fix taught this repo the night before. VRAM arithmetic says 16384 fits
# (weights ~4466 MiB + KV 896 MiB at 56 KiB/token, against 8192 MiB total).
#
# DO NOT raise CHUNK_LIMIT on the strength of that env var. Restart Ollama,
# confirm `n_ctx_slot = 16384` in %LOCALAPPDATA%\Ollama\server.log, and only
# then raise it - budgeting against a context the server is not actually
# serving is how a silent overflow ships. `tests/test_local_security_review.py`
# pins the 4096 arithmetic and will fail loudly if this is raised alone.
#
# The OpenAI-compat `/v1/chat/completions` endpoint this uses cannot carry
# `num_ctx` per request, so the env var is the only lever short of moving to
# native `/api/chat`.
CHUNK_LIMIT = 6_000

EXIT_CLEAN, EXIT_FINDINGS, EXIT_CANNOT_REVIEW = 0, 1, 2

SYSTEM = (
    "You are a security reviewer for a Python trading system. You are given a "
    "unified git diff. Report ONLY concrete security defects you can point at "
    "in the diff.\n"
    "Look for: hardcoded secrets, API keys and passwords; command or SQL "
    "injection; shell=True with interpolated input; eval/exec on untrusted "
    "data; unsafe deserialization (pickle, yaml.load); path traversal; "
    "disabled TLS verification; credentials in logs or error messages; "
    "broad except blocks that swallow security failures; and any new network "
    "egress.\n"
    "Output ONE LINE PER FINDING, exactly:\n"
    "SEVERITY | file | what is wrong | why it is exploitable\n"
    "SEVERITY is CRITICAL, HIGH, MEDIUM or LOW. No preamble, no bullets, no "
    "closing summary. If and only if you find nothing, output the single "
    "word NONE."
)

_FINDING = re.compile(
    r"^\s*(CRITICAL|HIGH|MEDIUM|LOW)\s*\|(.+)$", re.IGNORECASE)

# A diff that must produce at least one finding, or the reviewer is broken.
#
# DELIBERATE VULNERABILITIES, INERT BY CONSTRUCTION. The `shell=True`,
# `eval(...)` and `sk_live_...` below are INSIDE A STRING LITERAL that is only
# ever sent to a model as text. Nothing here is executed, imported, or
# written to disk, and the "key" is a made-up constant that authenticates
# nothing. They exist so `--self-test` can prove the scan is capable of
# failing - a reviewer that has never been shown a true positive is not known
# to work. Pattern scanners WILL flag these lines; that is the point, and it
# is the expected behaviour, not a defect to fix.
_CANARY_DIFF = '''\
diff --git a/payments.py b/payments.py
--- a/payments.py
+++ b/payments.py
@@ -1,3 +1,12 @@
+import os, subprocess
+
+STRIPE_SECRET = "sk_live_51HxQwErTyUiOpAsDfGhJkLzXcVbNm0011223344"
+
+def refund(user_input):
+    subprocess.run("refund-tool --id " + user_input, shell=True)
+
+def load_rule(blob):
+    return eval(blob)
'''


def _git(args: list[str], cwd: Path) -> str:
    """Run a git plumbing command. argv list, never a shell string."""
    # nosec B603 B607 - fixed argv, no shell, no user-controlled string, and
    # `git` resolved from PATH is this repo's standing convention for git
    # plumbing (auto_update.py:293, claim_check.py:102, corpus_sync.py:105).
    out = subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=str(cwd), capture_output=True, check=False)
    if out.returncode != 0:
        err = out.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")
    return out.stdout.decode("utf-8", errors="replace")


def collect_diff(rev: str | None, staged: bool, cwd: Path) -> str:
    if rev:
        return _git(["show", "--format=%H%n%s%n", "--unified=3", rev], cwd)
    if staged:
        return _git(["diff", "--cached", "--unified=3"], cwd)
    return _git(["diff", "--unified=3"], cwd)


def parse_findings(reply: str) -> list[str]:
    """Findings from the model's reply.

    Raises ValueError when the reply is neither NONE nor parseable - an
    unreadable answer is a BROKEN SCAN, and the caller maps it to exit 2.
    """
    text = (reply or "").strip()
    if not text:
        raise ValueError("model returned an empty reply")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    findings = [ln for ln in lines if _FINDING.match(ln)]
    if findings:
        return findings
    if any(ln.upper() == "NONE" or ln.upper().startswith("NONE")
           for ln in lines):
        return []
    raise ValueError(
        "model reply matched neither the finding format nor NONE; "
        f"first line was: {lines[0][:160]!r}")


# A 7B model asked to review a long diff drifts into prose roughly one run in
# three (measured 2026-09-13 on this repo's own staged diff: the first reply
# opened "This commit introduces a new script ..."). That is a FORMAT failure,
# not a review failure, so it gets one corrective retry before the run is
# declared unreviewable. The retry is capped at one on purpose: a loop that
# keeps asking until it gets a parseable answer would eventually accept a
# hallucinated one.
REFORMAT = (
    "\n\nYour previous reply was prose. Reply again with NOTHING but finding "
    "lines in exactly this shape, one per line:\n"
    "CRITICAL | file.py | what is wrong | why it is exploitable\n"
    "If there are no security defects, reply with the single word NONE. "
    "No summary, no explanation, no code fences."
)


def split_diff(diff: str) -> list[str]:
    """Split a unified diff into one chunk per file.

    WHY THIS IS NOT OPTIONAL. The Ollama server runs at whatever
    `OLLAMA_CONTEXT_LENGTH` says, and UNSET means **4096 tokens** (measured on
    this box 2026-09-14: `n_ctx_slot = 4096` on every slot, the variable unset
    in User, Machine and Process scope). A prompt over that is context-SHIFTED,
    which silently evicts the system prompt that defines the output format -
    and a model that has lost its instructions answers prose or `NONE`. That
    is a clean-looking review of code the model never saw, which is precisely
    the false green this tool exists to prevent.

    Sending one file at a time keeps every prompt small regardless of how big
    the commit is, so coverage does not depend on a character heuristic.
    Measured here: diff text runs about **9.6 chars/token** (a 19,715-char
    diff was 2,050 tokens), but dense or minified content approaches 3, so
    CHUNK_LIMIT is set for the worst case rather than the observed one.
    """
    if not diff.strip():
        return []
    parts = re.split(r"(?m)^(?=diff --git )", diff)
    chunks = [p for p in parts if p.strip()]
    return chunks or [diff]


def review_chunk(chunk: str, base_url: str, model: str,
                 timeout: float, retries: int) -> list[str]:
    body = truncate_content(chunk, CHUNK_LIMIT)
    note = ("\n\n[NOTE: this file's diff was truncated for length; this "
            "review is PARTIAL]" if len(chunk) > CHUNK_LIMIT else "")
    prompt = f"Review this diff.\n\n```diff\n{body}\n```{note}"
    last: Exception | None = None
    for attempt in range(retries + 1):
        payload = build_chat_payload(
            prompt=prompt if attempt == 0 else prompt + REFORMAT,
            system=SYSTEM, max_tokens=1400, model=model)
        reply = call_endpoint(payload, base_url, timeout=timeout)
        try:
            return parse_findings(reply)
        except ValueError as exc:
            last = exc
    raise ValueError(f"{last} (after {retries + 1} attempts)")


def review(diff: str, base_url: str, model: str,
           timeout: float = 180.0, retries: int = 1) -> list[str]:
    """Review a whole diff, one file at a time. Any chunk that cannot be
    reviewed raises - a partial sweep must never be reported as a clean one.
    """
    out: list[str] = []
    for chunk in split_diff(diff):
        out.extend(review_chunk(chunk, base_url, model, timeout, retries))
    return out


# The NEGATIVE arm. A self-test with only a positive arm proves the scan can
# fire and says nothing about whether it cries wolf; `scripts/
# instrument_contract.check_self_tests` enforces that both exist, and this
# file failed that clause on its first pass through the deploy battery.
#
# These two are deliberately the UNAMBIGUOUS controls - a docs edit and a pure
# rename. The harder controls (a parameterised query, a list-form subprocess
# call, `ast.literal_eval`) live in `scripts/local_review_eval.py`, where BOTH
# measured models flagged 2 of 5. Putting a known-failing control in a gate
# that blocks deploys would wedge the pipeline; measuring it in the eval,
# where it is reported as a rate, is the right home for a bar nothing clears.
_CONTROL_DIFFS = (
    ("docs-only", '''\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,4 @@
+## Reporting
+
+The daily report now includes the fee tier.
'''),
    ("pure-rename", '''\
diff --git a/calc.py b/calc.py
--- a/calc.py
+++ b/calc.py
@@ -1,3 +1,4 @@
+def total(rows):
+    subtotal = sum(r.amount for r in rows)
+    return subtotal
'''),
)


def _self_test(base_url: str, model: str) -> int:
    """Two arms. Detection alone is half a measurement."""
    print("[self-test] POSITIVE arm: a diff with a hardcoded live-format key, "
          "a shell=True interpolation and eval() on untrusted input...")
    try:
        found = review(_CANARY_DIFF, base_url, model)
        flagged = []
        for name, diff in _CONTROL_DIFFS:
            hits = review(diff, base_url, model)
            if hits:
                flagged.append((name, hits))
    except Exception as exc:                       # noqa: BLE001
        # UNREACHABLE ENDPOINT IS NOT A FINDING ABOUT THIS INSTRUMENT, and it
        # must not wedge the deploy battery the way a gate depending on a
        # generated artifact already did once (see the record, section 9).
        # Exit 0 with a loud banner: nothing was demonstrated, in either
        # direction. A model that IS reachable and gets an arm wrong still
        # exits non-zero below.
        print(f"[self-test] UNVERIFIED - could not reach the model ({exc})")
        print("[self-test] 0/2 arms exercised (positive + negative control). "
              "A tool that could not run is not a weak tool; it is an "
              "unmeasured one. Re-run with the endpoint up.")
        return EXIT_CLEAN

    for f in found:
        print("   ", f)
    n_ctl = len(_CONTROL_DIFFS)
    n_fp = len(flagged)
    for name, hits in flagged:
        print(f"    CONTROL WRONGLY FLAGGED [{name}]: {hits[0][:110]}")
    print(f"[self-test] positive arm: {len(found)} finding(s) on 3 planted "
          f"defects")
    print(f"[self-test] negative arm: {n_fp}/{n_ctl} controls wrongly "
          f"flagged (false positive rate {100.0 * n_fp / n_ctl:.0f}%)")

    if not found:
        print("[self-test] FAILED - found NOTHING in a diff with three "
              "textbook vulnerabilities. Do not trust a green from it.")
        return EXIT_CANNOT_REVIEW
    if n_fp:
        print("[self-test] FAILED - it fires on clean code, so a finding "
              "from it carries no information.")
        return EXIT_CANNOT_REVIEW
    print("[self-test] PASSED - fires on planted defects, silent on the "
          "controls.")
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rev", help="review this commit instead of the worktree")
    ap.add_argument("--staged", action="store_true", help="review the index")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any finding (default also exits 1; "
                         "--strict additionally treats LOW as blocking)")
    ap.add_argument("--self-test", action="store_true",
                    help="plant a known-vulnerable diff and require a hit")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--repo", default=str(_REPO_ROOT))
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test(a.base_url, a.model)

    try:
        diff = collect_diff(a.rev, a.staged, Path(a.repo))
    except RuntimeError as exc:
        print(f"[review] CANNOT REVIEW: {exc}")
        return EXIT_CANNOT_REVIEW

    if not diff.strip():
        print("[review] CANNOT REVIEW: the diff is empty. Nothing was "
              "examined - this is NOT a clean result.")
        return EXIT_CANNOT_REVIEW

    try:
        findings = review(diff, a.base_url, a.model)
    except Exception as exc:                       # noqa: BLE001
        print(f"[review] CANNOT REVIEW: {exc}")
        print("[review] Start the local model, then re-run. A missing model "
              "is NOT a pass.")
        return EXIT_CANNOT_REVIEW

    scope = a.rev or ("the index" if a.staged else "the working tree")
    chunks = split_diff(diff)
    partial = sum(1 for c in chunks if len(c) > CHUNK_LIMIT)
    truncated = (f" ({partial} file(s) TRUNCATED - partial review)"
                 if partial else "")
    print(f"[review] {scope}: {len(diff)} bytes across {len(chunks)} "
          f"file(s){truncated}, model={a.model}")
    if not findings:
        print("[review] no findings. Run --self-test to confirm the scan "
              "can fire at all before reading this as clean.")
        return EXIT_CLEAN
    for f in findings:
        print("   ", f)
    blocking = [f for f in findings
                if not f.upper().startswith("LOW")] if not a.strict else findings
    print(f"[review] {len(findings)} finding(s), {len(blocking)} blocking.")
    return EXIT_FINDINGS if blocking else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
