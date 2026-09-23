"""
Regression for the v7 feature trio (58->61): vol_term (realized-vol term
structure - the DERIVATIVE of vol that level+percentile cannot see),
mkt_ret_6_dir (equal-weight market-factor drift with the trade - separates
"my asset moving" from "everything moving"), and book_touch_share (depth
concentration at the touch - book SHAPE, invisible to imbalance/depth_log).
Pins the schema geometry (trio before the direction/gate_confidence tail),
the neutral defaults (0.0 / 0.0 / 0.2 flat-book), the contract ranges, and
the migration padding for pre-v7 bundles.
"""
import csv
from types import SimpleNamespace

import numpy as np

from main import LiquidityBot
from ml.contracts import _RANGES, get_contract
from ml.features import (FEATURE_NAMES, FEATURE_SCHEMA_VERSION,
                         TRIO_NEUTRAL, _vol_term, build_features)

IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}


# ---------------------------------------------------------------- helpers
def _closes(returns) -> np.ndarray:
    px = [100.0]
    for r in returns:
        px.append(px[-1] * float(np.exp(r)))
    return np.array(px)


def _vector(direction: str, extras_overrides=None) -> np.ndarray:
    """test_side_relative's stub scaffold, extended with trio extras."""
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
    extras = {"ts": 1_700_000_000.0}
    extras.update(extras_overrides or {})
    return build_features("BTC", direction, 0.7, view, fv, vol, liq,
                          macro, None, sent, {}, extras=extras)


def _shell_bot(view: dict, books: dict) -> LiquidityBot:
    """LiquidityBot shell with only the fields _feature_extras reads -
    same pattern as test_exploration's _stub_bot (no engine graph)."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.view = view
    b.kraken_books = books
    b._last_imb = {}
    b._regime_since = {}
    b._manip_scores = {}
    b._wl_p95, b._wl_thr = 1.27, 1.45
    b.liq = SimpleNamespace(state=lambda a: SimpleNamespace(
        spoof_score=0.0, imbalance_whiplash=0.0, depth_ratio=1.0))
    b.thales = SimpleNamespace(feature_scores=lambda a, now: {})
    return b


def _extras(bot, asset="BTC"):
    web = SimpleNamespace(fear_greed=50.0, dominance_delta=0.0)
    risk = SimpleNamespace(risk_z=0.0, opt_pcr_z=0.0, opt_oi_pcr_z=0.0,
                           opt_iv_skew=0.0)
    return bot._feature_extras(asset, bot.view.get(asset) or {}, web,
                               risk, None, 1_700_000_000.0)


def _candles(rets):
    return [{"close": c, "open": c, "high": c, "low": c, "volume": 1.0}
            for c in _closes(rets)]


# ------------------------------------------------------------ schema pins
def test_schema_is_68_wide_v10_trio_before_signal_tail():
    # deliberate re-pin: v8 adds flow_tox after the trio (61->62, 7->8);
    # v9 adds the ofi_dir/basis_mom_dir shadow pair (62->64, 8->9);
    # v10 adds the dp_* dark-pool SHADOW block (64->68, 9->10)
    assert len(FEATURE_NAMES) == 68
    assert FEATURE_SCHEMA_VERSION == 10
    assert FEATURE_NAMES[-12:] == ["vol_term", "mkt_ret_6_dir",
                                   "book_touch_share", "flow_tox",
                                   "ofi_dir", "basis_mom_dir",
                                   "dp_surge_z", "dp_vol_z", "dp_hhi",
                                   "avail_dp",
                                   "direction", "gate_confidence"]


def test_contract_declares_ranges_and_accepts_a_built_vector():
    assert _RANGES["vol_term"] == (-2, 2)
    assert _RANGES["mkt_ret_6_dir"] == (-3, 3)
    assert _RANGES["book_touch_share"] == (0, 1)
    ok, reasons = get_contract().check(
        _vector("long", {"mkt_ret_6": 0.001, "book_touch_share": 0.35}))
    assert ok, reasons


# --------------------------------------------------------------- vol_term
def test_vol_term_expanding_positive_compressing_negative():
    quiet = [0.0002 * (-1) ** i for i in range(96)]
    violent = [0.01 * (-1) ** i for i in range(12)]
    assert _vol_term(_closes(quiet[:84] + violent)) > 0     # expansion
    assert _vol_term(_closes(violent + quiet[:84])) < 0     # compression


def test_vol_term_neutral_on_short_or_degenerate_history():
    assert _vol_term(_closes([0.01] * 40)) == 0.0           # <97 closes
    assert _vol_term(np.full(120, 100.0)) == 0.0            # sigma_long == 0
    assert _vol_term(np.array([0.0])) == 0.0                # empty view stub


def test_vol_term_flows_through_build_features_clipped():
    x = _vector("long")
    assert -2.0 <= x[IDX["vol_term"]] <= 2.0
    # NOT direction-signed: term structure is symmetric information
    assert x[IDX["vol_term"]] == _vector("short")[IDX["vol_term"]]


# ---------------------------------------------------------- mkt_ret_6_dir
def test_market_drift_signed_with_the_trade():
    up = {"mkt_ret_6": 0.002}
    assert _vector("long", up)[IDX["mkt_ret_6_dir"]] > 0    # market with me
    assert _vector("short", up)[IDX["mkt_ret_6_dir"]] < 0   # market against
    assert _vector("long")[IDX["mkt_ret_6_dir"]] == 0.0     # missing extra


def test_extras_mkt_ret_6_equal_weight_mean_skips_short_history():
    up = _candles([0.001] * 8)          # ln(c[-1]/c[-7]) = +0.006
    dn = _candles([-0.001] * 8)         # ln(c[-1]/c[-7]) = -0.006
    stub = [{"close": 100.0}] * 3       # <7 candles: dropped, not counted
    bot = _shell_bot({"BTC": {"candles": up, "imbalance_ratio": 1.0},
                      "ETH": {"candles": dn, "imbalance_ratio": 1.0},
                      "SOL": {"candles": stub, "imbalance_ratio": 1.0}}, {})
    ex = _extras(bot)
    assert abs(ex["mkt_ret_6"] - 0.0) < 1e-9    # +0.006 and -0.006 average out
    bot2 = _shell_bot({"BTC": {"candles": up, "imbalance_ratio": 1.0}}, {})
    assert abs(_extras(bot2)["mkt_ret_6"] - 0.006) < 1e-9


def test_extras_mkt_ret_6_neutral_with_no_usable_candles():
    bot = _shell_bot({"BTC": {"imbalance_ratio": 1.0}}, {})
    assert _extras(bot)["mkt_ret_6"] == 0.0


# ------------------------------------------------------- book_touch_share
def _book(bid_sizes, ask_sizes, px=100.0):
    return {"bids": [[px - 0.01 * (i + 1), s]
                     for i, s in enumerate(bid_sizes)],
            "asks": [[px + 0.01 * (i + 1), s]
                     for i, s in enumerate(ask_sizes)]}


def test_touch_share_flat_book_near_02_concentrated_near_1():
    flat = _book([5.0] * 10, [5.0] * 10)
    bot = _shell_bot({"BTC": {"imbalance_ratio": 1.0}}, {"BTC": flat})
    assert abs(_extras(bot)["book_touch_share"] - 0.2) < 0.01
    touchy = _book([100.0] + [0.001] * 9, [100.0] + [0.001] * 9)
    bot2 = _shell_bot({"BTC": {"imbalance_ratio": 1.0}}, {"BTC": touchy})
    assert _extras(bot2)["book_touch_share"] > 0.99


def test_touch_share_neutral_on_missing_or_one_sided_book():
    bot = _shell_bot({"BTC": {"imbalance_ratio": 1.0}}, {})   # no book
    assert _extras(bot)["book_touch_share"] == 0.2
    one_sided = {"bids": [[99.9, 5.0]], "asks": []}
    bot2 = _shell_bot({"BTC": {"imbalance_ratio": 1.0}},
                      {"BTC": one_sided})
    assert _extras(bot2)["book_touch_share"] == 0.2
    # builder default when the extra never arrives: same neutral, clipped
    assert _vector("long")[IDX["book_touch_share"]] == 0.2


def test_touch_share_clipped_to_unit_interval_in_builder():
    x = _vector("long", {"book_touch_share": 7.3})   # garbage upstream
    assert x[IDX["book_touch_share"]] == 1.0


# -------------------------------------------------------------- migration
def test_migrate_pads_pre_v7_rows_with_documented_neutrals(tmp_path):
    from scripts.migrate_history import KNOWN_NEUTRAL, migrate_rows
    assert TRIO_NEUTRAL == {"vol_term": 0.0, "mkt_ret_6_dir": 0.0,
                            "book_touch_share": 0.2}
    for k, v in TRIO_NEUTRAL.items():
        assert KNOWN_NEUTRAL.get(k) == v
    header = ["position_id", "asset", "side", "ret_6", "direction",
              "gate_confidence", "label", "net_pnl_usd", "source", "ts"]
    src = tmp_path / "old.csv"
    with open(src, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(["p1", "BTC", "long", "0.500000", "1.000000",
                    "0.700000", "1", "2.00", "live", "1700000000"])
    rows, padded = migrate_rows(str(src))
    for name in ("vol_term", "mkt_ret_6_dir", "book_touch_share"):
        assert name in padded
        got = float(rows[0][3 + FEATURE_NAMES.index(name)])
        assert got == TRIO_NEUTRAL[name]
