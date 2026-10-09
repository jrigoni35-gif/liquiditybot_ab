"""Scratch: a raise in an EARLY hourly stage starves fee-recon, model adopt,
auto-retrain and drift for the whole hour; and a raise in auto-retrain
starves drift."""
import sys
from pathlib import Path
import pytest
WT = Path(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
sys.path.insert(0, str(WT / "tests"))
from test_decision_events import _bot  # noqa: E402


@pytest.mark.parametrize("fault", [None, "macro.update", "corr.update_turbulence",
                                   "_maybe_auto_retrain"])
def test_hourly_stage_coupling(tmp_path, monkeypatch, fault):
    monkeypatch.chdir(tmp_path)
    bot = _bot(tmp_path)
    called = []
    monkeypatch.setattr(bot.orders, "check_fee_reconciliation",
                        lambda now: called.append("fee_recon"))
    monkeypatch.setattr(bot.monitor, "check_drift",
                        lambda *a, **k: called.append("drift"))
    orig_retrain = bot._maybe_auto_retrain
    monkeypatch.setattr(bot, "_maybe_auto_retrain",
                        lambda: (called.append("retrain"), orig_retrain()))
    if fault:
        obj_name, _, meth = fault.rpartition(".")
        target = getattr(bot, obj_name) if obj_name else bot
        def boom(*a, **k):
            if fault == "_maybe_auto_retrain":
                called.append("retrain")
            raise RuntimeError("injected")
        monkeypatch.setattr(target, meth, boom)
    bot._last_macro = 0.0
    bot.cycle_once(1_700_000_000.0)
    print(fault, "->", called, "exit_eval_failures", bot._exit_eval_failures)
    if fault is None:
        assert called == ["fee_recon", "retrain", "drift"]     # CONTROL
    elif fault == "_maybe_auto_retrain":
        assert "drift" not in called
    else:
        assert called == []
