"""scripts/archetype_battery.py — archetype null population runner (v0.1).

Spec: docs/superpowers/specs/2026-08-27-archetype-null-battery-design.md.
Report-only. Archetypes live HERE, in scripts/ — the engine's
strategies.engine dispatch cannot reach them. Every run is QA-isolated
twice over: config paths via prepare_replay_config inside run_replay,
process singletons via configure_audit/configure_registry in main().

The tape generator exists because the smoke-test mocks cannot host a
trade (measured 2026-08-27: candle bar times frozen at 0..119, per-call
reseed, drift-vs-history divergence tripping the watchdog). One
PriceWorld per seed drives ALL venues; candles are a rolling window
whose times advance with the replay clock.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.replay import FeedRecorder  # noqa: E402
from scripts.smoke_test import synth_book  # noqa: E402

ASSETS = ("ETH", "BTC")
BASE_PRICES = {"ETH": 2000.0, "BTC": 60000.0}
BAR_SEC = 300                       # 5m bars == the engine's candle bar
VENUE_NOISE_BPS = {"okx": 4.0, "binanceus": 7.0, "kraken": 0.0}
CANDLE_WINDOW = 120


class PriceWorld:
    """One GBM-with-regime path per asset per seed; every venue reads it."""

    def __init__(self, seed: int, bars: int, bar_sec: int = BAR_SEC):
        self.bars = bars
        self.bar_sec = bar_sec
        self.t0 = 1_700_000_000.0           # fixed epoch: tapes are timeless
        rng = np.random.default_rng(seed)
        self._px = {}
        for a in ASSETS:
            drift = rng.normal(0.0, 0.00035)         # per-seed regime tilt
            vol = float(rng.uniform(0.0015, 0.0045))  # per-seed vol level
            steps = rng.normal(drift, vol, bars)
            self._px[a] = BASE_PRICES[a] * np.exp(np.cumsum(steps))

    def price(self, asset: str, bar_i: int) -> float:
        return float(self._px[asset][min(max(bar_i, 0), self.bars - 1)])

    def bar_time(self, bar_i: int) -> float:
        return self.t0 + bar_i * self.bar_sec


def _candles(world: PriceWorld, asset: str, upto_bar: int,
             n: int = CANDLE_WINDOW) -> list:
    lo = max(0, upto_bar - n + 1)
    out = []
    for i in range(lo, upto_bar + 1):
        c = world.price(asset, i)
        o = world.price(asset, i - 1) if i > 0 else c
        out.append({"time": world.bar_time(i), "open": o,
                    "high": max(o, c) * 1.001, "low": min(o, c) * 0.999,
                    "close": c, "volume": 900.0})
    return out


class _WorldVenue:
    """Shared venue base: serves the world's price ± bounded venue noise."""

    def __init__(self, world: PriceWorld, name: str):
        self._w = world
        self._name = name
        self._bar = 0
        self._i = 0

    def set_bar(self, bar_i: int):
        self._bar = bar_i

    def _mark(self, asset: str) -> float:
        px = self._w.price(asset, self._bar)
        noise = VENUE_NOISE_BPS[self._name] * 1e-4
        # deterministic per (venue, asset, bar): coherent AND seed-stable
        h = (hash((self._name, asset, self._bar)) % 1000) / 1000.0 - 0.5
        return px * (1.0 + 2.0 * noise * h)


class WorldOKX(_WorldVenue):
    def get_market_data(self):
        out = {}
        for sym, asset in (("ETH-USDT-SWAP", "ETH"), ("BTC-USDT-SWAP", "BTC")):
            px = self._mark(asset)
            self._i += 1
            out[sym] = {"order_book": synth_book(px, depth=300, seed=self._i),
                        "candles": _candles(self._w, asset, self._bar),
                        "funding_rate": 0.0001, "volume_24h": 5e8}
        return out

    def get_daily_candles(self, symbol, limit=300):
        asset = "ETH" if symbol.startswith("ETH") else "BTC"
        step = max(1, 288)                       # 288 x 5m = 1 day
        bars = list(range(0, self._w.bars, step))[-limit:]
        return [{"time": self._w.bar_time(i), "open": self._w.price(asset, i),
                 "high": self._w.price(asset, i) * 1.01,
                 "low": self._w.price(asset, i) * 0.99,
                 "close": self._w.price(asset, i), "volume": 5e4}
                for i in bars]

    def get_candles(self, symbol, bar="5m", limit=100):
        asset = "ETH" if symbol.startswith("ETH") else "BTC"
        return _candles(self._w, asset, self._bar, n=min(limit, 300))


class WorldBinanceUS(WorldOKX):
    def get_market_data(self):
        out = {}
        for sym, asset in (("ETHUSD", "ETH"), ("BTCUSD", "BTC")):
            px = self._mark(asset)
            self._i += 1
            out[sym] = {"order_book": synth_book(px, depth=280, seed=self._i + 7),
                        "candles": _candles(self._w, asset, self._bar),
                        "funding_rate": None, "volume_24h": 4e5}
        return out


class WorldKraken(_WorldVenue):
    def __init__(self, world: PriceWorld):
        super().__init__(world, "kraken")
        self.trading_pairs = ["ETH/USD", "BTC/USD"]

    def kraken_pair(self, symbol):
        return symbol.replace("/", "")

    def get_ticker_price(self, pair):
        return self._mark("ETH" if pair.startswith(("ETH", "XETH")) else "BTC")

    def get_tickers(self, pairs):
        return {p: self.get_ticker_price(p) for p in pairs}

    def get_order_book(self, pair, depth=20):
        px = self.get_ticker_price(pair)
        self._i += 1
        return synth_book(px, spread_bps=5.0, depth=80, seed=self._i)

    def get_candles(self, pair, interval_min=5, limit=100):
        asset = "ETH" if pair.startswith(("ETH", "XETH")) else "BTC"
        return _candles(self._w, asset, self._bar, n=min(limit, 300))

    def get_daily_candles(self, pair, limit=720):
        return WorldOKX.get_daily_candles(self, pair, limit)


def _battery_config(cycles: int) -> dict:
    from main import load_config
    from scripts.smoke_test import qa_redirect_paths
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    # qa_redirect_paths mutates cfg in place AND returns it (verified against
    # scripts/smoke_test.py:61-124); assigned anyway to match the canonical
    # call pattern at scripts/replay.py:81 rather than rely on the in-place
    # mutation.
    cfg = qa_redirect_paths(cfg, "archetype_tape")
    # qa_redirect_paths points every write at a FIXED tag dir under the
    # system tempdir (not test-scoped - TMP = tempfile.gettempdir()), so
    # repeat record_tape() calls (this module's own seed-determinism test
    # calls it twice back to back; so does any rerun of this file) would
    # otherwise inherit ml.history_path/ledger rows a PRIOR call already
    # wrote, drifting self.history.row_count() at __init__ between two
    # runs that must be byte-identical. Same "one call = one clean slate"
    # fix scripts/replay.py:82-90 applies to its own per-pid QA dir, over
    # the same path set (state_path is re-pointed to a seed-specific file
    # below regardless, so it is omitted here).
    for stale in (cfg["system"]["weekly_ledger_path"],
                  cfg["system"]["monthly_ledger_path"],
                  cfg["system"]["fills_ledger_path"],
                  cfg["ml"]["history_path"],
                  cfg["ml"]["multi_horizon"]["shadow_path"]):
        Path(stale).unlink(missing_ok=True)
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    # world-backed assets only. NOTE: main.py builds self.symbol_map (and
    # every downstream asset loop) from config["exchanges"]["kraken"]
    # ["trading_pairs"] (main.py:1241; also strategies/liquidity_model.py:
    # 108) - there is no top-level "trading_pairs" config key read anywhere
    # in the engine, so setting one is dead config. Left at its config.json
    # default (7 pairs incl. PAXG/SUI/ARB/MINA/FLOW) the World venues would
    # silently price every non-ETH pair as BTC (_mark/get_ticker_price's
    # ETH-else-BTC branch), polluting daily_candles/marks for assets this
    # tape was never meant to carry. Pin the actually-consumed key instead.
    cfg["exchanges"]["kraken"]["trading_pairs"] = ["ETH/USD", "BTC/USD"]
    # the replay clock and the world bar clock must advance TOGETHER: one
    # cycle == one bar. main.py derives self.poll_sec from
    # system.polling_interval_sec (main.py:680, default 5s); left at
    # default it would drift out of lockstep with the world's 300s bars
    # over a run (poll_sec is also the cadence data/replay.py's player
    # expects a recording to be replayed at). Pin it to BAR_SEC.
    cfg["system"]["polling_interval_sec"] = BAR_SEC
    return cfg


def record_tape(seed: int, cycles: int, out_dir: Path) -> str:
    """Record one coherent tape by driving the REAL engine over world
    venues (mirrors overfit_check.make_offline_recording's isolation; no
    forced signals - the tape is strategy-neutral)."""
    from main import LiquidityBot
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sink = str(out_dir / f"tape_s{seed}.jsonl")
    Path(sink).unlink(missing_ok=True)

    cfg = _battery_config(cycles)
    cfg["system"]["state_path"] = str(out_dir / f"state_s{seed}.json")

    world = PriceWorld(seed, bars=cycles + CANDLE_WINDOW + 8)
    okx, bnc, krk = WorldOKX(world, "okx"), WorldBinanceUS(world, "binanceus"), \
        WorldKraken(world)
    bot = LiquidityBot(cfg, okx=FeedRecorder(okx, "okx", sink),
                       binanceus=FeedRecorder(bnc, "binanceus", sink),
                       kraken=FeedRecorder(krk, "kraken", sink),
                       resume=False)
    # the replay clock and the world bar clock advance TOGETHER: one
    # cycle == one bar (poll_sec is the recording cadence; data/replay.py
    # requires replaying at the cadence recorded)
    t = world.bar_time(CANDLE_WINDOW)
    for k in range(cycles):
        bar = CANDLE_WINDOW + k
        for v in (okx, bnc, krk):
            v.set_bar(bar)
        bot.cycle_once(t)
        t += bot.poll_sec
    return sink


def tape_coherence(recording_path: str) -> dict:
    """Self-check: the three SEV-1 defects, measured on the tape itself."""
    frames = [json.loads(x) for x in
              Path(recording_path).read_text(encoding="utf-8").splitlines()]
    md = [(i, f) for i, f in enumerate(frames) if f["method"] == "get_market_data"
          and f["feed"] == "okx"]
    end_times, series = [], set()
    for _, f in md:
        c = f["result"]["ETH-USDT-SWAP"]["candles"]
        end_times.append(c[-1]["time"])
        series.add(round(c[-1]["close"], 6))
    ticks = [(i, f) for i, f in enumerate(frames) if f["feed"] == "kraken"
             and f["method"] == "get_tickers" and isinstance(f["result"], dict)]
    gaps = []
    for fi, f in md:
        okx_px = f["result"]["ETH-USDT-SWAP"]["candles"][-1]["close"]
        # Nearest by FILE POSITION, not by the recorder's wall-clock "t":
        # okx/binanceus.get_market_data only fire on slow cycles (every
        # slow_cycle_every_n-th) while kraken.get_tickers fires every fast
        # cycle, so within one recorded session the tick written in the
        # SAME cycle_once call as a given market-data frame is always a
        # few frames away in the file - a fixed, deterministic distance.
        # Matching by "t" = round(time.time(), 3) instead (data/replay.py's
        # FeedRecorder stamp) chases sub-millisecond OS scheduling jitter on
        # a recording loop that logs 100+ frames in a fraction of a second;
        # measured 2026-08-27: 7/20 seeds at cycles=40 pulled in the FOLLOWING
        # cycle's tick that way, reading pure 1-bar GBM drift (up to ~50bps,
        # once within <1bps of this function's own gate) as "venue gap" on a
        # tape whose venues never actually diverge by more than
        # VENUE_NOISE_BPS - the same instrument-before-theory check this
        # repo's CLAUDE.md prescribes for a surprising number. File position
        # is a property of the recorded session itself (order of writes to
        # one shared, serial sink - main.py's _serial_feeds under
        # record_feeds=true), not of how fast this process happened to run.
        _, near = min(ticks, key=lambda g: abs(g[0] - fi), default=(None, None))
        if near:
            kp = next((v for k, v in near["result"].items()
                       if k.startswith(("ETH", "XETH"))), None)
            if kp:
                gaps.append(abs(okx_px / float(kp) - 1.0) * 1e4)
    return {"bar_times_advance": end_times == sorted(end_times)
            and len(set(end_times)) == len(end_times),
            "distinct_series": len(series),
            "max_venue_gap_bps": max(gaps) if gaps else 0.0}


# ---------------------------------------------------------------- archetypes
# Entries ONLY (spec [SEV-5]): every rung exits through the deployed
# machinery; exit_profile="deployed" on every row. Each factory returns a
# FRESH closure so grid anchors / clocks / EMAs never leak across runs.
# The engine may SHADE the confidence downstream — it is an input, not a
# pass-through.
from strategies.signal_gates import SignalResult  # noqa: E402


def _no_signal(asset: str) -> "SignalResult":
    return SignalResult(symbol=f"{asset}/USD", direction=None,
                        confidence=0.0, size=0.0, all_confirmed=False,
                        gates_passed={})


def _sig(asset: str, direction: str, conf: float) -> "SignalResult":
    return SignalResult(symbol=f"{asset}/USD", direction=direction,
                        confidence=conf, size=0.0, all_confirmed=True,
                        gates_passed={"archetype": True})


def _closes(view: dict) -> list:
    return [c["close"] for c in (view.get("candles") or [])]


def _random_entry(seed: int, p_fire: float = 0.06):
    rng = np.random.default_rng(seed * 1009 + 1)

    def fn(asset, view):
        if not _closes(view):
            return _no_signal(asset)
        if rng.random() < p_fire:
            return _sig(asset, "long" if rng.random() < 0.5 else "short", 0.8)
        return _no_signal(asset)
    return fn


def _buy_hold(seed: int):
    fired = set()

    def fn(asset, view):
        if asset in fired or not _closes(view):
            return _no_signal(asset)
        fired.add(asset)
        return _sig(asset, "long", 0.9)
    return fn


def _naive_grid(seed: int, levels: int = 5, spacing_pct: float = 0.8):
    anchors = {}

    def fn(asset, view):
        closes = _closes(view)
        if not closes:
            return _no_signal(asset)
        px = closes[-1]
        if asset not in anchors:
            anchors[asset] = px
            return _no_signal(asset)
        drop_pct = (anchors[asset] - px) / anchors[asset] * 100.0
        rung = int(drop_pct // spacing_pct)
        if 1 <= rung <= levels:
            anchors[asset] = px            # re-arm below the fill (grid-bot)
            return _sig(asset, "long", 0.7)
        return _no_signal(asset)
    return fn


def _clockwork_dca(seed: int, every_n_calls: int = 12):
    calls = {}

    def fn(asset, view):
        if not _closes(view):
            return _no_signal(asset)
        calls[asset] = calls.get(asset, 0) + 1
        if calls[asset] % every_n_calls == 0:
            return _sig(asset, "long", 0.7)
        return _no_signal(asset)
    return fn


def _momentum_chaser(seed: int, k: int = 12):
    def fn(asset, view):
        closes = _closes(view)
        if len(closes) < k + 1:
            return _no_signal(asset)
        ret = closes[-1] / closes[-1 - k] - 1.0
        if abs(ret) < 0.001:
            return _no_signal(asset)
        return _sig(asset, "long" if ret > 0 else "short", 0.75)
    return fn


def _stop_herder(seed: int, proximity_pct: float = 0.25):
    def fn(asset, view):
        closes = _closes(view)
        if not closes:
            return _no_signal(asset)
        px = closes[-1]
        step = 10 ** max(0, len(str(int(px))) - 2)     # 2 leading digits
        dist = abs(px - round(px / step) * step) / px * 100.0
        if dist <= proximity_pct:
            return _sig(asset, "long", 0.7)
        return _no_signal(asset)
    return fn


def _vol_trend(seed: int, fast: int = 8, slow: int = 24,
               max_bar_vol: float = 0.006):
    def _ema(xs, n):
        a = 2.0 / (n + 1.0)
        e = xs[0]
        for x in xs[1:]:
            e = a * x + (1 - a) * e
        return e

    def fn(asset, view):
        closes = _closes(view)
        if len(closes) < slow + 2:
            return _no_signal(asset)
        rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
        vol = float(np.std(rets[-slow:]))
        if vol > max_bar_vol:
            return _no_signal(asset)              # vol gate: stand down
        f, s = _ema(closes[-slow:], fast), _ema(closes[-slow:], slow)
        if abs(f / s - 1.0) < 0.0008:
            return _no_signal(asset)
        return _sig(asset, "long" if f > s else "short", 0.8)
    return fn


ARCHETYPES = {
    "random_entry": _random_entry,
    "buy_hold": _buy_hold,
    "naive_grid": _naive_grid,
    "clockwork_dca": _clockwork_dca,
    "momentum_chaser": _momentum_chaser,
    "stop_herder": _stop_herder,
    "vol_trend": _vol_trend,
    "deployed": None,          # the measured member: no patch
}


def oracle_factory(world: "PriceWorld", horizon_bars: int = 12):
    """Test-only planted edge: reads the world's FUTURE price. Exists so
    the battery's validation can prove the pipeline ranks a real edge
    first (the-method injection obligation). Never in ARCHETYPES."""
    def fn(asset, view):
        closes = _closes(view)
        if not closes:
            return _no_signal(asset)
        px = closes[-1]
        arr = world._px[asset]
        i = int(np.argmin(np.abs(arr - px)))
        fut = world.price(asset, min(i + horizon_bars, world.bars - 1))
        if abs(fut / px - 1.0) < 0.0005:
            return _no_signal(asset)
        return _sig(asset, "long" if fut > px else "short", 0.95)
    return fn
