# Multi-route learning — what shipped, what is barred, and the door back

*2026-08-18. Operator request: make the bot "simultaneously understand
things faster in the same manner it is now … taking more routes to
learning more effectively," citing the multi-agent stock-LLM architecture
family (role-specialized Bull/Bear researchers, iterative debate with
layered memory, multimodal fusion, DRL execution, RAG grounding).*

## What shipped: the learning panel

`scripts/learning_panel.py` — one command that runs every report-only
learning lens in the repo **concurrently** and writes a consolidated
panel (`outputs/learning_panel.{md,json}`): per-route status, duration,
and headline excerpt. The routes are the ~14 measurement tools that
already existed (lessons digest, cohort eval, gate truth/efficacy, cost
attribution/truth, corpus linkage, feature stability, horizon, fill
hazard, defensive cadence, interpretability, learning curve, per-asset
learning). This is the "more routes, simultaneously" ask delivered in
the only form current law permits: the bot's *measurement* bandwidth
widens; its *decision* surface does not move.

Each route keeps its own epistemic honesty — the panel reprints route
output rather than re-summarizing it, because several gates degrade
honestly (SYNTHETIC overfit corpus, sub-n cohort refusals) and a
consolidated paraphrase is exactly where such caveats get laundered out.

## What is barred right now, and by which law

| Requested capability | Status | Authority |
|---|---|---|
| Bull/Bear researcher agents, iterative debate, LLM memory loops in or feeding the engine | **REJECT** (standing) | `docs/research/2026-07-23_tradingagents_gap.md` §4 — LLM-in-engine violates determinism/auditability; every numeric output TA-style debate produces, this bot already computes deterministically and overfit-audited |
| New model families, features, meta-labeling (incl. patch-Transformer price encoders, RAG-grounded models) | **FROZEN** | CLAUDE.md, 2026-08-10 operator adjudication — model-side investment frozen until the era-4 gate readout; the retrain loop itself continues by design |
| DRL execution / any change to entry decisioning, sizing, stop-exit geometry, fill sim, fee booking, order lifecycle | **COHORT-RESETTING — forbidden without operator adjudication** | CLAUDE.md era-4 accrual moratorium (re-fenced at cut #7, geometry epoch `7-e7d5ca1a`) |

The refusal is not architectural conservatism; it is sequencing. The
era-4 gate (pre-registered n=50 honest-fill closes) exists to make ONE
decision decidable — NO_GROSS_EDGE / COST_BOUND / CONTINUE — and every
capability above would either restart that clock or add degrees of
freedom the overfit battery (OF-7) would have to pay for before the
current question is answered.

## The door back (post-readout pathway)

1. **Era-4 gate readout** at n=50 names which decision is decidable.
2. **ALGO-5** (stop widths + time-decay ladder, at ~30 uncensored paths)
   is the PRE-NAMED next geometry adjudication — it goes first, not any
   new learning architecture.
3. Model-freeze lift is an operator adjudication. If lifted, the
   2026-07-23 adoption ledger already ranks the adoptable multi-agent
   surface: offline measurement first (shipped: lessons digest, now the
   panel), advisory sentiment feeds second, macro structural inputs
   third with hard OF-7 guards — and LLM-in-engine stays REJECT
   regardless.

Effective-n reporting (n_eff, not row count, over concurrent trips) is
applied by `gate_truth_report` (since 2026-07-29) and `cohort_eval`
(since 2026-08-15); the other routes do not yet claim it, and their
SE-bearing figures should be read with that in mind.
