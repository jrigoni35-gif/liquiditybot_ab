"""PostToolUse hook: ruff-check any .py file Claude just edited.

WHY: on 2026-08-23/24 ruff was run BY HAND ~40 times per session, and twice
it caught real defects minutes after the edit (a stale max_seq reference, an
unused variable) that would otherwise have surfaced at the manual gate. This
moves that catch to the moment of the edit.

Exit 2 on findings: PostToolUse feeds stderr back to Claude as a blocking
error, so the lint output lands in-context immediately. Non-.py files and
missing tools exit 0 silently - a missing linter is not a finding about the
edit (the auto_update lesson, 2026-07-21).
"""
import json
import os
import subprocess
import sys


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0
    f = (d.get("tool_input") or {}).get("file_path") or \
        (d.get("tool_response") or {}).get("filePath") or ""
    if not f.endswith(".py") or not os.path.exists(f):
        return 0
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    py = os.path.join(root, ".venv", "Scripts", "python.exe")
    if not os.path.exists(py):
        return 0                      # missing tool is not a finding
    try:
        r = subprocess.run([py, "-m", "ruff", "check", f],
                           capture_output=True, text=True, timeout=60)
    except Exception:
        return 0
    if r.returncode != 0:
        out = (r.stdout or "") + (r.stderr or "")
        sys.stderr.write("ruff (auto, on edit):\n" + out[-1800:])
        return 2                      # feed the findings back to Claude
    return 0


if __name__ == "__main__":
    sys.exit(main())
