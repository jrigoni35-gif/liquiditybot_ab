# 2026-09-10 — Coupling and gate integrity

Built from the 2026-09-09/10 session. Every task below is traceable to a
measurement made in that session; none is speculative. Where a claim was
established by injection or mutation, that is stated — those are the ones not
to re-litigate.

**Branch:** `claude/markov-instruments` (NOT main; `main` is the deploy channel
of a running bot). Last commit `cea23515`.

**Standing constraints that shape every task here**
- Era-9 accrual is live. Anything touching entry decisioning, sizing,
  stop/exit geometry, the fill simulator, fee booking, the order lifecycle,
  the universe, the hedger, the probe ticket or the heat cap is
  COHORT-RESETTING and forbidden without operator adjudication.
- Model-side investment is FROZEN (2026-08-10 adjudication): no new families,
  features, or meta-labeling.
- `system.dry_run` stays true. Four-step road to live, sentinel included.
- Definition of done runs in full before any commit. A green is only as big as
  its corpus — read the ARMED count, not the exit code.

---


## EXECUTION STATUS — updated 2026-09-10 end of session

Commits on `claude/markov-instruments`; cut #12 went to `main` as its own commit
(`feea9612`) by operator decision, unbundled from this branch's work.

DONE, each mutation-verified:
  A1 A2   overfit gate + reason-code chain                  c915e043 ec08c3e9
  B0      resolved by cut #12 landing on main               feea9612
  C1      import fence, incl. the PEP 420 residual          8e0768c4 7a0e5459
  C3      stale prose + doc-currency pin                    a4218167
  C4a     cost-stack knobs the code silently clamps         66646687
  D5      test-skip census ratchet                          b841d5d9
  O1      all 4 scheduled tasks S4U + boot trigger          ab8c5640 (RUN)
  HYG-1   the four gate tools pinned                        bef0b023
  HYG-2/3 NUL + err1.log removed, *.log ignored             f9a0611f
  HYG-4   REFUTED - see below
  HYG-8   bandit ./outputs in all three runners             65db3158
  NEW-1   replay harness isolates the audit singleton       d5bcc633
          + quarantine/seam tool for the rows already there d8542e53
  T11     entry-sweep absorption counters (EN family)       32191298

FINDINGS THAT DID NOT SURVIVE RE-MEASUREMENT, recorded so they are not redone:

  * HYG-4 ("stop the daily task writing untracked reports into the tracked docs
    tree") read the situation BACKWARDS. Four fill-hazard reports and a
    signal-quality doc are already TRACKED - it is a deliberately versioned
    dated series. The only defect was that three were never committed (1c5f0426).

  * B0 "REVERSED - lost uncommitted work" was WRONG. The deleted
    `tests/test_config_guard_cost_basis.py` pinned a DUPLICATE check written and
    reverted in the same session (needle `cost basis split`, asserting
    `barrier_geometry` - strings cut #12's check never emits). Cut #12's own
    check is alive at core/config_guard.py:576 and pinned at
    tests/test_config_guard_fee_floor.py:272. Deleting it was correct. The
    finding inferred loss from surviving bytecode without checking WHOSE check
    it pinned.

  * T16 ("ml/registry.py ok=None fail-open silently accepted") is wrong on both
    counts. `verify()` DOES consult `verify_chain()` (:275); a broken chain
    returns ok=False with a CRITICAL ML-011 and refuses to treat the pedigree as
    evidence. `ok=None` happens only for an artifact with no pedigree at all and
    is NOT silent - **ML-061** warning (ML-060 means "artifact registered"; this line said ML-060 until red-team OBJ-16, 2026-09-12), documented as deliberate so a hand-trained
    model still loads. RESIDUAL, small: nothing AGGREGATES how often ok=None
    occurs, so "the champion has loaded with unknown provenance for three weeks"
    is invisible. **BUILT in the same commit that wrote this line (b6e1633a) - "Docketed, not built" was false the moment it shipped; red-team OBJ-16, conceded.**

STILL OPEN:
  T12   C5 fixture repair - THE BLOCKER, and larger than this plan estimated.
        Root-caused by line-tracing: absorption into ENTERED is exactly 0. The
        chain is drift -> fair-value lag -> watchdog + FW-050 (all three clear
        as drift -> 0, dose-response 277/148/56/40 bps max lag, rejects 45/9/0),
        and then the TERMINAL absorber is the fill simulator itself: 20 orders
        place, resting 50.4 bps out, where this repo's own calibrated hazard
        gives 0.12 expected fills. Zero fills is CORRECT behaviour, not a bug.
        Making the fixture open positions therefore needs near-touch quoting or
        a taker path - both touch decisioning and need operator adjudication.
        Two earlier hypotheses of mine died here: `_candles` forward-drift
        (planted the fix, INERT) and candle sigma driving the AS spread
        (REFUTED, 8x sigma reduction moved deviations 9 bps).
  T13   OF-4 axis - depends on T12
  T6    reason_chain_report pins
  T8    invariant-3 docs (the ONBOARDING half)
  T14   venue open-order reconciler (report-only first)
  T15   signal_history sidecar integrity
  Metamorphic couplings - blocked by T12, and PROVEN blocked: a replay-parity
  test written this session passed and then SURVIVED a real behaviour mutation
  (`_entry_rotation += 1`), because every outcome field is 0 in both arms. Any
  property built on this fixture passes for the wrong reason.

## BLOCKER — resolve before B-series or C-series can commit

### B0. `core/config_guard.py` is shared with cut-12's uncommitted work

**Measured.** `git diff --stat core/config_guard.py` = **159 insertions across
4 hunks**. Exactly one hunk (~65 lines, the label/live cost-basis check) was
written this session. The other three predate it and belong to the in-flight
cut-12 work, alongside 24 other uncommitted cut-12 paths including
`config.json`, `CLAUDE.md`, `core/fill_ledger.py` and five `test_config_guard_*`
files.

Consequence: `core/config_guard.py` and `tests/test_config_guard_cost_basis.py`
**cannot be committed without also committing another session's unfinished
work**, and staging a single hunk out of a file mid-cascade would produce a
branch state where `config.json` and its guard disagree about which cut is
booked.

**This is an operator decision, not an engineering one.** Options, in
increasing order of entanglement:

| Option | What it does | Cost |
|---|---|---|
| B0-a | Land the cut-12 work first (its own battery + commit), then commit the cost-basis check on top | cleanest; needs the cut-12 author's intent |
| B0-b | Move the cost-basis check into a NEW module (`core/config_coherence.py`) called from `validate()` — one-line touch to the shared file | near-clean; still one shared line |
| B0-c | Hold both files uncommitted until cut-12 lands | zero risk, zero progress |

**Do not proceed past this without a choice.** Everything in the C-series is
independent of it and can run meanwhile.

---

## A-series — commit what is already done and clean

These three files were created this session, are touched by nobody else, and
have passed their own suites plus mutation verification.

### A1. Commit the overfit gate work
- `scripts/overfit_check.py` — OF-5 abstention + arming ratchet + silent-synthetic guard
- `tests/test_overfit_arming_ratchet.py` — 21 pins

**Established:** exit contract is now `0` green / `1` a gate failed / `3` a
family that used to arm went dark / `4` silent synthetic substitution.
Mutation-verified: 6 pins go red when the branch is removed. The OF-5 time
bomb (28 conviction trades, arms at 30, `dsr_gate_reachable` proves
unsatisfiable for every n≥4) now abstains instead of failing forever, and
re-arms itself when a trial ledger makes `var_trial_sr` measurable.

**Verify:** `pytest tests/test_overfit_arming_ratchet.py -q` (21 passed) ·
`pytest tests/test_audit_ml_offline.py tests/test_overfit_check_ci.py tests/test_overfit.py -q`
(the suite that caught the first cut of this change) · full battery.

### A2. Commit the reason-code chain
- `scripts/reason_chain_report.py`

**Established:** 47 of 201 registered codes ever fire; 32/32 tested codes carry
information about their successor (so the chain is real, not a histogram); the
top three codes — all exploration/probe states — hold **86.4%** of long-run
reasoning time with self-loops of 95.0% / 95.9% / 99.5%.

**Verify:** run it (`RC=0`), confirm the Markov information test still reports
a non-empty informative set, confirm it is absent from decision code
(`tests/test_runtime_imports_no_scripts.py`).

**Not done in A2, deliberately:** wiring it into `learning_panel.py`'s ROUTES.
That file is clean, but adding a route while `RUNTIME_TREES` (task C1) is still
blind is the wrong order.

---

## C-series — defects found this session, independent of B0

Ordered by (value ÷ cost). C1 first because it is this session's own defect.

### C1. The import fence is blind to new top-level packages — MY defect
**Mutation-confirmed** by the review: `tests/test_runtime_imports_no_scripts.py`
scans a hardcoded 9-name `RUNTIME_TREES` tuple, and a `scripts/` import placed
in any directory outside it is invisible. A planted `import markov` in a
synthetic tree was not caught.

- Derive the runtime tree list rather than hardcoding it, or pin the tuple
  against the shipped package set so a new top-level package fails loudly.
- Keep the AST approach (a docstring naming a script must not trip it).

**Verify:** plant a new top-level package importing `scripts.util`; the guard
must go red. Restore byte-identical (`read_bytes`, never `read_text` — text
mode hides line-ending changes; that mistake rewrote `core/codes.py` earlier in
this session). **Risk: SAFE.**

### C2. Hard invariant 3 is held by a different mechanism than the law names
**Established by 39 passing tests plus an independent corroboration.** The
adapter / router / `config_guard` "triple gate" is **not on the live order
path**: `main.py:767` constructs `self.router` and never reads it;
`OrderManager` (`order_manager.py:176,910`) calls `KrakenFeed` directly;
`execution_eligible` is subclass-overridable and a `LiarAdapter` reaching the
wire is already demonstrated in `tests/test_verified_findings_batch2.py:270-287`.

Independent corroboration from this session's reason-code scan: **zero VN-
codes appear in 86,052 audit records**, against 5 registered. The venue layer
has never emitted a disposition, because nothing calls it.

What actually holds Kraken-sole-execution is a single hardcoded `KrakenFeed`
reference in `OrderManager` — real, BY-CONSTRUCTION, and **uncredited**.

- Correct the mechanism description in CLAUDE.md invariant 3.
- Pin the real one: a test asserting `OrderManager` holds exactly one feed and
  that no other feed type is reachable from `submit()`.

**Why this ranks high despite being documentation:** an ordinary, well-meant
refactor making `OrderManager` take a pluggable feed would pass every guard the
law currently names. **Risk: SAFE** (doc + one new test).

### C3. Stale prose in the two files a newcomer reads to learn the coupling
- `ml/labeling.py:39-41` — the docstring of `barrier_geometry`, the most-cited
  coupling in the repo — states the round-trip cost is "~1.2%". Live is
  **0.45%**. That is **2.7× wrong**, in the one place a newcomer looks.
- `docs/ONBOARDING.md:25-26` and `:106` name the accruing era as "era-6,
  exec_era 9-16ec821e, cut #9". Ground truth is **era-9, `12-10d4d0c2`,
  cut #12**.

Fix both. Prefer naming where to re-derive over writing a new number in — this
repo's single most-repeated failure is a confident stale figure.
**Risk: SAFE** (comments and docs only).

### C4. Two geometry levers that nothing classifies as geometry
`pretrade.adverse_selection_kappa` (0.35) has **no `config_guard` check at
all**; `pretrade.impact_eta` (0.8) is bounded only by `if < 0` — unbounded
above. Both are summands of `est_cost_bps`, which is the sigma-floor input to
the live bracket's `barrier_geometry` call, so **both set traded PT/SL width**.
Neither appears in `scripts/cut12_stage.py`'s EDITS list, so a cut does not
consider them.

- Add range guards in the same idiom as `label_pt_cost_mult`.
- Add both to the geometry-key list a cut must consider.

**Depends on B0** (same file). **Risk: SAFE** (validator only).

### C5. The offline replay fixture opens zero positions
**Established:** `make_offline_recording()` → `run_replay()` on the shipped
cut-12 config yields `entries_filled: 0`. Consequences, both already visible:
OF-4's plateau rung reports "parameter inert on this recording" for all three
parameters, and any replay-derived gate compares zero to zero.

**This blocks the metamorphic-coupling work** (permute asset order → identical
decisions; raise cost → PT widens monotonically). Those properties over a
zero-entry replay would pass vacuously — three more green lights measuring
nothing.

- Make the fixture open positions (a recording that clears the entry bar).
- Then, and only then, add the metamorphic properties.

**Risk: SAFE** if the fixture is test-only. **Check carefully** that it does not
touch the shipped replay path used by `auto_update`'s deploy gate.

---

## D-series — larger, needs its own adjudication

### D1. Venue open-order reconciliation
The one genuinely load-bearing gap against the industry. Nautilus ships
`ExecutionEngine.reconcile_state`; LEAN calls `Brokerage.GetOpenOrders()` at
init. Here `KrakenFeed.get_open_orders()` **is implemented and has zero
production callers** (double-derived).

Consequence: the bot's picture of what rests at Kraken can only shrink toward
truth, never toward reality. A `CancelOrder` returning `None` (rate limit, 5xx,
error payload) increments `cancel_unconfirmed`, audits OM-090, and forces the
order terminal locally while it may still rest at the venue.

Shape: call it at live boot and on a slow cadence; diff venue txids against
`OrderManager._orders`; venue-only → new registered ORPHAN code + alert.

**Risk: touches the order lifecycle → COHORT-RESETTING.** Report-only
reconciliation (log the diff, change nothing) is SAFE and is the right first
step.

### D2. OF-5's real repair
The abstention in A1 is correct but is a holding action. The repair is a
`var_trial_sr` **measured** from per-trial Sharpe; `trial_ledger` v0.1 records
none. Until then OF-5 abstains and says so.

### D3. Unkeyed integrity digests
`core/audit.py:63`, `ml/registry._record_hash`, `core/persistence.py:687` are
all bare `sha256` with no key. Anyone who can write the file can recompute a
self-consistent chain over tampered content — the MLSEC-1 shape, re-confirmed
by injection this session (deleting `registry.jsonl` makes `verify()` return
`ok=None`, which is not `False`, so ML-011 fails open).

### D4. `signal_history.csv` has no integrity coupling
No hash, no chain, no per-row attestation. `ml/contracts.py` range-screens
FEATURES; the label columns are unscreened. Corpus poisoning is undetectable.

### D5. Skip census
26 test files carry `skipif`/`skip`. Nothing pins how many should skip, so
`4950 passed / 9 skipped` and `4950 passed / 17 skipped` are byte-identical at
the exit code. Same class as the arming ratchet in A1 — pin the inventory.

---

## O-series — operator only, cannot be done from a session

| | Item | Why it needs you |
|---|---|---|
| O1 | Run `scripts/fix_scheduled_tasks.ps1` **elevated** | All four scheduled tasks are `LogonType=Interactive`, so logging off stops the bot **and** the KeepAlive watchdog that would restart it. Measured: a **21-hour outage** (09-08 19:25 → 09-09 16:28) with exactly one audit record in the window — the boot. S4U registration was refused with "Access is denied". |
| O2 | Smart App Control | `WinError 4551` blocks the unsigned C++ diode intermittently — it passed in two battery runs and failed in two others on the same tree. **The definition of done is non-deterministic on this box.** |
| O3 | Two unmerged cloud branches | `claude/remote-control-wlsi28` (hedger fail-safe + SWEEP-0, self-labelled SAFE but the hedger is on the cohort-resetting list) and `claude/flow-pos-analysis-monitor-cojqog` (+4,561 lines, vendored MIT skills) |
| O4 | Cut-12 completion | 24 uncommitted paths; blocks B0 |

---

## Execution order

```
B0 (decide)  ──────────────┐
                           ├─→ C4  ─→ (config_guard work)
A1 → A2                    │
  │                        │
  └─→ C1 → C2 → C3 ────────┘
            │
            └─→ C5 ─→ metamorphic couplings
                  │
                  └─→ D1 (report-only first)
```

A-series and C1–C3 are unblocked and independent of B0. C5 gates the
metamorphic work. D1 is the biggest real gap but wants its own adjudication.

## Definition of done for every task here

`pytest tests/ -q` · `smoke_test.py` · `assurance_check.py` · `overfit_check.py`
· ruff · pyright (shipped scope at zero) · bandit · compileall — **capturing
each return code directly, never through a pipe.** A pipe hands back the
filter's exit code; that laundered a pytest usage error into a green earlier in
this session.

Each new guard must be **mutation-verified**: break the fix, watch the pin go
red, restore byte-identical with `read_bytes`. A pin that cannot fail is worth
nothing — one written this session was vacuous until an audit caught it.
