"""Operator weekly loss-budget re-anchor (2026-08-08 live incident).

WHY THIS COMMAND EXISTS: the loss budget measures from EQUITY ANCHORS
(risk/protocols.py spent_fracs), and the anchors are persisted, so
neither a restart nor any existing control verb can clear bug-
attributable consumption. Live case: the ADA hedge-churn class (fixed
in 5c111962/cf454d5e/FW-070) manufactured ~$303 of fee losses inside
ISO week 2026-W32; weekly_budget_used_frac read 1.0906 and taper_mult
0.0 - every entry blocked through the weekend for losses a since-fixed
bug created. Without the bug the week was net positive.

THE PROPER SHAPE (operator: "do it properly"): a ControlChannel verb,
refused without an explicit reason, audited with a registered code
(RP-042), touching ONLY the anchor - never weekly_pnl, never pools,
never learning data. The natural ISO rollover keeps working afterward.
Deliberately NOT exposed over REST (same posture as arm_live/stop:
risk-loosening verbs stay off the browser-reachable surface).
"""
import api.rest_server as rest
import core.audit
from core.audit import AuditTrail
from risk.protocols import RiskProtocolStack
from runner import BotRunner


def _stack() -> RiskProtocolStack:
    return RiskProtocolStack({"enabled": True,
                              "budget": {"enabled": True,
                                         "daily_loss_budget_pct": 2.5,
                                         "weekly_loss_budget_pct": 6.0}})


# ---------------------------------------------------------------- protocols
def test_reanchor_clears_bug_consumed_week_only():
    rp = _stack()
    rp.observe(5000.0, now=1_786_000_000.0)          # week anchors at 5000
    day0, week0 = rp.spent_fracs(4700.0)             # -6% -> week fully spent
    assert week0 >= 1.0
    assert rp.reanchor_week(4700.0, now=1_786_000_000.0) is True
    day1, week1 = rp.spent_fracs(4700.0)
    assert week1 == 0.0, "re-anchored week must read zero consumption"
    assert day1 == day0, "the DAY anchor must be untouched"


def test_natural_iso_rollover_still_works_after_reanchor():
    rp = _stack()
    rp.observe(5000.0, now=1_786_000_000.0)
    rp.reanchor_week(4700.0, now=1_786_000_000.0)
    # ~8 days later: a new ISO week must re-anchor at the observed equity
    rp.observe(4400.0, now=1_786_000_000.0 + 8 * 86400.0)
    _, week = rp.spent_fracs(4400.0)
    assert week == 0.0, "new ISO week re-anchors at its first observation"


def test_reanchor_refuses_degenerate_equity():
    rp = _stack()
    rp.observe(5000.0, now=1_786_000_000.0)
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        assert rp.reanchor_week(bad) is False
    _, week = rp.spent_fracs(4700.0)
    assert week > 0.0, "a refused re-anchor must change nothing"


def test_reanchor_survives_persistence_roundtrip():
    rp = _stack()
    rp.observe(5000.0, now=1_786_000_000.0)
    rp.reanchor_week(4700.0, now=1_786_000_000.0)
    rp2 = _stack()
    rp2.from_dict(rp.to_dict())
    _, week = rp2.spent_fracs(4700.0)
    assert week == 0.0


# ---------------------------------------------------------------- runner
class _State:
    def total_equity(self, marks):
        return 4700.0

    def open_positions(self):
        return []


class _Bot:
    def __init__(self, rp):
        self.risk_protocols = rp
        self.state = _State()
        self.marks = {}


def _runner(bot) -> BotRunner:
    r = BotRunner.__new__(BotRunner)   # test_audit_runner_state convention
    r.bot = bot
    r.state = "RUNNING"
    return r


def test_command_refused_without_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(core.audit, "_AUDIT",
                        AuditTrail(str(tmp_path / "audit.jsonl")))
    rp = _stack()
    rp.observe(5000.0, now=1_786_000_000.0)
    _runner(_Bot(rp)).handle_command({"cmd": "budget_reanchor_week"},
                                     now=1_786_000_000.0)
    _, week = rp.spent_fracs(4700.0)
    assert week > 0.0, "no reason -> refused -> anchor untouched"


def test_command_reanchors_and_audits(tmp_path, monkeypatch):
    trail = AuditTrail(str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(core.audit, "_AUDIT", trail)
    rp = _stack()
    rp.observe(5000.0, now=1_786_000_000.0)
    _runner(_Bot(rp)).handle_command(
        {"cmd": "budget_reanchor_week",
         "args": {"reason": "ADA churn class, fixed 5c111962"}},
        now=1_786_000_000.0)
    _, week = rp.spent_fracs(4700.0)
    assert week == 0.0
    entries = (tmp_path / "audit.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert any("RP-042" in e and "ADA churn" in e for e in entries), (
        "the override must land in the hash-chained audit trail")


def test_verb_is_not_exposed_over_rest():
    assert "budget_reanchor_week" not in rest.ALLOWED_CONTROL


def test_verb_is_in_valid_commands():
    """The drift class runtime.py documents: a verb handled by the
    runner but absent from VALID_COMMANDS is silently dropped at consume
    with no ack and no error - pin the membership."""
    from core.runtime import VALID_COMMANDS
    assert "budget_reanchor_week" in VALID_COMMANDS
