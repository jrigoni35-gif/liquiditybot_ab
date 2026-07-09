"""
scripts/session_digest.py

Reconcile a run's telemetry into one artifact an operator (or an agent picking
the work back up) can read first: outputs/session_digest.json (machine) and
outputs/session_digest.md (human). Answers "did it trade, did it make money,
and if not why not" by cross-joining audit.jsonl, events.jsonl, equity.csv,
state.json, signal_history.csv and postmortem_summary.csv, then running the
SD-* detectors in core/session_digest.py.

Read-only: never writes to the audit chain, never touches trading state.

Usage:
    python scripts/session_digest.py                 # reads ./outputs
    python scripts/session_digest.py --outputs DIR   # a saved run
    python scripts/session_digest.py --json           # print JSON to stdout
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.session_digest import render_markdown, write_digest  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default="outputs",
                    help="directory holding the run's telemetry files")
    ap.add_argument("--config", default="config.json",
                    help="config.json for the capital-coherence detector")
    ap.add_argument("--json", action="store_true",
                    help="print the digest as JSON instead of markdown")
    args = ap.parse_args()

    config = {}
    cfg_path = Path(args.config)
    if cfg_path.exists():
        try:
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            config = {}

    digest = write_digest(args.outputs, config)

    if args.json:
        print(json.dumps(digest, indent=2, default=str))
    else:
        print(render_markdown(digest))
        print(f"written: {Path(args.outputs) / 'session_digest.json'} "
              f"(+ .md)")
    # non-zero exit if any detector fired at error severity, so CI/automation
    # can gate on a broken run without parsing the report
    worst = digest["diagnostics"][0] if digest["diagnostics"] else {}
    return 2 if worst.get("severity") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
