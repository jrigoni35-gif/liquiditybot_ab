# Pre-move backup — 2026-10-09 (PC going offline for a house move)

COLD BACKUP. Nothing reads this branch automatically (corpus_sync only reads
paper-telemetry). Restore by hand, deliberately.

| path | what | restore |
|---|---|---|
| `bundle/` | session_export of the learning data at 2026-10-09T20:48:05Z: signal_history.csv (38,668 rows: 38,111 candidate + 557 live), equity, fills, retrain history, checkin log, digest, served meta_model.json, ... | `python scripts/session_import.py --src bundle` (review), then `--apply` |
| `bundle/audit.jsonl.gz` | hash-chained audit trail, gzipped because GitHub refuses files > 100 MB (123 MB raw) | `gunzip`, check against `audit.jsonl.sha256`, rename to `audit.jsonl` before import |
| `extra/models/` | every model artifact + `registry.jsonl` (champion lineage) | copy into `outputs/models/` |
| `extra/state/` | state.json / fills / trade_paths snapshot — the PAPER book | only into a STOPPED bot; never next to a running one (forks the book) |
| `extra/darkpool_v2.duckdb` | the dark-pool mirror (static, newest week 2026-06-26) | `outputs/darkpool/` |
| `vault/` | the Obsidian llm-wiki (not a git repo anywhere else) | copy to `Documents/liquiditybot/vault` |
| `claude-config/` | Claude memory + global CLAUDE/USAGE/RTK (no settings, no credentials) | `~/.claude/...` |
| `repo-untracked/` | the last fill-hazard report written to the old path | `docs/quant/` |

NOT here, by size: `outputs/recordings/` (11 GB order-book recordings), `ticks/`,
`reports/`, logs — they stay on the PC's disk. Secrets (.env / API keys) are
deliberately absent: keep them in your password manager.

Why the hourly backup stopped: since 2026-10-05 19:32 every sidecar push was
rejected — the bundle's audit.jsonl crossed GitHub's 100 MB per-file limit.
