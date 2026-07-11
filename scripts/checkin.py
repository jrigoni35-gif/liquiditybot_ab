"""
scripts/checkin.py

Unattended supervised check-in for a running paper (DRY_RUN) session.
Meant to fire on a schedule (0/6/12/24h) while no operator is watching:
pulls session_digest, cross-checks audit-chain integrity, ML kill-switch
state, equity/data sanity, feed health, and process liveness (the
runner's heartbeat lock), and pauses new entries via the ControlChannel
if anything looks structurally wrong. Never flips dry_run, never
flattens, never stops the runner - pause only blocks new risk, exits
stay live (same invariant the bot's own faults/disarm paths honor).

Writes one report per checkpoint (outputs/checkin/checkin_<label>.md
+ .json) and appends a line to outputs/checkin/checkin_log.jsonl so a
later checkpoint (or a human) can see the run's trend across checkpoints.

Usage:
    python scripts/checkin.py --label 6h
    python scripts/checkin.py --label 24h --outputs outputs --config config.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runtime import ControlChannel, read_json  # noqa: E402
from core.session_digest import write_digest  # noqa: E402

HEARTBEAT_STALE_SEC = 180.0   # generous vs. the runner's own 30s self-lock


def _process_liveness(outputs_dir: Path) -> dict:
    lock = read_json(outputs_dir / "runner.lock")
    if not isinstance(lock, dict):
        return {"alive": False, "detail": "no runner.lock found"}
    age = time.time() - float(lock.get("heartbeat", 0) or 0)
    alive = age < HEARTBEAT_STALE_SEC
    return {"alive": alive, "pid": lock.get("pid"), "heartbeat_age_s": round(age, 1),
            "detail": "ok" if alive else f"heartbeat stale ({age:.0f}s > "
                                          f"{HEARTBEAT_STALE_SEC:.0f}s) - runner "
                                          f"looks dead or wedged"}


def _equity_sanity(digest: dict, config: dict) -> dict:
    pnl = digest.get("pnl", {})
    starting = config.get("capital_management", {}).get("starting_capital_usd") \
        or pnl.get("starting_capital") or 0
    equity_end = pnl.get("equity_end")
    problems = []
    if equity_end is None:
        problems.append("no equity samples in window")
    else:
        try:
            e = float(equity_end)
            if e != e or e in (float("inf"), float("-inf")):
                problems.append(f"equity_end is non-finite ({equity_end!r})")
            elif e <= 0:
                problems.append(f"equity_end <= 0 ({e})")
            elif starting and (e > starting * 5 or e < starting * 0.2):
                problems.append(f"equity_end {e:.2f} is >5x or <0.2x "
                                f"starting_capital {starting} - data/feed "
                                f"corruption, not a trading judgment call")
        except (TypeError, ValueError):
            problems.append(f"equity_end not numeric ({equity_end!r})")
    return {"ok": not problems, "problems": problems, "equity_end": equity_end}


def _kill_switch_state(digest: dict) -> dict:
    model = digest.get("model", {})
    audit = digest.get("audit", {})
    level = model.get("monitor_level", 0)
    ml050 = sum(n for code, n in audit.get("top_codes", []) if code == "ML-050")
    return {"monitor_level": level, "ml_kill_switch_events_in_window": ml050,
            "engaged": level is not None and level >= 2}


def run_checkin(label: str, outputs: str, config_path: str) -> dict:
    outputs_dir = Path(outputs)
    config = {}
    cfg_path = Path(config_path)
    if cfg_path.exists():
        try:
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            config = {}

    digest = write_digest(str(outputs_dir), config)
    status = read_json(outputs_dir / "status.json") or {}
    liveness = _process_liveness(outputs_dir)
    equity = _equity_sanity(digest, config)
    kill_switch = _kill_switch_state(digest)
    audit = digest.get("audit", {})

    critical = []
    warnings = []

    worst = digest["diagnostics"][0] if digest.get("diagnostics") else {}
    if worst.get("severity") == "error":
        critical.append(f"session_digest verdict: {digest.get('verdict')}")
    elif worst.get("severity") == "warn":
        warnings.append(f"session_digest verdict: {digest.get('verdict')}")

    if audit.get("chain_ok") is False:
        critical.append(f"audit hash chain broken at "
                        f"{audit.get('chain_first_break')}")

    mode = status.get("mode")
    if mode and mode != "DRY_RUN":
        critical.append(f"status.json mode is {mode!r}, expected DRY_RUN - "
                        f"live capital may be at risk")

    if not liveness["alive"]:
        critical.append(f"runner process: {liveness['detail']}")

    if not equity["ok"]:
        critical.extend(f"equity sanity: {p}" for p in equity["problems"])

    if kill_switch["engaged"]:
        warnings.append(f"ML kill switch engaged (monitor level "
                        f"{kill_switch['monitor_level']}) - model output "
                        f"disabled, this is the safety system working as "
                        f"designed, not a bug")

    feed_err = digest.get("events", {}).get("feed_error_events", 0)
    if feed_err and feed_err > 5:
        warnings.append(f"{feed_err} feed error events in window")

    paused = False
    pause_attempted = False
    if critical and liveness["alive"]:
        pause_attempted = True
        try:
            ControlChannel(str(outputs_dir / "control")).send(
                "pause", {"reason": f"checkin[{label}]: " + "; ".join(critical)})
            paused = True
        except Exception as e:  # noqa: BLE001 - best-effort operator alert path
            critical.append(f"tried to send pause command but it failed: {e}")

    report = {
        "label": label,
        "generated_at": time.time(),
        "verdict": digest.get("verdict"),
        "status_snapshot": {"mode": mode, "runner_state": status.get("runner_state"),
                            "equity": status.get("equity")},
        "process_liveness": liveness,
        "equity_sanity": equity,
        "kill_switch": kill_switch,
        "audit_chain_ok": audit.get("chain_ok"),
        "feed_error_events": feed_err,
        "critical": critical,
        "warnings": warnings,
        "paused_bot": paused,
        "pause_attempted": pause_attempted,
        "anomaly": bool(critical),
    }

    checkin_dir = outputs_dir / "checkin"
    checkin_dir.mkdir(parents=True, exist_ok=True)
    (checkin_dir / f"checkin_{label}.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    (checkin_dir / f"checkin_{label}.md").write_text(
        render_markdown(report), encoding="utf-8")
    with open(checkin_dir / "checkin_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(report, default=str) + "\n")

    return report


def render_markdown(report: dict) -> str:
    lines = [f"# Check-in: {report['label']}",
             f"generated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report['generated_at']))}",
             "", f"**verdict:** {report['verdict']}",
             f"**anomaly:** {report['anomaly']}",
             f"**paused_bot:** {report['paused_bot']}", ""]
    snap = report["status_snapshot"]
    lines.append(f"- mode={snap['mode']} runner_state={snap['runner_state']} "
                 f"equity={snap['equity']}")
    live = report["process_liveness"]
    lines.append(f"- process: alive={live['alive']} {live.get('detail', '')}")
    lines.append(f"- audit chain ok: {report['audit_chain_ok']}")
    ks = report["kill_switch"]
    lines.append(f"- ML kill switch: engaged={ks['engaged']} "
                 f"level={ks['monitor_level']}")
    lines.append(f"- feed error events: {report['feed_error_events']}")
    if report["critical"]:
        lines.append("\n## CRITICAL")
        lines.extend(f"- {c}" for c in report["critical"])
    if report["warnings"]:
        lines.append("\n## warnings")
        lines.extend(f"- {w}" for w in report["warnings"])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="checkpoint label, e.g. 0h/6h/12h/24h")
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    report = run_checkin(args.label, args.outputs, args.config)
    print(render_markdown(report))
    return 2 if report["anomaly"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
