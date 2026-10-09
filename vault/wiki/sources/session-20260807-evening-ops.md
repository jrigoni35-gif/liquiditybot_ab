---
title: "The Rotation Deploy and the Local-Commit Blind Spot (2026-08-07 evening) — Five Ops-Plane Findings"
category: source
summary: "Commit 48a63610. Five confirmed findings on the ops plane: (1) supervisor child-log rotation shipped AND verified live within 15 minutes (19:49:32 'rotated runner.log (64MB cap)'; the 153.8MB runner.log archived on disk) — owed item 38(b) CLOSED; (2) the auto_update local-commit blind spot — locally-authored commits never bounce the runner (decide() 'current'/'ahead' paths return with the runner untouched; only externally-pushed commits reach _signal_restart), while pushers bounce on ANY rev change — committed is not deployed on this box; (3) the recurring test_audit_security flake root-caused as the REST _deny RST class — _deny closes the socket with the POST body unread (deliberate anti-smuggling choice, ab76cdfb), and close-with-unread-data aborts via TCP RST that can destroy the in-flight response; survived the 30s-timeout fix, which is what ruled timeout out; fix owed, not shipped (item 39); (4) the fee-ledger write topology verified at file:line — ONE lifetime counter fees_total with exactly TWO writers (entry legs main.py:1935, exit legs main.py:1980); fees_total is the ONLY complete fee ledger, validating the money-path fee identity; (5) the venv shim process pairs verified live — every supervised logical process is TWO pids (shim -> base interpreter), the supervisor tracks the shim while runner.lock names the base, and the pusher bounce kills both halves only by accident of command-line propagation."
tags: [session, deploy, observability, supervisor, rotation, auto-update, rest, fees, venv, windows]
sources: 1
source_path: none — session work product (evening ops session after capacity-sweep round 1)
source_date: 2026-08
authors: [claude]
ingested: 2026-08-07
updated: 2026-08-07
---

# The Rotation Deploy and the Local-Commit Blind Spot (2026-08-07 evening)

## Provenance and boundary statement

Commit **`48a63610`**, 2026-08-07 **19:34:27 −0500** (= 2026-08-08 **00:34:27Z** — zone-stamped
per domain rule 9). The session that followed [[sources/session-20260807-capacity-sweep]] round 1
the same evening. Battery on the shipped tree: **3427 passed / 1 failed / 1 skipped in 400.57s**
(`-n 8` parallel); the one failure IS finding 3 below.

**Paper/real boundary** ([[concepts/paper-real-boundary]]): findings 1, 2, 3 and 5 are
**repo-side / box-side** — process supervision, deploy plumbing, test harness. Finding 4 is the
**write topology** of the fee ledger (repo-side); every dollar that flows through it is
**sim-side** (config-constant fees the institutional review falsified against Kraken's schedule —
[[synthesis/owed-measurements]] item 37(a)). Nothing here moves the standing question's four
quantities.

---

## 1. Child-log rotation shipped AND verified live — owed item 38(b) CLOSED

The capacity sweep measured `outputs/runner.log` at **153.8 MB with no rotation anywhere** and
deferred the fix (item 38(b)). `48a63610` shipped it the same evening:

- **Mechanism:** the supervisor opens the child log append-mode at each spawn and the child holds
  the handle for life — **Windows refuses to rename an open file**, so the only moment a rotation
  can succeed is the gap between a child's death and its respawn. `_spawn` now calls
  `_rotate_child_log` immediately before re-opening (`scripts/pc_supervisor.py:208-260`).
- **Caps:** `LB_CHILD_LOG_MAX_MB=64`, `LB_CHILD_LOG_KEEP=2` — sized against the **measured
  ~7 MB/day** growth: ~9 days/generation, **~3 weeks retained**, the window this month's incident
  investigations actually needed.
- **Best-effort by contract:** a lingering handle skips rotation and appends — an unrotated log
  is an inconvenience, an unspawned runner is an outage. `gc_log_pusher._drain_rotated` (the 29g
  work) already consumes renames losslessly. 5 tests red-first.

**The live verification, 15 minutes after commit** — this is the part that makes it a fact rather
than a shipped shape (domain rule 5):

```
pc_supervisor.log  2026-08-07 19:49:32  rotated runner.log (64MB cap)
                   2026-08-07 19:49:32  runner stale/absent -> relaunching
```

On disk at filing time: `runner.log.1` = **146.86 MiB** (= **~154.0 decimal MB** — the same file
the sweep measured at 153.8 MB; MiB-vs-MB, not shrinkage), last write 19:47:16; fresh
`runner.log` = 0.04 MiB and growing. The archive exists, the live log is new, and the pusher's
rotated-drain had already been proven lossless. **Rotation worked on the first real spawn
boundary after deploy.** (The supervisor got its own new code via its documented
source-change self-restart; what put the runner through a spawn boundary at 19:49 was its
stale/absent relaunch — the rotation evidence stands either way.)

## 2. The auto_update local-commit blind spot — committed is not deployed

`48a63610`'s own commit message says *"Deploys via the normal auto_update bounce."* **That
sentence is false for every locally-authored commit**, and today's `auto_update.log` shows both
sides of the asymmetry in one afternoon (times −0500):

```
13:53:34  1 new commit(s) on main - testing the incoming code first     <- EXTERNAL push
14:02:34  incoming-code battery rc=0: 3423 passed, 1 skipped in 536.90s
14:04:16  updated 9b1eb6a5 -> cf454d5e (battery-verified)
14:04:16  sent stop - supervisor will relaunch on the new code           <- runner bounced
19:24:03  already up to date                                             <- LOCAL 101f7436
19:24:06  pushers bounced for rev 101f7436
19:39:04  already up to date                                             <- LOCAL 48a63610
19:39:06  pushers bounced for rev 48a63610                               <- runner NOT bounced
```

**Mechanism, named at file:line** ([[concepts/iron-law-of-debugging]]):
`scripts/auto_update.py`'s `decide()` (lines 114-146) routes local==remote to `'current'` and
local-ahead to `'ahead'` — both paths return with **the runner untouched** (lines 499-505:
*"nothing to deploy, runner untouched"*). Only the remote-ahead `'test'` path reaches
`battery → ff → _signal_restart()` (line 549). Meanwhile `_ensure_pushers_current()` (lines
413-447) bounces the **telemetry sidecars** on ANY head change via the `pushers_code_rev.txt`
marker. So a locally-authored commit produces a box where **the pushers run the new code and the
runner runs the old code**, indefinitely — until an external push, a manual bounce, or (for
`pc_supervisor.py` changes only) the supervisor's own source-change self-restart.

`48a63610` deployed **only because its one shipped file WAS `pc_supervisor.py`** — the single
file with a self-restart path. Any engine-file commit authored on this box has **no automatic
deploy path at all**. This sharpens the standing entity-page claim (*"local-ahead commits bypass
the battery and the code is already live"*): they bypass the battery **and the bounce** —
**committed ≠ running**. The by-design halves are deliberate (never battery-test your own
just-written commit into a self-brick; never rollback-bounce on 'ahead'); the blind spot is that
**nothing closes the loop later**. Filed to [[synthesis/documentation-drift-register]] (a
commit message stale at commit time, the 08-06 class) and [[entities/auto-update]].

## 3. The REST `_deny` RST class — root cause named, fix owed (item 39)

The battery's one failure: `tests/test_audit_security.py::test_control_refuses_html_form_text_plain_post`
— **while the harness captured the server's own log firing the refusal correctly**:

```
WARNING liquiditybot.api.rest:rest_server.py:196 REST-003: /control refused,
        Content-Type 'text/plain;charset=UTF-8' is not application/json
```

The server refused exactly as designed; the **client side** of the harness still failed. And it
failed **at the 30-second client timeout shipped hours earlier** (`00bd0e52` — which fixed the
`hdrs3` cross-site case's load-starved 5s window) — **recurrence past the timeout fix is what
rules the timeout class out.**

**Root cause, named:** `_deny` (`api/rest_server.py:109-121`) answers and then closes the
connection **with the refused POST's body still unread** — a *deliberate* choice from the
2026-08-01 audit (`ab76cdfb`): on a keep-alive connection the unread body would be parsed as the
next request line, so *"close instead of draining attacker-chosen bytes"* (anti-smuggling).
But closing a socket with unconsumed data in the receive buffer aborts via **TCP RST**, and an
RST can destroy the client's in-flight, not-yet-read response. Under `-n 8` scheduler saturation
the client's read window widens and the race intermittently lands: the refusal fires server-side,
the 415 body dies in transit, the harness sees a connection error. **One hazard's fix (request
smuggling) created a different, rarer failure (response-destroying RST) — visible only under
parallel load.**

**Status: OPEN.** Root cause named per the Iron Law; no fix chosen or shipped — the decision
(bounded drain-then-close vs harness-side RST tolerance, plus a red-first pin either way) is
filed as [[synthesis/owed-measurements]] **item 39**. Production exposure: the server is
loopback-only, refusals are correct and logged — this is a **harness-plane flake**, not an
engine defect. It is also not [[concepts/false-green]]: it fails red, honestly; the hazard is
alarm fatigue teaching operators to shrug at test_audit_security.

## 4. The fee-ledger write topology — `fees_total` is the ONLY complete fee ledger

File:line verification of where every fee dollar lands, extending
[[sources/session-20260807-pnl-reconciliation]]'s three-series reconciliation with the write
topology under it:

- **One lifetime counter:** `state.fees_paid_total` (`core/state.py:168-170`), surfaced as
  snapshot key `fees_total` (`runner.py:1154`), shipped to Grafana via the `gc_pusher.py:250`
  whitelist.
- **Exactly TWO writers, both in `main.py` fill handling:**
  - **Entry/open legs** (hedge opens included): `main.py:1935` `record_fees` **paired with**
    `main.py:1936` `record_entry_fee` — the cash-only debit that enters **NO P&L series**
    (the −157.84 channel of owed item 36(b)).
  - **Exit legs:** `main.py:1980` `record_fees`, alongside `pos.fees_paid_usd` accrual
    (`main.py:1979`) and net settlement into realized.
- **The resulting taxonomy** (which counter sees which legs):

| Series | Entry/open legs | Exit legs |
|---|---|---|
| `fees_total` | ✔ | ✔ — **the only complete ledger** |
| realized / daily / weekly | ✘ | ✔ (netted) |
| perf-ring nets | ✔ pro-rata (`main.py:1955-1971`) | ✔ — a third fee basis |
| cash / equity | ✔ (`record_entry_fee` debit) | ✔ (net settlement) |

**Why it matters:** [[synthesis/the-money-path-thesis]]'s fee identity — the book's entire
drawdown is fees (−384.67 equity vs 382.28 `fees_total`, ~flat on price) — compares equity
against **the one counter that actually sees every leg**. The topology verifies that comparison
is well-founded rather than luckily right. Every dollar named here is **sim-side**
(config-constant fees; the constants themselves falsified, item 37(a)).

## 5. The venv shim process pairs — one logical process, two pids, verified live

Live process table at filing time (`Win32_Process`, command lines matching the bot):

| Logical process | shim pid → base pid |
|---|---|
| pc_supervisor | 9268 → 13496 |
| runner.py | 19740 → 23020 |
| gc_log_pusher | 22280 → 19696 |
| gc_trace_pusher | 23404 → 24280 |
| gc_pusher | 8144 → 22560 |

**10 OS processes = 5 logical processes.** On Windows, the venv's `pythonw.exe` is a redirector
that spawns the base interpreter as a **child with an identical command line** — every
supervised process is a pair. `scripts/pc_tidy.ps1:195` documented this as "normal" on 07-30
(`2873bb19`); today's table is the live confirming measurement, with the sharp consequences now
stated:

1. **Two authorities track different halves.** The supervisor's `Popen` child is the **shim**
   (runner = 19740); `runner.lock` names the **base interpreter** (`{"pid": 23020}`, heartbeat
   live at filing) because `os.getpid()` runs there. Neither is wrong; they are different pids
   for one logical process, and any tooling that compares them naively will conclude the lock
   is stale.
2. **The force-kill path targets the base, not the pair.** `auto_update._force_kill` runs
   `taskkill /F /PID <lock pid>` **without `/T`** — it kills the base interpreter and leaves the
   shim to reap and exit on its own. Safe today (the shim's only job is waiting), and
   `_pid_is_runner`'s identity check works on **either** half because the shim propagates the
   command line — the same propagation that makes `_ensure_pushers_current`'s
   commandline-matched `Stop-Process` kill **both** halves. Pair-safety is currently an
   **accident of command-line propagation**, not a stated contract.
3. **The rotation contract's "held handle" is a pair property.** The spawn-time stdout handle is
   inherited down the pair, so the rename window requires **the whole pair** gone — one more
   reason `_rotate_child_log` is best-effort by contract (finding 1), and the reason a
   half-dead pair would read as a lingering handle rather than a rotation opportunity.

Any future pid-count liveness probe, kill escalation, or "how many bots are running" check on
this box must expect **2 pids per logical process**.

---

## What this session changes

- **Closes:** owed item 38(b) (rotation) — shipped AND live-verified same evening.
- **Opens:** owed item 39 (the `_deny` RST class fix decision + pin).
- **Corrects:** the auto-update entity page's "the code is already live" phrasing; adds a
  drift-register row for `48a63610`'s "normal auto_update bounce" claim.
- **Verifies:** the fee identity's foundation (topology) and the shim-pair operational model.

## Related
[[sources/session-20260807-capacity-sweep]] · [[entities/auto-update]] ·
[[entities/observability-sidecars]] · [[sources/session-20260807-pnl-reconciliation]] ·
[[synthesis/the-money-path-thesis]] · [[synthesis/owed-measurements]] ·
[[synthesis/documentation-drift-register]] · [[concepts/paper-real-boundary]] ·
[[concepts/iron-law-of-debugging]] · [[concepts/false-green]] ·
[[concepts/liveness-by-output-cadence]] · [[entities/liquiditybot]]
