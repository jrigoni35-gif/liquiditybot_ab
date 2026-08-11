"""
liquiditybot v2 - orchestrator

Cadence model (all inside one thread; nothing blocks):

FAST  (every polling_interval_sec, default 5s)
        Kraken marks + books, poll open orders -> apply fills,
        hard stops (vol/regime scaled - v1 gap fixed), profit tiers
        (regime tier_scale + inventory tighten), inventory derisk,
        hedging.

SLOW  (every slow_cycle_every_n fast cycles, default 30s)
        OKX/Binance.US fetch -> market view, fair value, vol/liquidity
        regimes, intraday correlation, sentiment poll, then the entry
        pipeline: signal engine (informed_flow by default; five_gate is
        the rollback, set strategies.engine) -> features -> meta P(win)
        -> narrative filter -> Kelly sizer -> AS quote -> pre-trade gate
        -> limit order via OrderManager.

HOURLY (macro_refit_minutes)
        Daily candles -> HMM/TSMOM macro regime refit, turbulence.

Order of authority on any entry: regime playbook -> inventory ->
leverage governor -> sizer -> pre-trade gate. Any veto kills the trade.
Sentiment can only shade size/confidence within clamps; it cannot
create, veto, or flip a trade.
"""

import csv
import hashlib
import json
import logging
import math
import os
import random
import time
import types
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Deque, Optional

import numpy as np

from core.audit import get_audit
from core.codes import Code, tag
from core.goals import evaluate_goal
from core.sanitize import safe_float
from core.precision import fmt_price, price_decimals as _price_decimals
from core.state import PortfolioState, Position
from core.persistence import StateStore
from core.runtime import SimOverrides, durable_append
from core.alerts import AlertSink
from core.fault import FaultManager, Severity
from core.config_guard import enforce as enforce_config
from core.watchdog import Watchdog
from execution.risk_firewall import RiskFirewall
from data.okx_feed import OKXFeed
from data.binanceus_feed import BinanceUSFeed
from data.ws_feed import (KrakenV2BookStream, LiveMarketCache,
                          WebSocketFeedManager)
from data.kraken_feed import KrakenFeed
from data.webdata_feed import WebDataFeed
from data.moomoo_feed import MoomooFeed
from data.context_engine import ContextFeed
from strategies.liquidity_model import LiquidityModel, extract_base_asset
from strategies.signal_gates import (GateStats, SignalGateEngine,
                                     concentration_conf_mult)
from risk.capital_manager import CapitalManager
from risk.profit_tiers import ProfitTierEngine
from risk.stop_placement import nudge_stop_off_round
from execution.algos import ExecutionScheduler
from execution.routing import SmartOrderRouter
from risk.leverage import LeverageGovernor
from risk.position_sizer import PositionSizer
from risk.protocols import RiskProtocolStack
from risk.long_book import (EvidenceLadder, LongBookEngine, AddPlan,
                            DenyReason, EngineConfig, bid_is_stale,
                            thesis_stop_price)
from regime import (MacroRegimeEngine, VolRegimeEngine,
                    LiquidityRegimeEngine, CorrelationEngine,
                    MacroRegimeState)
from execution.fair_value import FairValueEngine
from execution.market_maker import AvellanedaStoikovQuoter
from execution.inventory import InventoryManager
from execution.pretrade import PreTradeGate, PreTradeContext
from execution.order_manager import OrderManager
from execution.hedging import HedgeEngine
from execution.markout import MarkoutTracker
from execution.tactics import ExecutionPlanner
from execution.grid_ladder import GridLadderEngine
from ml.features import FEATURE_NAMES, REGIME_LABELS, build_features
from ml.meta_model import MetaModelService
from ml.history import HistoryStore, CandidateLabeler, HorizonShadowStore
from ml.labeling import ExitPolicy, barrier_geometry
from ml.event_sampler import StateChangeSampler
from ml.monitor import ModelMonitor
from core.performance import PerformanceTracker
from ml.postmortem import PostmortemEngine, TradeThesis
from risk.circuit_breaker import CircuitBreaker
from risk.conviction import ConvictionFormula
from sentiment.scanner import SentimentScanner
from sentiment.fear_filter import NarrativeFilter, StructuralInputs

log = logging.getLogger("liquiditybot.main")

EPS = 1e-9


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config(path: str = "config.json") -> dict:
    """CWD-independent: the given path is tried as-is; a relative path
    that doesn't exist from the current directory falls back to the
    package directory, so `python /path/to/runner.py` works from
    anywhere."""
    if not os.path.isabs(path) and not os.path.exists(path):
        anchored = os.path.join(BASE_DIR, path)
        if os.path.exists(anchored):
            path = anchored
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pick_unteachable_unwind(positions: list, pending_ids: set,
                            at_capacity: bool,
                            rows: int, until_live_rows: int, now: float,
                            min_age_h: float):
    """Learning-phase anti-wedge (ML-071), pure decision logic: when the
    book is full and NOT ONE open position can produce a training row
    (their pending vectors were dropped by a feature-schema gate), the
    row pipeline is starved behind dead weight - return the OLDEST
    non-hedge position to unwind, one per call. If even one position
    still teaches, or exploration has graduated (rows >=
    until_live_rows), never intervenes. Exits remain owned by the tier
    engine/ratchet in every other circumstance."""
    if not at_capacity or rows >= until_live_rows or not positions:
        return None
    if any(p.position_id in pending_ids for p in positions):
        return None
    # book=="long" is exempt (same lane rule as ML-073's picker below): a
    # Phase-C thesis position is not dead weight blocking the row
    # pipeline - it is the compounder holding its slot by design. The
    # anti-wedge may still drain unteachable 5m positions around it.
    old_enough = [p for p in positions if not p.is_hedge and
                  getattr(p, "book", "5m") != "long" and
                  (now - p.opened_at.timestamp()) / 3600.0 >= min_age_h]
    if not old_enough:
        return None
    return max(old_enough, key=lambda p: now - p.opened_at.timestamp())


# goal columns appended (in fixed order) to every period-close ledger row
_GOAL_COLS = ["goal", "hit", "category", "attainment_pct", "shortfall_usd",
              "miss_reason"]


def _append_period_ledger(path: Path, row: dict, cols: list) -> None:
    """Append one period-close row to a pool/goal ledger (header on create
    OR on a zero-length file, UTF-8, torn-tail-healed, fsynced). Fixed
    column order so the file stays machine-readable as the summary dict
    grows - callers pass the column order for their period (weekly vs
    monthly).

    This was the only append-only writer in the repo with NO error
    handling at all: an OSError propagated straight into the period-close
    path, so an unwritable outputs/ could abort a weekly/monthly roll.
    durable_append returns False instead (CLAUDE.md invariant 5:
    bookkeeping never breaks the action it records)."""
    durable_append(path, lambda f: csv.writer(f).writerow(
        [row.get(c, "") for c in cols]),
        header=",".join(cols) + "\r\n")


def exit_in_flight(open_orders: list, position_id: str) -> bool:
    """True when a working exit order already exists for this position.
    The learning-phase unwinds (ML-071/ML-073) run every slow tick; without
    this guard a slow fill makes them re-log the same disposition each tick
    and re-enter _submit_exit, whose maker-preempt rung would cancel a
    resting maker profit-take — paying the spread for a close that is not
    urgent (the working exit banks the same label when it fills)."""
    return any(o.purpose == "exit" and o.position_id == position_id
               for o in open_orders)


def effective_realize_spans(spans: float, fastpath: float,
                            occupancy: int, slot_cap: int,
                            drought_h: float = 0.0,
                            drought_after_h: float = 0.0) -> float:
    """ML-073 VALUE-OF-INFORMATION horizon (pure, unit-tested). The realize
    horizon only throttles learning when the book is FULL — with a free slot
    a new teach trade can open regardless, so holding a position to the full
    label window costs nothing and keeps the richer outcome. Full book ->
    the shorter fastpath horizon buys a teach slot with the least
    label-richness cost; that faster live-label flow reaches the evidence
    gate's floors sooner, unlocking model capacity earlier (compounding).

    `occupancy` must mirror the ENTRY GATE's fullness test (all filled
    positions INCLUDING hedges, plus resting entry orders), not the
    teachable subset: a hedge or resting entry occupies a slot no teach
    trade can use — counting only non-hedge positions left the fastpath
    dormant in exactly the entry-blocked state it exists to clear
    (adversarially-verified fleet finding, 2026-07-20).

    SIGNAL DROUGHT extension: the free-slot premise is "a new teach trade
    can open regardless" — during a drought (no entry admitted for
    drought_after_h hours; thin weekend books, sustained gate vetoes) that
    premise fails, so holding to the full window buys nothing and costs
    label latency with no offsetting entry flow. The fastpath then arms
    with free slots too. drought_after_h <= 0 disables the extension.
    fastpath <= 0 disables everything (always the full spans)."""
    if fastpath <= 0:
        return spans
    if occupancy >= max(slot_cap, 1):
        return min(spans, fastpath)
    if drought_after_h > 0 and drought_h >= drought_after_h:
        return min(spans, fastpath)
    return spans


def pick_label_mature_unwind(positions: list, rows: int, until_live_rows: int,
                             now: float, mature_h: float):
    """Learning-phase LABEL REALIZATION (ML-073), pure decision logic. The
    documented SD-002 starvation loop: dry-run exploration opens paper trades
    that must CLOSE to become live labels, but in a quiet book they hit no
    tier/stop and sit for days — the book fills to capacity, no new teaching
    entry can fire, and the model never gets fresh ground truth (0 entries,
    18x retrain-requested-but-cold).

    A position held past the model's LABEL HORIZON has already resolved its
    triple-barrier outcome; holding it open teaches nothing more. Return the
    stalest non-hedge position older than `mature_h` so it closes at market,
    banking its live label and freeing a slot — one per call, so the book
    drains gradually, not in a flatten. Auto-off once exploration has
    graduated (rows >= until_live_rows): past that, exits belong entirely to
    the tier engine/ratchet. Caller gates on dry_run (never live).

    BRACKET positions (geometry-alignment follow-up, 2026-07-28): a
    position trading its labeled bracket (bracket_pt_frac armed, T5) is
    mature ONLY once its OWN bracket_deadline_ts has passed — never on
    the mature_h clock. The VOI fastpath (spans < 1) realized SUI
    efc8f3e2 at 2.0h of an 8h bracket with barrier="realized", whose
    exit_sim label era the era-exclusion filter drops from training: the
    slot was recycled for a label the trainer threw away, and the traded
    bet stopped being the labeled bet. Before the deadline the bet is
    UNRESOLVED; past it this close IS the vertical barrier (the caller
    threads reason "tb_time" so the row trains). An armed bracket with
    NO deadline (defensive — the fast tb_time leg can never fire on it)
    keeps the legacy clock or the position would be immortal.
    getattr-guarded: pre-T5 doubles/snapshots may lack the fields."""
    if rows >= until_live_rows or not positions or mature_h <= 0:
        return None

    def _mature(p) -> bool:
        # LONG-BOOK exemption (live evidence ETH 15403f29, 2026-07-28
        # 18:32Z): the fastpath realized a Phase-C thesis position (12%
        # structural stop, built to run for days) at exactly 2.0h,
        # banking a training-dead exit_sim label and defeating the
        # compounder lane - the long book shipped after ML-073 and was
        # never exempted. A book=="long" position is not teach
        # inventory, at any age. getattr default "5m" keeps pre-Phase-C
        # doubles/snapshots on the legacy clock.
        if p.is_hedge or getattr(p, "book", "5m") == "long":
            return False
        if getattr(p, "bracket_pt_frac", 0.0) > EPS and \
                getattr(p, "bracket_deadline_ts", 0.0) > EPS:
            return now >= p.bracket_deadline_ts
        return (now - p.opened_at.timestamp()) / 3600.0 >= mature_h

    mature = [p for p in positions if _mature(p)]
    if not mature:
        return None
    return max(mature, key=lambda p: now - p.opened_at.timestamp())


def probe_corpus_decay_factor(live_labels: int, corpus_target_live: int,
                              floor_frac: float) -> float:
    """P3 corpus-aware probe throttle, pure decay math (2026-07-23 P&L
    diagnosis): probes are 69% of live closes and -$22.87 of -$31.68
    measured net PnL, while the corpus (3.3k rows / 214 live) has grown
    past the point marginal probe value justifies the base admission
    rate. effective_rate = base_rate x clip(corpus_target_live /
    max(live_labels, 1), floor_frac, 1.0) - decays the exploration
    epsilon toward `floor_frac` (never to zero: the learner keeps a
    trickle) as live_labels grows past corpus_target_live. `live_labels`
    is the SAME live-row count _exploration_active/ML-071/ML-073 already
    read via HistoryStore.source_counts() - never re-counted here."""
    raw = corpus_target_live / max(live_labels, 1)
    return min(max(raw, floor_frac), 1.0)


def cross_fitted_calibrated_oof(oof_p, oof_y, folds: int = 5):
    """H13 (2026-08-01 audit): calibration-HONEST out-of-fold probabilities
    for the deploy gate.

    The shipped artifact keeps its full-pool PAV calibrator (unchanged,
    byte-identical) - but scoring the challenger with a calibrator fit on
    the very rows it is then scored on is in-sample. PAV is unregularized
    and maximally adapted to its own fit set, so that Brier is biased DOWN
    by a systematic, one-directional optimism (measured against fresh
    independent draws of the same fitted calibrator: +0.0066 at n=300,
    +0.0050 at n=600, +0.0032 at n=1200) while the champion is scored
    strictly out-of-sample by ModelMonitor.rescore_frozen's FROZEN
    calibrator. `challenger_brier_margin` is 0.005, so the tilt is
    25-150% of the entire deploy margin and always in the challenger's
    favour; it never averages out across repeated retrains.

    Fix: fit on each fold's COMPLEMENT and transform only that fold, so
    every returned probability is out-of-sample w.r.t. the calibrator that
    produced it. Folds are STRIDED (i % k), not contiguous blocks: each
    complement is then a representative sample of the same pool, which
    isolates the in-sample optimism this exists to remove instead of
    confounding it with a distribution shift the shipped full-pool
    calibrator will never suffer. Deterministic (no RNG) - replay
    determinism is a standing engine invariant.

    K defaults to 5, not the minimum 2: every complement is then 80% of
    the pool, so each fold's calibrator stays close to the full-pool one
    the artifact actually ships (K-fold pessimism shrinks with K), and the
    complement still clears IsotonicCalibrator's 20-point fit floor at the
    deploy_min_oof=30 evidence floor - K=2 would fit on 15 rows there and
    silently degrade to raw exactly where the gate is most marginal.

    Degenerate pools fall through to IsotonicCalibrator's own documented
    identity behaviour (fit() needs >= 20 points, `fitted` needs >= 2
    knots): a fold whose complement cannot be fit is scored on RAW
    probabilities, exactly as the whole pool already is below 20 points.
    Raw is never optimistic, so the gate stays fail-closed on promotion."""
    from ml.calibration import IsotonicCalibrator
    p = np.asarray(oof_p, float)
    y = np.asarray(oof_y, float)
    n = len(p)
    k = max(int(folds), 2)
    if n == 0:
        return p
    out = np.array(p, float)
    idx = np.arange(n)
    for i in range(k):
        part = idx % k == i
        if not part.any() or part.all():
            continue
        cal = IsotonicCalibrator().fit(p[~part], y[~part])
        out[part] = cal.transform(p[part])
    return out


def _regime_under_coverage_floor(regime_live: int,
                                 regime_floor_live: int) -> bool:
    """Task 4 (#103) regime-coverage hold, pure math: True when the
    CURRENT regime's own live-labeled count is still below
    regime_floor_live - the corpus-decay term above must be held at 1.0
    (no decay) for that regime's signals rather than let a mature GLOBAL
    corpus (dominated by other regimes) mask an under-covered one.
    regime_floor_live<=0 disables the check (byte-identical P3: the term
    never overrides the shipped decay)."""
    return regime_floor_live > 0 and regime_live < regime_floor_live


# nudge_stop_off_round_number RETIRED here 2026-08-11 (cut #7): its
# tighten-side semantics ("exit before the cascade detonates") meant any
# sweep TO a round level took the position out - the shakeout ejection the
# operator's bull-readiness directive names. The unified widen-beyond
# implementation, its documented semantic flip, and the same half-step
# lattice live in risk/stop_placement.nudge_stop_off_round.


def manip_suspect_score(spoof: float, whiplash: float,
                        kraken_imb: float, composite_imb: float) -> float:
    """Adversarial-data suspicion in [0, 1], parameter-free (MAX of
    normalized components, no fitted weights): the most alarming single
    indicator sets the level. Components a manipulator cannot cheaply
    fake in unison:
      spoof      - resting-ladder manipulation signature (liquidity regime)
      whiplash   - imbalance flip-flopping (painted flow)
      divergence - the EXECUTION venue's book disagreeing with the
                   composite street book: painting every venue at once,
                   including the one we trade on, is expensive
    Feeds four places: the manip_suspect FEATURE (the model learns what
    fear of manipulation is worth), a training-weight DISCOUNT (lessons
    learned under suspect data count less), the status panel (the operator
    sees who is being leaned on), and — since the anti-scalp gate — a LIVE
    downsize/veto on NEW entries only (risk.manip_gate; exits untouched):
    don't post fresh liquidity into a book a bigger fish is painting to
    scalp. Conservative by default so only a clearly manipulated book bites.
    """
    divergence = min(abs(float(kraken_imb) - float(composite_imb)) / 4.0,
                     1.0)                      # imb is clipped to [-2, 2]
    return float(min(max(spoof, whiplash, divergence), 1.0))


def manip_entry_scale(score: float, downsize_at: float, veto_at: float,
                      min_scale: float):
    """Anti-scalp entry sizing under manipulation suspicion. Returns a
    multiplicative size scale in [min_scale, 1.0] for a NEW entry, or None
    to VETO it. Below downsize_at: 1.0 (untouched). downsize_at..veto_at:
    linear taper from 1.0 down to min_scale (the more painted the book, the
    less liquidity we post into it). >= veto_at: None — refuse the entry, so
    a bigger fish can't spoof us into adding liquidity it then scalps. Pure
    and parameter-free beyond the configured band; EXITS never call this."""
    # a non-finite score (a NaN leaking up from spoof/whiplash) must not
    # propagate: NaN>=veto and NaN<downsize are both False, so it would fall
    # into the taper and return NaN, which the sizer's _fin guard then
    # substitutes with 1.0 — silently discarding kelly_mult/explore_scale and
    # UP-sizing the entry (review A1-F3). Treat unknown suspicion as none.
    if not math.isfinite(score):
        return 1.0
    if score >= veto_at:
        return None
    if score < downsize_at:
        return 1.0
    span = max(veto_at - downsize_at, 1e-9)
    frac = (score - downsize_at) / span
    return 1.0 - frac * (1.0 - min_scale)


def whiplash_suspicion(whiplash_std: float, healthy_p95: float,
                       spoofy_threshold: float) -> float:
    """Normalize the liquidity model's raw imbalance-whiplash (a STD with
    healthy p50~1.1 / p95~1.27 at the 30s book cadence — see the 45h
    calibration in regime/liquidity_regime.py) into the [0, 1] suspicion
    scale manip_suspect_score expects: 0 anywhere inside the healthy
    envelope, 1 at the classifier's own 'spoofy' threshold. Feeding the
    raw std saturated the score on every quiet book (healthy median 1.1
    clamps to 1.0), which pegged manip_suspect=1.0 for entire overnight
    sessions and halved the training weight of perfectly good rows."""
    span = max(float(spoofy_threshold) - float(healthy_p95), 1e-9)
    return float(min(max((float(whiplash_std) - float(healthy_p95)) / span,
                         0.0), 1.0))


# v8 venue-grounded candle plumbing (module-level so the duck-typed test
# stand-ins that call _augment_view_with_kraken unbound keep working):
# FETCH_BUDGET bounds slow-cycle latency + Kraken REST budget - at most
# this many OHLC calls per cycle, most-stale assets first (candles are 5m
# bars; being up to candle_refresh_sec behind is harmless). STALE_MULT is
# the serving fence: cached venue bars older than this multiple of the
# refresh cadence are treated as ABSENT, so a persistently-failing fetch
# degrades to the external feed instead of freezing every candle-derived
# feature on the last good frame (the DL-10 never-expires failure class).
# 3x = two missed refreshes of grace before falling back.
_KR_CANDLE_FETCH_BUDGET = 3
_KR_CANDLE_STALE_MULT = 3.0

# FW-080 stale-bar threshold: 4 five-minute bars. Thin Kraken pairs
# legitimately omit empty intervals, so 2 bars would cry wolf on quiet
# listings (latency audit 2026-08-07).
_STALE_BAR_SEC = 1200.0


def _bar_age_check(bot, asset: str, candles: list, now: float) -> None:
    """Venue bars carry their own timestamps; fetch age proves the CALL
    was recent, not the DATA (latency audit 2026-08-07: nothing anywhere
    validated candles[-1]['time'], so a venue serving a stale OHLC page
    was undetectable while those bars fed vol, features and sizing).
    Warns FW-080 once per stale EPISODE - latched per asset on the bot,
    re-armed when the feed recovers - when the last committed bar lags
    more than _STALE_BAR_SEC behind the engine clock. Detection only:
    the veto-grade response is sequenced with the staleness-veto
    resurrection (owed 42), never bolted on here. Module-level with a
    duck-typed `bot` (the SimpleNamespace fixture convention in
    test_v8_batch.py drives _augment_view_with_kraken without a real
    engine). Deterministic under replay: venue bar times and the
    injected `now` only; telemetry must never raise."""
    try:
        bar_ts = float((candles[-1] or {}).get("time", 0.0) or 0.0)
    except (TypeError, ValueError, IndexError, AttributeError):
        return                     # malformed/list-shaped rows: sanitize
                                   # owns row shape, not this check
    if bar_ts <= 0.0:
        return                     # no timestamp -> nothing to measure
    latched = getattr(bot, "_stale_bar_latched", None)
    if latched is None:
        latched = bot._stale_bar_latched = set()
    if now - bar_ts > _STALE_BAR_SEC:
        if asset not in latched:
            latched.add(asset)
            log.warning(
                f"{Code.FW_STALE_BARS.value}: {asset} last committed "
                f"bar is {now - bar_ts:.0f}s old (> {_STALE_BAR_SEC:.0f}s)"
                f" - venue bars entering the view are stale; vol/"
                f"features/sizing read old data (detection only)")
    else:
        latched.discard(asset)


def _context_avail_check(bot, avail: dict) -> None:
    """DF-020/DF-021 (owed 41b): latched one-log-per-episode transition
    when feature rows are being built while a context source is dark or
    frozen. Same latched discipline as FW-080/_bar_age_check above and
    41a's DF-010/DF-011; module-level with a duck-typed `bot` for the
    same fixture reasons. Telemetry only - the per-row truth is the
    avail_* columns; this log exists so the OPERATOR sees the episode
    without diffing the corpus. Never raises."""
    try:
        down = frozenset(k for k, ok in
                         (("web", avail.get("web")),
                          ("equity", avail.get("equity")),
                          ("options", avail.get("options")))
                         if not ok) | (
            frozenset(("frozen",)) if avail.get("frozen") else frozenset())
    except AttributeError:
        return
    prev = getattr(bot, "_ctx_avail_down", None)
    if prev is None:
        prev = bot._ctx_avail_down = frozenset()
    if down == prev:
        return
    bot._ctx_avail_down = down
    if down:
        log.warning(
            f"{Code.DF_CONTEXT_DEGRADED.value}: building feature rows "
            f"with degraded context ({', '.join(sorted(down))}) - the "
            f"affected features read neutral; rows carry avail_* flags")
    else:
        log.info(f"{Code.DF_CONTEXT_RECOVERED.value}: all context "
                 f"sources live again - degradation episode over")


def _book_imbalance(book: dict) -> float:
    """log(bid depth / ask depth) over the top 10 levels, clipped like the
    imbalance feature; 0.0 when a side is missing."""
    try:
        bids = sum(float(sz) for _, sz in book.get("bids", [])[:10])
        asks = sum(float(sz) for _, sz in book.get("asks", [])[:10])
        if bids > 0 and asks > 0:
            return float(np.clip(np.log(bids / asks), -2, 2))
    except (TypeError, ValueError):
        pass
    return 0.0


def _composite_imbalance(venue_books: list) -> Optional[float]:
    """Mean of PER-VENUE log-imbalances for the manip divergence term.
    NEVER the price-merged combined book: OKX (perp, contract-unit sizes)
    and Binance.US (spot, coin-unit sizes) don't share size units, so
    _book_imbalance over their concatenation is a garbage ratio - it
    square-waved a false cross-venue divergence (and a false 'spoofy'
    manip flag) on BTC/ETH (SD-003). A log-ratio is unit-consistent only
    WITHIN one book, so average per-venue log-imbalances instead; same
    log-space as kraken_imb so manip_suspect_score compares like with
    like. Returns None when no coherent external book exists this cycle -
    the caller then makes divergence 0 (unmeasurable, not 'manipulated')."""
    vals = [_book_imbalance(b) for b in (venue_books or [])
            if b and b.get("bids") and b.get("asks")]
    return float(sum(vals) / len(vals)) if vals else None


def _book_mid(book: dict) -> float:
    """Top-of-book mid, 0.0 when either side is missing/malformed."""
    try:
        bid = float(book["bids"][0][0])
        ask = float(book["asks"][0][0])
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return 0.0


class LiquidityBot:
    def __init__(self, config: dict, okx=None, binanceus=None, kraken=None,
                webdata=None, moomoo=None, sentiment_scanner=None,
                resume: bool = True):
        self.config = config
        sys_cfg = config.get("system", {})
        self.dry_run = bool(sys_cfg.get("dry_run", True))
        # C2 (2026-08-01 audit): the SESSION's configured mode, captured
        # once and never written again. `self.dry_run` above is MUTABLE -
        # runner.force_dry flips it LIVE->DRY mid-session (invariant #2) -
        # so it cannot answer "were this book's positions born against a
        # real venue?". Everything that must key on provenance rather than
        # on the current simulation flag reads THIS field: the simulated-
        # fill guard below, and (cross-file) the sim_* injection gate.
        self._config_dry_run = bool(sys_cfg.get("dry_run", True))
        # one-shot latch so the CRITICAL fault/alert fires once, not per
        # fabricated fill (see _simulated_fill_on_live_book)
        self._sim_fill_on_live_latched = False
        # operator alerting + config invariants FIRST: a live bot on a
        # broken config must never get as far as touching the exchange
        self.alerts = AlertSink(config.get("alerts", {}))
        enforce_config(config, self.alerts)
        # session fingerprint (Assurance Build): the audit chain's first
        # record pins exactly which configuration this session ran under —
        # the config-side twin of the model registry's artifact hashes.
        try:
            cfg_sha = hashlib.sha256(json.dumps(
                config, sort_keys=True, default=str).encode()).hexdigest()
            get_audit().log(
                "startup", Code.CG_SESSION_START,
                "session start: config fingerprint",
                {"config_sha256": cfg_sha[:16], "dry_run": self.dry_run,
                 "maker_fee_bps": config.get("pretrade", {})
                 .get("maker_fee_bps"),
                 "taker_fee_bps": config.get("pretrade", {})
                 .get("taker_fee_bps"),
                 "starting_capital_usd": config
                 .get("capital_management", {})
                 .get("starting_capital_usd")})
        except Exception:
            log.exception("config fingerprint failed (non-fatal)")
        self.poll_sec = float(sys_cfg.get("polling_interval_sec", 5))
        self.slow_every = int(sys_cfg.get("slow_cycle_every_n", 6))
        self.macro_refit_sec = float(sys_cfg.get("macro_refit_minutes", 60)) * 60.0
        self.snapshot_sec = float(sys_cfg.get("snapshot_interval_sec", 30))

        # --- feeds (injectable for tests) ---
        self.okx = okx or OKXFeed(config["exchanges"]["okx"])
        # push-based Binance.US depth stream. Symbols default to the REST
        # feed's own list so the two never drift (a stream covering pairs the
        # REST feed doesn't fetch, or vice versa, buys nothing). Ships
        # DISABLED (config websockets.enabled=false): start() is then a no-op,
        # get_order_book returns None, and the engine runs exactly on REST.
        ws_cfg = dict(config.get("websockets", {}))
        ws_cfg.setdefault("binanceus_symbols",
                          config["exchanges"]["binanceus"].get("symbols", []))
        self.ws_manager = WebSocketFeedManager(ws_cfg)
        self.binanceus = binanceus or BinanceUSFeed(
            config["exchanges"]["binanceus"], ws=self.ws_manager)
        self.ws_manager.start()
        # optional read-only CCXT data adapter: config declared it but it was
        # never wired into the market view. Data-only by construction
        # (CCXT-001 refuses credentials); a broken optional feed must never
        # stop the bot, so construction failure degrades to "absent", loudly.
        self.ccxt_feed = None
        ccxt_cfg = config["exchanges"].get("ccxt") or {}
        if ccxt_cfg.get("enabled"):
            try:
                from data.ccxt_feed import CCXTFeed
                self.ccxt_feed = CCXTFeed(ccxt_cfg)
                log.info("ccxt data feed wired: %s %s",
                         self.ccxt_feed.exchange_id, self.ccxt_feed.symbols)
            except Exception:
                log.exception("ccxt feed enabled but failed to construct - "
                              "continuing without it")
        self.kraken = kraken or KrakenFeed(config["exchanges"]["kraken"])
        # recording wraps feeds in FeedRecorder instances that append to ONE
        # shared sink file - keep those calls serial (see _fetch_market_payloads)
        self._serial_feeds = bool(config.get("system", {}).get("record_feeds"))
        self.webdata = webdata or WebDataFeed(config.get("webdata", {}))
        wcfg = config.get("webdata", {})
        self.fg_fear_max = float(wcfg.get("fear_greed_fear_max", 15))
        self.fg_euphoria_min = float(wcfg.get("fear_greed_euphoria_min", 85))
        self.moomoo = moomoo or MoomooFeed(config.get("moomoo", {}))
        # Compounder Phase B (spec §3): telemetry-only cycle/macro context
        # engine. NOT a decision-path input this phase - the ONLY other
        # touch point in this file is the one poll line in slow_cycle's
        # sentiment/web/risk poll cluster below; status/audit/gc_pusher are
        # the sole consumers (data/context_engine.py module docstring).
        self.context = ContextFeed(config.get("context", {}))

        # --- v1 core ---
        self.liquidity_model = LiquidityModel(config)
        # base assets with a real external (OKX/Binance.US) cross-venue feed —
        # the ONLY assets that get an external imbalance from build_view. Used
        # to decide whether to surface the Kraken exec-book imbalance (v9 flow
        # unlock): a genuinely Kraken-only listing (SUI/ARB/MINA/FLOW) gets it;
        # a major (ETH/BTC) never does, even on a cycle its external feed drops.
        self._external_bases = set()
        for _ex in ("okx", "binanceus"):
            for _s in (config.get("exchanges", {}).get(_ex, {})
                       .get("symbols", []) or []):
                _b = extract_base_asset(_s)
                if _b:
                    self._external_bases.add(_b)
        engine_kind = (config.get("strategies") or {}).get("engine",
                                                          "five_gate")
        if engine_kind == "informed_flow":
            from strategies.informed_flow import InformedFlowEngine
            self.gates = InformedFlowEngine(config.get("informed_flow", {}))
        else:
            self.gates = SignalGateEngine(config)
        log.info(f"signal engine: {engine_kind}")
        self.tactics = ExecutionPlanner(config.get("execution_tactics", {}))
        self.ladder = GridLadderEngine(config.get("grid_ladder", {}))
        self.capital = CapitalManager(config.get("capital_management", {}))
        self.tiers_base = config.get("profit_taking", {})
        self._tier_engines = {}
        self.last_signals: dict = {}     # asset -> last evaluation snapshot (UI)
        exec_cfg = config.get("execution", {})
        self.algo = ExecutionScheduler(exec_cfg.get("algos", {}))
        self.router = SmartOrderRouter(exec_cfg.get("routing", {}))
        self._algo_meta: dict = {}       # parent_id -> submit template
        start_cap = float(config["capital_management"]
                          .get("starting_capital_usd", 0))
        if start_cap <= 0:
            if not self.dry_run:
                # config_guard already raised; this is belt-and-suspenders
                raise ValueError("starting_capital_usd must be > 0 live")
            start_cap = 10_000.0
            log.info("dry run: starting_capital_usd unset -> $10,000 paper")
        self.state = PortfolioState(starting_capital=start_cap)

        # --- v2 engines ---
        self.macro = MacroRegimeEngine(config.get("regime", {}))
        self.vol = VolRegimeEngine(config.get("vol_regime", {}))
        self.liq = LiquidityRegimeEngine(config.get("liquidity_regime", {}))
        _lr = config.get("liquidity_regime", {})
        self._wl_p95 = float(_lr.get("whiplash_healthy_p95", 1.27))
        self._wl_thr = float(_lr.get("imbalance_whiplash_threshold", 1.45))
        self.corr = CorrelationEngine(config.get("correlation", {}))
        self.fv = FairValueEngine(config.get("fair_value", {}))
        self.quoter = AvellanedaStoikovQuoter(config.get("market_maker", {}))
        self.inventory = InventoryManager(config.get("inventory", {}))
        self.pretrade = PreTradeGate(config.get("pretrade", {}))
        # ADV haircut/floor for the impact model (lifted literals): 24h venue
        # volume is haircutted to a Kraken-share proxy and floored, feeding
        # the participation clamp (PT-030). Same defaults as the old
        # constants (0.10, $1M).
        _pt_cfg = config.get("pretrade", {}) or {}
        self._adv_haircut = min(max(
            float(_pt_cfg.get("adv_haircut", 0.10)), 0.01), 1.0)
        self._adv_floor_usd = max(
            float(_pt_cfg.get("adv_floor_usd", 1e6)), 1.0)
        self.firewall = RiskFirewall(config.get("risk_firewall", {}),
                                     self.alerts)
        self.watchdog = Watchdog(config.get("watchdog", {}), self.alerts)
        # cache once - slow_cycle checks this every entry attempt
        self.max_equity_drift_pct = float(
            config.get("watchdog", {}).get("max_equity_drift_pct", 2.0))
        # venue precision metadata: wrong price decimals = guaranteed
        # AddOrder rejection (BTC/USD allows 1, not 2). Static fallback
        # keeps tests and offline runs working.
        pair_syms = config["exchanges"]["kraken"].get("trading_pairs", [])
        pairs = [self.kraken.kraken_pair(sym) for sym in pair_syms]
        try:
            pair_meta = self.kraken.get_pair_meta(pairs)
        except Exception:
            pair_meta = {}
        if not pair_meta:
            # verified Kraken AssetPairs metadata; mirrors the fallback in
            # data/kraken_feed.get_pair_meta so offline/dry/test runs format
            # prices to each pair's real precision (MINA=5, ARB/FLOW/SUI=4,
            # not the generic 2 that would be rejected)
            fallback = {"ETHUSD": {"price_decimals": 2, "lot_decimals": 8,
                                   "ordermin": 0.002},
                        "XBTUSD": {"price_decimals": 1, "lot_decimals": 8,
                                   "ordermin": 0.00005},
                        "BTCUSD": {"price_decimals": 1, "lot_decimals": 8,
                                   "ordermin": 0.00005},
                        "SUIUSD": {"price_decimals": 4, "lot_decimals": 5,
                                   "ordermin": 5.0},
                        "ARBUSD": {"price_decimals": 4, "lot_decimals": 5,
                                   "ordermin": 60.0},
                        "MINAUSD": {"price_decimals": 5, "lot_decimals": 8,
                                    "ordermin": 120.0},
                        "FLOWUSD": {"price_decimals": 4, "lot_decimals": 8,
                                    "ordermin": 200.0}}
            pair_meta = {p: fallback.get(p, {"price_decimals": 2,
                                             "lot_decimals": 8,
                                             "ordermin": 0.0})
                         for p in pairs}
        # fee-tier reconciliation (OM-080) must catch the pretrade EV gate's
        # cost stack underestimating fees, not just OrderManager's own
        # booking bps - both config blocks are in scope here, _pt_cfg reused
        # from above.
        self.orders = OrderManager(self.kraken, config.get("order_manager", {}),
                                dry_run=self.dry_run,
                                firewall=self.firewall, pair_meta=pair_meta,
                                pretrade_fee_bps=(
                                    float(_pt_cfg.get("maker_fee_bps", 25.0)),
                                    float(_pt_cfg.get("taker_fee_bps", 40.0))))
        self.lev_gov = LeverageGovernor(config.get("leverage", {}))
        self.risk_protocols = RiskProtocolStack(
            config.get("risk_protocols", {}))
        self.sizer = PositionSizer(config.get("position_sizer", {}),
                                config.get("profit_taking", {}),
                                config.get("risk", {}),
                                pretrade_cfg=config.get("pretrade", {}),
                                capital_cfg=config.get(
                                    "capital_management", {}),
                                protocols=self.risk_protocols)
        # Compounder Phase C: long-horizon accumulation book engine
        # integration (task C4; risk/long_book.py's EvidenceLadder/
        # LongBookEngine are C2/C3). Parameterized instances of the SAME
        # tier/sizer machinery the 5m book uses above - never a duplicate
        # stack: the long ProfitTierEngine reads long_book.profit_taking;
        # the long PositionSizer reads long_book's own position_sizer
        # sub-block (absent today -> PositionSizer's shipped defaults)
        # plus the SHARED risk/pretrade/capital_management blocks and the
        # SAME risk_protocols INSTANCE (combined envelope Global
        # Constraint: the long book never gets its own risk stack).
        # EvidenceLadder is ONE shared instance for the whole book - its
        # ceiling gates total book exposure across every configured asset,
        # not per-asset (risk/long_book.py's own docstring). LongBookEngine
        # is a pure namespace ("never itself constructed" per its own
        # docstring) - only its decide_add staticmethod is ever called
        # from _long_book_cycle, never instantiated.
        lb_cfg = config.get("long_book", {}) or {}
        self.long_tier_engine = ProfitTierEngine(
            lb_cfg.get("profit_taking", {}))
        self.long_sizer = PositionSizer(
            lb_cfg.get("position_sizer", {}),
            lb_cfg.get("profit_taking", {}),
            config.get("risk", {}),
            pretrade_cfg=config.get("pretrade", {}),
            capital_cfg=config.get("capital_management", {}),
            protocols=self.risk_protocols)
        self.long_ladder = EvidenceLadder(lb_cfg.get("ladder", {}))
        # C4 review, Critical #1(c): stamped on FILL (main._handle_fill),
        # never at submit - a zero-fill expiry/cancel must not burn the
        # ~24h-scale spacing window. Process-scoped, persisted (core/
        # persistence.py's _restore_long_book_section).
        self._long_last_add_ts: dict = {}   # asset -> ts of last successful FILL
        self._long_adds_placed = 0          # cumulative successful submits (telemetry)
        self._long_context_aligned_last: Optional[bool] = None
        self._long_last_deny: str = ""      # most recent deny detail (telemetry)
        # C4 review, Important #3(a): per-asset backoff after a post-plan
        # sizing/submission failure (sizer veto, sub-ordermin, firewall
        # reject, zero notional) - NOT persisted (process-local, like the
        # conviction cadence governor's own windows): a restart costs at
        # most one extra retry attempt, never a false/stuck backoff.
        self._long_retry_backoff_until: dict = {}   # asset -> ts backoff clears
        # task C5 item 3(a): the book's own realized+unrealized equity
        # curve peak/drawdown (_long_book_dd_frac) - fed by every long-
        # book close (_finalize_position) and read every _long_book_cycle
        # pass. Persisted (core/persistence.py's _restore_long_book_
        # section) so a restart never resets the peak downward.
        self._long_book_realized_pnl_total = 0.0
        self._long_book_peak_value = 0.0
        # edge-detector for the downgrade breach (EvidenceLadder.
        # maybe_downgrade has no internal edge-detection by design - the
        # caller must debounce to one call per breach episode).
        self._long_book_dd_breach_active = False
        # task C5 item 3(b): adverse-context-transition-survived episode
        # tracker (a risk-off episode = stress > stress_max_for_add
        # SUSTAINED for ladder.cfg.adverse_min_hours). None = not
        # currently in an episode.
        self._long_book_adverse_episode_start: Optional[float] = None
        self._long_book_adverse_held_exposure = True
        self._long_book_adverse_dd_ok = True
        # task C5 item 6: per-asset deny-debounce state for the "chatty"
        # DenyReason kinds (event_window/context_unknown/context_
        # misaligned/crisis) and enforce-mode conviction denials - NOT
        # persisted (process-local, like _long_retry_backoff_until above:
        # a restart costs at most one extra audit row, never a stuck
        # suppression).
        self._long_book_deny_state: dict = {}
        self.meta = MetaModelService(config.get("ml", {}))
        self.history = HistoryStore(
            config.get("ml", {})
            .get("history_path", "outputs/signal_history.csv"),
            # era-deadlock fix (2026-07-31): the store tags new
            # triple_barrier rows with the horizon that produced them
            max_bars=int(config.get("ml", {}).get("label_max_bars", 96)))
        # multi-horizon shadow evidence (separate fixed-schema file so it can
        # never rotate the training data); only wired when enabled in config
        mh_cfg = config.get("ml", {}).get("multi_horizon", {})
        self.horizon_shadow = HorizonShadowStore(
            mh_cfg.get("shadow_path", "outputs/horizon_shadow.csv")) \
            if mh_cfg.get("enabled", False) else None
        self.monitor = ModelMonitor(config.get("ml", {}).get("monitor", {}))
        self.postmortem = PostmortemEngine(config.get("ml", {}).get("postmortem", {}))
        # complete rolling P&L ledger (win-rate/PF/expectancy/streak, per asset):
        # the postmortem engine only records underperformers, so it can't grade
        # the full book. Telemetry only — feeds the trading dashboard, no
        # decision reads it.
        self.perf = PerformanceTracker(config.get("performance", {}))
        # per-asset consecutive-loss circuit breaker: pulls a misbehaving
        # symbol off the sheet (new entries only — exits never consult it),
        # auto-resets after cooldown. Deliberately separate from the
        # telemetry-only perf ledger: this one IS a decision input.
        self.breaker = CircuitBreaker(config.get("circuit_breaker", {}))
        # empirical adverse-selection meter: measures whether our entry fills
        # were picked off (the ground truth the manip anti-scalp gate pre-empts)
        self.markout = MarkoutTracker(config.get("markout", {}))
        # per-gate predictive power learned from labeled candidates; the
        # labeler feeds it as triple-barrier outcomes land (engine-agnostic
        # over gates_passed dicts, so informed-flow gates learn too)
        # The realized ledger is keyed by GEOMETRY ERA, so GateStats is told
        # which era it is trading under at construction. Same vocabulary the
        # label corpus uses (ml.history.triple_barrier_era), so a gate's
        # realized evidence and the rows it trained on agree on what "era"
        # means. A geometry change starts a fresh realized ledger and resets
        # the sample clock — correct, not a regression: after the barriers
        # move you genuinely have no realized evidence about the new system,
        # and the old samples stay readable but stop voting.
        from ml.history import triple_barrier_era as _tbe
        self.gate_stats = GateStats({
            **(config.get("signal_gates", {}).get("learned_weights", {})),
            "era": _tbe(int(config.get("ml", {}).get("label_max_bars", 96))),
        })
        # exit-policy labeler reads the live stop + tier + give-back geometry
        # from the SAME config the engine trades, so candidate labels answer
        # "would this signal net positive under OUR exit policy" (default mode)
        self.candidates = CandidateLabeler(self.history, config.get("ml", {}),
                                           on_label=self.gate_stats.note_label,
                                           shadow_store=self.horizon_shadow,
                                           exit_policy=ExitPolicy.from_config(
                                               config))
        # State-Change Sampler (ml/event_sampler.py): event-based candidate
        # sampling — CUSUM price trigger OR-fused with our own regime/liq
        # label flips. Gates ONLY candidate registration (the learning
        # corpus), never entries/exploration/gates/exits.
        self.scs = StateChangeSampler(config.get("ml", {}).get("sampling", {}))
        self._scs_pending: dict = {}        # asset -> teachable event latched
        # geometry-alignment T5 (spec D1): model-lane bracket exits - "the
        # traded bet is the labeled bet". Default FALSE when the key is
        # absent entirely (T5 review IMPORTANT-3 fix, 2026-07-28): must
        # match core/config_guard.py's own bracket_exits.enabled default
        # (False) - the two parses had drifted (this one defaulted True),
        # so a KEYLESS config traded the bracket with the coherence FATAL
        # (enabled + non-triple_barrier label_mode, right below) never
        # even evaluated. config.json ships bracket_exits.enabled=true
        # EXPLICITLY, so shipped behavior is unchanged; only a config
        # that OMITS the key now falls back to legacy tier exits instead
        # of silently opting into the bracket. The four knobs mirror
        # ml/history.py CandidateLabeler's own parse (label_pt_vol_mult/
        # label_sl_vol_mult/label_pt_cost_mult/label_max_bars) exactly,
        # so the live bracket-exit engine and the candidate labeler read
        # the SAME config the SAME way - structural alignment, not by
        # convention.
        self._bracket_exits_enabled = bool(
            config.get("bracket_exits", {}).get("enabled", False))
        _ml_cfg_t5 = config.get("ml", {}) or {}
        self._label_pt_vol_mult = float(_ml_cfg_t5.get("label_pt_vol_mult", 8.0))
        self._label_sl_vol_mult = float(_ml_cfg_t5.get("label_sl_vol_mult", 6.0))
        self._label_pt_cost_mult = float(_ml_cfg_t5.get("label_pt_cost_mult", 0.0))
        self._label_max_bars = int(_ml_cfg_t5.get("label_max_bars", 96))
        # THALES lazy-bot insecurity model (docs/THALES.md): detector bank
        # over public books/candles; shadow by default (telemetry only),
        # bounded confidence shading only when influence=advise
        from strategies.thales import ThalesEngine
        self.thales = ThalesEngine(config.get("thales", {}))
        # TH-021 evidence-concentration shade (docs/THALES.md §Evidence
        # concentration): trims a DIFFUSE-and-marginal signal's confidence
        # (the averaging trap). Disabled by default — a config-gated promotion,
        # never a silent behavior change.
        self._conc_shade_cfg = (config.get("thales", {})
                                .get("evidence_concentration", {})) or {}
        # Smart Money Concepts structural features (docs/SMC.md): MTF
        # trend alignment, premium/discount zone, liquidity-pocket pull,
        # FVG pull/confluence, volume-profile POC/VA - additional signal
        # inputs to the meta-model's feature vector, never a gate/veto
        from strategies.smc import SMCEngine
        self.smc = SMCEngine(config.get("smc", {}))
        # active-learning exploration: with no proven edge the sizer's net-Kelly
        # bar (p_win > ~0.60) vetoes every confirmed signal, so the bot never
        # trades and never gathers live labels to improve. In DRY RUN ONLY, take
        # a fraction of confirmed signals as small paper trades to bootstrap
        # real-fill training data; auto-disables once enough live rows accrue.
        # HARD-GATED on dry_run (see _exploration_active) - never live.
        _ex = config.get("ml", {}).get("exploration", {}) or {}
        self.explore_enabled = bool(_ex.get("enabled", False))
        self.explore_epsilon = min(max(float(_ex.get("epsilon", 0.25)), 0.0), 1.0)
        self.explore_until_rows = int(_ex.get("until_live_rows", 120))
        self.explore_p_win = min(max(float(_ex.get("p_win", 0.62)), 0.0), 0.95)
        self.explore_size_scale = min(max(float(_ex.get("size_scale", 0.25)),
                                          0.01), 1.0)
        # DRY-RUN exploration bypasses the pre-trade PROFIT-EV gate (edge/cost,
        # EV floor) so net-thin signals still get TAKEN and yield real-fill
        # labels — otherwise the cost stack vetoes every exploration entry and
        # the model only ever learns from shadow candidates, never fills.
        self.explore_bypass_ev = bool(_ex.get("bypass_pretrade_ev", True))
        # CONVICTION-SCALED aggressive exploration: normal exploration always
        # min-sizes, so the model only ever sees fill outcomes on timid marginal
        # trades. Occasionally, when the model is reasonably confident AND the
        # book is clean, take a FULL-conviction ticket instead — the model then
        # learns from confident calls at real size. Bounded by every risk-stack
        # veto + the manip gate + kelly_cap; dry-run only (exploration is).
        _ag = _ex.get("aggressive", {}) or {}
        self._explore_aggr_enabled = bool(_ag.get("enabled", True))
        self._explore_aggr_frac = min(max(float(_ag.get("frac", 0.15)),
                                          0.0), 1.0)
        self._explore_aggr_min_p = float(_ag.get("min_conviction", 0.55))
        self._explore_aggr_max_manip = float(_ag.get("max_manip", 0.6))
        self._explore_aggr_p = min(max(float(_ag.get("sizing_p", 0.72)),
                                       0.0), 0.95)
        # variety: stop exploration-bumping an asset once it holds this
        # share of the labeled history (the active pair otherwise hogs
        # every learning slot and quiet pairs never accrue fill labels)
        self.explore_max_asset_share = min(max(
            float(_ex.get("max_asset_share", 0.5)), 0.0), 1.0)
        self.explore_share_min_rows = int(_ex.get("share_min_rows", 10))
        # P3 corpus-aware probe throttle (2026-07-23 P&L diagnosis): probes
        # were 69% of live closes and -$22.87 of -$31.68 measured net PnL -
        # the corpus (3.3k rows / 214 live) has grown past the point
        # marginal probe value justifies the base admission rate. TWO
        # throttles, both toward a floor/cap rather than to zero (the
        # learner keeps a trickle): (a) a rolling SHARE CAP over the last
        # probe_share_window entry ADMISSIONS (probes+conviction), see
        # _probe_share_would_deny; (b) CORPUS DECAY folded into
        # _exploration_active's own epsilon roll, see
        # probe_corpus_decay_factor. Denials emit Code.SZ_PROBE_THROTTLED
        # (SZ-047). Conviction entries are never throttled by this lever -
        # the decision method takes no sizing argument (pinned in
        # tests/test_probe_throttle.py).
        self._probe_max_share = min(max(
            float(_ex.get("max_probe_share", 0.35)), 0.0), 1.0)
        self._probe_share_window = max(
            int(_ex.get("probe_share_window", 40)), 1)
        _dfl = _ex.get("drought_floor", {}) or {}
        # F0b (grill C2): drought-scoped floor - see _drought_floor_admit
        self._drought_floor_enabled = bool(_dfl.get("enabled", True))
        self._drought_min_sec = max(
            float(_dfl.get("drought_hours", 8.0)), 0.0) * 3600.0
        self._floor_spacing_sec = max(
            float(_dfl.get("min_spacing_hours", 2.0)), 0.0) * 3600.0
        # spacing clock for floor admissions - RESTART STATE, persisted
        # beside probe_admissions (core/persistence.py): unpersisted, the
        # deploy-restart cadence would reset the trickle bound every
        # deploy and allow an immediate re-fire.
        self._last_floor_admit_ts: Optional[float] = None
        _cd = _ex.get("corpus_decay", {}) or {}
        self._corpus_target_live = int(_cd.get("corpus_target_live", 300))
        self._corpus_floor_frac = min(max(
            float(_cd.get("floor_frac", 0.25)), 0.0), 1.0)
        # Task 4 (#103) regime-coverage hold: while the CURRENT macro
        # regime has fewer than this many live-labeled rows, the decay
        # term above is held at 1.0 for that regime's signals (see
        # _regime_under_coverage_floor / _exploration_active). 0 disables
        # the term entirely (byte-identical P3 behavior).
        self._regime_floor_live = int(_cd.get("regime_floor_live", 60))
        # rolling window of the last probe_share_window entry ADMISSIONS
        # (True=probe, False=conviction). RESTART STATE: persisted (see
        # core/persistence.py snapshot/restore "probe_admissions") rather
        # than reset-on-restart. Reasoning: unlike risk/circuit_breaker.py's
        # trip state (persisted so "a trip can't be laundered by a
        # reboot"), a reset here can only ever ADMIT more probes than a
        # persisted window would have (the share-cap denominator is the
        # FIXED configured window size, never the deque's current fill -
        # see _probe_share_would_deny), never fewer - so it is a safe
        # direction of error in isolation. But this codebase's own
        # documented deploy pattern (core/persistence.py: "the auto-updater
        # restarts the bot on every deploy") means an UNPERSISTED window
        # would reset on every single deploy, not just rare crashes -
        # making a 40-admission cap nearly inert in production. Persisting
        # it (cheap: a plain bool list, same shape as _stop_hit) keeps the
        # cap meaningful across the routine restart cadence this bot
        # actually runs under.
        self._probe_admissions: Deque[bool] = deque(
            maxlen=self._probe_share_window)
        # SPB-R probe-admission budget (docs/superpowers/specs/2026-07-30-
        # probe-budget-spbr-design.md), LANDED DARK: mode defaults to
        # "share_cap" (the shipped SZ-047 deque path above, byte-identical
        # including _explore_rng draw counts - test-pinned in
        # tests/test_probe_budget.py); "budget" replaces the share-cap
        # branch with refill -> scarcity price -> probabilistic
        # affordability (see _budget_admission). The legacy deque is fed
        # in BOTH modes (stateful rollback: one config key + restart
        # resumes a WARM window).
        _adm = _ex.get("admission", {}) or {}
        self._probe_admission_mode = str(_adm.get("mode", "share_cap"))
        _bg = _adm.get("budget", {}) or {}
        self._budget_tokens_per_day = float(_bg.get("tokens_per_day", 15))
        self._budget_burst_hours = float(_bg.get("burst_hours", 8.0))
        self._budget_scarcity_pricing = bool(
            _bg.get("scarcity_pricing", True))
        _bsf = _bg.get("scarcity_floor")
        self._budget_scarcity_floor: Optional[float] = \
            float(_bsf) if _bsf is not None else None
        self._budget_refund_unfilled = bool(
            _bg.get("refund_unfilled_entry", True))
        _bgv = _bg.get("governor", {}) or {}
        self._budget_tuition_frac_max = float(
            _bgv.get("tuition_daily_frac_max", 0.001))
        self._budget_outlier_clip_div = float(
            _bgv.get("outlier_clip_div", 3))
        # bucket state - RESTART STATE: {tokens, tuition} persisted beside
        # probe_admissions (core/persistence.py "probe_budget" section);
        # last_refill_ts deliberately NOT persisted - it re-seeds to the
        # first engine `now` after restart so downtime never accrues
        # tokens (degraded toward FEWER probes, the safe direction).
        self._budget_tokens = 0.0
        self._budget_last_refill_ts: Optional[float] = None
        # trailing-24h clipped probe tuition: (close_ts, clipped_loss_usd)
        # per probe-tagged close, pruned at read, never latched (§1.5)
        self._budget_tuition: Deque[tuple] = deque()
        # decision->placement cost stash (§1.4): the decision stashes,
        # the placement hook (_record_probe_admission) pops and deducts -
        # a probe vetoed in between never reaches the hook, costs zero.
        self._pending_probe_cost: dict = {}
        self._pending_probe_asset: Optional[str] = None
        self._budget_governor_factor = 1.0
        # SZ-049 transition bracket state (engaged span + denied count)
        self._budget_exhausted_since: Optional[float] = None
        self._budget_denied_arrivals = 0
        # trailing-window telemetry (§8) - report-only, process-local
        # (a restart costs at most one window of counters; the durable
        # SPB-R state is only {tokens, tuition}, spec §5)
        self._budget_admit_events: Deque[tuple] = deque()    # (ts, cost)
        self._budget_refund_events: Deque[float] = deque()
        self._budget_denied_events: Deque[float] = deque()
        self._budget_rollfail_events: Deque[float] = deque()
        self._budget_label_events_7d: Deque[float] = deque()
        # DEDICATED rng stream (§1.3, C2's RNG discipline): _explore_rng's
        # draw count is untouched in BOTH modes. str-seeding is
        # deterministic and PYTHONHASHSEED-independent.
        self._budget_rng = random.Random(  # nosec B311 - admission sampling, not crypto
            f"{int(config.get('system', {}).get('seed', 42))}:probe-budget")
        # Compounder Phase A: deterministic conviction formula
        # (risk/conviction.py). report mode (default) = dispositions
        # logged, entry behavior byte-identical; the enforce flip is a
        # conscious operator decision (see the module docstring).
        self.conviction = ConvictionFormula(
            config.get("conviction", {}) or {})
        self._entry_rotation = 0            # round-robin offset, see _entry_assets
        self._explore_rng = random.Random(int(  # nosec B311 - epsilon sampling, not crypto
            config.get("system", {}).get("seed", 42)))
        self._stop_hit: dict = {}           # position_id -> bool
        self._thales_fired: dict = {}       # asset -> fired detectors (V2)
        self._pos_thales: dict = {}         # position_id -> fired at entry
        # Gate attribution for the REALIZED-outcome loop (2026-08-02).
        # gates_passed already travels to candidates.register(), which feeds
        # GateStats.note_label — a triple-barrier PRICE label that knows
        # nothing about the round trip. On this feed the barrier label rate
        # is 0.3991 against a realized win rate of 0.038, so a gate could be
        # credited for a "win" on a trade that lost money and the ledger
        # would keep confirming it. These two maps carry the same dict down
        # the TRADE path so a close can attribute actual P&L back to the
        # gates that authorised it. Exactly the _thales_fired/_pos_thales
        # shape, which already solves this problem for detectors.
        self._sig_gates: dict = {}          # asset -> gates_passed at signal
        self._pos_gates: dict = {}          # position_id -> gates at entry
        self._last_imb: dict = {}           # asset -> last log-imbalance
        self._regime_since: dict = {}       # asset -> (label, changed_at_ts)
        self._manip_scores: dict = {}       # asset -> latest suspicion [0,1]
        # cumulative count of ISOLATED cycle-stage failures that were caught so
        # they could not starve the per-position stop loop (invariant #5):
        # per-position exit/stop eval, every pre-stop fast-cycle stage, the
        # hourly/slow refit, and fill application. Surfaced in status; a
        # non-zero, climbing value means something is wedging an escape path and
        # needs an operator's eye — the logs name the exact stage/reason code.
        self._exit_eval_failures = 0
        self._rows_at_last_train = self.history.row_count()
        # Whether the FIRST-champion train has been attempted this process.
        # In-memory by design: a cold container (bundle-restored rows, no
        # state.json) defaults _rows_at_last_train to the full count, which
        # would make the min-NEW-rows gate block the very first train forever.
        # This lets the first cold-start attempt bypass that gate exactly once
        # per process; if the challenger fails to deploy, normal new-row
        # throttling resumes (no retrain storm).
        self._retrain_attempted = False
        # retrain is wrapped in a fail-safe except (below): if walk-forward /
        # calibration / deploy throws EVERY cycle the bot silently keeps the
        # stale champion forever ("the ML worked until it didn't"). Count the
        # failures so a rising number is visible on the incidents dashboard.
        self._retrain_failures = 0
        # per-family calibration gap from the last retrain's evaluate_and_
        # select results - report-only, rebuilt each retrain, never persisted
        # (surfaced into status.ml.retrain_calib_gap for observability)
        self._last_retrain_calib_gap: dict = {}
        self.xscan = sentiment_scanner or SentimentScanner(
            config.get("sentiment", {}))
        self.narrative = NarrativeFilter(config.get("sentiment", {}).get("filter", {}))

        # asset universe: base asset -> kraken symbol
        self.symbol_map = {}
        for sym in config["exchanges"]["kraken"].get("trading_pairs", []):
            self.symbol_map[sym.split("/")[0]] = sym
        # asset -> Kraken REST pair, precomputed: kraken_pair is pure and the
        # universe is fixed, so rebuilding this every fast_cycle was wasted
        # work + allocation on the hot path.
        self._pair_of = {a: self.kraken.kraken_pair(s)
                         for a, s in self.symbol_map.items()}
        self._pair_list = list(self._pair_of.values())
        self.hedger = HedgeEngine(config.get("hedging", {}), self.symbol_map)

        # Kraken v2 public book stream (execution venue, READ-ONLY public
        # data): when live it replaces the rate-limited per-pair REST Depth
        # loop in fast_cycle with a push feed. Cache is keyed by the Kraken
        # REST pair, so fast_cycle's get_order_book(pair) reads it directly.
        # Fail-safe: disabled/stale/down -> None -> REST, no behavior change.
        # Gated on the REAL Kraken feed (kraken is None): when a feed is
        # injected - tests (MockKraken), replay/backtest - we must NOT open a
        # live socket that would override the injected book source and break
        # hermeticity/determinism. Production (kraken is None) gets the stream.
        self.kraken_ws = None
        _kws = config.get("websockets", {}) or {}
        if kraken is None and _kws.get("kraken_enabled", False):
            _sym_to_pair = {sym: self.kraken.kraken_pair(sym)
                            for sym in self.symbol_map.values()}
            _kcache = LiveMarketCache()
            _kadapter = KrakenV2BookStream(
                _sym_to_pair, _kcache,
                depth=int(_kws.get("kraken_depth", 10)),
                # W2-28: consecutive checksum-mismatch resubscribe backoff -
                # see KrakenV2BookStream.__init__'s derivation comment
                ck_backoff_base_s=float(
                    _kws.get("kraken_checksum_backoff_base_s", 1.0)),
                ck_backoff_cap_s=float(
                    _kws.get("kraken_checksum_backoff_cap_s", 60.0)))
            self.kraken_ws = WebSocketFeedManager(
                {"enabled": True,
                 "max_book_age_sec": float(
                     _kws.get("kraken_max_book_age_sec", 5.0))},
                cache=_kcache, adapter=_kadapter)
            self.kraken_ws.start()

        risk_cfg = config.get("risk", {})
        self.base_stop_pct = float(risk_cfg.get("stop_loss_pct", 2.0))
        self.stop_vol_mult = float(risk_cfg.get("stop_vol_mult", 4.0))
        self.max_slip_pct = float(risk_cfg.get("max_slippage_pct", 0.5))
        # a mark older than this (both the ticker AND the book mid failed to
        # refresh it for that long) is STALE: non-escape risk actions (profit
        # tiers, inventory derisk, equity-peak ratchet) defer on it rather than
        # fabricate a give-back/liquidation off a frozen price. Escapes (the
        # protective stop) never defer. Generous vs the ~5s cycle so a healthy
        # feed never trips it; only a genuinely dead per-symbol feed does.
        self._mark_stale_sec = float(risk_cfg.get("mark_stale_sec", 20.0))
        # anti-scalp gate: manip_suspect_score (MAX of spoof / imbalance-
        # whiplash / cross-venue book divergence, [0,1]) becomes a LIVE risk
        # action on NEW entries only — exits are never touched. Below
        # downsize_at the entry is unchanged; downsize_at..veto_at shrinks it
        # linearly toward min_scale (folded into the sizer's risk_scale);
        # >= veto_at the entry is vetoed (SZ-045). Conservative by default so
        # only clear painted-flow / venue-divergence bites — the spoofy
        # liquidity label still hard-vetoes on its own path.
        _mg = risk_cfg.get("manip_gate", {}) or {}
        self._manip_gate_enabled = bool(_mg.get("enabled", True))
        self._manip_downsize_at = float(_mg.get("downsize_at", 0.6))
        self._manip_veto_at = float(_mg.get("veto_at", 0.9))
        self._manip_min_scale = float(_mg.get("min_scale", 0.25))
        esc = risk_cfg.get("exit_escalation", {}) or {}
        self.esc_widen_mult = float(esc.get("widen_mult", 2.0))
        self.esc_max_slip_pct = float(esc.get("max_slippage_cap_pct", 3.0))
        self.esc_market_after = int(esc.get("market_after_attempts", 3))
        # maker-first PROFIT exits: rest post-only on our side first, capture
        # the spread; risk exits stay marketable. On by default (the whole
        # point), config-gated for a clean A/B and instant rollback.
        self.maker_first_profit_exits = bool(
            esc.get("maker_first_profit_exits", True))
        self._exit_attempts: dict = {}      # position_id -> failed attempts
        # last time the entry pipeline ADMITTED an order (signal passed the
        # gates and a submit succeeded) — the ML-073 drought clock. Left
        # unseeded (None) here and lazily seeded from the first INJECTED
        # `now` fast_cycle sees (W2-18): seeding with time.time() at
        # construction made `now - _last_entry_admit_ts` go wildly negative
        # under replay, where the injected now is historical and almost
        # always far behind the real wall clock — the drought fastpath
        # could never arm. A restore (core/persistence.py) sets a concrete
        # float before the first cycle and is never clobbered by the lazy
        # seed; a fresh boot's first fast_cycle seeds it exactly once, so a
        # restart still never instantly declares a drought.
        self._last_entry_admit_ts: Optional[float] = None
        self._stop_ok: dict = {}            # asset -> stop eval allowed this cycle
        self._equity_drift_pct: float = 0.0

        # --- rolling market state ---
        self.view: dict = {}                # base asset -> merged venue view
        self.kraken_books: dict = {}        # base asset -> kraken order book
        self.marks: dict = {}               # kraken symbol -> last price
        self._mark_ts: dict = {}            # kraken symbol -> last mark update
        # TELEMETRY-ONLY wall-clock twins of _mark_ts (latency audit
        # 2026-08-07): _mark_ts stamps the loop-frozen injected `now`, so
        # any age computed against that same `now` is arithmetically 0 -
        # status.json showed marks_age_sec=0.0 beside a 253ms feed RTT.
        # No decision path may ever read this dict (replay determinism);
        # the runner's status export is its only consumer.
        self._mark_wall_ts: dict = {}
        self._stale_bar_latched: set = set()  # FW-080 one-warn-per-episode
        self.book_ts: dict = {}             # base asset -> fetch time
        self.daily_candles: dict = {}       # base asset -> daily candles
        # v8 venue-grounded candles: execution-venue 5m bars, cached per
        # asset as (fetched_ts, candles) and refreshed round-robin by
        # _augment_view_with_kraken (throttled REST; the ws feed owns
        # books, candles tolerate staleness up to the refresh cadence).
        self._kr_candles: dict = {}         # base asset -> (ts, candles)
        self._kr_candle_refresh_sec = float(
            config["exchanges"]["kraken"].get("candle_refresh_sec", 150.0))
        self.margin_level_pct: float = 0.0
        self._pos_realized: dict = {}       # position_id -> cumulative net PnL
        self._cycle = 0                     # per-process heartbeat
        self._cycle_lifetime = 0            # survives restarts via snapshot
        self._last_macro = 0.0
        self._last_snapshot = 0.0
        self._halted = False
        # --- control surface (driven by runner/UI) ---
        self.entries_enabled = True     # kill switch for NEW risk
        self.live_armed = False         # live orders require explicit arm
        self.sim = SimOverrides()       # dry-run condition injection
        self._live_block_logged = 0.0

        # central fault authority (op-state ledger + policy). Constructed and
        # armed BEFORE store.restore() below (W2-15): arm() promotes a clean
        # FaultManager INIT -> ARMED, which is correct for a bot that finished
        # __init__ up to this point (enforce_config above raises on a live
        # FATAL, so startup validation already passed). restore() then
        # re-latches any fault that survived a prior run - composing on top
        # of ARMED via the normal latch() transition rules (see core/fault.py
        # docstring for why this order, not the reverse, is required).
        # Driven by the halt conditions (catastrophe hard-stop here, the
        # runner wedge in runner.py); allow_new_risk() gates NEW entries —
        # exits are NEVER gated (invariant #5).
        self.fault = FaultManager(alerts=self.alerts)
        self.fault.arm()

        # --- pause/resume ---
        self.store = StateStore(sys_cfg.get("state_path", "outputs/state.json"))
        self._resumed = False
        if resume and self.store.exists():
            self._resumed = self.store.restore(self)
            if self._resumed and not self.dry_run:
                self._reconcile_live_on_resume()
        # ML-076: the restored monitor snapshot can carry a champion badge from
        # a model no longer on disk (a newer artifact was saved, or an older
        # snapshot was restored). Gating challengers against that ghost lets it
        # squat and reject every retrain forever (live: badge 0.1441 vs loaded
        # model 0.2259 -> model stuck KILLED). Realign the badge to the model
        # actually loaded - badge only, never the governor level. model_loaded
        # (meta.trained) is the load-truth: a champion that failed the v8 width
        # guard (a 58-feature logistic on a 62-feature schema, live 2026-07-21)
        # never loads, so the badge is a ghost with nothing behind it and is
        # reset to the no-champion default so a current-schema challenger can
        # deploy and re-arm the governor.
        self.monitor.reconcile_champion_badge(self.meta.oof_brier,
                                              model_loaded=self.meta.trained)

    def _reconcile_live_on_resume(self) -> None:
        """Live resume: restored resting orders reconcile through the normal
        poll path (QueryOrders reports fills that happened while offline as
        deltas vs the persisted fill state, and they flow through
        _handle_fill like any other fill). This method only adds an advisory
        balance cross-check so silent drift is at least visible."""
        try:
            balances = self.kraken.get_account_balance() or {}
        except Exception:
            log.warning("resume balance check skipped: Balance call failed")
            return
        for asset, _symbol in self.symbol_map.items():
            local = sum(p.size if p.direction == "long" else -p.size
                        for p in self.state.open_positions()
                        if self._asset_of(p.symbol) == asset)
            # Kraken balance keys vary (XETH/ETH, XXBT/XBT for BTC)
            keys = {asset, f"X{asset}", "XXBT" if asset == "BTC" else asset,
                    "XBT" if asset == "BTC" else asset}
            held = 0.0
            for k in keys:
                try:
                    held = max(held, float(balances.get(k, 0.0)))
                except (TypeError, ValueError):
                    pass
            if local > 0 and held < local * 0.98:
                log.warning(
                    f"RESUME MISMATCH {asset}: snapshot says {local:.6f} long "
                    f"but Kraken balance shows {held:.6f}. Positions may have "
                    f"been closed manually while the bot was down - review "
                    f"before trusting the restored book.")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _tier_engine(self, scale: float) -> ProfitTierEngine:
        key = round(max(scale, 0.1), 2)
        eng = self._tier_engines.get(key)
        if eng is None:
            scaled = json.loads(json.dumps(self.tiers_base))   # deep copy
            for i in range(1, 5):
                t = scaled.get(f"tier_{i}")
                if t:
                    t["trigger_pct_gain"] = float(t["trigger_pct_gain"]) * key
                    if "trigger_vol_mult" in t:
                        t["trigger_vol_mult"] = \
                            float(t["trigger_vol_mult"]) * key
            eng = ProfitTierEngine(scaled)
            self._tier_engines[key] = eng
        return eng

    def _submit_algo_child(self, parent, now: float) -> None:
        """Price and submit one child slice through the UNCHANGED
        hardened path: fresh AS quote + tactics for placement, then
        order_manager (pre-trade already approved the parent's edge;
        the firewall re-checks every child)."""
        # setdefault (not .get(...) or {}): the "_admission_recorded" flag
        # set below must persist on THIS SAME dict across every child of
        # this parent, not a fresh throwaway {} each call.
        meta_t = self._algo_meta.setdefault(parent.parent_id, {})
        asset = parent.asset
        v = self.view.get(asset) or {}
        vol_cum = sum(max(float(c.get("volume") or 0.0), 0.0)
                      for c in (v.get("candles") or [])[-12:])
        child = self.algo.next_slice(parent.parent_id, now, vol_cum)
        if child is None:
            return
        fv_state = self.fv.state(asset)
        vol_state = self.vol.state(asset)
        liq_state = self.liq.state(asset)
        equity = self._equity()
        mark = self.marks.get(parent.symbol) or fv_state.kraken_mid or \
            parent.arrival_price
        inv_ratio = self.inventory.inventory_ratio(self.state, asset,
                                                   self.marks, equity)
        quote = self.quoter.quote(fv_state.fair_value or mark,
                                  vol_state.sigma_bar_pct, inv_ratio,
                                  liq_state.label,
                                  fee_bps=self.pretrade.maker_fee_bps)
        plan = self.tactics.plan_entry(parent.direction, quote,
                                       self.kraken_books.get(asset) or {},
                                       parent.urgency, liq_state.label)
        # ONE position per parent, not one per child. A fresh uuid per slice
        # fragmented a single sliced order into up to max_children separate
        # positions — each with its own stop/tiers/high_water and each eating a
        # max_concurrent_positions slot (so one algo parent could block every
        # other entry). Deriving the id from parent_id makes every child fill
        # COALESCE into one position (size-weighted entry via _handle_fill), and
        # it's deterministic so it survives a mid-execution restart.
        position_id = f"algo-{parent.parent_id}"
        # F6 Rule 534 self-cross guard: BEFORE any marketable (non-post_only)
        # sell on this pair, cancel our own resting long-book entry bid first.
        # No-op for a maker-first post_only entry, and for a buy-side entry.
        # getattr-guarded: unit tests exercise this off a minimal stub.
        _lb_guard = getattr(self, "_clear_long_book_bid_before_sell", None)
        if callable(_lb_guard):
            _lb_guard(asset, parent.side, plan.post_only,
                      reason="algo-child entry")
        order = self.orders.submit(
            asset=asset, symbol=parent.symbol,
            pair=self.kraken.kraken_pair(parent.symbol), side=parent.side,
            price=plan.price, size=child.units, purpose="entry",
            position_id=position_id, post_only=plan.post_only,
            leverage=meta_t.get("leverage", 1.0),
            ref_price=mark, equity=equity,
            book=self.kraken_books.get(asset) or {},
            sigma_bar_pct=vol_state.sigma_bar_pct,
            meta={"p_win": meta_t.get("p_win", 0.0),
                  "edge_bps": meta_t.get("edge_bps", 0.0),
                  "est_cost_bps": meta_t.get("est_cost_bps", 0.0),
                  "features": meta_t.get("features"),
                  "avail": meta_t.get("avail") or {},
                  "gate_components": meta_t.get("gate_components") or {},
                  "probe": bool(meta_t.get("probe", False)),
                  "candidate_id": meta_t.get("candidate_id") or "",
                  "algo_parent": parent.parent_id,
                  "algo_child_seq": child.seq,
                  "bracket_pt_frac": meta_t.get("bracket_pt_frac", 0.0),
                  "bracket_sl_frac": meta_t.get("bracket_sl_frac", 0.0),
                  "bracket_deadline_ts": meta_t.get(
                      "bracket_deadline_ts", 0.0)},
            now=now,
        )
        if order:
            self.algo.note_child_order(parent.parent_id, position_id)
            if not meta_t.get("_admission_recorded"):
                # first successful child EVER landed for this parent: this
                # is where "an order actually went out" first became true
                # for the parent as a whole - record the ONE probe
                # admission here (was previously recorded at parent
                # creation, before any child could be rejected). getattr-
                # guarded: unit tests exercise this off a minimal stub
                # `self` that may not define _record_probe_admission at all.
                meta_t["_admission_recorded"] = True
                record_admission = getattr(self, "_record_probe_admission",
                                          None)
                if callable(record_admission):
                    # review fix #2: the parent template carries its OWN
                    # priced cost (None for conviction/share_cap) - never
                    # the pointer's, which may belong to a later decision.
                    # cost= only when priced: legacy single-arg stubs (and
                    # the pinned signature) stay callable unchanged.
                    _pc = meta_t.get("probe_cost")
                    if _pc is None:
                        record_admission(bool(meta_t.get("probe", False)))
                    else:
                        record_admission(bool(meta_t.get("probe", False)),
                                         cost=_pc)
            self._last_entry_admit_ts = now            # ML-073 drought clock
            log.info(f"ALGO-CHILD {child.seq}/{child.n_total} "
                     f"{parent.side} {child.units:.6f} {parent.symbol} "
                     f"@ {self._px(parent.symbol, plan.price)} [{plan.style}] "
                     f"parent={parent.parent_id}")
        else:
            self.algo.note_child_rejected(parent.parent_id, child.units,
                                          "order_manager/firewall refused")

    def _step_exec_algos(self, now: float) -> None:
        """Advance every live parent one scheduling step; abort them all
        when new risk is globally blocked (kill switch / watchdog)."""
        if not self.algo.parents:
            return
        if not self.entries_enabled:
            self.algo.abort_all("EX-ALGO-ENTRIES-OFF: operator kill switch")
            return
        if not self._live_order_allowed("entry"):
            return                         # disarmed: pause, don't abort
        for pid in list(self.algo.parents):
            parent = self.algo.parents.get(pid)
            if parent is None:
                continue
            if self.watchdog.state.entries_blocked:
                self.algo.abort_all("EX-ALGO-WATCHDOG: data quality block")
                return
            self._submit_algo_child(parent, now)

    def _asset_of(self, symbol: str) -> str:
        return symbol.split("/")[0]

    def _mark_fresh(self, symbol: str, now: float) -> bool:
        """True when `symbol`'s mark was refreshed (ticker or book mid) within
        mark_stale_sec. A missing stamp reads as stale. Non-escape risk actions
        gate on this so they never fire off a frozen price; escapes never do."""
        return (now - self._mark_ts.get(symbol, 0.0)) <= self._mark_stale_sec

    def _measured_sigma(self, asset: str) -> Optional[float]:
        """Per-bar vol for sigma-scaled geometry (exit-floor tier evaluate /
        _exit_floor_hit, SCS sigma hint), or None until the estimator has
        actually measured this asset this session. VolState's dataclass
        default (0.05) is a placeholder: the fast cycle evaluates restored
        positions before the slow cycle's first vol.update, and feeding the
        placeholder to the tier engine collapsed the vol-scaled give-back
        arm to 0.10% and instantly exited an underwater restored short 38s
        after a reboot (LINK 3ea2a851, 2026-07-28). None selects each
        consumer's designed no-vol-feed fallback (static arm_gain_pct /
        legacy triggers / trail_pct; the sampler's own EWMA) — arming input
        only; the fire path never blocks an exit."""
        st = self.vol.state(asset)
        # getattr tolerance mirrors the restored-Position convention: only
        # the real VolState carries the placeholder-vs-measured distinction
        # (field always present, default False); a duck-typed stub that
        # supplies sigma_bar_pct without the flag means the number.
        return st.sigma_bar_pct if getattr(st, "measured", True) else None

    def _px(self, symbol: str, price: float) -> str:
        """Format a price at its venue precision for human output, so a
        sub-dollar pair (ARB/MINA/FLOW) is never logged on a 2-decimal grid
        coarser than its own tick. Display only - the engine computes on
        the full-precision float."""
        return fmt_price(price, getattr(self.orders, "pair_meta", {}),
                         self.kraken.kraken_pair(symbol))

    def _equity(self) -> float:
        return self.state.total_equity(self.marks) if self.marks \
            else self.state.total_equity()

    def _adv_usd(self, asset: str, price: float) -> float:
        """Conservative ADV estimate for the impact model.

        Venue 24h volume units differ across feeds, so this normalizes to
        USD if the number looks like base units, then haircuts by
        pretrade.adv_haircut (Kraken-share proxy; lifted literal, default
        0.10) and floors at adv_floor_usd. Impact is a secondary term at
        this ticket size; conservatism is the point.
        """
        v = float((self.view.get(asset) or {}).get("volume_24h") or 0.0)
        if v <= 0:
            return self._adv_floor_usd
        usd = v * price if v * price < 1e13 and v < 1e8 else v
        return max(usd * self._adv_haircut, self._adv_floor_usd)

    def _nudge_stop(self, stop: float, direction: str) -> float:
        """Cut #7 Osler widen-beyond nudge, config-gated. One method so the
        bracket sl leg and the vol-scaled fallback can never drift apart
        (the bracket caller back-derives sl_frac from the result - the
        traded bet stays the labeled bet)."""
        # NOTE the block is config["risk"], where the knob actually lives -
        # the retired implementation read config["risk_management"], which
        # does not exist, so the config value was NEVER read and only the
        # coinciding 5.0 default masked it (phantom-knob class).
        rm = self.config.get("risk", {})
        return nudge_stop_off_round(
            stop, direction,
            band_bps=float(rm.get("stop_round_buffer_bps", 5.0)),
            offset_bps=float(rm.get("stop_round_offset_bps", 5.0)))

    def _stop_price_for(self, direction: str, entry: float, asset: str) -> float:
        vol_state = self.vol.state(asset)
        macro_state = self.macro.state(asset)
        stop_pct = max(self.base_stop_pct,
                       self.stop_vol_mult * vol_state.sigma_bar_pct)
        stop_pct *= macro_state.playbook.get("stop_mult", 1.0)
        stop_pct *= self.monitor.stop_widen
        stop = entry * (1 - stop_pct / 100.0) if direction == "long" \
            else entry * (1 + stop_pct / 100.0)
        # Osler round-number hygiene, WIDEN-BEYOND semantics since cut #7
        # (risk/stop_placement - the semantic flip is documented there).
        # The old tail's clamps (max(nudged, stop) for long) structurally
        # enforced tighten-only and were removed WITH the flip; widening
        # moves away from entry so no toward-entry clamp is needed.
        return self._nudge_stop(stop, direction)

    # ------------------------------------------------------------------
    # fill handling
    # ------------------------------------------------------------------
    def _finalize_position(self, pos: Position, total_net: float,
                           now: float, close_reason: str = "") -> None:
        """Single close-out path (fill-flat and dust-flat both land here):
        history close, postmortem observation, ledger removal, counter
        cleanup. Keeping this in one place means the two exits can never
        drift apart.

        `close_reason` (geometry-alignment T5, spec D1; default "" -
        every legacy caller unchanged) is the exit order's own `reason`
        string (order.meta["reason"]) that triggered THIS flattening
        fill. Threaded VERBATIM into the live-label barrier column only
        when it is one of the bracket-exit engine's own three reasons
        (tb_pt/tb_sl/tb_time) - label_era_of then tags the row
        LABEL_ERA_TRIPLE_BARRIER, joining the live corpus to the era the
        model trains on (V1's closure). Any OTHER reason (tier/stop/
        hard-stop/ratchet/flatten/force_dry/...) falls back to
        log_close's own "realized" default, byte-identical to before
        this task.

        geometry-alignment T6 (spec D6, ML-082): a bracket close ALSO
        threads this entry's own notional (entry_usd) and cost estimate
        (est_cost_bps -> cost_pct) plus the ml.telemetry config block, so
        log_close can run its own report-only labeled-vs-realized
        comparator (see ml/history.py for the counterfactual it computes
        and why). getattr(self, "config", {}) is self-healing for the
        stub-bot unit-test harnesses (this method predates a real bot
        always carrying self.config)."""
        asset = self._asset_of(pos.symbol)
        # POOL SPLIT, once per TRADE, on the fully-net result (round-2
        # finding 2026-08-05). Per-leg skimming funded locked savings and
        # reserve from trades that ended up losing - and savings is never
        # clawed back, so each of those was permanent. Guarded like every
        # other close-path bookkeeping step: a pool-split failure must
        # never block a close (CLAUDE.md invariant 5).
        try:
            _skim = getattr(self.capital, "skim_trade", None)
            if callable(_skim):
                _skim(total_net, self.state)
        except Exception:                       # noqa: BLE001
            log.exception("pool skim failed at close - position still "
                          "finalized, pools unchanged")
        # SPB-R §1.5: probe-tagged closes feed the tuition governor's
        # trailing-24h clipped-loss window (both modes - warm-flip state;
        # self-guarded no-op on stub bots and non-probe closes).
        self._note_probe_tuition(pos, total_net, now)
        barrier = close_reason if close_reason in (
            "tb_pt", "tb_sl", "tb_time") else "realized"
        # I0 (2026-07-31): the `barrier` above is LOSSY by design - every
        # non-bracket close collapses to "realized", so neither the corpus
        # nor the audit trail can say what actually ended the position.
        # Emit the verbatim reason with the context needed to adjudicate
        # the era deadlock (docs/quant/2026-07-31_live_label_era_deadlock).
        # Guarded: close-path bookkeeping must never block an exit
        # (CLAUDE.md invariant 5).
        try:
            _op = getattr(pos, "opened_at", None)
            _bars = None
            if _op is not None:
                _ts = _op.timestamp() if hasattr(_op, "timestamp") else float(_op)
                _bars = round(max(0.0, now - _ts) / 300.0, 2)
            _det = tag(Code.PT_CLOSE_REASON,
                       f"close {self._asset_of(pos.symbol)}: "
                       f"reason={close_reason or 'unspecified'} "
                       f"barrier={barrier} bars={_bars} "
                       f"probe={bool(getattr(pos, 'is_probe', False))} "
                       f"net={total_net:+.4f}")
            get_audit().log(
                "exit", Code.PT_CLOSE_REASON, _det,
                {"asset": self._asset_of(pos.symbol),
                 "position_id": pos.position_id,
                 "close_reason": close_reason or "",
                 "barrier": barrier, "bars_held": _bars,
                 "is_probe": bool(getattr(pos, "is_probe", False)),
                 "is_bracket": bool(getattr(pos, "bracket_pt_frac", 0.0)),
                 "pt_frac": float(getattr(pos, "bracket_pt_frac", 0.0) or 0.0),
                 "net_usd": round(float(total_net), 6)})
        except Exception:
            log.exception("close-reason audit failed - close unaffected")
        self.history.log_close(
            pos.position_id, total_net, barrier=barrier,
            pt_frac=pos.bracket_pt_frac, sl_frac=pos.bracket_sl_frac,
            entry_usd=pos.entry_price * pos.original_size,
            cost_pct=pos.est_cost_bps / 100.0,
            telemetry_cfg=getattr(self, "config", {})
            .get("ml", {}).get("telemetry", {}),
            # price anchor (2026-08-04): entry only. A multi-tier close
            # has no single exit price - the per-fill truth already lives
            # in outputs/fills.csv keyed by position_id, so exit_price
            # stays 0 ("absent") here rather than a fabricated blend.
            entry_price=float(pos.entry_price or 0.0))
        # rolling performance ledger — every full close, real positions only
        # (hedges carry no thesis/stop of their own). total_net is the popped
        # cumulative (all tier closes + final), so this is the whole trade.
        if not pos.is_hedge:
            self.perf.record_close(
                asset, total_net, pos.entry_price * pos.original_size,
                entry_price=pos.entry_price, stop_price=pos.stop_price, now=now,
                is_probe=bool(getattr(pos, "is_probe", False)))
            if self.breaker.record_close(asset, total_net > 0, now=now):
                get_audit().log("circuit_breaker", Code.SZ_CIRCUIT_BREAKER,
                                f"{asset} paused: "
                                f"{self.breaker.loss_streak} consecutive "
                                f"losses", {"asset": asset})
            # THALES V2 vindication: grade the detectors that advised on
            # this trade's entry against its realized outcome. 2026-07-29
            # (audit A-1/B-2): an EMPTY fired list still grades — it feeds
            # the __base__ outcome ledger that _rel_weight uses as its
            # base-rate null, so every model-lane close counts exactly
            # once whether or not a detector fired on it.
            fired = self._pos_thales.pop(pos.position_id, None)
            if fired is not None:
                self.thales.note_outcome(fired, total_net > 0)
            # --- REALIZED-OUTCOME LOOP (2026-08-02) ---------------------
            # The only place gates and money meet. total_net is net of fees
            # and slippage, so this is the outcome the barrier label could
            # never see: on this feed the label says 0.3991 and the money
            # says 0.038, and the whole gap is the round trip.
            #
            # Normalised to PERCENT of entry notional so it is comparable
            # across position sizes and matches postmortem realized_pct.
            # A zero/absent notional yields no lesson rather than a
            # divide-by-zero or a fabricated 0% — an unattributable close
            # must not quietly count as a loss.
            gp = getattr(self, "_pos_gates", {}).pop(pos.position_id, None)
            if gp:
                notional = abs(pos.entry_price * pos.original_size)
                if notional > 0:
                    try:
                        self.gate_stats.note_realized(
                            gp, (total_net / notional) * 100.0)
                    except Exception:      # never break a close on stats
                        log.exception("gate_stats.note_realized raised - "
                                      "isolated; close continues")
            # Compounder Phase C (task C4): feed this book-tagged close
            # into the shared evidence ladder (risk/long_book.py) - the
            # ONLY place closed_paper/closed_live/pf_live/rung ever move.
            # dry_run selects the paper vs live evidence track (the SAME
            # flag the rest of the engine uses for live/paper posture).
            if pos.book == "long":
                # task C5 item 3(a): cumulative realized PnL feeds the
                # book's own equity-curve peak/drawdown
                # (_long_book_dd_frac) - self-healing getattr, mirroring
                # _long_last_add_ts above, for stub-bot callers that
                # predate this counter.
                if hasattr(self, "_long_book_realized_pnl_total"):
                    self._long_book_realized_pnl_total += total_net
                prev_rung = self.long_ladder.rung()
                self.long_ladder.note_close(total_net, is_live=not self.dry_run)
                new_rung = self.long_ladder.rung()
                if new_rung > prev_rung:
                    detail = tag(Code.LB_RUNG_UP,
                                f"{asset}: evidence ladder rung "
                                f"{prev_rung} -> {new_rung}")
                    get_audit().log("long_book", Code.LB_RUNG_UP, detail,
                                    {"asset": asset, "prev_rung": prev_rung,
                                     "rung": new_rung})
                    log.warning(detail)
        self.postmortem.on_close(
            pos.position_id, total_net, pos.fees_paid_usd,
            entry_usd=pos.entry_price * pos.original_size,
            stopped_out=self._stop_hit.pop(pos.position_id, False),
            exit_regime=self.macro.state(asset).label,
            exit_liq=self.liq.state(asset).label,
            now=now,
            # orphan-close degradation (2026-08-11): if the thesis is gone,
            # these let the paths ledger still name the trade
            asset=asset, direction=pos.direction)
        self.state.remove_position(pos.position_id)
        self._exit_attempts.pop(pos.position_id, None)
        # v10 ladder: a fully-closed position drops the armed state so
        # re-entry needs the full p_win_arm bar again, not the lower
        # disarm bar an in-flight position was allowed to hold at.
        self.ladder.note_exit(asset)

    def _mark_cand(self, asset: str, direction: str, code: str) -> None:
        """Stamp the newest open candidate with the pipeline's final verdict
        (entered / veto). Guarded: bookkeeping never breaks the entry loop."""
        try:
            self.candidates.mark_disposition(asset, direction, code)
        except Exception:
            log.exception("candidate disposition mark failed (%s)", code)

    def _ledger_fill(self, order, event, fees_delta: float,
                     now: float) -> None:
        """Durable per-fill execution record (core/fill_ledger). Guarded:
        recording must never break the trade that produced it."""
        try:
            from core.fill_ledger import append_fill, fill_row
            append_fill(Path(self.config.get("system", {}).get(
                "fills_ledger_path", "outputs/fills.csv")),
                fill_row(order, event, fees_delta, now))
        except Exception:
            log.exception("fill ledger failed - row lost, fill unaffected")

    def _simulated_fill_on_live_book(self, order) -> bool:
        """C2 provenance guard: True when `order` is a SIMULATED fill being
        applied to a book that was born LIVE, in which case the caller must
        refuse it outright.

        `DRY-` txids are minted at exactly one place - OrderManager.submit's
        `if self.dry_run:` branch - and `_poll_dry`/`_sim_cross` then
        fabricate their fills off the local book. In a session CONFIGURED
        live that can only happen after `force_dry` (invariant #2 flips
        both `bot.dry_run` and `bot.orders.dry_run` mid-session): the
        runner stays RUNNING, so every subsequent exit for a real Kraken
        position is simulated, and `_handle_fill` - which carries no
        dry/paper provenance of its own - would decrement `pos.size`, book
        paper PnL and `_finalize_position` a position the venue still holds.
        The book of record must never be closed by a fill that never
        happened; refusing leaves the real positions visible and open.

        Keyed on `_config_dry_run` (immutable, __init__-captured), NEVER on
        `self.dry_run` (force_dry's own target). getattr-defaulted to paper
        so restored objects and the `LiquidityBot.__new__()` stub harnesses
        are exactly inert - a paper session can never trip this."""
        if getattr(self, "_config_dry_run", True):
            return False
        if not str(getattr(order, "txid", "") or "").startswith("DRY-"):
            return False
        detail = (f"simulated fill REFUSED on a live-born book: "
                  f"{getattr(order, 'side', '?')} {getattr(order, 'purpose', '?')} "
                  f"{getattr(order, 'symbol', '?')} txid="
                  f"{getattr(order, 'txid', '?')} position="
                  f"{str(getattr(order, 'position_id', '') or '?')[:8]} - the "
                  f"session is configured LIVE, so this fill was fabricated "
                  f"against a real Kraken book (force_dry with open "
                  f"positions). Position left OPEN and untouched.")
        log.error(detail)
        if not getattr(self, "_sim_fill_on_live_latched", False):
            self._sim_fill_on_live_latched = True
            fm = getattr(self, "fault", None)
            if fm is not None:
                # CRITICAL -> HALTED: refuses NEW risk while leaving exits
                # allowed (core/fault.py). Latched once so the operator gets
                # one alert, not one per fabricated fill.
                fm.latch("simulated_fill_on_live_book", Severity.CRITICAL,
                         detail)
        return True

    def _drop_ladder_probe_tag(self, order) -> None:
        """SPB-R §1.4 sibling seam (H16). The refundable `probe_cost` tag
        rides exactly ONE rung of a grid ladder, but the refund's real
        precondition is "this DECISION bought no label". A fill on ANY rung
        of the group means a label WAS bought, so the tag must die even
        when the tagged rung itself later expires unfilled - otherwise one
        deduction could be refunded against a ladder that did open a
        position. Exception-free by construction (explicit guards, no
        blanket except): fill accounting may never depend on it."""
        meta = getattr(order, "meta", None)
        grp = meta.get("ladder_group") if isinstance(meta, dict) else None
        om = getattr(self, "orders", None)
        if not grp or om is None:
            return
        for sibling in om.open_orders():
            m = getattr(sibling, "meta", None)
            if isinstance(m, dict) and m.get("ladder_group") == grp:
                m.pop("probe_cost", None)

    def _handle_fill(self, event, now: Optional[float] = None) -> None:
        now = now if now is not None else time.time()
        order = event.order
        # C2: provenance gate BEFORE any bookkeeping - a fabricated fill
        # must not refund a probe, ledger a row, or touch the position.
        # getattr-guarded: several suites drive _handle_fill off a
        # SimpleNamespace stub `self` (the _record_probe_admission idiom),
        # and a paper stub can never be the live book this guard protects.
        _prov = getattr(self, "_simulated_fill_on_live_book", None)
        if callable(_prov) and _prov(order):
            return
        # SPB-R §1.4 order-terminal seam: an unfilled probe ENTRY terminal
        # (fill_ratio == 0 on the final event) refunds its placement-time
        # cost (SZ-052). The helper is self-guarded (meta tag presence,
        # never raises) - a no-op for every order that never carried a
        # probe_cost, i.e. all of share_cap mode.
        if getattr(event, "final", False):
            self._maybe_refund_probe_order(order, now)
        if event.fill_size > EPS and order.purpose in ("entry", "hedge"):
            # H16: any rung filling retires the ladder's single refundable
            # probe tag (see _drop_ladder_probe_tag) - a decision that
            # bought a label is never refunded. Same getattr guard as
            # above: stub-`self` harnesses carry no ladder orders at all.
            _drop = getattr(self, "_drop_ladder_probe_tag", None)
            if callable(_drop):
                _drop(order)
            pos = self.state.get_position(order.position_id) if order.position_id else None
            if pos is None:
                position_id = order.position_id or str(uuid.uuid4())
                pos = Position(
                    position_id=position_id, symbol=order.symbol,
                    direction="long" if order.side == "buy" else "short",
                    entry_price=event.fill_price, size=event.fill_size,
                    original_size=event.fill_size,
                    # injected engine time, NOT wall clock: ML-071/ML-073
                    # ages and replay determinism both compare against the
                    # injected now (fleet finding: wall-clock stamps made
                    # historical replays behave unlike production)
                    opened_at=datetime.fromtimestamp(now, tz=timezone.utc),
                    is_hedge=(order.purpose == "hedge"),
                    is_probe=bool(order.meta.get("probe", False)),
                    confidence=order.meta.get("p_win", 0.0),
                    edge_bps=order.meta.get("edge_bps", 0.0),
                    est_cost_bps=order.meta.get("est_cost_bps", 0.0),
                    leverage=order.leverage,
                    book=order.meta.get("book", "5m"),
                    # geometry-alignment T5 (spec D1): 0.0 defaults keep a
                    # non-bracket entry (bracket_exits.enabled=false, or
                    # any order.meta that predates T5) exactly inert - the
                    # exit-evaluation seam below reads bracket_pt_frac>0
                    # as "this position trades the bracket".
                    bracket_pt_frac=order.meta.get("bracket_pt_frac", 0.0),
                    bracket_sl_frac=order.meta.get("bracket_sl_frac", 0.0),
                    bracket_deadline_ts=order.meta.get(
                        "bracket_deadline_ts", 0.0),
                )
                if pos.book == "long":
                    # Compounder Phase C (task C4): a wide, non-trailing
                    # structural stop off the (then-current) average entry -
                    # NOT the 5m vol-scaled protective stop (the tier/give-
                    # back machinery already owns profit protection for
                    # this book; risk/long_book.py's thesis_stop_price
                    # docstring). Re-anchored on every averaging fill below.
                    pos.stop_price = thesis_stop_price(
                        pos.entry_price, float(self.config.get(
                            "long_book", {}).get("thesis_stop_pct", 12.0)))
                elif pos.bracket_sl_frac > EPS:
                    # T5: the sl LEG of this position's bracket - the
                    # existing protective-stop check in
                    # _manage_open_position reuses pos.stop_price
                    # unmodified (same escalation ladder, same OM-011
                    # final-rung market exception); only the LEVEL is the
                    # labeled bracket's own sl_frac, entry*(1-/+sl_frac),
                    # never the config vol-scaled distance below.
                    pos.stop_price = pos.entry_price * (
                        1.0 - pos.bracket_sl_frac) if pos.direction == "long" \
                        else pos.entry_price * (1.0 + pos.bracket_sl_frac)
                    # ALGO-7 (cut #7, Osler round-number avoidance): a stop
                    # resting inside a round-number cluster is hit by any
                    # sweep TO the cluster. Nudge beyond it, then
                    # BACK-DERIVE sl_frac from the nudged price - the
                    # traded bet stays the labeled bet (geometry-alignment
                    # law); tb_sl threads unchanged.
                    _nudged = self._nudge_stop(pos.stop_price, pos.direction)
                    if _nudged != pos.stop_price:
                        pos.stop_price = _nudged
                        pos.bracket_sl_frac = abs(
                            1.0 - _nudged / pos.entry_price)
                else:
                    # _stop_price_for nudges internally (cut #7) - wrapping
                    # it here again would double-nudge
                    pos.stop_price = self._stop_price_for(
                        pos.direction, pos.entry_price,
                        self._asset_of(pos.symbol))
                order.position_id = position_id
                self.state.add_position(pos)
                fired = order.meta.get("thales_fired")
                # 2026-07-29 (THALES A-1/B-2): empty lists are stored too
                # — a close with no detector fired still grades the
                # __base__ outcome ledger (the reliability null). Only
                # orders that never carried the key (hedges/legacy) skip.
                if fired is not None and not pos.is_hedge:
                    self._pos_thales[position_id] = list(fired)
                # Same lifecycle for the gate verdicts. Hedges are excluded
                # for the same reason as above: a hedge's P&L is not a
                # verdict on the gates that opened the position it protects,
                # and crediting it either way teaches the wrong lesson.
                gp = order.meta.get("gates_passed")
                if gp and not pos.is_hedge:
                    getattr(self, "_pos_gates", {})[position_id] = dict(gp)
                self.postmortem.note_fill(position_id, event.fill_price)
                if not pos.is_hedge and "features" in order.meta:
                    self.history.log_entry(position_id, self._asset_of(pos.symbol),
                                        pos.direction, order.meta["features"],
                                        probe=pos.is_probe,
                                        candidate_id=order.meta.get(
                                            "candidate_id"),
                                        book=pos.book,
                                        gate_components=order.meta.get("gate_components"),
                                        avail=order.meta.get("avail"))
                if pos.book == "long":
                    self._register_long_book_thesis(
                        pos, position_id, event.fill_price, now)
                log.info(f"OPEN {pos.direction} {pos.size:.6f} {pos.symbol} "
                        f"@ {self._px(pos.symbol, pos.entry_price)} "
                        f"(p={pos.confidence:.2f}, "
                        f"hedge={pos.is_hedge})")
            else:
                # H1 (2026-08-01 audit): the give-back ratchet arms off
                # ProfitTierEngine._mfe_pct = (high_water - entry)/entry, so
                # re-basing entry WITHOUT re-basing high_water re-prices a
                # peak that never happened. Averaging DOWN - the long book's
                # entire purpose - leaves the peak pinned to the OLD, higher
                # basis, so a position never once in profit reports a
                # phantom MFE, arms the ratchet, and gets 100%-closed at a
                # loss with the thesis stop still far away. Capture the
                # peak-gain FRACTION against the old basis first and
                # re-anchor it onto the new one: the fraction is the
                # invariant, so a never-profitable position carries 0.0 and
                # stays disarmed while a genuine winner keeps its exact
                # MFE%. Ratchet-only semantics are untouched -
                # _update_high_water's max()/min() still owns every later
                # move, and a LOWER re-anchored chandelier anchor can only
                # produce a stop candidate _ratchet_stop already refuses
                # (it never loosens held ground). high_water None (never
                # evaluated) stays None: _mfe_pct would read it as the
                # entry itself, and materialising it here would be a silent
                # behaviour change on a position the tier engine has not
                # yet seen.
                _hw = getattr(pos, "high_water", None)
                peak_frac = (ProfitTierEngine._mfe_pct(pos) / 100.0
                             if _hw is not None else None)
                total = pos.size + event.fill_size
                pos.entry_price = (pos.entry_price * pos.size +
                                   event.fill_price * event.fill_size) / total
                pos.size = total
                pos.original_size = max(pos.original_size, total)
                if peak_frac is not None:
                    pos.high_water = pos.entry_price * (
                        (1.0 + peak_frac) if pos.direction == "long"
                        else (1.0 - peak_frac))
                if pos.book == "long":
                    # re-anchor the thesis stop off the NEW average entry
                    # (main.py:~1255's averaging path; Global Constraint:
                    # long-book adds AVERAGE into the existing position)
                    pos.stop_price = thesis_stop_price(
                        pos.entry_price, float(self.config.get(
                            "long_book", {}).get("thesis_stop_pct", 12.0)))
            if pos.book == "long" and order.purpose == "entry":
                # C4 review, Critical #1(c): the spacing clock keys on
                # FILL, not submit - covers BOTH the first-open branch
                # above and this averaging branch (every real fill, first
                # or averaging, is an accumulation event the NEXT add must
                # space off of). A zero-fill expiry/cancel never reaches
                # here at all (event.fill_size > EPS is this whole
                # branch's own guard), so it can never burn the window;
                # the resting bid's own presence is what prevents a
                # duplicate submit meanwhile (_long_book_cycle's book-aware
                # resting-order check, Minor #10). Self-healing getattr:
                # other tests drive _handle_fill off a minimal stub bot
                # that may not set this dict at all.
                last_add_ts = getattr(self, "_long_last_add_ts", None)
                if last_add_ts is not None:
                    last_add_ts[self._asset_of(pos.symbol)] = now
            # empirical adverse-selection: record every NEW-risk fill so its
            # post-fill mark move is measured against the trusted mark. Entries
            # are limit orders (OM-011) — the classic maker adverse-selection
            # target; a persistently negative mark-out here is the bot being
            # scalped, the ground truth the manip gate tries to pre-empt.
            _mk = getattr(self, "markout", None)
            if _mk is not None:
                _mk.record_fill(order.symbol, self._asset_of(order.symbol),
                                order.side, event.fill_price, now)
            fee_seen_delta = order.fees_usd - order.meta.get("_fees_seen", 0.0)
            pos.fees_paid_usd += fee_seen_delta
            pos.entry_fees_usd += fee_seen_delta
            if order.meta.get("algo_parent"):
                self.algo.note_fill(order.meta["algo_parent"],
                                    event.fill_size, event.fill_price)
            order.meta["_fees_seen"] = order.fees_usd
            fee_booked_delta = order.fees_usd - order.meta.get("_fees_booked", 0.0)
            self.state.record_fees(fee_booked_delta)
            self.state.record_entry_fee(fee_booked_delta)
            order.meta["_fees_booked"] = order.fees_usd
            self._ledger_fill(order, event, fee_booked_delta, now)

        elif event.fill_size > EPS and order.purpose == "exit":
            pos = self.state.get_position(order.position_id)
            if pos is None:
                return
            # de-escalate the exit ladder ONLY when this exit order
            # COMPLETED — a dribble partial fill on each timed-out attempt
            # must not reset the counter, or the ladder can never widen its
            # slippage cap / reach the market rung in the dislocated-book
            # case it exists for (adversarially-verified fleet finding).
            if order.remaining <= EPS:
                self._exit_attempts.pop(order.position_id, None)
            sgn = 1.0 if pos.direction == "long" else -1.0
            fee_delta = order.fees_usd - order.meta.get("_fees_seen", 0.0)
            order.meta["_fees_seen"] = order.fees_usd
            self._ledger_fill(order, event, fee_delta, now)
            gross = sgn * (event.fill_price - pos.entry_price) * event.fill_size
            # cash settlement nets ONLY the exit leg (entry fees already left
            # cash at fill time via record_entry_fee); the TRADE net used for
            # labels/perf/breaker additionally carries this slice's pro-rata
            # share of the entry fees, so decisions are graded fully net.
            net = gross - fee_delta
            # entry fees drain as a POOL proportional to the slice of the
            # CURRENT size being closed: shares vs original_size could sum
            # past 100% when an entry order keeps filling after a partial
            # exit (self-audit 2026-07-18); a pool can never over-allocate,
            # a full close drains it, later entry fills refill it.
            entry_share = 0.0
            if pos.size > EPS and pos.entry_fees_usd > 0.0:
                entry_share = pos.entry_fees_usd * min(
                    event.fill_size / pos.size, 1.0)
                pos.entry_fees_usd -= entry_share
            trade_net = net - entry_share
            pos.size = max(pos.size - event.fill_size, 0.0)
            # advance the profit-tier ladder ON FILL (Assurance Build fix:
            # tier_closed was never written, so tier 1 re-fired forever and
            # tiers 2-4 + the trailing stop were unreachable dead code)
            tf = int(order.meta.get("tier_fired", 0) or 0)
            if tf > pos.tier_closed:
                pos.tier_closed = tf
            pos.fees_paid_usd += fee_delta
            self.state.record_fees(fee_delta)
            # Settle CASH per leg (entry fees already left cash at fill
            # time, so `net` is the right cash delta) but DEFER the pool
            # split to trade close: skimming per winning LEG on this
            # entry-fee-inclusive number funded locked savings/reserve out
            # of trades that ended up losing, and with tiered exits that is
            # the normal shape (round-2 finding 2026-08-05). The trade's
            # fully-net result is skimmed once in _finalize_position.
            self.capital.record_realized_profit(net, self.state, skim=False)
            self._pos_realized[pos.position_id] = \
                self._pos_realized.get(pos.position_id, 0.0) + trade_net
            log.info(f"CLOSE {event.fill_size:.6f} {pos.symbol} @ "
                    f"{self._px(pos.symbol, event.fill_price)} "
                    f"net ${trade_net:+,.2f} (remaining {pos.size:.6f})")
            if pos.size <= pos.original_size * 1e-4 or pos.size <= EPS:
                total_net = self._pos_realized.pop(pos.position_id, trade_net)
                self._finalize_position(
                    pos, total_net, now,
                    close_reason=str(order.meta.get("reason", "")))
                log.info(f"FLAT {pos.symbol} position {pos.position_id[:8]}: "
                        f"total net ${total_net:+,.2f}")

    def _register_long_book_thesis(self, pos: Position, position_id: str,
                                   fill_price: float, now: float) -> None:
        """Postmortem TradeThesis for the long book's FIRST fill on a new
        accumulation position (task C4 - the financial-analyst accounting
        requirement). Averaging fills never re-register: register_entry()
        upserts by position_id, so a second call would silently discard
        the original thesis's accumulated marks/entry_ts - the caller
        (_handle_fill) only invokes this from the first-fill branch.

        No meta-model probability exists for this book (a rule-based
        accumulation engine, not p(win)-driven) - p_win is a neutral 0.5
        ("no informative belief") used ONLY for this thesis's own
        expected-return bookkeeping; Position.confidence (the real
        decision-relevant field) is set separately from order.meta
        elsewhere. stop_pct/target_pct are the long tier GEOMETRY
        (thesis_stop_pct config + the long tier engine's own tier-1
        trigger) - never fitted, never duplicated from the 5m book."""
        asset = self._asset_of(pos.symbol)
        thesis_pct = float(self.config.get("long_book", {})
                           .get("thesis_stop_pct", 12.0))
        tiers = getattr(self.long_tier_engine, "tiers", None) or []
        target_pct = float((tiers[0] or {}).get("trigger_pct_gain", 0.0)) \
            if tiers else 0.0
        p_win = 0.5
        ev_pct = p_win * target_pct - (1.0 - p_win) * thesis_pct
        fv = self.fv.state(asset).fair_value or fill_price
        self.postmortem.register_entry(TradeThesis(
            position_id=position_id, asset=asset, symbol=pos.symbol,
            direction=pos.direction, entry_ts=now, p_win=p_win,
            expected_ret_pct=ev_pct, expected_cost_bps=0.0,
            stop_pct=thesis_pct, target_pct=target_pct,
            entry_regime=self.macro.state(asset).label,
            entry_liq=self.liq.state(asset).label,
            narrative_label="", fair_value=fv, quote_price=fill_price,
            price_decimals=_price_decimals(
                getattr(self.orders, "pair_meta", {}),
                self.kraken.kraken_pair(pos.symbol), fill_price),
            model_p=-1.0, shadow_p=-1.0, model_scored=False,
            fill_price=fill_price,
        ))

    def _close_periods(self, now: float) -> None:
        """Daily P&L reset + weekly/monthly close-outs, factored from
        fast_cycle so the crash-atomicity guarantee at the bottom is pinned
        by tests/test_period_close_durability.py (29c)."""
        self.state.maybe_reset_daily_pnl(now)
        # WEEKLY CLOSE-OUT (RP-070): exactly once at each ISO-week boundary,
        # restart-safe. The rollover ritual: reserve refills a losing week's
        # realized loss into trading cash (capital_manager.weekly_rollover),
        # then the week's signed record lands in the hash-chained audit and
        # the append-only ledger. Reporting + pool bookkeeping only - no
        # orders, no risk-state changes.
        _wk = self.state.maybe_close_week(now)
        if _wk is not None:
            try:
                _refill = self.capital.weekly_rollover(self.state, _wk)
                _wk["reserve_refill"] = round(_refill, 2)
                _wk.update(self._grade_period_goal(
                    "week", _wk["weekly_realized"],
                    "weekly_profit_goal_usd", reserve_refill=_refill))
                get_audit().log(
                    "engine", Code.RP_WEEK_CLOSED,
                    f"week {_wk['week']} closed: net "
                    f"{_wk['weekly_realized']:+.2f}, refill {_refill:.2f}, "
                    f"goal {_wk['category']}",
                    dict(_wk))
                _append_period_ledger(
                    Path(self.config.get("system", {}).get(
                        "weekly_ledger_path", "outputs/weekly_ledger.csv")),
                    _wk, ["week", "weekly_realized", "reserve_refill", "cash",
                          "savings", "reserve", "realized_total"] + _GOAL_COLS)
            except Exception:
                log.exception("weekly close-out failed - trading unaffected, "
                              "ledger row lost for %s", _wk.get("week"))
        # calendar-month close (RP-071): goal-grading only, NO reserve
        # rollover (the shock absorber is weekly by design)
        _mo = self.state.maybe_close_month(now)
        if _mo is not None:
            try:
                _mo.update(self._grade_period_goal(
                    "month", _mo["monthly_realized"],
                    "monthly_profit_goal_usd"))
                get_audit().log(
                    "engine", Code.RP_MONTH_CLOSED,
                    f"month {_mo['month']} closed: net "
                    f"{_mo['monthly_realized']:+.2f}, goal {_mo['category']}",
                    dict(_mo))
                # RP-072 ratchet: a month closing at >=100% of its EFFECTIVE
                # goal raises the next month's bar x1.5. Never down - the
                # stress never relaxes (operator directive 2026-08-11:
                # "scale the profits to the most it can stress every
                # month"). Fires AFTER grading so the closed month is judged
                # by the bar it was run under.
                # consume the grader's OWN verdict (_GOAL_COLS carries
                # "hit") rather than re-deriving `realized >= goal` here -
                # two sites deriving one predicate drift silently the day
                # evaluate_goal's hit semantics grow a tolerance or a
                # net-of-refill adjustment (challenge ordering audit,
                # 2026-08-11)
                _eff = float(_mo.get("goal", 0.0) or 0.0)
                if _eff > 0 and bool(_mo.get("hit")):
                    _old = float(getattr(self.state, "goal_ladder_mult", 1.0))
                    self.state.goal_ladder_mult = _old * 1.5
                    get_audit().log(
                        "engine", Code.RP_GOAL_ESCALATED,
                        f"month {_mo['month']} met its {_eff:.2f} goal: "
                        f"ladder {_old:.4f} -> "
                        f"{self.state.goal_ladder_mult:.4f} (next effective "
                        f"goal {_eff * 1.5:.2f})",
                        {"month": _mo["month"], "old_mult": round(_old, 4),
                         "new_mult": round(self.state.goal_ladder_mult, 4),
                         "realized": round(float(_mo["monthly_realized"]), 2),
                         "effective_goal": round(_eff, 2)})
                _append_period_ledger(
                    Path(self.config.get("system", {}).get(
                        "monthly_ledger_path", "outputs/monthly_ledger.csv")),
                    _mo, ["month", "monthly_realized", "cash", "savings",
                          "reserve", "realized_total"] + _GOAL_COLS)
            except Exception:
                log.exception("monthly close-out failed - trading unaffected, "
                              "ledger row lost for %s", _mo.get("month"))
        if _wk is not None or _mo is not None:
            # CRASH-ATOMICITY (29c): maybe_close_week/month advanced the
            # persisted period key and zeroed the period P&L in MEMORY only;
            # waiting for the next 30s cadence snapshot leaves a window
            # where a kill restores the OLD key and REPLAYS the close on
            # restart - duplicate RP_WEEK_CLOSED audit/ledger rows and,
            # after a losing week, a SECOND reserve->cash refill for the
            # same loss. Snapshot NOW so the boundary crossing and its
            # rollover land on disk together.
            self.store.snapshot(self)

    def _submit_exit(self, pos: Position, close_pct: float, reason: str,
                 tier_fired: int = 0, now: Optional[float] = None,
                 profit_take: bool = False, reason_code: str = "") -> None:
        """Risk-reduction exit: marketable limit, slippage-capped, never
        blocked by the pre-trade edge gate (exits are risk management).

        `reason_code` (default "" — every legacy caller unchanged) is a
        registered core/codes.py Code carried on THIS specific close (e.g.
        Code.PT_TIME_STOP.value on a PT-060 scratch, threaded from
        TierAction.reason_code); it rides in order.meta["reason_code"] so a
        disposition is identifiable without string-matching `reason`.

        ESCALATION LADDER (expect the market to gap): each time an exit
        for this position expires unfilled, the next attempt widens its
        slippage cap by esc_widen_mult (capped at esc_max_slip_pct).
        After esc_market_after failed attempts the final rung is a true
        market order - in a dislocated book, being out at a bad price
        beats being trapped at a good one."""
        now = now if now is not None else time.time()
        asset = self._asset_of(pos.symbol)
        live = [o for o in self.orders.open_orders()
                if o.purpose == "exit" and o.position_id == pos.position_id]
        if live:
            # One live exit per position — EXCEPT a risk-off exit (hard stop,
            # fault, derisk, hedge unwind, protective floor/trail/BE) must
            # PREEMPT a non-urgent resting maker PROFIT-take. That maker rests
            # post-only on the passive side (sell at the ask / buy at the bid);
            # in a fast adverse move it will not fill, and silently dropping the
            # escape left the position unprotected for a whole order timeout
            # (~25s). Cancel the maker and fall through to the marketable exit.
            # Every other pairing keeps the dedup: a marketable risk-off exit is
            # already an escape in flight (the ladder re-attempts on expiry), and
            # a profit-take never preempts anything.
            preemptable = [o for o in live if o.post_only]
            if profit_take or not preemptable:
                return
            for o in preemptable:
                self.orders.cancel_order(o, reason=f"preempted by {reason}")
            log.warning(tag(Code.OM_EXIT_PREEMPT,
                            f"{pos.symbol} risk-off '{reason}' cancelled a "
                            f"resting maker profit-take to clear the escape"))
            # DRAIN THE LAST LOOK before sizing (round-2 finding 2026-08-05):
            # cancel_order's final reconcile books a fill that landed since
            # the previous poll into order.filled and QUEUES its FillEvent,
            # which poll() would not deliver until the NEXT cycle - so the
            # `size = pos.size * close_pct` a few lines below would size the
            # escape off a position that has already shrunk. At a 100% close
            # of a fully-filled preempted take that sells the position TWICE
            # (live: flips short), then the deferred fill drives pos.size
            # into the zero-clamp with the extra units unaccounted.
            # take_deferred() was written for exactly this caller and had
            # none; each event goes through the SAME _handle_fill path poll()
            # would use, so the single-application invariant holds.
            # callable() narrows to a callable returning bare `object`;
            # declare the seam's shape so the iteration type-checks
            _late: "Callable[[], list] | None" = getattr(
                self.orders, "take_deferred", None)
            if _late is not None:
                for _ev in _late():
                    try:
                        self._handle_fill(_ev, now)
                    except Exception:       # noqa: BLE001 - never block an escape
                        log.exception(
                            "deferred fill application failed during exit "
                            "preemption - continuing to the escape")
                if pos.size <= EPS:
                    log.warning(
                        f"{pos.symbol} preempted take filled the position "
                        f"flat - no escape needed")
                    return
        pair = self.kraken.kraken_pair(pos.symbol)
        omin = self.orders._ordermin(pair)

        # DUST-FLAT (Assurance Build): a remainder below the venue minimum
        # can never be exited — without this it orbits forever, spamming
        # rejected orders and inflating the escalation counter. Finalize
        # it locally at zero incremental PnL (the value is real but
        # unrealizable; sub-ordermin notional is cents by construction).
        if omin > 0 and pos.size < omin:
            total_net = self._pos_realized.pop(pos.position_id, 0.0)
            log.warning(f"DUST FLAT {pos.symbol} {pos.position_id[:8]}: "
                        f"remainder {pos.size:.8f} below venue minimum "
                        f"{omin} - closing the book on it (total net "
                        f"${total_net:+,.2f})")
            self._finalize_position(pos, total_net, now, close_reason=reason)
            return

        attempts = self._exit_attempts.get(pos.position_id, 0)
        slip_pct = min(self.max_slip_pct * (self.esc_widen_mult ** attempts),
                       self.esc_max_slip_pct)
        go_market = attempts >= self.esc_market_after
        book = self.kraken_books.get(asset) or {}
        bids, asks = book.get("bids") or [], book.get("asks") or []
        mark = self.marks.get(pos.symbol, pos.entry_price)
        # collar REFERENCE (EX-6): the exit collar must center on an
        # INDEPENDENT current price - fresh mark, else live book mid, else
        # fair value - NEVER the entry price. Anchoring to entry in a gap
        # clamps the escape toward where the position was opened (a price
        # that no longer exists) and the order never fills; with no
        # independent reference at all, pass None - the firewall lets
        # exits through uncollared by design (fail-safe, documented).
        if pos.symbol in self.marks and self._mark_fresh(pos.symbol, now):
            ref = self.marks[pos.symbol]
        elif bids and asks:
            ref = 0.5 * (bids[0][0] + asks[0][0])
        else:
            ref = self.fv.state(asset).fair_value or None
        # MAKER-FIRST profit exits: a scheduled profit-TARGET take (price
        # reached the tier trigger; profit_take=True) is not urgent risk-off -
        # it is capturing gains, so its FIRST attempt rests POST-ONLY on our
        # own side of the book (sell at the ask / buy at the bid) to CAPTURE
        # the spread instead of paying it. The 35-54bps that bled 8/8 live
        # trades IS this exit leg. If it does not fill it expires (order
        # timeout) and escalates into the existing marketable ladder below
        # (attempt>=1), so nothing gets trapped. RISK exits stay marketable-
        # first: hard stops, faults, derisk, hedge unwind, AND protective
        # floor/trail/BE closes (which carry tier_fired>0 for bookkeeping but
        # are risk-off, so profit_take is False) - being out fast beats the
        # spread. Requires a live two-sided book; degrades to marketable if
        # the touch is missing.
        maker_first = bool(self.maker_first_profit_exits and profit_take
                           and attempts == 0 and bids and asks
                           and not go_market)
        if pos.direction == "long":
            side = "sell"
            if maker_first:
                price = asks[0][0]                 # rest at the ask (maker)
            else:
                touch = bids[0][0] if bids else mark
                price = touch * (1 - slip_pct / 100.0)
        else:
            side = "buy"
            if maker_first:
                price = bids[0][0]                 # rest at the bid (maker)
            else:
                touch = asks[0][0] if asks else mark
                price = touch * (1 + slip_pct / 100.0)
        if not (isinstance(price, (int, float)) and math.isfinite(price)
                and price > 0):
            # TOTAL feed poisoning (29f): a NaN touch/mark walks into a NaN
            # limit price, and with no valid reference the firewall rejects
            # the exit outright (FW_INVALID_PRICE) - even at the MARKET
            # rung, whose price is advisory. An exit must never be
            # rejectable for its price: fall back mark -> ref -> entry. A
            # stale anchor on a limit is survivable (timeout -> ladder ->
            # market); a rejected exit is a standing block on the escape.
            _fallback = next((float(x) for x in (mark, ref, pos.entry_price)
                              if isinstance(x, (int, float))
                              and math.isfinite(x) and x > 0),
                             float(pos.entry_price))
            log.warning(f"exit price non-finite for {pos.symbol} - "
                        f"substituting {_fallback:.10g} (feed poisoned)")
            price = _fallback
        size = pos.size * close_pct / 100.0
        if size <= EPS:
            return
        if omin > 0 and size < omin:
            # a dust SLICE with a viable remainder: close the whole
            # position instead of leaving an unexitable stub behind
            log.info(f"exit slice {size:.8f} {pos.symbol} below venue "
                     f"minimum {omin} - escalating to full close")
            close_pct, size = 100.0, pos.size
        # F6 Rule 534 self-cross guard: BEFORE any marketable (non-
        # post_only) sell on this pair, cancel our own resting long-book
        # entry bid first (see _clear_long_book_bid_before_sell). No-op
        # for a maker_first post_only rest, and for a buy-side exit.
        # getattr-guarded: unit tests exercise this off a minimal stub
        # self (SimpleNamespace) that may not define the guard method at
        # all - the same pattern as _record_probe_admission elsewhere.
        _lb_guard = getattr(self, "_clear_long_book_bid_before_sell", None)
        if callable(_lb_guard):
            _lb_guard(asset, side, maker_first, reason=reason,
                      reason_code=reason_code)
        order = self.orders.submit(
            asset=asset, symbol=pos.symbol, pair=self.kraken.kraken_pair(pos.symbol),
            side=side, price=price, size=size, purpose="exit",
            position_id=pos.position_id, close_pct=close_pct,
            post_only=maker_first,
            ordertype="market" if go_market else "limit",
            # ref may be None BY DESIGN (see EX-6 above: the firewall lets
            # exits through uncollared on a missing reference)
            ref_price=ref, equity=self._equity(),  # type: ignore[arg-type]
            book=book, sigma_bar_pct=self.vol.state(asset).sigma_bar_pct,
            meta={"reason": reason, "attempt": attempts + 1,
                  "tier_fired": int(tier_fired),
                  "reason_code": reason_code},
            now=now,
        )
        if order is None:
            # Rejected orders STILL climb the ladder (29f): an attempt was
            # made, and skipping the counter froze the ladder at rung 0 for
            # as long as the rejection cause persisted - the MARKET rung
            # stayed unreachable exactly when the feed was at its worst
            # (invariant #5: exits are ALWAYS allowed). Counting reaches
            # go_market, whose finite-price fallback above cannot be
            # rejected for price.
            self._exit_attempts[pos.position_id] = attempts + 1
            return
        self._exit_attempts[pos.position_id] = attempts + 1
        if attempts > 0 or go_market:
            log.warning(f"exit ESCALATION {pos.symbol} attempt "
                        f"{attempts + 1}: slip cap {slip_pct:.2f}%"
                        f"{' -> MARKET' if go_market else ''} ({reason})")
        else:
            log.info(f"exit {close_pct:.0f}% of {pos.symbol} ({reason})")

    def _clear_long_book_bid_before_sell(self, asset: str, side: str,
                                         post_only: bool, *, reason: str,
                                         reason_code: str = "") -> None:
        """Rule 534 self-cross guard (market-conduct pass, F6). Mechanics:
        a long-horizon book bid rests up to order_ttl_hours at ~0.5-0.85%
        below mark (risk/long_book.py); a MARKETABLE sell on the SAME pair
        (the risk-off exit escalation ladder in `_submit_exit`, or a
        marketable short-entry/hedge-open sell) can walk down through the
        book far enough to trade against our OWN resting bid - a literal
        self-fill, or the venue's self-trade-prevention (STP) cancelling
        the escape leg this guard exists to protect instead of the entry.

        Cancel-FIRST: find and cancel this asset's resting long-book entry
        bid (meta book=="long", purpose=="entry" - `_long_book_open_orders`)
        BEFORE the marketable sell is submitted, so the sell is never
        delayed by it. Cancel failure (or any exception raised looking up
        / cancelling the resting order) is logged and swallowed - the sell
        this guards must never be blocked or slowed by it; the venue's own
        STP remains the backstop for the residual race between this check
        and the sell actually landing on the book.

        A no-op unless `side == "sell"` (a buy can never cross a resting
        BID) and the sell is NOT post_only - a resting post_only ask can
        never cross the book either, so passive-passive same-pair quoting
        (a resting long-book bid alongside a resting maker exit ask) is
        bona fide two-sided market making, not the wash-trade pattern
        Rule 534 targets."""
        if side != "sell" or post_only:
            return
        try:
            resting = next((o for o in self._long_book_open_orders()
                            if o.asset == asset), None)
            if resting is None:
                return
            detail = tag(Code.LB_BID_CLEARED,
                        f"{asset}: own resting long-book bid cancelled "
                        f"ahead of a marketable sell ({reason})")
            self.orders.cancel_order(resting, reason=detail)
            get_audit().log(
                "long_book", Code.LB_BID_CLEARED, detail,
                {"asset": asset, "bid_price": resting.price,
                 "reason": reason, "reason_code": reason_code})
        except Exception:
            log.exception(f"{asset}: long-book bid cancel-before-sell "
                          f"guard raised - proceeding with the sell "
                          f"uncancelled (venue STP is the backstop)")

    # ------------------------------------------------------------------
    # FAST cycle
    # ------------------------------------------------------------------
    def fast_cycle(self, now: float) -> None:
        if getattr(self, "_last_entry_admit_ts", None) is None:
            # W2-18: seed the ML-073 drought clock from the first now this
            # engine ever actually sees (replay parity) rather than
            # time.time() at construction; a restore already set a
            # concrete float before the first cycle, so this never fires
            # after a restart with continuity data. getattr-guarded: test
            # doubles built via LiquidityBot.__new__() may never have set
            # this attribute at all - that is the same "unseeded" case.
            self._last_entry_admit_ts = now
        # marks + books from the execution venue; every mark passes the
        # tick quarantine so one anomalous print can't fire every stop.
        # Marks fetch in ONE batched Ticker call (6 pairs -> 1 request)
        # rather than per-pair, cutting fast-cycle Kraken round-trips; the
        # per-pair book (Depth is single-pair only) still loops below.
        pair_of = self._pair_of                  # precomputed in __init__
        # tick quarantine holds stops for EXACTLY one cycle (the watchdog's
        # documented contract). Without this reset the False flag LATCHED
        # when the feed died right after a quarantined tick — the hard stop
        # never re-evaluated through the whole outage (audit EX-2
        # 2026-07-17). Mark FRESHNESS separately gates decisions whenever
        # no new data arrives, so the reset never runs stops on stale data.
        if self._stop_ok:
            self._stop_ok = dict.fromkeys(self._stop_ok, True)
        marks = self.kraken.get_tickers(self._pair_list)
        # Books stay a SERIAL loop: measured live, parallelizing the 6 fetches
        # saved ~0ms (serial 2004ms vs parallel 2014ms) because the Kraken 3/s
        # rate limit is the binding constraint - concurrency can't beat a wall
        # you're rate-limited against. Under a rate limit only cutting call
        # COUNT helps (see the batched ticker above); the push-based websocket
        # feed is what actually removes these calls. Not worth threads on the
        # stop-feeding hot path for no gain.
        for asset, symbol in self.symbol_map.items():
            pair = pair_of[asset]
            px = marks.get(pair)
            if px:
                mark, stop_ok = self.watchdog.filter_mark(asset, px)
                self.marks[symbol] = mark
                self._mark_ts[symbol] = now      # mark freshness (TH-freeze)
                self._stamp_mark_wall(symbol)    # telemetry only
                self._stop_ok[asset] = stop_ok
            # push-based Kraken book first (sub-second, keyed by REST pair);
            # None means disabled/stale/down -> REST, the source of truth
            book = None
            if self.kraken_ws is not None:
                try:
                    book = self.kraken_ws.get_order_book(pair)
                except Exception:
                    book = None
            if book is None:
                book = self.kraken.get_order_book(pair)
            # feed-integrity signal: book is None when missing OR sanitize-
            # rejected (crossed/poisoned). THALES treats a sustained bad rate
            # per asset as an unreliable-venue shade (TH-014).
            self.thales.observe_feed_health(asset, book is not None, now)
            if book:
                self.kraken_books[asset] = book
                # 42a: stamp DATA time, not look time. recv_ts is the
                # feed's own receive stamp (ws cache write / REST parse
                # wall clock; replay reproduces it verbatim from the
                # recording). Books without it - older recordings, test
                # stub books - keep the legacy cycle-`now` stamp, byte-
                # identical to the pre-42a behavior. This is what makes
                # the pre-trade staleness veto (PT-020) and the DL-10
                # absent-book gate measure something real: previously
                # book_ts was re-stamped with the same cycle-frozen `now`
                # it was later compared against, so both read ~0 forever.
                self.book_ts[asset] = float(book.get("recv_ts") or now)
                self.thales.observe_fast(asset, book,
                                         self.marks.get(symbol, 0.0), now)
                # MARK FRESHNESS: the batched Ticker can silently stop returning
                # a price for one pair while its Depth book stays live (the two
                # are separate calls). Without this the mark FREEZES at its last
                # value while book_ts still reads fresh — so every stop/exit runs
                # on a stale price and the watchdog (which only inspects book_ts)
                # never sees it. When the ticker didn't refresh the mark this
                # cycle, derive it from the FRESH book mid so the hot path always
                # runs on a current price whenever ANY venue source is live.
                if not px:
                    bids, asks = book.get("bids") or [], book.get("asks") or []
                    if bids and asks:
                        mid = 0.5 * (bids[0][0] + asks[0][0])
                        if mid > 0:
                            m, ok = self.watchdog.filter_mark(asset, mid)
                            self.marks[symbol] = m
                            self._mark_ts[symbol] = now
                            self._stamp_mark_wall(symbol)
                            self._stop_ok[asset] = ok

        # execution algos: release due child slices (paced). ISOLATED, like
        # every pre-stop stage below, so a raise here cannot skip the
        # per-position stop loop at the bottom of this cycle (invariant #5).
        try:
            self._step_exec_algos(now)
        except Exception:
            self._exit_eval_failures += 1
            log.exception("_step_exec_algos raised - isolated; stop loop still runs")

        try:
            self._apply_sim()   # sim overlays AFTER fresh data lands
        except Exception:
            self._exit_eval_failures += 1
            log.exception("_apply_sim raised - isolated; stop loop still runs")

        # advance orders, apply fills
        sig = {a: self.vol.state(a).sigma_bar_pct for a in self.symbol_map}
        try:
            fills = self.orders.poll(self.kraken_books, sig, now)
        except Exception:
            fills = []
            self._exit_eval_failures += 1
            log.exception("orders.poll raised - isolated; stop loop still runs")
        # Apply each fill under its OWN guard (W1-2). orders.poll has already
        # advanced order state and drained deferred events before returning, so
        # a raise in _handle_fill on event i must NOT discard events i+1..n
        # (book/venue desync; a dry-run fill lost permanently) nor skip the
        # post-batch snapshot. One bad event is counted + tagged (OM-070), the
        # rest are still applied, and the snapshot below ALWAYS runs.
        for event in fills:
            try:
                self._handle_fill(event, now)
            except Exception:
                self._exit_eval_failures += 1
                log.exception("%s", tag(
                    Code.OM_FILL_APPLY_FAILED,
                    "fill application raised for one poll event - the rest of "
                    "the batch is still applied and snapshotted"))
        if fills:
            self.store.snapshot(self)      # never lose an executed fill

        self._close_periods(now)
        equity = self._equity()
        # A held mark is TRUSTED for equity/liquidation math only when it is
        # both (a) jump-CONFIRMED — not a quarantined >tick_jump_pct fat-finger
        # print — and (b) FRESH — refreshed by the ticker or the book mid within
        # mark_stale_sec. An untrusted mark must not ratchet the peak equity
        # high-water (a spike would persist a fake peak that reads as a huge
        # fabricated drawdown) nor trip the catastrophe hard-stop into a
        # full-book liquidation off a price that never held or has gone dark.
        # Both defer until the mark is trusted again; the per-position protective
        # stop below (an ESCAPE) never defers — it runs on the best mark there is.
        marks_confirmed = all(
            self._stop_ok.get(self._asset_of(p.symbol), True)
            and self._mark_fresh(p.symbol, now)
            for p in self.state.open_positions())
        if marks_confirmed:
            self.state.note_equity(equity)  # ratchet peak MTM equity for drawdown

        # tail-event sentry: staleness / divergence / pnl velocity
        kraken_mids = {}
        for a, b in self.kraken_books.items():
            bids, asks = b.get("bids") or [], b.get("asks") or []
            if bids and asks:
                kraken_mids[a] = 0.5 * (bids[0][0] + asks[0][0])
        fvs = {a: (self.fv.state(a).fair_value or 0.0)
               for a in self.symbol_map}
        try:
            self.watchdog.evaluate(
                now, self.book_ts, list(self.symbol_map), kraken_mids, fvs,
                equity, self.state.open_position_count(), self.dry_run)
        except Exception:
            self._exit_eval_failures += 1
            # W2-27: isolating the raise must not fail the ENTRIES side
            # OPEN on the frozen prior state - evaluate() only assigns
            # self.state at its end, so a raise partway through never
            # reassigns it. Force entries_blocked for as long as evaluate()
            # keeps failing; exits below never consult this flag.
            self.watchdog.note_evaluation_failure(
                "watchdog.evaluate raised - entries forced closed pending recovery")
            log.exception("watchdog.evaluate raised - isolated; stop loop still "
                          "runs, entries forced closed for this cycle")

        # the TRIGGER stays gated on all-marks-confirmed (a quarantined or
        # stale print must never fabricate the drawdown that liquidates the
        # book), but once LATCHED the flatten retries every cycle regardless
        # (EX-3: a single dark symbol used to stall the whole catastrophe
        # flatten AND the halt latch until every mark recovered)
        if ((marks_confirmed
             and self.capital.hard_stop_triggered(self.state, equity))
                or self._halted):
            if not self._halted:
                log.critical("HARD STOP drawdown breached - flattening, no new risk")
                self._halted = True
                fm = getattr(self, "fault", None)
                if fm is not None:
                    fm.latch("hard_stop_drawdown", Severity.CRITICAL,
                             "catastrophe drawdown hard-stop: flatten-and-stop")
            # emergency flatten: isolate per position so one that errors on
            # exit submission cannot leave the REST of the book unflattened.
            # Per-position mark gate: flatten every position whose OWN mark
            # is trusted; a dark symbol defers (never liquidate off a
            # phantom print), retries next cycle, and its protective stop
            # below still manages it in the meantime.
            for pos in list(self.state.open_positions()):
                try:
                    if not (self._stop_ok.get(self._asset_of(pos.symbol), True)
                            and self._mark_fresh(pos.symbol, now)):
                        continue
                    self._submit_exit(pos, 100.0, "hard stop", now=now)
                except Exception:
                    self._exit_eval_failures += 1
                    log.exception("[%s] hard-stop flatten raised - flattening "
                                  "the rest of the book", pos.symbol)
            if marks_confirmed:
                return
            # some marks are dark: fall through so the protective-stop loop
            # (an ESCAPE that runs on the best mark there is) still manages
            # the deferred positions this cycle

        macro_states = {a: self.macro.state(a) for a in self.symbol_map}

        # postmortem / mark-out / risk observation, each stage ISOLATED so a
        # raise cannot skip the per-position stops that follow (invariant #5).
        # Split into a helper to keep fast_cycle under the C901 ceiling.
        self._fast_cycle_observe(now, equity)

        # Each position's stop/tier evaluation is ISOLATED: one position whose
        # state deterministically raises (a corrupt stop_price, a bad
        # vol.state, a tier-engine edge) must never abort the loop and leave
        # every LATER position's hard stop unevaluated — that is exactly the
        # "exits silently blocked" condition invariant #5 forbids. A raise is
        # counted, logged loudly, and the next position is still managed.
        for pos in list(self.state.open_positions()):
            try:
                self._manage_open_position(pos, now, equity, macro_states)
            except Exception:
                self._exit_eval_failures += 1
                log.exception("[%s] stop/tier evaluation raised - other "
                              "positions still managed this cycle", pos.symbol)

        # 3) inventory derisk (hard caps, stale losers). Same trusted-mark gate:
        # a fat-finger OR stale mark can push inventory_ratio over a hard cap or
        # trip a stale-loser threshold, fabricating a forced reduction off a
        # price that never held or has gone dark. Skip that asset until its mark
        # is trusted again; a real breach re-fires on the confirmed fresh tick.
        # Isolated from the stop loop AND the hedge block: a derisk failure
        # must not skip hedging or wedge the cycle. The action LIST is built
        # under a guard (a bad generator can't skip hedging), and EACH action
        # is isolated too (review A1-F4) so one position erroring on its forced
        # reduction can't starve the OTHER positions' derisk this cycle — the
        # same per-position isolation the protective-stop loop already has.
        try:
            derisk_actions = list(self.inventory.derisk_actions(
                self.state, self.marks, equity, macro_states, now))
        except Exception:
            derisk_actions = []
            self._exit_eval_failures += 1
            log.exception("inventory derisk_actions() raised - hedging still runs")
        for act in derisk_actions:
            try:
                pos = self.state.get_position(act.position_id)
                if pos and self._stop_ok.get(self._asset_of(pos.symbol), True) \
                        and self._mark_fresh(pos.symbol, now):
                    self._submit_exit(pos, act.close_pct, act.reason, now=now)
            except Exception:
                self._exit_eval_failures += 1
                log.exception("derisk action raised - other positions still "
                              "derisked this cycle")

        # 4) hedging
        self._run_hedge_pass(now, equity)

    def _run_hedge_pass(self, now: float, equity: float) -> None:
        """Hedge/unwind/trim actions, isolated so a hedge-engine error cannot
        wedge fast_cycle (the stop loop already ran above)."""
        try:
            self._hedge_actions(now, equity)
        except Exception:
            self._exit_eval_failures += 1
            log.exception("hedge pass raised - isolated, cycle continues")

    def _hedge_actions(self, now: float, equity: float) -> None:
        for act in self.hedger.evaluate(self.state, self.marks, equity,
                                        self.corr.state, now=now):
            if act.kind == "unwind":
                pos = self.state.get_position(act.position_id)
                if pos:
                    self._submit_exit(pos, 100.0,
                                      f"hedge unwind: {act.reason}", now=now)
            elif act.kind == "trim":
                # net-delta reduction by shrinking a held position instead of
                # opening the offsetting hedge (same delta, half the fees)
                pos = self.state.get_position(act.position_id)
                if pos:
                    px = self.marks.get(pos.symbol) or pos.entry_price
                    pos_usd = pos.size * px
                    if pos_usd > EPS:
                        pct = min(100.0, act.usd / pos_usd * 100.0)
                        self._submit_exit(pos, pct,
                                          f"hedge trim: {act.reason}", now=now)
            elif act.kind == "open" and not self.orders.has_open(act.asset, "hedge") \
                    and self._live_order_allowed("hedge"):
                # A hedge OPEN is NEW risk (invariant #5): hold it to the
                # exact bar entries clear, not the looser bar unwind/trim
                # (risk REDUCTION, never gated) get above. Freshness first -
                # a frozen mark on the symbol being hedged must never price
                # or size a live order (mirrors the tier/derisk/equity-peak
                # trusted-mark gate) - then every new-risk authority entries
                # consult: the operator kill switch, the watchdog data-
                # quality block, and the fault manager/halt (DEGRADED/HALTED
                # refuses new risk; the entries gate's exact expression).
                fm = getattr(self, "fault", None)
                if not (self._mark_fresh(act.symbol, now)
                        and self._stop_ok.get(act.asset, True)) \
                        or not self.entries_enabled \
                        or self.watchdog.state.entries_blocked \
                        or self._halted \
                        or (fm is not None and not fm.allow_new_risk()):
                    log.info(tag(Code.HG_OPEN_BLOCKED,
                                f"{act.symbol} hedge open blocked: stale "
                                f"mark or new-risk gate closed ({act.reason})"))
                    continue
                px = self.marks.get(act.symbol)
                book = self.kraken_books.get(act.asset) or {}
                if not px:
                    continue
                side = "buy" if act.direction == "long" else "sell"
                touch = ((book.get("asks") or [[px, 0]])[0][0] if side == "buy"
                        else (book.get("bids") or [[px, 0]])[0][0])
                price = touch * (1 + self.max_slip_pct / 100.0) if side == "buy" \
                    else touch * (1 - self.max_slip_pct / 100.0)
                # F6 Rule 534 self-cross guard: a hedge OPEN that sells
                # (a short hedge) is marketable (post_only=False below) -
                # cancel our own resting long-book bid on this pair first.
                # getattr-guarded, same reason as the _submit_exit call
                # site above (minimal test doubles for `self`).
                _lb_guard = getattr(self, "_clear_long_book_bid_before_sell",
                                    None)
                if callable(_lb_guard):
                    _lb_guard(act.asset, side, False,
                             reason=f"hedge open: {act.reason}")
                self.orders.submit(
                    asset=act.asset, symbol=act.symbol,
                    pair=self.kraken.kraken_pair(act.symbol), side=side,
                    price=price, size=act.usd / px, purpose="hedge",
                    post_only=False, book=book, ref_price=px, equity=equity,
                    sigma_bar_pct=self.vol.state(act.asset).sigma_bar_pct,
                    meta={"reason": act.reason},
                    now=now,
                )
                log.info(f"HEDGE {act.direction} ${act.usd:,.0f} {act.symbol}: "
                        f"{act.reason}")

    def _fast_cycle_observe(self, now: float, equity: float) -> None:
        """Post-fill observation: mark trails, mark-out horizons, risk-protocol
        telemetry, and elapsed-thesis close scoring. Runs AFTER fills and BEFORE
        the per-position stop loop; every stage is isolated (counted into
        _exit_eval_failures, logged) so a raise here can never starve the stops
        that follow (invariant #5). Extracted from fast_cycle to hold the C901
        complexity ceiling; ordering and behaviour are otherwise unchanged."""
        try:
            self.postmortem.record_marks(self.marks, now)
        except Exception:
            self._exit_eval_failures += 1
            log.exception("postmortem.record_marks raised - isolated; stop loop still runs")
        # post-fill mark-out resolves due horizons against the TRUSTED mark
        # (jump-confirmed + fresh); a stale/dark feed defers, never fabricates.
        _mk = getattr(self, "markout", None)
        if _mk is not None:
            try:
                _mk.poll(self.marks, now, is_fresh=self._mark_fresh)
            except Exception:
                self._exit_eval_failures += 1
                log.exception("markout.poll raised - isolated; stop loop still runs")
        try:
            self.risk_protocols.observe(equity, self.marks, now)
        except Exception:
            self._exit_eval_failures += 1
            log.exception("risk_protocols.observe raised - isolated; stop loop still runs")
        try:
            for cause, thesis in self.postmortem.poll(now):
                won = int(thesis.realized_net_usd > 0)
                self.monitor.record_close(self._thesis_scored_p(thesis),
                                        won, thesis.model_scored, cause,
                                        now=now)
                # ML-075: while KILLED the close above is model_scored=False, so
                # the recovery window can never refill. Feed the champion's
                # telemetry-only shadow score (captured at entry) so a killed
                # model can re-arm on evidence. No-op when armed / no shadow.
                if not thesis.model_scored and getattr(thesis, "shadow_p", -1.0) >= 0.0:
                    self.monitor.record_shadow_close(thesis.shadow_p, won)
        except Exception:
            self._exit_eval_failures += 1
            log.exception("postmortem.poll/record_close raised - isolated; "
                          "stop loop still runs")

    def _manage_open_position(self, pos: Position, now: float, equity: float,
                              macro_states: dict) -> None:
        """Stop + profit-tier management for ONE open position. Called inside a
        per-position guard in fast_cycle so a single position that errors can
        never starve the OTHER positions' hard stops (invariant #5). Behaviour
        is identical to the former inline loop body; `continue` became `return`
        (single-position scope)."""
        symbol = pos.symbol
        px = self.marks.get(symbol)
        if not px:
            return
        asset = self._asset_of(symbol)

        # 1) hard protective stop (v2: enforced every cycle).
        # (exits are always allowed - invariant 5 - and this branch runs
        # unconditionally, before the tier engine below is even consulted;
        # the PT-060 reclamp-sliver suppression added below is scoped to
        # the tier-engine branch ONLY and can never reach here.)
        # A quarantined tick (single anomalous print) holds stop
        # evaluation for exactly one cycle; confirmation fires it.
        if pos.stop_price and self._stop_ok.get(asset, True) and (
                (pos.direction == "long" and px <= pos.stop_price) or
                (pos.direction == "short" and px >= pos.stop_price)):
            self._stop_hit[pos.position_id] = True
            # geometry-alignment T5 (spec D1): for a bracket position,
            # pos.stop_price IS the sl leg (entry*(1-/+sl_frac), stamped
            # at fill time - see _handle_fill) - the reason threads
            # VERBATIM into the live-label barrier column so this close
            # joins LABEL_ERA_TRIPLE_BARRIER (ml/history.py label_era_of),
            # not the legacy "stop $X hit" string.
            reason = "tb_sl" if pos.bracket_sl_frac > EPS else \
                f"stop {self._px(pos.symbol, pos.stop_price)} hit"
            self._submit_exit(pos, 100.0, reason, now=now,
                              # Compounder Phase C (task C4): this same
                              # unconditional stop check enforces the long
                              # book's thesis stop too (pos.stop_price is
                              # set to thesis_stop_price(...) at fill time
                              # for book=="long" - see _handle_fill), so
                              # LB-031 (structural invalidation) is coded
                              # here rather than duplicating this branch.
                              reason_code=(Code.LB_THESIS_INVALIDATED.value
                                          if pos.book == "long" else ""))
            return

        # 2) profit tiers, scaled by regime + inventory pressure. Gated on a
        # TRUSTED mark — jump-confirmed AND fresh: the tier engine ratchets
        # pos.high_water and the give-back/chandelier stop from `px`, so a
        # fat-finger OR a stale/frozen mark would (a) corrupt persisted
        # high_water and (b) fabricate a give-back/trail exit off a price
        # that never held or has gone dark. Deferring a profit-take (never
        # an escape) until the mark is trusted is always safe.
        if not pos.is_hedge and self._stop_ok.get(asset, True) \
                and self._mark_fresh(symbol, now):
            # Compounder Phase C (task C4): a long-book position is
            # evaluated by the LONG tier engine instance (its own
            # long_book.profit_taking geometry - wider, absolute-pct,
            # never regime-scaled) instead of the 5m per-regime-scaled
            # engine below. The 5m branch (else:) is untouched byte-for-
            # byte - a completely separate branch, not a refactor of it.
            if pos.book == "long":
                inv_ratio = abs(self.inventory.inventory_ratio(
                    self.state, asset, self.marks, equity))
                action = self.long_tier_engine.evaluate(
                    pos, px,
                    sigma_bar_pct=self._measured_sigma(asset),
                    # no 5m signal exists for this book's thesis - unknown
                    # stays None (no-op), same convention the tier engine
                    # itself uses for "no fresh evaluation"
                    signal_alive=None,
                    inventory_pressure=min(inv_ratio, 1.0),
                    now=now)
            else:
                scale = macro_states[asset].playbook.get("tier_scale", 1.0)
                inv_ratio = abs(self.inventory.inventory_ratio(
                    self.state, asset, self.marks, equity))
                if inv_ratio >= self.inventory.soft_cap_pct / self.inventory.hard_cap_pct:
                    scale *= 0.75          # bleed inventory down sooner
                # is the ENTRY signal still confirmed in this direction?
                # None (no fresh evaluation) must stay None - only a
                # definitive "not confirmed" may tighten the runner leash
                sig_snap = self.last_signals.get(asset)
                signal_alive = None
                if sig_snap and (now - float(sig_snap.get("ts", 0.0))) < 180.0:
                    signal_alive = bool(sig_snap.get("confirmed")) and \
                        sig_snap.get("direction") == pos.direction
                action = self._tier_engine(scale).evaluate(
                    pos, px,
                    sigma_bar_pct=self._measured_sigma(asset),
                    signal_alive=signal_alive,
                    inventory_pressure=min(inv_ratio, 1.0),
                    # EX-8/DL-5: the engine's injected clock reaches the trail's
                    # time-tightening - the last wall-clock read in the exit path
                    now=now)
            # geometry-alignment T5 (spec D1): a bracket position's pt
            # leg REPLACES the tier engine's own scheduled profit-take
            # for THIS position (never both - "the traded bet is the
            # labeled bet"). The tier engine above is still called
            # UNCONDITIONALLY (never skipped) so its give-back ratchet -
            # a SENIOR overlay, not a scheduled tier (CLAUDE.md
            # invariant 5: overlays stay senior) - keeps ratcheting
            # pos.high_water/trailing_stop_price and can still fire
            # exactly as it does for a non-bracket position; only a TIER
            # TRIGGER (is_profit_take) is suppressed here, because the
            # bracket's own pt leg below owns that disposition instead.
            # 2026-07-29 PT-060 WEDGE CORRECTION (live incident, LINK
            # 3ea2a851): spec D1 originally suppressed the PT-060
            # time-stop here too, handing "give up on a stale thesis" to
            # the bracket deadline leg (ml.label_max_bars = 96 bars).
            # Measured live, that re-opened the exact bleed class PT-060
            # was shipped to kill (P2, 2026-07-23: no-progress cohort
            # MFE 0.16% / MAE -1.44%, recovered 0/17): a no-progress
            # probe (MFE 0.18%) sat wedged for hours - PT-060 due at 36
            # bars, deadline not due until 96 - and closed -1.69% where
            # the scratch would have taken ~-0.2%. The time-stop is a
            # PROTECTIVE overlay (loss-avoidance evidence, not a
            # scheduled take), so it now stays senior to the bracket
            # exactly like the give-back ratchet; its close lands
            # barrier="realized" like every other overlay close (never
            # tb_*), and the candidate twin still supplies the tb label,
            # so the labeled bet is untouched. (T5 review MINOR-4
            # correction: the
            # chandelier trail - trailing_stop.activate_after_tier,
            # default 2 - and the break-even floor - be_after_tier,
            # default 1 - are both TIER-PROGRESS-gated
            # (position.tier_closed >= that threshold) inside
            # ProfitTierEngine._exit_floor_hit. tier_closed never
            # advances on a bracket position (the scheduled take that
            # would advance it is always suppressed here), so those two
            # never actually arm on a bracket position by design - "the
            # labeled bet has no trail/BE". The give-back floor (armed
            # off the PEAK move, not tier progress) and the hard stop
            # above are the only overlays that actually live here.)
            is_bracket = pos.book != "long" and pos.bracket_pt_frac > EPS
            bracket_exit_pending = is_bracket
            if action.should_close_partial and action.close_pct > 0:
                is_time_stop = action.reason_code == Code.PT_TIME_STOP.value
                # 2026-07-29 wedge correction (see the block comment
                # above): PT-060 is deliberately NOT in this suppression
                # - only the scheduled profit-take defers to the bracket.
                suppressed_for_bracket = is_bracket and action.is_profit_take
                # sub-25s reclamp sliver (whole-program review Minor #6): a
                # resting maker tier-1 take on a still-virgin position
                # (tier_closed increments on FILL, not on submit) can be
                # preempted by PT-060 if a vol spike reclamps the tier-1
                # trigger during the submission-to-fill window - the tier
                # engine can't see this (tier_closed reads 0 either way);
                # the ORDER BOOK can. Suppressed for exactly one cycle: a
                # resting take that dies unfilled lets the time-stop fire
                # at the next evaluation. Scoped to the PT-060 branch ONLY
                # - every other exit (hard stop above, floor/trail/give-
                # back below) is untouched; exits stay always-allowed.
                # (Wave-4/5 verify note: during this single <=25s deferral
                # window a give-back floor crossing is also unseen, because
                # evaluate() early-returned at the time-stop before its own
                # _exit_floor_hit - a vol-reclamp corner bounded to one
                # maker rest; the hard protective stop above stays live.)
                suppress_pt060 = is_time_stop and \
                    self._has_resting_profit_take(pos)
                if not suppressed_for_bracket and not suppress_pt060:
                    # PT-060 review fix: a time-stop scratch previously
                    # logged as "tier trail" via the tier_fired-or-'trail'
                    # fallback (tier_fired==0 on a time-stop) - correct for
                    # a floor/trail close but wrong for a scratch. The
                    # meta["reason_code"] wiring below is unchanged; only
                    # the human-readable reason string is reason-aware.
                    reason = ("time-stop scratch" if is_time_stop
                             else f"tier {action.tier_fired or 'trail'}")
                    reason_code = action.reason_code
                    # Compounder Phase C (task C4): a long-book PROFIT-TAKE
                    # (tier fired) is coded LB-030; the 5m reason_code
                    # (action.reason_code, "" unless PT-060) is untouched.
                    if pos.book == "long" and not reason_code \
                            and action.is_profit_take:
                        reason_code = Code.LB_TIER_BANK.value
                    self._submit_exit(pos, action.close_pct, reason,
                                    tier_fired=action.tier_fired, now=now,
                                    profit_take=action.is_profit_take,
                                    reason_code=reason_code)
                    bracket_exit_pending = False
                elif suppressed_for_bracket:
                    # T5 review fix (IMPORTANT-2): ProfitTierEngine.
                    # evaluate() RETURNS EARLY on the tier-1 trigger / the
                    # PT-060 time-stop branch just suppressed above -
                    # _exit_floor_hit (the give-back floor) is never
                    # reached internally THIS cycle, so an armed floor
                    # sitting ABOVE that early-return's price (e.g. a
                    # give-back floor still above tier-1's own trigger
                    # price) would otherwise never be evaluated at all
                    # while gain stays >= the suppressed trigger - an
                    # armed floor crossing produces NO exit in that band
                    # (reviewer-demonstrated: entry 100, floor armable at
                    # 102, px 101.5 -> no exit, pre-fix). high_water was
                    # already updated THIS cycle by evaluate()'s own
                    # _update_high_water call at its top (unconditional,
                    # runs before the early return), so calling the SAME
                    # engine instance's _exit_floor_hit here sees the
                    # current peak and reuses its exact math (never a
                    # duplicate). The reason string matches exactly what
                    # a non-occluded floor-hit would have produced
                    # ("tier trail" - pos.tier_closed stays 0 on a
                    # bracket position, see the MINOR-4 note above) -
                    # NEVER tb_* (this is an overlay exit, not a
                    # labeled-bet disposition).
                    if self._tier_engine(scale)._exit_floor_hit(
                            pos, px,
                            sigma_bar_pct=self._measured_sigma(asset),
                            signal_alive=signal_alive, now=now):
                        self._submit_exit(
                            pos, 100.0, f"tier {pos.tier_closed or 'trail'}",
                            tier_fired=pos.tier_closed, now=now,
                            profit_take=False)
                        bracket_exit_pending = False
            if bracket_exit_pending:
                self._evaluate_bracket_exit(pos, px, now)

    def _evaluate_bracket_exit(self, pos: Position, px: float,
                              now: float) -> None:
        """pt/deadline legs of a model-lane bracket position's exit
        geometry (geometry-alignment T5, spec D1). The sl leg is NOT
        duplicated here - it reuses the existing hard protective-stop
        check at the top of _manage_open_position (pos.stop_price was
        stamped to entry*(1-/+bracket_sl_frac) at fill time, see
        _handle_fill). Called only when the tier engine's own action did
        not already submit an exit this cycle - the give-back floor (a
        senior overlay; T5 review MINOR-4: chandelier/break-even are
        tier-progress-gated and never arm on a bracket position, see
        _manage_open_position's own comment) always gets first refusal
        (invariant 5)."""
        if pos.direction == "long":
            hit = px >= pos.entry_price * (1.0 + pos.bracket_pt_frac)
        else:
            hit = px <= pos.entry_price * (1.0 - pos.bracket_pt_frac)
        if hit:
            # maker-first profit exit (spec D1): profit_take=True gives
            # this its own first-attempt rest on our own side of the book
            # (_submit_exit's maker_first gate), same as a legacy tier
            # take - escalates into the marketable ladder if it expires.
            self._submit_exit(pos, 100.0, "tb_pt", now=now,
                              profit_take=True)
            return
        if pos.bracket_deadline_ts > EPS and now >= pos.bracket_deadline_ts:
            # vertical barrier: an aging bracket gets no special leniency
            # (marketable-first, like the legacy time-stop scratch it
            # replaces for this position) - being out fast beats holding
            # a thesis whose label horizon has already expired.
            self._submit_exit(pos, 100.0, "tb_time", now=now)

    def _has_resting_profit_take(self, pos: Position) -> bool:
        """True iff `pos` already has an OPEN resting (post-only) profit-
        take exit order working. _submit_exit's maker-first leg is the
        ONLY path that ever posts an exit order with post_only=True -
        every risk-off exit (hard stop, fault, derisk, hedge unwind,
        protective floor/trail/BE) stays marketable-first by construction
        (see _submit_exit's maker_first gate). So an open exit order for
        this position with post_only=True IS, by construction, a resting
        profit-take - no new state needed (P2 review Minor #6, sub-25s
        reclamp sliver)."""
        return any(o.purpose == "exit" and o.position_id == pos.position_id
                  and o.post_only for o in self.orders.open_orders())

    # ------------------------------------------------------------------
    # SLOW cycle - data refresh + entry pipeline
    # ------------------------------------------------------------------
    def _explore_aggressive_eligible(self, model_p: float, manip: float,
                                     regime_label: str) -> bool:
        """Conditions (excluding the random roll) for a FULL-conviction
        aggressive exploration trade: the model is reasonably confident, the
        book is clean (low manip suspicion), and it is not a crisis regime.
        The caller only reaches this in dry-run exploration, and the trade is
        still bounded by every risk-stack veto + the manip gate + kelly_cap."""
        return (self._explore_aggr_enabled
                and model_p >= self._explore_aggr_min_p
                and manip <= self._explore_aggr_max_manip
                and regime_label != "crisis")

    def _live_label_count(self) -> int:
        """Live (real closed-trade) row count the corpus has actually
        accrued - the SAME basis _exploration_active / ML-071 / ML-073 /
        the P3 probe throttle all graduate/decay on. The corpus is
        dominated by candidate (triple-barrier PROXY) labels, so counting
        all rows once retired exploration at 1370 total while only ~35
        real fill outcomes existed — silently starving the model of the
        live-outcome data it actually needs (2026-07-18: OF-1 gap 0.44,
        exploration off). Falls back to total rows only when the source
        split is unavailable (legacy HistoryStore)."""
        _sc_fn: Optional[Callable[[], dict]] = getattr(
            self.history, "source_counts", None)
        _sc = _sc_fn() if callable(_sc_fn) else {}
        return _sc.get("live", 0) if _sc else self.history.row_count()

    def _exploration_active(self, now: float,
                            asset: Optional[str] = None,
                            regime_label: Optional[str] = None) -> bool:
        """True only when it is safe and useful to take a paper exploration
        trade. HARD INVARIANT: dry_run only - exploration must never influence
        a live order. Off once enough training rows have accrued (the model
        can then be trusted to gate on its own). When `asset` is given, an
        asset already holding >= max_asset_share of the labeled history is
        skipped (variety: the most active pair otherwise hogs every learning
        slot and quiet pairs never accrue fill labels). The epsilon roll
        itself is corpus-decayed (P3, probe_corpus_decay_factor) - a mature
        corpus (live_labels past corpus_target_live) admits probes at a
        scaled-down rate, floored at floor_frac so the learner keeps a
        trickle rather than starving entirely.

        `regime_label` (Task 4, #103 regime-coverage hold): the shipped P3
        decay above pools every regime into ONE live-label count, but a
        diagnostic found 227/234 live-labeled rows in a SINGLE regime
        (range) with bear at 4 - a mature GLOBAL corpus says nothing about
        an under-covered regime. When `regime_label` is supplied (the
        admission site's macro_state.label - see _probe_admission_decision)
        AND regime_floor_live > 0, the decay term is instead HELD AT 1.0
        (no decay - base epsilon) whenever the CURRENT regime's own
        live-labeled count is below regime_floor_live, or the label is not
        one of the five known REGIME_LABELS (unmapped/unknown fails SAFE:
        no per-regime evidence exists for it either, so the learner still
        needs data - the SAME treatment as under-floor, never the
        opposite). `regime_label` omitted (None, the default - every
        pre-T4 caller) skips this branch entirely and reproduces the exact
        P3 decay; regime_floor_live=0 disables the term even when a label
        IS supplied (byte-identical P3 behavior either way). max_probe_share
        (the rolling share cap, _probe_share_would_deny) is NOT touched by
        this - it still bounds total probe flow regardless of regime."""
        if not self.dry_run:
            return False                        # never in live - hard-gated
        if not self.explore_enabled:
            return False
        # Honors the config key's own name (until_LIVE_rows): graduate on
        # REAL closed-trade rows, never the proxy-inflated total.
        _grad_rows = self._live_label_count()
        if _grad_rows >= self.explore_until_rows:
            return False                        # enough REAL data: trust the model
        _decay = probe_corpus_decay_factor(
            _grad_rows,
            getattr(self, "_corpus_target_live", 300),
            getattr(self, "_corpus_floor_frac", 0.25))
        _rfl = getattr(self, "_regime_floor_live", 60)
        if regime_label is not None and _rfl > 0:
            if regime_label not in REGIME_LABELS:
                _decay = 1.0                # unmapped label: fail safe, hold
            elif _regime_under_coverage_floor(
                    self.history.regime_live_count(regime_label), _rfl):
                _decay = 1.0                # under floor: hold, no decay
        _eff_epsilon = self.explore_epsilon * _decay
        if self._explore_rng.random() >= _eff_epsilon:
            return False
        if asset is not None and self.explore_max_asset_share < 1.0:
            counts = self.history.asset_counts()
            total = sum(counts.values())
            share = counts.get(asset, 0) / total \
                if total >= self.explore_share_min_rows else 0.0
            if share >= self.explore_max_asset_share:
                # TAPER, not a wall: pass with probability (1 - share). A
                # hard skip deadlocked live - when the dominant asset is
                # the ONLY one confirming, yielding the slot leaves it
                # empty and learning starves entirely (observed at $800:
                # BTC 59% share, sole signal source, zero labels). The
                # taper keeps variety pressure but can only reach zero
                # exploration at 100% share.
                if self._explore_rng.random() >= (1.0 - share):
                    log.info("[%s] exploration yielded: asset holds %d/%d "
                             "labeled rows (share %.0f%% >= cap %.0f%%; "
                             "taper passes %.0f%% of rolls)", asset,
                             counts.get(asset, 0), total, share * 100,
                             self.explore_max_asset_share * 100,
                             (1.0 - share) * 100)
                    return False
        return True

    def _drought_floor_admit(self, now: float) -> bool:
        """F0b livelock repair (grill C2 CONFIRMED): may ONE rate-bounded
        floor probe be admitted despite the share cap? True only when
        (a) the floor is enabled, (b) the ML-073 drought clock
        (_last_entry_admit_ts - engine time, set on admissions of ANY
        kind at the submit sites, seeded W2-18) shows >= drought_hours
        with zero admissions, and (c) the previous floor admission is >=
        min_spacing_hours old. Pure predicate - no side effects; the
        CALLER records the admission, and does so at DECISION time
        (unlike the normal path, which records at the submit sites):
        a floor admission's submit may still be vetoed downstream
        (min-ticket, manip, SZ-046), and recording on decision keeps the
        window honest about floor USE and self-bounds repeat fires.
        Decision-time recording has two accepted costs, both in the
        conservative (over-throttling) direction: a floor probe whose
        submit SUCCEEDS is counted twice (decision here + submit site;
        bounded to one per drought episode, since the submit resets the
        drought clock), and a drought whose floor probes keep getting
        VETOED downstream accumulates one True per spacing span, tilting
        the 40-slot window toward denial for the 40 admissions after the
        drought ends.
        Unreachable outside a drought, so non-drought behavior is
        byte-identical to P3 (test-pinned). Engine `now` only - wall
        clock here would break replay determinism."""
        if not getattr(self, "_drought_floor_enabled", False):
            return False
        last = getattr(self, "_last_entry_admit_ts", None)
        if last is None:
            return False            # clock unseeded: cannot prove a drought
        if (now - last) < getattr(self, "_drought_min_sec", float("inf")):
            return False            # entries flowed recently: no drought
        prev = getattr(self, "_last_floor_admit_ts", None)
        if prev is not None and \
                (now - prev) < getattr(self, "_floor_spacing_sec", 0.0):
            return False            # trickle bound: one per spacing span
        return True

    def _probe_share_would_deny(self) -> bool:
        """P3 rolling SHARE CAP: would admitting ONE more probe push the
        probe share - over the last probe_share_window entry ADMISSIONS
        (probes+conviction) - above max_probe_share? The denominator is
        the FIXED configured window size, never the deque's current fill,
        so a freshly-reset or partially-filled window (restart) is at
        most as permissive as a fully-populated one, never MORE
        restrictive (see __init__'s restart-state note). Admission-COUNT
        keyed, never time - deterministic under replay."""
        probes = sum(1 for p in self._probe_admissions if p)
        return (probes + 1) / self._probe_share_window > self._probe_max_share

    def _record_probe_admission(self, is_probe: bool,
                                cost: Optional[float] = None) -> None:
        """Feed one ADMITTED entry (an order actually placed, on any of the
        direct/algo/ladder entry paths) into the rolling share-cap window.
        Called for BOTH conviction (False) and probe (True) admissions -
        the share cap denominator counts every admission, not just probes.
        Self-healing (getattr, lazy-init) rather than requiring __init__:
        integration tests exercise _ladder_entry/_place_ladder directly off
        a minimal LiquidityBot.__new__() stub that never runs __init__.

        SPB-R (spec §1.4), extend-with-defaults: this IS the placement
        hook - it only fires after orders.submit succeeded - so in
        mode="budget" a probe admission additionally deducts its
        scarcity price here (`tokens -= cost`; may go negative: bounded
        debt, floor -C by construction since admission requires
        tokens > 0 and cost <= C). `cost` None (every existing caller -
        the two pinned direct/ladder `(explored)` call sites and the
        algo child hook) pops the decision-time stash via the
        `_pending_probe_asset` pointer; the pointer is only ever set by a
        PRICED admit and cleared at every budget decision, so an SZ-048
        floor probe (never priced) and any stale vetoed stash can never
        be charged. share_cap mode returns right after the deque append -
        byte-identical legacy behavior."""
        admissions = getattr(self, "_probe_admissions", None)
        if admissions is None:
            admissions = deque(maxlen=getattr(self, "_probe_share_window", 40))
            self._probe_admissions = admissions
        admissions.append(bool(is_probe))
        if getattr(self, "_probe_admission_mode", "share_cap") != "budget" \
                or not is_probe:
            return
        if cost is None:
            _pa = getattr(self, "_pending_probe_asset", None)
            if _pa is None:
                return              # floor probe / stale pointer: costs zero
            cost = self._pending_probe_cost.pop(_pa, None)
            self._pending_probe_asset = None
            if cost is None:
                return
        self._budget_tokens = \
            getattr(self, "_budget_tokens", 0.0) - float(cost)

    def _drought_floor_fire(self, now: float, asset: str) -> bool:
        """F0b (SZ-048): the caller's throttle is, by position, the binding
        denial here (_exploration_active already rolled True) - under a
        proven drought, admit ONE rate-bounded floor probe instead of
        livelocking the label stream. Recorded into the window IMMEDIATELY
        (see _drought_floor_admit's docstring for why this differs from
        the normal path). Extracted VERBATIM from the share-cap deny
        branch (SPB-R §3.4) so both admission modes share the identical
        backstop: in share_cap mode it fires when the cap binds during a
        drought; in budget mode it backstops a budget non-admit and is
        the livelock CANARY (alert-wired - it should never fire there)."""
        if not self._drought_floor_admit(now):
            return False
        detail = tag(
            Code.SZ_PROBE_FLOOR,
            f"drought floor probe {asset}: no admissions for >= "
            f"{self._drought_min_sec / 3600.0:.1f}h with the share "
            f"cap binding - one rate-bounded probe admitted")
        get_audit().log(
            "exploration", Code.SZ_PROBE_FLOOR, detail,
            {"asset": asset,
             "drought_hours": self._drought_min_sec / 3600.0,
             "spacing_hours": self._floor_spacing_sec / 3600.0})
        log.info("[%s] drought floor: probe admitted under SZ-048 "
                 "(share cap was binding, drought >= %.1fh)", asset,
                 self._drought_min_sec / 3600.0)
        self._last_floor_admit_ts = now
        self._record_probe_admission(True)
        return True

    # ------------------------------------------------------------------
    # SPB-R: scarcity-priced probe budget, refunded (mode="budget"; spec
    # docs/superpowers/specs/2026-07-30-probe-budget-spbr-design.md).
    # All timestamps engine-injected `now` only (the SZ-048 precedent -
    # wall clock here would break replay determinism); all label counts
    # LIVE labels only; every method self-heals via getattr for the
    # stub-bot test harnesses (the _record_probe_admission pattern).
    # ------------------------------------------------------------------
    @staticmethod
    def _prune_budget_events(dq, now: float, window_s: float) -> None:
        """Drop entries older than `window_s` engine-seconds. Entries are
        floats (event ts) or (ts, value) tuples - both windows are pruned
        at read AND write, never latched."""
        while dq:
            head = dq[0]
            ts = head[0] if isinstance(head, tuple) else head
            if (now - ts) <= window_s:
                break
            dq.popleft()

    def _budget_capacity(self) -> float:
        """C = tokens_per_day x burst_hours/24 (§1.2): 15 x 8/24 = 5.0
        tokens = exactly one book-fill max burst (the labeler's own 8h
        horizon)."""
        return float(getattr(self, "_budget_tokens_per_day", 15.0)) * \
            float(getattr(self, "_budget_burst_hours", 8.0)) / 24.0

    def _budget_floor_frac(self) -> float:
        """F (§1.1): scarcity_floor if set, else corpus_decay.floor_frac -
        ONE trickle-floor concept in the whole config, not two."""
        sf = getattr(self, "_budget_scarcity_floor", None)
        if sf is not None:
            return float(sf)
        return float(getattr(self, "_corpus_floor_frac", 0.25))

    def _tuition_governor_factor(self, now: float) -> float:
        """§1.5 tuition governor - a runaway BRAKE (bound, not estimator):
        X = sum of CLIPPED realized probe losses over the trailing 86400
        engine-s (fed at the _finalize_position seam, _note_probe_tuition);
        f = 1 while X <= cap, else clip(cap/X, F, 1) - scale-with-floor,
        self-redeeming as the window rolls (probation, never a life
        sentence). Transitions across 1.0 (either way) emit SZ-053; steady
        state emits nothing. The 86400 s window is the daily budget's own
        unit - deliberately NOT a knob."""
        tu = getattr(self, "_budget_tuition", None)
        if tu is None:
            return 1.0
        self._prune_budget_events(tu, now, 86400.0)
        cap_usd = float(getattr(self, "_budget_tuition_frac_max", 0.001)) \
            * self._equity()
        x = sum(loss for _, loss in tu)
        if cap_usd <= 0.0:
            # zero/negative equity: a BRAKE fails toward the floor, never
            # toward full refill (2026-07-31 review #9; unreachable in
            # practice - equity would have halted the bot far earlier).
            f = self._budget_floor_frac()
        elif x <= cap_usd:
            f = 1.0
        else:
            f = min(max(cap_usd / x, self._budget_floor_frac()), 1.0)
        prev = getattr(self, "_budget_governor_factor", 1.0)
        if (f < 1.0) != (prev < 1.0):
            phase = "engaged" if f < 1.0 else "released"
            detail = tag(
                Code.SZ_PROBE_TUITION_GOVERNOR,
                f"probe tuition governor {phase}: trailing-24h clipped "
                f"tuition ${x:.2f} vs cap ${cap_usd:.2f} -> refill factor "
                f"{f:.2f}")
            get_audit().log(
                "exploration", Code.SZ_PROBE_TUITION_GOVERNOR, detail,
                {"phase": phase, "tuition_24h_usd": round(x, 4),
                 "cap_usd": round(cap_usd, 4), "factor": round(f, 4)})
            log.info(detail)
        self._budget_governor_factor = f
        return f

    def _budget_refill(self, now: float) -> None:
        """§1.2 token-bucket refill at each budget-mode admission decision:
        tokens <- min(C, tokens + f_governor x R x dt) with R =
        tokens_per_day/86400 engine-s. A None clock (first cycle after
        boot/restart) SEEDS to `now` and accrues nothing: downtime never
        accrues tokens (§5 - the conservative direction; the old deque's
        restart asymmetry was permissive, this one is not)."""
        last = getattr(self, "_budget_last_refill_ts", None)
        self._budget_last_refill_ts = now
        if last is None:
            return
        dt = max(0.0, now - last)
        rate = float(getattr(self, "_budget_tokens_per_day", 15.0)) / 86400.0
        f_gov = self._tuition_governor_factor(now)
        self._budget_tokens = min(
            self._budget_capacity(),
            getattr(self, "_budget_tokens", 0.0) + f_gov * rate * dt)

    def _probe_cost(self, asset: str, regime_label: Optional[str]
                    ) -> tuple[float, float, float, float]:
        """§1.1 scarcity price (deterministic, no RNG). Returns
        (cost, w_asset, w_regime, surcharge):

          w_asset  = clip(sqrt(T_a/(1+n_a)), F, 1), T_a = corpus_target/A
          w_regime = clip(sqrt(regime_floor_live/(1+n_r)), F, 1)
          S        = max(w_asset, w_regime)   [EITHER dimension redeems]
          cost     = min(1/S x surcharge, C)  [clamped: a price > C would
                                               be a livelock wall]

        An unmapped regime label is treated as n_r = 0 -> w_regime = 1.0,
        cost 1.0 (fail-safe scarce, the same direction as the existing
        regime hold). scarcity_pricing=false -> flat cost 1.0 (the 1-knob
        rule, a REAL config point for the simplicity ladder). The Wilson-
        UPPER surcharge ships DARK (§1.6): Stage 0 computes NO surcharge
        (1.0) - the flip is gated on the era-filtered outcomes accessor +
        the simplicity-ladder race, neither of which exists yet."""
        cap = self._budget_capacity()
        if not getattr(self, "_budget_scarcity_pricing", True):
            return min(1.0, cap), 1.0, 1.0, 1.0
        floor = self._budget_floor_frac()
        n_assets = len(getattr(self, "symbol_map", {}) or {})
        t_a = float(getattr(self, "_corpus_target_live", 300)) \
            / max(n_assets, 1)
        _alc: Optional[Callable[[], dict]] = getattr(
            self.history, "asset_live_counts", None)
        n_a = int((_alc() if callable(_alc) else {}).get(asset, 0))
        w_asset = min(max(math.sqrt(t_a / (1.0 + n_a)), floor), 1.0)
        if regime_label is not None and regime_label in REGIME_LABELS:
            n_r = int(self.history.regime_live_count(regime_label))
        else:
            n_r = 0                     # unmapped: fail-safe scarce
        rfl = float(getattr(self, "_regime_floor_live", 60))
        w_regime = min(max(math.sqrt(rfl / (1.0 + n_r)), floor), 1.0)
        s = max(w_asset, w_regime)
        surcharge = 1.0                 # §1.6: dark in Stage 0
        cost = min((1.0 / s) * surcharge, cap)
        return cost, w_asset, w_regime, surcharge

    def _budget_admission(self, now: float, asset: str,
                          regime_label: Optional[str]) -> bool:
        """§1.2-1.3: refill -> price -> probabilistic-affordability roll.
        Evaluated only AFTER _exploration_active (epsilon x decay x
        regime-hold x taper) already rolled True - this is the SUPPLY
        side. ADMIT iff u < p with p = clip(tokens/cost, 0, 1) on the
        DEDICATED _budget_rng stream (u drawn only when tokens > 0, so
        replay streams never desync on exhausted spans). Relative
        admission rates between arms are 1/cost - price = inverse
        admission weight - and every arm's p > 0 whenever tokens > 0: no
        starvation wall by construction (the taper lesson). A failed roll
        is a NON-disposition (like a failed epsilon/taper roll - §4's
        conscious semantic change); exhaustion is bracketed by SZ-049
        transition pairs carrying exact denied-arrival counts."""
        # stash hygiene (§1.4): a probe vetoed between the previous
        # decision and its placement never reached the hook - clear the
        # pointer (and this asset's stale entry) so a later placement can
        # never charge a stale price.
        self._pending_probe_asset = None
        self._pending_probe_cost.pop(asset, None)
        self._budget_refill(now)
        cost, w_asset, w_regime, surcharge = \
            self._probe_cost(asset, regime_label)
        tokens = self._budget_tokens
        if tokens <= 0.0:
            if self._budget_exhausted_since is None:
                self._budget_exhausted_since = now
                self._budget_denied_arrivals = 0
                detail = tag(
                    Code.SZ_PROBE_BUDGET_EXHAUSTED,
                    f"probe budget exhausted (engaged): tokens "
                    f"{tokens:.3f} <= 0 - arrivals denied until refill")
                get_audit().log(
                    "exploration", Code.SZ_PROBE_BUDGET_EXHAUSTED, detail,
                    {"phase": "engaged", "tokens": round(tokens, 4),
                     "asset": asset})
                log.info(detail)
            self._budget_denied_arrivals += 1
            self._budget_denied_events.append(now)
            self._prune_budget_events(self._budget_denied_events, now,
                                      86400.0)
            return False
        if self._budget_exhausted_since is not None:
            span = now - self._budget_exhausted_since
            denied = self._budget_denied_arrivals
            detail = tag(
                Code.SZ_PROBE_BUDGET_EXHAUSTED,
                f"probe budget released: {denied} arrival(s) denied over "
                f"{span:.0f}s, tokens {tokens:.3f}")
            get_audit().log(
                "exploration", Code.SZ_PROBE_BUDGET_EXHAUSTED, detail,
                {"phase": "released", "arrivals_denied": denied,
                 "span_s": round(span, 3), "tokens": round(tokens, 4)})
            log.info(detail)
            self._budget_exhausted_since = None
            self._budget_denied_arrivals = 0
        p = min(max(tokens / cost, 0.0), 1.0)
        u = self._budget_rng.random()
        if u >= p:
            self._budget_rollfail_events.append(now)
            self._prune_budget_events(self._budget_rollfail_events, now,
                                      86400.0)
            return False
        # ADMIT: stash the price for the placement hook (§1.4 - deduct at
        # PLACEMENT, not decision; tokens_after below is the level the
        # deduction WILL produce; a downstream veto discards it unspent).
        self._pending_probe_cost[asset] = cost
        self._pending_probe_asset = asset
        detail = tag(
            Code.SZ_PROBE_PRICED,
            f"probe priced {asset}/{regime_label or '?'}: cost "
            f"{cost:.2f} (w_asset {w_asset:.3f}, w_regime {w_regime:.3f}) "
            f"p {p:.3f} tokens {tokens:.3f}")
        get_audit().log(
            "exploration", Code.SZ_PROBE_PRICED, detail,
            {"asset": asset, "regime": regime_label or "",
             "cost": round(cost, 4), "w_asset": round(w_asset, 4),
             "w_regime": round(w_regime, 4),
             "surcharge": round(surcharge, 4), "p": round(p, 4),
             "u": round(u, 6), "tokens_before": round(tokens, 4),
             "tokens_after": round(tokens - cost, 4)})
        self._budget_admit_events.append((now, cost))
        self._prune_budget_events(self._budget_admit_events, now, 86400.0)
        return True

    def _maybe_refund_probe_order(self, order, now: float) -> None:
        """§1.4 refund on unfilled probe entry terminal (SZ-052): if a
        probe ENTRY order terminates with fill_ratio == 0, its placement-
        time cost (riding in order.meta["probe_cost"] - no orphanable
        side-table) is refunded, clamped at C. Partial or full fill ->
        the position exists -> ML-073 realizes a label <= 8h -> no refund
        (the tag is dropped so a duplicate terminal can never refund
        either). Leak-proof where a close-keyed reservation was not:
        OrderManager terminates every entry by construction (25s timeout,
        <= 1 reprice, 60s deadman). Guarded: refund bookkeeping must
        never break fill handling."""
        try:
            meta = getattr(order, "meta", None)
            if not isinstance(meta, dict) or "probe_cost" not in meta:
                return
            if getattr(order, "purpose", "") != "entry" \
                    or not meta.get("probe"):
                return
            if order.fill_ratio != 0.0:
                meta.pop("probe_cost", None)    # filled: never refundable
                return
            cost = meta.pop("probe_cost", None)
            if cost is None or \
                    not getattr(self, "_budget_refund_unfilled", False):
                return
            self._budget_tokens = min(
                self._budget_capacity(),
                getattr(self, "_budget_tokens", 0.0) + float(cost))
            asset = getattr(order, "asset", "?")
            detail = tag(
                Code.SZ_PROBE_REFUND,
                f"probe refund {asset}: unfilled entry terminal, "
                f"{float(cost):.2f} tokens returned "
                f"(tokens {self._budget_tokens:.3f})")
            get_audit().log(
                "exploration", Code.SZ_PROBE_REFUND, detail,
                {"asset": asset, "cost_refunded": round(float(cost), 4),
                 "tokens_after": round(self._budget_tokens, 4)})
            log.info(detail)
            ev = getattr(self, "_budget_refund_events", None)
            if ev is not None:
                ev.append(now)
                self._prune_budget_events(ev, now, 86400.0)
        except Exception:
            log.exception("probe refund failed - fill handling unaffected")

    def _note_probe_tuition(self, pos, total_net: float,
                            now: float) -> None:
        """§1.5 governor feed at the _finalize_position seam: every probe-
        tagged close appends (close_ts, clipped_loss) to the trailing-24h
        tuition window - clip_usd = cap/outlier_clip_div, so no SINGLE
        probe may contribute more than a third of the day's cap (one
        probe is never evidence). Wins append 0.0 loss (the window then
        doubles as the labels_24h counter - every probe close realizes a
        live label). Fed in BOTH modes (cheap, no RNG, no behavior) so a
        flip to mode="budget" starts with a WARM window - the same
        stateful-rollback rationale as the legacy deque. Guarded: close-
        path bookkeeping must never block an exit (invariant 5)."""
        tu = getattr(self, "_budget_tuition", None)
        if tu is None or getattr(pos, "is_hedge", False) \
                or not getattr(pos, "is_probe", False):
            return
        try:
            cap_usd = float(getattr(self, "_budget_tuition_frac_max",
                                    0.001)) * self._equity()
            div = max(float(getattr(self, "_budget_outlier_clip_div", 3.0)),
                      1.0)
            clip_usd = cap_usd / div
            loss = min(max(0.0, -float(total_net)), clip_usd)
            tu.append((float(now), loss))
            self._prune_budget_events(tu, now, 86400.0)
            lbl = getattr(self, "_budget_label_events_7d", None)
            if lbl is not None:
                lbl.append(float(now))
                self._prune_budget_events(lbl, now, 7 * 86400.0)
        except Exception:
            log.exception("probe tuition feed failed - close unaffected")

    def probe_budget_status(self, now: float) -> dict:
        """§8 telemetry surface, read by the runner's StatusWriter into
        status.ml.probe_budget and exported by gc_pusher. REPORT-ONLY:
        no RNG draws, no decision-state mutation beyond window pruning -
        safe to call in either mode, every loop. per_asset carries the
        stats-judge's ONE combined-drag number per asset (eff_weight =
        taper_pass_prob x S, normalized) - never two invisible
        multiplications. unlock_eta_days keys on the 60-label tb-era
        milestone (§6/§8); tb_era_labels reads the last training load's
        triple_barrier era rows (the closest existing measure - refreshed
        per retrain, honest-absent 0 before the first)."""
        for dq in (getattr(self, "_budget_admit_events", None),
                   getattr(self, "_budget_refund_events", None),
                   getattr(self, "_budget_denied_events", None),
                   getattr(self, "_budget_rollfail_events", None)):
            if dq is not None:
                self._prune_budget_events(dq, now, 86400.0)
        lbl7 = getattr(self, "_budget_label_events_7d", None)
        if lbl7 is not None:
            self._prune_budget_events(lbl7, now, 7 * 86400.0)
        tu = getattr(self, "_budget_tuition", None)
        if tu is not None:
            self._prune_budget_events(tu, now, 86400.0)
        cap_usd = float(getattr(self, "_budget_tuition_frac_max", 0.001)) \
            * self._equity()
        admits: list = list(getattr(self, "_budget_admit_events", None)
                            or [])
        labels_24h = sum(1 for ts, _ in (tu or ()) if now - ts <= 86400.0)
        tb_era = int(((getattr(self.history, "last_load_stats", {}) or {})
                      .get("label_era", {}) or {})
                     .get("triple_barrier", {}).get("rows", 0) or 0)
        horizon_h = float(getattr(self, "_label_max_bars", 96)) * 300.0 \
            / 3600.0
        per_asset: dict = {}
        raw_weights: dict = {}
        _alc: Optional[Callable[[], dict]] = getattr(
            self.history, "asset_live_counts", None)
        live_counts = _alc() if callable(_alc) else {}
        counts = self.history.asset_counts() \
            if hasattr(self.history, "asset_counts") else {}
        total_rows = sum(counts.values())
        share_min = int(getattr(self, "explore_share_min_rows", 10))
        max_share = float(getattr(self, "explore_max_asset_share", 0.5))
        for a in getattr(self, "symbol_map", {}) or {}:
            r_label = self.macro.state(a).label \
                if hasattr(self, "macro") else None
            cost, w_asset, w_regime, _sur = self._probe_cost(a, r_label)
            share = counts.get(a, 0) / total_rows \
                if total_rows >= share_min and total_rows > 0 else 0.0
            taper = 1.0 if share < max_share else max(0.0, 1.0 - share)
            raw = taper * max(w_asset, w_regime)
            raw_weights[a] = raw
            per_asset[a] = {"n_live": int(live_counts.get(a, 0)),
                            "w_asset": round(w_asset, 4),
                            "cost": round(cost, 4)}
        w_total = sum(raw_weights.values())
        for a, raw in raw_weights.items():
            per_asset[a]["eff_weight"] = \
                round(raw / w_total, 4) if w_total > 0 else 0.0
        open_probes = sum(
            1 for p in self.state.open_positions()
            if getattr(p, "is_probe", False)
            and not getattr(p, "is_hedge", False)) \
            if hasattr(self, "state") else 0
        return {
            "mode": getattr(self, "_probe_admission_mode", "share_cap"),
            "tokens": round(getattr(self, "_budget_tokens", 0.0), 4),
            "capacity": round(self._budget_capacity(), 4),
            "refill_per_day": round(
                float(getattr(self, "_budget_tokens_per_day", 15.0))
                * getattr(self, "_budget_governor_factor", 1.0), 4),
            "governor_factor": round(
                getattr(self, "_budget_governor_factor", 1.0), 4),
            "tuition_24h_usd": round(
                sum(loss for _, loss in (tu or ())), 4),
            "tuition_cap_usd": round(cap_usd, 4),
            "admits_24h": len(admits),
            "refunds_24h": len(getattr(self, "_budget_refund_events", ())
                               or ()),
            "denied_exhausted_24h": len(
                getattr(self, "_budget_denied_events", ()) or ()),
            "rolls_failed_24h": len(
                getattr(self, "_budget_rollfail_events", ()) or ()),
            "avg_cost_24h": round(
                sum(c for _, c in admits) / len(admits), 4) if admits
            else None,
            "labels_24h": labels_24h,
            "live_labels_per_day_7d": round(len(lbl7 or ()) / 7.0, 4),
            "tb_era_labels": tb_era,
            "unlock_eta_days": round(
                max(0.0, 60.0 - tb_era) / max(labels_24h, 1), 2),
            "avg_concurrent_probes": round(
                labels_24h * horizon_h / 24.0, 3),
            "open_probes": open_probes,
            "per_asset": per_asset,
            "per_regime_live": {
                r: int(self.history.regime_live_count(r))
                for r in REGIME_LABELS},
        }

    def _probe_admission_decision(self, now: float, asset: str,
                                  regime_label: Optional[str] = None) -> bool:
        """Single throttle decision point for whether this cycle's signal
        is admitted as a PROBE (True) or falls through as an ordinary
        conviction attempt (False - conviction entries are NEVER
        throttled by this lever: this method takes no p_win/size argument
        and cannot touch sizing: it only gates whether the exploration
        BUMP is applied, never the signal's own on-the-merits evaluation).
        Corpus decay already lives inside _exploration_active (scales the
        base epsilon roll); the rolling share cap is enforced here, AFTER
        _exploration_active's own roll decided a probe is wanted, so a
        denial changes nothing about how a non-exploring signal is
        evaluated - the caller just skips the bump block.

        `regime_label` (Task 4, #103): forwarded verbatim to
        _exploration_active so the corpus-decay term can be held at 1.0
        for an under-covered regime (regime-coverage hold) - defaulted so
        every existing caller is unaffected. A REGIME TAG, not a sizing
        value: it cannot mutate p_win/explore_scale, only which regime's
        live-label evidence gates the admission roll - the "no sizing
        argument" invariant this method's signature carries is unchanged."""
        if not self._exploration_active(now, asset, regime_label=regime_label):
            return False
        # SPB-R (spec §1.3): in mode="budget" the share-cap branch below is
        # replaced by refill -> scarcity price -> probabilistic-
        # affordability roll; on non-admit, fall through to the SZ-048
        # drought floor exactly as today (verbatim - in budget mode it
        # should never fire and becomes the livelock CANARY). getattr
        # default keeps every pre-SPB-R stub bot on the legacy path.
        if getattr(self, "_probe_admission_mode", "share_cap") == "budget":
            if self._budget_admission(now, asset, regime_label):
                return True
            return self._drought_floor_fire(now, asset)
        if self._probe_share_would_deny():
            if self._drought_floor_fire(now, asset):
                return True
            # route through tag() (not a bare get_audit().log()) so SZ-047
            # bumps core/code_stats.py's frequency tally like every other
            # SZ-family admission code (SZ_CIRCUIT_BREAKER/SZ_MANIP_SUSPECT/
            # SZ_DD_THROTTLE) - tag() returns the canonical "CODE: detail"
            # string, reused verbatim as the audit message.
            detail = tag(
                Code.SZ_PROBE_THROTTLED,
                f"probe throttled {asset}: rolling share cap "
                f"({self._probe_max_share:.0%} of last "
                f"{self._probe_share_window} admissions) would be exceeded")
            get_audit().log(
                "exploration", Code.SZ_PROBE_THROTTLED, detail,
                {"asset": asset, "window": self._probe_share_window,
                 "max_share": self._probe_max_share})
            # 2026-07-29 log hygiene: while the cap binds, this fires on
            # every admission attempt per asset (constant INFO spam in
            # the live events feed). The SZ-047 audit record above stays
            # per-event (invariant 6: every disposition is recorded);
            # the human-readable line repeats at most once per asset per
            # 10 minutes. getattr-guarded lazy dict: stub-bot unit-test
            # harnesses build this object via __new__ (the documented
            # _record_probe_admission pattern).
            throttle_ts = getattr(self, "_probe_throttle_log_ts", None)
            if throttle_ts is None:
                throttle_ts = self._probe_throttle_log_ts = {}
            last_logged = throttle_ts.get(asset)   # None = first denial ->
            if last_logged is None or now - last_logged >= 600.0:  # always log
                throttle_ts[asset] = now
                log.info("[%s] probe THROTTLED: rolling share cap (%.0f%% "
                         "of last %d admissions) - falling through as an "
                         "ordinary (conviction) entry attempt", asset,
                         self._probe_max_share * 100,
                         self._probe_share_window)
            return False
        return True

    def _conviction_disposition(self, asset: str, signal, decision,
                                regime_label: str,
                                explored: bool,
                                context_aligned: Optional[bool] = None,
                                feed_governor: bool = True
                                ) -> Optional[Code]:
        """Compounder Phase A conviction formula, engine seam: evaluate
        ONE pretrade-approved entry attempt. Returns the denial Code when
        the caller must SKIP the entry (enforce mode only), else None.
        Probes are exempt (they are the exploration channel; the formula
        governs CONVICTION flow). Report mode always returns None —
        dispositions + cadence alarms are logged, entry behavior stays
        byte-identical (the honest threshold-derivation period). Runs
        AFTER the pretrade gate so the EV term reads the gate's MEASURED
        est_edge_bps/est_cost_bps for THIS entry. Self-healing getattr
        (like _record_probe_admission): entry-path integration tests run
        off a minimal LiquidityBot.__new__() stub.

        `context_aligned` (Compounder Phase C, task C4): term 4 of the
        formula (risk/conviction.py's evaluate). Every 5m call site keeps
        the None default (context is not-applicable to the 5m book —
        auto-passes, byte-identical to pre-C4 behavior); ONLY
        _long_book_cycle's long-book admission call passes the computed
        boolean (True/False — never None, since the long book always
        knows whether it evaluated context as known).

        `signal.gates_passed` may be None (C4 review, Important #4): this
        book has no gate-stack agreement measure to offer, so `agreement`
        is passed through as None (not-applicable, auto-passes term 1 —
        risk/conviction.py's evaluate) rather than a fabricated 1.0. Every
        5m call site always passes a real dict (never None), so `agreement`
        stays a real float there, byte-identical to before.

        `feed_governor` (C4 review, Important #3b): False for the
        long-book call site ONLY. conv.note()/cadence_alarms() drive the
        SHARED conviction cadence governor's rolling admit-share windows —
        derived for the 5m book's per-signal cadence (risk/conviction.py's
        cadence_alarms docstring), not this book's ~24h-scale evaluation
        rate. Feeding it here would either silently dilute the 5m-tuned
        windows with long-book samples or spuriously trip CV-050/051 off
        the long book's own naturally sparse cadence. The disposition is
        still evaluated and audit-logged either way — only the governor
        feed is skipped."""
        conv = getattr(self, "conviction", None)
        if conv is None or not conv.enabled or explored:
            return None
        gp = signal.gates_passed
        if gp is None:
            agreement = None
        else:
            agreement = (sum(1 for ok in gp.values() if ok) / len(gp)) \
                if gp else 0.0
        rfl = int(getattr(self, "_regime_floor_live", 0))
        regime_known = True
        if rfl > 0:
            if regime_label not in REGIME_LABELS:
                regime_known = False    # unmapped label: no evidence bucket
            else:
                regime_known = not _regime_under_coverage_floor(
                    self.history.regime_live_count(regime_label), rfl)
        cdec = conv.evaluate(
            agreement=agreement, est_edge_bps=decision.est_edge_bps,
            est_cost_bps=decision.est_cost_bps, regime_known=regime_known,
            context_aligned=context_aligned)
        if feed_governor:
            conv.note(cdec, regime_label)
        get_audit().log(
            "conviction", cdec.code,
            tag(cdec.code,
                f"{asset} conviction "
                f"{'admitted' if cdec.admitted else 'denied'} "
                f"({conv.mode})"),
            {"asset": asset, "mode": conv.mode, **cdec.terms})
        if feed_governor:
            for acode, adetail in conv.cadence_alarms():
                get_audit().log("conviction", acode, tag(acode, adetail),
                                {"asset": asset})
        if not cdec.admitted and conv.enforce:
            return cdec.code
        return None

    def _entry_assets(self) -> list:
        """Per-cycle entry evaluation order, round-robin rotated. Fixed dict
        order would hand the first asset permanent first claim on scarce
        position slots (variety: under contention ETH would win every free
        slot simply by being evaluated first)."""
        items = [(a, v) for a, v in self.view.items() if a in self.symbol_map]
        if not items:
            return items
        k = self._entry_rotation % len(items)
        self._entry_rotation += 1
        return items[k:] + items[:k]

    @staticmethod
    def _thesis_scored_p(thesis) -> float:
        """The probability the governor grades the model on: the model's own
        call (model_p) when the thesis recorded one. Exploration bumps p_win
        for SIZING; grading the model on that forced number is how the
        governor once blamed it for epsilon-greedy noise. Theses from before
        the model_p field (sentinel -1) fall back to the sized p_win."""
        mp = float(getattr(thesis, "model_p", -1.0))
        return mp if mp >= 0.0 else float(thesis.p_win)

    def _log_sizer_veto(self, asset: str, reasons: list,
                        explored: bool) -> None:
        """Exploration entries surface their sizer veto at INFO: these are
        the trades the bot takes SPECIFICALLY to learn, so a veto here is a
        learning outage, not routine noise. (A DEBUG-only veto hid 45h of
        total entry starvation behind a miscalibrated liquidity label.)"""
        log.log(logging.INFO if explored else logging.DEBUG,
                "[%s] sizer veto: %s", asset,
                "; ".join(str(r) for r in reasons) or "(no reason recorded)")

    def _bracket_for_entry(self, *, asset: str, symbol: str, direction: str,
                          price: float, p_win: float, equity: float,
                          macro_state, vol_state, liq_state, verdict,
                          lev_decision, now: float, decision,
                          explored: bool, aggressive: bool,
                          explore_scale: float, manip_scale: float,
                          sized):
        """geometry-alignment T5 (spec D1): "the traded bet is the labeled
        bet". Computes THIS entry's triple-barrier bracket
        (barrier_geometry() - ml/labeling.py, the SAME pure helper the
        candidate labeler calls, T2) from the entry's own sigma_bar and
        the pretrade decision's own (real, post-participation-clamp)
        est_cost_bps, then re-sizes through the labeled bracket (spec D3:
        per-trade bar/Kelly/risk-in-size notional) - a PASS-2 sizer.size()
        call, never a re-run of price discovery or the pretrade EV gate
        (`decision` itself, computed by the caller against PASS-1's
        `sized`, stays the entry's one approval).

        Returns (pt_frac, sl_frac, deadline_ts, sized, veto_reasons):
          * bracket_exits.enabled=false -> (0.0, 0.0, 0.0, `sized`
            unchanged, []) - byte-identical legacy (CLAUDE.md invariant
            7): the caller's own PASS-1 `sized`/`decision.size_units`
            reproduce exactly.
          * enabled, bracket-sizing APPROVED -> the labeled fractions,
            entry + ml.label_max_bars bars, the NEW (PASS-2) SizeDecision
            (`decision.size_units` is rescaled here, in place, to the
            SAME proportion PASS-2's notional bears to PASS-1's - the
            participation-clamped size the pretrade gate already
            approved just scales with the bracket-driven notional, never
            re-validated against the gate a second time - CLAMPED so it
            can only shrink, never grow past PASS-1's approval; see the
            rescale_ratio comment below, T5 review IMPORTANT-1).
          * enabled, bracket-sizing VETOED -> (pt_frac, sl_frac, 0.0,
            None, reasons) - `sized is None` is the caller's signal to
            veto this entry exactly like an ordinary sizer veto."""
        if not self._bracket_exits_enabled:
            return 0.0, 0.0, 0.0, sized, []
        from ml.walkforward import BAR_SECONDS
        sigma_bar = vol_state.sigma_bar_pct / 100.0
        cost_pct = decision.est_cost_bps / 100.0
        pt_frac, sl_frac = barrier_geometry(
            sigma_bar, cost_pct, self._label_pt_vol_mult,
            self._label_sl_vol_mult, self._label_pt_cost_mult)
        bracket_sized = self.sizer.size(
            asset, direction, price, p_win, equity, self.state,
            macro_state, vol_state, liq_state, verdict.risk_multiplier,
            self.inventory, lev_decision, self.marks, now,
            risk_scale=self.monitor.kelly_mult * explore_scale
            * manip_scale,
            # 2026-07-29 (THALES audit B-1b): the explore floor must not
            # RE-INFLATE a manip-downsized probe — with manip in the
            # downsize band (manip_scale < 1) the SZ-045 haircut was
            # measured being floored right back to the $15 probe minimum,
            # leaving the 0.6-0.9 band void for exactly the floor-sized
            # probe flow it most needs to bind on. A suspect book pays
            # for its label at honest (downsized) size or not at all;
            # the training-weight discount already halves such rows'
            # learning value, so full-price tuition was never justified.
            symbol=symbol, floor_to_min=(explored and not aggressive
                                         and manip_scale >= 1.0 - 1e-9),
            bracket=(pt_frac * 100.0, sl_frac * 100.0))
        if not bracket_sized.approved:
            return pt_frac, sl_frac, 0.0, None, bracket_sized.reasons
        if sized.units > EPS:
            # T5 review fix (IMPORTANT-1): PASS-1's `decision` is the
            # ENTRY'S ONE APPROVAL against the participation/impact/EV
            # cost stack (pretrade.evaluate()) - a CEILING, never
            # revisited here. PositionSizer.size()'s risk-in-size scales
            # notional by (stop_loss_pct_ref / sl_pct) for a bracket call
            # (risk/position_sizer.py), so a FLOORED bracket whose sl_pct
            # sits below stop_loss_pct_ref can demand MORE notional than
            # PASS-1 ever cleared (measured 1.46x at a floored case) -
            # scaling decision.size_units up by that ratio would put size
            # on the market the gate never approved. Clamping the ratio
            # at 1.0 preserves the DOWNSCALE case exactly (a smaller
            # bracket-driven size still shrinks decision.size_units) while
            # forbidding any growth without a second pretrade-gate pass
            # (which this function never runs).
            rescale_ratio = min(bracket_sized.units / sized.units, 1.0)
            decision.size_units *= rescale_ratio
        deadline_ts = now + self._label_max_bars * BAR_SECONDS
        return pt_frac, sl_frac, deadline_ts, bracket_sized, []

    def _fetch_market_payloads(self) -> list:
        """Fetch each market feed CONCURRENTLY (one thread per feed; each
        feed owns its own Session and throttle, so cross-feed parallelism is
        safe). Measured live: the serial chain cost ~4.3s of dead time per
        slow cycle (OKX 2.75s + Binance.US 1.55s) during which stops are
        blind; concurrent fetch bounds it by the slowest single feed. A
        failing feed degrades to an empty payload, never an exception.
        Recording mode stays serial: FeedRecorder instances append to one
        shared sink file and must not interleave writes."""
        feeds = [("okx", self.okx.get_market_data),
                 ("binanceus", self.binanceus.get_market_data)]
        if self.ccxt_feed is not None:
            feeds.append(("ccxt", self.ccxt_feed.get_market_data))

        def _safe(name, fn):
            try:
                return fn() or {}
            except Exception:
                log.exception("feed %s fetch failed - continuing without it",
                              name)
                return {}

        if self._serial_feeds or len(feeds) == 1:
            return [_safe(n, f) for n, f in feeds]
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(feeds),
                                thread_name_prefix="feed") as ex:
            futures = [ex.submit(_safe, n, f) for n, f in feeds]
            return [f.result() for f in futures]   # feed order preserved

    def _augment_view_with_kraken(self, now: float) -> None:
        """Ground EVERY mapped asset's candles on the EXECUTION venue (v8
        wash-trading hygiene): build_view merges external candles by
        "prefer the longer history" venue-agnostically, so volume_z /
        vol_term / ret_* learned unregulated-venue REPORTED volume - the
        exact quantity Cong-Li-Tang-Yang 2023 showed averages >70%
        fabricated on such venues. Kraken bars replace an asset's external
        bars whenever they cover the longest builder window (vol_term: 97
        bars) OR are at least as long; external candles are kept when
        Kraken's are shorter (never degrade feature windows) or the fetch
        fails (availability preserved, debug log). External BOOKS still
        feed imbalance/dislocation/manip divergence unchanged. Throttled:
        at most _KR_CANDLE_FETCH_BUDGET REST fetches per slow cycle,
        most-stale assets first, each asset refreshed every
        candle_refresh_sec (5m bars - staleness up to the cadence is
        harmless). Data-cold GAP assets (no external candles - e.g. a
        Kraken-only listing like MINA/USD) warm vol/liq/fair-value from
        these same bars plus a cached-book fallback, as before."""
        stale = sorted(((now - self._kr_candles.get(a, (0.0, []))[0], a)
                        for a in self.symbol_map), reverse=True)
        fetched = 0
        for age, asset in stale:
            if fetched >= _KR_CANDLE_FETCH_BUDGET \
                    or age < self._kr_candle_refresh_sec:
                break              # ages sorted desc: the rest are fresher
            fetched += 1
            pair = self.kraken.kraken_pair(self.symbol_map[asset])
            try:
                candles = self.kraken.get_candles(pair)
            except Exception:
                log.debug("kraken candle refresh failed for %s", asset,
                          exc_info=True)
                continue
            if candles:
                self._kr_candles[asset] = (now, candles)

        max_age = _KR_CANDLE_STALE_MULT * self._kr_candle_refresh_sec
        for asset, symbol in self.symbol_map.items():
            ts, kr = self._kr_candles.get(asset, (0.0, []))
            if not kr or (now - ts) > max_age:
                continue           # no usable venue bars -> external stands
            _bar_age_check(self, asset, kr, now)
            existing = self.view.get(asset)
            ext = (existing or {}).get("candles") or []
            if len(kr) < 97 and len(kr) < len(ext):
                continue           # would shrink the feature window: keep ext
            entry = dict(existing or {})
            entry["candles"] = kr
            entry.setdefault("order_book", self.kraken_books.get(asset) or {})
            entry.setdefault("kraken_symbol", symbol)
            self.view[asset] = entry

    def _stamp_mark_wall(self, symbol: str) -> None:
        """Telemetry-only wall-clock stamp beside _mark_ts. getattr-guarded
        lazy init (the _sig_gates fixture convention): __new__ test doubles
        bypass __init__ and must never trip fast_cycle on a missing dict."""
        d = getattr(self, "_mark_wall_ts", None)
        if d is None:
            d = self._mark_wall_ts = {}
        d[symbol] = time.time()

    def _refresh_market_state(self, now: float) -> None:
        """Per-asset market-state refresh, extracted verbatim from the top
        of slow_cycle (C901 ratchet: the conviction call-site branch put
        slow_cycle one over the pinned ceiling; this block was the
        self-contained candidate). fv/vol/liq updates, manip-suspect
        refresh, regime-age tracking, SCS advance, and the intraday
        correlation update. Behavior-identical: communicates with the
        rest of slow_cycle only through self-state."""
        closes = {}
        for asset, v in self.view.items():
            if asset not in self.symbol_map:
                continue
            kbook = self.kraken_books.get(asset) or {}
            # DL-10: kraken_books entries never expire - when the venue
            # goes quiet the LAST book would keep classifying liquidity/
            # spoof/imbalance as if live, freezing every book feature at
            # its final frame. Past the watchdog's critical staleness the
            # book is treated as ABSENT (spread 999 / depth 0 - the same
            # fail-closed shape as a missing venue). Exits are untouched:
            # they price off marks/books at submit time, gated separately.
            if kbook and (now - self.book_ts.get(asset, 0.0)) > \
                    self.watchdog.stale_critical_sec:
                kbook = {}
            self.fv.update(asset, [v.get("order_book") or {}], kbook, now)
            self.vol.update(asset, v.get("candles") or [],
                            self.daily_candles.get(asset) or [])
            self.liq.update(asset, v.get("order_book") or {}, kbook, now)
            # refresh the manipulation score EVERY cycle, not only at
            # signal evaluation: while the position cap pauses entries no
            # signals are evaluated, and a defense gauge that freezes on
            # its last value is blind exactly when the operator watches it
            ls = self.liq.state(asset)
            self._surface_kraken_imbalance(asset, v, kbook, ls)
            # cross-venue divergence: Kraken (exec) vs the COHERENT per-venue
            # composite, not the mixed-unit merged book (SD-003). No external
            # book this cycle -> composite is unmeasurable, so mirror
            # kraken_imb to make divergence exactly 0 (never flag Kraken's own
            # natural imbalance as manipulation).
            kimb = _book_imbalance(kbook)
            comp = _composite_imbalance(v.get("venue_books") or [])
            self._manip_scores[asset] = round(manip_suspect_score(
                ls.spoof_score,
                whiplash_suspicion(ls.imbalance_whiplash,
                                   self._wl_p95, self._wl_thr),
                kimb,
                comp if comp is not None else kimb), 3)
            # regime age: when did the macro label last change? Feeds the
            # regime_age feature - a 2-bar-old "range" and a 3-day-old
            # "range" are different animals the one-hots cannot separate.
            label = self.macro.state(asset).label
            prev = self._regime_since.get(asset)
            if prev is None or prev[0] != label:
                self._regime_since[asset] = (label, now)
            if v.get("candles"):
                closes[asset] = float(v["candles"][-1]["close"])
                # State-Change Sampler: advance the CUSUM EVERY bar (it
                # integrates drift) and LATCH any event until candidate
                # registration consumes it — the register site may skip
                # cycles (unconfirmed signal), but the event must not be
                # lost. Samples the learning corpus only; no entry/exit/
                # gate decision reads this.
                if self.scs.observe(asset, closes[asset],
                                    sigma_bar_pct=self._measured_sigma(asset),
                                    regime_label=label,
                                    liq_label=ls.label):
                    self._scs_pending[asset] = True
        if closes:
            self.corr.update_intraday(closes)

    def slow_cycle(self, now: float) -> None:
        self.view = self.liquidity_model.build_view(
            *self._fetch_market_payloads(), now=now)
        self._augment_view_with_kraken(now)
        self._refresh_market_state(now)

        self._maybe_unwind_unteachable(now)
        self._maybe_realize_mature_label(now)
        sentiment = self.xscan.maybe_poll(now)
        web = self.webdata.maybe_poll(now)
        risk = self.moomoo.maybe_poll(now)
        self._context_state = self.context.maybe_poll(now)
        # Fear&Greed extremes join fear/euphoria detection (same clamps
        # apply downstream - still a filter, never a trigger)
        if self.dry_run and self.sim.force_fear > 0:
            sentiment.fear_spike = True
        if web.available:
            if web.fear_greed <= self.fg_fear_max and not sentiment.fear_spike:
                sentiment.fear_spike = True
                log.info(f"Fear&Greed extreme ({web.fear_greed:.0f}) -> "
                        f"fear context on")
            elif web.fear_greed >= self.fg_euphoria_min and not sentiment.euphoria_spike:
                sentiment.euphoria_spike = True

        for asset, v in self.view.items():
            if asset in self.symbol_map and v.get("candles"):
                self.candidates.update_candles(asset, v["candles"])
                self.thales.observe_candles(asset, v["candles"], now)
        self.candidates.poll()

        # NEW-risk gate: the halt flag OR the central fault authority (DEGRADED/
        # HALTED refuses new risk; ARMED allows). Behaviour-preserving — the
        # only conditions that leave ARMED (hard-stop, runner wedge) already
        # set _halted, so this adds no new blocking today; it makes latch() a
        # live control so future faults refuse new risk without a code change.
        # Exits run in fast_cycle and are never gated here (invariant #5).
        fm = getattr(self, "fault", None)
        if self._halted or (fm is not None and not fm.allow_new_risk()):
            return

        equity = self._equity()
        if equity <= EPS:
            return
        # the capital cap gates LIVE entries only - never the learning
        # lane: shadow candidates cost nothing, and halting evaluation
        # while the book is full starves the label pipeline for hours
        # (observed live: ~110 blocked cycles/hour, zero new candidates,
        # open-candidate pool drained 65 -> 7 during a capped stretch).
        # Pending (resting, unfilled) entry orders are committed risk that
        # positions-on-fill accounting hasn't booked yet; reserve a cap slot
        # for each so filled + pending never exceeds max_concurrent. The
        # counter is decremented forward as this cycle places entries.
        reserved_entries = sum(1 for o in self.orders.open_orders()
                               if o.purpose == "entry")
        can_enter = self.capital.can_open_new_position(
            self.state, reserved_entries)

        # structural stress inputs for the narrative filter
        vols = [self.vol.state(a).percentile for a in self.symbol_map]
        depths = [self.liq.state(a).depth_ratio for a in self.symbol_map]
        fundings = [abs((self.view.get(a) or {}).get("funding_rate") or 0.0)
                    for a in self.symbol_map]
        bases = [abs(self.fv.state(a).basis_bps) for a in self.symbol_map]
        structure = StructuralInputs(
            vol_percentile=max(vols) if vols else 50.0,
            depth_ratio=min(depths) if depths else 1.0,
            funding_rate=max(fundings) if fundings else 0.0,
            turbulence_pct=self.corr.state.turbulence_pct,
            basis_bps=max(bases) if bases else 0.0,
            risk_asset_z=risk.risk_z,
            risk_asset_available=risk.available,
        )
        verdict = self.narrative.evaluate(sentiment, structure)
        self.postmortem.note_stress(verdict.label == "confirmed_stress")

        # operator pause and ledger-drift blocks stop NEW RISK, not the
        # learning lane or the signals panel (same reasoning as the
        # capital cap above: candidates cost nothing, and a frozen
        # status gauge is a blind operator). The WATCHDOG block stays a
        # hard return: it trips on data quality - candidates registered
        # from suspect feeds would poison the training set.
        if not self.entries_enabled:
            can_enter = False
        if self.watchdog.state.entries_blocked:
            log.info(f"watchdog blocking entries: "
                     f"{self.watchdog.state.reasons}")
            return
        if abs(self._equity_drift_pct) > self.max_equity_drift_pct:
            log.warning(f"equity drift {self._equity_drift_pct:+.2f}% vs "
                        f"venue truth - entries blocked until reconciled")
            can_enter = False

        for asset, v in self._entry_assets():
            symbol = self.symbol_map[asset]
            if not self._live_order_allowed("entry"):
                can_enter = False      # live-not-armed: learning continues
            # Minor #10 (C4 review): book-aware - a resting LONG-book bid
            # (now living for hours, not ~25s) must not block the 5m
            # book's own entries on the same asset.
            if self.orders.has_open(asset, "entry", book="5m"):
                continue

            signal = self.gates.evaluate_asset(asset, v)
            # learned per-gate weighting shades confidence toward gates
            # that predict wins on this feed (cold start = naive fraction;
            # never touches direction or all_confirmed)
            signal.confidence = self.gate_stats.weighted_confidence(
                signal.gates_passed, signal.confidence)
            # THALES shade: bounded, post-gate-stats, never touches
            # direction or all_confirmed; shadow mode records the
            # counterfactual and leaves confidence untouched
            th = self.thales.shade_confidence(
                asset=asset, direction=signal.direction or "",
                urgency=float(getattr(signal, "urgency", 0.0)),
                confidence=signal.confidence,
                macro_label=self.macro.state(asset).label, now=now)
            signal.confidence = th.confidence
            # TH-021 evidence-concentration shade: after the THALES footprint
            # shade, trim a DIFFUSE-and-marginal signal (many weak factors
            # averaged into a marginal pass) toward the floor; concentrated
            # conviction is untouched. Down-only, bounded, disabled by default
            # (mult==1.0 -> exact prior behavior). Never touches all_confirmed.
            _cmult = concentration_conf_mult(
                getattr(signal, "evidence_concentration", 0.0),
                signal.confidence, self._conc_shade_cfg)
            if _cmult < 1.0 - 1e-9:
                _pre = signal.confidence
                signal.confidence = _pre * _cmult
                get_audit().log("thales", Code.TH_CONCENTRATION_SHADE,
                                f"{asset} diffuse-marginal trim x{_cmult:.3f}",
                                {"conc": round(float(getattr(
                                    signal, "evidence_concentration", 0.0)), 3),
                                 "conf": round(_pre, 3),
                                 "mult": round(_cmult, 3)})
            # V2 vindication loop: remember which detectors advised on
            # THIS signal so a resulting position's close can grade them.
            # 2026-07-29 correction (THALES audit B-2): grading is
            # OBSERVATIONAL — advice quality is measurable whether or not
            # the shade was applied, and shadow-mode grades are exactly
            # the promotion evidence the reliability bar requires. The
            # old advise-only gate was a chicken-and-egg: promotion to
            # advise required shadow evidence, but the ledger only
            # learned in advise — so it stayed empty forever. Influence
            # gating still lives where it belongs: shade_confidence
            # applies mult only in advise mode.
            self._thales_fired[asset] = list(th.fired)
            # Snapshot the gate verdicts alongside the detector list so an
            # entry can carry them to the position (realized-outcome loop).
            # Copied, not referenced: signal objects are rebuilt each cycle.
            if hasattr(self, "_sig_gates"):
                self._sig_gates[asset] = dict(signal.gates_passed or {})
            if th.notes and abs(th.would_mult - 1.0) > 1e-6:
                log.info(f"thales {asset}: {'; '.join(th.notes)}")
            self.last_signals[asset] = {
                "confirmed": bool(signal.all_confirmed),
                "direction": signal.direction,
                "confidence": round(float(signal.confidence), 3),
                "urgency": round(float(getattr(signal, "urgency", 0.0)), 2),
                # shadow evidence-concentration (0 diffuse .. 1 pinpointed):
                # exposed to telemetry so the desk can compare concentrated
                # conviction vs blended-average signals across assets
                "concentration": round(float(getattr(
                    signal, "evidence_concentration", 0.0)), 3),
                "gates": {k: bool(x) for k, x in
                          (signal.gates_passed or {}).items()},
                "ts": now,
            }
            if not signal.all_confirmed or not signal.direction:
                continue

            macro_state = self.macro.state(asset)
            vol_state = self.vol.state(asset)
            liq_state = self.liq.state(asset)
            fv_state = self.fv.state(asset)
            others = [a for a in self.symbol_map if a != asset]

            gate_conf = min(max(signal.confidence + verdict.confidence_tilt, 0.0), 1.0)
            smc_feats = self.smc.compute(asset, v.get("candles") or [],
                                         signal.direction, now,
                                         daily_candles=self.daily_candles.get(asset))
            extras = self._feature_extras(asset, v, web, risk,
                                          others[0] if others else None, now)
            # 41b: availability flags at THIS signal's build instant - they
            # ride the candidate row, the order meta and the eventual live
            # row as bookkeeping columns (never features)
            feat_avail = extras.get("avail") or {}
            feats = build_features(asset, signal.direction, gate_conf, v,
                                fv_state, vol_state, liq_state, macro_state,
                                self.corr.state, sentiment, smc_feats,
                                other_asset=others[0] if others else None,
                                extras=extras)
            p_win = self.meta.p_win(feats, gate_conf,
                                    shrinkage=self.monitor.shrinkage,
                                    use_model=self.monitor.use_model)

            # active-learning: in DRY RUN, take a fraction of confirmed signals
            # as small paper trades even when the model is too skeptical to
            # clear the net-Kelly bar, so real-fill labels accrue. Bump the
            # sizing belief just past net breakeven and shrink the size; the
            # logged FEATURES and the win/loss LABEL stay real (honest data).
            model_p, explore_scale = p_win, 1.0
            explored = aggressive = False
            # position id PRE-ASSIGNED (before any entry order exists) so
            # the ML-070 exploration audit can name the position a probe
            # becomes, and OF-5 can exclude it per-trade. Direct entries
            # submit under this id (the fill coalesces onto it); an entry
            # routed to the algo slicer uses "algo-<parent>" instead - the
            # probe flag still reaches its position via _algo_meta.
            pid = str(uuid.uuid4())
            if can_enter and self._probe_admission_decision(
                    now, asset, regime_label=macro_state.label):
                explored = True
                p_win = max(p_win, self.explore_p_win)
                explore_scale = self.explore_size_scale
                # conviction-scaled AGGRESSIVE roll: the model is reasonably
                # confident, the book is clean (low manip, non-crisis), and the
                # dice say so -> size on real conviction, no shrink, no min
                # floor. The risk stack / manip gate / kelly_cap still bound it.
                ms = float(self._manip_scores.get(asset, 0.0))
                if self._explore_aggressive_eligible(
                        model_p, ms, macro_state.label) \
                        and self._explore_rng.random() < self._explore_aggr_frac:
                    aggressive = True
                    p_win = max(p_win, self._explore_aggr_p)
                    explore_scale = 1.0
                code = Code.ML_EXPLORE_AGGRESSIVE if aggressive \
                    else Code.ML_EXPLORATION
                get_audit().log("exploration", code,
                                f"{'aggressive ' if aggressive else ''}paper "
                                f"exploration entry {asset} {signal.direction}",
                                {"model_p": round(model_p, 3),
                                 "sized_p": round(p_win, 3),
                                 "aggressive": aggressive, "manip": round(ms, 3),
                                 "position_id": pid,
                                 "rows": self.history.row_count()})
                log.info("[%s] %sEXPLORATION paper entry: model p=%.2f -> sizing "
                         "p=%.2f, size x%.2f (learning; %d history rows)",
                         asset, "AGGRESSIVE " if aggressive else "", model_p,
                         p_win, explore_scale, self.history.row_count())

            # every confirmed signal becomes a training candidate (labeled
            # later via triple-barrier) - taken AND vetoed, so the model
            # learns from an unbiased sample instead of survivors only.
            # SCS gate: register only when a state-change event is latched
            # (ml/event_sampler.py). Unbiasedness is preserved because
            # event times are independent of gate verdicts — taken AND
            # vetoed signals are still both sampled, just at event times.
            # Sampler disabled -> observe() returns True every cycle, the
            # latch is always set, behavior identical to legacy.
            if v.get("candles") and self._scs_pending.get(asset):
                if self.candidates.register(asset, signal.direction, feats,
                                        vol_state.sigma_bar_pct / 100.0,
                                        v["candles"][-1]["time"],
                                        gates_passed=signal.gates_passed,
                                        spread_bps=liq_state.spread_bps,
                                        confidence=model_p,  # W2-1: honest p(win)
                                        gate_components=signal.components,
                                        avail=feat_avail):
                    # consume the latch ONLY on a real append: a same-
                    # candle dedup no-op keeps the event pending so the
                    # state-change lesson registers at the next bar
                    self._scs_pending[asset] = False
            self.monitor.note_features(feats)
            if not can_enter:
                self._mark_cand(asset, signal.direction, "capped")
                continue          # book full: lesson recorded, no new risk

            lev_decision = self.lev_gov.decide(
                self.state, self.marks, equity, vol_state.sigma_annual_pct,
                macro_state.playbook.get("leverage_cap", 1.0),
                self.margin_level_pct)

            # circuit breaker: a symbol on a losing streak is pulled off the
            # sheet — new entries only, exits never consult this. Checked
            # before sizing so a paused asset costs nothing further.
            if self.breaker.is_tripped(asset, now):
                left_h = self.breaker.remaining_s(asset, now) / 3600.0
                self._log_sizer_veto(asset, [tag(
                    Code.SZ_CIRCUIT_BREAKER,
                    f"paused {left_h:.1f}h more (consecutive-loss "
                    f"breaker)")], explored)
                self._mark_cand(asset, signal.direction,
                                Code.SZ_CIRCUIT_BREAKER.value)
                continue

            # anti-scalp: fold manipulation suspicion into the NEW entry.
            # manip_suspect_score (MAX of spoof / imbalance-whiplash / cross-
            # venue book divergence) is the operator's read on whether this
            # book is being painted. This is a new-risk-only action — exits
            # are never touched. At/above veto_at the entry is refused
            # (SZ-045: don't add liquidity a bigger fish is spoofing to
            # scalp); between downsize_at and veto_at the entry shrinks
            # linearly toward min_scale, folded into the sizer's multiplicative
            # risk_scale (clamped [0,1] there). Below downsize_at: untouched.
            manip_scale = 1.0
            if self._manip_gate_enabled:
                ms = float(self._manip_scores.get(asset, 0.0))
                scale = manip_entry_scale(ms, self._manip_downsize_at,
                                          self._manip_veto_at,
                                          self._manip_min_scale)
                if scale is None:
                    self._log_sizer_veto(asset, [tag(
                        Code.SZ_MANIP_SUSPECT,
                        f"manip suspect {ms:.2f} >= veto "
                        f"{self._manip_veto_at:.2f}")], explored)
                    self._mark_cand(asset, signal.direction,
                                    Code.SZ_MANIP_SUSPECT.value)
                    continue
                manip_scale = scale

            sized = self.sizer.size(
                asset, signal.direction,
                self.marks.get(symbol) or fv_state.kraken_mid or 0.0,
                p_win, equity, self.state, macro_state, vol_state, liq_state,
                verdict.risk_multiplier, self.inventory, lev_decision,
                self.marks, now,
                risk_scale=self.monitor.kelly_mult * explore_scale * manip_scale,
                # floor withheld under manip suspicion — see the PASS-2
                # site in _bracket_for_entry for the full B-1b rationale
                symbol=symbol, floor_to_min=(explored and not aggressive
                                             and manip_scale >= 1.0 - 1e-9))
            if not sized.approved:
                self._log_sizer_veto(asset, sized.reasons, explored)
                # No pre-truncation: mark_disposition owns the cap
                # (DISPOSITION_MAX_CHARS). Slicing to 40 here cut through
                # the '[bracket pt=..% sl=..%]' payload the sizer had just
                # computed - see mark_disposition for the corpus measurement.
                self._mark_cand(asset, signal.direction,
                                str((sized.reasons or ["sizer"])[0]))
                continue

            # AS quote prices the entry; maker side of our own quote
            inv_ratio = self.inventory.inventory_ratio(self.state, asset,
                                                        self.marks, equity)
            quote = self.quoter.quote(fv_state.fair_value or sized.usd / sized.units,    
                                    vol_state.sigma_bar_pct, inv_ratio,
                                    liq_state.label,
                                    fee_bps=self.pretrade.maker_fee_bps)
            plan = self.tactics.plan_entry(
                signal.direction, quote,
                self.kraken_books.get(asset) or {},
                getattr(signal, "urgency", 0.0), liq_state.label)
            entry_price = plan.price
            side = "buy" if signal.direction == "long" else "sell"

            # exact per-trade EV in the sizer's reference geometry:
            # EV = p*target - (1-p)*stop with target = b*stop
            #    = stop * (p*(1+b) - 1), floored at 0. The old shorthand
            # (2p-1)*b*stop equals this ONLY at b=1 (2026-07-29 unit
            # audit) - it understates edge for b>1 and overstates it for
            # b<1 (the honest post-payoff-fix shipped b is ~0.92, so the
            # exact form is the CONSERVATIVE one today; the wave-1
            # verify pass confirmed pretrade's own clamp at
            # execution/pretrade.py keeps a negative alpha from passing
            # either way). base_stop_pct (not the
            # vol-widened stop) is the correct pair: sizer.b is derived
            # against this same reference stop.
            exp_alpha_bps = max(p_win * (1.0 + self.sizer.b) - 1.0, 0.0) * \
                self.base_stop_pct * 100.0
            ctx = PreTradeContext(
                kraken_book=self.kraken_books.get(asset) or {},
                sigma_daily_pct=vol_state.sigma_daily_pct,
                adv_usd=self._adv_usd(asset, entry_price),
                liq_label=liq_state.label,
                spread_bps=liq_state.spread_bps,
                staleness_ms=(now - self.book_ts.get(asset, 0.0)) * 1000.0,
                tier=liq_state.tier,
            )
            decision = self.pretrade.evaluate(
                side, sized.units, entry_price,
                exp_alpha_bps=exp_alpha_bps,
                fv_edge_bps=fv_state.edge_bps(side),
                ctx=ctx, taker=plan.taker,
                extra_edge_ratio=self.monitor.edge_ratio_bump,
                # dry-run exploration takes net-thin signals to gather real-fill
                # labels; `explored` is only ever True in dry_run, so the
                # profit-EV bypass can never reach a live order.
                exploring=(explored and self.explore_bypass_ev))
            if not decision.approved:
                log.info(f"[{asset}] pre-trade veto: {decision.reasons}")
                self._mark_cand(asset, signal.direction,
                                str((decision.reasons or ["pretrade"])[0]))
                continue

            # geometry-alignment T5 (spec D1): "the traded bet is the
            # labeled bet". Every model-lane entry (conviction AND probe
            # alike, operator decision 1) computes its own triple-barrier
            # bracket - see _bracket_for_entry's docstring. bracket_exits.
            # enabled=false reproduces `sized`/`decision.size_units` from
            # the PASS-1 call above byte-identical (CLAUDE.md invariant 7).
            (bracket_pt_frac, bracket_sl_frac, bracket_deadline_ts,
             bracket_sized, bracket_veto_reasons) = self._bracket_for_entry(
                asset=asset, symbol=symbol, direction=signal.direction,
                price=self.marks.get(symbol) or fv_state.kraken_mid or 0.0,
                p_win=p_win, equity=equity, macro_state=macro_state,
                vol_state=vol_state, liq_state=liq_state, verdict=verdict,
                lev_decision=lev_decision, now=now, decision=decision,
                explored=explored, aggressive=aggressive,
                explore_scale=explore_scale, manip_scale=manip_scale,
                sized=sized)
            if bracket_sized is None:
                # bracket-driven sizing vetoed this entry (e.g. the
                # labeled bracket's own breakeven no longer clears p_win) -
                # treated exactly like an ordinary sizer veto.
                self._log_sizer_veto(asset, bracket_veto_reasons, explored)
                self._mark_cand(asset, signal.direction,
                                str((bracket_veto_reasons or ["sizer"])[0]))
                continue
            sized = bracket_sized

            # Compounder Phase A: conviction formula disposition. None ->
            # proceed (always, in report mode); a Code -> the enforce-mode
            # skip path (registered CV-*, candidate marked, no bare string).
            deny_code = self._conviction_disposition(
                asset, signal, decision, macro_state.label, explored)
            if deny_code is not None:
                self._mark_cand(asset, signal.direction, deny_code.value)
                continue

            # the id pre-assigned before the ML-070 audit IS the position
            # id - the audited probe and the eventual position correlate 1:1
            position_id = pid
            # W2-4 lineage: id of this signal's already-registered candidate
            # row (if any), read-only peek - threaded into every entry
            # path's meta so the live row can join back to its candidate
            # twin by id, not by an exact feature match that funding_dist's
            # cross-cycle clock drift can silently defeat.
            cand_id = self.candidates.open_candidate_id(asset,
                                                        signal.direction)
            # thesis for the postmortem engine: what did we expect and why
            stop_pct_eff = max(self.base_stop_pct,
                               self.stop_vol_mult * vol_state.sigma_bar_pct) * \
                macro_state.playbook.get("stop_mult", 1.0) * self.monitor.stop_widen
            target_pct = self.sizer.b * stop_pct_eff
            ev_pct = (p_win * target_pct - (1 - p_win) * stop_pct_eff) - \
                decision.est_cost_bps / 100.0
            # the thesis must record the bet actually TRADED: with an armed
            # bracket the exit geometry is the bracket's own legs, not the
            # legacy stop/target above (2026-07-29 unit audit - postmortem's
            # stop-gap check graded bracket positions against a stop they
            # do not trade). Threads to BOTH thesis sites (direct entry and
            # every ladder rung) since both read these three names.
            if bracket_pt_frac > EPS and bracket_sl_frac > EPS:
                stop_pct_eff = bracket_sl_frac * 100.0
                target_pct = bracket_pt_frac * 100.0
                ev_pct = (p_win * target_pct
                          - (1 - p_win) * stop_pct_eff) \
                    - decision.est_cost_bps / 100.0
            # ML-075 shadow score: the CHAMPION's armed prediction, captured even
            # when the governor has KILLED the model (use_model=False) so it
            # never reached the sizer. Telemetry-only - it changes no trade;
            # it lets a killed model re-arm on evidence at close. When the model
            # is live, model_p already IS the champion's call (no extra predict).
            shadow_p = model_p if self.monitor.use_model else (
                self.meta.p_win(feats, gate_conf,
                                shrinkage=self.monitor.shrink_base,
                                use_model=True)
                if self.meta.trained else -1.0)
            self.postmortem.register_entry(TradeThesis(
                position_id=position_id, asset=asset, symbol=symbol,
                direction=signal.direction, entry_ts=now, p_win=p_win,
                expected_ret_pct=ev_pct,
                expected_cost_bps=decision.est_cost_bps,
                stop_pct=stop_pct_eff, target_pct=target_pct,
                entry_regime=macro_state.label, entry_liq=liq_state.label,
                narrative_label=verdict.label,
                fair_value=fv_state.fair_value, quote_price=entry_price,
                price_decimals=_price_decimals(
                    getattr(self.orders, "pair_meta", {}),
                    self.kraken.kraken_pair(symbol), entry_price),
                # exploration trades carry a FORCED p_win (explore_p_win) for
                # sizing, so the governor must never grade the model on p_win
                # here - but the model's OWN call (model_p) is honest evidence
                # on every fill. Grading model_p keeps the window alive at
                # small equity where exploration is most of the flow; the old
                # not-explored exclusion starved the window and froze the
                # governor (kelly pinned at 0.7, then a kill-switch deadlock).
                model_p=model_p, shadow_p=shadow_p,
                model_scored=(self.monitor.use_model and self.meta.trained)))
            notional_usd = decision.size_units * entry_price
            if self.algo.should_engage(notional_usd):
                parent = self.algo.create_parent(
                    asset, symbol, side, signal.direction,
                    decision.size_units,
                    arrival_price=self.marks.get(symbol) or entry_price,
                    now=now, sigma_bar_pct=vol_state.sigma_bar_pct,
                    urgency=getattr(signal, "urgency", 0.0),
                    candles=v.get("candles"))
                self.sizer.note_entry(asset, now)
                self._algo_meta[parent.parent_id] = {
                    "p_win": p_win, "edge_bps": decision.est_edge_bps,
                    "est_cost_bps": decision.est_cost_bps,
                    "features": feats, "leverage":
                        lev_decision.allowed_leverage,
                    "post_only": plan.post_only,
                    "probe": explored,
                    # SPB-R review fix #2 (2026-07-31): carry the priced
                    # admit's cost ON THE PARENT TEMPLATE and clear the
                    # decision stash NOW - the first successful child
                    # deducts it explicitly (cost= at the record hook), so
                    # a LATER decision's pointer can never be charged
                    # against this parent (the wrong-arm hazard), and a
                    # parent whose first child submits cycles later still
                    # deducts the right price (closes R2's under-charge).
                    # Algo probes still never refund (R3, conservative).
                    "probe_cost": ((getattr(self, "_pending_probe_cost",
                                            None) or {}).pop(asset, None)
                                   if explored else None),
                    "candidate_id": cand_id or "",
                    "avail": feat_avail,
                    "thales_fired": self._thales_fired.get(asset) or [],
                    "gates_passed": getattr(self, "_sig_gates", {}).get(asset) or {},
                    "gate_components": dict(getattr(signal, "components", None) or {}),
                    "bracket_pt_frac": bracket_pt_frac,
                    "bracket_sl_frac": bracket_sl_frac,
                    "bracket_deadline_ts": bracket_deadline_ts}
                if explored:
                    self._pending_probe_asset = None
                self._mark_cand(asset, signal.direction, "entered")
                # admission-record asymmetry fix (post-program review): the
                # probe-share window records "an order actually went out" -
                # the SAME semantic the direct path uses below (recorded
                # only on a successful order.submit). Recording HERE, before
                # any child order is even attempted, meant a parent whose
                # first child got rejected still filled the share window.
                # _submit_algo_child now records the ONE admission for this
                # parent on its FIRST successful child submit.
                self._submit_algo_child(parent, now)   # first slice now
                log.info(
                    f"ENTRY-ALGO {signal.direction} {symbol} "
                    f"[{parent.algo}]: ${notional_usd:,.0f} sliced over "
                    f"{self.algo.max_children} children | p={p_win:.2f}")
                reserved_entries += 1                  # committed a slot
                if not self.capital.can_open_new_position(
                        self.state, reserved_entries):
                    can_enter = False
                continue
            # ---- v10 logistic-armed grid ladder ------------------------
            # split the ONE sizer-approved entry into decay-sized maker
            # rungs when p(win) clears the arm bar; ladder total == the
            # sized units exactly, rung count capped by free slots + the
            # per-asset same-side inventory cap so fills can't breach
            # either. Not handled -> the legacy single-entry path below.
            reserved_entries, can_enter, handled = self._ladder_entry(
                position_id=position_id, asset=asset, symbol=symbol,
                side=side, signal=signal, entry_price=entry_price,
                decision=decision, sized=sized, lev=lev_decision,
                equity=equity, vol_state=vol_state, fv_state=fv_state,
                macro_state=macro_state, liq_state=liq_state,
                verdict=verdict, feats=feats, feat_avail=feat_avail,
                explored=explored,
                p_win=p_win, model_p=model_p, shadow_p=shadow_p,
                ev_pct=ev_pct, stop_pct_eff=stop_pct_eff,
                target_pct=target_pct, now=now,
                reserved_entries=reserved_entries, can_enter=can_enter,
                cand_id=cand_id, bracket_pt_frac=bracket_pt_frac,
                bracket_sl_frac=bracket_sl_frac,
                bracket_deadline_ts=bracket_deadline_ts)
            if handled:
                continue

            # F6 Rule 534 self-cross guard: BEFORE any marketable (non-
            # post_only) sell on this pair, cancel our own resting long-book
            # entry bid first (see _clear_long_book_bid_before_sell). No-op
            # for a maker_first post_only rest, and for a buy-side entry.
            # getattr-guarded: unit tests exercise this off a minimal stub
            # self (SimpleNamespace) that may not define the guard method at
            # all - the same pattern as _record_probe_admission elsewhere.
            _lb_guard = getattr(self, "_clear_long_book_bid_before_sell", None)
            if callable(_lb_guard):
                _lb_guard(asset, side, plan.post_only, reason="entry")
            # SPB-R §1.4: a budget-mode priced probe carries its scarcity
            # cost on the order so the unfilled-terminal refund seam
            # (_maybe_refund_probe_order) can key on the ORDER lifecycle.
            # share_cap mode has an always-empty stash -> None -> the key
            # is never added and legacy order.meta stays byte-identical.
            _spbr_cost = (getattr(self, "_pending_probe_cost", None)
                          or {}).get(asset) if explored else None
            order = self.orders.submit(
                asset=asset, symbol=symbol,
                pair=self.kraken.kraken_pair(symbol), side=side,
                price=entry_price, size=decision.size_units, purpose="entry",
                position_id=position_id, post_only=plan.post_only,
                leverage=lev_decision.allowed_leverage,
                # mark, else fair value — both INDEPENDENT of the order price.
                # Never fall back to entry_price (the order's own price): that
                # self-reference zeroes the collar deviation and defeats the
                # firewall's fail-closed entry refusal. No independent reference
                # -> pass None and let the firewall refuse this blind entry.
                ref_price=self.marks.get(symbol) or fv_state.fair_value,
                equity=equity,
                book=self.kraken_books.get(asset) or {},
                sigma_bar_pct=vol_state.sigma_bar_pct,
                meta={"p_win": p_win, "edge_bps": decision.est_edge_bps,
                    "est_cost_bps": decision.est_cost_bps,
                    "features": feats, "probe": explored,
                    "candidate_id": cand_id or "",
                    "avail": feat_avail,
                    "thales_fired": self._thales_fired.get(asset) or [],
                    "gates_passed": getattr(self, "_sig_gates", {}).get(asset) or {},
                    "gate_components": dict(getattr(signal, "components", None) or {}),
                    "bracket_pt_frac": bracket_pt_frac,
                    "bracket_sl_frac": bracket_sl_frac,
                    "bracket_deadline_ts": bracket_deadline_ts,
                    **({"probe_cost": _spbr_cost}
                       if _spbr_cost is not None else {})},
                now=now,
            )
            if order:
                self.sizer.note_entry(asset, now)
                self._mark_cand(asset, signal.direction, "entered")
                self._record_probe_admission(explored)
                self._last_entry_admit_ts = now        # ML-073 drought clock
                reserved_entries += 1                  # committed a slot
                if not self.capital.can_open_new_position(
                        self.state, reserved_entries):
                    can_enter = False
                log.info(
                    f"ENTRY {signal.direction} {symbol} [{plan.style}]: "
                    f"${decision.size_units * entry_price:,.0f} "
                    f"({decision.size_units:.6f}) @ "
                    f"{self._px(symbol, entry_price)} | "
                    f"p={p_win:.2f} edge={decision.est_edge_bps:.0f}bps "
                    f"cost={decision.est_cost_bps:.0f}bps regime={macro_state.label} "
                    f"narrative={verdict.label}")

        # Compounder Phase C (task C4): the long-horizon accumulation book's
        # own decision cycle, AFTER the 5m entry loop above (a completely
        # separate call, not folded into the loop body - the long book has
        # its own fixed asset list, not the 5m rotation/entry_assets() view).
        self._long_book_cycle(now, sentiment=sentiment, web=web, risk=risk)

    def _surface_kraken_imbalance(self, asset: str, v: dict, kbook: dict,
                                  ls) -> None:
        """v9 flow unlock: Kraken-only listings (SUI/ARB/MINA/FLOW) carry no
        external cross-venue imbalance from build_view, so the alpha's flow
        gate read a defaulted 1.0 (s_flow==0) and could NEVER confirm — the
        true reason only ETH/BTC ever filled. Surface the exec-book imbalance
        the regime engine already computed so those assets can generate a
        signal. Guarded three ways so it never feeds the alpha a bad number:
        (1) only assets with NO external venue (a major keeps its external
        imbalance even on a cycle its feed drops); (2) only a FRESH Kraken
        book (kbook is {} past critical staleness — never surface a frozen
        book); (3) only a two-sided, measurable book (spread<900 sentinel —
        a one-sided book's 3.0 imbalance sentinel would fabricate a max-long
        signal)."""
        if (v.get("imbalance_ratio") is None
                and asset not in self._external_bases
                and bool(kbook) and ls.spread_bps < 900.0):
            v["imbalance_ratio"] = ls.imbalance_ratio

    # ------------------------------------------------------------------
    # Compounder Phase C: long-horizon accumulation book (task C4)
    # ------------------------------------------------------------------
    def _long_book_dd_frac(self, equity: float) -> float:
        """Task C5 item 3(a): the long book's OWN equity-curve peak and
        current drawdown, as a fraction of TOTAL portfolio equity (the
        same equity-fraction convention every other long-book ceiling in
        this module uses). Kept simple and honest: a running curve of
        cumulative realized PnL from every long-book close
        (self._long_book_realized_pnl_total, fed by _finalize_position)
        plus the unrealized mark-to-market of every currently open
        long-book position. The all-time PEAK of that curve is a
        ratchet (persisted, monotonic non-decreasing) so one bad cycle's
        drawdown is measured against the book's own best-ever mark, not
        a value that could itself slip backward.

        Phase-C whole-phase review, Minor #5: the mark read is
        `self.marks.get(p.symbol) or p.entry_price` - the SAME
        zero/None-guarded fallback this method's own sibling book-
        exposure sums use (main._long_book_cycle's book_exposure_usd/
        book_exposure_usd_snapshot) - not `.get(p.symbol, p.entry_price)`,
        whose default only ever applies when the KEY is absent. A 0.0
        mark (a bad/stale tick, key present with value 0.0) read
        literally would fabricate a huge phantom unrealized loss (and a
        false dd-ladder downgrade) from a single bad tick instead of
        degrading to "no fresh mark, use entry_price"."""
        unrealized = sum(
            ((self.marks.get(p.symbol) or p.entry_price) - p.entry_price)
            * p.size
            for p in self.state.open_positions() if p.book == "long")
        book_value = self._long_book_realized_pnl_total + unrealized
        self._long_book_peak_value = max(self._long_book_peak_value,
                                         book_value)
        if equity <= 0:
            return 0.0
        return max(self._long_book_peak_value - book_value, 0.0) / equity

    def _long_book_ladder_maintenance(self, ctx_state, now: float,
                                      equity: float,
                                      book_exposure_usd: float,
                                      stress_max: float,
                                      lb_cfg: dict) -> None:
        """Book-wide (not per-asset) evidence-ladder upkeep, ONE call per
        _long_book_cycle pass: the downgrade drawdown check (task C5 item
        3(a)) and the adverse-context-transition-survived episode tracker
        (item 3(b)). Both reuse the SAME `ctx_state` local the caller
        already bound from the polled context snapshot - no new context-
        attribute read site (tests/test_context_integration.py's source
        pin stays at exactly 2 references to that polled-context
        attribute in main.py)."""
        dd_frac = self._long_book_dd_frac(equity)
        dd_threshold = self.long_ladder.cfg.dd_downgrade_pct / 100.0
        breached = dd_frac >= dd_threshold
        # edge-triggered: maybe_downgrade has no internal edge-detection
        # (risk/long_book.py's own docstring) - a still-breached dd_frac
        # every cycle must apply exactly ONE downgrade per breach episode.
        if breached and not self._long_book_dd_breach_active:
            if self.long_ladder.maybe_downgrade(dd_frac):
                detail = tag(Code.LB_RUNG_DOWN,
                            f"long-book drawdown {dd_frac:.2%} >= "
                            f"{dd_threshold:.2%} - instant one-rung "
                            f"downgrade (rung now "
                            f"{self.long_ladder.rung()})")
                get_audit().log("long_book", Code.LB_RUNG_DOWN, detail,
                                {"dd_frac": round(dd_frac, 4),
                                 "rung": self.long_ladder.rung()})
                log.warning(detail)
            self._long_book_dd_breach_active = True
        elif not breached:
            self._long_book_dd_breach_active = False

        # adverse-transition-survived episode tracker (C2 design, C4-
        # review item 3(b)): a risk-off episode is stress KNOWN and >
        # stress_max_for_add, SUSTAINED for ladder.cfg.adverse_min_hours.
        # note_adverse_transition_survived() fires once, on the episode's
        # END, only when the book held exposure and stayed under the
        # downgrade line for the WHOLE episode.
        stress_known = bool(getattr(ctx_state, "stress_known", False))
        stress = getattr(ctx_state, "stress", None)
        in_episode_now = stress_known and stress is not None \
            and stress > stress_max
        held_exposure_now = book_exposure_usd > 0.0
        dd_ok_now = dd_frac < dd_threshold
        if in_episode_now:
            if self._long_book_adverse_episode_start is None:
                self._long_book_adverse_episode_start = now
                self._long_book_adverse_held_exposure = held_exposure_now
                self._long_book_adverse_dd_ok = dd_ok_now
            else:
                self._long_book_adverse_held_exposure = (
                    self._long_book_adverse_held_exposure
                    and held_exposure_now)
                self._long_book_adverse_dd_ok = (
                    self._long_book_adverse_dd_ok and dd_ok_now)
        elif self._long_book_adverse_episode_start is not None:
            adverse_min_hours = self.long_ladder.cfg.adverse_min_hours
            duration_h = (now - self._long_book_adverse_episode_start) \
                / 3600.0
            if duration_h >= adverse_min_hours \
                    and self._long_book_adverse_held_exposure \
                    and self._long_book_adverse_dd_ok:
                self.long_ladder.note_adverse_transition_survived()
                detail = tag(
                    Code.LB_ADVERSE_SURVIVED,
                    f"long-book survived a {duration_h:.1f}h adverse "
                    "context episode (exposure held, dd stayed under "
                    "the downgrade line) - adverse_transitions_survived "
                    f"now {self.long_ladder.adverse_transitions_survived}")
                get_audit().log(
                    "long_book", Code.LB_ADVERSE_SURVIVED, detail,
                    {"duration_h": round(duration_h, 2)})
                log.info(detail)
            self._long_book_adverse_episode_start = None

    def _long_book_cycle(self, now: float, sentiment=None, web=None,
                        risk=None) -> None:
        """One accumulation decision per configured long_book asset,
        called from slow_cycle AFTER the 5m entry loop. Long-only,
        post_only maker bids that AVERAGE into the book's single growing
        position per asset (_handle_fill's averaging branch) - never a
        second same-book position on one asset (Global Constraint).

        `sentiment`/`web`/`risk` (C5-discovered spec gap fix): slow_cycle's
        own already-polled locals, threaded through purely so
        _place_long_book_add can assemble a REAL feature vector at add
        time (see that method's docstring). All default None so a direct/
        unit-test caller that predates this parameter keeps working
        unchanged.

        Gate order mirrors LongBookEngine.decide_add's own docstring
        (halted/entries_enabled -> averaging -> spacing -> event window ->
        context -> ceiling), PLUS this engine's own conviction-formula
        term-4 re-check (context_aligned) between decide_add's plan and
        sizing. By construction decide_add's OWN context gate already
        denies a misaligned/unknown context before ever returning a plan,
        so reaching the conviction call below means context_aligned is
        already True (or None, if context was never required known) -
        this second check is a governance/audit-consistency backstop (the
        SAME conviction ledger the 5m book feeds via _conviction_
        disposition), not the primary blocking mechanism. Documented as a
        deliberate design reading of the brief in task-C4-report.md.

        Combined envelope: sizing goes through the LONG PositionSizer
        instance (_place_long_book_add), which internally applies the
        SHARED RiskProtocolStack multiplier and consults the SHARED
        InventoryManager.can_add - the long book never gets its own risk
        stack. `halted`/`entries_enabled` are recomputed here (not just
        inherited from slow_cycle's own early-returns above) so this
        method is independently correct under a direct/stub-bot call,
        exactly mirroring LongBookEngine.decide_add's own two new-risk
        gates.

        C4 review additions (Critical #1, Important #3, Minor #8): per-
        asset retry backoff after a post-plan sizing/submission failure
        (checked first, cheapest); a book-aware resting-order lookup that
        either leaves a still-fresh bid alone (never double-submits — the
        resting bid IS the dedup lock) or cancels-and-replaces a stale one
        THIS SAME pass (at most once per asset per pass, by construction —
        one loop iteration); and book_exposure_usd now also counts every
        currently-resting long-book entry order's notional, not just
        filled positions (load-bearing now that order_ttl_hours can leave
        a bid resting for hours — otherwise two assets in the SAME pass
        could each commit up to the full ceiling, a same-cycle cross-asset
        double-commit)."""
        lb_cfg = self.config.get("long_book", {}) or {}
        if not bool(lb_cfg.get("enabled", False)):
            return
        assets = lb_cfg.get("assets", []) or []
        if not assets:
            return
        equity = self._equity()
        if equity <= EPS:
            return
        fm = getattr(self, "fault", None)
        halted = bool(self._halted) or \
            (fm is not None and not fm.allow_new_risk())
        entries_enabled = bool(self.entries_enabled) and \
            self._live_order_allowed("entry")
        # ONE read of the context snapshot, shared across every asset this
        # cycle (context is a systemwide macro signal, not per-asset) -
        # the sole new _context_state consumer site this task adds
        # (tests/test_context_integration.py's source pin is updated to
        # allow exactly this).
        ctx_state = self._context_state
        stress_max = float(lb_cfg.get("context", {})
                           .get("stress_max_for_add", 1.0))
        stress_known = bool(getattr(ctx_state, "stress_known", False))
        stress = getattr(ctx_state, "stress", None)
        context_aligned = (stress <= stress_max) \
            if (stress_known and stress is not None) else None
        self._long_context_aligned_last = context_aligned
        # parsed ONCE for the whole cycle: shared by the staleness check
        # below and threaded into _place_long_book_add so it isn't
        # re-parsed per asset.
        ecfg = EngineConfig.from_dict(lb_cfg)

        # task C5 item 5 (euphoria give-back): reuses the SAME `ctx_state`
        # local above, so no new polled-context read site. Cheap,
        # idempotent - safe to call every cycle regardless of whether the
        # phase actually changed since the last one.
        self.long_tier_engine.set_phase(
            getattr(ctx_state, "halving_phase", ""))

        # task C5 items 3(a)/3(b): book-wide (not per-asset) downgrade +
        # adverse-transition-survived upkeep, computed ONCE per cycle from
        # a fresh book-wide exposure snapshot (deliberately taken here,
        # BEFORE any per-asset cancel-and-replace below might change it -
        # a coarser, more stable figure is appropriate for a book-level
        # drawdown/episode concept, unlike the per-asset ceiling-headroom
        # figure recomputed fresh inside the loop below).
        book_exposure_usd_snapshot = sum(
            p.size * (self.marks.get(p.symbol) or p.entry_price)
            for p in self.state.open_positions() if p.book == "long") + \
            sum(o.remaining * o.price for o in self._long_book_open_orders())
        self._long_book_ladder_maintenance(
            ctx_state, now, equity, book_exposure_usd_snapshot, stress_max,
            lb_cfg)

        for asset in assets:
            symbol = self.symbol_map.get(asset)
            if not symbol:
                continue
            mark = self.marks.get(symbol)
            if not mark or mark <= 0:
                continue

            # Important #3(a): a post-plan sizing/submission failure backs
            # this asset off for retry_backoff_minutes instead of
            # re-running decide_add (and re-auditing the SAME sizer/
            # submit/conviction denial) every ~30s slow_cycle tick.
            if now < self._long_retry_backoff_until.get(asset, 0.0):
                continue

            # Critical #1(b)/(c): the resting bid IS the dedup lock - at
            # most one long-book entry order rests per asset at a time
            # (has_open is now book-aware, Minor #10, though this reads
            # open_orders() directly to get the object, not just a bool).
            # Still fresh -> leave it alone (never double-submit). Stale
            # (mark drifted past add_offset_pct + zone_tol_pct +
            # zone_buffer_pct - phase-C review Important #1: the full
            # collar-coherence band, matching a magnet-shifted bid's own
            # worst-case rest distance from mark, not just offset+buffer
            # - or a resubmit's collar would now refuse it) -> cancel and let
            # THIS SAME pass re-decide/re-place at the fresh level (the
            # collar re-checks naturally on resubmit) - at most one
            # replace per asset per pass, by construction (one iteration).
            resting = next(
                (o for o in self._long_book_open_orders() if o.asset == asset),
                None)
            if resting is not None:
                if bid_is_stale(mark, resting.price, ecfg.add_offset_pct,
                                ecfg.zone_buffer_pct, ecfg.zone_tol_pct):
                    # F8 (market-conduct pass): a dedicated LB-021 code for
                    # the cancel-for-reprice audit, replacing the prior
                    # LB_ADD_DENIED kind="reprice" overload - nothing here
                    # was denied, the SAME add replaces at a fresh level
                    # this same pass. The OM cancel reason is now the
                    # tagged string itself, not a bare literal.
                    detail = tag(Code.LB_BID_REPRICED,
                                f"{asset}: resting bid stale vs mark - "
                                f"cancelled for reprice")
                    self.orders.cancel_order(resting, reason=detail)
                    get_audit().log(
                        "long_book", Code.LB_BID_REPRICED, detail,
                        {"asset": asset, "kind": "reprice",
                         "old_price": resting.price, "mark": mark})
                else:
                    continue

            position = next(
                (p for p in self.state.open_positions()
                 if p.book == "long" and self._asset_of(p.symbol) == asset),
                None)
            # combined envelope: the WHOLE book's exposure across every
            # long-book asset (not just this one) - the ceiling headroom
            # LongBookEngine.decide_add computes lives inside the shared
            # portfolio heat cap, never a per-asset budget. Minor #8: also
            # counts every resting long-book entry order's notional
            # (re-fetched fresh - the cancel above, if it fired, must not
            # still be counted).
            book_exposure_usd = sum(
                p.size * (self.marks.get(p.symbol) or p.entry_price)
                for p in self.state.open_positions() if p.book == "long") + \
                sum(o.remaining * o.price
                    for o in self._long_book_open_orders())

            plan_or_deny = LongBookEngine.decide_add(
                now=now, asset=asset, mark=mark,
                sigma_bar_pct=self.vol.state(asset).sigma_bar_pct,
                context_state=ctx_state, ladder=self.long_ladder,
                position=position,
                last_add_ts=self._long_last_add_ts.get(asset),
                dry_run=self.dry_run, halted=halted,
                entries_enabled=entries_enabled,
                equity=equity, book_exposure_usd=book_exposure_usd,
                cfg=lb_cfg,
                macro_regime_label=self.macro.state(asset).label)

            if isinstance(plan_or_deny, DenyReason):
                self._long_book_deny(asset, plan_or_deny, now)
                continue

            deny_code = self._long_book_conviction_gate(
                asset, context_aligned)
            if deny_code is not None:
                detail = tag(Code.LB_ADD_DENIED,
                            f"{asset}: conviction term-4 denied "
                            f"({deny_code.value})")
                self._long_last_deny = detail
                log.info(detail)
                # task C5 item 6 (deny-debounce): an enforce-mode
                # conviction denial repeats every ~30s slow_cycle tick
                # while the underlying disposition persists - audit on
                # TRANSITION (a different deny_code, or the asset's
                # first-ever denial) or after retry_backoff_minutes has
                # elapsed since the last emission, reusing the SAME knob
                # _long_book_note_failure debounces post-plan failures
                # with (task C4 Important #3a).
                if self._long_book_deny_gate(
                        asset, f"conviction:{deny_code.value}", now,
                        ecfg.retry_backoff_minutes):
                    get_audit().log(
                        "long_book", Code.LB_ADD_DENIED, detail,
                        {"asset": asset,
                         "conviction_code": deny_code.value})
                # phase-C whole-phase review, Important #2: a persistent
                # conviction denial must back this asset off exactly like
                # the sizer/submit failure branches below
                # (_place_long_book_add) - otherwise the deny-gate above
                # only debounces the AUDIT row while decide_add and this
                # conviction re-check both re-run every ~30s slow_cycle
                # tick for as long as the disposition holds.
                self._long_book_note_failure(asset, now,
                                             ecfg.retry_backoff_minutes)
                continue

            self._place_long_book_add(
                asset, symbol, position, plan_or_deny, equity, now,
                ecfg=ecfg, sentiment=sentiment, web=web, risk=risk)

    def _long_book_open_orders(self) -> list:
        """Every currently-resting long-book ENTRY order (any asset) -
        purpose=="entry" AND meta["book"]=="long" (defaults "5m", same
        convention as main._handle_fill's own order.meta.get("book",
        "5m")). Shared by _long_book_cycle's cancel-and-replace staleness
        check and Minor #8's book-wide resting-notional headroom figure."""
        return [o for o in self.orders.open_orders()
               if o.purpose == "entry" and o.meta.get("book", "5m") == "long"]

    def _long_book_deny_gate(self, asset: str, kind: str, now: float,
                             retry_backoff_minutes: float) -> bool:
        """Task C5 item 6 (deny-debounce, C4 re-review latent finding):
        returns True the FIRST time for a given (asset, kind) pair - a
        kind change (including the asset's first-ever call) always
        re-arms immediately, since the debounce only suppresses
        IDENTICAL repeat noise, never a genuine change of disposition -
        or after `retry_backoff_minutes` has elapsed since the last True
        return for the SAME kind. False on every repeat call in between;
        the caller must skip its audit emission on False. Reuses the
        SAME retry_backoff_minutes knob _long_book_note_failure debounces
        post-plan failures with (task C4 Important #3a) rather than a new
        config knob for an identical "don't re-fire every ~30s tick"
        concept. NOT persisted - process-local, like
        _long_book_retry_backoff_until (a restart costs at most one extra
        audit row, never a stuck suppression)."""
        state = self._long_book_deny_state.get(asset)
        if state is None or state.get("kind") != kind or \
                now - state.get("ts", 0.0) >= float(retry_backoff_minutes) \
                * 60.0:
            self._long_book_deny_state[asset] = {"kind": kind, "ts": now}
            return True
        return False

    def _long_book_deny(self, asset: str, deny: DenyReason,
                        now: float) -> None:
        """Log + selectively audit one long-book DenyReason (LB-010, plus
        LB-050/CX-030 riding along on the qualifying kinds - core/codes.py's
        own comments). "spacing" is the OVERWHELMING routine case (a
        24h-scale cadence evaluated every ~30s slow_cycle) - python-logged
        at DEBUG and NOT durably audit-logged there, or the hash-chained
        audit trail would carry thousands of no-op rows per add cycle; a
        contraction-scaled spacing denial is the exception (LB-050 rides
        along - risk/long_book.py's own DenyReason.detail string flags
        contraction-scaling explicitly, and it is a rarer, notable cadence
        state, not the routine wait).

        Task C5 item 6 (deny-debounce): event_window/context_unknown/
        context_misaligned/crisis repeat IDENTICALLY every ~30s tick
        while the underlying condition persists (an event window can run
        for hours, a stress-misaligned regime for days) - auditing every
        tick would flood the hash-chained trail with no new information.
        Task C6 (C5 review, Minor 5): "ceiling" joins the debounced set
        for the identical reason - a book parked at its ceiling with no
        closed position to free headroom denies IDENTICALLY every pass,
        potentially for as long as the ceiling holds (C5 left it
        undebounced deliberately, "not named in the brief" - this task
        closes that gap). Emitted on TRANSITION (a kind change, or the
        asset's first-ever denial) or after retry_backoff_minutes has
        elapsed since the last emission for this SAME kind
        (_long_book_deny_gate). Python-log line above stays unconditional
        (process log noise, not the audited trail).

        Phase-C whole-phase review, Important #3: contraction_spacing now
        ALSO joins the debounced set (a distinct "contraction_spacing"
        gate kind, so it never collides with a plain "spacing" call -
        which never reaches this branch anyway, the early-return above
        handles it). C4/C5 deliberately left it undebounced on the theory
        it was "rarer and notable"; whole-phase math instead shows
        ~11.5k rows/day/asset during a halving contraction phase (which
        runs for MONTHS, not hours) - the exact same "thousands of no-op
        rows" problem the other debounced kinds exist to prevent. The
        audited `kind` in the row itself stays "spacing" (unchanged
        audit-trail contract); only the internal debounce-state key
        differs.

        Minor #6 (determinism wart): `now` is required, no wall-clock
        fallback - every in-tree caller (main._long_book_cycle) already
        passes it."""
        self._long_last_deny = deny.detail
        detail = tag(Code.LB_ADD_DENIED, f"{asset}: {deny.detail}")
        contraction_spacing = deny.kind == "spacing" and \
            "(contraction-scaled)" in deny.detail
        if deny.kind == "spacing" and not contraction_spacing:
            log.debug(detail)
            return
        log.info(detail)
        if deny.kind in ("event_window", "context_unknown",
                        "context_misaligned", "crisis", "ceiling") \
                or contraction_spacing:
            backoff_min = float((self.config.get("long_book", {}) or {})
                                .get("retry_backoff_minutes", 30.0))
            gate_kind = "contraction_spacing" if contraction_spacing \
                else deny.kind
            if not self._long_book_deny_gate(asset, gate_kind, now,
                                             backoff_min):
                return
        get_audit().log("long_book", Code.LB_ADD_DENIED, detail,
                        {"asset": asset, "kind": deny.kind})
        if deny.kind == "context_unknown":
            cx_detail = tag(Code.CX_CONTEXT_UNKNOWN,
                           f"{asset}: long-book add blocked - context "
                           f"stress dial unknown")
            get_audit().log("long_book", Code.CX_CONTEXT_UNKNOWN,
                            cx_detail, {"asset": asset})
        if deny.kind in ("event_window", "context_unknown", "crisis") or \
                contraction_spacing:
            pause_detail = tag(Code.LB_PAUSED, f"{asset}: {deny.detail}")
            get_audit().log("long_book", Code.LB_PAUSED, pause_detail,
                            {"asset": asset, "kind": deny.kind})

    def _long_book_conviction_gate(self, asset: str,
                                   context_aligned: Optional[bool]
                                   ) -> Optional[Code]:
        """Route a long-book admission through the SAME conviction-formula
        ledger the 5m book feeds (Global Constraint: "context before
        conviction" - term 4, CV-040). Terms 1-2 (agreement/EV) are
        genuinely NOT APPLICABLE to this book: it has no gate-pass
        fraction or pretrade EV estimate of its own to offer, so both are
        passed as None (risk/conviction.py's evaluate: None = auto-pass,
        recorded as null in the audit terms) - C4 review, Important #4.
        This REPLACES the prior fabricated agreement=1.0 / est_edge_bps=
        1.0 / est_cost_bps=0.0 stand-ins (a faked pass looks identical to
        a real one in the audit trail; None is honest about "not
        measured"). regime_label uses the REAL current macro regime label
        (self.macro.state) so term 3 reads the SAME live-label evidence-
        coverage floor the 5m book's own conviction calls read - a
        considered reuse of a real systemwide corpus-quality signal
        (documented choice, not a brief literal - see task-C4-report.md).
        feed_governor=False (Important #3b): this book's ~24h-scale
        cadence must not pollute the SHARED conviction cadence governor,
        whose rolling windows/thresholds were derived for the 5m book's
        per-signal selectivity."""
        signal = types.SimpleNamespace(gates_passed=None)
        decision = types.SimpleNamespace(est_edge_bps=None, est_cost_bps=None)
        regime_label = self.macro.state(asset).label
        return self._conviction_disposition(
            asset, signal, decision, regime_label, False,
            context_aligned=context_aligned, feed_governor=False)

    def _long_book_note_failure(self, asset: str, now: float,
                                retry_backoff_minutes: float) -> None:
        """Important #3(a) (C4 review): a post-plan sizing/submission
        failure (manip veto, sizer veto, sub-EPS notional, order-manager
        refusal) backs THIS asset off for retry_backoff_minutes rather
        than letting _long_book_cycle re-run decide_add - and re-audit
        the identical failure - every ~30s slow_cycle tick."""
        self._long_retry_backoff_until[asset] = \
            now + float(retry_backoff_minutes) * 60.0

    def _place_long_book_add(self, asset: str, symbol: str,
                             position: Optional[Position], plan: AddPlan,
                             equity: float, now: float,
                             ecfg: Optional[EngineConfig] = None,
                             sentiment=None, web=None, risk=None) -> None:
        """Size + submit ONE long-book add. Sizing goes through the LONG
        PositionSizer instance (self.long_sizer) with a NEUTRAL, non-
        regime-gated macro state constructed fresh here - the 5m book's
        own regime playbook (direction_bias / allow_new) must not veto an
        accumulation buy LongBookEngine.decide_add's own gates already
        cleared (decide_add has no regime gate at all in its documented
        order - feeding the REAL macro_state would silently add an
        undocumented veto surface, e.g. refusing every long in a "bear"-
        labeled regime, defeating a buy-the-dip accumulation book by
        construction). Real vol/liq state for THIS asset still apply
        (legitimate sizing signals, no reason to neutralize). p_win=1.0
        (fixed): admission is decided upstream (decide_add's gate chain +
        the conviction term-4 gate above), never by the sizer's own
        p-bar - the Kelly math here is a formality, always bounded down to
        `plan.usd` (the ladder's own ceiling-headroom budget for this
        add) as a HARD CAP applied AFTER sizing, never the reverse (the
        sizer's protocols/inventory/drawdown-throttle machinery can only
        shrink the ticket further, never inflate it past the ladder's
        budget).

        `ecfg` (C4 review): the caller (_long_book_cycle) passes its
        already-parsed EngineConfig so this isn't re-parsed per asset;
        optional (defaults to a fresh parse) so direct/unit-test callers
        that predate this parameter keep working unchanged.

        C4 review additions: Important #5 (THALES manip gate, SZ-045
        parity - the SAME anti-scalp veto/downsize the 5m book's new-risk
        entries go through, main.py's 5m entry loop ~2841) runs BEFORE
        sizing; Important #2 (measured maker-entry/taker-exit round-trip
        est_cost_bps, replacing the prior hardcoded 0.0); Critical #1a
        (order_ttl_hours threaded into OrderManager.submit's ttl_sec
        override instead of the shared ~25s order_timeout_sec); Critical
        #1c (the submit-time _long_last_add_ts stamp is REMOVED - the
        spacing clock now keys on FILL, main._handle_fill); Important #3a
        (every failure branch below backs this asset off via
        _long_book_note_failure).

        `sentiment`/`web`/`risk` (C5-discovered spec gap fix, task C5-fix):
        threaded from slow_cycle (via _long_book_cycle) purely so a REAL
        feature vector can be assembled at add time - see the block below
        that mirrors the 5m entry loop's own build_features call site
        (main.py's 5m loop ~2814-2823). All three default None: a direct/
        unit-test caller that predates this parameter (every STUB-harness
        test in tests/test_long_book_integration.py) keeps working
        unchanged - feature assembly degrades to a skip (see below), it
        never raises for a missing input."""
        ecfg = ecfg or EngineConfig.from_dict(
            self.config.get("long_book", {}) or {})
        vol_state = self.vol.state(asset)
        liq_state = self.liq.state(asset)

        # Important #5 (C4 review, SZ-045 parity): anti-scalp manipulation
        # gate - a long-book add is new risk exactly like a 5m entry, so
        # it goes through the SAME veto/downsize band (main.py's 5m entry
        # loop reads self._manip_scores/_manip_gate_enabled/_manip_
        # downsize_at/_manip_veto_at/_manip_min_scale identically).
        manip_scale = 1.0
        if self._manip_gate_enabled:
            ms = float(self._manip_scores.get(asset, 0.0))
            scale = manip_entry_scale(ms, self._manip_downsize_at,
                                      self._manip_veto_at,
                                      self._manip_min_scale)
            if scale is None:
                detail = tag(Code.LB_ADD_DENIED,
                            f"{asset}: manip suspect {ms:.2f} >= veto "
                            f"{self._manip_veto_at:.2f} "
                            f"({Code.SZ_MANIP_SUSPECT.value})")
                self._long_last_deny = detail
                log.info(detail)
                get_audit().log("long_book", Code.LB_ADD_DENIED, detail,
                                {"asset": asset, "kind": "manip",
                                 "manip_score": ms})
                self._long_book_note_failure(asset, now,
                                             ecfg.retry_backoff_minutes)
                return
            manip_scale = scale

        neutral_macro = MacroRegimeState(
            asset=asset, label="long_book",
            playbook={"direction_bias": "both", "size_mult": 1.0,
                     "allow_new": True, "counter_trend_conf_bonus": 0.0,
                     "leverage_cap": 1.0, "tier_scale": 1.0,
                     "stop_mult": 1.0})
        sized = self.long_sizer.size(
            asset, "long", plan.price, 1.0, equity, self.state,
            neutral_macro, vol_state, liq_state, 1.0, self.inventory,
            None, self.marks, now, risk_scale=manip_scale, symbol=symbol)
        if not sized.approved:
            detail = tag(Code.LB_ADD_DENIED,
                        f"{asset}: sizer vetoed - "
                        f"{'; '.join(str(r) for r in sized.reasons) or 'no reason recorded'}")
            self._long_last_deny = detail
            log.info(detail)
            get_audit().log("long_book", Code.LB_ADD_DENIED, detail,
                            {"asset": asset, "kind": "sizer"})
            self._long_book_note_failure(asset, now,
                                         ecfg.retry_backoff_minutes)
            return

        usd = min(sized.usd, plan.usd)
        if usd <= EPS:
            self._long_book_note_failure(asset, now,
                                         ecfg.retry_backoff_minutes)
            return
        units = usd / plan.price
        position_id = position.position_id if position is not None \
            else str(uuid.uuid4())
        if "magnet" in plan.reason_detail:
            get_audit().log(
                "long_book", Code.LB_ZONE_SHIFT,
                tag(Code.LB_ZONE_SHIFT, f"{asset}: {plan.reason_detail}"),
                {"asset": asset})

        # Important #2 (C4 review): a MEASURED maker-entry/taker-exit
        # round-trip cost estimate, reusing the SAME components execution.
        # pretrade.PreTradeGate's own cost stack uses for its 5m maker
        # path (fee + ... + exit_leg, where exit_leg = taker_fee_bps +
        # 0.5*spread_bps - "every entry must be unwound, the escalation
        # ladder's common terminal case is a taker exit through the
        # current spread") - not a new cost model, the SAME shared
        # pretrade/order config the 5m path reads plus this asset's OWN
        # currently-measured spread. Replaces the prior hardcoded 0.0,
        # which made profit_tiers.tier1_cost_floor_pct's min_trigger_
        # cost_mult floor provably inert for every long-book position
        # (min_trigger_cost_mult * 0.0 == 0.0, never binds).
        est_cost_bps = (self.pretrade.maker_fee_bps
                       + self.pretrade.taker_fee_bps
                       + 0.5 * liq_state.spread_bps)

        # C5-discovered spec gap fix: stamp the REAL feature vector at add
        # time, mirroring the 5m entry loop's own call site (main.py's 5m
        # loop ~2814-2823: smc.compute then build_features) - spec §5 /
        # acceptance §8.4 require long-horizon labels to flow into the
        # corpus under the book tag (the paper positions ARE the
        # learning). `gate_conf`=1.0 is a NEUTRAL literal, not fitted: no
        # gate stack runs on this path (this book has no gate-pass
        # fraction of its own - the SAME "not applicable" reasoning
        # _long_book_conviction_gate already documents for agreement/EV);
        # the features exist to record CONTEXT for the corpus, and ml/
        # history.py's load_training_data already excludes every
        # book=="long" row from the 5m model's X/y (task C5), so a
        # neutral gate_conf here cannot leak into the 5m model. Assembly
        # is best-effort ONLY: a missing input this cycle (no candles in
        # self.view) or any exception mid-assembly skips the stamp
        # entirely (features stays None, logged once at DEBUG) - the add
        # itself must NEVER be blocked by feature assembly. Mirrors how
        # _handle_fill already tolerates an absent "features" key by
        # skipping log_entry for whatever fill this order produces.
        feats = None
        try:
            view_snap = getattr(self, "view", {}).get(asset)
            if view_snap and view_snap.get("candles"):
                others = [a for a in self.symbol_map if a != asset]
                other_asset = others[0] if others else None
                fv_state = self.fv.state(asset)
                macro_state = self.macro.state(asset)
                smc_feats = self.smc.compute(
                    asset, view_snap.get("candles") or [], "long", now,
                    daily_candles=self.daily_candles.get(asset))
                gate_conf = 1.0   # neutral: no gate stack on this path
                feats = build_features(
                    asset, "long", gate_conf, view_snap, fv_state,
                    vol_state, liq_state, macro_state, self.corr.state,
                    sentiment, smc_feats, other_asset=other_asset,
                    extras=self._feature_extras(
                        asset, view_snap, web, risk, other_asset, now))
            else:
                log.debug("long-book feature assembly skipped for %s - "
                         "no candles this cycle", asset)
        except Exception:
            feats = None
            log.debug("long-book feature assembly failed for %s - add "
                     "proceeds without a corpus row", asset, exc_info=True)

        meta = {"book": "long", "p_win": 0.0, "edge_bps": 0.0,
               "est_cost_bps": est_cost_bps, "probe": False}
        if feats is not None:
            meta["features"] = feats

        order = self.orders.submit(
            asset=asset, symbol=symbol,
            pair=self.kraken.kraken_pair(symbol), side="buy",
            price=plan.price, size=units, purpose="entry",
            position_id=position_id, post_only=True, leverage=1.0,
            book=self.kraken_books.get(asset) or {},
            sigma_bar_pct=vol_state.sigma_bar_pct,
            ref_price=self.marks.get(symbol) or plan.price,
            equity=equity,
            meta=meta,
            # Critical #1a: patient maker bids live HOURS, not the 5m
            # book's shared ~25s order_timeout_sec.
            ttl_sec=ecfg.order_ttl_hours * 3600.0,
            now=now,
        )
        if order:
            # Critical #1(c): the submit-time _long_last_add_ts stamp is
            # REMOVED - the spacing clock now keys on FILL
            # (main._handle_fill), so a zero-fill expiry/cancel can never
            # burn the ~24h-scale spacing window.
            self._long_adds_placed += 1
            self._long_last_deny = ""
            detail = tag(Code.LB_ADD_PLACED,
                        f"{asset}: {plan.reason_detail} - ${usd:,.2f} @ "
                        f"{plan.price:,.6f}")
            get_audit().log(
                "long_book", Code.LB_ADD_PLACED, detail,
                {"asset": asset, "usd": round(usd, 2), "price": plan.price,
                 "rung": self.long_ladder.rung(), "position_id": position_id})
            log.info(detail)
        else:
            detail = tag(Code.LB_ADD_DENIED,
                        f"{asset}: order manager refused submission "
                        f"(firewall/venue-min/zero-format)")
            self._long_last_deny = detail
            log.info(detail)
            get_audit().log("long_book", Code.LB_ADD_DENIED, detail,
                            {"asset": asset, "kind": "submit"})
            self._long_book_note_failure(asset, now,
                                         ecfg.retry_backoff_minutes)

    def _ladder_entry(self, *, position_id, asset, symbol, side, signal,
                      entry_price, decision, sized, lev, equity, vol_state,
                      fv_state, macro_state, liq_state, verdict, feats,
                      explored, p_win, model_p, shadow_p, ev_pct,
                      stop_pct_eff, target_pct, now, reserved_entries,
                      can_enter, cand_id=None, bracket_pt_frac=0.0,
                      bracket_sl_frac=0.0, bracket_deadline_ts=0.0,
                      feat_avail=None):
        """v10 ladder pathway for one approved entry. Returns the updated
        (reserved_entries, can_enter, handled): handled=True means the ladder
        placed (or consciously consumed) this entry and the caller skips the
        single-entry path; False means fall through unchanged."""
        # the ladder is a MAKER strategy (every rung rests post_only=True);
        # a taker-urgent entry (ExecutionPlanner decided urgency cleared
        # taker_at, so pretrade evaluated it with taker=True — echoed onto
        # the approved decision) must never be forced to rest — fall
        # through to the legacy path, which honors plan.post_only.
        if decision.taker:
            return reserved_entries, can_enter, False
        lplan = self.ladder.plan(
            asset, signal.direction, entry_price, vol_state.sigma_bar_pct,
            decision.size_units, p_win, liq_label=liq_state.label,
            max_rungs=self._ladder_rung_budget(asset, signal.direction,
                                               reserved_entries))
        if not lplan.armed or len(lplan.rungs) < 2:
            return reserved_entries, can_enter, False
        # SPB-R §1.4 (H16): this path deducts a probe token below
        # (_record_probe_admission) exactly like the direct path, but
        # stamped `probe_cost` on nothing - so the SZ-052 unfilled-entry
        # refund was unreachable for every ladder-routed probe (~half of
        # all placed probes, measured), burning tokens the spec guarantees
        # back. Every rung is post_only with a ~25s timeout, i.e. exactly
        # the attrition population the refund exists for. READ (not pop),
        # mirroring the direct path's idiom above: the single deduction
        # still happens once, in _record_probe_admission, and a ladder that
        # places nothing falls through with the stash intact.
        _spbr_cost = (getattr(self, "_pending_probe_cost", None)
                      or {}).get(asset) if explored else None
        placed = self._place_ladder(
            lplan, position_id=position_id, asset=asset, symbol=symbol,
            side=side, signal=signal, decision=decision, lev=lev,
            equity=equity, vol_state=vol_state, fv_state=fv_state,
            macro_state=macro_state, liq_state=liq_state, verdict=verdict,
            feats=feats, feat_avail=feat_avail, explored=explored,
            p_win=p_win, model_p=model_p,
            shadow_p=shadow_p, ev_pct=ev_pct, stop_pct_eff=stop_pct_eff,
            target_pct=target_pct, now=now, cand_id=cand_id,
            bracket_pt_frac=bracket_pt_frac,
            bracket_sl_frac=bracket_sl_frac,
            bracket_deadline_ts=bracket_deadline_ts,
            probe_cost=_spbr_cost)
        if not placed:
            # every rung rejected (firewall/collar/venue-min) — the
            # approved entry must fall back to the legacy single-entry
            # path, not vanish silently.
            return reserved_entries, can_enter, False
        reserved_entries += placed             # each rung holds a slot
        self.sizer.note_entry(asset, now)
        self._mark_cand(asset, signal.direction, "entered")
        # one call regardless of `placed` rung count: one DECISION (this
        # signal, admitted as probe or conviction) = one admission for the
        # P3 share cap - counting per-rung would dilute the probe share
        # denominator against multi-rung ladders for no throttle-relevant
        # reason (the admission decision was made once, upstream).
        self._record_probe_admission(explored)
        self._last_entry_admit_ts = now
        step_bps = lplan.rungs[-1].offset_bps / \
            max(len(lplan.rungs) - 1, 1)
        log.info(
            f"ENTRY-LADDER {signal.direction} {symbol}: "
            f"{placed}/{len(lplan.rungs)} rungs, "
            f"${decision.size_units * entry_price:,.0f} "
            f"total | p={p_win:.2f} spacing={step_bps:.1f}bps | "
            f"{lplan.reason}")
        if not self.capital.can_open_new_position(self.state,
                                                  reserved_entries):
            can_enter = False
        return reserved_entries, can_enter, True

    def _place_ladder(self, lplan, *, position_id, asset, symbol, side,
                      signal, decision, lev, equity, vol_state, fv_state,
                      macro_state, liq_state, verdict, feats, explored,
                      p_win, model_p, shadow_p, ev_pct, stop_pct_eff,
                      target_pct, now, cand_id=None, bracket_pt_frac=0.0,
                      bracket_sl_frac=0.0, bracket_deadline_ts=0.0,
                      probe_cost=None, feat_avail=None) -> int:
        """Submit an armed ladder's rungs as maker-only limit entries through
        the FULL existing rail (firewall, collar, venue minimums). Every rung
        is its own position with its own postmortem thesis, so labels stay
        honest per fill. Returns rungs actually placed (each holds a slot).

        `probe_cost` (H16, default None = every pre-existing caller and the
        stub-bot harnesses unchanged, invariant #7): the SPB-R scarcity
        price this ONE decision will be charged. Stamped on the FIRST rung
        that actually rests, so one decision = one deduction = one
        refundable tag. Never on every rung - that would refund N times a
        single deduction; and `_drop_ladder_probe_tag` retires the tag the
        moment any sibling rung fills, because a decision that bought a
        label is not refundable."""
        book = self.kraken_books.get(asset) or {}
        # W2-10: rung 0 already cleared PreTradeGate.evaluate() (this whole
        # pathway only runs off an APPROVED decision) -- no double-charge,
        # it is never re-checked. But rungs 1..n rest strictly further from
        # the mid than rung 0's own price, and the gate's maker EV term is
        # p_fill-weighted with p_fill DECAYING in that distance
        # (grid_ladder's "monotone by construction" docstring covers only
        # the edge-ratio, never this). Re-run the gate's own arithmetic at
        # each deeper rung's actual offset before submitting it.
        sigma_bar_bps = self.pretrade.sigma_bar_bps(vol_state.sigma_daily_pct)
        placed = 0
        for rung in lplan.rungs:
            if rung.idx > 0:
                dist_bps = self.pretrade.maker_dist_bps(book, rung.price)
                rung_edge_bps = decision.est_edge_bps + rung.offset_bps
                p_fill, ev = self.pretrade.maker_p_fill_ev(
                    rung_edge_bps, decision.est_cost_bps, dist_bps,
                    sigma_bar_bps)
                if ev < self.pretrade.ev_min_bps:
                    log.info("%s", tag(
                        Code.GL_RUNG_EV_VETO,
                        f"{asset} rung {rung.idx}: EV {ev:+.2f}bps @ "
                        f"p_fill {p_fill:.2f} dist {dist_bps:.1f}bps < "
                        f"{self.pretrade.ev_min_bps:.2f} floor"))
                    continue
            rid = position_id if rung.idx == 0 else \
                f"{position_id}-r{rung.idx}"
            rung_order = self.orders.submit(
                asset=asset, symbol=symbol,
                pair=self.kraken.kraken_pair(symbol), side=side,
                price=rung.price, size=rung.size_units, purpose="entry",
                position_id=rid,
                post_only=True,              # grid rungs are maker-only
                leverage=lev.allowed_leverage,
                ref_price=self.marks.get(symbol) or fv_state.fair_value,
                equity=equity,
                book=book,
                sigma_bar_pct=vol_state.sigma_bar_pct,
                meta={"p_win": p_win,
                      # deeper rungs rest strictly further from fair value:
                      # their edge grows by the offset
                      "edge_bps": decision.est_edge_bps + rung.offset_bps,
                      # est_cost_bps is rung 0's gate-approved cost stack,
                      # unchanged across rungs (only edge grows with offset,
                      # W2-10) - threaded onto every rung's Position so the
                      # tier-1 cost floor (P1) sees the same cost every rung
                      # of this entry was actually approved against.
                      "est_cost_bps": decision.est_cost_bps,
                      "features": feats, "avail": feat_avail or {},
                      "probe": explored,
                      "ladder_rung": rung.idx,
                      # H16 group key: every rung of ONE decision shares it,
                      # so a fill on any rung can retire the single
                      # refundable probe tag (_drop_ladder_probe_tag).
                      "ladder_group": position_id,
                      "candidate_id": cand_id or "",
                      "thales_fired": self._thales_fired.get(asset) or [],
                      "gates_passed": getattr(self, "_sig_gates", {}).get(asset) or {},
                      "gate_components": dict(getattr(signal, "components", None) or {}),
                      "bracket_pt_frac": bracket_pt_frac,
                      "bracket_sl_frac": bracket_sl_frac,
                      "bracket_deadline_ts": bracket_deadline_ts},
                now=now)
            if not rung_order:
                continue
            placed += 1
            if probe_cost is not None and placed == 1:
                # SPB-R §1.4: the ONE refundable tag for this decision,
                # on the first rung that actually rested (a rejected rung
                # never carries it, so an all-rejected ladder - which
                # falls back to the direct path - leaves nothing tagged).
                rung_order.meta["probe_cost"] = probe_cost
            # honest-labels doctrine: a thesis is registered only for a
            # rung that actually rested — a rejected rung (firewall/
            # collar/venue-min) must never leave an orphan postmortem
            # thesis. Rung 0's thesis is registered by the caller before
            # the ladder pathway even runs (it IS the approved entry).
            if rung.idx > 0:
                self.postmortem.register_entry(TradeThesis(
                    position_id=rid, asset=asset, symbol=symbol,
                    direction=signal.direction, entry_ts=now, p_win=p_win,
                    expected_ret_pct=ev_pct,
                    expected_cost_bps=decision.est_cost_bps,
                    stop_pct=stop_pct_eff, target_pct=target_pct,
                    entry_regime=macro_state.label,
                    entry_liq=liq_state.label,
                    narrative_label=verdict.label,
                    fair_value=fv_state.fair_value,
                    quote_price=rung.price,
                    price_decimals=_price_decimals(
                        getattr(self.orders, "pair_meta", {}),
                        self.kraken.kraken_pair(symbol), rung.price),
                    model_p=model_p, shadow_p=shadow_p,
                    model_scored=(self.monitor.use_model
                                  and self.meta.trained)))
        return placed

    def _ladder_rung_budget(self, asset: str, direction: str,
                            reserved_entries: int) -> int:
        """How many grid rungs may rest for this asset+side RIGHT NOW without
        the fills being able to breach either the global concurrency cap or
        the per-asset same-side inventory cap. Both caps are normally checked
        per ENTRY DECISION; a ladder turns one decision into several
        potential positions, so the same books must be balanced here."""
        slots = self.capital.max_concurrent_positions - \
            self.state.open_position_count() - reserved_entries
        same = sum(1 for pos in self.state.open_positions()
                   if (pos.symbol.split("/")[0] if "/" in pos.symbol
                       else pos.symbol) == asset
                   and pos.direction == direction
                   and not getattr(pos, "is_hedge", False))
        side_left = self.inventory.max_same_side - same
        budget = max(1, min(slots, side_left))
        if self.ladder.enabled and budget < self.ladder.max_rungs:
            log.info("%s", tag(Code.GL_RUNG_CAPPED,
                               f"{asset} {direction}: {budget} rung(s) "
                               f"(slots={slots}, same_side_left={side_left})"))
        return budget

    def _grade_period_goal(self, period: str, actual: float, goal_key: str,
                           reserve_refill: float = 0.0) -> dict:
        """Grade a just-closed period's realized PnL against its config
        goal and return the goal fields to merge into the close summary.
        Measurement only: reads config + close-time context flags, changes
        no trading state. Context is best-effort (unknown -> not a factor),
        so a stub bot without a monitor still grades cleanly."""
        goal = float(self.config.get("capital_management", {})
                     .get(goal_key, 0.0) or 0.0)
        # RP-072 goal ladder (stressor regime, operator-adjudicated
        # 2026-08-11): the MONTH is graded against base x ladder. The week
        # stays at base - escalation is monthly by directive. Grading uses
        # the mult the month was RUN under; the ratchet (in _close_periods)
        # fires AFTER grading, for the next month.
        if period == "month":
            goal *= float(getattr(self.state, "goal_ladder_mult", 1.0))
        ctx = {"reserve_refill": reserve_refill,
               "model_active": getattr(self.monitor, "use_model", None),
               "entries_enabled": getattr(self, "entries_enabled", None)}
        verdict = evaluate_goal(period, actual, goal, ctx)
        # drop period/actual: the close summary already owns those keys
        return {k: verdict[k] for k in _GOAL_COLS}

    def _feature_extras(self, asset: str, v: dict, web, risk,
                        other_asset, now: float) -> dict:
        imb = float(np.clip(np.log(max(v.get("imbalance_ratio", 1.0),
                                       1e-3)), -2, 2))
        delta = imb - self._last_imb.get(asset, imb)
        self._last_imb[asset] = imb
        other_ret6 = 0.0
        ov = self.view.get(other_asset) if other_asset else None
        if ov and ov.get("candles") and len(ov["candles"]) > 6:
            c = ov["candles"]
            if c[-7]["close"] > 0:
                other_ret6 = float(np.log(c[-1]["close"] / c[-7]["close"])
                                   * 100.0)
        # kraken (execution venue) vs the composite view book, in bps:
        # positive = kraken rich vs the street. Both books already sit in
        # memory - no extra I/O.
        disloc_bps = 0.0
        km = _book_mid(self.kraken_books.get(asset) or {})
        vm = _book_mid(v.get("order_book") or {})
        if km > 0 and vm > 0:
            disloc_bps = (km - vm) / vm * 1e4
        since = self._regime_since.get(asset)
        liq_state = self.liq.state(asset)
        # manip_suspect FEATURE (trains the model): the divergence term
        # compares Kraken to the COHERENT per-venue composite, never the
        # mixed-unit merged book (SD-003 - the incoherent path poisoned this
        # feature with false 'divergence' on the majors). No external book ->
        # mirror kraken_imb so divergence is 0, not a phantom manip flag.
        # equal-weight market factor: RAW mean 6-bar log-return across
        # every viewed asset with enough committed history. Un-normalized
        # here - build_features divides by THIS asset's sigma_bar*sqrt(6)
        # (the exact ret_6_dir denominator) so the units match. Missing
        # candles simply drop out; no assets qualifying -> 0.0 (no drift
        # observed), never a raise.
        mkt_rets = []
        for av in self.view.values():
            c = (av or {}).get("candles") or []
            if len(c) >= 7:
                try:
                    c0, c1 = float(c[-7]["close"]), float(c[-1]["close"])
                    if c0 > 0 and c1 > 0:
                        mkt_rets.append(math.log(c1 / c0))
                except (KeyError, TypeError, ValueError):
                    continue
        mkt_ret_6 = float(np.mean(mkt_rets)) if mkt_rets else 0.0
        # depth CONCENTRATION at the touch (book shape) from the Kraken
        # book already in memory: (bid1 + ask1 notional) / sum of the top
        # 10 notionals BOTH SIDES (5 levels per side, 10 numbers total -
        # this denominator is what makes the flat-book neutral 0.2: each
        # of the 10 levels carries 1/10, the touch is one level per side
        # = 2/10). Missing/one-sided book -> 0.2; 0.0 would falsely
        # claim a hollow touch.
        touch_share = 0.2
        kb = self.kraken_books.get(asset) or {}
        try:
            bid_n = [float(p) * float(s)
                     for p, s in (kb.get("bids") or [])[:5]]
            ask_n = [float(p) * float(s)
                     for p, s in (kb.get("asks") or [])[:5]]
            total = sum(bid_n) + sum(ask_n)
            if bid_n and ask_n and total > 0:
                touch_share = (bid_n[0] + ask_n[0]) / total
        except (TypeError, ValueError):
            pass
        kb_imb = _book_imbalance(self.kraken_books.get(asset) or {})
        comp_imb = _composite_imbalance(v.get("venue_books") or [])
        suspect = manip_suspect_score(
            liq_state.spoof_score,
            whiplash_suspicion(liq_state.imbalance_whiplash,
                               self._wl_p95, self._wl_thr),
            kb_imb, comp_imb if comp_imb is not None else kb_imb)
        self._manip_scores[asset] = round(suspect, 3)
        # 41b availability truth: which context feeds were LIVE when these
        # features were built. A dark feed's neutrals are byte-identical to
        # genuine neutral on the ML path (input-feed audit 2026-08-07), so
        # the flags ride every corpus row as bookkeeping columns - never as
        # features (the DoF ledger is closed). "frozen" is 41a's closed-
        # market signature: the equity quote is real but static.
        avail = {"web": bool(getattr(web, "available", False)),
                 "equity": bool(getattr(risk, "available", False)),
                 "options": bool(getattr(risk, "options_available", False)),
                 "frozen": bool(getattr(risk, "quotes_frozen", False))}
        _context_avail_check(self, avail)
        return {"avail": avail,
                "fear_greed": web.fear_greed,
                "dominance_delta": web.dominance_delta,
                "equity_risk_z": risk.risk_z,
                "ts": now,
                "imbalance_delta": delta,
                "other_ret_6": other_ret6,
                "depth_ratio": self.liq.state(asset).depth_ratio,
                "regime_age_sec": max(now - since[1], 0.0) if since else 0.0,
                "venue_disloc_bps": disloc_bps,
                "thales": self.thales.feature_scores(asset, now),
                "opt_pcr_z": risk.opt_pcr_z,
                "opt_oi_pcr_z": risk.opt_oi_pcr_z,
                "opt_iv_skew": risk.opt_iv_skew,
                "manip_suspect": suspect,
                "mkt_ret_6": mkt_ret_6,
                "book_touch_share": touch_share}

    def _maybe_unwind_unteachable(self, now: float) -> None:
        """ML-071 anti-wedge (see pick_unteachable_unwind). Dry-run only:
        live exits stay entirely with the tier engine and operator."""
        cfg = self.config.get("ml", {}).get("exploration", {})
        if not self.dry_run or not cfg.get("unteachable_unwind", True):
            return
        positions = self.state.open_positions()
        cap = self.capital.max_concurrent_positions
        # graduate on LIVE (real closed-trade) rows, not total — same reason
        # as _exploration_active: a proxy-inflated total count would retire
        # the teaching-slot unwind while real fill outcomes are still scarce,
        # letting non-teaching positions squat every slot and starving the
        # learning loop of meaningful data.
        _sc_fn: Optional[Callable[[], dict]] = getattr(
            self.history, "source_counts", None)
        _sc = _sc_fn() if callable(_sc_fn) else {}
        _grad_rows = _sc.get("live", 0) if _sc else self.history.row_count()
        pos = pick_unteachable_unwind(
            positions, set(self.history._pending), len(positions) >= cap,
            _grad_rows,
            int(cfg.get("until_live_rows", 240)), now,
            float(cfg.get("unteachable_min_age_h", 1.0)))
        if pos is None or exit_in_flight(self.orders.open_orders(),
                                         pos.position_id):
            return
        # trusted-mark gate (same as derisk/tiers): a learning unwind is NOT
        # an escape — closing against a stale cached book banks a phantom-
        # price PnL as a live training label, and buys nothing (the watchdog
        # blocks entries on the same staleness, so the freed slot is unusable)
        if not (self._stop_ok.get(self._asset_of(pos.symbol), True)
                and self._mark_fresh(pos.symbol, now)):
            return
        get_audit().log("engine", Code.ML_UNTEACHABLE_UNWIND,
                        f"learning-phase unwind {pos.symbol} "
                        f"{pos.position_id[:8]}: book full, zero pending "
                        f"label vectors - freeing a slot for trades that "
                        f"teach", {"position_id": pos.position_id})
        log.warning(f"{Code.ML_UNTEACHABLE_UNWIND.value}: unwinding "
                    f"{pos.symbol} {pos.position_id[:8]} - full book, no "
                    f"open position can produce a training row")
        self._submit_exit(pos, 100.0, "unteachable unwind (ML-071)",
                          now=now)

    def _maybe_realize_mature_label(self, now: float) -> None:
        """ML-073 learning-phase label realization (see pick_label_mature_unwind).
        Dry-run only: live exits stay entirely with the tier engine/operator.
        A dry-run position held past the model's label horizon has resolved its
        triple-barrier outcome — close it to bank the live label and keep the
        learning loop fed with fresh ground truth."""
        cfg = self.config.get("ml", {}).get("exploration", {})
        if not self.dry_run or not cfg.get("realize_mature_labels", True):
            return
        # horizon = the labeler's own window (label_max_bars * bar seconds),
        # scaled by realize_after_label_spans — NOT a free literal: once a
        # position outlives the label window the barrier has already fired, so
        # its realized outcome is exactly the label the model expects.
        from ml.walkforward import BAR_SECONDS
        _ml = self.config.get("ml", {})
        _bars = int(_ml.get("label_max_bars", 96))
        _spans = float(cfg.get("realize_after_label_spans", 1.0))
        # value-of-information fast-forward: when the book is FULL the
        # horizon is the learning bottleneck — use the fastpath spans to
        # buy a teach slot; with free slots keep the full window (holding
        # is free and the outcome richer). Fullness mirrors the ENTRY
        # GATE (all filled positions incl. hedges + resting entry
        # orders): a hedge or resting entry occupies a slot no teach
        # trade can use. See effective_realize_spans.
        _open = self.state.open_positions()
        _reserved = sum(1 for o in self.orders.open_orders()
                        if o.purpose == "entry")
        # defensive: fast_cycle always seeds _last_entry_admit_ts before
        # slow_cycle (this method's caller) runs in the same cycle_once, so
        # this is never unset in normal operation; a zero-elapsed fallback
        # (not a crash) if this is ever called in isolation.
        _admit_ts = getattr(self, "_last_entry_admit_ts", None)
        if _admit_ts is None:
            _admit_ts = now
        _spans = effective_realize_spans(
            _spans, float(cfg.get("realize_fastpath_spans", 0.0)),
            len(_open) + _reserved, self.capital.max_concurrent_positions,
            drought_h=(now - _admit_ts) / 3600.0,
            drought_after_h=float(cfg.get("realize_drought_h", 0.0)))
        mature_h = _spans * _bars * BAR_SECONDS / 3600.0
        # graduate on LIVE rows (real closed trades), same basis as exploration
        _sc_fn: Optional[Callable[[], dict]] = getattr(
            self.history, "source_counts", None)
        _sc = _sc_fn() if callable(_sc_fn) else {}
        _grad_rows = _sc.get("live", 0) if _sc else self.history.row_count()
        pos = pick_label_mature_unwind(
            _open, _grad_rows,
            int(cfg.get("until_live_rows", 500)), now, mature_h)
        if pos is None or exit_in_flight(self.orders.open_orders(),
                                         pos.position_id):
            return
        # trusted-mark gate (same as derisk/tiers): realizing against a stale
        # cached book would bank a phantom-price PnL as GROUND TRUTH
        if not (self._stop_ok.get(self._asset_of(pos.symbol), True)
                and self._mark_fresh(pos.symbol, now)):
            return
        age_h = (now - pos.opened_at.timestamp()) / 3600.0
        # bracket positions are only ever picked PAST their own deadline
        # (pick_label_mature_unwind) - this close IS the vertical barrier,
        # so the reason threads "tb_time" verbatim and log_close files the
        # row under LABEL_ERA_TRIPLE_BARRIER (it trains). The legacy
        # "realized" string joins the exit_sim era the era-exclusion
        # filter drops - correct for a non-bracket position, label-
        # destroying for a bracket one.
        bracket_backstop = getattr(pos, "bracket_pt_frac", 0.0) > EPS and \
            getattr(pos, "bracket_deadline_ts", 0.0) > EPS
        reason = "tb_time" if bracket_backstop else \
            "label-mature realization (ML-073)"
        get_audit().log("engine", Code.ML_LABEL_REALIZE,
                        f"label-mature realize {pos.symbol} "
                        f"{pos.position_id[:8]}: held {age_h:.1f}h past the "
                        + ("bracket deadline - banking the tb_time label, "
                           "freeing a teach slot" if bracket_backstop else
                           f"{mature_h:.1f}h label horizon - banking the "
                           f"live label, freeing a teach slot"),
                        {"position_id": pos.position_id,
                         "age_h": round(age_h, 2),
                         "barrier": "tb_time" if bracket_backstop
                         else "realized"})
        log.warning(f"{Code.ML_LABEL_REALIZE.value}: realizing {pos.symbol} "
                    f"{pos.position_id[:8]} - {age_h:.1f}h > {mature_h:.1f}h "
                    f"label horizon; banking live label")
        self._submit_exit(pos, 100.0, reason, now=now)

    # ------------------------------------------------------------------
    # HOURLY cycle - macro regime + turbulence
    # ------------------------------------------------------------------
    @staticmethod
    def _symbol_base(sym: str) -> str:
        """Base asset of an exchange symbol: 'ETH-USDT'/'ETH/USDT' -> 'ETH',
        'ETHUSDT' -> 'ETH'. Used so a prefix match for 'ETH' can't grab
        'ETHFI-*'/'ETHW-*' (startswith bug) and feed the wrong asset's candles."""
        for sep in ("-", "/"):
            if sep in sym:
                return sym.split(sep, 1)[0]
        for q in ("USDT", "USDC", "USD"):
            if sym.endswith(q):
                return sym[:-len(q)]
        return sym

    def hourly_cycle(self, now: float) -> None:
        # adaptive-penalty staleness decay: without this a raised entry
        # bar can deadlock (bar blocks trades -> no closes -> the causes
        # window that justifies the bar never refreshes)
        self.monitor.decay_stale_causes(now)
        okx_syms = self.config["exchanges"]["okx"].get("symbols", [])
        binanceus_syms = self.config["exchanges"]["binanceus"].get("symbols", [])
        for asset in self.symbol_map:
            candles = []
            for s in okx_syms:
                if self._symbol_base(s) == asset:
                    candles = self.okx.get_daily_candles(s)
                    break
            if not candles:
                for s in binanceus_syms:
                    if self._symbol_base(s) == asset:
                        candles = self.binanceus.get_daily_candles(s)
                        break
            if not candles:
                candles = self.kraken.get_daily_candles(
                    self.kraken.kraken_pair(self.symbol_map[asset]))
            if candles:
                self.daily_candles[asset] = candles

        self.corr.update_turbulence(self.daily_candles)
        for asset in self.symbol_map:
            self.macro.update(asset, self.daily_candles.get(asset) or [],
                            self.corr.state.turbulence_pct)

        if not self.dry_run and self.lev_gov.use_margin:
            self.margin_level_pct = self.kraken.get_margin_level_pct()
        if not self.dry_run:
            self._check_equity_truth()
        # W2-9 remainder: periodic fee-tier reconciliation (report-only).
        # Read-only regardless of dry_run (a credential check, not a live-
        # trading gate, decides whether it can run at all). Isolated at
        # THIS call site too, like every other hourly peer above/below -
        # check_fee_reconciliation is internally fail-safe already, but a
        # raise from an incompletely-stubbed self.orders (tests) or any
        # other surprise here must never starve the retrain/drift work
        # that follows.
        try:
            self.orders.check_fee_reconciliation(now)
        except Exception:
            log.debug("fee reconciliation call skipped: unexpected error",
                     exc_info=True)

        # adopt an EXTERNALLY-retrained model (scripts/train_meta.py run
        # against a LIVE bot writes outputs/meta_model.json + a champion_brier
        # into state.json that the bot's next snapshot then clobbers). Detect
        # the changed artifact, reload it, and realign the champion baseline to
        # ITS OWN OOF brier — so an offline retrain actually reaches the running
        # engine and the baseline can't be clobbered back to a stale value.
        if self.meta.reload_if_changed():
            if self.meta.trained and self.meta.oof_brier is not None:
                self.monitor.note_deployed(float(self.meta.oof_brier))
                log.warning("adopted externally-retrained meta-model %s "
                            "(oof brier %.4f) - champion baseline realigned",
                            self.meta.model_id or "?", self.meta.oof_brier)
            else:
                log.warning("external meta-model change detected but the "
                            "artifact was rejected (schema/integrity) - staying "
                            "on the cold-start prior")
            # W2-3: reconcile_champion_badge was only ever called at
            # __init__/resume (see the ML-076 comment above), never here - a
            # REJECTED reload flips meta.trained False but left the badge
            # untouched, so a ghost champion_brier could squat and reject
            # every honest challenger forever (the exact ML-076 deadlock,
            # just reachable through this call site instead). Mirror the
            # __init__ call's arguments in BOTH branches: accepted syncs to
            # the new artifact's own oof (a no-op after note_deployed already
            # set it exactly); rejected discards a ghost badge that no longer
            # has a backing model.
            self.monitor.reconcile_champion_badge(
                self.meta.oof_brier, model_loaded=self.meta.trained)
        self._maybe_auto_retrain()
        self.monitor.check_drift(self.meta.feature_deciles, FEATURE_NAMES)

        st = self.monitor.status()
        log.info(f"health: equity=${self._equity():,.2f} "
                f"positions={self.state.open_position_count()} "
                f"orders={len(self.orders.open_orders())} "
                f"monitor_level={st['level']} "
                f"brier={st.get('brier', 'n/a')} "
                f"kelly_mult={st['kelly_mult']:.2f} "
                f"history_rows={self.history.row_count()}")

    def _check_equity_truth(self) -> None:
        """Live only: compare the bot's internal equity ledger against the
        venue's TradeBalance. Config can lie, fills can be missed, someone
        can trade the account manually - the exchange's number is the
        ground truth. Material drift alerts the operator and blocks new
        entries until the books agree again. The ledger is never silently
        'corrected': hidden adjustments are how small errors become
        unexplainable ones."""
        try:
            tb = self.kraken.get_trade_balance() or {}
        except Exception:
            log.warning("equity truth check skipped: TradeBalance failed")
            return
        venue_eq = safe_float(tb.get("eb") or tb.get("e"), default=0.0)
        if venue_eq <= 0:
            return
        local_eq = self._equity()
        if local_eq <= 0:
            return
        self._equity_drift_pct = (local_eq - venue_eq) / venue_eq * 100.0
        if abs(self._equity_drift_pct) > self.max_equity_drift_pct:
            self.alerts.fire(
                "equity_drift",
                f"internal equity ${local_eq:,.2f} vs venue "
                f"${venue_eq:,.2f} ({self._equity_drift_pct:+.2f}%). "
                f"Manual trades, missed fills, or a config error. New "
                f"entries blocked; reconcile before re-arming.")

    def _retrain_gate(self, rows: int) -> bool:
        """Decide whether to ATTEMPT an auto-retrain this cycle (side effect:
        logs a cold-start request, marks the first cold attempt).

        COLD START (no champion + enough rows) drives the attempt DIRECTLY,
        never via the flag file: that flag lives in gitignored outputs/ and is
        wiped by a container rollback, while the durable retrain cooldown then
        refuses to rewrite it - so a flag-gated cold start stalls for a full
        cooldown after every restart and the first champion never trains
        (observed: trained=false at 240+ rows). Degradation/drift retrains
        still route through the monitor level / flag.

        The min-NEW-rows throttle governs RE-trains of a live champion; the
        first cold-start attempt bypasses it once (a cold container's
        _rows_at_last_train == full restored count would otherwise zero the
        delta and block the first train outright), then normal throttling
        resumes so a non-deploying challenger can't retrain every cycle."""
        cold_start = (not self.meta.trained
                      and rows >= self.monitor.retrain_min_rows)
        if cold_start:
            self.monitor.request_retrain(
                f"cold start: {rows} labeled rows and no champion")
        want = (cold_start or self.monitor.level >= 2
                or self.monitor.flag_path.exists())
        if not want:
            return False
        first_cold_attempt = cold_start and not self._retrain_attempted
        if (not first_cold_attempt
                and rows - self._rows_at_last_train
                < self.monitor.retrain_min_new_rows):
            return False
        if rows < self.monitor.retrain_min_rows:
            return False
        self._retrain_attempted = True
        return True

    def _maybe_auto_retrain(self) -> None:
        """Self-improvement loop: when the monitor requests a retrain (level
        2, or the flag file exists) and enough NEW labeled rows have accrued,
        retrain in-process on live+candidate history. The challenger only
        deploys if its out-of-fold Brier beats the champion's - the bot
        never swaps in a worse model just to feel busy."""
        rows = self.history.row_count()
        if not self._retrain_gate(rows):
            return
        try:
            from ml.walkforward import evaluate_and_select
            from ml.retrain_log import family_metric
            from ml.models import save_model
            from ml.calibration import (IsotonicCalibrator, brier_score,
                                        feature_deciles)
            sw_cfg = self.config.get("ml", {}).get("sample_weights", {})
            tele_cfg = self.config.get("ml", {}).get("telemetry", {})
            epoch_cfg = self.config.get("ml", {}).get("epoch", {})
            # era-gated training exclusion (docs/quant/2026-07-26_era_exclusion.md):
            # this is the production retrain path - the ONE consumer that must
            # never drift from what OF-3's PBO measures (docs/quant/
            # pbo_admission_policy.md's cross-consumer prerequisite).
            era_cfg = self.config.get("ml", {}).get("era_exclusion", {})
            X, y, w, sig, res = self.history.load_training_data(
                half_life_days=float(sw_cfg.get("half_life_days", 30)),
                candidate_weight=float(sw_cfg.get("candidate_weight", 0.4)),
                manip_discount=float(sw_cfg.get("manip_discount", 0.5)),
                return_label_times=True, weights_cfg=sw_cfg,
                telemetry_cfg=tele_cfg, epoch_cfg=epoch_cfg, era_cfg=era_cfg)
            # LP-4: the same feature contract the INFERENCE path enforces
            # screens the training matrix - a poisoned row must not be
            # 'fixed' into the weights (rows dropped, never imputed)
            from ml.contracts import get_contract
            _keep = get_contract().check_matrix(X)["keep"]
            if not _keep.all():
                X, y, w = X[_keep], y[_keep], w[_keep]
                sig, res = sig[_keep], res[_keep]
            if len(X) < 60 or y.sum() < 10 or (len(y) - y.sum()) < 10:
                return
            log.warning(f"auto-retrain: {len(X)} rows "
                        f"({rows - self._rows_at_last_train} new)")
            # sig -> TIME-based fold purge: the deployed champion is selected
            # on leak-free OOF (row-count purge under-purges bursty signals).
            # label_span MUST match the labeler's actual horizon (config
            # label_max_bars) or the purge window and the label window drift.
            # opt-in adaptive rung: only enters the deployed selection when
            # ml.adaptive_gbt.enabled (disabled -> extra_models=() -> the
            # historical in-process ladder, unchanged).
            _ag = self.config.get('ml', {}).get('adaptive_gbt', {}) or {}
            # opt-in monotone-constrained GBT rung (T3.4): SHIPPED DISABLED
            # (ml.gbt_mono.enabled=false) - entering the deployed ladder is
            # a conscious PBO re-baseline (T3.5 rule), not this task's call.
            # Constraint feature NAMES are resolved to column indices here
            # (main.py already imports FEATURE_NAMES at module scope) so
            # ml/walkforward.py never needs to import ml.features itself.
            _gm = self.config.get('ml', {}).get('gbt_mono', {}) or {}
            _gm_constraints = {
                FEATURE_NAMES.index(_name): int(_sign)
                for _name, _sign in (_gm.get('constraints') or {}).items()
                if _name in FEATURE_NAMES} if _gm.get("enabled") else {}
            _extra = tuple(
                _name for _name, _on in
                (("adaptive_gbt", _ag.get("enabled")),
                 ("gbt_mono", _gm.get("enabled"))) if _on)
            # EVIDENCE GATE: admit a higher-capacity family only when the
            # LIVE (ground-truth) label count can support it - don't train
            # every model when the data gives the complex ones no chance.
            # Count from the load's own CLEAN pass when available: a raw CSV
            # scan counts dirty live rows the loader just dropped, making the
            # floor marginally permissive vs the rows actually entering the fit.
            _stats = getattr(self.history, "last_load_stats", {}) or {}
            _n_live = _stats.get("live_clean")
            if _n_live is None:
                _sc_fn: Optional[Callable[[], dict]] = getattr(
                    self.history, "source_counts", None)
                _n_live = ((_sc_fn() or {}).get("live", 0)
                           if callable(_sc_fn) else 0)
            _sel_cfg = self.config.get('ml', {}).get('model_selection') or None
            results = evaluate_and_select(
                X, y, sample_weight=w, feature_names=FEATURE_NAMES,
                label_span=int(self.config.get('ml', {})
                            .get('label_max_bars', 96)),
                ensemble_k=int(self.config.get('ml', {})
                            .get('ensemble_seeds', 3)), sig=sig,
                extra_models=_extra, adaptive_cfg=_ag,
                n_live=int(_n_live), select_cfg=_sel_cfg, res=res,
                gbt_mono_cfg={"constraints": _gm_constraints})
            self._last_retrain_calib_gap = family_metric(results, "calib_gap")
            if results.get("gated"):
                get_audit().log(
                    "ml_governor", Code.ML_LADDER_GATED,
                    f"selection gated to {results.get('admitted')} "
                    f"(skipped {results['gated']}): {_n_live} live labels",
                    {"admitted": results.get("admitted"),
                     "gated": results["gated"], "live": int(_n_live),
                     "total": int(len(X))})
            sel = results[results["selected"]]
            cal = IsotonicCalibrator().fit(sel["oof_p"], sel["oof_y"])
            if not cal.fitted:
                log.warning(f"ML-014: calibration skipped - only "
                           f"{len(sel['oof_p'])} OOF points (<20 needed) - "
                           f"challenger ships with raw, uncalibrated "
                           f"probabilities")
                get_audit().log("ml_governor", Code.ML_CALIBRATION_SKIPPED,
                                f"isotonic PAV had {len(sel['oof_p'])} OOF "
                                f"points (<20) - auto-retrain challenger "
                                f"ships uncalibrated",
                                {"oof_points": int(len(sel["oof_p"]))})
            # H13: the SHIPPED calibrator above stays the full-pool fit
            # (the artifact is unchanged), but the GATE score must not be
            # calibration-in-sample while the champion is rescored strictly
            # out-of-sample - see cross_fitted_calibrated_oof. This one
            # vector feeds challenger_brier, the n_oof evidence count and
            # shared_challenger_brier, so all three move together.
            _cv_folds = int((self.config.get("ml", {}).get("monitor", {})
                             or {}).get("gate_calibration_folds", 5))
            oof_cal = cross_fitted_calibrated_oof(
                sel["oof_p"], sel["oof_y"], folds=_cv_folds) \
                if len(sel["oof_p"]) else sel["oof_p"]
            if not len(oof_cal):
                # purged walk-forward can produce ZERO out-of-fold points at
                # small row counts (the purge span swallows every test fold)
                # - the challenger is then UNSCOREABLE, not "0.25". Say so
                # instead of letting a fabricated score masquerade as a fair
                # reject (observed: 88 rows -> 0 OOF -> silent auto-reject).
                log.warning("auto-retrain unscoreable: 0 OOF points at "
                            "%d rows (purge span eats the folds) - keeping "
                            "champion until more labels accrue", len(X))
                return
            challenger_brier = brier_score(sel["oof_y"], oof_cal)
            self._rows_at_last_train = rows
            oof_idx = results.get("oof_idx", [])
            # STALE-BADGE GUARD (ML-042): rescore the FROZEN incumbent on
            # the same fresh OOF rows before gating — its stored brier is
            # a birth certificate from an older corpus era, and comparing
            # challengers against it lets an aging champion squat forever
            # (measured live: badge 0.1887 vs 0.27+ for every honestly-
            # scored candidate on the current corpus).
            champ_fresh = self.monitor.rescore_frozen(
                self.meta.model, self.meta.calibrator, X, y,
                oof_idx, self.meta.trained_rows,
                self.monitor.deploy_min_oof)
            if champ_fresh is not None and \
                    abs(champ_fresh - self.monitor.champion_brier) > 1e-9:
                get_audit().log(
                    "ml_governor", Code.ML_CHAMP_RESCORED,
                    f"champion rescored on fresh OOF: "
                    f"{self.monitor.champion_brier:.4f} -> "
                    f"{champ_fresh:.4f}",
                    {"old": round(self.monitor.champion_brier, 4),
                     "new": round(champ_fresh, 4)})
                log.info("champion badge realigned: %.4f -> %.4f (fresh "
                         "OOF, rows beyond its training horizon)",
                         self.monitor.champion_brier, champ_fresh)
                self.monitor.champion_brier = champ_fresh
            # W2-2 stale-gate CAS: snapshot the on-disk champion's identity
            # right before the gate decision. A CLI scripts/train_meta.py run
            # can race this in-process retrain — both gate a challenger
            # against the CURRENT champion; whichever writes last must not
            # silently clobber the other's already-deployed artifact with a
            # decision made against a champion that no longer exists on
            # disk. save_model() re-checks this immediately before its write.
            from ml.registry import sha256_file
            _model_path_p = Path(self.meta.model_path)
            try:
                _prior_hash = (sha256_file(_model_path_p)
                              if _model_path_p.exists() else None)
            except OSError:
                _prior_hash = None
            # LIKE-FOR-LIKE GATE: should_deploy may only compare champion and
            # challenger scores drawn from the IDENTICAL row set. Before this,
            # the champion above was rescored on the fresh OOF tail (base
            # rate can differ ~79% from the full span — measured live 0.0841
            # vs 0.1508) while the challenger below was scored over the FULL
            # oof_idx span: Brier is not comparable across differing base
            # rates, so the champion won by population, not merit (four
            # days, 68/68 REJECT — task-champ-report.md). When a real
            # champion is loaded, gate both scores on the SAME shared rows;
            # an incomparable pair (too few fresh rows, a rescore fault)
            # fails CLOSED — promotion is new risk and is never granted by
            # default. Cold start (no champion loaded yet) has no incumbent
            # population to match, so should_deploy's own no-champion
            # clause still decides on the challenger's full-span score,
            # exactly as before.
            if self.meta.model is None:
                _deploy_ok = self.monitor.should_deploy(challenger_brier,
                                                        n_oof=len(oof_cal))
            elif int(self.meta.trained_rows) > len(X):
                # 2026-07-29 ERA-ORPHAN UNLOCK (ML-083): the champion's
                # trained_rows watermark indexes a corpus POPULATION that
                # no longer exists - era exclusion (ML-081) rebuilt the
                # training matrix smaller than the watermark itself
                # (measured live: champion rows=4823 vs post-exclusion
                # matrix 1516), so idx >= trained_rows is empty BY
                # CONSTRUCTION and the fail-closed branch below would
                # REJECT every retrain forever (observed: RETRAIN flag
                # stuck QUEUED, deploys structurally impossible). An
                # unfalsifiable badge may not gate forever (ML-076
                # doctrine): fall back to the no-champion clause - the
                # challenger must clear the SAME absolute cold-start bar
                # (should_deploy's own thresholds; nothing widened), and
                # the incumbent keeps serving until one does. NOTE: if
                # the corpus regrows past a stale watermark before any
                # deploy, indexes would misalign silently - this branch
                # fires first precisely because the watermark exceeds
                # the matrix, closing that window with an audit record.
                # ignore_champion=True (wave-4/5 adversarial-verify fix,
                # same day): the era-orphaned BADGE is set aside too -
                # it is a Brier measured on the dead population's base
                # rate and consulting it kept the deadlock alive in a
                # softer form (should_deploy's no-champion disjunct only
                # frees the bar when the badge is >= 0.25; the live
                # badge is 0.1237). The challenger faces the true
                # cold-start standard: Brier < 0.25 + deploy_min_oof.
                get_audit().log(
                    "ml_governor", Code.ML_CHAMPION_ERA_ORPHAN,
                    f"champion watermark era-orphaned: trained_rows="
                    f"{int(self.meta.trained_rows)} > corpus {len(X)} - "
                    f"like-for-like impossible by construction; deploy "
                    f"gate applies the cold-start bar with the badge "
                    f"set aside (era-orphaned, not comparable)",
                    {"trained_rows": int(self.meta.trained_rows),
                     "corpus_rows": int(len(X)),
                     "challenger_brier": float(challenger_brier),
                     "n_oof": int(len(oof_cal))})
                _deploy_ok = self.monitor.should_deploy(
                    challenger_brier, n_oof=len(oof_cal),
                    ignore_champion=True)
            else:
                shared = None if champ_fresh is None else \
                    self.monitor.shared_challenger_brier(
                        oof_idx, self.meta.trained_rows,
                        self.monitor.deploy_min_oof, oof_cal, y)
                if shared is None:
                    n_shared = int(np.sum(
                        np.asarray(oof_idx, int) >=
                        int(self.meta.trained_rows)))
                    detail = {"decision": "REJECT", "n_shared": n_shared,
                             "deploy_min_oof": self.monitor.deploy_min_oof}
                    get_audit().log(
                        "ml_governor", Code.ML_DEPLOY_REJECT,
                        "challenger rejected: no like-for-like shared row "
                        f"set could be built vs the frozen champion "
                        f"({n_shared} candidate fresh OOF rows, "
                        f"deploy_min_oof={self.monitor.deploy_min_oof}) - "
                        f"comparing populations with different label base "
                        f"rates is refused, fail-closed", detail)
                    log.info("challenger brier=%.4f vs frozen champion: no "
                             "honest shared row set (%d candidate fresh "
                             "rows, deploy_min_oof=%d) -> REJECT "
                             "(fail-closed)", challenger_brier, n_shared,
                             self.monitor.deploy_min_oof)
                    _deploy_ok = False
                else:
                    _shared_brier, n_shared = shared
                    _deploy_ok = self.monitor.should_deploy(
                        _shared_brier, n_oof=n_shared)
            # continuous learning curve: one history row per retrain,
            # deployed or rejected (ml/retrain_log)
            from ml import retrain_log as _rl
            from ml.retrain_log import append_retrain, retrain_record
            append_retrain(
                self.config.get("ml", {}).get(
                    "retrain_history_path",
                    _rl.RETRAIN_HISTORY_PATH_DEFAULT),
                retrain_record(time.time(), "auto", results, len(X),
                               int(_n_live), challenger_brier,
                               self.monitor.champion_brier, _deploy_ok))
            if not _deploy_ok:
                return
            from ml.interpret import background_sample
            from ml.registry import sha256_array
            saved = save_model(results["model"], self.meta.model_path,
                    extra={"calibration": cal.to_dict(),
                            "oof_brier": challenger_brier,
                            "feature_deciles": feature_deciles(X),
                            # history-spanning background so interventional
                            # SHAP (scripts/interpret_report.py) is defined
                            # for THIS artifact without the training corpus
                            "background": background_sample(
                                X, int(self.config.get("ml", {})
                                       .get("interpret", {})
                                       .get("background_rows", 64))),
                            # walk-forward importance under its OWN key:
                            # "importance" would overwrite the gbt model's
                            # internal {idx: gain} dict in save_model's
                            # d.update(extra), so an auto-deployed gbt lost its
                            # gain importance while a CLI-deployed one kept it.
                            # Match scripts/train_meta.py's key.
                            "wf_importance": results.get("importance", []),
                            "rows": int(len(X)),
                            "class_balance": round(float(y.mean()), 3),
                            "train_data_sha": sha256_array(X)},
                    expect_prior_sha256=_prior_hash)
            if not saved:
                # W2-2: a concurrent writer (CLI train_meta.py) already
                # deployed to model_path since this gate read the champion -
                # this challenger was gated against a champion that no
                # longer exists on disk. Discard it rather than clobber the
                # newer artifact; the next cycle re-gates against whatever
                # actually landed.
                log.warning("auto-retrain challenger gated OK but a "
                           "concurrent writer already deployed to %s since "
                           "the gate read - discarding this challenger "
                           "instead of overwriting the newer artifact",
                           self.meta.model_path)
                return
            self.meta.reload()
            self.monitor.note_deployed(challenger_brier)
            log.warning(f"auto-retrain DEPLOYED {results['selected']} "
                        f"(oof brier {challenger_brier:.4f})")
        except Exception:
            self._retrain_failures += 1
            log.exception("auto-retrain failed - keeping current model "
                          "(retrain_failures=%d)", self._retrain_failures)

    def cycle_once(self, now: Optional[float] = None) -> None:
        """Exactly one engine cycle. The engine owns NO loop - runner.py
        (or a test, or the UI's 'run one cycle' button) drives this."""
        now = now if now is not None else time.time()
        if now - self._last_macro >= self.macro_refit_sec:
            # Hourly/slow refit is ISOLATED from the fast cycle below: a
            # deterministic raise in the refit (a poisoned cached candle in
            # macro.update, a model-load edge) must NEVER propagate out of
            # cycle_once and starve fast_cycle's per-position stop loop
            # (invariant #5). Advance the cadence stamp FIRST/regardless so a
            # poisoned hour retries next macro INTERVAL, not every cycle forever
            # (which is exactly how a single bad candle starved every exit).
            self._last_macro = now
            try:
                self.hourly_cycle(now)
            except Exception:
                self._exit_eval_failures += 1
                log.exception("hourly_cycle raised - isolated; fast-cycle exits "
                              "still run, retry next macro interval")
        self.fast_cycle(now)
        if self._cycle % self.slow_every == 0:
            # slow work (data refresh + entry pipeline) is NEW risk, never an
            # escape. Isolate it too: an unguarded raise here would propagate,
            # freeze the heartbeat increments below (so `_cycle % slow_every`
            # stays 0 and slow_cycle re-raises every cycle), and add nothing to
            # the exits fast_cycle already ran this cycle.
            try:
                self.slow_cycle(now)
            except Exception:
                self._exit_eval_failures += 1
                log.exception("slow_cycle raised - isolated; exits unaffected")
        self._cycle += 1
        self._cycle_lifetime += 1

    def _apply_sim(self) -> None:
        if not self.dry_run or not self.sim.active():
            return
        for asset, shock in self.sim.price_shock.items():
            sym = self.symbol_map.get(asset)
            if sym and self.marks.get(sym):
                self.marks[sym] *= (1.0 + shock["pct"] / 100.0)
        for asset, fr in self.sim.force_regime.items():
            st = self.macro.state(asset)
            st.label = fr["label"]
            st.playbook = dict(self.macro.playbooks.get(
                fr["label"], self.macro.playbooks["range"]))
            self.macro._states[asset] = st
        self.sim.tick()

    def _live_order_allowed(self, purpose: str) -> bool:
        """Hard gate: in live mode, entries/hedges require the operator to
        have armed trading. Exits are always allowed - blocking risk
        reduction is never safe. Dry run is unaffected (simulated)."""
        if self.dry_run or purpose == "exit" or self.live_armed:
            return True
        if time.time() - self._live_block_logged > 60:
            self._live_block_logged = time.time()
            log.warning("LIVE NOT ARMED: blocking new orders (exits still "
                        "allowed). Arm from the dashboard to trade.")
        return False

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Back-compat: the loop lives in runner.py now."""
        from runner import BotRunner
        BotRunner(self.config, bot=self).run()


def main() -> None:
    """Delegates to the runner - the loop lives there. `python main.py`
    and `python runner.py` are equivalent."""
    from runner import main as runner_main
    runner_main()


if __name__ == "__main__":
    main()
