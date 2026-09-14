"""Pins for scripts/local_security_review.py.

The property under test is NOT "does it find bugs" - that is the model's job
and it varies. It is: **a run that could not happen must never look like a
clean one.** Every test below exists because the opposite behaviour is the
failure class this repo keeps re-shipping (CLAUDE.md, THE MINDSET: "0 findings
and the scan is broken are the SAME OBSERVATION until separated").

No network. The endpoint is stubbed everywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import local_security_review as lsr  # noqa: E402


# --------------------------------------------------------------------------
# parse_findings: the three outcomes must stay distinguishable
# --------------------------------------------------------------------------

def test_findings_are_parsed():
    reply = (
        "CRITICAL | pay.py | hardcoded key | grants access\n"
        "MEDIUM | run.py | eval on input | remote code execution\n")
    assert len(lsr.parse_findings(reply)) == 2


def test_none_is_a_clean_result_not_an_error():
    assert lsr.parse_findings("NONE") == []
    assert lsr.parse_findings("  none  ") == []


@pytest.mark.parametrize("reply", [
    "",
    "   \n  ",
    "Sure! I'd be happy to review this diff for you.",
    "```json\n{\"findings\": []}\n```",
    "I could not access the file.",
])
def test_unparseable_reply_RAISES_and_is_never_read_as_clean(reply):
    """A reply the tool cannot read is a BROKEN SCAN, not zero findings.

    If this ever returns [] instead of raising, a chatty or malformed model
    reply silently becomes a green review.
    """
    with pytest.raises(ValueError):
        lsr.parse_findings(reply)


def test_prose_around_a_real_finding_still_yields_the_finding():
    reply = ("Here is what I found:\n"
             "HIGH | net.py | TLS verification disabled | MITM\n"
             "Let me know if you want more detail.")
    assert len(lsr.parse_findings(reply)) == 1


# --------------------------------------------------------------------------
# exit codes: 2 means COULD NOT REVIEW and must never collapse to 0
# --------------------------------------------------------------------------

def test_empty_diff_exits_CANNOT_REVIEW_not_clean(monkeypatch):
    monkeypatch.setattr(lsr, "collect_diff", lambda *a, **k: "   \n")
    rc = lsr.main(["--repo", str(_ROOT)])
    assert rc == lsr.EXIT_CANNOT_REVIEW
    assert rc != lsr.EXIT_CLEAN


def test_unreachable_model_exits_CANNOT_REVIEW_not_clean(monkeypatch):
    monkeypatch.setattr(lsr, "collect_diff", lambda *a, **k: "diff --git a b\n+x")

    def _down(*a, **k):
        raise RuntimeError("local model endpoint failed (connection refused)")

    monkeypatch.setattr(lsr, "call_endpoint", _down)
    rc = lsr.main(["--repo", str(_ROOT)])
    assert rc == lsr.EXIT_CANNOT_REVIEW
    assert rc != lsr.EXIT_CLEAN


def test_git_failure_exits_CANNOT_REVIEW(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("git diff failed: not a repository")

    monkeypatch.setattr(lsr, "collect_diff", _boom)
    assert lsr.main(["--repo", str(_ROOT)]) == lsr.EXIT_CANNOT_REVIEW


def test_findings_exit_nonzero(monkeypatch):
    monkeypatch.setattr(lsr, "collect_diff", lambda *a, **k: "diff --git a b\n+x")
    monkeypatch.setattr(
        lsr, "call_endpoint",
        lambda *a, **k: "CRITICAL | a.py | hardcoded key | grants access")
    assert lsr.main(["--repo", str(_ROOT)]) == lsr.EXIT_FINDINGS


def test_clean_review_exits_zero(monkeypatch):
    monkeypatch.setattr(lsr, "collect_diff", lambda *a, **k: "diff --git a b\n+x")
    monkeypatch.setattr(lsr, "call_endpoint", lambda *a, **k: "NONE")
    assert lsr.main(["--repo", str(_ROOT)]) == lsr.EXIT_CLEAN


# --------------------------------------------------------------------------
# the self-test is the anti-vacuous guard; it must fail when nothing is found
# --------------------------------------------------------------------------

def test_self_test_FAILS_when_the_reviewer_finds_nothing(monkeypatch):
    """A reviewer that misses three planted vulnerabilities is broken.

    Without this, --self-test would print PASSED on a model that answers
    NONE to everything, which is exactly a check that cannot fail.
    """
    monkeypatch.setattr(lsr, "call_endpoint", lambda *a, **k: "NONE")
    assert lsr._self_test(lsr.DEFAULT_BASE_URL,
                          lsr.DEFAULT_MODEL) == lsr.EXIT_CANNOT_REVIEW


def test_self_test_passes_when_the_canary_is_caught(monkeypatch):
    monkeypatch.setattr(
        lsr, "call_endpoint",
        lambda *a, **k: "CRITICAL | payments.py | hardcoded secret | access")
    assert lsr._self_test(lsr.DEFAULT_BASE_URL,
                          lsr.DEFAULT_MODEL) == lsr.EXIT_CLEAN


def test_canary_diff_actually_contains_the_three_planted_defects():
    """If the canary is edited into harmlessness the self-test goes vacuous.

    The three needles below are SUBSTRING LITERALS compared against a string
    constant. Nothing is executed, imported or written; `eval(` here is four
    characters of text, not a call. Pattern scanners flag these lines, which
    is the expected cost of pinning that the canary still carries teeth.
    """
    d = lsr._CANARY_DIFF
    assert "shell=True" in d
    assert "eval(" in d
    assert "sk_live_" in d


# --------------------------------------------------------------------------
# the format retry: recovers from prose, but is CAPPED
# --------------------------------------------------------------------------

def test_prose_first_reply_is_retried_once_and_recovers(monkeypatch):
    replies = iter([
        "This commit introduces a new script for local security reviews.",
        "HIGH | a.py | shell=True with user input | command injection",
    ])
    calls = []

    def _fake(payload, *a, **k):
        calls.append(payload["messages"][-1]["content"])
        return next(replies)

    monkeypatch.setattr(lsr, "call_endpoint", _fake)
    assert len(lsr.review("d", lsr.DEFAULT_BASE_URL, lsr.DEFAULT_MODEL)) == 1
    assert len(calls) == 2
    assert "prose" in calls[1]          # the corrective instruction was sent
    assert "prose" not in calls[0]      # and was NOT sent the first time


def test_retry_is_capped_so_it_cannot_loop(monkeypatch):
    """Two prose replies must fail, not spin until something parses."""
    calls = []

    def _prose(payload, *a, **k):
        calls.append(1)
        return "Here is a friendly summary of the changes."

    monkeypatch.setattr(lsr, "call_endpoint", _prose)
    with pytest.raises(ValueError):
        lsr.review("d", lsr.DEFAULT_BASE_URL, lsr.DEFAULT_MODEL)
    assert len(calls) == 2, "exactly one retry, never more"


def test_retries_zero_means_a_single_attempt(monkeypatch):
    calls = []
    monkeypatch.setattr(lsr, "call_endpoint",
                        lambda *a, **k: (calls.append(1), "prose")[1])
    with pytest.raises(ValueError):
        lsr.review("d", lsr.DEFAULT_BASE_URL, lsr.DEFAULT_MODEL, retries=0)
    assert len(calls) == 1


# --------------------------------------------------------------------------
# per-file chunking: the guard against a SILENT context overflow
# --------------------------------------------------------------------------

_TWO_FILE_DIFF = (
    "diff --git a/one.py b/one.py\n--- a/one.py\n+++ b/one.py\n@@ -1 +1 @@\n+a\n"
    "diff --git a/two.py b/two.py\n--- a/two.py\n+++ b/two.py\n@@ -1 +1 @@\n+b\n")


def test_diff_is_split_one_chunk_per_file():
    chunks = lsr.split_diff(_TWO_FILE_DIFF)
    assert len(chunks) == 2
    assert chunks[0].startswith("diff --git a/one.py")
    assert chunks[1].startswith("diff --git a/two.py")


def test_empty_diff_splits_to_nothing():
    assert lsr.split_diff("") == []
    assert lsr.split_diff("   \n ") == []


def test_a_diff_with_no_git_header_is_still_reviewed_as_one_chunk():
    """Never drop content just because it is not shaped like a git diff."""
    assert lsr.split_diff("just some text") == ["just some text"]


def test_every_file_is_sent_in_its_own_request(monkeypatch):
    seen = []
    monkeypatch.setattr(lsr, "call_endpoint",
                        lambda p, *a, **k: (seen.append(p["messages"][-1]["content"]), "NONE")[1])
    lsr.review(_TWO_FILE_DIFF, lsr.DEFAULT_BASE_URL, lsr.DEFAULT_MODEL)
    assert len(seen) == 2, "each file gets its own prompt, so none can overflow"
    assert "one.py" in seen[0] and "two.py" not in seen[0]


def test_findings_from_all_files_are_aggregated(monkeypatch):
    monkeypatch.setattr(
        lsr, "call_endpoint",
        lambda p, *a, **k: "HIGH | x.py | hardcoded key | grants access")
    assert len(lsr.review(_TWO_FILE_DIFF, lsr.DEFAULT_BASE_URL,
                          lsr.DEFAULT_MODEL)) == 2


def test_one_unreviewable_file_fails_the_WHOLE_review(monkeypatch):
    """A partial sweep must never be reported as a clean one.

    If file 1 reviews clean and file 2 cannot be reviewed, returning []
    would print "no findings" for a commit half of which was never read.
    """
    calls = {"n": 0}

    def _second_fails(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return "NONE"
        raise RuntimeError("endpoint died mid-sweep")

    monkeypatch.setattr(lsr, "call_endpoint", _second_fails)
    with pytest.raises(RuntimeError):
        lsr.review(_TWO_FILE_DIFF, lsr.DEFAULT_BASE_URL, lsr.DEFAULT_MODEL)


def test_chunk_limit_fits_the_measured_server_context():
    """CHUNK_LIMIT must stay inside the 4096-token server window.

    Budget: 4096 total - 1400 generated - ~250 system = ~2450 tokens for the
    diff. At a worst-case 3 chars/token that is ~7350 chars. If someone raises
    CHUNK_LIMIT past that without also raising OLLAMA_CONTEXT_LENGTH, prompts
    start being context-shifted and the reviewer goes silently blind.
    """
    worst_case_tokens = lsr.CHUNK_LIMIT / 3
    assert worst_case_tokens + 1400 + 250 < 4096


# --------------------------------------------------------------------------
# truncation must be announced, never silent
# --------------------------------------------------------------------------

def test_oversized_diff_is_truncated_and_says_so(monkeypatch):
    seen = {}

    def _cap(payload, *a, **k):
        seen["prompt"] = payload["messages"][-1]["content"]
        return "NONE"

    monkeypatch.setattr(lsr, "call_endpoint", _cap)
    oversized = "diff --git a/x b/x" + "\n" + "x" * (lsr.CHUNK_LIMIT + 5000)
    lsr.review(oversized, lsr.DEFAULT_BASE_URL, lsr.DEFAULT_MODEL)
    assert "PARTIAL" in seen["prompt"]
