---
title: "Config solidity check — config.json verified clean (2026-08-19)"
category: source
type: source
date: 2026-08-19
summary: "config.json verified: 0 FATAL, no duplicate keys, no BOM, utf-8 clean, phantom-knob sweep clean (only the by-design `assurance` doc block); 4 standing guard WARNs catalogued, three of them readout-docket tunables."
tags: [config, config-guard, measurement]
sources: 1
updated: 2026-08-19
---

# Config solidity check — 2026-08-19

Operator asked "make sure my json file is absolutely solid." Every claim
below is a run result, not recall (zero-hallucination discipline; file
read 2026-08-19 ~01:20Z, repo HEAD d25489aa).

## Verdict: SOLID. 0 FATAL. No structural defects.

| Check | Result |
|---|---|
| Parse (strict utf-8) | OK — 121,299 bytes, no BOM, LF-only (0 CRLF), decodes clean |
| Duplicate keys (silent last-wins class) | **none** (object_pairs_hook scan, all levels) |
| `config_guard.validate` on the live file | **0 FATAL**, 4 WARN (advisory class, below) |
| Guard enforced at startup | yes — `main.py:56` imports `enforce`; FATALs raise when live |
| Load path | `main.py:115 load_config` — explicit `encoding="utf-8"`, CWD-independent |
| Phantom top-level keys (drift-register lesson, cf. stop_round_buffer_bps) | only `assurance` unreferenced — it is a description block by design, not a knob |
| `system.dry_run` | `true` |
| `system.deploy_branch` | `"main"` (the 2026-08-18 auto-deploy pin) |
| Cosmetic | no trailing newline (harmless) |

## The 4 WARNs (standing advisories, not defects)

1. `ml.era_exclusion.min_new_era_rows` 150 < overfit synthetic floor 640 —
   a 490-row window would read as machinery-validation, not market.
2. `ml.exploration.admission.budget.burst_hours` 24.0 ≠ label horizon 36.0h
   (432 bars × 5m) — capacity should mirror the horizon.
3. `order_manager.sim_fill.queue_aware=true` — verify passive fills not
   starved at live sigma/poll cadence before trusting labels.
4. `give_back.arm_gain_pct` 0.6% arms inside the 86bps break-even buffer —
   locked share of such moves is fee noise.

All four are guard-designed WARN tier (dry-run finds these; live blocks
only FATALs). Changing #1/#2/#4 touches tunables under the era-4
moratorium/freeze → readout-docket items, not tonight's edits.

## Method note

Console rendering garbled one em-dash in WARN #3's capture (cp1252
console, not file corruption — the file itself decodes clean utf-8).

Related: [[synthesis/documentation-drift-register]] (phantom-knob class),
[[synthesis/comparability-boundaries]] (era constants the config carries).
