"""PreToolUse hook: warn when a pytest run is piped through a filter.

WHY: `pytest ... | tail -3` DISCARDS pytest's exit code - the shell reports
the FILTER's status. On 2026-08-24 this masked a real rc=1 twice in one
session ("1 failed" scrolled past while the harness printed exit 0), and the
fix each time was the same: redirect to a file, then echo the real $?.

This hook never blocks and never decides permission - it only injects a
reminder into context when the pattern appears. A guard that cried wolf or
auto-allowed anything would be worse than none.
"""
import json
import re
import sys


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0
    c = (d.get("tool_input") or {}).get("command") or ""
    if re.search(r"pytest[^|&\n]*\|\s*(tail|head|grep|sed|awk)\b", c):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "PIPE-MASK WARNING: this pytest run is piped through a "
                "filter, so the shell reports the FILTER's exit code, not "
                "pytest's - the exact pattern that hid a real rc=1 twice on "
                "2026-08-24. Prefer: `pytest ... > out.txt 2>&1; echo "
                "\"REAL rc=$?\"` then read the file.")}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
