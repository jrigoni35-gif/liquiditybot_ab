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
