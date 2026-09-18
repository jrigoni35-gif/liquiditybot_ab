# AGENTS.md — liquiditybot engineering law

Binding for every agent session touching this repo (Kimi Code, Claude Code,
Codex, Cursor, OpenCode, …), new or continued. This file and CLAUDE.md are
the SAME law: Claude Code auto-loads CLAUDE.md, Kimi Code and other
AGENTS.md-aware CLIs auto-load this one. The bodies below this header are
kept identical — edit one and edit both in the same commit; an unpaired
edit is documentation drift.
Read this file FIRST. When an instruction in chat conflicts with a HARD
INVARIANT below, stop and say so instead of complying.

## Hard invariants (never weaken, never "temporarily" bypass)

1. `system.dry_run` defaults to **true**. No code path, config default,
   test fixture, or control command may set it false at runtime. The only
   road to live has **FOUR** steps, not three: delete the
   `outputs/force_dry.on` sentinel (or boot `--fresh`, which clears it) →
   config `dry_run:false` → restart → typed `ARM LIVE`.
   The sentinel step is not optional and is easy to miss because it fails
   SAFE and silently: `runner.apply_force_dry_sentinel` runs at boot BEFORE
   the engine reads `system.dry_run` and forces it true whenever that file
   exists, logging only `sentinel is a no-op this boot` while the config
   already says dry. **This box has carried that sentinel since
   2026-08-01** and has logged that line on every boot since; following the
   three-step version of this instruction here would not reach live, and
   the reason would not be obvious. `force_dry` moves one way only
   (LIVE→DRY) — see invariant 2.
2. `force_dry` is one-way (LIVE→DRY) and must flip **both** `bot.dry_run`
   and `bot.orders.dry_run` (OrderManager caches the flag at init).
3. Kraken is the **sole execution venue**. OKX / Binance.US / ccxt /
   moomoo are read-only data. IBKR/DMA/prime/FIX adapters exist as
   hard-off stubs.
   **The enforcement is a DENY-LIST in `main.py` (~:861), not the venue
   adapter.** If the feed handed to `OrderManager` is one of the real
   read-only venue classes — OKX / BinanceUS / Moomoo / WebData / Context /
   ccxt — engine construction RAISES `VN_ROGUE_EXECUTION`. `FeedRecorder`
   wraps the feed, so the check unwraps `_feed` first. Deliberately a
   deny-list and not an allow-list: the suite injects `SimpleNamespace` /
   `MockKraken` doubles and must keep constructing. Pinned three ways by
   `tests/test_cut10_boundary.py` — rogue refused, wrapped rogue refused,
   and an anti-rubber-stamp case proving doubles still work.
   **`VenueAdapter.execution_eligible` is NOT on this path** and this file
   named it as the enforcement until 2026-09-10. Re-derived that day:
   `execution_eligible` appears only in `execution/routing.py` and
   `execution/venue_adapters.py`, never in `main.py` / `runner.py` /
   `execution/order_manager.py`, and a full-range scan of all 87,640 audit
   records found ZERO `VN-*` of any kind. The router is constructed and never
   read. Cut #10 (B4) fixed the code after a 2026-09-05 measurement in which
   a live submit on a non-Kraken feed PLACED with a wire payload emitted —
   the invariant had rested on a default value — but the LAW kept citing the
   layer that had never guarded it. Do not relax the deny-list, do not
   subclass around it, and do not restore a claim that the adapter enforces
   this.
4. Withdrawals/transfers are impossible: the endpoint deny-list
   (Withdraw, WithdrawInfo, WalletTransfer, WithdrawAddresses) blocks
   before any network I/O. Never add withdrawal capability in any form.
5. Entries are limit orders only (OM-011); market orders are for the
   exit escalation ladder's final rung. Exits are ALWAYS allowed —
   disarm, faults, and kill switches block new risk, never escapes.
6. Hash-chained JSONL audit trail and a registered reason code on every
   disposition. New behavior = new registered code in `core/codes.py`,
   never a bare string. **`core/codes.py` is the registry and the only
   authority on which prefixes exist** — no count is written here on
   purpose. The enumerated list this replaces had drifted to a third of
   the real families, because a prefix list written into law goes stale
   the day someone adds one. Re-derive when you need it.
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

## Accrual moratorium — era-9 (cut #12, FEE-4: the row the account holds, 2026-09-08)

**History in one line each, all citable AS their era, none poolable across a
cut:** era-4 CLOSED (COST_BOUND n=54); cut #8's 40/80 premise SUPERSEDED;
cut #9 (`9-16ec821e`) fees 22/38 — read from the operator's app and RIGHT;
cut #10 (`10-a5acfe2d`, 2026-09-06) six verified defects + E1, which
re-booked 20/35 on a LEGACY-ladder premise (era-7, 2 closed trips); cut #11
(`11-6e584923`, 2026-09-07) the COMMIT configuration — hedger OFF, majors
only, $60 probes (era-8; its closing count is whatever
`scripts/cohort_eval.py` reports at the cut-#12 restart — no count is
written into law on purpose). Records: `docs/HANDOFF.md` ERA sections,
`docs/quant/`.

**Cut #12 — FEE-4** (`exec_era` `12-10d4d0c2`) was minted 2026-09-08 under
operator approval, verbatim: *"Re-book now … Yes do a reset."* The account's
fee tier, read three ways (Kraken-app screenshot: **Tier 5, 30-day spot
volume $69,652.65, AoP $822.24**; the venue's fee page as raw text;
`core/venue_fees.binding_row`, which reproduces the app's next-tier
distances to the cent), is **15/30 bps**. The booked 20/35 was Tier 4 —
cut #10's E1 had booked it on the word of a reference table that was
Kraken's legacy ladder (`docs/quant/2026-09-08_fee_ladder_correction.md`,
the-method recurrence #13) — and over-stated the round trip by 10 bps. Six
keys moved, the cut-#9/#10 cascade and nothing else: `pretrade` and
`order_manager` maker/taker 20/35 → **15/30**, `profit_taking.est_fee_bps`
35 → **30**, `ml.label_round_trip_cost_pct` 0.55 → **0.45**; derived entry
bar 0.6642 → 0.6381. No other KEY moved — universe, hedger OFF, skimmer
OFF, $60 floor, budget, time-stop, give-back, the model and the 0.35 heat
cap ("I'll just wait it out"). **But the barrier geometry moves with the
cost by construction**, as it did at cuts #9 and #10 and was not said then:
`ml/labeling.barrier_geometry` floors σ at `pt_cost_mult·cost/pt_mult`, and
that floor binds at any 5 m σ below cost/2 (the normal case), so the
label's PT falls **220 → 180 bps** and SL **165 → 135 bps** (σ_bar 0.10%);
the live bracket calls the same helper on `est_cost_bps`, and the
break-even/trail floor (`2·est_fee + buffer`) drops 76 → 66 bps — under the
same `label_era` name, which encodes the horizon only. dry_run STAYS true.
**The tier ROLLS** with the operator's real trading (Tier 3 on 08-29,
Tier 5 on 09-08; paper fills count toward nothing): book it from a fresh
reading at the boundary that adopts it, never chase it mid-era, re-read it
at every readout (`scripts/fee_drift_report.py --volume-30d <v> --aop-usd
<a>`) and name the drift. Decision record:
`docs/quant/2026-09-08_cut12_fee_rebook_adjudication.md` (§7 erratum);
stage `scripts/cut12_stage.py`; pins `tests/test_cut12_fees.py`.

**Era-9 accrual begins at the cut #12 runner restart**, from zero, on the
same pre-registered machinery (`scripts/cohort_eval.py` — untouched). Read
points are REGISTERED as at cut #11: **n=50 = the lean** (sign + CI, act
only if the CI excludes zero); **n=100 = the verdict** (CONTINUE iff net > 0
with CI excluding −fee; STOP on no-gross-edge or cost-bound — and STOP does
NOT revert to the hedged 12-asset book, which is the measured loss
channel). Expected under H0 (coin flip): −fee/trip ≈ −$0.27 at a $60
ticket, ≈ −$0.8/day at the ~3 entries/day observed on 09-08 (n=50 in
~2–3 weeks). The LONG BOOK (`long_book.enabled`, BTC/ETH accumulation with
12% thesis stops) shares the heat cap and the slot count with this book
and holds 2 of 5 slots at the cut; it is in no cut's "untouched" list and
is an operator docket item, not law. Until it reads out:

- **COHORT-RESETTING — forbidden without operator adjudication** (any of
  these mints the next boundary and restarts accrual): changes to entry
  decisioning, position sizing, stop/exit geometry (placement, nudges, time
  limits), the fill simulator, fee booking, the order lifecycle, the
  universe, the hedger, the probe ticket, or the heat cap. **The one thing
  not to touch during the run is anything.** Take-profit width (label PT
  180 bps at the cut-#12 cost floor — 220 at cut #10, "240" was cut #9's
  world — vs the majors' 36 h median oracle move of 132–178) is the
  PRE-NAMED next lever, deferred because the label-era name encodes the
  horizon only and a DELIBERATE width change would mix two geometries under
  one era; CONC-1 behind it. Other candidates live on the HANDOFF docket,
  never here.
- **THE PRICE OF A MINT — read this before calling one (added 2026-09-16).**
  This file enumerates exhaustively what IS cohort-resetting and, until this
  bullet, never once said what calling one COSTS. Twelve boundaries in 37.9
  days at a median 2.43-day interval is the measured behaviour of a system
  with an UNPRICED action: every other rule here assumes a boundary is rare,
  and nothing made it rare. A mint costs three things, all measured
  2026-09-16 and all AS-OF — re-derive with `scripts/discard_ledger.py`,
  `scripts/era_readout.py` and `scripts/cohort_eval.py`, never quote these:
  (1) **the accrual clock goes to zero** — 1 of 6 closed eras has ever
  reached the n=50 lean and **ZERO has ever reached the n=100 verdict**, the
  longest era ever run being 16.1 days against the ~26.6 a verdict needs;
  (2) **trips already banked leave the gate** — measured 77.9–78.2% of every
  trip carrying a stamp, by two independent reconstructions; (3) **trips in
  flight are CENSORED, at a rate that rises as eras shorten** — 11.1% lost at
  a 16.1-day era, 57.1% at 2.6 days, 83.3% at 2.2, 100.0% at 1.1. Rate and
  era length are NOT independent: a short era does not merely accrue less, it
  throws away most of what it did accrue.
  **THEREFORE, binding:** a mint must be JUSTIFIED IN WRITING against that
  price, in the same decision record that authorises it, and an era runs a
  **MINIMUM OF 14 DAYS** (the lean needs ~12.7–13.5 at the measured rate)
  before a discretionary boundary may be called. Exactly two things break the
  minimum — a **SAFETY INVARIANT** (hard invariants 1–7 above) and a **WRONG
  VENUE CONSTANT** making the bot trade on a false cost. Nothing else, and
  "we learned something interesting" is not a safety invariant.
  **Why this bullet exists:** four of the last five boundaries were fee
  re-bookings, and three of those were the MEASUREMENT PLANE correcting its
  own earlier misreading of a venue constant — not the strategy changing. The
  law did not require those resets; the absence of a price permitted them.
  Note the interaction with the fee rule above: the tier rolled Tier 3 → Tier
  5 in the ten days 2026-08-29 → 2026-09-08, so under the practice this
  bullet replaces, **the fee tier moves faster than a cohort can finish.**
  Deferring a known-wrong fee to the next boundary carries a real, named cost
  (~10 bps per round trip of conservative bias); carry it deliberately rather
  than paying the reset instead.
- **SAFE**: measurement/report tools, dashboards, tests, wiki, telemetry
  export, and bug fixes that do not alter which orders are placed or how
  they fill.
- Do not read the accruing gate numbers as a trend; do not retune on
  them. The registration is the law; the readout names which decision has
  become decidable — it never decides.
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
· `bandit -c pyproject.toml -r . -x ./.venv,./tests,./outputs` · `python -m
compileall -q . -x '(\.venv|\.claude)'`.
*(`./outputs` was added to bandit's exclusion on 2026-09-09: it is
gitignored runtime state and agent scratch — that day six High-confidence
findings, all in a measurement study's scratch scripts under
`outputs/reports/`, reddened the gate on a cut whose shipped code was
clean. A gate that reads a corpus nothing ships measures the wrong thing;
`tests/test_ofi_feature.py` and `tests/test_bracket_divergence.py` skip
`outputs` for the same reason.)*
*(`.claude` is excluded because agent worktrees live under
`.claude/worktrees/` and are checkouts of OTHER branches: measured
2026-09-05, the old `-x '.venv'` form compiled **510** files out of a
15-day-stale branch on every run, so a syntax error on a branch nobody
is deploying could redden this gate. `bandit` already excludes it. Use
`-f` when you actually want to see SyntaxWarnings — `compileall` skips
files with a current `.pyc`, which is how an invalid escape sequence
sat green in `tests/` until 2026-09-05.)*
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
- Inside that battery, **FOUR of the seven rungs can fail to arm — not two.**
  Mirror of `scripts/overfit_check.py`'s own summary block (read it there, it
  is the authority): **OF-1** is informational under exploration; **OF-3** is
  evidence-gated to a single family, which makes "PBO measures the deployed
  selection rule" *vacuous* while only one family qualifies; **OF-4** plateau
  is inert whenever the replay recording opens no positions (a plateau test
  with zero entries cannot tell a plateau from a cliff); **OF-5** DSR defers
  below its conviction-trade floor. None is a failure; all four are gates that
  could not fire. **The number to read is the ARMED count, never the exit
  code** — `passed 3, failed 0` reads identically whether seven gates fired
  and three passed or three fired and four were dark.
- Any statistic over **concurrent** trips or overlapping label windows must
  report **effective n**, not row count — `scripts/gate_truth_report.py` has
  applied that standard since 2026-07-29 and `scripts/cohort_eval.py` since
  2026-08-15. An SE computed on nominal n is optimistic by `sqrt(n/n_eff)`.

**DO NOT "fix" any of these by lowering a floor.** The overfit row floor,
`SG_MIN_ROWS`, and the cohort gate's `n=50` are **measurement standards, not
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
the most-governed code here: hard invariants, the accrual moratorium,
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

Seven dated incidents — a struck fee schedule asserting itself "the
conservative check", a digest reporting cured conditions as current, a
test pin satisfied by a comment, a detector scoring honest and hostile
flow byte-identically, an unsmoothed board number read as a trend, the
overfit battery's silent synthetic corpus, and the era-confounded veto
baseline (2026-08-27) — live with full citations in vault
`wiki/concepts/the-method.md` ("Measured recurrences" register). Read
them there before trusting any instrument this file governs.

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
   same rate as the claims you doubt. (f) *(2026-09-01, second measured
   instance)* A feature's skill against the triple-barrier label is
   TWO numbers, never one: RESOLUTION (did the path touch a barrier at
   all — volatility loads it, no edge) and DIRECTION (which barrier —
   the only channel that is an edge). A raw-label AUC is their blend;
   report both with day-block CIs before the word "signal" is used
   (vault `concepts/resolution-vs-direction-decomposition`).
   Session-side ad-hoc extraction snippets are the least-governed
   instruments in the room — the asymmetry above applies to THEM first.

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
