# 07 — Implementation plan: permanent token-efficiency injections

Ranked by expected-tokens-saved / implementation-risk. All items are measurement/config
plane (SAFE class per CLAUDE.md era-4 rules — none alter which orders are placed or how
they fill). Baselines cited from README.md snapshot 2026-08-27; every item's saving is
arithmetic on those baselines, and every item carries a VERIFY step because per
the-mindset the instrument (including rtk's own counter and any paper percentage) is the
first suspect.

**rtk scope note**: rtk is a compiled binary routed via hook. Configurable here: the hook
rewrite rules, which commands get proxied, and routing around known quirks (USAGE.md
rule 4). NOT editable: its filters/summarizers — improving e.g. grep savings is an
UPSTREAM REQUEST, not a local change.

---

## 1. Re-measure, then re-trim the skill-catalog listing — REQUIRES-OPERATOR-SIGNOFF (trim list)

- **What**: The per-request skill LISTING re-grew to ~80+ entries (sc:* ~30,
  superpowers ~15, artifact/design/etc) after the 2026-08-20 trim — the previously
  measured ~42k tok/request toll class. (a) Re-measure the current listing cost first
  (`/context` or system-prompt token count — the 42k is a class label, not today's
  number). (b) Propose a trim list: park the sc:* block and superpowers set unless the
  operator uses them (plugin-delivered — disable/park at the plugin or
  `~/.claude/skills` level, per the claude-skills-install memory procedure); keep the
  ~8-15 with measured routing hits. SkillReducer's method is the principled version:
  validate routing preservation per kept skill, revert regressors individually (its 14%
  regression tail forbids blanket application).
- **Expected saving**: if the listing is again ~42k-class and trims to a ~10k-class
  active set: ~30k tokens/request context occupancy. Cached (0.1x read, Fable 5 $10/M):
  ~$0.03/request read-side + avoided 2x cache-write on 30k (~$0.60) per 1h-TTL window.
  Over a 100-request session: ~3M raw prefix-tokens not carried. Largest single lever on
  the board.
- **Risk**: a parked skill silently stops routing — the "confident instrument, wrong,
  nothing flagging it" shape. Mitigation = injection test: issue a prompt that should
  trigger a parked skill, confirm the miss is LOUD (skill absent from listing, not
  half-loaded).
- **VERIFY**: before/after system-prompt token measurement same-day; then a week of
  $/session from API usage. Signoff because skill availability is operator environment
  policy (the all-active state was itself a past operator instruction).

## 2. Cache-discipline enforcement: no mid-session prefix churn — auto-apply

- **What**: Lumer: dynamic content inside the cached span and dynamic function-calling
  patterns are the canonical cache-breakers; naive caching can cost MORE. Locally
  controllable: (a) never load/unload MCP servers or toggle skill/plugin sets
  mid-session (the mythos-router block appearing mid-conversation this session is
  exactly such a churn event) — restart instead; (b) enforce USAGE.md rule l's
  run-one-then-fan-out in every workflow script (concurrent agents cannot read a cache
  still being written); (c) identical CONTEXT/RULES fan-out prefixes byte-stable, >512
  tokens. Prefix ORDERING (gitStatus/scratchpad injected early) is harness-owned —
  UPSTREAM, note only.
- **Expected saving**: cache read 0.1x vs full-price re-write at 2x (1h TTL): each
  avoided prefix invalidation on a ~10k-tok instruction block + catalog saves ~1.9x its
  size in billed input per subsequent request-window. Not a fixed number — measured, not
  claimed (Lumer's 41–80% is their traffic, not ours).
- **Risk**: none — no capability lost; pure sequencing/hygiene.
- **VERIFY**: `cache_read_input_tokens` / `cache_creation_input_tokens` ratio from API
  responses over a week of real traffic, before vs after; claude-api skill for the
  current field names, never memory.

## 3. Budget-triage stage in the delegation prompt pattern (TALE-EP) — auto-apply

- **What**: Extend the USAGE.md rule-i prior-art Haiku pass to also emit, per delegated
  task: model tier + effort + an output-budget hint spliced into the subagent prompt —
  a cheap estimator call instead of hand-set per-phase settings (rules j/k made
  per-task). Add to the standing workflow prompt template alongside the
  delegated-measurement contract. TALE's elasticity clause goes in verbatim as a floor
  rule: never effort=low on verify/judge/synthesis — below the feasible range the model
  reverts to long reasoning and cost goes UP (the 5-of-9-wrong-numbers shape).
- **Expected saving**: TALE-EP measured −67% output tokens on math QA; unverified for
  agentic work — claim only the direction. Local anchor: the monoculture incident was
  61 agents / ~5.6M tokens all at session-model/effort-high; per-task tiering attacks
  the same overspend the rules h-m law already names. Estimator overhead ~1 Haiku call
  per task (~$1/M) — negligible against Fable 5 output at $50/M.
- **Risk**: elasticity backfire if the estimator under-budgets hard stages (mitigated by
  the judge-stage floor); estimator itself can be confidently wrong (it is an
  instrument).
- **VERIFY**: per-workflow token totals from API usage on two comparable workflows
  (triaged vs rules-as-written), plus rework count. Do not adopt the paper's −67% as an
  expectation.

## 4. Batch API routing for offline lanes — auto-apply

- **What**: USAGE.md rule m is law but has no enforcement point. Add a standing check to
  workflow launch: non-latency-sensitive lanes (nightly/session digests, graded
  literature passes like this one, cohort re-scores, bulk re-labels) go through Message
  Batches. Verify current mechanics via the claude-api skill at implementation time.
- **Expected saving**: contractual −50% in/out on everything routed — the only number in
  this plan that is pricing, not measurement. A 5M-token offline workflow at Fable 5
  rates: ~$25+ halved; batching also amortizes per-item instruction overhead
  (BatchGEMBA).
- **Risk**: latency (hours-scale turnaround) — by definition acceptable for these lanes;
  misclassifying an interactive lane as offline would stall a session (lane list is
  explicit, opt-in).
- **VERIFY**: invoice/usage delta per workflow class, batch vs interactive, one week.

## 5. MEMORY.md progressive-disclosure trim — auto-apply

- **What**: MEMORY.md 8,135B (~2.3k tok/request). It is an index over per-topic files
  that already exist — SkillReducer Stage 2 (core always-loaded, detail on-demand) plus
  its safest class, dedup (retention 1.000). Tighten each index line to
  link + one-clause pointer; move residual detail into the topic files. Target ≤6,000B
  (~−600 tok/request, every request).
- **Expected saving**: ~600 tok/request raw; at 0.1x cached read, small in $ — the case
  is less-is-more (context distraction) plus a smaller stable prefix to cache-write at
  2x per TTL window.
- **Risk**: an over-trimmed index line stops surfacing its topic file (routing loss,
  silent). Mitigation: keep every trigger keyword; per-line review, not bulk rewrite.
- **VERIFY**: byte count before/after; injection — ask a question whose answer lives in
  a topic file, confirm the file still gets pulled.

## 6. USAGE.md + project CLAUDE.md compression — REQUIRES-OPERATOR-SIGNOFF

- **What**: USAGE.md 10,038B and project CLAUDE.md 14,307B are the operator's binding
  law — Claude does not edit law unprompted. Deliver candidates only: (a) USAGE.md
  target ~7,500B (−2.5KB ≈ −700 tok/request): the rtk-quirks narrative and dated
  incident prose compress to pointer form (vault holds the full accounts); every rule
  a-m survives verbatim. (b) project CLAUDE.md target ~12,000B (−2.3KB ≈ −650
  tok/request): the MINDSET recurrence list (6 bullets of measured incidents) moves to
  the vault page it already cites, leaving the operating consequences; hard invariants,
  moratorium, DoD untouched — byte-for-byte. SkillReducer caveat applies: these files
  are hand-curated and terse, far from the 60%-non-actionable wild baseline — expect
  the LOW end of gains, and the 14% regression tail is why this is signoff-gated: a
  hard invariant or contract clause missing from context is a safety regression, not a
  savings.
- **Expected saving**: ~1,350 tok/request combined if both accepted (~14% of the
  always-loaded ~9-10k).
- **Risk**: highest on the board relative to size — behavioral drift from lost law
  context. Mandatory clusters (invariants, era-4, contracts a-g, backpack) are excluded
  from candidacy entirely.
- **VERIFY**: byte counts; then injection per SkillReducer — pose a task each moved
  clause governs, confirm the session still cites/obeys it (routing-preservation test),
  regressors reverted individually.

## 7. Mid-trajectory checkpoint for long delegated agents (MSIFR S2) — experimental, auto-apply as trial only

- **What**: For fan-out agents expected to run long, add a cheap validator pass at ~50%
  (orchestrator peeks at partial output): boundary/needle named per the
  delegated-measurement contract? magnitudes sane? spec being filled silently? Kill and
  respawn with a corrected spec on failure — cheaper than grading a finished wrong
  answer.
- **Expected saving**: unvalidated magnitude (MSIFR's 78.2% headline is composed +
  single-benchmark; standalone floor 1.4%). Local anchor: one under-determined spec
  produced 5 of 9 wrong numbers — the rework, not the paper, is the case.
- **Risk**: false rejection kills a good agent mid-flight (paper self-reports <5%,
  unaudited); validator rules are fitted literals needing local derivation; checkpoint
  overhead never isolated in the paper.
- **VERIFY**: A/B on comparable workflows vs no-checkpoint, tracking total tokens
  INCLUDING validator + respawn cost; per MSIFR's missing null, compare against
  matched-rate random respawn before crediting the validator rules.

## 8. Codify structured-output discipline in workflow templates — auto-apply, ~0 tokens

- **What**: One line in the standing workflow prompt template: reasoning agents reason
  free-form in transcript and emit schema ONCE at the end; never schema-constrain a
  judge/synthesis agent throughout (Tam: strict format restriction measurably degrades
  reasoning; classification unharmed). Cheap-model reformat is the repair path for parse
  errors.
- **Expected saving**: none direct — this is a quality guard that prevents silently
  paying full price for degraded judge output. Zero risk.
- **VERIFY**: none needed beyond template review; the current contract already complies —
  the injection is making it permanent so it survives template edits.

## 9. rtk grep coverage — local routing now, upstream request for the rest

- **What**: `rtk grep` averages 23.9% savings vs the read-class 99%+ (baseline). Local
  (configurable): keep routing content-search to the dedicated Grep tool, which bypasses
  bash+rtk entirely and is already the environment's stated preference — the hook only
  matters for residual bash grep. Upstream (NOT locally fixable — compiled binary): file
  a request for stronger grep-output summarization (count-mode defaults, match capping).
- **Expected saving**: bounded by residual bash-grep traffic share — read it from
  `rtk gain --history` per command class (MSIFR lesson: never quote filter savings as
  one number), remembering rtk's own counter is the instrument being read.
- **Risk**: none locally.
- **VERIFY**: `rtk gain --history` grep-class share and savings before/after a week of
  routing discipline.

---

## Explicitly NOT APPLICABLE (model-weight / serving-stack access — we do not run inference infrastructure)

- BE-token soft-prompt compression (02) — embedding-layer training.
- TALE-PT fine-tuning (01) — white-box post-training.
- LLMLingua-class extractive compression (06) — fails agentic settings besides; rtk's
  lossless source-filtering is the correct local instrument.
- Trained context compaction / CompactionRL (06) — training loop.
- LYNX/speculative-rejection decoding composition (04) — decoding-level control.

## Standing constraint

Nothing above touches CLAUDE.md hard invariants, the era-4 moratorium, overfit gates, or
any decision-path code. Items 1 and 6 modify operator law/policy surfaces and are
REQUIRES-OPERATOR-SIGNOFF; the rest are workflow/config hygiene. Every adopted item's
saving is credited only from its own before/after measurement on this box's traffic —
paper percentages set direction, never magnitude.
