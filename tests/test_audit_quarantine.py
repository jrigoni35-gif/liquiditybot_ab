"""The quarantine classifier must not lose records, and must not over-attribute.

scripts/audit_quarantine.py separates synthetic QA sessions from the live bot's
in the shared hash-chained trail. Two ways it could be worthless:

  * it drops records (a filter that silently loses evidence is worse than none)
  * it over-attributes to SYNTHETIC via the forward-leak - the live bot emits
    CG-000 once at boot, so a QA burst's CG-000 would otherwise capture every
    later live record until the next reboot.

The second is the interesting one and it is pinned by INJECTION: a fixture that
reproduces the exact 2026-09-10 shape (live session, QA burst mid-stream, live
records afterwards) and asserts the live records come back to PRODUCTION. Under
a classifier without the idle-close rule that assertion fails, which is what
makes these tests non-vacuous.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_quarantine import (  # noqa: E402
    SESSION_START, classify, production_capital, seams)

PROD = 800.0
SYN = 10000.0


def _rec(code, ts, capital=None, seq=0, prev="x", h="y"):
    r = {"code": code, "ts": ts, "seq": seq, "prev": prev, "h": h}
    if capital is not None:
        r["data"] = {"starting_capital_usd": capital}
    return r


def _labels(recs, idle=300.0):
    return [lab for lab, _ in classify(recs, PROD, idle)]


# ---------------------------------------------------------------------------
# conservation
# ---------------------------------------------------------------------------

def test_every_record_gets_exactly_one_label():
    recs = [_rec(SESSION_START, 100.0, PROD),
            _rec("LB-010", 101.0), _rec("CX-030", 102.0)]
    out = classify(recs, PROD)
    assert len(out) == len(recs)
    assert all(lab in ("PRODUCTION", "SYNTHETIC", "UNCLASSIFIED")
               for lab, _ in out)


def test_records_before_any_session_start_are_unclassified_not_guessed():
    """Silently assigning them to production would inflate the honest count."""
    recs = [_rec("LB-010", 100.0), _rec(SESSION_START, 101.0, PROD)]
    assert _labels(recs)[0] == "UNCLASSIFIED"


# ---------------------------------------------------------------------------
# the basic split
# ---------------------------------------------------------------------------

def test_the_shipped_capital_is_production_and_anything_else_is_not():
    recs = [_rec(SESSION_START, 100.0, PROD), _rec("LB-010", 101.0),
            _rec(SESSION_START, 102.0, SYN), _rec("OM-020", 102.5)]
    assert _labels(recs) == ["PRODUCTION", "PRODUCTION",
                             "SYNTHETIC", "SYNTHETIC"]


def test_production_capital_is_read_from_the_config_not_hardcoded(tmp_path):
    """If the operator re-capitalises, the tool must follow. A hardcoded 800
    would relabel every subsequent live session as synthetic."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(
        {"capital_management": {"starting_capital_usd": 1234.5}}),
        encoding="utf-8")
    assert production_capital(cfg) == 1234.5


# ---------------------------------------------------------------------------
# THE forward-leak - the defect this rule exists for
# ---------------------------------------------------------------------------

def _leak_fixture():
    """The measured 2026-09-10 shape: live session, a ~1s QA burst at t+1000,
    then live records resuming well after it."""
    return [
        _rec(SESSION_START, 0.0, PROD),      # bot boots
        _rec("LB-010", 10.0),                # live
        _rec(SESSION_START, 1000.0, SYN),    # QA burst starts
        _rec("OM-020", 1000.4),              # QA
        _rec("FW-050", 1001.0),              # QA
        _rec("LB-010", 5000.0),              # live again, long after
        _rec("CX-030", 5180.0),              # live
    ]


def test_live_records_after_a_qa_burst_are_not_stolen_by_it():
    labels = _labels(_leak_fixture())
    assert labels == ["PRODUCTION", "PRODUCTION",
                      "SYNTHETIC", "SYNTHETIC", "SYNTHETIC",
                      "PRODUCTION", "PRODUCTION"], labels


def test_the_burst_itself_is_still_quarantined():
    """The reclaim must not over-correct and hand the QA rows back too."""
    labels = _labels(_leak_fixture())
    assert labels[2:5] == ["SYNTHETIC"] * 3


def test_without_the_idle_rule_the_leak_reappears():
    """CONTROL. A huge idle threshold disables the reclaim; the live tail is
    then mislabelled. If this ever passes, the rule above is doing nothing and
    its test is vacuous."""
    labels = _labels(_leak_fixture(), idle=10 ** 9)
    assert labels[-2:] == ["SYNTHETIC", "SYNTHETIC"]


def test_reclaimed_records_are_reported_as_INFERRED():
    """The share resting on inference must be visible - reporting only the
    transition point understated it by two orders of magnitude on the real
    trail (86 vs 16,429)."""
    out = classify(_leak_fixture(), PROD)
    reasons = [reason for _, reason in out]
    assert reasons[-2:] == ["inferred", "inferred"]
    assert reasons[:2] == ["session", "session"]


def test_a_real_session_start_clears_the_inferred_flag():
    """Once a CG-000 is READ, the label is no longer an inference."""
    recs = _leak_fixture() + [_rec(SESSION_START, 6000.0, PROD),
                              _rec("LB-010", 6001.0)]
    out = classify(recs, PROD)
    assert out[-1] == ("PRODUCTION", "session")


# ---------------------------------------------------------------------------
# seams
# ---------------------------------------------------------------------------

def test_seams_mark_every_class_transition_with_both_sides():
    recs = _leak_fixture()
    marks = seams(recs, classify(recs, PROD))
    assert [(m["from"], m["to"]) for m in marks] == [
        ("PRODUCTION", "SYNTHETIC"), ("SYNTHETIC", "PRODUCTION")]
    assert all("seq_before" in m and "seq_after" in m for m in marks)


def test_seams_record_whether_the_hash_chain_links_across_them():
    recs = [_rec(SESSION_START, 0.0, PROD, prev="a", h="b"),
            _rec(SESSION_START, 1.0, SYN, prev="ZZZ", h="c")]
    marks = seams(recs, classify(recs, PROD))
    assert len(marks) == 1
    assert marks[0]["chain_intact"] is False


def test_no_seams_when_one_writer_owns_the_whole_trail():
    recs = [_rec(SESSION_START, 0.0, PROD)] + [
        _rec("LB-010", float(i)) for i in range(1, 6)]
    assert seams(recs, classify(recs, PROD)) == []


# ---------------------------------------------------------------------------
# it must survive the real file's shape
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not (REPO_ROOT / "outputs" / "audit.jsonl").is_file(),
                    reason="no production trail on this machine")
def test_the_real_trail_classifies_without_losing_records():
    trail = REPO_ROOT / "outputs" / "audit.jsonl"
    recs = []
    with open(trail, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                recs.append({"_unparseable": True})
    out = classify(recs, production_capital(REPO_ROOT / "config.json"))
    assert len(out) == len(recs)
    assert sum(1 for lab, _ in out if lab == "UNCLASSIFIED") == 0, (
        "the real trail opens with a session start; unclassified records mean "
        "the CG-000 payload shape changed and this tool has gone blind")
