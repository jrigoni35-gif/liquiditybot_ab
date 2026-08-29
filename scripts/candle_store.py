"""
scripts/candle_store.py — the candle store's operator CLI and polars lane.

SAFE class. Reads the journal, publishes a DISPOSABLE parquet index, and
answers "what does this store actually hold?". Every semantic - dedup
order, first-committed-wins, the canonical sort, the coverage algebra -
lives in data/candle_journal.py; this file only moves bytes and prints.

THE PARQUET TREE IS DISPOSABLE. `rm -r parquet/ && python
scripts/candle_store.py rebuild` reproduces it from the journal alone. That
single property neutralises every parquet weakness: not greppable -> grep
the journal; corrupt -> verify() then rebuild(); polars absent -> the
stdlib journal path answers the same questions, just slower.

`verify --deep` is the store's own INSTRUMENT-VERIFICATION hook: it
recompacts into a throwaway directory and asserts incremental == full. Run
it BEFORE citing any number this store produced.

Subcommands:
    verify [--deep]   parse every segment, report what it holds, exit 1 on
                      an instrument fault
    lanes             what the store holds, per (symbol, interval, source,
                      quote)
    coverage          expected/present/holes for one lane and window
    digest            the content digest (the reproducibility contract)
    compact [--full]  publish the parquet index
    rebuild           drop and re-publish the parquet index
    quarantine        move unparsable records out of a wedged store so
                      ingest can resume (--apply; dry run by default)
    unlock --force    clear a stale .ingest.lock (OPERATOR ONLY)
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runtime import atomic_write_json, replace_with_retry  # noqa: E402
from data import candle_journal as cj                           # noqa: E402

# Pinned parquet writer parameters. They are part of the published index's
# identity: 2016 five-minute bars is exactly 7 days, so a row group is a
# week. Changing any of them changes the file bytes without changing the
# data - which is precisely why the CONTENT digest, not the file sha, is
# the reproducibility contract.
PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 3
PARQUET_ROW_GROUP_SIZE = 2016


@dataclass
class CompactReport:
    partitions: int = 0
    rows: int = 0
    conflicts: int = 0
    skipped: bool = False
    canonical_digest: str = ""
    partition_files: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class VerifyReport:
    ok: bool = True
    segments: int = 0
    bar_rows: int = 0
    coverage_rows: int = 0
    reject_rows: int = 0
    conflicts: int = 0
    lanes: int = 0
    content_digest: str = ""
    canonical_digest: str = ""
    deep_matches: bool | None = None
    # None = no manifest published. True = MANIFEST.json no longer matches
    # the ledgers on disk, so its `lanes` inventory (and every t_min_s /
    # t_max_s in it) is from an earlier state of the store. Reported rather
    # than silently preferred; `lanes` below is ALWAYS journal-derived.
    manifest_stale: bool | None = None
    fault: str = ""


def _import_polars():
    """Lazy, in-function, with a guidance-bearing error.

    data/candle_journal.py imports polars NOWHERE at any scope - it is
    inside the engine-scope dependency-hygiene gate. This file is in
    scripts/, which is where the analysis stack legitimately lives."""
    try:
        import polars as pl
    except ImportError as exc:                      # pragma: no cover
        raise ImportError(
            "the parquet index needs polars (pip install polars). The "
            "journal is the source of truth and every query in "
            "data/candle_journal.py answers without it - only compact/"
            "rebuild need this.") from exc
    return pl


def _segment_shas(root: Path | str | None) -> dict[str, list]:
    """Delegates to the store's own helper so ONE map binds both the
    compaction skip-state and the published MANIFEST.json. It covers all
    three ledgers (journal, coverage, rejects), not the journal alone -
    which also means a coverage-only append correctly invalidates the
    skip."""
    return cj.segment_shas(root)


def _publish(tmp: Path, dest: Path) -> None:
    """PID-scoped tmp in the SAME directory, fsync before the rename,
    replace_with_retry for the Windows WinError-5 case, unlink on every
    exit path."""
    try:
        # r+b, not rb: Windows refuses fsync on a read-only handle with
        # EBADF, so a "rb" reopen would make the durability step silently
        # unreachable behind an exception on the platform this runs on.
        with open(tmp, "r+b") as f:
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp, dest)
    finally:
        Path(tmp).unlink(missing_ok=True)


def compact(root: Path | str | None = None, *, full: bool = False,
            ) -> CompactReport:
    """Publish the parquet index from the journal.

    full=False SKIPS THE WHOLE PASS when no journal segment's sha256 has
    changed since the last compaction. Per-PARTITION incrementality is NOT
    implemented and this docstring says so rather than implying it: when
    anything changed, every partition is rewritten. That is honest and
    cheap at this store's size; claiming finer granularity than the code
    delivers is the kind of confident-and-wrong artifact this repo keeps
    paying for."""
    pl = _import_polars()
    rep = CompactReport()
    shas = _segment_shas(root)
    state_path = cj.compaction_state_path(root)
    prior = {}
    if state_path.exists():
        try:
            prior = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prior = {}
    if not full and prior == shas and cj.parquet_dir(root).is_dir():
        rep.skipped = True
        rep.note = "no journal segment changed since the last compaction"
        rep.canonical_digest = cj.canonical_digest(root)
        return rep

    rows = cj.canonical_bar_rows(root)
    rep.rows = len(rows)
    rep.canonical_digest = cj.canonical_digest(root)
    rep.conflicts = sum(1 for r in cj._iter_bar_rows(root)
                        if r["record_kind"] == "CONFLICT")

    pdir = cj.parquet_dir(root)
    pdir.mkdir(parents=True, exist_ok=True)
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault((str(r["symbol"]), int(r["interval_s"])),
                          []).append(r)
    for (symbol, interval_s), part in sorted(groups.items()):
        frame = pl.DataFrame(
            {col: [r[col] for r in part] for col in cj.BAR_COLUMNS})
        dest = pdir / f"{symbol}_{interval_s}.parquet"
        if dest.resolve().parent != pdir.resolve():
            # BELT AND BRACES over the read-path symbol validation in
            # data/candle_journal._validate_row. `symbol` comes out of a
            # journal cell and goes straight into a filesystem path; the
            # store root lives under outputs/, so `..\..` reaches the repo.
            # Two independent checks, because this one is cheap and the
            # consequence is an overwrite outside the store.
            raise cj.CandleStoreUnreadable(
                f"partition path escapes the store root: {dest}")
        tmp = dest.with_suffix(dest.suffix + f".{os.getpid()}.tmp")
        frame.write_parquet(
            tmp, compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
            statistics=True, row_group_size=PARQUET_ROW_GROUP_SIZE)
        _publish(tmp, dest)
        rep.partitions += 1
        rep.partition_files.append(dest.name)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(state_path, shas)
    # MANIFEST LAST, so a crash leaves a stale-but-internally-valid pointer.
    atomic_write_json(cj.manifest_path(root), {
        "schema_version": cj.SCHEMA_VERSION,
        "ts_unit": "unix_seconds_utc",
        "ts_anchor": "bar_open",
        "written_at_s": int(time.time()),
        "rows": rep.rows,
        "conflicts": rep.conflicts,
        "canonical_digest": rep.canonical_digest,
        "content_digest": cj.content_digest(root),
        # BINDS THE INVENTORY TO THE BYTES IT WAS DERIVED FROM. Without it
        # cj.lanes() served this array verbatim forever - stale after the
        # next collect, and forgeable by anyone who can write a plain file
        # in the store root - while verify() reported it beside FRESH
        # bar_rows at ok:true.
        "segment_shas": shas,
        "lanes": cj.lanes(root=root),
    })
    return rep


def rebuild(root: Path | str | None = None) -> CompactReport:
    """Drop the parquet index and republish it from the journal alone.

    Proves the disposability claim rather than asserting it."""
    shutil.rmtree(cj.parquet_dir(root), ignore_errors=True)
    cj.compaction_state_path(root).unlink(missing_ok=True)
    return compact(root, full=True)


def verify(root: Path | str | None = None, *, deep: bool = False,
           ) -> VerifyReport:
    """Parse everything and report. An instrument fault sets ok=False.

    `lanes` is derived from the JOURNAL, never from MANIFEST.json - mixing a
    manifest-derived lane count with journal-derived bar_rows in one report
    is how a stale inventory reads as fresh. Manifest freshness is its own
    field."""
    rep = VerifyReport()
    try:
        rep.segments = len(cj._segments(cj.journal_dir(root)))
        bar_rows = list(cj._iter_bar_rows(root))
        rep.bar_rows = sum(1 for r in bar_rows if r["record_kind"] == "BAR")
        rep.conflicts = sum(1 for r in bar_rows
                            if r["record_kind"] == "CONFLICT")
        rep.coverage_rows = len(list(cj._iter_coverage_rows(root)))
        rep.reject_rows = len(list(cj._iter_reject_rows(root)))
        manifest = cj.read_json(cj.manifest_path(root))
        if isinstance(manifest, dict):
            rep.manifest_stale = (
                manifest.get("segment_shas") != cj.segment_shas(root))
        rep.lanes = len(cj.lanes(root=root))
        rep.content_digest = cj.content_digest(root)
        rep.canonical_digest = cj.canonical_digest(root)
    except cj.CandleStoreUnreadable as exc:
        rep.ok = False
        rep.fault = str(exc)
        return rep
    if deep:
        # THE INSTRUMENT-VERIFICATION HOOK: recompact into a throwaway
        # directory and assert incremental == full.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            shadow = Path(tmp) / "candles"
            (shadow / "journal").mkdir(parents=True, exist_ok=True)
            for p in cj.journal_dir(root).glob("*.csv"):
                shutil.copy2(p, shadow / "journal" / p.name)
            rep.deep_matches = (
                cj.canonical_digest(shadow) == rep.canonical_digest)
        rep.ok = rep.ok and bool(rep.deep_matches)
    return rep


@dataclass
class QuarantineReport:
    ok: bool = True
    applied: bool = False
    segments_touched: int = 0
    records_quarantined: int = 0
    records_kept: int = 0
    sidecars: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    fault: str = ""


def _quarantine_segment(path: Path, columns: tuple[str, ...], *, apply: bool,
                        rep: QuarantineReport) -> None:
    """Split ONE segment into keepers and unparsable fragments.

    A fragment is a row whose field count differs from the header, or whose
    closed-vocabulary cells are outside their sets - the two shapes that
    make data/candle_journal refuse the whole store. The header itself is
    NEVER guessed at: a segment whose header is not this generation's
    schema is left completely alone and reported as a fault, because a
    wrong header means we do not know what any of its columns mean."""
    with open(path, encoding="utf-8", newline="") as f:
        raw_rows = [r for r in csv.reader(f) if r != []]
    if not raw_rows or tuple(raw_rows[0]) != columns:
        rep.ok = False
        rep.fault = (f"{path.name}: header is not the schema - refusing to "
                     f"guess. Resolve by hand.")
        return
    keep: list[list[str]] = []
    drop: list[tuple[int, list[str]]] = []
    for lineno, row in enumerate(raw_rows[1:], start=2):
        if len(row) != len(columns):
            drop.append((lineno, row))
            continue
        try:
            cj._validate_row(path, lineno,
                             dict(zip(columns, row, strict=True)))
        except cj.CandleStoreUnreadable as exc:
            drop.append((lineno, row))
            rep.details.append(f"{path.name}:{lineno} {exc}")
            continue
        keep.append(row)
    rep.records_kept += len(keep)
    if not drop:
        return
    rep.segments_touched += 1
    rep.records_quarantined += len(drop)
    for lineno, row in drop:
        rep.details.append(f"{path.name}:{lineno} -> quarantined: {row!r}")
    if not apply:
        return
    stamp = f"{os.getpid()}_{int(time.time())}"
    # The sidecar lives in its OWN directory, never beside the segment: a
    # *.csv file inside a ledger directory is a segment by definition, and
    # data/candle_journal._segments refuses a name it does not recognise -
    # so a sidecar dropped next to the segment would wedge the store it
    # just unwedged.
    qdir = path.parent.parent / "quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    sidecar = qdir / f"{path.parent.name}.{path.name}.quarantine_{stamp}.csv"
    with open(sidecar, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_segment", "source_lineno", "raw_fields"])
        for lineno, row in drop:
            w.writerow([path.name, lineno, json.dumps(row)])
    rep.sidecars.append(sidecar.name)
    backup = path.with_suffix(path.suffix + f".preschema_{stamp}")
    shutil.copy2(path, backup)
    tmp = path.with_suffix(path.suffix + f".quarantine.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(list(columns))
        for row in keep:
            w.writerow(row)
    replace_with_retry(tmp, path)


def quarantine(root: Path | str | None = None, *, apply: bool = False,
               ) -> QuarantineReport:
    """THE OPERATOR ESCAPE HATCH FOR A WEDGED STORE. Dry run by default.

    One kill-torn record makes EVERY lane answer STORE_UNREADABLE and makes
    ingest() refuse to append at all - correct (an instrument fault must
    never read as a data hole) but terminal, because the store is
    append-only and durable_append's own "the reader skips the junk line"
    recovery is deliberately unavailable here. Meanwhile the 5m collector
    lane and Kraken's 720-bar cap mean the wedge window is not
    re-acquirable, so "resolve it by hand" is a race against data loss.

    This moves the unparsable fragments into a `.quarantine_<pid>_<ts>.csv`
    sidecar (they are never deleted), keeps a `.preschema_` copy of the
    whole segment, and rewrites the segment with the survivors - under the
    INGEST LOCK, refusing rather than stealing. It appends nothing, invents
    nothing, and repairs nothing: a fragment stays a fragment, in a file, on
    disk, for whoever wants to read it."""
    rep = QuarantineReport()
    # THE DRY RUN TAKES NO LOCK AND CREATES NOTHING - not even the lock
    # file. data/candle_journal's P8 rule is that reading creates nothing,
    # and a report is a read. --apply is the only path that writes, and it
    # is the only path that locks.
    with (cj.ingest_lock(root) if apply
          else contextlib.nullcontext(True)) as acquired:
        if not acquired:
            rep.ok = False
            rep.fault = ("the ingest lock is held - refusing to rewrite a "
                         "segment underneath a live writer")
            return rep
        for directory, by_version in (
                (cj.journal_dir(root), cj._BAR_COLUMNS_BY_VERSION),
                (cj.coverage_dir(root), cj._COVERAGE_COLUMNS_BY_VERSION),
                (cj.reject_dir(root), cj._REJECT_COLUMNS_BY_VERSION)):
            if not directory.is_dir():
                continue
            for p in sorted(directory.glob("*.csv")):
                m = cj._SEGMENT_RE.match(p.name)
                if m is None:
                    rep.ok = False
                    rep.fault = (f"{p.name}: not a segment name - refusing "
                                 f"to touch it")
                    return rep
                version = int(m.group(3))
                columns = by_version.get(version)
                if columns is None:
                    rep.ok = False
                    rep.fault = (f"{p.name} is schema v{version}; this code "
                                 f"reads up to v{cj.SCHEMA_VERSION}. Upgrade "
                                 f"the reader - do NOT downgrade the file.")
                    return rep
                _quarantine_segment(p, columns, apply=apply, rep=rep)
                if not rep.ok:
                    return rep
        rep.applied = apply
    return rep


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__ or "",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="store root")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("verify")
    p_ver.add_argument("--deep", action="store_true")
    sub.add_parser("lanes").add_argument("--symbol", default=None)
    sub.add_parser("digest")
    p_cov = sub.add_parser("coverage")
    p_cov.add_argument("--symbol", required=True)
    p_cov.add_argument("--interval", type=int, required=True)
    p_cov.add_argument("--source", required=True)
    p_cov.add_argument("--quote", required=True)
    p_cov.add_argument("--from-s", type=int, required=True)
    p_cov.add_argument("--to-s", type=int, required=True)
    p_com = sub.add_parser("compact")
    p_com.add_argument("--full", action="store_true")
    sub.add_parser("rebuild")
    p_qua = sub.add_parser("quarantine")
    p_qua.add_argument("--apply", action="store_true",
                       help="commit the excision; without it this is a dry "
                            "run that only names the fragments")
    p_unl = sub.add_parser("unlock")
    p_unl.add_argument("--force", action="store_true", required=True,
                       help="required: an automatic steal is the "
                            "gate-releases-the-thing-it-blocks shape")
    args = ap.parse_args(argv)
    root = args.root

    if args.cmd == "verify":
        rep = verify(root, deep=args.deep)
        print(json.dumps(rep.__dict__, indent=1, default=str))
        return 0 if rep.ok else 1
    if args.cmd == "lanes":
        for row in cj.lanes(getattr(args, "symbol", None), root=root):
            print(json.dumps(row, default=str))
        return 0
    if args.cmd == "digest":
        print(f"content_digest   {cj.content_digest(root)}")
        print(f"canonical_digest {cj.canonical_digest(root)}")
        return 0
    if args.cmd == "coverage":
        out = cj.coverage(args.symbol, args.interval, args.from_s, args.to_s,
                          series=cj.Series(args.source, args.quote),
                          root=root)
        print(json.dumps(out, indent=1, default=str))
        return 0
    if args.cmd == "compact":
        print(json.dumps(compact(root, full=args.full).__dict__, indent=1))
        return 0
    if args.cmd == "rebuild":
        print(json.dumps(rebuild(root).__dict__, indent=1))
        return 0
    if args.cmd == "quarantine":
        qrep = quarantine(root, apply=args.apply)
        print(json.dumps(qrep.__dict__, indent=1, default=str))
        if not qrep.applied and qrep.records_quarantined:
            print("\nDRY RUN - nothing moved. Re-run with --apply.")
        return 0 if qrep.ok else 1
    if args.cmd == "unlock":
        age = cj.lock_age_s(root)
        if age is None:
            print("no ingest lock held")
            return 0
        cj.lock_path(root).unlink(missing_ok=True)
        print(f"cleared ingest lock (heartbeat age {age:.0f}s; stale "
              f"threshold {cj.LOCK_STALE_S}s)")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
