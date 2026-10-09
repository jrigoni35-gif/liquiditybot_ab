---
title: Mythos-Router Integration (2026-08-04) — Dormant Receipts Identified, 36/36 Security False Positives Adjudicated, MCP Integration Under Write Policy
category: source
summary: "The repo's dormant .mythos/ identified as the receipt store of github.com/thewaltero/mythos-router (v1.23.0) — two verified Strict-Write-Discipline receipts from 2026-07-12; a skill-security-auditor FAIL verdict (28 CRITICAL / 8 HIGH) adjudicated finding-by-finding to ALL 36 false positives (fixed SQL literals read as injection, shell-free execFileSync read as command execution, two of its OWN security tests flagged as risks) — pattern-matching-without-adjudication now proven for security scanners; integrated as a project MCP (tooling-only, runtime never consumes MCP) under a write policy that makes never-delete-learning-data machine-enforced (BLOCK outputs/** + config.json + .git); its memory system and NVIDIA distillation blueprint deliberately NOT integrated (vault remains sole brain per governance rule 12; blueprint YAGNI). Commit b824a854 pushed, battery 3292/1 green"
tags: [session, external-systems, security, adjudication, tooling, mcp, governance]
sources: 1
updated: 2026-08-04
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [operator, claude]
ingested: 2026-08-04
---

# Mythos-Router Integration (2026-08-04)

## Provenance
Session work product — no `raw/` snapshot. Ground truth: commit `b824a854` (**pushed**;
head = remote = `b824a854`, tree clean), the `.mythos/` receipt store on disk, `.mcp.json`,
`.mythos/policy.json` (gitignored, this box), and the live `mythos runs` output listing both
July receipts PASS. Battery **3292 passed / 1 skipped, green**.

Five findings, each with a verdict.

---

## 1. DISCOVERY — the dormant `.mythos/` directory identified

The repo's dormant `.mythos/` directory is the **receipt store of
[[entities/mythos-router]]** (`github.com/thewaltero/mythos-router`, v1.23.0). It contains
**two verified Strict Write Discipline (SWD) runs from 2026-07-12** — a create and a fix of
`asset_learning_report.py` — each carrying before/after **sha256**, git context, and provider
attribution (`claude-code` / `claude-fable-5`). The sibling directory
`Documents/mythos-workspace` is the tool's **abandoned memory scaffold**: its `MEMORY.md`
log table has **zero entries**.

**Marketing caveat, filed:** the repo's tagline claims a *"leaked Anthropic reasoning
protocol."* This is **hype — no such thing exists**. The real, verifiable mechanics are
Strict Write Discipline: path validation, snapshots, hash verification, rollback, receipts.
The tool is adjudicated on what its code does, not on what its README claims.

---

## 2. SECURITY ADJUDICATION — a FAIL verdict with 36/36 false positives

`skill-security-auditor` raw verdict: **FAIL, 28 CRITICAL / 8 HIGH**. Finding-by-finding
adjudication: **ALL 36 are false positives.**

- **20 "CRITICAL"** = SQLite `Database.exec()` calls on **fixed SQL string literals**
  (`BEGIN`/`COMMIT`/`PRAGMA`) — transaction control, not code execution; nothing
  user-controlled reaches them.
- The remaining CRITICALs = `execFileSync` — the **shell-free, arg-array** process variant.
  `git.ts` is **exemplary**, not dangerous: branch-name regex validation, path normalization
  that rejects `../` and absolute paths, no shell ever invoked.
- **8 "HIGH"** included **two of the project's own security tests** flagged as risks: a
  path-traversal *assertion* and a CI guard that *forbids* npm lifecycle hooks — the scanner
  convicted the defenses for containing the attack strings they defend against.

**Independent sweeps, all clean:** no install hooks, 2 reputable dependencies, 0 npm audit
vulnerabilities, egress only to opt-in provider APIs (`surplusintelligence.ai` is an optional
4th provider, key-gated — **not telemetry**), no phone-home.

> **Lesson (extends [[concepts/iron-law-of-debugging]]): pattern-matching without
> adjudication convicts the innocent — now proven for security scanners too.** The same
> defect class as the fixture-fill and substring-path convictions: matching on surface shape
> (a string that *looks like* SQL injection, an API name that *correlates with* command
> execution) instead of the identifying structure (what is actually reachable by
> user-controlled input). A raw scanner verdict is a lead sheet, never a verdict.

---

## 3. INTEGRATED — project MCP under a machine-enforced write policy

- **Installed globally**, v1.23.0; registered as a **project MCP in `.mcp.json`** beside
  coinpaprika, under the **same tooling-only boundary: the runtime never consumes MCP**
  (unchanged from the standing [[entities/liquiditybot]] rule — MCP is for agent/dev
  tooling, never the decision cycle).
- **Write policy** at `.mythos/policy.json` (gitignored, this box):
  - **BLOCK** `outputs/**` + `config.json` + `.git` — the audit chain, ledgers, corpus, and
    guarded config are **untouchable by external write tooling**. This makes
    never-delete-learning-data ([[synthesis/governance-doctrine]] rule 8) **machine policy**,
    not just doctrine.
  - **CONFIRM** on all engine trees and scripts.
- **Verified working:** `mythos runs` lists both July receipts **PASS**.
- **Role:** receipts for **AGENT file actions**, complementing the hash-chained `audit.jsonl`
  (**ENGINE actions**). It **replaces nothing** — two provenance planes, one per actor class.

---

## 4. NOT INTEGRATED, deliberately — two rejections with citations

- **The mythos memory system — REJECT.** The vault remains the **sole brain** per
  [[synthesis/governance-doctrine]] rule 12; a **third memory store would fragment truth**.
  (The tool's own abandoned scaffold — a zero-entry `MEMORY.md` — is the empirical
  illustration of what an unmaintained second brain becomes.)
- **The NVIDIA distillation blueprint — REJECT, stays clone-only.** Safe but irrelevant:
  it is news-classification distillation, this box has no GPU infrastructure, and it
  addresses **neither geometry nor corpus** — the two things that actually bind
  ([[concepts/payoff-asymmetry]]). **YAGNI.** (Consistent with the 08-02 adjudication of the
  same blueprint as irrelevant — the rejection is now filed with its citation and binds
  future sessions per [[concepts/adoption-ledger]].)

---

## 5. STATUS

Battery **3292 / 1 green**, tree clean, head = remote = **`b824a854`**.

---

## Related
[[entities/mythos-router]] — the adjudicated external system
[[concepts/adoption-ledger]] — the four-bucket method this adjudication instantiates (third worked case)
[[concepts/iron-law-of-debugging]] — the pattern-matching-convicts-the-innocent corollary, extended to security scanners
[[synthesis/governance-doctrine]] — rule 8 now machine-enforced; rule 12 applied to reject a third memory store
[[entities/tradingagents]] — the first external-system adjudication, for contrast
