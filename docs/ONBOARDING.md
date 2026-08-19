# Onboarding — liquiditybot

> Deterministic, cost-aware paper-trading engine on Kraken data with a
> quant-grade risk stack, an audited learning loop, and a pre-registered
> evaluation gate. One bot, one PC, everything else is a console.

**Read order on day one:** `CLAUDE.md` (the law — hard invariants, the
era-4 moratorium, definition of done) → this file → `README.md`.
When chat/tickets conflict with CLAUDE.md, CLAUDE.md wins; stop and say so.

---

## What is this?

A Windows-resident trading bot that trades **paper only** (`system.dry_run`
defaults true; the only road to live is config + restart + a typed phrase
at the PC console). It places limit-order entries through a sizing/risk
stack, labels EVERY gate-confirmed signal (taken or vetoed) for learning,
and accrues evidence toward a pre-registered strategy verdict (the era-4
gate, n=50 honest-fill closes). Model investment is frozen until that
readout; the retrain loop itself keeps running by design.

- **Live state**: one always-on PC (`DESKTOP-OS02KQS`) is THE bot.
- **Observability**: Grafana Cloud (telemetry pushers read shared state
  files). No in-repo UI process — do not add one.
- **Control**: local `ControlChannel` command files, the git
  remote-control plane (`scripts/remote_control.py`, no open ports), and
  the VS Code bridge (`.vscode/tasks.json`).

## Quick start

| Tool | Note |
|---|---|
| Python 3.11+ (3.14 on the PC) | venv is mandatory; UTF-8 enforced |
| git | transport for telemetry AND remote control |
| C++17 compiler (optional) | only for the referee diode; everything else skips without it |

```
# Windows                      # POSIX / cloud
install.bat                    bash install.sh
start.bat                      .venv/bin/python runner.py
```

Verify: `python scripts/smoke_test.py` (219 checks), then open the
`.vscode/` tasks — `Bot: status snapshot`, `Definition of Done (full matrix)`.
Cloud/phone sessions: the SessionStart hook installs deps and imports
telemetry bundles automatically (`docs/PHONE_SESSIONS.md`).

## Architecture (do not re-tangle)

```
runner.py      lifecycle loop, PAUSED/RUNNING/STOPPED, ControlChannel   <- the ONLY loop
main.py        LiquidityBot engine: pure decision pipeline; cycle_once(now) is
               deterministic under injected feeds
core/runtime   shared state: atomic status.json, events.jsonl, control files
core/audit     hash-chained JSONL audit; ONE writer (the runner); reason codes in core/codes.py
data/          feeds: Kraken WS + REST (execution venue), OKX/Binance.US/moomoo/web (read-only)
regime/        macro/vol/liquidity classification (incl. the spoof/thin/liquid veto)
risk/          PositionSizer x RiskProtocolStack (CVaR/gap/budget/heat), inventory caps, hedger
strategies/    signal generation; every confirmed signal -> CandidateLabeler
ml/            triple-barrier labeling, walk-forward champion, Brier judge, drift
               governor, exploration probes, postmortems, model registry (hash-chained)
execution/     OrderManager (limit entries, exit ladder), fill ledger (exec_era stamps)
scripts/       ~60 operational tools: report lenses, gates, supervisor, remote control
diode/         C++17 referee (lb_diode.cpp) - independent re-computation of ground truths
tests/         ~3.9k tests; Windows is the target runtime
```

Key law points: Kraken is the sole execution venue (triple-gated);
withdrawals are deny-listed before network I/O; exits are ALWAYS allowed —
kill switches block new risk, never escapes; every disposition carries a
registered reason code (never a bare string); no fitted literals in
decision paths — knobs live in `config.json`, validated by
`core/config_guard.py`.

## The two standing fences (why your change may be refused)

1. **Era-4 accrual moratorium**: anything that changes which orders are
   placed or how they fill (entries, sizing, stop/exit geometry, fill sim,
   fees, order lifecycle) resets the verdict cohort and needs operator
   adjudication FIRST. Measurement, reports, tests, docs, telemetry = SAFE.
2. **Model freeze** (operator-adjudicated): no new model families,
   features, or meta-labeling until the era-4 gate reads out. The retrain
   loop continues; the schema does not grow.

Check accrual any time: VS Code task `Bot: era-4 accrual (n/50)` or the
`era4` field in the published `pc_status.json`.

## Definition of done (every change)

`pytest tests/ -q` · `scripts/smoke_test.py` · `scripts/assurance_check.py`
· `scripts/overfit_check.py` · ruff (scope in CLAUDE.md) · pyright
(shipped scope stays at ZERO) · bandit · compileall. One VS Code task runs
the sequence: **Definition of Done (full matrix)**.

**Read what each gate measured, not just its exit code.** Known honest
degradations: overfit battery substitutes a SYNTHETIC benchmark under its
row floor (its green then validates machinery, not market — the corpus
prints on the summary line); OF-4 is inert on zero-entry recordings; DSR
defers below its conviction floor. Four tests fail on Linux by design
(they exercise `cmd.exe` batch gates and Windows file locking); they run
green on the PC, whose pre-deploy battery is the authoritative gate.

## Deploy + coordination

- Deploy channel is pinned: work merged to **main** auto-deploys to the PC
  within ~15 min, battery-gated, then the runner restarts gracefully
  (`scripts/auto_update.py`; per-box override `LB_UPDATE_BRANCH`, never
  edit the tracked config on the box).
- One session owns main fast-forwards at a time; `pull --rebase` before
  push. Sessions develop on `claude/*` branches.
- Telemetry travels on the orphan `paper-telemetry` branch (bundles +
  `control/pc_status.json` + command queue). It is quarantined: never
  merged, deletable, carries no code.
- `state.json`/`status.json` NEVER travel — importing them would fork the
  one running book. Bundles carry records (fills, ledgers, corpus) which
  import as inert reports.

## The learning loop (one paragraph)

Signal → candidate (labeled even when vetoed — 97% of the corpus is
roads-not-taken) → triple-barrier outcome (h432) → dedup/purge/uniqueness
weighting (report n_eff, never row count) → walk-forward champion
(logistic today) → Brier judge vs base-rate null → drift/calibration
governor (alarms, never auto-tunes) → budgeted exploration probes buy new
labels → postmortem cause attribution → retrain. Referees (Python report
suite + the C++ diode) read the same ground truth independently and are
diffed against each other — see `docs/quant/2026-08-19_referee_lattice.md`
for why checking is mutual but feeding never is.

## Debugging quick hits

| Symptom | First move |
|---|---|
| "Why didn't it trade?" | `core/session_digest.py` output (`outputs/session_digest.md`), then `scripts/lessons_digest.py` |
| Bot seems frozen | `Bot: status snapshot` task; check `status_stale` in pc_status; single-instance lock in `outputs/runner.lock` |
| Gate/veto questions | `scripts/gate_efficacy_report.py` (grades every veto against counterfactual outcomes) |
| Learning questions | `scripts/learning_panel.py` (all 14 lenses, concurrent) |
| Fill/era questions | `scripts/cohort_eval.py`; C++ diode for an independent second opinion |
| Audit integrity | `verify_chain()` — NEVER `AuditTrail().verify()` (constructing the trail is a WRITE) |
| Logs | `outputs/runner.log` (rotated), `events.jsonl`; audit chain is `outputs/audit.jsonl` |

## Audience notes

- **New engineer**: run the matrix before and after any change; extend
  interfaces with defaults, never rename; new behavior = new test + (if it
  disposes) a new registered code. No bare `print` outside `scripts/`.
- **Senior**: the interesting subsystems are the risk stack
  (`risk/`), the honest-measurement machinery (n_eff, pre-registration,
  censoring notes in `scripts/cohort_eval.py`), and the referee lattice.
  Numbers in docs decay — dated measurements live in the operator's vault,
  deliberately not in law files.
- **Contractor**: your safe surface is `scripts/` report tools, `tests/`,
  `docs/`, and telemetry. ANY touch on `risk/`, `execution/`,
  `strategies/`, `ml/` feature schema, or `config.json` decision knobs
  goes through operator adjudication — ask first, cite the fence.

*Update this file in the same PR as any change that invalidates it.*
