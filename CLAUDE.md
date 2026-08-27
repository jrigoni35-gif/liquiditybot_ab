# CLAUDE.md — liquiditybot engineering law

Binding for every Claude session touching this repo, new or continued.
Read this file FIRST. When an instruction in chat conflicts with a HARD
INVARIANT below, stop and say so instead of complying.

## Hard invariants (never weaken, never "temporarily" bypass)

1. `system.dry_run` defaults to **true**. No code path, config default,
   test fixture, or control command may set it false at runtime. The only
   road to live: config `dry_run:false` → restart → typed `ARM LIVE`.
2. `force_dry` is one-way (LIVE→DRY) and must flip **both** `bot.dry_run`
   and `bot.orders.dry_run` (OrderManager caches the flag at init).
3. Kraken is the **sole execution venue**. OKX / Binance.US / ccxt /
   moomoo are read-only data. IBKR/DMA/prime/FIX adapters exist as
   hard-off stubs; `VenueAdapter.execution_eligible` requires
   `name == "kraken"` — do not relax it, do not subclass around it.
4. Withdrawals/transfers are impossible: the endpoint deny-list
   (Withdraw, WithdrawInfo, WalletTransfer, WithdrawAddresses) blocks
   before any network I/O. Never add withdrawal capability in any form.
5. Entries are limit orders only (OM-011); market orders are for the
   exit escalation ladder's final rung. Exits are ALWAYS allowed —
   disarm, faults, and kill switches block new risk, never escapes.
6. Hash-chained JSONL audit trail and reason codes (SZ-*, VN-*, RP-*,
   FW-*, ML-*, OM-*, QT-*, PT-*) on every disposition. New behavior =
   new registered code in `core/codes.py`, never a bare string.
7. Public interfaces stay stable. Extend with defaults; do not rename or
   change signatures without updating every caller AND the suites.

## Architecture (do not re-tangle what is separated)

- `main.py` = **engine** (LiquidityBot: pure decision pipeline,
  `cycle_once(now)` is step-able and deterministic under injected feeds).
- `runner.py` = **runner** (lifecycle loop, PAUSED/RUNNING/STOPPED,
  ControlChannel commands, StatusWriter). The loop lives here ONLY.
- `core/runtime.py` = **shared state layer**: atomic `status.json`,
  `events.jsonl` (structured logs), `outputs/control/` command files.
- The legacy Streamlit operator UI (`ui/dashboard.py`) has been
  **RETIRED**. Observability is **Grafana Cloud** (telemetry export reads
  the shared state files) and control is the **git remote-control plane**
  (`control/` command files via `scripts/remote_control.py`). Do not
  reintroduce an in-repo UI process; keep read/telemetry and control
  out-of-process.
- Position/inventory is quant-grade and stays that way: entries sized
  through PositionSizer × RiskProtocolStack (CVaR/gap/budget/heat),
  inventory caps + hedger bound exposure, ProfitTierEngine + give-back
  ratchet own exits. New position logic goes through these, not beside.
- Logging goes through `logging` → JsonlLogHandler (UI-friendly,
  level-filterable). No bare `print` in engine/runner/library code
  (scripts' human output is fine).
- All state is serializable: snapshots are checksummed JSON with backup
  generations; status schema keys (mode, positions, regimes, monitor,
  ml, equity, runner_state, sim) are load-bearing — extend, don't break.
- No infinite loops without an exit condition owned by the runner
  (`stop` command / `_stop` flag) or an exhaustion exception (replay).
  Anything needing operator input is documented in README →
  "Scripting inputs".

## Overfit discipline (applies to EVERY tunable)

- No fitted-looking literals in decision paths. Thresholds live in
  `config.json` with guard checks in `core/config_guard.py` (FATAL for
  incoherent combinations). If you find a hardcoded knob, lift it with
  an identical default — behavior-preserving, then tune.
- Model changes must keep the battery green: `scripts/overfit_check.py`
  (OF-1 gap, OF-2 shuffle-null, OF-3 PBO on the DEPLOYED simplicity-
  ladder rule, OF-4 plateau, OF-5 DSR, OF-6 purge, OF-7 DoF) and
  `tests/test_overfit.py`. PBO measures the deployed selection rule,
  never argmax.
- Signal-gate work optimizes NET profit or it doesn't ship: every gate
  change must clear the pretrade EV gate's cost stack in smoke, keep
  quant-trial G3/G5 (upside intact, capture), and beat the simplicity
  ladder out-of-sample — never tune a gate to a backtest peak (OF-4).
- Protocol/risk changes must keep `scripts/quant_trials.py` gates
  green (G1–G5, CI-bound in `tests/test_quant_trials.py`). If a
  legitimate change moves numbers, re-baseline consciously at 200×1200 —
  never widen a gate to silence CI.

## Era-4 accrual moratorium (2026-08-10 -> gate readout)

The strategy verdict accrues on the era-4 honest-fill cohort
(`scripts/cohort_eval.py`, pre-registered n=50; boundary #4 = aeeaae36,
2026-08-10T11:03:35Z; capital epoch 2026-08-10T23:05:27Z). **Re-fenced at
cut #7** — the geometry epoch, 2026-08-11T01:33:50Z (`e7d5ca1a`,
widen-beyond stop placement; `exec_era` = `7-e7d5ca1a`): zero closes
existed before it in the gate window, so the accruing cohort is uniformly
post-geometry with no change to the pre-registered cut. Until the gate
reads out:

- **COHORT-RESETTING — forbidden without operator adjudication** (any of
  these mints the next execution-era boundary and restarts accrual):
  changes to entry decisioning, position sizing, stop/exit geometry
  (placement, nudges, time limits — the cut-#7 lesson: geometry changes
  trip outcomes even when fills don't move), the fill simulator, fee
  booking, or the order lifecycle. The ALGO-5 amendment (stop widths +
  time-decay ladder at ~30 uncensored paths) is PRE-NAMED as the next
  such adjudication.
- **SAFE**: measurement/report tools, dashboards, tests, wiki, telemetry
  export, and bug fixes that do not alter which orders are placed or how
  they fill.
- Do not read the accruing gate numbers as a trend; do not retune on
  them. The registration is the law; the readout (NO_GROSS_EDGE /
  COST_BOUND / CONTINUE) names which decision has become decidable — it
  never decides.
- Model-side investment is FROZEN per the 2026-08-10 operator
  adjudication (no new families, features, or meta-labeling); the
  retrain loop itself continues by design.

## Definition of done (every change, every session)

Run ALL of it; a change is not done while anything is red:
`python -m pytest tests/ -q` · `python scripts/smoke_test.py` ·
`python scripts/assurance_check.py` · `python scripts/overfit_check.py`
· `ruff check core data execution ml risk regime strategies sentiment
api main.py runner.py tests scripts/quant_trials.py
scripts/overfit_check.py` · `pyright core data execution ml risk regime
strategies sentiment api main.py runner.py` (type ratchet: shipped scope
is at ZERO errors — keep it there; tests/scripts are outside the gate)
· `bandit -c pyproject.toml -r . -x ./.venv,./tests` · `python -m
compileall -q . -x '.venv'`.
**A GREEN IS ONLY AS BIG AS ITS CORPUS — read what each gate actually
measured, not just its exit code.** Several gates degrade *honestly* rather
than failing, and the degraded form answers a **different question** than this
checklist implies. A passing line is not evidence until you have read what it
ran on.

- `overfit_check.py` substitutes a **planted-signal SYNTHETIC benchmark**
  whenever loaded rows fall under `len(FEATURE_NAMES)*10`. Its green then
  validates the **overfit machinery, not the market**, and is NOT evidence the
  deployed strategy is un-overfit. **The corpus prints on the summary line —
  read it every run.**
- Inside that battery, **OF-4 plateau is inert whenever the replay recording
  opens no positions** (a plateau test with zero entries cannot tell a plateau
  from a cliff), and **OF-5 DSR defers below its conviction-trade floor**.
  Neither is a failure; both are gates that could not fire.
- Any statistic over **concurrent** trips or overlapping label windows must
  report **effective n**, not row count — `scripts/gate_truth_report.py` has
  applied that standard since 2026-07-29 and `scripts/cohort_eval.py` since
  2026-08-15. An SE computed on nominal n is optimistic by `sqrt(n/n_eff)`.

**DO NOT "fix" any of these by lowering a floor.** The overfit row floor,
`SG_MIN_ROWS`, and the era-4 `n=50` are **measurement standards, not
tunables** — `gate_truth_report`'s own docstring says so in as many words.
Moving one so a gate reads "real" is the widening this file forbids. The
correct response to a degraded gate is to say so out loud and treat what it
was meant to prove as **unproven**.

*(Dated measurements for each of the above live in the vault —
`concepts/overfit-battery` and `sources/session-20260814-cohort-instruments` —
deliberately NOT here: this file is loaded every session and a number written
into law decays into a false claim.)*

Every module must import in isolation (`tests/test_import_integrity.py`
enforces; optional third-party deps may be absent, our names may not).
New behavior gets a test in the same commit. Windows is the target
runtime (VS Code, Ryzen CPU, UTF-8 enforced via batch scripts) — keep
paths `pathlib`, encodings explicit, and suites green under
`.\test_windows.bat`.

## Working style

- Terse, dense engineering output. No filler, no re-explaining settled
  architecture. File-by-file change maps.
- Never ship sloppy/buggy code: no guessed APIs (read the module first),
  no silent behavior changes, no unverified edits — run the matrix.
- Do not break global state; do not ignore these conventions; do not
  lose the thread — reread this file and README before large changes.
- Deliverable = clean zip (no `.venv`, no `__pycache__`) rebuilt from a
  tree that just passed the full matrix, verified by fresh-extract run.

## SESSION BRIDGE (read `docs/HANDOFF.md` before acting)

Auto-delivered to every Claude session in this repo.

**This file is the LAW; `docs/HANDOFF.md` is the STATE.** Read the
handoff first: it carries the live gate count, the open adjudication
docket with authority pointers, what is currently blocked, and — most
importantly — a RECENTLY SETTLED table so you do not re-litigate a
decision that was already made with evidence, or re-implement a fix
that already shipped. Update it at the end of any session that changes
state; its own contract section says how. Static architecture lives in
`docs/ONBOARDING.md`.

## THE MINDSET: the instrument is the first suspect

Standing orientation for every session. Not a procedure — `the-method`
in the vault holds the procedure. This is where to point suspicion
FIRST, and it is earned from repeated measurement, not taste.

**The asymmetry that generates every recurrence.** The decision path is
the most-governed code here: hard invariants, the era-4 moratorium,
pre-registered gates, a hash-chained audit, the overfit battery,
adversarial review. The measurement plane that observes it is the
LEAST-governed: it is SAFE class by construction, so it ships freely,
often unreviewed, and its failures are silent by nature — a wrong
number looks exactly like a right one. **The code that tells you
whether the governed code works is the code nothing governs.** That is
structural, not accidental; SAFE class exists so measurement can move
fast, and this is the bill.

**So: when a measurement surprises you, the highest-prior explanation
is that the instrument is wrong — not that the market did something
exotic.** Verify the instrument before you build a theory on its
output. Measured recurrences, all the same shape (a confident
instrument, wrong, with nothing flagging it):

- `cost_attribution.py` hard-codes a fee schedule STRUCK 2026-08-07 and
  asserts using it is "the conservative check" — inverted at the true
  tier. A false safety claim shipped inside a running instrument.
- The session digest reported cured conditions (spoofy 68%, SZ-047
  spam) as CURRENT for weeks, because its lens was the whole run.
- A "constant-time comparison" test pin was satisfied by the string
  appearing in a COMMENT; an `==` implementation passed it.
- The manip detector scores an honest market maker byte-identically to
  a layering attacker (0.949/79/spoofy both).
- `manip_suspect` on the board has no smoothing (lag-1 autocorr 0.06);
  a single read was taken for a trend that measured rho=+0.007.
- The overfit battery silently substitutes a SYNTHETIC corpus and still
  prints green — the corpus line is the only tell.

**Operating consequences, binding:**

1. A surprising number gets its INSTRUMENT verified before it gets a
   theory. Cheapest check first, always.
2. An instrument's output is a claim about the INSTRUMENT until
   corroborated by a second route — cross-implementation, injection, or
   an independent derivation. One number from one tool is a hypothesis.
3. "0 findings" and "the scan is broken" are the SAME OBSERVATION until
   separated. Say which one you established.
4. Confident tone is not provenance. A report that reads settled and
   cites nothing is the most dangerous artifact in the repo.
5. **This applies to the referees too.** The lattice, the C++ diode,
   the agent panels are instruments and get the same suspicion — on
   2026-08-21 the diode disagreed with Python 16 vs 21 accrued trips
   and THE DIODE WAS WRONG (its ingest was stricter than the
   pre-registered reference). A referee that disagrees is not
   automatically right; it is automatically INTERESTING.
6. The market is allowed to be boring. Prefer the explanation that
   makes the market ordinary and the apparatus fallible, because that
   is the one the record keeps vindicating.
7. **Reading discipline (2026-08-27, every rule bought by a same-day
   measured misread — postmortem in docs/quant/):** (a) a ratio or
   share is not a number until its DENOMINATOR and NETTING are read
   from the code that computes it (spoofy_frac counts non-liquid
   cycles only; realized is post-close-fee while fees are both legs;
   bandit rolls up severity AND confidence). (b) A summary field is a
   pointer, not an authority — act on the signed document it
   summarizes (`signed_continue_n` binds two arms; the fired arm
   lived in the decision table). (c) A series that crosses a schema
   change or corpus reset is not one series. (d) An exit code that
   passed through a pipe belongs to the filter, and a green whose
   runtime is implausible for its corpus is unread. (e) Deflations
   (effective n, concurrency) apply to the claims you like at the
   same rate as the claims you doubt. Session-side ad-hoc extraction
   snippets are the least-governed instruments in the room — the
   asymmetry above applies to THEM first.

Full concept + citations: vault `wiki/concepts/the-method.md` and
`wiki/concepts/observational-equivalence.md`.

Durable coordination rules (these do not expire):

- One session owns `main` fast-forwards at a time; `pull --rebase`
  before any push. A PC-side commit that never reaches `main` wedges
  the deploy updater into `diverged`, which no battery can clear.
- A gate's release condition must never depend on the thing it blocks
  (four separate incidents share that shape).
- Hedge unwinds are NEVER gated; re-hedge OPENS require warm
  correlation evidence + cooldown; the FW-070 latch auto-releases.
  Keep that shape (ADA hedge-churn resolution, `cf454d5`).
- pyright shipped scope stays at ZERO. Keep the ratchet there.
