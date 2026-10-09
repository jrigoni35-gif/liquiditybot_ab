# vault — LLM Wiki

> **Topic:** liquiditybot — quant trading research, model validation, and engineering decisions
> **Initialized:** 2026-08-01
> **Tool:** Claude Code (this file). A parallel `AGENTS.md` exists for Codex/Cursor/Antigravity.

You are the maintainer of this wiki. You read from `raw/`, you write to `wiki/`. You never edit `raw/`.

> [!CAUTION]
> # TWO VAULTS — READ BEFORE FILING ANYTHING
> There are TWO liquiditybot vaults. **This one (`C:\Users\haird\Documents\liquiditybot\vault`) is
> canonical.** `C:\Users\haird\vaults\liquiditybot` is a **RETIRED** duplicate (write target
> retired 2026-08-14, nothing deleted). Do **not** file new liquiditybot knowledge there, do
> **not** bulk-copy it into canonical (a shared basename is not a shared page), and do **not**
> delete it. The merge-or-retire decision is the **operator's** and it is **OPEN**. Full detail,
> the measured inventory, and the prohibitions:
> ``wiki/concepts/two-vaults-open-decision``

## The three layers

```
raw/     → sources (articles, papers, notes). IMMUTABLE. You only read.
wiki/    → the knowledge base. You own this. Create, update, cross-reference.
CLAUDE.md / AGENTS.md → schema (this file). Co-evolved with the user.
```

## Vault structure

```
raw/
├── <sources>              # articles, papers, notes — IMMUTABLE
└── assets/                # downloaded images from clipped articles

wiki/
├── index.md               # content catalog — update every ingest
├── log.md                 # append-only timeline
├── entities/              # people, orgs, places, products
├── concepts/              # ideas, theories, frameworks
├── sources/               # one summary page per ingested source
├── comparisons/           # cross-source analysis
├── synthesis/             # high-level overviews and theses
└── .templates/            # page templates (reference only)
```

## Page frontmatter (required on every wiki page)

```yaml
---
title: <Title>
category: entity | concept | source | comparison | synthesis
status: SETTLED | PROVISIONAL | SUPERSEDED
summary: <one-line summary>
tags: [tag1, tag2]
sources: <count of sources referencing this page>
updated: YYYY-MM-DD
---
```

`status:` is **required on every claim page** (domain rule 12 / governance rule 21).
Ledger pages are exempt by name: `index.md`, `log.md`, and the four registers
(`owed-measurements`, `open-contradictions-register`, `documentation-drift-register`,
`evidence-closed-register`) — every entry there carries its own disposition.
Enforced by `~/.claude/skills/llm-wiki/scripts/lint_claim_status.py --vault .`

For `source` pages, also include:
```yaml
source_path: raw/<path>
source_date: YYYY-MM (original publication)
authors: [author1, author2]
ingested: YYYY-MM-DD
```

## The three operations

### Ingest (`/wiki-ingest <path>`)

1. Run `python scripts/ingest_source.py --vault . --source <path> --json` to get the brief
2. Read the source directly
3. **Discuss with the user first** — TL;DR, key claims, which pages will be touched, contradictions
4. Wait for confirmation
5. Create or merge the summary page at `wiki/sources/<slug>.md`
6. Update every relevant entity and concept page (typically 5-15 pages)
7. Flag contradictions with `> ⚠️ Contradiction:` callouts on both sides
8. Update `wiki/index.md` (run `update_index.py` or edit inline)
9. Run `append_log.py --op ingest --title "<title>" --detail "<touched pages>"`
10. Report back with a bulleted list of touched pages

### Query (`/wiki-query <question>`)

1. Read `wiki/index.md` first
2. Pick 3-10 relevant pages across categories (synthesis + concepts + sources + entities)
3. Read them in full
4. Follow wikilinks opportunistically
5. Fall back to `wiki_search.py --query <terms>` if the index doesn't surface the answer
6. Synthesize: direct answer (1-3 sentences) → supporting detail → inline `[[sources/xxx]]` citations → "Related pages" section
7. **Offer to file the answer back** as a new page in `comparisons/` or `synthesis/`

### Lint (`/wiki-lint`)

1. Run `python scripts/lint_wiki.py --vault .` for mechanical checks
2. Run `python scripts/graph_analyzer.py --vault .` for structural stats
3. Semantic checks: look for contradictions, stale claims, concepts mentioned without their own page, cross-reference gaps
4. Present findings as a markdown report with suggested actions
5. Append a `lint` entry to `log.md`

## Iron rules

1. **`raw/` is immutable.** You read from it; you never write to it.
2. **All writes go to `wiki/`.** No exceptions.
3. **Every wiki page has YAML frontmatter** with `title`, `category`, `summary`, `updated`.
4. **Every ingest touches ≥5 files.** The source summary, 2-4 entity/concept pages, `index.md`, `log.md`.
5. **Every claim has a citation.** Link back to the `sources/<slug>` page.
6. **Contradictions get flagged inline.** Both pages get the callout.
7. **Good answers get filed back.** Explorations compound.

## Log format

```
## [YYYY-MM-DD] <op> | <title>
<optional detail — which pages touched, what changed>
```

Valid ops: `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.

Grep the log: `grep "^## \[" wiki/log.md | tail -10`

## Tools

All scripts live at `~/.claude/skills/llm-wiki/scripts/` (or wherever you installed the plugin). Standard library only.

- `init_vault.py` — bootstrap a vault
- `ingest_source.py` — prep a source for ingest (metadata + preview)
- `update_index.py` — regenerate `wiki/index.md` from page frontmatter
- `append_log.py` — append a standardized log entry
- `wiki_search.py` — BM25 search fallback
- `lint_wiki.py` — mechanical health check
- `graph_analyzer.py` — link graph stats
- `export_marp.py` — render a page as a Marp slide deck

## Obsidian

The user opens this vault in Obsidian. They watch the graph view while you edit. Useful plugins: Graph view, Backlinks, Dataview, Marp, Templates, Git.

## Style

- Be concise. Wiki pages are read, not generated.
- Prefer short paragraphs. Bulleted lists where appropriate.
- Cite aggressively with `[[wikilinks]]`.
- When you're not sure, say so in the page. Don't invent content.
- Update `updated:` frontmatter whenever you touch a page.


---

# Project-specific conventions (liquiditybot vault)

Added 2026-08-01 after the initial bulk ingest of 35 sources. These are the domain rules this
vault has learned; they extend, not replace, the generic schema above.

## What lives in `raw/`
Snapshots of the repo's own working documents, grouped by kind:
`raw/quant/` (validation and adjudication memos, date-prefixed) · `raw/research/` (literature passes)
· `raw/architecture/` (design and assurance docs) · `raw/audits/`.
These are copies. The originals live in the repo's `docs/` tree and are the operator's to edit.

## Domain rules for this wiki

1. **Always qualify a measurement by its corpus size and date.** Baselines in this project are
   ambiguous without them — the same day produced both "5 passed / 3 failed" and "4 passed / 4
   failed" on different row counts. Never write a bare battery result.

2. **Preserve the exact numbers.** Thresholds, gate margins, row counts, basis points, p-values and
   reason codes are the substance here. Round nothing. When a document states a number to six
   decimals, keep six.

3. **Record retractions and overrides as first-class content.** This corpus retracts its own claims
   in-document and consciously overrides prior decisions. A page that states only the final position
   loses the most valuable part. Use the pattern: *what was claimed -> what refuted it -> what stands*.

4. **Every rejection carries its killing citation.** Rejections are binding on future sessions; a
   rejection without its reason will be re-litigated. See `concepts/evidence-grading-ladder`.

5. **Distinguish "shipped" from "working."** This project has repeatedly found fixes that were
   correct in shape and inert in effect. When a page says something shipped, say whether anything
   measured it afterwards.

6. **Contradictions go in `synthesis/open-contradictions-register`**, not silently into a page. Mark
   each RESOLVED or UNRESOLVED. The unresolved ones are the point.

7. **New owed measurements go in `synthesis/owed-measurements`** with what would close them.

8. **The wiki is the truth — file confirmed findings same-session.** Operator directive
   (2026-08-02, verbatim in `sources/session-20260802-digest` final micro-addendum, binding as
   `synthesis/governance-doctrine` rule 12): everything determined correct gets injected into
   this wiki in the session that determined it. "Confirmed" = measured, battery-green,
   committed. Hypotheses enter only as owed measurements, never as facts. The wiki is NOT the
   training corpus — nothing synthetic or relabeled ever enters `signal_history`.

9. **State the paper/real boundary on every filed conclusion.** Operator directive
   (2026-08-07, binding as governance rule 13, page `concepts/paper-real-boundary`): the bot
   executes NO real bids/positions — every fill, fee, queue, latency and markout is SIMULATED
   (dry_run, fill-at-limit RNG, config-constant fees). This is THE central relation of the
   project, not a caveat: the corpus rehearses real-money discipline on simulated execution.
   Every conclusion states which side its evidence comes from (sim-side / venue-data-side /
   repo-side), and sim-conditioned numbers — fees, fills, markout, RTT, all dollar P&L — are
   never cited as venue truth. Also: zone-stamp every incident window (one churn was
   double-filed purely by local-vs-UTC rendering).

10. **Stay current, and never leave an orphan claim.** Operator directive
    (2026-08-14, binding as governance rule 18, page `concepts/no-orphan-claims`).
    The wiki is not a place knowledge is *stored*; it is the place knowledge is
    *kept true*. Three obligations, **in this order**, on every question:

    **(a) CONSULT FIRST.** Read `wiki/index.md` before deriving anything. Not
    after, not "to check the answer" — recall-before-derive is cheaper than
    re-derivation and it is how the corpus compounds instead of being rebuilt
    each session. A workflow launched before the wiki is queried has already
    paid for something it may already own (measured: a 1.12M-token architecture
    fan-out re-derived a taxonomy this vault already held).

    **(b) IF THE WIKI DOES NOT KNOW — REFERENCE BACK.** Do **not** answer from
    the model's own recall and do **not** file the answer. Walk to the primary
    artifact the relevant page cites — `raw/`, a commit, a `file:line`, a
    ledger, a measurement — and answer from **that**, citing what you walked
    to. A page that is silent on a question is not evidence of absence; it is
    an instruction to go one level down. This also runs against the vault's own
    content: **recall-before-derive must never become reuse of a cached
    conclusion as evidence** — re-derive any number that is load-bearing in the
    current turn, including one this vault states.

    **(c) IF NO REFERENCE EXISTS — FIND ONE.** *"No citation available" is a
    task, not a disposition.* An unsourced claim is not filed and not acted on.
    It converts into one of exactly three things, and never into a fact:
    an entry in `synthesis/owed-measurements` with what would close it; a
    literature pass graded on `concepts/evidence-grading-ladder`; or a
    measurement run **now** against the repo's own artifacts. The corpus has
    twice paid for the alternative — a claim that entered as prose and was
    believed because it was written down (`synthesis/documentation-drift-register`).

    **And currency is part of correctness.** A page contradicted by a
    measurement gets its callout **in the same session** that measured it —
    both sides, per rule 6. An out-of-date page is not a neutral artifact; it
    is an active source of false confidence, because everything here is read
    as settled.

11. **A session is not a citation, and an unstated protocol is an absent
    protocol.** Operator directives 2026-08-16, binding as
    `synthesis/governance-doctrine` rules **19** and **20**; pages
    `concepts/session-identity-is-not-stable` and
    `concepts/location-not-magnitude`; measured in
    `sources/session-20260811-16-vscode-3b307393`.

    **(a) Session identity is not stable.** A session is a *process*, not an
    observer. One VS Code Claude session ran **four calendar days** across
    several host-process restarts with its in-context "now" frozen at
    2026-08-12 while disk reached 2026-08-16 and **33 commits** (24
    first-parent) from other sessions landed unseen. Observed in that one
    session: a frozen clock; background monitors dead with the host while the
    session still awaited their notifications; MCP servers detaching
    mid-conversation; a user interrupt killing four subagents and leaving a run
    with no completion record; stale, out-of-order notifications.

    Therefore: **every filed claim carries a session identity AND a wall-clock
    date** (source pages already do — `authors:` + `ingested:`; this is why); a
    conclusion carried inside a long-lived session is **RECALL, not evidence**,
    and is re-derived against disk before it is filed or acted on (rule 10's
    obligation (b), now with a carrier-level mechanism); and **every pre-gap
    background task is presumed dead** — re-derive wall clock, git branch + tip,
    and bot vitals (`status.json` age, `runner.lock` age, `pythonw` count) at
    the start of any session that may have been suspended, snapshot-stamped.

    **(b) Delegated agents do not inherit the parent's skills.** Any agent
    dispatched to EDIT anything carries the focused-fix five-phase protocol
    **by path** in its prompt (SCOPE -> TRACE -> DIAGNOSE -> FIX -> VERIFY;
    IRON LAW *no fixes without completing scope/trace/diagnose first*; escalate
    at 3+ cascading fixes). Same failure shape as the delegated-measurement
    contract — agents fill gaps silently rather than halting. **Optimizations
    are exempt from the phase gate, never from rigor:** read the module first,
    measure rather than infer, no silent behavior changes, DoD matrix still
    runs.

12. **Declare the status, or the page is read as SETTLED.** Operator directive
    (2026-08-21, binding as `synthesis/governance-doctrine` rule 21, page
    `concepts/claim-status-discipline`). Stage 9 of `concepts/the-method`.

    **A wiki has no neutral register — filing something IS the claim that it is
    settled.** An in-flight finding written without a marker does not read as
    "preliminary"; it reads as **true**. It is not incomplete, it is
    **misinformation, believed because it is written down.**

    Every claim page carries `status:` in frontmatter, and **PROVISIONAL and
    SUPERSEDED must ALSO be visible in the body** — Obsidian's reading view does
    not render frontmatter, which is how a human actually reads the page.

    - **SETTLED** — measured, the measurement ran, **and its refuters ran and
      failed**. A claim about the evidence, not about the future. **Never stamp
      it in bulk**: stamping a page SETTLED because nobody objected is the
      orphan-claim failure (rule 10) at scale.
    - **PROVISIONAL / WIP** — the investigation is open. **Actionable as a LEAD;
      never citable as evidence; nothing downstream may depend on it.** Must
      carry a `> [!warning] PROVISIONAL` callout, a `## What would settle this`
      section, and its **PENDING REFUTERS** named (default disposition
      **REFUTED**) — plus an entry in `synthesis/owed-measurements`.
    - **SUPERSEDED** — overturned, never deleted. Must carry a
      `> [!failure] SUPERSEDED` callout and a `**Superseded by** + a wikilink` wikilink
      routing the reader forward.

    **ENFORCED, not adopted:** run
    `python ~/.claude/skills/llm-wiki/scripts/lint_claim_status.py --vault .`
    Mutation-verified 2026-08-21 (6/6 checks fired on a planted defect). It
    **cannot** see whether content is settled — a page that is
    wrong-but-declared-SETTLED passes it and always will.

    **Undeclared is an honest third reading** — *no session has asserted a status
    here*. The ~204 pre-existing pages were deliberately NOT bulk-stamped;
    declaring page-by-page as each is next touched is a task, not a disposition.

## Ingest checklist for a new document from this repo
- Create `sources/<slug>.md` with the date, the verdict, the numbers, and what it supersedes.
- Update every concept page whose position it changes — especially if it *retracts* something.
- Add to `synthesis/open-contradictions-register` if it conflicts with a standing claim.
- Add to `synthesis/owed-measurements` if it defers anything, and remove anything it closes.
- **Before filing any proposed technique/input/data source, check
  `synthesis/evidence-closed-register`** — rejections bind future sessions and reopen only on
  their stated revisit terms.
- If it mints or moves a regime cut of any kind, update
  `synthesis/comparability-boundaries` — the one authoritative table — in the same session.
- Check whether it changes `synthesis/the-money-path-thesis` or
  `synthesis/learning-pipeline-arc` — those two carry the live narrative.
- Regenerate the index; append to the log.

## Standing question to re-check on every ingest
*(Rewritten 2026-08-02 — `cost/sigma` was the binding constraint until the corrected P&L measurement.
Amended 2026-08-10 evening: the model freeze, the era-4 gate, and the capital epoch.)*
Does the new document move any of these five?
0. The **model freeze and the era-4 verdict gate** (2026-08-10, CAIO adjudication,
   `wiki/sources/session-20260810-stressor-epoch`): model-side investment is FROZEN; the ONLY
   unfreeze trigger is the pre-registered era-4 gate readout (`scripts/cohort_eval.py` —
   NO_GROSS_EDGE / COST_BOUND / CONTINUE at n≥50 on the post-epoch cohort, population cut
   `max(B4_TS, CAPITAL_EPOCH_TS)`). Cohort-resetting changes are fenced by the accrual
   moratorium (governance rule 17) — a document proposing one requires the operator's
   adjudication ON ITS FACE. Mid-accrual numbers are not a trend.
1. The **payoff-asymmetry diagnosis** — 0.561 observed vs 0.750 needed at 57.1% win rate,
   post-quarantine n=217 (`wiki/concepts/payoff-asymmetry`).
2. The **two decisive nulls** — no entry-timing signal (random-entry MFE control, n=51) and no
   surviving bracket geometry (pre-registered 48-combo grid): exit design minimizes bleed, it
   does not create edge.
3. The **ranked cost levers** — maker-only execution, asymmetric entry banding, pooling across
   symbols — or the 432-bar cohort hold (no geometry change until 50 closed trades).
4. The **execution-era boundaries — now FOUR** (updated 2026-08-10): (i) the QA-contamination
   quarantine (`858c8d71`/`483f6727`); (ii) commit `8e5455e8` (2026-08-02, `passive_base_prob`
   0.45 → 0.048, the XV-021 measured trade-through rate, ts~1785717000) — pre-boundary paper
   data is fill-flattered 9x, and a starving paper book after it is the honest rate, not a
   defect (`wiki/synthesis/risk-posture-doctrine`); (iii) commit `3cfe0710` (2026-08-08, the
   fill-sim TTL normalization, `wiki/sources/session-20260808-morning-batch`) — rows before it
   were filled under the compounding simulator that gifted 6h long-book orders certainty fills
   at −50bps; **(iv) commit `aeeaae36`, stamp `2026-08-10T11:03:35Z` (= `2026-08-10 06:03:35
   −05:00`; the shipped `_doc` and `config_guard` comment say "2026-08-09" — use the stamp,
   `wiki/sources/session-20260810-fill-double-count`)** — the fill sim modelled ONE market
   crossing with TWO mechanisms, giving `2f−f² = 21.96%` against an `f = 11.66%` target
   (ledger-measured 22.30%), **1.88x at the touch and approaching 2x as f falls**. Any paper
   fill-rate, entry-rate, markout, per-asset or cohort statistic must be qualified by which side
   of EACH boundary it was measured on; label cohorts treat all four dates as regime cuts.
   **Boundary (iv) is special: the ENTIRE corpus is on its pre-boundary side** (last ledger row
   2026-08-10T06:50:23.746Z, zero fills at or after the commit), so **every fill statistic in
   this vault carries the ~1.88x near-touch upward bias** — and "the fill sim is honest now" has
   been claimed three times and been wrong twice, so require the measurement, not the commit.
   *(2026-08-10: the shipped strings now carry the true stamp — `2fee7f64`.)*
   **Since `2fee7f64`/`6fe6d98d`, `fills.csv` rows carry an `exec_era` provenance column
   (now "7-e7d5ca1a" since cut #7); pre-schema rows are deliberately blank = decide by ts.**
   *(2026-08-11: cut #7 MINTED — the geometry epoch, 2026-08-11T01:33:50Z, `e7d5ca1a`:
   Osler widen-beyond stop flip + ALGO-6 pins, landed at the free cohort reset — zero closes
   since the capital epoch, so the era-4 gate population is uniformly post-geometry with no
   change to the pre-registered cut. Stop-distance/MAE/stop-hit statistics must not pool
   across it. The ALGO-5 amendment is the pre-named next boundary.)*
   **PLUS the capital epoch (v): `2026-08-10T23:05:27Z` (epoch 1786403127), the $800 stressor
   reset** — capital 5000 → 800 with venue floors unscaled ($15 ticket 0.3% → 1.9% of equity),
   so gross%/net%/expectancy statistics must also be qualified by capital regime; the era-4
   verdict population cut is `max(B4_TS, CAPITAL_EPOCH_TS)`. **The one authoritative table of
   ALL cuts (fill axis, label axis 7566ea88, capital axis, and the paper/real boundary above
   them) is `wiki/synthesis/comparability-boundaries` — check it before pooling any two
   numbers.** And above them, the **paper/real boundary** (domain rule 9,
   `wiki/concepts/paper-real-boundary`): does the document quote any sim-conditioned number —
   fees, fills, markout, RTT, dollars — as if it were venue truth? Flag it if so.
