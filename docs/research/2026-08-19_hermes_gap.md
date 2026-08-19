# Adoption Ledger — Hermes plugin vs this stack (2026-08-19)

*Operator asked to improve the bot "from hermes frameworks."
Hermes (claude-code-hermes-plugin, quarantined clone at
`Documents\claude-code-hermes-plugin`) is a HARNESS-side self-learning
plugin: it upgrades Claude Code sessions, never a trading engine. Same
adjudication grammar as `2026-07-23_tradingagents_gap.md`: nothing
already shipped is re-proposed; LLM-in-engine stays REJECT; the
freeze/moratorium fence every bot-side surface regardless.*

## Verdict (plain language)

Hermes' five capabilities are all SESSION-tooling. Mapped against this
project, four already exist here in stronger, law-governed form, and the
fifth is a standing security refusal on this machine. **The bot itself
gains nothing from Hermes that its own architecture does not already do
better** — the honest improvement Hermes points at is discipline we
already wrote into law (vault filing, memory curation), not code.

## Capability map

| Hermes capability | This stack already has | Disposition |
|---|---|---|
| Trajectory Logging (per-session action log) | Bot-side: hash-chained audit + `scripts/lessons_digest.py` per-decision outcome ledger (TA-A1). Harness-side: vault `log.md` append-only timeline + USAGE.md rule 2 (findings FILED before session end) | **ALREADY AHEAD** — ours is outcome-joined and tamper-evident; Hermes' is prose |
| Memory Search | The Obsidian vault + `wiki/index.md` catalog + recall-before-derive / no-orphan-claims law | **ALREADY AHEAD** — governed recall with citation obligations, not similarity search |
| Auto-Skill Creation | `self-improving-agent` skill (installed): MEMORY.md patterns promoted to rules/skills deliberately, with review | **ADAPT (exists)** — deliberate promotion beats automatic generation; auto-created skills are unreviewed instructions executing in a harness that holds deploy authority |
| Context Compression | USAGE.md reduced-usage protocol + caveman register + the digest recent-lens work | **ALREADY PRESENT** |
| Skills Hub (pulls from agentskills.io) | — | **REJECT on this box** — remote-content channel into a harness with repo-write ⇒ battery-gated deploy authority over the live bot; trojan-via-trusted-channel, threat list item #7. Standing precedent: skills enter via audited bulk install, not live hub |

## The one transferable idea

Hermes' framing — "the session should learn as a first-class artifact" —
is worth keeping, and this project already ratified it as LAW rather
than plugin: vault governance rule 2 (file findings before scrollback
dies) and the auto-memory directory. No code to adopt; the discipline to
keep is filing fidelity.

## Bot-side note (why nothing crosses the line)

Any Hermes-inspired "self-learning" wired into the ENGINE would be a new
model-side surface (frozen, 2026-08-10 adjudication) and — if it touched
decisions — cohort-resetting (era-4 moratorium, accrual 21/50 at
filing). The lattice law also applies: the learner reads ground truth
only; no tooling layer feeds it. The door is the readout docket, same as
ALGO-5 and the NN candidacy.

## Quarantine status

Clone retained for reference, nothing installed, hub untouched. If a
session-tooling install is ever wanted: full skill-security-auditor pass
first, `CLAUDE_HERMES_SKILLS_HUB_URL` disabled, non-bot machine
preferred.
