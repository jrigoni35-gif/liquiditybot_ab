---
name: vscode-update-loop-fix
description: VS Code auto-update parked-installer loop killed Claude sessions repeatedly; fixed 2026-08-07 (update.mode=manual + deliberate updater script). Diagnostic map for recurrence.
metadata: 
  node_type: memory
  type: reference
  originSessionId: 63d8f842-8108-448c-b2d9-fa9a4c8a2da4
  modified: 2026-08-07T22:57:00.692Z
---

**The failure (recurred twice: ~2026-08-04 and 2026-08-07):** VS Code auto-update downloads, installs to 100%, then parks with `/nocloseapplications` waiting for every `Code.exe` to exit — which never happens on this always-on box. Result: repeated forced reloads that KILL the Claude Code session and all its background tasks/workflows, plus extension updates that bounce ("click to update" reverts) because new extension versions demand a newer engine (e.g. GitHub PRs 0.162.0 needs ^1.130.0 vs installed 1.128.0).

**Diagnostic signatures:** `CodeSetup-stable-*` processes with changing PIDs (relaunch loop, not one wedge); `%TEMP%\vscode-stable-user-x64\update-progress` reading `N,N` (=100%, parked); install dir `%LOCALAPPDATA%\Programs\Microsoft VS Code` containing `new_Code.exe` + hash-named payload dirs (STAGED update — the hash-dir layout is NORMAL for 2026 builds, not damage; do not "repair" it) + multiple `unins00N.exe` generations.

**The fix (2026-08-07):** kill installer tree; purge `%TEMP%\vscode-stable-user-x64` and `%TEMP%\is-*.tmp`; set `"update.mode": "manual"` in `%APPDATA%\Code\User\settings.json` (verified written); download current stable via `https://update.code.visualstudio.com/latest/win32-x64-user/stable`; `C:\Users\haird\Desktop\Update-VSCode.cmd` waits for Code.exe exit → silent install → relaunch. Update landed: 1.128.0 → 1.132.0. Reinstalls never touch settings/extensions (`%APPDATA%\Code`, `~/.vscode`).

**Session practice:** background workflows/batteries die with the VS Code window. Workflow resumes are cheap (`resumeFromRunId` + BYTE-IDENTICAL args — the resume MUST re-pass `args` or the script fails on `args.*`). Time VS Code updates for when no background work is in flight, and warn the operator before they close the window. [[local-compute-directive]]
