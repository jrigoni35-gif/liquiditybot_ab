---
title: "Claim Status Discipline (SETTLED / PROVISIONAL / SUPERSEDED — an unmarked in-progress finding is misinformation)"
category: concept
status: SETTLED
summary: "Governance rule 21, operator directive 2026-08-21. A vault is read as SETTLED BY DEFAULT — that is what filing something MEANS — so an in-flight finding written without a status marker is not merely incomplete, it is misinformation that is believed BECAUSE it is written down. Every claim page therefore declares status: SETTLED | PROVISIONAL | SUPERSEDED in frontmatter, and the two non-settled states must ALSO be visible in the rendered body, because frontmatter is invisible in Obsidian's reading view — which is how a human actually reads the page. A PROVISIONAL page must name its PENDING REFUTERS and its settle-condition, or it never settles; a SUPERSEDED page must route the reader forward by wikilink, because nothing is ever deleted. ENFORCED, not adopted: scripts/lint_claim_status.py fails the vault on an invalid value, a PROVISIONAL page missing its callout / settle-condition / refuters, or a SUPERSEDED page with no supersedor — mutation-verified 2026-08-21 (each check planted and watched to fire). Type specimen: synthesis/live-readiness-verdict, filed the same day as a final-reading verdict while a cost-stack investigation that reframes its economics was still running."
tags: [governance, epistemics, method, enforcement, provisional, currency]
sources: 2
updated: 2026-08-21
---

# Claim Status Discipline

> **The defect this closes.** A wiki has no neutral register. **Filing
> something IS the claim that it is settled** — that is what a reader takes
> from the act of it being written down, dated, cross-linked and indexed. So
> an in-flight finding filed without a marker does not read as "preliminary";
> it reads as **true**. The corpus has already paid twice for a claim that
> "entered as prose and was believed because it was written down"
> ([[synthesis/documentation-drift-register]]).

**Operator directive, 2026-08-21. Binding as [[synthesis/governance-doctrine]]
rule 21.** Stage 9 of [[concepts/the-method]].

## The rule

**Every claim page declares its status in frontmatter:**

```yaml
status: SETTLED | PROVISIONAL | SUPERSEDED
```

**And the two non-settled states declare it again, visibly, in the body** — as
the first thing under the H1. This is not redundancy: **Obsidian's reading
view does not render frontmatter**, so a status that lives only in the YAML is
invisible to the human the rule exists to protect. A marker a reader cannot
see is [[concepts/adoption-is-not-enforcement|adopted, not enforced]].

## The three states

### SETTLED

The claim was **measured, the measurement ran, and its refuters ran and
failed**. It may be cited without re-derivation *of the finding* — though any
number that is load-bearing in the citing turn is still re-derived
([[concepts/the-method]] stage 0's trap; governance rule 18(b)).

**SETTLED is a claim about the EVIDENCE, not about the future.** It says the
work was done, not that it can never be overturned. A settled page is
overturned by being marked SUPERSEDED, never by being quietly edited.

> **SETTLED is not the default you may stamp in bulk.** Stamping a page
> SETTLED because nobody has objected to it is exactly the orphan claim this
> rule exists to stop — at scale. A page becomes SETTLED when a session
> *establishes* that its refuters ran, not when a session passes over it.
> This is why 209 undeclared pages were **not** bulk-stamped when this rule
> landed (see *Scope*, below).

### PROVISIONAL / WIP

The investigation is **open**: the measurement is running, unverified, single-
route, or its refuters have not been run. **A provisional finding may be acted
on as a lead. It may never be cited as evidence, and nothing downstream may
depend on it.**

A PROVISIONAL page **must** carry, or it fails the linter:

1. a visible `> [!warning] PROVISIONAL` callout under the H1, stating in one
   line **what is unverified**;
2. a `## What would settle this` section — *a provisional claim with no
   settle-condition never settles, it just ages into being believed*;
3. its **pending refuters**, named. The refuters that have not yet run are the
   whole reason the page is provisional; naming them converts "we are not sure"
   into a task list. **Default disposition REFUTED** applies —
   [[concepts/the-method]] stage 8.

**And it gets an entry in [[synthesis/owed-measurements]]** with what would
close it. A provisional page and an owed measurement are the same object seen
from two directions.

### SUPERSEDED

The claim has been overturned or replaced. **Nothing is ever deleted**
(governance rule 8) — the retraction *is* the content, and this corpus's
domain rule 3 requires the pattern *what was claimed → what refuted it → what
stands*.

A SUPERSEDED page **must** carry a visible `> [!failure] SUPERSEDED` callout
and a **`**Superseded by** + a wikilink`** wikilink routing the reader forward. A
superseded page with no supersedor is a dead end that still reads as an
answer.

## What the status is NOT

- **Not a confidence score.** It is a statement about **which stages of
  [[concepts/the-method]] have been completed**. "I feel good about this" is
  not SETTLED; "the refuters ran and failed" is.
- **Not a per-sentence device.** It is page-level. A page that needs two
  statuses is two pages, or one page with an explicitly scoped callout on the
  provisional section.
- **Not a way to file speculation.** PROVISIONAL is for work that is *running*,
  not a licence to file a hypothesis. Rule 18(c) still stands: a claim with no
  reference becomes an owed measurement, a graded literature pass, or a
  measurement run now — **never a page.**

## Enforcement

> **The rule that depends on every future author remembering it is not a
> rule.** ([[concepts/adoption-is-not-enforcement]])

`~/.claude/skills/llm-wiki/scripts/lint_claim_status.py --vault <path>` fails
(exit 1) on:

| # | check | why it exists |
|---|---|---|
| 1 | `status:` present but not one of the three | catches a typo or an invented value silently reading as undeclared |
| 2 | PROVISIONAL with no visible body callout | frontmatter is invisible in reading view |
| 3 | PROVISIONAL with no `## What would settle this` | a provisional claim with no settle-condition never settles |
| 4 | PROVISIONAL with no **pending refuters** | the unrun refuters are the reason for the status |
| 5 | SUPERSEDED with no visible body callout | same as 2 |
| 6 | SUPERSEDED with no `**Superseded by** + a wikilink` | nothing is deleted, so it must route forward |

Plus an **ADVISORY** (never an error) pass: an undeclared page carrying
in-flight language — *"in flight", "still running", "pending verification",
"work in progress"* and five siblings — is reported as a question, not a
finding. `--require-all` promotes *undeclared* to an error for a
full-enforcement run.

**Ledger pages are exempt by name** — `index.md`, `log.md`,
[[synthesis/owed-measurements]],
[[synthesis/open-contradictions-register]],
[[synthesis/documentation-drift-register]],
[[synthesis/evidence-closed-register]]. Every entry in those carries its own
disposition, so a single page-level status would be a false claim about the
whole register.

### Mutation-verified, not read-verified

Per [[concepts/the-method]] stage 5, the linter was **not** shipped on the
strength of reading correct. Each check was planted and watched to fire, then
restored:

- invalid value `status: PROVISONAL` (typo) → **flagged**, check 1;
- PROVISIONAL callout deleted → **flagged**, check 2;
- `## What would settle this` renamed → **flagged**, check 3;
- "pending refuters" removed → **flagged**, check 4;
- `Superseded by` wikilink stripped → **flagged**, check 6;
- clean control page → **passes**.

**What the linter cannot see, stated plainly:** it cannot tell whether a
page's *content* is settled. It checks that a declaration exists, is spelled
validly, and carries the structure that makes it useful. **A page that is
wrong-but-declared-SETTLED passes this linter and always will.** The advisory
scan is a keyword heuristic with a known false-positive rate — on the
2026-08-21 **pre-filing baseline of 209 pages** it raised 16 advisories, most of
them "mid-flight deploy" and similar innocent uses.

**Three further limits, from this rule's own adversarial pass (recorded per
governance rule 16 — a disposition gets the same pass as the finding):**

1. **Check 4 is satisfiable without doing the work.** It matches the phrase
   *pending refuters* anywhere on the page, so a page can pass by mentioning
   refuters without naming one. The check enforces that the AUTHOR WAS ASKED,
   not that the author answered. Same for check 3 — a `## What would settle
   this` heading over an empty section passes.
2. **THE ENFORCEMENT ITSELF IS UNENFORCED, AND LIVES OUTSIDE BOTH TREES.**
   `lint_claim_status.py` sits in `~/.claude/skills/llm-wiki/scripts/` — not in
   the vault, not in the repo, not under version control, and inside a
   directory this operator has previously **bulk-reinstalled**. If it is
   overwritten the rule reverts to hoped-for **silently**, and every schema
   file will still cite it by path. That is
   [[concepts/adoption-is-not-enforcement]] recurring one level up, on the
   enforcer. **Nothing runs this linter automatically** — no hook, no gate, no
   DoD stage. It is a tool a session must choose to run.
3. **Attack surface is genuinely small, and that is a finding too.** The linter
   is read-only, takes no network, evaluates nothing, echoes no page content
   (advisory hits come from a fixed needle list, never from the file), and
   reads with `errors="replace"` so a corrupt page cannot crash the run. The
   only file-derived string it prints is a path.

## Scope of the retroactive application (2026-08-21)

**Applied:** every page filed or amended in the 2026-08-21 session (six pages),
plus the new pages that session produced. **Not applied:** the other **203**
pages, which remain **UNDECLARED** — deliberately. Final count at filing close,
double-derived (linter JSON vs `grep -rl '^status: ' wiki/`): **212 scanned — 7
SETTLED, 2 PROVISIONAL, 0 SUPERSEDED, 203 UNDECLARED, 0 errors.**

This is the rule's own first exercise of itself. Bulk-stamping 203 pages
SETTLED without re-establishing that their refuters ran would be a
203-page orphan claim, filed in the name of a rule against orphan claims.
**UNDECLARED is therefore an honest third reading**: *no session has asserted
a status here.* Declaring status page-by-page, as each page is next touched
for any reason, is a task on [[synthesis/owed-measurements]] — not a
disposition.

## Type specimen — why this rule landed on 2026-08-21

[[synthesis/live-readiness-verdict]] was filed the same day as a
final-reading, five-blocker **VERDICT** — the vault's single answer to "can
this go live yet" — while a **cost-stack investigation that reframes its
central economics was still running** and unverified. Nothing on the page was
false. The page simply did not, and structurally could not, say *"an open
investigation may move this."*

The reframe under way ([[sources/session-20260821-cost-stack-in-flight]],
PROVISIONAL): on 434 closed positions the mean **gross** was measured
**POSITIVE**, with the configured fee stack turning it net-negative by roughly
a factor of ten — which does not change the NOT-READY verdict but changes what
the verdict is *about*. A reader taking the settled page at face value would
have carried a materially different picture of the problem for as long as the
investigation ran.

**That is the exact shape rule 21 exists to prevent, and it was produced by a
session that was following every other rule correctly.**

## Relation to the rules it extends

- **Rule 12** (*the wiki is the truth — file confirmed findings same-session*)
  says what to file. Rule 21 says **what filing asserts**.
- **Rule 18** (*no orphan claims*) says currency is part of correctness — a
  page a measurement contradicts gets its callout the same session. Rule 21
  covers the case rule 18 cannot: **the measurement has not finished yet.**
  Between "no finding" and "a contradicted page" sits a real state that had no
  vocabulary.
- **Rule 20's carve-out** is this rule's ancestor — a *temporary* suspension
  was filed as standing rule text and had to be amended the same session,
  because *everything in this vault reads as settled*. Rule 21 generalizes
  that amendment into a required field.
- **Rule 8** (*nothing is ever deleted*) is why SUPERSEDED exists at all,
  rather than an edit.

## Related

[[concepts/the-method]] · [[synthesis/governance-doctrine]] ·
[[concepts/no-orphan-claims]] · [[concepts/adoption-is-not-enforcement]] ·
[[synthesis/documentation-drift-register]] ·
[[synthesis/open-contradictions-register]] · [[synthesis/owed-measurements]] ·
[[synthesis/live-readiness-verdict]] ·
[[sources/session-20260821-cost-stack-in-flight]] ·
[[concepts/false-green]] · [[concepts/session-identity-is-not-stable]]
