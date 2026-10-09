---
title: "The Capacity Sweep, Round 1 (2026-08-07) — Two Definition-of-Done Gates Were Lying About Themselves"
category: source
summary: "Commits 00bd0e52 + 101f7436. The throughput/hygiene half of the capacity sweep, with a gate-integrity headline: (1) full-scope ruff was RED on the live tree — cf454d5e's hedger snapshot section grew core/persistence.py restore() past C901 (42>40) and nobody ran full-scope ruff after the pull; (2) the battery's pyright type-ratchet stage had printed 'SKIPPED' for weeks because the tool was never installed, while CLAUDE.md claimed a zero-error ratchet — the bat now HARD-FAILS on a missing tool (a gate that can quietly not exist is a gate that lies); pyright 1.1.411 now in-venv, 0 errors on shipped scope. Matrix hardening measured on the 5600X: pytest-xdist -n 8 institutionalized (623s->~400s, two clean runs; the one flake was a load-starved 5s harness timeout hardened to 30s); the battery now runs BelowNormal (profit-protection — a Normal-priority battery outcompeted the BelowNormal LIVE trading loop on all 12 threads); compileall -j 0 (9.32s->1.71s cold). Full hardened matrix ALL GREEN end-to-end. Four items deferred to owed-measurements item 38; the sweep's coverage half is unstarted. Plus the false-green lesson: a Git Bash cmd /c invocation of test_windows.bat printed a banner and exited 0 without running any stage — output must be read, exit codes are not evidence."
tags: [session, gates, dod, tooling, battery, performance, false-green, enforcement]
sources: 1
source_path: none — session work product (capacity-sweep round 1)
source_date: 2026-08
authors: [claude]
ingested: 2026-08-07
updated: 2026-08-07
---

# The Capacity Sweep, Round 1 (2026-08-07)

## Provenance and boundary statement

Commits **`00bd0e52` + `101f7436`**, 2026-08-07 — round 1 of the capacity sweep (the
**throughput/hygiene half**; the **coverage half is unstarted**, owed item 38(c)). Hardware
context for every timing below: the **5600X production box, 12 threads** — the same machine
running the LIVE paper runner.

**Paper/real boundary** ([[concepts/paper-real-boundary]], domain rule 9): everything on this
page is **repo-side** — build tooling, test-battery mechanics, lint/type gates. **No
sim-conditioned or venue number appears here**, and nothing here moves the standing question's
four quantities (payoff asymmetry, the two nulls, the cost levers, the fill-regime boundary).
The one trading-relevant consequence is *negative space*: the battery is now forbidden from
starving the live loop (§3).

---

## 1. The headline: two Definition-of-Done gates were lying about themselves

The DoD (repo CLAUDE.md) lists ruff and a zero-error pyright ratchet among the gates every
commit must pass. The sweep found **both stages disagreeing with reality** — in two different
ways.

### 1a. ruff was RED on the live tree — an existing gate, not run

Full-scope ruff on the production tree failed **C901**: `core/persistence.py` `restore()` at
complexity **42 against the limit of 40**. The breach was introduced by **`cf454d5e`'s hedger
snapshot section** ([[sources/session-20260807-hedge-churn-guards]] §3 — the `hedger` block
added beside `monitor`), and it sat red because **nobody ran full-scope ruff after the pull**:
the commit was authored by the cloud session, deployed through the pytest deploy battery, and
the local lint stage was never exercised on the merged tree.

**Fix:** extract **`_restore_subsystem_sections`** from `restore()` — per the file's **own
existing convention** of per-section restore helpers, not a new pattern. Full-scope ruff green
again.

> A gate that exists is enforced only as often as it is **run on the current tree**. "The DoD
> includes ruff" was true; "the tree passes ruff" had been unmeasured since the pull. The DoD
> claim was riding on the cloud session's record — which this finding demotes (see
> [[synthesis/documentation-drift-register]]).

### 1b. The pyright ratchet had quietly not existed for weeks — a missing gate rendered as a pass

The battery's type-ratchet stage had printed **`SKIPPED`** on every run **for weeks**, because
**pyright was never installed on this box** — while CLAUDE.md claimed a **zero-error pyright
ratchet** as part of the DoD. Every local "battery green" in that window asserted a type gate
that **did not run**; the ratchet's zero was real only in cloud-session environments (e.g. the
`cf454d5e` record's `pyright 0`).

**Fix, in two parts:**
1. **`test_windows.bat` now HARD-FAILS when a stage's tool is missing.** A missing tool is a
   red battery, never a skip — *a gate that can quietly not exist is a gate that lies.*
2. **pyright `1.1.411` installed in-venv**; measured at **0 errors on shipped scope** — the
   ratchet claim is now true *on this box*, by measurement.

This is the same family as [[concepts/adoption-is-not-enforcement]] (the gate itself was
adopted, not enforced — its own recursion section predicted this) and the vacuous-test episode
(`af544d4c`, a test green on the buggy engine). The class now has its own page:
**[[concepts/false-green]]**.

## 2. The false-green invocation — exit codes are not evidence

During the sweep, a **Git Bash `cmd /c test_windows.bat` invocation printed a banner and
exited 0 without running any stage.** Read as an exit code, that was a full green battery; read
as output, it was **nothing at all**.

> **Output must be read. Exit codes are not evidence.** A wrapper that can exit 0 without
> printing per-stage results must be treated as *unmeasured*, not as passed. This is the
> invocation-layer twin of §1b — filed on [[concepts/false-green]] as the third way this repo
> has produced green without the work.

(Battery invocations on this box go through the native shell; the Git Bash `cmd /c` path is
not a supported invocation.)

## 3. Matrix hardening, measured on the 5600X

All three changes carry measurements; the matrix ran **ALL GREEN end-to-end** in its hardened
form.

| Change | Before | After | Note |
|---|---|---|---|
| **pytest-xdist `-n 8` institutionalized** | 623 s serial | **~400 s** | Two clean runs (first: 3423/1 in 413 s, logged 08-07 as pending its confirming run — now confirmed and institutionalized). The **one flake across both runs** was a **load-starved 5 s harness timeout**, hardened to **30 s** in `00bd0e52` — a timeout tuned for an idle box, not 8 concurrent workers; the test was innocent. |
| **Battery priority → BelowNormal** | Normal | **BelowNormal** | **Profit-protection, not speedup.** The LIVE runner runs BelowNormal; a Normal-priority battery **outcompeted the trading loop on all 12 threads during every verify cycle** — the deploy gate was starving the very process it protects. Rule: **renice the tests, never the bot.** |
| **`compileall -j 0`** | 9.32 s | **1.71 s** cold | Parallel bytecode compilation. |

The xdist item closes the log's 08-07 "in flight, unfiled by design" marker: the second
confirming run happened, and the parallel battery is now the institutional form, at a priority
that cannot contend with the live loop.

## 4. Deferred — four items, filed as owed item 38, none measured

Recorded here with their blockers; full closure terms on [[synthesis/owed-measurements]] §38:

- **(a) Windows Defender exclusion A/B** — needs admin elevation, and the tradeoff is real (an
  AV exclusion over the repo/venv is a **supply-chain exposure**); the owed thing is the
  *measurement*, the adoption decision prices the tradeoff.
- **(b) `runner.log` rotation** — **153.8 MB** and growing; the live process **holds an append
  handle**, so in-place rotation is unsafe; the rotation point is the **supervisor spawn
  boundary**.
- **(c) The coverage baseline** — pytest-cov over shipped scope has **never been measured**;
  the sweep's coverage half is unstarted.
- **(d) venv pruning** — the **retired streamlit/pandas UI stack** is still installed
  (**~150–250 MB**), **zero importers verified** in shipped scope.

## 5. What this session changes elsewhere in the wiki

- **NEW [[concepts/false-green]]** — the class: a green that does not entail the work ran
  (skipped-stage, vacuous test, exit-0-no-stages invocation; plus the adjacent unrun-gate case).
- **[[concepts/adoption-is-not-enforcement]]** — the recursion's sharpest instance yet: the
  gate itself quietly absent for weeks.
- **[[sources/session-20260807-hedge-churn-guards]]** — §6 addendum: the `cf454d5e` record's
  `ruff · pyright 0` line did not hold on the pulled tree.
- **[[synthesis/documentation-drift-register]]** — two rows: the CLAUDE.md ratchet claim; the
  cloud battery record vs the local tree.
- **[[synthesis/owed-measurements]]** — new item 38 (a–d).

## Related
[[concepts/false-green]] · [[concepts/adoption-is-not-enforcement]] ·
[[concepts/never-widen-a-gate]] · [[sources/session-20260807-hedge-churn-guards]] ·
[[synthesis/documentation-drift-register]] · [[synthesis/owed-measurements]] ·
[[concepts/paper-real-boundary]] · [[entities/auto-update]]
