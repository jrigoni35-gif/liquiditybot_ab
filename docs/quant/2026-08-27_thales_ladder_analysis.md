# The Thales ladder — archetype population, capitalization, and the registry
**2026-08-27 · status: adjudication input (SAFE-class analysis; no decision-path change)**

Operator proposal under analysis: model the full ladder of trader
archetypes (naive one-search grid bot -> beginner -> intermediate ->
experienced -> consistently profitable), across timeframes, all
consistently backtested and walk-forwarded; use that population as
information; feed a config-governed capitalization layer that the ML
stack and the operator vault (llm-wiki) jointly steer. Constraint set
by the operator: no new frameworks — improve and implement inside the
system at hand. Governance addendum (2026-08-27): every capturable
human mistake gets a governed registry entry that cannot rot
(`docs/thales/README.md`).

Method: five scoped surveys (THALES state; population/backtest infra;
ML + capitalization; counterparty-flow + funding/basis reach;
literature) + a full-ledger data archaeology + adversarial review of
this document before filing. Every load-bearing claim carries a
file:line or instrument pointer; carried claims are marked.

---

## 1. The proposal already exists in fragments — and one fragment is the cautionary case

**THALES is the thesis, implemented.** `strategies/thales.py` +
`docs/THALES.md`: a bank of 8 footprint detectors for exactly the
"sloppy one-search bot" population (grid ladders, metronome
cancel/replace, clockwork flow, stop herding, spoof flicker, bar-close
herding, feed-integrity self-checks), with a bounded advice channel
and a reliability ledger. `docs/THALES_FRAMEWORKS.md` is the naive
archetype catalogue (freqtrade / Hummingbot documented defaults).

**And THALES instantiated the rot chain the registry now forbids.**
State measured this session (full map in the scout survey; unit audit
`docs/quant/2026-07-29_thales_unit_audit.md`):

- Last substantive change 2026-07-29; untouched across all 50 visible
  commits (2026-08-18 -> HEAD `5e785c16`).
- The shade channel is INERT (`thales.influence: "shadow"`;
  `out.mult` fixed at 1.0 — `strategies/thales.py:855-861`), so the
  doctrine's profit channel never activated.
- Meanwhile five detector scores ship into EVERY feature vector
  (`main.py:6123` -> `ml/features.py:135-136`), i.e. rung 3 of the
  activation ladder went live by side door without the three gates its
  own doc requires (`docs/THALES.md` activation ladder); under the
  prior champion `th_clockwork` ranked #1 walk-forward importance
  (`docs/quant/2026-08-14_edge_training_design.md:60-62`).
- Six doc/code divergences, including an inverted one (TH-017 shipped
  in code, doc says "not built") and a live feature with no audit
  emitter (`Code.TH_BARCLOSE_HERD`, zero call sites).
- Promotion to `advise` is blocked by a real, flagged, unresolved
  double-count hazard (shade would enter p_win twice —
  `edge_training_design.md:129-131`).

Add -> add -> never incorporate -> (next step would have been)
"failed, poor configuration" -> forgot. The registry
(`docs/thales/REGISTRY.md`, 15 seeded entries, staleness-vs-boundary
test) is the structural answer; THALES's own items are entries
TH-R-001..006.

**Other existing fragments of the operator's idea:**

| fragment | where | what it already gives the ladder |
|---|---|---|
| tier-0 baseline archetype | `scripts/random_entry_control.py` | random-entry control, K=200 per real trade, timing-isolated |
| 2-rung strategy pair | `scripts/quant_trials.py` `run_long_trials` | naive DCA vs LongBookEngine, identical paths, G1-G5 gates |
| model simplicity ladder | `ml/walkforward.py:46,61` | logistic->gbt->blend->mlp climb rule, PBO-measured (OF-3) — but these are p-models, NOT trading strategies |
| archetype taxonomy on paper | `docs/quant/2026-08-20_learning_symmetry_result.json` | 28-row capability matrix, rungs common/professional/expert — a ready-made population spec, never run |
| recorded tier specimens | our own ledgers | epoch 4 ($5,000, 25.1d, **-7.93%**, win 3.8%, MFE capture -3.341) = the bad-bot trace; era-4 epoch 5 (+0.30%, fee-bound) = the intermediate trace |

## 2. The bot's own data is the bottom of the ladder (archaeology, all ledgers)

Five capital epochs (250,098 equity samples), 68,982 audit records,
17,872 signal rows read this session:

- **Epoch ladder:** $25k shakeout -> $100k config experiment -> $800 ->
  $5,000 old-geometry era (**-$396, the measured naive tier**) ->
  $800 era-4 honest fills (+0.30%, the fee-bound intermediate tier).
- **Behavioral census:** ~89% of ALL audit dispositions are the probe
  machinery (SZ-047 32.3% / ML-070 30.3% / SZ-051 26.7%) — the bot is,
  by measured behavior, a label factory; conviction trading is a
  rounding error of its activity (5 conviction vs 49 probe trips in
  the era-4 cohort).
- **Named human biases with our numbers:** disposition effect (MFE
  capture -3.341 while 87% of trades had upside — corrected by h432),
  fee blindness (booked 25/40 vs true 40/80; fees ate ~83-87% of gross
  realized at BOOKED schedule), overtrading (median ticket $18, below
  any fee floor), fear-herding (SZ-021 vetoed candidates won 0.509 vs
  baseline 0.265 — the gate herded WITH the fear). Registry entries
  TH-R-011..014.
- **Signal-lane split:** live probe labels win 0.154 (n=280) vs
  candidate corpus 0.320 (n=17,505) vs live conviction 0.308 (n=26) —
  the exploration tax visible in the label stream (caveat: label-era
  mix differs by lane; small conviction n).

Consequence: archetype tiers 1-3 need no invention — they have
recorded, replayable ground truth in our own history. Only the upper
rungs (experienced -> consistently profitable) lack an in-house
specimen; that is what reference implementations + the harness must
supply.

## 3. What actually exists to run a population — and the one seam that matters

Two disjoint worlds today (population-infra survey):

- **Engine-replay world** (`scripts/replay.py`, `scripts/sweep.py`,
  OF-4): runs the REAL engine deterministically on recordings, varies
  config knobs. Strategy injection exists at exactly one seam:
  `evaluate_asset` — the engine dispatches on `strategies.engine`
  (`main.py:752-757`), and `bot.gates.evaluate_asset` is already
  monkeypatched in 6 places (`overfit_check.py:360-363` et al.). An
  archetype = one `evaluate_asset` callable returning `SignalResult`.
- **Statistics world** (`walkforward_lab.py`, `cohort_eval.py`,
  OF-3/OF-5): post-hoc resampling of one realized fills ledger; cannot
  run a strategy at all.

**Decisive property: the deployed fill physics is reusable offline for
free.** `run_replay` builds a real LiquidityBot in `dry_run=True`
(`replay.py:75`), so fills go through `_poll_dry` / `_sim_maker_cross`
/ `_passive_poll_prob` (`execution/order_manager.py:1297,61-100`) —
the SAME code path that defines the era-4 honest-fill boundary
(`cohort_eval.py:89-93`). There is no separate backtest fill model to
drift. Isolation is already handled (`prepare_replay_config` redirects
all state paths to TMP and disables externals).

**What is missing (and none of it is a new framework):**

1. A population RUNNER: a loop over N `evaluate_asset` implementations
   × M seeded tapes through `run_replay`, with the determinism gate
   (`core/replay_gate.determinism_ok`) run per archetype. `sweep.py`'s
   conventions (rows -> `outputs/sweeps/*.csv`) are the template.
2. A strategy-keyed TRIAL LEDGER. This is not new bookkeeping — it is
   **the docketed TRIALS-1 artifact**: `deflated_sharpe` currently
   falls back to `var_trial_sr = SR^2` because no trial count or SR
   dispersion was ever recorded (`ml/overfit.py:861-862`;
   self-disclosed at `walkforward_lab.py:686-689`). A measured
   archetype population closes it with a real N and a real dispersion.
3. Multi-tape discipline: `make_offline_recording` is single-seed
   (77); ranking N archetypes on one 60-cycle tape is a coin flip —
   seeds become the resampling unit, and a cross-strategy
   multiple-testing correction (the repo has Bonferroni only within
   `geometry_search`'s 48 cells) is mandatory.
4. Event-level counterparty substrate: recordings carry NO trade
   prints or order events (`fill_hazard_report.py` header), so the
   grid-bot order-flow fingerprint (periodicity, cancel-to-fill,
   replenishment) is undetectable today — registry TH-R-007, blocked
   on a recording-capability adjudication.
5. Wall-clock trap for synthetic cohorts: `era4_trips` filters on
   absolute 2026-08-10 timestamps — pass `since=0.0` when feeding
   archetype ledgers to `walkforward_lab` or the cohort silently
   empties.

## 4. Capitalization: what "extremely flexible, controlled through constants and variables" already means here

There is **no cross-strategy capital allocator** in this codebase — one
signal engine at a time (`strategies.engine`), one shared risk
envelope ("the long book never gets its own risk stack",
`main.py:872-874`), no allocation vocabulary anywhere in code. What
DOES exist is a deep, guarded, single-strategy sizing pipeline
(PositionSizer Kelly core × multiplier stack × RiskProtocolStack
[CVaR/gap/budget/heat] × governor kelly_mult/shrinkage × inventory +
heat caps), ~20 governing config keys, config_guard-checked — with two
exceptions: **`position_sizer.kelly_fraction` and `kelly_cap` have
zero guard coverage** (SAFE-NOW guard-check candidate).

Eight existing seams where a family/archetype weight could attach
WITHOUT new machinery, ranked (capitalization survey): (1)
`PositionSizer.size(risk_scale=)` — already composes
`monitor.kelly_mult × explore_scale × manip_scale`; (2) a sibling cap
in `RiskProtocolStack`; (3) a second `EvidenceLadder` (the long book's
rung-gated equity fraction is structurally identical to "an arm earns
its ceiling"); (4) `GateStats` per-arm Wilson-LCB weights (bounded
0.7-1.3, era-keyed, never vetoes); (5) the probe budget's scarcity
pricing (a working across-arm allocator of label-buying budget — the
template mechanism); (6) the dark `admission.budget.surcharge`
channel; (7) the skimmer's promote-at-restart-boundary pattern; (8)
config_guard cross-block checks. **Every one of these is position
sizing = cohort-resetting = era-boundary adjudication material.**
"Flawless" is not a property this system recognizes; the honest
rendering is: config-governed, guard-checked, gate-bound, falsifiable
— with the lattice rule intact (evaluators never feed the learner
mid-era; changes flow back generationally through the docket,
`docs/quant/2026-08-19_referee_lattice.md`).

llm-wiki's role, confirmed: an operator-side vault skill outside this
repo (`scripts/vault_guard.py` is its in-repo half); all LLM/report
tooling is analysis-side with zero decision-path contact — which is
exactly where the registry sits.

## 5. Literature verdicts (fintech-quant survey, web-verified citations)

**The ecology thesis is established.** Strategy populations shape
returns and crowded naive rules leave detectable, self-defeating
footprints: Farmer 2002; Farmer-Joshi 2002 (common rules -> common
footprints); Scholl-Calinescu-Farmer 2021 *PNAS* (the closest
peer-reviewed statement of the operator's thesis); Lo's Adaptive
Markets; Khandani-Lo 2011 and Lou-Polk 2022 (crowding measured from
COMOVEMENT in real data). The validated measurement route is
footprints/comovement in real data — NOT a calibrated zoo of simulated
bots (LeBaron 2006: ABM results are calibration-fragile). Per-actor
attribution is unsupported — which this repo proved internally
(observational equivalence: honest maker byte-identical to attacker).

**Naive crypto flow has a signed, measurable footprint.** Kogan-
Makarov-Niessner-Schoar 2024 *JFE* (retail crypto traders are momentum
chasers); Barber-Odean line (naive/leveraged retail loses
predominantly to COSTS — the ladder's bottom rungs are net losers by
construction, exploitable mainly by the fee-advantaged counterparty,
not by another taker-tier retail bot). Grid/martingale bots
specifically: NO peer-reviewed corpus exists — vendor performance
claims are red flags, not benchmarks. Osler 2003/2005 remains the
peer-reviewed license for stop-cluster capture (TH-013).

**Null populations are orthodox; selection from them is the sin.**
White 2000 Reality Check / Hansen 2005 SPA (SPA is mandatory when
known-losing rules pad the universe — raw RC is mechanically weakened
by them); Sullivan-Timmermann-White 1999 (the canonical naive-rule
universe); Burns 2006 and Fama-French 2010 (simulated zero-skill
populations as nulls are standard); Arnott et al. 2013 (nulls are
meaningless unless costs and mechanics are matched — our
`random_entry_control.py` already meets that bar). Bailey-López de
Prado 2014 DSR needs the ACTUAL trial count and SR dispersion — the
exact hole TRIALS-1 names (`ml/overfit.py:861-862` runs on var=SR^2
and a default N=7). Harvey-Liu-Zhu 2016: building the ladder RAISES
our own strategy's required bar — correct if and only if trials are
honestly ledgered.

**The capitalization overlay is refuted at this sample size.** Michaud
1989 (estimation-error maximizer); Chopra-Ziemba 1993 (mean errors
~11x variance errors); DeMiguel-Garlappi-Uppal 2009 (1/N beats
fourteen optimizers; estimated allocation needs data windows we will
not have for years); Timmermann 2006 / Smith-Wallis 2009 (estimated
combination weights lose to equal weights); Cover 1991 / Cesa-Bianchi-
Lugosi 2006 (regret bounds vacuous at T≈54, and Blum-Kalai 1999: fees
destroy universal-portfolio guarantees at 40-80 bps/side). At
n_eff≈10-21 the only defensible overlay configuration is NO overlay —
constant weights, which the current single-strategy architecture
already is.

**Fee floor bounds every anticipation edge.** With $18 median tickets
and ~134 bps true round trip, the bp-scale edges this literature
documents (index flow, liquidation racing, basis) are under the floor
by an order of magnitude; speed races are winner-take-all to the
fastest (Budish 2015; Aquilina 2022) and structurally out of reach for
a 5s-snapshot spot bot. What remains reachable is what THALES already
targets: LARGE and SLOW footprints at multi-minute horizons via limit
entries — and the cohort's only lane above the cost-tolerance bar
(43-118 bps) is conviction (+1.46%/trip at true fees, n=5).

**Walk-forward standard.** Arian-Norouzi-Seco 2024: plain walk-forward
is the WEAKEST scheme at false-discovery prevention; the house battery
(purged expanding WF + CSCV-PBO + stationary bootstrap) is already
near best practice. Archetype backtests must inherit the house
purge/embargo/CSCV discipline or their outputs are inadmissible; every
added timeframe multiplies overlapping label windows and shrinks
effective n exactly as CLAUDE.md's standard warns.

## 6. Staged disposition — every component lands in an existing seam or an existing docket

**SAFE NOW (no adjudication needed; measurement/report class):**

- **S1. Archetype NULL battery + trial ledger** — N reference
  `evaluate_asset` archetypes (from the learning_symmetry 28-row
  matrix + frameworks-doc defaults) × M seeded tapes through
  `run_replay`, determinism-gated per archetype, results to a
  strategy-keyed ledger mirroring `sweep.py` conventions. **The
  population is a NULL and a trial ledger, never a selection pool**:
  SPA-form comparison (Hansen 2005 — mandatory once known-losing rungs
  pad the universe), both fee anchors (booked 25/40 AND true 40/80),
  uniqueness-weighted effective n, matched costs/mechanics (Arnott et
  al. discipline; `random_entry_control.py` is the house precedent).
  Closes TRIALS-1 twice over: (i) harvest the trials ALREADY evaluated
  (`outputs/tune_search_state.json`, `geometry_search` grids, OF-3
  `n_configs`) into a measured N and SR dispersion for
  `deflated_sharpe`; (ii) the archetype runs extend that ledger with a
  real population. The-method obligations before any number is
  quoted: planted-edge injection ranks first; an all-null population
  brackets zero at both fee anchors; the corpus line prints on every
  run. Buys the claim `cohort_eval` cannot currently make: "our net
  sits at percentile p of a zero-skill naive population under
  identical costs." Power honesty: at n_eff≈10-21 the deployed
  strategy will likely be indistinguishable from most of the
  population — the value is BOUNDING claims and disciplining future
  readouts, not a verdict now. Tier-1 rungs calibrate against the
  epoch-4 trace (the recorded bad bot). No rung is ever promoted by
  argmax; if one ever looks promotable, the only road is the existing
  one (shadow evidence -> OF battery -> G1-G5, post-freeze,
  post-boundary).
- **S2. Registry operations** — `docs/thales/REGISTRY.md` live;
  reviews bound to boundaries by test.
- **S3. Instrument hygiene from the THALES audit** — TH-012
  shuffle-null upgrade; TH-015 emitter-or-demote; doc reconciliation
  (TH-017, stale V2 text); `kelly_fraction`/`kelly_cap` guard checks.
- **S4. Funding/basis report-only series** (TH-R-008/009): funding is
  already fetched per-symbol (OKX), basis legs are already both in
  memory and only ever price-merged — deriving series is observation,
  not decisioning.

**AT THE ERA-4 READOUT ADJUDICATION (due at the printed readout —
54/50 crossed; the signed COST_BOUND arm is 2D + the staged fee-truth
package, per `docs/quant/2026-08-16_era4_readout_decision_table.md`):**
fee truth (TH-R-012), fewer-larger + CONC-1 + ALGO-5 (TH-R-013),
REG-8 v2 (TH-R-014), mixed-cohort ruling. The registry's B-section
rides this docket; nothing in it ships before the operator signs.

**AT FREEZE LIFT (pre-register first, through the head node):** any
archetype-derived features (candidate columns pre-named in the
registry); THALES advise promotion (double-count hazard resolved
first); any capitalization overlay experiment — and the overlay
enters as a MEASURED archetype in the battery before it ever touches
`risk_scale`.

**NEW-CAPABILITY ADJUDICATIONS (operator-only):** trade-print/order
event recording (unlocks TH-R-007); read-only OI/liquidation feeds
(TH-R-010, the ATTR-2 blind axis); the conduct-doc silence on trading
against predictable naive flow (a governance question, not a code
question).

**Explicitly rejected (with evidence, per the registry contract):**
per-counterparty exit-timing capture (TH-R-015 — unobservable in
public data); Backpack Exchange or any non-Kraken execution
(CLAUDE.md invariant 3 — the idea transfers, the venue does not);
"flawless algorithm" as a requirement (replaced by
falsifiable-and-bounded, §4).

## 7. Verdict

The operator's ladder is not a new direction — it is the completion of
THALES under governance that prevents a second rot. The literature
endorses the proposal exactly where this repo already built it
(footprint detection in shadow, matched null populations,
population-deflated evaluation) and refutes it exactly where it is
glamorous (a tuned allocation overlay on an n_eff≈10-21 population —
simultaneously an estimation-error maximizer, an unledgered selection
rule, and a cohort-resetting sizing change). The highest
value-per-risk item is S1: SAFE-class, existing harnesses only,
produces the trial ledger the overfit battery has been missing
(TRIALS-1), gives the deployed strategy a real population to be
deflated against instead of an assumed one, and calibrates its bottom
tiers on recorded ground truth. The capitalization layer is last in
line by design: at this effective n its only defensible configuration
is the constant-weight architecture we already run, and any future
overlay enters as a measured archetype in the battery — then the
boundary docket — before it ever touches `risk_scale`. The registry is
the memory that keeps all of it from being forgotten.
