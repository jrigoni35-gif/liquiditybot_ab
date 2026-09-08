# Skills provenance

Source: https://github.com/obra/superpowers (plugin "superpowers" v6.1.1, MIT, Jesse Vincent)
Installed: 2026-07-07, project scope, SKILL folders only.
NOT installed: SessionStart hook (hooks/), plugin manifest (.claude-plugin/),
maintainer scripts (scripts/), other-platform dirs, tests/.
=> No auto-run hooks, no settings.json changes. All skills are opt-in via the Skill tool.

---

Source: https://github.com/agiprolabs/claude-trading-skills (MIT, AGIPro)
Skill: market-microstructure @ 981e1d7 (2026-09-02). Installed 2026-09-08,
project scope, vendored unmodified with LICENSE.md and PROVENANCE.md.
Read-only analysis methodology (trade classification, buy/sell pressure,
wash-trading screen). Scripts optionally need `httpx` (not a repo dependency;
`--demo` mode works without network). No hooks, no settings changes.
