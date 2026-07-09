"""Regression for SD-007 (audit chain break at a runner restart).

Mechanism: an AuditTrail constructed EARLY but writing LATE (runner boot)
reused seq/prev captured before a concurrently-running QA script appended
its records - the chain then forked (seq regressed 7444 -> 7306 in the
live file). Two defenses under test:

  1. AuditTrail re-adopts the file tail at its FIRST write, so the
     construction-to-first-write window can no longer produce stale
     seq/prev.
  2. configure_audit() lets QA harnesses (smoke/assurance/trials/pytest)
     point the process singleton away from the production trail entirely.
"""

import core.audit as audit_mod
from core.audit import AuditTrail, configure_audit, get_audit


def test_late_first_writer_resyncs_to_tail(tmp_path):
    p = tmp_path / "audit.jsonl"
    early = AuditTrail(p)                 # constructed against empty file
    other = AuditTrail(p)
    for i in range(3):
        assert other.log("qa", "FT-010", f"other {i}", {"i": i}) == i + 1
    # early instance writes only now: must continue at seq 4, chained to
    # other's last hash - NOT reuse seq 1 with a genesis prev
    assert early.log("qa", "FT-010", "late writer", {}) == 4
    r = early.verify()
    assert r["ok"] is True
    assert r["records"] == 4


def test_resync_never_regresses_seq(tmp_path):
    p = tmp_path / "audit.jsonl"
    a = AuditTrail(p)
    for i in range(5):
        a.log("qa", "FT-010", f"a {i}", {})
    b = AuditTrail(p)                     # tail already at seq 5
    assert b.log("qa", "FT-010", "b", {}) == 6
    assert b.verify()["ok"] is True


def test_configure_audit_repoints_singleton(tmp_path):
    before = audit_mod._AUDIT
    try:
        p = tmp_path / "qa_audit.jsonl"
        t = configure_audit(p)
        assert get_audit() is t
        t.log("qa", "FT-010", "isolated", {})
        assert p.exists()
        assert t.verify()["ok"] is True
    finally:
        audit_mod._AUDIT = before         # restore for the other tests
