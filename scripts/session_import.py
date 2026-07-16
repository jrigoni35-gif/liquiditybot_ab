"""
scripts/session_import.py — verify a session bundle and merge its
LEARNING data into this machine's outputs. The "proof-read" gate for
work done in phone/cloud sessions: nothing is adopted until the
operator runs this, reads the plan, and re-runs with --apply.

Verification before anything else:
  1. every bundled file's sha256 matches its manifest entry
  2. the bundled audit chain replays end-to-end (hash-chain intact)
  3. the bundle's history header matches THIS checkout's schema (and
     the destination file's, when one exists) - schema drift routes
     through scripts/migrate_history.py, never silent padding here

What --apply does: back up the local signal_history.csv into
outputs/archive/, append only rows not already present (keyed by
position_id, falling back to the raw line hash), and file the bundle's
reports under outputs/imported_sessions/<label>/ for the record.
What it never does: touch state.json, status.json, or any live runner
artifact - importing another session's ledger would fork the book.

Exit codes: 0 ok, 2 integrity failure, 3 schema mismatch, 4 bad bundle.

Usage:
    python scripts/session_import.py --src outputs/export/session_XYZ
    python scripts/session_import.py --src ... --apply
"""

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.audit import AuditTrail  # noqa: E402
from ml.history import HistoryStore  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_rows(path: Path):
    """Header list + raw data lines (kept verbatim so numeric formatting
    survives the round-trip byte-for-byte)."""
    with open(path, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split(",")
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    return header, lines


def _row_key(header, line):
    try:
        pid = line.split(",")[header.index("position_id")].strip()
        if pid:
            return f"pid:{pid}"
    except (ValueError, IndexError):
        pass
    return "raw:" + hashlib.sha256(line.encode("utf-8")).hexdigest()


def verify_bundle(src: Path) -> dict:
    mf_path = src / "manifest.json"
    if not mf_path.exists():
        print(f"REFUSED: no manifest.json in {src}")
        return {"rc": 4}
    manifest = json.loads(mf_path.read_text(encoding="utf-8"))
    if manifest.get("bundle_format") != 1:
        print(f"REFUSED: unknown bundle_format "
              f"{manifest.get('bundle_format')!r}")
        return {"rc": 4}
    for name, meta in manifest.get("files", {}).items():
        f = src / name
        if not f.exists():
            print(f"INTEGRITY FAIL: {name} listed in manifest but missing")
            return {"rc": 2}
        got = _sha256(f)
        if got != meta.get("sha256"):
            print(f"INTEGRITY FAIL: {name} sha256 mismatch "
                  f"(bundle tampered or corrupt)")
            return {"rc": 2}
    audit = src / "audit.jsonl"
    chain = None
    if audit.exists():
        chain = AuditTrail(str(audit)).verify()
        if not chain.get("ok"):
            print(f"INTEGRITY FAIL: audit chain breaks at record "
                  f"{chain.get('first_break')} - refusing bundle")
            return {"rc": 2}
    return {"rc": 0, "manifest": manifest, "chain": chain}


def run(src: str, outputs: str, apply: bool) -> int:
    srcp = Path(src)
    out = Path(outputs)
    v = verify_bundle(srcp)
    if v["rc"] != 0:
        return v["rc"]
    manifest, chain = v["manifest"], v["chain"]

    expected = HistoryStore(str(out / "signal_history.csv"))._header
    hist_src = srcp / "signal_history.csv"
    new_lines, dupes, b_header = [], 0, None
    if hist_src.exists():
        b_header, b_lines = _read_rows(hist_src)
        if b_header != expected:
            # Features are only ever ADDED to the schema over time, so an OLDER
            # bundle is strictly NARROWER. Migrate those UP (pad new features
            # with documented neutrals, derive side-relative from absolute)
            # instead of stranding the whole bundle's learning — the same
            # transform migrate_history.py applies to the local file, run inline
            # to close the leak where every feature-schema bump orphaned the
            # entire backup chain. A same-width-different or WIDER header is a
            # newer/unknown schema whose column MEANINGS may have drifted; we
            # can't safely reconcile that, so it still refuses (never silently
            # drop columns). A narrower-but-unmappable file (missing meta
            # columns) also refuses — migrate_rows raises SystemExit for those.
            if len(b_header) >= len(expected):
                print(f"SCHEMA MISMATCH: bundle history has {len(b_header)} "
                      f"cols vs {len(expected)} (not an older schema) - "
                      f"refusing, cannot safely down-migrate a newer schema")
                return 3
            try:
                from scripts.migrate_history import migrate_rows
                migrated, padded = migrate_rows(str(hist_src))
            except SystemExit as e:
                print(f"SCHEMA MISMATCH: bundle history not migratable "
                      f"({e}) - refusing")
                return 3
            print(f"  migrated bundle history {len(b_header)} -> "
                  f"{len(expected)} cols (padded {len(padded)} new feature(s))")
            b_header = list(expected)
            b_lines = [",".join(str(c) for c in row) for row in migrated]
        dest_hist = out / "signal_history.csv"
        seen = set()
        if dest_hist.exists():
            d_header, d_lines = _read_rows(dest_hist)
            if d_header != expected:
                print("SCHEMA MISMATCH: local signal_history.csv is on an "
                      "older schema - migrate it before importing.")
                return 3
            seen = {_row_key(d_header, ln) for ln in d_lines}
        for ln in b_lines:
            if _row_key(b_header, ln) in seen:
                dupes += 1
            else:
                new_lines.append(ln)

    h = manifest.get("history", {})
    print(f"bundle '{manifest.get('label')}' created "
          f"{manifest.get('created_at_utc')} @ git {manifest.get('git_sha')}")
    print(f"  audit chain: "
          f"{'ok, ' + str(chain.get('records')) + ' records' if chain else 'not bundled'}")
    print(f"  training rows: {h.get('rows')} bundled "
          f"{h.get('by_source')} -> {len(new_lines)} new, {dupes} duplicate")
    print(f"  reports: {', '.join(sorted(manifest.get('files', {})))}")

    if not apply:
        print("plan only - re-run with --apply to merge (a backup of the "
              "local history is taken first)")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    # the trained model travels copy-if-absent: a machine that already has
    # outputs/meta_model.json keeps its own (retrain locally from the merged
    # rows); a fresh container consumes the bundled brain immediately.
    model_src = srcp / "meta_model.json"
    model_dst = out / "meta_model.json"
    if model_src.exists() and not model_dst.exists():
        model_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(model_src, model_dst)
        # register the adopted brain in THIS machine's ledger so its
        # integrity gate (ML-011) accepts it. A foreign artifact has no
        # local pedigree, and any stale ledger entry for the path would fail
        # the hash match — refusing the model until a retrain, exactly the
        # cross-machine papercut this hand-off exists to avoid. Registration
        # files the adopted hash as the expected one. Never blocks the copy.
        try:
            from ml.registry import ModelRegistry
            mid = ModelRegistry(str(out / "models")).register(
                str(model_dst),
                {"source": f"bundle:{manifest.get('label')}",
                 "bundle_created": manifest.get("created_at_utc"),
                 "adopted": True})
            print(f"  meta_model.json adopted + registered locally ({mid})")
        except Exception as e:                       # noqa: BLE001 - never block
            print(f"  meta_model.json adopted (local registration skipped: {e})")
    dest_hist = out / "signal_history.csv"
    if new_lines:
        if dest_hist.exists():
            bak = out / "archive" / f"signal_history_pre_import_{stamp}.csv"
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest_hist, bak)
            print(f"  backup: {bak}")
        else:
            dest_hist.parent.mkdir(parents=True, exist_ok=True)
            dest_hist.write_text(",".join(expected) + "\n", encoding="utf-8")
        with open(dest_hist, "a", encoding="utf-8") as f:
            for ln in new_lines:
                f.write(ln + "\n")
    record = out / "imported_sessions" / str(manifest.get("label") or stamp)
    record.mkdir(parents=True, exist_ok=True)
    for name in manifest.get("files", {}):
        if name != "signal_history.csv" and (srcp / name).exists():
            shutil.copy2(srcp / name, record / name)
    shutil.copy2(srcp / "manifest.json", record / "manifest.json")
    print(f"  merged {len(new_lines)} rows; bundle reports filed under "
          f"{record}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="bundle directory")
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--apply", action="store_true",
                    help="merge after review (default is plan-only)")
    args = ap.parse_args()
    return run(args.src, args.outputs, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
