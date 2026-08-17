"""
tests/test_code_stats.py — the central reason-code frequency ledger.

Every registered code (PT-/SZ-/RP-/FW-/…) now bumps a cumulative counter via
tag(), so the operator can finally see HOW OFTEN each reject/veto/fault fires,
not just the current disposition. Regression for the "no central {code: count}"
gap surfaced by the fault audit.
"""
from core import code_stats
from core.codes import Code, tag


def test_bump_and_snapshot():
    code_stats.reset()
    code_stats.bump("SZ-030")
    code_stats.bump("SZ-030")
    code_stats.bump("PT-040")
    snap = code_stats.snapshot()
    assert snap["SZ-030"] == 2 and snap["PT-040"] == 1


def test_tag_bumps_the_ledger():
    code_stats.reset()
    tag(Code.SZ_KELLY_ZERO, "kelly 0")
    tag(Code.SZ_KELLY_ZERO, "kelly 0 again")
    tag(Code.PT_EV_NEGATIVE, "ev fail")
    assert code_stats.snapshot()[Code.SZ_KELLY_ZERO.value] == 2
    assert code_stats.snapshot()[Code.PT_EV_NEGATIVE.value] == 1


def test_by_prefix_aggregates():
    code_stats.reset()
    for _ in range(3):
        tag(Code.SZ_KELLY_ZERO, "x")
    tag(Code.SZ_PWIN_BAR, "y")            # another SZ family member
    tag(Code.FW_RATE_LIMIT, "z")
    agg = code_stats.by_prefix()
    assert agg["SZ"] == 4 and agg["FW"] == 1


def test_top_orders_by_frequency():
    code_stats.reset()
    for _ in range(5):
        code_stats.bump("SZ-030")
    for _ in range(2):
        code_stats.bump("PT-040")
    assert list(code_stats.top(1)) == ["SZ-030"]


def test_bump_never_raises():
    code_stats.reset()
    code_stats.bump("anything")           # must not raise
    assert code_stats.snapshot()["anything"] == 1


def test_tag_still_returns_canonical_string():
    assert tag(Code.OM_MARKET_REFUSED, "no market entry") == \
        "OM-011: no market entry"


# --------------------------------------------------------------------------
# The AUDIT frequency lane (2026-08-17). tag() was the only bump site, so
# audit-only emissions — ML-*, OM-000/OM-040 terminals, FT-*, RP-070/071/072,
# RC/RT, CG-000 — could NEVER appear in code_stats.by_prefix(): live status
# showed {FW,LT,CX,LB,TH,SZ,RP,PT,GL,CV} while audit.jsonl carried
# ML-070/OM-000 the same day, and the exported liquiditybot_code_count lied
# about ML/OM forever. AuditTrail.log() now bumps too, with two guards so a
# both-lanes call site still counts each emission exactly once.
# --------------------------------------------------------------------------
def _trail(tmp_path):
    from core.audit import AuditTrail
    return AuditTrail(str(tmp_path / "audit.jsonl"), fsync=False)


def test_audit_only_emission_reaches_by_prefix(tmp_path):
    """The gap itself: an ML-family audit record with a plain (un-tagged)
    msg must land in the tally — this is what put ML/OM on the glass."""
    code_stats.reset()
    at = _trail(tmp_path)
    seq = at.log("ml_governor", Code.ML_DEPLOY, "challenger deployed", {})
    assert seq == 1
    at.log("order_manager", Code.OM_TIMEOUT_CANCEL,
           "abc buy BTC/USD terminal=expired fill_ratio=0.00 (ttl)", {})
    snap = code_stats.snapshot()
    assert snap[Code.ML_DEPLOY.value] == 1
    assert snap[Code.OM_TIMEOUT_CANCEL.value] == 1
    agg = code_stats.by_prefix()
    assert agg["ML"] == 1 and agg["OM"] == 1


def test_tag_idiom_both_lanes_call_site_counts_once(tmp_path):
    """The documented idiom — log(src, code, tag(code, detail)) — already
    bumped via tag(); the audit lane must detect the 'CODE: ' msg prefix
    and not re-count the same emission."""
    code_stats.reset()
    at = _trail(tmp_path)
    msg = tag(Code.LB_ADD_PLACED, "BTC: rung 0 - $25.00 @ 60,000")
    at.log("long_book", Code.LB_ADD_PLACED, msg, {"asset": "BTC"})
    assert code_stats.snapshot()[Code.LB_ADD_PLACED.value] == 1


def test_counted_true_suppresses_the_audit_bump(tmp_path):
    """risk_firewall's reject/clamp sites tag() the code into a DIFFERENT
    string (reasons/notes) and audit a summary msg — they pass counted=True
    so the emission still counts exactly once."""
    code_stats.reset()
    at = _trail(tmp_path)
    tag(Code.FW_DUPLICATE, "identical order 1.2s ago")   # the reasons lane
    at.log("firewall", "FW-030",
           "BTC/USD buy entry px=1.0 sz=1.0 :: FW-030: identical order",
           {"seq": 7}, counted=True)
    assert code_stats.snapshot()[Code.FW_DUPLICATE.value] == 1


def test_firewall_duplicate_reject_counts_once_end_to_end(tmp_path):
    """INJECTION, not inference: run the real firewall duplicate-reject
    path (tag()'d reasons + audited summary) and assert FW-030 counts
    exactly once per rejected emission."""
    import core.audit as audit_mod
    from core.audit import configure_audit
    from execution.risk_firewall import RiskFirewall
    prior = audit_mod._AUDIT      # conftest's session-isolated trail
    configure_audit(str(tmp_path / "audit.jsonl"), fsync=False)
    try:
        fw = RiskFirewall({"dupe_window_sec": 60.0})
        kw = dict(pair="BTC/USD", side="buy", purpose="entry", price=100.0,
                  size=1.0, ref_price=100.0, equity=10_000.0, now=1000.0)
        assert fw.check(**kw).allowed          # first submit accepted
        code_stats.reset()
        v = fw.check(**{**kw, "now": 1001.0})  # identical inside the window
        assert not v.allowed
        assert any("FW-030" in r for r in v.reasons)
        assert code_stats.snapshot().get(Code.FW_DUPLICATE.value) == 1, \
            "duplicate reject must count ONCE (tag lane), not twice " \
            "(tag + audit)"
    finally:
        audit_mod._AUDIT = prior


def test_non_canonical_audit_codes_never_pollute_the_tally(tmp_path):
    """Freeform/src-like code strings must not mint fake prefixes in
    by_prefix() — only canonical 'XX-NNN' values are counted."""
    code_stats.reset()
    at = _trail(tmp_path)
    at.log("startup", "not-a-code", "boot", {})
    at.log("startup", "SDX-0001", "wrong shape", {})
    assert code_stats.snapshot() == {}
