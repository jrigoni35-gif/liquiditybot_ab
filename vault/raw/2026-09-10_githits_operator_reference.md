# RAW — operator-flagged reference, 2026-09-10: GitHits

Filed VERBATIM before any relevance assessment, per the standing operator
directive of 2026-09-07 ("Stop and include this no matter what"). Nothing in
this file is adjudicated; the assessment lives in
`wiki/sources/githits-evaluation-2026-09-10.md` and is PROVISIONAL.

## 1. What the operator pasted, verbatim

```
GitHits
Community
Trending
Version-aware index of open-source dependencies for Claude
```

No URL accompanied the paste. Context: it arrived immediately after a exchange
about Skills added in the claude.ai web UI that were not present on this
machine's filesystem, so the operator's intent may be "this is the source" or
"look at this" — NOT DETERMINED, do not infer.

## 2. Web search result, verbatim (2026-09-10, WebSearch)

Query: `GitHits version-aware index of open-source dependencies for Claude`

Links returned:

- https://github.com/githits-com — "GitHits · GitHub"
- https://www.producthunt.com/products/githits — "GitHits beta 0.9: Give your
  AI coding agent access to open-source code | Product Hunt"
- https://github.com/githits-com/githits-cli — "Command Line Interface for the
  GitHits"
- https://docs.githits.com/introduction — "What is GitHits? - GitHits"
- https://githits.com/ — "GitHits - Version-aware index for public open-source
  code and packages"
- https://www.claudepluginhub.com/plugins/githits-com-githits-2 — "githits -
  Claude Code Plugin"
- https://githits.com/the-index/ — "The Index — GitHits"
- https://githits.com/blog/what-it-actually-takes-to-index-open-source/ —
  "What It Actually Takes to Index Open Source | GitHits"

Search-engine summary as returned (these are VENDOR/THIRD-PARTY claims relayed
by the search tool, not measurements by this session):

> GitHits builds a version-aware index of open-source code, package internals,
> documentation, dependency graphs, vulnerabilities, changelogs, and package
> upgrade changes so agents can retrieve and navigate the actual code running
> in the stack.
>
> GitHits indexes open-source code, documentation, and package data by version,
> then exposes tools for code navigation, package inspection, vulnerability
> checks, changelog and upgrade review, and prior art. It builds a
> version-aware index of open-source code on demand, usually in 10-20 seconds
> for an average repository.
>
> It installs the CLI and connects GitHits to Claude Code, Codex, Cursor, or
> any MCP-compatible agent. GitHits runs as an MCP server that your AI
> assistant connects to over stdio.
>
> The assistant decides when to call these tools on its own — typically when
> it's stuck, needs a working example for an unfamiliar API, or encounters an
> error it can't resolve from its training data alone.

## 3. What this session did NOT do

- Did not fetch any githits.com page.
- Did not install the CLI, the plugin, or the MCP server.
- Did not probe any endpoint, so NOTHING above is corroborated by runtime.
- Did not establish pricing, auth requirements, telemetry behaviour, or what
  the MCP server transmits off-box.

Every claim in §2 is `[UNVERIFIED — vendor claim relayed by a search engine]`.
The `pyth-evaluation-2026-08-30` precedent on this exact shape: a vendor's
"no auth" claims were REFUTED by runtime probe after reading suggested
otherwise. Read that page before trusting anything here.

---

## 4. ADDENDUM — operator paste #2 (same day), verbatim

```
GitHits connects Claude to a fast, version-aware index of open-source code,
documentation, package intelligence, and implementation examples.

Use GitHits to:

• Search, navigate, grep, and read exact source files in packages and repositories
• Search and read package documentation
• Inspect versions, licenses, dependencies, vulnerabilities, changelogs, and upgrade evidence
• Find implementation examples and prior art across open-source projects

GitHits helps Claude work from source evidence for the dependency versions in
use instead of relying on stale training data or brute-forcing answers with
tools not designed for dependency research.

GitHits indexes the open-source ecosystem you app depends on — not your local workspace.

Tools
code_files
code_grep
code_read
docs_list
docs_read
feedback
get_example
pkg_changelog
pkg_deps
pkg_info
pkg_upgrade_review
pkg_vulns
search
search_language
search_status
```

## 5. RUNTIME PROBE — 2026-09-10, and it refutes part of the above

MCP `initialize` + `tools/list` + `tools/call` over stdio against the pinned
build `githits@0.16.1`. This is a MEASUREMENT; §2 and §4 are readings.

- `initialize` -> OK. serverInfo `{name: githits, version: 0.16.1}`,
  protocol `2024-11-05`.
- `tools/list` -> OK **UNAUTHENTICATED**, 15 tools:
  `code_files, code_grep, code_read, docs_list, docs_read, get_example,
  pkg_changelog, pkg_deps, pkg_info, pkg_upgrade_review, pkg_vulns,
  quick_start, search, search_language, search_status`
- **`feedback` is NOT present. `quick_start` IS.** The operator paste in §4
  lists the opposite pair. The docs page (§2 lineage) matched the probe. The
  §4 list therefore describes a DIFFERENT surface — plausibly the web
  connector or the plugin-hub listing — which is `[UNVERIFIED]`; it is not
  this stdio build.
- `pkg_info(registry=pypi, package_name=numpy)` -> `isError=true`,
  `{"error":"No local GitHits authentication token found.",
    "code":"AUTH_REQUIRED","retryable":false}`
- `pkg_vulns(registry=pypi, package_name=numpy)` -> same `AUTH_REQUIRED`.

**Shape:** catalog free, every data call gated — the same shape the pyth
evaluation refuted, except GitHits states the login requirement up front
rather than implying otherwise. The server is INERT until `githits login`.

**Lesson, filed against this session's own interest:** the tool-list
correction was written into `.mcp.json` BEFORE the probe ran, on the strength
of a pasted list, and it was wrong. the-method #1 — the instrument is the
first suspect, and an operator paste is an instrument.

## 6. SUPERSEDED — 2026-09-10 ~22:39Z, after a CLI update and a restart

§5's `AUTH_REQUIRED` result was true when measured and is now **superseded by
events**, not by re-reading. Recorded rather than edited away, because the
sequence is the finding.

What changed between §5 and here: Claude Code was updated 2.1.251 -> 2.1.268,
the operator restarted, and a GitHits browser login was performed.

- `githits doctor`: `Auth storage mode: keychain`; the file-storage `token` is
  `unset/missing` while `metadata.json` EXISTS — i.e. the credential is in the
  Windows Credential Manager, not on disk. `GITHITS_API_TOKEN` unset.
- `mcp__githits__pkg_info(pypi, numpy)` -> **real data** (numpy 2.5.3,
  BSD-3-Clause, 942M downloads/month, 8 historical advisories). No auth error.

**TWO GitHits surfaces are now live in one session, and this is the new finding:**

1. `mcp__githits__*` — the stdio server wired into the repo's git-tracked
   `.mcp.json`, PINNED to 0.16.1, carrying the trust-boundary `_doc`.
2. `mcp__claude_ai_GitHits__*` — **synced from claude.ai**, appearing on its
   own after the 2.1.268 update. Also returns real data.

That confirms the docs' "Synced from claude.ai" skill/connector loading path
WORKS on 2.1.268 and did not on 2.1.251 — the earlier session's inability to
see account-side configuration was a VERSION problem, not a design limit.

**The duplicate is a cost, not a win:** 30 tool schemas where 15 would do. The
account-synced surface is invisible to the repo (no pin, no `_doc`, no diff,
follows whatever version the vendor serves) — which is the HYG-1 supply-chain
shape the `.mcp.json` entry was pinned to avoid. The git-tracked one is the
one this repo's law prefers; the account one is the one the operator
configured. Choosing which to retire is an OPERATOR decision and is OPEN.

Also measured at restart: the bot was NEVER touched — pid 19164 across the
whole update/restart cycle, heartbeat 4 s. Its parent chain is
`pythonw -> pythonw -> pythonw -> svchost -> services.exe`, i.e. it is owned by
Task Scheduler, not by VS Code. Closing the editor or Claude cannot kill it.
**Logging off can**: all four `LiquidityBot*` scheduled tasks are
`LogonType = Interactive`, including `KeepAlive-10m`, the watchdog — the same
mechanism as the 21-hour outage, and `scripts/fix_scheduled_tasks.ps1` (O1)
converts only the two tasks that do NOT matter.
