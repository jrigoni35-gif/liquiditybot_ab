"""
scripts/session_export.py — bundle a session's LEARNING artifacts for
review on another machine.

Phone/cloud sessions run in ephemeral containers: their outputs/ dies
with the container, so labeled training rows earned there are lost
unless exported. This script stages the portable, reviewable artifacts
into a bundle directory with a checksummed manifest; the companion
scripts/session_import.py verifies and merges a bundle ON THE OPERATOR'S
MACHINE, after human review ("proof-read"), never automatically.

What travels: signal_history.csv (labeled training rows), audit.jsonl
(hash-chained provenance), equity.csv, session digest, check-in log,
postmortem summary, overfit report. What NEVER travels: state.json /
status.json (a live ledger belongs to exactly one runner - importing
positions elsewhere would fork the book), locks, console logs.

Usage:
    python scripts/session_export.py --dest outputs/export/session_XYZ \
        [--outputs outputs] [--label night-shift] [--refresh-digest]
"""

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BUNDLE_FORMAT = 1
PORTABLE = [
    "signal_history.csv",
    "audit.jsonl",
    "equity.csv",
    "session_digest.md",
    "session_digest.json",
    "checkin/checkin_log.jsonl",
    "postmortem_summary.csv",
    "overfit_report.md",
    "meta_model.json",
    # skimmer promotions: without this a fresh container boots the bare core
    # universe until the skimmer re-scores (~an hour of lost breadth). Safe to
    # carry: AssetSkimmer.load_active hard-validates on every read, and import
    # is copy-if-absent (a live machine keeps its own fresher file).
    "skimmer_active.json",
    # append-only RECORDS, not runner state (same class as equity.csv /
    # audit.jsonl): without them every off-box cohort_eval run degrades to
    # "MODEL-ERA UNKNOWN" / "FILL-ERA 0/0" / "accrual 0/50" (measured
    # 2026-08-18) - the era-4 gate, the single number the project waits on,
    # was unreadable from a phone session. Import files them as reports
    # under imported_sessions/<label>/; nothing adopts them into a live
    # ledger, so the one-running-book law (state.json NEVER travels) holds.
    "fills.csv",
    "retrain_history.jsonl",
]
NEVER = {"state.json", "state.json.bak", "status.json", "runner.lock",
         "runner.pid"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_sha(repo: Path) -> str:
    """Best-effort HEAD sha without shelling out."""
    try:
        head = (repo / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            ref = repo / ".git" / head[5:]
            return ref.read_text(encoding="utf-8").strip()[:12]
        return head[:12]
    except OSError:
        return "unknown"


def _history_stats(path: Path) -> dict:
    if not path.exists():
        return {"rows": 0, "by_source": {}, "header": []}
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        try:
            src_i = header.index("source")
        except ValueError:
            src_i = -1
        rows, by_source = 0, {}
        for line in f:
            if not line.strip():
                continue
            rows += 1
            if src_i >= 0:
                parts = line.rstrip("\n").split(",")
                src = parts[src_i] if src_i < len(parts) else "?"
                by_source[src] = by_source.get(src, 0) + 1
    return {"rows": rows, "by_source": by_source, "header": header}


def export(outputs: str, dest: str, label: str,
           refresh_digest: bool = False) -> dict:
    out = Path(outputs)
    dst = Path(dest)
    repo = Path(__file__).resolve().parents[1]
    if refresh_digest:
        from core.session_digest import write_digest
        cfg_path = repo / "config.json"
        cfg = {}
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cfg = {}
        write_digest(str(out), cfg)

    dst.mkdir(parents=True, exist_ok=True)
    files = {}
    for rel in PORTABLE:
        srcf = out / rel
        assert Path(rel).name not in NEVER
        if not srcf.exists():
            continue
        target = dst / Path(rel).name
        shutil.copy2(srcf, target)
        files[target.name] = {"sha256": _sha256(target),
                              "bytes": target.stat().st_size}

    hist = _history_stats(out / "signal_history.csv")
    cfg_file = repo / "config.json"
    manifest = {
        "bundle_format": BUNDLE_FORMAT,
        "label": label,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": _git_sha(repo),
        "config_sha256": _sha256(cfg_file) if cfg_file.exists() else None,
        "history": hist,
        "files": files,
    }
    (dst / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--dest", required=True,
                    help="bundle directory to create/overwrite")
    ap.add_argument("--label", default=time.strftime("%Y%m%d-%H%M",
                                                     time.gmtime()))
    ap.add_argument("--refresh-digest", action="store_true",
                    help="regenerate session_digest before bundling")
    args = ap.parse_args()
    m = export(args.outputs, args.dest, args.label, args.refresh_digest)
    h = m["history"]
    print(f"bundle '{m['label']}' -> {args.dest}")
    print(f"  files: {len(m['files'])} | history rows: {h['rows']} "
          f"{h['by_source']} | git {m['git_sha']}")
    print("  review + merge on the operator machine with: "
          "python scripts/session_import.py --src <bundle> [--apply]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
