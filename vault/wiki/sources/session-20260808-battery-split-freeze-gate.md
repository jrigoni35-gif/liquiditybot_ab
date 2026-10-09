---
title: "The Battery Split and the Frozen-Quote Gate (2026-08-08 afternoon) — Owed 44 Closed by Mechanism-Tagged Scheduling; Docket 41a Ships"
category: source
summary: "Two pushed commits, both re-verified against the box at filing. (1) be341867 closes owed 44: the load-marginal timing family — 17 tests across 7 files, tagged by MECHANISM (hard 120s subprocess wall timeouts on overfit_check CLI children = the TimeoutExpired flakes; burst-gap compression from worker descheduling between throttle release and stamp; upper-bounded elapsed asserts; a starvable heartbeat thread) — carries @pytest.mark.timing, registered STRICT so a typo is a collection error; the battery runs a parallel -n 8 -m 'not timing' pass plus a SERIAL -m timing pass, each behind its own honest `if errorlevel 1` gate, pinned by test_battery_gate.py (now 5). First split battery fully green zero-flake: parallel 3445 passed / 1 skipped in 3:28, serial 17/17 in 3:07 — and the arithmetic closes exactly (3459 collected at the split commit + 4 freeze-gate tests = 3463 = 3445+1+17). (2) 01d59908 ships docket 41a, the input-feed audit's #1 CRITICAL: a FULL-basket per-ticker-return repeat vs the previous poll is the closed-market signature; on a frozen poll the z-window is NOT appended, so z holds its last honest value instead of decaying (+0.39→0.00 was the defect); the snapshot gains additive quotes_frozen (available stays True); DF-010/DF-011 registered latched codes (registry 187→189); the options window gates on raw (pcr, oi_pcr) equality. Red-first 4/4 → green. 41c persistence stays deliberately AFTER the gate. One docket claim corrected at filing AND adjudicated by measurement: the ~14:10 auto_update cycle bounces the PUSHERS for a locally-authored pushed rev (watched land: 14:10:04 'pushers bounced for rev 01d59908', runner pid untouched) — the runner bounce onto 01d59908 needs the stop→supervisor-relaunch path used three times today; at filing the runner still runs f07d60f8, so the freeze gate is committed, pushed, and not yet the running code."
tags: [session, battery, flakes, test-discipline, gates, feeds, moomoo, staleness, reason-codes, ops]
sources: 2
source_path: none — session work product (two shipped commits, every claim re-verified against the box at filing)
source_date: 2026-08
authors: [operator, claude-session]
ingested: 2026-08-08
updated: 2026-08-08
---

# The Battery Split and the Frozen-Quote Gate (2026-08-08 afternoon)

## Provenance and boundary statement

Session work product, filed same session; **every claim re-verified against the box at
filing** — `git show` both commits (messages + stats), `pyproject.toml` marker block,
`test_windows.bat:39-45`, `data/moomoo_feed.py` at the cited lines, `core/codes.py` scanned
(**189** registered codes), `grep quotes_frozen` over `runner.py`/`main.py`/`gc_pusher.py`
(absent — the 41b deferral is real), test names collected from both new/changed test files,
`outputs/auto_update.log`, `outputs/runner.log:24488-24540`, `outputs/pc_supervisor.log`,
`outputs/runner.lock` (pid 22740, heartbeat live at 14:01 local), `git status` (head =
remote = `01d59908`).

**Paper/real boundary** ([[concepts/paper-real-boundary]]): both findings are **repo-side**
— one on the harness plane, one on a feed adapter. No sim dollar is quoted in this filing.
The moomoo quotes being gated are **real venue-data-side inputs** (US-equity risk basket);
the defect was in how the *adapter* re-served them, not in the data. Battery timings are
box timings on the 5600X under the adopted Defender posture
([[concepts/conscious-re-baseline]]).

---

## 1. Owed 44 CLOSED (`be341867`) — the battery split, scheduled by mechanism, not vibes

Commit `be341867` (2026-08-08 13:56:37 −0500, pushed). The honest pytest gate (`050421a7`,
[[concepts/false-green]] specimen #5's fix) had immediately made the load-marginal timing
family the batteries' binding constraint — the `f07d60f8` ship cycle went red·clean·red on
rotating members, each red solo-green on the same tree
([[sources/session-20260808-budget-reanchor]] §5). The split ships exactly as owed item 44
specced ([[synthesis/owed-measurements]]).

**The family: 17 tests across 7 files, tagged by MECHANISM.** The commit message names the
mechanism per member — this is the [[concepts/iron-law-of-debugging]] applied to flakes
(no test enters the family without its failure mechanism named):

- **Hard 120s subprocess wall timeouts** on `overfit_check` CLI children — the
  `subprocess.TimeoutExpired` class (`test_pbo_variants` CLI ×3, `test_overfit_check_ci`
  subprocess ×3): 8 saturated workers blow a fixed wall the child was calibrated to clear
  on a quiet machine ([[entities/overfit-check]]).
- **Burst-gap / thread-gap compression** under real contention (`test_concurrency_throttle`
  module): a worker descheduled between throttle release and stamp compresses the measured
  gap the assert bounds.
- **Upper-bounded elapsed asserts** (`test_feed_concurrency` concurrent fetch,
  `test_audit_data` poll-budget ×3, `test_throttle_threadsafe` fast path,
  `test_pc_supervisor_lock` stale reclaim): "this completes in under X" is a claim about
  the box's load, not the code.
- **A starvable heartbeat thread** (`pc_supervisor` live-peer refusal).

**Deliberate non-members:** lower-bounded elapsed tests stay parallel — load only *grows*
their measured durations, so saturation cannot fail them.

**The mechanics, all verified on the tree:**

- `@pytest.mark.timing`, registered in `pyproject.toml` under **`--strict-markers`** — the
  file's own comment states the reason: a typo'd mark is a **collection ERROR, never a
  silent no-op** that would quietly put a load-marginal test back into the parallel pass.
  [[concepts/adoption-is-not-enforcement]] applied *before* the drift, for once.
- `test_windows.bat:39-45`: **two passes, each behind its own honest gate** —
  `start /belownormal /b /wait "" %PY% -m pytest tests -q -n 8 -m "not timing"` then the
  SERIAL `-m timing` pass, each followed by `if errorlevel 1 (… & exit /b 1)`. Both arms
  BelowNormal (the profit-protection renice), both held to false-green design rule 6.
- **Pinned by `tests/test_battery_gate.py` — now 5 tests** (was 4): the new
  `test_matrix_splits_timing_family_into_a_serial_pass` asserts exactly two pytest passes,
  parallel excludes `timing`, the timing pass is serial, and both use the honest
  `if errorlevel 1` form; the banned-construct fence stays.

**First split battery: fully green, zero flake.** Parallel **3445 passed / 1 skipped in
3:28**; serial **17/17 in 3:07** (session-observed; the commit's own pre-battery
verification ran the family serial in 3:41 — two separate runs, both green). **The
arithmetic closes exactly:** whole-suite collection at `be341867` was 3459 (17 selected
under `-m timing`); the green run's tree carried `01d59908`'s 4 new freeze-gate tests →
3463 collected = **3445 + 1 skipped + 17 serial**. Smoke unchanged.

**What this is and is not:** not a retry, not a widening
([[concepts/never-widen-a-gate]]) — the tests stay honest reds wherever they fail; they
just stop being judged under a load profile they were never calibrated for. The serial
pass is a **gated stage**, so a genuine regression in a timing-family test still stops the
line. The cost the honest gate had been charging (a full ~350s re-run per rotating red) is
retired by scheduling, not by tolerance.

## 2. Docket 41a SHIPPED (`01d59908`) — the moomoo frozen-quote gate

Commit `01d59908` (2026-08-08 13:56:46 −0500, pushed). The input-feed audit's **#1
CRITICAL** ([[sources/session-20260807-fleet-findings]] §3, owed item 41a): moomoo had no
market-hours or staleness guard, so with the US market closed `get_market_snapshot`
re-served the same last/prev pair and `_poll` re-appended the identical basket return to
the z window every ~5 minutes — **93% of a closed day's polls were duplicates of two
values**, each duplicate shrinking the window's std and dragging its mean onto the frozen
value. Verified live on 08-07: identical `+3.60%` basket for hours, **z decayed +0.39 →
+0.00 on frozen input**, with ~62h of closed-market weekend ahead. The same mechanism
pinned `opt_oi_pcr_z` at a permanent 0.00 (option volume/OI are cumulative day totals,
byte-identical while closed).

**The gate** (`data/moomoo_feed.py:253-276`): a **FULL-basket repeat — every per-ticker
return identical to the previous poll (`per == self._last_per`) — is the closed-market
signature.** Three liquid names byte-identical is not a quiet market; one name moving is
not a freeze (so a genuinely dull session cannot trip it). On a frozen poll the window is
**not appended**, and the z computed from the unpolluted history **holds its last honest
value** instead of decaying. The quote itself stays real: `available` remains True, and
the snapshot carries **`quotes_frozen`** as an **additive field** (`:60`, set at `:299`) —
interface rule 7; **41b deliberately wires availability flags toward the ML path later**.

- **DF-010 / DF-011 registered** (`core/codes.py:464/476`; registry **187 → 189**,
  [[entities/reason-code-registry]]): DF-010 logged **once per freeze episode** (latched,
  same discipline as FW-080), DF-011 on resume. Transitions, not spam.
- **Options gated on raw `(pcr, oi_pcr)` equality** (`:384`) — append-skip only; the
  basket log carries the episode.
- **Red-first: `tests/test_feed_freeze_gate.py` (4)** — frozen-basket
  no-append + snapshot-flag + z-hold · moving-quotes append normally · DF-010/DF-011
  latched once per episode · single-ticker-moving is not a freeze. Ran **4/4 red on the
  pre-fix tree** (`AttributeError: quotes_frozen`), 4/4 green post-fix;
  `test_moomoo_failfast` 5/5 intact; smoke's moomoo checks unaffected (its warmup
  alternates ±0.1% per poll — never two identical frames).
- **Sequencing held:** window persistence (**41c**) lands deliberately **AFTER** this
  gate, per the audit's own warning — persistence alone would carry stale-repeat decay
  **across restarts** and make it harder to see. Gate first, then persist honest windows.
  *(Landed same day evening exactly in that order: `e22df720`, with the 41a×41c
  composition — first post-restart poll of a still-frozen market reads frozen, no
  re-seed — pinned by test.
  [[sources/session-20260808-evening-availability-persistence]] §2.)*
- **Verified deferral:** `status.json`'s moomoo block does **not** yet carry
  `quotes_frozen` (grep over `runner.py`/`main.py`/`gc_pusher.py`: absent) — operator
  visibility of a freeze episode rides with **41b**, not this commit. Until then the
  evidence of a freeze is the DF-010 log line, not a status field. *(Discharged same
  day evening: 41b `64724480` puts `quotes_frozen` in the runner status moomoo block,
  and records the same truth on every corpus row —
  [[sources/session-20260808-evening-availability-persistence]] §1.)*

This is the first shipped fix from [[concepts/zero-is-not-a-reading]]'s input-plane wing:
the gate treats "no new information" as **absence** (do not append) rather than letting
repetition manufacture "measured calm." Staleness was one of that page's four spellings of
"I don't know"; it now parses as *I don't know* on this feed.

**Parked-file note CLEARED:** the freeze-gate tests written and parked on 08-08 morning
(`test_feed_freeze_gate.py.parked`, session scratchpad —
[[sources/session-20260808-budget-reanchor]] §6) are **restored to `tests/` and committed
in `01d59908`** — the tests shipped *with* the fix, red-first, exactly as the owed item
required. Nothing remains in session-scoped storage.

## 3. Deploy state at filing — and a docket claim corrected

Both commits **pushed**, head = remote = `01d59908` verified. But at filing (14:03 local)
**the runner does not yet run the freeze gate**:

- The runner (pid 22740, heartbeat live) booted **13:11:58** onto `f07d60f8` — via the
  day's third **manual bounce**: ControlChannel `stop` at 13:09:24 → final snapshot
  13:09:30 → supervisor "runner stale/absent → relaunching" 13:11:57 → resumed from a
  2.5-min-old snapshot, 2 positions. (This also resolves how the 13:13:10 `RP-042` ack was
  possible on a verb committed at 13:09 — the bounce happened between them, unrecorded in
  the budget-reanchor filing.)
- ⚠️ **Docket claim corrected:** "auto_update's 15-min cadence will bounce the runner
  ~14:10, before US close" is **not what this box's filed mechanics do for a
  locally-authored pushed rev**. Per the local-commit blind spot
  ([[entities/auto-update]], [[sources/session-20260807-evening-ops]] §2), `decide()`
  reads local = remote as `current` and bounces **the pushers only** (the 13:10:01
  precedent: "pushers bounced for rev f07d60f8"). Every cycle up to 13:55:02 refused on
  "local uncommitted changes"; the 14:10 cycle was the first to see the clean tree —
  **and it adjudicated the correction by measurement, watched land at filing:**
  `14:10:03 already up to date` / `14:10:04 pushers bounced for rev 01d59908`, runner pid
  22740 untouched and still trading through 14:09:50+ log lines. The blind spot behaved
  exactly as filed. **The runner bounce onto `01d59908` needs the same stop →
  supervisor-relaunch path used at 11:08, ~13:10 — an operator/session action, not the
  cadence.** Until it happens, the
  moomoo gate is committed-not-running, and the weekend's ~62h of frozen closed-market
  polls starts at Friday's US close ([[concepts/deadlock-discipline]] rule 4: the window
  that matters is sized by the *market's* clock, not the deploy loop's).
- **Evening postscript (same day):** exactly that bounce was sent — ControlChannel
  `stop` ~17:4x local onto `e22df720` (supervisor relaunch pending at the evening
  filing), carrying this gate **plus** 41b's availability columns and 41c's persisted
  windows into the weekend window
  ([[sources/session-20260808-evening-availability-persistence]] §3).

## Related

[[synthesis/owed-measurements]] · [[sources/session-20260808-budget-reanchor]] ·
[[sources/session-20260808-morning-batch]] · [[sources/session-20260807-fleet-findings]] ·
[[concepts/false-green]] · [[concepts/never-widen-a-gate]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/adoption-is-not-enforcement]] ·
[[concepts/iron-law-of-debugging]] · [[entities/reason-code-registry]] ·
[[entities/overfit-check]] · [[entities/auto-update]] · [[concepts/paper-real-boundary]]
