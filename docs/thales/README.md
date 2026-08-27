# docs/thales/ — the exploitable-mistake registry and its contract

THALES's thesis (docs/THALES.md): other participants' predictable
mistakes are capturable. This folder is where that thesis is
**governed**: every human/naive-bot mistake we believe is capturable
for profit gets a REGISTRY entry, and every entry MOVES — toward
incorporation or toward an explicit, evidence-backed rejection. A
write-only idea graveyard is forbidden here by contract.

## The failure chain this folder exists to prevent (operator, 2026-08-27)

> add -> add -> add -> never incorporate even though it should go under
> the same circumstances -> conclude failed due to poor configuration
> -> be forgot.

THALES itself is the founding cautionary case: built and audited by
2026-07-29, then frozen at `influence: "shadow"` with its promotion
bar never fed, while five detector scores shipped into the live ML
lane by side door without the gates its own doctrine requires, its
docs went stale against the code in six places, and one detector
(TH-015) became a live feature with no audit-trail emitter. That is
the chain above, mid-execution. The registry + the rules below are
the counter-mechanism. Full state map:
`docs/quant/2026-08-27_thales_ladder_analysis.md`.

## Lifecycle (every entry carries exactly one status)

| status | meaning |
|---|---|
| REGISTERED | named and scoped; no measurement yet |
| EVIDENCED | measured at least once, instrument cited |
| STAGED | packaged for a NAMED adjudication (the trigger names it) |
| INCORPORATED | live in the system (entry says exactly where) |
| DORMANT | incorporated but not firing / channel inert — still reviewed |
| REJECTED | closed with evidence; terminal (reopen condition may be named) |

## The contract (binding)

1. **Every entry is complete.** Summary row (id, mistake, status,
   trigger, reviewed) plus a detail block with Footprint, Capture,
   Evidence, Falsifier. `tests/test_thales_registry.py` enforces the
   schema — an incomplete entry is a red suite.
2. **No silent aging.** `REGISTRY.md` declares `last_boundary:` (the
   most recent execution-era boundary). Every NON-TERMINAL entry's
   `reviewed` stamp must be on or after that date. When a boundary is
   minted, whoever updates `last_boundary` inherits the duty the test
   then enforces: advance, re-stamp, or reject every entry. Rot is a
   test failure, not a mood.
3. **Every entry names its falsifier.** What observation kills it. An
   entry that cannot be killed cannot be believed either.
4. **Registration is SAFE-class; incorporation is not.** This folder
   never changes which orders are placed or how they fill. The road
   INTO the decision path is unchanged law: era-boundary adjudication
   for cohort-resetting changes (CLAUDE.md moratorium), model-freeze
   lift for new features, both through the operator head node of the
   lattice (docs/quant/2026-08-19_referee_lattice.md — checking is
   mutual, feeding is not; evaluator output never feeds the learner
   mid-era). The registry's job is to make the queue visible and
   reviewed, never to bypass the fence.
5. **Incorporation is a diff, not a design.** Each entry pre-names its
   candidate feature columns and audit code where applicable, so when
   its trigger fires the change is mechanical and reviewable.
6. **Both directions count.** Section A registers OTHER participants'
   mistakes (capture as edge). Section B registers OUR OWN measured
   mistakes (capture as correction, and as calibration ground truth
   for the archetype tiers — the bot's own epochs are the recorded
   bad-to-intermediate specimens).
7. **Conduct boundary stands.** Detect-and-react only (THALES hard
   boundary, docs/THALES_FRAMEWORKS.md): we never place, space, or
   time an order to induce anyone's behavior.
   `docs/compliance_market_conduct.md` is currently SILENT on trading
   against predictable naive flow — that governance question is
   itself registry material and goes to the operator, not to code.

## Consumers

- **llm-wiki / vault**: the operator-side llm-wiki skill (outside this
  repo; `scripts/vault_guard.py` is its in-repo half) mirrors settled
  entries into vault concepts. This file and REGISTRY.md are written
  to be ingested as-is.
- **Neural network / ML**: receives NOTHING from here directly. At
  freeze lift, pre-named feature columns go through the normal
  schema/battery road (ml/features.py, overfit battery, quant gates).

## Layout

- `docs/THALES.md` — doctrine + detector catalogue (legacy path kept;
  12 in-code references point at it).
- `docs/THALES_FRAMEWORKS.md` — naive-framework footprint reference
  (freqtrade / Hummingbot defaults).
- `docs/thales/REGISTRY.md` — THE registry (this folder's core).
- `tests/test_thales_registry.py` — the contract's teeth.
