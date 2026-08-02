"""QA harnesses must never write to a production output file.

This has now gone wrong SIX times, each found only after it had corrupted a
result, and every previous fix was "add the one missing line to
qa_redirect_paths" plus a comment saying it now covers everything:

  outputs/state.json            a smoke bot saved fixture state over the
                                runner's snapshot, deleting three real open
                                positions (scripts/smoke_test.py:64-66)
  postmortem summaries          leaked the same way (smoke_test.py:66)
  retrain flags                 leaked the same way (smoke_test.py:66)
  outputs/context_history.jsonl a smoke/replay battery wrote 100+
                                contaminating rows (smoke_test.py:72-74)
  outputs/audit.jsonl           mock entries reached the cloud trail
                                (scripts/debug_cycle.py:42-43)
  outputs/retrain_history.jsonl 305 of 306 records were suite fixtures
                                (ml/retrain_log.py:18-20)
  outputs/fills.csv             64 fixture rows under 16 position_ids, from
                                debug_cycle's ETH=2000.0 mock; made mean
                                gross P&L wrong by 27x and manufactured a
                                loss tail that did not exist

A comment cannot fail. This test can. It asserts the INVARIANT rather than
the seven known cases, so a path added to config.json next month is covered
without anyone remembering this file exists.

WHY THE LAST TWO WERE INVISIBLE: config.json does not set
system.fills_ledger_path or any retrain-history key. The engine falls back
to a hardcoded default that IS the production file, so grepping config for
the key finds nothing. Absence of a key is not absence of a write.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# Keys whose VALUE is a filesystem destination. Every redirected key in
# qa_redirect_paths matches one of these, and so does every path key in
# config.json - the repo names them consistently, which is what makes a
# generic invariant possible instead of a hand-maintained list.
_PATH_SUFFIXES = ("_path", "_dir")

# Exempt ONLY with evidence that qa_redirect_paths is the wrong lever, never
# because a leak looked inconvenient. Each of these is covered by another
# assertion below rather than simply excused.
_EXEMPT = {
    # Process-wide singletons: the config key is not consumed by
    # main.py/runner.py/core at all, so setting it here would be dead config.
    # configure_audit() / configure_registry() are the real mechanisms, and
    # test_every_qa_entrypoint_isolates_the_singletons pins that they are
    # called. Found by this test: debug_cycle.py redirected the audit trail
    # but NOT the registry, so a step-through appended fixture model cards to
    # the production ledger (ml/models.py:404 -> get_registry().register()).
    "assurance.audit_path",
    "assurance.registry_dir",
    # Read only at runner.py:203, never by LiquidityBot - a QA bot that
    # constructs the engine directly cannot reach feed recording. Same
    # category as status.json / equity.csv / events.jsonl / skimmer_active,
    # which are all constructed in runner.py (lines 308, 1700, 266) only.
    "system.recording_dir",
}

OUTPUTS = (ROOT / "outputs").resolve()


def _walk(node, prefix=""):
    """Yield (dotted_key, value) for every path-ish string in a config."""
    if isinstance(node, dict):
        for k, v in node.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, str) and str(k).endswith(_PATH_SUFFIXES):
                yield key, v
            else:
                yield from _walk(v, key)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{prefix}[{i}]")


def _under_outputs(value: str) -> bool:
    try:
        p = Path(value)
        p = p if p.is_absolute() else (ROOT / p)
        return os.path.normcase(str(OUTPUTS)) in os.path.normcase(
            str(p.resolve()))
    except (OSError, ValueError):
        return False


@pytest.fixture
def redirected():
    """Real production config through the real redirect, module attribute
    restored afterwards so this test cannot leak into the rest of the run -
    which would be the same class of bug it exists to catch."""
    import ml.retrain_log as rl
    from main import load_config
    from smoke_test import qa_redirect_paths
    saved = rl.RETRAIN_HISTORY_PATH_DEFAULT
    try:
        cfg = qa_redirect_paths(load_config(str(ROOT / "config.json")),
                                "isolation_test")
        yield cfg, rl
    finally:
        rl.RETRAIN_HISTORY_PATH_DEFAULT = saved


def test_no_config_path_survives_redirect_pointing_at_outputs(redirected):
    """THE invariant. Any *_path/*_dir still under outputs/ after the
    redirect is a QA bot writing a production file."""
    cfg, _ = redirected
    leaks = [(k, v) for k, v in _walk(cfg)
             if k not in _EXEMPT and _under_outputs(v)]
    assert not leaks, (
        "qa_redirect_paths left %d config path(s) pointing at the production "
        "outputs/ directory:\n  %s\nAdd them to qa_redirect_paths in "
        "scripts/smoke_test.py. If a path is genuinely not consumed by the "
        "engine graph, add it to _EXEMPT here WITH the evidence that nothing "
        "constructs it." % (len(leaks),
                            "\n  ".join(f"{k} = {v}" for k, v in leaks)))


def test_retrain_history_default_is_rebound(redirected):
    """No config key exists for this one, so the generic walk above cannot
    see it - it lives as a module attribute (ml/retrain_log.py:15-23) and
    must be rebound. This is the case that reached 305/306 contamination."""
    _, rl = redirected
    assert not _under_outputs(rl.RETRAIN_HISTORY_PATH_DEFAULT), (
        "ml.retrain_log.RETRAIN_HISTORY_PATH_DEFAULT still points at %s - "
        "qa_redirect_paths must rebind it." % rl.RETRAIN_HISTORY_PATH_DEFAULT)


@pytest.mark.parametrize("key", [
    "system.fills_ledger_path",
    "system.state_path",
    "ml.history_path",
    "ml.model_path",
    "ml.multi_horizon.shadow_path",
])
def test_known_leak_keys_are_actually_set(redirected, key):
    """The generic test passes vacuously if a key is simply absent from the
    config - and fills_ledger_path WAS absent, which is exactly why the leak
    survived. Assert each one is present and redirected, so deleting a line
    from qa_redirect_paths fails loudly instead of silently."""
    cfg, _ = redirected
    found = dict(_walk(cfg))
    assert key in found, f"{key} missing from the redirected config"
    assert not _under_outputs(found[key])


def test_a_fill_under_the_redirected_config_lands_outside_outputs(redirected):
    """END-TO-END, not just key-shape. The config assertions above all pass
    if main.py reads a DIFFERENT key than the one qa_redirect_paths sets, so
    they cannot prove the leak is closed. This drives the real writer.

    LiquidityBot._ledger_fill (main.py:1652) touches nothing on self except
    self.config, so a stub is enough and this stays a fast unit test rather
    than a full bot build."""
    from types import SimpleNamespace

    from main import LiquidityBot
    cfg, _ = redirected
    dest = Path(cfg["system"]["fills_ledger_path"])
    if dest.exists():
        dest.unlink()
    order = SimpleNamespace(
        order_id="qa1", position_id="qa-pos", purpose="entry",
        symbol="ETH/USD", side="buy", ordertype="limit", post_only=True,
        arrival_ref=2000.0, remaining=0.0, meta={"attempt": 0, "reason": ""})
    event = SimpleNamespace(fill_size=0.25, fill_price=1988.024658)

    before = (OUTPUTS / "fills.csv")
    before_bytes = before.read_bytes() if before.exists() else None

    LiquidityBot._ledger_fill(SimpleNamespace(config=cfg),
                              order, event, 0.5, 1785605719.0)

    assert dest.exists(), (
        "the redirected ledger was never written - _ledger_fill is reading a "
        "different config key than qa_redirect_paths sets")
    assert "1988.024658" in dest.read_text(encoding="utf-8")
    if before_bytes is not None:
        assert before.read_bytes() == before_bytes, (
            "production outputs/fills.csv changed during a redirected fill")


@pytest.mark.parametrize("fn", ["configure_audit", "configure_registry"])
def test_every_qa_entrypoint_isolates_the_singletons(fn):
    """Backs the _EXEMPT entries for assurance.audit_path and
    assurance.registry_dir. Both are process-wide singletons isolated by an
    explicit call, not by config, so a QA script that builds engine
    components without calling them writes the real hash-chained trail
    (observed: debug_cycle.py:42-43) or the real model registry.

    This is what caught debug_cycle.py: it called configure_audit and not
    configure_registry, and was the only entrypoint of the seven that did."""
    builds_engine = ["smoke_test.py", "debug_cycle.py", "overfit_check.py",
                     "quant_trials.py", "replay.py", "replay_gate.py",
                     "assurance_check.py"]
    missing = [n for n in builds_engine
               if fn not in (ROOT / "scripts" / n).read_text(encoding="utf-8")]
    assert not missing, (
        "QA entrypoint(s) build engine components without calling %s(): %s"
        % (fn, ", ".join(missing)))
