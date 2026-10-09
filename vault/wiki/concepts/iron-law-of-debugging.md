---
title: The Iron Law of Debugging
category: concept
summary: No fix may be chosen until the mechanism is named
tags: [debugging, discipline, method]
sources: 10
updated: 2026-08-06
---

# The Iron Law of Debugging

## Statement
> **No fix may be chosen until the mechanism is named.**

## The instance that invoked it
Two independent briefs — an advocate and a skeptic — converged on the same blocker: **the mechanism
closing probe positions was UNKNOWN**. Three of the eight bracket probes ever closed died at 19.8, 24.8
and 35.8 minutes — **too early for every known overlay**. Neither brief could name what ended them,
because the barrier field collapses every non-bracket close to a single generic string.

The consequence was procedural: an instrument to record the true close reason was ruled **SHIP FIRST**,
ahead of every candidate fix, because it was both briefs' prerequisite.

## Why it is load-bearing here
The same investigation had already produced **two wrong diagnoses** — one retracted in-document as an
apples-to-oranges comparison. Both were plausible, both would have justified a fix, and both were wrong.
Naming the mechanism is what separates a fix from a guess that happens to correlate.

## The second instance (2026-08-02): four hours on an unnamed mechanism
The duplicate-fills investigation spent **four hours** on the theory that fills were re-logged on
position restore — and that unnamed-mechanism theory **drove a diagnosis** before being refuted.
What refuted it was the timing structure: identical intra-block offsets (entry, then exits at
+20/+25/+85 seconds), identical prices to 10 significant figures, fresh `order_id`s — a restore
cannot reproduce deterministic offsets and would not re-enter. `append_fill` has exactly one
caller. The real mechanism was a QA harness writing fixtures into production
([[concepts/default-path-fallback-writes]]).

> **Corollary: "same data twice" is not evidence of re-logging; check whether the timing is
> deterministic.** ([[sources/session-20260802-digest]])

## The corollary sharpened (08-02 addendum): repetition is not evidence — timing structure is
The same session's residual-contamination sweep proved the point twice over, with **opposite
verdicts on two repeated-block groups**:
- `rows=2141` × 6 at **3603 s gaps** — the live hourly retrain cadence on an era-frozen corpus.
  **CLEAN.**
- `rows=60` × 7 at **548 s median** spacing — a test-suite burst. **CONTAMINATED.**

The first heuristic ("identical blocks = fixtures") **convicted the wrong group** — the six-fold
repeat was the live system doing exactly what an era-frozen corpus should do, and the actual
fixtures hid in the smaller, faster burst. Repetition count discriminates nothing; inter-block
timing does. Where timing is ambiguous, the decisive classifier is `order_id` membership in the
hash-chained `audit.jsonl` ([[concepts/default-path-fallback-writes]]).

## The corollary generalized (2026-08-03): arithmetic shape is not provenance either
The 08-03 bug sweep found fills with slip of **exactly −50.0bps** — an exact ref×constant
shape, the same silhouette as the known fixture fill (`1491.018493 = 1491.018493-ref × (1 −
2.5bps)` class). Verdict: **BENIGN** — they are [[entities/long-book]] accumulation adds whose
`add_offset_pct=0.5` rests bids 0.5% below mark **by design**, `order_id`s verified in the
hash-chained `audit.jsonl` ([[sources/session-20260803-bug-sweep]]).

> **An exact ref-multiple fill can be design (a resting offset) or fabrication (a fixture).
> The arithmetic alone does not distinguish them; the audit chain does.**

With the 08-02 lesson this completes a pattern: neither **repetition count**, nor **identical
values**, nor **exact-multiple arithmetic** convicts a row. The discriminators that work are
**timing structure** and, decisively, **provenance** — `order_id` membership in the
hash-chained audit log.

## The corollary extended (2026-08-04): substring where identity was required — third instance
The deploy-gate incident ([[sources/session-20260804-deploy-gate]]) is the **third instance in
one week** of the same defect class — matching by **substring or shape** where **identity**
was the requirement:
1. **`position_id` grouping** — one fabricated position under 16 ids, the 27x P&L error
   ([[synthesis/open-contradictions-register]] #2b/#15);
2. **the round-number plausibility error**;
3. **absolute-path substring filtering** — `"outputs" not in str(f)` matched *every* path in
   the gate's outputs-nested worktree, turning the test red exactly where deploys are decided
   (fixed `242568fb`, [[concepts/location-invariant-tests]]).

> **Match on the identifying structure — path components, keys, hash chains — never on a
> string that merely correlates with it.**

> ⚠️ **Citation hazard (2026-08-04):** a test that passes everywhere **except the deploy
> gate's worktree** is invisible until the first **external** push — a single-writer repo
> never exercises its own gate. "Green in every normal checkout" is not evidence about the
> gate environment ([[entities/auto-update]]).

## The corollary proven for security scanners (2026-08-04, same day): the scanner is a lead sheet, not a verdict
The [[entities/mythos-router]] adjudication ([[sources/session-20260804-mythos-router]])
ran `skill-security-auditor` against an external tool: raw verdict **FAIL, 28 CRITICAL /
8 HIGH** — and finding-by-finding adjudication showed **all 36 were false positives**.
20 "CRITICAL" were SQLite `exec()` calls on **fixed SQL literals**
(`BEGIN`/`COMMIT`/`PRAGMA` — transaction control, not injection); the rest were
`execFileSync`, the **shell-free arg-array** variant, in code with branch-name regexes and
path normalization rejecting `../`. Among the "HIGH" findings were **two of the tool's own
security tests** — a path-traversal assertion and a CI guard forbidding npm lifecycle hooks
— convicted for containing the attack strings they defend against. Independent sweeps (no
install hooks, 0 npm vulns, no phone-home) were clean.

> **Pattern-matching without adjudication convicts the innocent — for fills, for paths, and
> now for security scanners.** The scanner matched on surface shape (an API name, a string
> that looks like SQL); the discriminator that works is the same one as always: the
> identifying structure — **what user-controlled input can actually reach**. A raw scanner
> FAIL is a set of leads to adjudicate, never a verdict to act on — in either direction.

## The corollary reaches the stack's own instruments (2026-08-05): phantom ghosts
The telemetry-stack audit ([[sources/telemetry-stack-audit]]) ran a static regex scan over
`gc_pusher` and got **92 "displayed-but-not-emitted" metrics and 16 "non-snake_case"
names — all false positives**: the emitter builds metric names in f-strings, so a static
scan sees truncated prefixes (`liquiditybot_context_`, `liquiditybot_gate_`, …) and misses
the constructed full names. The repo's **own source-matching test is green (ghosts = 0)**
and is the authority; the audit's dark-metrics list was hand-adjudicated name-by-name
before filing.

> **Static metric scans over f-string emitters produce phantom ghosts.** Same shape as the
> security-scanner lesson one day earlier: the raw scan is a lead sheet, never a verdict —
> and this time the hazard bit the audit that was measuring everyone else.

## The law applied prospectively (2026-08-05): name the mechanism, then STOP
The 08-05 debug sweep ([[sources/session-20260805-debug-sweep]]) is the law run forward
instead of after an incident: every one of its 8 ranked findings ships with the **mechanism
named at file:line**, a concrete failure scenario, and a confidence grade
(confirmed/probable/possible) — and then **no fix is chosen**. Report-only; the fix
adjudication is a separate, owed decision ([[synthesis/owed-measurements]] item 29).
**The separation completed the same day:** the docket was adjudicated and 7 of 8 fixed in
two battery-green commits (`e7ebbf60`, `b409a24b`), with 29d **deferred** per the standing
432 hold — name the mechanism, stop, decide, then fix, all as distinct steps. And the fix
pass ran the law against the sweep itself: implementing 29b **corrected the sweep's own
"minutes of training" staleness claim** (the real window was the seconds of
rescore+gate+save — `load_raw` happens post-training), filed as an accuracy note on the
source page. Even a named mechanism gets re-measured when the fix touches it. The
sweep also applied the lead-sheet discipline to **its own output**: three plausible findings
were investigated to ground truth and filed as **near-misses (verified OK)** rather than as
findings — a torn-tail re-ship that cannot fire because the pusher's offset never passes an
unterminated line, a handle "leak" that CPython's scoping already closes, and the two sibling
pushers verified immune to the 08-03 duplicate-spawn class **by measurement of their tick
spacing**, not by style. Suspicion is a lead; only the named mechanism convicts — in either
direction.
When the mechanism cannot be named because the system does not record it, **the first deliverable is
the recorder**, report-only, with no behavior change. It confirmed the suspected overlay as the killer
(three records at 36.02-36.03 bars) — and left the 20-36 minute cohort **still unexplained**, with the
instrument armed.

## The law turned on the fixer (2026-08-05 evening): review your own same-day work with hostile eyes
The evening pass ([[sources/session-20260805-evening]], commit `46cdc19a`) ran an **adversarial
review of the day's own fixes** — `e7ebbf60`, `b409a24b` and the `bc198aa5` board restructure,
all written hours earlier. **Verdict: all seven round-1 fixes HOLD.** And it still found **three
residual edges, each narrower than the bug it neighbors**:
1. the torn-tail heal did not cover the **create-to-first-flush window**, so `fills.csv` could be
   born **headerless** and every consumer would misparse it silently
   ([[concepts/default-path-fallback-writes]]);
2. the rotation drain saved **new-generation offsets under the old inode** — a smaller instance of
   the hole it had just closed, and **invisible to its own provenance check**;
3. the **brand-new** `gate_divergence` panel collapsed its per-gate series under a bare `max()`,
   **hiding exactly the trend its own description tells the operator to watch**.

> **A fix's neighborhood is where the next bug lives.** None of the three was reachable by
> re-reading the original finding; each required attacking the **new** code. Naming the mechanism
> licenses a fix — it does not certify the fix. [[concepts/adversarial-verification]] is normally
> pointed at *someone else's* correction wave; here it was pointed at the same session's own, and
> paid for itself the same evening.

> ⚠️ **Corollary for instruments (2026-08-05):** an instrument can be **emitted, boarded, and
> still blind**. `gate_divergence` went from dark (telemetry audit finding 2) to displayed to
> *displayed-but-wrong* inside one session. **Boarding a metric is not displaying it.**

## The discriminator rule, applied before the fact (2026-08-05): AST over prose
`regime/haven.py` ships report-only, and the test that pins that restraint **parses the AST**
rather than grepping the source — because a **text search for `import execution` would match the
module's own docstring**, the docstring promising the very restraint being checked
([[synthesis/tangible-value-doctrine]]).

> **Match on the identifying structure, never on a string that merely correlates with it** — the
> 08-04 rule, this time used to *prevent* a defect instead of to explain one. The failure it
> avoids is the worst kind: a guard that is **green forever and worth nothing**, exactly like the
> substring path filter that bricked the deploy gate and the static metric scan that invented 92
> phantom ghosts.

## The inverted hazard (2026-08-05): a stale fixture erases a real metric
Finding 5 of [[sources/telemetry-stack-audit]] is a static scan **inventing** metrics that exist.
Its mirror surfaced the same day: the synthetic status fixture **predated** the `gate_divergence`
instrument, so `test_every_query_hits_an_emitted_metric` read the metric as **never emitted** and
silently **declined to protect it**. Same root error in both directions — **trusting a derived
artifact (scan output, test fixture) over the source**. Recorded as the reason the later `haven`
block was added to the fixture **at birth**.

## The law satisfied by an instrument, then betrayed by a test (2026-08-06): the hedge thrash
The 147-round-trip hedge thrash ([[sources/session-20260806-hedge-thrash]], commit `5c111962`) is
the cleanest case in the corpus of the law being **satisfied for free**. The mechanism did not
have to be inferred, hypothesized, or reconstructed: **`fills.csv`'s `reason` column recorded both
sides of the disagreement verbatim**, 147 times each —

```
hedge  sell  reason="net delta +1,086 beyond cap 932, beta=0.18"
exit   buy   reason="hedge unwind: correlation 0.00 below floor"
```

— which names the open's quantity and the unwind's quantity **in the same file, adjacent rows,
five seconds apart**. This is the payoff on the recorder the law demanded in its first instance
(where "the mechanism closing probe positions was UNKNOWN" because the barrier field collapsed
every close to a generic string). **A reason string that carries the deciding quantity turns a
four-hour investigation into a diff.**

> ⚠️ **And then the fix's own headline test was green on the buggy code.** Filing re-ran the new
> `tests/test_hedge_thrash.py` against the **parent's** module in a scratch tree: **3 of 5 failed
> (the real red-first tests), 2 passed** — and one of the two passing was
> `test_open_and_unwind_agree_across_repeated_evaluations`, whose docstring says *"The actual
> money bug."* It is **vacuous**: `evaluate()` is a pure function of a state the test never
> mutates and whose actions it never applies, so its `seen` set can only ever hold one element,
> **for any implementation**. It tests determinism, not oscillation.
>
> **A test named after the mechanism is not a test of the mechanism.** The repo had stated the
> discipline **one commit earlier** — the append gate was proven to bite by injecting a bare
> append ([[concepts/adoption-is-not-enforcement]] rule 5) — and did not apply it to the next
> commit. **Run the new test against the old code; that is the whole check, and it costs one
> `git show`.**

## Related
[[concepts/honest-null-result]] — the companion rule for when the measurement comes back empty.
[[concepts/adversarial-verification]] — the instrument this law reaches for when the fixer and the
reviewer are the same session.
[[concepts/two-paths-one-quantity]] · [[concepts/zero-is-not-a-reading]] ·
[[sources/session-20260806-hedge-thrash]] — the 08-06 instance above.
[[concepts/test-double-fidelity]] · [[sources/session-20260809-adversarial-audits]] — the
**third** instance of the AST-over-grep discriminator (2026-08-09): the pin shipped with
`1fee174e` **parses** rather than greps, because a substring check matched **the module's own
prose describing the bug** and failed on its first run. Three-for-three now: where a check
reasons about code, parse it — a text scan is defeated by the code's own documentation.
