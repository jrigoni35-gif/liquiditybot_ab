"""Scratch: an arrival that becomes a RANDOMIZED exploration entry (ML-070)
is still stamped propensity=1.0 in its DE-010 event."""
import json, sys
from pathlib import Path
from types import SimpleNamespace
WT = Path(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
sys.path.insert(0, str(WT / "tests"))
from test_decision_events import _bot  # noqa: E402


def test_explored_arrival_claims_propensity_one(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bot = _bot(tmp_path)
    bot.gate_stats.enabled = False
    bot.gates.evaluate_asset = lambda asset, v: SimpleNamespace(
        direction="long", all_confirmed=True, confidence=0.61,
        gates_passed={"rsi": True, "mom": True}, urgency=0.0,
        evidence_concentration=0.0, components={})
    rolls = []
    def forced(now, asset, regime_label=None):
        rolls.append(asset); return True        # the epsilon roll "hit"
    monkeypatch.setattr(bot, "_probe_admission_decision", forced)
    bot.slow_cycle(1_700_000_000.0)
    recs = [json.loads(x) for x in (tmp_path / "audit.jsonl").read_text().splitlines()]
    ml070 = [r for r in recs if r["code"] in ("ML-070", "ML-072")]
    explored_assets = {r["msg"].split()[3] for r in ml070}
    print("rolls", rolls, "ML-070/072", len(ml070), explored_assets)
    assert ml070, "harness did not reach the exploration branch (CONTROL)"
    ev = [e for e in bot._de_events if e["asset"] in explored_assets]
    print("DE events for explored assets:", [(e["asset"], e["absorb"], e["propensity"], e.get("explored")) for e in ev])
    assert ev
    # the defect: a randomized action logged with the deterministic propensity
    assert all(e["propensity"] != 1.0 or e.get("explored") is True for e in ev), \
        "explored arrival stamped propensity=1.0 with no exploration marker"
