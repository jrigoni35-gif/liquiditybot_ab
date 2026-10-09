---
title: Session Identity Is Not Stable (a session is not a citation)
category: concept
summary: "Measured 2026-08-11..16 on VS Code session 3b307393: one Claude session persisted across FOUR calendar days and multiple host-process restarts while its in-context 'now' stayed frozen at 2026-08-12 — disk had moved to 2026-08-16 with 33 commits from other sessions landed unseen. SIX failure modes measured (planning around a tomorrow four days past; background monitors dead with the host while the session still awaited their notifications; MCP servers detaching mid-conversation; a user interrupt killing four investigator subagents and leaving a run with no completion record; stale out-of-order notifications; and — added 2026-08-16 by the correction pass — a silent agent that was NOT dead but merely LATE, declared dead on 0-byte outputs and no notification, then reporting ~6 minutes after the eulogy). The consequence is corpus-grade: 'a session found X' is not a citation — every filed claim carries a session identity AND a wall-clock date, and a conclusion carried inside a long-lived session is RECALL, not evidence, until it is re-derived against disk. The sixth mode adds the ATTRIBUTION rule: 'did not answer in time' and 'died' are the same observation until separated, and the vault may only record the one that was established. Standing wake protocol: re-derive clock, branch+tip and bot vitals before acting; assume every pre-gap background task is dead — but write 'unreturned', never 'dead', unless the death was observed"
tags: [governance, epistemics, sessions, delegation, provenance, recall, doctrine]
sources: 1
updated: 2026-08-16
---

# Session Identity Is Not Stable

**Operator directive, 2026-08-16** ("everything — even the fact sessions can get
mixed up — needs to be apparent to the wiki"). Binding as
[[synthesis/governance-doctrine]] rule 19.
Measured in [[sources/session-20260811-16-vscode-3b307393]].

**Boundary (domain rule 9):** everything on this page is **repo-side / host-side**.
No sim number, no venue number, no P&L claim is involved.

> A session is a **process**, not an **observer**. It has no reliable clock, no
> guaranteed continuity with its own subprocesses, and no notification that the
> world moved while it was suspended.

## The measurement

VS Code Claude session `3b307393-71c1-40a0-959d-1a1552a21cf1` persisted across
**four calendar days** (2026-08-11 → 2026-08-16) and multiple host-process
restarts. Its in-context "now" remained **2026-08-12** throughout. Disk was at
**2026-08-16**.

**Re-derived at the filing** (`git rev-list`, working tree
`C:\Users\haird\Documents\liquiditybot\liquiditybot_ab`, branch `main`):

| range `8cb56a82..c4272391` | count |
|---|---:|
| all commits | **33** |
| non-merge | 32 |
| merge | 1 |
| first-parent | **24** |

Endpoints: `8cb56a82` *fix: `_NOWIN` dict unpack untyped every sidecar subprocess
call*, **2026-08-12T18:24:10-05:00** → `c4272391` *feat: strip every board,
rebuild ONE — the liquidity board*, **2026-08-15T21:02:27-05:00**.

> **⚠️ The session's own count was "25 commits".** It matches neither derivation
> (33 all / 24 first-parent). The discrepancy is left standing here rather than
> quietly replaced, because **it is this page's own thesis firing on the page's
> own source**: a number carried inside a long-lived session is recall.
> [[concepts/no-orphan-claims]] obligation (b).

## Six failure modes, all measured in the one session

1. **Frozen clock.** The session repeatedly planned around "tomorrow's update"
   for a tomorrow that was four days past. Nothing in-context contradicted it.
2. **Background monitors die with the host, silently.** Monitors launched before
   a host restart exited (status 4) while the session continued to *expect their
   notifications*. Absence of an alarm was read as absence of an event — the
   [[concepts/false-green]] shape, with the check not merely unable to fire but
   **not running at all** (see that page, §the ninth way).
3. **MCP servers detach mid-conversation.** `MCP_DOCKER`, `coinpaprika` and
   TodoWrite tooling vanished from under running plans. A tool present at plan
   time is not a tool present at execution time.
4. **An interrupt propagates into a running workflow.** A user interrupt killed
   **four investigator subagents**, leaving a wedged run with **no completion
   record**.
   Re-derived from the primary artifact
   (`~/.claude/projects/c--Users-haird-Documents-liquiditybot-liquiditybot-ab/3b307393-.../subagents/workflows/wf_dd79a1a4-724/journal.jsonl`):
   **12 lines — 8 `started`, 4 `result`.** Exactly four agents
   (`a4ec4bab902f7c612`, `a4ac7be5a385f31f2`, `abd313aafc976fda4`,
   `ad8f71d837e8b562f`) have a `started` line and **no** `result` line.
   *(The session recorded this as "4 started and 0 result lines" — wrong shape,
   right substance. The sibling run `wf_ff7688fb-22b` shows 13 lines, 7 `started`
   / 6 `result`, one agent — `a1ae89f12d7f1c02c` — without a result.)*
   **A workflow's own journal is the completion record; the orchestrator's
   memory of "they were running" is not.**
5. **Stale, out-of-order task notifications.** Arrival order is not event order,
   and arrival is not proof of recency.
6. **A silent agent may be DEAD or merely LATE — and the difference is not
   observable from silence.** *(Added 2026-08-16 by the correction pass; this is
   mode 2's mirror and the more dangerous of the pair.)* The catch-up ingest
   launched two background verification agents, observed **no notification** and
   **0-byte output files**, concluded they had **died with the host** exactly as
   mode 2 predicts, said so in the filing, and re-derived everything itself.
   **Both agents were alive.** They reported roughly **six minutes after the
   ingest concluded they were dead** — agent A (static repo facts, 18 items, 62
   tool uses against live files/git/AST) and agent B (runtime cohort re-derivation,
   31 tool uses, `cohort_eval.py` in the repo `.venv`, window
   2026-08-16T20:43:15Z–20:48:54Z).

   **The recovery was right and the stated cause was wrong.** Independent
   re-derivation was the correct move and it reached **the same numbers the late
   agents did**, so no conclusion was harmed — only the **attribution** was false.
   That is precisely why it is filed: the error was invisible in the results and
   would have been permanent in the record.

   > **"No notification" and "the work is dead" are the SAME OBSERVATION until
   > separated.** Mode 2 licenses *presuming* death in order to act; it does not
   > license *recording* death as a finding. **Presume dead, act accordingly,
   > write "unreturned".**

   Rule: the vault records **what was observed** ("did not answer within N
   minutes"), never the **inferred cause** ("died with the host"), unless the
   death was independently established — an exit status, a journal `result` line,
   a dead PID. Mode 4 already supplies the discriminator: **a workflow's own
   journal is the completion record.** Nobody read it here.

## What this does to the corpus

> **"A session found X" is not a citation.**

Three consequences, binding:

- **Every filed claim carries a session identity AND a wall-clock date.** This
  vault's source pages already carry `authors: [session-...]` and `ingested:`;
  the rule is now explicit about *why* — a session id without a date is
  ambiguous across four days of its own life.
- **A conclusion carried inside a long-lived session is RECALL, not evidence.**
  It must be re-derived against disk before it is acted on. This is exactly
  [[concepts/no-orphan-claims]] obligation (b) and the delegated-measurement
  contract's rule (g) — **now with a measured mechanism** rather than a caution.
- **Pre-gap state is presumed dead.** Any background task, monitor, subagent or
  MCP connection that predates a gap is assumed gone until re-observed.

## The wake protocol (standing)

Before acting, at the top of any session that may have been suspended, re-derive
— never recall:

| what | how | this filing's reading |
|---|---|---|
| wall clock | `date -u` | **2026-08-16T20:25:17Z** |
| branch + tip | `git rev-parse --abbrev-ref HEAD` · `git log -1` | `main` @ `c4272391` (2026-08-15T21:02:27-05:00) |
| bot vitals | `outputs/status.json` age | `DRY_RUN` / `RUNNING`, written_at age **1.5 s** |
| | `outputs/runner.lock` mtime | 2026-08-16 15:25 local (47 B) |
| | `pythonw` process count | **10** |

*(Snapshot-stamped per the delegated-measurement contract rule (c): these are
as-of the read time above, never "current".)*

**Then assume every pre-gap background task is dead** and re-launch what is
needed rather than waiting for it — **but write "unreturned", not "dead"**
(failure mode 6). The presumption is an *operating* rule, not a *finding*. If the
death matters enough to file, establish it: check the workflow journal for a
`result` line (mode 4), the exit status, or the PID.

## Why this is governance and not a tip

The corpus's whole method is that a claim is only as good as the artifact it
was walked to. A long-lived session breaks that at the *carrier* level: the
claim is intact, the citation formatting is intact, and the world it referred to
has moved. That is the most dangerous failure this vault tracks — a claim that
*looks* sourced ([[concepts/no-orphan-claims]] §why the order matters, failure
mode 2), reached by a different road.

It also composes with [[concepts/location-not-magnitude]]: delegated agents are
reliable for pointers and unreliable for numbers, **and** the orchestrator's own
numbers decay with session age. The re-derivation obligation lands on the
orchestrator either way.

## Related

- [[synthesis/governance-doctrine]] — rule 19
- [[concepts/no-orphan-claims]] — rule 18; obligation (b) is this law applied to the wiki
- [[concepts/location-not-magnitude]] — the delegation half of the same problem
- [[concepts/iron-law-of-repair]] — rule 20, filed the same day: an unstated protocol is an
  absent protocol, and a protocol carried in session memory is **recall**, not law. Its
  optimization carve-out is **TEMPORARY (active 2026-08-16)** — this page's own thesis applied
  to a governance page: a suspension that a later session inherits as settled is a stale claim
  with the citation formatting intact.
- [[concepts/false-green]] — silence from a dead watcher is not a green; and the
  **third polarity** of that page's discriminator, filed 2026-08-16 from failure
  mode 6: *no output* vs *no output **YET***
- [[sources/session-20260811-16-vscode-3b307393]] — the session this is measured on
- [[concepts/zero-is-not-a-reading]] · [[concepts/adversarial-verification]]
