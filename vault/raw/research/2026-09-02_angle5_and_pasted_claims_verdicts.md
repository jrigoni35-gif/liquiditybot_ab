---
title: "Angle 5 (model-risk doctrine, documented instrument failures) + VERDICTS on the operator's pasted LLM-inconsistency claims"
date: 2026-09-02
type: raw/research
workflow: purpose-built wf_229201a9-eb7 (task w5sqv2oav), 10 agents, 0 errors, 698k tokens
status: COMPLETE for what it scoped. Third attempt; the first died on a session limit, the second extracted 120 claims and verified 25. This one CAPPED each agent at 4 claims so verification was affordable, and skipped search for angle 5 because its documents were already identified.
verification: 8 of 8 checked claims CONFIRMED at primary source, each with a wording tightening. The verifier could not parse any of the four PDFs through the fetch tool and downloaded + extracted them locally with PyMuPDF - a genuine second route.
---

# Angle 5 + the pasted-claim verdicts

## PART A — VERDICTS ON THE PASTED TEXT

The operator was handed an unsourced summary titled "Mitigating LLM Inconsistency in
Production". **Every one of its five claims now has a verdict. The underlying papers are
mostly real; the summary's ATTRIBUTIONS are substantially wrong.**

| # | pasted claim | verdict |
|---|---|---|
| (a) | "a finance-focused LLM produced fabricated content in 41% of probing test cases" | **REAL NUMBER, INVERTED ATTRIBUTION** |
| (b) | "stronger LLMs perform WORSE in live crypto trading, over-indexing on facts vs sentiment" | **NARROWER RESULT EXISTS, AND ITS CAUSAL STORY IS THE REVERSE** |
| (c) | "LLM multi-agent systems show total sign reversals under slight window shifts" | **REAL REVERSAL EXISTS BUT NOT THIS ONE** |
| (d) | "belief homogenization / advanced agents exploit weaker ones, introducing mini-crashes" | **REAL BUT OVERSTATED** |
| (e) | "Strict Separation Framework" | **NO PRIMARY SOURCE FOUND — a synthesized label** |

### (a) The 41% belongs to a general reasoning model, not a finance model — and the finance model was the BEST
Source: *Expect the Unexpected: FailSafe Long Context QA for Finance*, arXiv 2502.06329.
Verbatim: "the most robust model, OpenAI o3-mini, fabricated information in 41% of tested
cases", while "Palmyra-Fin-128k-Instruct, recognized as the most compliant model …
encountered challenges in sustaining robust predictions in 17% of test cases."
- **The finance-tuned model is the best on the fabrication axis (Context Grounding 0.80), not the 41% case.** The pasted sentence inverts the paper's finding.
- 41% is the **floor of a 41–70% range** the paper gives for reasoning-style models.
- **Denominator [DERIVED]:** 220 examples × 2 input transformations = **440 judged cases** per model. 41% ≈ 180 cases.
- **A "probing test case" is a deliberately broken prompt** (document missing, or an irrelevant document attached) where the CORRECT behaviour is refusal. "Fabrication" is scored by an LLM judge (Qwen2.5-72B, temp 0) rating relevance below 4 on a 1–6 scale. **No human-agreement rate for that judge is reported.**
- Verifier correction: Palmyra's 17% is a **robustness** deficit and o3-mini's 41% a **context-grounding** deficit — two different axes. The paper frames a trade-off (answering robustly vs refusing to hallucinate), not a single ranking.

### (b) "Do not ALWAYS outperform" is not "perform worse", and the fact/sentiment story runs the other way
Source: FS-ReasoningAgent, arXiv 2410.12464.
Verbatim: "stronger LLMs (o1-mini, GPT-4o) **do not always outperform** weaker LLMs".
- In the paper's own Table 1 the **weakest** model is the **worst** bull performer (GPT-3.5-turbo 12.35% vs GPT-4 22.68%) — directly contradicting the pasted wording.
- **The causal claim is inverted.** The paper's insights: "Subjectivity is more important in the bull market… Facts are more important in the bear market." The defect it identifies is **regime-blind weighting**, not a preference for facts.
- Scale: 3 coins × 2 regimes = **6 test windows, all inside 2024**, ~49 bull and ~42–53 bear transaction days; all three bull windows are the **same span**, so the coins are not independent samples. Headline gains 7% BTC / 2% ETH / 10% SOL. No seeds, no CIs, no significance tests.
- **LIVE INSTRUMENT WARNING, recorded by the agent against itself:** its fetch tool returned **three mutually inconsistent versions** of this paper's tables across four fetches of one URL, and an earlier pass **fabricated** ETH and SOL return figures. A hallucinating extractor inside a study of hallucination. The disputed tables remain UNRUN against the repo.

### (c) The sign reversal is single-agent, single-stock, and a 40× window extension
Source: FINSABER, arXiv 2505.07078. Verbatim: "FinMem exhibited a drastic change in
cumulative returns for MSFT from a reported 23.261% down to **-22.036%**".
- That is **n=1 system, n=1 symbol, n=2 windows** — a single-agent memory system, not a multi-agent system, and the window went from ~6 months to 20 years. **Not a "slight window shift."**
- The paper's own framing is the transferable part: narrow timeframes and limited universes "overstate effectiveness due to survivorship and data-snooping biases".

### (d) Real, quantified, and weaker than the sentence implies
Source: *Machine Spirits*, arXiv 2604.18602 (Saxena, Pangallo, Hommes, Caccioli,
del Rio-Chanona), 15 LLMs in a learning-to-forecast laboratory asset market.
- Exploitation and adaptation in mixed populations are in the abstract; **but the paper reports endogenous BUBBLES, not "mini-crashes"** — correct the wording before citing.
- Homogenization is real and small: common (shared) error contributes **41%** of mean individual squared forecast error — agents using different strategies still coordinate.
- Single extraction route; **not double-derived against the PDF.** Confirm before quoting permanently.

### (e) The name is invented; the practice is real under other names
- Exact-phrase search for "Strict Separation Framework" returns **only unrelated domains** — separating hyperplanes, phase segregation, church and state. **Zero finance/LLM-architecture hits.** It is a synthesized label presented as an established framework.
- **The underlying practice IS published**, unnamed as such: arXiv 2604.26747 implements exactly the split — "an agent … proposes falsifiable factor hypotheses … while a **deterministic engine** enforces fixed data splits, selection gates, transaction costs, and portfolio tests." Its self-reported Sharpe 1.55 carries no stated trial count, i.e. exactly the deflation problem our own MinBTL discipline exists to catch.
- This is a NEGATIVE result from one search route: it establishes "no public primary source", not "no firm does this".

---

## PART B — ANGLE 5

### B1. Model-risk doctrine — and a currency failure in my own premise
**SR 11-7 / OCC 2011-12 explicitly covered measurement-only tools.** A model has a
"**reporting component**", and enumerated uses include "**identifying and measuring
risks**" and "maintaining the formal control apparatus of the bank".

**On the same-agent problem, the doctrine is direct:** "A model's developer is an
important source of information but **cannot be relied on as an objective or sole
source** on which to base an assessment of model quality." Where developers do
validation, "it is **essential** … that such validation work be subject to critical
review by an **independent party**, who should conduct **additional activities**."
Independence "should be judged by **actions and outcomes**" — not by an org chart.

**On the degraded-instrument case** (it names "lack of data" explicitly): "**even more
attention should be paid to the model's limitations** … and senior management should be
fully informed of those limitations when using the models for decision making."
**Never a lowered threshold.**

**CURRENCY FAILURE — my premise was stale.** SR 11-7 was **superseded on 2026-04-17 by
SR 26-2** (Fed + OCC + FDIC). The replacement narrows "model" to *complex* methods,
**excludes deterministic rule-based processes and spreadsheet arithmetic**, and its
footnote 3 puts **generative and agentic AI outside its scope**, while stating that an
organization's own governance must still determine controls for uncovered tools. It is
also aimed at banks over **$30 billion** in assets. **Our measurement scripts are doubly
outside the live definition.** Cite SR 11-7 as a borrowed standard of care — never as
live regulation.

### B2. Two documented cases where the INSTRUMENT was the failure
**JPMorgan CIO 2012 VaR.** The Task Force report: "after subtracting the old rate from
the new rate, the spreadsheet **divided by their sum instead of their average**". The
model "operated through a series of Excel spreadsheets, which had to be completed
manually, by a process of **copying and pasting** data from one spreadsheet to another"
— and this was known **during** the approval review. Same-day effect: CIO VaR fell
**50%, $132m → $66m**. Firm policy "did not require the Model Review Group or any other
Firm unit to test and monitor the approved model", and the group "did not compare the
results under the existing Basel I model to the results being generated under the new
model."
**Attribution warning:** the division error appears **only** in the JPM Task Force
report. A grep of the Senate PSI report returns **zero** hits for "sum instead" or
"Excel spreadsheet" — anyone citing PSI for the mechanism is citing the wrong document.

**Reinhart–Rogoff.** The Excel AVERAGE spanned rows **30–44 instead of 30–49**, silently
dropping five alphabetically-ordered countries (Australia, Austria, Belgium, Canada,
Denmark). Corrected, high-debt average real growth is **+2.2%/yr, not the published
−0.1%/yr**; the claimed cliff shrinks from 3.3pp to **1.0pp**.

### B3. The two error rates that bear directly on our position
**FALSE POSITIVES — Simmons, Nelson & Simonsohn 2011, Table 1** (p<.05): two dependent
variables **9.5%**; ten more observations per cell **7.7%**; controlling for gender or
its interaction **11.7%**; dropping one of three conditions **12.6%**; **all four
combined 60.7%** — the famous "61%" is the paper's own rounding. In **pure noise**.
Verifier tightening: the single-DF rates are *not* all "roughly double"; the paper
describes the added-observations case as raising the rate by ~50%, and calls its own
list conservative.

**FALSE NEGATIVES — Harvey & Liu 2020, *Journal of Finance*: this is the one that
matters most for us.** "when p0 = 2% of funds are truly outperforming, the chance of the
best-performing metric … committing a **Type II error is 86.9%** under the 5%
significance level" — where the true performers earn ~10.66%/yr alpha.
Verifier tightening: that is the simulated Type II rate of the Fama-French bootstrap for
the best of seven statistics against a joint null, not a generic property of all
multiple-testing procedures.
**Reading: a joint multiple-testing null is nearly powerless. "Indistinguishable from
zero" and "there is nothing there" remain the same observation.**

**And the cost of stopping out on a bad instrument:** desks using IID-based metrics fire
truly skillful managers at up to **3.38×** their intended rate (Bailey & López de Prado;
model-implied, not an observed count, and by the same authors as the triple-penance rule).

### B4. What has no primary source
**The base rate — what fraction of researched strategies a desk kills, or how many
hypotheses are tested per deployed strategy — NO PRIMARY SOURCE FOUND.** What circulates
as if it were that figure is anecdote. Meta-labeling is likewise offered by López de
Prado as a **method with a named pitfall it solves** ("Learning side and size
simultaneously"), **not as a tested result**.

---

## UNRUN / not verified — named, never presented as a null
- **The entire JPMorgan block was not re-fetched by the verifier.** All four of its claims are extractor-side only, including the division error, the copy-paste chain, and the $132m→$66m drop.
- The Reinhart–Rogoff **−0.1%** figure is quoted as Herndon-Ash-Pollin report it; R&R's own 2010 papers were not fetched.
- FS-ReasoningAgent's repo was never fetched — the single highest-value unrun item, since it would settle the tables a hallucinating extractor corrupted.
- arXiv 2605.16895 (a candidate for (d)) was never fetched: unknown, not null.
- *Machine Spirits* PDF never fetched; its section-level numbers rest on one route.
- The FailSafeQA PDF was never fetched; all quotes are from the v1 HTML.
