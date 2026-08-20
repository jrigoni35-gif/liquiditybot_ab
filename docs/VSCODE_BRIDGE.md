# VS Code bridge — continuing a session in the editor

> A Claude session that starts in one surface (desktop app, CLI, phone,
> cloud) and continues in VS Code loses its scrollback at the boundary.
> This file is the durable half of that crossing; the volatile half is
> `scripts/vscode_bridge.py`, which re-derives it on every run.

**Read order:** `CLAUDE.md` (law) → `docs/HANDOFF.md` (state) → this file
(the surface you are sitting in). Nothing here may weaken a hard
invariant; this is tooling and observability only, which the era-4
moratorium classifies as SAFE.

---

## The one command

In VS Code: **Tasks: Run Task** → `Bridge: what am I attached to? (auth +
session)`. Or:

```bash
python scripts/vscode_bridge.py
```

It is read-only, offline, and never fetches. It answers the three
questions that otherwise get re-derived by hand at every hop:

1. **Which Claude binary am I actually talking to?** Not "which one is on
   PATH" — see the shim trap below.
2. **Is it authenticated?** Established by asking the binary
   (`claude auth status`), never by reading a credential file.
3. **What is this working tree in the middle of?** Branch, ahead/behind,
   dirty paths — the thing the status bar only hints at.

Add `--probe-wsl` to also verify the configured WSL binary exists (it
starts a stopped distro, so it is opt-in). `--json` for machine output,
`--no-auth` to skip the binary probes when you only want tree state.

---

## Traps this box actually has

**More than one thing called "Claude" can be installed at once.** The
official `anthropic.claude-code` extension and third-party chat panels
look alike, launch *different binaries*, and read *different credential
stores*. When something asks you to sign in, the first question is not
"why am I logged out" but **"which panel is asking"**. The bridge report
lists every extension it finds, official and third-party, for exactly
this reason.

**`claude` on PATH may be a forwarding shim, not a binary.** A shim that
resolves the newest extension install with a plain directory glob picks
the **last match in lexicographic order** — and `2.1.99` sorts *after*
`2.1.238` as a string. With one install present this is dormant; the
moment a second appears it silently selects the older one. The bridge
report flags the shim, and warns when more than one official install
exists. `scripts/vscode_bridge.py` sorts by parsed version tuple, which
is what the shim should do too.

**WSL keeps a completely separate `~/.claude`.** Any extension setting
that routes Claude through WSL (`*.wsl.enabled`) means a Windows-side
login never satisfies it — different filesystem, different credential
store, possibly no binary at all. Verify with `--probe-wsl` rather than
assuming either way.

**The status bar shows the folder you have open, not the tree a session
is editing.** With worktrees checked out under `.claude/worktrees/`,
those are routinely different. The bridge report prints both.

---

## Refuted — do not re-derive these

Measured 2026-08-20. Recorded here because both are *attractive* wrong
answers that cost a real investigation, and the next session will reach
for them in the same order.

| hypothesis | verdict | why |
|---|---|---|
| "`~/.claude/.credentials.json` is `{}`, so the CLI is logged out" | **FALSE** | Auth can ride on a `/login` managed key held in `~/.claude.json`. The credentials file then stays an empty object permanently while `claude auth status` reports `loggedIn: true`. An empty credentials file is not evidence of anything. |
| "The WSL misconfiguration causes the repeated login prompt" | **NOT ESTABLISHED** | A missing WSL binary yields `bash: <path>: No such file or directory`, which matches none of the extension's login-error patterns. It is a real defect that breaks that panel — but it surfaces as command-not-found, not as a login loop. |

The general lesson, and the reason the script is built the way it is:
**auth state is a property of the running process, not of a file on
disk.** Every credential-file inference above read correct and was
wrong. `vscode_bridge.py` therefore stats `.credentials.json` (to report
the misleading appearance) and deliberately never reads it — its
contents are secret material *and* they do not answer the question.

---

## What the bridge cannot see

Stated in the report itself on every run, and repeated here because a
green report is only as big as its corpus:

- **Which surface is prompting for login.** The script proves the CLI's
  auth state. The VS Code sidebar, the desktop app, and claude.ai hold
  separate session state that no local file exposes. If a prompt
  persists while the report reads `logged in`, the prompt is coming from
  a surface this script cannot inspect — identify it by *where it
  appears*, not by guessing.
- **Anything inside WSL** unless `--probe-wsl` is passed.
- **Anything requiring the network.** Ahead/behind is computed from refs
  already on disk and is only as fresh as your last fetch; the report
  stamps that age rather than hiding it.

---

## Handing a session over

The bridge answers *where am I*. `docs/HANDOFF.md` answers *what is
pending* — the live gate count, the open docket, what is blocked. A
session continuing in VS Code should read the handoff first and run the
bridge second; the bridge is cheap enough to run at every wake, and the
session-staleness rule (VS Code windows survive for days with stale
context) means every wake needs it.
