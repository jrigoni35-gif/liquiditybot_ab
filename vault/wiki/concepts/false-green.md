---
title: "False Green (a passing signal that does not entail the work ran)"
category: concept
summary: "A gate's green is evidence only if green is impossible without the gated work actually running — this repo has produced green five ways without the work: a stage that printed SKIPPED for weeks because its tool was never installed (while the DoD claimed a zero-error ratchet), a test named for the money bug that was green on the buggy engine, a battery invocation that printed a banner and exited 0 without running any stage, a dependency verification (source grep + silent pip check) structurally blind to a vendor SDK's undeclared runtime requirement, and — CRITICAL, 2026-08-08 — the battery's own pytest stage gate that could NEVER fire: `start /b /wait cmd || (...)` satisfies || with start's LAUNCH success while the child's exit code lands only in ERRORLEVEL; a red pytest sailed to ALL GREEN. Design rules: missing tool = hard fail, never skip; output must be read — exit codes are not evidence; a gate is only as true as its last full-scope run on the current tree; a verification is only as good as the graph it can see; and a lying gate survives exactly as long as it is never the last line of defense. MIRROR SPECIMEN 2026-08-09: a RED explained away by a claim that was never run — 36fcfd6e's 'the identical red reproduces on the parent commit' was ASSERTED, NEVER RUN, and running it would have exposed the +9,272-row corpus corruption the same evening; design rules 7 and 8 follow (a first-time red is a blocking investigation, not a footnote; every orthogonality claim ships with the command that produced it). POSITIVE INSTANCE, same day: a gate that refused to compare and was RIGHT — ML-083 set an unfalsifiable badge aside and unwedged a bug-promoted champion with no operator override, the deploy record naming its own branch and operands; design rule 9 follows (a gate's refusal to compare is the gate working — fix what makes the refusal correct, not the gate). SIXTH WAY, same day, and it sits at the boundary of the class: ~3,400 tests green over a world that does not exist — the sizer read an attribute PortfolioState lacks, and the test doubles supplied it, so the work RAN CORRECTLY against a fabricated object while three risk controls were inert; design rule 10 follows (a test's docstring states its author's fear, not its scope — read the fixtures), and the AST-over-grep discriminator went three-for-three. SEVENTH WAY, 2026-08-09 evening: a pipeline's exit code belongs to its LAST command — the battery was reported green on `tail`'s status, the owed-44 lying-gate class recurring one day after design rule 2 was filed; unlike specimen #3 the mechanics are sound and the READER is pointed at the wrong process, so no change to the battery would have prevented it. The recovery move was worse than the error — a green run from BEFORE the change cited as clearance — and is filed separately as concepts/retroactive-excuse; design rule 11 follows (a caught false-green obliges a RE-RUN, never a citation; prior greens are CONTEXT, never CLEARANCE). Counterweight the same day: test_every_query_hits_an_emitted_metric fired CORRECTLY on the _SYNTH_STATUS schema drift — a gate that could fire and did. SEVENTH WAY RECURRED 2026-08-10 (owed 44, SECOND occurrence in one night): battery 14 reported as exit 0 off the TASK wrapper's exit instead of BATCH_EXIT — self-caught, corrected by reading the right marker directly (battery 14 was truly RED; battery 15's ALL GREEN verified on BATCH_EXIT=0), both markers now checked; the fix for this family is mechanical marker-checking, not vigilance. And the hidden RED was the family's best positive instance yet: the conftest production-outputs tripwire's FIRST confirmed catch (the owed-65 QA row in trade_paths.csv) — a true RED from a working gate, briefly hidden by a lying reader, recovered mechanically. THE CLASS IS NAMED at the cut-#7 session — EVIDENCE TRUNCATION, and it runs in BOTH polarities: battery 16 went RED on a correct tree because a test pin's <=4 threshold came from a head-truncated grep (main.py legitimately says tb_time six times) — where battery 14's truncated read HID a red, battery 16's MANUFACTURED one; same mechanism (a conclusion drawn from a truncated evidence stream), same fix (mechanical exact reads — count the call site, check the marker), and the pin's docstring records its own first version's mistake. NINTH WAY 2026-08-16: silence from a watcher that died with its host — background monitors exited (status 4) with a restarted host process while the session still awaited their notifications, and a killed workflow's only trace was 4 started lines with no result; design rule 12 follows — a channel is evidence only if the sender is proven alive at read time. THE NINTH WAY'S OWN INVERSE, measured hours later on the session that wrote it: the THIRD polarity of this page's founding discriminator, 'no output' vs 'no output YET'. Two background verification agents were declared dead on 0-byte outputs and a quiet inbox — rule 12 applied correctly — and both were merely LATE, reporting ~6 minutes after the eulogy. The action was right; the RECORD was wrong. Independent re-derivation reached the same numbers the late agents did, so the error was invisible in the output and would have been permanent. Design rule 14 follows — a presumption granted for ACTION may never be filed as a FINDING; write 'unreturned after N minutes' (the observation), never 'died' (the cause), unless a journal result line, an exit status or a PID established it"
tags: [method, gates, tests, enforcement, defect-class, discipline, dependencies, windows-cmd]
sources: 17
updated: 2026-09-15
---

# False Green

## The claim

**A gate's green is evidence only if green is impossible without the gated work actually
running.** The moment a passing signal can be produced some other way — a skip rendered as
success, a test that cannot fail, a wrapper that exits 0 without executing — the gate stops
measuring the code and starts measuring nothing, while continuing to *report*. That is worse
than having no gate: an absent gate is a known hole; a false-green gate is a hole wearing a
certificate.

> **A gate that can quietly not exist is a gate that lies.** (2026-08-07 capacity sweep,
> [[sources/session-20260807-capacity-sweep]])

## The five ways this repo produced green without the work

| Variant | Instance | Mechanism | Repair |
|---|---|---|---|
| **The skipped stage** | The battery's pyright type-ratchet stage printed **`SKIPPED` for weeks** — the tool was **never installed** on the box — while CLAUDE.md claimed a **zero-error ratchet** ([[sources/session-20260807-capacity-sweep]] §1b) | A stage that treats "tool missing" as skip **converts the gate's absence into its pass**; every local "battery green" in the window asserted a type gate that did not run | `test_windows.bat` now **hard-fails on a missing tool**; pyright 1.1.411 in-venv, measured 0 errors on shipped scope |
| **The vacuous test** | `test_open_and_unwind_agree_across_repeated_evaluations` — docstring *"the actual money bug"* — was **green against the pre-fix engine** ([[sources/session-20260806-hedge-thrash]] §5–6) | The test evaluated a book it never mutated: a pure function of unchanging state passes for **any** implementation | The fixed-point rewrite (`af544d4c`): evaluate → **apply the actions** → evaluate, proven RED against the genuine parent blob ([[sources/session-20260807-hedge-churn-guards]] §4) |
| **The false-green invocation** | A Git Bash **`cmd /c test_windows.bat`** run **printed a banner and exited 0 without running any stage** ([[sources/session-20260807-capacity-sweep]] §2) | The wrapper's exit code did not summarize its stages; read as a code it was a full pass, read as output it was nothing | **Output must be read — exit codes are not evidence.** A run without per-stage results is *unmeasured*, not passed; the invocation path is unsupported |
| **The blind verification** | The venv prune's **"zero importers verified"** — source grep clean AND `pip check` silent — was **wrong for pandas**: the moomoo SDK **hard-exits at import** without it (`site-packages/moomoo/__init__.py` prints `Missing required package pandas`, `sys.exit(1)`), a requirement **never declared to pip** ([[sources/session-20260807-closing-batch]] §4; cost: a 22:21–22:25 crash-loop) | Both greens were **structurally incapable of seeing the property**: grep sees only *our* sources, pip check sees only *declared* metadata — a vendor SDK's undeclared runtime requirement is invisible to each | **A verification is only as good as the graph it can see.** Static grep ≠ the runtime import graph; the conclusive check is **booting the pruned venv** — which is what caught it. Ledger amended: pandas KEEP, the other six removals stand |
| **The gate that could never fire** (CRITICAL) | The battery's **pytest stage** — its primary arm, 3,400+ tests — ran as `start /b /wait "" %PY% -m pytest ... \|\| (echo FAILED & exit /b 1)` from `101f7436` (the BelowNormal renice, 08-07) to `050421a7` (08-08): **the `\|\|` arm was dead from birth**, in the very commit whose headline was *"repair two lying gates"* ([[sources/session-20260808-morning-batch]] §2) | `start`'s **LAUNCH success satisfies the `\|\|` conditional**; the awaited child's exit code lands only in `ERRORLEVEL`, which the `\|\|` form never reads — so a red pytest (1 failed) **sailed through to ALL GREEN**, the first false arm the matrix ever produced. Found **live**, not by audit | `if errorlevel 1` (the documented-reliable form), **proven two-sided live** (old form fell through on an exit-1 child; new form fired). `tests/test_battery_gate.py` (4) pins the cmd semantics **both ways** and **bans the construct from the bat** — a class fence, not an instance fix |

**The adjacent case — the unrun gate.** The same sweep found full-scope **ruff RED on the live
tree** (C901: `core/persistence.py` `restore()` 42 > 40, introduced by `cf454d5e`'s hedger
snapshot section) — not because the gate lied, but because **nobody ran it full-scope after the
pull**. A gate that exists is enforced only as often as it is run: *"the DoD includes ruff"*
was true while *"the tree passes ruff"* had been unmeasured for a day-plus. Not strictly false
green — false **belief in green** — and it travels with the class because the operator
experience is identical: a red tree under an assumed-green DoD.

**Why specimen #5 survived a day of real batteries (and why the class is CRITICAL): a lying
gate survives exactly as long as it is never the last line of defense.** Every earlier failed
battery in the window was caught by LATER stages — smoke, assurance, overfit — whose engines
broke on the same bugs the tests would have caught. Redundancy masked the dead gate; the death
became visible only the first time the lying stage was the **sole** detector of a failure (a
load-marginal flake red in pytest, everything downstream green). Corollary: **stage redundancy
is not evidence that each stage works** — each arm must be proven to bite independently
(design rule 3), because the day one arm is the only one that can see the defect is the day
you find out whether it ever could.

**Implementation gotcha, filed so it is not re-suffered:** inline
`cmd /c "start /b /wait ..."` **DEADLOCKS under captured pipes** (reproduced 3x as 60s
`TimeoutExpired` while building the pin tests) — the construct must run from a **real `.bat`
file**. Windows batch semantics under harness capture are their own hazard plane; the pin
tests run the constructs from generated .bat files for exactly this reason.

## Design rules

1. **Missing tool = hard fail, never skip.** A skip is acceptable only for a *reasoned,
   written* exemption (the append gate's allowlist pattern); "the tool isn't here" is an
   environment defect, and an environment defect must stop the line, not wave it through.
2. **Output must be read; exit codes are not evidence.** Any wrapper that can exit 0 without
   emitting per-stage results is capable of false green by construction. The evidence is the
   stage output — counts, durations, the ratchet number — not the shell's integer.
3. **Prove the gate bites — including the runner of gates.**
   [[concepts/adoption-is-not-enforcement]] design rule 5 ("a gate never shown to fail is a
   gate whose passing means nothing") applies one level up: the *battery script itself* must be
   shown to go red when a stage cannot run. The 08-07 hard-fail change is that proof shipped.
4. **A DoD claim is only as true as its last full-scope run on the current tree.** Records
   from another environment (the cloud session's `pyright 0`) certify that environment, not
   this one — see the drift rows in [[synthesis/documentation-drift-register]].
5. **A verification is only as good as the graph it can see** (2026-08-07 night). Before
   trusting a "no consumers" claim, name the graph the check traversed — our sources? declared
   metadata? the actual runtime? — and prefer the check that exercises the runtime itself
   (boot it) over any static proxy. Vendor SDKs hide requirements; the box does not.
6. **Prove the failure arm, not just the pass arm — two-sided, live** (2026-08-08). A gate's
   conditional must be shown to fire on a genuinely failing child AND to pass a genuinely
   succeeding one, in the real invocation environment (specimen #5's `\|\|` form passed every
   inspection that only ever saw green children). Where the language has a
   documented-treacherous form (`start /wait` + `\|\|`), ban the form with a fence test, not a
   review convention.

## Aftermath of specimen #5 — what an honest gate costs (2026-08-08 afternoon)

The repaired gate immediately started charging for what the dead gate had been absorbing: the
`f07d60f8` ship cycle's three battery runs went **red · clean · red**, each red on **one
rotating load-marginal timing test** (`test_pbo_variants` schema-AB, then
`test_concurrency_throttle` burst), each **solo-verified green on the same tree**
([[sources/session-20260808-budget-reanchor]] §5). Before `050421a7`, some of these reds
would have sailed to ALL GREEN unseen. **The binding constraint moved from a lying gate to
load-sensitive tests** — which is the repair working, not a regression. Dispositions held:
disclosure over retry (the `48a63610` precedent — ship with the flake named), no blanket
retries ([[concepts/never-widen-a-gate]]), and the structural fix registered as
[[synthesis/owed-measurements]] item 44 (parallel `-m "not timing"` pass + gated SERIAL
`-m timing` pass, both arms held to this page's design rules).

**Item 44 shipped the same day (`be341867`,
[[sources/session-20260808-battery-split-freeze-gate]] §1)** — and it extends this page's
mechanics rather than relaxing them: the battery now has **two pytest arms, each behind its
own honest `if errorlevel 1` gate**, the 17-test timing family runs serial by **named
mechanism**, the `timing` marker is **strict-registered** (a typo is a collection error —
the silent-rejoin hole closed at the collector, not by convention), and
`test_battery_gate.py` (now 5) pins the two-pass structure alongside the construct ban.
First split battery green zero-flake (3445/1 parallel + 17/17 serial). The honest gate's
cost problem was solved by **scheduling, not tolerance** — no retry, no widening, both
arms still proven to bite.

## The mirror image — a RED explained away by a claim that was never run (2026-08-09)

This page is about greens that do not entail the work. Its mirror arrived on 2026-08-09 and
belongs here because the mechanism is identical: **a claim about a gate, believed without
the measurement that would have supported it.**

`36fcfd6e`'s commit message asserted **"the identical red reproduces on the parent
commit"** — the standard orthogonality disclosure. **It was ASSERTED, NEVER RUN.**

**Had it been run, the +9,272-row jump in the loaded corpus would have been unmissable**,
and the `label_era` corpus corruption would have been caught the same evening. Instead the
red was filed as honest cold-start growth, a **false root cause reached the wiki**, and the
corruption ran for another day — during which it deployed a champion that is now wedged
([[sources/session-20260809-corpus-corruption]] §14, [[concepts/ghost-badge]]).

**The half that was true is what made the whole believable.** The diff really did touch zero
ML paths — *diff* orthogonality was proven. But **orthogonality of the diff was never
evidence about the corpus**, and the two were conflated under one word. A partially-verified
disclosure reads exactly like a fully-verified one.

**The precedent is tightened (extending the `f07d60f8` disclosure rule, which covered
KNOWN, CHARACTERIZED flakes and was never a license to ship past a novel red):**

> **Design rule 7 — a battery stage turning red FOR THE FIRST TIME is a blocking
> investigation, not a disclosable footnote.** The disclosure precedent applies to a
> recurring flake with a named mechanism. A stage that has never been red before is an
> unnamed mechanism, and [[concepts/iron-law-of-debugging]] already forbids acting before
> the mechanism is named.

> **Design rule 8 — any "orthogonal" / "reproduces on parent" claim must ship with the
> command that produced it.** An orthogonality claim is a **measurement**; without its
> command it is a **hope**. This is design rule 2 ("output must be read — exit codes are not
> evidence") applied to prose: **a claim in a commit message is not evidence either.**

The sharpest detail is that the corrupted state was **loudly self-reporting the whole
time** — the battery printed `live rows=467` for a corpus holding **305 live rows total**
that is **append-only**, an arithmetically impossible number. It went unread for a day
because two stale strings labelled total loaded rows as "live rows" (fixed at source in
`3c0debd7`, filed to [[synthesis/documentation-drift-register]]). **An instrument that
prints the wrong noun for its own quantity will eventually be believed** — and it will be
believed hardest by the person who already has an explanation.

## The POSITIVE instance — a gate that refused, correctly, and healed the system (2026-08-09)

Every entry above is a gate that failed to be evidence. **This one is the counterweight, and
it is filed here deliberately** — a page that only collects failures teaches distrust of
gates rather than the ability to tell a real one from a fake one.

**The situation.** A bug-promoted `gbt` champion was **wedged** in place by a badge (0.1537)
measured on a corrupted corpus; no clean-corpus challenger could beat it
([[concepts/ghost-badge]], [[concepts/deploy-deadlock]]). The recommendation on the table was
to **retire the baseline as bug-attributable and re-baseline**. The gate was **deliberately
not overridden** — CLAUDE.md forbids bypass, and re-baselining is a conscious act.

**What happened instead.** At **02:56:04** the codebase's **own already-adjudicated ML-083
doctrine** fired: the champion's watermark (**9,708**) exceeded the repaired training matrix
(**701**), the badge was declared **unfalsifiable**, set aside entirely
(`ignore_champion=True`), and `logistic` cleared the true cold-start bar at **0.24728 <
0.25** and deployed. Under the normal branch it would have been **REJECTED**
(`0.24728 < 0.1537 − 0.005` is FALSE) — so the ML-083 path is *provably* what deployed, not
an inference from the outcome ([[sources/session-20260809-gate-policy-and-self-heal]] §1).

**Why this belongs on THIS page, in three parts:**

1. **The green was real, and provably so.** The distinguishing property this page keeps
   demanding — *green is impossible without the gated work actually running* — held: the
   deploy record names its own branch (ML-083), carries the inputs that selected it
   (`trained_rows`, `corpus_rows`, `challenger_brier`, `n_oof`), and the arithmetic of the
   alternative branch can be checked independently. **A gate that logs the predicate it
   took, with its operands, cannot be a false green.** That is a design rule this corpus
   arrived at by five failures and one success.

2. **The restraint was the measurement.** Overriding the gate would have produced the
   **identical visible outcome** — a `logistic` deployed on 701 clean rows — while
   **destroying the information that the system could reach it alone**. The override was the
   false green available for the taking: a green that would not have entailed the work,
   authored by us. **Not acting was what made the result evidence.**

3. **The fix was upstream, exactly as the class predicts.** The corpus repair (`3c0debd7`)
   was the **necessary and sufficient** intervention; **the model layer healed itself once
   the data was true.** Every gate downstream had been behaving correctly on a corrupted
   input all along — which is the same observation [[concepts/migration-idempotence]] makes
   from the data side, arriving at it from the gate side.

> **Design rule 9 — a gate's refusal to compare is not a failure to be routed around; it is
> the gate working.** Before overriding a gate that is refusing, ask what would have to be
> true for its refusal to be correct, and fix *that*. The five specimens above are gates that
> said yes without evidence; this is a gate that said *"I cannot answer"* and was right —
> and the corpus's oldest rule, [[concepts/iron-law-of-debugging]], is what turns that into
> an instruction: **name the mechanism before choosing the fix, and the fix is frequently not
> at the gate.**

**The honest bound, so this is not over-credited.** ML-083 detects orphaning by a
**row-count proxy** and fired only because the corrupted corpus was **larger** than the
clean one. A corrupt population that happened to be **smaller** would have compared
"successfully" against incommensurable rows and passed unremarked — which is a **latent
false green of exactly the type this page catalogues**, still open. The missing field is
provenance on the stored watermark ([[synthesis/owed-measurements]] item 47's residue).

## The sixth way (2026-08-09): ~3,400 green tests over a world that does not exist

Commit `1fee174e` ([[sources/session-20260809-adversarial-audits]] §1). `risk/position_sizer.py`
read `getattr(state, "positions", {})` at three sites; **`PortfolioState` has no `positions`
attribute**, so the default was taken **unconditionally, for the life of the module**. Three risk
controls were inert, all failing permissive, and tickets ran **13.7% larger than designed** —
while **~3,400 tests passed.**

> **This specimen is at the boundary of the class and is worth stating precisely.** The other
> five are greens produced **without the work running**. Here **the work ran, correctly** — against
> a `_State` fixture that supplied the missing attribute. **The gate was honest; the world was
> fabricated.** Filed as its own class, [[concepts/test-double-fidelity]], and adopted as
> [[synthesis/governance-doctrine]] rule 15.

The sharpest detail belongs here rather than there: the test that hid it,
`test_open_heat_reads_position_size_not_units`, **exists to catch this exact failure class** —
its docstring says so — and it **guarded a nonexistent field on `Position` while depending on a
nonexistent attribute on `state`.** A green whose *name* asserts coverage of the bug it is hiding
is the most persuasive false green this repo has produced.

**Design rule 10 follows:**

> **A test's docstring states its author's fear, not its scope.** Before crediting a test with
> covering a class, read its **fixtures**. Ask *"does any object in this test exist outside this
> test?"*

**And a third instance of the AST-over-grep discriminator:** the pin shipped with the fix
**PARSES rather than greps**, because a substring check matched **the module's own prose
describing the bug** and failed on its first run. The rule is now three-for-three in this repo —
**where a check reasons about code, parse it; a text scan is defeated by the code's own
documentation** ([[concepts/iron-law-of-debugging]]).

## The SEVENTH way (2026-08-09): a pipeline's exit code belongs to its LAST command

The lying-gate class **recurred**, and it recurred in the same form the corpus had already named
as owed **44** ([[sources/session-20260809-turing-test-hedge-verdict]] §8.1):

**The battery was reported as passing, on an exit code that belonged to `tail`.** In a shell
pipeline, the status observed is the *last* command's — so the battery's real result never reached
the assertion at all. Design rule 2 (*exit codes are not evidence*) had been filed for a day and
the class still landed.

> **What makes this the seventh way rather than a repeat of the third:** specimen #3 was a gate
> that *could never fire* (`start /b /wait cmd ||` satisfied by launch success). This one is a gate
> that fires correctly and whose **verdict is read off the wrong process**. The mechanics are
> sound; the **reader** is pointed at the wrong object. That distinction matters because no change
> to the battery would have prevented it.

### And the recovery move was worse than the error — a new adjacent class

On catching the `tail` mistake, the agent's first move was to cite **a green battery run from
BEFORE the change**. A pre-change green measures **a tree that no longer exists**; the change under
test is precisely the difference between that tree and this one.

This recovery move is now filed as its own class: **[[concepts/retroactive-excuse]]**. It is more
dangerous than the bare false green, because the bare error stays open until the next run while the
excuse **closes the question with an answer that was never about the current tree**.

**Design rule 11 follows:** *a caught false-green obliges a **RE-RUN**, never a citation. Prior
greens are CONTEXT, never CLEARANCE, and a green whose commit is not named is not evidence.*

**Positive counterweight the same day:** `test_every_query_hits_an_emitted_metric` **fired
correctly** on the `_SYNTH_STATUS` schema drift (owed **59**) — a gate that could fire and did. The
family is not "all gates lie"; it is *"a gate's authority is exactly as good as its mechanics, and
the mechanics must be checked."*

### The seventh way recurred — owed 44's SECOND occurrence in one night (2026-08-10, Grand Synthesis session)

The reader-pointed-at-the-wrong-process class fired again: **battery 14 was reported as exit 0
by reading the TASK wrapper's exit instead of `BATCH_EXIT`** — the wrapper reports its own
launch/completion status; the battery's verdict lives only in the `BATCH_EXIT` marker. Same
shape as the `tail` specimen (mechanics sound, reader wrong), **second occurrence that night**,
**self-caught and corrected in-session** ([[synthesis/grand-synthesis-algorithm-package]]
§delivery — filed per governance rule 16, the disposition gets the adversarial pass too).
The correction followed design rule 11's letter: **a re-run/direct re-read, never a citation**
— battery 14's true state was read off `BATCH_EXIT` (it was **RED**), and battery 15's ALL
GREEN was verified on `BATCH_EXIT=0` **directly**; both markers are now checked. A class that
recurs twice in one night on a reader who had filed the rule the first time is the strongest
evidence yet that the fix for this family is **mechanical marker-checking, not vigilance**.

**And the RED it had papered over was the family's best positive instance to date:** battery
14's red was the **conftest production-outputs tripwire firing on the owed-65 QA row in
`outputs/trade_paths.csv` — the tripwire's FIRST confirmed catch** since the
outputs-contamination class got a gate. A gate that could fire, did, on exactly the class it
was built for, over a file the next algorithm would have parameterized from
([[concepts/default-path-fallback-writes]] ninth instance). The night's full shape is the
family in miniature: **a true RED from a working gate, briefly hidden by a lying reader, then
recovered by reading the right marker** — the gate never lied; the reader did, and the fix was
mechanical.

### The class gets its name — EVIDENCE TRUNCATION, in both polarities (cut #7, 2026-08-11)

Battery 16 supplied the family's inverse specimen, and with it the class's proper name
([[sources/session-20260811-cut7-geometry-epoch]] §4). The new ALGO-6 pin asserted **`<=4`
occurrences of `tb_time`** — a threshold derived from a **head-truncated grep**; `main.py`
legitimately says `tb_time` **six** times, so **battery 16 went RED on a correct tree**. The
fix: count **the submit call exactly** (the property, not a corpus-wide string tally), with the
test's docstring recording its own first version's mistake.

Set beside the wrapper-exit specimens, the shape resolves: **the common defect is a conclusion
drawn from a truncated evidence stream**, and it runs in both polarities — battery 14's
truncated read (wrapper exit for `BATCH_EXIT`) **hid** a red; battery 16's (head-cut grep)
**manufactured** one. A false RED is cheaper than a false green — it stops the line instead of
waving defects through — but it spends credibility the next real red will need, and it is the
same class, caught by the same discipline. The fix is identical and mechanical: **exact reads
of the full evidence** — count the call site, check the marker, never `head`/`tail` an
evidence stream you are about to pin or report. (Sibling of the drift register's INVERTED row
— a test red on correct code — with the cause now identified: truncation at authoring time.)

- [[concepts/retroactive-excuse]] is the reader-side sibling of this whole family: every other
  entry is a defect **in a gate**; that one is a defect in **the reasoning of whoever reads the
  gate**, and it is therefore unfixable by any schema pin or hard-fail.
- [[concepts/test-double-fidelity]] is the sixth-way sibling: the gate runs and reports
  honestly about **an object production never supplies**. Distinguishing question — false green
  asks *"could this have gone green without the work running?"*; that page asks *"does anything
  in this test exist outside the test?"*
- [[concepts/adoption-is-not-enforcement]] is the parent: an invariant held by convention
  rather than by a gate. False green is the sharper sequel — **the gate exists, and its
  reporting channel is the thing that defected.** That page's own recursion section ("a gate
  is itself adopted") predicted exactly this: the pyright stage was adopted into the bat and
  nothing enforced that it could run.
- [[concepts/zero-is-not-a-reading]] is the same shape in data: a sentinel ("SKIPPED", exit 0,
  rho = 0.0) landing inside the domain of the comparison, indistinguishable from a
  measurement. Here the sentinel landed on the *pass* side of a gate.
- [[concepts/never-widen-a-gate]] governs gates that fire; this page governs gates that
  *cannot* fire. Both exist because a gate's authority is exactly as good as its mechanics.

## Related
[[sources/session-20260808-morning-batch]] ·
[[sources/session-20260808-budget-reanchor]] ·
[[sources/session-20260808-battery-split-freeze-gate]] ·
[[sources/session-20260807-capacity-sweep]] · [[sources/session-20260806-hedge-thrash]] ·
[[sources/session-20260807-closing-batch]] ·
[[sources/session-20260807-hedge-churn-guards]] · [[concepts/adoption-is-not-enforcement]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/never-widen-a-gate]] ·
[[synthesis/documentation-drift-register]] · [[synthesis/owed-measurements]] ·
[[sources/session-20260809-corpus-corruption]] · [[concepts/iron-law-of-debugging]] ·
[[concepts/ghost-badge]] · [[concepts/migration-idempotence]] ·
[[sources/session-20260809-gate-policy-and-self-heal]] · [[concepts/deploy-deadlock]] ·
[[entities/ml-governor]] · [[concepts/unfalsifiable-explanation]] ·
[[concepts/retroactive-excuse]] · [[concepts/test-double-fidelity]] ·
[[sources/session-20260809-turing-test-hedge-verdict]] ·
[[sources/session-20260811-cut7-geometry-epoch]]

## The narrative twin (2026-08-09)
This page governs **instruments**: a green that does not entail the work ran. Its mirror
specimen — `36fcfd6e`'s *"the identical red reproduces on the parent commit"*, **asserted, never
run** — sits at the boundary between the two classes, because a claim in the grammar of a
measurement is a **false green produced by prose rather than by a gate**.

The class one level up is now filed separately as
**[[concepts/unfalsifiable-explanation]]** — *an explanation that cannot be wrong is not an
explanation*. Where this page asks *"could this green have happened without the work?"*, that one
asks *"could this account have been contradicted by any observation?"* Same question, applied to
narratives instead of gates; design rules 7 and 8 here are its instrument-side form.
([[sources/session-20260809-unbiased-economics]] §2)

## The EIGHTH way (2026-08-14) — there was no green, there was nothing

Every specimen above is a green that did not entail the work. This one is the limiting case:
**the battery did not run at all, and the failure did not present as a test result.**

A globally-installed SuperClaude pytest plugin **applies** four marks during collection
(`unit`, `integration`, `hallucination`, `performance`) while registering only its own,
different set. Under this repo's deliberate `--strict-markers`, that mismatch is not a warning
and not one red test — pytest raises `INTERNALERROR` mid-collection and prints:

```
Failed: 'performance' not found in `markers` configuration option
no tests ran in 4.28s
```

**"no tests ran" is not a failure count.** It is an absence, and it appears where a reader
expects a summary line. Any session on this box running the definition-of-done matrix was
verifying nothing — while the matrix's own instruction says a change is not done while
anything is red, and nothing was red.

Note what is *new* here. Specimen #1 (a stage printing SKIPPED for weeks) is the closest
relative, but that stage announced itself. Specimen #3 (a banner and exit 0) is closer still —
yet it produced an exit code a reader could in principle check. This one produces a **non-zero
exit and a loud traceback**, and still slipped, because the traceback is a *plugin* stack trace
that reads like an environment complaint rather than a gate failure. **Design rule 12: a
battery's output must be checked for the presence of a result, not only for the absence of a
failure.** Absence of red is not presence of green, and "no tests ran" is the shape that
distinction takes.

The fix is the page's own doctrine applied to itself: **declare** the four marks in
`pyproject.toml` rather than disable the plugin. `-p no:superclaude` would hide the guest
instead of housing it, and would thereafter depend on every human, lane and future session
remembering the flag — *a fix that survives only by being remembered is a debt wearing a
friendly face*, which is the same failure mode [[concepts/adoption-is-not-enforcement]]
governs. Loosening `--strict-markers` was refused for the reason its own comment records: a
typo'd `timing` tag silently returns a load-marginal test to the parallel pass, and a gate hole
that fails silently is the only kind that matters.

Verified in **both** configurations, because the fix's whole claim is that it changes nothing
except collection: **3656 passed / 1 skipped** with the plugin disabled, and the **identical
3656 / 1** with it enabled. — [[sources/session-20260814-cohort-instruments]] Finding 4

## THREE MORE TESTS THAT CANNOT FAIL (2026-08-15, found by class scan)

A fan-out hunting recurrences of this exact class found three, all confirmed by an adversarial
kill pass. The page's rule was already known; these are instances that survived it.

- **`tests/test_no_console_popups.py:81` — the pin matches its own comment banner.** It reads
  `scripts/close_prompts.ps1` as RAW TEXT, and that file's 21-line `#` banner supplies the FIRST
  match of every pinned token: `CloseMainWindow` @397 (line 8), `Stop-Process` @1075 (line 17),
  `MainWindowTitle` @978, `prompt_sweep.log` @186. So
  `ps1.index("CloseMainWindow") < ps1.index("Stop-Process")` compares **two comment offsets** and
  never observes the body (code offsets 1538 / 2083). **Deleting `close_prompts.ps1:61-65` and
  the line-52 `MainWindowTitle` discriminator leaves the test GREEN.**
- **`tests/test_append_invariant.py:163` — a substring where an AST check is claimed.**
  `assert "durable_append" in src` is a whole-file token test whose own docstring says "deleting
  the call is caught". `scripts/corpus_sync.py` carries the token twice — a function-local import
  at :149 and the only real `Call` at :185 — and is in the `ALLOWED` list, so the negative AST
  gate skips it. **Replacing :185 with a bare `open(dest,"a")` while leaving the import restores
  the SD-007 second-appender seam with all three gates green.**
- **`tests/test_battery_gate.py:100` — "class-wide" over a non-recursive glob.** The docstring
  claims the `start /wait` + `||` ban is class-wide, but the loop is
  `_BAT.parent.glob("*.bat")` — repo root only. **4 of 9 `.bat` files are never opened**,
  including the live scheduled `scripts/run_checkin.bat`, so adding the 2026-08-08 incident's
  exact pattern there reproduces it with the gate green.

> **The uncomfortable pairing, recorded per rule 16.** The session that found these had, hours
> earlier, written source-level pins of its own that failed **the same way** — asserting a
> forbidden string was absent while matching it inside the comment that documented why it was
> forbidden. Fixed there with a `_code_only()` comment-stripping helper. **Knowing a class by
> name does not confer immunity**; the specimen and its rediscovery arrived on the same day, in
> the same session, in both directions.
> — [[sources/session-20260815-scans-and-corrections]] §3

## The NINTH way (2026-08-16): silence from a watcher that died with its host

The eighth way was *there was no green, there was nothing*. The ninth is its
**asynchronous** form, and it does not even produce a missing line — it produces
**a quiet inbox**.

A VS Code Claude session that survived four calendar days and several
host-process restarts kept **waiting on notifications from background monitors
that had exited (status 4) with the host process**. Nothing announced their
death. The session read *no alarm* as *nothing to report*, which is the same
inference as reading a green as evidence — one level further removed, because
there is no artifact to misread at all.

Two artifacts show the shape:

- **The monitors.** Every background task launched before the gap was dead; the
  session's plan still had them reporting.
- **The wedged workflow.** A user interrupt killed four investigator subagents,
  and the only durable trace is the run's own journal —
  `wf_dd79a1a4-724/journal.jsonl`: **12 lines, 8 `started`, 4 `result`**. Four
  agents have a `started` line and **no** `result`. **The absence of a result
  line IS the record**; nothing else in the system reports it.
  ([[sources/session-20260811-16-vscode-3b307393]] §1)

**Design rule 12 follows:** *a channel is evidence only if the sender is proven
alive at read time.* Waiting is not observing. Check the **journal, the exit
status, the process** — never the inbox — and treat every pre-gap watcher as
dead until re-observed. This is [[concepts/zero-is-not-a-reading]] applied to
notifications, and it is why the wake protocol on
[[concepts/session-identity-is-not-stable]] re-derives vitals rather than asking
what the session last heard.

*(Related but distinct: [[concepts/liveness-by-output-cadence]] is a supervisor drawing the
WRONG conclusion from silence. Here nothing draws a conclusion at all — the
watcher is gone and no supervisor exists.)*

### The ninth way's OWN inverse, measured the same day: "no output" vs "no output YET"

**Design rule 12 was applied correctly and produced a false statement anyway** —
within hours of being written, on the session that wrote it.

This page's founding discriminator is that **"0 findings" and "the scan is
broken" are the same observation until separated**. The ninth way added a second
polarity: **"no alarm" vs "no watcher"**. The correction pass supplies the
**third, and it is the one the rule itself invites**:

> **"no output" vs "no output *YET*".**

The catch-up ingest launched two background verification agents. It observed **no
notification** and **0-byte output files** — the exact signature design rule 12
names — and correctly followed the rule: treat them as dead, do not wait, and
**re-derive independently**. It then did something the rule does *not* authorize:
it **wrote the death into the filing as a finding**.

**Both agents were alive.** They returned roughly **six minutes after** the
ingest concluded they were dead, having done real work against live artifacts
(agent A: 18 static repo items, 62 tool uses; agent B: 31 tool uses running
`cohort_eval.py` in the repo `.venv`, 2026-08-16T20:43:15Z–20:48:54Z).

**Three things make this worth a section rather than a footnote:**

1. **The action was right and the record was wrong.** Presuming death and
   re-deriving is exactly correct under rule 12. The defect is entirely at the
   **reporting** step — an *operating presumption* was promoted to a *measured
   cause*. A rule that licenses acting on an inference does not license filing it.
2. **The error was invisible in the output.** Independent re-derivation reached
   **the same numbers the late agents did**, so nothing downstream was wrong.
   Only the attribution was false — the failure mode this vault is worst at
   catching, because there is no red anywhere to pull on.
3. **A cheap discriminator existed and was not used.** The ninth way already
   names it: **the workflow journal**. A `started` line with no `result` line is
   "still running"; a nonzero exit status is "dead". Nobody looked. The rule
   supplied the remedy and the remedy was skipped in favour of the presumption
   the rule had already granted.

> **Design rule 14:** *a presumption granted for ACTION may never be filed as a
> FINDING.* "Assume it is dead" is an operating instruction; "it died" is a
> claim, and a claim needs the journal, the exit status, or the PID. Absent
> those, the vault writes **"unreturned after N minutes"** — the observation —
> and never the cause. Symmetrical with design rules 2 and 11: *output must be
> read*, and *a caught false-green obliges a re-run, never a citation*.

Filed as failure mode 6 on [[concepts/session-identity-is-not-stable]], beside
mode 2 which it mirrors. Both polarities of the silence problem are now on
record: **mode 2** — treating silence as *nothing to report* when the watcher is
dead; **mode 6** — treating silence as *proof of death* when the watcher is merely
slow. Same observation, opposite errors, and the honest reading of silence is
that **it is not a reading at all** ([[concepts/zero-is-not-a-reading]]).

## The SIBLING CLASS, filed at last (2026-08-16): a confident verdict about a population that no longer exists

*(This generalization was promised to this page by the `bb7c193b` filing on
2026-08-15 — log entry §1, "Generalization for `concepts/false-green`" — and
**never applied**. The log carried it; the concept page did not. Closed here by the
08-12..16 catch-up, [[sources/session-20260816-catchup-08-12-to-08-16]]. **A
generalization recorded only in a log entry is not filed** — the log is
chronological and the concept page is where a future reader looks.)*

Every other way on this page is a green **that measured nothing**. This one is
worse in the way that matters: **the work ran, the measurement was real, and it was
taken over the wrong population.**

`scripts/gate_truth_report.py` filtered `label_era == "triple_barrier"` — the
**RETIRED** unqualified 96-bar era — while `ml.label_max_bars` has been **432**
since the horizon migration (`7566ea88`; `config.json` carries 432). Measured:

| what it read | what it should have read |
|---|---|
| **5,328 retired rows** (4,228 instrumented) | **0** of them |
| **zero** deployed `h432` rows | all 359 of them |

It then printed a confident **XV-040 ALIGNED**. It was not failing visibly; it was
**answering about a label geometry the bot had stopped using.** Corrected verdict
after the fix: **XV-042 THIN — 56.1 effective observations (< 100), no verdict
yet.** The honest reading was *"I cannot tell you"*, and the instrument had been
saying *"aligned"*.

**The tests pinned the defect rather than catching it.** All **8** fixtures
hardcoded `label_era: "triple_barrier"` while passing the real `config.json` (432).
They passed **only because the report hardcoded the same literal**. This is the
page's design rule 10 in its purest form:

> **Two hardcoded copies agreeing is not a test.** A fixture that repeats the
> production constant tests that the constant equals itself.

The same defect existed in `main.py` (a report-only field), so it was a **class**,
not an instance.

**The distinguishing property is identical to every other way on this page: the
instrument never named its corpus.** That is why the fix was not only the filter
but **printing the era on the report's face** — the same remedy the overfit battery
needed when it turned out to be running SYNTHETIC
([[concepts/overfit-battery]] §the battery is CURRENTLY on the synthetic
benchmark), and the same standard [[concepts/pooled-populations]] demands.

> **Design rule 13:** *a verdict is evidence only if the instrument states the
> population it read.* An unnamed corpus makes ALIGNED and CANNOT-TELL
> indistinguishable — and the pleasant one is the one that gets quoted.

*(Filed alongside: the first regression pin written for this fix was **itself**
tautological — `assert retired not in text` can never fail, because
`"triple_barrier_h432"` **contains** `"triple_barrier"` — committed by the author
**while fixing that exact defect class**. It was proven non-vacuous only after
mutation (revert → RED). See [[concepts/tautological-instrument]] §fourth specimen
class and [[concepts/adversarial-verification]]: the tautological-pin trap is not a
lapse of care, it is the DEFAULT outcome of asserting about a **name** instead of a
**behaviour**.)*

---

**New family member, 2026-08-27: the host-state-dependent green** — the same suite
read **4060/0/9 on the live repo** and **2 failed / 4085 passed / 1 error on a fresh
worktree**, same day, because the running bot's host state (real audit history, a
pre-existing stamp file) supplied what two fixtures forgot to stub. A live-repo
green is design rule 13's failure at the machine level: the instrument never named
its corpus — the corpus was the *host*, and the pleasant reading is the one that
got quoted. Full class page: [[concepts/host-state-dependent-green]]
([[sources/session-20260827-sdd-verification-and-era-confound]] §3).

## The inverted variant — a gate whose evidence of health is a FAILURE (2026-09-15)

Every specimen above shares a polarity: the broken machinery produces a **PASS**, and the repair
is to make a pass impossible without the work. **A mutation sweep inverts the success
criterion.** Its evidence of health is that the mutant *died* — so a harness that cannot run at
all produces **"100% of mutants caught"**, the most flattering answer the instrument can emit,
through the same channel a genuine 100% uses.

**The specimen** ([[sources/session-20260915-master-survey-and-double-exit]] §12): a watch-lane
mutation sweep reported `4/4 caught`, each mutant dying in **~0.3 s**. Nothing had run. The
harness passed `--basetemp=/c/lbt/ms` — a **Git-Bash path Python resolves as `C:\c\lbt\ms`**,
which does not exist — so the session fixture raised at setup and each mutant "died" before a
test was collected. Two tells, both in the output that *was* read: a runtime implausible for the
corpus (0.3 s for 29 tests — design rule 2's own sibling, and the same implausible-runtime
discriminator CLAUDE.md's reading-discipline item (d) names), and the word **`error`** where a
killed mutant produces **`failed`**.

**Why design rule 2 is necessary and not sufficient here.** "Output must be read — exit codes
are not evidence" was satisfied: the output was read and it said `1 error`, which is what a
caught mutant looks like to a careless reader. Reading harder is not a mechanism.

> **Design rule 15. A mutation sweep must run the UNMUTATED CONTROL first and assert it green
> before reporting any mutant result, and must distinguish `error` from `failed`.** The control
> row is the only thing that separates "every mutant died" from "the harness never ran" — the
> same separator [[concepts/the-method]] states for scans ("'0 findings' and 'the scan is broken'
> are the SAME OBSERVATION until separated"), reached from the opposite polarity.

**It paid for itself on first use.** The corrected sweep — control asserted green — is the run
that found `NON_ATOMIC_SAVE` **surviving**: the watch lane's atomicity pin asserted only "no
`*.tmp` is left" and "the result parses", both satisfied by a plain `open(p, "w")`. The
false-green harness had been reporting that decorative pin as a kill. So this variant does not
merely hide a red; **it launders a weak test as a strong one**, which is the vacuous-test
variant above being manufactured by the very instrument built to detect it.

**Sweep hygiene, the same session's second lesson.** A mutation sweep that plants a
**production-path** defect does not simulate the bad write — it **performs** it. The repo's
conftest audit-hook tripwire caught the offending test and named it correctly, and **did not,
and cannot, undo the write**: `outputs/watch_history_state.json` (27 KB, fabricated bars on the
test file's own `NOW` epoch) survived two sweeps sitting in the operator's tree, and the next
relaunch would have restored it as a live pending pool. A tripwire is a detector, not a
janitor.

> **Design rule 16. A sweep that plants a production-path mutant must delete its own artifact,
> and the operator's tree must be re-checked after any sweep — a green tripwire report means the
> write was CAUGHT, never that it was UNDONE.**

That artifact is also what produced the session's best fix: an age gate on the restore path,
because finding the file forced the question "what happens when this gets read back?"
([[sources/session-20260915-master-survey-and-double-exit]] §14).
