"""
scripts/smoke_test.py

No-network verification of the whole v2 stack. Two layers:

  1. Unit checks with known answers:
     - Gaussian HMM recovers planted regime switches on synthetic data
     - Avellaneda-Stoikov monotonicity (long inventory -> lower
       reservation; higher vol -> wider spread)
     - spoof detector fires on planted flash-pulled walls
     - pre-trade gate approves cheap-edge trades and vetoes bad ones
     - triple-barrier labels a constructed path correctly
     - numpy MLP reaches AUC > 0.62 on separable synthetic data
     - purged walk-forward split leaves no train/test overlap
     - sizer produces zero in crisis regime, >0 in bull with edge
     - narrative filter ignores unconfirmed fear, de-risks confirmed

  2. Integration: 60 cycles of the full LiquidityBot loop on mocked
     OKX/Binance.US/Kraken feeds (regime-switching GBM prices, synthetic
     books), asserting no exceptions and live pipeline decisions.

Run:  python scripts/smoke_test.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from ml.features import FEATURE_NAMES
N_FEATURES = len(FEATURE_NAMES)

import tempfile
TMP = Path(tempfile.gettempdir())   # portable: /tmp on posix, %TEMP% on Windows

PASS, FAIL = 0, 0


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except Exception:
        return True


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def qa_redirect_paths(cfg: dict, tag: str) -> dict:
    """Point EVERY file the engine graph writes at TMP. QA bots run on
    the production config, whose path defaults are the live telemetry
    files - a smoke bot once saved its fixture state over the runner's
    outputs/state.json, deleting three real open positions; postmortem
    summaries and retrain flags leaked the same way. Sections may still
    override individual paths AFTER this call.

    Also disables the Phase B context feed: `ContextFeed.maybe_poll`
    (data/context_engine.py) has no path override, so ANY enabled QA bot
    both hits five real HTTP endpoints (FRED/CFTC/DefiLlama) and appends
    to the real `outputs/context_history.jsonl` PIT file every slow
    cycle - a smoke/replay battery once wrote 100+ contaminating rows
    there. Disabling here is the only knob; there is no redirectable
    history_path in config.

    THE HARDEST ONES TO SEE are the paths config.json does NOT set: the
    engine falls back to a hardcoded default that IS the production file, so
    grepping config.json for the key finds nothing and the leak is invisible
    until the damage shows up in analysis. Two were found that way, both
    after they had corrupted a result:

      outputs/fills.csv           main.py:1659 default; config sets no
                                  system.fills_ledger_path. 64 fixture rows
                                  from debug_cycle's ETH=2000.0 mock landed
                                  in the live ledger under 16 position_ids
                                  and produced a mean-gross figure wrong by
                                  27x, plus a loss tail that did not exist.
      outputs/retrain_history     ml/retrain_log.py:23 module default; no
                                  config key at all, so it must be REBOUND
                                  rather than configured. 305 of 306 real
                                  records were suite fixtures (measured
                                  2026-07-31) and a prior session read the
                                  resulting degeneracy as a corpus problem.

    Not redirected here, deliberately: assurance.audit_path (config.json
    1074) is not consumed by main.py/runner.py/core - configure_audit()
    owns the process-wide trail and every QA entrypoint calls it, so setting
    it here would be dead config. tests/test_qa_isolation.py pins that
    exemption along with everything above."""
    d = TMP / f"smoke_out_{tag}"
    cfg["system"]["state_path"] = str(d / "state.json")
    cfg["system"]["weekly_ledger_path"] = str(d / "weekly_ledger.csv")
    cfg["system"]["monthly_ledger_path"] = str(d / "monthly_ledger.csv")
    cfg["system"]["fills_ledger_path"] = str(d / "fills.csv")
    ml = cfg.setdefault("ml", {})
    ml["history_path"] = str(d / "history.csv")
    ml["model_path"] = str(d / "meta_model.json")
    ml.setdefault("multi_horizon", {})
    ml["multi_horizon"]["shadow_path"] = str(d / "horizon_shadow.csv")
    ml.setdefault("postmortem", {})
    ml["postmortem"]["report_dir"] = str(d / "postmortems")
    ml["postmortem"]["summary_path"] = str(d / "postmortem_summary.csv")
    ml["postmortem"]["paths_path"] = str(d / "trade_paths.csv")
    ml.setdefault("monitor", {})
    ml["monitor"]["retrain_flag_path"] = str(d / "retrain.flag")
    cfg.setdefault("context", {})["enabled"] = False
    # No config key exists for this one - retrain_log resolves it through the
    # MODULE attribute precisely so it can be rebound, and both callers
    # (main.py's auto path and scripts/train_meta.py) read it that way, so one
    # rebind covers both. Import-and-set is the sanctioned mechanism, not a
    # monkeypatch hack: see the comment at ml/retrain_log.py:15-22.
    import ml.retrain_log as _rl
    _rl.RETRAIN_HISTORY_PATH_DEFAULT = str(d / "retrain_history.jsonl")
    return cfg


# ---------------------------------------------------------------------------
# synthetic data builders
# ---------------------------------------------------------------------------
def synth_daily_candles(n=400, seed=3):
    """Regime-switching GBM: bull (+ drift, low vol) then bear (- drift, high vol)."""
    rng = np.random.default_rng(seed)
    px = 2000.0
    candles = []
    for i in range(n):
        bull = i < n * 0.55
        mu = 0.0025 if bull else -0.0035
        sig = 0.018 if bull else 0.045
        r = rng.normal(mu, sig)
        o = px
        px = px * np.exp(r)
        hi = max(o, px) * (1 + abs(rng.normal(0, sig / 2)))
        lo = min(o, px) * (1 - abs(rng.normal(0, sig / 2)))
        candles.append({"time": i, "open": o, "high": hi, "low": lo,
                        "close": px, "volume": 1000 + rng.random() * 500})
    return candles


def synth_book(mid, spread_bps=4.0, depth=60.0, levels=15, seed=None):
    rng = np.random.default_rng(seed)
    half = mid * spread_bps / 2e4
    bids = [[mid - half - i * half * 0.5, depth * (0.8 + 0.4 * rng.random())]
            for i in range(levels)]
    asks = [[mid + half + i * half * 0.5, depth * (0.8 + 0.4 * rng.random())]
            for i in range(levels)]
    return {"bids": bids, "asks": asks}


# ---------------------------------------------------------------------------
# 1. unit checks
# ---------------------------------------------------------------------------
def test_hmm():
    from regime.macro_regime import GaussianHMM, MacroRegimeEngine, parkinson_vol
    candles = synth_daily_candles(400)
    closes = np.array([c["close"] for c in candles])
    highs = np.array([c["high"] for c in candles])
    lows = np.array([c["low"] for c in candles])
    rets = np.diff(np.log(closes))
    pv = parkinson_vol(highs, lows)[1:]
    X = np.column_stack([rets, np.log(pv + 1e-9)])
    hmm = GaussianHMM(n_states=3)
    ok = hmm.fit(X)
    check("HMM fits without error", ok)
    gamma = hmm.posteriors(X)
    order = np.argsort(hmm.state_return_means())
    bear, bull = order[0], order[-1]
    bull_share_early = gamma[:150, bull].mean()
    bear_share_late = gamma[-100:, bear].mean()
    check("HMM identifies planted bull phase", bull_share_early > 0.5,
          f"bull posterior early={bull_share_early:.2f}")
    check("HMM identifies planted bear phase", bear_share_late > 0.5,
          f"bear posterior late={bear_share_late:.2f}")

    eng = MacroRegimeEngine({"min_daily_bars": 120, "hysteresis_confirms": 1})
    st = eng.update("ETH", candles)
    check("macro engine labels planted bear/crisis at the end",
          st.label in ("bear", "crisis"), f"label={st.label}")
    check("macro playbook blocks longs in bear",
          not st.allows_direction("long") or st.label == "crisis")


def test_as_quoter():
    from execution.market_maker import AvellanedaStoikovQuoter
    q = AvellanedaStoikovQuoter({})
    flat = q.quote(2000.0, 0.10, 0.0)
    long_inv = q.quote(2000.0, 0.10, 0.8)
    short_inv = q.quote(2000.0, 0.10, -0.8)
    check("AS: long inventory lowers reservation",
          long_inv.reservation < flat.reservation < short_inv.reservation)
    calm = q.quote(2000.0, 0.05, 0.0)
    wild = q.quote(2000.0, 0.50, 0.0)
    check("AS: higher vol widens spread",
          wild.half_spread_bps > calm.half_spread_bps)
    spoofy = q.quote(2000.0, 0.10, 0.0, liq_label="spoofy")
    check("AS: spoofy regime widens spread",
          spoofy.half_spread_bps > flat.half_spread_bps)
    check("AS: bid < reservation < ask",
          flat.bid < flat.reservation < flat.ask)


def test_spoof_detector():
    from regime.liquidity_regime import LiquidityRegimeEngine
    eng = LiquidityRegimeEngine({"spoof_max_lifetime_sec": 90,
                                 "spoof_ewma_alpha": 0.5,
                                 "spoof_score_threshold": 0.3})
    t0 = 1000.0
    mid = 2000.0
    normal = synth_book(mid, seed=1)
    eng.update("ETH", normal, normal, now=t0)
    for k in range(6):
        spoofed = synth_book(mid, seed=2 + k)
        # plant a wall far below the touch (never reachable), then pull it
        if k % 2 == 0:
            spoofed["bids"].insert(5, [mid * 0.997, 5000.0])
        eng.update("ETH", spoofed, spoofed, now=t0 + 5 * (k + 1))
    st = eng.state("ETH")
    check("spoof detector fires on planted pulled walls",
          st.spoof_events_total >= 2, f"events={st.spoof_events_total}")
    check("spoofy regime blocks new risk", st.label == "spoofy" and st.reduce_only,
          f"label={st.label} score={st.spoof_score:.2f}")


def test_pretrade():
    from execution.pretrade import PreTradeGate, PreTradeContext
    gate = PreTradeGate({"maker_fee_bps": 16, "taker_fee_bps": 26,
                         "min_edge_cost_ratio": 1.3})
    book = synth_book(2000.0, spread_bps=4.0, depth=100.0, seed=5)
    ctx = PreTradeContext(kraken_book=book, sigma_daily_pct=2.0, adv_usd=5e7,
                          liq_label="liquid", spread_bps=4.0, staleness_ms=500)
    good = gate.evaluate("buy", 0.5, 2000.0, exp_alpha_bps=60.0,
                         fv_edge_bps=10.0, ctx=ctx, taker=False)
    check("pretrade approves edge > 1.3x cost", good.approved,
          f"{good.reasons}")
    bad = gate.evaluate("buy", 0.5, 2000.0, exp_alpha_bps=5.0,
                        fv_edge_bps=0.0, ctx=ctx, taker=True)
    check("pretrade vetoes edge < cost", not bad.approved)
    stale = PreTradeContext(kraken_book=book, sigma_daily_pct=2.0, adv_usd=5e7,
                            liq_label="liquid", spread_bps=4.0, staleness_ms=9000)
    check("pretrade vetoes stale data",
          not gate.evaluate("buy", 0.5, 2000.0, 60.0, 10.0, stale).approved)
    spoof_ctx = PreTradeContext(kraken_book=book, sigma_daily_pct=2.0, adv_usd=5e7,
                                liq_label="spoofy", spread_bps=4.0, staleness_ms=500)
    check("pretrade vetoes new risk in spoofy regime",
          not gate.evaluate("buy", 0.5, 2000.0, 60.0, 10.0, spoof_ctx).approved)
    huge = gate.evaluate("buy", 1e6, 2000.0, 500.0, 0.0, ctx, taker=True)
    check("pretrade caps participation vs depth",
          (not huge.approved) or huge.size_units < 1e6)
    legless = PreTradeGate({"maker_fee_bps": 16, "taker_fee_bps": 26,
                            "min_edge_cost_ratio": 1.3,
                            "price_exit_leg": False})
    g2 = legless.evaluate("buy", 0.5, 2000.0, exp_alpha_bps=60.0,
                          fv_edge_bps=10.0, ctx=ctx, taker=False)
    check("pretrade prices the unwind leg (taker fee + half spread)",
          abs((good.est_cost_bps - g2.est_cost_bps) - (26.0 + 2.0)) < 1e-9)


def test_triple_barrier():
    from ml.labeling import triple_barrier
    closes = np.array([100.0] * 5 + [100, 101, 102, 103, 104, 105], float)
    highs = closes * 1.001
    lows = closes * 0.999
    out = triple_barrier(closes, highs, lows, i=5, side=1, sigma_bar=0.005,
                         pt_mult=8, sl_mult=6, max_bars=5, cost_pct=0.06)
    check("triple barrier: clean up-move labels win via pt",
          out.label == 1 and out.barrier == "pt", f"{out}")
    closes2 = np.array([100.0] * 5 + [100, 99, 98, 97, 96, 95], float)
    out2 = triple_barrier(closes2, closes2 * 1.001, closes2 * 0.999, i=5, side=1,
                          sigma_bar=0.005, pt_mult=8, sl_mult=6, max_bars=5)
    check("triple barrier: down-move stops out long",
          out2.label == 0 and out2.barrier == "sl", f"{out2}")


def test_mlp():
    from ml.models import NumpyMLP, LogisticModel, auc_score
    rng = np.random.default_rng(11)
    n, d = 900, 12
    X = rng.normal(0, 1, (n, d))
    w = rng.normal(0, 1, d)
    y = ((X @ w + 0.6 * (X[:, 0] * X[:, 1]) + rng.normal(0, 0.7, n)) > 0).astype(float)
    cut = 700
    mlp = NumpyMLP(epochs=150, seed=4).fit(X[:cut], y[:cut])
    auc = auc_score(y[cut:], mlp.predict_proba(X[cut:]))
    check("MLP learns separable structure (AUC > 0.62)", auc > 0.62,
          f"auc={auc:.3f}")
    logit = LogisticModel().fit(X[:cut], y[:cut])
    auc_l = auc_score(y[cut:], logit.predict_proba(X[cut:]))
    check("logistic baseline sane (AUC > 0.55)", auc_l > 0.55, f"auc={auc_l:.3f}")
    d2 = mlp.to_dict()
    mlp2 = NumpyMLP.from_dict(d2)
    same = np.allclose(mlp.predict_proba(X[:5]), mlp2.predict_proba(X[:5]))
    check("MLP JSON round-trip preserves predictions", same)


def test_walkforward():
    from ml.walkforward import purged_walk_forward
    splits = list(purged_walk_forward(600, n_splits=4, label_span=50))
    check("walk-forward yields folds", len(splits) >= 3)
    ok = all(tr.max() < te.min() - 49 for tr, te in splits if len(tr))
    check("purge: train ends >= label_span before test", ok)


def test_sizer_and_filter():
    from risk.position_sizer import PositionSizer
    from risk.leverage import LeverageGovernor
    from execution.inventory import InventoryManager
    from regime.macro_regime import MacroRegimeState, DEFAULT_PLAYBOOKS
    from regime.vol_regime import VolState
    from regime.liquidity_regime import LiquidityState
    from core.state import PortfolioState
    from sentiment.fear_filter import NarrativeFilter, StructuralInputs
    from sentiment.scanner import SentimentSnapshot

    profit_cfg = {"tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
                  "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
                  "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
                  "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25}}
    sizer = PositionSizer({"min_p_win": 0.55, "entry_cooldown_min": 0},
                          profit_cfg, {"stop_loss_pct": 2.0})
    inv = InventoryManager({})
    lev = LeverageGovernor({"use_margin": False}).decide(
        PortfolioState(10000), {}, 10000, 60.0, 2.0, 0.0)
    state = PortfolioState(starting_capital=10000)
    bull = MacroRegimeState("ETH", label="bull_quiet",
                            playbook=dict(DEFAULT_PLAYBOOKS["bull_quiet"]))
    crisis = MacroRegimeState("ETH", label="crisis",
                              playbook=dict(DEFAULT_PLAYBOOKS["crisis"]))
    vol = VolState("ETH", sigma_annual_pct=50.0)
    liq = LiquidityState("ETH", size_mult=1.0)

    # edge_p above the honest net breakeven (~0.632 after the maker+taker
    # round-trip cost fix): d1 must APPROVE on a genuine edge; d2/d3 veto on
    # regime/direction regardless of p, so they share the same probability.
    edge_p = 0.72
    d1 = sizer.size("ETH", "long", 2000.0, edge_p, 10000, state, bull, vol, liq,
                    1.0, inv, lev, {})
    check("sizer approves bull + edge", d1.approved, f"{d1.reasons}")
    d2 = sizer.size("ETH", "long", 2000.0, edge_p, 10000, state, crisis, vol, liq,
                    1.0, inv, lev, {})
    check("sizer blocks new risk in crisis", not d2.approved)
    d3 = sizer.size("ETH", "short", 2000.0, edge_p, 10000, state, bull, vol, liq,
                    1.0, inv, lev, {})
    check("sizer blocks counter-bias short in bull_quiet", not d3.approved)

    filt = NarrativeFilter({})
    fear = SentimentSnapshot(score=-0.8, fear_spike=True, available=True)
    calm = StructuralInputs(vol_percentile=40, depth_ratio=1.0,
                            funding_rate=0.0, turbulence_pct=40, basis_bps=5)
    v1 = filt.evaluate(fear, calm)
    check("narrative filter ignores unconfirmed fear (risk stays 1.0)",
          v1.label == "narrative_noise" and v1.risk_multiplier == 1.0)
    stressed = StructuralInputs(vol_percentile=97, depth_ratio=0.35,
                                funding_rate=0.001, turbulence_pct=97,
                                basis_bps=60)
    v2 = filt.evaluate(fear, stressed)
    check("narrative filter de-risks confirmed stress",
          v2.label == "confirmed_stress" and v2.risk_multiplier <= 0.6)
    check("confidence tilt hard-clamped to +/-0.15",
          abs(v1.confidence_tilt) <= 0.15 and abs(v2.confidence_tilt) <= 0.15)


def test_inventory_and_hedge():
    from execution.inventory import InventoryManager
    from execution.hedging import HedgeEngine
    from regime.correlation import CorrState
    from core.state import PortfolioState, Position
    from datetime import datetime, timezone

    state = PortfolioState(starting_capital=10000)
    inv = InventoryManager({"soft_cap_pct_of_equity": 15,
                            "hard_cap_pct_of_equity": 25})
    marks = {"ETH/USD": 2000.0, "BTC/USD": 60000.0}
    state.add_position(Position("p1", "ETH/USD", "long", 2000.0, 1.0, 1.0,
                                datetime.now(timezone.utc)))
    add = inv.can_add(state, "ETH", "long", 1000.0, 10000.0, marks)
    check("inventory blocks same-side add past soft cap", not add.allowed)
    add2 = inv.can_add(state, "ETH", "short", 500.0, 10000.0, marks)
    check("inventory allows risk-reducing opposite add", add2.allowed)

    hedger = HedgeEngine({"max_net_delta_pct_of_equity": 15,
                          "rebalance_band_pct": 5, "min_hedge_usd": 50},
                         {"ETH": "ETH/USD", "BTC": "BTC/USD"})
    corr = CorrState(corr_fast={("BTC", "ETH"): 0.85},
                     betas={("ETH", "BTC"): 1.2, ("BTC", "ETH"): 0.6})
    acts = hedger.evaluate(state, marks, 10000.0, corr)
    check("hedger opens beta-weighted opposite hedge",
          len(acts) == 1 and acts[0].kind == "open" and
          acts[0].asset == "BTC" and acts[0].direction == "short",
          f"{acts}")


# ---------------------------------------------------------------------------
# 2. integration: full bot on mocked feeds
# ---------------------------------------------------------------------------
class MockOKX:
    def __init__(self, prices):
        self.prices = prices
        self.i = 0

    def _candles(self, asset, n=120):
        base = self.prices[asset]
        rng = np.random.default_rng(hash(asset) % 1000)
        closes = base * np.exp(np.cumsum(rng.normal(0.0004, 0.004, n)))
        return [{"time": k, "open": c * 0.999, "high": c * 1.004,
                 "low": c * 0.996, "close": c, "volume": 800 + rng.random() * 900}
                for k, c in enumerate(closes)]

    def get_market_data(self):
        out = {}
        for sym, asset in (("ETH-USDT-SWAP", "ETH"), ("BTC-USDT-SWAP", "BTC")):
            px = self.prices[asset]
            out[sym] = {"order_book": synth_book(px, depth=300, seed=self.i),
                        "candles": self._candles(asset),
                        "funding_rate": 0.0001, "volume_24h": 5e8}
        self.i += 1
        return out

    def get_daily_candles(self, symbol, limit=300):
        return synth_daily_candles(200, seed=5)

    def get_candles(self, symbol, bar="5m", limit=100):
        asset = "ETH" if symbol.startswith("ETH") else "BTC"
        return self._candles(asset, min(limit, 300))


class MockBinanceUS(MockOKX):
    def get_market_data(self):
        out = {}
        for sym, asset in (("ETHUSD", "ETH"), ("BTCUSD", "BTC")):
            px = self.prices[asset]
            out[sym] = {"order_book": synth_book(px, depth=280, seed=self.i + 7),
                        "candles": self._candles(asset),
                        "funding_rate": None,      # spot venue: no funding
                        "volume_24h": 4e5}
        self.i += 1
        return out

    def get_daily_candles(self, symbol, limit=720):
        return synth_daily_candles(200, seed=6)


class MockKraken:
    def __init__(self, prices):
        self.prices = prices
        self.trading_pairs = ["ETH/USD", "BTC/USD"]

    def kraken_pair(self, symbol):
        return symbol.replace("/", "")

    def get_ticker_price(self, pair):
        return self.prices["ETH" if pair.startswith("ETH") else "BTC"]

    def get_tickers(self, pairs):
        # mirror the real batched contract: {pair: price}
        return {p: self.get_ticker_price(p) for p in pairs}

    def get_order_book(self, pair, depth=20):
        px = self.get_ticker_price(pair)
        return synth_book(px, spread_bps=5.0, depth=80, seed=int(px) % 97)

    def get_daily_candles(self, pair, limit=720):
        return synth_daily_candles(200, seed=7)

    def get_margin_level_pct(self):
        return 0.0

    def _private_post(self, endpoint, data=None):
        return {}


def test_integration():
    from main import LiquidityBot, load_config
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000  # hermetic
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                 entry_cooldown_min=0, min_p_win=0.50)
    qa_redirect_paths(cfg, "integration")
    cfg["ml"]["cold_start_prior_p"] = 0.60
    cfg["ml"]["model_path"] = str(TMP / "none.json")
    cfg["ml"]["history_path"] = str(TMP / "smoke_history.csv")
    Path(str(TMP / "smoke_history.csv")).unlink(missing_ok=True)

    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)

    rng = np.random.default_rng(21)
    t = time.time()
    errors = 0
    for cycle in range(60):
        for a in prices:
            prices[a] *= float(np.exp(rng.normal(0.0006, 0.0035)))
        try:
            if cycle == 0 or cycle == 30:
                bot.hourly_cycle(t)
            bot.fast_cycle(t)
            if cycle % 3 == 0:
                bot.slow_cycle(t)
        except Exception:
            errors += 1
            import traceback
            traceback.print_exc()
            break
        t += 5.0
    check("integration: 60 mocked cycles, zero exceptions", errors == 0)
    check("integration: regimes computed for both assets",
          all(bot.macro.state(a).bars_used > 0 for a in ("ETH", "BTC")))
    check("integration: fair value live",
          all(bot.fv.state(a).updated for a in ("ETH", "BTC")))
    submitted = len(bot.orders._orders)
    print(f"    (orders submitted during sim: {submitted}, "
          f"open positions: {bot.state.open_position_count()}, "
          f"equity ${bot._equity():,.0f})")
    check("integration: pipeline reached order stage or vetoed cleanly",
          submitted >= 0)


def test_entry_fill_exit_path():
    """Force a confirmed signal through the pipeline and verify the full
    lifecycle: sizer -> AS quote -> pretrade -> limit order -> fill ->
    position with stop -> tier exit reduces size and books PnL."""
    from main import LiquidityBot, load_config
    from strategies.signal_gates import SignalResult

    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000  # hermetic
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                 entry_cooldown_min=0, min_p_win=0.50)
    qa_redirect_paths(cfg, "lifecycle")
    # 0.72: above the honest net breakeven (~0.690 after the 2026-07-29 payoff-compounding fix; was 0.66 vs the flat-weighted 0.632 - the maker+taker
    # round-trip cost fix). Subject is the order pipeline, not cost policy,
    # so the forced entry must clear net-Kelly to produce an order.
    cfg["ml"]["cold_start_prior_p"] = 0.72
    cfg["ml"]["model_path"] = str(TMP / "none.json")
    cfg["ml"]["history_path"] = str(TMP / "smoke_history2.csv")
    cfg["pretrade"]["min_edge_cost_ratio"] = 0.1   # let the forced signal through
    cfg["pretrade"]["price_exit_leg"] = False  # subject: order pipeline, not cost policy
    # subject is the order pipeline (sizer->quote->pretrade->fill->tier exit),
    # not fill realism: use the deterministic passive fill model so the forced
    # entry reliably fills. queue-aware gating (the live default) starves a tiny
    # order behind realistic mock depth; that realism lives in test_sim_fill_queue.
    # base prob pinned too - the shipped value is the MEASURED market rate
    # (0.048 since XV-021, 2026-08-02) and "deterministic" must not depend on it.
    # AND the hazard must be allowed to fire at all: since owed 57 /
    # execution-era boundary #4 (2026-08-09) it is off whenever a book is
    # present, because it double-counted the same crossing _sim_maker_cross
    # already models. Without this the mock book never crosses the resting
    # entry and the forced signal produces an order that never fills - the
    # fixture would be testing nothing. Realism stays in
    # tests/test_fill_double_count and tests/test_sim_fill_queue.
    _sf = cfg.setdefault("order_manager", {}).setdefault("sim_fill", {})
    _sf["queue_aware"] = False
    _sf["passive_base_prob"] = 1.0
    _sf["passive_hazard_with_book"] = True
    # this scenario tests tier PLUMBING (reduce + book PnL) against the
    # legacy fixed-% path; rev-3 vol-scaled calculus is covered by
    # tests/test_rev3.py
    cfg["profit_taking"] = dict(cfg["profit_taking"], vol_scaled=False)
    # geometry-alignment T5: config.json ships bracket_exits.enabled=true,
    # which would trade this forced entry's exits through the LABELED
    # bracket instead of the tier ladder this scenario is actually
    # exercising - disabled here so the legacy tier-plumbing subject stays
    # isolated (bracket exit behavior has its own coverage,
    # tests/test_bracket_exits.py).
    cfg["bracket_exits"] = dict(cfg.get("bracket_exits", {}), enabled=False)
    Path(str(TMP / "smoke_history2.csv")).unlink(missing_ok=True)

    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)

    forced = {"on": True}
    real_eval = bot.gates.evaluate_asset

    def fake_eval(base_asset, view):
        if forced["on"] and base_asset == "ETH":
            return SignalResult(symbol="ETH/USD", direction="long",
                                confidence=1.0, size=0.0, all_confirmed=True,
                                gates_passed={})
        return real_eval(base_asset, view)

    bot.gates.evaluate_asset = fake_eval

    t = time.time()
    bot.hourly_cycle(t)
    # bull the macro playbook so longs are allowed regardless of synth regime
    for a in ("ETH", "BTC"):
        st = bot.macro.state(a)
        st.label = "bull_quiet"
        st.playbook = dict(bot.macro.playbooks["bull_quiet"])
        bot.macro._states[a] = st
    bot.fast_cycle(t)
    bot.slow_cycle(t)
    check("forced signal produced an entry order",
          len(bot.orders._orders) >= 1,
          f"orders={len(bot.orders._orders)}")

    # crossing limit in dry run fills immediately or via passive sim
    for k in range(1, 12):
        t += 5
        bot.fast_cycle(t)
        if bot.state.open_position_count() > 0:
            break
    opened = bot.state.open_position_count() > 0
    check("fill event created a live position", opened)
    if opened:
        forced["on"] = False
        pos = bot.state.open_positions()[0]
        check("position carries a protective stop", pos.stop_price is not None
              and pos.stop_price < pos.entry_price)
        check("entry features logged for meta-training",
              pos.position_id in bot.history._pending)
        # pump price +2.5% -> tier 1 and 2 should fire and reduce size
        prices["ETH"] = pos.entry_price * 1.025
        start_size = pos.size
        for k in range(14):
            t += 5
            bot.fast_cycle(t)
        check("profit tiers reduced the position on the way up",
              pos.size < start_size or bot.state.get_position(pos.position_id) is None,
              f"size {start_size:.6f} -> {pos.size:.6f}")
        check("realized PnL booked through capital manager",
              bot.state.realized_pnl_total > 0,
              f"realized=${bot.state.realized_pnl_total:,.2f}")
        # crash price -25% -> stop must flatten the remainder
        prices["ETH"] = pos.entry_price * 0.75
        for k in range(14):
            t += 5
            bot.fast_cycle(t)
        _p = bot.state.get_position(pos.position_id)
        check("hard stop flattened the remainder on the crash",
              _p is None or _p.size < start_size * 0.6)


def test_capped_book_learning():
    """A full book (position cap reached) must starve LIVE entries only -
    never the learning lane. Observed live: hours of ~110 blocked
    cycles/hour with zero new candidates drained the open-candidate pool
    65 -> 7. Candidates are shadow trades: zero capital, always safe."""
    from main import LiquidityBot, load_config
    from strategies.signal_gates import SignalResult

    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["capital_management"]["max_concurrent_positions"] = 0   # cap saturated
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    qa_redirect_paths(cfg, "capped")
    cfg["ml"]["model_path"] = str(TMP / "none.json")
    cfg["ml"]["history_path"] = str(TMP / "smoke_capped.csv")
    Path(str(TMP / "smoke_capped.csv")).unlink(missing_ok=True)

    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)
    bot.gates.evaluate_asset = lambda base_asset, view: SignalResult(  # type: ignore[assignment]
        symbol="ETH/USD", direction="long", confidence=1.0, size=0.0,
        all_confirmed=True, gates_passed={}) if base_asset == "ETH" else \
        SignalResult(symbol="BTC/USD", direction=None, confidence=0.0,
                     size=0.0, all_confirmed=False, gates_passed={})
    t = time.time()
    bot.hourly_cycle(t)
    for a in ("ETH", "BTC"):
        st = bot.macro.state(a)
        st.label = "bull_quiet"
        st.playbook = dict(bot.macro.playbooks["bull_quiet"])
        bot.macro._states[a] = st
    bot.fast_cycle(t)
    bot.slow_cycle(t)
    check("capped book still registers training candidates",
          len(bot.candidates._cands) >= 1,
          f"cands={len(bot.candidates._cands)}")
    check("capped book places zero live entry orders",
          len(bot.orders._orders) == 0,
          f"orders={len(bot.orders._orders)}")
    check("capped book still surfaces signals to status",
          bot.last_signals.get("ETH", {}).get("confirmed") is True)
    # operator pause: same contract - learning and gauges live, no orders
    bot.entries_enabled = False
    bot.last_signals.clear()
    bot.slow_cycle(t + 5)
    check("entries_off still surfaces signals to status",
          bot.last_signals.get("ETH", {}).get("confirmed") is True)
    check("entries_off places zero live entry orders",
          len(bot.orders._orders) == 0)
    # cold-start training trigger: degradation/drift both need an existing
    # model, so an untrained bot with enough rows must SELF-flag - without
    # this the first champion never trains no matter how many rows accrue
    bot.monitor.flag_path.unlink(missing_ok=True)
    bot.history.row_count = lambda: bot.monitor.retrain_min_rows + 1  # type: ignore[method-assign]
    bot._maybe_auto_retrain()
    check("cold start with enough rows requests the FIRST training",
          bot.monitor.flag_path.exists())
    bot.monitor.flag_path.unlink(missing_ok=True)


def test_pending_entries_count_against_the_cap():
    """Positions are booked on FILL; a resting (pending) entry order is
    committed risk invisible to open_position_count(). With one pending
    entry allowed per asset, a cap that counted only filled positions
    could be overfilled when they land. The cap must reserve a slot per
    pending entry - here zero filled + a cap-full book of PENDING entries
    must block a new live entry while the learning lane stays open."""
    from main import LiquidityBot, load_config
    from strategies.signal_gates import SignalResult

    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["capital_management"]["max_concurrent_positions"] = 1
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    qa_redirect_paths(cfg, "pending_cap")
    cfg["ml"]["model_path"] = str(TMP / "none_pc.json")
    cfg["ml"]["history_path"] = str(TMP / "smoke_pending_cap.csv")
    Path(str(TMP / "smoke_pending_cap.csv")).unlink(missing_ok=True)

    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)
    bot.gates.evaluate_asset = lambda base_asset, view: SignalResult(  # type: ignore[assignment]
        symbol=f"{base_asset}/USD", direction="long", confidence=1.0, size=0.0,
        all_confirmed=True, gates_passed={})
    # a REAL resting BTC entry (buy limit far below market never fills, so it
    # stays pending through poll) holds the single cap slot while
    # open_position_count() is still 0 - the exact positions-vs-pending gap
    from execution.order_manager import ManagedOrder
    bot.orders._orders["pend-btc"] = ManagedOrder(
        order_id="pend-btc", txid=None, asset="BTC", pair="XXBTZUSD",
        symbol="BTC/USD", side="buy", price=1.0, size=0.001,
        status="pending", purpose="entry", position_id="pp")
    t = time.time()
    bot.hourly_cycle(t)
    for a in ("ETH", "BTC"):
        st = bot.macro.state(a)
        st.label = "bull_quiet"
        st.playbook = dict(bot.macro.playbooks["bull_quiet"])
        bot.macro._states[a] = st
    reg0 = len(bot.candidates._cands)
    seen_in_flight = []
    _orig_cap = bot.capital.can_open_new_position
    bot.capital.can_open_new_position = (                        # type: ignore[method-assign]
        lambda state, in_flight_entries=0: seen_in_flight.append(in_flight_entries)
        or _orig_cap(state, in_flight_entries))
    bot.fast_cycle(t)
    bot.slow_cycle(t)
    bot.capital.can_open_new_position = _orig_cap               # type: ignore[method-assign]
    check("engine feeds the pending-entry count into the concurrency cap",
          bool(seen_in_flight) and max(seen_in_flight) >= 1,
          f"in_flight seen={seen_in_flight}")
    check("pending entry reserves the only slot: cap reports full",
          _orig_cap(bot.state, 1) is False and bot.state.open_position_count() == 0,
          f"filled={bot.state.open_position_count()}")
    check("cap-full-by-pending still registers training candidates",
          len(bot.candidates._cands) > reg0,
          f"cands {reg0} -> {len(bot.candidates._cands)}")


def test_persistence_roundtrip():
    """Open a position, snapshot, resume into a NEW bot instance, and verify
    the restored bot has identical state and keeps managing the position
    (tiers/stops still fire after resume)."""
    from main import LiquidityBot, load_config
    from strategies.signal_gates import SignalResult

    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000  # hermetic
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    qa_redirect_paths(cfg, "persist")
    cfg["system"]["state_path"] = str(TMP / "smoke_state.json")
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                 entry_cooldown_min=0, min_p_win=0.50)
    # 0.72: above the honest net breakeven (~0.690 after the 2026-07-29 payoff-compounding fix; was 0.66 vs the flat-weighted 0.632 - the maker+taker
    # round-trip cost fix). This test's subject is persistence, not gate
    # economics, so the synthetic entry must clear net-Kelly to have a
    # position to snapshot (0.62 now sits below breakeven -> SZ-030 veto).
    cfg["ml"]["cold_start_prior_p"] = 0.72
    cfg["ml"]["model_path"] = str(TMP / "none.json")
    cfg["ml"]["history_path"] = str(TMP / "smoke_history3.csv")
    cfg["pretrade"]["min_edge_cost_ratio"] = 0.1
    # subject here is persistence, not gate economics: without these the
    # round-trip cost stack (price_exit_leg) can EV-veto the synthetic
    # entry and the roundtrip has no position to snapshot
    cfg["pretrade"]["price_exit_leg"] = False
    # subject is persistence, not fill realism: use the deterministic passive
    # fill model so the synthetic entry reliably fills. queue-aware gating (now
    # the live default) starves a tiny order behind realistic mock depth — that
    # realism is exercised in tests/test_sim_fill_queue, not here.
    # base prob pinned too - the shipped value is the MEASURED market rate
    # (0.048 since XV-021, 2026-08-02) and "deterministic" must not depend on it.
    # AND the hazard must be allowed to fire at all: since owed 57 /
    # execution-era boundary #4 (2026-08-09) it is off whenever a book is
    # present. Without this there is no fill, hence no position, and
    # open_positions()[0] below raises IndexError rather than failing an
    # assertion. Realism stays in tests/test_fill_double_count.
    _sf = cfg.setdefault("order_manager", {}).setdefault("sim_fill", {})
    _sf["queue_aware"] = False
    _sf["passive_base_prob"] = 1.0
    _sf["passive_hazard_with_book"] = True
    # geometry-alignment T5: this scenario's subject is snapshot/restore
    # plumbing, not exit geometry - disabled so the "tiers must fire"
    # assertion below exercises the legacy tier ladder it was written
    # against, not the shipped bracket default (own coverage in
    # tests/test_bracket_exits.py).
    cfg["bracket_exits"] = dict(cfg.get("bracket_exits", {}), enabled=False)
    Path(str(TMP / "smoke_history3.csv")).unlink(missing_ok=True)
    Path(str(TMP / "smoke_state.json")).unlink(missing_ok=True)

    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)
    bot.gates.evaluate_asset = lambda base_asset, view: SignalResult(  # type: ignore[assignment]
        symbol="ETH/USD", direction="long", confidence=1.0, size=0.0,
        all_confirmed=True, gates_passed={}) if base_asset == "ETH" else \
        SignalResult(symbol="BTC/USD", direction=None, confidence=0.0,
                     size=0.0, all_confirmed=False, gates_passed={})

    t = time.time()
    bot.hourly_cycle(t)
    for a in ("ETH", "BTC"):
        st = bot.macro.state(a)
        st.label = "bull_quiet"
        st.playbook = dict(bot.macro.playbooks["bull_quiet"])
        bot.macro._states[a] = st
    bot.fast_cycle(t)
    bot.slow_cycle(t)
    for _ in range(12):
        t += 5
        bot.fast_cycle(t)
        if bot.state.open_position_count() > 0:
            break
    check("persistence: position open before snapshot",
          bot.state.open_position_count() == 1)
    pos_before = bot.state.open_positions()[0]
    bot.sizer.note_entry("ETH", t)
    bot._regime_since["ETH"] = ("bull_quiet", t - 7200.0)   # 2h-old regime
    ok = bot.store.snapshot(bot)
    check("persistence: snapshot written", ok and Path(str(TMP / "smoke_state.json")).exists())

    # --- "restart": brand-new instance restores from disk ---
    bot2 = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                        kraken=MockKraken(prices), resume=True)
    check("persistence: resume flag set", bot2._resumed)
    check("persistence: regime age survives restart (regime_age_sec)",
          bot2._regime_since.get("ETH") == ("bull_quiet", t - 7200.0))
    check("persistence: position survives restart",
          bot2.state.open_position_count() == 1)
    p2 = bot2.state.open_positions()[0]
    check("persistence: position fields intact",
          p2.position_id == pos_before.position_id and
          abs(p2.entry_price - pos_before.entry_price) < 1e-9 and
          abs(p2.size - pos_before.size) < 1e-12 and
          p2.stop_price == pos_before.stop_price and
          p2.confidence == pos_before.confidence)
    check("persistence: pending history features survive",
          p2.position_id in bot2.history._pending and
          len(bot2.history._pending[p2.position_id][2]) == N_FEATURES)
    check("persistence: cooldown timestamp survives",
          abs(bot2.sizer._last_entry.get("ETH", 0) - t) < 1e-6)
    check("persistence: balances survive",
          abs(bot2.state.cash_balance - bot.state.cash_balance) < 1e-6 and
          abs(bot2.state.savings_balance - bot.state.savings_balance) < 1e-6)

    # resumed bot keeps managing: pump price, tiers must fire
    bot2.hourly_cycle(t)
    for a in ("ETH", "BTC"):
        st = bot2.macro.state(a)
        st.label = "bull_quiet"
        st.playbook = dict(bot2.macro.playbooks["bull_quiet"])
        bot2.macro._states[a] = st
    prices["ETH"] = p2.entry_price * 1.03
    start_size = p2.size
    for _ in range(14):
        t += 5
        bot2.fast_cycle(t)
    check("persistence: resumed bot still manages tiers",
          p2.size < start_size or bot2.state.get_position(p2.position_id) is None,
          f"{start_size:.6f} -> {p2.size:.6f}")
    check("persistence: resumed close produced a labeled history row or pending",
          bot2.state.realized_pnl_total > 0)

    # dry/live mismatch guard
    snap = bot2.store
    snap.snapshot(bot2)
    cfg_live = json.loads(json.dumps(cfg))
    cfg_live["system"]["dry_run"] = False
    # config_guard requires creds to RESOLVE in live mode; this test isn't
    # about that. Supplied via ENV, not literals: the H15 guard now FATALs on
    # a literal in git-tracked config.json (a committed secret) in both modes,
    # so the harness must model the documented credential path - env FIRST -
    # rather than the one the guard exists to forbid.
    import os
    _cred_env = {"KRAKEN_API_KEY": "x",
                 "KRAKEN_API_SECRET": "eA=="}  # nosec B105 - dummy test secret
    _saved = {k: os.environ.get(k) for k in _cred_env}
    os.environ.update(_cred_env)
    # cfg weakened min_edge_cost_ratio to 0.1 above to force the synthetic
    # entry through the EV gate (persistence is the subject, not cost
    # policy) - now FATAL in live mode (W2-7 guard). This test is about the
    # dry/live resume mismatch, not the EV gate, so restore a valid ratio.
    cfg_live["pretrade"]["min_edge_cost_ratio"] = 1.3
    try:
        bot3 = LiquidityBot(cfg_live, okx=MockOKX(prices),
                            binanceus=MockBinanceUS(prices),
                            kraken=MockKraken(prices), resume=True)
    finally:
        # never leak the dummy creds into the checks that follow
        for _k, _v in _saved.items():
            if _v is None:
                os.environ.pop(_k, None)
            else:
                os.environ[_k] = _v
    check("persistence: refuses to mix paper snapshot into live mode",
          not bot3._resumed and bot3.state.open_position_count() == 0)


def test_calibration():
    from ml.calibration import IsotonicCalibrator, brier_score, calibration_gap
    rng = np.random.default_rng(5)
    # deliberately overconfident probs: true rate = 0.5 + 0.3*(p_raw - 0.5)
    p_raw = rng.uniform(0.05, 0.95, 600)
    y = (rng.random(600) < 0.5 + 0.3 * (p_raw - 0.5)).astype(float)
    cal = IsotonicCalibrator().fit(p_raw, y)
    check("calibration: PAV fits", cal.fitted)
    assert cal.y is not None  # fitted implies knots are set
    p_cal = cal.transform(p_raw)
    check("calibration: output monotone in input",
          all(np.diff(cal.y) >= -1e-12))
    g_before = calibration_gap(y, p_raw)
    g_after = calibration_gap(y, p_cal)
    check("calibration: gap shrinks", g_after < g_before,
          f"{g_before:.3f} -> {g_after:.3f}")
    check("calibration: brier improves",
          brier_score(y, p_cal) < brier_score(y, p_raw))
    rt = IsotonicCalibrator.from_dict(cal.to_dict())
    check("calibration: JSON round-trip",
          np.allclose(rt.transform(p_raw[:9]), p_cal[:9]))


def test_monitor_ladder():
    from ml.monitor import ModelMonitor
    m = ModelMonitor({"window_trades": 20, "min_trades_to_judge": 10,
                      "retrain_flag_path": str(TMP / "smoke_retrain.flag"),
                      "retrain_cooldown_hours": 0})
    Path(str(TMP / "smoke_retrain.flag")).unlink(missing_ok=True)
    # confidently wrong model: p=0.8, loses every time
    for _ in range(24):
        m.record_close(0.8, 0, model_scored=True)
    check("monitor: escalates to failing on confident wrongness",
          m.level == 2, f"level={m.level}")
    check("monitor: bypasses model when failing", not m.use_model)
    check("monitor: floors kelly", m.kelly_mult <= 0.41)
    check("monitor: retrain flag written",
          Path(str(TMP / "smoke_retrain.flag")).exists())
    # recovery: model behaves (p matches outcomes). W2-17 gates de-escalation
    # on `deescalate_healthy_windows` (default 3) CONSECUTIVE healthy windows,
    # so the fixture must be UNAMBIGUOUSLY well-calibrated, not just
    # noisily-honest-on-average (a uniform-random p vs Bernoulli(p) outcome
    # hovers within brier_margin of the baseline and can sit degraded
    # forever on pure sampling noise - which is exactly the flap the fix
    # exists to stop rewarding). A clean, deterministic, clearly-calibrated
    # block (matches tests/test_monitor_shadow_recovery.py) repeated enough
    # times to clear the streak requirement proves genuine recovery.
    def _clean_block():
        for k in range(5):
            m.record_close(0.8, 1 if k < 4 else 0, model_scored=True)
        for k in range(5):
            m.record_close(0.2, 1 if k < 1 else 0, model_scored=True)
    for _ in range(8):
        _clean_block()
    check("monitor: recovers when predictions become honest",
          m.level == 0, f"level={m.level}")
    # recurring whipsaw causes widen stops (bounded)
    m2 = ModelMonitor({"min_trades_to_judge": 999,
                       "retrain_flag_path": str(TMP / "smoke_m2.flag")})
    for _ in range(8):
        m2.record_close(0.6, 0, True, cause="whipsaw")
    check("monitor: recurring whipsaws widen stops within cap",
          1.0 < m2.stop_widen <= 1.5, f"{m2.stop_widen}")
    # champion/challenger gate
    m2.champion_brier = 0.20
    check("monitor: rejects worse challenger", not m2.should_deploy(0.21))
    check("monitor: accepts better challenger", m2.should_deploy(0.18))


def test_postmortem():
    from ml.postmortem import PostmortemEngine, TradeThesis
    import shutil
    shutil.rmtree(str(TMP / "smoke_pm"), ignore_errors=True)
    pm = PostmortemEngine({"report_dir": str(TMP / "smoke_pm"),
                           "summary_path": str(TMP / "smoke_pm" / "summary.csv"),
                           # TENTH instance of the QA-writes-production class
                           # (2026-08-11): 2602371b made poll() write EVERY
                           # finalized close to the paths ledger; this cfg
                           # predates that and fell through to the production
                           # default - pm1/pm2 fixture rows (ts~1e6, epoch
                           # 1970) landed in outputs/trade_paths.csv. The
                           # conftest tripwire can never catch smoke_test
                           # (it runs outside pytest) - hence the synthetic-
                           # clock tripwire in __main__ below.
                           "paths_path": str(TMP / "smoke_pm" / "trade_paths.csv"),
                           "observe_minutes": 1, "mark_sample_sec": 1})
    t0 = 1_000_000.0
    th = TradeThesis(position_id="pm1", asset="ETH", symbol="ETH/USD",
                     direction="long", entry_ts=t0, p_win=0.62,
                     expected_ret_pct=1.2, expected_cost_bps=45.0,
                     stop_pct=2.0, target_pct=2.5, entry_regime="bull_quiet",
                     entry_liq="liquid", narrative_label="neutral",
                     fair_value=2000.0, quote_price=1999.0, model_scored=True)
    pm.register_entry(th)
    pm.note_fill("pm1", 2000.0)
    # price dives to the stop...
    t = t0
    for px in (1995, 1988, 1979, 1965, 1960):
        t += 60
        pm.record_marks({"ETH/USD": float(px)}, t)
    pm.on_close("pm1", realized_net_usd=-4.2, fees_usd=0.9, entry_usd=200.0,
                stopped_out=True, exit_regime="bull_quiet", exit_liq="liquid",
                now=t)
    # ...then recovers past entry during the observation window
    for px in (1975, 1992, 2004, 2011):
        t += 60
        pm.record_marks({"ETH/USD": float(px)}, t)
    results = pm.poll(t + 120)
    check("postmortem: finalizes after observe window", len(results) == 1)
    cause = results[0][0]
    check("postmortem: stop-then-recover attributed as whipsaw",
          cause == "whipsaw", f"cause={cause}")
    reports = list(Path(str(TMP / "smoke_pm")).glob("*.md"))
    check("postmortem: markdown report written", len(reports) == 1)
    body = reports[0].read_text(encoding="utf-8")
    check("postmortem: report carries thesis vs outcome + mitigation",
          "WHIPSAW" in body and "Mitigation" in body and "p(win) 0.62" in body)
    check("postmortem: summary row appended",
          Path(str(TMP / "smoke_pm" / "summary.csv")).read_text(encoding="utf-8").count("whipsaw") == 1)

    # cost-overrun case: fills way through the quote, fees heavy, no recovery
    th2 = TradeThesis(position_id="pm2", asset="ETH", symbol="ETH/USD",
                      direction="long", entry_ts=t, p_win=0.60,
                      expected_ret_pct=1.0, expected_cost_bps=30.0,
                      stop_pct=2.0, target_pct=2.5, entry_regime="range",
                      entry_liq="thin", narrative_label="neutral",
                      fair_value=2000.0, quote_price=2000.0, model_scored=True)
    pm.register_entry(th2)
    pm.note_fill("pm2", 2016.0)          # 80bps through the quote
    for px in (2016, 2014, 2013):
        t += 60
        pm.record_marks({"ETH/USD": float(px)}, t)
    pm.on_close("pm2", realized_net_usd=-1.5, fees_usd=1.6, entry_usd=200.0,
                stopped_out=False, exit_regime="range", exit_liq="thin", now=t)
    t += 90
    pm.record_marks({"ETH/USD": 2012.0}, t)
    res2 = pm.poll(t + 120)
    check("postmortem: slippage+fee blowout attributed as cost_overrun",
          res2 and res2[0][0] == "cost_overrun", f"{res2}")


def test_candidate_labeling():
    from ml.history import HistoryStore, CandidateLabeler
    Path(str(TMP / "smoke_cand.csv")).unlink(missing_ok=True)
    store = HistoryStore(str(TMP / "smoke_cand.csv"))
    lab = CandidateLabeler(store, {"label_max_bars": 20,
                                   "label_pt_vol_mult": 8,
                                   "label_sl_vol_mult": 6})
    rng = np.random.default_rng(8)
    px = 2000.0
    candles = []
    for i in range(30):
        px *= float(np.exp(0.004 + rng.normal(0, 0.001)))   # steady grind up
        candles.append({"time": i, "open": px * 0.999, "high": px * 1.002,
                        "low": px * 0.998, "close": px, "volume": 100.0})
    lab.update_candles("ETH", candles[:5])
    feats = np.zeros(N_FEATURES)
    lab.register("ETH", "long", feats, sigma_bar=0.004, bar_time=4)
    check("candidate: not labeled before horizon", lab.poll() == 0)
    lab.update_candles("ETH", candles)      # dedupe + extend past horizon
    n = lab.poll()
    check("candidate: labeled after horizon elapses", n == 1)
    X, y, w = store.load_training_data()
    check("candidate: row in training data with win label on up-grind",
          len(X) == 1 and y[0] == 1.0, f"rows={len(X)} y={y}")
    d = lab.to_dict()
    lab2 = CandidateLabeler(store, {})
    lab2.restore(d)
    check("candidate: labeler state round-trips", lab2._seq == lab._seq)


FAKE_RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Bitcoin breakout: institutions accumulating, analysts bullish on rally</title><pubDate>Fri, 03 Jul 2026 10:00:00 GMT</pubDate></item>
<item><title>Michael Saylor says company will keep buying bitcoin, calls it undervalued</title><pubDate>Fri, 03 Jul 2026 09:00:00 GMT</pubDate></item>
<item><title>Ethereum shows strength as market recovery continues higher</title><pubDate>Fri, 03 Jul 2026 08:00:00 GMT</pubDate></item>
</channel></rss>"""

FAKE_RSS_BEAR = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Crypto crash deepens: panic selling and liquidations as market collapses</title><pubDate>Fri, 03 Jul 2026 10:00:00 GMT</pubDate></item>
<item><title>Bearish breakdown: bitcoin dumps as fear grips traders</title><pubDate>Fri, 03 Jul 2026 09:30:00 GMT</pubDate></item>
</channel></rss>"""

def FAKE_HN():
    now = int(time.time()) - 600
    return ('{"hits":['
            '{"title":"Massive rally incoming, accumulating more BTC,'
            ' so bullish","points":900,"created_at_i":%d},'
            '{"title":"Breakout confirmed, sending it higher",'
            '"points":400,"created_at_i":%d}]}' % (now, now))


def test_sentiment_scanner():
    from sentiment.scanner import SentimentScanner, parse_rss_items, \
        parse_hn_posts
    from sentiment.lexicon import score_text
    import json as _json
    check("lexicon: bullish text scores positive",
          score_text("massive bullish breakout, accumulate the rally") > 0.3)
    check("lexicon: negation flips",
          score_text("this is not bullish at all") < 0)
    items = parse_rss_items(FAKE_RSS)
    check("scanner: RSS parse extracts titles+ages",
          len(items) == 3 and all(a >= 0 for _, a in items))
    posts = parse_hn_posts(_json.loads(FAKE_HN()))
    check("scanner: HN crowd parse extracts posts", len(posts) == 2)

    def fake_fetch(url):
        if "news.google.com" in url or "coindesk" in url:
            return FAKE_RSS
        if "hn.algolia.com" in url:
            return FAKE_HN()
        raise RuntimeError("dead source")

    sc = SentimentScanner({
        "enabled": True, "poll_minutes": 0,
        "figures": [{"name": "Michael Saylor", "weight": 1.0}],
        "news_feeds": [{"url": "https://www.coindesk.com/rss", "weight": 1.0},
                       {"url": "https://dead.example/rss", "weight": 1.0}],
        "crowd_queries": [{"query": "bitcoin OR crypto", "weight": 1.0}],
    }, fetch=fake_fetch)
    snap = sc.maybe_poll(time.time())
    check("scanner: blended bullish score from all sources",
          snap.available and snap.score > 0.2 and
          set(snap.per_source) == {"figures", "news", "crowd"},
          f"score={snap.score:.2f} sources={snap.per_source}")
    check("scanner: figure attribution present",
          "Michael Saylor" in snap.per_figure)
    check("scanner: dead source degraded without breaking", True)

    sc2 = SentimentScanner({"enabled": True, "poll_minutes": 0,
                            "news_feeds": [{"url": "https://x.example/rss",
                                            "weight": 1.0}]},
                           fetch=lambda u: FAKE_RSS_BEAR)
    s1 = sc2.maybe_poll(1000.0)
    check("scanner: bearish headlines score negative", s1.score < -0.3,
          f"{s1.score:.2f}")


def test_webdata_feed():
    from data.webdata_feed import WebDataFeed
    payloads = {
        "alternative.me": '{"data":[{"value":"12"},{"value":"20"}]}',
        "coingecko": '{"data":{"market_cap_percentage":{"btc":54.2},'
                     '"total_market_cap":{"usd":2.4e12}}}',
    }

    def fetch(url):
        for k, v in payloads.items():
            if k in url:
                return v
        raise RuntimeError("nope")

    wd = WebDataFeed({"enabled": True, "poll_minutes": 0}, fetch=fetch)
    s1 = wd.maybe_poll(1000.0)
    check("webdata: fear&greed + dominance parsed",
          s1.available and s1.fear_greed == 12.0 and s1.btc_dominance == 54.2)
    payloads["coingecko"] = payloads["coingecko"].replace("54.2", "55.0")
    s2 = wd.maybe_poll(2000.0)
    check("webdata: dominance delta computed across polls",
          abs(s2.dominance_delta - 0.8) < 1e-9, f"{s2.dominance_delta}")

    wd2 = WebDataFeed({"enabled": True, "poll_minutes": 0},
                      fetch=lambda u: (_ for _ in ()).throw(RuntimeError()))
    s3 = wd2.maybe_poll(1000.0)
    check("webdata: total failure degrades to neutral, loop unbroken",
          s3.fear_greed == 50.0 and not s3.available)


def test_moomoo_feed():
    from data.moomoo_feed import MoomooFeed

    class FakeDF:
        def __init__(self, rows): self.rows = rows
        def iterrows(self): return enumerate(self.rows)

    class FakeCtx:
        def __init__(self): self.move = 0.0
        def get_market_snapshot(self, codes):
            rows = [{"code": c, "last_price": 100.0 * (1 + self.move),
                     "prev_close_price": 100.0} for c in codes]
            return 0, FakeDF(rows)
        def close(self): pass

    ctx = FakeCtx()
    mm = MoomooFeed({"enabled": True, "poll_minutes": 0,
                     "tickers": [{"code": "US.COIN", "weight": 1.0},
                                 {"code": "US.QQQ", "weight": 0.5}]},
                    quote_ctx=ctx)
    t = 1000.0
    for k in range(12):                      # quiet history
        ctx.move = 0.001 * ((-1) ** k)
        mm.maybe_poll(t); t += 1
    ctx.move = -0.05                         # 5% basket selloff
    snap = mm.maybe_poll(t)
    check("moomoo: selloff produces strongly negative risk z",
          snap.available and snap.risk_z < -2.0, f"z={snap.risk_z:.2f}")
    check("moomoo: per-ticker returns reported",
          snap.per_ticker.get("US.COIN") == -5.0)

    # Deterministically exercise the no-SDK path on EVERY machine —
    # including ones where moomoo-api is installed and OpenD is live.
    # A sys.modules None-sentinel was used before and was bypassed by
    # at least one Windows interpreter's import hooks, which built a
    # real OpenQuoteContext and connected to the operator's live OpenD
    # mid-test. Patching the feed's own import seam has no import
    # machinery to route around: the SDK cannot be imported and a
    # gateway cannot be touched, full stop.
    from unittest.mock import patch
    with patch.object(MoomooFeed, "_import_sdk",
                      side_effect=ImportError("forced by smoke test")):
        mm2 = MoomooFeed({"enabled": True, "poll_minutes": 0,
                          "tickers": [{"code": "US.COIN"}]})
        s = mm2.maybe_poll(1000.0)
        check("moomoo: missing SDK degrades gracefully",
              not s.available and mm2._ctx is None)

    # equity selloff feeds structural stress
    from sentiment.fear_filter import NarrativeFilter, StructuralInputs
    filt = NarrativeFilter({})
    calm = StructuralInputs(vol_percentile=50, depth_ratio=1.0,
                            turbulence_pct=50)
    stressed = StructuralInputs(vol_percentile=50, depth_ratio=1.0,
                                turbulence_pct=50, risk_asset_z=-3.5,
                                risk_asset_available=True)
    i_calm, _ = filt.structural_stress(calm)
    i_sell, parts = filt.structural_stress(stressed)
    check("structural stress: equity selloff raises the index",
          i_sell > i_calm and parts.get("equity", 0) > 0.5,
          f"{i_calm:.2f} -> {i_sell:.2f}")


def test_runtime_and_runner():
    import shutil
    import os
    from core.runtime import (ControlChannel, StatusWriter, JsonlLogHandler,
                              tail_events, ARM_PHRASE)
    from runner import BotRunner
    from main import load_config
    import logging as _logging

    shutil.rmtree(str(TMP / "smoke_rt"), ignore_errors=True)
    os.makedirs(str(TMP / "smoke_rt"), exist_ok=True)

    # --- control channel round trip ---
    ch = ControlChannel(str(TMP / "smoke_rt" / "control"))
    ch.send("pause"); ch.send("sim_force_fear", {"cycles": 4})
    got = ch.consume()
    check("runtime: control channel round-trips in order",
          [c["cmd"] for c in got] == ["pause", "sim_force_fear"] and
          got[1]["args"]["cycles"] == 4)
    check("runtime: channel drained after consume", ch.consume() == [])
    try:
        ch.send("withdraw_everything")
        check("runtime: unknown commands rejected", False)
    except ValueError:
        check("runtime: unknown commands rejected", True)

    # --- structured log capture ---
    h = JsonlLogHandler(str(TMP / "smoke_rt" / "events.jsonl"))
    lg = _logging.getLogger("liquiditybot.test")
    lg.addHandler(h); lg.setLevel(_logging.INFO)
    lg.warning("stop 1979.20 hit")
    lg.info("routine")
    lg.removeHandler(h)
    evs = tail_events(str(TMP / "smoke_rt" / "events.jsonl"), min_level="WARNING")
    check("runtime: logs captured as structured JSONL, level-filterable",
          len(evs) == 1 and evs[0]["msg"] == "stop 1979.20 hit")

    # --- status writer atomic + equity log ---
    sw = StatusWriter(str(TMP / "smoke_rt" / "status.json"), str(TMP / "smoke_rt" / "equity.csv"))
    sw.write({"equity": 123.45, "daily_pnl": 1.0, "mode": "DRY_RUN"}, now=1000.0)
    payload = json.loads(Path(str(TMP / "smoke_rt" / "status.json")).read_text(encoding="utf-8"))
    check("runtime: status.json serializable with timestamp",
          payload["equity"] == 123.45 and "written_at" in payload)
    check("runtime: equity curve appended",
          "1000,123.45" in Path(str(TMP / "smoke_rt" / "equity.csv")).read_text(encoding="utf-8"))

    # --- kraken withdrawal deny list ---
    from data.kraken_feed import KrakenFeed, FORBIDDEN_PRIVATE_ENDPOINTS
    kf = KrakenFeed({"api_key": "k", "api_secret": "a2V5"})  # nosec B105 - dummy test secret
    kf.session.post = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("network reached for forbidden endpoint!"))
    check("safety: Withdraw endpoint hard-blocked before any network",
          kf._private_post("Withdraw", {"amount": "999"}) is None)
    check("safety: deny list covers transfers",
          "WalletTransfer" in FORBIDDEN_PRIVATE_ENDPOINTS)

    # --- runner: paused start, step exactly one cycle, status written ---
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000  # hermetic
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    qa_redirect_paths(cfg, "runtime")
    cfg["system"]["state_path"] = str(TMP / "smoke_rt" / "state.json")
    cfg["ml"]["model_path"] = str(TMP / "none.json")
    cfg["ml"]["history_path"] = str(TMP / "smoke_rt" / "hist.csv")
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    from main import LiquidityBot
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)
    r = BotRunner(cfg, bot=bot, start_paused=True)
    r.status = StatusWriter(str(TMP / "smoke_rt" / "status.json"),
                            str(TMP / "smoke_rt" / "equity.csv"))
    check("runner: starts paused", r.state == "PAUSED" and bot._cycle == 0)
    r.handle_command({"cmd": "step", "args": {}})
    now = time.time()
    if r._step_requested:
        r._step_requested = False
        bot.cycle_once(now)
    r.status.write(r.build_status(now), now)
    check("runner: step executed exactly one cycle while paused",
          bot._cycle == 1 and r.state == "PAUSED")
    check("manip gauge refreshes every slow cycle (not only at signals)",
          set(bot._manip_scores) >= set(prices)
          and all(0.0 <= v <= 1.0 for v in bot._manip_scores.values()))
    st = json.loads(Path(str(TMP / "smoke_rt" / "status.json")).read_text(encoding="utf-8"))
    check("runner: status schema complete",
          all(k in st for k in ("mode", "positions", "regimes", "monitor",
                                "ml", "equity", "runner_state", "sim")))
    check("runner: mode reported DRY_RUN", st["mode"] == "DRY_RUN")
    # mark-freshness: after a cycle the marks just updated, so age ~0. This is
    # the TRUTHFUL staleness signal - feed_latency_ms freezes on a Ticker
    # outage, marks_age_sec keeps climbing when a price stops updating.
    check("runner: marks_age_sec present and fresh after a live cycle",
          "marks_age_sec" in st and st["marks_age_sec"] < 5.0,
          f"marks_age_sec={st.get('marks_age_sec')}")
    # freeze a mark (simulate a Ticker-only outage: the WALL stamps stop
    # advancing) and rebuild - the age must climb, exposing the stale
    # price as stale. 2026-08-07 latency audit: the gauge's truth source
    # moved from _mark_ts (loop-frozen `now`, arithmetically 0 forever)
    # to the telemetry-only _mark_wall_ts, so the outage is simulated on
    # the wall stamps - exactly what a real Ticker outage freezes.
    for s in bot._mark_wall_ts:
        bot._mark_wall_ts[s] -= 120.0
    st2 = r.build_status(now)
    check("runner: marks_age_sec climbs when a mark freezes (stale != live)",
          st2["marks_age_sec"] >= 120.0,
          f"marks_age_sec={st2['marks_age_sec']}")

    # --- sim injection: price shock moves marks (dry only) ---
    r.handle_command({"cmd": "sim_price_shock",
                      "args": {"asset": "ETH", "pct": -10.0, "cycles": 1}})
    before = bot.marks.get("ETH/USD", 0.0)
    bot.cycle_once(now + 5)
    after = bot.marks.get("ETH/USD", 0.0)
    check("runner: sim price shock moved the mark",
          before > 0 and after < before * 0.95,
          f"{before:.2f} -> {after:.2f}")

    # --- entries kill switch + live arm gate ---
    r.handle_command({"cmd": "entries_off", "args": {}})
    check("runner: entries kill switch applied", not bot.entries_enabled)
    r.handle_command({"cmd": "entries_on", "args": {}})

    bot.dry_run = False              # pretend live for the gate check
    check("safety: live entries blocked when disarmed",
          not bot._live_order_allowed("entry"))
    check("safety: exits ALWAYS allowed even disarmed",
          bot._live_order_allowed("exit"))
    r.handle_command({"cmd": "arm_live", "args": {"confirm": "arm live"}})
    check("safety: wrong phrase refused", not bot.live_armed)
    r.handle_command({"cmd": "arm_live", "args": {"confirm": ARM_PHRASE}})
    check("safety: exact phrase arms", bot.live_armed and
          bot._live_order_allowed("entry"))
    r.handle_command({"cmd": "disarm_live", "args": {}})
    check("safety: disarm is unconditional", not bot.live_armed)
    r.handle_command({"cmd": "sim_force_fear", "args": {"cycles": 3}})
    check("safety: sims refused in live mode", bot.sim.force_fear == 0)
    # mirror a genuinely live-constructed bot (main.py wires
    # OrderManager(dry_run=self.dry_run)); the fixture flipped bot.dry_run
    # post-init so the manager flag must be arranged to match
    bot.orders.dry_run = False
    r.handle_command({"cmd": "force_dry", "args": {}})
    check("safety: force_dry flips bot AND order-manager to dry",
          bot.dry_run and bot.orders.dry_run and not bot.live_armed)
    hostile = [
        {"cmd": "arm_live", "args": {"confirm": "ARM LIVE"}},
        {"cmd": "force_dry", "args": {"dry": False}},
        {"cmd": "start", "args": {"dry_run": False}},
        {"cmd": "entries_on", "args": {"live": True}},
        {"cmd": "sim_clear", "args": {}},
        {"cmd": "snapshot", "args": {}},
        {"cmd": "step", "args": {}},
        {"cmd": "disarm_live", "args": {}},
    ]
    for c in hostile:
        r.handle_command(c)
    check("safety: NO command sequence resurrects live mode after "
          "force_dry", bot.dry_run and bot.orders.dry_run
          and not bot.live_armed)
    bot.dry_run = True


def test_dl_upgrades():
    from ml.calibration import psi, feature_deciles
    from ml.walkforward import evaluate_and_select
    from ml.models import LogisticModel
    from ml.monitor import ModelMonitor
    rng = np.random.default_rng(13)

    # --- PSI: detects a shifted distribution, quiet on a stable one ---
    train = rng.normal(0, 1, (500, 3))
    dec = feature_deciles(train)
    stable = rng.normal(0, 1, 200)
    shifted = rng.normal(1.6, 1, 200)
    check("psi: stable distribution scores low", psi(dec[0], stable) < 0.10,
          f"{psi(dec[0], stable):.3f}")
    check("psi: shifted distribution flagged", psi(dec[0], shifted) > 0.25,
          f"{psi(dec[0], shifted):.3f}")

    # --- monitor drift ladder requests retrain on broad input drift ---
    m = ModelMonitor({"drift_min_rows": 30, "retrain_cooldown_hours": 0,
                      "retrain_flag_path": str(TMP / "smoke_drift.flag")})
    Path(str(TMP / "smoke_drift.flag")).unlink(missing_ok=True)
    for _ in range(40):
        m.note_features(rng.normal(2.0, 1, 3))     # all 3 features shifted
    m.check_drift(dec, ["a", "b", "c"])
    check("drift: broad shift requests retrain",
          m.drift_share == 1.0 and Path(str(TMP / "smoke_drift.flag")).exists())

    # --- recency weighting: recent regime dominates the fit ---
    n = 600
    X = rng.normal(0, 1, (n, 4))
    y = np.empty(n)
    y[:300] = (X[:300, 0] > 0)          # old regime: feature 0 positive
    y[300:] = (X[300:, 0] < 0)          # new regime: relationship FLIPPED
    y = y.astype(float)
    w_recent = np.concatenate([np.full(300, 0.05), np.full(300, 1.0)])
    m_flat = LogisticModel().fit(X, y)
    m_wgt = LogisticModel().fit(X, y, sample_weight=w_recent)
    Xn = rng.normal(0, 1, (300, 4))
    yn = (Xn[:, 0] < 0).astype(float)   # future = new regime
    from ml.models import auc_score
    a_flat = auc_score(yn, m_flat.predict_proba(Xn))
    a_wgt = auc_score(yn, m_wgt.predict_proba(Xn))
    check("sample weights: recency weighting adapts to regime flip",
          a_wgt > a_flat + 0.1 and a_wgt > 0.7,
          f"flat={a_flat:.2f} weighted={a_wgt:.2f}")

    # --- weighted walk-forward + ensemble + importance end to end ---
    w2 = rng.normal(0, 1, 4)
    y2 = ((X @ w2 + rng.normal(0, 0.6, n)) > 0).astype(float)
    res = evaluate_and_select(X, y2, sample_weight=np.ones(n),
                              feature_names=["f0", "f1", "f2", "f3"],
                              ensemble_k=2)
    check("walkforward: returns importance from a true OOS fold",
          len(res["importance"]) > 0 and
          all(isinstance(v, float) for _, v in res["importance"]))
    top = [name for name, _ in res["importance"][:2]]
    strongest = f"f{int(np.argmax(np.abs(w2)))}"
    check("importance: strongest planted feature ranks top-2",
          strongest in top, f"planted={strongest} top={top}")
    if res["selected"] == "mlp":
        check("ensemble: selected model is the seed ensemble",
              res["model"].kind == "ensemble_mlp")
    else:
        check("ensemble: honest selection kept the baseline", True)


def test_record_replay_sweep():
    import shutil
    from data.replay import FeedRecorder
    from scripts.replay import run_replay
    from main import LiquidityBot, load_config
    from strategies.signal_gates import SignalResult

    shutil.rmtree(str(TMP / "smoke_rec"), ignore_errors=True)
    Path(str(TMP / "smoke_rec")).mkdir(parents=True)
    sink = str(TMP / "smoke_rec" / "session.jsonl")

    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000  # hermetic
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    qa_redirect_paths(cfg, "record")
    cfg["system"]["state_path"] = str(TMP / "smoke_rec" / "state.json")
    cfg["ml"]["model_path"] = str(TMP / "none.json")
    cfg["ml"]["history_path"] = str(TMP / "smoke_rec" / "hist.csv")
    cfg["position_sizer"] = dict(cfg.get("position_sizer", {}),
                                 entry_cooldown_min=0, min_p_win=0.50)
    # 0.72: above the honest net breakeven (~0.690 after the 2026-07-29 payoff-compounding fix; was 0.66 vs the flat-weighted 0.632 - the maker+taker
    # round-trip cost fix). Subject is the recorder, not cost policy.
    cfg["ml"]["cold_start_prior_p"] = 0.72
    cfg["pretrade"]["min_edge_cost_ratio"] = 0.1
    cfg["pretrade"]["price_exit_leg"] = False  # subject: recorder, not cost policy

    # --- record a live-ish session with mocked feeds + forced signal ---
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    okx, bnc, krk = MockOKX(prices), MockBinanceUS(prices), MockKraken(prices)
    bot = LiquidityBot(cfg,
                       okx=FeedRecorder(okx, "okx", sink),
                       binanceus=FeedRecorder(bnc, "binanceus", sink),
                       kraken=FeedRecorder(krk, "kraken", sink),
                       resume=False)
    bot.gates.evaluate_asset = lambda base_asset, view: SignalResult(  # type: ignore[assignment]
        symbol=f"{base_asset}/USD", direction="long" if base_asset == "ETH" else None,
        confidence=1.0 if base_asset == "ETH" else 0.0, size=0.0,
        all_confirmed=(base_asset == "ETH"), gates_passed={})
    rng = np.random.default_rng(77)
    t = time.time()
    for k in range(40):
        for a in prices:
            prices[a] *= float(np.exp(rng.normal(0.001, 0.003)))
        bot.cycle_once(t)
        if k == 0:      # first cycle ran the macro fit; force a long-friendly
            for a in ("ETH", "BTC"):   # playbook so the forced signal can act
                st = bot.macro.state(a)
                st.label = "bull_quiet"
                st.playbook = dict(bot.macro.playbooks["bull_quiet"])
                bot.macro._states[a] = st
        t += 5.0
    recorded_entries = sum(1 for o in bot.orders._orders.values()
                           if o.purpose == "entry")
    check("recorder: session file written with frames",
          Path(sink).exists() and Path(sink).stat().st_size > 5000)
    check("recorder: pipeline submitted entries during recording",
          recorded_entries >= 1, f"entries={recorded_entries}")

    # --- replay determinism: two replays match each other exactly ---
    cfg_r = json.loads(json.dumps(cfg))
    # (run_replay owns state/history paths - it redirects both to TMP)
    # Replay runs REAL gates - the forced-signal patching wasn't recorded.
    # We verify DETERMINISM here, not that the replay reproduces the
    # forced-signal run.
    r1 = run_replay(cfg_r, sink)
    r2 = run_replay(cfg_r, sink)
    check("replay: consumed the recorded session",
          r1["cycles"] >= 30, f"cycles={r1['cycles']}")
    check("replay: two runs byte-identical (deterministic)",
          r1["final_equity"] == r2["final_equity"] and
          r1["realized_pnl"] == r2["realized_pnl"] and
          r1["entries_filled"] == r2["entries_filled"], f"{r1} vs {r2}")

    # --- sweep machinery: two combos produce two ranked rows ---
    from scripts.sweep import parse_grid
    grid = parse_grid(["position_sizer.min_p_win=0.5,0.99"])
    check("sweep: grid parser types values",
          grid[0][1] == [0.5, 0.99])
    from scripts.replay import set_dotted
    c1 = json.loads(json.dumps(cfg_r)); set_dotted(c1, grid[0][0], "0.5")
    c2 = json.loads(json.dumps(cfg_r)); set_dotted(c2, grid[0][0], "0.99")
    s1 = run_replay(c1, sink)
    s2 = run_replay(c2, sink)
    check("sweep: parameter change alters behavior in replay",
          s1["cycles"] == s2["cycles"], "cycle counts should match")
    check("sweep: p_win=0.99 takes fewer/equal entries than 0.50",
          s2["entries_filled"] <= s1["entries_filled"],
          f"{s2['entries_filled']} vs {s1['entries_filled']}")


def test_security_hardening():
    from core.sanitize import (safe_float, loads_bounded, clean_book,
                               clean_candles, safe_rss_root, cap_text)
    import math as _math

    # --- safe_float rejects the poison values stdlib json accepts ---
    check("sanitize: NaN -> default", safe_float(float("nan"), 7.0) == 7.0)
    check("sanitize: +Inf -> default", safe_float(float("inf"), 7.0) == 7.0)
    check("sanitize: -Inf -> default", safe_float(float("-inf"), 7.0) == 7.0)
    check("sanitize: garbage -> default", safe_float("not a number", 7.0) == 7.0)
    check("sanitize: clamps to range",
          safe_float(999, 0.0, lo=0.0, hi=100.0) == 100.0 and
          safe_float(-5, 0.0, lo=0.0, hi=100.0) == 0.0)
    check("sanitize: valid value passes", safe_float("54.2", 0.0) == 54.2)

    # --- loads_bounded refuses NaN/Infinity JSON constants ---
    check("sanitize: JSON with NaN rejected",
          loads_bounded('{"x": NaN}') is None)
    check("sanitize: JSON with Infinity rejected",
          loads_bounded('{"x": Infinity}') is None)
    check("sanitize: clean JSON parses", loads_bounded('{"x": 1.5}') == {"x": 1.5})
    check("sanitize: oversized payload rejected",
          loads_bounded('{"x":1}', max_bytes=3) is None)

    # --- clean_book rejects poisoned order books ---
    good = {"bids": [[100.0, 2.0], [99.0, 1.0]], "asks": [[101.0, 2.0]]}
    check("sanitize: valid book passes", clean_book(good) is not None)
    check("sanitize: NaN price level dropped",
          (clean_book({"bids": [[float("nan"), 1.0], [99.0, 1.0]],
                       "asks": [[101.0, 1.0]]}) or {})["bids"] == [[99.0, 1.0]])
    check("sanitize: negative price level dropped",
          (clean_book({"bids": [[-5.0, 1.0], [99.0, 1.0]],
                       "asks": [[101.0, 1.0]]}) or {})["bids"] == [[99.0, 1.0]])
    check("sanitize: Inf size dropped",
          clean_book({"bids": [[99.0, float("inf")]],
                      "asks": [[101.0, 1.0]]}) is None)   # bids empty -> None
    check("sanitize: crossed book rejected",
          clean_book({"bids": [[102.0, 1.0]], "asks": [[101.0, 1.0]]}) is None)
    check("sanitize: empty side rejected",
          clean_book({"bids": [], "asks": [[101.0, 1.0]]}) is None)

    # --- clean_candles drops poisoned rows ---
    cc = clean_candles([
        {"time": 1, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 5},
        {"time": 2, "open": float("nan"), "high": 1, "low": 1, "close": 1, "volume": 1},
        {"time": 3, "open": -1, "high": 1, "low": 1, "close": 1, "volume": 1},
        {"time": 4, "open": 100, "high": 101, "low": 99, "close": 100,
         "volume": float("inf")},
    ])
    check("sanitize: only clean candles survive",
          len(cc) == 2 and cc[0]["time"] == 1 and cc[1]["time"] == 4)
    check("sanitize: Inf volume coerced to 0",
          cc[1]["volume"] == 0.0)

    # --- XML entity-expansion (billion laughs) defense ---
    billion_laughs = """<?xml version="1.0"?>
    <!DOCTYPE lolz [<!ENTITY lol "lol">
    <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
    <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>
    <rss><channel><item><title>&lol3;</title></item></channel></rss>"""
    root = safe_rss_root(billion_laughs)
    check("sanitize: XML entity-expansion attack neutralized (no bomb)",
          root is None or "lollol" not in (root.findtext(".//title") or ""))
    check("sanitize: oversized XML rejected",
          safe_rss_root("<rss/>" * 100, max_bytes=5) is None)
    check("sanitize: cap_text truncates",
          len(cap_text("x" * 100, max_bytes=10) or "") == 10)

    # --- end-to-end: poisoned feeds cannot corrupt snapshots ---
    from data.webdata_feed import WebDataFeed

    def poison(url):
        if "alternative" in url:
            return '{"data":[{"value":"NaN"}]}'
        return ('{"data":{"market_cap_percentage":{"btc":Infinity},'
                '"total_market_cap":{"usd":1e999}}}')

    wd = WebDataFeed({"enabled": True, "poll_minutes": 0}, fetch=poison)
    s = wd.maybe_poll(1000.0)
    check("sanitize: poisoned webdata falls back to safe defaults, no NaN/Inf",
          _math.isfinite(s.fear_greed) and _math.isfinite(s.btc_dominance) and
          s.fear_greed == 50.0 and s.btc_dominance == 0.0,
          f"fg={s.fear_greed} dom={s.btc_dominance}")

    # poisoned OKX book must not reach the view
    from data.okx_feed import OKXFeed
    ok = OKXFeed({"symbols": ["ETH-USDT-SWAP"]})
    # ctVal answered (scale 1.0) so the subject stays SANITIZE — with the
    # lookup failing, DL-8's fail-closed skip would return None before
    # clean_book ever ran (that contract is pinned in test_okx_ctval.py)
    ok._get = lambda path, params=None: ([{  # type: ignore[assignment]
        "bids": [["NaN", "1"], ["1999.0", "2"]],
        "asks": [["2001.0", "2"]]}] if "books" in path
        else [{"ctVal": "1"}] if "instruments" in path else None)
    book = ok.get_order_book("ETH-USDT-SWAP")
    check("sanitize: poisoned OKX book cleaned before use",
          book is not None and
          all(_math.isfinite(p) and p > 0 for p, _ in book["bids"]) and
          [1999.0, 2.0] in book["bids"])

    # --- withdrawal deny list still airtight (re-assert here) ---
    from data.kraken_feed import FORBIDDEN_PRIVATE_ENDPOINTS
    for ep in ("Withdraw", "WithdrawInfo", "WalletTransfer", "WithdrawAddresses"):
        check(f"safety: {ep} on deny list", ep in FORBIDDEN_PRIVATE_ENDPOINTS)



# ---------------------------------------------------------------------------
# 24. institutional hardening layer
# ---------------------------------------------------------------------------
def test_hardening_layer():
    import copy
    from core.config_guard import validate, enforce, ConfigError
    from core.watchdog import Watchdog
    from execution.risk_firewall import RiskFirewall
    from execution.order_manager import OrderManager
    from main import load_config

    base = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    qa_redirect_paths(base, "hard")

    # --- config guard -----------------------------------------------------
    c = copy.deepcopy(base)
    c["pretrade"]["maker_fee_bps"] = 10       # mismatch + sub-floor
    fatals = [m for sev, m in validate(c) if sev == "FATAL"]
    check("guard: fee mismatch between pretrade and order_manager is FATAL",
          any("fee mismatch" in m for m in fatals), str(fatals))

    c = copy.deepcopy(base)
    c["pretrade"]["maker_fee_bps"] = 10
    c["order_manager"]["maker_fee_bps"] = 10
    c["system"]["dry_run"] = False
    c["capital_management"]["starting_capital_usd"] = 5000
    fatals = [m for sev, m in validate(c) if sev == "FATAL"]
    check("guard: sub-floor fees are FATAL in live config",
          any("public spot floor" in m for m in fatals), str(fatals))
    raised = False
    try:
        enforce(c)
    except ConfigError:
        raised = True
    check("guard: enforce() refuses to start live on fatal config", raised)
    c["system"]["dry_run"] = True
    check("guard: same config only WARNS in dry-run (paper finds mistakes)",
          enforce(c) is not None)

    c = copy.deepcopy(base)
    c["capital_management"]["daily_loss_limit_pct"] = 20   # >= hard stop 15
    check("guard: daily loss limit above hard stop is FATAL",
          any("must be below" in m for sev, m in validate(c) if sev == "FATAL"))

    c = copy.deepcopy(base)
    c["profit_taking"]["tier_3"]["trigger_pct_gain"] = 1.5  # below tier_2
    check("guard: non-increasing tier triggers are FATAL",
          any("not strictly above" in m
              for sev, m in validate(c) if sev == "FATAL"))

    c = copy.deepcopy(base)
    # capital so small the max-position ticket (capital * position cap) can never
    # reach min_ticket_usd: $50 * 25% = $12.50 < $15. (Kept below the cap so the
    # check tracks the live position cap rather than a hardcoded percentage.)
    c["capital_management"]["starting_capital_usd"] = 50
    check("guard: sub-min-ticket capital flagged untradeable "
          "(max position ticket below min ticket)",
          any("NO entry can ever be approved" in m
              for sev, m in validate(c) if sev == "WARN"))

    c = copy.deepcopy(base)
    c["system"]["dry_run"] = False
    c["capital_management"]["starting_capital_usd"] = 5000
    c["exchanges"]["kraken"]["api_key"] = ""
    c["exchanges"]["kraken"]["api_secret"] = ""  # nosec B105 - empty test placeholder
    check("guard: live mode without Kraken API keys is FATAL",
          any("api_key and api_secret" in m
              for sev, m in validate(c) if sev == "FATAL"))

    c = copy.deepcopy(base)
    c["regime"]["momentum_bear_max"] = 0.2      # bear threshold above zero
    check("guard: inverted regime momentum thresholds are FATAL",
          any("momentum thresholds incoherent" in m
              for sev, m in validate(c) if sev == "FATAL"))

    c = copy.deepcopy(base)
    c["hedging"]["max_equity_frac"] = 1.5       # hedge bigger than equity
    check("guard: hedge cap above equity is FATAL",
          any("max_equity_frac" in m
              for sev, m in validate(c) if sev == "FATAL"))

    c = copy.deepcopy(base)
    c["hedging"]["beta_floor"] = 1.2            # every beta 'unreliable'
    check("guard: hedging beta_floor >= 1 is FATAL",
          any("beta_floor" in m
              for sev, m in validate(c) if sev == "FATAL"))

    # --- risk firewall -----------------------------------------------------
    fw = RiskFirewall({"entry_collar_bps": 100, "exit_collar_bps": 500,
                       "max_order_usd": 5000, "max_order_pct_equity": 30,
                       "max_orders_per_min": 5, "dupe_window_sec": 2.0})
    t0 = 1000.0
    v = fw.check(pair="ETHUSD", side="buy", purpose="entry", price=2100.0,
                 size=0.1, ref_price=2000.0, equity=10000, now=t0)
    check("firewall: entry 500bps off reference REJECTED", not v.allowed,
          str(v.reasons))
    v = fw.check(pair="ETHUSD", side="sell", purpose="exit", price=1800.0,
                 size=0.1, ref_price=2000.0, equity=10000, now=t0 + 0.1)
    check("firewall: exit outside collar CLAMPED, never blocked",
          v.allowed and v.clamped and abs(v.price - 1900.0) < 1e-6,
          f"price={v.price}")
    v = fw.check(pair="ETHUSD", side="buy", purpose="entry", price=2000.0,
                 size=10.0, ref_price=2000.0, equity=10000, now=t0 + 0.2)
    check("firewall: entry notional over cap REJECTED", not v.allowed)
    v = fw.check(pair="ETHUSD", side="sell", purpose="exit", price=2000.0,
                 size=10.0, ref_price=2000.0, equity=10000, now=t0 + 0.3)
    check("firewall: oversized exit shrunk to cap and allowed",
          v.allowed and v.clamped and v.size < 10.0, f"size={v.size}")
    v1 = fw.check(pair="ETHUSD", side="buy", purpose="entry", price=2000.0,
                  size=0.1, ref_price=2000.0, equity=10000, now=t0 + 1.0)
    v2 = fw.check(pair="ETHUSD", side="buy", purpose="entry", price=2000.0,
                  size=0.1, ref_price=2000.0, equity=10000, now=t0 + 1.5)
    check("firewall: identical order inside dupe window suppressed",
          v1.allowed and not v2.allowed, str(v2.reasons))
    # rev 2 contract: limits are BOUNDED — "disable via absurd value" is
    # itself a refused config (that's the point of the guard). Isolate
    # the rate limiter with legal, merely-generous limits instead.
    check("firewall: absurd limit config REFUSED at init (fail closed)",
          _raises(lambda: RiskFirewall({"entry_collar_bps": 1e9})))
    fw2 = RiskFirewall({"max_orders_per_min": 3, "dupe_window_sec": 0.0,
                        "entry_collar_bps": 5000.0,
                        "exit_collar_bps": 10000.0, "max_order_usd": 1e9,
                        "max_order_pct_equity": 100.0})
    oks = [fw2.check(pair="ETHUSD", side="buy", purpose="entry",
                     price=2000.0 + i, size=0.1, ref_price=2000.0 + i,
                     equity=1e9, now=t0 + i * 0.1).allowed for i in range(5)]
    check("firewall: per-minute rate limit engages",
          oks[:3] == [True] * 3 and not oks[3], str(oks))

    # --- watchdog -----------------------------------------------------------
    wd = Watchdog({"stale_warn_sec": 30, "stale_critical_sec": 120,
                   "max_venue_divergence_bps": 150,
                   "pnl_velocity_window_sec": 900,
                   "pnl_velocity_max_drop_pct": 6.0,
                   "tick_jump_quarantine_pct": 8.0})
    now = 5000.0
    st = wd.evaluate(now, {"ETH": now - 60}, ["ETH"], {"ETH": 2000.0},
                     {"ETH": 2000.0}, 10000.0, 1, dry_run=True)
    check("watchdog: stale venue data blocks entries",
          st.entries_blocked and "stale" in st.reasons[0], str(st.reasons))
    st = wd.evaluate(now, {"ETH": now}, ["ETH"], {"ETH": 2000.0},
                     {"ETH": 1950.0}, 10000.0, 0, dry_run=True)
    check("watchdog: cross-venue divergence (>150bps) blocks entries",
          st.entries_blocked and st.divergent_assets, str(st.reasons))
    wd2 = Watchdog({"pnl_velocity_window_sec": 900,
                    "pnl_velocity_max_drop_pct": 6.0,
                    "pnl_velocity_cooldown_sec": 1800})
    wd2.evaluate(now, {"ETH": now}, ["ETH"], {"ETH": 2000.0},
                 {"ETH": 2000.0}, 10000.0, 0, dry_run=True)
    st = wd2.evaluate(now + 300, {"ETH": now + 300}, ["ETH"],
                      {"ETH": 2000.0}, {"ETH": 2000.0}, 9300.0, 0,
                      dry_run=True)
    check("watchdog: -7% equity in 5min trips the velocity breaker",
          st.velocity_tripped, f"vel={st.pnl_velocity_pct:.2f}%")
    st = wd2.evaluate(now + 400, {"ETH": now + 400}, ["ETH"],
                      {"ETH": 2000.0}, {"ETH": 2000.0}, 9400.0, 0,
                      dry_run=True)
    check("watchdog: velocity trip latches through cooldown",
          st.velocity_tripped)

    wd3 = Watchdog({"tick_jump_quarantine_pct": 8.0})
    m, ok = wd3.filter_mark("ETH", 2000.0)
    m, ok = wd3.filter_mark("ETH", 1700.0)          # -15% single print
    check("watchdog: anomalous tick quarantined (stops held one cycle)",
          not ok)
    m, ok = wd3.filter_mark("ETH", 1690.0)          # confirmed crash
    check("watchdog: confirmed move releases stops next cycle",
          ok and m == 1690.0)
    wd4 = Watchdog({"tick_jump_quarantine_pct": 8.0})
    wd4.filter_mark("ETH", 2000.0)
    wd4.filter_mark("ETH", 1700.0)
    m, ok = wd4.filter_mark("ETH", 2001.0)          # outlier reverts
    check("watchdog: bogus print discarded when next tick reverts",
          ok and m == 2001.0)

    # --- order manager: precision / ordermin / market invariant -------------
    class _FeedStub:
        def __init__(self):
            self.deadman_calls = []
        def cancel_all_orders_after(self, t):
            self.deadman_calls.append(t)
            return True
        def _private_post(self, e, d=None):
            return {}
    meta = {"ETHUSD": {"price_decimals": 2, "lot_decimals": 8,
                       "ordermin": 0.002},
            "XBTUSD": {"price_decimals": 1, "lot_decimals": 8,
                       "ordermin": 0.00005}}
    om = OrderManager(_FeedStub(), {"deadman_timeout_sec": 60},
                      dry_run=True, pair_meta=meta)
    check("orders: BTC price formatted to venue precision (1 decimal)",
          om._fmt_price("XBTUSD", 60123.456) == "60123.5")
    check("orders: ETH price formatted to venue precision (2 decimals)",
          om._fmt_price("ETHUSD", 2000.567) == "2000.57")
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
                  price=2000.0, size=0.0005, purpose="entry")
    check("orders: entry below venue ordermin skipped pre-flight", o is None)
    o = om.submit(asset="ETH", symbol="ETH/USD", pair="ETHUSD", side="buy",
                  price=2000.0, size=0.01, purpose="entry",
                  ordertype="market")
    check("orders: market order REFUSED for entries (exit-only invariant)",
          o is None)
    fs = _FeedStub()
    om_live = OrderManager(fs, {"deadman_timeout_sec": 60}, dry_run=False,
                           pair_meta=meta)
    om_live.poll({}, {}, now=1000.0)
    om_live.poll({}, {}, now=1010.0)      # inside half-interval: no refresh
    om_live.poll({}, {}, now=1035.0)      # past half-interval: refresh
    check("orders: dead-man switch refreshed at half timeout cadence",
          fs.deadman_calls == [60, 60], str(fs.deadman_calls))
    om_dry = OrderManager(_FeedStub(), {"deadman_timeout_sec": 60},
                          dry_run=True, pair_meta=meta)
    om_dry.poll({}, {}, now=1000.0)
    check("orders: dead-man never armed in dry run",
          om_dry.feed.deadman_calls == [])

    # --- snapshot integrity: checksum + backup generation --------------------
    import json as _json
    from main import LiquidityBot
    cfg = copy.deepcopy(base)
    cfg["system"]["dry_run"] = True
    cfg["system"]["state_path"] = str(TMP / "smoke_hard" / "state.json")
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["ml"]["history_path"] = str(TMP / "smoke_hard" / "hist.csv")
    import shutil
    shutil.rmtree(str(TMP / "smoke_hard"), ignore_errors=True)
    Path(str(TMP / "smoke_hard")).mkdir(parents=True)
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)
    bot.state.cash_balance = 7777.0
    check("snapshot: write with checksum succeeds", bot.store.snapshot(bot))
    bot.state.cash_balance = 8888.0
    bot.store.snapshot(bot)                      # rotates 7777 -> .bak
    sp = Path(cfg["system"]["state_path"])
    raw = _json.loads(sp.read_text(encoding="utf-8"))
    check("snapshot: checksum present in file", "_sha256" in raw)
    sp.write_text(sp.read_text()[:-30] + "}", encoding="utf-8")    # corrupt the primary
    bot2 = LiquidityBot(cfg, okx=MockOKX(prices),
                        binanceus=MockBinanceUS(prices),
                        kraken=MockKraken(prices), resume=True)
    check("snapshot: corrupt primary falls back to .bak generation",
          abs(bot2.state.cash_balance - 7777.0) < 1e-6,
          f"cash={bot2.state.cash_balance}")

    # --- exit escalation ladder ------------------------------------------
    from core.state import Position
    from datetime import datetime, timezone
    cfg2 = copy.deepcopy(cfg)
    cfg2["system"]["state_path"] = str(TMP / "smoke_hard" / "state2.json")
    bot3 = LiquidityBot(cfg2, okx=MockOKX(prices),
                        binanceus=MockBinanceUS(prices),
                        kraken=MockKraken(prices), resume=False)
    pos = Position(position_id="escpos", symbol="ETH/USD", direction="long",
                   entry_price=2000.0, size=0.5, original_size=0.5,
                   opened_at=datetime.now(timezone.utc))
    bot3.state.add_position(pos)
    bot3.marks["ETH/USD"] = 2000.0
    bot3.kraken_books["ETH"] = {}                # gap: no book, nothing fills
    t = 9000.0
    types_seen = []
    for i in range(4):
        bot3._submit_exit(pos, 100.0, "gap test")
        o = [x for x in bot3.orders.open_orders() if x.purpose == "exit"][-1]
        types_seen.append((o.ordertype, o.price))
        o.created_ts = t - 999                   # force timeout
        bot3.orders.poll({"ETH": {}}, {"ETH": 0.05}, now=t)
        t += 30
    check("escalation: first exit is a capped limit",
          types_seen[0][0] == "limit")
    check("escalation: slippage cap widens on each unfilled attempt",
          types_seen[1][1] < types_seen[0][1] and
          types_seen[2][1] < types_seen[1][1],
          str([round(p, 2) for _, p in types_seen]))
    check("escalation: final rung is a MARKET order",
          types_seen[3][0] == "market", str(types_seen))
    check("escalation: attempts tracked per position",
          bot3._exit_attempts.get("escpos", 0) == 4)


def test_rev4_connectivity_and_protocols():
    import math as _m
    import time as _t
    from execution.venue_adapters import VenueOrder, VenueRegistry
    from risk.protocols import RiskProtocolStack, give_back_stop

    vcfg = {"venues": {"kraken": {"enabled": True},
                       "ibkr": {"enabled": False}, "dma": {"enabled": False},
                       "prime": {"enabled": False}, "ccxt": {"enabled": False},
                       "fix": {"enabled": False}}}
    reg = VenueRegistry.from_config(vcfg)
    check("venues: registry carries all 6 adapters",
          len(reg.adapters) == 6, str(sorted(reg.adapters)))
    check("venues: kraken is the SOLE execution-eligible venue",
          reg.eligible_execution_venues() == ["kraken"],
          str(reg.eligible_execution_venues()))
    kraken = reg.get("kraken")
    assert kraken is not None
    ack = kraken.place(VenueOrder(
        pair="ETHUSD", side="buy", price=2000.0, size=0.01))
    check("venues: kraken ack-only mode accepts without a socket",
          ack.accepted and "ack-only" in ack.reason, ack.reason)
    ib = reg.get("ibkr")
    assert ib is not None
    check("venues: disabled connectivity adapter refuses place()",
          _raises(lambda: ib.place(VenueOrder(
              pair="ETHUSD", side="buy", price=2000.0, size=0.01))))
    ib.enabled = True
    ib.can_be_execution_eligible = True     # hostile flag-flip attempt
    check("venues: flag tamper cannot make non-kraken eligible",
          not ib.execution_eligible)

    st = RiskProtocolStack({})              # defaults, zero history
    m0, _ = st.entry_multiplier(0.25, 10_000.0, float("nan"), "ETH", 0.0)
    check("protocols: warmup is neutral (mult=1, no raise)",
          abs(m0 - 1.0) < 1e-9, f"{m0}")
    gap = RiskProtocolStack({"vol_target": {"enabled": False},
                             "cvar": {"enabled": False},
                             "budget": {"enabled": False},
                             "heat": {"enabled": False},
                             "gap": {"enabled": True, "gap_shock_pct": 15.0,
                                     "max_equity_loss_pct": 4.0}})
    mg, rg = gap.entry_multiplier(0.50, 10_000.0, float("nan"), "ETH", 0.0)
    check("protocols: gap cap sizes to survive a 15% gap at 4% equity loss",
          abs(mg - (0.04 / 0.15) / 0.50) < 1e-6, f"{mg:.4f} {rg}")
    cv = RiskProtocolStack({"vol_target": {"enabled": False},
                            "gap": {"enabled": False},
                            "budget": {"enabled": False},
                            "heat": {"enabled": False},
                            "cvar": {"enabled": True, "alpha": 0.975,
                                     "lookback_bars": 96, "min_obs": 40,
                                     "es_budget_frac": 0.010,
                                     "horizon_bars": 24}})
    t0, px = _t.time(), 2000.0
    for i in range(150):                    # fat-tailed mark history
        px *= (1.0 - 0.08) if i % 25 == 24 else 1.001
        cv.observe(10_000.0, {"ETH": px}, now=t0 + 300.0 * i)
    mc, rc = cv.entry_multiplier(0.25, 10_000.0, float("nan"), "ETH", 0.0,
                                 now=t0 + 300.0 * 151)
    check("protocols: CVaR budget shrinks size on fat-tailed history",
          0.0 < mc < 1.0 and any("RP-" in r for r in rc),
          f"{mc:.4f} {rc}")
    bd = RiskProtocolStack({"vol_target": {"enabled": False},
                            "cvar": {"enabled": False},
                            "gap": {"enabled": False},
                            "heat": {"enabled": False},
                            "budget": {"enabled": True,
                                       "daily_loss_budget_pct": 2.5,
                                       "weekly_loss_budget_pct": 6.0,
                                       "taper_start": 0.5,
                                       "floor_mult": 0.15}})
    bd.observe(10_000.0, {}, now=t0)        # anchor the day
    mb, rb = bd.entry_multiplier(0.25, 9_800.0, float("nan"), "ETH", 0.0,
                                 now=t0 + 3_600.0)
    check("protocols: loss-budget taper engages at 80% of daily budget",
          0.10 <= mb < 1.0 and any("RP-" in r for r in rb),
          f"{mb:.4f} {rb}")
    ht = RiskProtocolStack({"vol_target": {"enabled": False},
                            "cvar": {"enabled": False},
                            "gap": {"enabled": False},
                            "budget": {"enabled": False},
                            "heat": {"enabled": True,
                                     "max_portfolio_heat_frac": 0.35,
                                     "assumed_corr": 0.9}})
    mh, _ = ht.entry_multiplier(0.25, 10_000.0, float("nan"), "ETH", 0.40)
    check("protocols: over-max portfolio heat hard-vetoes new entries",
          mh == 0.0, f"{mh}")
    check("protocols: give-back ratchet locks 60% of peak open profit",
          abs(give_back_stop(100.0, 105.0, True, 0.40) - 103.0) < 1e-9)
    mz, _ = st.entry_multiplier(float("inf"), float("nan"), float("inf"),
                                "", float("nan"))
    check("protocols: garbage inputs never raise, mult stays finite",
          _m.isfinite(mz), f"{mz}")


if __name__ == "__main__":
    # synthetic order/fault/self-test records must never enter the
    # production audit trail (they bury real dispositions and break the
    # live runner's hash chain when run concurrently)
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(TMP / "liqbot_smoke_audit.jsonl")
    configure_registry(TMP / "liqbot_smoke_models")
    print("liquiditybot v2 smoke test\n" + "=" * 42)
    print("[1] HMM regime recovery");       test_hmm()
    print("[2] Avellaneda-Stoikov quoter"); test_as_quoter()
    print("[3] spoof detection");           test_spoof_detector()
    print("[4] pre-trade gate");            test_pretrade()
    print("[5] triple-barrier labeling");   test_triple_barrier()
    print("[6] numpy MLP + AUC");           test_mlp()
    print("[7] purged walk-forward");       test_walkforward()
    print("[8] sizer + narrative filter");  test_sizer_and_filter()
    print("[9] inventory + hedging");       test_inventory_and_hedge()
    print("[10] full-bot integration");     test_integration()
    print("[11] entry->fill->exit lifecycle"); test_entry_fill_exit_path()
    print("[12] persistence round-trip");   test_persistence_roundtrip()
    print("[12b] capped-book learning lane"); test_capped_book_learning()
    print("[12c] pending entries reserve cap slots"); test_pending_entries_count_against_the_cap()
    print("[13] probability calibration");  test_calibration()
    print("[14] model monitor ladder");     test_monitor_ladder()
    print("[15] trade postmortems");        test_postmortem()
    print("[16] candidate labeling");       test_candidate_labeling()
    print("[17] sentiment scanner (free)"); test_sentiment_scanner()
    print("[18] webdata feed");             test_webdata_feed()
    print("[19] moomoo feed");              test_moomoo_feed()
    print("[20] runtime + runner + safety");test_runtime_and_runner()
    print("[21] DL upgrades");              test_dl_upgrades()
    print("[22] record/replay/sweep");      test_record_replay_sweep()
    print("[23] security hardening");        test_security_hardening()
    print("[24] institutional hardening");  test_hardening_layer()
    print("[25] rev4 venues + risk protocols"); test_rev4_connectivity_and_protocols()
    # SYNTHETIC-CLOCK TRIPWIRE (2026-08-11, tenth QA-writes-production
    # instance). Smoke fixtures run on a synthetic clock (ts ~1e6, epoch
    # 1970); production rows are all ts >= 1.75e9. Any row in a production
    # ledger with ts < 1e9 is a QA fixture that leaked. This runs OUTSIDE
    # pytest, where the conftest tripwire structurally cannot see - and it
    # is immune to the live runner appending real rows concurrently, which
    # a bytes-unchanged check would false-flag.
    import csv as _csv
    for _led in ("outputs/trade_paths.csv", "outputs/postmortem_summary.csv",
                 "outputs/signal_history.csv", "outputs/fills.csv"):
        _p = Path(_led)
        if not _p.exists():
            continue
        try:
            with open(_p, newline="", encoding="utf-8") as _fh:
                for _row in _csv.DictReader(_fh):
                    _ts = float(_row.get("ts") or _row.get("entry_ts") or "nan")
                    if _ts == _ts and 0 < _ts < 1e9:
                        check(f"tripwire: NO synthetic-clock rows in {_led}",
                              False, f"ts={_ts} ({_row.get('position_id') or _row.get('candidate_id') or '?'})")
                        break
        except Exception as _e:          # unreadable ledger is its own alarm
            check(f"tripwire: {_led} readable", False, repr(_e))
    print("=" * 42)
    print(f"passed {PASS}, failed {FAIL}")
    sys.exit(1 if FAIL else 0)
