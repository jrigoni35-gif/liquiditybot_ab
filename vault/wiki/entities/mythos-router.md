---
title: mythos-router
category: entity
summary: An external agent-tooling CLI/MCP adjudicated 2026-08-04 — its Strict Write Discipline receipts adopted for AGENT file actions under a blocking write policy; its memory system and marketing claims rejected
tags: [external, tooling, mcp, provenance, adjudicated]
sources: 1
updated: 2026-08-04
---

# mythos-router

`github.com/thewaltero/mythos-router`, **v1.23.0** — an external CLI/MCP tool whose real
mechanic is **Strict Write Discipline (SWD)**: path validation, snapshots, sha256 hash
verification, rollback, and per-run receipts for file actions taken by coding agents.

Discovered dormant: the repo's `.mythos/` directory turned out to be its receipt store,
holding **two verified SWD runs from 2026-07-12** (`asset_learning_report.py` create + fix,
before/after sha256, git context, provider `claude-code`/`claude-fable-5`). The sibling
`Documents/mythos-workspace` is its **abandoned memory scaffold** — `MEMORY.md` log table
with **zero entries**.

## Marketing vs mechanics
Its tagline claims a *"leaked Anthropic reasoning protocol"* — **hype; no such thing
exists**. The adjudication ignored the claim and graded the code: the SWD mechanics are real
and well-built ([[sources/session-20260804-mythos-router]]).

## Security adjudication — the scanner convicted, the audit acquitted
`skill-security-auditor` said **FAIL (28 CRITICAL / 8 HIGH)**; finding-by-finding review
found **all 36 false positives** — fixed SQL literals (`BEGIN`/`COMMIT`/`PRAGMA`) read as
injection, shell-free arg-array `execFileSync` read as command execution (`git.ts` is
exemplary: branch-name regex, path normalization rejecting `../` and absolute, no shell),
and **two of its own security tests** flagged as risks. Independent sweeps clean: no install
hooks, 2 reputable deps, 0 npm vulns, egress only to opt-in provider APIs
(`surplusintelligence.ai` = optional 4th provider, key-gated, not telemetry), no phone-home.
The generalized lesson lives in [[concepts/iron-law-of-debugging]].

## The verdict (adoption ledger)
- **ADOPT — SWD receipts.** Installed globally, registered as a **project MCP** in
  `.mcp.json` beside coinpaprika, **tooling-only** (the runtime never consumes MCP). Write
  policy at `.mythos/policy.json` (gitignored, per-box): **BLOCK** `outputs/**` +
  `config.json` + `.git` (never-delete-learning-data as **machine policy** —
  [[synthesis/governance-doctrine]] rule 8), **CONFIRM** all engine trees + scripts.
  Verified: `mythos runs` lists both July receipts **PASS**.
- **REJECT — its memory system.** The vault is the sole brain (governance rule 12); a third
  memory store would fragment truth. Its own zero-entry scaffold is the cautionary exhibit.
- **REJECT — the NVIDIA distillation blueprint** (clone-only): news-classification
  distillation, no GPU infra here, addresses neither geometry nor corpus. **YAGNI.**

## Role in the provenance architecture
Receipts cover **AGENT file actions**; the hash-chained `audit.jsonl` covers **ENGINE
actions**. Two provenance planes, one per actor class — **it replaces nothing**
([[entities/reason-code-registry]], [[entities/liquiditybot]]).

See [[concepts/adoption-ledger]] (third worked case) and [[entities/tradingagents]] (the
first external adjudication, for contrast: that one produced text, this one produces
receipts).
