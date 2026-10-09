---
title: Two-Vaults Merge Inventory (2026-09-02)
category: raw
summary: Read-only inventory of the retired-vault/canonical-vault gap, produced to make the standing merge-or-retire operator decision cheap to take. No files were merged, copied, or written into the retired vault.
---

# Two-Vaults Merge Inventory — 2026-09-02

Read time (UTC): **2026-09-02T13:46:46Z**. Retired vault:
`C:\Users\haird\vaults\liquiditybot` (write-retired 2026-08-14). Canonical:
`C:\Users\haird\Documents\liquiditybot\vault`. This document is an
**inventory only** — no merge was performed, and none is proposed as
auto-mergeable. All counts below were derived by direct `find`/`comm`
traversal at the read time above, not recalled from any prior report.

## 1. Headline counts [K]

| | retired vault | canonical vault |
|---|---|---|
| total `.md` (whole tree, case-insensitive glob `*.md`) | **117** | **293** |
| `.md` under `wiki/` only | **97** | **235** |

Needle: `find <root> -iname "*.md" \| wc -l`, run separately for whole-tree
and for `<root>/wiki`.

## 2. The prior "84 absent" disagreement, resolved by explicit definition [K]

A prior count of "84 absent" was not reproduced by a second route
(78–82 across five definitions, per the standing note). Re-derived here
under five stated definitions, same read, same two trees:

| # | Definition (exact) | Count absent | Command shape |
|---|---|---|---|
| **D1** | Same **relative path** under `wiki/`, case-sensitive (retired `wiki/X` has no canonical `wiki/X`) | **84** | `comm -23` on sorted relpath lists |
| D2 | Retired **basename** (case-sensitive) matches no file **anywhere** in canonical (whole tree, not just `wiki/`) | 82 | `comm -23` on sorted basename sets |
| D3 | Same as D2 but basename comparison **case-insensitive** | 78 | basenames lower-cased before `comm` |
| D4 | Retired basename (case-sensitive) matches no file anywhere in canonical **`wiki/` only** (excludes canonical `raw/`, root docs) | 82 | basenames restricted to canonical `wiki/` |
| D5 | Same relative path, but the whole comparison **case-insensitive** | 84 | relpaths lower-cased before `comm` |

D1 = D5 (no case-only collisions exist in this pair). D2 = D4 (no retired
basename matches a canonical file that lives outside `wiki/`, e.g. in
canonical `raw/`). D3 is the smallest because case-insensitive basename
matching is the most permissive test — it is also the **weakest** test:
it says nothing about whether the matching file is the same page, a
different page that happens to share a name, or a stub.

**This document uses D1 (84, same relative path under `wiki/`) as the
primary worklist** — it is the definition the retirement note's own
"88 basenames present here and absent from canonical" claim was
approximating (that note counted 88 basenames including 7 vault-root
docs like `README.md`/`CLAUDE-invariants.md` that sit outside `wiki/`
entirely and are out of scope for a `wiki/`-relative-path comparison —
88 − 7 root-only + 3 basename-vs-relpath drift ≈ this range). D1 is the
strictest and most defensible test for "does canonical already have
this page" because it requires exact placement, not just a name
collision — and per §4 below, name collisions across unrelated pages
are real in this pair (retired `thales-footprint-detection.md` vs
canonical's differently-organized `thales-engine.md`/`thales-doctrine.md`
cluster).

## 3. Root signpost file [K]

`_RETIRED_READ_THIS_FIRST.md` **exists** at the retired vault root, size
4533 B, mtime **2026-08-14 21:08**. It states: retired as a write target
2026-08-14 by operator decision, nothing deleted; canonical is
authoritative; lists **88 basenames** (mixed — includes 7 root-level
docs and 81 wiki-tree pages) present in the retired vault and absent
from canonical at the time it was written; explicitly instructs: do not
file new knowledge here, do not bulk-copy into canonical (shared
basename ≠ shared page), do not delete the vault; states the owed
decision is "merge selected pages into canonical, or retire this tree
wholesale." Consistent with the standing prohibition in this session's
CLAUDE/USAGE context.

## 4. Live-write check — anything modified since 2026-08-14? [K]

Full-range scan, `find -iname "*.md" -printf` over the **whole** retired
tree (117 files), filtered to mtime date ≥ 2026-08-14:

- 6 wiki files + `_RETIRED_READ_THIS_FIRST.md` carry mtimes on
  **2026-08-14 itself** (16:52–21:08) — these are the retirement-day
  edits that produced the signpost note and its final synthesis-page
  touches (`governor-taxonomy.md`, `model-monitor.md`,
  `thales-vindication-loop.md`, `wiki/index.md`,
  `liquiditybot-design-overview.md`, `safety-architecture.md`,
  `raw/session-2026-08-13-analyses.md`, `wiki/log.md`). All pre-date or
  coincide with the 21:08 retirement note itself — not post-retirement
  writes.
- **`CLAUDE.md` and `AGENTS.md` at the retired vault root carry mtime
  2026-08-30** (18:02–18:03), **16 days after retirement.** Read: both
  now open with a `[!CAUTION] RETIRED — DO NOT WRITE HERE` banner
  matching the signpost note's content and pointing at canonical. This
  is a **retirement-enforcement edit** (the banner text itself declares
  the pre-existing maintainer instructions below it "VOID for this
  copy"), not new knowledge accrual — the file's substance is the
  warning, not fresh liquiditybot content. **Flagging per protocol
  regardless**: this is the one instance since 2026-08-14 of anything
  in the retired tree being touched, and it was not caught by a
  wiki-only scan (these two files sit at vault root, outside `wiki/`).
  No other file in the retired tree (wiki or root) has a post-2026-08-14
  mtime. **Not a live-write problem** — no session is filing new
  analysis there — but the write did happen and the operator should
  know two files there are not frozen at 2026-08-14 the way the rest of
  the tree is.

## 5. The D1 worklist — 84 pages, grouped [K/I]

All 84 have first-heading and size/mtime read directly (`sed -n '1,6p'`
for headings/frontmatter, `stat` for size/mtime); one-line judgements
are **inferred** from title + summary line only — no full-body read was
done for 83 of the 84 (budget), so judgements below are directional, not
verified content-diffs. Where a canonical file exists with a related
*topic* under a *different* name, a crude signal was run: grep the
retired page's exact heading string across all of canonical (whole
tree). **This is a weak proxy** (it catches incidental mentions, not
semantic overlap, and it is case-insensitive substring matching) — it
found 17 heading-string hits, listed under "possible name-drift overlap"
below; treat every one as "check this pair first," not "these are
duplicates."

All 84 files carry mtime **2026-08-13** except `model-monitor.md` and
`thales-vindication-loop.md` (2026-08-14) — i.e. the entire cohort was
authored in the single 2026-08-13/14 session the signpost note blames
for the mis-filing.

### SAFE TO RETIRE (1 file — self-declared non-unique)

- `concepts/thales-footprint-detection.md` (590 B) — heading "THALES
  Footprint Detection"; body opens "Alias — merged into the THALES
  Detector Bank page" (its own text says it is a stub pointing at
  `thales-detector-bank.md`, which is itself absent from canonical
  under that name but a differently-organized THALES cluster exists in
  canonical — see below). No independent content.

### SCAFFOLD (0 files)

None of the 84 are index/log/template files — canonical and retired
both already carry their own `wiki/index.md` and `wiki/log.md` (those
compare unequal — 285 vs 109 lines — but both **exist** at the same
relative path, so they are not in this D1 absent-list; they are a
content-diff question, not a presence question, and out of this
inventory's scope).

### NEEDS A HUMAN READ (83 files)

All 83 have a substantive `summary:` frontmatter line (concept/entity/
source/synthesis pages with real claims — fee floors, hash-chain
structure, detector names, ratios), not stub placeholders. Full list
with size/mtime/heading is in the raw scan
(`/tmp/def1_details.tsv` this session, not persisted — re-run the D1
`comm` above to regenerate) — key sub-groups:

**Large synthesis docs with no topical counterpart found anywhere in
canonical** (highest-value read, highest risk of real unique content):
`synthesis/governor-taxonomy.md` (20,339 B), `synthesis/
liquiditybot-design-overview.md` (20,417 B), `synthesis/
safety-architecture.md` (5,086 B), `synthesis/incident-history.md`
(4,506 B), `synthesis/operations-runbook-map.md` (4,034 B). Canonical's
`wiki/synthesis/` has 16 files, none title-matching these five.

> **CORRECTION 2026-09-02T14:09:14Z (adversarial review, C-2).** The
> original text here read "canonical has no `*governor*`, `*incident*`,
> or `*runbook*` file anywhere by basename search". **The `governor`
> third is FALSE and was shipped without running the search it names.**
> Re-run, two routes: `find <canonical> -iname '*governor*'` and a
> Python basename scan over all 295 canonical `.md` both return
> **`wiki/entities/ml-governor.md`** (13,105 B, mtime 2026-08-09,
> title "The ML Governor", summary "A staged monitor that can only make
> the bot more conservative than config"). `incident` → **[]** and
> `runbook` → **[]** are reproduced and stand. [K]
>
> Consequence: `synthesis/governor-taxonomy.md` (20,339 B) is still the
> **largest** no-title-match synthesis doc, but it is **no longer a
> zero-counterpart page** — it must be read *against* canonical
> `entities/ml-governor.md`, not as unrecoverable-if-retired. The
> retired side also holds `concepts/leverage-governor.md` and
> `concepts/model-monitor.md` on the same subject, so this is a
> **three-page retired governor cluster against one canonical entity
> page** — the same name-drift shape §5's own caveat warns about for
> THALES, missed here because the asserted search was never executed.

**Possible name-drift overlap (18 files) — the crude heading-grep hit
something in canonical under a different name; verify these first, in
this priority order because the canonical hit looks most specific to
least:**
`concepts/overfit-discipline.md` → canonical `concepts/
never-widen-a-gate.md` + `concepts/the-method.md`; `concepts/
evidence-concentration.md` → canonical `entities/thales-engine.md`;
`entities/freqtrade.md` and `entities/hummingbot.md` → canonical
`entities/retail-bot-frameworks.md` (looks like a genuine consolidation —
canonical may have merged both frameworks into one entity page);
`concepts/config-guard.md` → canonical `concepts/deadlock-discipline.md`
+ `entities/kraken.md`; `concepts/dead-man-switch.md` → canonical
`concepts/failure-plane-taxonomy.md` + `entities/kraken.md`; `concepts/
era-4-accrual-moratorium.md` → canonical `entities/liquiditybot.md` +
`wiki/index.md`; `concepts/exit-escalation-ladder.md` → canonical
`sources/session-20260821-cost-stack-in-flight.md`; `concepts/
leverage-governor.md` → canonical `sources/architecture-v2.md`;
`concepts/spoof-detection.md` → canonical `sources/architecture-v2.md`;
`concepts/watchdog.md` → canonical `comparisons/
stated-invariants-vs-audited-reality.md` + `concepts/
parallel-domain-audit.md`; `entities/claude-code.md` → canonical
`sources/session-20260827-sdd-verification-and-era-confound.md`;
`entities/grafana-cloud.md` → canonical `concepts/
liveness-by-output-cadence.md` + `entities/liquiditybot.md`; `entities/
moomoo.md` → canonical `concepts/false-green.md` + `concepts/
zero-is-not-a-reading.md` (this one reads as an incidental word-mention
false positive, not topical overlap — flagging the weakness of this
signal explicitly); `synthesis/incident-history.md` → canonical
`entities/observability-sidecars.md`; `concepts/
attribution-drift.md` and `concepts/clustered-permutation-importance.md`
→ canonical `sources/interpretability-design.md` (this one looks like
a real fold-in candidate — canonical appears to have consolidated
interpretability topics into one source doc);
`concepts/model-monitor.md` → canonical `entities/ml-governor.md`
(**added 2026-09-02T14:09:14Z, correction C-1 — see §8**; this pairing
is NOT a heading-grep hit, it is a summary-line read: retired
"Self-diagnosis ladder … recast as a staged governor in rev 3.0"
vs canonical "A staged monitor that can only make the bot more
conservative than config". Strongest topical counterpart in the 18.)

**Remaining 65 of the 83**: no heading-string hit anywhere in canonical
by this crude check — higher prior of being genuinely absent topics
(concepts: alert-sink, arm-live-gate, audit-trail, avellaneda-stoikov-
quoting, control-api-surface, engine-runner-separation, equity-truth-
check, exact-shapley-attribution, execution-algorithms, execution-
tactics, fair-value-microprice, feed-sanitization, fix-protocol-layer,
fractional-kelly-sizing, informed-flow-engine, inventory-and-hedging,
local-llm-companion, long-book, macro-regime-engine, markout-toxicity,
meta-labeling-pipeline, narrative-filter, observation-lapse, order-
lifecycle, pc-supervisor, pretrade-ev-gate, queue-aware-fill-simulation,
read-only-data-plane, remote-control-plane, replay-backtesting, risk-
firewall, session-continuity-loop, smart-order-routing, smc-structural-
features, state-persistence, thales-detector-bank, thales-stop-cluster-
defense, thales-vindication-loop, trust-boundary-model, venue-adapter-
contract, wash-trade-prevention, watchdog-stack, withdrawal-deny-list;
entities: claude-code-remote-control, cme, ollama; sources: assurance,
engineering-invariants, execution-connectivity, hardening,
interpretability, local-llm-setup, market-conduct-compliance, pc-
always-on, phone-sessions, readme-operations, research-2026-07-18,
session-2026-08-13-analyses, smc, thales-frameworks, thales;
synthesis: governor-taxonomy, liquiditybot-design-overview, safety-
architecture, operations-runbook-map). **Caveat**: "no heading-string
hit" is not "no canonical content on this topic" — canonical's THALES
material (`thales-engine.md`, `thales-doctrine.md`, `thales-frameworks-
calibration.md`, `thales-unit-audit.md`, plus two `comparisons/*thales*`
pages) demonstrates canonical already reorganizes THALES content under
titles that share **no** heading substring with the retired pages
(`thales-detector-bank`, `thales-stop-cluster-defense`, `thales-
vindication-loop`, `thales-frameworks`, `thales` itself) — so this whole
6-file THALES sub-cluster is a **known instance of the exact risk the
signpost warns about**: real canonical content on the same subject
exists, just not discoverable by name-matching. Any human read pass
should check the THALES sub-cluster against canonical's THALES cluster
specifically, not assume "no name hit" means "no overlap."

## 6. What this inventory did NOT do

- Did not diff file **contents** for any of the 83 "needs a human read"
  files against canonical (only frontmatter summary + first ~6 lines
  read).
- Did not check whether canonical's already-235 wiki pages carry
  claims that **contradict** anything in the 84 absent pages (no-orphan-
  claims currency check) — that is exactly the work a human-read pass
  would do.
- Did not touch, move, or copy anything in the retired vault.
- The 17-file "possible name-drift overlap" list is a single crude
  case-insensitive heading-substring grep — not a semantic similarity
  check, not verified by a second route. Treat it as a triage order,
  not a verdict.

## 7. Recommended decision shape (recommendation only — the decision is the operator's)

Three options, sized against the D1 worklist (84 files, 1 already
flagged safe-to-retire, 83 unresolved).

> **AMENDED by §8.** Wherever this section says the 5 large synthesis
> docs have "zero topical counterpart", read: **four** of them do —
> `governor-taxonomy.md` now has a named canonical counterpart
> (`entities/ml-governor.md`, C-2). The per-option file counts below
> (61 / 79) were derived off the pre-correction 17-file overlap list
> and are **left as originally written rather than silently patched**;
> they are approximate group sizes, not load-bearing counts. The
> load-bearing numbers are D1 = 84 and its exact partition in §8.

- **Option A — Retire wholesale.** Leave the retired vault exactly as
  archived; canonical stays the sole source; do nothing further. Cost:
  0 files reviewed, 0 files moved. Risk: any of the 83 files with real
  unique content (most plausibly the 5 large synthesis docs in §5 with
  no canonical topical counterpart at all) stays permanently
  unrecoverable-by-search from canonical.
- **Option B — Targeted human-read merge, prioritized.** Human (or a
  future single-file-scoped session, per this repo's "single agent for
  single-file questions" spend rule) reads the 5 large synthesis docs
  first (highest size, no topical counterpart — highest expected
  unique-content density), then the 17-file possible-overlap list
  (resolve THALES cluster + interpretability-design fold-in + retail-
  bot-frameworks fold-in explicitly), then triages the remaining 61
  concept/entity/source stubs in batches by category. Cost: up to 83
  file-pairs read; likely far fewer once the synthesis docs and overlap
  cluster are resolved, since many of the 61 may turn out pre-empted by
  content the overlap check didn't catch by title.
- **Option C — Retire wholesale but promote the 5 large synthesis docs
  only.** Split the difference: human-reads just `governor-taxonomy.md`,
  `liquiditybot-design-overview.md`, `safety-architecture.md`,
  `incident-history.md`, `operations-runbook-map.md` (5 files, the ones
  with zero topical counterpart and the largest sizes — 20KB × 2, plus
  three 4–5KB docs) for merge-worthiness, retires the other 79 files
  (78 unresolved + 1 self-declared alias) wholesale without further
  review. Cost: 5 files reviewed, lowest effort of the three non-trivial
  options.

This document makes none of these choices; it is sized so whichever is
picked has an exact file list already in hand.

## 8. Correction log — adversarial review, 2026-09-02T14:09:14Z [K]

Two CONFIRMED defects in the version above, both found by re-running
the report's own derivations rather than re-reading its prose. Neither
changes the D1 count (84, reproduced independently: retired `wiki/`
97 `.md`, canonical `wiki/` 235 `.md`, set difference on relative path
= 84). Both changed the **grouping the operator was told to act on**,
which was the stated deliverable.

**C-1 — one D1 file was assigned to no action group.**
`wiki/concepts/model-monitor.md` (5,758 B, mtime 2026-08-14 16:53,
title "Model Monitor") appeared in the D1 corpus and in two asides
(§4 retirement-day mtimes, §5 mtime-exception sentence) but in **none**
of SAFE TO RETIRE / SCAFFOLD / possible-overlap / remaining. Machine
parse of the "Remaining 66" parenthetical returned **65** tokens, all
valid D1 stems, none spurious — so nothing was invented, one name was
simply never written down. Arithmetic before: 1 + 17 + 65 = **83 ≠ 84**.
After: 1 safe-to-retire + 18 overlap + 65 remaining = **84**. The
enumerated remaining list is unchanged and was always correct at 65;
only its header said 66. An operator working the groups would have
silently never decided this file.

**C-2 — a basename search was asserted, not run.** See the inline
CORRECTION box in §5. `governor` has a canonical hit; the claim was
the sole stated justification for ranking `governor-taxonomy.md` as
the top-priority no-counterpart read.

**Compounding, stated plainly:** C-1 and C-2 are the same miss. The
file dropped from the groups (`model-monitor.md`) is precisely the
topic of the canonical file the unrun search would have surfaced
(`ml-governor.md`). Retiring on the uncorrected text would have
discarded the retired governor cluster **and** never noticed canonical
already held a 13 KB page on it.

**What this correction did NOT do:** no file contents were diffed —
the `model-monitor.md` ↔ `ml-governor.md` pairing is a summary-line
judgement [I], not a verified content overlap, and it is offered as a
**read-these-together** instruction, not as grounds to retire either.
The 17 pre-existing overlap pairs were not re-verified. No second
route was run against the *other* 64 remaining stems to check for the
same class of unrun-search error, so C-2 should be read as one
instance found, not as the only one present. Nothing in either vault
was moved, copied, or deleted.
