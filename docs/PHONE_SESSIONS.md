# Phone / cloud sessions — how satellite work flows home

Sessions started from a phone (Claude Code on the web) run the bot in an
**ephemeral cloud container**: the repo is cloned fresh, `outputs/` lives
only as long as the container, and everything not exported is gone when
the session is reclaimed. This document is the contract that makes that
work durable — and keeps the operator's own machine ("home") the sole
authority over what gets adopted.

## The two lanes

| What | Travels as | Proof-read at home by |
|---|---|---|
| Code changes | `claude/*` branch -> pull request | normal PR review + the full test matrix (CLAUDE.md "definition of done") |
| Learning data (labeled training rows, audit chain, digests, reports) | session bundle on the **`paper-telemetry`** orphan branch | `scripts/session_import.py` (verify -> plan -> `--apply`) |

Live runner state never travels in either lane: `state.json` /
`status.json` describe one running ledger and importing them elsewhere
would fork the book. The export tool refuses to bundle them.

## The continuity loop (no matter which device)

Both devices feed and drink from the SAME stream — one code line
(`main`), one data branch (`paper-telemetry`):

- **Cloud session starts** → the SessionStart hook
  (`.claude/hooks/session-start.sh`, registered in
  `.claude/settings.json`) installs dependencies, fetches
  `paper-telemetry`, and imports every bundle into `outputs/` before any
  work begins. The bot resumes from the accumulated training rows and
  adopts the bundled `meta_model.json` when it has none — never a cold
  start after the first session.
- **Cloud session runs** → hourly export pushes the growing bundle back
  to `paper-telemetry`.
- **At home** → import bundles with `session_import.py` (below); export
  after a home run with `session_export.py` so the next phone session
  consumes what home learned. The trained model travels copy-if-absent:
  a machine that already has `outputs/meta_model.json` keeps its own and
  retrains from the merged rows; only a machine with no model adopts the
  bundled one.

## Session side (automated in-session)

```
python scripts/session_export.py --dest /tmp/bundle --label 20260713-shift \
    --refresh-digest
```

Bundles `signal_history.csv`, `audit.jsonl`, `equity.csv`, the session
digest, check-in log, postmortem summary and overfit report, plus a
`manifest.json` carrying sha256 checksums, row counts by source, the
git SHA and the config hash. The bundle is committed to the
`paper-telemetry` orphan branch under `sessions/<label>/`.

`paper-telemetry` deliberately shares no history with `main` (the
`.gitignore` law — runtime telemetry never enters code history — holds:
the branch is a quarantined side channel, never merged, deletable at any
time without touching code history).

## Home side (the proof-read, operator-driven)

```
git fetch origin paper-telemetry
git worktree add ..\bot-telemetry paper-telemetry     # once
python scripts\session_import.py --src ..\bot-telemetry\sessions\<label>
```

Plan-only by default. The import refuses outright when: a checksum
mismatches (tampered/corrupt bundle), the audit hash-chain fails to
replay, or the history schema differs from this checkout's
`FEATURE_NAMES` (schema drift routes through
`scripts/migrate_history.py`, never silent padding). Otherwise it prints
what would merge — new rows vs duplicates (keyed by `position_id`) —
and waits.

```
python scripts\session_import.py --src ... --apply
```

backs up the local `signal_history.csv` into `outputs/archive/`, appends
only the new rows, and files the bundle's reports under
`outputs/imported_sessions/<label>/`. Re-applying the same bundle is a
no-op. Retrain whenever the merged rows warrant it:
`python scripts/train_meta.py` gated by `scripts/overfit_check.py`.

## Mirroring the unattended-shift watchdog at home (Windows)

The cloud shift runs the same supervision stack that works natively on
Windows. Two Task Scheduler entries reproduce it:

1. **Revival** — every 10 min: `.venv\Scripts\python.exe scripts\keepalive.py`
   (working dir = repo root). Armed only while `outputs\keepalive.on`
   exists; delete that file before an intentional stop.
2. **Deep audit** — hourly: `scripts\run_checkin.bat` (pauses new entries
   on critical findings; exits are never blocked).

`core/watchdog.py` (feed staleness / PnL-velocity quarantine) is always
on inside the engine and needs no scheduling.

## Home runbook (Windows) — full parity in ~15 minutes

One-time setup on the PC, in order:

1. **Bot**: clone the repo, run `install.bat`, then `start.bat`
   (dashboard opens locally; bot starts in DRY RUN as always).
2. **Adopt the cloud learning**: fetch the telemetry branch and import -
   see "Home side" above. If the import reports a schema mismatch, run
   the `migrate_history.py` command it prints, then re-import.
3. **Watchdog** (Task Scheduler, two entries, see previous section):
   keepalive every 10 min + `run_checkin.bat` hourly; create
   `outputs\keepalive.on` to arm revival.
4. **Phone dashboard** (Tailscale, no repo config changes - the
   loopback hardening in `.streamlit/config.toml` stays exactly as is):
   - install Tailscale on the PC and sign in (same account as the phone)
   - in PowerShell: `tailscale serve --bg 8501`
   - the dashboard is now `https://<pc-name>.<tailnet>.ts.net` from any
     of your tailnet devices, TLS included. Phone on the same Wi-Fi
     connects directly (single-digit ms); on LTE typically 30-80ms.
   - `tailscale serve --https=443 off` disables it; the serve config
     survives reboots otherwise.
5. **Optional - moomoo equities context**: install the OpenD gateway,
   log in, leave it running (port 11111), `pip install moomoo-api` in
   the venv. The bot auto-detects it on the next poll; without it the
   `equity_risk_z` feature simply stays neutral.

Cloud sessions and the home bot then share one code line (`main`) and
one learning stream (`paper-telemetry`), with the phone able to watch
either dashboard through the same private tailnet.

## Grafana Cloud (phone dashboard, no tailnet required)

The primary phone view is a Grafana Cloud stack fed by
`scripts/gc_pusher.py`, a sidecar that reads `outputs/status.json`
every 30s and posts OTLP gauges. The bot never knows it exists;
Streamlit remains available locally but is not served anywhere.

- **Dashboard source of truth**: `docs/grafana/liquiditybot_dashboard.json`
  (uid `liquiditybot-ctrl`). Import/update via the HTTP API
  (`POST /api/dashboards/db`, service-account token) or the UI.
  Stored metric names match the pusher's exported names exactly
  (`liquiditybot_equity`, `liquiditybot_ml_history_rows`, ...): the
  pusher sends an EMPTY unit because Grafana's OTLP translator appends
  `_ratio` to unit-"1" gauges, which would mislabel raw counts. Every
  query carries `{job="liquiditybot"}` (set from service.name).
- **Pusher** (either machine, venv python):
  set `GC_OTLP_URL`, `GC_INSTANCE_ID`, `GC_TOKEN_FILE` (a chmod-600
  file holding the OTLP write token — never committed), then run
  `python scripts/gc_pusher.py`. One instance at a time is plenty.
  It also exports `liquiditybot_status_age_sec` stamped with wall-clock
  time, so a frozen runner (status file no longer advancing) is visible
  even while `runner_state` still reads RUNNING.
- **Event log → Loki** (`scripts/gc_log_pusher.py`, same env vars):
  tails `outputs/events.jsonl` into the stack's Loki via the same OTLP
  gateway (`/otlp/v1/logs`), offset-persisted and rotation-safe, so the
  full reason-coded event history is searchable from the phone
  (`{service_name="liquiditybot"} |= "ML-071"` in Explore). The
  dashboard's "Event log" section shows warnings and the live stream.
- **Alerts** (provisioned in the stack, folder `liquiditybot`):
  `telemetry stale or down` (status age > 180s for 5m, and NO DATA —
  a dead pusher — also fires) and `manipulation suspicion high`
  (any asset's `manip_suspect` > 0.9 for 10m). Both route to the
  stack's default contact point — set an email/push target there once
  and every rule uses it.
- **moomoo over the tailnet**: when OpenD runs on the PC, share it with
  `tailscale serve --bg --tcp 11111 tcp://127.0.0.1:11111`; a cloud
  container (userspace tailscaled, no TUN) reaches it via
  `python scripts/tailnet_forward.py --tailscale <bin> --socket
  <ts.sock> --dest <pc-100.x-ip> --port 11111`, which makes
  `127.0.0.1:11111` work exactly as the feed expects.
