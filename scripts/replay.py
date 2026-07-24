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
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.replay import ReplayExhausted, load_session  # noqa: E402
from main import LiquidityBot, load_config  # noqa: E402

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


def run_replay(config: dict, recording: str, quiet: bool = True) -> dict:
    """Drive the engine through one recorded session; return the summary."""
    cfg = copy.deepcopy(config)
    cfg["system"]["dry_run"] = True
    cfg["system"]["record_feeds"] = False
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg.setdefault("context", {})["enabled"] = False
    # QA intermediates go to the system temp dir, NEVER outputs/: replay
    # state/history/postmortems/flags landing in the production telemetry
    # directory polluted live monitoring - a replayed bot even overwrote
    # the live state.json. These paths OVERRIDE whatever the caller set.
    tmp = Path(tempfile.gettempdir())
    cfg["system"]["state_path"] = str(tmp / "liqbot_replay_state.json")
    cfg["system"]["weekly_ledger_path"] = str(tmp / "liqbot_replay_weekly_ledger.csv")
    cfg["system"]["monthly_ledger_path"] = str(tmp / "liqbot_replay_monthly_ledger.csv")
    ml_cfg = cfg.setdefault("ml", {})
    ml_cfg["history_path"] = str(tmp / "liqbot_replay_history.csv")
    ml_cfg.setdefault("postmortem", {})
    ml_cfg["postmortem"]["report_dir"] = str(tmp / "liqbot_replay_pm")
    ml_cfg["postmortem"]["summary_path"] = str(tmp / "liqbot_replay_pm.csv")
    ml_cfg.setdefault("monitor", {})
    ml_cfg["monitor"]["retrain_flag_path"] = str(tmp / "liqbot_replay.flag")
    Path(cfg["system"]["state_path"]).unlink(missing_ok=True)
    Path(ml_cfg["history_path"]).unlink(missing_ok=True)
    Path(cfg["system"]["weekly_ledger_path"]).unlink(missing_ok=True)
    Path(cfg["system"]["monthly_ledger_path"]).unlink(missing_ok=True)

    players = load_session(recording)
    meta = players.pop("_meta")
    bot = LiquidityBot(cfg,
                       okx=players.get("okx"),
                       binanceus=players.get("binanceus"),
                       kraken=players.get("kraken"),
                       resume=False)
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
        "entries_filled": len(entries),
        "exit_orders": len(closed),
        "open_positions_end": bot.state.open_position_count(),
        "labeled_rows": bot.history.row_count(),
    }


def main():
    # replayed bots audit their dispositions and record model lifecycle
    # events; keep synthetic records out of the production trail/ledger
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(Path(tempfile.gettempdir()) / "liqbot_replay_audit.jsonl")
    configure_registry(Path(tempfile.gettempdir()) / "liqbot_replay_models")
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
