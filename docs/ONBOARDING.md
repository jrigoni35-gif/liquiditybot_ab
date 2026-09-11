# Onboarding — liquiditybot

> Deterministic, cost-aware paper-trading engine on Kraken data with a
> quant-grade risk stack, an audited learning loop, and a pre-registered
> evaluation gate. One bot, one PC, everything else is a console.

**Read order on day one:** `CLAUDE.md` (the LAW — hard invariants, the
accrual moratorium, definition of done) → `docs/HANDOFF.md` (the STATE —
live gate counts, the open adjudication docket, standing fences, and a
RECENTLY SETTLED table so you do not re-litigate a decision already made
with evidence) → this file → `README.md`.
When chat/tickets conflict with CLAUDE.md, CLAUDE.md wins; stop and say so.
CLAUDE.md is law, HANDOFF is state; **this file is orientation only — on
any live number, both of those outrank it.**

---

## What is this?

A Windows-resident trading bot that trades **paper only** (`system.dry_run`
defaults true; the only road to live is config + restart + a typed phrase
at the PC console). It places limit-order entries through a sizing/risk
stack, labels EVERY gate-confirmed signal (taken or vetoed) for learning,
and accrues evidence toward a pre-registered strategy verdict (the cohort
gate, n=50 honest-fill closes). **Which era is accruing is not written here**
— this passage named era-6 / `9-16ec821e` / cut #9 for three cuts after it
stopped being true (corrected 2026-09-10; ground truth at the time was
`12-10d4d0c2`). Read it from the code that stamps it, which cannot go stale:

```
python -c "from core.fill_ledger import EXEC_ERA; print(EXEC_ERA)"
python scripts/cohort_eval.py        # the accruing count, per era
```

The ERA sections of `docs/HANDOFF.md` carry each era's history and its
minting cut. Era-4 is CLOSED: it read out **COST_BOUND at n=54**
(`docs/quant/2026-08-26_why_losing_deep_dive.md`). Model investment is
frozen by the **2026-08-10 operator adjudication**, which carries no gate
condition and was NOT lifted by that readout; the retrain loop itself
keeps running by design. (Era names move with every cut — re-derive,
never recall: `python -c "from core.fill_ledger import EXEC_ERA;
print(EXEC_ERA)"`.)

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

Verify: `python scripts/smoke_test.py` — its last line prints
`passed N, failed 0`; that line IS the check count, which is why none is
written here. Then open the `.vscode/` tasks — `Bot: status snapshot`,
`Definition of Done (full matrix)`.
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
scripts/       operational tools: report lenses, gates, supervisor, remote control
diode/         C++17 referee (lb_diode.cpp) - independent re-computation of ground truths
tests/         the suite; Windows is the target runtime
```

**Sizes are commands here, not numbers.** Every count this file used to
hardcode had drifted; a count in a doc is a claim that decays silently, so
each one below is the command that prints it instead. Run it — do not cite
this table's existence as the answer.

| what | re-derive with |
|---|---|
| operational tools in `scripts/` | `ls scripts/*.py \| wc -l` |
| tests in the suite | `python -m pytest tests/ -q --collect-only \| tail -1` |
| smoke checks | `python scripts/smoke_test.py` (last line) |
| assurance checks | `python scripts/assurance_check.py` (last line) |
| learning-panel lenses | `python scripts/learning_panel.py --list` |
| live execution era | `python -c "from core.fill_ledger import EXEC_ERA; print(EXEC_ERA)"` |

Key law points: Kraken is the sole execution venue — enforced by a DENY-LIST at `main.py` ~:861 that refuses to construct the engine if a read-only venue class reaches `OrderManager` (`VN_ROGUE_EXECUTION`), NOT by `VenueAdapter.execution_eligible`, which is not on that path (re-derived 2026-09-10: zero `VN-*` in 87,640 audit records, and the router is constructed and never read);
withdrawals are deny-listed before network I/O; exits are ALWAYS allowed —
kill switches block new risk, never escapes; every disposition carries a
registered reason code (never a bare string); no fitted literals in
decision paths — knobs live in `config.json`, validated by
`core/config_guard.py`.

## The two standing fences (why your change may be refused)

1. **Accrual moratorium** (the accruing era is whatever
   `python -c "from core.fill_ledger import EXEC_ERA; print(EXEC_ERA)"`
   prints — this line named a stale one for three cuts, so it names none):
   anything that changes which orders are placed or how they fill
   (entries, sizing, stop/exit geometry, fill sim, fee booking, order
   lifecycle) MINTS THE NEXT EXECUTION ERA, restarts accrual from zero,
   and needs operator adjudication FIRST. Measurement, reports, tests,
   docs, telemetry = SAFE. The era number advances at every cut — read
   CLAUDE.md's moratorium heading for the live one, not this sentence's
   memory of it.
2. **Model freeze** — authority is the **2026-08-10 operator
   adjudication**: no new model families, features, or meta-labeling.
   **This fence has NO gate condition and no expiry.** A cohort readout
   does not lift it: era-4 already read out (COST_BOUND at n=54) and the
   freeze stands unchanged. Only a further operator adjudication lifts
   it. The retrain loop continues; the schema does not grow.

**Reading accrual — a live trap.** The VS Code task is still labelled
`Bot: era-4 accrual (n/50)` and `pc_status.json` still publishes an
`era4` field, but that counter belongs to the CLOSED era-4 trigger and
**is not era-scoped and never was**: `era4_trips()` selects on five
predicates and `exec_era` appears in none of them, so its total pools
cuts #7/#8/#9 into one cohort. Informational only — it is not a cut-#9
readout. For the era actually accruing, run `python
scripts/cohort_eval.py` and read its **PER-ERA SEGMENTATION** block,
which marks the current era and counts only trips lying WHOLLY inside it
(a trip that opened in one era and closed in another is counted in
neither — that is the moratorium's "nothing pooled across the cut", not a
rounding choice). Equivalently by hand: freeze a copy of
`outputs/fills.csv`, then filter `era4_trips(<snap>)` to trips whose
`eras` list is exactly the current stamp. **Never cite an accruing count
from memory** — snapshot-stamp it, or read `docs/HANDOFF.md`, which
carries the value with its stamp.

## Definition of done (every change)

`pytest tests/ -q` · `scripts/smoke_test.py` · `scripts/assurance_check.py`
· `scripts/overfit_check.py` · ruff (scope in CLAUDE.md) · pyright
(shipped scope stays at ZERO) · bandit · compileall. One VS Code task runs
the sequence: **Definition of Done (full matrix)**.

**Read what each gate measured, not just its exit code.** Known honest
degradations: overfit battery substitutes a SYNTHETIC benchmark under its
row floor (its green then validates machinery, not market — the corpus
prints on the summary line); OF-4 is inert on zero-entry recordings; DSR
defers below its conviction floor. The tests that encode Windows-only
semantics (`cmd.exe` batch gates, NT file-locking on rename) are pinned
`skipif(os.name != "nt")` or platform-SPLIT rather than left to fail off
Windows — `tests/test_battery_gate.py`, `tests/test_child_log_rotation.py`;
list them with `grep -n "os.name" tests/*.py`. They are UNSKIPPED on the
PC, whose pre-deploy battery is the authoritative gate. A skip is not a
pass: a green suite on Linux has measured strictly less than the PC's.

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

Signal → candidate (labeled even when vetoed — the corpus is dominated by
roads-not-taken; the `disp` column in `outputs/signal_history.csv` carries
the refusal code, and a bare share quoted without stating how `disp`'s
blanks were treated is not a measurement) → triple-barrier outcome
(h432 — `config.json:label_max_bars`) → dedup/purge/uniqueness
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
| Learning questions | `scripts/learning_panel.py` (every lens, concurrent; `--list` names them) |
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
