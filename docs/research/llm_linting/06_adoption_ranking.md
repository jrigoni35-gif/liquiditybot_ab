# 06 — Adoption ranking (all SAFE / measurement plane)

Scoring: evidence grade (how well the source measured the mechanism,
per its own numbers) × fit (does it close a gap we actually have, vs
duplicate a shipped mechanism) × cost (build + run). All items are
SAFE-class per the era-4 moratorium (no change to which orders are
placed or how they fill). NN/model wiring stays forbidden under the
2026-08-10 freeze — nothing below trains, fine-tunes, or feeds a model.
Every item ships with its mutation test (plant the defect, watch the
check fire, break the check, watch the self-test go red) per backpack
rule 2 and the CLAUDE.md DoD (test in the same commit).

## Ranked list

| # | Item | Source | Evidence | Fit | Cost | Verdict |
|---|---|---|---|---|---|---|
| 1 | Raw-vs-rendered hidden-text diff in vault_guard | PhantomLint | Strong (0.092% FP single-venue; mechanism deterministic) | Direct gap: vault_guard has NO render-channel check; sessions read raw | Low (pure-Python, no model) | **BUILD** |
| 2 | Deterministic claim-citation linter for docs/quant/ + vault | sciwrite-lint | Strong on this tier only (98.5% injected recall, 0 FP — deterministic checks) | Extends vault's existing 0-broken-links standard to docs/quant/ | Low (no model) | **BUILD** |
| 3 | Deficient-verdict screen on lattice transcripts | ReviewGuard | Medium (features p<0.001 on 24.6k reviews; direction must be re-validated on our corpus) | Real gap: no pre-trust lint on referee output today | Low (textstat-style, zero model calls) | **BUILD (direction-validation first)** |
| 4 | Pre-ingest PhantomLint pass on fetched papers | PhantomLint | Medium (113/113 has low effective n; FP rate is the load-bearing number) | Real threat (22 preprint positives in the wild); our lit workflows ingest arXiv | Low-med (external tool + C2-style bypass corpus) | Build after #1 (shares insight, #1 is ours to control) |
| 5 | Mutation-rule battery for measurement scripts | LintLLM | Medium (their benchmark works; our overfit_check precedent works) | High — the least-governed plane is CLAUDE.md's named structural exposure — but broad scope, per-script effort | Medium | Adopt incrementally, one script per touch |
| 6 | Frontier-build/local-run rule pack | scicode-lint | Medium (cost numbers measured; detection value unproven) | Partial duplicate: USAGE.md j/k/l already say this; new part is local-llm MCP as executor | Low (doc + convention) | Fold into USAGE practice, no new artifact |
| 7 | "Deterministic first, LLM terminal" panel-input spec | sciwrite-lint + scicode-lint | Medium (pattern sensible; papers' own FP rates show LLM tier noise) | Real but diffuse: injection handling scattered, no unified spec | Low (spec page) | Write when the next panel is built, not before |
| 8 | Fix-one-re-detect triage procedure | LintLLM | Weak (their own GPT-series regression; n=90) | Marginal: focused-fix protocol covers most of it | Low | Note in protocol appendix only |
| 9 | Static methodology pre-commit scan over ml/ | scicode-lint | Weak (54% holdout, 11% ai-training, 0% overlap leakage) | Duplicates OF-battery's dynamic coverage on the classes that matter | Medium | Defer indefinitely |

## Top 3 — implementation sketches

### 1. vault_guard raw-vs-rendered diff (PhantomLint transfer)

1. New check in scripts/vault_guard.py: for each vault .md, strip
   content Obsidian's renderer hides — HTML comments `<!-- -->`,
   `style="display:none"` / `visibility:hidden` spans, white-on-white
   color styles — and diff stripped-vs-raw; nonempty residue = finding
   with file/line, report-only.
2. Reuse the existing measured-recall banner pattern (vault_guard C1/C2
   rebuild): print corpus size + recall every run, never bare "0
   findings" (mindset rule 3: separate "clean" from "scan broken").
3. Mutation test: plant an HTML-comment payload and a display:none
   payload in a scratch vault → check fires; break the stripper →
   --self-test goes red.
4. FP pass over the full canonical vault: legitimate HTML in pages must
   not spam; tune by allowlisting elements, never by weakening the diff.
5. tests/test_vault_guard.py extended same commit; ruff/pyright green
   (scripts outside the pyright gate, keep clean anyway).

### 2. Claim-citation linter for docs/quant/ + vault (sciwrite-lint deterministic tier)

1. scripts/doc_cite_lint.py: parse docs/quant/*.md + canonical vault
   pages for (a) wikilinks, (b) `path:line` citations, (c) commit-hash
   references; verify each resolves — file exists, line count covers
   the cited line, hash known to git.
2. Deterministic ONLY — no LLM claim-support tier (measured 60% FP in
   the source; would flood the 0-broken-links standard).
3. Output: per-file findings with citation text + failure class;
   exit 0 always (advisory, report-only — never a DoD gate whose
   release condition a doc controls).
4. Mutation test: plant a dangling wikilink, a stale file:line (cite
   line 9999 of a short file), and a bogus hash → all three fire;
   run over current docs/quant/ and file the initial findings.
5. Line-number citations rot as code moves — the linter flags them; it
   cannot verify semantic match. Say so in its banner (backpack rule 5).

### 3. Deficient-verdict screen for referee transcripts (ReviewGuard features)

1. Phase 0 (blocking): direction-validation on our own graded-review
   corpus (the graded commits cb0a2461 / 5d5c4e40 lineage) — confirm
   whether our failure mode is sycophantic-positive, per the memory
   note, before any threshold exists. No fitted literals: thresholds
   land in config.json with config_guard coherence checks.
2. scripts/verdict_screen.py: zero-model structural features per
   transcript — sentence count, token count, citation/file-path
   density (specificity proxy), asserted-confidence markers vs
   evidence-count mismatch.
3. Output: anomaly telemetry attached to the lattice's consensus layer
   (Layer 2 input hygiene), NEVER a gate — a padded transcript defeats
   the features (source's own adversarial hole), so it screens for
   sloppiness, not fraud. Report effective n: transcripts cluster per
   session.
4. Mutation test: plant a known-cursory transcript (3 sentences, zero
   citations, high-confidence verdict) → screen flags it; plant a
   dense genuine one → passes.
5. Placement respects the lattice DAG: the screen reads transcripts,
   publishes numbers, feeds no evaluator and no learner
   (docs/quant/2026-08-19_referee_lattice.md — no evaluator feeds the
   learner; checking is mutual, feeding is not).
