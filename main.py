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

import hashlib
import json
import logging
import math
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from core.audit import get_audit
from core.codes import Code, tag
from core.sanitize import safe_float
from core.precision import fmt_price, price_decimals as _price_decimals
from core.state import PortfolioState, Position
from core.persistence import StateStore
from core.runtime import SimOverrides
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
from strategies.liquidity_model import LiquidityModel
from strategies.signal_gates import GateStats, SignalGateEngine
from risk.capital_manager import CapitalManager
from risk.profit_tiers import ProfitTierEngine
from execution.algos import ExecutionScheduler
from execution.routing import SmartOrderRouter
from risk.leverage import LeverageGovernor
from risk.position_sizer import PositionSizer
from risk.protocols import RiskProtocolStack
from regime import (MacroRegimeEngine, VolRegimeEngine,
                    LiquidityRegimeEngine, CorrelationEngine)
from execution.fair_value import FairValueEngine
from execution.market_maker import AvellanedaStoikovQuoter
from execution.inventory import InventoryManager
from execution.pretrade import PreTradeGate, PreTradeContext
from execution.order_manager import OrderManager
from execution.hedging import HedgeEngine
from execution.markout import MarkoutTracker
from execution.tactics import ExecutionPlanner
from ml.features import FEATURE_NAMES, build_features
from ml.meta_model import MetaModelService
from ml.history import HistoryStore, CandidateLabeler, HorizonShadowStore
from ml.labeling import ExitPolicy
from ml.monitor import ModelMonitor
from core.performance import PerformanceTracker
from ml.postmortem import PostmortemEngine, TradeThesis
from risk.circuit_breaker import CircuitBreaker
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


def pick_unteachable_unwind(positions, pending_ids, at_capacity: bool,
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
    old_enough = [p for p in positions if not p.is_hedge and
                  (now - p.opened_at.timestamp()) / 3600.0 >= min_age_h]
    if not old_enough:
        return None
    return max(old_enough, key=lambda p: now - p.opened_at.timestamp())


def nudge_stop_off_round_number(stop: float, direction: str,
                                buffer_bps: float) -> float:
    """Osler (Stop-Loss Orders and Price Cascades in Currency Markets,
    J. Int'l Money & Finance 2005 / NY Fed SR150): stop orders cluster
    at round numbers, and cascades fire just AFTER price crosses one -
    a stop resting within buffer_bps of a round level fills at the
    bottom of the herd's cascade, not at its trigger. Nudge ours to the
    safe side of the level (long stops just ABOVE it, short stops just
    BELOW), exiting BEFORE the cluster detonates. The round lattice is
    magnitude-relative: half of the second-significant-digit unit
    (BTC ~63k -> every 500; ETH ~1.8k -> every 50; MINA ~0.45 -> every
    0.005), matching the 00/50 endings Osler documents. The nudge only
    ever TIGHTENS the stop (toward entry); if it cannot stay on the
    stop's own side of the level, the stop is returned unchanged."""
    if stop <= 0 or buffer_bps <= 0:
        return stop
    import math as _math
    spacing = 10.0 ** (_math.floor(_math.log10(stop)) - 1) / 2.0
    level = round(stop / spacing) * spacing
    if abs(stop - level) / stop * 1e4 > buffer_bps:
        return stop
    pad = level * buffer_bps / 1e4
    return level + pad if direction == "long" else level - pad


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


def _composite_imbalance(venue_books: list):
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
                "startup", "CG-000", "session start: config fingerprint",
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

        # --- v1 core ---
        self.liquidity_model = LiquidityModel(config)
        engine_kind = (config.get("strategies") or {}).get("engine",
                                                          "five_gate")
        if engine_kind == "informed_flow":
            from strategies.informed_flow import InformedFlowEngine
            self.gates = InformedFlowEngine(config.get("informed_flow", {}))
        else:
            self.gates = SignalGateEngine(config)
        log.info(f"signal engine: {engine_kind}")
        self.tactics = ExecutionPlanner(config.get("execution_tactics", {}))
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
        self.orders = OrderManager(self.kraken, config.get("order_manager", {}),
                                dry_run=self.dry_run,
                                firewall=self.firewall, pair_meta=pair_meta)
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
        self.meta = MetaModelService(config.get("ml", {}))
        self.history = HistoryStore(config.get("ml", {})
                                    .get("history_path", "outputs/signal_history.csv"))
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
        self.gate_stats = GateStats(config.get("signal_gates", {})
                                    .get("learned_weights", {}))
        # exit-policy labeler reads the live stop + tier + give-back geometry
        # from the SAME config the engine trades, so candidate labels answer
        # "would this signal net positive under OUR exit policy" (default mode)
        self.candidates = CandidateLabeler(self.history, config.get("ml", {}),
                                           on_label=self.gate_stats.note_label,
                                           shadow_store=self.horizon_shadow,
                                           exit_policy=ExitPolicy.from_config(
                                               config))
        # THALES lazy-bot insecurity model (docs/THALES.md): detector bank
        # over public books/candles; shadow by default (telemetry only),
        # bounded confidence shading only when influence=advise
        from strategies.thales import ThalesEngine
        self.thales = ThalesEngine(config.get("thales", {}))
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
        self._entry_rotation = 0            # round-robin offset, see _entry_assets
        self._explore_rng = random.Random(int(  # nosec B311 - epsilon sampling, not crypto
            config.get("system", {}).get("seed", 42)))
        self._stop_hit: dict = {}           # position_id -> bool
        self._thales_fired: dict = {}       # asset -> fired detectors (V2)
        self._pos_thales: dict = {}         # position_id -> fired at entry
        self._last_imb: dict = {}           # asset -> last log-imbalance
        self._regime_since: dict = {}       # asset -> (label, changed_at_ts)
        self._manip_scores: dict = {}       # asset -> latest suspicion [0,1]
        # cumulative count of per-position exit/stop evaluations that RAISED
        # and were isolated (surfaced in status). One position that
        # deterministically errors must never starve the OTHER positions'
        # hard stops — a non-zero, climbing value means a book position is
        # wedging its own escape path and needs an operator's eye.
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
                depth=int(_kws.get("kraken_depth", 10)))
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
        self._stop_ok: dict = {}            # asset -> stop eval allowed this cycle
        self._equity_drift_pct: float = 0.0

        # --- rolling market state ---
        self.view: dict = {}                # base asset -> merged venue view
        self.kraken_books: dict = {}        # base asset -> kraken order book
        self.marks: dict = {}               # kraken symbol -> last price
        self._mark_ts: dict = {}            # kraken symbol -> last mark update
        self.book_ts: dict = {}             # base asset -> fetch time
        self.daily_candles: dict = {}       # base asset -> daily candles
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

        # --- pause/resume ---
        self.store = StateStore(sys_cfg.get("state_path", "outputs/state.json"))
        self._resumed = False
        if resume and self.store.exists():
            self._resumed = self.store.restore(self)
            if self._resumed and not self.dry_run:
                self._reconcile_live_on_resume()

        # central fault authority (op-state ledger + policy). Armed at the END
        # of a SUCCESSFUL construction: a bot that finished __init__ passed
        # startup validation (enforce_config above raises on a live FATAL), so
        # ARMED is correct. Driven by the halt conditions (catastrophe hard-stop
        # here, the runner wedge in runner.py); allow_new_risk() gates NEW
        # entries — exits are NEVER gated (invariant #5). Faults are process-
        # scoped and latch until an operator clears them or restarts.
        self.fault = FaultManager(alerts=self.alerts)
        self.fault.arm()

    def _reconcile_live_on_resume(self):
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
        for asset, symbol in self.symbol_map.items():
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

    def _submit_algo_child(self, parent, now: float):
        """Price and submit one child slice through the UNCHANGED
        hardened path: fresh AS quote + tactics for placement, then
        order_manager (pre-trade already approved the parent's edge;
        the firewall re-checks every child)."""
        meta_t = self._algo_meta.get(parent.parent_id) or {}
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
                  "features": meta_t.get("features"),
                  "algo_parent": parent.parent_id,
                  "algo_child_seq": child.seq},
        )
        if order:
            self.algo.note_child_order(parent.parent_id, position_id)
            log.info(f"ALGO-CHILD {child.seq}/{child.n_total} "
                     f"{parent.side} {child.units:.6f} {parent.symbol} "
                     f"@ {self._px(parent.symbol, plan.price)} [{plan.style}] "
                     f"parent={parent.parent_id}")
        else:
            self.algo.note_child_rejected(parent.parent_id, child.units,
                                          "order_manager/firewall refused")

    def _step_exec_algos(self, now: float):
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

    def _px(self, symbol: str, price) -> str:
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

    def _stop_price_for(self, direction: str, entry: float, asset: str) -> float:
        vol_state = self.vol.state(asset)
        macro_state = self.macro.state(asset)
        stop_pct = max(self.base_stop_pct,
                       self.stop_vol_mult * vol_state.sigma_bar_pct)
        stop_pct *= macro_state.playbook.get("stop_mult", 1.0)
        stop_pct *= self.monitor.stop_widen
        stop = entry * (1 - stop_pct / 100.0) if direction == "long" \
            else entry * (1 + stop_pct / 100.0)
        # Osler round-number hygiene: never rest a stop inside the herd's
        # cascade zone (see nudge_stop_off_round_number). Config-gated;
        # the nudge is bps-scale and only ever tightens.
        buf = float(self.config.get("risk_management", {})
                    .get("stop_round_buffer_bps", 5.0))
        nudged = nudge_stop_off_round_number(stop, direction, buf)
        if direction == "long":
            return min(max(nudged, stop), entry * 0.999)
        return max(min(nudged, stop), entry * 1.001)

    # ------------------------------------------------------------------
    # fill handling
    # ------------------------------------------------------------------
    def _finalize_position(self, pos: Position, total_net: float, now: float):
        """Single close-out path (fill-flat and dust-flat both land here):
        history close, postmortem observation, ledger removal, counter
        cleanup. Keeping this in one place means the two exits can never
        drift apart."""
        asset = self._asset_of(pos.symbol)
        self.history.log_close(pos.position_id, total_net)
        # rolling performance ledger — every full close, real positions only
        # (hedges carry no thesis/stop of their own). total_net is the popped
        # cumulative (all tier closes + final), so this is the whole trade.
        if not pos.is_hedge:
            self.perf.record_close(
                asset, total_net, pos.entry_price * pos.original_size,
                entry_price=pos.entry_price, stop_price=pos.stop_price, now=now)
            if self.breaker.record_close(asset, total_net > 0, now=now):
                get_audit().log("circuit_breaker", Code.SZ_CIRCUIT_BREAKER,
                                f"{asset} paused: "
                                f"{self.breaker.loss_streak} consecutive "
                                f"losses", {"asset": asset})
            # THALES V2 vindication: grade the detectors that shaded this
            # trade's entry against its realized outcome
            fired = self._pos_thales.pop(pos.position_id, None)
            if fired:
                self.thales.note_outcome(fired, total_net > 0)
        self.postmortem.on_close(
            pos.position_id, total_net, pos.fees_paid_usd,
            entry_usd=pos.entry_price * pos.original_size,
            stopped_out=self._stop_hit.pop(pos.position_id, False),
            exit_regime=self.macro.state(asset).label,
            exit_liq=self.liq.state(asset).label,
            now=now)
        self.state.remove_position(pos.position_id)
        self._exit_attempts.pop(pos.position_id, None)

    def _handle_fill(self, event, now: Optional[float] = None):
        now = now if now is not None else time.time()
        order = event.order
        if event.fill_size > EPS and order.purpose in ("entry", "hedge"):
            pos = self.state.get_position(order.position_id) if order.position_id else None
            if pos is None:
                position_id = order.position_id or str(uuid.uuid4())
                pos = Position(
                    position_id=position_id, symbol=order.symbol,
                    direction="long" if order.side == "buy" else "short",
                    entry_price=event.fill_price, size=event.fill_size,
                    original_size=event.fill_size,
                    opened_at=datetime.now(timezone.utc),
                    is_hedge=(order.purpose == "hedge"),
                    confidence=order.meta.get("p_win", 0.0),
                    edge_bps=order.meta.get("edge_bps", 0.0),
                    leverage=order.leverage,
                )
                pos.stop_price = self._stop_price_for(
                    pos.direction, pos.entry_price, self._asset_of(pos.symbol))
                order.position_id = position_id
                self.state.add_position(pos)
                fired = order.meta.get("thales_fired")
                if fired and not pos.is_hedge:
                    self._pos_thales[position_id] = list(fired)
                self.postmortem.note_fill(position_id, event.fill_price)
                if not pos.is_hedge and "features" in order.meta:
                    self.history.log_entry(position_id, self._asset_of(pos.symbol),
                                        pos.direction, order.meta["features"])
                log.info(f"OPEN {pos.direction} {pos.size:.6f} {pos.symbol} "
                        f"@ {self._px(pos.symbol, pos.entry_price)} "
                        f"(p={pos.confidence:.2f}, "
                        f"hedge={pos.is_hedge})")
            else:
                total = pos.size + event.fill_size
                pos.entry_price = (pos.entry_price * pos.size +
                                   event.fill_price * event.fill_size) / total
                pos.size = total
                pos.original_size = max(pos.original_size, total)
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

        elif event.fill_size > EPS and order.purpose == "exit":
            pos = self.state.get_position(order.position_id)
            if pos is None:
                return
            self._exit_attempts.pop(order.position_id, None)  # progress: de-escalate
            sgn = 1.0 if pos.direction == "long" else -1.0
            fee_delta = order.fees_usd - order.meta.get("_fees_seen", 0.0)
            order.meta["_fees_seen"] = order.fees_usd
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
            self.capital.record_realized_profit(net, self.state)
            self._pos_realized[pos.position_id] = \
                self._pos_realized.get(pos.position_id, 0.0) + trade_net
            log.info(f"CLOSE {event.fill_size:.6f} {pos.symbol} @ "
                    f"{self._px(pos.symbol, event.fill_price)} "
                    f"net ${trade_net:+,.2f} (remaining {pos.size:.6f})")
            if pos.size <= pos.original_size * 1e-4 or pos.size <= EPS:
                total_net = self._pos_realized.pop(pos.position_id, trade_net)
                self._finalize_position(pos, total_net, now)
                log.info(f"FLAT {pos.symbol} position {pos.position_id[:8]}: "
                        f"total net ${total_net:+,.2f}")

    def _submit_exit(self, pos: Position, close_pct: float, reason: str,
                 tier_fired: int = 0, now: Optional[float] = None,
                 profit_take: bool = False):
        """Risk-reduction exit: marketable limit, slippage-capped, never
        blocked by the pre-trade edge gate (exits are risk management).

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
            self._finalize_position(pos, total_net, now)
            return

        attempts = self._exit_attempts.get(pos.position_id, 0)
        slip_pct = min(self.max_slip_pct * (self.esc_widen_mult ** attempts),
                       self.esc_max_slip_pct)
        go_market = attempts >= self.esc_market_after
        book = self.kraken_books.get(asset) or {}
        bids, asks = book.get("bids") or [], book.get("asks") or []
        mark = self.marks.get(pos.symbol, pos.entry_price)
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
        size = pos.size * close_pct / 100.0
        if size <= EPS:
            return
        if omin > 0 and size < omin:
            # a dust SLICE with a viable remainder: close the whole
            # position instead of leaving an unexitable stub behind
            log.info(f"exit slice {size:.8f} {pos.symbol} below venue "
                     f"minimum {omin} - escalating to full close")
            close_pct, size = 100.0, pos.size
        order = self.orders.submit(
            asset=asset, symbol=pos.symbol, pair=self.kraken.kraken_pair(pos.symbol),
            side=side, price=price, size=size, purpose="exit",
            position_id=pos.position_id, close_pct=close_pct,
            post_only=maker_first,
            ordertype="market" if go_market else "limit",
            ref_price=mark, equity=self._equity(),
            book=book, sigma_bar_pct=self.vol.state(asset).sigma_bar_pct,
            meta={"reason": reason, "attempt": attempts + 1,
                  "tier_fired": int(tier_fired)},
        )
        if order is None:
            return                      # rejected orders never escalate
        self._exit_attempts[pos.position_id] = attempts + 1
        if attempts > 0 or go_market:
            log.warning(f"exit ESCALATION {pos.symbol} attempt "
                        f"{attempts + 1}: slip cap {slip_pct:.2f}%"
                        f"{' -> MARKET' if go_market else ''} ({reason})")
        else:
            log.info(f"exit {close_pct:.0f}% of {pos.symbol} ({reason})")

    # ------------------------------------------------------------------
    # FAST cycle
    # ------------------------------------------------------------------
    def fast_cycle(self, now: float):
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
                self.book_ts[asset] = now
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
                            self._stop_ok[asset] = ok

        # execution algos: release due child slices (paced, guarded)
        self._step_exec_algos(now)

        self._apply_sim()   # sim overlays AFTER fresh data lands

        # advance orders, apply fills
        sig = {a: self.vol.state(a).sigma_bar_pct for a in self.symbol_map}
        fills = self.orders.poll(self.kraken_books, sig, now)
        for event in fills:
            self._handle_fill(event, now)
        if fills:
            self.store.snapshot(self)      # never lose an executed fill

        self.state.maybe_reset_daily_pnl()
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
        self.watchdog.evaluate(
            now, self.book_ts, list(self.symbol_map), kraken_mids, fvs,
            equity, self.state.open_position_count(), self.dry_run)

        if marks_confirmed and self.capital.hard_stop_triggered(self.state, equity):
            if not self._halted:
                log.critical("HARD STOP drawdown breached - flattening, no new risk")
                self._halted = True
                fm = getattr(self, "fault", None)
                if fm is not None:
                    fm.latch("hard_stop_drawdown", Severity.CRITICAL,
                             "catastrophe drawdown hard-stop: flatten-and-stop")
            # emergency flatten: isolate per position so one that errors on
            # exit submission cannot leave the REST of the book unflattened
            for pos in list(self.state.open_positions()):
                try:
                    self._submit_exit(pos, 100.0, "hard stop", now=now)
                except Exception:
                    self._exit_eval_failures += 1
                    log.exception("[%s] hard-stop flatten raised - flattening "
                                  "the rest of the book", pos.symbol)
            return

        macro_states = {a: self.macro.state(a) for a in self.symbol_map}

        # postmortem plumbing: mark trails + finalize elapsed observations
        self.postmortem.record_marks(self.marks, now)
        # post-fill mark-out resolves due horizons against the TRUSTED mark
        # (jump-confirmed + fresh); a stale/dark feed defers, never fabricates.
        _mk = getattr(self, "markout", None)
        if _mk is not None:
            _mk.poll(self.marks, now, is_fresh=self._mark_fresh)
        self.risk_protocols.observe(equity, self.marks, now)
        for cause, thesis in self.postmortem.poll(now):
            self.monitor.record_close(self._thesis_scored_p(thesis),
                                    int(thesis.realized_net_usd > 0),
                                    thesis.model_scored, cause)

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

    def _run_hedge_pass(self, now: float, equity: float):
        """Hedge/unwind/trim actions, isolated so a hedge-engine error cannot
        wedge fast_cycle (the stop loop already ran above)."""
        try:
            self._hedge_actions(now, equity)
        except Exception:
            self._exit_eval_failures += 1
            log.exception("hedge pass raised - isolated, cycle continues")

    def _hedge_actions(self, now: float, equity: float):
        for act in self.hedger.evaluate(self.state, self.marks, equity,
                                        self.corr.state):
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
                px = self.marks.get(act.symbol)
                book = self.kraken_books.get(act.asset) or {}
                if not px:
                    continue
                side = "buy" if act.direction == "long" else "sell"
                touch = ((book.get("asks") or [[px, 0]])[0][0] if side == "buy"
                        else (book.get("bids") or [[px, 0]])[0][0])
                price = touch * (1 + self.max_slip_pct / 100.0) if side == "buy" \
                    else touch * (1 - self.max_slip_pct / 100.0)
                self.orders.submit(
                    asset=act.asset, symbol=act.symbol,
                    pair=self.kraken.kraken_pair(act.symbol), side=side,
                    price=price, size=act.usd / px, purpose="hedge",
                    post_only=False, book=book, ref_price=px, equity=equity,
                    sigma_bar_pct=self.vol.state(act.asset).sigma_bar_pct,
                    meta={"reason": act.reason},
                )
                log.info(f"HEDGE {act.direction} ${act.usd:,.0f} {act.symbol}: "
                        f"{act.reason}")

    def _manage_open_position(self, pos, now: float, equity: float,
                              macro_states: dict):
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
        # A quarantined tick (single anomalous print) holds stop
        # evaluation for exactly one cycle; confirmation fires it.
        if pos.stop_price and self._stop_ok.get(asset, True) and (
                (pos.direction == "long" and px <= pos.stop_price) or
                (pos.direction == "short" and px >= pos.stop_price)):
            self._stop_hit[pos.position_id] = True
            self._submit_exit(pos, 100.0,
                              f"stop {self._px(pos.symbol, pos.stop_price)} hit",
                              now=now)
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
                sigma_bar_pct=self.vol.state(asset).sigma_bar_pct,
                signal_alive=signal_alive,
                inventory_pressure=min(inv_ratio, 1.0))
            if action.should_close_partial and action.close_pct > 0:
                self._submit_exit(pos, action.close_pct,
                                f"tier {action.tier_fired or 'trail'}",
                                tier_fired=action.tier_fired, now=now,
                                profit_take=action.is_profit_take)

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

    def _exploration_active(self, now: float,
                            asset: Optional[str] = None) -> bool:
        """True only when it is safe and useful to take a paper exploration
        trade. HARD INVARIANT: dry_run only - exploration must never influence
        a live order. Off once enough training rows have accrued (the model
        can then be trusted to gate on its own). When `asset` is given, an
        asset already holding >= max_asset_share of the labeled history is
        skipped (variety: the most active pair otherwise hogs every learning
        slot and quiet pairs never accrue fill labels)."""
        if not self.dry_run:
            return False                        # never in live - hard-gated
        if not self.explore_enabled:
            return False
        if self.history.row_count() >= self.explore_until_rows:
            return False                        # enough data: trust the model
        if self._explore_rng.random() >= self.explore_epsilon:
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

    def _log_sizer_veto(self, asset: str, reasons: list, explored: bool):
        """Exploration entries surface their sizer veto at INFO: these are
        the trades the bot takes SPECIFICALLY to learn, so a veto here is a
        learning outage, not routine noise. (A DEBUG-only veto hid 45h of
        total entry starvation behind a miscalibrated liquidity label.)"""
        log.log(logging.INFO if explored else logging.DEBUG,
                "[%s] sizer veto: %s", asset,
                "; ".join(str(r) for r in reasons) or "(no reason recorded)")

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

    def _augment_view_with_kraken(self):
        """Data-cold fallback: any execution-venue pair that the third-party
        data feeds (OKX/Binance.US) don't carry - e.g. a Kraken-only listing
        like MINA/USD - still needs intraday candles + a book to warm up
        vol/liq/fair-value and to emit training candidates, or it would be
        tradeable-but-inert. Fetch those from Kraken itself (the venue that
        by definition lists every pair we trade), mirroring the daily-candle
        Kraken fallback already in hourly_cycle. Only fills GAPS: an asset
        the multi-venue view already covers is left untouched, so ETH/BTC
        cross-venue imbalance is unchanged and this is behavior-preserving
        for the existing universe."""
        for asset, symbol in self.symbol_map.items():
            existing = self.view.get(asset)
            if existing and existing.get("candles"):
                continue
            pair = self.kraken.kraken_pair(symbol)
            try:
                candles = self.kraken.get_candles(pair)
            except Exception:
                log.debug("kraken intraday fallback failed for %s", asset,
                          exc_info=True)
                continue
            if not candles:
                continue
            book = self.kraken_books.get(asset) or {}
            entry = dict(existing or {})
            entry["candles"] = candles
            entry.setdefault("order_book", book)
            entry.setdefault("kraken_symbol", symbol)
            self.view[asset] = entry

    def slow_cycle(self, now: float):
        self.view = self.liquidity_model.build_view(
            *self._fetch_market_payloads())
        self._augment_view_with_kraken()

        closes = {}
        for asset, v in self.view.items():
            if asset not in self.symbol_map:
                continue
            kbook = self.kraken_books.get(asset) or {}
            self.fv.update(asset, [v.get("order_book") or {}], kbook)
            self.vol.update(asset, v.get("candles") or [],
                            self.daily_candles.get(asset) or [])
            self.liq.update(asset, v.get("order_book") or {}, kbook, now)
            # refresh the manipulation score EVERY cycle, not only at
            # signal evaluation: while the position cap pauses entries no
            # signals are evaluated, and a defense gauge that freezes on
            # its last value is blind exactly when the operator watches it
            ls = self.liq.state(asset)
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
        if closes:
            self.corr.update_intraday(closes)

        self._maybe_unwind_unteachable(now)
        sentiment = self.xscan.maybe_poll(now)
        web = self.webdata.maybe_poll(now)
        risk = self.moomoo.maybe_poll(now)
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
            if self.orders.has_open(asset, "entry"):
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
            # V2 vindication loop: remember which detectors shaded THIS
            # signal so a resulting position's close can grade them
            # (advise mode only — shadow advice never influenced the trade)
            self._thales_fired[asset] = (
                list(th.fired) if self.thales.influence == "advise" else [])
            if th.notes and abs(th.would_mult - 1.0) > 1e-6:
                log.info(f"thales {asset}: {'; '.join(th.notes)}")
            self.last_signals[asset] = {
                "confirmed": bool(signal.all_confirmed),
                "direction": signal.direction,
                "confidence": round(float(signal.confidence), 3),
                "urgency": round(float(getattr(signal, "urgency", 0.0)), 2),
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
            feats = build_features(asset, signal.direction, gate_conf, v,
                                fv_state, vol_state, liq_state, macro_state,
                                self.corr.state, sentiment, smc_feats,
                                other_asset=others[0] if others else None,
                                extras=self._feature_extras(
                                    asset, v, web, risk,
                                    others[0] if others else None, now))
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
            if can_enter and self._exploration_active(now, asset):
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
                                 "rows": self.history.row_count()})
                log.info("[%s] %sEXPLORATION paper entry: model p=%.2f -> sizing "
                         "p=%.2f, size x%.2f (learning; %d history rows)",
                         asset, "AGGRESSIVE " if aggressive else "", model_p,
                         p_win, explore_scale, self.history.row_count())

            # every confirmed signal becomes a training candidate (labeled
            # later via triple-barrier) - taken AND vetoed, so the model
            # learns from an unbiased sample instead of survivors only
            if v.get("candles"):
                self.candidates.register(asset, signal.direction, feats,
                                        vol_state.sigma_bar_pct / 100.0,
                                        v["candles"][-1]["time"],
                                        gates_passed=signal.gates_passed,
                                        spread_bps=liq_state.spread_bps)
            self.monitor.note_features(feats)
            if not can_enter:
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
                    continue
                manip_scale = scale

            sized = self.sizer.size(
                asset, signal.direction,
                self.marks.get(symbol) or fv_state.kraken_mid or 0.0,
                p_win, equity, self.state, macro_state, vol_state, liq_state,
                verdict.risk_multiplier, self.inventory, lev_decision,
                self.marks, now,
                risk_scale=self.monitor.kelly_mult * explore_scale * manip_scale,
                symbol=symbol, floor_to_min=(explored and not aggressive))
            if not sized.approved:
                self._log_sizer_veto(asset, sized.reasons, explored)
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

            exp_alpha_bps = max((p_win - 0.5) * 2.0, 0.0) * \
                self.sizer.b * self.base_stop_pct * 100.0
            ctx = PreTradeContext(
                kraken_book=self.kraken_books.get(asset) or {},
                sigma_daily_pct=vol_state.sigma_daily_pct,
                adv_usd=self._adv_usd(asset, entry_price),
                liq_label=liq_state.label,
                spread_bps=liq_state.spread_bps,
                staleness_ms=(now - self.book_ts.get(asset, 0.0)) * 1000.0,
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
                continue

            position_id = str(uuid.uuid4())
            # thesis for the postmortem engine: what did we expect and why
            stop_pct_eff = max(self.base_stop_pct,
                               self.stop_vol_mult * vol_state.sigma_bar_pct) * \
                macro_state.playbook.get("stop_mult", 1.0) * self.monitor.stop_widen
            target_pct = self.sizer.b * stop_pct_eff
            ev_pct = (p_win * target_pct - (1 - p_win) * stop_pct_eff) - \
                decision.est_cost_bps / 100.0
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
                model_p=model_p,
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
                    "features": feats, "leverage":
                        lev_decision.allowed_leverage,
                    "post_only": plan.post_only,
                    "thales_fired": self._thales_fired.get(asset) or []}
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
                    "features": feats,
                    "thales_fired": self._thales_fired.get(asset) or []},
            )
            if order:
                self.sizer.note_entry(asset, now)
                reserved_entries += 1                  # committed a slot
                if not self.capital.can_open_new_position(
                        self.state, reserved_entries):
                    can_enter = False
                log.info(
                    f"ENTRY {signal.direction} {symbol} [{plan.style}]: ${sized.usd:,.0f} "
                    f"({decision.size_units:.6f}) @ "
                    f"{self._px(symbol, entry_price)} | "
                    f"p={p_win:.2f} edge={decision.est_edge_bps:.0f}bps "
                    f"cost={decision.est_cost_bps:.0f}bps regime={macro_state.label} "
                    f"narrative={verdict.label}")

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
        kb_imb = _book_imbalance(self.kraken_books.get(asset) or {})
        comp_imb = _composite_imbalance(v.get("venue_books") or [])
        suspect = manip_suspect_score(
            liq_state.spoof_score,
            whiplash_suspicion(liq_state.imbalance_whiplash,
                               self._wl_p95, self._wl_thr),
            kb_imb, comp_imb if comp_imb is not None else kb_imb)
        self._manip_scores[asset] = round(suspect, 3)
        return {"fear_greed": web.fear_greed,
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
                "manip_suspect": suspect}

    def _maybe_unwind_unteachable(self, now: float):
        """ML-071 anti-wedge (see pick_unteachable_unwind). Dry-run only:
        live exits stay entirely with the tier engine and operator."""
        cfg = self.config.get("ml", {}).get("exploration", {})
        if not self.dry_run or not cfg.get("unteachable_unwind", True):
            return
        positions = self.state.open_positions()
        cap = self.capital.max_concurrent_positions
        pos = pick_unteachable_unwind(
            positions, set(self.history._pending), len(positions) >= cap,
            self.history.row_count(),
            int(cfg.get("until_live_rows", 240)), now,
            float(cfg.get("unteachable_min_age_h", 1.0)))
        if pos is None:
            return
        get_audit().log("engine", Code.ML_UNTEACHABLE_UNWIND,
                        f"learning-phase unwind {pos.symbol} "
                        f"{pos.position_id[:8]}: book full, zero pending "
                        f"label vectors - freeing a slot for trades that "
                        f"teach", {"position_id": pos.position_id})
        log.warning(f"{Code.ML_UNTEACHABLE_UNWIND.value}: unwinding "
                    f"{pos.symbol} {pos.position_id[:8]} - full book, no "
                    f"open position can produce a training row")
        self._submit_exit(pos, 100.0, "unteachable unwind (ML-071)")

    # ------------------------------------------------------------------
    # HOURLY cycle - macro regime + turbulence
    # ------------------------------------------------------------------
    def hourly_cycle(self, now: float):
        # adaptive-penalty staleness decay: without this a raised entry
        # bar can deadlock (bar blocks trades -> no closes -> the causes
        # window that justifies the bar never refreshes)
        self.monitor.decay_stale_causes(now)
        okx_syms = self.config["exchanges"]["okx"].get("symbols", [])
        binanceus_syms = self.config["exchanges"]["binanceus"].get("symbols", [])
        for asset in self.symbol_map:
            candles = []
            for s in okx_syms:
                if s.startswith(asset):
                    candles = self.okx.get_daily_candles(s)
                    break
            if not candles:
                for s in binanceus_syms:
                    if s.startswith(asset):
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

    def _check_equity_truth(self):
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

    def _maybe_auto_retrain(self):
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
            from ml.models import save_model
            from ml.calibration import (IsotonicCalibrator, brier_score,
                                        feature_deciles)
            sw_cfg = self.config.get("ml", {}).get("sample_weights", {})
            X, y, w, sig = self.history.load_training_data(
                half_life_days=float(sw_cfg.get("half_life_days", 30)),
                candidate_weight=float(sw_cfg.get("candidate_weight", 0.4)),
                manip_discount=float(sw_cfg.get("manip_discount", 0.5)),
                return_sig=True)
            if len(X) < 60 or y.sum() < 10 or (len(y) - y.sum()) < 10:
                return
            log.warning(f"auto-retrain: {len(X)} rows "
                        f"({rows - self._rows_at_last_train} new)")
            # sig -> TIME-based fold purge: the deployed champion is selected
            # on leak-free OOF (row-count purge under-purges bursty signals).
            # label_span MUST match the labeler's actual horizon (config
            # label_max_bars) or the purge window and the label window drift.
            results = evaluate_and_select(
                X, y, sample_weight=w, feature_names=FEATURE_NAMES,
                label_span=int(self.config.get('ml', {})
                            .get('label_max_bars', 96)),
                ensemble_k=int(self.config.get('ml', {})
                            .get('ensemble_seeds', 3)), sig=sig)
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
            oof_cal = cal.transform(sel["oof_p"]) if len(sel["oof_p"]) else sel["oof_p"]
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
            # STALE-BADGE GUARD (ML-042): rescore the FROZEN incumbent on
            # the same fresh OOF rows before gating — its stored brier is
            # a birth certificate from an older corpus era, and comparing
            # challengers against it lets an aging champion squat forever
            # (measured live: badge 0.1887 vs 0.27+ for every honestly-
            # scored candidate on the current corpus).
            champ_fresh = self.monitor.rescore_frozen(
                self.meta.model, self.meta.calibrator, X, y,
                results.get("oof_idx", []), self.meta.trained_rows,
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
            if not self.monitor.should_deploy(challenger_brier,
                                              n_oof=len(oof_cal)):
                return
            from ml.interpret import background_sample
            from ml.registry import sha256_array
            save_model(results["model"], self.meta.model_path,
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
                            "train_data_sha": sha256_array(X)})
            self.meta.reload()
            self.monitor.note_deployed(challenger_brier)
            log.warning(f"auto-retrain DEPLOYED {results['selected']} "
                        f"(oof brier {challenger_brier:.4f})")
        except Exception:
            self._retrain_failures += 1
            log.exception("auto-retrain failed - keeping current model "
                          "(retrain_failures=%d)", self._retrain_failures)

    def cycle_once(self, now: Optional[float] = None):
        """Exactly one engine cycle. The engine owns NO loop - runner.py
        (or a test, or the UI's 'run one cycle' button) drives this."""
        now = now if now is not None else time.time()
        if now - self._last_macro >= self.macro_refit_sec:
            self.hourly_cycle(now)
            self._last_macro = now
        self.fast_cycle(now)
        if self._cycle % self.slow_every == 0:
            self.slow_cycle(now)
        self._cycle += 1
        self._cycle_lifetime += 1

    def _apply_sim(self):
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
    def run(self):
        """Back-compat: the loop lives in runner.py now."""
        from runner import BotRunner
        BotRunner(self.config, bot=self).run()


def main():
    """Delegates to the runner - the loop lives there. `python main.py`
    and `python runner.py` are equivalent."""
    from runner import main as runner_main
    runner_main()


if __name__ == "__main__":
    main()
