# Duplicate-runner double exit — one position closed twice by two live processes (2026-09-15)

**Class:** decision-path defect, measured. **Fix class:** COHORT_RESETTING (order lifecycle) AND
adjacent to hard invariant 5 — **operator adjudication, nothing shipped.** Two SAFE instrument gaps
ride along (§6). Method: `systematic-debugging` Phase 1-2 (root cause + pattern), no fix proposed.
Every number below is as-of its stated read; re-derive, never recall.

## 1. What happened, in plain English

On 2026-09-10 at 06:58 UTC the bot sold the same PAXG position twice, three seconds apart, with two
different orders. Two copies of the bot were running at once: an older one that had just lost the
single-instance lock, and a newer one the supervisor had launched 3.5 minutes earlier which restored
the same open position from the snapshot. Both saw the position's 36-hour deadline had passed, and
both exited it. The older copy did this **after it already knew it had lost the lock**, because the
bot is built so that faults never block an exit (hard invariant 5) — a rule that assumes the process
still owns the position. A duplicate doesn't.

In paper mode the simulator filled both sells, so the only damage was a phantom **+$86.64** of gross in
`outputs/fills.csv` on that trip (the second sell has no matching buy). **In live mode the second sell
would be a naked sale of the full position size.**

This is rare — **1 trip in 533 closed, all eras** — and it is the measured cost of a design choice the
repo already documents (`runner.py:424-428`).

## 2. The trip

`outputs/fills.csv`, read 2026-09-15T04:14Z (mtime 00:42:45Z), position `0526a410-e748-455b-a962-626f28e12489`:

| ts (UTC) | purpose | side | size | price | order_id | reason |
|---|---|---|---|---|---|---|
| 09-08 18:56:11 | entry | buy | 0.019593 | 4375.86 | 5aefad5d | |
| 09-10 06:58:55 | exit | sell | 0.019593 | 4422.14 | **6daedca4** | tb_time |
| 09-10 06:58:58 | exit | sell | 0.019593 | 4422.12 | **bc34b1bf** | tb_time |

Exit size = 2.00 × entry size; two distinct order ids; 3.3 s apart. Full-range scan of all 1,321 legs:
this is the **only** closed trip with exit size > 1.02 × entry size.

## 3. The audit trail shows two writers, not one

`outputs/audit.jsonl`, read 2026-09-15T04:16Z. Sequence numbers **repeat** with different timestamps
and different `prev` hashes — the signature of two processes appending with independent counters:

```
seq=85257 06:39:48.727Z CG-000  boot A   {config_sha256 ebbd0a85369dfc71, starting_capital_usd 800}
seq=85260 06:55:06.563Z CG-000  boot B   {config_sha256 ebbd0a85369dfc71, starting_capital_usd 800}
seq=85264 06:58:48.155Z CV-000                      prev=b5bbd2206a  <- chain B
seq=85265 06:58:49.395Z LB-010                      prev=1bb6821c74  <- chain B
seq=85264 06:58:55.881Z FT-020  lock-lost latch     prev=5c977b86b2  <- chain A
seq=85265 06:58:56.178Z OM-000  exit 6daedca4 sell  prev=5c0ffce888  <- chain A  (0.3 s after FT-020)
seq=85266 06:58:56.366Z PT-061  close #1            prev=fc6cc180e5  <- chain A
seq=85266 06:58:58.938Z OM-000  exit bc34b1bf sell  prev=a0570a7b1d  <- chain B
seq=85267 06:59:00.633Z PT-061  close #2            prev=f1b731a797  <- chain B
seq=85267 06:59:05.619Z RT-010  duplicate forfeited prev=deff62e2b7  <- chain A  {pid 19160}
```

Both boots carry the live bot's signature (`starting_capital_usd 800`, the production `config_sha256`),
so this is **two live runners**, not a QA harness. Process A latched `FT-020` at :55.881, **submitted
its exit 0.3 s later**, and forfeited (`RT-010`) 9.7 s after that. Process B, resumed from a snapshot
that still held the position open, exited it independently at :58.938. Both `PT-061` rows carry a
full-size `net_usd` (0.475365 / 0.474974).

That morning had **six** live boots between 04:44Z and 06:55Z (a relaunch storm); `FT-010` fired at
06:48:40 on chain A.

## 4. Root cause, from the code

- **Within one process this cannot happen.** `fast_cycle` drains fills at `main.py:2886-2897`
  (`orders.poll()` → fill events → `_finalize_position` → `state.remove_position` at `:1866`,
  unconditional) *before* the per-position stop loop at `:3013`. A position whose exit filled is gone
  before it can be re-evaluated. The hypothesis "no exit dedup guard" was **refuted by reading**:
  `_submit_exit` (`main.py:2453-2465`) returns if a **resting** exit exists for the position.
- **Across two processes the guard is blind.** Process B's `OrderManager` has no record of process A's
  order; process B's snapshot has the position open; the time-stop is a **level** condition with no
  latch (`main.py:3419`: `now >= pos.bracket_deadline_ts`) and fires on every evaluation.
- **The losing process keeps running the full cycle after it knows it lost the lock.**
  `runner.py:1636-1641`: on the *first* lost heartbeat, `_lock_lost_latched = True` →
  `_note_lock_lost()` → `FT-020`; the comment says verbatim *"Seal NEW risk now; exits keep running
  (invariant #5)."* `runner.py:1642-1663`: only when `self._lock.forfeited` — after
  `LOST_LIMIT = 3` consecutive lost refreshes (`core/runtime.py:300`) — does the loop `break`. On the
  same iteration as the latch, `runner.py:1696-1700` still calls `bot.cycle_once(now)`, whose stop
  loop submitted the exit. The comment at `:1644-1647` names the hazard — *"staying would race
  snapshots and eat its control commands"* — but scopes it to snapshots and commands, not exits.
- **Window:** up to `LOST_LIMIT × hb_sec` = 3 × 5 s ≈ 15 s, measured 9.7 s here. Any position at an
  exit condition inside that window is exited by both processes.

`allow_new_risk()` gates entries only: `main.py:3096` (hedge open), `:4546` (5m entry sweep),
`:5342` (long-book add). `fast_cycle` at `:2760` has no lock or fault check by design.

## 5. Exposure

`outputs/audit.jsonl`, full range, read 2026-09-15T04:17Z: span 63.7 days, **103** live boots,
**FT-020 × 469** (lock-lost latch), **RT-010 × 10** (a duplicate actually forfeited: 07-16, 07-27,
08-17, 09-08, and **six on 09-10**). So the latch is ~98% false alarms (heartbeat stalls that recover —
the C1 history in `runner.py`), and there have been ten true overlap windows. One of the ten coincided
with a position at its deadline. Era-9 alone has had 13 restarts (measured 2026-09-15).

## 6. The trade-off, stated so the operator can decide it

The code's choice — keep managing exits through a lost heartbeat — is defensible: forfeiting on the
first miss would kill a healthy process ~460 times in 64 days and leave the book unmanaged for the
~2-minute supervisor relaunch each time. The cost of the choice is a double exit in the ~2% of latches
that are real duplicates. **Options, none applied:**

1. On `_lock_lost_latched`, skip the exit loop (not the heartbeat) until the lock is re-acquired or
   forfeited: ≤15 s unmanaged in the false-alarm case; no double in the true-duplicate case. **This
   narrows invariant 5** ("exits are ALWAYS allowed") to "…by a process that owns the book" — a law
   change, which is why it is not shipped.
2. Cross-process exit dedup: an exit-intent marker under `outputs/` checked before `_submit_exit`
   submits. Heavier; touches the order lifecycle.
3. Accept: 1 in 533 in paper; document and monitor `RT-010`.

Whichever is chosen mints or does not mint a boundary; the operator owns it.

**SAFE instrument gaps (no decision path):**
- `scripts/disposition_integrity_report.py` has no check for two `PT-061` rows on one `position_id`
  (needle grep: 0 hits for `PT-061|double|duplicate|twice`). A double close is invisible to the
  integrity tool.
- `scripts/cohort_eval.py:330-331` silently `continue`s any trip whose exit size differs from its entry
  size by >2% — not fooled by this trip, but it reports no count of what it dropped.
- The duplicate-seq / forked-`prev` signature in `audit.jsonl` is the fastest test for "were two
  processes alive" and nothing prints it; `FT-020` is not that signal (469 vs 10).

## 7. What this record could not see

No pytest/battery/smoke was run (live runner on the box). The 09-10 relaunch storm's cause (six boots
in two hours) was not investigated. Whether `verify_chain` flags the two-writer fork is open
(HANDOFF IJ-07 arm c). The mechanism is read from source and corroborated by one audit sequence; no
in-situ reproduction was attempted, because reproducing it means running two live runners.
