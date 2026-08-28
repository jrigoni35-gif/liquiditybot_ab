# Token-efficiency research pass — 2026-08-27

Graded literature harvest on LLM token/spend reduction, mapped onto THIS environment's
real levers only (rtk, skill catalog, instruction files, agent tiering, cache discipline,
structured outputs, output-length discipline). No repo decision-path code is touched by
anything here — all candidate changes are measurement/config plane (SAFE class), several
gated on operator signoff. Deliverable = `07_implementation_plan.md`.

Evidence register: numbers below each page are the papers' claims at their stated scope.
Per house rules, no paper percentage is adopted as a local expectation — every plan item
carries its own before/after measurement.

## Status

| # | Page | Source | Status | Applies here? |
|---|------|--------|--------|---------------|
| 01 | [01_tale.md](01_tale.md) | TALE, arXiv:2412.18547 (ACL 2025 Findings) | FOUND | EP route yes (prompt-level); PT route NOT APPLICABLE (fine-tuning) |
| 02 | [02_be_token.md](02_be_token.md) | Behavior-Equivalent Token, arXiv:2511.23271 | FOUND | NOT APPLICABLE (embedding access); analogues: cache + catalog trim |
| 03 | [03_dsm.md](03_dsm.md) | DSM conversation clustering, DSM 2024 / arXiv:2410.00749 | FOUND | Principle yes (partition+sequence fan-outs); algorithm no |
| 04 | [04_msifr.md](04_msifr.md) | MSIFR in-flight rejection, arXiv:2605.14062 | FOUND | Pattern yes (mid-trajectory agent checkpoint); magnitudes unvalidated |
| 05 | [05_skillreducer.md](05_skillreducer.md) | SkillReducer, arXiv:2603.29919 | FOUND | Directly (skill-catalog trim + progressive disclosure) |
| 06 | [06_harvest_survey.md](06_harvest_survey.md) | Survey: caching / Self-Route / compression / compaction / structured output / batch | SURVEY | Caching, batch, output discipline yes; LLMLingua-class NO (fails agentic) |
| 07 | [07_implementation_plan.md](07_implementation_plan.md) | — | **DELIVERABLE** | Ranked permanent injections w/ verify-by-measurement |

## MEASURED BASELINES (snapshot 2026-08-27, this session — cite as-is, do not re-derive)

- rtk (Rust Token Killer bash-output proxy, hook-installed): lifetime 5,008 commands, 125.6M tokens saved, 99.0% efficiency; dominated by 'rtk read' (124.6M); 'rtk grep' averages only 23.9% savings.
- Always-loaded instruction files: 33,488 bytes total (~9-10k tokens per request, every request): user CLAUDE.md 18B (imports), RTK.md 990B, USAGE.md 10,038B, project CLAUDE.md 14,307B, MEMORY.md 8,135B.
- Skill catalog: 8 user + 15 project skill dirs, BUT the per-request system-prompt skill LISTING carries ~80+ entries (sc:* ~30, superpowers ~15, artifact/design/etc) — a previously-measured ~42k tokens/request toll class (memory: claude-skills-install, re-trimmed 2026-08-20, has since re-grown via plugins).
- Session model: Fable 5 at $10/$50 per 1M in/out; cache read ~0.1x; 1h cache TTL active. Agent-spend tiering law already in force (USAGE.md rules h-m). Deferred tool schemas already active (ToolSearch). Caveman output mode already default.
