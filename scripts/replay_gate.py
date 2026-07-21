"""scripts/replay_gate.py — the replay-vs-live standing gate (battery entry).

Discovers recorded sessions under outputs/recordings/, replays the newest few
through the UNMODIFIED production engine twice each, and checks:
  * determinism  — two replays of one recording must be identical (hard fail);
  * reconciliation — replay P&L must match the live session's flat-start delta
    within tolerance; hard-fails only on a self-contained recording.

Exit status: 0 on PASS or SKIP (no recordings => dormant, so the battery stays
green on a fresh clone), 1 on FAIL. Replayed bots write their state/history/
audit/models to the system temp dir, never to outputs/ (production telemetry).

    python scripts/replay_gate.py
    python scripts/replay_gate.py --recording-dir outputs/recordings --max 5
"""

import argparse
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code  # noqa: E402
from core.replay_gate import run_gate  # noqa: E402
from main import load_config  # noqa: E402
from scripts.replay import run_replay  # noqa: E402

log = logging.getLogger("replay_gate")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recording-dir", default="outputs/recordings")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--max", type=int, default=3,
                    help="newest N recordings to replay (default 3)")
    ap.add_argument("--rel-tol", type=float, default=0.005)
    ap.add_argument("--abs-tol", type=float, default=0.01)
    ap.add_argument("--determinism-only", action="store_true",
                    help="skip reconciliation (deploy-gate mode: cross-version "
                         "P&L reconcile would false-fail intentional changes)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # keep replayed dispositions/models out of the production trail
    from core.audit import configure_audit
    from ml.registry import configure_registry
    tmp = Path(tempfile.gettempdir())
    configure_audit(tmp / "liqbot_replaygate_audit.jsonl")
    configure_registry(tmp / "liqbot_replaygate_models")

    cfg = load_config(args.config)
    res = run_gate(args.recording_dir, replay_fn=lambda p: run_replay(cfg, p),
                   rel_tol=args.rel_tol, abs_tol=args.abs_tol,
                   max_recordings=args.max,
                   check_reconcile=not args.determinism_only)

    if res.status == "SKIP":
        print(f"{Code.XV_GATE_SKIP.value}: {res.reason}")
        return 0
    for d in res.details:
        line = (f"  {d['recording']}: determinism={d['determinism']} "
                f"reconcile={d['reconcile']}")
        if d.get("determinism_detail"):
            line += f" | {d['determinism_detail']}"
        if d.get("reconcile_detail"):
            line += f" | {d['reconcile_detail']}"
        print(line)
        if d["reconcile"] == "WARN":               # registered code on the disposition
            print(f"{Code.XV_RECONCILE_WARN.value}: {d['recording']} "
                  f"{d.get('reconcile_detail', '')}")
    if res.status == "PASS":
        print(f"{Code.XV_GATE_PASS.value}: {res.reason}")
        return 0
    # FAIL: surface the specific determinism / reconciliation codes
    for d in res.details:
        if d["determinism"] in ("FAIL", "ERROR"):
            print(f"{Code.XV_DETERMINISM_FAIL.value}: {d['recording']} "
                  f"{d.get('determinism_detail') or d.get('detail', '')}")
        if d["reconcile"] == "FAIL":
            print(f"{Code.XV_RECONCILE_MISMATCH.value}: {d['recording']} "
                  f"{d.get('reconcile_detail', '')}")
    print(f"replay gate FAILED: {res.reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
