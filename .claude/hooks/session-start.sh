#!/bin/bash
# SessionStart hook (Claude Code on the web only): make a fresh/ephemeral
# container behave like the always-on home box, and self-heal after a hard
# restart. On 2026-07-14 a restart restored a day-old filesystem snapshot:
# the checkout reverted to stale code (64-col schema), the bundle import
# refused every newer training bundle and truncated outputs/ to 22 rows, and
# the runner + sidecars died with nothing to relaunch them. Recovery was
# fully manual. This hook now makes each of those steps automatic.
#
# Design rule: every step is best-effort and idempotent, and NO single step
# may abort the ones after it — the runner relaunch at the end is the most
# important line in the file and must run even if pip, a fetch, or an import
# hiccuped. Hence `set -uo pipefail` WITHOUT `-e`; each step handles and logs
# its own failure instead of taking the whole hook down.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0   # home machines keep their own outputs/; nothing to do
fi
cd "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR must be set}" || exit 0

log() { echo "session-start: $*"; }
PY=.venv/bin/python

# --- 1. dependencies (conditional: skip the slow, network-bound path when
#        the deps already import — a flaky proxy must never wedge startup) ---
if [ ! -x "$PY" ]; then
  python3 -m venv .venv || log "venv create FAILED (bot may not start)"
fi
if ! "$PY" -c "import main" 2>/dev/null; then
  log "installing dependencies"
  "$PY" -m pip install -q --upgrade pip          || log "pip upgrade failed (continuing)"
  "$PY" -m pip install -q -r requirements.txt     || log "requirements install failed (continuing)"
  "$PY" -m pip install -q pytest ruff bandit      || log "tooling install failed (continuing)"
else
  log "dependencies already present - skipping pip"
fi

# --- 2. code continuity (fast-forward only, best-effort) -------------------
# FF-only never rewrites history and never discards uncommitted work; if the
# branch diverged or the tree is dirty the merge declines and we keep local.
# Runs BEFORE the import so code and training-data schema stay in lockstep.
BR="$(git symbolic-ref --quiet --short HEAD || true)"
if [ -n "$BR" ] && git fetch origin "$BR" 2>/dev/null; then
  if git merge --ff-only "origin/$BR" 2>/dev/null; then
    log "code synced to origin/$BR"
  else
    log "code already current or FF declined (kept local)"
  fi
fi

# --- 3 + 4. learning + process continuity ---------------------------------
# The data restore rewrites signal_history.csv, which would race the runner's
# own appends if it were already writing. So the heavy recovery (migrate +
# import + relaunch) fires ONLY when no runner is alive: a healthy resume is
# a clean no-op, a cold/crashed container is fully rebuilt. import is dedup-
# safe, so re-running it after a mere runner crash is harmless.
mkdir -p outputs
if pgrep -f "python.*runner\.py$" >/dev/null 2>&1; then
  log "runner already alive - healthy session, skipping data restore"
else
  # A rolled-back snapshot can leave outputs/signal_history.csv on an OLDER
  # schema than the (now fast-forwarded) checkout; session_import refuses to
  # merge across schemas, so lift the local file to the current schema first.
  # migrate_history is a verified no-op when the schemas already match.
  if [ -f outputs/signal_history.csv ]; then
    if "$PY" scripts/migrate_history.py --src outputs/signal_history.csv \
          --dest outputs/signal_history.csv 2>/dev/null; then
      log "local training file aligned to current schema"
    fi
  fi
  if git fetch origin paper-telemetry 2>/dev/null; then
    TDIR="$(mktemp -d)"
    trap 'rm -rf "$TDIR"' EXIT
    git archive origin/paper-telemetry | tar -x -C "$TDIR"
    shopt -s nullglob
    for bundle in "$TDIR"/sessions/*/; do
      "$PY" scripts/session_import.py --src "$bundle" --apply \
        || log "bundle $(basename "$bundle") refused (integrity/schema) - skipped"
    done
    log "learning continuity restored into outputs/"
  else
    log "no paper-telemetry branch yet - cold start"
  fi
  log "no runner alive - relaunching detached"
  setsid nohup "$PY" runner.py >> outputs/runner_stdout.log 2>&1 < /dev/null &
  log "runner relaunched (pid $!)"
fi

# --- 5. process continuity: telemetry pushers (optional, env-gated) -------
# The phone dashboard only survives a hard restart if its OTLP token does.
# Endpoint + tenant are NOT secrets, so bake correct defaults for this stack
# (us-east-3, metrics write-instance 1722437 — the value the OTLP connection
# page authorises; the datasource's read-side id differs and must NOT be used
# here). That leaves the TOKEN as the only secret, re-materialised below from a
# durable environment secret so a filesystem rollback that wipes the ephemeral
# scratchpad cannot silently 401 the feed. No secret is ever committed.
: "${GC_OTLP_URL:=https://otlp-gateway-prod-us-east-3.grafana.net/otlp/v1/metrics}"
: "${GC_INSTANCE_ID:=1722437}"
export GC_OTLP_URL GC_INSTANCE_ID
# Re-materialise the OTLP write token from the durable secret GC_OTLP_TOKEN
# (set as a Claude Code environment secret) into a stable 0600 file OUTSIDE the
# repo, so it is present on every cold start and never enters git. When the
# secret is absent we fall back to any operator-supplied GC_TOKEN_FILE.
if [ -n "${GC_OTLP_TOKEN:-}" ]; then
  TOKDIR="${HOME:-/root}/.liquiditybot"; mkdir -p "$TOKDIR"
  ( umask 077; printf '%s' "$GC_OTLP_TOKEN" > "$TOKDIR/gc-token" )
  chmod 600 "$TOKDIR/gc-token"
  export GC_TOKEN_FILE="$TOKDIR/gc-token"
  log "OTLP token materialised from durable secret"
fi
if [ -n "${GC_TOKEN_FILE:-}" ] && [ -s "${GC_TOKEN_FILE:-/nonexistent}" ] \
   && [ -n "${GC_OTLP_URL:-}" ] && [ -n "${GC_INSTANCE_ID:-}" ]; then
  if ! pgrep -f "[g]c_pusher\.py" >/dev/null 2>&1; then
    setsid nohup "$PY" scripts/gc_pusher.py >> outputs/gc_pusher.log 2>&1 < /dev/null &
    log "metrics pusher relaunched"
  fi
  if ! pgrep -f "[g]c_log_pusher\.py" >/dev/null 2>&1; then
    setsid nohup "$PY" scripts/gc_log_pusher.py >> outputs/gc_log_pusher.log 2>&1 < /dev/null &
    log "log pusher relaunched"
  fi
fi
