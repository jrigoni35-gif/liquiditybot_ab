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

from core.codes import Code, tag

log = logging.getLogger("liquiditybot.core.fill_ledger")

# fixed column order: the file must stay machine-readable as fields grow —
# append new columns at the END only (same discipline as the corpus)
COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
        "ordertype", "post_only", "attempt", "fill_size", "fill_price",
        "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason",
        "exec_era", "book"]

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
#
# 8-ca55e2ba: cut #8, the FEE-TRUTH epoch - "boundary #5" on the fill-axis
# counter the vault's comparability table keeps in parallel (four fill-axis
# cuts + the label axis + the capital epoch + geometry = cut #7; this is the
# eighth cut and the fifth fill-axis boundary; both counters are in use and
# both name THIS cut). Applied by scripts/boundary5_stage.py --apply at
# 2026-08-28T02:34:42Z under the 2026-08-27 operator adjudication ("both:
# full bundle"), batched to the era-4 readout (COST_BOUND at n=54) exactly as
# owed-88 prescribed. What changed: pricing AND booking fees 25/40 -> the
# venue-true Kraken Tier-1 40/80 bps, the profit-taking break-even floor
# 40 -> 80, the label round-trip cost 0.5% -> 1.2%, and the exploration
# sizing ticket p_win 0.70 -> 0.85 (the one coherence edit that clears the
# net-Kelly FATAL the guard correctly raises at true cost). Every fill priced,
# booked and labelled after this cut is on a DIFFERENT cost manifold than
# every fill before it - do not pool them.
#
# WHY THE SHA NAMES 16ec821e AND NOT THIS COMMIT. The rule above ("bump in
# the SAME commit") is satisfiable; naming the bumping commit's own sha is
# NOT - a commit cannot contain its own hash. As at cut #8, the bump rides
# the behavior change (the fee_correction_stage.py --apply config write is in
# this same commit, no debt), and the 8-hex names the commit that DEFINES the
# boundary's content - 16ec821e, which shipped scripts/fee_tier_rederive.py
# and docs/quant/2026-08-29_fee_tier_correction_adjudication.md. That is the
# sha the vault's boundary table uses for this cut, so stamp and table agree.
#
# CUT #9 - THE TIER-3 FEE CORRECTION (2026-08-30, operator ARM "fee correction
# only", dry_run STAYS true). Cut #8 booked 40/80 (assumed Tier-1); the
# account is real Tier 3 = 22/38 (operator Kraken screenshot), so cut #8
# over-stated fees ~2x. This cut books the real tier: pretrade+order_manager
# 22/38, label rt 0.6, allow_sub_floor_fees true (22/38 is below the 40/80
# KRAKEN_SPOT_FLOOR tripwire, which stays put; the account genuinely holds a
# Tier-3 volume discount), and the derived entry bar recomputes 0.8335 ->
# 0.6772 (conviction resumes). ALGO-5 tail-control EXCLUDED (net-CI spans
# zero on fills alone). Prior cut-8 rows stay citable AS cut-8; nothing
# accruing under this constant may be pooled with them.
#
# The era BEGINS at the runner restart on this commit (a running process
# keeps the fee constants it read at init), not at the config write; that
# instant is stamped in docs/HANDOFF.md and the vault boundary row in this
# same session. Rows stamped 9-16ec821e are exactly the rows a binary
# carrying this constant wrote - which is the only claim the stamp makes.
# 10-a5acfe2d: cut #10, the VERIFIED-DEFECTS BOUNDARY (era-7), minted
# 2026-09-06 under operator approval. Stamp names the decision-record commit
# (docs/quant/2026-09-06_cut10_boundary_adjudication.md), the same shape as
# cut #9 (16ec821e record -> 59bdcf87 code). What changed on the fill axis:
# fee BOOKING 22/38 -> 20/35 (E1: 22/38 was not a published row; 20/35 is the
# binding row at the measured $17,482/30d volume), est_fee_bps 38 -> 35,
# label round-trip cost 0.60% -> 0.55%, plus six confirmed defects on the
# entry/sizing/exit/order-lifecycle path (B1-B6). Every fill booked after this
# stamp is on a different cost manifold AND a different decision path than
# every fill before it - do not pool across it. Era-6 rows stay citable AS
# era-6.
EXEC_ERA = "10-a5acfe2d"

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


#: Count of times the dedup key cache could not be loaded. A read failure
#: leaves `keys` EMPTY, which is indistinguishable from "this ledger has no
#: rows yet" - so a replayed fill re-lands in the P&L book and nothing says so.
#: Report-only; nothing reads it as a decision input.
dedup_disarmed = 0


def _load_keys(path: Path) -> "set | None":
    """The dedup key set, or None if the ledger could not be read (cut #10,
    B5). None means UNKNOWN and the caller must not treat it as clean."""
    keys = set()
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                keys.add(_dup_key(r))
    except OSError:
        # WAS `pass`, SILENTLY. The contrast is inside this same file: the
        # append path at the bottom logs its OSError with log.exception, while
        # this one - the guard that keeps a duplicate fill OUT of realized
        # P&L - swallowed it and produced ZERO output. Measured 2026-09-05:
        # locking byte 0 of fills.csv, or an os.replace rotation landing
        # between the new_file check and this call, gives `rows = 3` with a
        # duplicate landed and no log record anywhere.
        #
        # THIS IS THE OBSERVABILITY HALF ONLY. Making dedup FAIL CLOSED changes
        # whether a fill row reaches outputs/fills.csv, which feeds realized
        # P&L -> equity -> loss budget -> sizing; that is a booking change and
        # needs operator sign-off (docketed B5). Logging it does not.
        global dedup_disarmed
        dedup_disarmed += 1
        log.exception("fill-ledger dedup key cache UNLOADABLE: could not read "
                      "%s (occurrence #%d) - the append path will scan the "
                      "ledger directly, and refuse the row if that fails too",
                      path, dedup_disarmed)
        # CUT #10 (B5): None, not an empty set. An empty set is
        # indistinguishable from "this ledger has no rows yet" and DISARMED
        # dedup silently; None says "unknown" and the caller must not treat
        # unknown as clean.
        return None
    return keys


def _key_on_disk(path: Path, key: tuple) -> bool:
    """Direct scan: is `key` already in the ledger? Raises OSError if the
    ledger cannot be read - the caller decides what unknowable means."""
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if _dup_key(r) == key:
                return True
    return False


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
            "exec_era": EXEC_ERA,
            # BOOK PROVENANCE (2026-09-05). Which book opened this leg. The
            # value was already in hand at the call site (main.py passes
            # book=order.meta.get("book","5m") into the order) but was never
            # recorded, so the ledger could not separate long-book adds from
            # 5m entries and every cohort reconstruction pooled them. It was
            # recoverable only by joining signal_history on position_id, which
            # works but is limited to rows that have been LABELED - an open
            # position has no label yet, so the join is silently partial
            # exactly when you are watching a live cohort.
            #
            # Appended at the END, per this file's discipline: DictReader
            # assigns positionally, so a row written by a binary that predates
            # this column reads book=None, which is the correct meaning
            # ("writer predates the field") and is distinguishable from ""
            # (writer knew the field, value absent) - the same three-way the
            # exec_era stamp relies on one column to its left.
            "book": str(order.meta.get("book", "") or "")}


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
            # CUT #10 (B5): close the rotation window. An os.replace landing
            # between the new_file check above and the load leaves the cache
            # describing a file that no longer exists; re-derive new_file
            # AFTER the load so the header decision matches the file we will
            # actually append to.
            new_file = not path.exists() or path.stat().st_size == 0
            if key_cache is not None:
                _seen_keys[str(path)] = key_cache      # only cache a real load
        k = _dup_key(row)
        if key_cache is None:
            # The cache could not be loaded. FAIL CLOSED: scan the ledger
            # directly for THIS key; if even that fails, the replay question
            # is unknowable and the row is refused. Before cut #10 this path
            # cached an EMPTY set and appended blind - a replayed fill re-
            # landed in realized P&L with zero log output (measured: byte-0
            # lock -> rows = 3, duplicate landed).
            try:
                dup = (not new_file) and _key_on_disk(path, k)
            except OSError:
                log.error(tag(
                    Code.OM_LEDGER_DEDUP_UNKNOWN,
                    f"fill row REFUSED: dedup state unknowable for {path} "
                    f"(order_id={row.get('order_id')} size="
                    f"{row.get('fill_size')} px={row.get('fill_price')}). "
                    f"A lost row is recoverable from the audit trail; a "
                    f"duplicate in realized P&L is not."))
                return
            if dup:
                log.warning("OM-085: duplicate fill row REFUSED on direct "
                            "scan (order_id=%s) - cache was unloadable",
                            row.get("order_id"))
                return
            key_cache = set()          # this append only; not cached
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
