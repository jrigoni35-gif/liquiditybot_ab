"""run_replay mutate_bot hook: default is byte-identical; hook sees the bot.

The hook exists so scripts/archetype_battery.py can inject an archetype
evaluate_asset (the overfit_check.py:360 precedent) WITHOUT run_replay
growing any strategy knowledge. Determinism keys plus cycles must be
unchanged by a no-op hook.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.replay_gate import _DETERMINISM_KEYS, determinism_ok  # noqa: E402


def _recording_and_cfg(tmp_path):
    from main import load_config
    from scripts.overfit_check import make_offline_recording
    rec_dir = tmp_path / "rec"
    make_offline_recording(rec_dir)
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    return str(rec_dir / "session.jsonl"), cfg


def test_default_mutate_bot_is_inert_and_deterministic(tmp_path):
    from scripts.replay import run_replay
    rec, cfg = _recording_and_cfg(tmp_path)
    a = run_replay(cfg, rec, quiet=True)
    b = run_replay(cfg, rec, quiet=True, mutate_bot=None)
    ok, diff = determinism_ok(a, b, keys=_DETERMINISM_KEYS + ("cycles",))
    assert ok, diff
    assert "fills_ledger_path" in a and a["fills_ledger_path"].endswith(".csv")


def test_mutate_bot_receives_the_constructed_bot(tmp_path):
    from scripts.replay import run_replay
    rec, cfg = _recording_and_cfg(tmp_path)
    seen = {}

    def probe(bot):
        seen["gates"] = hasattr(bot, "gates")
        seen["evaluate"] = callable(getattr(bot.gates, "evaluate_asset", None))

    run_replay(cfg, rec, quiet=True, mutate_bot=probe)
    assert seen == {"gates": True, "evaluate": True}
