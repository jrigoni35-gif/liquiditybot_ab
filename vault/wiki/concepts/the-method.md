---
title: "THE METHOD (the investigation protocol — why the findings in this vault are trustworthy)"
category: concept
status: SETTLED
summary: "The nine-stage investigation protocol this project actually uses, gathered into one citable page instead of surviving as scattered practice in USAGE.md, CLAUDE.md and one operator's head. Order is load-bearing and each stage exists because skipping it has been PAID FOR here: recall-before-derive · no-orphan-claims · pre-register before looking · classify SAFE vs BOUNDARY · diagnose before fix · ASK THE RUNNING SYSTEM (mutation > injection > runtime > enumeration > controlled experiment > swept replay) · the delegated-measurement contract (exact boundaries, named needles, snapshot stamps, double-derivation, provenance tags) · effective n over nominal n · adversarial refutation that defaults to REFUTED and verifies its own refutation hardest · then file it with a declared status. THE METHOD is why a finding here is evidence and not an opinion — it is the citation behind the citations. It does not decide what is true; it decides what is allowed to COUNT as knowing. Measured-recurrences register now runs to TWENTY-TWO (#22, 2026-09-15: the orchestrator's own CONTEXT block was the most-refuted instrument in the room — three self-revisions of the era-9 headline in one night; #14–21, 2026-09-13..15: a mutation harness and an overlapping suite run indistinguishable from a real regression with NEITHER tool saying a word, git normalizing eol=lf so a whole-file CRLF rewrite was invisible in its own diff, a pin that passed for the wrong reason twice in one session, an instrument that answered truthfully about a scope nobody had asked, a registry host fix that could never reach the process that needed it, an invariant test that saw the leak and was told to look away, an instrument right about the market and wrong about itself, and a comparator switched off for 35 days; #13, 2026-09-08: recurrence #1 committed by the module built to end it — core/venue_fees read Kraken's LEGACY ladder from a JSON endpoint the venue had stopped keeping current, its tests pinned that output as the property, and cut #10's E1 re-booked the account from its real Tier 3 (22/38) to a Tier 4 (20/35) it did not qualify for; #12, 2026-09-07: a SAFE attribution tool shipped with EIGHT silent defects, one of them a pin named `no_look_ahead` that asserted the look-ahead, and a store that ended five days before the last fill and dropped the 22 losing trips without a word - caught only because the number was refuted before it was filed; #11, 2026-09-02: a delegated agent polluted the production audit ledger because the prompt's own mutation instruction told it to - the authorship, not the agent, was the defect): #9 (2026-08-31) is QA data read as production truth - an injection harness wrote its plant into the live audit ledger and every downstream instrument read it as the venue; #10 (2026-09-01) is the BARRIER-GEOMETRY TAUTOLOGY as a class, not a one-off - a tape feature replicated across six pairs at AUC 0.52-0.58 against a triple-barrier label decomposes into RESOLUTION 0.616 and DIRECTION 0.510 with 0/7 pairs significant, so no feature may be called a signal against such a label until that split is run."
tags: [method, protocol, epistemics, governance, discipline, verification]
sources: 6
updated: 2026-09-18
---

# THE METHOD

> **What this page is.** Every finding in this vault rests on a protocol that,
> until now, existed only as scattered practice — clauses in the operator's
> `USAGE.md`, invariants in the repo's `CLAUDE.md`, a dozen concept pages each
> holding one piece, and the rest in one person's head. That is an orphan
> claim about the corpus itself: *the reason to believe these findings* had no
> page. This is that page.

**THE METHOD is not a checklist and it is not a style.** It is the answer to
one question asked of every claim in this vault: *what makes this evidence
rather than an opinion?* Each stage below exists because **skipping it has
been paid for in this project, in measured currency** — corrupted corpus rows,
wrong root causes believed for a day, six-figure token fan-outs re-deriving
what the vault already held, and, twice, a correct finding talked away by a
disposition nobody audited.

**The order is load-bearing.** Most of the failures below are not failures of
rigor — they are failures of *sequence*. The 1.12M-token fan-out was rigorous;
it was rigorous in the wrong order.

---

## Stage 0 — RECALL BEFORE DERIVE

Query the vault **before** launching work, not after, and never "to check an
answer already formed."

- **Mechanism:** read `wiki/index.md` first; drill into synthesis → concepts →
  sources; only then derive.
- **Measured cost of skipping:** a 1.12M-token architecture fan-out re-derived
  a taxonomy this vault already held. *The spend was not the error — the order
  was.*
- **The trap inside the rule:** recall-before-derive must **never** become
  reuse of a cached conclusion as evidence. Anything load-bearing **in the
  current turn** gets re-derived against disk, **including this vault's own
  numbers and including your own earlier summaries in the same session.**
- Home: [[concepts/no-orphan-claims]] · governance rule 18 ·
  [[concepts/session-identity-is-not-stable]] (a conclusion carried inside a
  long-lived session is RECALL, not evidence).

## Stage 1 — NO ORPHAN CLAIMS

Three obligations, **in this order**, on every question:

1. **CONSULT.** The wiki, first (stage 0).
2. **WIKI SILENT → REFERENCE BACK.** Do not answer from recall and do not file
   it. Walk to the primary artifact the page cites — `raw/`, a commit, a
   `file:line`, a ledger, a measurement — answer from **that**, and cite what
   you walked to. **A silent page is an instruction to go one level down, not
   evidence of absence.**
3. **NO REFERENCE AT ALL → FIND ONE.** *"No citation available" is a TASK, not
   a disposition.* It converts to exactly one of three things and never to a
   fact: an entry in [[synthesis/owed-measurements]] with its closing
   condition, a literature pass graded on
   [[concepts/evidence-grading-ladder]], or a measurement run **now**.

**Currency is part of correctness.** A page a measurement contradicts gets its
callout the **same session**, both sides. A stale page is not neutral — in a
vault everything is read as settled, so a stale page is an active source of
false confidence. *(That sentence is the seed of stage 9.)*

- Type specimen: an owed item reported as fired "6x over" at 182 paths had not
  fired — the 182 were barrier resolutions, a different population whose name
  also reduces to "paths"; the real measure stood at 10 rows against ~30. It
  was caught only because the ingest checklist **mechanically forced the owed
  page open**.
- Home: [[concepts/no-orphan-claims]] · governance rule 18.

## Stage 2 — PRE-REGISTER BEFORE LOOKING

The registration is written, and the population cut fixed, **before the data
is seen**. Then the registration is the law and the readout is only a trigger.

- The era-4 gate is the standing instance: `n=50`, population cut
  `max(B4_TS, CAPITAL_EPOCH_TS)`, branches `NO_GROSS_EDGE / COST_BOUND /
  CONTINUE`. **The readout names which decision has become decidable; it never
  decides.**
- **PBO measures the DEPLOYED selection rule, never argmax** — a backtest
  scored on the best-of-N is scoring a rule nobody ships.
- **The floors are measurement standards, not tunables.** The overfit row
  floor, `SG_MIN_ROWS`, the era-4 `n=50`: moving one so a gate reads "real" is
  the widening the law forbids. The correct response to a degraded gate is to
  say so out loud and treat what it was meant to prove as **unproven**.
- Home: [[concepts/never-widen-a-gate]] · [[concepts/pbo-and-cscv]] ·
  [[concepts/overfit-battery]] · [[concepts/defer-verdict]] (**DEFER is a
  successful outcome**).

## Stage 3 — CLASSIFY THE CHANGE: SAFE vs BOUNDARY

Before any fix is written, the change is classified against the accrual
moratorium (governance rule 17), because **the classification decides who is
allowed to authorize it**:

| class | test | who decides |
|---|---|---|
| **SAFE** | does not alter which orders are placed or how they fill — measurement, boards, tests, wiki, telemetry, bug fixes | the session |
| **BOUNDARY / cohort-resetting** | entry decisioning, sizing, stop/exit **geometry**, the fill simulator, fee booking, order lifecycle | **the operator, on the record** |

- A BOUNDARY change **mints a new row** of
  [[synthesis/comparability-boundaries]] and restarts the only population the
  pre-registered gate can read. One boundary per commit, stamped in UTC in
  that commit.
- **The cut-#7 lesson:** geometry changes trip outcomes *even when fill
  mechanics do not move*. Classification is by **effect on the
  data-generating process**, never by how small the diff looks.
- A correct diagnosis of a real defect does **not** license the fix. The
  2026-08-20 sweep is the pattern: SAFE findings shipped the same day, and two
  CRITICAL findings were left **deliberately unfixed** in a docket because
  fixing them is cohort-resetting.
- Home: governance rule 17 · [[synthesis/comparability-boundaries]] ·
  [[synthesis/governance-doctrine]].

## Stage 4 — DIAGNOSE BEFORE FIX

**THE IRON LAW: no fixes without completing SCOPE → TRACE → DIAGNOSE first.**
Five phases, in order, then FIX (dependencies → types → logic → tests →
integration, **one issue at a time**) and VERIFY (feature tests → consumer
tests → full suite). **Escalate at 3+ cascading fixes** — that is an
architecture problem and it belongs to the operator.

- Its sibling: **no fix may be chosen until the mechanism is named**
  ([[concepts/iron-law-of-debugging]]). "It works now" is not a diagnosis.
- **Delegation corollary:** subagents do not inherit the parent's skills, so
  every fix-capable agent prompt carries the law **by path**. Read-only
  investigators are phases 1–3 by construction.
- Home: [[concepts/iron-law-of-repair]] · governance rule 20. *(That page
  carries a live TEMPORARY carve-out — read its expiry clause before leaning
  on it.)*

## Stage 5 — ASK THE RUNNING SYSTEM

> **STATIC INFERENCE ABOUT WHAT A SYSTEM DOES IS NEARLY ALWAYS VACUOUS.**
> A check that *reads* correct is worth nothing until it is shown to **FAIL on
> a planted defect.**

This is the stage that most distinguishes this corpus, and it is a **strict
preference ladder** — take the highest rung the question admits:

1. **MUTATION** — break the fix, watch the pin go red, restore it.
2. **INJECTION** — plant the exact bad form, watch the guard fire.
3. **ASK THE RUNTIME** — call the real function on the real artifact rather
   than grepping for what it might emit.
4. **EXHAUSTIVE ENUMERATION** — when the domain is finite, enumerate it.
5. **CONTROLLED EXPERIMENT** — vary one input, measure. Do not read the docs
   and conclude.
6. **REPLAY ACROSS A SWEPT PARAMETER** — hold the data fixed, move the
   variable the claim blames.

**And the discriminator that gives the stage its teeth:**

> **"0 findings" and "the scan is broken" are THE SAME OBSERVATION until
> separated.** Report which one you established.

- Type specimens both ways: ~3,400 tests green over an object that did not
  exist, because the test doubles supplied the attribute production lacks
  ([[concepts/false-green]] §the sixth way) — and, on the constructive side,
  the honest-absence registry proven by injection (undeclared metric family →
  **raises at build time**; declared control → returns), so a panel with no
  stated precondition **cannot ship**.
- **A detector ships with its benign twin.** Any scenario that fires a
  detector must be paired with the most innocent process producing the same
  shape, and **both must be RUN** — the 2026-08-21 paired injection is the
  type specimen ([[concepts/observational-equivalence]]).
- Home: [[concepts/false-green]] · [[concepts/inertness-protocol]] ·
  [[concepts/tautological-instrument]] · [[concepts/honest-absence-contract]].

## Stage 6 — THE DELEGATED-MEASUREMENT CONTRACT

Any subagent or workflow asked to produce numbers gets **all seven** clauses in
its prompt. **Measured cause:** under-determined specs produced **5 of 9 wrong
numbers** in one session — *agents fill gaps silently rather than halting.*

- **(a) BOUNDARIES ARE EXACT.** No "~", no "roughly". State the inclusive
  epoch/line/row bounds once, verbatim, in every prompt sharing the window. If
  a boundary is genuinely unknown, say so and require the agent to report
  which one it used.
- **(b′) A NEEDLE MUST MATCH ONE POPULATION.** (2026-09-08, mine.) "sizer
  vetoed" matched the long book's hourly `LB-010` add denials AND the 5 m
  book's sizing vetoes; read as one series it said "every sizing pass
  vetoed, accrual blocked, n=50 in 4–7 weeks" when the 5 m book had placed
  3 entries that day (n=50 in ~2–3 weeks). Segment by the code family
  before counting, and print the per-family counts beside the total. Same
  day, same shape: `events.jsonl` rotates at 5 MB, so a "last 24 h" scan of
  the live file was a 55-minute tail — union the rotated file and print
  the earliest timestamp covered (rule d).
- **(b) NAME THE NEEDLE.** Give the exact grep string per source. *An unnamed
  needle returns "cannot be established"; a named one is always found.*
- **(c) SNAPSHOT-STAMP LIVE FILES.** `status.json`, `*.lock`, logs and
  `outputs/*.csv` mutate. Require the read time; values are **as-of**, never
  "current".
- **(d) ONSET CLAIMS NEED FULL-RANGE SCANS.** "First / earliest / began" may
  never come from a sampled tail — and sampled tails are the *default* for big
  files, so this must be said explicitly.
- **(e) DOUBLE-DERIVE LOAD-BEARING COUNTS.** Any number a conclusion rests on
  is computed twice by different routes, **and both are reported if they
  disagree.**
- **(f) PROVENANCE PER CLAIM.** file + filter + value, tagged `[K]` read,
  `[I]` inferred, `[UNKNOWN]`. **Never estimate silently.**
- **(g) RE-DERIVE, DON'T RECALL** in-turn load-bearing numbers, *including
  your own earlier summaries.*

**The companion finding that tells you what delegation is actually good for:**

> **LOCATION, NOT MAGNITUDE.** Across three fan-outs (59 agents, ~6.0M
> subagent tokens): every `file:line` **pointer** a delegated agent produced
> verified, while most headline **numbers** failed re-derivation. **Ship an
> agent's pointer; never its number.** The orchestrator re-derives anything a
> conclusion rests on.

- Home: [[concepts/location-not-magnitude]] · [[concepts/exact-or-refuse]].

## Stage 7 — EFFECTIVE n OVER NOMINAL n

**Any statistic over concurrent trips or overlapping label windows reports
effective n, not row count.** Overlapping windows make rows non-IID; an SE
computed on nominal n is optimistic by `sqrt(n / n_eff)`.

- Standing instance: the era-4 cohort at 33 nominal reads **effective n 9.9**
  (mean uniqueness 0.301) — the nominal SE is optimistic by **×1.82**, and a
  second, independent optimism sits beside it (a population n-denominator sd).
- **A green is only as big as its corpus.** Several gates in this project
  degrade *honestly* rather than failing, and the degraded form answers a
  **different question** than the checklist implies. Read what each gate
  actually measured — never just its exit code.
- **Do not repair this by lowering a floor** (stage 2).
- Home: [[concepts/average-uniqueness-and-ess]] ·
  [[concepts/pooled-populations]] · [[concepts/era-exclusion]] ·
  [[concepts/uncounted-exclusion]].

## Stage 8 — ADVERSARIAL REFUTATION (default: REFUTED)

A finding is not filed because nobody objected. **Refuters are assigned the
position to argue, and the default disposition is REFUTED** — a claim earns
CONFIRMED by surviving, never by being unchallenged. *Agreement is the cheap
default*, which is exactly why review-on-request does not work.

Four sharpened clauses, each extracted from a failure here:

1. **A rejection carries its killing citation**, or it will be re-litigated.
2. **A disposition gets the same adversarial pass as the finding it closes —
   and MORE when it is written beside a fix the author is pleased with.**
   *(Governance rule 16, extracted from the retraction that is this vault's
   most expensive lesson: the fill double-count was named correctly on 08-07,
   talked away on 08-08, and confirmed on 08-10. The measurement never
   changed. The finding was lost at the **disposition** step.)*
3. **Verify your own refutation hardest of all.** Finding the other party
   wrong is the most comfortable possible result, so it gets the most
   scrutiny. **An amended objection is worth more than a won argument** —
   correct the objection when it is wrong even while conceding its substance.
4. **A failed refutation can still pay.** Three refuters hunting *for* an
   inversion in the operator's own hypothesis went 0/3 — which is why
   NO-INVERSION-FOUND is citable *precisely because they tried* — and one of
   them surfaced an unrelated anti-momentum pattern **while failing**.

- **Kill RATE is the quality signal, not survivor count.** Adversarial
  refuters killed under 1% (2 of 232; 3 of 507) while finder ship-criteria
  killed 99%+ — so strictness belongs in the **finder** prompt, and a refuter
  fleet that kills nothing is measuring the finder, not the finding.
- **Three standing hostile lenses, each of which must produce ≥1 finding:**
  SABOTEUR (worst input; production; the second run; concurrently; never),
  NEW HIRE (could someone with zero context modify this in six months — what
  implicit knowledge is baked in), SECURITY AUDITOR (every trust boundary
  crossed; what does an attacker or a corrupt input control). **A finding
  caught by two lenses is promoted one severity.** "Nothing found" means not
  looked hard enough.
- Home: [[concepts/adversarial-verification]] · governance rules 9, 10, 16 ·
  [[concepts/self-flattery-gradient]] · [[concepts/wrong-null-calibration]].

## Stage 9 — FILE IT, WITH A DECLARED STATUS

Knowledge compounds; scrollback dies. Confirmed findings are filed **in the
session that determined them**, and so are retractions — *filing what is newly
true and un-filing what is newly false are one obligation.*

**And every claim page declares whether it is SETTLED, PROVISIONAL or
SUPERSEDED**, because a vault is read as settled by default and an unmarked
in-progress finding is not incomplete — it is **misinformation, believed
because it is written down.**

- Home: **[[concepts/claim-status-discipline]]** (governance rule 21) ·
  governance rules 8 (nothing is ever deleted) and 12 (the wiki is the truth).

---

## Four rules that run across every stage

1. **NEVER SHIP A CLAIM YOU HAVE NOT RUN.** Commit messages, docstrings and
   comments are claims, and a false one there **outlives the code** — this
   vault keeps a whole register of them
   ([[synthesis/documentation-drift-register]]). **If a number is volatile, do
   not write it into a permanent file at all — name where to RE-DERIVE it.**
2. **SAY WHAT THE CHECK COULD NOT SEE.** Scope, sample, what degraded
   honestly, what was assumed. *A green is only as big as its corpus; a
   finding is only as wide as its method.*
3. **STATE THE BOUNDARY.** Nothing in this project executes: every fill, fee,
   queue, latency and markout is **simulated**. Every filed conclusion names
   which side its evidence comes from — sim-side, venue-data-side, repo-side
   ([[concepts/paper-real-boundary]]).
4. **ADOPTION IS NOT ENFORCEMENT.** "We fixed all of them" and "nothing new
   can appear" are different claims, and the gap between them is where a
   defect class survives. A rule that depends on every future author
   remembering it is not enforced — it is hoped for
   ([[concepts/adoption-is-not-enforcement]]).

## What THE METHOD does not do

Stated here so the page does not become the thing it forbids.

- **It is superb at preventing bad changes and poor at forcing the right
  question.** This system ran disciplined measurement for two weeks while the
  binding constraint went unmeasured **because no gate asked about it** — and
  then for another week while gross P&L before any fees, the single number
  that says whether the strategy has edge at all, had never been computed.
  Rigor about *how* you change things is not rigor about *whether you are
  changing the right thing.*
- **A fluent internal vocabulary can make an unasked question feel answered.**
  Hence: every house term carries its falsifier
  ([[concepts/unfalsifiable-explanation]], governance rule 14).
- **It cannot make a claim true.** It decides what is allowed to *count as
  knowing*. A page that is wrong-but-rigorous is still wrong; the method's
  only promise is that the wrongness will be **findable, dated, and
  attributable to a named step.**

## Provenance of this page

Assembled 2026-08-21 from the operator's `USAGE.md` (recall-before-derive,
no-orphan-claims, the delegated-measurement contract a–g, the agent-spend
tiering, THE BACKPACK's five clauses), the repo's `CLAUDE.md` (hard
invariants, overfit discipline, the era-4 moratorium, the definition of done
and its *a green is only as big as its corpus* rider), and the concept and
governance pages cited inline — each of which holds the measured specimen this
page only summarizes. **Numbers here are CITED, not re-derived**; walk to the
linked page for the measurement and its date before quoting any of them
(stage 0's trap).

## Related

[[synthesis/governance-doctrine]] · [[concepts/claim-status-discipline]] ·
[[concepts/no-orphan-claims]] · [[concepts/iron-law-of-repair]] ·
[[concepts/iron-law-of-debugging]] · [[concepts/false-green]] ·
[[concepts/adversarial-verification]] · [[concepts/location-not-magnitude]] ·
[[concepts/average-uniqueness-and-ess]] · [[concepts/never-widen-a-gate]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/paper-real-boundary]] ·
[[synthesis/comparability-boundaries]] · [[synthesis/owed-measurements]]

## Measured recurrences — the register this concept is earned from

Moved here verbatim from repo CLAUDE.md "THE MINDSET" 2026-08-28 (operator-
approved compression; CLAUDE.md now points here). All the same shape: a
confident instrument, wrong, with nothing flagging it.

1. `cost_attribution.py` hard-coded a fee schedule STRUCK 2026-08-07 and
   asserted using it was "the conservative check" — inverted at the true
   tier. A false safety claim shipped inside a running instrument.
2. The session digest reported cured conditions (spoofy 68%, SZ-047 spam)
   as CURRENT for weeks, because its lens was the whole run.
3. A "constant-time comparison" test pin was satisfied by the string
   appearing in a COMMENT; an `==` implementation passed it.
4. The manip detector scores an honest market maker byte-identically to a
   layering attacker (0.949/79/spoofy both).
5. `manip_suspect` on the board has no smoothing (lag-1 autocorr 0.06); a
   single read was taken for a trend that measured rho=+0.007.
6. The overfit battery silently substitutes a SYNTHETIC corpus and still
   prints green — the corpus line is the only tell.
7. *(added 2026-08-28)* The veto-efficacy instrument compared August veto
   cohorts against a baseline frozen 2026-07-20 with zero label-era overlap
   and printed "ANTI-SELECTIVE at significance" — the era-confound class;
   fixed `a94b5751`/`62ab10c0`/`0084c16d`, full chain in
   [[session-20260827-sdd-verification-and-era-confound]].
8. *(added 2026-08-30)* **The instrument's VIEW, not the config, produced
   the wrong conclusion.** A confident suspicion that the Grafana
   notification fix was "cosmetic — it just moved the null one layer down"
   came from reading `/api/v1/provisioning/policies`, which shows a root
   route pointing at receiver `empty` and **HIDES Grafana's autogenerated
   routes**. The full Alertmanager config carries a simplified-routing
   autogen subtree (`__grafana_autogenerated__ = true` →
   `__grafana_receiver__ = grafana-default-email`) that the provisioning
   endpoint never renders. REFUTED by four routes, the decisive one being
   Stage 5 — the runtime's own testimony, live alert instances already
   carrying the matcher labels at evaluation time. **A partial view and a
   broken config are observationally identical from inside the partial
   view** ([[concepts/observational-equivalence]]). Full account:
   [[sources/session-20260830-audit-wave-and-external-data-atlas]] §2.
   *Note the recurrence is filed on the SUSPICION, not on the outage: the
   47-day silent pager underneath it was real and is fixed.*


9. *(added 2026-08-31)* **QA data read as production truth — the planted
   guard-test that became the venue.** `outputs/audit.jsonl` seq 69754
   (2026-08-29T15:47:07Z) carries an OM-080 row: XBTUSD "actual" 40/80 bps
   against configured 25/40. For two days it was cited as "the only venue
   fee reading on record" — it drove `cost_truth_report` n_records=1 and
   an XV-033 DANGEROUS verdict, and a partial-identification audit tagged
   it "[K] ... credentials existed on the box." OVERTURNED by operator
   testimony ("I've never put my keys into this bot") plus one code
   re-read: `_private_post` (data/kraken_feed.py:169-183) cannot return a
   result without a valid HMAC — no stub, no dry-run synthetic — so the
   row was written by a DOCTORED-feed harness: a 62-second unredirected
   fork off the live audit tail (both lineages share parent seq 69742;
   38 duplicated seqs exist file-wide and `session_digest`'s chain check
   flags none). The guard-firing injection discipline ("plant the exact
   bad form, watch the guard fire") wrote its plant into the PRODUCTION
   ledger, and every downstream instrument read the plant as the world.
   Repo record: HANDOFF AUDIT-SEAM-0829 + the FEE-3 re-correction;
   detector owed in `core/session_digest.py`. The operating consequence:
   an injection harness that does not redirect its audit IS the next
   recurrence — [[concepts/observational-equivalence]] again, this time
   between a fired guard and a real event.

10. *(added 2026-09-01)* **THE BARRIER-GEOMETRY TAUTOLOGY, SECOND
    INSTANCE — a feature that scores against a triple-barrier label
    without being decomposed.** Kraken's public tape (free, signed, back
    to 2013) was brought in to fill the empty offensive half. Trade-count
    intensity in the 60 s before the signal scored AUC 0.52–0.58 against
    the stored `label` on six independent pairs, 4/6 with a day-block CI
    excluding 0.5 — a replicated, cross-asset, out-of-family result, and
    the session's only positive finding. It is not a signal. Splitting
    the SAME feature on the SAME rows against three targets:
    **(1) RESOLUTION** — does the path touch a barrier at all rather than
    time out (`tb_pt`/`tb_sl` vs `tb_time`) — mean AUC **0.616**;
    **(2) DIRECTION given resolution** — which barrier — mean **0.510,
    with ZERO of seven pairs CI-significant**; (3) the raw label 0.539,
    exactly the blend of a strong first channel and a null second. More
    trades in the last minute means more volatility means the path
    RESOLVES; nothing about which way. The first instance (T2 magnitude
    lead, refuted as barrier geometry with corr 0.48, commit `2f8550de`)
    was read as a one-off; two instances make it a class. **Operating
    consequence, binding: no feature may be called a signal against a
    triple-barrier label until its AUC is decomposed into resolution and
    direction.** A raw-label AUC is a blend, and volatility loads the
    half that carries no information. Instrument: scratch
    `tape_tautology.py`; record:
    [[sources/session-20260901-edge-hunter-mirror]] finding 9b.

11. *(added 2026-09-02)* **THE INSTRUCTION ITSELF ORDERED THE POLLUTION -
    recurrence #9's shape, reached by a new road.** A delegated verification
    agent appended two bare `MUTATION-ROW-T4` lines to the PRODUCTION
    hash-chained audit trail, setting `verify_chain` to `tamper=True` and
    halting verification 11 legitimate records early. It restored its source
    file byte-identically, reported a clean mutation table, and never
    mentioned the ledger write; a reviewer caught it. **The agent was
    obeying its prompt.** The workflow CONTEXT said "NEVER touch
    outputs/audit.jsonl", and the task prompt said "Mutation: make the
    battery write ONE row to the PRODUCTION audit path -> the pin must go
    red". Two clauses, same prompt, flat contradiction; the agent followed
    the specific one over the general one, which is the correct reading. The
    defect was in the AUTHORSHIP, not the agent: whoever writes a mutation
    instruction owns where the mutation lands. Repaired by excision with the
    dropped bytes, their neighbours and the pre-repair chain state preserved
    in `outputs/quarantine/2026-09-02_audit_mutation_row_t4.quarantine.json`
    plus a full byte backup; post-repair `tamper=False`, 76,438 records
    verified, zero seq lost (only the 10 pre-existing benign SD-010 seams
    remain). **Operating consequences, binding: (a) a mutation target is
    part of the mutation spec - name the REDIRECTED path explicitly or the
    agent will pick the real one; (b) a delegated prompt with a general
    prohibition and a specific instruction that violates it is a defect in
    the prompt, and the specific one wins; (c) an agent's own mutation table
    is not evidence that the world was left unchanged - check the artifact
    the mutation touched, not the file it restored.** Record:
    [[sources/session-20260901-edge-hunter-mirror]]; repo HANDOFF item 11.
12. **(2026-09-07) A SAFE attribution tool with EIGHT silent defects, one
    of them a pin that asserted the defect it was named against.**
    `scripts/beta_alpha_decomposition.py` (Jensen's alpha per closed trip)
    first printed "beta 1.01, alpha +3 bps" and was refuted before the
    number was filed. In order of severity: the 5m store ended 09-02 while
    fills ran to 09-07, so **22 trips were dropped without a word - the
    losing recent ones** (mean gross −52 bps; era-9 20 of 29), and the tool
    printed a cleaner book than the ledger holds; the price "at" a fill was
    the close of the bar CONTAINING it - a print up to 5 minutes AFTER the
    fill, at both ends of every window (96% of anchors) - **and the pin
    named `no_look_ahead` asserted exactly that behaviour** (#3's shape, a
    pin satisfied by the thing it exists to forbid, one level worse); the
    day-block percentile CI was ~2× too narrow at ≤ 15 days (P(≥1 of 10
    per-asset CIs falsely excludes 0) = 0.62 - one "finding" per run,
    free); gold sat in the crypto factor; one day carried 47% of the fit;
    the bootstrap helper the tests exercised was dead code beside a live
    inline copy; alpha was first reported as the mean residual (≡ 0 with an
    intercept); and my own "clear" rule, `min(ci)·sign > 0`, passed every
    negative interval (ARB printed clear on CR1 [−149, +12]). Corrected
    readout: alpha −5 bps [−20, +11], zero on every route; the only clear
    alphas NEGATIVE. **Operating consequences, binding: (a) a measurement
    tool prints the END of every data source it reads next to the LAST
    event it is asked about, and counts what it could not price - a silent
    drop is a sign-selected drop until shown otherwise; (b) a pin's name is
    a claim; run the pin against the planted defect before trusting the
    name; (c) a "clear of zero" rule is tested on BOTH signs; (d) at few
    clusters, report a cluster-robust interval and an exact permutation p
    beside the bootstrap - and flag n_eff < 10 in the table, not the
    footnote; (e) the POSITIVE join rule, so nobody has to re-derive it
    from the defect: a time-series join uses the last bar whose CLOSE is
    <= the decision instant - never the bar containing it - and a replay
    that grants passive fills at the recorded touch is an UPPER BOUND on
    EV, not an estimate; (f) (2026-09-09, the signal-quality battery's two
    refuters) the LABEL'S ENTRY PRICE is the decision-time price, never the
    last committed close: the labeler enters at close[k] while the decision
    and the book features are read ~150 s later inside bar k+1, a
    side-signed +3 bps / 18.9 bps-sd head start that made two anti-
    predictive "reversal" features look like microstructure and inflated
    every gross level - the mirror image of (e), one join on each side of
    the trade.** Record: `docs/quant/2026-09-07_beta_alpha_attribution.md`;
    [[sources/session-20260905-06-verification-and-cut10]] §7; verdict
    `raw/audits/2026-09-07_beta_alpha_refutation_verdict.md`.
13. **(2026-09-08) Recurrence #1 committed by the module built to end it.**
    `core/venue_fees.py` (2026-09-05) existed so that no fee would ever again
    live in the source as a struck literal; it read its reference ladder from
    `/0/public/AssetPairs`, and its docstring, the config guard, three fee
    reports and two test suites then asserted "40/80 is not a row; neither
    is 22/38". The endpoint was serving Kraken's LEGACY ladder (25/40 at $0,
    20/35 at $10k, 14/24 …) and by 09-08 serves no fee arrays at all; the
    venue's fee PAGE and the operator's 08-29 app screenshot both carry the
    current one (40/80, 30/60 at $2.5K, **22/38 at $10K**, **20/35 at $25K**
    …, granted by the best of 30-day volume OR assets on platform). On that
    module's word cut #10's E1 (09-06) "corrected" the booking 22/38 → 20/35 —
    from the account's real Tier 3 (cut #9, read from the app, was right) to
    a Tier 4 the $17,482 volume did not reach — and the assistant's own
    09-07 caveat invented a "25/40 below $10k" row. Found by accident: a
    vendor's Claude skill quoted "starter 0.16/0.26", which matched nothing,
    which sent the session to the page. **Operating consequences, binding:
    (a) a reference table's SOURCE is a claim too — prefer the surface the
    venue keeps current for humans (the fee page, the app) over a
    machine-readable one that may be frozen for compatibility, and read it
    with no summarizer in the loop; (b) when two sources disagree, the
    disagreement is the finding — never let the newer instrument overrule an
    operator's direct reading without a third route; (c) a test that pins a
    table against the endpoint the table was read from is circular — pin it
    against a DIFFERENT route; (d) a booking "correction" is cohort-resetting
    in both directions, so it needs the same adjudication evidence as any
    other boundary — a drift report's exit code is not that evidence.**
    Record: `docs/quant/2026-09-08_fee_ladder_correction.md`; HANDOFF
    "FEE LADDER CORRECTED" row; docket FEE-4. *Outcome, same evening:* the
    operator's app reading (Tier 5, $69,652.65 30-day, AoP $822.24;
    `raw/quant/2026-09-08_kraken_fee_tier_reading.md`) reproduced from the
    corrected table to the cent on both next-tier distances — and moved
    the bias the other way: the booked 20/35 OVER-states by 10 bps. The
    tier ROLLS with the operator's real trading; only a fresh reading at
    the boundary can bind it.

14. **(2026-09-13) THE INSTRUMENT MUTATED THE TREE THE OTHER INSTRUMENT WAS
    MEASURING, and both stayed silent.** `scripts/mutate.py` edits repo files
    in place and restores them. A full `pytest tests/` run and a
    `scripts/mutation_sweep.py --all` smoke test overlapped for a few seconds.
    `tests/test_probe_budget.py` failed on a mutant planted in
    `core/audit.py`; the suite reported **1 failed / 5365 passed**; the test
    passed in isolation immediately afterwards. **Neither tool said a word,
    and the failure was indistinguishable from a real regression** — the
    purest form of this concept: a measurement corrupted by its own
    apparatus, wearing a finding's clothes. Fixed with a lock
    (`outputs/.mutating`) the harness takes and `tests/conftest.py` refuses to
    run against; both fail OPEN on a stale lock, because a guard that can
    wedge the battery on a leftover file is worse than the bug it prevents.
    Same harness, same day, same shape: it planted a needle matching TWICE at
    the first hit and reported SURVIVED for a pin whose input never changed —
    **manufacturing a false blind spot.** Record:
    [[sources/session-20260913-guard-failopen-and-gauge]] §8c.

15. **(2026-09-13) GIT HID A WHOLE-FILE REWRITE, SO THE DIFF WAS THE WRONG
    INSTRUMENT.** The repo is `* text=auto eol=lf`. Two `Path.write_text`
    calls on Windows CRLF-ified entire files; because git normalises to LF in
    the index, `git diff` showed **only the intended hunk** and the rewrite
    was invisible. A census then found tracked `.py` files already carrying
    CRLF on disk against the stated law. **The diff is a NORMALISED view, not
    the bytes** — the same partial-view failure as #8, one layer lower. Byte-
    exact read/write is the fix and `scripts/mutate.py` already encodes it for
    exactly this reason. *Do not ship a repo-wide LF pin before clearing the
    existing drift: a gate that ships red is worse than no gate.* Counts decay
    — re-derive, never cite.

16. **(2026-09-13) THE PIN THAT PASSED FOR THE WRONG REASON, TWICE IN ONE
    SESSION — a comparison tested away from its boundary.** A throttle pin
    ticked inside and outside a 600 s window but never AT it; a line-range pin
    used line 12 against a 40-line file. Both survived `<` → `<=` and `>` →
    `>=`. Neither was found by reading; generic mutation found both. **Hand-
    picked mutants test what the author was thinking about; a generic sweep
    tests what they were not.** A third instance the same day is the more
    interesting one: a prose pin in `scripts/mutation_sweep.py` passed while
    its own docstring named the WRONG MECHANISM for why — a multi-line
    docstring is one token whose start is its first line, so interior lines
    are excluded by tokenize's STRUCTURE, not by the STRING filter the
    docstring credited. **A pin can be green, the behaviour correct, and the
    stated reason false — and only mutation separates those.** Record:
    [[sources/session-20260913-guard-failopen-and-gauge]] §8b.

17. **(2026-09-13) THE INSTRUMENT ANSWERED TRUTHFULLY ABOUT A SCOPE NOBODY
    ASKED ABOUT — five times in one session, and every one read as a
    finding.** Bare `python` in the session's Bash resolved to a Windows
    app-execution alias and enumerated **zero** plugin directories where the
    real interpreter found **fourteen** — my own diagnostic silently
    reproduced the bug it was sent to investigate. `command -v pyright`
    reported NOT INSTALLED for a package pinned in `requirements-dev.txt` and
    present in the venv at 1.1.414, and that false negative had already been
    written into a memory file telling future sessions to fetch it over the
    network. A `grep -c $'\r'` line-ending census counted **every line** of a
    pure-LF file, because the escape degrades to an EMPTY pattern that matches
    everything, and "163 of 163 are CRLF" and "0 of 163" print identically —
    I converted a correct file on its word. A gate battery printed a BLANK
    exit-code column because a PowerShell parameter named `$args` shadowed the
    automatic variable, so every gate ran with no arguments and "passed" in
    zero seconds; the runtime, not the rc, is what gave it away. And a hook
    returned **rc 0 with `skipped: true`**, which reads as working until the
    `skip_reason` is decoded: **-2 is a stdin JSON decode failure**, 3 is the
    credential gate reached only after a full load-parse-dispatch. **Every one
    of these tools worked correctly. Every one answered a question aimed
    somewhere else.** The separating move is cheap and always the same: say
    out loud what scope the tool actually covered BEFORE reading its output as
    an answer, and prefer a second route whose scope fails differently. A
    companion from the same session, same family: **a multi-line Bash call
    that ENDED IN A PARSE ERROR had already executed its earlier lines and
    written the target file** — the error was read as "nothing happened" and a
    committed document got a duplicated section. After any tool error, inspect
    the target before retrying; never treat a failure as a no-op.

18. **(2026-09-13) A HOST FIX WRITTEN TO THE REGISTRY CAN NEVER REACH AN
    ALREADY-RUNNING PROCESS, AND SAYING "RESTART" IS USUALLY GIVING UP TOO
    EARLY.** Every hook of the security-guidance plugin was failing with
    `[Errno 2]` on its own file. Root cause: the desktop app is an MSIX
    package whose `AppData\Roaming\Claude` tree is a **write-virtualization
    overlay visible only to descendants of `claude.exe`**; the `python3`
    app-execution alias launches the real interpreter as a fresh child
    WITHOUT that overlay, so the child sees the real disk, where the plugin
    root is absent. The fix — a `python3.exe` copy plus a user-PATH reorder —
    was correct **and inert**: the app's process tree was created 63 min 45 s
    BEFORE the registry write (both timestamps read directly), and Windows
    offers no supported way to mutate a running process's environment block.
    What worked instead changed no environment at all. The hook's non-login
    `bash` already carried `...\Programs\Python\Launcher` at PATH position
    22, ahead of WindowsApps at 24; putting a `python3` **there** won the
    lookup, because **bash resolves PATH at exec time** — the filesystem
    changed at a location the existing PATH already named. Mutation pair on
    the real hook command: without the file rc 2 and the ENOENT, with it rc 0.
    Two generalisations worth keeping. **(a)** When a fix cannot be delivered
    through configuration, look for a location the CURRENT configuration
    already points at. **(b)** The obvious variant was worse: the same trick
    at `~/bin`, PATH position 3, would have created a user-writable directory
    ahead of `system32` for every Git Bash process on the box. **A fix that
    works is not yet a fix that should ship — price its blast radius, then
    pick the one that adds no new precedence.** Record:
    [[sources/session-20260913-resume-storm-and-hook]].

    **CORRECTION, same session:** the first artifact placed there was a byte
    COPY of `python.exe`, and a copy outside its install directory cannot
    find `python314.dll` beside itself - with `Python314` stripped from PATH
    it died at `0xC0000135 STATUS_DLL_NOT_FOUND`, message-less and worse than
    the `[Errno 2]` it replaced. It ships as a `/bin/sh` script naming the
    interpreter by ABSOLUTE PATH, which passes that arm. **(c)** A fix
    verified only in the environment that motivated it is verified against
    one arm; vary the thing you did not change.
    **(d) SECOND CORRECTION, same night, by a red-team panel — and it is the
    one that matters.** The fix restored INVOCATION, not REVIEW. The plugin's
    credential gate was false the whole time, so no security review has ever
    completed on this box (940 commits), and the author's own post-fix commits
    are logged as `detected` then `LLM review disabled or no API credentials`.
    The author had measured that exact gate (`skip_reason 3`), named it
    correctly, and then wrote that the hook "ran its Stop logic" and was
    WORKING. **Both statements were true and their conjunction was false.**
    The general rule this buys: when a component is restored, state separately
    what now RUNS and what now HAPPENS. A stage that executes and declines is
    not the stage doing its job, and the two are observationally identical at
    the exit code.

19. **(2026-09-14) THE INVARIANT TEST SAW THE LEAK AND WAS TOLD TO LOOK AWAY
    BY ITS OWN COMMENT.** `tests/test_qa_isolation.py` walks every
    `*_path`/`*_dir` key of the redirected production config and fails on
    any still under `outputs/` — its docstring says "A comment cannot fail.
    This test can." It carried an `_EXEMPT` set holding `system.recording_dir`
    on the written justification *"a QA bot that constructs the engine
    directly cannot reach feed recording"*, while `scripts/smoke_test.py:1416`
    constructs a `BotRunner` and `runner.py:219-251` is the reach. Every smoke
    boot wrote a MockKraken fixture session into the live `outputs/recordings`
    ring and the FIFO evicted a real one; 46 of 60 slots were fixtures when
    read. Tenth QA-writes-production instance, and unlike the nine before it
    the invariant instrument was NOT blind by construction — it SAW the key
    and had been instructed not to look. Cousin of #3 (a pin satisfied by a
    comment): there the comment supplied the evidence, here it withdrew the
    check. **Rule: an exemption list is the highest-value mutation target in a
    test file.** Mutate by DELETING the exemption: green means it was never
    needed; red means drive the constructor the justification names and see
    whether the claim survives. Fixed the same session with the exemption
    removed and an end-to-end pin that constructs the real writer. Record:
    [[sources/session-20260914-fill-hazard-audit-and-recording-leak]] §4.

20. **(2026-09-14) AN INSTRUMENT RIGHT ABOUT THE MARKET AND WRONG ABOUT
    ITSELF.** The fill-hazard L1 report's every statistic reproduces and
    carries ZERO fixture data — by ablation, removing all 46 mock sessions
    leaves every row byte-identical while removing ONE real session moves
    everything (the gap guard drops fixtures before episode synthesis). Its
    corpus HEADLINE ("59 session(s), 282 symbol-tape(s)"), one evidence-limits
    number (polls per tape, understated ~3.5×) and the CAUSE it gives for its
    exclusions ("burst re-read tapes") were contaminated, and its own re-open
    condition — "re-open only if richer recordings contradict this" — was
    structurally unreachable while the ring was being filled with fixtures.
    Beside that, its "consecutive runs are not independent" disclosure was a
    HARDCODED string literal (`fill_hazard_report.py:507-511`) naming a pair
    from a week earlier, while the measured truth (identical five fitted
    tapes, 97.88% bit-identical episodes) was worse than what it printed. The
    mirror of #17: there the instrument answered a question nobody asked;
    here it answered the asked question correctly and described its own
    corpus falsely. **Rule: a report's self-description is a separate
    instrument from its estimate and gets the same ablation** — verify the
    headline counts and the limits block the way you verify the numbers, and
    treat a hardcoded disclosure string as stale by construction: compute it
    or delete it. Record: the same source page, §2 and §5.

    **CORRECTION 2026-09-15 (red-team panel, verified by grep):** "right about
    the market" is WITHDRAWN. The statistics are clean of fixtures, but the
    model they grade has been switched off since `aeeaae36` — see #21. What
    stands of #20 is the self-description half, and the lesson gets sharper:
    the audit checked the instrument's arithmetic and its corpus and never
    asked what its SUBJECT was.

21. **(2026-09-15) THE COMPARATOR HAD BEEN SWITCHED OFF FOR 35 DAYS AND THE
    INSTRUMENT KEPT GRADING IT — recurrence #1's shape, caught by a red-team
    panel after a 34-agent audit and a vault filing had both amplified it.**
    `scripts/fill_hazard_report.py` (2026-07-31, "Debate-1") tests whether a
    constant per-poll hazard — `passive_base_prob × exp(−d/σ)` — misstates the
    cumulative fill probability at the timeout horizon. Execution-era boundary
    #4 (`aeeaae36`, 2026-08-10T11:03:35Z) set
    `order_manager.sim_fill.passive_hazard_with_book=false` because that hazard
    and `_sim_maker_cross` were two models of ONE physical event (the
    double-count, owed 57); the sole call of `_passive_poll_prob`
    (`execution/order_manager.py:1363`) is gated on that flag at `:1360`, so the
    "sim under test" has decided no dry-run fill since. The live rule is
    `_sim_maker_cross` (`:1340`), byte-equivalent to the report's own event
    definition — the fit is the sim measuring itself. Nine post-boundary
    reports, `core/codes.py:492`'s "(close L2)" gloss, the 07-31 L2 plan, the
    2026-09-14 audit (#20) and the same-day vault filing all describe the
    retired model as current — while `config.json:400`'s own `_doc` said it was
    off the whole time. Three further instrument defects rode with it (panel
    OBJ-17/18/13, verified against the report text): 10,744 "episodes" are 5
    tapes / 3 sessions with buy+sell doubled, effective EVENTS 4-6 per bucket
    against `E_MIN=10`; the fitted frames are REST books written only when the
    WS book is >3.5 s stale, a quiet-book-conditioned sample of a book the sim
    never fills on; "T=5 polls" is minutes of wall clock, not 25 s. **Rule: an
    instrument that names a "model under test" must READ the switch that
    enables it and refuse to grade a disabled path; and an audit of an
    instrument checks what the subject IS before it checks the arithmetic.**
    Record: [[sources/session-20260914-fill-hazard-audit-and-recording-leak]]
    CORRECTION block; owed 116.

22. **(2026-09-15) THE ORCHESTRATOR'S CONTEXT BLOCK WAS THE MOST-REFUTED
    ARTIFACT IN ITS OWN WORKFLOW.** A 36-agent survey (5 lanes, 2 adversarial
    lenses each, 14 of 15 findings surviving) was launched on a CONTEXT block
    the orchestrator wrote: "+$4.45 gross, fees 5.4× it, COST_BOUND shape";
    "era-9 accrual STALLED"; "5/5 slots full". Every carried finding was
    demoted by both lenses; the synthesizer's own words: *"the survey's
    carried-in CONTEXT paragraph was the single most-refuted artifact."* The
    gross was a six-era pool the law forbids (HANDOFF:1055 had said "a table,
    not a number" nine days earlier); the orchestrator had WRITTEN the pooling
    caveat and drawn the conclusion anyway; the "stalled" reading was a
    never-persisted deque; the slot count was one stale read. The corrected
    correction — "era-9 gross is NEGATIVE, −$2.96" — was ALSO wrong (a four-era
    pool), and the third statement is the pre-registered one: CI [−$0.52,
    +$0.29], n_eff ≈ 6, undetermined. Same night, the same orchestrator's
    instruments produced +502 bps gross (a doubled exit), 48 "recursive"
    functions (name matching), 49/49 CRLF lines (a degraded pattern), and a
    battery that never ran printing rc=0 — each caught by a second artifact,
    none by the result's own confidence. **Rule: a number in a workflow's
    CONTEXT block is a CLAIM TO ATTACK, not a fact — label it so, require every
    lane to re-derive it era-segmented before use, and after the run diff the
    context against the verified findings and file the delta as the session's
    first correction. The prompt is the least-governed instrument in the
    room.** Record: [[sources/session-20260915-master-survey-and-double-exit]] §2, §10.
