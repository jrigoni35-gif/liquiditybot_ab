---
title: "Comparability Boundaries — the one authoritative table"
category: synthesis
status: SETTLED
summary: "Every cut across which a statistic of this project must not be pooled, on one page: the paper/real boundary above all, four fill-axis execution boundaries (QA quarantine, XV-021 8e5455e8, TTL 3cfe0710, double-count aeeaae36 at 2026-08-10T11:03:35Z), the label-axis 432 migration (7566ea88), the capital epoch 2026-08-10T23:05:27Z, and cut #7 the geometry epoch MINTED at 2026-08-11T01:33:50Z (e7d5ca1a, widen-beyond stop placement; exec_era 7-e7d5ca1a) — with the exact instant, the mechanism, what each cut poisons, and the decision rule for rows that predate the exec_era provenance column. STANDING BLIND SPOT added 2026-08-16: outputs/fills.csv is gitignored (.gitignore:9 'outputs/', a directory rule) and has NO git history, so every boundary on this page is applied to a file whose past states are unrecoverable — composition drift can only be RE-DERIVED, never forensically diffed, two disagreeing readings cannot be adjudicated by history, the quarantine rule IS the version history, and every cohort statement is as-of-read. Same for outputs/signal_history.csv, observed growing between two reads 34 seconds apart. EXECUTED 2026-08-28: boundary #5, the fee-truth cut, is cut #8 on the all-cuts counter — minted under operator adjudication ('both: full bundle') at the deploy instant 2026-08-28T03:14:13Z (config applied 02:34:42Z, but a running process keeps its init-read constants, so the era begins at the runner restart); exec_era 8-ca55e2ba, anchor = the package-defining commit ca55e2ba because a commit cannot contain its own hash; apply commit 4e502478 carried the exec_era bump IN THE SAME COMMIT (cut #7's late-bump debt not repeated), deploy stamped 9f0264c6, both on origin/main; fees 25/40 → 40/80 both pricing and booking sides, derived entry bar 0.6902 → 0.8335 (0.833 proven in the running binary's startup log), p_win 0.85, control-arm tag (schema 94→95) merged in the same bundle; era-5 accrual starts at ZERO — nothing pools with era-4. ROWS 10–12 APPENDED 2026-09-18 (from docs/HANDOFF.md ERA-9, the session-authoritative record for these cuts, plus the 2026-09-08 cut-12 adjudication doc): cut #10 (10-a5acfe2d, 2026-09-06) six defects + the E1 legacy-ladder 20/35 re-booking; cut #11 (11-6e584923, 2026-09-07) the COMMIT configuration (hedger OFF, majors only, $60 probes); cut #12 (12-10d4d0c2, live 2026-09-08T23:47:45Z) FEE-4 20/35 → 15/30 Tier 5, geometry moving by construction (PT 220→180, SL 165→135, BE floor 76→66), era-8 closed FINAL 4/1, era-9 accruing — n=50 lean / n=100 verdict pre-registered. Numbers on rows 10–12 are AS-OF-HANDOFF; re-derive against primary records before citing them as measurements."
tags: [register, boundaries, comparability, epistemics, cohorts]
sources: 13
updated: 2026-09-18
---

# Comparability Boundaries — the one authoritative table

**Purpose.** Before this page, era membership lived in a join between row timestamps and
constants scattered across config prose, commit messages, and four wiki pages. This page is the
single place a session checks **before pooling any two numbers**. If a statistic spans a row of
this table, it must be qualified by which side each observation came from — or split.

**The rule:** a trend across ANY of these cuts is confounded with the cut **by construction**.
Pooling across one produces [[concepts/pooled-populations]]; reading a trend across one is a
regime change wearing a trend costume.

## The table

| # | axis | cut (exact) | commit / event | what changed | what it poisons if pooled |
|---|---|---|---|---|---|
| 0 | **paper/real** | permanent, above all others | operator directive 2026-08-07 | nothing here executes — every fill, fee, dollar is simulated | citing ANY sim-conditioned number as venue truth ([[concepts/paper-real-boundary]]) |
| 1 | fill | 2026-08-02 | `858c8d71` / `483f6727` (QA quarantine) | QA-harness fixture fills quarantined out of the ledgers (the 27x error's substrate) | any per-fill statistic including pre-quarantine rows unfiltered |
| 2 | fill | 2026-08-02, ts≈1785717000 | `8e5455e8` (XV-021) | `passive_base_prob` 0.45 → 0.048 (measured trade-through rate) | pre-boundary paper data is fill-flattered **9x**; post-boundary starvation is the honest rate, not a defect |
| 3 | fill | 2026-08-08 (~11:10 boot) | `3cfe0710` (TTL normalization) | per-poll hazard normalized per-ORDER; kills the compounding gift that filled 6h long-book bids with certainty at −50bps | long-book fill rates, −50bps "capture," any TTL-sensitive fill statistic |
| 4 | fill | **2026-08-10T11:03:35Z** (= 06:03:35 −05:00; shipped strings said "08-09" until `2fee7f64` — **use the stamp**) | `aeeaae36` (double-count removal) | one market crossing was modelled by TWO mechanisms; `2f−f²` = 21.96% vs f = 11.66% target — **~1.88x at the touch** | **the ENTIRE pre-#4 corpus** — every fill statistic in this vault carries the ~1.88x near-touch upward bias; zero post-boundary fills existed at the last audit of this claim |
| L | **label** | 2026-08-01T20:27:08−05:00 (= 2026-08-02T01:27:08Z) | `7566ea88` (verified against the repo at filing: "432-bar horizon migration — move the bar, not the calibration") | label horizon → 432 bars (`triple_barrier_h432`); pre-registered cohort, verdict at n=50 closes | pooling h24/h96/h432 label definitions in any training or win-rate statistic ([[concepts/label-era]] — the corpus-corruption incident is what pooling them looks like) |
| 5 | **capital** | **2026-08-10T23:05:27Z** (epoch 1786403127) | the $800 stressor reset (`38751d5b` deployed; epoch amended into the gate by `a7dab725`) | capital 5000 → 800; all money state zeroed; goals 25/wk, 100/mo, ladder 1.0; venue floors deliberately UNSCALED so the $15 ticket floor moves 0.3% → **1.9%** of equity | any gross%/net%/expectancy statistic pooled across the epoch — sizing floors shift the whole distribution; the era-4 verdict cut is **`max(B4_TS, CAPITAL_EPOCH_TS)`** and the 3 post-#4 pre-epoch closes are excluded |
| 7 | **geometry** | **2026-08-11T01:33:50Z** (deploy instant; book flat and orderless through the kill→relaunch window, so the boundary is ambiguity-free) | `e7d5ca1a` (widen-beyond stop placement; `exec_era` → `7-e7d5ca1a` one commit late in `76030603` — verified zero fills in the gap) | Osler stop semantics FLIPPED tighten-above → widen-beyond (stops near half-step round levels rest PAST the level: herd fires first, ours only on a genuine break); the dormant tighten-side nudge retired, its phantom `risk_management` config read fixed, and the nudge now runs on the BRACKET path — i.e. on virtually every trade, where before it ran on almost none | any stop-distance, MAE, stop-hit-rate, or trip-outcome statistic pooled across the cut — the traded stop geometry changed sign AND coverage; era-4 gate accrual restarted 0/50 at this instant at zero cost (no closes since the capital epoch) |
| 8 | **fee** (fill-axis **boundary #5**; ⚠ fee figures CORRECTED by row 9 — cut #8 over-stated ~2x) | **2026-08-28T03:14:13Z** (deploy instant — config applied 02:34:42Z, but a running process keeps the fee constants it read at init, so the era begins at the runner restart: stop issued 03:11:58Z → STOPPED 03:12:13Z → new runner PID 9108 up **03:14:13Z**, first observed RUNNING 03:14:51Z; corroborated by the new process's own startup log `fees=40/80bps … p(win) bar=0.833 (derived)`) | `4e502478` (stager `--apply` + `exec_era` → `8-ca55e2ba` **in the same commit** — cut #7's late-bump debt NOT repeated; deploy stamped `9f0264c6`; both on `origin/main`; operator adjudication 2026-08-27, "both: full bundle". Naming judgment, recorded in the constant's own comment: the anchor is `ca55e2ba`, the package-DEFINING commit, because a commit cannot contain its own hash) | fee truth (owed 88): 25/40 → **Kraken Tier-1 40/80 bps on BOTH the pricing and booking sides**, PT break-even floor → 80, label round-trip cost → 1.2%, exploration `p_win` → 0.85; derived entry bar **0.6902 → 0.8335** — the probe lane that generated 85% of era-4 stops clearing BY CONSTRUCTION (first 162 post-cut cycles: SZ-023 ×42 = the adjudicated book-quieting, not a fault); the control-arm stratification tag (schema **94→95**, write-path only, never read) merged in the same bundle; `dry_run` TRUE untouched | ANY fee-sensitive statistic pooled across the cut — booked fees ~double, net/expectancy/EV shift wholesale, and the admission mix flips probe-starved; **era-5 accrual starts at ZERO from this instant** — nothing from era-4 (COST_BOUND, n=54, cohort CLOSED at its readout state) may be pooled with it. Standing residue: `scripts/quant_trials.py` `TIER_CFG["est_fee_bps"]` still 40 (QT-1, [[synthesis/owed-measurements]] item 106) — G1–G5 greens are about the harness's OLD cost world, not deployed geometry |
| 9 | **fee** (fill-axis **boundary #6**) | **2026-08-30T15:32:36Z** (deploy instant — config applied earlier that morning by `scripts/fee_correction_stage.py --apply`, but the era begins at the runner restart: `stop` sent via control plane 15:30:24Z (cid `1788103824.226997-67a8f6`), runner acked 15:30:25Z, pc_supervisor relaunch 15:32:36Z, new runner worker PID 7692 created **15:32:36Z**, first RUNNING line 15:32:37Z; corroborated by the new process's own startup log `fees=22/38bps … net of 0.60% rt cost … p(win) bar=0.677 (derived)`. NOTE the updater could never have restarted it: a locally-born deploy reads "local is AHEAD — runner untouched"; restart is operator-side by construction for on-box cuts) | `59bdcf87` (stager `--apply` + `exec_era` → `9-16ec821e` **in the same commit**; anchor `16ec821e` = the fee_tier_correction adjudication commit that DEFINES the cut — verified it shipped `scripts/fee_tier_rederive.py` + the adjudication doc; operator ARM 2026-08-30 "fee correction only"; a commit cannot name its own hash) | **cut #8 over-stated fees ~2x** — the account is real **Kraken Tier 3 = 22/38 bps** (operator Kraken app, $17,482 30-day volume), not the assumed Tier-1 40/80. 40/80 → **22/38** on both pricing+booking, PT break-even floor 80 → 38, label round-trip cost 1.2% → **0.6%**, `allow_sub_floor_fees` → true (22/38 is below the 40/80 `KRAKEN_SPOT_FLOOR` tripwire, which STAYS as the understated-fee guard; the account genuinely holds the Tier-3 discount — what the flag is for); exploration `p_win` LEFT at 0.85; derived entry bar **0.8335 → 0.6772** (runtime-verified, sizer==hand) — **conviction RESUMES**, cut #8's probe-dominated book UNWOUND (it was an artifact of the ~2x-too-high fee); give-back buffer 166 → **82bps**; ALGO-5 tail-control EXCLUDED (net-CI spans zero on fills alone); `dry_run` TRUE untouched | ANY fee-sensitive statistic pooled across the cut — booked fees ~halve back toward truth, net/expectancy/EV shift wholesale, admission mix un-starves; **era-6 accrual starts at ZERO from the restart instant** — nothing from era-5/cut-8 (or era-4) may be pooled with it. **Corrects row 8's fee figures**: cut #8's "COST_BOUND at true fees" verdict rested on the ~2x-too-high schedule (the-method #1 recurrence — a struck fee schedule asserting itself as truth). QT-1 residue UPDATED: `TIER_CFG["est_fee_bps"]=40` vs deployed **38** now (was 80) — drift narrowed 40bps → 2bps, harness near-coherent again |
| 10 | **fee** | **2026-09-06** (deploy instant per the running binary's startup log — same-session authority: `docs/HANDOFF.md` ERA-9 history line) | `a5acfe2d` (`exec_era` → `10-a5acfe2d` in the same commit) | six verified defects fixed + **E1: fees re-booked 20/35 on a LEGACY-ladder premise** (Kraken's old fee table, not the account's tier) — the fourth instance of the-method recurrence #1, committed "inside the module built to end it" (`core/venue_fees.py`); the 20/35 over-stated the round trip by 10 bps (22.2%) against cut #9's 22/38 | ANY fee-sensitive statistic pooled across the cut — booked round trip moved 22/38 → 20/35 (wrong direction, legacy-ladder basis); era-7 ran at the wrong cost; SUPERSEDED fee-wise by row 12, which re-booked from the app reading |
| 11 | **config** (not fee) | **2026-09-07** | `6e584923` (`exec_era` → `11-6e584923`) | **the COMMIT configuration**: hedger OFF, majors only, $60 probe tickets (skimmer OFF, universe narrowed to the core majors; the deliberate "run the registered experiment, not the hedge grid" configuration) | any statistic pooled across it confounds the configuration change with performance — hedger state, universe width, and ticket size all moved at once; era-8 accrues under it; its closing count is whatever `scripts/cohort_eval.py` reports (deliberately no count in law) |
| 12 | **fee** | **minted 2026-09-08; LIVE since 2026-09-08T23:47:45Z — earlier than planned and not by a deliberate act**: pc_supervisor logged "runner stale/absent -> relaunching" at 23:41:21Z (heartbeat starved under the cut's own DoD battery plus two workflows' agents running pytest concurrently), the relaunched runner booted from the working tree with config already applied and took the single-instance lock; every fill from that boot is stamped `12-10d4d0c2` | `10d4d0c2` (`exec_era` → `12-10d4d0c2`; decision record `docs/quant/2026-09-08_cut12_fee_rebook_adjudication.md`, §7 erratum; operator approval verbatim: *"Re-book now … Yes do a reset."*) | **FEE-4: 20/35 → 15/30** (Kraken **Tier 5**, read three ways: app screenshot 30-day spot volume **$69,652.65**, AoP **$822.24**; the venue fee page as raw text; `core/venue_fees.binding_row` reproducing the app's next-tier distances to the cent). Six keys moved, the cut-#9/#10 cascade and nothing else: `pretrade`+`order_manager` maker/taker 20/35 → 15/30, `profit_taking.est_fee_bps` 35 → 30, `ml.label_round_trip_cost_pct` 0.55 → **0.45**, derived entry bar 0.6642 → **0.6381** (re-derived 2026-09-17: `PositionSizer(...).p_bar_base` == 0.6381). **The barrier geometry moved with the cost by construction** (the §7 erratum — "geometry untouched" was false): label PT 220 → **180 bps**, SL 165 → **135** at σ_bar 0.10% (re-derived via `ml/labeling.barrier_geometry`), BE/trail floor 76 → **66 bps** = 2·30+6; the tier ROLLS on the operator's real trading (Tier 3 on 08-29 → Tier 5 on 09-08): re-read at every readout with `scripts/fee_drift_report.py --volume-30d <v> --aop-usd <a>`, never chase mid-era. **Era-8 CLOSED FINAL: 4 entries, 1 closed trip.** Era-9 accrues from zero; read points pre-registered at cut #11: n=50 = the lean, n=100 = the verdict; H0 ≈ −$0.2851/trip (era-measured, adopted 2026-09-15 — the −$0.27 cut-#12 figure is one generation stale) | ANY fee- or geometry-sensitive statistic pooled across the cut — booked fees fell 10 bps/round trip, label PT/SL and the live bracket widths moved with them under the same `label_era` name (it encodes the horizon only); era-8's 1 trip is the entire post-#11 population; **era-9 accrual starts at ZERO from the 23:47:45Z boot** |

## How to decide which side a fill row is on

Since `6fe6d98d` (2026-08-10), `fills.csv` carries an **`exec_era` provenance column**
(`"4-aeeaae36"`), stamped at write time — the constant bumps in the same commit as any future
boundary. **Old rows are deliberately BLANK** (back-filling a guess would manufacture
provenance): **blank = decide by row timestamp against this table.** The migration left them
blank on purpose; that is a feature of the schema, not a gap in it
([[sources/session-20260810-stressor-epoch]] §2).

> ⚠️ **Contradiction — QUALIFIED 2026-08-14, not overturned.** The blank rule above is
> correct for the rows it was written about and **returns the WRONG era for a class it did
> not anticipate: rows where `exec_era` is ABSENT rather than empty.**
>
> *What was claimed:* blank ⇒ decide by ts; the schema has no gap.
> *What refuted it:* `outputs/fills.csv` field-width histogram **`{17: 1059, 16: 6}`**
> (measured 2026-08-14T22:49Z, double-derived — a first pass by naive comma-splitting
> wrongly said 170 and was discarded). `exec_era` is column index **16, the LAST** of 17,
> so a writer whose `COLS` predates the stamp emits a **16-field row** and the field is
> *missing*, not blank. Six such rows exist. Deciding them by ts reads **era-7** while
> their fill physics is **pre-boundary-#4**: `git reflog` puts the live tree at `21769fb8`
> (2026-08-07) from 08-11 19:50 until the 08-12 20:21 fast-forward, and boundaries #3, #4
> and cut #7 are all **non-ancestors** of it — the TTL-hazard bug and the ~1.88x near-touch
> double-count were both live for those fills.
> *What stands:* the table itself, and the blank rule for genuinely blank rows. What is
> added is a **three-way** read, now implemented in `scripts/cohort_eval.py` and pinned by
> `tests/test_cohort_homogeneity.py`:
>
> | `exec_era` | meaning |
> |---|---|
> | **absent** (row shorter than header) | **stale binary** — do NOT decide by ts |
> | **blank** (`""`) | pre-stamp row of a stamp-aware writer — decide by ts, as above |
> | stamped | authoritative |
>
> **Cohort impact: 4 of 13 accruing era-4 trips carry a stale-binary leg**, and 6 of 13
> straddle a mid-flight champion deploy. No cut is minted or moved by this finding — it
> reports contamination against the EXISTING cuts. Whether a mixed cohort resets accrual is
> an operator adjudication, deliberately not taken.
> — [[sources/session-20260814-cohort-instruments]] Finding 1

## Who reads which cut

- **The era-4 verdict gate** (`scripts/cohort_eval.py`): population starts at
  `max(B4_TS, CAPITAL_EPOCH_TS)` = **2026-08-10T23:05:27Z**. Accrual 0/50 from that instant.
  *Operational note, so the gap is never misread as a market property: the first **25h 9m**
  after the epoch (to `2026-08-12T00:14:10Z`) contain **zero entries BY INCIDENT** — the
  un-re-anchored weekly loss budget hard-vetoed all new risk (RP-041,
  [[sources/session-20260812-weekly-anchor-lockout]]). No population effect (nothing traded,
  nothing excluded); a pure hole in the accrual calendar.* **[UPD 2026-08-28: era-4 is CLOSED
  at its readout state (COST_BOUND, n=54). Era-5 accrual starts at zero from the cut-#8 deploy
  instant 2026-08-28T03:14:13Z; the pre-registered gate machinery (`cohort_eval.py`, bands,
  selection rule) was deliberately NOT touched by the cut.]*
- **The 432 cohort** ([[comparisons/horizon-96-vs-24-bars]]): label-axis cohort that now
  contains fill boundaries #2, #3, #4 AND the capital epoch inside it — any within-cohort trend
  is quadruply confounded.
- **Label training** ([[concepts/era-exclusion]]): keys on the label axis (persisted
  `label_era`), not on this table's fill or capital axes — by design.
- **Every wiki filing**: [[concepts/paper-real-boundary]]'s filing rule (state the side), plus
  this table for the inner cuts.

## Minting a new boundary

Per the **era-4 accrual moratorium** ([[synthesis/governance-doctrine]] rule 17): a
cohort-resetting change (entry decisioning, sizing, fill sim, fee booking, order lifecycle)
mints the next row of this table and is **forbidden without operator adjudication**. One
boundary per commit ([[concepts/lever-coupling]], [[concepts/inertness-protocol]]) — owed 61
stays open precisely because fixing it would mint one. When a boundary is minted: bump
`exec_era`, stamp the UTC instant in the same commit (the class of error `2fee7f64` had to fix),
and add the row here in the same session.

**The next cut is already named — #7, the geometry epoch (PROSPECTIVE, not minted).** The Grand
Synthesis standing directive ([[sources/directive-20260811-grand-synthesis]], Phase C) plans
**one adjudicated geometry-epoch package** — cheapest at low accrual, 0/50 at filing — whose
**timing adjudication is PENDING with the operator**. ~~This paragraph is a reservation, not
a boundary.~~ **SUPERSEDED — cut #7 is MINTED: 2026-08-11T01:33:50Z, the geometry epoch.**
The operator's pasted-back adjudication (2026-08-11, the CDO-review split of
[[synthesis/grand-synthesis-algorithm-package]]) landed the evidence-sufficient Tier-2
elements at zero accrual: ALGO-7's widen-beyond Osler flip (the only behavior change — see the
table row) and ALGO-6 as **pins, not duplicates** (the hard time limit and PT-060 already
existed; four tests now pin them). ALGO-5's replay-parameterized stop widths and the
time-decay ladder are **deferred to an amendment at ~30 uncensored trade paths** — that
amendment, when adjudicated, mints the NEXT row of this table, not a revision of this one.
The timing bet paid exactly as planned: zero closes existed between the capital epoch and the
deploy, so the era-4 gate population is uniformly post-geometry **with no code change to the
pre-registered gate** — `max(B4_TS, CAPITAL_EPOCH_TS)` and "after cut #7" select identical
populations by construction, forever (every future close postdates both).

*Minting-rule debt, recorded: the `exec_era` bump did NOT ride the boundary commit as the rule
above requires — it landed one commit late (`76030603`). The gap was verified fill-free (book
flat, runner down for most of it), so zero rows were mis-stamped; the provenance pin now locks
the exact constant, so the next bump cannot land silently OR late without a red test.*

~~**The next cut after that is STAGED — boundary #5, the fee-truth cut (STAGED 2026-08-25,
NOT minted).**~~ **SUPERSEDED — boundary #5 is EXECUTED as cut #8: 2026-08-28T03:14:13Z, the
fee-truth epoch (see the table row).** Commit `ca55e2ba` shipped `scripts/boundary5_stage.py` —
the owed-88 fee-constant correction (config 25/40 → true Tier-1 40/80, plus exploration
`p_win 0.85` against the derived net-Kelly entry bar **0.8335**) fully prepared and INERT. Its
adjudicated batching condition — **AT READOUT** (the 2026-08-16 operator adjudication of owed
88) — was **met on 2026-08-26**: the era-4 gate crossed n=50 and read **COST_BOUND**
([[sources/session-20260826-why-losing-deep-dive]]). The operator's adjudication arrived
2026-08-27 ("both: full bundle" — the fee apply AND the control-arm merge), and the apply ran
2026-08-28: the stager owned every config write (drift-check green, backup written, `validate()`
on the applied file = 0 FATAL / 4 WARN, all four documented consequences), `4e502478` carried
the `--apply` result and the `exec_era` bump **in the same commit** per the minting rule above
(fee booking → cohort-resetting → the table row filed the same session, per the executor's OWED
note in `docs/HANDOFF.md` — this paragraph and the row above discharge it), and `9f0264c6`
stamped the deploy instant. **Fees are proven in the running BINARY, not just the repo** (the
readout-needs-a-binary-sha lesson below, applied prospectively): the post-restart startup log
prints `fees=40/80bps` and the derived bar `0.833`. 7 suite pins re-baselined (2 structural),
none widened; `dry_run` TRUE untouched. Numbering note: "boundary #5" continues the fill-axis
execution boundary count (#1-#4 in the table; the repo reserves "#6" for the CONC-1 concurrency
decision, `docs/HANDOFF.md`), while "cut #8" counts ALL cuts — four fill-axis + the label axis
+ the capital epoch = six, geometry seventh, fee-truth **eighth**. Two counters, both in use —
`8-ca55e2ba` binds them: era ordinal from the all-cuts counter, anchor from the package-defining
commit (a commit cannot contain its own hash, so the apply commit could not self-name).
— [[sources/session-20260827-sdd-verification-and-era-confound]] §6 (the cut-#8 addendum)

## The readout needs a BINARY sha, not a repo sha (2026-08-16)

> **ANY GATE READOUT WITHOUT A RECORDED RUNNING-BINARY SHA IS UNVERIFIABLE AFTER THE FACT.**

Every boundary in the table above is a **commit** — and a commit is a statement about the
*repository*, not about **the process that produced the rows**. Those two came apart, measurably:

- The **live tree sat at `21769fb8` (2026-08-07)** until the 2026-08-12 fast-forward.
- **Boundaries #3, #4 and cut #7 are NOT ancestors of `21769fb8`.**
- The **deploy branch is `claude/remote-control-e3h815`, not `main`.**

So for a window of the accrual, "the boundary commit exists in the repo" and "the running bot
contains it" were **different facts**, and only the second one is about the rows. This is the
[[concepts/session-identity-is-not-stable]] problem moved from the session to the **binary**: the
citation formatting is intact and the world it refers to is a different checkout — the same shape
as *date the checkout, not the fix commit*.

**Standing requirement, effective now:** at the era-4 readout, **verify and RECORD the sha of the
running binary** (branch + tip of the deploy checkout, snapshot-stamped), beside the cohort cut.
A readout is a claim about a population produced by a program; naming the program is part of
naming the population.

**Related epoch-minting item, still owed:** `max_concurrent_positions` (**5**, `config.json`) is
declared **EPOCH-MINTING until adjudicated** — it sets both the **accrual rate** and the
**uniqueness** of overlapping trips, hence `n_eff` and therefore the gate's own resolution floor
([[concepts/average-uniqueness-and-ess]]). Changing it does not merely change how fast rows
arrive; it changes **what the pre-registered n=50 is worth**. Operator adjudication, per
[[synthesis/governance-doctrine]] rule 17.
— [[sources/session-20260816-catchup-08-12-to-08-16]]

## STANDING BLIND SPOT — the cohort source has no history (2026-08-16)

**`outputs/fills.csv` is gitignored** and therefore **has no git history at all**.
Re-derived: `git check-ignore -v outputs/fills.csv` → **`.gitignore:9:outputs/`** — a
**directory** rule, so every cohort artifact under `outputs/` is covered — and
`git log -- outputs/fills.csv` returns **empty**.

> **Every boundary on this page is applied to a file whose past states are
> unrecoverable.** Composition drift between two reads **can never be forensically
> diffed** — only **re-derived**. There is no "what did the cohort look like on
> 08-15" query, and two readings that disagree **cannot be adjudicated by history**.

This is permanent and not fixable retroactively. Three consequences that bind:

1. **Every cohort statement is AS-OF-READ.** Snapshot-stamp it (delegated-measurement
   contract rule (c)); a cohort number without a read time is not a measurement.
2. **The quarantine rule IS the version history.** The decision table's §5 item 10 —
   *"Loss or rewrite of `outputs/fills.csv`. It is the sole cohort source. Quarantine,
   never delete"* (machine-enforced by `.mythos/policy.json`) — is load-bearing, not
   ceremonial. It is the only mechanism standing in for `git log`.
3. **The same applies to `outputs/signal_history.csv`**, which is where
   `geometry_breakeven` reads (`scripts/cohort_eval.py:390`, `:648`) and which was
   observed **growing between two reads 34 seconds apart** (8,395,113 bytes, mtime
   2026-08-16T21:16:29Z). A statistic over a live file is a **snapshot**, and its row
   count belongs in every quotation of it.

**What the read could see `[K]`, 2026-08-16T21:15:55Z:** `fills.csv` 170,155 bytes,
**1,069 data rows**, mtime **2026-08-16T15:28:57.671817Z** — **2.1 s after** the last
trade's close (15:28:55.563Z), consistent with **pure append**. **What it could not
see:** the absence of a retroactive rewrite. Append-consistent mtimes are *evidence
of*, not *proof of*, an append-only history — and with no git history, **no stronger
check exists**. ([[concepts/zero-is-not-a-reading]] — the absence of a diff is not a
clean diff.)

**Demonstrated, not argued — the file moved mid-analysis.** Two reads 9½ minutes
apart, with no write by the reader: **170,155 → 170,303 bytes**, **1,069 → 1,070 data
rows**, mtime **15:28:57.671817Z → 21:25:24.872329Z** (the live bot appending), while
the era-4 cohort held at **n=16** with a bit-identical gross mean
**+0.6576563162731225%**. **Row growth is NOT cohort growth** — the new row is an
**open leg**, not a closed round trip. A later session seeing 1,070 rows must not
infer the cohort moved, and **with no git history it cannot check — only re-derive.**
— [[sources/session-20260816-catchup-08-12-to-08-16]] §10c

## Related

[[concepts/paper-real-boundary]] · [[synthesis/owed-measurements]] ·
[[comparisons/horizon-96-vs-24-bars]] · [[concepts/label-era]] · [[concepts/era-exclusion]] ·
[[sources/session-20260810-stressor-epoch]] · [[sources/session-20260810-fill-double-count]] ·
[[sources/session-20260808-morning-batch]] · [[sources/session-20260802-digest]] ·
[[sources/directive-20260811-grand-synthesis]]
