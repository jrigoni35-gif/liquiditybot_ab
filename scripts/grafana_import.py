"""scripts/grafana_import.py — push the repo's dashboards into Grafana Cloud
via the HTTP API (no manual JSON pasting).

Auth: a Grafana SERVICE ACCOUNT token (glsa_...) with Editor role, supplied
via the GRAFANA_SA_TOKEN environment variable OR persisted at
~/.liquiditybot/grafana-sa-token (2026-07-30, operator away from the PC:
the same durable-token pattern as ~/.liquiditybot/gc-token, so
pc_supervisor's dashboard auto-import can run unattended). Never argv,
never committed. The OTLP access-policy token cannot do this
(metrics-write realm only).

Imports every docs/grafana/*.json dashboard (they are stored UNWRAPPED; the
API wants {"dashboard": {...}}, so this wraps at POST time), into the target
folder (created if missing), overwrite=true — stable uids mean re-runs update
in place, never duplicate.

    GRAFANA_SA_TOKEN=glsa_... python scripts/grafana_import.py \
        [--url https://goldsavanna1216.grafana.net] [--folder liquiditybot-ops]

`--stamp PATH --fingerprint STR` (pc_supervisor auto-import contract):
on a fully successful run the fingerprint is written to PATH — the
supervisor's change-detection stamp. Written ONLY when every dashboard
imported (failures retry on the next supervisor tick).
"""
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARDS = [
    # the four banner-linked Liquid Glass boards — generator-owned by
    # scripts/build_trading_dashboard.py (the command board keeps uid
    # liquiditybot-trading, replacing the old monolith). The dedicated
    # glass + mobile boards were retired 2026-07-22; the glass treatment
    # lives in the boards themselves (docs/grafana/README_glass.md).
    # The Pulse "one screen, one truth" hero USED to live inside the Command
    # board (operator decision 2026-07-23). It was DELETED 2026-08-15 with
    # the rest of the board content; do not go looking for it. The family
    # still stays at four, and all four are still imported: three of them
    # now carry only the glass injector, and importing an intentionally
    # empty board is what KEEPS it empty on the instance - skipping it would
    # leave the old panel-laden version live in Grafana forever.
    "liquiditybot_command.json",
    "liquiditybot_execution.json",
    "liquiditybot_problem_solution.json",
    "liquiditybot_screening.json",
]

# Boards retired — deleted from the instance on every run so a re-import
# can never leave a dead board (with its fixed defects) live. DELETE is
# idempotent here: 404 = already gone, which is success. glass + mobile
# retired 2026-07-22; the standalone Pulse board 2026-07-23 (folded into
# Command the same day it shipped — "not a new one").
RETIRED_UIDS = ["liquiditybot-glass", "liquiditybot-glass-mobile",
                "liquiditybot-pulse"]


def _req(url: str, token: str, payload: dict | None = None, method=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        method=method or ("POST" if payload is not None else "GET"))
    with urllib.request.urlopen(req, timeout=30) as r:  # nosec B310 - https
        body = r.read()
        return json.loads(body) if body else {}


def ensure_folder(base: str, token: str, folder_uid: str) -> str:
    """Return the folder uid, creating the folder when absent."""
    try:
        got = _req(f"{base}/api/folders/{folder_uid}", token)
        return got["uid"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    made = _req(f"{base}/api/folders", token,
                {"uid": folder_uid, "title": folder_uid})
    print(f"  created folder {made['uid']}")
    return made["uid"]


def _resolve_token() -> str:
    """GRAFANA_SA_TOKEN env first; else the persisted token file
    ~/.liquiditybot/grafana-sa-token (durable-token pattern, see module
    docstring). Empty string when neither exists."""
    tok = os.environ.get("GRAFANA_SA_TOKEN", "").strip()
    if tok:
        return tok
    try:
        f = Path.home() / ".liquiditybot" / "grafana-sa-token"
        if f.is_file():
            return f.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://goldsavanna1216.grafana.net")
    ap.add_argument("--folder", default="liquiditybot-ops")
    ap.add_argument("--stamp", default=None,
                    help="on FULL success, write --fingerprint here "
                         "(pc_supervisor auto-import contract)")
    ap.add_argument("--fingerprint", default="",
                    help="content fingerprint recorded by --stamp")
    args = ap.parse_args()
    token = _resolve_token()
    if not token.startswith("glsa_"):
        print("set GRAFANA_SA_TOKEN (or persist the token at "
              "~/.liquiditybot/grafana-sa-token) — a Grafana "
              "service-account token (glsa_...) with Editor role; see "
              "module docstring")
        return 2
    base = args.url.rstrip("/")
    if not base.startswith("https://"):
        print("refusing non-https Grafana URL")
        return 2
    folder_uid = ensure_folder(base, token, args.folder)
    failures = 0
    for name in DASHBOARDS:
        path = ROOT / "docs" / "grafana" / name
        if not path.exists():
            print(f"  SKIP {name}: not in repo")
            continue
        model = json.loads(path.read_text(encoding="utf-8"))
        model.pop("id", None)               # instance-local, never portable
        try:
            out = _req(f"{base}/api/dashboards/db", token,
                       {"dashboard": model, "folderUid": folder_uid,
                        "overwrite": True, "message": "import via "
                        "scripts/grafana_import.py"})
            print(f"  OK   {name} -> {out.get('url')} "
                  f"(v{out.get('version')})")
        except urllib.error.HTTPError as e:
            failures += 1
            print(f"  FAIL {name}: HTTP {e.code} {e.read()[:200]!r}")

    for uid in RETIRED_UIDS:
        try:
            _req(f"{base}/api/dashboards/uid/{uid}", token, method="DELETE")
            print(f"  RETIRED {uid}: deleted")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  RETIRED {uid}: already gone")
            else:
                failures += 1
                print(f"  FAIL retire {uid}: HTTP {e.code}")
    if not failures and args.stamp:
        # pc_supervisor auto-import contract: record WHAT was imported
        # (content fingerprint), only on full success — a partial or
        # failed run leaves the stamp untouched so the supervisor
        # retries on its next tick.
        try:
            Path(args.stamp).write_text(str(args.fingerprint),
                                        encoding="utf-8")
        except OSError as e:
            print(f"  stamp write failed (import itself succeeded): {e}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
