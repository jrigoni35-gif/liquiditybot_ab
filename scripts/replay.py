"""
scripts/replay.py

Replay a recorded market session through the unmodified production
engine and report what it did. This is the truth-level backtest: same
gates, same AS quotes, same order state machine, same fill simulator,
against the exact frames the market actually produced.

Record a session first (dry run):
    set  "system.record_feeds": true   in config.json, run the bot for
    a few hours; a file appears under outputs/recordings/.

Replay:
    python scripts/replay.py --recording outputs/recordings/session_XXX.jsonl
    python scripts/replay.py --recording ... --set position_sizer.min_p_win=0.60

--set overrides any dotted config path (repeatable), which is what the
sweep tool builds on. Sentiment/webdata/moomoo are disabled during
replay (their live values weren't part of the recorded frames; features
fall back to neutral - documented limitation). The Phase B context feed
(data/context_engine.py) is disabled too - it has no per-run redirect,
so leaving it on would both hit five real network endpoints and append
to the real outputs/context_history.jsonl PIT file every replay.
"""

import argparse
import copy
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.replay import ReplayExhausted, load_session  # noqa: E402
from main import LiquidityBot, load_config  # noqa: E402
from scripts.smoke_test import qa_redirect_paths  # noqa: E402

log = logging.getLogger("replay")


def set_dotted(cfg: dict, dotted: str, raw: str):
    keys = dotted.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    try:
        val = json.loads(raw)
    except json.JSONDecodeError:
        val = raw
    node[keys[-1]] = val


def isolate_qa_singletons() -> None:
    """Point the process-wide audit + registry singletons at scratch paths.

    THE HOLE THIS CLOSES. `core/audit.py:423` and `ml/registry.py:337` both
    say QA harnesses "MUST call this before constructing any engine
    component" - and both put that obligation on the CALLER, which makes it a
    convention rather than a mechanism.

    Be precise about who actually forgot, because the obvious suspects did
    NOT (verified 2026-09-10, and an earlier draft of this docstring got it
    wrong): `tests/conftest.py:81-86` redirects both singletons in a
    session-scoped autouse fixture, so the pytest suite is covered; and all
    four shipped script callers - `sweep.py`, `archetype_battery.py`,
    `replay_gate.py`, `smoke_test.py` - call both functions themselves.

    The exposed party is the caller that is neither: an ad-hoc analysis
    script that imports `run_replay` / `make_offline_recording` as LIBRARY
    functions outside pytest. Nothing warned it, and four separate call sites
    each independently remembering the same rule is exactly the shape that
    decays. That is how the trail below was polluted, including by this
    session's own C5 diagnosis probes.

    Measured on this tree 2026-09-10: bucketing `outputs/audit.jsonl`'s 476
    `CG-000` session-start records by `data.starting_capital_usd` gave
    {800: 98, 5000: 264, 10000: 114} - only 98 of 476 sessions carry the
    production bot's capital, and 10000 is `make_offline_recording`'s own
    literal. The chain carries 59 `prev`/`h` linkage breaks and 29
    backward-`seq` steps, the signature of two writers with independent
    counters appending to one file. Ninth instance of the QA-writes-production
    class; `prepare_replay_config`'s own docstring records the eighth, and
    `configure_audit`'s records SD-007.

    A convention cannot be enforced by the module that documents it. This
    makes it a MECHANISM: the redirect happens on the way IN, so an importer
    cannot forget it.

    Deliberately PERMANENT for the interpreter rather than restored on exit.
    A restoring context manager would hand the singleton back to
    `outputs/audit.jsonl` the moment the call returned, re-exposing every
    later engine construction in the same process - and a pytest run builds
    thousands. Permanence cannot reach the live bot: no production entrypoint
    imports this module (`runner.py` and `main.py` mention replay only in
    comments and via `data.replay`), and the redirect fires on CALL, never on
    import.
    """
    from core.audit import configure_audit
    from ml.registry import configure_registry
    tmp = Path(tempfile.gettempdir())
    configure_audit(tmp / "liqbot_replay_audit.jsonl")
    configure_registry(tmp / "liqbot_replay_models")


def prepare_replay_config(config: dict) -> dict:
    """Deep-copy and fully QA-isolate a config for a replay run.

    Live-only feeds are disabled (their values weren't part of the recorded
    frames; features fall back to neutral - documented limitation), then
    EVERY engine write path is redirected through qa_redirect_paths - the
    ONE canonical list. This function used to keep a private six-path list,
    which silently lacked fills_ledger_path, the horizon shadow path,
    model_path and the retrain history: every replay/sweep/gate run
    appended synthetic fills to the production ledger, and a
    monitor-flagged retrain during a long replay could deploy a
    replay-trained model. Eighth instance of the QA-writes-production
    class; pinned by the replay-family tests in
    tests/test_qa_isolation.py. Never re-grow a private list here - add
    missing paths to qa_redirect_paths so smoke, replay, sweep and the
    gate stay covered together.
    """
    # the audit + model-registry singletons are NOT config-carried, so
    # qa_redirect_paths below cannot reach them - see isolate_qa_singletons
    isolate_qa_singletons()
    cfg = copy.deepcopy(config)
    cfg["system"]["dry_run"] = True
    cfg["system"]["record_feeds"] = False
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    # context.enabled is force-disabled inside qa_redirect_paths
    cfg = qa_redirect_paths(cfg, f"replay_{os.getpid()}")
    # one replay = one clean slate: successive runs in a sweep share the
    # per-pid QA dir, so drop the previous combo's state/ledgers/history
    for stale in (cfg["system"]["state_path"],
                  cfg["system"]["weekly_ledger_path"],
                  cfg["system"]["monthly_ledger_path"],
                  cfg["system"]["fills_ledger_path"],
                  cfg["ml"]["history_path"],
                  cfg["ml"]["multi_horizon"]["shadow_path"],
                  cfg["ml"]["postmortem"]["paths_path"]):
        Path(stale).unlink(missing_ok=True)
    return cfg


def run_replay(config: dict, recording: str, quiet: bool = True, *,
               mutate_bot=None) -> dict:
    """Drive the engine through one recorded session; return the summary.

    mutate_bot: optional callable invoked with the constructed LiquidityBot
    after init and before the first cycle — the sanctioned strategy-injection
    seam (the overfit_check make_offline_recording precedent). Default None
    is byte-identical to the pre-hook behavior; pinned by
    tests/test_replay_mutate_hook.py.
    """
    # belt and braces: prepare_replay_config already isolates, but a future
    # edit that stops routing through it must not silently re-open the hole
    isolate_qa_singletons()
    cfg = prepare_replay_config(config)

    players = load_session(recording)
    meta = players.pop("_meta")
    bot = LiquidityBot(cfg,
                       okx=players.get("okx"),
                       binanceus=players.get("binanceus"),
                       kraken=players.get("kraken"),
                       resume=False)
    if mutate_bot is not None:
        mutate_bot(bot)
    if quiet:
        logging.getLogger("liquiditybot").setLevel(logging.WARNING)

    t = meta["start_ts"]
    cycles = 0
    t_wall = time.time()
    try:
        while True:
            bot.cycle_once(t)
            t += bot.poll_sec
            cycles += 1
    except ReplayExhausted:
        pass
    finally:
        logging.getLogger("liquiditybot").setLevel(logging.INFO)

    closed = [o for o in bot.orders._orders.values() if o.purpose == "exit"]
    entries = [o for o in bot.orders._orders.values()
               if o.purpose == "entry" and o.filled > 0]
    return {
        "cycles": cycles,
        "sim_minutes": round(cycles * bot.poll_sec / 60.0, 1),
        "wall_seconds": round(time.time() - t_wall, 1),
        "final_equity": round(bot._equity(), 2),
        "realized_pnl": round(bot.state.realized_pnl_total, 2),
        "fees": round(bot.state.fees_paid_total, 2),
        "entry_fees": round(bot.state.entry_fees_total, 2),
        "entries_filled": len(entries),
        "exit_orders": len(closed),
        "open_positions_end": bot.state.open_position_count(),
        "labeled_rows": bot.history.row_count(),
        # per-run QA fills ledger — read it BEFORE the next run: successive
        # runs share the per-pid QA dir and prepare_replay_config unlinks it
        "fills_ledger_path": cfg["system"]["fills_ledger_path"],
    }


def main():
    # replayed bots audit their dispositions and record model lifecycle
    # events; keep synthetic records out of the production trail/ledger.
    # One source of truth so the __main__ path and the library path cannot
    # drift to different scratch locations - they did not, but nothing
    # stopped them.
    isolate_qa_singletons()
    ap = argparse.ArgumentParser()
    ap.add_argument("--recording", required=True)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--set", action="append", default=[],
                    metavar="path.to.key=value",
                    help="override a config value (repeatable)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)
    for ov in args.set:
        dotted, raw = ov.split("=", 1)
        set_dotted(cfg, dotted, raw)
        log.info(f"override: {dotted} = {raw}")

    summary = run_replay(cfg, args.recording, quiet=not args.verbose)
    log.info("replay summary: " + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
