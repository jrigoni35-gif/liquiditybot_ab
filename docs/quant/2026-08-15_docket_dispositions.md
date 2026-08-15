# Docket dispositions — commit f756676e

Companion to `2026-08-15_red_team_docket_f756676e.md`. That file is the
CHARGE; this one is the ANSWER. The panel's rule: *the docket is not
closed until every objection has a recorded disposition.*

Verification method: each objection re-checked against LIVE code by an
independent agent that was instructed to be adversarial toward the
objection AND toward the author. Nothing below is accepted on the
panel's say-so; where an agent contradicted the panel, the agent's
evidence is recorded and the objection is amended.

Status: 12 of 16 dispositioned. OBJ-4/7/8 and OBJ-13(a) pending.

---

## Settled

| # | Sev (panel) | Disposition | Basis |
|---|---|---|---|
| OBJ-1 | BLOCKING | **CONCEDE** | `overfit_check.py:1118` says "era exclusion left 346 loaded"; artifact reads 347, re-measured 352. A volatile number shipped into a permanent file by the same commit that evicted volatile numbers from CLAUDE.md. |
| OBJ-2 | BLOCKING | **CONCEDE** | 5 derivations of the predicate (`:704, 833, 1075, 1084, 1089`), not 1. The assert counts the *assignment spelling*, so its message "exactly ONE place may derive on_synthetic" is false and the test passes anyway. Claim C3 is false. |
| OBJ-9 | BLOCKING | **CONCEDE** | Same pin, second angle: it cannot fail on the duplication already present. |
| OBJ-14 | BLOCKING | **CONCEDE** | Mutation survives: swapping `if on_synthetic:` for the inline predicate leaves all three asserts green. C5 moved the count, not the property. |
| OBJ-11 | CRITICAL | **CONCEDE** | `gate_truth_report.py:194` filters `label_era == "triple_barrier"` — the RETIRED era — reading zero deployed `h432` rows. CLAUDE.md cites it as the exemplar of a standard it is not applying to current data. |
| OBJ-16 | CRITICAL | **CONCEDE** | `test_windows.bat:57` is exit-code only, so the corpus banner is invisible to the battery form CLAUDE.md itself mandates. |
| OBJ-12 | CRITICAL | **CONCEDE** | Headline prints `live history (N rows)` where N is LOADED. Re-derived census: candidate 10,331 : live 327 = **31.6:1**; today's live path would print 352 against `n_live=6` = **58.7:1**. Contest condition fails: `n_live` is unconditionally in scope at `:701`, and `live_clean` comes from the same load pass. |
| OBJ-5 | MINOR | **CONCEDE** | Same root cause as OBJ-12; fix at `:254` where the string is minted. **Objection amended**: its claim that any fix "requires editing the pin at `:176`" is overstated — the pin matches the print *expression*, so a `:254` fix leaves it green. |
| OBJ-15 | CRITICAL | **CONCEDE the denominator; REFUTE the rider** | `info()` moves neither PASS_N nor FAIL_N, so "7 passed, 0 failed" has no denominator. **Objection amended: the true ratio is 7 of 14, not 7 of 13** — it missed the `:955`/`:941` dof site. Two `monotone` slots vanish SILENTLY (the `continue` at `:309` skips both checks). OF-4 mis-attribution charge **REFUTED**: CLAUDE.md:132 already attributes inertness to "the replay recording opens no positions", exactly as the objection demands. |
| OBJ-10 | CRITICAL | **CONCEDE the rationale; CONTEST the remedy-reversal** | The stated failure mode is provably impossible: `reason` interpolates inside the parens, and 7 rewords leave both predicates True. No string breaks `in ...upper()` but not `startswith` — verified by EXHAUSTIVE scan of all 1,114,112 codepoints plus 200k random suffixes, zero counterexamples. **But the panel's remedy is refused**: the banned form fails OPEN on false positives (`'live history (348 rows, synthetic-fill era)'` → banned form True, retained form False), which would print "not evidence about the deployed strategy" over a REAL corpus — the banner's own failure class, inverted. Keep single-sourcing; keep the CI ban. Downgrade CRITICAL → MINOR: the code is correct, the prose is not. **Also**: the false claim is duplicated in a live docstring at `tests/test_preventive_maintenance.py:169-170`, so the fix must land there too. |
| OBJ-3 | SERIOUS | **CONCEDE at MINOR/MODERATE** | `:247` has three conjuncts, `:260-261` has one story; a class-balance trip prints the literally false `loaded rows=700 < 640` as the new headline. Contest bar unmeetable — nothing couples `y.sum()` to `len(X)`. `grep -rn "loaded rows" tests/` = **0**, so nothing pins the reason text. **Objection amended twice**: (1) its citation is wrong — `exit_sim_time_stop` appears **0 times** in `overfit_check.py`; the real source is `docs/quant/2026-08-14_model_promotion_migration_design.md:106`; (2) severity over-graded — the string is self-refuting on its face (`700 < 640` is visibly nonsense) and that era is era-EXCLUDED from training. CLAUDE.md:127-129 is true-but-incomplete (`whenever X` asserts X ⟹ substitution), not false. |
| OBJ-6 | MINOR | **CONCEDE the attribution** | The docstring covers **1 of 3**: `gate_truth_report.py:12` says "measurement standard, not a tunable" about SG_MIN_ROWS only; zero hits in `cohort_eval.py`/`cost_truth_report.py`/`overfit_check.py`. Cite each floor on its own authority instead. **Finding the panel missed**: of the three floors, `cohort_eval.py:75-82` has *stronger* pre-registration doctrine, but the **overfit row floor has neither a doctrine sentence nor a test pin** — `min_rows` is a caller-overridable kwarg with zero test references. CLAUDE.md is currently the only thing holding it, which makes it the weakest of the three and the one most worth hardening. |

### OBJ-13(a) — MAJOR — **CONCEDE the accounting; REFUTE the severity class**

The `pyrightconfig.json +13` is still uncommitted and is a separate
delta — `f756676e` never touched that file, exactly as the docket says.
The owed accounting is now paid, by measurement rather than by reading
docs (pyright 1.1.411, four runs, no working-tree mutation, no stash):

| run | invocation | result |
|---|---|---|
| 1 | the DoD command (11 explicit paths) | **0 errors, 0 warnings** |
| 2 | `pyright tests scripts` — both ABSENT from `include` | **1545 errors, 1 warning** |
| 3 | bare `pyright` WITH the include list | **0 errors, 0 warnings** |
| 4 | explicit reconstruction of the pre-change file set | **1545 errors, 1 warning** |

Run 2 settles the precedence question empirically: if `include` filtered
command-line paths, run 2 would have reported 0. It did not. **Explicit
CLI paths override config `include`**, so the DoD command and
`test_windows.bat:72` (also path-explicit) are provably inert to this
change. 0 + 1545 = 1545 locates 100% of the errors inside
`tests/`+`scripts/` — which CLAUDE.md states in as many words are
"outside the gate."

**Severity REFUTED**: the docket files this under "a check that cannot
fail." It is not that class. No gate loses power and nothing red turns
green in any gate; what narrows is a *never-gated advisory surface* —
bare `pyright` and, because `.vscode/settings.json` sets the non-default
`diagnosticMode: workspace`, the editor Problems panel. The counterweight
is real: after the change, bare `pyright` and the DoD command finally
agree, where before bare pyright printed 1545 errors no gate cared about
— a red that wasn't, the exact mirror of the green-that-isn't failure
`f756676e` exists to fix.

**Disposition: commit it SEPARATELY**, with a message naming the surface
(editor / bare-pyright only; DoD path-explicit and unaffected; 1545
ungated diagnostics intentionally suppressed). A bare `+13` to a
gate-config file riding along silently in a tree full of commits about
honest corpora reads as scope-narrowing until someone runs those four
experiments.

### NEW — raised by verification, not by the panel

**The shipped-scope list now exists in THREE uncoordinated copies** with
nothing binding them: `CLAUDE.md` prose (~line 116),
`tests/test_dependency_hygiene.py:30-32` (`ENGINE_DIRS`/`ENGINE_FILES`),
and now `pyrightconfig.json`'s `include`. All three agree exactly today;
nothing keeps them agreeing. A new engine directory would be added to
one and silently missed by the others — and the pyright copy means bare
`pyright` would stop checking it with no signal. This is the
duplicated-predicate defect class of OBJ-2, one level up, and it is
partly self-inflicted: `test_dependency_hygiene.py` was authored in a
prior session of this same effort.

### OBJ-7 — MINOR — **CONCEDE**

Commit body defect #2 claims the count "read 346, then 352, then 347
within the hour". Settled by replaying the SHIPPED loader over successive
CSV prefixes, with the method calibrated against ground truth first:
`outputs/overfit_report.md` header 16:13Z reads `loaded rows=347`, and
the replay returns 347 at 16:13Z — exact match, so the method is
validated, not assumed.

Measured trajectory (commit instant 16:22:53Z):

| count | first true (UTC) |
|---|---|
| 346 | 13:02:02 |
| 347 | 14:15:40 |
| 348 | 16:17:46 — the value AT the commit |
| 352 | **17:00:35 — 37m42s AFTER the commit** |

The trajectory is monotone non-decreasing, so **346 → 352 → 347 is
impossible in any window**. In the hour before the commit the count
changed exactly once (347→348). No artifact anywhere under the data root
records 346 or 352, so the contest condition — name three runs with path,
header timestamp and cwd — **cannot be met**. *Panel arithmetic corrected:
their figures carry a consistent +1 offset; the 16:13Z artifact arbitrates
for the replay. Every panel conclusion survives the correction.*

### OBJ-4 — MINOR — **CONCEDE the narrowed form; REFUTE the mechanism**

`:1118` still carries `Measured 2026-08-15: era exclusion left 346 loaded`
— date-only, no minute resolution. **346 was true for 73 minutes**
(13:02:02Z–14:15:40Z); the same date ranged 313→353. CLAUDE.md is now
clean of the volatile numbers, so the number was *relocated, not
removed*, by the commit declaring the class defeated. 640 stays: it is
`len(FEATURE_NAMES)*10` written beside its own expression, self-checking.

**Mechanism REFUTED.** The panel says the drift is "wall-clock label
resolution, not file growth". On the byte-identical frozen file the
loader returns **353 under every wall clock from 2026-08-06 to
2026-09-21** — a 46-day span. `ml/history.py:1532`'s `now = time.time()`
feeds only weight decay and fallbacks; there is **no wall-clock inclusion
predicate**. The 346→352 drift is file growth: 346 at data row 10652,
352 at row 10658 — six appended rows. The panel's datum is arithmetically
right but does not isolate what it claims.

### OBJ-8 — MAJOR — **CONCEDE, and it is the most structural finding in the docket**

`7566ea88` (2026-08-01) moved `ml.label_max_bars` 24→432, minting
`triple_barrier_h432`. First row 2026-08-12T20:56:18Z, 150th at
2026-08-14T00:15:07Z — both match the objection exactly.

**The arming cliff, located to the row**: at the append whose last row
stamps **2026-08-14T00:15:08Z**, the loaded corpus falls
**10,315 → 150, a single-step drop of −10,165**. That one event put the
battery under the floor.

Counterfactual matrix on the same frozen corpus answers the contest
demand directly:

| config | era | loaded | vs 640 |
|---|---|---|---|
| shipped (h432, armed) | `triple_barrier_h432` | 353 | SYNTHETIC |
| `forced_off=true` | — | 10,522 | REAL |
| **h96 era, SAME exclusion** | `triple_barrier` | **5,287** | **REAL** |
| h24 era, armed | `triple_barrier_h24` | 10,522 | REAL |

Row 3 is the proof: identical filter, mature era, 5,287 rows, REAL.
**No mechanism exists by which era exclusion alone drives a >640-row
corpus below the floor.** Exclusion is the transmission; the era RESET is
the trigger.

**The recurring structural defect**: `min_new_era_rows = 150` sits BELOW
the overfit floor of 640, which *guarantees* a window
`150 ≤ new_era_rows < 640` where the filter is armed and the battery is
simultaneously under its floor. Currently 353/640 — we are inside that
window right now, and it will recur at **every** horizon migration.

**And the un-fenced door**: `core/config_guard.py:911-914` type-checks
`forced_off` as a bool and nothing more, while `forced_on` gets a
semantic FATAL at `:925-934`. Flipping `forced_off` moves the battery
353 → 10,522 and SYNTHETIC → REAL on a corpus mixing five label eras
whose base rates span 40x — the exact widening the new CLAUDE.md
paragraph forbids by floors, reachable through a config flag instead.

## Docket CLOSED — 16 of 16 dispositioned

**Tally**: 14 CONCEDE (several with the objection amended), 2 split
concede/refute, 0 fully dismissed. Concession rate **~88%**.

Against the panel's own metric — *0% conceded → theatre; 100% conceded →
the author stopped thinking* — 88% is high, and the honest reading is
that the change genuinely was defective in most of the ways alleged.
What keeps it from being capitulation is that **seven objections were
amended or partly refuted on verification**: OBJ-15's arithmetic (7 of
14, not 13, and its OF-4 attribution rider was wrong), OBJ-10's remedy
(the banned spelling fails OPEN on false positives), OBJ-3's citation
(`exit_sim_time_stop` appears 0 times in that file) and severity, OBJ-5's
blocking claim, OBJ-13(a)'s severity class, OBJ-7's arithmetic (+1
offset), and OBJ-4's stated mechanism (refuted over a 46-day clock span).

The verification layer disagreed with the panel roughly as often as with
the author. That is the property that makes the number meaningful rather
than a vote.

## Reading so far

11 conceded (several with the objection amended), 1 split
concede/contest, 0 fully refuted. Against the panel's own metric —
*0% conceded → the panel is theatre; 100% conceded → the author stopped
thinking* — the useful signal is not the rate but that **four
objections were amended on verification**: OBJ-15's arithmetic, OBJ-10's
remedy, OBJ-3's citation and severity, OBJ-5's blocking claim. The
verification layer disagreed with the panel as often as it disagreed
with the author, which is what stops this from being either theatre or
capitulation.

**What actually needs fixing in code** (not prose): the volatile number
at `:1118`; the five-fold predicate derivation; the loaded-vs-live
conflation at `:254`; the missing could-not-fire denominator; the
one-story reason string at `:260-261`; and `gate_truth_report.py:194`'s
retired-era filter — the last being the only one with live consequences
today, since that verdict instrument currently reads zero deployed rows.
