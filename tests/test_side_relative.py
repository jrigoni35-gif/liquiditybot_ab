"""
Regression for the v2 side-relative feature encoding: signed market-
absolute features are presented in the frame the label lives in
(feature x direction, '+' = with my trade), so the simplicity ladder's
linear baseline can use them without waiting for a tree model to earn
interactions. Pins the exact flip set - and that everything else,
including the already-side-relative fv_edge_bps/mtf_align, does NOT
double-flip - plus the migration derivation for short-side rows.
"""
from types import SimpleNamespace

import numpy as np

from ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, build_features

DIR_FEATURES = {
    "ret_1_dir", "ret_6_dir", "ret_12_dir", "ret_48_dir", "imbalance_dir",
    "basis_dir", "funding_dir", "mom_dir", "sent_dir",
    "imbalance_delta_dir", "other_ret_6_dir", "venue_disloc_dir",
    "pat_engulf_dir", "pat_hammer_dir", "pat_marubozu_dir",
    "mkt_ret_6_dir", "ofi_dir", "basis_mom_dir", "direction",
}


def _vector(direction: str) -> np.ndarray:
    candles = [{"time": 100 + i * 300, "open": 10 + i * 0.1,
                "high": 10.3 + i * 0.1, "low": 9.9 + i * 0.1,
                "close": 10.2 + i * 0.1, "volume": 5.0}
               for i in range(60)]
    view = {"candles": candles, "imbalance_ratio": 1.6,
            "funding_rate": 0.0002, "ofi_event": 0.8}
    fv = SimpleNamespace(edge_bps=lambda side: 7.0, basis_bps=12.0,
                         basis_mom_bps=6.0)
    vol = SimpleNamespace(sigma_bar_pct=0.4, percentile=55.0)
    liq = SimpleNamespace(spread_bps=4.0, depth_top10_usd=250_000.0)
    macro = SimpleNamespace(label="range", momentum_score=0.6,
                            drawdown_pct=20.0)
    sent = SimpleNamespace(score=0.3, fear_spike=False)
    smc = {"mtf_align": 0.8, "pd_zone": 0.4, "liq_pocket_pull": 0.2,
           "fvg_pull": 0.1, "fvg_liq_confluence": 0.0, "poc_dist": 0.3,
           "va_pos": -0.2}
    return build_features("BTC", direction, 0.7, view, fv, vol, liq,
                          macro, None, sent, smc,
                          extras={"ts": 1_700_000_000.0, "fear_greed": 30.0,
                                  "imbalance_delta": 0.5,
                                  "other_ret_6": 1.2, "depth_ratio": 1.1,
                                  "mkt_ret_6": 0.001,
                                  "book_touch_share": 0.35,
                                  "regime_age_sec": 7200.0,
                                  "venue_disloc_bps": 9.0,
                                  "thales": {"grid": 0.4, "metronome": 0.2, "barclose": 0.3,
                                             "clockwork": 0.1,
                                             "stop_zone": 0.7}})


def test_schema_version_current():
    # deliberate re-pin: v10 (2026-09-21) adds the dp_surge_z/dp_vol_z/
    # dp_hhi/avail_dp dark-pool SHADOW block; the v9 shadow pair
    # (ofi_dir/basis_mom_dir ARE in DIR_FEATURES - signed flow/drift,
    # presented with-my-trade like imbalance_dir/basis_dir; the stub
    # carries nonzero ofi_event/basis_mom_bps so the flip test proves it
    # non-vacuously). flow_tox and the whole dp_* block stay in the
    # must-NOT-flip branch (symmetric information; avail_dp is a 0/1
    # availability gauge, not a signed quantity).
    assert FEATURE_SCHEMA_VERSION == 10


def test_flow_tox_is_live_in_the_flip_stub():
    # the NOT-flip branch of the test below only proves something for
    # flow_tox if the stub actually produces a NONZERO value (0 == -0
    # would pass vacuously): the stub's 60 trending candles cover the
    # 48-bar toxicity window and read one-sided, so it is genuinely hot
    x = _vector("long")
    assert x[FEATURE_NAMES.index("flow_tox")] > 0.0


def test_long_short_flip_exactly_the_dir_features():
    x_long = _vector("long")
    x_short = _vector("short")
    for i, name in enumerate(FEATURE_NAMES):
        if name in DIR_FEATURES:
            assert x_long[i] == -x_short[i], (
                f"{name} must flip with direction")
        else:
            assert x_long[i] == x_short[i], (
                f"{name} must NOT depend on direction (double-flip?)")


def test_dir_features_positive_means_with_the_trade():
    x_long = _vector("long")
    idx = {n: i for i, n in enumerate(FEATURE_NAMES)}
    # rising closes + bid-heavy book + positive momentum, long side:
    # every side-relative signal reads "with my trade"
    assert x_long[idx["ret_6_dir"]] > 0
    assert x_long[idx["imbalance_dir"]] > 0
    assert x_long[idx["mom_dir"]] > 0
    assert x_long[idx["direction"]] == 1.0


def test_migration_derives_short_side_correctly(tmp_path):
    import csv
    from scripts.migrate_history import migrate_rows
    header = ["position_id", "asset", "side", "ret_6", "direction",
              "gate_confidence", "label", "net_pnl_usd", "source", "ts"]
    src = tmp_path / "old.csv"
    with open(src, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(["p1", "BTC", "short", "0.500000", "-1.000000",
                    "0.700000", "1", "2.00", "live", "1700000000"])
    rows, padded = migrate_rows(str(src))
    got = float(rows[0][3 + FEATURE_NAMES.index("ret_6_dir")])
    assert got == -0.5                    # absolute 0.5 x short = -0.5
    assert "ret_6_dir" not in padded
