"""Scratch: a raise in ONE slow_cycle head stage (darkpool / context poll)
starves the entry sweep, EN-000 and DE-010 for the whole cycle."""
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
WT = Path(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
sys.path.insert(0, str(WT / "tests"))
from test_decision_events import _bot  # noqa: E402


def _stub_gates(bot):
    bot.gates.evaluate_asset = lambda asset, v: SimpleNamespace(
        direction=None, all_confirmed=False, confidence=0.5,
        gates_passed={"rsi": True}, urgency=0.0,
        evidence_concentration=0.0, components={})


@pytest.mark.parametrize("stage", [None, "darkpool", "context", "moomoo"])
def test_stage_raise_starves_sweep(tmp_path, monkeypatch, stage):
    monkeypatch.chdir(tmp_path)
    bot = _bot(tmp_path)
    _stub_gates(bot)
    if stage:
        def boom(*a, **k):
            raise RuntimeError(f"injected {stage} fault")
        monkeypatch.setattr(getattr(bot, stage), "maybe_poll", boom)
    bot._cycle = 0                       # force the slow branch
    bot.cycle_once(1_700_000_000.0)      # cycle_once isolates slow_cycle
    arrivals = bot.entry_absorb_status().get("arrivals", 0)
    print(stage, "arrivals", arrivals, "de_events", len(bot._de_events),
          "exit_eval_failures", bot._exit_eval_failures)
    if stage is None:
        assert arrivals > 0 and len(bot._de_events) == arrivals   # CONTROL
    else:
        assert arrivals == 0 and bot._de_events == []   # whole sweep starved
