---
title: "Staleness Truth and the Battery's Honest Turn (2026-08-08 night) — Owed 42a Ships; the Overfit Stage Flips to Live Grading and Goes Red"
category: source
summary: "⚠️ CORRECTED IN PLACE 2026-08-09 — §2's root cause was FALSE IN BOTH HALVES (there is no 60-row threshold; the predicate is len(X) >= len(FEATURE_NAMES)*10 = 640 over LOADED rows, and the flip was the era-filter DISARM caused by the corpus corruption of [[sources/session-20260809-corpus-corruption]], not cold-start growth); §1's known-limits list was also incomplete (a CRITICAL-latent veto band plus three limits, all filed on the corrective page). The struck text is preserved below as the retraction record. || ORIGINAL: One shipped commit + one finding requiring OPERATOR ADJUDICATION. (1) 36fcfd6e closes owed 42a: the pre-trade staleness veto is resurrected via recv_ts on books — REST attaches the stamp after clean_book, the ws manager attaches the cache's raw write stamp via new LiveMarketCache.book_ts (zero-caller accessor promoted), and the engine stamps book_ts = float(book.get(\"recv_ts\") or now) in fast_cycle + the runner PAUSED-flatten. Replay determinism preserved BY CONSTRUCTION: FeedRecorder records returned dicts verbatim (extra-key pass-through pre-pinned by test_recording), stampless legacy books take the byte-identical fallback. 6 tests in test_staleness_truth.py incl. the write-time-not-read-time pin and the two-writer source contract; 2 ws-manager shape pins updated, cache-layer pins untouched. Known limits documented: content-frozen-through-a-live-socket is the 41a class per-feed; the watchdog's .get(a, now) fail-open default left for its own item. (2) NEW FINDING, registered as owed item 46: the battery's overfit stage flipped from synthetic to LIVE grading when live rows crossed overfit_check's 60-row threshold — the cold-start corpus (64 features vs this-era labels) fails OF-1 (train_auc ~0.70-0.77 vs oof ~0.51, all 3 families) and OF-7 (dead_frac=0.97) HONESTLY, the DoF CLOSED-ledger conclusion stated back by the gate. Every future battery is red at the overfit stage until adjudicated → auto_update deploy gate blocked, DoD ALL GREEN unattainable. 42a shipped with disclosure (orthogonality proven: diff touches zero ML paths; pytest 3458+17, smoke 219, assurance 49, ruff/pyright/bandit/compileall, quant G1-G5 all green). Policy options registered NOT decided — (a) exploration-phase informational grading (DSR precedent), (b) hard block until the corpus grows, (c) --force-synthetic until the era-3 corpus matures. Runner NOT bounced onto 36fcfd6e pending the adjudication; 42e next in queue."
tags: [session, latency, staleness, feeds, replay, overfit, battery, deploy-gate, adjudication, governance, corrected]
sources: 2
source_path: none — session work product (one shipped commit + one finding requiring operator adjudication)
source_date: 2026-08
authors: [operator, claude-session]
ingested: 2026-08-08
updated: 2026-08-09
---

# Staleness Truth and the Battery's Honest Turn (2026-08-08 night)

> ⚠️ **CORRECTED IN PLACE 2026-08-09 — read this banner before anything below it.**
> **§2's root cause is FALSE in both halves** and has been struck rather than deleted
> (this vault records retractions as first-class content). **§1's known-limits list was
> incomplete** — an adversarial audit of this very commit the next day found one
> **CRITICAL-latent** defect it introduced plus three limits it did not claim. **§1's
> ship-disclosure contains an assertion that was never run**, and running it would have
> caught the corruption the same evening. All three corrections, with their evidence,
> are on **[[sources/session-20260809-corpus-corruption]]**.

## Provenance and boundary statement

Session work product, filed same session per governance rule 12 from the executing
session's own record (battery evidence and red-first test runs as stated by that session;
the register moves below are the filing's own).

**Paper/real boundary** ([[concepts/paper-real-boundary]]): everything here is
**repo-side**. No sim dollar is quoted. The `recv_ts` stamps the veto now ages are
**venue-data-side facts about real feeds** (when the book actually arrived); the OF-1/OF-7
readings are repo-side gradings of the training corpus, whose live-era rows are
sim-execution-conditioned by construction.

---

## 1. Owed 42a SHIPPED (`36fcfd6e`) — the staleness veto resurrected via `recv_ts`

Commit `36fcfd6e`. The last clock-shaped tautology in the decision path
([[concepts/tautological-instrument]]) is repaired: the pre-trade staleness veto no longer
ages a timestamp with the same cycle-frozen `now` that stamped it.

**The mechanism — books carry the feed's own write stamp:**

- **REST path:** `recv_ts` is attached **after `clean_book`** — the stamp records when the
  book was actually received/written, not when the cycle later read it.
- **WS path:** the ws manager attaches the cache's **raw write stamp** via new
  **`LiveMarketCache.book_ts`** — a zero-caller accessor promoted to production use.
- **Engine:** `book_ts = float(book.get("recv_ts") or now)` stamped in `fast_cycle` and
  the runner's PAUSED-flatten path.

**Replay determinism preserved BY CONSTRUCTION**, not by hope: `FeedRecorder` records the
returned dicts **verbatim** — extra-key pass-through was **pre-pinned** by
`test_recording` before the change — and **stampless legacy books take the byte-identical
fallback** (`or now`, the old arithmetic). A pre-42a recording replays exactly as it
always did.

**Tests:** 6 in `tests/test_staleness_truth.py`, including the
**write-time-not-read-time pin** (the exact defect, pinned by name) and the **two-writer
source contract** (REST and WS both attach the stamp). 2 ws-manager shape pins updated;
cache-layer pins untouched.

**Known limits, documented at ship rather than discovered later:**

- **Content-frozen-through-a-live-socket** is the 41(a) class, **per-feed**: a live socket
  delivering fresh-stamped but frozen content passes this veto — detecting that is the
  freeze-gate's job ([[sources/session-20260808-battery-split-freeze-gate]] §2), one feed
  at a time, not this veto's.
- The watchdog's `.get(a, now)` **fail-open default** (the
  [[concepts/zero-is-not-a-reading]] spelling: a missing entry reads perfectly fresh) is
  **left for its own item** — consciously out of this diff.

> ⚠️ **CORRECTION 2026-08-09 — the known-limits list above was incomplete, and this
> commit introduced a CRITICAL-latent defect it did not know about.** An adversarial
> audit of `36fcfd6e` the next day found four things
> ([[sources/session-20260809-corpus-corruption]] §11):
>
> 1. **THE VETO BAND (CRITICAL-latent, now fixed in `3c0debd7`).** Once this commit made
>    `book_ts` **data time**, `websockets.kraken_max_book_age_sec` = **5.0s** exceeded
>    `pretrade.max_data_staleness_ms` = **4000ms** — so a ws book aged 4–5s is **SERVED**
>    by the cache and then **VETOED** by PT-020, and because `main.py` only falls back to
>    REST when the ws returns `None`, that doomed book **PREEMPTS a REST read that would
>    have been fresh**. Exposure **~0.6–3% of entry evaluations**, worst on the thinnest
>    pairs (MINA 3.2%, FLOW 2.9%, PAXG/LINK 1.9%, BTC 0.6%) — **skewing which assets can
>    accumulate fill labels**. Masked only because the book was full 5/5; it would have
>    armed the moment a position closed. Fixed `5.0 → 3.5` plus a `config_guard` **FATAL
>    on the relation itself**.
> 2. **REST-path sign inversion.** `now` is frozen at cycle start but `recv_ts` is stamped
>    **after** the blocking fetch, so `staleness_ms <= 0` for any book fetched this cycle
>    (a 50s REST hang reads **−50000ms**). **This commit buys NO new detection power on the
>    REST path** — the genuine gain is the **WS path only**.
> 3. **The pre-42a code was NOT tautological on the FAILURE path** — `book_ts` held the
>    last successful cycle's `now` and grew **~5s/cycle**, which is exactly the path this
>    commit's message led with. The tautology was real on the **success path only**.
> 4. **DL-10 cannot benefit** — the new measurement is capped at `kraken_max_book_age_sec`
>    (now 3.5s) while DL-10/watchdog trip at `stale_critical_sec` = **120**; a quantity
>    capped at 3.5 cannot cross 120.

**Ship disclosure:** the battery's overfit stage was **red at ship** for the corpus reason
in §2 — and the diff's **orthogonality was proven** (it touches zero ML paths; pytest
**3458 + 17 serial**, smoke 219, assurance 49, ruff/pyright/bandit/compileall, quant
G1–G5 **all green**). ~~Shipping with a disclosed, proven-orthogonal red is the honest
version of what [[concepts/false-green]] forbids faking.~~

> ⚠️ **CORRECTION 2026-08-09 — the disclosure claimed a measurement it never took.**
> This commit's message asserted **"the identical red reproduces on the parent commit."**
> It was **ASSERTED, NEVER RUN.** Had it been run, the **+9,272-row jump** in the loaded
> corpus would have been unmissable and the corruption would have been caught the same
> evening; instead the false premise of §2 reached the wiki. The **diff-orthogonality**
> half of the disclosure stands (the diff really does touch zero ML paths) — but
> orthogonality of the *diff* was never evidence about the *corpus*, and the two were
> conflated. Precedent tightened
> ([[sources/session-20260809-corpus-corruption]] §14, [[concepts/false-green]]):
> **a battery stage turning red FOR THE FIRST TIME is a blocking investigation, not a
> disclosable footnote**, and **any "orthogonal"/"reproduces on parent" claim must ship
> with the command that produced it.**

## 2. ~~NEW FINDING — the overfit stage flips to LIVE grading and goes honestly red~~ — ROOT CAUSE **RETRACTED** 2026-08-09 (OPERATOR ADJUDICATION STILL OWED, item 46)

> ⚠️ **RETRACTION — the root cause below is FALSE IN BOTH HALVES.** Struck, not deleted.
> The corrected filing is [[sources/session-20260809-corpus-corruption]] §9; the corrected
> numbers are its §8.

**WHAT WAS CLAIMED (struck):**

> ~~This evening the live-row count crossed `overfit_check`'s **60-row threshold**, and the
> battery's overfit stage **flipped from synthetic to LIVE grading** for the first time —
> honest cold-start growth.~~
>
> ~~**The readings:** OF-1 train_auc ~0.70–0.77 vs oof ~0.51 (all 3 families); OF-7
> dead_frac = 0.97.~~

**WHAT REFUTED IT:**

1. **There is no 60.** The predicate is **`len(X) >= len(FEATURE_NAMES) * 10 = 640`**
   (`scripts/overfit_check.py:180-182, :207`). **The flat `60` was DELETED 2026-07-11 by
   `7486ab29`** — it had not existed for a month when this page claimed it.
2. **`len(X)` is LOADED rows** — candidate + live, after every filter — **not live rows**.
   The corpus holds **305 live rows total** and is **append-only**, so this battery's own
   printed **"live rows=467"** was **arithmetically impossible**. Two stale strings caused
   the misreading (the module docstring `:9` and the report string `:216`, both
   mislabelling total loaded rows as "live rows"); **both fixed at source in `3c0debd7`**.
3. **The flip was a DISARM, not growth.** Between the 17:06 and 23:30 batteries only
   **33 rows** were appended (**all candidate**) while the **loaded** count jumped
   **467 → 9,739**. That +9,272 jump is the **era-filter DISARM** caused by the
   `label_era` corpus corruption — a **self-inflicted data bug**, not cold-start growth
   ([[sources/session-20260809-corpus-corruption]] §1–§4).

**WHAT STANDS.** The overfit stage **is** honestly red, and the red **is** the
[[concepts/dof-budget]] CLOSED-ledger conclusion stated back by the gate — but on the
**repaired** corpus, with different numbers, for a different reason. On the clean corpus
the audit is **3 pass / 4 fail**: OF-1 gaps **+0.422 / +0.414 / +0.503** (logistic / gbt /
mlp — **worse** than the pooled corpus's +0.19..+0.27, exactly as a smaller cleaner corpus
should be), OF-7 **dead_frac 0.95** (61 of 64 features near-zero), OF-7 **rows/feature
10.8 PASSES but barely**, shuffle and purge PASS; and the audit's own learning curve reads
**"CLIMBING (delta_auc=+0.112) — data-starved."** The **conclusion survived its own false
premise** — which is exactly why the premise had to be checked.

**Consequence:** every future battery is **red at the overfit stage until adjudicated** —
the [[entities/auto-update]] deploy gate fails closed for **any** external push regardless
of the commit's content, and DoD ALL GREEN is unattainable in the interim.

**Policy options registered, NOT decided** — gate-widening is forbidden without conscious
re-baselining per CLAUDE.md ([[concepts/never-widen-a-gate]],
[[concepts/conscious-re-baseline]]); this is the operator's call:

- **(a)** Exploration-phase **informational** grading for OF-1/OF-7 — the DSR precedent
  ("informational not gating during exploration").
- **(b)** **Hard block** until the corpus grows past the honest thresholds.
- **(c)** **`--force-synthetic`** in the battery until the era-3 corpus matures —
  validates the machinery, not the corpus.

Registered as **[[synthesis/owed-measurements]] item 46** — *(2026-08-09 note: this page
referenced "item 46" but **never actually created the entry**; it was written for the
first time, with the corrected root cause, during the corpus-corruption filing.)* The red
is the mirror image of [[concepts/false-green]] — an honest red — to be disclosed per
battery, never retried away, never silently widened. **The three policy options above
survive the retraction unchanged**; only their justification moved.

## 3. Deploy state at filing

The runner was **deliberately NOT bounced onto `36fcfd6e`** pending the gate adjudication
(the local-commit blind spot means the cadence would not have bounced it anyway —
[[entities/auto-update]]; here the non-bounce is a choice, not the blind spot). **Owed
42(e) (the restart-warmup race) remains next in the queue.**

## 4. Register moves

- **42(a) CLOSED** in [[synthesis/owed-measurements]]; the docket's open half is now
  (d)'s veto-grade response and (e).
- **NEW item 46 registered** — the overfit-stage live-grading adjudication,
  operator-owned, blocking the deploy gate ahead of everything in the queue.
- [[concepts/tautological-instrument]] — the veto specimen (the class's last decision-path
  clock) marked repaired.
- Queue: **42(e) → 37(g) → 37(b) → 45a–45f**, with item 46's adjudication gating deploys
  across all of it.

**2026-08-09 register corrections** ([[sources/session-20260809-corpus-corruption]] §15):

- **42(a) is NOT fully closed** — three known limits (REST sign inversion, the
  success-path-only tautology, the DL-10 cap) are now open sub-items, and the commit
  introduced the veto band that `3c0debd7` fixed.
- **Item 46 rewritten** with the corrected root cause and the repaired-corpus numbers.
- **NEW item 47** — the wedged champion, a direct consequence of the corruption this page
  misdiagnosed.

## Related

**[[sources/session-20260809-corpus-corruption]]** (the corrective filing — read it with
this page) · [[synthesis/owed-measurements]] · [[concepts/tautological-instrument]] ·
[[concepts/label-era]] · [[concepts/migration-idempotence]] ·
[[entities/pretrade-gate]] · [[entities/config-guard]] ·
[[entities/overfit-check]] · [[entities/auto-update]] · [[concepts/dof-budget]] ·
[[concepts/never-widen-a-gate]] · [[concepts/conscious-re-baseline]] ·
[[concepts/false-green]] · [[concepts/zero-is-not-a-reading]] ·
[[sources/session-20260808-battery-split-freeze-gate]] ·
[[sources/session-20260807-fleet-findings]] · [[concepts/paper-real-boundary]]
