#!/bin/bash
# SessionStart hook (Claude Code on the web only): make a fresh ephemeral
# container behave like the always-on home box.
#   1. install the bot's dependencies (idempotent; container state caches)
#   2. CODE CONTINUITY: fast-forward the working branch to origin. A hard
#      container restart can restore an OLDER filesystem snapshot (observed
#      2026-07-14: the checkout reverted a full day, which then made the
#      schema guard refuse every newer training bundle and truncated
#      outputs/ back to a stale 22-row set). Syncing code FIRST keeps the
#      code + training-data schema in lockstep for step 3.
#   3. LEARNING CONTINUITY: pull the paper-telemetry branch and import
#      every session bundle into outputs/ (checksums + audit chain + schema
#      verified by scripts/session_import.py; dedup makes re-runs no-ops),
#      so the bot resumes from the accumulated training rows and model
#      instead of cold-starting.
#   4. PROCESS CONTINUITY: relaunch the runner if none holds the
#      single-instance lock, so the bot never stays dark after a restart.
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

# --- code continuity (fast-forward only, best-effort, never fatal) --------
# FF-only never rewrites history and never discards uncommitted work; if the
# branch has diverged or the tree is dirty the merge simply declines and the
# hook carries on with whatever is checked out.
BR="$(git symbolic-ref --quiet --short HEAD || true)"
if [ -n "$BR" ] && git fetch origin "$BR" 2>/dev/null; then
  if git merge --ff-only "origin/$BR" 2>/dev/null; then
    echo "session-start: code fast-forwarded to origin/$BR"
  else
    echo "session-start: code already current or FF declined (kept local)"
  fi
fi

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

# --- process continuity: keep the bot alive across restarts ---------------
# If no runner holds the single-instance lock, relaunch it detached. This is
# idempotent: a live runner already owns the lock, so a race-launched second
# process would forfeit and self-terminate (RT-010) anyway - but the pgrep
# guard avoids even starting one. The GC/tailscale/moomoo sidecars carry
# session-specific secrets and stay operator-managed; the core decision
# engine must never depend on that to come back up.
if ! pgrep -f "python.*runner\.py$" >/dev/null 2>&1; then
  echo "session-start: no runner alive - relaunching detached"
  setsid nohup .venv/bin/python runner.py >> outputs/runner_stdout.log 2>&1 < /dev/null &
else
  echo "session-start: runner already alive - leaving it"
fi
