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
# THE PROBE MUST COVER WHAT THE SUITE NEEDS, NOT JUST THE ENGINE (2026-09-03).
# `import main` alone was STRUCTURALLY BLIND to the dependency whose absence
# actually bricks the battery: tests/test_dependency_hygiene.py forbids pandas
# at engine scope ON PURPOSE, so `import main` is GUARANTEED never to touch it.
# The two rules are each correct and jointly blind. Measured cost: a container
# reported "dependencies already present", and `pytest tests/` then collected
# 4,541 tests and ran ZERO - "Interrupted: 3 errors during collection", rc=2.
# So the probe now asks the engine AND the analysis stack separately, and says
# which is missing instead of claiming readiness it never checked.
#
# pandas/pyarrow/polars stay OUT of requirements.txt deliberately - engine
# scope must not depend on them (that is the hygiene rule) - but they belong
# in the venv, which tests/test_dependency_hygiene.py's own docstring states:
# "it ships in the venv for offline analysis". Absent, ~51 tests skip and
# scripts/rpe_factor.py's --self-test cannot run at all.
_need_engine=0; _need_analysis=0
"$PY" -c "import main" 2>/dev/null || _need_engine=1
"$PY" -c "import pandas, pyarrow, polars" 2>/dev/null || _need_analysis=1
if [ "$_need_engine" = 1 ]; then
  log "installing engine dependencies"
  "$PY" -m pip install -q --upgrade pip          || log "pip upgrade failed (continuing)"
  "$PY" -m pip install -q -r requirements.txt     || log "requirements install failed (continuing)"
  "$PY" -m pip install -q pytest ruff bandit      || log "tooling install failed (continuing)"
fi
if [ "$_need_analysis" = 1 ]; then
  log "installing analysis stack (scripts/tests scope; NOT requirements.txt)"
  "$PY" -m pip install -q pandas pyarrow polars   || log "analysis stack install failed (continuing)"
fi
# Report what is ACTUALLY importable now - a readiness line that was never
# checked is the artifact this whole block exists to stop producing.
_eng=missing; _ana=missing
"$PY" -c "import main" 2>/dev/null && _eng=ok
"$PY" -c "import pandas, pyarrow, polars" 2>/dev/null && _ana=ok
if [ "$_eng" = ok ] && [ "$_ana" = ok ]; then
  log "dependencies ready (engine ok, analysis stack ok)"
else
  log "dependencies INCOMPLETE - engine=$_eng analysis=$_ana; the suite will \
run in DEGRADED form (optional-dep tests skip). This line is the warning."
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
if pgrep -f "python.*runner\.py( |$)" >/dev/null 2>&1; then
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
    # Import NEWEST bundle FIRST (by manifest created_at_utc). Row merge is
    # order-independent (append-only union, dedup by position_id), but the
    # trained model is adopted copy-if-absent - so without newest-first order
    # a stale older bundle's meta_model.json would win over a fresher one.
    for bundle in $("$PY" - "$TDIR/sessions" <<'PYSORT'
import glob, json, os, sys
base = sys.argv[1]
def ts(d):
    try:
        with open(os.path.join(d, "manifest.json"), encoding="utf-8") as fh:
            return json.load(fh).get("created_at_utc", "")
    except Exception:
        return ""
for d in sorted((g for g in glob.glob(os.path.join(base, "*/"))),
                key=ts, reverse=True):
    print(d)
PYSORT
    ); do
      "$PY" scripts/session_import.py --src "$bundle" --apply \
        || log "bundle $(basename "$bundle") refused (integrity/schema) - skipped"
    done
    log "learning continuity restored into outputs/ (newest bundle first)"
  else
    log "no paper-telemetry branch yet - cold start"
  fi
  # ONE-BOT architecture (operator directive 2026-07-17): the PC is THE bot;
  # this cloud environment is the dev bench + remote console. No cloud runner
  # is launched by default — set LB_CLOUD_RUNNER=1 for a local test runner.
  if [ -n "${LB_CLOUD_RUNNER:-}" ]; then
    log "no runner alive - relaunching detached (LB_CLOUD_RUNNER set)"
    setsid nohup "$PY" runner.py >> outputs/runner_stdout.log 2>&1 < /dev/null &
    log "runner relaunched (pid $!)"
  else
    log "one-bot mode: cloud runner retired (PC is the bot; LB_CLOUD_RUNNER=1 opts back in)"
  fi
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
# Fallback for a container PAUSE (not a full rebuild): the session-scratchpad
# token path carries a per-session UUID the hook can't rediscover, but a token
# persisted to the stable ~/.liquiditybot/gc-token survives a pause. Recover
# from it when no durable GC_OTLP_TOKEN secret is configured, so a resume
# self-heals the feed instead of leaving the dashboard dark (2026-07-15: a 6h
# idle-pause left the pushers unrelaunched because the token env was gone).
if [ -z "${GC_TOKEN_FILE:-}" ] \
   && [ -s "${HOME:-/root}/.liquiditybot/gc-token" ]; then
  export GC_TOKEN_FILE="${HOME:-/root}/.liquiditybot/gc-token"
  log "OTLP token recovered from persisted ~/.liquiditybot/gc-token"
fi
# Grafana push OWNERSHIP: the metric series is single-instance by design
# (job="liquiditybot", no host label — see scripts/gc_pusher.py). The always-on
# PC (scripts/pc_supervisor.py) owns that series; a cloud session pushing at the
# same time would interleave both bots' samples into one garbled line. So the
# CLOUD does NOT push by default. Set GC_CLOUD_PUSH=1 (env secret) to let a cloud
# session own the feed instead — e.g. when the PC is offline. This gate does not
# touch the PC: its supervisor launches the pushers independently of this hook.
if [ "${GC_CLOUD_PUSH:-0}" = "1" ] \
   && [ -n "${GC_TOKEN_FILE:-}" ] && [ -s "${GC_TOKEN_FILE:-/nonexistent}" ] \
   && [ -n "${GC_OTLP_URL:-}" ] && [ -n "${GC_INSTANCE_ID:-}" ]; then
  if ! pgrep -f "[g]c_pusher\.py" >/dev/null 2>&1; then
    setsid nohup "$PY" scripts/gc_pusher.py >> outputs/gc_pusher.log 2>&1 < /dev/null &
    log "metrics pusher relaunched (GC_CLOUD_PUSH=1)"
  fi
  if ! pgrep -f "[g]c_log_pusher\.py" >/dev/null 2>&1; then
    setsid nohup "$PY" scripts/gc_log_pusher.py >> outputs/gc_log_pusher.log 2>&1 < /dev/null &
    log "log pusher relaunched (GC_CLOUD_PUSH=1)"
  fi
else
  log "cloud Grafana push disabled (GC_CLOUD_PUSH!=1) — the PC owns the series"
fi

# --- 6. learning DURABILITY: checkpoint training rows to paper-telemetry ---
# The restore in step 3 only recovers rows as fresh as the last PUSH. This
# sidecar (scripts/telemetry_backup.py) exports + pushes the growing bundle on
# an interval, tied to the bot's lifecycle so it can't stall the way an
# external scheduled trigger does when the session dies.
# Working-tree-safe (isolated worktree) and fail-safe by design.
#
# ONE WRITER PER BUNDLE LABEL (ISO-1, 2026-09-03). The sidecar exists to
# protect rows THIS box generated. Since the 2026-07-17 one-bot directive the
# cloud launches no runner, so it generates NONE — its outputs/ is a pure
# RECONSTRUCTION of what it imported. Measured 2026-09-03: the local corpus,
# the pc-live bundle and the cloud-mirror bundle were ALL exactly 23,586 rows;
# the mirror carried zero rows the PC lacked. So re-exporting the PC's own
# corpus under a second label bought no durability — and it cost isolation,
# because every cloud container hard-coded the SAME label 'cloud-mirror' and
# `hostname` is 'vm' in all of them. N containers therefore raced ONE branch
# path, last-writer-wins (measured: three pushes in ten minutes, only one of
# them this container's; docs/quant/2026-09-03_workspace_isolation.md §3).
# The 2026-07-18 label split separated cloud from PC; it never separated
# cloud from cloud.
#
# So the sidecar now follows the same flag as the runner it exists to protect,
# and when a runner IS opted in the label carries a per-container suffix so
# two opted-in containers cannot collide either. Escape hatches unchanged:
# LB_BACKUP_DISABLED=1 forces off, LB_BACKUP_DRYRUN=1 bundles without pushing,
# LB_BACKUP_LABEL overrides the name; LB_BACKUP_FORCE=1 runs the sidecar
# without a cloud runner (for a session that deliberately generates rows).
if [ "${LB_BACKUP_DISABLED:-}" = "1" ]; then
  log "learning-durability sidecar OFF (LB_BACKUP_DISABLED=1)"
elif [ -z "${LB_CLOUD_RUNNER:-}" ] && [ -z "${LB_BACKUP_FORCE:-}" ]; then
  log "one-bot mode: learning-durability sidecar retired - no cloud runner, so this box generates no rows to protect and the PC owns pc-live (LB_CLOUD_RUNNER=1 or LB_BACKUP_FORCE=1 opts back in)"
elif pgrep -f "[t]elemetry_backup\.py" >/dev/null 2>&1; then
  log "learning-durability sidecar already alive - leaving it"
else
  # Per-container label: a shared constant is what made N writers invisible.
  # Persisted under ~/.liquiditybot (outside the repo and outside the bundle
  # allow-list) so it survives a container PAUSE and stays ONE label per box.
  if [ -z "${LB_BACKUP_LABEL:-}" ]; then
    _IDF="${HOME:-/root}/.liquiditybot/backup-label"
    if [ ! -s "$_IDF" ]; then
      mkdir -p "$(dirname "$_IDF")"
      printf 'cloud-%s' \
        "$(od -An -tx1 -N4 /dev/urandom 2>/dev/null | tr -d ' \n')" > "$_IDF"
    fi
    LB_BACKUP_LABEL="$(cat "$_IDF")"
    # an unreadable/empty id file must never silently become the old shared
    # constant - fall back to a per-process name instead of colliding
    [ -n "$LB_BACKUP_LABEL" ] || LB_BACKUP_LABEL="cloud-$$"
  fi
  setsid nohup env LB_BACKUP_LABEL="$LB_BACKUP_LABEL" \
    "$PY" scripts/telemetry_backup.py \
    >> outputs/telemetry_backup.log 2>&1 < /dev/null &
  log "learning-durability backup sidecar relaunched (label $LB_BACKUP_LABEL)"
fi
