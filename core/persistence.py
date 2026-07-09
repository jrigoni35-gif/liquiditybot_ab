"""
core/persistence.py

Snapshot/restore for pause-and-resume. Everything the bot cannot
reconstruct from the exchange is written to one JSON file:

  * PortfolioState - balances, realized/daily PnL, fees, every open
    Position with its v2 fields (stops, hedge flag, confidence, fees)
  * open ManagedOrders - so a restart keeps managing resting limits
    instead of orphaning them on Kraken
  * HistoryStore pending entries - feature vectors of open positions,
    so trades that close after a restart still produce labeled training
    rows instead of silently vanishing from the dataset
  * sizer cooldowns, per-position realized PnL, the halt flag

Writes are atomic (tmp file + os.replace) so a crash mid-write can
never corrupt the last good snapshot. Restore is best-effort per
section: a malformed section is skipped with a warning rather than
refusing to start.

What is deliberately NOT persisted: market state (books, regimes, fair
value). All of it rebuilds from live data within one slow cycle, and
stale copies would be worse than none.
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("liquiditybot.core.persistence")

SNAPSHOT_VERSION = 2


# --------------------------------------------------------------------------
# serializers
# --------------------------------------------------------------------------
def position_to_dict(pos) -> dict:
    return {
        "position_id": pos.position_id,
        "symbol": pos.symbol,
        "direction": pos.direction,
        "entry_price": pos.entry_price,
        "size": pos.size,
        "original_size": pos.original_size,
        "opened_at": pos.opened_at.isoformat(),
        "tier_closed": pos.tier_closed,
        "trailing_stop_price": pos.trailing_stop_price,
        "is_hedge": pos.is_hedge,
        "stop_price": pos.stop_price,
        "confidence": pos.confidence,
        "edge_bps": pos.edge_bps,
        "fees_paid_usd": pos.fees_paid_usd,
        "leverage": pos.leverage,
        "high_water": pos.high_water,
    }


def position_from_dict(d: dict):
    from core.state import Position
    return Position(
        position_id=d["position_id"], symbol=d["symbol"],
        direction=d["direction"], entry_price=float(d["entry_price"]),
        size=float(d["size"]), original_size=float(d["original_size"]),
        opened_at=datetime.fromisoformat(d["opened_at"]),
        tier_closed=int(d.get("tier_closed", 0)),
        trailing_stop_price=d.get("trailing_stop_price"),
        is_hedge=bool(d.get("is_hedge", False)),
        stop_price=d.get("stop_price"),
        confidence=float(d.get("confidence", 0.0)),
        edge_bps=float(d.get("edge_bps", 0.0)),
        fees_paid_usd=float(d.get("fees_paid_usd", 0.0)),
        leverage=float(d.get("leverage", 1.0)),
        high_water=(None if d.get("high_water") is None else float(d["high_water"])),
    )


def _jsonable_meta(meta: Optional[dict]) -> dict:
    out = {}
    for k, v in (meta or {}).items():
        if isinstance(v, np.ndarray):
            out[k] = {"__ndarray__": v.tolist()}
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, dict)):
            out[k] = v
    return out


def _restore_meta(meta: Optional[dict]) -> dict:
    out = {}
    for k, v in (meta or {}).items():
        if isinstance(v, dict) and "__ndarray__" in v:
            out[k] = np.array(v["__ndarray__"], dtype=float)
        else:
            out[k] = v
    return out


def order_to_dict(o) -> dict:
    return {
        "order_id": o.order_id, "txid": o.txid, "asset": o.asset,
        "pair": o.pair, "symbol": o.symbol, "side": o.side,
        "price": o.price, "size": o.size, "filled": o.filled,
        "avg_price": o.avg_price, "fees_usd": o.fees_usd,
        "status": o.status, "purpose": o.purpose,
        "position_id": o.position_id, "close_pct": o.close_pct,
        "created_ts": o.created_ts, "reprices": o.reprices,
        "post_only": o.post_only, "leverage": o.leverage,
        "ordertype": o.ordertype,
        "meta": _jsonable_meta(o.meta),
    }


def order_from_dict(d: dict):
    from execution.order_manager import ManagedOrder
    o = ManagedOrder(
        order_id=d["order_id"], txid=d.get("txid"), asset=d["asset"],
        pair=d["pair"], symbol=d["symbol"], side=d["side"],
        price=float(d["price"]), size=float(d["size"]),
        filled=float(d.get("filled", 0.0)),
        avg_price=float(d.get("avg_price", 0.0)),
        fees_usd=float(d.get("fees_usd", 0.0)),
        status=d.get("status", "pending"), purpose=d.get("purpose", "entry"),
        position_id=d.get("position_id"),
        close_pct=float(d.get("close_pct", 0.0)),
        created_ts=float(d.get("created_ts", time.time())),
        reprices=int(d.get("reprices", 0)),
        post_only=bool(d.get("post_only", True)),
        leverage=float(d.get("leverage", 1.0)),
        ordertype=str(d.get("ordertype", "limit")),
        meta=_restore_meta(d.get("meta")),
    )
    return o


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------
class StateStore:
    def __init__(self, path: str = "outputs/state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return self.path.exists()

    # --- snapshot -----------------------------------------------------
    def snapshot(self, bot) -> bool:
        try:
            state = bot.state
            data = {
                "version": SNAPSHOT_VERSION,
                "saved_at": time.time(),
                "dry_run": bot.dry_run,
                "portfolio": {
                    "starting_capital": state.starting_capital,
                    "cash_balance": state.cash_balance,
                    "savings_balance": state.savings_balance,
                    "realized_pnl_total": state.realized_pnl_total,
                    "daily_realized_pnl": state.daily_realized_pnl,
                    "fees_paid_total": state.fees_paid_total,
                    "last_pnl_reset_date": state._last_pnl_reset_date,
                    "positions": [position_to_dict(p)
                                for p in state.open_positions()],
                },
                "open_orders": [order_to_dict(o)
                                for o in bot.orders.open_orders()],
                "history_pending": {
                    pid: {"asset": a, "direction": d, "features": f.tolist()}
                    for pid, (a, d, f) in bot.history._pending.items()
                },
                "sizer_last_entry": dict(bot.sizer._last_entry),
                "pos_realized": dict(bot._pos_realized),
                "halted": bot._halted,
                "monitor": bot.monitor.to_dict(),
                "postmortem": bot.postmortem.to_dict(),
                "candidates": bot.candidates.to_dict(),
                "gate_stats": bot.gate_stats.to_dict(),
                "stop_hit": dict(bot._stop_hit),
                "risk_protocols": getattr(bot, "risk_protocols",
                                          None) and
                bot.risk_protocols.to_dict(),
            }
            # integrity seal: checksum over the payload, so a torn or
            # bit-rotted file is DETECTED at load instead of silently
            # restoring a corrupt book
            body = json.dumps(data, sort_keys=True)
            data["_sha256"] = hashlib.sha256(body.encode()).hexdigest()
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())        # survive power loss, not just crash
            # rotate the previous good snapshot to .bak BEFORE replacing,
            # so there is always one known-good generation to fall back to
            if self.path.exists():
                try:
                    os.replace(self.path, self.path.with_suffix(".json.bak"))
                except OSError:
                    log.debug("bak rotation failed - continuing")
            os.replace(tmp, self.path)
            return True
        except Exception:
            log.exception("snapshot failed - continuing without persisting")
            return False

    @staticmethod
    def _verify(data: dict) -> bool:
        """Checksum verification. Snapshots from before the checksum era
        (no _sha256 key) pass - the version gate handles incompatibility."""
        want = data.pop("_sha256", None)
        if want is None:
            return True
        body = json.dumps(data, sort_keys=True)
        return hashlib.sha256(body.encode()).hexdigest() == want

    # --- restore ------------------------------------------------------
    def _load_verified(self, path) -> dict:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not self._verify(data):
            raise ValueError(f"checksum mismatch in {path}")
        return data

    def restore(self, bot) -> bool:
        if not self.path.exists():
            return False
        data = None
        for candidate in (self.path, self.path.with_suffix(".json.bak")):
            if not Path(candidate).exists():
                continue
            try:
                data = self._load_verified(candidate)
                if candidate != self.path:
                    log.warning(f"primary snapshot corrupt - restored from "
                                f"backup generation {candidate}")
                break
            except (OSError, json.JSONDecodeError, ValueError) as e:
                log.error(f"snapshot {candidate} unusable ({e}) - trying "
                          f"next generation")
        if data is None:
            log.error("no usable snapshot generation - starting fresh")
            return False
        if data.get("version") != SNAPSHOT_VERSION:
            log.warning(f"snapshot version {data.get('version')} != "
                        f"{SNAPSHOT_VERSION} - starting fresh")
            return False
        if bool(data.get("dry_run", True)) != bot.dry_run:
            log.warning(
                f"snapshot was taken with dry_run={data.get('dry_run')} but bot "
                f"is running dry_run={bot.dry_run} - refusing to mix paper and "
                f"live state; starting fresh (use --fresh to silence this)")
            return False

        # portfolio
        try:
            p = data["portfolio"]
            state = bot.state
            state.starting_capital = float(p["starting_capital"])
            state.cash_balance = float(p["cash_balance"])
            state.savings_balance = float(p["savings_balance"])
            state.realized_pnl_total = float(p["realized_pnl_total"])
            state.daily_realized_pnl = float(p["daily_realized_pnl"])
            state.fees_paid_total = float(p.get("fees_paid_total", 0.0))
            state._last_pnl_reset_date = p.get("last_pnl_reset_date", "")
            for pd in p.get("positions", []):
                state.add_position(position_from_dict(pd))
        except (KeyError, TypeError, ValueError):
            log.exception("portfolio section malformed - skipped")

        # open orders
        try:
            for od in data.get("open_orders", []):
                o = order_from_dict(od)
                bot.orders._orders[o.order_id] = o
        except Exception:
            log.exception("open-orders section malformed - skipped")

        # pending history features
        try:
            for pid, h in data.get("history_pending", {}).items():
                bot.history._pending[pid] = (
                    h["asset"], h["direction"],
                    np.array(h["features"], dtype=float))
        except Exception:
            log.exception("history section malformed - skipped")

        bot.sizer._last_entry.update(data.get("sizer_last_entry", {}))
        bot._pos_realized.update(data.get("pos_realized", {}))
        bot._halted = bool(data.get("halted", False))
        try:
            bot.monitor.restore(data.get("monitor"))
            bot.postmortem.restore(data.get("postmortem"))
            bot.candidates.restore(data.get("candidates"))
            bot.gate_stats.restore(data.get("gate_stats"))
            bot._stop_hit.update(data.get("stop_hit", {}))
            rp = data.get("risk_protocols")
            if rp and getattr(bot, "risk_protocols", None) is not None:
                bot.risk_protocols.from_dict(rp)
        except Exception:
            log.exception("monitor/postmortem/candidate sections malformed - skipped")

        age_min = (time.time() - data.get("saved_at", 0)) / 60.0
        log.info(f"resumed from snapshot ({age_min:.1f} min old): "
                f"{bot.state.open_position_count()} positions, "
                f"{len(bot.orders.open_orders())} open orders, "
                f"{len(bot.history._pending)} pending labels, "
                f"equity=${bot.state.cash_balance + bot.state.savings_balance:,.2f} "
                f"halted={bot._halted}")
        return True

    def clear(self):
        self.path.unlink(missing_ok=True)
