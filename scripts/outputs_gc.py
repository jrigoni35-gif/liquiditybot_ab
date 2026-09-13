"""scripts/outputs_gc.py - read-and-recycle for outputs/, modelled on CPython.

WHY THIS EXISTS. outputs/ had a create step and a consume step and no retire
step. ml/history.py rotates signal_history to .bak_<ts> on every schema
change; scripts/corpus_sync.py recover_local_baks() merges them back. Nothing
ever reclaimed them, so 15 artifacts / 56.7MB accumulated over 34 days. The
same shape recurs across this repo: a pipeline missing its final stage.

THE MODEL IS CPython'S, NOT "delete old files".
  REFCOUNT     an artifact's refcount is the number of INFORMATION UNITS it
               holds that the live corpus does not. For a row corpus that is
               (a) row keys present here and absent live, plus (b) COLUMNS
               present here and absent live. Zero means redundant, not old.
  REACHABILITY anything referenced by tracked source is reachable and is
               never collected, whatever its refcount or age. The
               .stamp/.done sentinels are reachable via pc_supervisor.py.
  GENERATIONS  gen0 artifacts (younger than --gen0-days) are never collected.
               Youth is not evidence of redundancy, but a young artifact is
               the one most likely to still be mid-merge.
  RECYCLE      collection MOVES bytes to outputs/archive/ and writes a
               manifest recording what was PROVEN about each artifact. The
               information about the artifact survives the reclamation of the
               artifact. Nothing is unlinked by this tool, ever.

AGE IS NOT A REASON. A 34-day artifact holding one unmerged row is kept; a
one-hour artifact fully subsumed is collectable the moment it leaves gen0.
That is what "the optimal information at the appropriate time" has to mean if
it is going to be safe: reclaim redundancy, never reclaim information.

REPORT-ONLY BY DEFAULT. --apply is required to move anything, and --apply
still refuses any artifact that is reachable, in gen0, or refcount > 0.

    python scripts/outputs_gc.py [--outputs DIR] [--gen0-days N] [--json]
                                 [--apply]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess  # nosec B404 - git grep for reachability, fixed argv
import sys
import time
from pathlib import Path

# Artifacts whose refcount can be COMPUTED against a live counterpart. Anything
# not listed here is reported but never proposed for collection: an artifact
# whose redundancy cannot be proven is not redundant.
CORPUS_PAIRS = [
    ("signal_history.bak_*.recovered", "signal_history.csv", "position_id"),
    ("signal_history.bak_*", "signal_history.csv", "position_id"),
    ("fills.csv.bak_*", "fills.csv", "order_id"),
    ("fills.csv.preschema_*", "fills.csv", "order_id"),
    ("horizon_shadow.bak_*.csv", "horizon_shadow.csv", "position_id"),
]

# Never considered, at any age, for any reason.
NEVER = {
    "status.json", "audit.jsonl", "signal_history.csv", "fills.csv",
    "events.jsonl", "runner.log", "horizon_shadow.csv", "state.json",
    # watch_history.csv (core/watch_lane.py, 2026-09-13) - a CORPUS, and the
    # lane accrues it slowly by design, so age is exactly the wrong signal to
    # collect it on. Added in the commit that introduced the file rather than
    # after the first silent deletion.
    "watch_history.csv",
}


def _header_and_keys(path: Path, key: str):
    """Return (header, {key values}, row count). Tolerates ragged rows."""
    keys: set[str] = set()
    rows = 0
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            r = csv.reader(f)
            try:
                header = next(r)
            except StopIteration:
                return [], keys, 0
            if key not in header:
                return header, keys, 0
            i = header.index(key)
            for row in r:
                rows += 1
                if len(row) > i and row[i]:
                    keys.add(row[i])
    except OSError:
        return [], keys, 0
    return header, keys, rows


def refcount(artifact: Path, live: Path, key: str) -> dict:
    """Information units in `artifact` that `live` does not carry.

    TWO components, because either alone is a false negative:
      orphan_keys    rows whose identity is absent from live
      dropped_cols   columns that existed then and do not exist now - their
                     values survive ONLY here even when every row id matches
    """
    if not live.exists():
        return {"computable": False, "why": f"no live counterpart {live.name}"}
    a_hdr, a_keys, a_rows = _header_and_keys(artifact, key)
    l_hdr, l_keys, _ = _header_and_keys(live, key)
    if not a_hdr or not l_hdr:
        return {"computable": False, "why": "unreadable or empty csv"}
    if key not in a_hdr:
        return {"computable": False, "why": f"no {key} column in artifact"}
    orphan = a_keys - l_keys
    dropped = [c for c in a_hdr if c not in set(l_hdr)]
    return {
        "computable": True, "rows": a_rows, "keys": len(a_keys),
        "orphan_keys": len(orphan), "dropped_cols": dropped,
        "refcount": len(orphan) + len(dropped),
        "sample_orphans": sorted(orphan)[:5],
    }


def reachable(name: str, root: Path) -> list[str]:
    """Referenced by tracked source? Reachable objects are never collected."""
    try:
        r = subprocess.run(  # nosec B603 B607 - fixed argv, name is a filename
            ["git", "grep", "-l", "--fixed-strings", name, "--",
             "*.py", "*.bat", "*.ps1", "*.json", "*.md"],
            capture_output=True, text=True, cwd=str(root), timeout=60)
    except (OSError, subprocess.SubprocessError):
        # Cannot prove unreachable -> treat as REACHABLE. Failing closed is
        # the only safe direction for a tool that moves data.
        return ["<git unavailable - assumed reachable>"]
    # THE RETURN CODE IS PART OF THE ANSWER. Until 2026-09-05 only the
    # EXCEPTION path failed closed; a git that RAN and failed - rc=128 on a
    # non-git root, the exact shape of a worktree or an unpacked deliverable -
    # returned empty stdout, which `[h for h in r.stdout.split()]` renders as
    # `[]`, i.e. "0 references, safe to collect". Measured: a referenced corpus
    # file archived, `{'moved': 1, 'bytes_freed': 31}`.
    #
    # "git failed" and "nothing references this" are the SAME OBSERVATION until
    # separated, and this function already knew the right answer for the other
    # failure mode two lines up. rc 0 = matches, rc 1 = a real no-match; any
    # other rc is git declining to answer.
    if r.returncode not in (0, 1):
        return ["<git unavailable - assumed reachable>"]
    return [h for h in r.stdout.split() if h]


def survey(outputs: Path, root: Path, gen0_days: int) -> dict:
    now = time.time()
    matched: dict[Path, tuple] = {}
    for pattern, live_name, key in CORPUS_PAIRS:
        for p in sorted(outputs.glob(pattern)):
            if p.is_file() and p not in matched and p.name not in NEVER:
                matched[p] = (live_name, key)

    items = []
    for p, (live_name, key) in matched.items():
        age_d = (now - p.stat().st_mtime) / 86400.0
        rc = refcount(p, outputs / live_name, key)
        refs = reachable(p.name, root)
        gen = 0 if age_d < gen0_days else (1 if age_d < gen0_days * 10 else 2)
        collectable = bool(
            rc.get("computable") and rc.get("refcount") == 0
            and not refs and gen > 0)
        reasons = []
        if not rc.get("computable"):
            reasons.append(rc.get("why", "refcount not computable"))
        elif rc["refcount"]:
            reasons.append(
                f"refcount {rc['refcount']} "
                f"({rc['orphan_keys']} orphan keys, "
                f"{len(rc['dropped_cols'])} dropped cols)")
        if refs:
            reasons.append(f"reachable from {len(refs)} source file(s)")
        if gen == 0:
            reasons.append(f"gen0 (younger than {gen0_days}d)")
        items.append({
            "file": p.name, "bytes": p.stat().st_size,
            "age_days": round(age_d, 1), "generation": gen,
            "live_counterpart": live_name, "key": key,
            "refcount_detail": rc, "referenced_by": refs,
            "collectable": collectable,
            "kept_because": reasons,
        })
    items.sort(key=lambda d: (not d["collectable"], -d["bytes"]))
    return {
        "outputs": str(outputs), "gen0_days": gen0_days,
        "surveyed": len(items),
        "collectable": sum(1 for i in items if i["collectable"]),
        "reclaimable_bytes": sum(i["bytes"] for i in items if i["collectable"]),
        "items": items,
    }


def collect(res: dict, outputs: Path) -> dict:
    """MOVE collectable artifacts to archive/ and record what was proven.

    Never unlinks. The manifest is the point: after this runs, the bytes are
    reclaimed but the CLAIM that they were redundant remains auditable.
    """
    arch = outputs / "archive" / ("gc-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%SZ"))
    moved, freed = [], 0
    arch.mkdir(parents=True, exist_ok=True)
    for it in res["items"]:
        if not it["collectable"]:
            continue
        src = outputs / it["file"]
        try:
            shutil.move(str(src), str(arch / it["file"]))
        except OSError as e:
            it["move_error"] = str(e)[:120]
            continue
        moved.append(it["file"])
        freed += it["bytes"]
    manifest = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "tool": "scripts/outputs_gc.py",
        "basis": ("refcount 0 = every row key and every column present in "
                  "this artifact is present in the live corpus"),
        "moved": moved, "bytes_freed": freed,
        "proof": [i for i in res["items"] if i["file"] in moved],
    }
    (arch / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    return {"archive": str(arch), "moved": len(moved), "bytes_freed": freed}


def _render(res: dict, applied: dict | None) -> None:
    print("OUTPUTS GC - refcount + reachability + generations, CPython-style")
    print("=" * 72)
    print("outputs   %s" % res["outputs"])
    print("surveyed  %d artifact(s) with a computable live counterpart"
          % res["surveyed"])
    print("")
    print("%-46s %10s %6s %4s" % ("ARTIFACT", "BYTES", "AGE_D", "GEN"))
    print("-" * 72)
    for i in res["items"]:
        mark = "RECYCLE" if i["collectable"] else "KEEP"
        print("%-46s %10s %6.1f %4d  %s"
              % (i["file"][:46], f"{i['bytes']:,}", i["age_days"],
                 i["generation"], mark))
        d = i["refcount_detail"]
        if d.get("computable"):
            print("      rows %s | keys %s | orphan %s | dropped cols %s"
                  % (d["rows"], d["keys"], d["orphan_keys"],
                     d["dropped_cols"] or "none"))
        if not i["collectable"]:
            print("      kept: %s" % "; ".join(i["kept_because"]))
    print("-" * 72)
    print("collectable: %d artifact(s), %s bytes"
          % (res["collectable"], f"{res['reclaimable_bytes']:,}"))
    if applied:
        print("")
        print("APPLIED: moved %d artifact(s), freed %s bytes"
              % (applied["moved"], f"{applied['bytes_freed']:,}"))
        print("archive: %s" % applied["archive"])
        print("(moved, never unlinked; MANIFEST.json records the proof)")
    else:
        print("")
        print("DRY RUN. Nothing moved. Re-run with --apply to recycle.")
    print("")
    print("WHAT THIS CANNOT SEE: refcount is computed on the key column and")
    print("the column SET. It does not compare cell VALUES, so a row edited")
    print("in place after rotation reads as subsumed. It also cannot know")
    print("whether an artifact matters to something outside this repo.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--root", default=".")
    ap.add_argument("--gen0-days", type=int, default=3,
                    help="artifacts younger than this are never collected")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="move collectable artifacts into outputs/archive/")
    ns = ap.parse_args()
    outputs = Path(ns.outputs)
    if not outputs.is_dir():
        print("no outputs dir at %s" % outputs)
        return 2
    res = survey(outputs, Path(ns.root), ns.gen0_days)
    applied = collect(res, outputs) if ns.apply else None
    if ns.json:
        print(json.dumps({"survey": res, "applied": applied}, indent=1))
    else:
        _render(res, applied)
    return 0


if __name__ == "__main__":
    sys.exit(main())
