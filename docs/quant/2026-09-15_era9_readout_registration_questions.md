# Era-9 readout — seven questions to settle ON THE RECORD before n=50 lands (2026-09-15)

**Class:** DOC_ONLY / OPERATOR_DECISION. Nothing here changes code or config. **Deadline:** the n=50 lean
arrives at roughly **2026-09-19 to 09-22** (22 stamp-pure closes at 2026-09-15T04:27Z, 3.6–5.3 closes/day
by three routes; `scripts/cohort_eval.py` prints `CURRENT-ERA ACCRUAL: N/50` — re-derive, never quote this
page's count). **Every question below becomes post-hoc the moment the n=50 numbers are visible**, which
destroys the pre-registration that is the entire epistemic value of era-9. Decide them now, while the sample
is too small to know which answer flatters you.

Sources: `CLAUDE.md` era-9 block (:158-163); `docs/quant/2026-09-07_cut11_commit_adjudication.md` (the
registered metric, :86-99, :102-106); `docs/quant/2026-09-05_era6_membership_registration.md`;
`scripts/cohort_eval.py`; the 2026-09-15 survey and panels (vault `raw/audits/2026-09-15_session_f2f5d5cd/`).

---

## Q1. Which null does the verdict read against?

`CLAUDE.md:163` says *"−fee/trip ≈ −$0.27 at a $60 ticket"* (cut-#12 fees 15/30). The cut-#11 adjudication
(line 82) says *"−$0.33 at 55 bps × $60"* (cut-#11 fees). The rule is phrased *"CI excluding −fee."* The fee
was re-booked at cut #12 without re-stating the null. **Pick one number and write it down.**

## Q2. Is the UNDETERMINED → extend-to-200 branch in force for era-9?

The cut-#11 registration carries it (lines 102-106). `CLAUDE.md` omits it entirely. As it stands it is an
unregistered escape hatch that can only loosen STOP. **In or out, in writing.**

## Q3. Which trips are members? (22 vs 27)

Stamp-purity (every leg carries `exec_era 12-10d4d0c2`) gives **22**; that rule was registered 2026-09-05
for era-6. Closing-leg attribution gives **27**, adding 5 straddlers that opened under earlier fee rows —
including the long-book straddler `e602d04f`, era-12's largest winner (+$2.70). The answer to "does this
make money" moves by about $3 and one whole winning trade on this choice. **Confirm the 09-05 rule
transfers to era-9, or register a different one now.**

## Q4. Do long-book positions (`LB-000`, BTC/ETH accumulation, 12% thesis stops) belong in the 5-minute cohort?

`scripts/cohort_eval.py` has no `book` filter. 4 of 27 era-9 entry positions are long-book. The long book is
on no cut's "untouched" list and shares slots and heat with the probe book. **In or out.**

## Q5. The registration is internally inconsistent about its own test.

Its power paragraph tests z **against zero**; its decision rule tests **against −fee**. These give different
answers at the same n. **State which the n=50 lean and the n=100 verdict each use.**

## Q6. What does the readout actually TEST? (This is the one that matters.)

**23 of 23 era-9 five-minute-book entries were exploration probes** (`ML-070`), admitted by a model-free
budget roll and sized at a forced `p_win = 0.85` (`main.py:4728 max(p_win, explore_p_win)`;
`config.json ml.exploration.p_win`), while the model's own p was 0.39–0.51 against a 0.638 bar. **Zero
conviction entries since the cut.** The exploration lane's off-switch (`until_live_rows: 1200`) counts live
rows, which come from fills, which are ~95% probes — the lane's off-switch is fed by its own output.

So the n=50/n=100 verdict will describe *"$60 entries admitted by a constant, under this exit geometry and
this cost stack"* — a real and useful question — but it **cannot falsify the model's selection skill in
either direction.** `cohort_eval` discloses the probe share (`:675-719`) and computes the verdict on those
trips anyway. **State, in writing, that this is the question era-9 answers — or state that it is not, in which
case the experiment as posed cannot answer it and that should be known before the date, not after.**

## Q7. The registered statistic is not computed by any script. Build it before the date.

Registered (cut-#11 :88, adopted by `CLAUDE.md:158-161`): *net $/trip, 95% day-block bootstrap CI keyed on the
UTC day of the closing fill, 4,000 reps, seed 7; n=50 lean — act only if the CI excludes zero; n=100 verdict —
CONTINUE iff net > 0 with the CI excluding −fee.*

Shipped (`scripts/cohort_eval.py`, grep `bootstrap|day_block|seed|reps|4000` = **0 hits**): one threshold
(`ERA4_MIN_N = 50`, :144), **no n=100 tier**, a naive iid SE on nominal n (:378-379), **%/trip not $/trip**,
a three-way readout decided on **point-estimate signs** (:387-394) with **no interval anywhere in the
decision**, run on the **pooled n=131 six-era population** while printing only a count for era-9. Its
`COST_BOUND` word needs only a positive **median** (rule at :389-392 requires both mean and median ≤ 0 to
say no-edge); era-12 today has mean < 0 and median > 0.

**Action (SAFE, ~half a day, touches no decision path):** a report-only *sibling* script — `cohort_eval.py` is
named "untouched" by the law — computing (a) net $/trip and gross %/trip on the membership rule from Q3,
(b) the registered bootstrap CI, (c) both registered decision rules, (d) overlap-deflated effective n
(`cohort_eval.cohort_effective_n` exists, :623-672), pinned by a test that plants a known-edge and a
known-null synthetic ledger and watches both arms fire. A ~40-line prototype ran in a reviewer's scratchpad
on the 22 trips. **Without this the n=50 date arrives and the question is still unanswerable.**

---

## Two record defects the readout must know about

- **A position was closed twice**: `0526a410` PAXG, two full-size exits 3.3 s apart by two live runner
  processes (`docs/quant/2026-09-15_duplicate_runner_double_exit.md`). `cohort_eval` silently drops the trip
  (exit size ≠ entry size). Decide: count once, or exclude — and say so.
- **Three config fingerprints have run under the one era-9 stamp** (`CG-000 config_sha256`: `d3a2bfd0` at the
  cut boot, matching **no committed revision**; `ebbd0a85` ~24 h before its commit; `7aab700b` applied by an
  unrelated restart). The last two are verified benign (watch-lane keys). The first is unrecoverable.
  `cohort_eval`'s homogeneity verdict segments by a code constant and cannot see this. Decide whether era-9
  is still "one experiment" and record the answer.

---

# ADDENDUM, same day — Q8 to Q11, and two sharpenings

**Added 2026-09-15T16:10Z after the instrument of Q7 was built and put through a blind
reimplementation plus three mandated-position reviewers** (`scripts/era_readout.py`,
`tests/test_era_readout.py`; verdict `ship_after_named_fixes`, all twelve fixes applied).
Nothing below is a new opinion: each item is a property of the REGISTRATION that the
instrument made visible by computing it. The register-decay discipline applies — Q1 to Q7
above stand as written; these attach.

## Q8. The registered interval under-covers, and today it disagrees with its own calibration.

The registration names *"95% day-block bootstrap CI (UTC day of closing fill, 4,000 reps,
seed 7)"*. The default reading of that is a **percentile** bootstrap. A percentile bootstrap
over few clusters under-covers: simulated **~0.85 at 6 blocks** (today), **~0.92 at ~12**
(about n=50), **~0.94 at ~24** (about n=100) [I — assumed error model]. So the n=50 clause
*"act only if the CI excludes zero"* fires under H0 nearer **8–9%**, not 5%.

This is not hypothetical. On today's ledger the two families **disagree about the answer**:

| population | registered percentile CI | cluster-t (CR1, df=5) calibration |
|---|---|---|
| stamp-pure, all books | [−0.9247, **−0.1644**] — excludes zero | [−1.0775, **+0.0056**] — touches zero |
| stamp-pure, 5m only | [−0.8941, **−0.1575**] — excludes zero | [−0.9910, **+0.0442**] — touches zero |

**Decide now, not at the read point:** read the registered interval as written, accepting a
disclosed ~8–9% false-action rate under H0 (the registration says it is *"powered to catch
losing, not to certify small winning"*, so erring that way is arguably what you signed up
for) — **or** minute an amendment to a cluster-robust t interval **before** the n=50 data
exist. Choosing the family after seeing which one excludes zero is the single move a
pre-registration exists to prevent. The instrument prints both and lets no rule read the
calibration one.

**Also inside Q8:** the n=50 clause says *"act on it"* and **names no action**. Name one, or
strike the clause. As written it cannot be complied with or violated.

## Q9. The n=100 rule has a hole, and the 5m-only row is sitting in it.

The registered branches are: CONTINUE iff net > 0 and CI excludes −fee; STOP iff (gross mean
≤ 0 **and** gross median ≤ 0); STOP iff (gross > 0 **and** net ≤ 0). The quadrant **gross
mean ≤ 0, gross median > 0, net ≤ 0** matches none of them and falls to UNDETERMINED →
extend-to-200 — *even when the net CI excludes zero from below*, i.e. even when the book is
losing with a clear interval.

Today's 5m-only row is exactly there: gross mean **−0.212%**, gross median **+0.457%**, net
**−0.4734**. **What applies in that quadrant?** The letter says extend; the n=50 lean clause
says act. The instrument follows the letter and appends a note naming the conflict.

## Q10. Confirm "$60 tickets" and "majors only" are HYPOTHESIS wording, not filters.

The population clause names neither. Measured on the stamp-pure population: tickets span
**$31.27–$114.70** (median $60.03), and one ETH trip at $114.70 contributes **−$2.88 of the
−$13.94** total net — about 21% of the loss from 4% of the trips. Entries include 9 shorts.
Symbols are PAXG/ETH/BTC/LINK = the config universe.

If either phrase is meant as a filter it is a **decision key**, it is cohort-resetting, and
it must be registered explicitly — not applied silently by whoever runs the readout.

## Q11. Two dependence models are printed and they disagree by 1.7×. (For era-10, not era-9.)

The registered close-day blocks imply an SE inflation of **×1.08**; the overlap/uniqueness
deflation on the same page implies **×1.80** (effective n 8.0 of 26). Both are on the page
because both are true of different dependence; the rule uses the weaker one. **15 of 26 trips
cross UTC midnight** and 32 of 67 overlapping trip-pairs sit in different blocks, so the
registered interval does not see their shared market path.

**Do not change this for era-9** — it is the registered method. For the era-10 registration,
consider a moving-block or 2-day-block resample, decided in advance.

## Sharpening Q1 (the null) — there are THREE candidates, not two

cut-#11 registered **−0.33** (55 bps × $60) · CLAUDE.md cut-#12 **−0.27** (45 bps × $60) ·
**era measured −0.2960** (49.3 bps of the $60.03 median ticket — because every exit pays
taker). The instrument defaults to −0.27 and prints all three. The band **−0.296 to −0.27 is
2.6 cents wide and can flip CONTINUE ↔ UNDETERMINED at n=100** at the SE this cohort will
have. Pick one.

## Sharpening Q3/Q4 (membership) — the choice flips which STOP clause can fire

Not merely the count. Pooled (n=26) vs 5m-only (n=23):

| | net median | gross median |
|---|---|---|
| all books (n=26) | **−0.4191** | **−0.364%** |
| 5m only (n=23) | **+0.0033** | **+0.457%** |

Both medians change sign. Since the no-gross-edge STOP branch requires gross mean **and**
median ≤ 0, the book choice decides whether that branch is reachable at all. Three long-book
trips ($31–47 tickets, 36–94 h stale-loser thesis exits, **0 wins of 3**, mean −$1.02) carry
it. The instrument therefore labels **neither** row "REGISTERED" — it prints "registration
LETTER" (cohort_eval pools books) and "registration HYPOTHESIS" ($60 5m probes) and requires
you to select one.

## Expected outcome, stated in advance so it is not misread when it arrives

The cost is certain (~$0.30/trip). Era-9 gross/trip is **−$0.11, CI [−$0.52, +$0.29], effective n ≈ 6** at
n=22 — indistinguishable from zero. Five held-out instruments find no directional information in the entry
stream. Under both the no-gross-edge and cost-bound branches the era-9 registration routes to **STOP**, and
STOP does **not** revert to the hedged 12-asset book. If the readout comes back CONTINUE, suspect the
instrument before the market. Nominal 50 will most likely deliver a weak lean, not a decision — the SE is
inflated ~1.6× by overlap. That is the price already agreed for a readable sign; the only way to lose it is
to touch the order path before the date.
