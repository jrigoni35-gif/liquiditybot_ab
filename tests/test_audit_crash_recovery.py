"""tests/test_audit_crash_recovery.py — the audit trail must tell a CRASH
apart from TAMPER, and a bundle's audit seam must not cost a session's
learning.

Three guarantees:
  * verify() distinguishes a TORN TAIL (an incomplete final line from a crash
    mid-append — chain intact before it, benign) from a MID-CHAIN break (a
    record edited/removed/reordered with valid content still after it — the
    tamper signal). A crash on the last write must not read as tampering.
  * log() never raises into the disposition call site: a data payload that
    json.dumps chokes on drops the record (dropped++), it does NOT abort the
    order transition / firewall reject that was trying to audit itself.
  * session_import decouples learning from the audit chain: a mid-chain break
    QUARANTINES the audit trail but still imports signal_history.csv (which
    carries its own, already-verified sha256). --strict-audit restores the old
    hard refusal. A torn tail imports cleanly. This stops the newest learning
    bundle being discarded every boot over a benign restart seam.
"""
import json

from core.audit import AuditTrail, verify_chain
from core.codes import Code
from ml.history import HistoryStore

import scripts.session_export as sx
import scripts.session_import as si


# ==================== review-hardening (A2-F2/F3/F6, A3-F1) ==================
def test_tampered_final_record_is_not_laundered_as_torn_tail(tmp_path):
    # a COMPLETE final record whose hash is wrong is TAMPER, not a crash tail:
    # verify must report torn_tail=False so session_import quarantines it
    # instead of forgiving it as benign (review A2-F2).
    p = tmp_path / "a.jsonl"
    a = AuditTrail(str(p))
    for i in range(4):
        a.log("qa", Code.FW_FAULT_DEGRADED, f"rec {i}", {"i": i})
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[-1] = lines[-1].replace("rec 3", "rec HACKED")   # parseable, hash now wrong
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = verify_chain(str(p))
    assert r["ok"] is False and r["torn_tail"] is False    # tamper, not benign


def test_verify_chain_is_read_only(tmp_path):
    # verify_chain must NOT truncate a torn tail (only construction heals);
    # an external inspector can look without mutating the file.
    p = tmp_path / "a.jsonl"
    a = AuditTrail(str(p))
    for i in range(3):
        a.log("qa", Code.FW_FAULT_DEGRADED, f"rec {i}", {})
    with open(p, "a", encoding="utf-8") as f:
        f.write('{"seq": 4, "torn')                        # torn final line
    before = p.read_bytes()
    r = verify_chain(str(p))
    assert r["ok"] is False and r["torn_tail"] is True
    assert p.read_bytes() == before                        # untouched


def test_adopt_truncates_malformed_seq_without_raising(tmp_path):
    # a parseable final record with a non-int seq (null) must not TypeError out
    # of construction (log()'s never-raise contract) — it's truncated (A2-F6).
    p = tmp_path / "a.jsonl"
    a = AuditTrail(str(p))
    for i in range(3):
        a.log("qa", Code.FW_FAULT_DEGRADED, f"rec {i}", {})
    with open(p, "a", encoding="utf-8") as f:
        f.write('{"seq": null, "prev": "x", "h": "y"}\n')  # complete JSON, bad seq
    b = AuditTrail(str(p))                                  # must not raise
    assert b.tail_truncations == 1
    assert b.log("qa", Code.FW_FAULT_DEGRADED, "next", {}) == 4   # resumed clean
    assert b.verify()["ok"] is True


def test_missing_trailing_newline_is_repaired_not_concatenated(tmp_path):
    # a crash that drops only the final '\n' but keeps the record must be
    # repaired on adopt, so the next append doesn't concatenate into one line a
    # later adopt would truncate (destroying BOTH records) (A2-F3).
    p = tmp_path / "a.jsonl"
    a = AuditTrail(str(p))
    for i in range(3):
        a.log("qa", Code.FW_FAULT_DEGRADED, f"rec {i}", {})
    body = p.read_text(encoding="utf-8")
    p.write_text(body.rstrip("\n"), encoding="utf-8")       # drop the last newline
    b = AuditTrail(str(p))                                   # adopt -> repair newline
    assert b.log("qa", Code.FW_FAULT_DEGRADED, "next", {}) == 4
    # a fresh adopt sees 4 clean records, nothing concatenated/truncated
    c = AuditTrail(str(p))
    assert c.tail_truncations == 0 and c.verify()["ok"] is True
    assert c.verify()["records"] == 4


# ============================ verify() ======================================
def _seed_trail(path, n=5):
    t = AuditTrail(str(path))
    for i in range(n):
        t.log("qa", Code.FW_FAULT_DEGRADED, f"record {i}", {"i": i})
    return path.read_text(encoding="utf-8").splitlines()


def test_clean_chain_verifies(tmp_path):
    p = tmp_path / "a.jsonl"
    _seed_trail(p, 5)
    r = AuditTrail(str(p)).verify()
    assert r["ok"] and r["records"] == 5 and r["torn_tail"] is False


def test_adopt_truncates_torn_tail_and_resumes_cleanly(tmp_path):
    # a crash mid-append leaves an unparseable final line. Adopting the trail
    # must TRUNCATE it (not restart from genesis) so the next write chains onto
    # the last good record and the whole file re-verifies.
    p = tmp_path / "a.jsonl"
    _seed_trail(p, 3)
    with open(p, "a", encoding="utf-8") as f:
        f.write('{"seq": 4, "ts": 1.0, "prev": "abc", "msg": "torn')  # no newline, truncated
    a = AuditTrail(str(p))                    # __init__ -> _adopt_tail truncates
    assert a.tail_truncations == 1
    seq = a.log("qa", Code.FW_FAULT_DEGRADED, "after recovery", {})
    assert seq == 4                            # resumed at 3+1, no genesis reset
    r = a.verify()
    assert r["ok"] is True and r["records"] == 4    # clean, contiguous chain


def test_adopt_does_not_truncate_a_complete_but_tampered_record(tmp_path):
    # a COMPLETE final line that parses is never truncated - even if its hash
    # is wrong, that is tamper evidence verify() must keep, not silent recovery.
    p = tmp_path / "a.jsonl"
    lines = _seed_trail(p, 3)
    lines[-1] = lines[-1].replace("record 2", "record TAMPERED")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    a = AuditTrail(str(p))
    assert a.tail_truncations == 0             # parseable -> left in place
    assert a.verify()["ok"] is False           # tamper still visible


def test_torn_final_line_is_benign_not_tamper(tmp_path):
    # verify() is probed on the SAME instance (no re-construction) so the
    # heal-on-adopt truncation does not run first - this pins verify()'s own
    # torn-tail detection. (Heal-on-construct is covered separately below.)
    p = tmp_path / "a.jsonl"
    a = AuditTrail(str(p))
    for i in range(5):
        a.log("qa", Code.FW_FAULT_DEGRADED, f"record {i}", {"i": i})
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[-1] = lines[-1][:20]                       # crash mid-append
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = a.verify()
    assert r["ok"] is False                          # the file has a bad line
    assert r["torn_tail"] is True                    # ...but it's a crash tail
    assert r["records"] == 4 and r["first_break"] == 5


def test_mid_chain_edit_reads_as_tamper(tmp_path):
    p = tmp_path / "a.jsonl"
    lines = _seed_trail(p, 5)
    lines[2] = lines[2].replace("record 2", "record X")   # edit record 3 of 5
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = AuditTrail(str(p)).verify()
    assert r["ok"] is False and r["torn_tail"] is False   # real tamper
    assert r["first_break"] == 3


# ============================ log() never raises ============================
def test_malformed_payload_drops_record_not_raises(tmp_path):
    t = AuditTrail(str(tmp_path / "a.jsonl"))
    assert t.log("qa", Code.FW_FAULT_DEGRADED, "good", {"ok": 1}) == 1
    # a dict json cannot sort_keys (mixed int/str keys) -> TypeError inside
    # dumps. Must be swallowed: return 0, dropped++, seq not advanced.
    assert t.log("qa", Code.FW_FAULT_DEGRADED, "bad", {1: "a", "b": 2}) == 0
    assert t.dropped == 1
    # the trail is still coherent and the next good write continues at seq 2
    assert t.log("qa", Code.FW_FAULT_DEGRADED, "good2", {"ok": 2}) == 2
    assert AuditTrail(str(tmp_path / "a.jsonl")).verify()["ok"] is True


# ============================ session_import ================================
def _row(pid):
    header = HistoryStore("unused.csv")._header
    vals = []
    for col in header:
        vals.append({"position_id": pid, "asset": "ETH", "side": "long",
                     "label": "1", "source": "live"}.get(col, "0.0"))
    return ",".join(vals)


def _seed_outputs(root, pids, audit_records=4):
    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    header = HistoryStore(str(out / "signal_history.csv"))._header
    (out / "signal_history.csv").write_text(
        ",".join(header) + "\n" + "".join(_row(p) + "\n" for p in pids),
        encoding="utf-8")
    t = AuditTrail(str(out / "audit.jsonl"))
    for i in range(audit_records):
        t.log("qa", Code.FW_FAULT_DEGRADED, f"seed {i}", {"i": i})
    (out / "equity.csv").write_text("ts,equity,daily_pnl\n1,800.0,0.0\n",
                                    encoding="utf-8")
    (out / "session_digest.json").write_text('{"verdict": "ok"}',
                                              encoding="utf-8")
    return out


def _bundle_with_broken_audit(tmp_path, breaker):
    """Build a valid bundle, break its audit chain via breaker(lines)->lines,
    then re-stamp the manifest sha256 so the FILE-integrity gate passes and
    the run actually reaches the chain check."""
    out = _seed_outputs(tmp_path, ("p1", "p2"))
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    audit = dst / "audit.jsonl"
    lines = audit.read_text(encoding="utf-8").splitlines()
    audit.write_text("\n".join(breaker(lines)) + "\n", encoding="utf-8")
    mf = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    mf["files"]["audit.jsonl"]["sha256"] = sx._sha256(audit)
    (dst / "manifest.json").write_text(json.dumps(mf), encoding="utf-8")
    return dst


def _home(tmp_path):
    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    return home


def test_midchain_break_imports_learning_and_quarantines_audit(tmp_path):
    dst = _bundle_with_broken_audit(
        tmp_path, lambda ls: ls[:1] + [ls[1].replace("seed 1", "seed X")] + ls[2:])
    home = _home(tmp_path)
    rc = si.run(str(dst), str(home), apply=True)          # default (lenient)
    assert rc == 0, "a mid-chain audit break must NOT discard the bundle"
    # learning rows imported despite the broken audit trail
    rows = [ln for ln in (home / "signal_history.csv")
            .read_text(encoding="utf-8").splitlines()[1:] if ln.strip()]
    assert len(rows) == 2
    # audit trail filed under the QUARANTINED name, never as a clean chain
    rec_dir = home / "imported_sessions" / "qa"
    assert (rec_dir / "audit.jsonl.QUARANTINED").exists()
    assert not (rec_dir / "audit.jsonl").exists()


def test_strict_audit_still_refuses_a_broken_chain(tmp_path):
    dst = _bundle_with_broken_audit(
        tmp_path, lambda ls: ls[:1] + [ls[1].replace("seed 1", "seed X")] + ls[2:])
    home = _home(tmp_path)
    rc = si.run(str(dst), str(home), apply=True, strict_audit=True)
    assert rc == 2, "--strict-audit must hard-refuse a broken audit chain"
    assert not (home / "signal_history.csv").exists()     # nothing imported


def test_torn_tail_bundle_imports_without_quarantine(tmp_path):
    dst = _bundle_with_broken_audit(
        tmp_path, lambda ls: ls[:-1] + [ls[-1][:15]])     # crash on last append
    home = _home(tmp_path)
    rc = si.run(str(dst), str(home), apply=True)
    assert rc == 0
    rec_dir = home / "imported_sessions" / "qa"
    # a benign torn tail is filed under its normal name (not quarantined)
    assert (rec_dir / "audit.jsonl").exists()
    assert not (rec_dir / "audit.jsonl.QUARANTINED").exists()


def test_strict_audit_refuses_a_torn_tail_too(tmp_path):
    # --strict-audit contract is "refuse ANY audit-chain break" — a torn tail
    # is a break, so strict must refuse it (review A3-F1: it used to slip past
    # because the torn-tail branch short-circuited before the strict check).
    dst = _bundle_with_broken_audit(
        tmp_path, lambda ls: ls[:-1] + [ls[-1][:15]])     # torn final line
    rc = si.run(str(dst), str(_home(tmp_path)), apply=True, strict_audit=True)
    assert rc == 2, "--strict-audit must refuse a torn-tail break"


def test_sha256_tamper_still_hard_refuses(tmp_path):
    # the FILE-integrity gate is unchanged: content tamper without re-stamping
    # the manifest still refuses, chain-decoupling does not weaken it
    out = _seed_outputs(tmp_path, ("p1", "p2"))
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    hist = dst / "signal_history.csv"
    hist.write_text(hist.read_text(encoding="utf-8").replace("ETH", "BTC"),
                    encoding="utf-8")
    assert si.run(str(dst), str(_home(tmp_path)), apply=True) == 2
