# 03 — sciwrite-lint: manuscript/citation verification

**Citation**: Sergey V. Samsonau (Authentic Research Partners),
"sciwrite-lint: Verification Infrastructure for the Age of Science
Vibe-Writing", arXiv:2604.08501 [cs.DL], April 2026. Code:
github.com/authentic-research-partners/sciwrite-lint. FOUND.

## Claims

- Journal gatekeeping + open science cannot QA AI-accelerated writing;
  70-90% of citations are copied unread, so verification must trace the
  citation graph automatically — including one level into cited papers'
  OWN bibliographies (claimed unique).
- 22 integrity checks (reference existence/accuracy/retraction,
  claim-support vs cited full text, figure-vs-text, numbers-vs-tables,
  cross-section consistency) run entirely locally on one 16-20GB GPU.
- Purpose-weighted citation scoring (evidence 1.0 ≫ method 0.8 ≫
  context 0.2).
- Composite SciLint Score operationalizing Popper/Lakatos/Kitcher/
  Laudan/Mayo as computable properties.
- Verification-prior hypothesis: smaller models may verify BETTER
  (sycophancy scales with size; MiniCheck 770M / AlignScore 355M ≥
  GPT-4 on fact-checking).

## Numbers

- Injected-error recall: dangling-cite 38/38, dangling-ref 29/30,
  aggregate 98.5%, zero FP — **deterministic text checks only**.
- Real corpus: 30 unseen papers, 1,755 findings (~65/paper).
- FP adjudication (379 top findings, single Claude Sonnet judge):
  **14% TP / 60% FP / 26% uncertain**; FP mass in reference-DB checks
  pre-dating the 0.70-threshold matching engine — reported FPR
  describes a superseded config, no post-fix number given.
- Calibration n=20: 30/38 ordinal constraints pass; LIGO 0.570 vs
  LaCour fraud 0.162 (narrow dynamic range); Kitcher axis returned
  exactly zero for 12/20 (acknowledged broken).
- Runtime: ≤30 min initial (download-dominated); ~800 LLM calls/paper
  after embedding pre-filter (down from ~2,000); Qwen3 8B FP8 ~10GB
  VRAM.

## Limitations

- Author-stated: calibration/corpus "preliminary"; contribution
  framework experimental; cited papers' refs verified metadata-only;
  adversarial gaps (semantically unrelated citations, evasive
  contradictions, tampered PDFs) mitigated-not-tested.
- Extraction reading: 60% FP / 14% TP means the instrument generates
  more noise than signal; the 98.5% recall applies ONLY to two
  deterministic checks under self-injection — claim-support
  precision/recall never reported.
- Single LLM adjudicator, no human second route — the 14/60/26 split
  is itself a one-instrument number.
- Single-author company paper about its own product; philosophy-of-
  science multiplier is unfalsified ornamentation.

## GAP ANALYSIS

### ALREADY AHEAD

- **No-orphan-claims, humanly enforced**: its Stage-5 claim→cited-
  full-text→one-level-deeper walk is the automated form of USAGE.md
  rule 2b / vault governance rule 18 ("a silent page = go one level
  down") — we already run this protocol, by hand, with a stricter
  standard (owed measurements, not just supported/unsupported).
- **Corpus-mismatch green detection**: its headline (98.5% recall on
  deterministic tier, FP on a superseded config) is the exact "read
  what the gate actually measured" tell CLAUDE.md's DoD section made
  law after the overfit-battery synthetic-corpus lesson.
- **Double-derive on judges**: single-LLM FP adjudication violates
  delegated-measurement contract rule e (double-derive load-bearing
  counts) and mindset rule 2 (one number from one tool is a
  hypothesis) — cf. the 2026-08-21 diode incident.
- **Purpose-weighted severity**: severity-follows-argumentative-load is
  already shipped here as graded reason codes and veto-quality
  telemetry (commit 5e785c16).

### ADOPTABLE (SAFE class)

1. **Deterministic-tier claim-citation linter for docs/quant/ + the
   vault** — landing spot: a scripts/-side check that every wikilink
   and file:line citation in docs/quant/*.md and vault pages RESOLVES
   (reference-exists / dangling-link / metadata match). Canonical vault
   already lints at 0 broken links — extend the same standard to
   docs/quant/. Deterministic tier ONLY: the LLM claim-support tier
   ran at 60% FP and would flood a 0-broken-links standard with noise.
2. **"Deterministic checks first, LLM terminal" pipeline ordering** —
   landing spot: standing spec for any agent panel ingesting external
   text (fetched papers, news/sentiment): all deterministic ID/format
   checks run before any LLM invocation; XML delimiters + strict JSON
   schema on the LLM stage. Repo has injection-awareness scattered
   (core/audit.py, scripts/vault_guard.py) but no unified panel-input
   ordering spec.

### NOT APPLICABLE

- SciLint composite score / philosophy-of-science axes: unfalsified,
  one axis returns zero for 60% of its own calibration set; nothing
  here needs a prestige scalar.
