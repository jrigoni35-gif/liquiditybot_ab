---
title: liquiditybot
category: entity
summary: "A deterministic, cost-aware crypto market-making and signal bot running in paper mode — it executes NO real bids/positions; every fill, fee and dollar is simulated (the paper/real boundary is the project's central relation) — governed by hard invariants and an assurance spine. CURRENT REGIME since 2026-08-10T23:05:27Z: the operator-adjudicated $800 stressor (goals $100/mo with the RP-072 x1.5 ladder, venue floors unscaled so the $15 ticket is 1.9% of equity), model-side investment FROZEN behind the pre-registered era-4 gate readout (0/50), cohort-resetting changes fenced by the accrual moratorium. ECONOMIC BOTTOM LINE as of 2026-08-09 (all pre-epoch, pre-boundary-#4 numbers): over ~250 closed positions gross P&L before ANY fees is −11.66 (~−$0.05/trade ≈ 0) against 382.59 of fees — fees 32.8x |gross|, 100% of the −394.25 all-in loss is costs, and three unrelated instruments (OOF AUC 0.43–0.48, Brier 0.24728 vs 0.25, MFE median 0.18% vs ~0.65% cost) corroborate gross edge ≤ 0 — confirmed the same day by a second independent method (full-book fills reconstruction, −13.01 over 394 round trips). RISK LANE, same day: the sizer had been reading an attribute PortfolioState does not have, so three risk controls were inert and ALL failed permissive (tickets 13.7% larger than designed) — fixed in 1fee174e; and the all-in P&L statement is honest for the first time (a6334162), 49% of lifetime fees having appeared in no readable number. PROFESSIONAL READ, 2026-08-09 evening: identified as a MACHINE in seconds on mechanics (modal ticket exactly $18.00 x51, after-win/after-loss size ratio 1.000, 0.0% round-number landing, 100% limit 1019/1019, 59 holds at exactly 5.000s, zero empty hours) yet ECONOMICALLY INDISTINGUISHABLE from an unprofitable retail human (58.3% win rate on 0.670 payoff, 2.20x disposition effect) — a geometric, not psychological, bias; the algorithmic verdict is per-trade gross edge -0.0019% at t=-0.332 with fees 368x |edge| in percent space, a 0.91h median winner against 0.71% round-trip cost, and 60.6% taker fills on a maker-thesis book. The hedge book is the buried half: 159 round trips, ZERO profitable net of fees, -$325.70 on $39,460 notional (4.5x the entry book), invisible to both the performance ledger and the circuit breaker; and 77.3% of ALL lifetime fees were spent in 25 minutes by one churn bug. SELECTION ARCHITECTURE (2026-08-11 audit, verdict MIXED): no candidate leaderboard exists — entries are a round-robin over _entry_assets (main.py:3911-3921) — with per-asset regimes/features/vol-scaled stops/breakers/caps under a GLOBAL meta-model and gate thresholds; the bracket cost floor flattens the majors to identical 1.50/2.00 sl/pt while FLOW/ARB/MINA differentiate, and ETH/BTC fill concentration is gate-confirmation frequency (gate_confidence flat 0.81-0.90), not preference; the operator's backwards-derivative claim was REFUTED (NO-INVERSION-FOUND, 0/3 adversarial refuters — the *_dir features are side-relative, not inverted)"
tags: [system, hub, paper-mode, economics, behavioral]
sources: 29
updated: 2026-08-16
---

# liquiditybot

The subject of this vault. A crypto trading engine trading a handful of pairs on a single execution
venue, currently in **dry-run paper mode**.

## Identity
> "A deterministic cost-aware execution engine that produces **numbers**" — the self-definition used to
> distinguish it from LLM trading scaffolds that produce text.

> **THE central relation (operator directive 2026-08-07, governance rule 13): the bot executes
> NO real bids or positions.** Every fill, fee, queue, latency and markout is simulated
> (dry_run, fill-at-limit RNG, config-constant fees); the corpus rehearses real-money
> discipline on simulated execution — *that is the point*. Every conclusion about this system
> states which side of the boundary its evidence comes from, and sim-conditioned numbers are
> never venue truth. **[[concepts/paper-real-boundary]]** — read it before quoting any dollar
> figure on this page.

## Structure
- **Engine** — a pure decision pipeline whose cycle is step-able and deterministic under injected feeds.
- **Runner** — the lifecycle loop, control channel, and status writer. The loop lives only here.
- **Shared state layer** — atomic status file, structured event log, control command files.

Observability is an external dashboard reading the shared state files; control is an out-of-process
command plane. There is deliberately no in-repo UI process.

## The seven hard invariants
1. Dry-run defaults **true**; the only road to live is a config change, a restart, and a **typed
   ceremony phrase**.
2. The force-dry command is **one-way** and must flip both cached copies of the flag.
3. **One execution venue.** All other venues are read-only data; adapters for other venues exist as
   hard-off stubs and the eligibility check must not be relaxed.
4. **Withdrawals are impossible** — an endpoint deny-list blocks before any network I/O.
5. **Entries are limit orders only**; market orders exist only as the final rung of the exit ladder.
   **Exits are ALWAYS allowed** — kill switches block new risk, never escapes.
6. **Hash-chained audit trail and registered reason codes on every disposition.** New behavior means a
   new registered code, never a bare string. *(2026-08-05: the model registry `registry.jsonl` was
   found to carry the adjective without the property, and was rebuilt on `core/audit.py`'s
   construction — `4799bfc7`. **A shared adjective is not a shared property** —
   [[comparisons/stated-invariants-vs-audited-reality]].)*
7. Public interfaces stay stable; extend with defaults.

## Operating posture
Every change must pass a full matrix — tests, smoke, assurance, the
[[concepts/overfit-battery]], lint, a zero-error type gate, and a security scan — and every module must
import in isolation. Windows is the target runtime.

## Overfit discipline
No fitted-looking literals in decision paths; thresholds live in config with guard checks that are
FATAL on incoherent combinations. **"If you find a hardcoded knob, lift it with an identical default —
behavior-preserving, then tune."** Signal-gate work "optimizes NET profit or it doesn't ship."

## Current standing problem
**Payoff asymmetry** ([[concepts/payoff-asymmetry]], measured 2026-08-02, post-quarantine n=217
per-fill on a 637/637 audit-crossref-CLEAN ledger): win rate 57.1% is fine, but the payoff ratio
is 0.561 against 0.750 needed — the average loser is ~1.8x the average winner, and break-even is
impossible (p > 1) at every real fee schedule. The lever is exit geometry; cost levers are
necessary but not sufficient. The earlier cost/sigma framing
([[synthesis/the-money-path-thesis]]) is corrected in part — it was fed by fabricated fills that
made P&L wrong by 27x ([[concepts/default-path-fallback-writes]]); the payoff-asymmetry diagnosis
survived a second, residual quarantine unchanged (commit `483f6727`).

Two decisive nulls landed late on 08-02 ([[sources/session-20260802-digest]] second addendum):
the **random-entry MFE control** shows **no entry-timing signal** (real entries' mean MFE
percentile 0.516 [0.439, 0.594], n=51 vs 200 seeded matched controls each), and the
pre-registered **48-combo geometry search** finds **no bracket with positive expectancy** (best
mean −0.400%, lower bound −1.124%) — **exit design can minimize bleed, not create edge**.

One deliberate experiment is in flight: the 432-bar horizon migration at **17/50**
pre-registered closed trades as of 2026-08-05 — **first win recorded** (post-432 win rate
**5.9%, Wilson [1.0%, 27.0%]** — still unreadable) — **hold all geometry until the cohort
fills** ([[comparisons/horizon-96-vs-24-bars]]).

**Honest fills (2026-08-02 follow-on, commit `8e5455e8`, battery green):** the fill simulator's
`passive_base_prob` moved 0.45 → **0.048**, the XV-021 measured market trade-through rate
(22,854 resting-limit trials, Wilson [0.046, 0.050]) — the sim no longer fills resting orders
9x too often. **Paper entry rate will drop sharply; that IS the honest rate** — a starving
paper book under honest fills is a truthful outcome
([[synthesis/risk-posture-doctrine]]). The commit is an **execution-regime boundary inside the
432 cohort**; fee constants stay deliberately conservative at 25/40 bps vs Kraken's 16/26
(overstating cost is the safe direction — [[concepts/cost-truth]]).

**Repo state (2026-08-03):** ~~the 08-02 stall (seven local-only commits)~~ — **resolved:
pushed, head = remote = `d67fd6a5`, deploy chain fully live.** First honest-fills day measured:
**~8 positions/day vs ~16 before**, exits flowing (2 stale-loser purges incl. a 100h ETH
position; `tb_time` verticals firing), equity **$4,930.79**, `fills.csv` at 655 rows with zero
fixture signatures, single ERROR since restart = ML-032 retrain request at 37% feature drift
(expected, the day after the fill-regime change). One telemetry incident found and fixed: a
duplicate `gc_log_pusher` pair shipped every log line to Grafana Cloud twice for ~22h —
[[concepts/liveness-by-output-cadence]], [[sources/session-20260803-bug-sweep]].

**Repo state (2026-08-04):** main at **`242568fb`**, local == origin. First-ever deploy-gate
rejections: [[entities/auto-update]] red-rejected the first externally-pushed commits
(`4d56d0e0` price anchors, `c66fa836` dependency hygiene) twice, deterministically, on a
**location-variant test** — a substring path filter colliding with the gate's outputs-nested
worktree; root-caused and fixed same day ([[concepts/location-invariant-tests]],
[[sources/session-20260804-deploy-gate]]). Full battery **GREEN on the merged tree** (3292
passed / 1 skipped, smoke 219, assurance 49, ruff, compileall). Corpus migrated **87 → 89
cols** (`entry_price`/`exit_price` price anchors, 9,358 rows, zero features padded —
[[entities/historystore]]); from this deploy **every new labeled row carries its price
anchors** (legacy rows padded 0 = absent-forever; bookkeeping, never a feature). Deploy
confirmed: **runner relaunched, pid 9212 live on `242568fb`**; the `auto_update` dirty stamp
was transient (the uncommitted-fix window); the 15-min reject loop is ended. Equity
**$4,931.69** (2026-08-04); the honest-fills regime continues.

**Late 2026-08-04:** the realized-outcome loop is **proven working end-to-end in production** —
`ml.gate_stats.realized_closed` moved **0 → 1** on the first organic post-restart close
(`note_realized` credited it; gates → `order.meta` → position → close → era-keyed ledger;
`realized_active` correctly False, 1/25 toward activation) — the 08-03 watch item adjudicated:
the earlier zero was old-runner entries carrying no gates, as hypothesized
([[sources/session-20260804-deploy-gate]] §6). Price anchors **proven live**: 27 new corpus
rows carry real `entry_price`/`exit_price`, corpus **9,385 rows and growing anchored**. Cohort
**15/50**; equity **$4,932.05**; ~5 fill rows since morning under the honest-fills cadence.

**Tooling (2026-08-04, commit `b824a854` pushed, battery 3292/1 green):**
[[entities/mythos-router]] (v1.23.0) registered as a **project MCP** in `.mcp.json` beside
coinpaprika, under the standing **tooling-only boundary — the runtime never consumes MCP**.
Its Strict-Write-Discipline receipts cover **AGENT file actions**, complementing the
hash-chained `audit.jsonl` (**ENGINE actions**); it replaces nothing. A per-box write policy
(`.mythos/policy.json`, gitignored) **BLOCKs** `outputs/**` + `config.json` + `.git` —
never-delete-learning-data as machine policy — and requires **CONFIRM** on engine trees and
scripts ([[sources/session-20260804-mythos-router]]).

**Status (2026-08-05):** the post-432 cohort recorded its **first win** — **17/50** closed,
win rate **5.9%, Wilson [1.0%, 27.0%]** (was 0/15); the verdict is still refused, correctly.
The realized gate ledger is **accruing**: `realized_closed` **3** (was 1),
`realized_base_rate` **0.3333**, **3/25 toward activation**. Corpus **9,422 rows, 64
price-anchored** (was 27 — [[entities/historystore]]). `fills.csv` at **668 rows** (+8/day —
the honest-fills cadence steady at the measured rate). Equity **$4,931.73**, flat; deploy
chain current at **`b824a854`**; runner **pid 9212 healthy**. Watch item, not defect:
**ML-032 feature drift grew 37% → 40%** — the governor keeps requesting retrain and the
champion bar keeps refusing worse challengers; expected after the fill-regime change and
should resolve as post-change rows accumulate, but the deployed model is **increasingly
mismatched to the current fill regime** ([[entities/ml-governor]]).

Same day, **report-only**: the telemetry stack was audited end to end — scorecard **≈80/100**,
taxonomy the strength (95), dark metrics and the unmeasured gate→order funnel the gaps;
nothing changed, priorities filed as owed items 26-28
([[sources/telemetry-stack-audit]], [[entities/observability-sidecars]]).

Also same day, **report-only**: a read-only python-expert debugging deep-dive swept the full
engine (26 files at head `b824a854`) — **8 ranked findings (2 high / 3 medium / 3 low)**, 3
near-misses verified OK, HTML/timezone/sim-fill surfaces explicitly clean. Headlines: the
replay family is the **8th unfixed instance** of the QA-writes-production class
([[concepts/default-path-fallback-writes]]); `train_meta.py` does an unguarded stale
read-modify-write of the live `state.json`; week-close is not crash-atomic (double reserve
refill window); the 432-bar × 200-slot candidate pool saturates and evicts the newest signal.
Report-only as filed, then **adjudicated and shipped the same day — 7 of 8 fixed** in
`e7ebbf60` + `b409a24b`, 29d deferred per the 432 hold ([[sources/session-20260805-debug-sweep]]).

**Evening 2026-08-05 — head = remote = `4799bfc7`, five battery-green commits**
([[sources/session-20260805-evening]]; final battery **3376 passed / 1 skipped**, smoke 219,
assurance 49, ruff + compileall clean):

1. **`bc198aa5` — boards redesign, operator-ordered.** command → **"trading desk"** (exchange-style:
   money, positions & risk, geometry economics — the payoff-ratio tile now carries the **0.75
   break-even threshold** rather than borrowing the profit-factor scale); execution →
   **"models · learning · execution"**; screening → **"screening & market"**; problem_solution gains
   the **AUDIT & TELEMETRY INTEGRITY** row, **boarding the dark audit-health metrics and the
   `07d38a51` KNOWN-GAP `gate_divergence` instrument for the first time** — owed item 26 (a)+(b)
   closed. Glass skin, palette, HIG passes and **UIDs all preserved**; generator only
   ([[entities/observability-sidecars]]).
2. **`46cdc19a` — three residual edges, found by an ADVERSARIAL review of the same day's own
   fixes.** Round-1 verdict: **all seven hold.** Residue: `fills.csv` could still be born
   **headerless** (DictReader adopts a FILL as the header and every consumer misparses the whole
   ledger — same book of record as the 27x error); `gc_log_pusher` saved new-generation offsets
   under the **old inode**; the brand-new `gate_divergence` panel **collapsed its per-gate series
   under a bare `max()`**, hiding the trend it exists to show.
3. **`f3253f0d` — the five HIGH findings of debug round 2** (27 findings across 5 parallel area
   agents + an adversarial pass): a remote emergency command **acked but never run** for ~2 min
   after every deploy bounce; `take_deferred` with **zero production callers**, so a 100% close
   after a filled preempted maker take **sells the position twice**; failed `CancelOrder`
   **orphaning live GTC venue orders** while the healthy bot's own deadman refresh prevents the
   venue backstop from firing (new code **OM-090**); the **CLI deploy gate scoring in-sample**
   while the champion is scored OOS (optimism 25–150% of the deploy margin, always
   pro-challenger); and a **deploy-seam race that permanently rejected a good model** as tampered
   ([[comparisons/stated-invariants-vs-audited-reality]], [[entities/ml-governor]]).
4. **`717b2e39` — PAXG and the tangible-value gradient.** Gold opened as a **tangible investment**
   and `regime/haven.py` encodes the ladder **PAXG > BTC > ETH > ALTS**, report-only, pinned by a
   parsed-AST test. Its falsifiable prediction was **measured on live Kraken bars and held**:
   realized 5m vol ranks exactly down the ladder (**PAXG 0.075% < BTC 0.093% < ETH 0.120% ~ SUI
   0.116% < ARB 0.160%**). Costs one discretionary skimmer slot (`max_extra` **6 → 5**; the guard
   FATALs at 13 pairs on the 3 req/s REST envelope). **No feature-vector change** — the 432-bar
   cohort is frozen mid-migration. **Spot only; no margin anywhere and no margin panel invented to
   imply otherwise.** Doctrine: [[synthesis/tangible-value-doctrine]].

5. **`4799bfc7` — owed item 30 CLOSED, all ten, each with a red-first test.** Round 2's unfixed
   findings were filed with file:line and mechanism, then discharged as their own reviewable commit.
   The three that matter most:
   - **MONEY.** The profit-pool skim ran **once per exit LEG** on `net` — **gross minus that leg's
     exit fee, NOT minus the slice's pro-rata entry fees** — so it skimmed an **overstated base**
     *and* fired on **winning legs of trades that ended up losing**: a **+$16 tier take on a trade
     netting −$80 still moved ~$4.80 into locked savings/reserve, and savings is never clawed
     back**. With **tiered exits the normal shape**, trading cash **bled monotonically into locked
     pools as a function of gross winning legs**. Fixed by separating the fused concerns — cash
     settles per leg (`skim=False`; entry fees already left cash at fill time), while the three-way
     split runs **ONCE per closed trade** on the fully-net total via new `CapitalManager.skim_trade()`
     in `_finalize_position`, with equity-conservation and no-double-booking pins
     ([[concepts/payoff-asymmetry]]).
   - **EVIDENCE.** The governor's Wilson credibility guard was **algebraically dead** (`lcb ≤
     observed` always, so the clause could never veto — and grew *more* permissive as n fell), and
     `baseline_brier` was an **in-window oracle** scoring the window's own realized mean. Fixed with
     `wilson_ucb()` (must clear the most optimistic reading; correctly harder at small n) and
     `_prior_base_rate()` (rows predating the window only, neutral 0.5 at cold start — a **weaker**
     baseline, hence slower to convict) ([[entities/ml-governor]],
     [[concepts/wrong-null-calibration]]).
   - **PROVENANCE.** `ml/registry.py` is now **genuinely hash-chained** (`prev` + `seq` + content
     hash, matching `core/audit.py`'s construction), `verify_chain()` walks the links, and **a broken
     chain FAILS the load gate instead of authorizing it** — closing the standing citation hazard
     ([[comparisons/stated-invariants-vs-audited-reality]]). Writing the torn-row test surfaced an
     **eleventh bug**: the registry ledger had the **same torn-append fusion defect as the fills
     ledger** — **third instance of that class**, now [[concepts/torn-append-fusion]].

   The other seven: OKX deep history no longer truncated to 2000 bars (`train_meta` was asking ~10
   days of 5m bars and getting ~7, silently); the Kraken WS book **publishes only after checksum
   verification** (the resubscribe backoff had been serving a **phantom 1-5-level book stamped
   fresh** every frame); the deploy force-kill grace **45s → 150s** against runner stalls **measured
   at 88.1s/55.5s/50.2s** — the likely origin of `audit_tail_truncations`
   ([[entities/auto-update]]); skimmer replace-hysteresis **restored across restarts** (scores were
   persisted but never read back, so a 0.55 candidate evicted a 0.90 incumbent every 15-minute
   deploy); the boot-hang **lock-forever** bounded by `lock_boot_max_stall_sec`; within-bundle
   duplicate merges in the hourly unattended corpus import; and a transient `git show` failure no
   longer **permanently rejects** a valid remote command.

Filed clean by round 2: `ml/labeling.py`, `ml/walkforward.py`, `data/_http.py`,
`data/recording.py`.

**2026-08-06 → 08-07 — the hedge-churn arc, both incidents, both fixes, and the P&L
reconciliation** (head = remote = `21769fb8`; deploy-gate battery on the merged tree **3423
passed / 1 skipped**, deployed 19:04:16Z 08-07):

- **THE hedge churn (canonical: 01:09:00–01:34:59Z 08-07, 294 fills, 147 laps, paired gross
  −13.37 / fees 301.31 ≈ 95.7% fees)** — **panel-corrected 2026-08-07: ONE ledger event,
  double-filed** by two sessions under two clock conventions (the "08-06 20:09–20:34 thrash"
  IS this window in local time; all 159 lifetime hedge fills are 08-07 UTC). **Two mechanisms
  confirmed**: the wrong-pair unwind + cold-0.0 sentinel set the ~10s lap rate (the event ran
  on **pre-`5c111962` code** — D3 committed 01:53Z, after it ended, deployed 02:08Z;
  [[concepts/two-paths-one-quantity]], [[concepts/zero-is-not-a-reading]]); the
  open-on-delta vs unwind-on-corr disagreement **outlived the pair fix** as 12 residual
  warm-correlation laps (01:56Z–11:35Z, corr 0.34–0.55) until `cf454d5e`. The guard fix
  (CLOUD session, per the operator's [[concepts/deadlock-discipline]]): warmup evidence gate
  (`corr_min_samples` 12), per-asset re-hedge cooldown (600s), **FW-070 churn latch**
  (3-in-900s, auto-release on window+warm) — open side only, unwinds never gated; the
  coherence FATAL caught its own author's first config. `af544d4c` repaired the vacuous test
  (fixed-point loop, red at 13/12 against the parent blob). **Zero hedge fills since
  11:35Z.** Residuals owed: estimator warmth not persisted (floor = 30 min = exactly the
  median uptime); FW-070 telemetry-dark; the `cf454d5e` circulated record false on four
  verified counts (items 35, 37(b);
  [[sources/session-20260806-hedge-thrash]] · [[sources/session-20260807-hedge-churn-guards]]).
- **P&L reconciliation (08-07, read-only ground phase)**: all four board numbers reconcile once
  **three series are named** — period counters (daily −164.38 / weekly −173.23), the rolling
  last-200 **non-hedge** perf window (the mislabeled "NET P&L (ALL TIME)" tile, −56.91), and the
  monotonic unexported `realized_pnl_total` (**−208.22**) — plus the **invisible fee channel**:
  entry/hedge open-leg fees are cash-only (−157.84 on 08-07 alone; in no P&L counter). The
  perf ring contains **zero churn entries** — **win rate 8.0% / worst streak 57 is the organic
  picture** ([[sources/session-20260807-pnl-reconciliation]]; owed item 36). Equity
  **$4,615.18**, `fees_total` **382.28** vs starting capital 5,000.
- **The institutional review VERDICT landed (08-07 late,
  [[sources/session-20260807-institutional-review]]): 5 master judges, six areas (ground
  evidence, four lenses, decision record D1-D6) — unanimous 5-0 APPROVED_WITH_CONDITIONS,
  zero rejections, zero unconditional approvals.** The ledgers reconciled to the cent under
  adversarial audit; the records and instruments accrued conditions: churn gross was −13.37
  not 0.00; the **25/40 fee constant matches no row of Kraken's current schedule** (correction
  **sequenced post-h432** — the constant is load-bearing in the label definition,
  [[concepts/cost-truth]]); the conviction funnel's 0/0 is honest for a seam 1,100+
  exploration admissions bypass; the DRY_RUN fill-at-limit RNG manufactures a phantom "quoter
  edge" (all markout is sim-conditioned — [[concepts/paper-real-boundary]]); and one item
  left unadjudicated: the era realized ledger's **6/11 net winners** vs the recent-30
  still-losing story ([[synthesis/open-contradictions-register]] #17). Panel summary kept
  verbatim: *"unusually good bones for a $5k single-box bot — and a completely dark nervous
  system."* Conditions filed as owed item 37. Sidebar: pytest-xdist `-n 8` battery 3423/1 in
  413s vs 623s serial, identical results (second confirming run pending).

**2026-08-08 — era boundary #3, the honest battery gate, and the churn's last bill** (head =
remote = `f07d60f8`; runner RUNNING DRY_RUN on `050421a7` since 11:10 local):

- **Morning** ([[sources/session-20260808-morning-batch]]): `3cfe0710` TTL-normalized the
  passive fill hazard (**execution-era boundary #3** — pre-08-08 long-book fills stay
  uncitable) and `050421a7` repaired the battery's pytest gate, which had **never been able
  to fire** ([[concepts/false-green]] specimen #5, CRITICAL). Battery through the honest gate
  3449/0/1.
- **Afternoon** ([[sources/session-20260808-budget-reanchor]]): the ADA churn's W32 fees
  (~$303 sim) turned out to have consumed **109% of the weekly loss budget** — `taper_mult`
  0.0, all entries blocked, unclearable by restart (equity-anchored persisted state). Shipped
  `f07d60f8`: audited ControlChannel verb **`budget_reanchor_week`** (reason mandatory,
  **RP-042**, registry 186→187, both vocabulary halves, absent from REST — arm_live posture;
  8 red-first tests). Executed 13:13 local: re-anchored at **$4,617.00**, weekly_used 1.09 →
  0.000x, taper 1.0, **`weekly_pnl` −173.36 untouched** (the no-ledger-touch proof). Box at
  filing: equity **$4,616.90**, weekly_used 0.0004, taper 1.0, daily −0.12. Honest-gate
  aftermath: the load-marginal timing family is now the batteries' binding constraint (owed
  44 — split parallel/serial); 41(a)'s freeze-gate tests written and parked, implementation
  next.

**2026-08-08/09 — the corpus corruption, and the first honestly-red battery**
(head = remote = `3c0debd7`, pushed; runner bounce **sent**, relaunch onto `3c0debd7`
**unconfirmed at filing** — committed ≠ running, per [[entities/auto-update]]'s local-commit
blind spot):

- **THE INCIDENT** ([[sources/session-20260809-corpus-corruption]]): one non-idempotent line
  in `scripts/migrate_history.py:125` re-derived `label_era` on every migration pass,
  **pooling 2,729 rows across three incompatible label definitions**. Triggered by the
  project's *own* 41b schema commit — 4 new columns → corpus rotation 20:01:30 → `.bak`
  recovery merged back through the migrator 20:01:46. Chain: era filter **disarmed**
  (690→42 current-era rows) → 9,746 pooled rows into training → `live_clean` 5→299 → **all
  four evidence floors cleared in one step** → **`gbt` deployed champion 20:10:44 on a data
  bug**. **Zero rows lost.** Fixed + corpus **repaired** from preserved backups (2,729 cells,
  `position_id` join, 0 conflicts, 0 rows moved); re-corruption risk closed (`corpus_sync`
  spawns fresh). Now gated by a **fixed-point test**
  ([[concepts/migration-idempotence]], [[concepts/label-era]]).
- **A PRIOR WIKI FILING CORRECTED IN PLACE** — the 08-08-night claim that the overfit red
  came from "live rows crossing a 60-row threshold" was **false in both halves**; the real
  cause was this corruption ([[sources/session-20260808-night-staleness-overfit]] §2).
- **THE HONEST RED**: on the **repaired** corpus the overfit battery is **3 pass / 4 fail** —
  OF-1 gaps **+0.422/+0.414/+0.503** (worse than the corrupted pool's, correctly), OF-7
  `dead_frac` **0.95**, rows/feature **10.8** barely passing, learning curve **CLIMBING
  (+0.112, "data-starved")**. **No threshold was moved.** The deploy gate
  (`auto_update.battery_passes`) is **blocked** pending operator adjudication
  ([[synthesis/owed-measurements]] item 46).
- **A WEDGED CHAMPION** (item 47): selection correctly re-gated to `['logistic']`, but the
  champion gate rejected the swap — challenger **0.2714** (clean 692 rows) vs champion
  **0.1537** (**corrupted** 9,708 rows). Incommensurable sets; the bug-promoted `gbt` cannot
  be dislodged without a conscious re-baseline. Gate deliberately **not** overridden;
  [[entities/ml-governor]] still grades on realized outcomes meanwhile.
- **ALSO SHIPPED in `3c0debd7`**: the **42a veto band** — `kraken_max_book_age_sec`
  **5.0 → 3.5** plus a `config_guard` **FATAL on the relation** to
  `pretrade.max_data_staleness_ms` (at 5.0, books aged 4–5s were served then vetoed,
  preempting fresh REST reads on ~0.6–3% of entry evaluations, worst on thin pairs —
  [[entities/pretrade-gate]]); and the **owed-44 gap**: `test_import_integrity` now serial,
  timing family **17→18**.
- **Battery:** pytest **3466+1** parallel / **18** serial · smoke 219 · assurance · ruff ·
  **pyright 0** · bandit · compileall · quant **G1–G5 all green** — **overfit honestly RED.**

## Key pages
[[synthesis/research-program-overview]] · [[synthesis/learning-pipeline-arc]] ·
[[synthesis/governance-doctrine]] · [[synthesis/risk-posture-doctrine]] ·
[[synthesis/open-contradictions-register]]

## Subsystem map
| Layer | Page |
|---|---|
| Corpus and labeling | [[entities/historystore]] |
| Model governance | [[entities/ml-governor]] · [[entities/overfit-check]] |
| Risk simulation | [[entities/quant-trials-harness]] |
| Decision-time cost | [[entities/pretrade-gate]] |
| Manipulation defense | [[entities/thales-engine]] |
| Slow accumulation | [[entities/long-book]] |
| Startup safety | [[entities/config-guard]] |
| Accountability | [[entities/reason-code-registry]] |
| Telemetry plane | [[entities/observability-sidecars]] |
| Regime / haven read | [[synthesis/tangible-value-doctrine]] |

## Venues
[[entities/kraken]] (sole execution venue) · [[entities/read-only-venues]] (data only)

## Architecture and assurance sources
[[sources/architecture-v2]] — the base system map
[[sources/assurance-rev3]] — invariants and the assurance spine
[[sources/hardening-catalog]] — failure planes and concrete thresholds
[[sources/security-audit]] — the data-ingestion trust boundary
[[sources/compliance-market-conduct]] — the legal-limit overlay
[[sources/interpretability-design]] — the report-only explainer
[[sources/smc-features]] — structural context features
[[sources/whole-code-audit]] — where the invariants were measured

## The economic bottom line (2026-08-09) — read this before any plan

([[sources/session-20260809-unbiased-economics]]. Sim-side of
[[concepts/paper-real-boundary]]; re-derived at filing from the live `outputs/state.json`.)

```
GROSS trading P&L, before ANY fees :   −11.66   over ~250 closed positions / 438 entry fills
total fees paid                    : −382.59   (opening 185.94 + closing 196.65)
NET realized, all-in               : −394.25   = −7.89% of the 5000.00 starting capital
fees / |gross edge|                :    32.8x
```

**Gross is ~−$0.05 per trade — indistinguishable from zero. 100% of the loss is costs.**
Corroborated by three instruments sharing no mechanism: **OOF AUC 0.43–0.48** (at/below chance),
champion **Brier 0.24728 vs 0.25** for a coin, and postmortem **MFE median 0.18% / p90 0.55%**
against a **~0.65%** round-trip cost. The fill simulator is one-way optimistic, so real gross
would be **worse**: the defensible statement is **gross edge ≤ 0**.

**Three things this does NOT license, recorded to stop the obvious misreadings:**
- It does **not** say the bot is broken. Every subsystem on this page does what it was built to
  do; the assurance spine, the corpus machinery and the gates are all functioning. **The strategy
  is uneconomic at this geometry** — a different claim.
- It does **not** say "the corpus needs to grow." That account is **falsified as a complete
  explanation** — there is no gross edge to be starved of
  ([[concepts/unfalsifiable-explanation]], [[concepts/dof-budget]]).
- It does **not** point at the model. `config_guard` computes a **derived entry bar of 0.990**
  from **tiers, stop and fees alone** — *"fix the geometry, the bar is only reporting it"*
  ([[entities/config-guard]]). **A required win probability of ~99% is not a modelling problem.**

**The one live lead is geometric:** shadow win rate rises monotonically **22.3% → 30.4% →
35.4%** at 108 → 216 → 432 bars ([[comparisons/horizon-96-vs-24-bars]]).
**The one structural blocker:** the corpus carries `net_pnl_usd` and **no gross and no per-row
fee column**, so gross-edge-by-subpopulation is unaskable
([[synthesis/owed-measurements]] item 50).

## The current regime (2026-08-10 evening) — $800 stressor, model freeze, era-4 gate

As of **2026-08-10T23:05:27Z** ([[sources/session-20260810-stressor-epoch]]) the bot runs the
**operator-adjudicated $800 stressor**: capital 5000 → **800**, all money state zeroed (equity
800.00 = starting_capital verified on relaunch), goals **$25/week, $100/month** escalated by
the **RP-072 ×1.5 ladder** (never de-escalates; grading/telemetry only), venue floors
deliberately **unscaled** — the $15 minimum ticket is **1.9% of equity and the bite is the
stressor**. **Model-side investment is FROZEN**; the only unfreeze trigger is the
**pre-registered era-4 gate readout** (NO_GROSS_EDGE / COST_BOUND / CONTINUE at n≥50 on the
post-epoch honest-fill cohort, accruing 0/50). The **era-4 accrual moratorium**
([[synthesis/governance-doctrine]] rule 17) forbids cohort-resetting changes without operator
adjudication. Every dollar figure now carries a **capital-regime qualifier** as well as its
fill-era qualifier ([[synthesis/comparability-boundaries]]); `fills.csv` rows carry
**`exec_era` provenance** and the **OM-085** restart-replay write guard.

## How it selects assets (2026-08-11 audit) — per-asset plumbing, global brain, no leaderboard

([[sources/session-20260811-operator-audit]] §1, §3 — the standing description; verdict
**MIXED**.) There is **no candidate leaderboard**: entries iterate a **round-robin** over
`_entry_assets` (`main.py:3911-3921`), so nothing ranks assets against each other and no
ranking exists for an inverted feature to reverse (the load-bearing fact in the
backwards-derivative refutation). Around that loop the split is precise: **per-asset** —
regimes, features, vol-scaled stops, breakers, caps; **global** — the meta-model and the
gate thresholds, one brain scoring every asset. Two observed consequences that look like
policy but are arithmetic: the **bracket cost floor flattens the majors to identical
1.50/2.00 sl/pt** geometry (the floor binds — [[concepts/cost-truth]]) while FLOW/ARB/MINA
actually differentiate; and **ETH/BTC fill concentration is gate-confirmation frequency,
not preference** — `gate_confidence` is flat across assets (0.81–0.90), the gate simply
confirms more often on those books. The features the model sees are **side-relative**
([[concepts/side-relative-features]]) — raw corpus rows are unreadable without the `side`
column, which is what generated the backwards-derivative claim the audit refuted (0/3
adversarial refuters, NO-INVERSION-FOUND).

## The risk lane's worst live defect, found and fixed (2026-08-09, `1fee174e`)

([[sources/session-20260809-adversarial-audits]] §1.) **`risk/position_sizer.py` was reading a
state attribute `PortfolioState` does not have.** `getattr(state, "positions", {}).values()`, at
three sites — the book is `_positions`, exposed as `open_positions()` — so the **default was
taken unconditionally for the life of the module** and the sizer believed the book was **always
empty**.

**Three of this page's stated risk controls were inert, and all three failed PERMISSIVE:**

- the **portfolio-heat veto** (`max_portfolio_heat_frac` 0.35, `RP_HEAT_FULL`) — **unreachable**;
- the **signed-inventory reservation skew** (`SZ-061`) — **never applied**;
- the **inventory-aggression multiplier** — **pinned at `light_boost` 1.10**, a permanent
  **10% size-UP**, where it should taper toward `heavy_cut` 0.65.

**Measured on the live book with real position ages:** gross heat **0.1176** (read 0.0000),
signed **+0.1052** (read 0.0000), multiplier **0.9488** vs the pinned **1.1000** ⇒ **tickets were
13.7% LARGER than designed**, precisely when risk was already on. *(A first reconstruction printed
−40.9%; it stamped every position as opened NOW, maximizing the clustering term. Corrected in
place.)*

**Post-deploy, live:** `status` `heat_frac` **0.1177**, where it had been structurally 0.0
forever.

> **~3,400 tests were green over this**, because the doubles supplied the missing attribute — and
> the test that hid it exists to catch this exact class ([[concepts/test-double-fidelity]],
> [[synthesis/governance-doctrine]] rule 15). The fix centralises one `_open_book()` accessor and
> **logs once when a state cannot report its book**, so a dead reader and a genuinely flat book
> stop producing the identical benign 0.0 ([[concepts/zero-is-not-a-reading]]).

## The all-in P&L statement is now honest (2026-08-09, `a6334162`)

Operator symptom: *"net pnl all time doesn't match up with equity."* **No money was missing; the
STATEMENT was wrong.** `record_realized_pnl` nets the **closing leg only** while
`record_entry_fee` debits the **opening leg (entry AND hedge)** straight to cash — so **185.94 of
382.59 lifetime fees (49%) appeared in no readable number.**

Shipped: `entry_fees_total`, `realized_net_all_in`, and **`net_pnl_all_time` defined as the EQUITY
IDENTITY rather than a sum of counters** (so a forgotten counter cannot hide the same way twice),
plus 4 status keys, `gc_pusher` gauges, and an exact one-time backfill. **Verified live
post-bounce:** `entry_fees_total` **185.94**, `realized_net_all_in` **−394.25**,
`net_pnl_all_time` **−382.40** (= equity 4617.60 − 5000).

**Battery ALL GREEN on both commits:** pytest **3490 passed / 19 skipped**, smoke 219, assurance
49, overfit 3/0, ruff, pyright 0, bandit, compileall, quant G1–G5.

> **What the two fixes have in common, and it is this page's standing lesson:** both were
> **reporting/plumbing defects that flattered the bot** — one under-reported risk, the other
> under-reported cost. They sit inside a population of **eleven such distortions found the same
> day, all running the same direction and none running the other way**
> ([[concepts/self-flattery-gradient]]). **Every remaining item on that docket, when fixed, moves
> a published number DOWN.**

⚠️ **And `a6334162` is itself the cause of the next latent defect.** It shipped **4 status keys
without updating `_SYNTH_STATUS`**, the synthetic status fixture — invisible until a panel
referenced one, at which point `test_every_query_hits_an_emitted_metric` **failed correctly**. Owed
**59**; class [[concepts/test-double-fidelity]]. *A fix that ships keys without pinning the fixture
is how the next one enters.*

## What the bot looks like to a professional (2026-08-09) — machine on mechanics, retail loser on economics

([[sources/session-20260809-turing-test-hedge-verdict]],
[[comparisons/bot-vs-discretionary-vs-algo-trader]]. Mechanical tells **repo-side**; economics
**sim-side**.)

**Identified as a machine in seconds**, on order mechanics alone: modal ticket **exactly $18.00,
x51**; **after-win/after-loss size ratio 1.000**; **0.0%** round-number landing; **8-decimal**
sizes including **31 dust legs to 1.17e-09 ETH**; **100% limit (1019/1019)**; **59** trips held at
exactly **5.000s**; activity in all 24 hours (chi2 **137.8**, **zero empty hours**).

**And economically indistinguishable from an unprofitable retail human:** **58.3%** win rate on a
**0.670** payoff, with a **2.20x disposition effect** (losers **2.00h**, winners **0.91h**).

> **The bias is GEOMETRIC, not psychological** ([[concepts/behavioral-isomorphism]]). A near
> take-profit with a far stop manufactures the disposition effect by arithmetic. *"We are
> deterministic, therefore we have no retail biases"* is a non-sequitur — and the signature is
> what loses the money.

**The algorithmic verdict is colder and is the operative one:**

```
gross edge / trade  : -0.0019%      t = -0.332   (indistinguishable from zero)
fees / |edge|       :  368x         (percent space, per trade)
median WINNER hold  :  0.91 h  vs   0.71% round-trip cost
taker fill share    :  60.6%        (on a maker-thesis book)
```

**The hedge book is the buried half of the economics:** **159** round trips, **0 of them
profitable NET of fees** (gross win 15.1%, **net win 0.0%**), net **−$325.70** on **$39,460** of
notional — **4.5x** the entry book's **$8,821** — while invisible to both the performance ledger
and the circuit breaker. And **77.3% of ALL lifetime fees** (**$289.73** of **$374.96**) were spent
in **25 minutes** on 2026-08-07 by a single churn bug, with **no recurrence in 56.5h**.

> **Both halves travel together.** The churn dominates the fee *history*; removing it does **not**
> create an edge, because gross is ~0 independently. **Flat on selection, losing on cost.**

*(⚠️ **58.3% / 0.670** has an unstated corpus and is a **citation hazard** — a third payoff
derivation, not a replacement for **0.561 / 0.750 at n=217**.
[[synthesis/open-contradictions-register]] entry 6.)*

## Host infrastructure (2026-08-11 → 2026-08-16) — Docker deleted, backup taken, MCP boundary unchanged

*(host-side / tooling-side; no sim number here. [[sources/session-20260811-16-vscode-3b307393]] §3–4.)*

**Docker was DELETED from this box on 2026-08-11 by operator order, after an audit that found
nothing of the bot's in it.** The engine held **no Hummingbot** (archived 2026-07-09) and only
Docker Desktop's built-in **kind** Kubernetes sandbox: an nginx deployment `my-app` that had
served **zero requests** since the Aug-7 restart, plus the Grafana **k6 load-test operator** with
no active TestRuns — **ClusterIP only**, apiserver on **127.0.0.1:55743**, no external exposure.
Cost: ~**38% of one core** and ~**900 MB RAM** for **zero bot value**.

**Why zero:** the bot runs **natively as 10 `pythonw` processes**, and observability is **Grafana
CLOUD** — the local `grafana/k6` image is a *load tester*, not the dashboards.

**Removed:** MSI uninstall · `docker-desktop` WSL distro unregistered · `E:\DockerWSL` ·
`AppData\Local\Docker` junction · `Roaming\Docker*` · `docker-secrets-engine` · `~\.docker` ·
`ProgramData\Docker` · `Program Files\Docker` · HKCU autostart · the Desktop
*"Docker (clean start).bat"*.
**Preserved deliberately:** `D:\Archive\hummingbot-docker-2026-07-09\docker_data.vhdx` (the only
surviving copy) and the **Ubuntu** WSL distro. **Verified 2026-08-16:** Docker paths absent,
`docker` off PATH, `wsl -l -v` = Ubuntu only, archive vhdx present, bot **RUNNING | DRY_RUN** with
**10** `pythonw` alive.

**Tooling consequence, stated precisely** (a session note claiming more than this is corrected on
[[synthesis/documentation-drift-register]]): `MCP_DOCKER`'s tools are gone and its registration in
the global `~\.claude.json` is now **dangling**; **`coinpaprika` is unaffected** — it is a hosted
SSE MCP in the repo's own `.mcp.json`, not a Docker gateway tool. The **tooling-only boundary is
unchanged: the runtime never consumes MCP**, and the bot never used either. The AF_UNIX
broken-socket workaround is moot.

**Isolated backup, 2026-08-11** — `C:\Users\haird\Documents\liquiditybot_isolated_2026-08-11`,
taken **copy-not-move while the runners were live**: full tree incl. `.git` (all branches +
stash) and the 3.8 GB `outputs/` (**robocopy 2593/2593 files, 0 failed**, ended 20:01:56 local); a
git bundle of **all refs** verified *"records a complete history"* (**20,830,320 B**); a copy of
the Claude project dir (memory + every session transcript); a `README.txt` with restore steps.
**Not yet provably frozen** — [[synthesis/owed-measurements]] item 77.

## Can it go live?

Not yet, and the reasons are tracked in one place: [[synthesis/live-readiness-verdict]] — **NOT
READY as of 2026-08-21**, five independent blockers (the era-4 gate un-read at 33/50; its
resolution floor above the effect it is asked about; a cohort that is 85% exploration probes; two
CRITICAL defects inert only because `dry_run` is true; and a manipulation gate that cannot separate
honest repricing from layering). The road itself is unchanged law: config `dry_run:false` →
restart → typed `ARM LIVE`.
