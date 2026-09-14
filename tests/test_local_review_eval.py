"""Pins for scripts/local_review_eval.py.

The thing under test is the SCORE, not any model. A benchmark whose metric can
be gamed by a degenerate strategy is worse than no benchmark, because it
produces a confident number. The two degenerate strategies are:

  "always CRITICAL"  -> perfect recall, and must show 100% false positives
  "always NONE"      -> zero false positives, and must show 0% recall

Both are pinned below. If either ever scores well on the pair, the metric is
broken and any model ranking built on it is void.

No network: `review` is stubbed everywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import local_review_eval as ev  # noqa: E402


# --------------------------------------------------------------------------
# the corpus must keep both arms, or the score is meaningless
# --------------------------------------------------------------------------

def test_corpus_has_planted_cases_and_controls():
    assert len(ev.POSITIVES) >= 8
    assert len(ev.CONTROLS) >= 4


def test_every_positive_has_needles_and_every_control_has_none():
    assert all(c.needles and not c.is_control for c in ev.POSITIVES)
    assert all(not c.needles and c.is_control for c in ev.CONTROLS)


def test_the_safe_lookalike_controls_exist():
    """These separate reading the code from matching its vocabulary.

    A parameterised query, a list-form subprocess call and ast.literal_eval
    all contain the scary words and are correct. Lose them and the false
    positive rate stops meaning anything.
    """
    names = {c.name for c in ev.CONTROLS}
    assert {"SAFE-parameterised-sql", "SAFE-subprocess-list",
            "SAFE-literal-eval"} <= names


def test_safe_lookalikes_really_do_contain_the_dangerous_vocabulary():
    blob = " ".join(c.diff for c in ev.CONTROLS if c.name.startswith("SAFE"))
    for word in ("execute(", "subprocess", "eval"):
        assert word in blob, f"{word!r} missing - the control lost its teeth"


def test_planted_case_diffs_are_wellformed_unified_diffs():
    for c in ev.POSITIVES + ev.CONTROLS:
        assert c.diff.startswith("diff --git "), c.name
        assert "@@" in c.diff, c.name


# --------------------------------------------------------------------------
# _hit
# --------------------------------------------------------------------------

def test_hit_is_case_insensitive_substring_match():
    assert ev._hit(["CRITICAL | a.py | Hardcoded Secret | x"], ["hardcod"])
    assert not ev._hit(["CRITICAL | a.py | something else | x"], ["hardcod"])


def test_hit_is_false_when_there_are_no_findings():
    assert not ev._hit([], ["anything"])


# --------------------------------------------------------------------------
# THE GAMEABILITY PINS
# --------------------------------------------------------------------------

def _run_with(monkeypatch, reply_findings):
    monkeypatch.setattr(ev, "review", lambda *a, **k: list(reply_findings))
    monkeypatch.setattr(ev.time, "sleep", lambda *_: None)
    return ev.run_model("stub", "http://x", ev.POSITIVES + ev.CONTROLS,
                        pause=0.0, timeout=1.0)


def test_always_critical_scores_perfect_recall_AND_total_false_positives(
        monkeypatch):
    """The shouting model must be visibly bad on the second number."""
    shout = ["CRITICAL | any.py | hardcod secret inject eval pickle "
             "traversal tls log except | bad"]
    r = _run_with(monkeypatch, shout)
    assert r["recall_pct"] == 100.0
    assert r["false_pos_pct"] == 100.0, (
        "a model that flags every control must show a 100% false positive "
        "rate, or the metric is gameable")


def test_always_none_scores_zero_recall_and_zero_false_positives(monkeypatch):
    r = _run_with(monkeypatch, [])
    assert r["recall_pct"] == 0.0
    assert r["false_pos_pct"] == 0.0


def test_a_discriminating_model_beats_both_degenerates(monkeypatch):
    """Sanity: the score can express 'good', not only the two failure modes."""
    def _smart(diff, *a, **k):
        if "literal_eval" in diff or "?" in diff or '["rm"' in diff:
            return []
        if "README" in diff or "subtotal" in diff:
            return []
        return ["CRITICAL | x.py | hardcod secret inject eval pickle "
                "traversal tls log except | bad"]

    monkeypatch.setattr(ev, "review", _smart)
    monkeypatch.setattr(ev.time, "sleep", lambda *_: None)
    r = ev.run_model("stub", "http://x", ev.POSITIVES + ev.CONTROLS, 0.0, 1.0)
    assert r["recall_pct"] == 100.0
    assert r["false_pos_pct"] == 0.0


# --------------------------------------------------------------------------
# errors must not silently become good scores
# --------------------------------------------------------------------------

def test_model_errors_are_counted_not_scored_as_clean(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("endpoint down")

    monkeypatch.setattr(ev, "review", _boom)
    monkeypatch.setattr(ev.time, "sleep", lambda *_: None)
    r = ev.run_model("stub", "http://x", ev.POSITIVES + ev.CONTROLS, 0.0, 1.0)
    assert r["errors"] == len(ev.POSITIVES) + len(ev.CONTROLS)
    # A run where NOTHING answered has UNDEFINED rates, not zero ones. None is
    # the honest value and "n/a" is what prints; a literal 0.0 here would read
    # as "measured, scored nothing", which is a different claim. This pin
    # caught the author asserting 0.0 and being wrong about his own contract.
    assert r["recall_pct"] is None
    assert r["false_pos_pct"] is None
    assert r["recall"] == "n/a" and r["false_pos"] == "n/a"
    # and it must never look fast: no latency sample comes from a failed call
    assert r["median_sec"] is None, (
        "a failed call is not a latency sample")
