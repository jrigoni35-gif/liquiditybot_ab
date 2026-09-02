# Instrument verification standard

**What this is.** The minimum an LLM-written measurement instrument must clear before
its number is quoted, acted on, or written into a permanent file. Eight checks, each
anchored to either a primary source or a dated incident in this repo.

**How to use it.** Reference it BY PATH in every delegated prompt that produces a
number (`docs/INSTRUMENT_VERIFICATION_STANDARD.md`) rather than pasting it — single
source of truth, no drift. A subagent does not inherit the parent's context, so an
unstated standard is an absent standard.

**Provenance.** Derived 2026-09-02 from deep-research run `wf_c5fac112-377`
(106 agents, 3-vote adversarial verification) plus this repo's own measured
incidents. Full ledger, including what did NOT survive verification:
`vault/raw/research/2026-09-02_deep_research_llm_instrument_reliability.md`.
Tags: **[K]** anchored in a primary source read verbatim · **[I]** inferred from our
own incidents, literature silent.

---

## The eight checks

**1. Cross-implementation, or it did not happen.** A load-bearing number must be
reproduced by a second, independently written implementation before it is acted on.
Not a re-read of the same code — a different route.
*Anchor [K]:* EvalPlus found **18 of 164 (11%)** of HumanEval's own human-written
reference solutions defective, and found them *only* by differential testing against
a second re-implementation (NeurIPS 2023, arXiv 2305.01210). *Ours:* the unpinned
time-sort and the unpinned day-block width (2026-09-02) were caught exactly this way.
**Best-supported item on this list.**

**2. Green tests are not evidence until the suite is shown to fail.** Plant a defect,
watch the pin go red, restore byte-identically, report the table. **The defect must be
chosen by someone other than the instrument's author.**
*Anchor [K]:* DS-1000 §2.3, "Functional correctness alone is insufficient"
(arXiv 2211.11501); EvalPlus's ranking *inversion* under a stronger suite.
*Ours:* both 2026-09-02 defects passed all twelve of the author's own pins **and** its
self-test.

**3. Clean execution is not a signal at all.** Never report "the script ran" as partial
validation.
*Anchor [K]:* BLADE (Findings of EMNLP 2024, arXiv 2408.09667) — GPT-4o emitted a
non-empty executable analysis **96%** of the time while its best agreement with expert
analytical decisions was **F1 44.8** (95% CI 43.0–46.3). Separately DS-1000's best
system at publication solved **43.3%** of 1,000 problems.

**4. A placebo or null arm ships in the same commit as the effect.** Time-shift, label
shuffle, reflected-reference control — run *before* the effect is reported, not after
someone doubts it.
*Anchor [I], literature silent for LLM-written analysis code.* *Ours:* a +2.2σ
"adverse fill selection" effect killed by its own time-shift placebo minutes later
(2026-09-01); a tick markout whose "post-fill gain" correlated **+0.995** with the
reflected limit distance — a reference-frame error that produced a plausible number
rather than a crash (2026-09-02).

**5. Every ratio gets its denominator and netting read from the code that computes it.**
*Anchor [K]:* DS-1000 publishes **43.3%** (insertion), **39.2%** (completion) and
0.388 (repo release) for one benchmark — three denominators, differing by harness. If
a benchmark's own authors publish three, a session's ad-hoc extraction has no excuse.
*Ours:* the chance-baseline correction of 2026-09-02, where a realized null rate
measured on a *synthetic* corpus was quoted for the *real* one (5% nominal vs 12.5%
realized).

**6. Degenerate-input guards must fail loudly.** Any resample or CI asserts a minimum
distinct block count and aborts rather than emitting a zero-width interval.
*Anchor [I], literature silent.* *Ours:* one distinct day collapsed every bootstrap
draw to the same value, producing zero-width CIs that flagged **pure noise** as
significant (2026-09-02; now floored at `MIN_CI_DAYS`).

**7. Reproduction is not re-prompting.** Only re-executing pinned, committed,
deterministic code counts as reproduction, and the instrument must be committed before
its number is quoted.
*Anchor [K]:* temperature-0 output is not reproducible on default serving stacks —
1,000 temp-0 samples produced **80 unique completions**, the modal one occurring 78
times, identical for 102 tokens then diverging (thinkingmachines.ai, corroborated at
mechanism level by SGLang and vLLM's opt-in batch invariance). Medium confidence:
self-published, no independent replication of the specific digits.

**8. Make prohibitions machine-enforced, not instructional, and audit prompts for
self-contradiction before delegating.** "The agent will obey the standing prohibition"
is not assumable.
*Anchor [K], but cross-channel:* hierarchy compliance spans **98.2% to 20.5%** across
37 model variants on 2,336 executable scenarios, and drops from 85.4% (system-over-user)
to 68.6% (user-over-tool) by channel (arXiv 2607.25987, medium confidence: preprint,
vendor-authored). *Ours:* the 2026-09-02 audit-ledger pollution, where one prompt
carried a general prohibition ("never touch this file") and a specific instruction that
violated it ("write one row to this file"), and the agent followed the specific one —
correctly. **Weakest-anchored item:** our case was *same-channel* specific-versus-general,
which no located source measures. Its enforcement half [I] carries more weight than its
citation half.

---

## Closing rule

**"Zero findings" and "the scan is broken" are the same observation until separated.**
The instrument must report which one it established. Carried from `the-method` and
independently vindicated by every surviving finding above.

## What this standard does NOT rest on

Honesty about the evidence base, because the temptation is to over-cite it:

- **No primary source prescribes this checklist.** It is assembled from surviving
  findings plus our own incidents. Items 4 and 6, and half of item 8, have no
  literature behind them at all.
- **No located source measures the silent numeric error classes we actually hit** —
  wrong denominator, look-ahead window, sign or reference-frame error, wrong group-by,
  degenerate block count. Every surviving benchmark figure measures *test-detected*
  wrongness (DS-1000, EvalPlus) or expert-decision disagreement on open-ended analysis
  (BLADE). **Rendering 56.7% or 55.2% as a "silent error rate" is a category error the
  primary sources explicitly do not license**, and it is what sank most of the claims
  that failed verification in the run behind this document.
- **There is no surviving measurement** of whether LLM analysis errors are biased
  toward plausible-but-wrong results versus crashes, nor of how much adversarial
  cross-checking by a second model beats self-verification by the same model. Both
  remain open questions. Our own experience points one way; that is not evidence.
- Several claims that *sound* useful were killed in verification — mostly for
  scope-mismatch, not because the underlying papers are wrong. **Do not cite those
  refutations as evidence against the papers.**
