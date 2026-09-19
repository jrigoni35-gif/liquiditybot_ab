# Institutional judge — prep for the 09-22 opening (built 2026-09-19, SAFE-class)

**Classification: SAFE** — design document + vendored research reference +
downloaded corpus. No judge is wired anywhere; any judge output would be
advisory/measurement-plane until the operator adjudicates otherwise. Building
the *instrument* is SAFE; letting it touch entry decisioning, sizing, or exit
geometry is cohort-resetting and is NOT done here.

## What is in place today, and why it doesn't suffice

The current "judge" is the lens/refutation panel pattern (e.g.
`outputs/reports/config_debug_2026-09-08/judge_verdict.md`): lenses propose
claims about code/config, a judge verifies or refutes them against the repo.
It is a *correctness referee over engineering claims*. What it cannot do —
the operator's complaint — is reason about the thing the bot is FOR:

- it has no model of **institutional objectives** (fee-adjusted expectancy,
  capital efficiency, drawdown budget, capacity) and so cannot rank two
  technically-true findings by economic materiality;
- it never reads the *portfolio*: profit pooling across the 5m book vs the
  long book, heat/slot inventory, per-asset contribution, margin/leverage
  state (`leverage.use_margin` true since 2026-07-12);
- it does not understand the **data intake** — which of our computed numbers
  (fills ledger, audit chain, labels, readout) are population vs sample,
  stamped vs derived, censored vs complete — so it can't price how much a
  number should move a decision.

## What the new judge must understand (the rubric)

Adapted from how modern institutional desks are actually run, mapped to this
bot's surfaces:

1. **P&L attribution & profit pooling.** Every dollar of net P&L decomposed
   by book (5m / long), asset, lane (probe vs model-gated), and purpose
   (entry / exit / hedge / unwind). Known anchor: hedge+unwind = 80.5% of
   lifetime fees (HANDOFF edge-hunter, 09-01). The judge grades proposals
   against *which pool* they help or harm.
2. **Margin & heat management.** Heat frac vs cap (0.3766 vs 0.35 at the
   09-08 reading), slot inventory (5 slots, 2 held by the long book),
   leverage state. A judge that can't read `status.json` heat/slots is blind
   to the binding constraint half the time.
3. **Asset inventory & contribution planning.** Per-asset: realized net,
   fee drag in bps of notional, fill quality, regime fit (PAXG's
   decorrelation is a portfolio *asset*, not just a pair). The scaling
   governor (`docs/quant/2026-09-19_scaling_system_design.md`) already
   pre-registers quarter-Kelly edge-conditional sizing fed ONLY by the
   registration trip view — the judge must respect that feed boundary.
4. **Swing mechanics & failure anatomy.** To predict a swing you must model
   how one happens (aggressor imbalance → displacement → participation →
   exhaustion) and what a wrong call costs (adverse excursion distribution,
   give-back overlay behavior, the 10.6:1 trail/bracket asymmetry from the
   09-16 firing audit). The new 1m/5m corpus (dataset prep doc) is the
   study material; taker-buy imbalance + 1m path shape are the features.
5. **Epistemic discipline (already this repo's law).** Instrument-first,
   re-derive before citing, registered read points, one number = one
   hypothesis. The judge inherits `docs/law/mindset.md` wholesale.

## Architecture — proven pattern, vendored

**Downloaded: `research/vendor/TradingAgents/` (8.5 MB, shallow clone of
github.com/TauricResearch/TradingAgents, arXiv 2412.20138, ~60k stars).**
It is the closest shipped system to the brief: specialized analyst agents →
bull/bear researcher debate → trader proposal → **risk-management committee
(aggressive / conservative / neutral debators) → portfolio manager with
structured verdict output** (`tradingagents/agents/risk_mgmt/`,
`agents/managers/portfolio_manager.py` — typed `PortfolioDecision`,
rating scale, "commit to the stronger case sized by how decisively it wins;
Hold only when evidence is balanced or thin"). That PM-plus-risk-committee
pattern is exactly the judge shape to copy; read it in an afternoon.

Evaluated and deferred, with reasons:

- **FinRL (AI4Finance)** — RL portfolio allocator; a *policy learner*, not a
  judge, and model-side investment is frozen by the 2026-08-10 adjudication.
- **FinRobot / FinMem / PIXIU-FinBen** — agent/benchmark suites; equity
  fundamentals focus, no inventory/margin model; benchmarks could later
  grade the judge itself.
- **OpenBB** — institutional data intake; overlaps installed plugins
  (yahoo_finance, sec_edgar, imf, world_bank) already callable for
  macro/fundamental context.
- **Kimi plugin marketplace** — searched 2026-09-19 ("portfolio risk
  analytics", "crypto order book data", "quantitative trading backtest",
  "financial statement analysis"): **zero installable matches**.

## Proposed judge construction (design only — nothing built into the engine)

Three layers, all measurement-plane:

1. **Intake contract (the part the operator flagged).** The judge reads a
   frozen bundle per case: `fills.csv` slice + `audit.jsonl` window +
   `status.json` + the era_readout row + scaling_report output + the new
   kline corpus slice. Each field stamped population/sample, stamped/derived,
   censored/complete. No live reads mid-judgment.
2. **Committee.** Desk roles instead of generic lenses: Portfolio/Pooling
   desk, Margin/Heat desk, Inventory/Contribution desk, Swing-anatomy desk,
   and a Refuter that must attempt to kill each desk's claim against the
   raw bundle (the existing claim_check/mutation discipline, promoted into
   the judge). Portfolio-manager node issues the structured verdict:
   Materiality × Confidence × Affected-pool × Required-action-class
   (SAFE / boundary / refuse).
3. **Scoring against objectives.** Verdicts ranked on fee-adjusted dollars
   at the booked tier (15/30), heat-days, and cohort cost (does acting mint
   a boundary?) — the three currencies this project actually pays in.

**Gating:** even a built judge stays advisory; any route from judge output
to entry/sizing/exit is cohort-resetting and belongs in the same docket
class as R2. First milestone if approved on 09-22: build layer 1 (intake
bundle) + run the committee over the era-9 readout as a rehearsal judgment,
recorded in `docs/quant/`.

## Files this prep added

- `research/vendor/TradingAgents/` — reference implementation (unmodified)
- `research/corpus/binance_vision/` + `docs/quant/2026-09-19_dataset_prep.md`
- `scripts/fetch_binance_vision_1m.py` — dataset builder (SAFE tooling)
