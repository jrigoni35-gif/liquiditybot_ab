# 03 — DSM clustering of LLM conversations

**Citation**: Garcia Alarcia, R.M. & Golkar, A. "Optimizing Token Usage on Large Language
Model Conversations Using the Design Structure Matrix." 26th Intl DSM Conference (DSM
2024), Stuttgart; DOI 10.35199/dsm2024.08, pp. 069-078; arXiv:2410.00749. TU Munich.

## Claims

- Model an interdependent LLM design conversation as a DSM (elements × dependencies),
  weight cells by element token counts (worst case: all tokens cross every marked edge).
- Classical DSM clustering (J = alpha·sum|C| + beta·I0, alpha>beta; Damasio 2017 via
  DesignStructureMatrix.jl) partitions the conversation into pieces that each fit context
  window + output limit.
- Warfield-1973 reachability sequencing orders pieces so upstream info exists before
  downstream pieces need it.
- Spacecraft use case: single-shot conversation VIOLATES the output-token limit; after
  clustering+sequencing into 4 pieces, everything fits — feasibility restored without a
  bigger model.
- Frame: token budgeting is a decomposition problem, not (only) a compression problem.

## Numbers

- 13x13 DSM, ~31 dependencies, 2 clusters, 4 conversation pieces.
- Limits used: 32,000-tok window / 8,192-tok output (Mistral 7B), 5% margin.
- Pre: window fits (+10,399) but output limit VIOLATED (−1,427). Post: window budgets
  462 / 1,438 / 7,703 / 16 tok; all output cushions positive (tightest +103).
- No quality metrics of any kind — the only quantitative claim is budget feasibility.
- [I] WB composition (21,601) not re-derivable from the extract; extraction-proxy caveat.

## Limitations

- Clusters identified VISUALLY, not algorithmically; scalability beyond 13 elements
  unproven.
- Worst-case edge weighting systematically overestimates cross-piece context needs.
- Single use case; requires a pre-existing structured domain model (OPM).
- Zero evaluation of answer QUALITY after partitioning; context loss "mitigated" by
  sequencing is asserted, never measured. No baselines (summarization/RAG/truncation).

## APPLICABILITY

- **Algorithm as-published: not applicable** (needs a hand-built domain DSM; no quality
  evidence). **Principle: already half-deployed.** Subagent fan-out with per-agent
  context = "allocate chunks to different windows"; the paper adds the missing formalism —
  sequence by reachability so a downstream agent's prompt contains its upstream
  dependencies' OUTPUTS. That is the delegated-measurement contract's name-the-needle /
  name-the-boundary rule stated graph-theoretically → codified in plan item 3's prompt
  pattern.
- Skill-catalog trim IS this paper's move done by hand: drop elements with no dependency
  edges to the current task. A co-usage pass (which skills ever fire per task class)
  would make the active-set selection principled → plan item 1's trim-list method.
- Conditional instruction loading (cluster CLAUDE.md/USAGE.md by task class) is the
  paper's shape, BUT: a hard invariant missing from context is a safety regression — the
  CLAUDE.md core is a mandatory cluster, not a partitioning candidate. Signoff-gated.
- Cache interpretation the paper misses: under 0.1x-read/2x-write economics the
  alpha/beta weights flip — order pieces so the shared prefix is maximal and STABLE
  (re-reading stable prefix ~free; restating cross-cluster context full-price). This is
  USAGE.md rule l, formalized.
- rtk shrinks per-element token counts (DSM cell values); DSM shrinks elements per
  request — orthogonal, multiplicative. `rtk gain --history` could supply real
  per-element weights to replace the worst-case assumption.
- Deferred tool schemas are the degenerate DSM case: empty dependency row until the tool
  is plausible — edge-triggered loading a static matrix cannot express. Already deployed.
- Any adopted trim is measurement-plane (SAFE) but per the-mindset must be verified by
  injection: plant a task needing a parked skill, confirm the failure is LOUD.
