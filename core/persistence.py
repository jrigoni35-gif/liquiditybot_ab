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
        "entry_fees_usd": pos.entry_fees_usd,
        "leverage": pos.leverage,
        "high_water": pos.high_water,
        "is_probe": pos.is_probe,
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
        entry_fees_usd=float(d.get("entry_fees_usd", 0.0)),
        leverage=float(d.get("leverage", 1.0)),
        high_water=(None if d.get("high_water") is None else float(d["high_water"])),
        is_probe=bool(d.get("is_probe", False)),
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
        "queue_ahead": o.queue_ahead,
        "arrival_ref": getattr(o, "arrival_ref", 0.0),
        "meta": _jsonable_meta(o.meta),
    }


def _feature_schema_version() -> int:
    from ml.features import FEATURE_SCHEMA_VERSION
    return FEATURE_SCHEMA_VERSION


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
        queue_ahead=float(d.get("queue_ahead", -1.0)),
        arrival_ref=float(d.get("arrival_ref", 0.0)),
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
                    # peak MTM equity — persist so the drawdown backstop's
                    # high-water survives a restart (else it re-seats lower and
                    # understates true drawdown, delaying the catastrophe halt)
                    "equity_high_water": getattr(state, "_equity_high_water",
                                                 state.starting_capital),
                    "positions": [position_to_dict(p)
                                for p in state.open_positions()],
                },
                "open_orders": [order_to_dict(o)
                                for o in bot.orders.open_orders()],
                "feature_schema_version": _feature_schema_version(),
                "cycle_lifetime": int(getattr(bot, "_cycle_lifetime", 0)),
                # regime_age_sec feature integrity: without this a restart
                # resets every regime's age to zero and rows recorded in
                # the following hours understate it ("a 2-bar-old range
                # and a 3-day-old range are different animals")
                "regime_since": {a: [lbl, ts] for a, (lbl, ts) in
                                 getattr(bot, "_regime_since", {}).items()},
                "history_pending": {
                    pid: {"asset": e[0], "direction": e[1],
                          "features": e[2].tolist(),
                          # signal time (4th slot; older 3-tuples lack it)
                          "signal_ts": float(e[3]) if len(e) > 3 else None,
                          # PT-050 probe flag (5th slot; older tuples lack it)
                          "probe": bool(e[4]) if len(e) > 4 else False}
                    for pid, e in bot.history._pending.items()
                },
                "sizer_last_entry": dict(bot.sizer._last_entry),
                "pos_realized": dict(bot._pos_realized),
                # V2 vindication continuity: fired-detector maps for OPEN
                # positions and the graded reliability ledger. Detector
                # OBSERVATION state stays un-snapshotted (see NOTE below);
                # the ledger is outcome bookkeeping, not observations, so
                # persisting it carries no stale-advice hazard.
                "pos_thales": {k: list(v) for k, v in
                               getattr(bot, "_pos_thales", {}).items()},
                "thales_reliability": bot.thales.reliability_to_dict()
                if getattr(bot, "thales", None) is not None else {},
                "halted": bot._halted,
                # NOTE: THALES detector state is deliberately NOT
                # snapshotted - TH-016's restart safety relies on
                # last_fast_ts==0 cold-starting fresh (docs/THALES.md).
                # Persisting it without the lapse fields would silently
                # re-create the 2026-07-14 stale-advice hole.
                "monitor": bot.monitor.to_dict(),
                "postmortem": bot.postmortem.to_dict(),
                "performance": bot.perf.to_dict()
                if getattr(bot, "perf", None) is not None else {},
                # a restart must not launder an active per-asset trip
                "circuit_breaker": bot.breaker.to_dict()
                if getattr(bot, "breaker", None) is not None else {},
                "candidates": bot.candidates.to_dict(),
                "gate_stats": bot.gate_stats.to_dict(),
                "stop_hit": dict(bot._stop_hit),
                # restart must not defer auto-retrain: this counter's
                # init default is "rows right now", which pushes the
                # new-rows trigger back by retrain_min_new_rows on every
                # relaunch (observed: a keepalive revival moved the
                # goalpost from 62 to 137 rows mid-recovery)
                "rows_at_last_train": int(getattr(bot,
                                                  "_rows_at_last_train", 0)),
                "risk_protocols": getattr(bot, "risk_protocols",
                                          None) and
                bot.risk_protocols.to_dict(),
            }
            return self._seal_and_write(data)
        except Exception:
            log.exception("snapshot failed - continuing without persisting")
            return False

    def _seal_and_write(self, data: dict) -> bool:
        # integrity seal: checksum over the payload, so a torn or
        # bit-rotted file is DETECTED at load instead of silently
        # restoring a corrupt book
        # seal a COPY, never the caller's dict: mutating `data` in place (the
        # old `data["_sha256"] = ...`) leaves a stale seal on any dict a caller
        # reuses across calls, which then fails its own checksum. snapshot()
        # builds a fresh dict today, but the copy makes that a non-hazard.
        body = json.dumps(data, sort_keys=True)
        data = {**data, "_sha256": hashlib.sha256(body.encode()).hexdigest()}
        # PID-scoped tmp: a fixed shared "state.tmp" lets two runners (the
        # single-instance-lock convergence window) truncate/rename the SAME
        # tmp and clobber each other's snapshot — the torn write that
        # runtime.atomic_write_json already PID-scopes for status.json. Cleaned
        # up on any failure so a crashed write leaves no orphan behind.
        tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())    # survive power loss, not just crash
            # rotate the previous good snapshot to .bak BEFORE replacing,
            # so there is always one known-good generation to fall back to
            if self.path.exists():
                try:
                    os.replace(self.path, self.path.with_suffix(".json.bak"))
                except OSError:
                    log.debug("bak rotation failed - continuing")
            os.replace(tmp, self.path)
            # fsync the DIRECTORY so the rename itself is durable: a power loss
            # right after os.replace can otherwise lose the directory entry and
            # leave no primary (the .bak + checksum fallback covers it, but the
            # dir fsync closes the window). Best-effort - a dir fd fsync is not
            # supported on every platform (e.g. Windows), so never fatal.
            try:
                dfd = os.open(str(self.path.parent), os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except (OSError, ValueError):
                pass
            return True
        finally:
            Path(tmp).unlink(missing_ok=True)   # no-op on success (renamed away)

    def load_raw(self) -> Optional[dict]:
        """Best-effort raw snapshot dict (primary, falling back to .bak) -
        same verification path as restore(), for standalone scripts that
        need to read one section (e.g. governor state) without a live bot
        object to restore onto."""
        return self._pick_snapshot()

    def write_raw(self, data: dict) -> bool:
        """Atomic partial-state write for standalone scripts that need to
        update one section of the snapshot (e.g. manual model retrain
        updating the governor's champion_brier) without a live bot to
        snapshot from. Same checksum + backup-rotation guarantees as
        snapshot()."""
        try:
            data = dict(data)
            data.pop("_sha256", None)
            return self._seal_and_write(data)
        except Exception:
            log.exception("state write failed - continuing without "
                          "persisting")
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

    def _pick_snapshot(self) -> Optional[dict]:
        """Newest usable snapshot generation, or None. A MISSING primary is
        NOT fatal: a crash between _seal_and_write's primary->.bak rotation and
        the tmp->primary publish leaves the primary gone but .bak valid. Both
        restore() and load_raw() go through here so neither discards state the
        .bak still holds — the old restore() early-returned on a missing
        primary and lost every position/order/PnL the backup was keeping."""
        for candidate in (self.path, self.path.with_suffix(".json.bak")):
            if not Path(candidate).exists():
                continue
            try:
                data = self._load_verified(candidate)
                if candidate != self.path:
                    log.warning(f"primary snapshot unavailable - restored from "
                                f"backup generation {candidate}")
                return data
            except (OSError, json.JSONDecodeError, ValueError) as e:
                log.error(f"snapshot {candidate} unusable ({e}) - trying "
                          f"next generation")
        return None

    def restore(self, bot) -> bool:
        data = self._pick_snapshot()
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
            state._equity_high_water = float(p.get("equity_high_water",
                                                   state.starting_capital))
            for pd in p.get("positions", []):
                state.add_position(position_from_dict(pd))
        except (KeyError, TypeError, ValueError):
            log.exception("portfolio section malformed - skipped")

        # open orders — meta['features'] is version-gated exactly like
        # history_pending below: a feature-schema bump changes what a
        # same-width vector MEANS, and a restored entry order that fills
        # post-restart would push its stale-semantics vector into the label
        # pipeline via log_entry. Strip the vector, keep the order.
        try:
            snap_ver = int(data.get("feature_schema_version", 1) or 1)
        except (TypeError, ValueError):
            snap_ver = 1
        try:
            stripped = 0
            for od in data.get("open_orders", []):
                o = order_from_dict(od)
                if snap_ver != _feature_schema_version() and \
                        o.meta.get("features") is not None:
                    o.meta.pop("features", None)
                    stripped += 1
                bot.orders._orders[o.order_id] = o
            if stripped:
                log.warning(
                    "stripped feature vector(s) from %d restored order(s) "
                    "(feature-schema v%d != current v%d) - orders stay "
                    "managed, their fills will not produce training rows",
                    stripped, snap_ver, _feature_schema_version())
        except Exception:
            log.exception("open-orders section malformed - skipped")

        # pending history features - version-gated: a feature-schema bump
        # changes what same-width vectors MEAN (v2: side-relative), so a
        # pending vector from another version must not produce a training
        # row. The positions themselves still restore; only their future
        # label rows are forfeited to keep the dataset pure.
        try:
            snap_ver = int(data.get("feature_schema_version", 1) or 1)
            if snap_ver != _feature_schema_version():
                n = len(data.get("history_pending", {}))
                if n:
                    log.warning(
                        "dropped %d pending label vector(s) from feature-"
                        "schema v%d (current v%d) - their positions stay "
                        "managed but will not produce training rows",
                        n, snap_ver, _feature_schema_version())
            else:
                for pid, h in data.get("history_pending", {}).items():
                    bot.history._pending[pid] = (
                        h["asset"], h["direction"],
                        np.array(h["features"], dtype=float),
                        float(h["signal_ts"]) if h.get("signal_ts")
                        else time.time(),
                        bool(h.get("probe", False)))
        except Exception:
            log.exception("history section malformed - skipped")

        bot.sizer._last_entry.update(data.get("sizer_last_entry", {}))
        bot._pos_realized.update(data.get("pos_realized", {}))
        try:
            if hasattr(bot, "_pos_thales"):
                bot._pos_thales.update(
                    {str(k): [tuple(x) for x in v] for k, v in
                     (data.get("pos_thales") or {}).items()})
            if getattr(bot, "thales", None) is not None:
                bot.thales.reliability_restore(
                    data.get("thales_reliability") or {})
        except (TypeError, ValueError):
            log.warning("thales V2 sections malformed - skipped")
        bot._halted = bool(data.get("halted", False))
        # absent in pre-upgrade snapshots -> starts counting from now
        bot._cycle_lifetime = int(data.get("cycle_lifetime", 0) or 0)
        # regime ages survive restarts; if the label changed while we were
        # down, slow_cycle's change detection resets that asset naturally
        try:
            if hasattr(bot, "_regime_since"):
                bot._regime_since.update(
                    {a: (str(lbl), float(ts)) for a, (lbl, ts) in
                     (data.get("regime_since") or {}).items()})
        except (TypeError, ValueError):
            log.warning("regime_since section malformed - ages restart at 0")
        # absent in pre-upgrade snapshots -> keep the init-time value
        # (rows at launch), the old behavior
        if data.get("rows_at_last_train") is not None:
            bot._rows_at_last_train = int(data["rows_at_last_train"])
        try:
            bot.monitor.restore(data.get("monitor"))
            bot.postmortem.restore(data.get("postmortem"))
            if getattr(bot, "perf", None) is not None:
                bot.perf.restore(data.get("performance"))
            if getattr(bot, "breaker", None) is not None:
                bot.breaker.restore(data.get("circuit_breaker"))
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
        # remove ALL persisted generations so --fresh is truly fresh: leaving
        # .bak behind would let restore() (which now falls back to it)
        # resurrect the very state --fresh meant to discard.
        self.path.unlink(missing_ok=True)
        self.path.with_suffix(".json.bak").unlink(missing_ok=True)
        for t in self.path.parent.glob(self.path.stem + ".*.tmp"):
            t.unlink(missing_ok=True)
