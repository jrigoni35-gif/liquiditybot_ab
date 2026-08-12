"""Per-fill execution ledger — the record the aggregates were throwing away.

Every fill already computes implementation shortfall vs the arrival mark,
segment prices, fees and escalation context, then compressed it into rolling
aggregates in status.json and dropped the per-order record. This appender
makes each fill segment durable, powering work the aggregates cannot:
calibrating the dry-run maker fill model against reality (the MP-4/5/7
re-baseline), the cost-overrun feedback loop into the pretrade EV stack, and
proving execution quality before going live. Capture-only: no trading
behavior reads this file.

Slippage sign convention matches the exec-quality ledger (_note_exec):
positive bps = adverse (bought above / sold below arrival), negative =
price improvement. arrival_ref 0.0 (no arrival mark) -> slip left blank.
"""
import csv
import logging
import os
from pathlib import Path

log = logging.getLogger("liquiditybot.core.fill_ledger")

# fixed column order: the file must stay machine-readable as fields grow —
# append new columns at the END only (same discipline as the corpus)
COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
        "ordertype", "post_only", "attempt", "fill_size", "fill_price",
        "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason",
        "exec_era"]

# EXECUTION-ERA PROVENANCE (CDO review, 2026-08-10). Which fill-simulator
# regime produced this row. Era membership used to be derivable only by
# joining ts against boundary constants scattered across config docs and the
# vault - four boundaries deep, that is a silent-misattribution risk (a
# training run pooling era-1 inflated-fill labels with era-4 honest ones
# would do so invisibly). The stamp travels WITH the row. Bump this constant
# in the SAME commit as any future execution-era boundary. Blank exec_era on
# an old row = pre-stamp: decide by ts against the boundary table
# (paper-real-boundary in the vault); the only era-4-but-blank window is
# aeeaae36 -> the commit introducing this stamp.
#
# 7-e7d5ca1a: cut #7, the geometry epoch (widen-beyond stop placement),
# deployed 2026-08-11T01:33:50Z. The bump SHOULD have ridden e7d5ca1a itself
# per the rule above; it landed one commit late. Verified at the bump: ZERO
# fills between the deploy instant and this commit (book flat through the
# window), so no row ever carried "4-aeeaae36" on the era-7 side.
EXEC_ERA = "7-e7d5ca1a"

# --- restart-replay guard (owed 62 / CDO review 2026-08-10) ---------------
# THE DEFECT THIS BLOCKS: the ledger is fsync-durable PER FILL, but order
# state (filled/avg_price/meta) is durable only per state SNAPSHOT. A kill
# between fill and snapshot restores a pre-fill order; the sim then earns
# the fill AGAIN and appends an identical row - the "duplicates correlate
# 1:1 with restarts" signature that produced the 16x/27x headline error.
# The re-execution itself is snapshot-consistent (position state is equally
# stale), but the LEDGER is the book of record for P&L reconstruction, the
# era-4 verdict gate and the corpus, and it must not carry one fill twice.
#
# KEY: (order_id, fill_size, fill_price, remaining). `remaining` decreases
# monotonically within an order, so two LEGITIMATE fills of one order can
# never collide; a restart replay starts from the same pre-fill state and
# reproduces the same remaining, so it collides exactly. A replay whose
# re-drawn partial size differs is not caught here - the fill-pattern
# dedupe in the readers stays as the second layer.
# Per-path, lazily loaded once per process; bounded by ledger size (~1k).
_seen_keys: dict = {}


def _dup_key(row: dict) -> tuple:
    return (str(row.get("order_id", "")), str(row.get("fill_size", "")),
            str(row.get("fill_price", "")), str(row.get("remaining", "")))


def _load_keys(path: Path) -> set:
    keys = set()
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                keys.add(_dup_key(r))
    except OSError:
        pass
    return keys


def fill_row(order, event, fees_delta: float, now: float) -> dict:
    """Build one ledger row from the objects _handle_fill already holds."""
    arrival = float(getattr(order, "arrival_ref", 0.0) or 0.0)
    slip = ""
    if arrival > 0 and event.fill_price > 0:
        raw = (event.fill_price - arrival) / arrival * 1e4
        slip = round(raw if order.side == "buy" else -raw, 3)
    return {"ts": round(now, 3), "order_id": order.order_id,
            "position_id": order.position_id or "",
            "purpose": order.purpose, "symbol": order.symbol,
            "side": order.side, "ordertype": order.ordertype,
            "post_only": int(bool(order.post_only)),
            "attempt": int(order.meta.get("attempt", 0) or 0),
            "fill_size": f"{event.fill_size:.10g}",
            "fill_price": f"{event.fill_price:.10g}",
            "arrival_ref": f"{arrival:.10g}" if arrival > 0 else "",
            "slip_bps": slip,
            "fees_delta_usd": f"{float(fees_delta):.6f}",
            "remaining": f"{order.remaining:.10g}",
            "reason": str(order.meta.get("reason", ""))[:80],
            "exec_era": EXEC_ERA}


def append_fill(path: Path, row: dict) -> None:
    """Append one row (header on create). Never raises into the fill path —
    losing a ledger row must not break the trade that produced it.

    Durability (29h): a kill mid-append (auto_update's taskkill escalation,
    power loss) leaves a torn final line with no newline; appending straight
    onto it FUSED two fills into one malformed row in the P&L book of
    record. Heal the tail by terminating the fragment first — it isolates as
    one junk row that csv consumers skip, and the new fill lands intact in
    its own row. The fsync bounds the torn window itself to the single row
    being written, instead of everything since the last OS flush."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # size-0 counts as NEW: a kill in the create-to-first-flush window
        # leaves an empty file, and appending a data row without a header
        # makes DictReader silently adopt the first FILL as the header -
        # every consumer then misparses the whole ledger with no error.
        new_file = not path.exists() or path.stat().st_size == 0

        # restart-replay guard: refuse a row identical (by _dup_key) to one
        # already in the ledger. OM-085. First append this process pays a
        # one-time O(rows) load; the trade itself is never affected.
        key_cache = _seen_keys.get(str(path))
        if key_cache is None:
            key_cache = _load_keys(path) if not new_file else set()
            _seen_keys[str(path)] = key_cache
        k = _dup_key(row)
        if k in key_cache:
            log.warning(
                "OM-085: duplicate fill row REFUSED (order_id=%s size=%s "
                "px=%s remaining=%s) - identical row already in the ledger. "
                "Signature of a restart replay: the snapshot restored a "
                "pre-fill order and the sim earned the fill again. The "
                "book of record keeps the FIRST copy.",
                row.get("order_id"), row.get("fill_size"),
                row.get("fill_price"), row.get("remaining"))
            return
        key_cache.add(k)

        torn = False
        cols = COLS
        if not new_file:
            with open(path, "rb") as rf:
                rf.seek(0, os.SEEK_END)
                if rf.tell() > 0:
                    rf.seek(-1, os.SEEK_END)
                    torn = rf.read(1) != b"\n"
            # header-aware append: an existing file created before a column
            # was added keeps ITS OWN width - never emit ragged rows into
            # the book of record. New columns reach an old file only via an
            # explicit, backed-up migration (scripts/migrate_fills_schema).
            try:
                with open(path, newline="", encoding="utf-8") as hf:
                    hdr = next(csv.reader(hf), None)
                if hdr and all(c in COLS for c in hdr):
                    cols = hdr
            except (OSError, StopIteration):
                pass
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if torn:
                f.write("\r\n")           # isolate the torn fragment
            if new_file:
                w.writerow(COLS)
            w.writerow([row.get(c, "") for c in cols])
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        log.exception("fill ledger append failed - row lost, trade unaffected")
