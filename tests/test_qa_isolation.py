"""QA harnesses must never write to a production output file.

This has now gone wrong TEN times - the first seven found only after they
had corrupted a result, the eighth caught in review before it did, the ninth
(the two singletons, own section below) after it had polluted the trail, the
tenth found by an instrument audit after it had evicted real recordings - and
every early fix was "add the one missing line to qa_redirect_paths" plus a
comment saying it now covers everything:

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
  outputs/fills.csv             136 fixture rows under 34 position_ids from
                                the shared ETH=2000.0 mock feeds - written
                                by BATTERY smoke runs and debug_cycle alike,
                                every QA entry that builds a bot; made mean
                                gross P&L wrong by 27x and manufactured a
                                loss tail that did not exist. Confirmed by
                                audit crossref: 0 of the 136 order_ids
                                appear in the hash-chained audit trail,
                                which QA always redirected
  replay's second list          scripts/replay.py maintained its OWN
                                hand-rolled redirect list, which predated
                                four of the paths above (fills ledger,
                                horizon shadow, model_path, retrain
                                history) - so every replay/sweep/
                                replay_gate run appended synthetic fills
                                to outputs/fills.csv and a monitor-flagged
                                retrain during a replay could deploy a
                                replay-trained model. Found 2026-08-05 in
                                review, the only instance caught BEFORE it
                                corrupted a result. Fix: the family now
                                routes through qa_redirect_paths (the one
                                list) via prepare_replay_config, pinned by
                                the replay-family tests at the bottom.
  outputs/recordings/           (tenth) every smoke boot (section [20] builds
                                a real BotRunner on the production config) wrote a
                                MockKraken fixture session into the live
                                store, and the retain_files ring evicted a
                                REAL recording per boot. The key WAS in
                                config and WAS visible to the walk below - it
                                had been added to _EXEMPT on the written
                                claim that a QA bot "cannot reach feed
                                recording" (runner.py:219-251 is the reach).
                                Found 2026-09-14 by an audit of the
                                fill-hazard report, whose corpus headline had
                                counted the fixtures as sessions; measured
                                46 of 60 retained sidecars were fixtures.
                                The exemption was a comment. This file
                                exists because a comment cannot fail - and
                                one of its own comments had.

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
    # system.recording_dir WAS listed here until 2026-09-14, on the claim that
    # "a QA bot that constructs the engine directly cannot reach feed
    # recording". scripts/smoke_test.py:1416 constructs a BotRunner, and
    # runner.py:219-251 is where recording is reached, so the claim was false
    # for as long as it stood and the walk below was blind to a leak it could
    # see. An exemption is a claim about what constructs a path. It is now a
    # _KNOWN_LEAK_KEYS entry with an end-to-end test that drives the real
    # recorder (test_a_runner_under_the_redirected_config_records_outside_
    # outputs). Do not re-add it here.
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


# The keys that have actually leaked (or been one hardcoded default away
# from leaking). Shared by the smoke-redirect and replay-family tests below
# so the two entry paths can never drift apart on coverage again.
_KNOWN_LEAK_KEYS = [
    "system.fills_ledger_path",
    "system.state_path",
    "ml.history_path",
    "ml.model_path",
    "ml.multi_horizon.shadow_path",
    "ml.postmortem.paths_path",
    "system.recording_dir",           # tenth instance, 2026-09-14
]


@pytest.mark.parametrize("key", _KNOWN_LEAK_KEYS)
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


def test_a_runner_under_the_redirected_config_records_outside_outputs(
        redirected, monkeypatch, tmp_path):
    """END-TO-END for the tenth instance: drive the real recorder.

    The key-shape tests above go green the moment qa_redirect_paths sets
    system.recording_dir; they cannot tell whether runner.py READS that key.
    BotRunner.__init__ (runner.py:219-251) wraps every feed in a FeedRecorder
    whenever system.record_feeds is true and opens the session sink at
    system.recording_dir - that is the writer, so this constructs one.

    Two assertions, and the second is the one that matters:
      1. the sink the runner opened is not under the production outputs/;
      2. it is under the REDIRECTED directory - not cwd-relative
         outputs/recordings. The chdir below is a belt (every other BotRunner
         test wears it, and it is the only reason the pytest suite never
         leaked recordings while smoke_test.py did); a pass that relied on it
         would prove nothing about the redirect. Asserting the redirected
         parent separates "the redirect worked" from "chdir saved us".

    The bot is a duck-typed double carrying only what __init__ touches on the
    production-config path; nothing here polls a venue."""
    import types

    from core.state import PortfolioState
    from runner import BotRunner

    monkeypatch.chdir(tmp_path)
    cfg, _ = redirected
    assert cfg["system"].get("record_feeds"), (
        "precondition: the production config records feeds - if this is ever "
        "false the test exercises nothing and must be rewritten, not skipped")
    redirected_dir = Path(cfg["system"]["recording_dir"]).resolve()
    assert not _under_outputs(str(redirected_dir))

    feed = types.SimpleNamespace()               # FeedRecorder only stores it
    bot = types.SimpleNamespace(
        okx=feed, binanceus=feed, kraken=feed,
        state=PortfolioState(starting_capital=10_000.0),
        _equity=lambda: 10_000.0, fault=None, poll_sec=0.0, dry_run=True,
        entries_enabled=True)
    r = BotRunner(cfg, bot=bot, start_paused=True, lock=None)  # type: ignore[arg-type]
    try:
        sink = r._rec_sink
        assert sink is not None, (
            "the recorder did not arm under the production config - this test "
            "is not exercising the writer (recording setup is fail-soft; read "
            "the captured log for the exception it swallowed)")
        sink = Path(sink).resolve()
        assert not _under_outputs(str(sink)), f"recorder opened {sink}"
        assert sink.parent == redirected_dir, (
            f"recorder opened {sink}, not under the redirected "
            f"{redirected_dir} - runner.py is reading a different key than "
            "qa_redirect_paths sets, and only the chdir kept this out of the "
            "live store")
        assert not (tmp_path / "outputs" / "recordings").exists(), (
            "a cwd-relative outputs/recordings appeared: something still "
            "resolves the default path")
    finally:
        for srv in (getattr(r, "rest_api", None), getattr(r, "grpc_api", None)):
            stop = getattr(srv, "stop", None)
            if callable(stop):
                stop()


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
                     "assurance_check.py", "sweep.py"]
    missing = [n for n in builds_engine
               if fn not in (ROOT / "scripts" / n).read_text(encoding="utf-8")]
    assert not missing, (
        "QA entrypoint(s) build engine components without calling %s(): %s"
        % (fn, ", ".join(missing)))


# ---------------------------------------------------------------------------
# The replay family (replay.py, and sweep.py / replay_gate.py through it).
# scripts/replay.py maintained a SECOND hand-rolled redirect list that
# predated fills_ledger_path / shadow_path / model_path / retrain history -
# the eighth instance of this bug class, and invisible to every test above
# because those only exercise qa_redirect_paths. run_replay now prepares its
# config via prepare_replay_config -> qa_redirect_paths; these tests walk the
# REAL production config through the REAL replay preparation so the family
# and the canonical list can never drift apart again.
# ---------------------------------------------------------------------------

@pytest.fixture
def replay_prepared():
    """Real production config through the real replay config preparation,
    module attribute restored afterwards (same hygiene as `redirected`)."""
    import ml.retrain_log as rl
    from main import load_config
    from scripts.replay import prepare_replay_config
    saved = rl.RETRAIN_HISTORY_PATH_DEFAULT
    try:
        cfg = prepare_replay_config(load_config(str(ROOT / "config.json")))
        yield cfg, rl
    finally:
        rl.RETRAIN_HISTORY_PATH_DEFAULT = saved


def test_replay_config_leaves_no_path_under_outputs(replay_prepared):
    """THE invariant, applied to the replay entry path."""
    cfg, _ = replay_prepared
    leaks = [(k, v) for k, v in _walk(cfg)
             if k not in _EXEMPT and _under_outputs(v)]
    assert not leaks, (
        "prepare_replay_config left %d config path(s) pointing at the "
        "production outputs/ directory:\n  %s\nreplay must route through "
        "qa_redirect_paths, not a private list." % (
            len(leaks), "\n  ".join(f"{k} = {v}" for k, v in leaks)))


@pytest.mark.parametrize("key", _KNOWN_LEAK_KEYS)
def test_replay_sets_every_known_leak_key(replay_prepared, key):
    """Non-vacuous coverage: each known-leak key is PRESENT and redirected
    in a replay config - fills_ledger_path and shadow_path were exactly the
    keys the private list silently lacked."""
    cfg, _ = replay_prepared
    found = dict(_walk(cfg))
    assert key in found, f"{key} missing from the replay config"
    assert not _under_outputs(found[key])


def test_replay_rebinds_retrain_history_default(replay_prepared):
    """A monitor-flagged retrain during a long replay must append to a QA
    retrain history, not the production one."""
    _, rl = replay_prepared
    assert not _under_outputs(rl.RETRAIN_HISTORY_PATH_DEFAULT), (
        "replay leaves ml.retrain_log.RETRAIN_HISTORY_PATH_DEFAULT at %s"
        % rl.RETRAIN_HISTORY_PATH_DEFAULT)


# ---------------------------------------------------------------------------
# The two singletons the CONFIG cannot carry (ninth instance of the class).
#
# qa_redirect_paths can only move keys that exist in a config dict. The audit
# trail and the model registry are process-wide singletons reached through
# core.audit.get_audit() / ml.registry.get_registry(), so every test above is
# structurally blind to them - which is why this instance survived the eighth.
#
# WHY THESE PINS PLANT A BAD STATE FIRST. tests/conftest.py:81-86 redirects
# both singletons in a session-scoped autouse fixture, so inside pytest they
# are ALREADY safe. A test that merely asserted "the audit is not under
# outputs/" would therefore pass whether or not scripts/replay.py ever gained
# its fix - the exact vacuity this repo refuses. Each pin below installs a
# production-shaped path first, asserts that control, and only then proves the
# replay entrypoint moves it. Nothing here ever opens the real trail: the
# planted path is a name under outputs/ that is never written.
# ---------------------------------------------------------------------------

_PROBE_AUDIT = "outputs/_qa_isolation_probe_audit.jsonl"
_PROBE_MODELS = "outputs/_qa_isolation_probe_models"


@pytest.fixture
def singletons_planted():
    """Point both singletons at production-shaped paths, restore afterwards."""
    import core.audit as ca
    import ml.registry as mr
    saved_a, saved_r = ca._AUDIT, mr._REGISTRY
    try:
        ca._AUDIT = ca.AuditTrail(_PROBE_AUDIT, fsync=False)
        mr._REGISTRY = mr.ModelRegistry(_PROBE_MODELS)
        yield ca, mr
    finally:
        ca._AUDIT, mr._REGISTRY = saved_a, saved_r


def test_the_planted_state_is_actually_bad(singletons_planted):
    """Control. If this ever stops failing the two pins below go vacuous."""
    ca, mr = singletons_planted
    assert _under_outputs(str(ca.get_audit().path))
    assert _under_outputs(str(mr.get_registry().dir))


def test_replay_preparation_redirects_both_singletons(singletons_planted):
    """THE invariant: preparing a replay config moves the singletons that no
    config key can reach."""
    from main import load_config
    from scripts.replay import prepare_replay_config
    ca, mr = singletons_planted
    prepare_replay_config(load_config(str(ROOT / "config.json")))
    assert not _under_outputs(str(ca.get_audit().path)), (
        "replay left the audit singleton at %s - synthetic dispositions "
        "would append to the production hash-chained trail"
        % ca.get_audit().path)
    assert not _under_outputs(str(mr.get_registry().dir)), (
        "replay left the model registry at %s" % mr.get_registry().dir)


def test_make_offline_recording_isolates_BEFORE_building_an_engine(
        monkeypatch, tmp_path):
    """Ordering matters, not just occurrence: the redirect has to happen
    before any engine component exists, because construction itself audits.

    The spy raises, so the 60-cycle recording never runs - if the call were
    moved below the LiquidityBot construction this test would build a bot
    (slow) and then fail on the missing exception, and if it were removed
    entirely it fails immediately. Either way it cannot pass by accident."""
    import scripts.replay as rp
    import scripts.overfit_check as oc

    class _Called(Exception):
        pass

    def _spy():
        raise _Called

    monkeypatch.setattr(rp, "isolate_qa_singletons", _spy)
    with pytest.raises(_Called):
        oc.make_offline_recording(tmp_path / "rec")
