# 06 — Harvest survey: caching, routing, compression, compaction, format, batch (2024–2026)

**Citations** (per-claim): Lumer et al. 2026, arXiv:2601.06007 ("Don't Break the Cache");
Li et al., EMNLP 2024 Industry Track, arXiv:2407.16833 (Self-Route); Tam et al., EMNLP
2024 Industry Track, arXiv:2408.02442 (format restriction); Pan et al., Findings of ACL
2024, arXiv:2403.12968 (LLMLingua-2); Han et al., arXiv:2412.18547 (TALE); CompactionRL
arXiv:2607.05378, ACM arXiv:2607.23809, Slipstream arXiv:2605.08580, AGORA lineage
arXiv:2605.26596 (preprints, abstract-level); vendor batch-pricing docs (−50%).
Deep-read: Lumer, Li, Tam. Abstract-only: the rest ([I] per rule f).

## Claims + numbers

1. **Prompt caching for agents** (Lumer, 500+ sessions, 10k-tok system prompts, 3–50 tool
   calls): API cost −41–80%, TTFT −13–31% across OpenAI/Anthropic/Google. Naive
   full-context caching can INCREASE latency. Winning policy: static prefix first,
   dynamic content at prompt end, exclude dynamic tool results and dynamic
   function-calling patterns from the cached span; benefits only above provider
   min-cacheable-token thresholds.
2. **Self-Route** (Li): route to RAG unless the model self-reports it cannot answer, then
   escalate to long-context. GPT-4o 48.89 vs LC 48.67 vs RAG-only 32.60 at 61.40% of LC
   tokens; Gemini-1.5-Pro 46.41 vs 49.70 at 38.39% of tokens; ~57–82% of queries stay
   on the cheap path (per-model: 57.36% GPT-4o / 74.10% GPT-3.5-Turbo / 76.78% Gemini;
   the 82% is a Gemini first-step prose example). *(Corrected 2026-08-27: page
   previously printed "58–82%" — no 58% floor exists in the source.)*
3. **Output-length control** (TALE + successors SelfBudgeter arXiv:2505.11274,
   BudgetThinker arXiv:2508.17196): −67% output tokens / −59% expense; consensus that
   length control does not necessarily degrade reasoning quality.
4. **Prompt compression** (LLMLingua-2): 2–5x compression, up to 2.9x latency win on
   documents — BUT a later agentic audit (AGORA lineage) found extractive token-level
   compression "structurally inappropriate for agent settings": tool outputs / action
   grounding do not survive token deletion. **Compression is for documents, not agent
   scrollback.**
5. **Context compaction** (CompactionRL / ACM / Slipstream, 2026 preprints): production
   heuristics (reactive near-budget, periodic interval) are lossy and uncontrolled;
   2026 work trains compaction jointly with the task. Numbers not independently verified.
6. **Structured output vs prose** (Tam): strict schema constraints significantly degrade
   reasoning tasks (stricter → worse); classification largely unharmed. Cost-effective
   pattern: reason free-form, then reformat with a cheap model. Schema should WRAP, not
   constrain, the reasoning.
7. **Batch API**: Anthropic + OpenAI flat −50% in/out for non-latency-sensitive work —
   contractual pricing, stronger evidence than any paper. BatchGEMBA (arXiv:2503.02756):
   batching amortizes per-item instruction overhead, composes with compression.

## Limitations

- Lumer is a non-peer-reviewed preprint measured on 2025/26 provider pricing/semantics,
  which drift. TALE/LLMLingua-2/compaction numbers are abstract-level [I].
- The LLMLingua-agentic-failure audit table was not fetched (search-layer summary).
- Self-Route is QA benchmarks, not agentic CLI; self-reflection routing is itself an
  instrument that can be confidently wrong (the-method applies).
- Two arXiv IDs in the 2605–2607 range could not be triangulated against a second index;
  flagged, not settled.
- None of these face trading-style leakage controls; the analogous discipline is
  measuring savings on YOUR traffic (rtk gain, API cache-hit rates), not paper
  percentages.

## APPLICABILITY

- **Caching**: skill catalog + always-loaded CLAUDE.md/USAGE.md/MEMORY.md = exactly the
  static prefix the 41–80% figure amortizes. But gitStatus snapshot + session scratchpad
  path are DYNAMIC content injected early in system context — the canonical cache-breaker
  shape. Prefix ordering is harness-owned (upstream), but mid-session MCP/skill churn is
  ours to avoid → plan item 2. "Above provider minimums" + write-before-read maps to
  USAGE.md rule l (512-tok min, run-one-then-fan-out). Already law; enforce.
- **Self-Route = vault recall-before-derive in operational form** (USAGE.md rules 1/h):
  cheap retrieval path first, full re-derivation only when retrieval self-reports
  insufficient. The 1.12M-token workflow that re-derived a vault-held taxonomy is the
  LC-when-RAG-sufficed failure its ~57–82% routing rate quantifies. Already law; enforce.
- **LLMLingua-class compression: NOT APPLICABLE as deployed** — fails agentic settings,
  and rtk already does the right thing: lossless FILTERING of the variable suffix at
  source, sidestepping the action-grounding failure. rtk's counter is the instrument —
  first suspect when citing its 99.0%/125.6M numbers.
- **Trained compaction: NOT APPLICABLE** (training; we do not run inference
  infrastructure).
- **Structured outputs**: this environment's workflow contract (reason free-form in
  transcript, emit schema once at end) instantiates Tam's pattern correctly → codify so
  it survives (plan item 8). Never schema-constrain a judge/synthesis agent throughout.
- **Batch −50%**: USAGE.md rule m already names it; offline lanes (nightly digests,
  graded literature passes, cohort re-scores) are the fit → plan item 4.
