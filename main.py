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
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from core.audit import get_audit
from core.codes import Code
from core.sanitize import safe_float
from core.state import PortfolioState, Position
from core.persistence import StateStore
from core.runtime import SimOverrides
from core.alerts import AlertSink
from core.config_guard import enforce as enforce_config
from core.watchdog import Watchdog
from execution.risk_firewall import RiskFirewall
from data.okx_feed import OKXFeed
from data.binanceus_feed import BinanceUSFeed
from data.ws_feed import WebSocketFeedManager
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
from execution.tactics import ExecutionPlanner
from ml.features import FEATURE_NAMES, build_features
from ml.meta_model import MetaModelService
from ml.history import HistoryStore, CandidateLabeler, HorizonShadowStore
from ml.monitor import ModelMonitor
from ml.postmortem import PostmortemEngine, TradeThesis
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
        self.capital = CapitalManager(config)
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
        self.corr = CorrelationEngine(config.get("correlation", {}))
        self.fv = FairValueEngine(config.get("fair_value", {}))
        self.quoter = AvellanedaStoikovQuoter(config.get("market_maker", {}))
        self.inventory = InventoryManager(config.get("inventory", {}))
        self.pretrade = PreTradeGate(config.get("pretrade", {}))
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
        # per-gate predictive power learned from labeled candidates; the
        # labeler feeds it as triple-barrier outcomes land (engine-agnostic
        # over gates_passed dicts, so informed-flow gates learn too)
        self.gate_stats = GateStats(config.get("signal_gates", {})
                                    .get("learned_weights", {}))
        self.candidates = CandidateLabeler(self.history, config.get("ml", {}),
                                           on_label=self.gate_stats.note_label,
                                           shadow_store=self.horizon_shadow)
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
        self._explore_rng = random.Random(int(  # nosec B311 - epsilon sampling, not crypto
            config.get("system", {}).get("seed", 42)))
        self._stop_hit: dict = {}           # position_id -> bool
        self._last_imb: dict = {}           # asset -> last log-imbalance
        self._rows_at_last_train = self.history.row_count()
        self.xscan = sentiment_scanner or SentimentScanner(
            config.get("sentiment", {}))
        self.narrative = NarrativeFilter(config.get("sentiment", {}).get("filter", {}))

        # asset universe: base asset -> kraken symbol
        self.symbol_map = {}
        for sym in config["exchanges"]["kraken"].get("trading_pairs", []):
            self.symbol_map[sym.split("/")[0]] = sym
        self.hedger = HedgeEngine(config.get("hedging", {}), self.symbol_map)

        risk_cfg = config.get("risk", {})
        self.base_stop_pct = float(risk_cfg.get("stop_loss_pct", 2.0))
        self.stop_vol_mult = float(risk_cfg.get("stop_vol_mult", 4.0))
        self.max_slip_pct = float(risk_cfg.get("max_slippage_pct", 0.5))
        esc = risk_cfg.get("exit_escalation", {}) or {}
        self.esc_widen_mult = float(esc.get("widen_mult", 2.0))
        self.esc_max_slip_pct = float(esc.get("max_slippage_cap_pct", 3.0))
        self.esc_market_after = int(esc.get("market_after_attempts", 3))
        self._exit_attempts: dict = {}      # position_id -> failed attempts
        self._stop_ok: dict = {}            # asset -> stop eval allowed this cycle
        self._equity_drift_pct: float = 0.0

        # --- rolling market state ---
        self.view: dict = {}                # base asset -> merged venue view
        self.kraken_books: dict = {}        # base asset -> kraken order book
        self.marks: dict = {}               # kraken symbol -> last price
        self.book_ts: dict = {}             # base asset -> fetch time
        self.daily_candles: dict = {}       # base asset -> daily candles
        self.margin_level_pct: float = 0.0
        self._pos_realized: dict = {}       # position_id -> cumulative net PnL
        self._cycle = 0
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
        position_id = str(uuid.uuid4())
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
                     f"@ {plan.price:.2f} [{plan.style}] "
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

    def _equity(self) -> float:
        return self.state.total_equity(self.marks) if self.marks \
            else self.state.total_equity()

    def _adv_usd(self, asset: str, price: float) -> float:
        """Conservative ADV estimate for the impact model.

        Venue 24h volume units differ across feeds, so this normalizes to
        USD if the number looks like base units, then haircuts to ~10% as
        a Kraken-share proxy and floors at $1M. Impact is a secondary
        term at this ticket size; conservatism is the point.
        """
        v = float((self.view.get(asset) or {}).get("volume_24h") or 0.0)
        if v <= 0:
            return 1e6
        usd = v * price if v * price < 1e13 and v < 1e8 else v
        return max(usd * 0.10, 1e6)

    def _stop_price_for(self, direction: str, entry: float, asset: str) -> float:
        vol_state = self.vol.state(asset)
        macro_state = self.macro.state(asset)
        stop_pct = max(self.base_stop_pct,
                       self.stop_vol_mult * vol_state.sigma_bar_pct)
        stop_pct *= macro_state.playbook.get("stop_mult", 1.0)
        stop_pct *= self.monitor.stop_widen
        return entry * (1 - stop_pct / 100.0) if direction == "long" \
            else entry * (1 + stop_pct / 100.0)

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
                self.postmortem.note_fill(position_id, event.fill_price)
                if not pos.is_hedge and "features" in order.meta:
                    self.history.log_entry(position_id, self._asset_of(pos.symbol),
                                        pos.direction, order.meta["features"])
                log.info(f"OPEN {pos.direction} {pos.size:.6f} {pos.symbol} "
                        f"@ {pos.entry_price:.2f} (p={pos.confidence:.2f}, "
                        f"hedge={pos.is_hedge})")
            else:
                total = pos.size + event.fill_size
                pos.entry_price = (pos.entry_price * pos.size +
                                   event.fill_price * event.fill_size) / total
                pos.size = total
                pos.original_size = max(pos.original_size, total)
            pos.fees_paid_usd += order.fees_usd - order.meta.get("_fees_seen", 0.0)
            if order.meta.get("algo_parent"):
                self.algo.note_fill(order.meta["algo_parent"],
                                    event.fill_size, event.fill_price)
            order.meta["_fees_seen"] = order.fees_usd
            self.state.record_fees(order.fees_usd - order.meta.get("_fees_booked", 0.0))
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
            net = gross - fee_delta
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
                self._pos_realized.get(pos.position_id, 0.0) + net
            log.info(f"CLOSE {event.fill_size:.6f} {pos.symbol} @ "
                    f"{event.fill_price:.2f} net ${net:+,.2f} "
                    f"(remaining {pos.size:.6f})")
            if pos.size <= pos.original_size * 1e-4 or pos.size <= EPS:
                total_net = self._pos_realized.pop(pos.position_id, net)
                self._finalize_position(pos, total_net, now)
                log.info(f"FLAT {pos.symbol} position {pos.position_id[:8]}: "
                        f"total net ${total_net:+,.2f}")

    def _submit_exit(self, pos: Position, close_pct: float, reason: str,
                 tier_fired: int = 0, now: Optional[float] = None):
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
        if any(o.position_id == pos.position_id
            for o in self.orders.open_orders() if o.purpose == "exit"):
            return                      # one live exit per position
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
        if pos.direction == "long":
            touch = bids[0][0] if bids else mark
            price = touch * (1 - slip_pct / 100.0)
            side = "sell"
        else:
            touch = asks[0][0] if asks else mark
            price = touch * (1 + slip_pct / 100.0)
            side = "buy"
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
            position_id=pos.position_id, close_pct=close_pct, post_only=False,
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
        # tick quarantine so one anomalous print can't fire every stop
        for asset, symbol in self.symbol_map.items():
            pair = self.kraken.kraken_pair(symbol)
            px = self.kraken.get_ticker_price(pair)
            if px:
                mark, stop_ok = self.watchdog.filter_mark(asset, px)
                self.marks[symbol] = mark
                self._stop_ok[asset] = stop_ok
            book = self.kraken.get_order_book(pair)
            if book:
                self.kraken_books[asset] = book
                self.book_ts[asset] = now
                self.thales.observe_fast(asset, book,
                                         self.marks.get(symbol, 0.0), now)

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

        if self.capital.hard_stop_triggered(self.state):
            if not self._halted:
                log.critical("HARD STOP drawdown breached - flattening, no new risk")
                self._halted = True
            for pos in self.state.open_positions():
                self._submit_exit(pos, 100.0, "hard stop", now=now)
            return

        macro_states = {a: self.macro.state(a) for a in self.symbol_map}

        # postmortem plumbing: mark trails + finalize elapsed observations
        self.postmortem.record_marks(self.marks, now)
        self.risk_protocols.observe(equity, self.marks, now)
        for cause, thesis in self.postmortem.poll(now):
            self.monitor.record_close(thesis.p_win,
                                    int(thesis.realized_net_usd > 0),
                                    thesis.model_scored, cause)

        for pos in list(self.state.open_positions()):
            symbol = pos.symbol
            px = self.marks.get(symbol)
            if not px:
                continue
            asset = self._asset_of(symbol)

            # 1) hard protective stop (v2: enforced every cycle).
            # A quarantined tick (single anomalous print) holds stop
            # evaluation for exactly one cycle; confirmation fires it.
            if pos.stop_price and self._stop_ok.get(asset, True) and (
                    (pos.direction == "long" and px <= pos.stop_price) or
                    (pos.direction == "short" and px >= pos.stop_price)):
                self._stop_hit[pos.position_id] = True
                self._submit_exit(pos, 100.0, f"stop {pos.stop_price:.2f} hit",
                                  now=now)
                continue

            # 2) profit tiers, scaled by regime + inventory pressure
            if not pos.is_hedge:
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
                                    tier_fired=action.tier_fired, now=now)

        # 3) inventory derisk (hard caps, stale losers)
        for act in self.inventory.derisk_actions(self.state, self.marks, equity,
                                                macro_states, now):
            pos = self.state.get_position(act.position_id)
            if pos:
                self._submit_exit(pos, act.close_pct, act.reason, now=now)

        # 4) hedging
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

    # ------------------------------------------------------------------
    # SLOW cycle - data refresh + entry pipeline
    # ------------------------------------------------------------------
    def _exploration_active(self, now: float) -> bool:
        """True only when it is safe and useful to take a paper exploration
        trade. HARD INVARIANT: dry_run only - exploration must never influence
        a live order. Off once enough training rows have accrued (the model
        can then be trusted to gate on its own)."""
        if not self.dry_run:
            return False                        # never in live - hard-gated
        if not self.explore_enabled:
            return False
        if self.history.row_count() >= self.explore_until_rows:
            return False                        # enough data: trust the model
        return self._explore_rng.random() < self.explore_epsilon

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
            if v.get("candles"):
                closes[asset] = float(v["candles"][-1]["close"])
        if closes:
            self.corr.update_intraday(closes)

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

        if self._halted:
            return

        equity = self._equity()
        if equity <= EPS or not self.capital.can_open_new_position(self.state):
            return

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

        if not self.entries_enabled:
            return
        if self.watchdog.state.entries_blocked:
            log.info(f"watchdog blocking entries: "
                     f"{self.watchdog.state.reasons}")
            return
        if abs(self._equity_drift_pct) > self.max_equity_drift_pct:
            log.warning(f"equity drift {self._equity_drift_pct:+.2f}% vs "
                        f"venue truth - entries blocked until reconciled")
            return

        for asset, v in self.view.items():
            if asset not in self.symbol_map:
                continue
            symbol = self.symbol_map[asset]
            if not self._live_order_allowed("entry"):
                break
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
            explored = False
            if self._exploration_active(now):
                explored = True
                p_win = max(p_win, self.explore_p_win)
                explore_scale = self.explore_size_scale
                get_audit().log("exploration", Code.ML_EXPLORATION,
                                f"paper exploration entry {asset} "
                                f"{signal.direction}",
                                {"model_p": round(model_p, 3),
                                 "sized_p": round(p_win, 3),
                                 "rows": self.history.row_count()})
                log.info("[%s] EXPLORATION paper entry: model p=%.2f -> sizing "
                         "p=%.2f, size x%.2f (learning; %d history rows)",
                         asset, model_p, p_win, explore_scale,
                         self.history.row_count())

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

            lev_decision = self.lev_gov.decide(
                self.state, self.marks, equity, vol_state.sigma_annual_pct,
                macro_state.playbook.get("leverage_cap", 1.0),
                self.margin_level_pct)

            sized = self.sizer.size(
                asset, signal.direction,
                self.marks.get(symbol) or fv_state.kraken_mid or 0.0,
                p_win, equity, self.state, macro_state, vol_state, liq_state,
                verdict.risk_multiplier, self.inventory, lev_decision,
                self.marks, now,
                risk_scale=self.monitor.kelly_mult * explore_scale,
                symbol=symbol)
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
                extra_edge_ratio=self.monitor.edge_ratio_bump)
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
                model_scored=self.monitor.use_model and self.meta.trained))
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
                    "post_only": plan.post_only}
                self._submit_algo_child(parent, now)   # first slice now
                log.info(
                    f"ENTRY-ALGO {signal.direction} {symbol} "
                    f"[{parent.algo}]: ${notional_usd:,.0f} sliced over "
                    f"{self.algo.max_children} children | p={p_win:.2f}")
                continue
            order = self.orders.submit(
                asset=asset, symbol=symbol,
                pair=self.kraken.kraken_pair(symbol), side=side,
                price=entry_price, size=decision.size_units, purpose="entry",
                position_id=position_id, post_only=plan.post_only,
                leverage=lev_decision.allowed_leverage,
                ref_price=self.marks.get(symbol)
                    or fv_state.fair_value or entry_price,
                equity=equity,
                book=self.kraken_books.get(asset) or {},
                sigma_bar_pct=vol_state.sigma_bar_pct,
                meta={"p_win": p_win, "edge_bps": decision.est_edge_bps,
                    "features": feats},
            )
            if order:
                self.sizer.note_entry(asset, now)
                log.info(
                    f"ENTRY {signal.direction} {symbol} [{plan.style}]: ${sized.usd:,.0f} "
                    f"({decision.size_units:.6f}) @ {entry_price:.2f} | "
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
        return {"fear_greed": web.fear_greed,
                "dominance_delta": web.dominance_delta,
                "equity_risk_z": risk.risk_z,
                "ts": now,
                "imbalance_delta": delta,
                "other_ret_6": other_ret6,
                "depth_ratio": self.liq.state(asset).depth_ratio}

    # ------------------------------------------------------------------
    # HOURLY cycle - macro regime + turbulence
    # ------------------------------------------------------------------
    def hourly_cycle(self, now: float):
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

    def _maybe_auto_retrain(self):
        """Self-improvement loop: when the monitor requests a retrain (level
        2, or the flag file exists) and enough NEW labeled rows have accrued,
        retrain in-process on live+candidate history. The challenger only
        deploys if its out-of-fold Brier beats the champion's - the bot
        never swaps in a worse model just to feel busy."""
        want = self.monitor.level >= 2 or self.monitor.flag_path.exists()
        if not want:
            return
        rows = self.history.row_count()
        if rows - self._rows_at_last_train < self.monitor.retrain_min_new_rows \
                or rows < self.monitor.retrain_min_rows:
            return
        try:
            from ml.walkforward import evaluate_and_select
            from ml.models import save_model
            from ml.calibration import (IsotonicCalibrator, brier_score,
                                        feature_deciles)
            sw_cfg = self.config.get("ml", {}).get("sample_weights", {})
            X, y, w = self.history.load_training_data(
                half_life_days=float(sw_cfg.get("half_life_days", 30)),
                candidate_weight=float(sw_cfg.get("candidate_weight", 0.4)))
            if len(X) < 60 or y.sum() < 10 or (len(y) - y.sum()) < 10:
                return
            log.warning(f"auto-retrain: {len(X)} rows "
                        f"({rows - self._rows_at_last_train} new)")
            results = evaluate_and_select(
                X, y, sample_weight=w, feature_names=FEATURE_NAMES,
                ensemble_k=int(self.config.get('ml', {})
                            .get('ensemble_seeds', 3)))
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
            challenger_brier = brier_score(sel["oof_y"], oof_cal) \
                if len(oof_cal) else 0.25
            self._rows_at_last_train = rows
            if not self.monitor.should_deploy(challenger_brier):
                return
            from ml.registry import sha256_array
            save_model(results["model"], self.meta.model_path,
                    extra={"calibration": cal.to_dict(),
                            "oof_brier": challenger_brier,
                            "feature_deciles": feature_deciles(X),
                            "importance": results.get("importance", []),
                            "rows": int(len(X)),
                            "class_balance": round(float(y.mean()), 3),
                            "train_data_sha": sha256_array(X)})
            self.meta.reload()
            self.monitor.note_deployed(challenger_brier)
            log.warning(f"auto-retrain DEPLOYED {results['selected']} "
                        f"(oof brier {challenger_brier:.4f})")
        except Exception:
            log.exception("auto-retrain failed - keeping current model")

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
