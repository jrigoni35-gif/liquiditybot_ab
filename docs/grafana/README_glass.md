# Liquid Glass — REMOVED from Grafana (2026-08-30)

**The frosted-glass skin was deleted 100% on operator directive**, after
its CSS-injection mechanism (a Business Text panel's `afterRender` hook
appending `GLASS_RULES` to `document.head`) caused three same-day display
incidents: two black-screen reports (the style leaked across the SPA onto
non-board pages, and the stripped alert-inputs board rendered as bare skin)
and one glitching report (a `:has()`-scoping fix keyed the page theme to a
React-managed marker's mount state). Receipts: commits `51b261af`,
`b8a673ce`, `42560be0`, and the removal commit; operating history in
`.claude/skills/grafana-dashboard-architect/SKILL.md`.

## Current state

- The four boards (Command · Learning · Problems · Alert-inputs signpost)
  render **native Grafana dark theme** and carry **zero script-executing
  panels** — pure declarative JSON. The ban is pinned ONE-WAY by
  `tests/test_boards_stripped.py::test_no_panel_executes_javascript` and
  `test_glass_removal_is_total`; the allowed panel-type set in
  `tests/test_trading_dashboard.py` no longer admits any JS-capable plugin.
- What survives from the design language in Grafana is inert and semantic:
  the Apple system palette + HIG pass, applied at generation time as static
  colors in the emitted JSON.
- **The glass look lives on natively** in `scripts/glass_console.py`
  (`outputs/console.html`) — same palette, same idioms, no hack, no
  third-party plugin, no browser-executed injection.
- The **marcusolsson-dynamictext-panel** plugin is no longer used by
  anything in this repo. It can stay installed harmlessly, or the operator
  may uninstall it from the Grafana Cloud instance (Admin-only step).

## Why it can never come back the same way

Grafana Cloud sanitizes `<style>` in native text panels, so page-level CSS
can only reach a board through a plugin's script hook — i.e. arbitrary JS
running in the operator's browser, with tab-lifetime side effects on a SPA
that owns the page. Both halves of that sentence are the incident record.
A future re-skin belongs in a presentation layer that owns its own page
(the console), never in injected CSS.
