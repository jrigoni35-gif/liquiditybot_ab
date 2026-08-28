# 04 — A Systematic Review of Large Language Models, 2017–2026

**Citation.** Kyeremanteng, Adu-Manu, Donkor (Univ. of Ghana),
Preprints.org, posted 2026-07-06, DOI 10.20944/preprints202607.0296.v1.
**403 to automated fetch** — extraction from abstract + search-indexed
snippets. Hint correction: TEN themes (architecture/scaling, data,
alignment, prompting/reasoning, retrieval, tools/agents, evaluation,
risk/governance, domain-specialized, multimodal); the hint garbled four
themes into an "eval suite". It is a PRISMA literature review, not a
benchmark.

## Claims

- Evidence base 2017–2026 is UNEVEN: gains from scale/instruction
  tuning/retrieval/tool use coexist with brittle reasoning, benchmark
  leakage, privacy exposure, weak documentation.
- Progress not explained by parameter count alone.
- Retrieval grounding (REALM…Self-RAG) reduces hallucination without
  retraining.
- Public benchmarks became overfitting/contamination targets — a
  benchmark gain is not capability unless construct, contamination, and
  deployment transfer are addressed.
- Agentic systems need benchmarks for permission boundaries, reversible
  action, auditability, damage containment — not only task success.

## Numbers

- PRISMA flow: 400 OpenAlex + 400 Crossref + 85 citation-chased; 126
  duplicates removed; 759 screened; 287 assessed; 202 excluded; n=85
  synthesized. Single search date 2026-06-05, two databases.
- No benchmark figures or effect sizes recoverable through the 403 wall.

## Limitations

- Access: authors' own limitations section unread; limitations list is
  partly extractor inference. Not peer-reviewed (v1 preprint).
- Two databases + citation chasing → curator-shaped, canonical-skewed
  selection; narrative vote-counting over heterogeneous studies — the
  aggregation style this repo's discipline distrusts. A map, not a
  measurement.

## GAP ANALYSIS

**ALREADY AHEAD.**
- Contamination theme = what OF-2 shuffle-null (`scripts/overfit_check.py`
  line 794, THE leak gate per line 916) and OF-6 purge (line 910) enforce
  mechanically; "benchmark visibility invites overfitting" = the OF-4 ban
  on tuning to a backtest peak. Nothing to adopt; the repo is ahead of
  the recommendation.
- Agentic-risk axes map 1:1 onto hard invariants 1–4 and 6 (dry_run
  default-true, one-way force_dry, Kraken-only execution_eligible,
  withdrawal deny-list, hash-chained audit + reason codes).
- Eval-documentation demand = the corpus-line law ("a green is only as
  big as its corpus"; degraded gates declared, not counted).

**ADOPTABLE (SAFE-class).**
- One test-suite hook, and it lands on session finding (e): the agentic
  axes are exactly what the suite must pin with NEGATIVE tests — the
  guard FIRES on the bad form — not happy-path exercise. A coverage-gap
  pass over tests/ should classify invariant pins by whether a planted
  mutation kills them (a benchmark the implementation can satisfy without
  the property is a contaminated benchmark in miniature — the
  comment-satisfied pin incident). Landing spot: same SAFE report tool as
  01/03; house rule on any generated test: mutation-kill evidence, never
  green alone.
- Vocabulary only otherwise: use it as eval-hygiene cross-check.

**NOT APPLICABLE.**
- Its LLM apparatus (prompting/reasoning/RAG themes): model-side
  investment frozen 2026-08-10, no LLM components imported on
  survey-level evidence; this repo fine-tunes no LLMs. One line, closed.
- Session defects (a)–(c): no coverage — the review does not touch test
  environments, fixtures, or ordering.
