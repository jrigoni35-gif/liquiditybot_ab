"""v8 anti-predation batch - literature-grounded defenses, each pinned:

flow_tox        VPIN-lite Bulk-Volume-Classification toxicity (Easley/
                Lopez de Prado/O'Hara 2012): one-sided informed/predatory
                flow reads high, balanced two-way flow reads ~0; NOT
                direction-signed (toxic flow hurts whichever side provides
                liquidity). Degenerate inputs -> 0.0 = TOX_NEUTRAL.
decay imbalance distance-decayed book imbalance (Stoikov 2018 near-touch
                information; spoof economics: far size is cheap to paint
                and cancel - layering - while touch size gets executed).
                A painted far wall must NOT drag the ratio; decay 0 must
                be byte-identical legacy; regime + model sites must agree.
magnet stops    Osler 2003/2005: stops cluster just past round numbers
                and sweep wicks overshoot-then-revert; a trailing stop
                inside that band gets tagged by a pure hunt. The nudge
                moves a candidate band_bps BEYOND the level, always AWAY
                from price (ratchet can never loosen), never touches the
                break-even floor, and band 0 is a byte-identical no-op.
venue candles   wash-trading hygiene (Cong-Li-Tang-Yang 2023: >70% of
                reported volume on unregulated venues is fabricated):
                execution-venue bars ground every mapped asset's candles
                when long enough, throttled, never degrading windows and
                never losing availability on fetch failure.
migration       pre-v8 rows pad flow_tox with its documented 0.0 neutral.
"""
from types import SimpleNamespace

import numpy as np

from core.state import Position
from ml.features import (FEATURE_NAMES, FEATURE_SCHEMA_VERSION, TOX_NEUTRAL,
                         _flow_toxicity, build_features)
from regime.liquidity_regime import LiquidityRegimeEngine, _imbalance
from risk.profit_tiers import ProfitTierEngine
from strategies.liquidity_model import LiquidityModel

IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}


# ------------------------------------------------------------ schema pins
def test_schema_is_68_wide_v10_flow_tox_before_shadow_blocks():
    # deliberate re-pin: v9 adds the ofi_dir/basis_mom_dir shadow pair
    # after flow_tox (62->64, version 8->9; tests/test_ofi_feature.py);
    # v10 adds the dp_* dark-pool SHADOW block after that (64->68, 9->10)
    assert len(FEATURE_NAMES) == 68
    assert FEATURE_SCHEMA_VERSION == 10
    assert FEATURE_NAMES[-12:] == ["vol_term", "mkt_ret_6_dir",
                                   "book_touch_share", "flow_tox",
                                   "ofi_dir", "basis_mom_dir",
                                   "dp_surge_z", "dp_vol_z", "dp_hhi",
                                   "avail_dp",
                                   "direction", "gate_confidence"]
    assert TOX_NEUTRAL == {"flow_tox": 0.0}


def test_contract_declares_flow_tox_range():
    from ml.contracts import _RANGES
    assert _RANGES["flow_tox"] == (0, 1)


# --------------------------------------------------------------- flow_tox
def _px(rets, p0=100.0):
    px = [p0]
    for r in rets:
        px.append(px[-1] * float(np.exp(r)))
    return np.array(px)


def test_one_sided_heavy_flow_reads_toxic():
    # 48 bars all +3 sigma with live volume: BVC buy_frac ~ Phi(3) ~ 0.999
    # per bar -> volume-weighted |2f-1| ~ 1 (the flow that adversely
    # selects a liquidity provider)
    closes = _px([0.015] * 48)
    vols = np.full(48, 10.0)
    assert _flow_toxicity(closes, vols, 0.005) > 0.9


def test_balanced_alternating_flow_reads_near_zero():
    # alternating +-0.1 sigma bars: every bar is ~50/50 two-way flow, the
    # definition of benign - toxicity must sit near 0, NOT read the churn
    # as one-sided (this is what separates BVC from a plain |return| sum)
    closes = _px([0.0005 * (-1) ** i for i in range(48)])
    vols = np.full(48, 10.0)
    assert _flow_toxicity(closes, vols, 0.005) < 0.1


def test_degenerate_inputs_return_the_documented_neutral():
    ok = _px([0.015] * 48)
    assert _flow_toxicity(_px([0.01] * 30), np.full(30, 5.0), 0.005) == 0.0
    assert _flow_toxicity(ok, np.zeros(48), 0.005) == 0.0     # dead volume
    assert _flow_toxicity(ok, np.full(48, 10.0), 0.0) == 0.0  # dead sigma
    assert _flow_toxicity(np.array([0.0]), np.array([0.0]), 0.005) == 0.0


def _vector(direction: str) -> np.ndarray:
    """test_side_relative's stub scaffold: 60 trending candles cover the
    48-bar toxicity window with one-sided bars, so flow_tox is HOT."""
    candles = [{"time": 100 + i * 300, "open": 10 + i * 0.1,
                "high": 10.3 + i * 0.1, "low": 9.9 + i * 0.1,
                "close": 10.2 + i * 0.1, "volume": 5.0}
               for i in range(60)]
    view = {"candles": candles, "imbalance_ratio": 1.6,
            "funding_rate": 0.0002}
    fv = SimpleNamespace(edge_bps=lambda side: 7.0, basis_bps=12.0)
    vol = SimpleNamespace(sigma_bar_pct=0.4, percentile=55.0)
    liq = SimpleNamespace(spread_bps=4.0, depth_top10_usd=250_000.0)
    macro = SimpleNamespace(label="range", momentum_score=0.6,
                            drawdown_pct=20.0)
    sent = SimpleNamespace(score=0.3, fear_spike=False)
    return build_features("BTC", direction, 0.7, view, fv, vol, liq,
                          macro, None, sent, {},
                          extras={"ts": 1_700_000_000.0})


def test_flow_tox_flows_through_build_features_clipped_and_unsigned():
    x_long, x_short = _vector("long"), _vector("short")
    i = IDX["flow_tox"]
    assert 0.0 < x_long[i] <= 1.0
    # symmetric information: identical for both trade sides (no dir_sign)
    assert x_long[i] == x_short[i]


# ------------------------------------------------------- decay imbalance
def _book(painted_far_bid=0.0):
    """10-level flat book, levels 10bps apart; optional painted wall at
    the FARTHEST bid level (90bps from the touch - classic layering)."""
    bids = [[100.0 - 0.1 * i, 1.0] for i in range(10)]
    asks = [[100.1 + 0.1 * i, 1.0] for i in range(10)]
    if painted_far_bid:
        bids[9][1] = painted_far_bid
    return {"bids": bids, "asks": asks}


def test_painted_far_wall_inflates_legacy_but_not_decayed_ratio():
    painted = _book(painted_far_bid=50.0)
    assert _imbalance(painted) == 3.0                  # legacy: clamp ceiling
    decayed = _imbalance(painted, decay_bps=15.0)
    assert decayed < 1.2                               # near the flat book
    assert abs(decayed - _imbalance(_book(), decay_bps=15.0)) < 0.15


def test_decay_zero_is_byte_identical_legacy():
    for book in (_book(), _book(painted_far_bid=50.0)):
        b = sum(p * s for p, s in book["bids"][:10])
        a = sum(p * s for p, s in book["asks"][:10])
        legacy = min(b / a, 3.0)
        assert _imbalance(book) == legacy
        assert _imbalance(book, decay_bps=0.0) == legacy


def test_fallbacks_survive_decay():
    assert _imbalance({"bids": [[100.0, 1.0]], "asks": []},
                      decay_bps=15.0) == 3.0
    assert _imbalance({}, decay_bps=15.0) == 1.0
    lm = LiquidityModel({})
    assert lm._imbalance_ratio({"bids": [[100.0, 1.0]], "asks": []},
                               decay_bps=15.0) == 5.0
    assert lm._imbalance_ratio({}, decay_bps=15.0) == 1.0


def test_regime_and_model_sites_compute_the_same_decay():
    # identical math either side of the module boundary (clamps differ but
    # are inactive on a moderate book): one knob, one behavior
    lm = LiquidityModel({})
    book = _book(painted_far_bid=2.0)
    assert abs(_imbalance(book, decay_bps=15.0)
               - lm._imbalance_ratio(book, decay_bps=15.0)) < 1e-12


def test_decay_knob_single_source_of_truth():
    assert LiquidityRegimeEngine({}).imbalance_decay_bps == 15.0
    assert LiquidityRegimeEngine(
        {"imbalance_decay_bps": 0.0}).imbalance_decay_bps == 0.0
    assert LiquidityModel({}).imbalance_decay_bps == 15.0
    assert LiquidityModel({"liquidity_regime":
                           {"imbalance_decay_bps": 40.0}}
                          ).imbalance_decay_bps == 40.0


def test_build_view_applies_the_decay():
    payload = {"ETH-USDT-SWAP": {"order_book": _book(painted_far_bid=50.0),
                                 "candles": [], "funding_rate": 0.0,
                                 "volume_24h": 1.0}}
    on = LiquidityModel({}).build_view(payload)             # decay 15 default
    off = LiquidityModel({"liquidity_regime":
                          {"imbalance_decay_bps": 0.0}}).build_view(payload)
    assert off["ETH"]["imbalance_ratio"] == 5.0             # legacy: cap
    assert on["ETH"]["imbalance_ratio"] < 1.2               # wall decayed out


# ----------------------------------------------------------- magnet stops
def _pos(entry, direction="long", tier_closed=0):
    from datetime import datetime, timezone
    p = Position(position_id="p1", symbol="BTC/USD", direction=direction,
                 entry_price=entry, size=1.0, original_size=1.0,
                 opened_at=datetime.now(timezone.utc))
    p.tier_closed = tier_closed
    return p


def _eng(**cfg):
    return ProfitTierEngine({"stop_magnet": {"band_bps": 25.0}, **cfg})


def test_grid_auto_scales_across_price_magnitudes():
    g = ProfitTierEngine._magnet_grid
    assert g(118432.0) == 1000.0        # BTC
    assert g(3600.0) == 100.0           # ETH
    assert g(180.0) == 1.0              # SOL
    assert g(0.45) == 0.01              # ADA (sub-$1)


def test_long_stop_just_under_round_level_pushed_below_the_band():
    # a stop 0.4bps under 118000 sits exactly where the sweep wick tags it;
    # nudged to 25bps BELOW the level (wider = away from price)
    adj = _eng()._magnet_adjust("long", 117995.0)
    assert abs(adj - 118000.0 * (1 - 0.0025)) < 1e-6
    assert adj < 117995.0


def test_far_stop_unchanged():
    assert _eng()._magnet_adjust("long", 117500.0) == 117500.0


def test_short_mirror_pushed_above_the_band():
    adj = _eng()._magnet_adjust("short", 118005.0)
    assert abs(adj - 118000.0 * (1 + 0.0025)) < 1e-6
    assert adj > 118005.0


def test_sub_dollar_magnet_uses_the_scaled_grid():
    adj = _eng()._magnet_adjust("long", 0.4495)
    assert abs(adj - 0.45 * (1 - 0.0025)) < 1e-12


def test_band_zero_is_a_byte_identical_no_op():
    bare = ProfitTierEngine({})                    # legacy config: magnet OFF
    assert bare.mg_band_bps == 0.0
    assert bare._magnet_adjust("long", 117995.0) == 117995.0
    p = _pos(100000.0)
    bare._ratchet_stop(p, 117995.0)                # default magnet=True path
    assert p.trailing_stop_price == 117995.0


def test_ratchet_never_loosens_through_a_magnet_nudge():
    eng = _eng()
    p = _pos(100000.0)
    p.trailing_stop_price = 117800.0
    eng._ratchet_stop(p, 117900.0)     # nudged to 117705 = looser -> held
    assert p.trailing_stop_price == 117800.0


def test_chandelier_trail_site_is_magnet_adjusted():
    eng = ProfitTierEngine({"stop_magnet": {"band_bps": 25.0},
                            "trailing_stop": {"enabled": True,
                                              "activate_after_tier": 0,
                                              "trail_pct": 1.0},
                            "be_after_tier": 99})
    p = _pos(100000.0)
    # hw 119190 -> 1% trail candidate 117998.1, 0.16bps under 118000:
    # inside the hunt band -> nudged to 25bps below the level
    act = eng.evaluate(p, 119190.0)
    assert not act.should_close_partial
    assert abs(p.trailing_stop_price - 118000.0 * (1 - 0.0025)) < 1e-6


def test_break_even_floor_is_never_magnet_adjusted():
    # BE contract: lock entry + fees + buffer EXACTLY. be_px 999.5994 sits
    # 4bps under the 1000 magnet - a nudge would park it at 997.5, BELOW
    # breakeven, betraying the floor. The BE call site passes magnet=False.
    eng = ProfitTierEngine({"stop_magnet": {"band_bps": 25.0},
                            "est_fee_bps": 0.0, "be_buffer_bps": 6.0,
                            "be_after_tier": 1})
    p = _pos(999.0, tier_closed=1)
    eng.evaluate(p, 1005.0)                        # price well clear of BE
    assert abs(p.trailing_stop_price - 999.0 * 1.0006) < 1e-9


# --------------------------------------------------------- venue candles
def _kr_stub(candles_by_pair, fail=False):
    calls = {"n": 0}

    def get_candles(pair):
        calls["n"] += 1
        if fail:
            raise RuntimeError("kraken REST down")
        return candles_by_pair.get(pair, [])
    return SimpleNamespace(kraken_pair=lambda s: s.replace("/", ""),
                           get_candles=get_candles, calls=calls)


def _cbot(view, symbol_map, kraken, cache=None, refresh=150.0):
    return SimpleNamespace(view=view, symbol_map=symbol_map, kraken=kraken,
                           kraken_books={}, _kr_candles=cache or {},
                           _kr_candle_refresh_sec=refresh)


def _bars(n, close=100.0):
    return [{"time": i * 300, "open": close, "high": close, "low": close,
             "close": close, "volume": 1.0} for i in range(n)]


def _augment(bot, now):
    from main import LiquidityBot
    LiquidityBot._augment_view_with_kraken(bot, now)  # type: ignore[arg-type]


def test_kraken_replaces_external_when_covering_the_builder_window():
    # 97 = the longest feature window (vol_term); shorter external history
    # is irrelevant once the venue bars cover every builder window
    bot = _cbot({"ETH": {"candles": _bars(200), "imbalance_ratio": 1.1}},
                {"ETH": "ETH/USD"}, _kr_stub({"ETHUSD": _bars(97, 99.0)}))
    _augment(bot, 1_000.0)
    assert len(bot.view["ETH"]["candles"]) == 97
    assert bot.view["ETH"]["candles"][0]["close"] == 99.0
    assert bot.view["ETH"]["imbalance_ratio"] == 1.1        # books untouched


def test_short_kraken_history_keeps_external():
    bot = _cbot({"ETH": {"candles": _bars(50)}}, {"ETH": "ETH/USD"},
                _kr_stub({"ETHUSD": _bars(40, 99.0)}))
    _augment(bot, 1_000.0)
    assert len(bot.view["ETH"]["candles"]) == 50            # never degrade


def test_fetch_failure_keeps_external_candles():
    ext = _bars(50)
    bot = _cbot({"ETH": {"candles": ext}}, {"ETH": "ETH/USD"},
                _kr_stub({}, fail=True))
    _augment(bot, 1_000.0)                                  # must not raise
    assert bot.view["ETH"]["candles"] is ext                # availability


def test_at_most_three_fetches_per_cycle_most_stale_first():
    assets = {a: f"{a}/USD" for a in ("ETH", "BTC", "SUI", "ARB", "MINA")}
    kr = _kr_stub({f"{a}USD": _bars(97) for a in assets})
    # ALL FIVE are past the cadence, but ETH/BTC (age 300s) are fresher
    # than the three never-fetched assets (age 1000s): the 3-slot REST
    # budget must go to the most stale, and ETH/BTC must wait their turn
    cache = {"ETH": (700.0, _bars(97)), "BTC": (700.0, _bars(97))}
    bot = _cbot({}, assets, kr, cache=cache)
    _augment(bot, 1_000.0)
    assert kr.calls["n"] == 3
    assert all(bot._kr_candles[a][0] == 1_000.0
               for a in ("SUI", "ARB", "MINA"))
    assert bot._kr_candles["ETH"][0] == 700.0       # not refreshed this cycle


def test_refresh_throttle_honored_via_injected_now():
    kr = _kr_stub({"ETHUSD": _bars(97)})
    bot = _cbot({}, {"ETH": "ETH/USD"}, kr)
    _augment(bot, 1_000.0)
    assert kr.calls["n"] == 1
    _augment(bot, 1_010.0)                     # 10s later: inside cadence
    assert kr.calls["n"] == 1
    _augment(bot, 1_151.0)                     # past 150s: refresh again
    assert kr.calls["n"] == 2


def test_stale_cache_falls_back_to_external():
    # a persistently-failing fetch must not freeze features on the last
    # good frame (DL-10 class): past 3x the cadence the cache is ABSENT
    kr = _kr_stub({}, fail=True)
    ext = _bars(50)
    bot = _cbot({"ETH": {"candles": ext}}, {"ETH": "ETH/USD"},
                cache={"ETH": (1_000.0, _bars(97, 99.0))}, kraken=kr)
    _augment(bot, 1_100.0)                     # fresh cache still serves
    assert bot.view["ETH"]["candles"][0]["close"] == 99.0
    bot.view = {"ETH": {"candles": ext}}
    _augment(bot, 1_000.0 + 3 * 150.0 + 1.0)   # fence crossed -> external
    assert bot.view["ETH"]["candles"] is ext


# -------------------------------------------------------------- migration
def test_migration_pads_flow_tox_with_its_neutral(tmp_path):
    import csv

    from scripts.migrate_history import migrate_rows
    header = ["position_id", "asset", "side", "ret_6", "direction",
              "gate_confidence", "label", "net_pnl_usd", "source", "ts"]
    src = tmp_path / "old.csv"
    with open(src, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(["p1", "BTC", "long", "0.5", "1.0", "0.7", "1", "2.0",
                    "live", "1700000000"])
    rows, padded = migrate_rows(str(src))
    assert "flow_tox" in padded
    # documented neutral (TOX_NEUTRAL), not a bare unexplained zero
    assert rows[0][3 + FEATURE_NAMES.index("flow_tox")] == "0.000000"


# ------------------------------------------------------------ config guard
def test_guard_bounds_for_the_v8_knobs():
    from core.config_guard import validate

    def fatals(cfg):
        return [m for s, m in validate(cfg) if s == "FATAL"]

    base = {"system": {"dry_run": True}}
    ok = {**base, "profit_taking": {"stop_magnet": {"band_bps": 25.0}},
          "liquidity_regime": {"imbalance_decay_bps": 15.0},
          "exchanges": {"kraken": {"candle_refresh_sec": 150}}}
    assert not any("stop_magnet" in m or "imbalance_decay" in m
                   or "candle_refresh" in m for m in fatals(ok))
    assert any("stop_magnet" in m for m in fatals(
        {**base, "profit_taking": {"stop_magnet": {"band_bps": 101.0}}}))
    assert any("stop_magnet" in m for m in fatals(
        {**base, "profit_taking": {"stop_magnet": {"band_bps": -1.0}}}))
    assert any("imbalance_decay" in m for m in fatals(
        {**base, "liquidity_regime": {"imbalance_decay_bps": 250.0}}))
    assert any("candle_refresh" in m for m in fatals(
        {**base, "exchanges": {"kraken": {"candle_refresh_sec": 10}}}))
    assert any("candle_refresh" in m for m in fatals(
        {**base, "exchanges": {"kraken": {"candle_refresh_sec": 700}}}))
