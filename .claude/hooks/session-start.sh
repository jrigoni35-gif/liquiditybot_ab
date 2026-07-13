#!/bin/bash
# SessionStart hook (Claude Code on the web only): make a fresh ephemeral
# container behave like the always-on home box.
#   1. install the bot's dependencies (idempotent; container state caches)
#   2. LEARNING CONTINUITY: pull the paper-telemetry branch and import
#      every session bundle into outputs/ (checksums + audit chain + schema
#      verified by scripts/session_import.py; dedup makes re-runs no-ops),
#      so the bot resumes from the accumulated training rows and model
#      instead of cold-starting.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0   # home machines keep their own outputs/; nothing to do
fi
cd "$CLAUDE_PROJECT_DIR"

if [ ! -f .venv/bin/activate ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python -m pip install -q pytest ruff bandit

if git fetch origin paper-telemetry 2>/dev/null; then
  TDIR="$(mktemp -d)"
  trap 'rm -rf "$TDIR"' EXIT
  git archive origin/paper-telemetry | tar -x -C "$TDIR"
  shopt -s nullglob
  for bundle in "$TDIR"/sessions/*/; do
    python scripts/session_import.py --src "$bundle" --apply \
      || echo "session-start: bundle $bundle refused (integrity/schema) - skipped"
  done
  echo "session-start: learning continuity restored into outputs/"
else
  echo "session-start: no paper-telemetry branch yet - cold start"
fi
