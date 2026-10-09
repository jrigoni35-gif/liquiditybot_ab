---
title: "The Closing Batch (2026-08-07 night) — Defender Verdict, Latency Truth Tier 1, and the pandas the Grep Could Not See"
category: source
summary: "Operator-dictated closing batch, every item re-verified against the box at filing: (1) Defender A/B verdict — clean battery 3438/0/1 at 401.30s vs 375.39s = +6.9% under the ADOPTED final posture (source scanned, only .venv + pytest-temp excluded), with the event-log proof that the years-old broad exclusion meant every historical battery baseline ran effectively unscanned; (2) latency truth tier 1 SHIPPED as 915b362f — cycle_duration_sec/max, wall-clock marks_age_sec via telemetry-only _mark_wall_ts twins, FW-080 stale-bar detection (registry 186), 8 red-first tests, three integration seams caught by the matrix; (3) both new instruments proved non-tautological LIVE the same night (45.56s cold-boot stall caught; 16.7s-and-climbing while stopped); (4) the venv-prune incident — 'zero importers verified' was WRONG for pandas (moomoo hard-exits at import, never declared to pip), brief 22:21–22:25 crash-loop, recovered; static grep ≠ runtime import graph; (5) owed 43(a) and July transcript item 70 closed; (6) commit chain 48a63610 → 1e7f882c (closes owed 39) → 486a6891 (closes owed 36a) → 915b362f"
tags: [session, defender, latency, telemetry, incident, venv, dependencies, closures, battery]
sources: 1
source_path: none — session work product; every claim re-verified against the box at filing (git log, Defender event log 5007, runner.log, pc_supervisor.log, status.json, site-packages, config.json)
source_date: 2026-08
authors: [operator, claude]
ingested: 2026-08-07
updated: 2026-08-07
---

# The Closing Batch (2026-08-07 night)

## Provenance and boundary

Operator-dictated batch, filed same-session per governance rule 12. **Every headline claim below
was re-verified against the box at filing** — commits by `git show`, the Defender change by event
log 5007, the incident by `outputs/runner.log` + `outputs/pc_supervisor.log`, the instruments by
`outputs/status.json`, the dependency claims by the venv itself. **Everything here is repo-side /
ops-side** ([[concepts/paper-real-boundary]]); the only dollars ($4,605.78 / $4,615.71 / $4,616
equity) are **sim-side by construction** and appear as liveness markers, not performance claims.
All clock times **local −05:00 unless suffixed Z** (zone-stamp rule, governance rule 13).

---

## 1. The Defender A/B verdict — and what it says about every historical baseline

**Verdict: clean battery under the final posture — 3438 passed / 0 failed / 1 skipped in
401.30s vs 375.39s baseline = +6.9%**, attributed to source-tree scanning newly ON.
**The posture is ADOPTED**: source tree scanned; only two narrow exclusions remain —
`liquiditybot_ab\.venv` and the pytest temp dir. Documented, revertible. This closes
[[synthesis/owed-measurements]] **item 38(a)** on its own terms: the *measurement* first, then
the priced adoption decision — and the decision came out the opposite way the item feared
(exposure retired, cost accepted) because the broad exclusion was already there, unpriced.

**Event-log verification (Defender 5007, read at filing):**
- `21:14:50` — two **New value** entries: `...\liquiditybot_ab\.venv` and
  `...\Temp\pytest-of-johnmason` (the narrow pair; added by the operator's script).
- `21:18:19` — the broad `C:\Users\haird\Documents\liquiditybot` path appears **only as an
  Old value** — its removal, via `Remove-BroadExclusion.cmd` (verified present on the Desktop).
  *Filing correction, minor:* the operator's dictated "~21:5x" is superseded by the event log's
  21:18:19 — the log is the authority (same discipline that caught the double-filed churn
  window).
- **No add event for the broad path exists in today's log** — it predated the session (>3 days
  per the retention window; years old per the operator). So the 5007 record proves the claim
  that matters: **today's script added only the two narrow paths; the broad exclusion was
  historical.**

**The implication for the corpus:** every historical battery wall-time baseline — the 623s
serial number, the ~400s xdist numbers of the capacity sweep
([[sources/session-20260807-capacity-sweep]]) — was measured with the repo **and `.venv`
effectively unscanned** by Defender. The timing baselines were all conditioned on an
undocumented AV posture nobody had priced. Filed into [[concepts/conscious-re-baseline]]: the
scanning-on posture is the **new standing timing baseline**, written down with its condition.

> ⚠️ **Honesty caveat on the +6.9%.** The same night produced a third wall time under the
> adopted posture: `915b362f`'s own battery ran **3438/0/1 in 359.13s** — *below* the 375.39s
> scanning-off baseline. Same-posture spread (359.13–401.30s) exceeds the single-pair delta
> (25.91s), so **+6.9% is a one-pair estimate inside the noise band, not a precision cost**.
> What is adopted is the *posture* — battery fully green under scanning, cost bounded at
> roughly single-digit percent — not the number.

## 2. Latency truth tier 1 — SHIPPED as `915b362f` (verified at file:line)

Commit `915b362f` (22:16:15 −05:00), the deterministic-safe tier of the
[[synthesis/owed-measurements]] item-42 latency docket. Three instruments that previously
measured nothing:

1. **Cycle duration** — closes **42(c)**. The loop computed `elapsed` every iteration and used
   it only to size the sleep; the documented 88.1s stall left no trace in any exported number.
   Now: `BotRunner._note_cycle_duration` (`runner.py:1057`) records last/max, `build_status`
   exports `cycle_duration_sec`/`cycle_duration_max_sec`, and the metrics pusher ships both
   (`gc_pusher.py:253`).
2. **`marks_age_sec` is now wall-clock truth** — closes **42(b)**. The engine writes
   **telemetry-only `_mark_wall_ts` twins** (`main.py:1234`) beside the loop-frozen `_mark_ts`;
   the runner's `_marks_age_sec` helper (`runner.py:1806`) reads the twins with wall clock.
   **No decision path touches the wall stamps — replay determinism intact.** The
   [[concepts/tautological-instrument]] specimen is repaired, not deleted.
3. **FW-080 stale venue bars** — instruments **42(d)**, detection-only. Fetch age proved the
   CALL was recent, not the DATA; nothing validated `candles[-1]['time']`. New registered code
   `FW_STALE_BARS = "FW-080"` (`core/codes.py:51`; [[entities/reason-code-registry]] 185 → 186);
   module-level `_bar_age_check` (`main.py:468`), threshold `_STALE_BAR_SEC = 1200.0` — 4
   five-minute bars, chosen because thin pairs legitimately omit empty intervals — **latched
   once per stale episode per asset, re-armed on recovery**. The veto-grade response is
   explicitly **sequenced with the staleness-veto resurrection (42a), not bolted on** — 42(a)
   remains open by design, not by omission.

**Red-first: 8 tests, `tests/test_latency_truth.py` (132 lines), including parsed-AST wiring
pins.** Battery **3438/0/1 in 359.13s, smoke 219, ALL GREEN**.

**The matrix earned its keep three times on this one change** — three integration seams caught
before arming: **`__new__` doubles** (the exit-isolation suites), **SimpleNamespace-as-self**
(`test_v8_batch.py` drives `_augment_view_with_kraken` with a bare namespace — the reason
`_bar_age_check` is module-level and duck-typed), and **smoke's outage simulation** (its clock
freeze had to move to the wall stamps). A unit-green change would have shipped broken against
all three; this is the standing argument for the full hardened matrix
([[sources/session-20260807-capacity-sweep]]).

**Flake registration (load-marginal class):**
`test_feed_concurrency::test_fetch_is_concurrent_not_serial` flaked **once under `-n 8`**,
passes solo in 1.6s. Registered as the successor to the now-closed RST class (§6) in the
load-marginal timing family — an honest red, **not** to be blanket-retried
([[concepts/never-widen-a-gate]]).

## 3. Live verification, same night — both instruments proved non-tautological

The [[concepts/tautological-instrument]] diagnostic question — *what would this instrument have
to see to read differently?* — now has a demonstrated non-empty answer for both:

- **`cycle_duration_max_sec = 45.56` on first boot** — the cold-boot warmup stall left a trace
  in an exported number for the first time in the project's history. Still standing in
  `status.json` at filing (cycle 66).
- **`marks_age_sec` read 16.7 and climbing while the bot was STOPPED, and 0.0 when fresh.**
  The old arithmetic could read nothing but 0.0; the new gauge read a stopped bot as stale.

Both readings are telemetry-plane facts about the box — no venue claim. An instrument that
produced a reading its predecessor was arithmetically forbidden from producing is **verified by
that reading alone**.

## 4. The venv-prune incident — the correction is the finding

**What was claimed** ([[synthesis/owed-measurements]] 38(d)): the retired streamlit/pandas UI
stack had **"zero importers verified"** in shipped scope.
**What refuted it:** the moomoo SDK **runtime-requires pandas and hard-exits at import** —
`site-packages/moomoo/__init__.py` prints `Missing required package pandas` and calls
`sys.exit(1)` (verified at filing, lines 43/47). The requirement was **never declared to pip**,
so `pip check` was silent.
**What stands:** static grep of *our* sources is not the runtime import graph — **vendor SDKs
hide requirements**, and both greens (grep clean, pip check silent) were structurally incapable
of seeing this one. Filed as the fourth specimen of [[concepts/false-green]]. Prune ledger
amended: **pandas is a KEEP** (reinstalled — pandas 3.0.5 beside moomoo_api 10.8.6808 in the
venv at filing); **the other six removals stand** (streamlit verified absent).

**The incident, box-verified timeline (runner.log + pc_supervisor.log):**
- `22:18:46` post-bounce runner boots, runs **degraded (no moomoo)**; supervisor posture
  confirmed at its start line: `check=30s, stale=120s` (`pc_supervisor.log:3445`).
- The cold warmup ran **~3.5 min against the 120s stale window**; supervisor logged
  `runner stale/absent -> relaunching` at `22:21:45`; the displaced runner **exited
  gracefully** (`final snapshot saved` at 22:19:28 / 22:22:38 across the window — losing the
  instance lock, never crashing with state).
- Two bare `Missing required package pandas` stdout prints sit between boots — replacements
  that **died at import**, before logging existed. Boots at `22:21:46` and `22:24:48`,
  ~3 min apart = the **brief crash-loop, 22:21–22:25** (operator dictated 22:22–22:25; log
  bounds slightly wider).
- **pandas reinstalled 22:26 → recovered.** The 22:24:48 boot resumed from a 2.2-min-old
  snapshot — 3 positions, equity $4,605.78, `RUNNING`; at the operator's check: cycle 9,
  equity **$4,615.71**, 3 positions restored, moomoo connected, **FW-080 quiet**, HEAD
  `915b362f`. At filing: cycle 66, equity $4,616 (sim-side dollars).

**Two lessons filed, one watch item armed:**
1. **Static grep ≠ runtime import graph** — the false-green specimen above. The only
   verification that would have caught this is *booting the pruned venv*, which is exactly
   what caught it.
2. **The slow-first-cycle vs supervisor-staleness race** — cold warmup ~3.5 min vs stale=120s
   is [[concepts/liveness-by-output-cadence]] firing a **second time** (this time displacing a
   healthy-but-warming runner rather than duplicating a quiet pusher), and a
   [[concepts/deadlock-discipline]] rule-4 violation in waiting (a window never sized against
   the measured cadence it polices). Filed as **owed 42(e)** on the restart docket.

## 5. Sweep-survivor closures — verified this hour

- **Owed 43(a) — CRLF bundle transport — CLOSED, and the registration itself corrected.** The
  pin exists and is **stronger than the July-18 zip**: `scripts/telemetry_backup.py:246` writes
  a `.gitattributes` containing `* -text` **into the bundle worktree before `git add`**, per
  push, so the committed blob equals on-disk bytes on every machine regardless of local
  autocrlf. Introduced in `4a42d2c2` — **2026-07-18 20:14:56Z, the same day as the incident**:
  the port DID happen, same-day. `tests/test_telemetry_backup.py` exists (25.1K). The fleet
  sweep had looked for a **repo-level** `.gitattributes` pin — right invariant, wrong layer.
  Registered claim refuted-by-verification; the refutation is the closure.
- **July transcript-ledger item 70 — RESOLVED.** `ml.adaptive_gbt.enabled: true` **ships in
  `config.json`** (verified at filing). Opt-in top ladder rung, still evidence-gated: per the
  config's own doc note, enabling changes the deployed selection rule (OF-3 PBO reads the
  flag) and an adaptive_gbt champion must still beat mlp out-of-sample by the Brier margin.
  (Item 70 belongs to the four-agent ~200-bug transcript ledger of
  [[sources/session-20260807-fleet-findings]] §6 — a lead sheet, never a verdict sheet; this
  entry moves from lead to verified-resolved.)

## 6. The session commit chain — four commits, three register closures

`48a63610` (supervisor child-log rotation — already filed,
[[sources/session-20260807-evening-ops]]) →

**`1e7f882c` — the REST RST drain fix — closes [[synthesis/owed-measurements]] item 39, kills
the flake class.** `_deny` now **drains up to 64KB of unconsumed declared body before
responding**; `do_POST` refuses declared bodies over 1MB with **413 (REST-004, the REST log
namespace) BEFORE reading** — so the anti-smuggling property is kept (a hostile Content-Length
can neither pin the thread nor buy an unbounded read) while the close-with-unread-data TCP RST
that could destroy the in-flight response is gone. The red test reproduced the exact abort
(`ConnectionAbortedError` in `_deny`'s write). Battery **3430/0/1 in 375s — first fully clean
parallel run of the day.** This is precisely the "bounded drain-then-close" option item 39
specced, with the red-first pin it demanded. →

**`486a6891` — the three-series P&L taxonomy on the command board (boards v37) — closes item
36(a), with a correction.** Each series now carries its true name: the all-time hero tile reads
**`realized_total`**, the ring is retitled **"last 200 closes"**, and **`fees_total` gets its
own tile** — the only counter where an open leg's entry fee is visible before the close
([[sources/session-20260807-pnl-reconciliation]] §2's invisible channel, now on screen).
*Correction to the register:* 36(a)'s "realized_pnl_total is **unexported**" was wrong — the
key has been in `build_status` since the initial commit (`runner.py:1163`) and in the pusher's
ship list since `9b035996`. The true gap was **display and labeling**, which is exactly what
this commit fixes, board-generator only. →

**`915b362f`** — latency truth tier 1 (§2).

**Next-session queue unchanged: the fill-sim TTL fix (owed item 40) at the top.**

## Related
[[synthesis/owed-measurements]] · [[concepts/tautological-instrument]] ·
[[concepts/false-green]] · [[concepts/liveness-by-output-cadence]] ·
[[concepts/conscious-re-baseline]] · [[concepts/deadlock-discipline]] ·
[[concepts/never-widen-a-gate]] · [[concepts/paper-real-boundary]] ·
[[entities/reason-code-registry]] · [[entities/observability-sidecars]] ·
[[sources/session-20260807-fleet-findings]] · [[sources/session-20260807-evening-ops]] ·
[[sources/session-20260807-capacity-sweep]] · [[sources/session-20260807-pnl-reconciliation]]
