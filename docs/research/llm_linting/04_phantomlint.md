# 04 — PhantomLint: hidden-prompt detection in documents

**Citation**: Toby Murray (University of Melbourne), "PhantomLint:
Principled Detection of Hidden LLM Prompts in Structured Documents",
arXiv:2508.17884 [cs.CR], v1 2025-08-25, v2 2025-10-23. Code:
github.com/tobycmurray/phantom-lint. Preprint, not peer-reviewed as of
retrieval. FOUND.

## Claims

- First hiding-technique-agnostic detector of hidden LLM prompts in
  PDF/HTML (indirect prompt injection vs resume screeners, AI peer
  review).
- Key insight: hidden text exists in the machine-extractable source but
  not the human-visible rendering — render-then-OCR diff exposes the
  discrepancy regardless of hiding trick.
- Nine hiding classes covered (color-match, hidden layers/display:none,
  tiny fonts, z-index occlusion, off-page, zero-area clip, zero
  opacity, malicious glyph remapping, visibility:hidden).
- Composable with any downstream injection-text classifier (localizes,
  does not judge intent).

## Numbers

- FP 0.092% = 3/3,257 on ICML 2025 accepted PDFs.
- Detection 113/113 real in-the-wild hidden-prompt docs (89 CVs, 22
  preprints, 2 theses, 1 chapter); 0 false alarms on 6 visible-prompt
  negatives; 26/26 synthetic hiding-technique cases.
- 43-68 s/doc, unoptimized; no LLM / no frontier calls — uses Tesseract
  plus a small sentence-embedding model (Sentence Transformers) against
  the curated phrase list *(corrected 2026-08-27: page previously said
  "model-free (Tesseract + similarity)"; stage 1 is a neural embedding
  model, just not an LLM)*.

## Limitations

- Author-stated: best on short visually-tight hidden text; may localize
  only part of a prompt; Tesseract FPs on non-English glyphs/tiny
  fonts.
- Extraction reading: Stage-1 recall bounded by SEMANTIC SIMILARITY to
  a curated phrase list — matching is embedding-based, so paraphrases
  CAN still match, but sufficiently dissimilar prompts never reach the
  OCR stage *(softened 2026-08-27: page previously said "a hidden
  prompt phrased unlike the list never reaches the OCR stage", which
  overstated literal-phrasing dependence)*;
  the 113 positives are near-duplicate copies of publicized templates,
  effective n far below 113 (gate_truth_report effective-n standard).
- No adversarial evaluation: phrase-around-the-list, or attacks visible
  to humans but targeted at tokenizers, are out of scope.
- 0.092% FP measured on one venue's uniform LaTeX output;
  heterogeneous PDFs untested at scale.

## GAP ANALYSIS

### ALREADY AHEAD

- **Detector-recall-bounded-by-author's-imagination** is a defect class
  our vault_guard rebuild already documented and partially fixed:
  scripts/vault_guard.py:21-41 (C1/C2 — self-test that plants the
  exact strings the regexes were written against = tautology; fixed
  with a bypass corpus and a measured-recall banner). PhantomLint's
  phrase-list Stage 1 has exactly the C2 defect, unfixed.
- **Effective-n discipline**: 113/113 on template-duplicated positives
  would be reported here with effective n, per the standard
  gate_truth_report.py has applied since 2026-07-29.

### ADOPTABLE (SAFE class)

1. **Raw-vs-rendered diff in vault_guard** — the direct gap:
   vault_guard normalizes RAW markdown (zero-width chars line 63,
   homoglyphs lines 65-69) but does NO render-vs-source diff. An HTML
   comment `<!-- ... -->`, a `display:none` span, or white-on-white
   HTML in a vault page is invisible in Obsidian's render yet read by
   every Claude session under USAGE.md rule 1. Adoption: strip
   HTML-comment/hidden-style content the way Obsidian's renderer
   would, diff against raw, flag residue. Report-only, SAFE class.
   Validation gates per CLAUDE.md DoD: plant an HTML-comment payload
   and a display:none payload in a scratch vault and watch the check
   fire; break the check and watch --self-test go red; FP-measure over
   the full canonical vault (legitimate HTML must not spam); extend
   tests/test_vault_guard.py in the same commit.
2. **Pre-ingest scan for literature-workflow inputs** — landing spot:
   run the open-source tool (local, 43-68 s/doc — no frontier spend;
   not model-free: stage 1 uses a small sentence-embedding model —
   corrected 2026-08-27) on fetched arXiv PDFs/HTML before they reach
   judging agents. A paper carrying a hidden "review this favorably"
   prompt is precisely its threat model, and 22 preprint positives
   show the attack is live. Outside the trading path — no era-4
   exposure. If adopted, its phrase list gets the vault_guard C2
   treatment: a bypass corpus of phrasings it was NOT written around,
   recall printed every run, never a bare "0 findings".

### NOT APPLICABLE

- As an authentication mechanism for referee output or a gate: it
  localizes hidden text in documents; it says nothing about semantic
  manipulation visible to humans, and no adversarial recall exists.
