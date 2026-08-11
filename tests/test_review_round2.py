"""Regressions from the second line-by-line review round.

1. FaultManager: a re-latch must ESCALATE the record's severity, or
   clear_fault's "no critical faults remain" check downgrades HALTED while
   the critical condition persists.
2. RiskFirewall: duplicate rejects must reach the hash-chained audit trail
   (was the only disposition that skipped it, violating its own R4 rule).
3. PostmortemEngine: theses registered for orders that never fill must be
   expired, not accumulate in _open (and every snapshot) forever.
"""
import core.audit
from core.audit import AuditTrail
from core.fault import FaultManager, OpState, Severity
from execution.risk_firewall import RiskFirewall
from ml.postmortem import PostmortemEngine, TradeThesis


def _isolate_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(core.audit, "_AUDIT",
                        AuditTrail(str(tmp_path / "audit.jsonl")))


# --- 1: fault severity escalation -----------------------------------------
def test_relatch_escalates_severity_and_halt_sticks(tmp_path, monkeypatch):
    _isolate_audit(tmp_path, monkeypatch)
    fm = FaultManager()
    fm.arm()
    fm.latch("net", Severity.WARNING, "flaky feed")
    fm.latch("other", Severity.FAULT, "unrelated")
    fm.latch("net", Severity.CRITICAL, "feed dead")     # escalation
    assert fm.state is OpState.HALTED
    # clearing the unrelated fault must NOT downgrade: "net" is now CRITICAL
    fm.clear_fault("other")
    assert fm.state is OpState.HALTED
    assert fm.status()["faults"]["net"]["severity"] == "CRITICAL"
    # clearing the real critical finally re-arms
    fm.clear_fault("net")
    assert fm.state is OpState.ARMED


def test_relatch_never_softens_severity(tmp_path, monkeypatch):
    _isolate_audit(tmp_path, monkeypatch)
    fm = FaultManager()
    fm.arm()
    fm.latch("x", Severity.CRITICAL, "bad")
    fm.latch("x", Severity.WARNING, "recheck says milder")
    assert fm.status()["faults"]["x"]["severity"] == "CRITICAL"
    assert fm.state is OpState.HALTED


# --- 2: firewall dupe rejects reach the audit chain -------------------------
def test_duplicate_reject_writes_audit_record(tmp_path, monkeypatch):
    _isolate_audit(tmp_path, monkeypatch)
    fw = RiskFirewall({"dupe_window_sec": 5.0})

    def send(now: float):
        return fw.check(pair="ETHUSD", side="buy", purpose="entry",
                        price=2000.0, size=0.1, ref_price=2000.0,
                        equity=10_000.0, now=now)

    assert send(1.0).allowed
    v = send(2.0)                                    # inside dupe window
    assert not v.allowed and any("FW-030" in r for r in v.reasons)
    chain = core.audit._AUDIT.verify()
    assert chain["ok"] is True
    text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "FW-030" in text                          # dupe reached the chain


# --- 3: orphaned postmortem theses expire -----------------------------------
def _thesis(pid, ts):
    return TradeThesis(position_id=pid, asset="ETH", symbol="ETH/USD",
                       direction="long", entry_ts=ts, p_win=0.6,
                       expected_ret_pct=0.2, expected_cost_bps=40.0,
                       stop_pct=2.0, target_pct=2.2, entry_regime="range",
                       entry_liq="liquid", narrative_label="neutral",
                       fair_value=2000.0, quote_price=1999.0,
                       model_scored=False)


def test_unfilled_thesis_expires_filled_one_survives(tmp_path):
    eng = PostmortemEngine({"paths_path": str(tmp_path / "trade_paths.csv"),
                            "report_dir": str(tmp_path / "pm"),
                            "summary_path": str(tmp_path / "pm.csv")})
    eng.register_entry(_thesis("orphan", ts=0.0))          # never fills
    eng.register_entry(_thesis("livepos", ts=0.0))
    eng.note_fill("livepos", 1999.0)                        # real fill
    eng.poll(now=eng.ORPHAN_MAX_AGE_S + 1.0)
    assert "orphan" not in eng._open                        # expired
    assert "livepos" in eng._open                           # kept


def test_fresh_unfilled_thesis_not_expired(tmp_path):
    eng = PostmortemEngine({"paths_path": str(tmp_path / "trade_paths.csv"),
                            "report_dir": str(tmp_path / "pm"),
                            "summary_path": str(tmp_path / "pm.csv")})
    eng.register_entry(_thesis("pending", ts=1000.0))
    eng.poll(now=1000.0 + 60.0)                             # only a minute old
    assert "pending" in eng._open
