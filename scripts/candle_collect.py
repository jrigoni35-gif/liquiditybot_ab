"""
scripts/candle_collect.py — LANE A: recover the 5m path from state.json.

SAFE class, and the primary lane. A PURE READ of outputs/state.json plus
appends into outputs/candles/. Zero venue calls. It never writes, locks,
rotates or truncates state.json, and it is imported by nothing in the
decision path.

WHY THIS RUNS FIRST. ml/history.py's CandidateLabeler.update_candles keeps
`cap = self.horizon * 5` bars per asset and DISCARDS the rest every cycle,
and Kraken cannot re-serve 5m history past its 720-bar window (~2.5 days).
Every day this is not running is 5m path permanently lost - not lost from
this store, lost from the world. A venue backfill spends API calls to
reacquire a WORSE version of data this process is throwing away right now.

WHY IT IS THE FAITHFUL LANE. The corpus's `entry_price` IS a close from
this very cache (ml/history.py takes `entry_price=float(closes[i])` where
`closes = b["c"]`), rendered through the same %.10g formatter the store
uses. A store fed from here is byte-comparable to the labels. Any venue
backfill is a DIFFERENT series: different feed, different forming-bar
treatment, possibly a different quote currency.

THREE RULES, ALL PINNED BY TEST:

 1. IT ONLY EVER READS state.json.

 2. AN UNREADABLE POLL WRITES NOTHING - not even a coverage row. The read
    goes through core.runtime.read_json, which returns None on ANY
    OS/parse/decode error; on None this counts `poll_unreadable` and
    SKIPS. A coverage row for a failed poll would fabricate a permanent
    phantom hole into an append-only store. (state.json is published
    through StateStore._seal_and_write, so a reader sees old-or-new and
    never torn; the residual risk is a transient PermissionError inside
    the replace window, handled as the same skip.)

 2b. A LOST POLL EXITS NON-ZERO AND SAYS WHICH LANE. `status` and `written`
    are printed per asset and drive the exit code (see lost_polls). A poll
    refused by the ingest lock, or one whose append failed, writes nothing
    at all - and on this lane a silently skipped poll is 5m path lost from
    the world. "0 findings" and "the scan is broken" are the same
    observation until separated.

 3. PER-ASSET RIGHT EDGE, NEVER THE WALL CLOCK. `committed_upto_s` comes
    from THAT ASSET'S OWN newest cached bar. MEASURED live on this box at
    one instant [K, read_at_s=1788020156.44, state.json
    mtime=1788020127.93, size=3,248,129 B]: the per-asset right edges
    spanned 586,200 s = 6.785 DAYS - AVAX's newest bar was 1787433600
    while LINK/MINA/PAXG were at 1788019800. A collector using the poll
    time as the right edge would claim coverage over roughly 1,950
    five-minute bars per stale asset that were never observed, and every
    one of them would then read as a REAL HOLE instead of an honest
    NOT_COVERED.

The ring carries t/c/h/l ONLY - no open, no volume - so both are stored as
UNKNOWN (''), permanently, on this lane. They are never 0.0.

Usage:
    python scripts/candle_collect.py --dry-run
    python scripts/candle_collect.py --once
    python scripts/candle_collect.py --interval-poll-s 300 --cycles 12
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runtime import read_json                # noqa: E402
from data import candle_journal as cj             # noqa: E402

# The labeler's ring is a 5-minute series and the corpus anchors sit on the
# 5-minute grid. This is a FACT about the source, not a knob.
BAR_INTERVAL_S = 300
SOURCE = "bot_cache"
QUOTE = "USD"
COMMITTED_BY = "clock"


def default_state_path() -> Path:
    """A FUNCTION, not a module constant: a module-level outputs/ Path is
    leak-class instance #11 unless registered in tests/conftest.py's
    _REDIRECTED_PATH_ATTRS. This lane only ever READS the file, but the
    same discipline applies."""
    return Path("outputs") / "state.json"


def read_ring(state_path: Path | str | None = None,
              ) -> dict[str, dict[str, list]] | None:
    """`candidates.bars` from state.json, or None when the poll is
    UNREADABLE. None is never an empty ring: they mean different things and
    only one of them may be written down."""
    payload = read_json(Path(state_path) if state_path is not None
                        else default_state_path())
    if not isinstance(payload, dict):
        return None
    cands = payload.get("candidates")
    if not isinstance(cands, dict):
        return None
    ring = cands.get("bars")
    if not isinstance(ring, dict):
        return None
    return ring


def ring_to_bars(series: dict[str, list]) -> list[dict[str, Any]]:
    """One asset's ring -> store bar mappings.

    open and volume are UNKNOWN on this lane and are passed as None, which
    the store renders as '' - never 0.0. A ragged ring (unequal column
    lengths, which would mean the writer was interrupted mid-append) is
    truncated to the shortest column rather than zipped against a
    fabricated value."""
    t = series.get("t") or []
    c = series.get("c") or []
    h = series.get("h") or []
    lo = series.get("l") or []
    n = min(len(t), len(c), len(h), len(lo))
    return [{"time": t[i], "open": None, "high": h[i], "low": lo[i],
             "close": c[i], "volume": None} for i in range(n)]


def collect_once(state_path: Path | str | None = None,
                 root: Path | str | None = None,
                 assets: Sequence[str] | None = None,
                 now_s: int | None = None) -> dict[str, Any]:
    """One poll. Returns a summary; writes nothing on an unreadable poll."""
    now = int(time.time()) if now_s is None else int(now_s)
    ring = read_ring(state_path)
    if ring is None:
        return {"poll_unreadable": 1, "assets": 0, "reports": [],
                "read_at_s": now}
    reports: list[cj.IngestReport] = []
    for asset in sorted(ring):
        if assets is not None and asset not in assets:
            continue
        series = ring.get(asset)
        if not isinstance(series, dict):
            continue
        bars = ring_to_bars(series)
        if not bars:
            continue
        # RULE 3: this asset's OWN newest cached bar is the right edge.
        times = [b["time"] for b in bars
                 if isinstance(b["time"], (int, float))
                 and not isinstance(b["time"], bool)]
        if not times:
            continue
        committed_upto = int(max(float(t) for t in times))
        reports.append(cj.ingest(
            asset, BAR_INTERVAL_S, SOURCE, QUOTE, bars,
            committed_upto_s=committed_upto, committed_by=COMMITTED_BY,
            asked_from_s=None, asked_to_s=None, status="OK", now_s=now,
            root=root))
    return {"poll_unreadable": 0, "assets": len(reports),
            "reports": reports, "read_at_s": now}


def lost_polls(summary: dict[str, Any]) -> list[str]:
    """Lanes whose observation did NOT land, as printable strings.

    A LOST POLL MUST NEVER EXIT 0. The 5m ring is not re-acquirable - every
    poll this lane misses is path lost from the world, not merely from this
    store - and the two ways to lose one are both silent by default:

      * status == "LOCKED": a backfill (or a killed process whose lock
        survives) holds the single-writer lock, so ingest refuses, writes
        NOTHING - not even a coverage row - and returns. The refusal is
        CORRECT; the silence is the defect. Its only other visible trace was
        win_to_s == -1 in a column headed `right_edge_s`.
      * written == False: core.runtime.durable_append never raises and
        returns False on OSError (disk full, an ACL/AV lock). The report
        then prints `accepted=N` for N bars that never reached disk.
    """
    out: list[str] = []
    for rep in summary.get("reports", []):
        if rep.status != "OK":
            out.append(f"{rep.symbol}:{rep.status}")
        elif not rep.written:
            out.append(f"{rep.symbol}:WRITE_FAILED")
    return out


def _print(summary: dict[str, Any]) -> None:
    if summary["poll_unreadable"]:
        print(f"read_at_s={summary['read_at_s']}  state.json UNREADABLE - "
              f"skipped, nothing written (poll_unreadable=1)")
        return
    print(f"read_at_s={summary['read_at_s']}  assets={summary['assets']}")
    print(f"{'asset':<8}{'offered':>9}{'accepted':>10}{'dup':>7}"
          f"{'conflict':>10}{'rejected':>10}{'right_edge_s':>14}"
          f"{'status':>10}{'written':>9}  rejected_by_reason")
    for rep in summary["reports"]:
        print(f"{rep.symbol:<8}{rep.bars_offered:>9}{rep.bars_accepted:>10}"
              f"{rep.bars_dup:>7}{rep.bars_conflict:>10}"
              f"{rep.bars_rejected:>10}{rep.win_to_s:>14}"
              f"{rep.status:>10}{str(rep.written):>9}  "
              f"{rep.rejected_by_reason or ''}")
    lost = lost_polls(summary)
    if lost:
        print(f"LOST POLLS (nothing written, NOT re-acquirable): "
              f"{', '.join(lost)}")
        print("  a LOCKED lane means the ingest lock is held - if no writer "
              "is alive, `python scripts/candle_store.py unlock --force`")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__ or "",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default=None, help="path to state.json")
    ap.add_argument("--root", default=None, help="store root")
    ap.add_argument("--symbols", default=None,
                    help="comma-separated assets; default = every asset")
    ap.add_argument("--once", action="store_true", help="one poll and exit")
    ap.add_argument("--cycles", type=int, default=1,
                    help="number of polls (with --interval-poll-s between)")
    ap.add_argument("--interval-poll-s", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true",
                    help="read the ring and report it; write NOTHING")
    args = ap.parse_args(argv)
    assets = ([s.strip().upper() for s in args.symbols.split(",")]
              if args.symbols else None)

    if args.dry_run:
        ring = read_ring(args.state)
        if ring is None:
            print("state.json UNREADABLE - a real poll would skip and write "
                  "nothing (poll_unreadable=1)")
            return 1
        print(f"{'asset':<8}{'bars':>7}{'t_min_s':>13}{'t_max_s':>13}  "
              f"(DRY RUN - nothing written)")
        for asset in sorted(ring):
            bars = ring_to_bars(ring[asset])
            if not bars:
                continue
            if assets is not None and asset not in assets:
                continue
            times = [b["time"] for b in bars]
            print(f"{asset:<8}{len(bars):>7}{min(times):>13}{max(times):>13}")
        return 0

    cycles = 1 if args.once else max(1, args.cycles)
    rc = 0
    for n in range(cycles):
        summary = collect_once(args.state, args.root, assets)
        _print(summary)
        if summary["poll_unreadable"] or lost_polls(summary):
            rc = 1
        if n + 1 < cycles:
            time.sleep(max(1, args.interval_poll_s))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
