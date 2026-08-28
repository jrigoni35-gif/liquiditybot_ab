# 02 — Behavior-Equivalent Token: single-token prompt replacement

**Citation**: Dong, Jia, Peng, Wang, Wang, Su, Sun, Wang, Yin, Zhao. "Behavior-Equivalent
Token: Single-Token Replacement for Long Prompts in LLMs." arXiv:2511.23271 (cs.CL),
2025-11-28.

## Claims

- One learned prompt-specific token ([BE]) replaces an entire long system prompt (up to
  ~3000x reduction) at ~98% downstream task performance.
- Three stages: (0) universal [AE] auto-encoder trigger token per backbone; (1) train only
  the [BE] embedding to reconstruct the target prompt (model frozen); (2) distill behavior
  via KL between teacher (full prompt) and student ([BE]) on unlabeled queries
  (lambda=0.9, tau=2).
- Reconstruction alone fails (0–51%); soft prompts alone unstable (11–65%); behavior
  equivalence — not content equivalence — is the correct target.
- Beats encoder-based PCC, which degrades with shot count (74.91%→63.76% on GSM8K) while
  [BE] holds 79.05% vs 80.56% full-prompt.

## Numbers

- Compression: 337 tok→1 (RoleLLM); ~1,500x (GSM8K 8-shot); ~3,000x max (HPD);
  degradation begins beyond ~3,750 source tokens.
- Retention band 92–103% across Llama-3.2-1B/3B, Llama-3.1-8B, Qwen3-4B.
- HPD perplexity 17.99 with [BE] vs 26.08 full prompt (BETTER than teacher).
- TTFT −9–23% (337-tok prompt), −28–59% (1,584-tok); theoretical prefill speedup
  13.5–27.8x.

## Limitations

- Needs gradient access to the input embedding layer — white-box at the input. Cannot
  inject a learned soft embedding through a token-in/token-out API.
- One [BE] per prompt per backbone; any prompt edit invalidates it (retrain Stages 1–2).
- Single-turn only; multi-token composition untested; offline benchmarks only.
- Sweet spot ends ~3,000–3,750 source tokens — nowhere near 40k+ agent-CLI contexts.
- 98% is a point estimate without null or CI; >100% retention cells and improving
  perplexity under compression are the classic tell of judge/metric noise. Unvalidated
  headline by this repo's standard.

## APPLICABILITY

- **NOT APPLICABLE — requires model-weight/embedding access; we do not run inference
  infrastructure.** No soft-embedding injection exists through the Claude API.
- API-feasible discrete cousins, already deployed here: skill-catalog trimming
  (8 active / 328 parked class) and deferred tool schemas (ToolSearch) — same overhead
  class the paper targets.
- Prompt caching is the closed-model substitute: removes recompute cost (the paper's
  prefill-speedup target) but NOT context-window occupancy. For Claude Code the window
  occupancy of the fixed prefix is the unaddressable part — only trimming shrinks it.
- Per-edit retraining cost maps onto a truth CLAUDE.md already codifies: "a number
  written into law decays into a false claim" — a distilled token of a stale prompt is
  the same failure, frozen and invisible.
- For multi-model fan-outs, shared cached text prefixes (USAGE.md rule l) beat any
  learned-token scheme even where weights are open (per-tier training pipeline required).
- Frame worth keeping for rtk: reconstruction-only compression fails; the right target
  for output filtering is preserving downstream agent BEHAVIOR, not textual fidelity.
