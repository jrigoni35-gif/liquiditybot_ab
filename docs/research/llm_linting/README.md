# LLM-as-linter / LLM-as-evaluator — literature pass (2026-08-27)

Purpose: five-paper graded readout on LLM-driven linting/verification,
compared against this repo's verification culture (OF-1..OF-7 battery,
no-orphan-claims, delegated-measurement contract, referee lattice,
the-method, agent-spend tiering). Every number below carries the
extraction's caveats; nothing here is re-derived beyond the extractions
plus the grounding reads (CLAUDE.md, docs/HANDOFF.md:219,
docs/quant/2026-08-19_referee_lattice.md). SAFE class throughout —
measurement plane only; nothing touches order placement or the era-4
cohort. Model-side adoption stays FROZEN per the 2026-08-10
adjudication.

## Status table

| Paper | Found | Citation | One-line verdict |
|---|---|---|---|
| [01 LintLLM](01_lintllm.md) | FOUND | arXiv:2502.10815, GLSVLSI 2025 | LLM beats EDA linter on a mutation-injected n=90 benchmark; the benchmark design (planted defects, known answers) is the transferable idea, the +18.89pt headline is an unresampled point estimate. |
| [02 scicode-lint](02_scicode_lint.md) | FOUND | arXiv:2603.17893 | Frontier-builds/local-runs methodology linter; 54% holdout precision, 0% on overlap leakage — the one class this repo cares most about; its cost architecture, not its detector, is the import. |
| [03 sciwrite-lint](03_sciwrite_lint.md) | FOUND | arXiv:2604.08501 | Local manuscript/citation linter = mechanized no-orphan-claims; deterministic tier strong (98.5% injected recall), LLM claim-support tier ran at 60% FP — adopt the deterministic half only. |
| [04 PhantomLint](04_phantomlint.md) | FOUND | arXiv:2508.17884 | Render-vs-OCR diff exposes hidden prompts technique-agnostically; direct, cheap, model-free fix for a real vault_guard gap (hidden HTML in vault pages). |
| [05 ReviewGuard](05_reviewguard.md) | FOUND | arXiv:2510.16549, JCDL 2025 | Deficient-review signature (short, low-structure, confidence>substance) is a usable zero-model screen for lattice transcripts; its sentiment direction does NOT transfer, its multi-label headline is leakage-adjacent. |

Adoption ranking: [06_adoption_ranking.md](06_adoption_ranking.md).

## Four-paradigm taxonomy of LLM-as-evaluator

1. **Prompt-based** — a general model + structured prompt does the
   evaluating at query time (LintLLM's Logic-Tree; scicode-lint's
   runtime pattern execution). Cheap to build, stochastic, recall
   bounded by prompt author's imagination.
2. **Fine-tuned** — a small model trained on labeled verdicts
   (ReviewGuard's Qwen 3-8B). Stable and local-runnable, but inherits
   its annotator's blind spots (GPT-4.1 ground-truth circularity) and
   needs a corpus far bigger than any referee-transcript set we hold.
3. **RAG / retrieval-grounded** — evaluator fetches the evidence and
   checks the claim against it (sciwrite-lint's claim→cited-full-text
   pipeline). The only paradigm that mechanizes citation-tracing; its
   LLM tier measured 60% FP on real corpora.
4. **Multi-agent alignment** — multiple evaluators, agreement is the
   signal. The papers barely touch this; it is where OUR referee
   lattice sits — with two deliberate differences from the literature's
   mesh instinct (docs/quant/2026-08-19_referee_lattice.md): the
   analysts are predominantly deterministic *cross-implementations*
   (py vs cpp diode), not LLM panels, so "agreement" is a differential
   matrix with declared tolerances rather than vote-pooling of
   stochastic outputs; and the graph is a DAG — blind analysts →
   consensus diff → operator head → one learner, no evaluator ever
   feeds the learner (HANDOFF.md RECENTLY SETTLED row). Every paper
   here that fielded a single LLM judge (sciwrite-lint's Sonnet
   adjudicator, ReviewGuard's GPT-4.1 annotator) is running paradigm 1
   in the seat where paradigm 4 belongs — the one-instrument hypothesis
   CLAUDE.md's mindset rule 2 forbids.

## Cross-paper reading

- **The literature validates our instrument-first law from the outside.**
  Three of five papers verify their own detector with planted defects
  (LintLLM's 13 mutation rules, scicode-lint's ≥3 pos/≥3 neg test files
  per pattern, sciwrite-lint's error injection) — the same move as
  scripts/overfit_check.py's planted-signal synthetic benchmark. The
  two that skipped a second route on their headline (sciwrite-lint's
  single-LLM FP adjudication, ReviewGuard's annotator circularity)
  produced exactly the numbers their own limitations sections have to
  disown.
- **Severity anti-correlates with reliability** in two independent
  tools (scicode-lint critical-severity precision 24%; sciwrite-lint FP
  mass in its loudest check class). An agent-panel finding at high
  asserted severity earns MORE suspicion, not less — quantitative
  support for mindset rule 5.
- **Every headline is smaller than it reads.** n=90 no-CI (LintLLM),
  feedback-set→holdout precision drop 62→54% (scicode-lint), recall
  measured on a different tier than FP (sciwrite-lint), 113/113 on
  template-duplicated positives (PhantomLint), multi-label graded on
  its own synthetic distribution (ReviewGuard). "A green is only as
  big as its corpus" held in all five.
- **What this pass could not see**: extractions only — no paper was
  re-read here; numbers are as-of the extraction agents' retrieval
  (2026-08-27); none of the tools was run on our code.
