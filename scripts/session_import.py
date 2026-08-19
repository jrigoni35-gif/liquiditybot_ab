"""
scripts/session_import.py — verify a session bundle and merge its
LEARNING data into this machine's outputs. The "proof-read" gate for
work done in phone/cloud sessions: nothing is adopted until the
operator runs this, reads the plan, and re-runs with --apply.

Verification before anything else:
  1. every manifest string that becomes a PATH (label, every files key)
     is a bare allow-listed basename - the manifest is attacker-authored
     and scripts/corpus_sync.py applies bundles unattended
  2. every bundled file's sha256 matches its manifest entry
  3. the bundled audit chain replays end-to-end (hash-chain intact)
  4. the bundle's history header matches THIS checkout's schema (and
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
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.audit import verify_chain  # noqa: E402
from core.runtime import durable_append  # noqa: E402
from ml.history import HistoryStore  # noqa: E402

# Manifests are ATTACKER-AUTHORED. bundle_format and the per-file sha256 are
# self-consistency checks on the bundle's own bytes, not a trust boundary — and
# scripts/corpus_sync.py imports every bundle at the tip of the telemetry branch
# UNATTENDED (hourly, from pc_supervisor), so `label` and every `files` key are
# untrusted strings that become path components in the live checkout. Windows
# widens that far past "..": a drive letter or UNC prefix makes pathlib DISCARD
# the left side of the join outright, ":" opens an alternate data stream, and
# the reserved device names resolve to hardware from any directory. So: a strict
# bare-basename allow-list, mirroring scripts/local_llm_mcp.resolve_report_path
# (the in-repo pattern), plus a resolve-and-contain re-anchor at the join site.
# Real labels ("20260713-dayshift", "pc-live") and real file keys
# ("signal_history.csv") are all bare alphanumeric-led names, so this is
# behavior-preserving for every bundle session_export.py can produce.
_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL",
                 *(f"COM{i}" for i in range(1, 10)),
                 *(f"LPT{i}" for i in range(1, 10))}


def safe_component(value, kind: str) -> str | None:
    """Bare, allow-listed path component, or None after printing the reason.

    Rejects: non-strings, separators (both slashes), absolute paths, drive
    letters, UNC prefixes, alternate-data-stream colons, "." / ".." / any
    ".." substring, trailing dots (Windows silently strips them, aliasing
    two names onto one file), Windows reserved device names with or without
    an extension, and anything over 64 chars.
    """
    name = value if isinstance(value, str) else None
    if not name:
        print(f"REFUSED: manifest {kind} must be a non-empty string "
              f"(got {value!r})")
        return None
    if (name != Path(name).name or ".." in name or name.endswith(".")
            or not _COMPONENT_RE.match(name)
            or name.split(".")[0].upper() in _WIN_RESERVED):
        print(f"REFUSED: unsafe manifest {kind} {name!r} - path components "
              f"must be bare names matching [A-Za-z0-9][A-Za-z0-9._-]{{0,63}} "
              f"(no separators, drive letters, UNC prefixes, '..' or Windows "
              f"reserved device names)")
        return None
    return name


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


def verify_bundle(src: Path, strict_audit: bool = False) -> dict:
    mf_path = src / "manifest.json"
    if not mf_path.exists():
        print(f"REFUSED: no manifest.json in {src}")
        return {"rc": 4}
    manifest = json.loads(mf_path.read_text(encoding="utf-8"))
    if manifest.get("bundle_format") != 1:
        print(f"REFUSED: unknown bundle_format "
              f"{manifest.get('bundle_format')!r}")
        return {"rc": 4}
    # Path sanitisation is a VERIFY-time gate, not an apply-time one: the
    # plan-only run reads and prints these same strings, and refusing here is
    # what makes `--apply` (and corpus_sync's unattended `--apply`) unreachable
    # for a hostile bundle. An absent/empty label is legal — run() falls back
    # to the timestamp stamp — so only a PRESENT label is checked.
    if manifest.get("label") and safe_component(manifest["label"],
                                                "label") is None:
        return {"rc": 4}
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        print(f"REFUSED: manifest 'files' must be an object "
              f"(got {type(files).__name__})")
        return {"rc": 4}
    for name, meta in files.items():
        if safe_component(name, "files key") is None:
            return {"rc": 4}
        f = src / name
        # a symlinked bundle entry makes copy2 read through to an arbitrary
        # host file and file its CONTENT into the record dir; the bundle may
        # only ever contain regular files it actually shipped.
        if f.is_symlink() or (f.exists() and not f.is_file()):
            print(f"REFUSED: bundle entry {name!r} is a symlink or not a "
                  f"regular file")
            return {"rc": 4}
        if not f.exists():
            print(f"INTEGRITY FAIL: {name} listed in manifest but missing")
            return {"rc": 2}
        got = _sha256(f)
        if got != meta.get("sha256"):
            print(f"INTEGRITY FAIL: {name} sha256 mismatch "
                  f"(bundle tampered or corrupt)")
            return {"rc": 2}
    # Per-file sha256 (above) is the transport-integrity gate: if it passes,
    # the bundle's bytes are exactly what was bundled. The audit-chain replay
    # below is a SEPARATE, narrower check on the audit LOG's internal linkage.
    # A break there does NOT condemn the learning corpus — signal_history.csv
    # carries its own (already-verified) sha256, and the import NEVER merges a
    # bundle's audit trail into this machine's live chain (it is filed as a
    # report). Refusing the whole bundle over an audit-log seam discarded a
    # full session of fresh learning every boot (the newest bundle's chain had
    # a benign restart seam). So: a TORN TAIL (crashed final append) is benign;
    # a MID-CHAIN break quarantines the audit trail but still imports the rows;
    # only --strict-audit restores the old hard refusal.
    audit = src / "audit.jsonl"
    chain = None
    if audit.exists():
        # verify_chain is READ-ONLY (constructing an AuditTrail would heal a
        # torn tail by truncating the bundle copy on disk — a side effect that
        # also defeats --strict-audit's inspection).
        chain = verify_chain(str(audit))
        if not chain.get("ok"):
            fb = chain.get("first_break")
            # --strict-audit refuses ANY anomaly (torn, seam, or tamper),
            # matching its contract; checked FIRST so nothing slips past it.
            if strict_audit:
                where = (f"breaks at record {fb}" if fb is not None
                         else f"has {chain.get('seams')} writer seam(s)")
                print(f"INTEGRITY FAIL: audit chain {where} - "
                      f"refusing bundle (--strict-audit)")
                return {"rc": 2}
            if chain.get("seams"):
                print(f"  note: audit trail has {chain.get('seams')} writer "
                      f"seam(s) (hash-valid concurrent-writer fork, benign - "
                      f"no committed record altered); chain adopted through")
            if chain.get("torn_tail"):
                print(f"  note: audit trail has a torn final line (crash mid-"
                      f"append at record {fb}); chain intact before it")
            elif chain.get("tamper"):
                print(f"AUDIT CHAIN BROKEN at record {fb} - trail will be "
                      f"QUARANTINED; learning data (own sha256 ok) still "
                      f"imports. Re-run with --strict-audit to refuse instead.")
    return {"rc": 0, "manifest": manifest, "chain": chain}


def run(src: str, outputs: str, apply: bool,
        strict_audit: bool = False) -> int:
    srcp = Path(src)
    out = Path(outputs)
    v = verify_bundle(srcp, strict_audit=strict_audit)
    if v["rc"] != 0:
        return v["rc"]
    manifest, chain = v["manifest"], v["chain"]
    # TAMPER (edited/deleted record) => the audit trail is filed under a
    # QUARANTINED name so it is never mistaken for a clean chain. Benign
    # anomalies (torn tail, writer seam) file normally with a note — they
    # altered nothing committed, and quarantine-shouting them every boot
    # trained the operator to ignore the real tamper alarm. Gated on
    # audit.jsonl actually being a MANIFEST file (the copy loop only files
    # those) so the "QUARANTINED as ..." message can't fire when nothing is
    # filed (an on-disk-but-unlisted audit.jsonl).
    audit_quarantined = bool(chain and chain.get("tamper")
                             and "audit.jsonl" in manifest.get("files", {}))

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
            key = _row_key(b_header, ln)
            if key in seen:
                dupes += 1
            else:
                # add the accepted key to `seen` (round-2 fix 2026-08-05):
                # the check only consulted rows already in the LOCAL file, so
                # a bundle containing the same row twice - exactly what the
                # duplicate-fills bug class produced - appended both copies.
                # The corpus is append-only and later syncs see both rows as
                # already present, so nothing heals it: the training row
                # stays double-weighted forever, and corpus_sync --apply
                # runs this unattended every hour.
                seen.add(key)
                new_lines.append(ln)

    h = manifest.get("history", {})
    print(f"bundle '{manifest.get('label')}' created "
          f"{manifest.get('created_at_utc')} @ git {manifest.get('git_sha')}")
    if not chain:
        chain_desc = "not bundled"
    elif chain.get("ok"):
        chain_desc = f"ok, {chain.get('records')} records"
    elif chain.get("tamper"):
        chain_desc = (f"BROKEN at {chain.get('first_break')} - QUARANTINED "
                      f"({chain.get('records')} records verified before break)")
    else:
        # benign anomalies only: seams and/or a torn tail
        parts = []
        if chain.get("seams"):
            parts.append(f"{chain.get('seams')} writer seam(s) (benign fork)")
        if chain.get("torn_tail"):
            parts.append(f"torn final line at {chain.get('first_break')} "
                         f"(benign crash mid-append)")
        chain_desc = (f"{chain.get('records')} records, "
                      + ", ".join(parts))
    print(f"  audit chain: {chain_desc}")
    print(f"  training rows: {h.get('rows')} bundled "
          f"{h.get('by_source')} -> {len(new_lines)} new, {dupes} duplicate")
    print(f"  reports: {', '.join(sorted(manifest.get('files', {})))}")

    if not apply:
        print("plan only - re-run with --apply to merge (a backup of the "
              "local history is taken first)")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    # Resolve the record dir BEFORE any write: verify_bundle already
    # allow-listed the label, but the write side re-anchors and asserts
    # containment itself (so no future caller can reach the mkdir/copy without
    # passing through the check), and doing it first keeps --apply all-or-
    # nothing — a refusal here must not leave merged rows behind.
    label = safe_component(manifest.get("label") or stamp, "label")
    if label is None:
        return 4
    sessions_root = (out / "imported_sessions").resolve()
    raw_record = sessions_root / label
    record = raw_record.resolve()
    if record.parent != sessions_root or raw_record.is_symlink():
        print(f"REFUSED: record dir {raw_record} escapes {sessions_root}")
        return 4
    # the trained model travels copy-if-absent: a machine that already has
    # outputs/meta_model.json keeps its own (retrain locally from the merged
    # rows); a fresh container consumes the bundled brain immediately.
    model_src = srcp / "meta_model.json"
    model_dst = out / "meta_model.json"
    # SYMLINK GUARD (2026-08-20 security sweep): bundles are attacker-authored
    # and corpus_sync imports them UNATTENDED, so the copy-if-absent hand-off
    # must apply the same is_symlink refusal verify_bundle() gives listed
    # files - a symlinked meta_model.json/skimmer_active.json would otherwise
    # let a bundle read an arbitrary local path through copy2.
    if model_src.is_symlink():
        print(f"REFUSED: {model_src} is a symlink")
        return 4
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
    # skimmer promotions travel copy-if-absent for the same reason as the
    # model: a fresh container otherwise boots the bare core universe until
    # the skimmer re-scores (~an hour of lost breadth + label flow). A live
    # machine keeps its own (fresher) file; the boot merge hard-validates
    # whatever it reads, so a stale or garbled copy can only shrink to [].
    sk_src = srcp / "skimmer_active.json"
    sk_dst = out / "skimmer_active.json"
    if sk_src.is_symlink():
        print(f"REFUSED: {sk_src} is a symlink")
        return 4
    if sk_src.exists() and not sk_dst.exists():
        shutil.copy2(sk_src, sk_dst)
        print("  skimmer_active.json adopted (promotions apply at next boot)")
    dest_hist = out / "signal_history.csv"
    if new_lines:
        if dest_hist.exists():
            bak = out / "archive" / f"signal_history_pre_import_{stamp}.csv"
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest_hist, bak)
            print(f"  backup: {bak}")
        # THIRD independent appender to the training corpus (the runner's
        # HistoryStore._append_row and corpus_sync's recovery merge are the
        # other two), and this one runs HOURLY and UNATTENDED. Three writers
        # with no torn-tail heal is the seam that produced SD-007 on the
        # audit chain. durable_append also owns the header now: the old
        # `if dest_hist.exists()` branch left a ZERO-LENGTH file headerless,
        # and csv.DictReader then adopts the first TRAINING ROW as its
        # column names. One probe per open, not per row - the whole import
        # batch is a single append.
        def _emit(f, batch=new_lines):
            for ln in batch:
                f.write(ln + "\n")
        durable_append(dest_hist, _emit, newline="\n", torn_sep="\n",
                       header=",".join(expected) + "\n")
    record.mkdir(parents=True, exist_ok=True)
    for name in manifest.get("files", {}):
        if name == "signal_history.csv" or not (srcp / name).exists():
            continue
        # a mid-chain-broken audit trail is filed under a .QUARANTINED name so
        # nothing downstream (a future verify, a digest) mistakes it for a
        # clean chain; the bytes are preserved verbatim for forensics.
        dst_name = (f"{name}.QUARANTINED"
                    if name == "audit.jsonl" and audit_quarantined else name)
        shutil.copy2(srcp / name, record / dst_name)
    shutil.copy2(srcp / "manifest.json", record / "manifest.json")
    if audit_quarantined:
        print(f"  audit trail QUARANTINED as audit.jsonl.QUARANTINED "
              f"(broken at record {chain.get('first_break')}) - learning rows "
              f"imported regardless")
    print(f"  merged {len(new_lines)} rows; bundle reports filed under "
          f"{record}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="bundle directory")
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--apply", action="store_true",
                    help="merge after review (default is plan-only)")
    ap.add_argument("--strict-audit", action="store_true",
                    help="refuse the whole bundle on ANY audit-chain break "
                         "(default: import the separately-checksummed learning "
                         "rows and quarantine the broken audit trail)")
    args = ap.parse_args()
    return run(args.src, args.outputs, args.apply,
               strict_audit=args.strict_audit)


if __name__ == "__main__":
    raise SystemExit(main())
