# Compounder Framework — design spec

Date: 2026-07-24 · Status: DRAFT — awaiting operator approval (brainstorm
gate). Origin: operator vision session 2026-07-24 ("extract the exact idea
of the corpus's learning capabilities … create a formula … research 4 year
cycles / big money psychological patterns … implement a master model
including THALES … long term position agility / profit models / inventory
management / execution styles / learning methods").

One program, three internally-phased deliverables (A → B → C), one spec.
Approved section by section in-session; this document is the durable record.

---

## 0. Non-negotiables (inherited, restated so the program can't drift)

Every CLAUDE.md hard invariant binds every phase, unchanged:

- `system.dry_run` defaults true; the only road to live is config →
  restart → typed `ARM LIVE`. `force_dry` stays one-way LIVE→DRY.
- Kraken is the sole execution venue; everything else read-only.
- Withdrawal deny-list untouchable. No withdrawal capability, ever.
- Entries limit-only; exits ALWAYS allowed — disarm/faults/kill switches
  block new risk, never escapes.
- Hash-chained audit + registered reason codes on every disposition.
- No fitted-looking literals in decision paths: every threshold this
  program introduces is config-lifted with `core/config_guard.py`
  coherence checks and a derivation comment.
- Full battery green per landing (pytest · smoke · assurance · overfit ·
  ruff · pyright-zero shipped scope · bandit · compileall). No phase
  ships red.

Operator decisions fixed during the brainstorm (do not re-litigate):

- ONE program, phased A/B/C — not three specs.
- A long-horizon book EXISTS as a new position class beside the 5m book.
- Envelope = evidence ladder 10% → 20% → 30% of equity, unlocked by
  realized track record; long-only accumulation first, shorts earn
  admission later.
- NO shadow period: the long book trades paper from day one — the
  positions ARE the learning.
- "Fresh clean start" = new foundational framework/mindset. The corpus
  (3,628 rows), the engines, and the invariants CARRY FORWARD. No data
  reset, no rewrite of working machinery.
- Tooling: financial-analyst discipline embedded in the long book's
  accounting (§5); systematic-debugging is the program's closing
  hardening pass (§6); implementation via the SDD machinery.

---

## 1. Foundation — the Compounder Framework (five principles)

Every design choice below traces to one of these; anything that traces to
none of them is out of scope.

1. **Preservation is the root.** Compounding dies on drawdown. Size is
   earned, never assumed; de-risking is instant, re-risking is slow.
2. **Evidence buys size.** The only currency that unlocks equity share is
   realized, ledgered track record — never backtest peaks, never
   conviction alone (OF-4 discipline applied to capital allocation).
3. **Context before conviction.** No long-horizon risk without knowing
   where we are (cycle phase, structural stress, flow). Unknown context
   is a state, not a guess — and unknown blocks new long-book adds.
4. **One truth ledger.** One equity, one audit chain, one risk envelope
   across both books. Every position has a thesis, an expected path, and
   a close-out variance explanation.
5. **The corpus is the asset.** 3,628 labeled rows and the machinery that
   produced them are the moat. New learning extends the corpus (new label
   universe, shared infrastructure); nothing contaminates or resets it.

## 2. Phase A — the Conviction Formula

A deterministic, registered admission rule that turns "the corpus's
learning capability" into a formula the bot can follow consistently.

**Admission requires ALL of (conjunctive, no fitted weights):**

1. **Signal-stack agreement** ≥ config floor — the existing gate stack's
   agreement measure, config-lifted (no new alpha invented here).
2. **Cost-adjusted EV multiple** — pretrade EV must clear a config
   multiple of the *measured* cost stack (fees + spread + slip from our
   own telemetry), not a notional cost.
3. **Regime evidence known** — the candidate's regime has per-regime live
   label coverage at/above the T4 floor mechanism; a regime we have no
   evidence in cannot admit conviction size.
4. **Context alignment (long book only)** — Phase B's context state must
   affirmatively align with the position thesis; `unknown` fails this
   term for new adds.

**Conviction-cadence governor:** mirror of the probe throttle — maintains
a target conviction-admission share per window and per regime so the
formula cannot silently become always-on or always-off. Config-lifted
targets, guard-checked, reason-coded dispositions.

Everything is auditable: each admission/denial writes a registered code
with the failing/passing terms. No bare strings, no hidden scores.

## 3. Phase B — the Cycle/Macro Context Engine + research program

**Honesty rule that governs the phase:** a 4-year cycle yields ~3 complete
samples in recorded history. Nothing may *learn* the cycle from our own
data; cycle and macro enter as deterministic structural context only.

**Engine:** a read-only module on a slow cadence (hours, not 5m cycles)
producing a small fixed set of context inputs:

1. **Halving phase** — computed from public constants; days-since /
   days-to-next bucketed into named phases (accumulation / expansion /
   euphoria / contraction). Bucket boundaries config-lifted; derivation =
   the research doc.
2. **Structural stress trio** — FRED keyless endpoints: fed funds,
   10y–2y spread, VIX (TradingAgents A4 adoption). Risk-on/risk-off dial
   only; never an alpha signal.
3. **Institutional-flow proxy** — free/keyless observables only: CME
   futures basis (existing `basis_bps`) + stablecoin aggregate-supply
   delta. The research doc adjudicates which proxies carry evidence.
4. **Event calendar** — CME expiries (deterministic), FOMC dates
   (published yearly, shipped as a data file), halvings. The calendar
   gates *cadence* (long-book adds pause inside event windows), never
   direction.

**Disciplines:**

- Every context input is a feature or structural gate under the OF-7 DoF
  budget. Program-wide context-feature budget: a handful (exact cap set
  at planning, config-lifted, guard-checked) — the corpus affords no
  more. Each feature earns admission the same way existing features did.
- Every source can go dark → context degrades to `unknown` (a state, not
  a guess). Unknown is admissible for the 5m book; unknown blocks NEW
  long-book adds. Absent sources never fabricate values.

**Research program (runs first; freezes Phase B details):**
fintech-quant-researcher + financial-analyst produce ONE referenced doc
committed to `docs/research/`, covering: 4-year-cycle evidence (peer
review vs. folklore), institutional-flow literature (CME basis / COT
predictive content), AI-investment wave in crypto, CME/regulatory
calendar effects, university studies on crypto momentum/seasonality,
influencer/sentiment evidence (StockTwits stays a read-only feature
candidate). Each candidate input ships with an evidence grade; inputs
failing the bar are recorded REJECTED with citations (T6
durable-findings precedent). **THALES hardening rides this doc**: any
manipulation-pattern evidence found becomes a detector candidate, in its
own section.

## 4. Phase C — the Long-Horizon Book + master composition

**A new position class, not a new bot.** Reuses PositionSizer ×
RiskProtocolStack, inventory caps, ProfitTierEngine + give-back ratchet —
with its own config block and parameters. Engines are parameterized,
never duplicated ("new position logic goes through these, not beside").

- **Entry style — accumulation, not reaction.** Long-only first.
  Limit-only bid ladders at structural levels the context engine
  identifies; patient bids filled *by* volatility. Conviction Formula
  admission required; context alignment mandatory.
- **Sizing — the evidence ladder is the ceiling.** 10%/20%/30% of equity
  per §5; within the ceiling the existing CVaR/gap/budget/heat stack
  sizes each add.
- **Profit model — tiers rebuilt for the horizon.** Same
  ProfitTierEngine with long-horizon parameters: wider tiers, partial
  banking on cycle-phase transitions (euphoria tightens the give-back
  ratchet rather than exiting outright), and a hard structural stop that
  is a thesis-invalidation level, not a volatility stop. Exits always
  allowed.
- **Execution style — cost-first.** Post-only maker ladders, no urgency,
  order sizes bounded so the book never moves its own market. Verified
  against the existing measured cost stack.
- **Model-head socket, designed in but dark.** The long book runs
  rule-based (formula + context) from day one on paper. A model head
  slot exists in the composition; activation is evidence-gated (§5).

**Master composition — one envelope, two books:**

- One equity, one truth ledger, one risk budget. RiskProtocolStack sees
  COMBINED heat/exposure; both books' caps bind inside it.
  Cross-book correlation counts against heat (5m BTC long + long-book
  BTC = one bet, not two).
- Kill switches, disarm, faults: global, both books, instantly.
- The long book obeys every invariant in §0 and writes hash-chained
  audit with its own registered code family.
- **THALES watches both books**, hardened by the research doc; its
  manipulation scores gate long-book adds exactly as they gate 5m
  entries — a spoofed level is not a structural level.

## 5. Learning methods, evidence ladder, accounting discipline

**Long-horizon label pipeline (day one):** every paper long-book position
snapshots full entry context (conviction terms, cycle phase, stress trio,
flow proxy) and labels at horizon — triple-barrier geometry stretched to
the book's timescale. Labels enter the SAME corpus with a `book` tag
(mirroring the live/candidate source split): shared infrastructure,
separate label universe, zero contamination of the 5m brain. The 5m
book's learning loop (probe throttle, T4 regime floors, governor) is
untouched by this program.

**Model-head activation gate** (all three, else rules-only):

1. ≥ N long-horizon labels accumulated (config-lifted),
2. OOS improvement over the rule-based formula measured on the DEPLOYED
   selection rule (OF-3 PBO discipline, never argmax),
3. full overfit battery green on the long-horizon corpus slice.

**Financial-analyst discipline — the book's accounting:**

1. **Scenario modeling**: every long thesis carries base/bull/bear
   expected paths keyed to cycle phase.
2. **Variance analysis at close**: every closed position reconciles
   realized vs. expected — favorable/unfavorable classification + root
   cause — written to the truth ledger.
3. **Forecast-accuracy tracking**: the book's EV estimates are scored
   against realizations as a monitored health metric (calibration-style).

A position without a thesis, an expected path, and a close-out variance
explanation does not exist in this book.

**Evidence ladder** (defaults for planning; exact values config-lifted +
guard-checked, rungs monotonic, ceilings inside the heat cap):

- **Rung 0 — paper, day one.** No gate.
- **Rung 1 — 10% equity ceiling:** ≥ K closed paper positions, positive
  net EV after the full measured cost stack, zero invariant breaches.
  Live arming still requires the only road that exists (§0).
- **Rung 2 — 20%:** realized LIVE track record — ≥ K₂ closed positions,
  profit-factor floor, drawdown ceiling respected.
- **Rung 3 — 30%:** longer live record PLUS survival of ≥ 1 adverse
  context transition with ratchet discipline intact.
- **Downgrades automatic and instant** — breach a drawdown ceiling, drop
  a rung immediately. De-risk fast, re-earn slowly (force_dry philosophy
  applied to size).
- Shorts: no admission in this program; a future spec must earn them
  with the same evidence standard.

## 6. Battery, testing, and program close-out

- Every phase lands full-matrix green; new behavior gets tests in the
  same commit; every module imports in isolation; Windows stays green.
- **Reason codes:** new registered LB-* family in `core/codes.py` for
  every long-book disposition (admission, denial, add, tier, ratchet,
  invalidation, ladder rung change), plus codes for conviction-formula
  and context-engine dispositions.
- **Quant gates:** the long book gets its OWN gate set (quant_trials
  style), CI-bound only after conscious baselining. G1–G5 stay pinned to
  the 5m book — never diluted, never widened.
- **Config:** all new thresholds in `config.json` under new blocks
  (conviction, context, long_book) with config-guard coherence checks
  (ladder monotonic, ceilings ≤ heat cap, phase buckets ordered, EV
  multiple ≥ 1, feature budget enforced).
- **Status/telemetry:** status schema EXTENDED (never broken) with
  conviction/context/long-book sections; Grafana boards extend the
  existing four — no new boards.
- **Systematic-debugging closes the program:** final hardening pass runs
  the discipline on anything red or flaky, plus a dedicated adversarial
  pass over §0's invariants, before the whole-branch review.

## 7. Out of scope / explicitly rejected

- Shorts in the long book (future spec, own evidence bar).
- Any key-required or paid data vendor (keyless/free only this program).
- Learning the 4-year cycle from our own data (3 samples — impossible).
- New execution venues, new UI processes, a fifth Grafana board.
- Resetting/rewriting the corpus, the 5m learning loop, or any engine.
- Model-head activation without §5's three-part gate.

## 8. Acceptance (program level)

1. Conviction Formula admits/denies deterministically with registered
   codes; cadence governor holds target share per window and regime.
2. Context engine produces the four inputs with honest `unknown`
   degradation; research doc committed with evidence grades and REJECTED
   entries; THALES candidates recorded.
3. Long book runs paper from day one inside the composed envelope;
   ladder gates verified by tests; downgrade-on-breach instant.
4. Long-horizon labels flow into the corpus under the `book` tag with
   zero 5m contamination (test-pinned).
5. Full battery green; new quant gates baselined; all §0 invariants
   covered by the adversarial pass.
