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
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.runtime import replace_with_retry

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
        "est_cost_bps": pos.est_cost_bps,
        "book": pos.book,
        # geometry-alignment T5: bracket geometry, legacy-inert 0.0 default
        "bracket_pt_frac": pos.bracket_pt_frac,
        "bracket_sl_frac": pos.bracket_sl_frac,
        "bracket_deadline_ts": pos.bracket_deadline_ts,
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
        # P1: pre-P1 snapshots lack this key -> defaults 0.0, which keeps
        # risk/profit_tiers.py's tier-1 cost floor exactly inert for a
        # restored legacy position.
        est_cost_bps=float(d.get("est_cost_bps", 0.0)),
        # Compounder Phase C: pre-C snapshots lack this key -> defaults
        # "5m", the existing scalping book, so a legacy restore never
        # silently reclassifies a position onto the long book.
        book=d.get("book", "5m"),
        # geometry-alignment T5: pre-T5 snapshots lack these keys ->
        # default 0.0, exactly inert (the bracket exit-evaluation branch
        # in main._manage_open_position is unreachable at bracket_pt_
        # frac<=0, so a restored legacy position keeps trading the tier
        # engine exactly as before).
        bracket_pt_frac=float(d.get("bracket_pt_frac", 0.0)),
        bracket_sl_frac=float(d.get("bracket_sl_frac", 0.0)),
        bracket_deadline_ts=float(d.get("bracket_deadline_ts", 0.0)),
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
        # C4 review, Critical #1a: a resting order's per-order TTL override
        # must survive a restart — without this, a long-horizon accumulation
        # bid resumes with ttl_sec=None (falls back to the shared ~25s
        # order_timeout_sec) against its ORIGINAL (hours-old) created_ts and
        # is judged instantly expired on the very next poll.
        "ttl_sec": getattr(o, "ttl_sec", None),
        "meta": _jsonable_meta(o.meta),
    }


def _feature_schema_version() -> int:
    from ml.features import FEATURE_SCHEMA_VERSION
    return FEATURE_SCHEMA_VERSION


def _restore_subsystem_sections(bot, data: dict) -> None:
    """The learning/guard subsystem run of restore(), one try/except per
    section: a raise in one (e.g. a malformed monitor section) must never
    skip the others - a breaker trip or risk_protocols loss-budget anchor
    laundered by a reboot is exactly the failure mode
    risk/circuit_breaker.py's docstring exists to prevent.

    Extracted from restore() 2026-08-07: cf454d5e's hedger churn-guard
    section pushed restore past the C901 ceiling (42 > 40), and the
    file's own convention for that pressure is a _restore_*_section
    helper, not a waiver."""
    try:
        bot.monitor.restore(data.get("monitor"))
    except Exception:
        log.exception("monitor section malformed - skipped")
    try:
        if hasattr(bot, "hedger"):
            bot.hedger.from_dict(data.get("hedger"))
    except Exception:
        log.exception("hedger churn-guard section malformed - skipped")
    try:
        bot.postmortem.restore(data.get("postmortem"))
    except Exception:
        log.exception("postmortem section malformed - skipped")
    try:
        if getattr(bot, "perf", None) is not None:
            bot.perf.restore(data.get("performance"))
    except Exception:
        log.exception("performance section malformed - skipped")
    try:
        if getattr(bot, "breaker", None) is not None:
            bot.breaker.restore(data.get("circuit_breaker"))
    except Exception:
        log.exception("circuit_breaker section malformed - skipped")
    _restore_markout_section(bot, data)
    try:
        bot.candidates.restore(data.get("candidates"))
    except Exception:
        log.exception("candidates section malformed - skipped")
    try:
        bot.gate_stats.restore(data.get("gate_stats"))
    except Exception:
        log.exception("gate_stats section malformed - skipped")
    try:
        bot._stop_hit.update(data.get("stop_hit", {}))
    except (TypeError, ValueError):
        log.warning("stop_hit section malformed - skipped")


def _restore_fault_section(bot, data: dict) -> None:
    """W2-15: isolated so a malformed section can't skip anything else in
    restore(), and so this doesn't add to restore()'s own branch count
    (pyproject.toml's C901 ceiling is a frozen regression stop, not a
    target - do not grow restore() toward it)."""
    try:
        if getattr(bot, "fault", None) is not None:
            bot.fault.restore(data.get("fault"))
    except Exception:
        log.exception("fault section malformed - skipped")


def _restore_markout_section(bot, data: dict) -> None:
    """W2-16: same isolation rationale as _restore_fault_section above."""
    try:
        if getattr(bot, "markout", None) is not None:
            bot.markout.restore(data.get("markout"))
    except Exception:
        log.exception("markout section malformed - skipped")


def _restore_probe_admissions_section(bot, data: dict) -> None:
    """P3 probe throttle rolling share-cap window (main.py
    _probe_admissions): isolated so a malformed section can't skip
    anything else in restore() - same ISOLATION principle as
    _restore_fault_section/_restore_markout_section above, keeping
    restore()'s own branch count from growing toward pyproject.toml's
    frozen C901 ceiling. The except tuple itself matches the narrower
    "continuity anchors" restore block above (exit_attempts/scs/
    drought_elapsed_s: TypeError/ValueError/AttributeError on a
    malformed dict/list), not _restore_fault_section/
    _restore_markout_section's bare except Exception.

    Pre-P3 snapshot semantics (learning-acceleration plan Task 3, T1.3
    decision; see docs/quant/2026-07-25_livelock_f0_decision.md): a
    snapshot missing this section entirely is a NO-OP here, not a clear -
    whatever _probe_admissions/_last_floor_admit_ts already hold survives
    untouched (pinned in tests/test_probe_throttle.py::
    test_pre_p3_snapshot_preserves_existing_window_not_cleared). The sole
    caller (LiquidityBot.__init__, immediately before store.restore())
    always constructs _probe_admissions fresh and empty first, so a real
    restart from a pre-P3 snapshot still nets an EMPTY window in
    practice - up to probe_share_window unthrottled probes before the
    share cap re-binds - and the corpus decay/asset taper/manip gate
    still bound every one of them. Since the SZ-048 drought floor
    (Task 2) shipped, that empty-window shortcut is no longer the only
    road out of a frozen window, so restarting to "unstick" it is not
    the sanctioned path."""
    try:
        if hasattr(bot, "_probe_admissions"):
            pa = data.get("probe_admissions")
            if isinstance(pa, list):
                bot._probe_admissions.clear()
                bot._probe_admissions.extend(bool(x) for x in pa)
        # F0b drought floor (SZ-048, main.py _last_floor_admit_ts):
        # float-or-None spacing clock. Absent (pre-F0b snapshot) or null
        # keeps __init__'s None - the floor then re-arms from scratch and
        # never fires early off a missing key.
        fts = data.get("last_floor_admit_ts")
        if fts is not None and hasattr(bot, "_last_floor_admit_ts"):
            bot._last_floor_admit_ts = float(fts)
    except (TypeError, ValueError, AttributeError):
        log.warning("probe_admissions section malformed - skipped")


def _restore_probe_budget_section(bot, data: dict) -> None:
    """SPB-R probe budget (spec §5, main.py `_budget_tokens` /
    `_budget_tuition`): isolated so a malformed section can't skip
    anything else in restore() - the same ISOLATION principle (and the
    same narrow except tuple) as _restore_probe_admissions_section
    directly above, keeping restore()'s own branch count from growing
    toward pyproject.toml's frozen C901 ceiling.

    Missing/pre-SPB section -> NO-OP here (whatever the bot already
    holds survives untouched, mirroring the probe_admissions missing-
    section semantics); on a real cold start __init__ constructs an
    empty bucket first, so a pre-SPB snapshot nets tokens=0.0 which
    simply refills normally. `last_refill_ts` is deliberately NEVER
    restored (nor persisted): it re-seeds to the first engine `now`
    after restart, so downtime never accrues tokens - the conservative
    direction (spec §5)."""
    try:
        pb = data.get("probe_budget")
        if not isinstance(pb, dict):
            return
        if hasattr(bot, "_budget_tokens") and "tokens" in pb:
            # clamp to [-C, C] on restore (2026-07-31 review #8): a
            # corrupt-but-parsable snapshot must not hand the first
            # decision an unbounded balance (the in-engine clamp only
            # bites at the SECOND refill).
            tok = float(pb["tokens"])
            cap_fn: "Callable[[], float] | None" = getattr(
                bot, "_budget_capacity", None)
            if callable(cap_fn):
                cap = float(cap_fn())
                tok = min(max(tok, -cap), cap)
            bot._budget_tokens = tok
        tu = pb.get("tuition")
        if isinstance(tu, list) and hasattr(bot, "_budget_tuition"):
            restored = [(float(t), float(x)) for t, x in tu]
            bot._budget_tuition.clear()
            bot._budget_tuition.extend(restored)
    except (TypeError, ValueError, AttributeError):
        log.warning("probe_budget section malformed - skipped")


def _restore_long_book_section(bot, data: dict) -> None:
    """Compounder Phase C (task C4): the shared EvidenceLadder (follows
    RiskProtocolStack's own to_dict/from_dict pattern - malformed input
    degrades to keeping whatever state already exists, never raises) and
    the long book's per-asset last-add-ts spacing clock. Isolated so a
    malformed section can't skip anything else in restore() - same
    ISOLATION principle as _restore_fault_section/_restore_markout_section
    above, keeping restore()'s own branch count from growing toward
    pyproject.toml's frozen C901 ceiling."""
    try:
        if getattr(bot, "long_ladder", None) is not None:
            bot.long_ladder.from_dict(data.get("long_book_ladder"))
    except Exception:
        log.exception("long_book_ladder section malformed - skipped")
    try:
        if hasattr(bot, "_long_last_add_ts"):
            ts = data.get("long_book_last_add_ts") or {}
            if isinstance(ts, dict):
                bot._long_last_add_ts.update(
                    {str(k): float(v) for k, v in ts.items()})
    except (TypeError, ValueError, AttributeError):
        log.warning("long_book_last_add_ts section malformed - skipped")
    # task C5 items 3(a)/3(b): the book's own equity-curve peak/drawdown
    # ratchet + the adverse-context-transition-survived episode tracker -
    # a restart must never reset the peak downward (which would let a
    # downgrade breach silently re-clear) or drop a mid-flight episode's
    # accumulated held-exposure/dd-ok flags.
    try:
        if hasattr(bot, "_long_book_realized_pnl_total"):
            bot._long_book_realized_pnl_total = float(
                data.get("long_book_realized_pnl_total",
                        bot._long_book_realized_pnl_total))
        if hasattr(bot, "_long_book_peak_value"):
            bot._long_book_peak_value = float(
                data.get("long_book_peak_value", bot._long_book_peak_value))
        if hasattr(bot, "_long_book_dd_breach_active"):
            bot._long_book_dd_breach_active = bool(
                data.get("long_book_dd_breach_active",
                        bot._long_book_dd_breach_active))
    except (TypeError, ValueError):
        log.warning("long_book equity-curve section malformed - skipped")
    try:
        episode = data.get("long_book_adverse_episode") or {}
        if isinstance(episode, dict) and \
                hasattr(bot, "_long_book_adverse_episode_start"):
            start = episode.get("start")
            bot._long_book_adverse_episode_start = (
                float(start) if start is not None else None)
            bot._long_book_adverse_held_exposure = bool(
                episode.get("held_exposure", True))
            bot._long_book_adverse_dd_ok = bool(
                episode.get("dd_ok", True))
    except (TypeError, ValueError):
        log.warning("long_book_adverse_episode section malformed - skipped")


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
        ttl_sec=(float(d["ttl_sec"])
                if d.get("ttl_sec") is not None else None),
        meta=_restore_meta(d.get("meta")),
    )
    return o


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------
def _restore_pos_gates(bot, data) -> None:
    """Reattach gate verdicts to still-open positions after a restart.

    Extracted rather than inlined into restore(): that method was already
    at the C901 complexity ceiling (40), and one more branch tipped it. The
    honest fix is a named function, not a raised limit — restore() handling
    forty distinct snapshot sections is exactly the shape the ceiling exists
    to flag.

    Values arrive from a snapshot file, which is external input to this
    process, so gate names and verdicts are coerced rather than trusted.
    """
    if not hasattr(bot, "_pos_gates"):
        return
    bot._pos_gates.update(
        {str(k): {str(g): bool(p) for g, p in (v or {}).items()}
         for k, v in (data.get("pos_gates") or {}).items()
         if isinstance(v, dict)})


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
            # W2-18: _last_entry_admit_ts is None until the engine's first
            # fast_cycle lazily seeds it (replay parity) - a manual
            # "snapshot" control command fired before that first cycle
            # must not crash the whole snapshot over one unseeded field.
            _admit_ts = getattr(bot, "_last_entry_admit_ts", None)
            if _admit_ts is None:
                _admit_ts = time.time()
            data = {
                "version": SNAPSHOT_VERSION,
                "saved_at": time.time(),
                "dry_run": bot.dry_run,
                "portfolio": {
                    "starting_capital": state.starting_capital,
                    "cash_balance": state.cash_balance,
                    "savings_balance": state.savings_balance,
                    "reserve_balance": state.reserve_balance,
                    "weekly_realized_pnl": state.weekly_realized_pnl,
                    "last_week_key": state._last_week_key,
                    "monthly_realized_pnl": state.monthly_realized_pnl,
                    "last_month_key": state._last_month_key,
                    "realized_pnl_total": state.realized_pnl_total,
                    "daily_realized_pnl": state.daily_realized_pnl,
                    "fees_paid_total": state.fees_paid_total,
                    # 2026-08-09: the opening-leg fee population that hits
                    # cash but no P&L line (see PortfolioState.
                    # entry_fees_total). Persisted so the honest all-time
                    # figures survive a restart.
                    "entry_fees_total": state.entry_fees_total,
                    # goal-ladder multiplier (RP-072 stressor regime): the
                    # effective monthly goal survives restarts or the ladder
                    # silently un-ratchets every reboot
                    "goal_ladder_mult": getattr(state, "goal_ladder_mult",
                                                1.0),
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
                          "probe": bool(e[4]) if len(e) > 4 else False,
                          # W2-4 lineage: candidate id this position's
                          # signal was registered as (6th slot; older
                          # tuples lack it) - the twin-dedup join key
                          "candidate_id": (e[5] if len(e) > 5 and e[5]
                                           else None),
                          # Compounder Phase C (task C4, C1's carried gap):
                          # which book this pending vector belongs to (7th
                          # slot; older tuples lack it) - "5m" default
                          # threads through restore() the same way every
                          # other pre-C tuple shape does.
                          "book": e[6] if len(e) > 6 else "5m",
                          # gate-truth T4 (T2 review's carried gap): the
                          # informed-flow component scores captured at
                          # signal time (8th slot; older tuples lack it) -
                          # without this a restart on a still-open position
                          # silently degrades its eventual sg_* telemetry
                          # to all-zero even though log_entry recorded the
                          # real components.
                          "gate_components": e[7] if len(e) > 7 else {},
                          # 41b: context-availability flags captured at
                          # signal time (9th slot; older tuples lack it).
                          # None is meaningful (= unrecorded -> blank
                          # UNKNOWN columns) and must survive the trip -
                          # the exact silent-drop this fixed-shape rebuild
                          # inflicted on gate_components before T4.
                          "avail": e[8] if len(e) > 8 else None}
                    for pid, e in bot.history._pending.items()
                },
                "sizer_last_entry": dict(bot.sizer._last_entry),
                "pos_realized": dict(bot._pos_realized),
                # RESTART-COUPLING continuity (2026-07-20): the auto-updater
                # restarts the bot on every deploy; temporal anchors that
                # lived only in memory silently reset each time -
                # exit-escalation counters (a mid-ladder restart re-based the
                # slippage widening), the ML-073 drought clock (the 1h
                # drought could never fire on an active deploy day), and the
                # state-change sampler (a phantom bootstrap event per asset
                # per restart). Downtime does not count toward the drought:
                # elapsed RUNNING time is stored, not the wall timestamp.
                "exit_attempts": dict(getattr(bot, "_exit_attempts", {})),
                "drought_elapsed_s": max(0.0, time.time() - _admit_ts),
                "scs": (bot.scs.to_dict()
                        if getattr(bot, "scs", None) is not None else {}),
                # 41c: moomoo z-window + freeze-gate state. Guarded on the
                # METHOD (runner-state doubles stub moomoo with a bare
                # close()-only namespace), same duck-typed convention as
                # every other optional section here.
                "moomoo_state": (bot.moomoo.to_dict() if callable(
                    getattr(getattr(bot, "moomoo", None), "to_dict", None))
                    else {}),
                # V2 vindication continuity: fired-detector maps for OPEN
                # positions and the graded reliability ledger. Detector
                # OBSERVATION state stays un-snapshotted (see NOTE below);
                # the ledger is outcome bookkeeping, not observations, so
                # persisting it carries no stale-advice hazard.
                "pos_thales": {k: list(v) for k, v in
                               getattr(bot, "_pos_thales", {}).items()},
                # Gate attribution for open positions (realized-outcome
                # loop). Must persist for the same reason pos_thales does:
                # a position opened before a restart and closed after it
                # would otherwise teach the gate ledger nothing, and long
                # holds — 36h at the 432-bar horizon — make that the
                # COMMON case rather than an edge one.
                "pos_gates": {k: dict(v) for k, v in
                              getattr(bot, "_pos_gates", {}).items()},
                "thales_reliability": bot.thales.reliability_to_dict()
                if getattr(bot, "thales", None) is not None else {},
                "halted": bot._halted,
                # W2-15: latched faults survive a restart, except the
                # RECOVERABLE_FAULTS keys core/fault.py's restore() drops
                # (currently "cycle_wedged" - runner.py's documented
                # restart-recoverable wedge). See core/fault.py docstring.
                "fault": bot.fault.to_dict()
                if getattr(bot, "fault", None) is not None else {},
                # NOTE: THALES detector state is deliberately NOT
                # snapshotted - TH-016's restart safety relies on
                # last_fast_ts==0 cold-starting fresh (docs/THALES.md).
                # Persisting it without the lapse fields would silently
                # re-create the 2026-07-14 stale-advice hole.
                "monitor": bot.monitor.to_dict(),
                # hedge churn-guard clocks/latches (2026-08-07): median PC
                # uptime is 0.5h - an amnesiac cooldown resets every deploy.
                # hasattr: QA harnesses snapshot stub bots without a hedger
                "hedger": (bot.hedger.to_dict()
                           if hasattr(bot, "hedger") else {}),
                "postmortem": bot.postmortem.to_dict(),
                "performance": bot.perf.to_dict()
                if getattr(bot, "perf", None) is not None else {},
                # a restart must not launder an active per-asset trip
                "circuit_breaker": bot.breaker.to_dict()
                if getattr(bot, "breaker", None) is not None else {},
                # W2-16: pure telemetry (no trading decision) - a deploy
                # restart used to wipe the adverse-selection window entirely,
                # and under deploy cadence the window could never accumulate.
                "markout": bot.markout.to_dict()
                if getattr(bot, "markout", None) is not None else {},
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
                # P3 probe throttle rolling share-cap window (main.py
                # _probe_admissions): the auto-updater restarts the bot on
                # every deploy (see the RESTART-COUPLING note above), so an
                # unpersisted window would reset every deploy, not just rare
                # crashes, making a 40-admission cap nearly inert in
                # production. Plain bool list, same shape as stop_hit.
                "probe_admissions": [bool(x) for x in
                                    getattr(bot, "_probe_admissions", [])],
                # F0b drought floor (SZ-048): the floor's spacing clock
                # must survive the same deploy-restart cadence as the
                # window above - unpersisted, every deploy would reset
                # the trickle bound and allow an immediate re-fire.
                # Deliberately RAW (wall-comparable) unlike the drought
                # clock's elapsed-anchored persistence: downtime counts
                # toward SPACING (can only deny sooner re-fires, safe)
                # but never toward the DROUGHT itself.
                "last_floor_admit_ts": getattr(
                    bot, "_last_floor_admit_ts", None),
                # SPB-R probe budget (spec §5, MANDATORY): the token
                # bucket + the trailing-24h clipped-tuition ledger must
                # survive the same deploy-restart cadence as the window
                # above, or the auto-updater's restart-per-deploy would
                # reset the budget every deploy. last_refill_ts is
                # deliberately NOT persisted: it re-seeds to the first
                # engine `now` after restart, so downtime never accrues
                # tokens - degraded toward FEWER probes, the safe
                # direction (the old deque's restart asymmetry was
                # permissive; this one is conservative). Order-terminal
                # refunds need no state here: the cost rides in
                # order.meta, and OM state has its own lifecycle.
                "probe_budget": {
                    "tokens": float(getattr(bot, "_budget_tokens", 0.0)),
                    "tuition": [[float(t), float(x)] for t, x in
                                getattr(bot, "_budget_tuition", [])],
                },
                # Compounder Phase C (task C4): the shared EvidenceLadder
                # (closed_paper/closed_live/pf_live/downgrade markers -
                # risk/long_book.py's own to_dict/from_dict) and the long
                # book's per-asset add-spacing clock. Same pattern as
                # risk_protocols above - the parsed ladder config is
                # NOT included, only mutable state; the caller re-supplies
                # config at construction every boot.
                "long_book_ladder": (bot.long_ladder.to_dict()
                                    if getattr(bot, "long_ladder", None)
                                    is not None else {}),
                "long_book_last_add_ts": dict(
                    getattr(bot, "_long_last_add_ts", {})),
                # task C5 items 3(a)/3(b): the book's own equity-curve
                # peak/drawdown ratchet + the adverse-context-transition-
                # survived episode tracker - a restart must never reset
                # the peak downward or drop a mid-flight episode's
                # accumulated held-exposure/dd-ok flags.
                "long_book_realized_pnl_total": float(
                    getattr(bot, "_long_book_realized_pnl_total", 0.0)),
                "long_book_peak_value": float(
                    getattr(bot, "_long_book_peak_value", 0.0)),
                "long_book_dd_breach_active": bool(
                    getattr(bot, "_long_book_dd_breach_active", False)),
                "long_book_adverse_episode": {
                    "start": getattr(
                        bot, "_long_book_adverse_episode_start", None),
                    "held_exposure": bool(getattr(
                        bot, "_long_book_adverse_held_exposure", True)),
                    "dd_ok": bool(getattr(
                        bot, "_long_book_adverse_dd_ok", True)),
                },
            }
            return self._seal_and_write(data)
        except Exception:
            log.exception("snapshot failed - continuing without persisting")
            return False

    def _seal_and_write(self, data: dict) -> bool:
        # integrity CHECKSUM (not a tamper seal): a plain SHA-256 over the
        # payload, so a torn or bit-rotted file is DETECTED at load instead
        # of silently restoring a corrupt book. NO secret/HMAC - it catches
        # ACCIDENTAL corruption only; any writer with file access can
        # recompute it, so it is not evidence against deliberate tampering.
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
            # so there is always one known-good generation to fall back to.
            # M1: both replaces go through core.runtime.replace_with_retry -
            # the SAME Windows transient-PermissionError retry atomic_write_json
            # has always had. state.json is the book of record and was the one
            # publisher without it, so a reader holding it (session_digest under
            # the hourly check-in, train_meta) dropped the post-fill "never lose
            # an executed fill" snapshot: snapshot() swallows the exception and
            # main.py discards the False. Reused, never reinvented.
            if self.path.exists():
                try:
                    replace_with_retry(self.path,
                                       self.path.with_suffix(".json.bak"))
                except OSError:
                    log.debug("bak rotation failed - continuing")
            replace_with_retry(tmp, self.path)
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

    def _quarantine(self, reason: str) -> None:
        """Preserve a REJECTED snapshot before the write cadence destroys it.

        WHY THIS EXISTS (verified 2026-09-05, reproduction failed before the
        fix). `restore()` returning False starts the bot fresh, and the runner's
        periodic `snapshot()` (unconditional on whether a restore succeeded)
        then overwrites the primary and rolls it onto `.bak`. At the shipped
        `system.snapshot_interval_sec = 30` BOTH generations of the rejected
        state are gone inside ~60 seconds. Measured on a seeded valid snapshot:
        `recoverable anywhere on disk: False` after cadence #2.

        THE REACHABLE TRIGGER IS THE ARMED-LIVE RESTART. The version check has
        never fired (`SNAPSHOT_VERSION` has one commit in its history: "Initial
        commit"). The paper<->live mismatch below fires on exactly the boot
        where `dry_run` flips false - step 3 of CLAUDE.md invariant 1's
        four-step road to live - which is the boot whose prior state is most
        worth keeping and the one where the operator is least able to redo it.

        Copies, never moves: `restore()`'s semantics are unchanged and the
        caller still starts fresh. Best-effort by construction - a quarantine
        that raised would turn a recoverable start into a crash loop.
        """
        stamp = int(time.time())
        tag = "".join(c if c.isalnum() else "_" for c in reason)[:40]
        for src in (self.path, self.path.with_suffix(".json.bak")):
            try:
                if not src.exists():
                    continue
                dst = src.with_name(f"{src.name}.rejected_{stamp}_{tag}")
                shutil.copy2(src, dst)
                log.warning("snapshot quarantined: %s -> %s (%s)",
                            src, dst.name, reason)
            except OSError as e:
                log.error("could not quarantine %s (%s) - the rejected "
                          "snapshot will be overwritten by the next cadence",
                          src, e)

    def restore(self, bot) -> bool:
        data = self._pick_snapshot()
        if data is None:
            log.error("no usable snapshot generation - starting fresh")
            self._quarantine("unreadable")
            return False
        if data.get("version") != SNAPSHOT_VERSION:
            log.warning(f"snapshot version {data.get('version')} != "
                        f"{SNAPSHOT_VERSION} - starting fresh")
            self._quarantine("version_mismatch")
            return False
        if bool(data.get("dry_run", True)) != bot.dry_run:
            log.warning(
                f"snapshot was taken with dry_run={data.get('dry_run')} but bot "
                f"is running dry_run={bot.dry_run} - refusing to mix paper and "
                f"live state; starting fresh (use --fresh to silence this)")
            self._quarantine("paper_live_mismatch")
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
            # pool fields absent in pre-upgrade snapshots -> defaults
            state.reserve_balance = float(p.get("reserve_balance", 0.0))
            state.weekly_realized_pnl = float(
                p.get("weekly_realized_pnl", 0.0))
            if p.get("last_week_key"):
                state._last_week_key = str(p["last_week_key"])
            state.monthly_realized_pnl = float(
                p.get("monthly_realized_pnl", 0.0))
            if p.get("last_month_key"):
                state._last_month_key = str(p["last_month_key"])
            state._last_pnl_reset_date = p.get("last_pnl_reset_date", "")
            state._equity_high_water = float(p.get("equity_high_water",
                                                   state.starting_capital))
            # entry_fees_total (2026-08-09): a lifetime accumulator added
            # after this bot had already been trading, so defaulting it to
            # 0.0 on a pre-upgrade snapshot would leave the honest all-time
            # figures permanently wrong by the whole historical population.
            # It is EXACTLY derivable from the cash identity instead:
            #     cash = start + realized - entry_fees - (savings+reserve)
            # because those are the only four paths that move cash
            # (record_realized_pnl, record_entry_fee, and the pool
            # skim/refill pair in risk/capital_manager, whose net cash
            # removal is precisely the two pool balances). Backfilled ONCE;
            # thereafter the persisted value wins. Measured on the live
            # 2026-08-09 snapshot this recovers $185.94 of $382.59 lifetime
            # fees that no P&L line had ever shown.
            if "entry_fees_total" in p:
                state.entry_fees_total = float(p["entry_fees_total"] or 0.0)
            else:
                state.entry_fees_total = max(
                    0.0,
                    state.starting_capital + state.realized_pnl_total
                    - state.cash_balance - state.savings_balance
                    - state.reserve_balance)
                log.warning(
                    "entry_fees_total absent from snapshot - backfilled "
                    "%.2f from the cash identity (opening-leg fees that "
                    "hit cash but no P&L line; all-time P&L was "
                    "understating by this amount)", state.entry_fees_total)
            # goal ladder: absent on a pre-RP-072 snapshot => 1.0 (base goal).
            # Unlike entry_fees_total there is nothing to backfill - the
            # ladder had never escalated before it existed.
            state.goal_ladder_mult = max(float(p.get("goal_ladder_mult",
                                                     1.0) or 1.0), 1.0)
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
                        bool(h.get("probe", False)),
                        h.get("candidate_id") or "",
                        # Compounder Phase C (task C4, C1's carried gap):
                        # pre-C snapshots lack this key -> "5m" default,
                        # same convention as position_from_dict's own book
                        # default (never silently reclassify onto the
                        # long book on restore).
                        h.get("book") or "5m",
                        # gate-truth T4 (T2 review's carried gap): pre-T4
                        # snapshots lack this key -> {} default, same
                        # inert convention _append_row already applies to
                        # a missing/None gate_components argument.
                        h.get("gate_components") or {},
                        # 41b: pre-41b snapshots lack this key -> None =
                        # unrecorded; _append_row writes blank UNKNOWN
                        # columns for any falsy avail, so restored rows
                        # never fabricate a "measured down" reading.
                        h.get("avail") or None)
        except Exception:
            log.exception("history section malformed - skipped")

        try:
            bot.sizer._last_entry.update(data.get("sizer_last_entry", {}))
        except (TypeError, ValueError):
            log.warning("sizer_last_entry section malformed - skipped")
        # 41c: moomoo windows/freeze state - restored BEFORE the first
        # poll so 41a's gate classifies that poll against the pre-restart
        # per-ticker returns (a still-closed market reads frozen from
        # poll one instead of re-seeding an empty window with its quote).
        # from_dict is fail-soft by contract; pre-41c snapshots simply
        # lack the key.
        try:
            ms = data.get("moomoo_state")
            if ms and callable(getattr(getattr(bot, "moomoo", None),
                                       "from_dict", None)):
                bot.moomoo.from_dict(ms)
        except Exception:
            log.exception("moomoo section malformed - skipped")
        try:
            bot._pos_realized.update(data.get("pos_realized", {}))
        except (TypeError, ValueError):
            log.warning("pos_realized section malformed - skipped")
        try:
            if hasattr(bot, "_exit_attempts"):
                bot._exit_attempts.update(
                    {str(k): int(v) for k, v in
                     (data.get("exit_attempts") or {}).items()})
            if getattr(bot, "scs", None) is not None:
                bot.scs.from_dict(data.get("scs") or {})
            if (data.get("drought_elapsed_s") is not None
                    and hasattr(bot, "_last_entry_admit_ts")):
                # resume the RUNNING-time drought clock; the gap while the
                # bot was down is not a signal drought
                bot._last_entry_admit_ts = (
                    time.time() - float(data["drought_elapsed_s"]))
        except (TypeError, ValueError, AttributeError):
            log.warning("continuity anchors malformed - timers restart fresh")
        try:
            if hasattr(bot, "_pos_thales"):
                bot._pos_thales.update(
                    {str(k): [tuple(x) for x in v] for k, v in
                     (data.get("pos_thales") or {}).items()})
            _restore_pos_gates(bot, data)
            if getattr(bot, "thales", None) is not None:
                bot.thales.reliability_restore(
                    data.get("thales_reliability") or {})
        except (TypeError, ValueError):
            log.warning("thales V2 sections malformed - skipped")
        bot._halted = bool(data.get("halted", False))
        # W2-15: latched faults re-latch on top of the FaultManager's
        # already-armed state (main.py calls fault.arm() BEFORE store.restore()
        # specifically so this composes - see core/fault.py docstring).
        # RECOVERABLE_FAULTS keys (cycle_wedged) are dropped inside restore().
        _restore_fault_section(bot, data)
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
        # per-subsystem isolation lives in _restore_subsystem_sections (its
        # docstring carries the why): one malformed section must never skip
        # the others.
        _restore_subsystem_sections(bot, data)
        _restore_probe_admissions_section(bot, data)
        _restore_probe_budget_section(bot, data)
        try:
            rp = data.get("risk_protocols")
            if rp and getattr(bot, "risk_protocols", None) is not None:
                bot.risk_protocols.from_dict(rp)
        except Exception:
            log.exception("risk_protocols section malformed - skipped")
        _restore_long_book_section(bot, data)

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
