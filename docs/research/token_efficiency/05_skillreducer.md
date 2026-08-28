# 05 — SkillReducer: agent-skill compression

**Citation**: Gao, Li, Yuan, Ji, Ma, Wang. "SkillReducer: Optimizing LLM Agent Skills for
Token Efficiency." arXiv:2603.29919 (v1 2026-03-31, v2 2026-06-24), cs.SE.

## Claims

- Agent skills (Anthropic SKILL.md protocol) are systemically bloated: of 55,315 wild
  GitHub skills, 26.4% lack routing descriptions; only 38.5% of body content is
  actionable core rules (40.7% background, 12.9% examples, 7.6% templates); reference
  files inject up to 1.67M tokens across 100 skills.
- Two-stage optimizer: Stage 1 compresses/generates routing descriptions via adversarial
  delta debugging validated against actual Claude Code CLI routing; Stage 2 restructures
  bodies via taxonomy classification + progressive disclosure (core rules always-loaded;
  examples/background moved to on-demand reference modules), gated by faithfulness check
  and task-based eval with self-correcting feedback loop.
- **Less-is-more**: compressed skills OUTPERFORM originals (+2.8%, 0.742 vs 0.722) —
  removing non-essential content reduces context distraction.
- Transfers across models/frameworks without re-optimization (retention 0.965 across 5
  models; 0.944 on OpenCode); beats LLMLingua 0.820 / direct-LLM 0.918 / truncation
  0.845 / random 0.750 at equal budget (SkillReducer 0.949).

## Numbers

- Description compression 48% mean; body 39% (~1,000 tok/skill); SkillsBench per-task
  context 359K→84K (75%); wild sample 77.5% (no task-level validation on that sample).
- Quality: 86.0% pass (CI 83.1–88.7%); 25.3% improved / 60.7% maintained / **14.0%
  regressed**; routing preservation 536/536; +2.8% mean score.
- Reference dedup retention 1.000 — pure cost win, no task impact.
- Optimizer cost ~20–40 LLM calls/skill, ~$14–18 for 600 skills; 10.7% of skills found
  obsolete.

## Limitations

- Gate 2 is both optimization signal and evaluation criterion — selection-rule
  contamination (OF-3 shape, authors concede); cleaner evidence = held-out SkillsBench
  87/87 and cross-model retention.
- SKILL.md protocol only; wild 77.5% figure lacks task validation entirely.
- Rules embedded implicitly in examples lose dependencies under automated separation —
  the +2.8% mean coexists with a 14% regression tail: per-skill validation mandatory,
  blanket application forbidden.
- Compression rates are corpus-relative: hand-curated terse instruction sets (this
  operator's CLAUDE.md/USAGE.md) sit far from the 60%-non-actionable wild baseline —
  39–48% does NOT transfer as-is.

## APPLICABILITY

- **Direct hit on this box's largest fixed toll.** The skill LISTING re-grew to ~80+
  entries (~42k tok/request class) via plugins after the 2026-08-20 manual trim. The
  manual trim is crude Stage 1; the paper's routing-preservation validation (delta
  debugging against Claude Code itself) is the principled version → plan item 1.
- Progressive disclosure is a principle this repo independently derived: CLAUDE.md
  deliberately exiles dated numbers to the vault ("a number written into law decays into
  a false claim"). The paper adds the quantitative case (38.5% actionable in typical
  bodies) for auditing USAGE.md/MEMORY.md the same way → plan items 5/6.
- Less-is-more reframes prefix compression as an ACCURACY intervention (context
  distraction), not just spend — compounding with 2x-write/0.1x-read cache economics on a
  smaller stable prefix.
- Reference-module dedup (retention 1.000) = the safest compression class: move
  rarely-used content behind on-demand loads, don't rewrite it. Deferred tool schemas
  (ToolSearch) are the tool-call analogue, already active.
- Tiering hook: compress with cheap model, validate with a stronger judge + deterministic
  verifiers (kappa=0.939) — matches USAGE.md rules j/k and the instrument-first doctrine.
- Adoption gate (instrument is first suspect): a compressed/parked skill that silently
  stops routing is exactly the "confident instrument, wrong, nothing flagging it"
  failure. Spec: trim parked-catalog first, A/B route-trigger tests on active skills,
  retention floor ≥0.95 per skill, regressors reverted individually.
