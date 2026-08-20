"""Graceful bridge between a Claude Code session and VS Code.

A session that starts in one surface (desktop app, CLI, phone, cloud) and
continues in another has to re-derive three things before it can act: *which
Claude binary am I even talking to*, *is that binary authenticated*, and *what
is this working tree in the middle of*. Scrollback does not survive the hop.
This script answers all three from the running system, read-only, offline.

WHY THIS EXISTS AS A SCRIPT AND NOT A DOC
    A doc that names a version, a path, or an auth state decays into a false
    claim the moment either changes -- the same reason CLAUDE.md refuses to
    carry numbers. So the durable knowledge (the traps, the refuted
    hypotheses) lives in the prose below, and every volatile fact is
    re-derived on each run.

WHAT IT PROVES vs WHAT IT ASSUMES
    Auth is established by ASKING THE BINARY (`claude auth status`), never by
    inspecting a credential file. That distinction is load-bearing; see the
    REFUTED section below.

WHAT IT CANNOT SEE (say it out loud, every time)
    * Which surface is showing a login prompt. This script proves whether the
      *CLI* is authenticated. The VS Code sidebar, the desktop app, and
      claude.ai each own separate session state that no local file exposes.
    * Anything inside WSL, unless --probe-wsl is passed (probing wakes a
      stopped distro, which is a side effect, so it is opt-in).
    * Anything requiring the network: ahead/behind is computed from refs
      already on disk, so it is as stale as your last fetch. That staleness
      is reported, not hidden.

REFUTED -- do not re-derive these (measured 2026-08-20)
    1. "`~/.claude/.credentials.json` is `{}`, therefore the CLI is logged
       out."  FALSE. Auth can ride on a `/login` managed key held in
       `~/.claude.json`, in which case `.credentials.json` stays an empty
       object forever and `claude auth status` still reports loggedIn=true.
       An empty credentials file is NOT evidence of anything. This script
       stats that file but deliberately never reads it -- both because its
       contents are secret material and because its contents do not answer
       the question.
    2. "The claude-code-chat WSL misconfiguration causes the login prompt."
       NOT ESTABLISHED. A missing WSL binary yields
       `bash: <path>: No such file or directory`, which matches none of that
       extension's login-error patterns ('401 Invalid authentication
       credentials', 'Invalid API key', 'Not logged in', '/login', 'not
       authenticated'). It is a real defect -- that extension cannot work on
       this box -- but it surfaces as command-not-found, not as a login
       loop. Reported as BROKEN, never as the cause.

Exit status is always 0 unless the script itself failed: this is an
instrument, not a gate. Findings are carried in the report, and in --json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Windows is the target runtime (CLAUDE.md), but nothing here may hard-require
# it -- the same session may continue from WSL, a Linux box, or a container.
IS_WINDOWS = os.name == "nt"

# A binary that has to page in ~330 MB before answering gets a generous
# window; a wedged one must still not hang the report.
AUTH_TIMEOUT_S = 25.0
GIT_TIMEOUT_S = 15.0
WSL_TIMEOUT_S = 30.0

OK, WARN, BAD, INFO = "OK", "WARN", "BROKEN", "INFO"


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _config_dir() -> Path:
    """Honour CLAUDE_CONFIG_DIR -- a surface that sets it has a private store."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override) if override else _home() / ".claude"


def _run(cmd: list[str], timeout: float, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a command, never raise. Returns (rc, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout:.0f}s"
    except (OSError, ValueError) as exc:  # missing binary, bad args
        return 127, "", f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------- surfaces


def _extension_dirs() -> list[Path]:
    """Official Claude Code VS Code extension installs, newest-version last.

    Sorted by parsed version tuple, NOT lexicographically -- see the shim trap
    in vscode_wiring(): '2.1.99' sorts after '2.1.238' as a string, which is
    exactly backwards.
    """
    root = _home() / ".vscode" / "extensions"
    if not root.is_dir():
        return []
    found = [d for d in root.iterdir() if d.is_dir() and d.name.startswith("anthropic.claude-code-")]
    return sorted(found, key=lambda d: _version_key(d.name))


def _version_key(name: str) -> tuple[int, ...]:
    """Best-effort numeric version key; unparsable segments sort first."""
    core = name[len("anthropic.claude-code-"):] if name.startswith("anthropic.claude-code-") else name
    digits: list[int] = []
    for part in core.replace("-", ".").split("."):
        if part.isdigit():
            digits.append(int(part))
        else:
            break
    return tuple(digits) if digits else (-1,)


def _candidate_binaries() -> list[tuple[str, Path]]:
    """Every Claude entry point this box can reach, labelled by provenance."""
    out: list[tuple[str, Path]] = []

    on_path = shutil.which("claude")
    if on_path:
        out.append(("PATH", Path(on_path)))

    native = _home() / (".local/bin/claude.exe" if IS_WINDOWS else ".local/bin/claude")
    if native.exists():
        out.append(("native installer", native))

    for d in _extension_dirs():
        exe = d / "resources" / "native-binary" / ("claude.exe" if IS_WINDOWS else "claude")
        if exe.exists():
            out.append((f"vscode ext {d.name.split('claude-code-')[-1]}", exe))

    # De-duplicate by resolved target while keeping the first (most meaningful)
    # label -- a PATH shim and the file it forwards to are the same binary.
    seen: dict[str, tuple[str, Path]] = {}
    for label, path in out:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()
        seen.setdefault(key, (label, path))
    return list(seen.values())


def _auth_status(exe: Path) -> dict[str, Any]:
    """ASK THE BINARY. Never infer auth from a file on disk."""
    rc, out, err = _run([str(exe), "auth", "status"], AUTH_TIMEOUT_S)
    if rc == 124:
        return {"probe": "timeout", "detail": err}
    try:
        parsed = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return {"probe": "unparsable", "rc": rc, "raw": (out or err)[:400]}
    # Whatever the binary chooses to print is safe to echo -- it is a status
    # command, not a secret dump -- but never widen this to other subcommands.
    parsed["probe"] = "ok"
    return parsed


def _version(exe: Path) -> str:
    rc, out, err = _run([str(exe), "--version"], AUTH_TIMEOUT_S)
    return out or err or f"rc={rc}"


def surfaces(skip_auth: bool = False) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for label, path in _candidate_binaries():
        row: dict[str, Any] = {"label": label, "path": str(path), "version": _version(path)}
        row["auth"] = {"probe": "skipped"} if skip_auth else _auth_status(path)
        rows.append(row)

    cfg = _config_dir()
    creds = cfg / ".credentials.json"
    # STAT ONLY. Contents are secret material, and -- per REFUTED #1 -- they
    # do not answer the auth question anyway.
    cred_note: dict[str, Any] = {"path": str(creds), "exists": creds.exists()}
    if creds.exists():
        st = creds.stat()
        cred_note["bytes"] = st.st_size
        cred_note["empty_object"] = st.st_size <= 2
    return {"config_dir": str(cfg), "binaries": rows, "credentials_file": cred_note}


# ------------------------------------------------------------ vscode wiring


def _read_json(path: Path) -> Any | None:
    """Tolerant of the BOM and of JSONC trailing commas VS Code allows."""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _vscode_user_settings() -> tuple[Path | None, dict[str, Any]]:
    appdata = os.environ.get("APPDATA")
    candidates = []
    if appdata:
        candidates.append(Path(appdata) / "Code" / "User" / "settings.json")
    candidates.append(_home() / ".config" / "Code" / "User" / "settings.json")
    for c in candidates:
        if c.is_file():
            data = _read_json(c)
            if isinstance(data, dict):
                return c, data
    return None, {}


def _ide_locks() -> list[dict[str, Any]]:
    """`~/.claude/ide/<pid>.lock` -- an IDE advertising itself to the CLI.

    The lock carries an authToken for the local websocket; it is redacted here
    and must stay redacted.
    """
    d = _config_dir() / "ide"
    if not d.is_dir():
        return []
    locks: list[dict[str, Any]] = []
    for f in sorted(d.glob("*.lock")):
        data = _read_json(f)
        if not isinstance(data, dict):
            locks.append({"file": f.name, "parse": "unreadable"})
            continue
        locks.append(
            {
                "file": f.name,
                "pid": data.get("pid"),
                "ide": data.get("ideName"),
                "transport": data.get("transport"),
                "workspaceFolders": data.get("workspaceFolders"),
                "authToken": "<redacted>" if data.get("authToken") else None,
            }
        )
    return locks


def vscode_wiring(probe_wsl: bool = False) -> dict[str, Any]:
    findings: list[tuple[str, str]] = []

    ext_root = _home() / ".vscode" / "extensions"
    official = [d.name for d in _extension_dirs()]
    third_party = []
    if ext_root.is_dir():
        third_party = [
            d.name
            for d in ext_root.iterdir()
            if d.is_dir()
            and not d.name.startswith("anthropic.claude-code-")
            and ("claude" in d.name.lower() or "anthropic" in d.name.lower())
        ]

    if len(official) > 1:
        findings.append(
            (
                WARN,
                f"{len(official)} official extension installs present ({', '.join(official)}). "
                "If a PATH shim resolves them with a plain directory glob it will pick the "
                "LAST match in lexicographic order -- '2.1.99' beats '2.1.238' as a string. "
                "Pin the shim, or remove the stale install.",
            )
        )
    elif not official:
        findings.append((WARN, "no official Claude Code VS Code extension found under ~/.vscode/extensions"))

    # The PATH shim: whatever `claude` resolves to may not be what you think.
    on_path = shutil.which("claude")
    shim_body = None
    if on_path and Path(on_path).suffix.lower() in {".cmd", ".bat", ""}:
        try:
            body = Path(on_path).read_text(encoding="utf-8", errors="replace")
            if "extensions" in body or "%%D" in body or "for /d" in body:
                shim_body = on_path
                findings.append(
                    (
                        INFO,
                        f"`claude` on PATH is a forwarding shim ({on_path}), not a real binary. "
                        "It delegates to another install -- so 'which claude' does not identify "
                        "the process that actually runs.",
                    )
                )
        except (OSError, UnicodeDecodeError):
            pass

    settings_path, settings = _vscode_user_settings()
    wsl_enabled = bool(settings.get("claudeCodeChat.wsl.enabled"))
    wsl_distro = settings.get("claudeCodeChat.wsl.distro") or "Ubuntu"
    wsl_claude = settings.get("claudeCodeChat.wsl.claudePath") or "/usr/local/bin/claude"
    wsl_probe: dict[str, Any] = {"probed": False}

    if wsl_enabled:
        if probe_wsl and IS_WINDOWS:
            rc, out, err = _run(
                ["wsl.exe", "-d", str(wsl_distro), "bash", "-lc", f"test -x {wsl_claude} && echo PRESENT || echo ABSENT"],
                WSL_TIMEOUT_S,
            )
            present = "PRESENT" in (out or "")
            wsl_probe = {"probed": True, "present": present, "rc": rc, "detail": (out or err)[:200]}
            if not present:
                findings.append(
                    (
                        BAD,
                        f"claudeCodeChat is set to run Claude inside WSL '{wsl_distro}' at "
                        f"'{wsl_claude}', and that path does not exist in the distro. That "
                        "extension cannot work on this box. Note it fails as command-not-found, "
                        "NOT as a login prompt (see REFUTED #2 in this file's docstring).",
                    )
                )
        else:
            findings.append(
                (
                    WARN,
                    f"claudeCodeChat is configured to run Claude inside WSL '{wsl_distro}' at "
                    f"'{wsl_claude}'. WSL keeps a SEPARATE ~/.claude -- a Windows-side login "
                    "never satisfies it. Re-run with --probe-wsl to check whether that binary "
                    "exists (probing wakes the distro).",
                )
            )

    if third_party:
        findings.append(
            (
                WARN,
                f"third-party Claude extensions installed: {', '.join(third_party)}. "
                "Two chat panels that look alike but use different binaries and different "
                "credential stores is the single easiest way to be confused about which one "
                "is asking you to sign in.",
            )
        )

    locks = _ide_locks()
    if not locks:
        findings.append((INFO, "no IDE lock in ~/.claude/ide -- no editor is currently advertising itself to the CLI"))

    return {
        "extensions_official": official,
        "extensions_third_party": third_party,
        "path_shim": shim_body,
        "user_settings": str(settings_path) if settings_path else None,
        "wsl": {"enabled": wsl_enabled, "distro": wsl_distro, "claude_path": wsl_claude, "probe": wsl_probe},
        "ide_locks": locks,
        "findings": findings,
    }


# ------------------------------------------------------------ session state


def session_state(repo: Path) -> dict[str, Any]:
    """Where this working tree actually is -- the thing the status bar hints at."""
    findings: list[tuple[str, str]] = []

    def git(*args: str) -> str:
        rc, out, _ = _run(["git", *args], GIT_TIMEOUT_S, cwd=repo)
        return out if rc == 0 else ""

    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "<detached>"
    head = git("rev-parse", "--short", "HEAD")
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")

    ahead = behind = None
    if upstream:
        counts = git("rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        parts = counts.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            behind, ahead = int(parts[0]), int(parts[1])

    porcelain = git("status", "--porcelain=v1")
    dirty = [ln for ln in porcelain.splitlines() if ln.strip()]

    # Staleness of the ahead/behind answer: we never fetch (offline by
    # contract), so the comparison is only as fresh as the last fetch.
    fetch_head = repo / ".git" / "FETCH_HEAD"
    last_fetch = None
    if fetch_head.exists():
        last_fetch = fetch_head.stat().st_mtime
    else:
        # Worktrees keep .git as a file pointing at the real gitdir.
        common = git("rev-parse", "--git-common-dir")
        if common:
            fh = Path(common) / "FETCH_HEAD"
            if not fh.is_absolute():
                fh = repo / fh
            if fh.exists():
                last_fetch = fh.stat().st_mtime

    if ahead and dirty:
        findings.append(
            (
                BAD,
                f"{ahead} local commit(s) unpushed AND {len(dirty)} uncommitted path(s). "
                "This is the exact shape that wedges the deploy updater: it refuses to "
                "fast-forward across a dirty tree, and once the tree is clean an unpushed "
                "commit makes HEAD and origin diverge, which the guard refuses forever. "
                "Clear the dirt first, then rebase, then push.",
            )
        )
    elif dirty:
        findings.append((WARN, f"{len(dirty)} uncommitted path(s) -- the deploy updater will not fast-forward across them"))
    elif ahead:
        findings.append((WARN, f"{ahead} local commit(s) not on the upstream branch"))

    worktrees = git("worktree", "list").splitlines()
    if len(worktrees) > 1:
        findings.append(
            (
                INFO,
                f"{len(worktrees)} worktrees checked out. VS Code's status bar shows the folder "
                "you have OPEN -- which may not be the tree a Claude session is editing.",
            )
        )

    return {
        "repo": str(repo),
        "branch": branch,
        "head": head,
        "upstream": upstream or None,
        "ahead": ahead,
        "behind": behind,
        "dirty_count": len(dirty),
        "dirty_sample": dirty[:10],
        "worktrees": worktrees,
        "last_fetch_epoch": last_fetch,
        "findings": findings,
    }


# ------------------------------------------------------------------ report


def _fmt_auth(auth: dict[str, Any]) -> str:
    probe = auth.get("probe")
    if probe == "skipped":
        return "auth: (skipped)"
    if probe == "timeout":
        return f"auth: TIMEOUT ({auth.get('detail')})"
    if probe == "unparsable":
        return f"auth: unreadable -> {auth.get('raw', '')[:120]}"
    state = "logged in" if auth.get("loggedIn") else "LOGGED OUT"
    bits = [state]
    for k in ("authMethod", "apiKeySource", "email"):
        if auth.get(k):
            bits.append(f"{k}={auth[k]}")
    return "auth: " + " | ".join(bits)


def render(data: dict[str, Any]) -> str:
    L: list[str] = []
    add = L.append

    add("=" * 72)
    add("VS CODE BRIDGE - what this session is attached to")
    add("=" * 72)

    s = data["surfaces"]
    add("")
    add(f"CONFIG DIR: {s['config_dir']}")
    cf = s["credentials_file"]
    if cf["exists"] and cf.get("empty_object"):
        add(
            f"  .credentials.json: present but empty ({cf['bytes']}B) -- NOT a logout signal. "
            "Auth can ride on a managed key; the binary's own answer is below."
        )
    elif cf["exists"]:
        add(f"  .credentials.json: present ({cf['bytes']}B, contents deliberately unread)")
    else:
        add("  .credentials.json: absent")

    add("")
    add("CLAUDE BINARIES REACHABLE FROM HERE")
    if not s["binaries"]:
        add("  (none found)")
    for row in s["binaries"]:
        add(f"  [{row['label']}] {row['version']}")
        add(f"      {row['path']}")
        add(f"      {_fmt_auth(row['auth'])}")

    v = data["vscode"]
    add("")
    add("VS CODE WIRING")
    add(f"  official extensions : {', '.join(v['extensions_official']) or '(none)'}")
    add(f"  third-party         : {', '.join(v['extensions_third_party']) or '(none)'}")
    add(f"  user settings       : {v['user_settings'] or '(not found)'}")
    if v["path_shim"]:
        add(f"  PATH shim           : {v['path_shim']}")
    for lk in v["ide_locks"]:
        add(f"  IDE attached        : {lk.get('ide')} pid={lk.get('pid')} folders={lk.get('workspaceFolders')}")

    g = data["session"]
    add("")
    add("WORKING TREE")
    add(f"  repo     : {g['repo']}")
    add(f"  branch   : {g['branch']} @ {g['head']}")
    ab = []
    if g["behind"] is not None:
        ab.append(f"{g['behind']} behind")
    if g["ahead"] is not None:
        ab.append(f"{g['ahead']} ahead")
    add(f"  upstream : {g['upstream'] or '(none)'}{'  [' + ', '.join(ab) + ']' if ab else ''}")
    add(f"  dirty    : {g['dirty_count']} path(s)")
    for ln in g["dirty_sample"]:
        add(f"             {ln}")
    if g["last_fetch_epoch"] is None:
        add("  NOTE: no FETCH_HEAD -- ahead/behind is against refs of unknown age (never fetched here).")
    else:
        import time as _t

        age_min = (_t.time() - g["last_fetch_epoch"]) / 60.0
        add(f"  NOTE: ahead/behind is as of the last fetch, {age_min:.0f} min ago. This script never fetches.")

    add("")
    add("FINDINGS")
    all_f = list(v["findings"]) + list(g["findings"])
    if not all_f:
        add("  none -- but read the 'could not see' list in this script's docstring before calling that clean.")
    order = {BAD: 0, WARN: 1, INFO: 2, OK: 3}
    for sev, msg in sorted(all_f, key=lambda t: order.get(t[0], 9)):
        add(f"  [{sev}] {msg}")

    add("")
    add("WHAT THIS RUN COULD NOT SEE")
    add("  * Which surface is prompting for login. The CLI's auth state is proven above;")
    add("    the VS Code sidebar, the desktop app, and claude.ai hold separate session")
    add("    state that no local file exposes. If a prompt persists while the line above")
    add("    reads 'logged in', the prompt is coming from a surface this script cannot")
    add("    inspect -- identify it by where the prompt appears, not by guessing.")
    if not v["wsl"]["probe"].get("probed") and v["wsl"]["enabled"]:
        add("  * Whether the configured WSL claude binary exists (--probe-wsl to check).")
    add("  * Anything requiring the network. No fetch was performed.")
    add("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Report what this Claude session and VS Code are attached to.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--no-auth", action="store_true", help="skip `claude auth status` probes (faster)")
    ap.add_argument("--probe-wsl", action="store_true", help="check the configured WSL binary (wakes the distro)")
    ap.add_argument("--repo", default=".", help="repository/worktree to inspect (default: cwd)")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    data = {
        "surfaces": surfaces(skip_auth=args.no_auth),
        "vscode": vscode_wiring(probe_wsl=args.probe_wsl),
        "session": session_state(repo),
    }

    if args.json:
        # Findings are (severity, message) tuples -- make them explicit in JSON.
        for section in ("vscode", "session"):
            data[section] = dict(data[section])
            data[section]["findings"] = [{"severity": s, "message": m} for s, m in data[section]["findings"]]
        print(json.dumps(data, indent=2, default=str))
    else:
        print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
