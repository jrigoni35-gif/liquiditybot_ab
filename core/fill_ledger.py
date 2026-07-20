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
from pathlib import Path

log = logging.getLogger("liquiditybot.core.fill_ledger")

# fixed column order: the file must stay machine-readable as fields grow —
# append new columns at the END only (same discipline as the corpus)
COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
        "ordertype", "post_only", "attempt", "fill_size", "fill_price",
        "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason"]


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
            "reason": str(order.meta.get("reason", ""))[:80]}


def append_fill(path: Path, row: dict) -> None:
    """Append one row (header on create). Never raises into the fill path —
    losing a ledger row must not break the trade that produced it."""
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(COLS)
            w.writerow([row.get(c, "") for c in COLS])
    except OSError:
        log.exception("fill ledger append failed - row lost, trade unaffected")
