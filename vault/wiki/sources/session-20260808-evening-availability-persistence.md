---
title: "Availability on Every Row and Windows That Survive Restarts (2026-08-08 evening) — Owed 41b and 41c Ship; the Battery Catches Its First Ninth-Slot Drop"
category: source
summary: "Operator-directed queue execution, two shipped commits. (1) 64724480 closes owed 41b: context-feed availability recorded on EVERY corpus row at ZERO model DoF (the ledger stays closed per the same-day adjudication) — _feature_extras captures the {web, equity, options, frozen} truth dict and rides gate_components' proven plumbing (candidate dict, all three order-meta stashes incl. ladder rungs via threaded feat_avail, pending 9-tuple) into 4 trailing bookkeeping columns avail_web/avail_equity/avail_options/quotes_frozen; \"\" = UNKNOWN is strictly distinguished from \"0\" = measured down; DF-020/DF-021 latched episode codes registered (registry 189→191); the runner status moomoo block now carries quotes_frozen (closing 41a's visibility deferral). THE BATTERY EARNED ITS KEEP: the first red run exposed core/persistence.py's FIXED-SHAPE pending-tuple rebuild, which would have silently dropped the 9th slot on every restart — the exact class that ate gate_components pre-T4 — fixed + pinned; migrate_history.py pads the 4 columns blank. Four battery runs; the three reds were ALL legitimate downstream schema pins (test_book_tag byte-identity + tail, test_history_migration, test_gate_components 8→9, test_long_book_integration unpack, test_sample_weights ×2 name-anchor, test_session_import_migrate stale literal 22 → now DERIVES from _N_LEAD/_N_TRAIL); zero timing-family flakes across all four batteries — the owed-44 split holding. (2) e22df720 closes owed 41c: moomoo z-windows + freeze state persist across restarts via MoomooFeed.to_dict/from_dict + a StateStore \"moomoo_state\" section (method-guarded for close()-only doubles; fail-soft from_dict — partial garbage resets clean); poll timestamps deliberately NOT persisted (immediate re-poll wanted; the restored _last_per classifies it); closes the fleet-measured ~3.5h/day empty-window rebuild hole (median 0.5h restart cadence). THE 41a×41c COMPOSITION is pinned by test: the first post-restart poll of a still-frozen market reads frozen (no append, z holds) instead of re-seeding the empty window with the frozen quote — the audit's sequencing warning honored and now enforced. 5 tests in test_moomoo_persistence.py. Runner bounce onto e22df720 sent (stop ~17:4x local, supervisor relaunch pending) — carries 41a+41b+41c through the ~62h weekend closed-market window."
tags: [session, feeds, moomoo, corpus, schema, availability, persistence, restarts, reason-codes, battery, dof]
sources: 1
source_path: none — session work product (two shipped commits, operator-directed queue execution)
source_date: 2026-08
authors: [operator, claude-session]
ingested: 2026-08-08
updated: 2026-08-08
---

# Availability on Every Row and Windows That Survive Restarts (2026-08-08 evening)

## Provenance and boundary statement

Session work product, filed same session per governance rule 12 from the executing
session's own record (battery evidence, red-first test runs and the live bounce as stated
by that session; the register moves below are the filing's own).

**Paper/real boundary** ([[concepts/paper-real-boundary]]): both commits are **repo-side**
— corpus bookkeeping and a feed adapter's persistence. No sim dollar is quoted in this
filing. The availability truths the new columns record are **venue-data-side facts about
real feeds** (whether the web/equity/options context sources were actually reachable and
whether the moomoo basket was frozen when the row was written); the ~3.5h/day and
median-0.5h figures are the fleet's repo-side measurements
([[sources/session-20260807-fleet-findings]] §3).

---

## 1. Owed 41b SHIPPED (`64724480`) — context-feed availability on every corpus row, at zero model DoF

Commit `64724480` (2026-08-08 evening, pushed). The docket's availability wiring
([[synthesis/owed-measurements]] item 41(b)): the corpus now records, **on every row it
writes**, whether each context feed was actually alive when the features were captured.

**The mechanism — riding proven plumbing, not new plumbing.** `_feature_extras` captures
a `{web, equity, options, frozen}` truth dict at feature-capture time and rides
**`gate_components`' proven plumbing** — the candidate dict, **all three order-meta
stashes** (including ladder rungs, via a threaded `feat_avail`), and the **pending
9-tuple** — into **4 trailing bookkeeping columns**:
`avail_web` / `avail_equity` / `avail_options` / `quotes_frozen`.

**The semantics are the point** ([[concepts/zero-is-not-a-reading]] applied at the schema
level): **`""` = UNKNOWN is strictly distinguished from `"0"` = measured down.** A row
that predates the columns, or a capture where availability was never assessed, can never
be confused with a feed that was checked and found dead. This is the exact
three-worlds-one-encoding defect the fleet audit named ("options feed down" vs "options
flat" vs "row predates the feature") — resolved at the *record* layer.

**Zero model DoF — the ledger stays closed.** Per the same-day adjudication
([[concepts/dof-budget]]): these are **bookkeeping columns, never features** — the model
matrix is untouched, exactly like the price anchors and `entry_price`/`exit_price` before
them. Any decision-path consumption of availability would be a schema/DoF change and
stays sequenced behind the h432 verdict.

**Registry and visibility:**

- **DF-020 / DF-021 registered** — latched, once-per-episode transition codes (the same
  episode discipline as DF-010/DF-011 and FW-080); registry **189 → 191**
  ([[entities/reason-code-registry]]).
- **The runner status moomoo block now carries `quotes_frozen`** — closing 41(a)'s
  verified deferral ([[sources/session-20260808-battery-split-freeze-gate]] §2): a freeze
  episode is now operator-visible in `status.json`, not only as a DF-010 log line.

**THE BATTERY EARNED ITS KEEP — the first red run caught a restart-eating bug before it
shipped.** `core/persistence.py`'s pending-tuple rebuild was **FIXED-SHAPE**: it would
have **silently dropped the 9th slot on every restart** — the newly-threaded
`feat_avail` — which is **the exact class that ate `gate_components` pre-T4**. Fixed and
**pinned** in the same commit. Also caught: `migrate_history.py` now **pads the 4 new
columns blank** (`""` = UNKNOWN — the honest backfill; bookkeeping is never fabricated,
same rule as the price-anchor migration, [[entities/historystore]]).

**Four battery runs; every red was the schema pin doing its job.** Three runs went red,
and **all reds were legitimate downstream schema pins** — the deliberate-schema-change
ritual functioning, not flakes:

- `test_book_tag` — byte-identity + tail
- `test_history_migration`
- `test_gate_components` — pending tuple **8 → 9**
- `test_long_book_integration` — unpack
- `test_sample_weights` ×2 — name-anchor
- `test_session_import_migrate` — **stale literal 22 retired; the width now DERIVES from
  `_N_LEAD`/`_N_TRAIL`** (the same derive-don't-restate fix the width-guard message got
  on 08-06)

**Zero timing-family flakes across all four batteries** — the owed-44 split
([[sources/session-20260808-battery-split-freeze-gate]] §1) holding under its first
multi-battery day.

**Deploy mechanics known in advance:** the corpus **header change rotates the production
file on deploy**, and `recover_local_baks` **merges via marker** — the established
rotation/recovery flow ([[entities/historystore]]), not an incident.

## 2. Owed 41c SHIPPED (`e22df720`) — moomoo windows and freeze state persist across restarts

Commit `e22df720` (2026-08-08 evening, pushed). The persistence half the audit ordered
**deliberately AFTER the freeze gate** — gate first, then persist honest windows.

**The mechanism:** `MoomooFeed.to_dict`/`from_dict` + a **StateStore `"moomoo_state"`
section**. **Method-guarded** so close()-only test doubles keep working; `from_dict` is
**fail-soft** — partial garbage resets clean rather than poisoning the feed.

**Poll timestamps are deliberately NOT persisted** — an immediate post-restart re-poll is
*wanted*; the restored `_last_per` (last per-ticker returns) is what classifies that first
poll.

**What it closes:** the fleet-measured **~3.5h/day of fabricated-neutral context from
empty-window rebuilds** at the measured restart cadence (**median 0.5h**) —
[[sources/session-20260807-fleet-findings]] §3's rolling-windows finding, owed 41's
warm-start residue. Windows now carry their evidence across process lives instead of
re-earning it from nothing every boot.

**THE 41a×41c COMPOSITION is pinned by test:** the first post-restart poll of a
**still-frozen** market reads **frozen** — no append, z holds its last honest value —
instead of re-seeding the empty window with the frozen quote. This is the audit's
sequencing warning ("persistence alone would carry stale-repeat decay across restarts and
mask it") **honored and now enforced by a test**, not just by ship order.

**Tests:** 5 in `tests/test_moomoo_persistence.py`.

## 3. Deploy state at filing

**Runner bounce onto `e22df720` sent** — ControlChannel `stop` at ~17:4x local, supervisor
relaunch **pending** at filing (the same stop → stale/absent → relaunch path used three
times on 08-08; the local-commit blind spot means the cadence alone never bounces the
runner, [[entities/auto-update]]). Once relaunched, the box carries **41a + 41b + 41c
through the ~62h weekend closed-market window** — the freeze gate holds z honest, the
persisted windows survive any weekend restarts, and **the avail flags will document the
freeze on every row written**. The weekend the 08-07 audit dreaded becomes the mechanism's
first full-length live exercise.

## 4. Register moves

- **41(b) and 41(c) CLOSED** in [[synthesis/owed-measurements]].
- **41(d) (sentiment `vol_z` items=200 saturation) and 41(e) (`opt_iv_skew` −3.00 clip
  rail) remain open** — under the canonical docket lettering; two of
  [[concepts/zero-is-not-a-reading]]'s four spellings still parse as numbers.
- **Queue continues: 42(a)/42(e) → 37(g) → 37(b) → 45a-45f.**

## Related

[[synthesis/owed-measurements]] · [[sources/session-20260808-battery-split-freeze-gate]] ·
[[sources/session-20260807-fleet-findings]] · [[concepts/zero-is-not-a-reading]] ·
[[concepts/dof-budget]] · [[entities/historystore]] · [[entities/reason-code-registry]] ·
[[entities/auto-update]] · [[entities/overfit-check]] · [[concepts/paper-real-boundary]] ·
[[concepts/conscious-re-baseline]]
