"""TANK quant-2 Task 2 (K): event-based best-level OFI shadow feature.

The snapshot `imbalance_ratio` sees the book's STANDING size; the event
OFI (Cont-Kukanov-Stoikov 2014, J. Financial Econometrics 12(1):47-88)
sees its CHANGES - who is adding, cancelling, and stepping. Per poll
pair, per venue:

    e_n = 1{Pb_n>=Pb_n-1}*qb_n - 1{Pb_n<=Pb_n-1}*qb_n-1
        - 1{Pa_n<=Pa_n-1}*qa_n + 1{Pa_n>=Pa_n-1}*qa_n-1

normalized by that venue's OWN rolling (EWMA) best-level depth so
cross-venue size units (OKX contracts vs spot coins) never mix, divided
by the REAL wall-clock poll gap dt (THALES A-3: per-event units alias
with poll cadence) and scaled x60 = touch-depth turnover per minute,
then wall-time EWMA'd (alpha = 1-exp(-dt/tau)).

Sections:
  1. CKS event sign correctness on hand-built poll pairs
  2. view-build integration (build_view carries `ofi_event`)
  3. wall-time discipline: cadence invariance + staleness reset
  4. build_features wiring (ofi_dir: side-relative, clipped, NaN-safe)
  5. schema v9 pins + v8 pad-migration + explicit v8-row LOAD
  6. shadow purity: repo-grep proof no gate/sizer/exit/execution module
     reads the new keys (tests/test_bracket_divergence.py's walker idiom)
"""
import csv
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from ml.features import (FEATURE_NAMES, FEATURE_SCHEMA_VERSION, V9_NEUTRAL,
                         build_features)
from strategies.liquidity_model import LiquidityModel, _ofi_event

ROOT = Path(__file__).resolve().parents[1]
IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}


# ---------------------------------------------------------------- helpers
def _payload(pb, qb, pa, qa, symbol="ETH-USDT-SWAP"):
    return {symbol: {"order_book": {"bids": [[pb, qb]], "asks": [[pa, qa]]},
                     "candles": [], "funding_rate": 0.0, "volume_24h": 1.0}}


def _run_polls(polls, lm=None):
    """polls = [(now, (pb, qb, pa, qa)), ...] -> last ofi_event."""
    lm = lm or LiquidityModel({})
    out = 0.0
    for now, args in polls:
        view = lm.build_view(_payload(*args), now=now)
        out = view["ETH"]["ofi_event"]
    return out


# --------------------------------------------- 1. CKS event sign (unit)
# prev/cur tuples are (Pb, qb, Pa, qa)
def test_bid_size_add_is_positive():
    assert _ofi_event((100.0, 5.0, 100.1, 5.0),
                      (100.0, 8.0, 100.1, 5.0)) == pytest.approx(3.0)


def test_bid_cancel_is_negative():
    assert _ofi_event((100.0, 5.0, 100.1, 5.0),
                      (100.0, 2.0, 100.1, 5.0)) == pytest.approx(-3.0)


def test_ask_size_add_is_negative():
    assert _ofi_event((100.0, 5.0, 100.1, 5.0),
                      (100.0, 5.0, 100.1, 8.0)) == pytest.approx(-3.0)


def test_ask_cancel_is_positive():
    assert _ofi_event((100.0, 5.0, 100.1, 5.0),
                      (100.0, 5.0, 100.1, 2.0)) == pytest.approx(3.0)


def test_bid_price_up_counts_full_new_best():
    # Pb_n > Pb_n-1: only the 1{Pb_n>=Pb_n-1}*qb_n term fires (CKS eq. 4)
    assert _ofi_event((100.0, 5.0, 100.2, 5.0),
                      (100.1, 4.0, 100.2, 5.0)) == pytest.approx(4.0)


def test_bid_price_down_counts_lost_prior_best():
    # Pb_n < Pb_n-1: only -1{Pb_n<=Pb_n-1}*qb_n-1 fires
    assert _ofi_event((100.0, 5.0, 100.2, 5.0),
                      (99.9, 7.0, 100.2, 5.0)) == pytest.approx(-5.0)


def test_ask_price_down_is_sell_pressure():
    # Pa_n < Pa_n-1: only -1{Pa_n<=Pa_n-1}*qa_n fires
    assert _ofi_event((100.0, 5.0, 100.2, 5.0),
                      (100.0, 5.0, 100.1, 6.0)) == pytest.approx(-6.0)


def test_ask_price_up_is_receding_sell_pressure():
    # Pa_n > Pa_n-1: only +1{Pa_n>=Pa_n-1}*qa_n-1 fires
    assert _ofi_event((100.0, 5.0, 100.2, 5.0),
                      (100.0, 5.0, 100.3, 6.0)) == pytest.approx(5.0)


def test_unchanged_book_is_zero():
    assert _ofi_event((100.0, 5.0, 100.2, 5.0),
                      (100.0, 5.0, 100.2, 5.0)) == 0.0


def test_both_prices_step_up_is_double_buy_pressure():
    # rising ladder: +qb_n (bid up) + qa_n-1 (ask receding) - the exact
    # cadence-invariance driver used in section 3
    assert _ofi_event((100.0, 5.0, 100.2, 5.0),
                      (100.1, 5.0, 100.3, 5.0)) == pytest.approx(10.0)


# ------------------------------------------ 2. view-build integration
def test_build_view_carries_positive_ofi_on_bid_add():
    ofi = _run_polls([(0.0, (100.0, 5.0, 100.1, 5.0)),
                      (30.0, (100.0, 8.0, 100.1, 5.0))])
    assert ofi > 0.0


def test_build_view_carries_negative_ofi_on_ask_add():
    ofi = _run_polls([(0.0, (100.0, 5.0, 100.1, 5.0)),
                      (30.0, (100.0, 5.0, 100.1, 8.0))])
    assert ofi < 0.0


def test_first_poll_is_neutral_zero():
    assert _run_polls([(0.0, (100.0, 5.0, 100.1, 5.0))]) == 0.0


def test_build_view_without_now_still_works():
    # legacy callers (tests/offline tools) pass no now: wall-clock is
    # used, nothing crashes, the value stays finite
    lm = LiquidityModel({})
    v1 = lm.build_view(_payload(100.0, 5.0, 100.1, 5.0))
    v2 = lm.build_view(_payload(100.0, 8.0, 100.1, 5.0))
    assert math.isfinite(v1["ETH"]["ofi_event"])
    assert math.isfinite(v2["ETH"]["ofi_event"])


def test_deterministic_under_injected_now():
    polls = [(0.0, (100.0, 5.0, 100.1, 5.0)),
             (30.0, (100.0, 9.0, 100.1, 4.0)),
             (60.0, (100.1, 3.0, 100.2, 6.0))]
    assert _run_polls(polls) == _run_polls(polls)


def test_missing_or_one_sided_book_is_nan_safe():
    lm = LiquidityModel({})
    lm.build_view(_payload(100.0, 5.0, 100.1, 5.0), now=0.0)
    # one-sided book: no event, no crash, value decays toward 0
    payload = {"ETH-USDT-SWAP": {"order_book": {"bids": [[100.0, 5.0]],
                                                "asks": []},
                                 "candles": [], "funding_rate": 0.0,
                                 "volume_24h": 1.0}}
    v = lm.build_view(payload, now=30.0)
    assert v["ETH"]["ofi_event"] == 0.0
    # book vanished entirely -> still present, still finite
    payload2 = {"ETH-USDT-SWAP": {"order_book": {}, "candles": [],
                                  "funding_rate": 0.0, "volume_24h": 1.0}}
    v2 = lm.build_view(payload2, now=60.0)
    assert v2["ETH"]["ofi_event"] == 0.0


def test_self_heals_on_bare_new_instance():
    # test_funding_unavailable_policy's own harness: a __new__-built model
    # (no __init__) must degrade to the 0.0 neutral, never raise
    lm = LiquidityModel.__new__(LiquidityModel)
    lm.base_to_pair = {"ETH": "ETH/USD"}
    lm.imbalance_decay_bps = 0.0
    v = lm.build_view(_payload(100.0, 5.0, 100.1, 5.0), now=0.0)
    assert v["ETH"]["ofi_event"] == 0.0


def test_cross_venue_size_units_never_mix():
    """Venue B quotes sizes 1000x venue A's units with the SAME relative
    flow: per-venue depth normalization must make the two-venue average
    equal the single-venue value (the _combined_imbalance lesson)."""
    single = _run_polls([(0.0, (100.0, 5.0, 100.1, 5.0)),
                         (30.0, (100.0, 8.0, 100.1, 5.0))])
    lm = LiquidityModel({})
    for now, (qb_a, qb_b) in ((0.0, (5.0, 5000.0)), (30.0, (8.0, 8000.0))):
        a = _payload(100.0, qb_a, 100.1, 5.0)
        b = _payload(100.0, qb_b, 100.1, 5000.0, symbol="ETHUSD")
        view = lm.build_view(a, b, now=now)
    assert view["ETH"]["ofi_event"] == pytest.approx(single, rel=1e-6)


# ------------------------------- 3. wall-time discipline (THALES A-3)
def _ladder_polls(dt, total, step_every):
    """Rising one-tick ladder (constant size 5.0): a price move every
    `step_every` seconds, sampled every `dt` seconds."""
    polls, px = [], 100.0
    for k in range(int(total / dt) + 1):
        now = k * dt
        px = 100.0 + 0.01 * int(now / step_every)
        polls.append((now, (px, 5.0, px + 0.02, 5.0)))
    return polls


def _tail_avg(polls, n=20):
    """Run the polls, return the mean over the last n samples (>= one
    full ladder period at either cadence, past the EWMA transient) -
    averaging removes the ripple-phase parity between cadences."""
    lm = LiquidityModel({})
    vals = []
    for now, args in polls:
        vals.append(lm.build_view(_payload(*args),
                                  now=now)["ETH"]["ofi_event"])
    return sum(vals[-n:]) / n


def test_cadence_invariance_same_flow_two_poll_rates():
    """One tick-up per 20s = e_n 2q per move. Sampled at 10s vs 5s the
    NORMALIZED steady-state value must read the same touch-depth/min
    rate (2q/(q*20s)*60 = 6.0/min) - per-event units would read 2x
    apart between the two cadences."""
    slow = _tail_avg(_ladder_polls(dt=10.0, total=600.0, step_every=20.0))
    fast = _tail_avg(_ladder_polls(dt=5.0, total=600.0, step_every=20.0))
    assert slow == pytest.approx(6.0, rel=0.03)
    assert fast == pytest.approx(6.0, rel=0.03)
    assert abs(fast - slow) / slow < 0.03


def test_stale_gap_resets_to_zero_never_decays_a_fossil():
    ofi = _run_polls([(0.0, (100.0, 5.0, 100.1, 5.0)),
                      (30.0, (100.0, 9.0, 100.1, 5.0)),   # hot
                      (330.0, (100.0, 13.0, 100.1, 5.0))])  # gap 300 > 120
    assert ofi == 0.0


def test_quiet_book_decays_toward_zero():
    hot = _run_polls([(0.0, (100.0, 5.0, 100.1, 5.0)),
                      (30.0, (100.0, 9.0, 100.1, 5.0))])
    lm = LiquidityModel({})
    polls = [(0.0, (100.0, 5.0, 100.1, 5.0)),
             (30.0, (100.0, 9.0, 100.1, 5.0))]
    for now, args in polls:
        lm.build_view(_payload(*args), now=now)
    quiet = lm.build_view(_payload(100.0, 9.0, 100.1, 5.0),
                          now=60.0)["ETH"]["ofi_event"]
    assert 0.0 < quiet < hot


def test_value_is_clamped():
    # absurd flow (10000x depth turnover in one poll) must clamp, not blow
    ofi = _run_polls([(0.0, (100.0, 1.0, 100.1, 1.0)),
                      (30.0, (100.0, 100000.0, 100.1, 1.0))])
    assert -10.0 <= ofi <= 10.0


# ----------------------------------------- 4. build_features wiring
def _vector(direction, view_extra=None, fv_extra=None):
    candles = [{"time": 100 + i * 300, "open": 10 + i * 0.1,
                "high": 10.3 + i * 0.1, "low": 9.9 + i * 0.1,
                "close": 10.2 + i * 0.1, "volume": 5.0}
               for i in range(60)]
    view = {"candles": candles, "imbalance_ratio": 1.6,
            "funding_rate": 0.0002}
    view.update(view_extra or {})
    fv = SimpleNamespace(edge_bps=lambda side: 7.0, basis_bps=12.0,
                         **(fv_extra or {}))
    vol = SimpleNamespace(sigma_bar_pct=0.4, percentile=55.0)
    liq = SimpleNamespace(spread_bps=4.0, depth_top10_usd=250_000.0)
    macro = SimpleNamespace(label="range", momentum_score=0.6,
                            drawdown_pct=20.0)
    sent = SimpleNamespace(score=0.3, fear_spike=False)
    return build_features("BTC", direction, 0.7, view, fv, vol, liq,
                          macro, None, sent, {},
                          extras={"ts": 1_700_000_000.0})


def test_ofi_dir_is_side_relative():
    x_long = _vector("long", view_extra={"ofi_event": 0.8})
    x_short = _vector("short", view_extra={"ofi_event": 0.8})
    assert x_long[IDX["ofi_dir"]] == pytest.approx(0.8)
    assert x_short[IDX["ofi_dir"]] == pytest.approx(-0.8)


def test_ofi_dir_clipped_and_nan_safe():
    assert _vector("long", view_extra={"ofi_event": 7.0})[IDX["ofi_dir"]] \
        == pytest.approx(3.0)
    assert _vector("long")[IDX["ofi_dir"]] == 0.0             # key absent
    assert _vector("long",
                   view_extra={"ofi_event": float("nan")})[IDX["ofi_dir"]] \
        == 0.0                                                # NaN-safe


def test_contract_declares_the_v9_ranges():
    from ml.contracts import _RANGES
    assert _RANGES["ofi_dir"] == (-3, 3)
    assert _RANGES["basis_mom_dir"] == (-3, 3)


# --------------------------- 5. schema v9 + v8 pad-migration + load
def test_schema_is_64_wide_v9_shadow_pair_before_signal_tail():
    # deliberate re-pin: v9 adds ofi_dir/basis_mom_dir (62->64, 8->9)
    assert len(FEATURE_NAMES) == 64
    assert FEATURE_SCHEMA_VERSION == 9
    assert FEATURE_NAMES[-4:] == ["ofi_dir", "basis_mom_dir",
                                  "direction", "gate_confidence"]
    assert V9_NEUTRAL == {"ofi_dir": 0.0, "basis_mom_dir": 0.0}


def _v8_file(path):
    """A genuine v8-era corpus: the CURRENT schema minus the v9 pair."""
    v8_names = [n for n in FEATURE_NAMES
                if n not in ("ofi_dir", "basis_mom_dir")]
    header = ["position_id", "asset", "side", *v8_names,
              "label", "net_pnl_usd", "source", "ts"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(["p1", "BTC", "long", *[f"{0.1:.6f}"] * len(v8_names),
                    "1", "2.00", "live", "1700000000"])
    return path


def test_migration_pads_the_v9_pair_with_documented_neutrals(tmp_path):
    from scripts.migrate_history import migrate_rows
    rows, padded = migrate_rows(str(_v8_file(tmp_path / "v8.csv")))
    assert set(padded) == {"ofi_dir", "basis_mom_dir"}
    assert rows[0][3 + FEATURE_NAMES.index("ofi_dir")] == "0.000000"
    assert rows[0][3 + FEATURE_NAMES.index("basis_mom_dir")] == "0.000000"


def test_migrated_v8_row_loads_under_the_v9_schema(tmp_path):
    """The explicit v8-row LOAD proof: migrate -> append under the v9
    header -> load_training_data returns the row full-width with the
    neutrals in the new columns and the original values preserved."""
    from ml.history import HistoryStore
    from scripts.migrate_history import migrate_rows
    rows, _ = migrate_rows(str(_v8_file(tmp_path / "v8.csv")))
    store = HistoryStore(str(tmp_path / "hist.csv"))
    store._ensure_schema()
    with open(store.path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    X, y, w = store.load_training_data()[:3]
    assert len(X) == 1 and len(X[0]) == len(FEATURE_NAMES)
    assert X[0][IDX["ofi_dir"]] == 0.0
    assert X[0][IDX["basis_mom_dir"]] == 0.0
    assert X[0][IDX["flow_tox"]] == pytest.approx(0.1)   # v8 value survives
    assert y[0] == 1


# --------------------------------------------- 6. shadow purity (grep)
_TOKENS = ("ofi_event", "basis_mom_bps", "ofi_dir", "basis_mom_dir")
_ALLOWED_REL = {
    "strategies/liquidity_model.py",   # producer: view key ofi_event
    "execution/fair_value.py",         # producer: FVState.basis_mom_bps
    "ml/features.py",                  # the ONLY consumer (feature vector)
    "ml/contracts.py",                 # declared ranges (schema contract)
    "config.json",                     # knob _doc strings name the keys
}
_SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", "tests",
              "docs", ".superpowers", ".claude"}
# .claude: agent worktrees (.claude/worktrees/<id>/) are full repo
# checkouts under the repo root - walking into one finds that checkout's
# own legitimate producer/consumer files and fails this grep with
# phantom hits (same class as .venv/.git: not our tree).


def test_shadow_purity_no_decision_module_reads_the_v9_keys():
    """Requirement 1 (SHADOW): grep-provable - no gate, sizer, exit, or
    execution decision module references the two view keys / columns.
    Mirrors tests/test_bracket_divergence.py's report-only walker."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        rel_dir = Path(dirpath).relative_to(ROOT)
        for fn in filenames:
            if not (fn.endswith(".py") or fn == "config.json"):
                continue
            rel = str((rel_dir / fn)).replace("\\", "/")
            if rel.startswith("./"):
                rel = rel[2:]
            if rel in _ALLOWED_REL:
                continue
            fpath = Path(dirpath) / fn
            try:
                text = fpath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if any(t in text for t in _TOKENS):
                hits.append(rel)
    assert not hits, (
        f"v9 shadow keys referenced outside the producer/feature surface "
        f"(strategies/liquidity_model.py, execution/fair_value.py, "
        f"ml/features.py, ml/contracts.py, config.json): {hits}")


# ------------------------------------------------------- config guard
def test_guard_bounds_for_the_v9_ofi_knobs():
    from core.config_guard import validate

    def fatals(cfg):
        return [m for s, m in validate(cfg) if s == "FATAL"]

    base = {"system": {"dry_run": True}}
    ok = {**base, "liquidity_regime": {"ofi": {
        "ewma_tau_sec": 60.0, "depth_tau_sec": 300.0, "stale_sec": 120.0}}}
    assert not any("ofi." in m for m in fatals(ok))
    assert any("ofi.ewma_tau_sec" in m for m in fatals(
        {**base, "liquidity_regime": {"ofi": {"ewma_tau_sec": 1.0}}}))
    assert any("ofi.ewma_tau_sec" in m for m in fatals(
        {**base, "liquidity_regime": {"ofi": {"ewma_tau_sec": 5000.0}}}))
    assert any("ofi.depth_tau_sec" in m for m in fatals(
        {**base, "liquidity_regime": {"ofi": {"depth_tau_sec": 5.0}}}))
    assert any("ofi.stale_sec" in m for m in fatals(
        {**base, "liquidity_regime": {"ofi": {"stale_sec": 2000.0}}}))
    # coherence: stale bound at/below the slow-cycle poll gap (5s x 6 =
    # 30s default) resets the EWMA every poll - structurally dead feature
    assert any("ofi.stale_sec" in m for m in fatals(
        {**base, "liquidity_regime": {"ofi": {"stale_sec": 20.0}}}))


def test_basis_and_venue_disloc_keep_their_opposite_orientations():
    """2026-08-11 audit: basis_bps = (fair_value - kraken_mid) is positive
    when Kraken is CHEAP; venue_disloc_bps = (kraken_mid - venue_mid) is
    positive when Kraken is RICH. The two near-identical quantities enter
    the feature vector ANTI-oriented - documented, intended, and the model
    learned each weight against its own sign. This pin exists because that
    anti-orientation is the closest thing to a 'backwards derivative' in
    the codebase: 'harmonizing' either sign now would be a feature-meaning
    change under the MODEL FREEZE and would silently invert a trained
    weight's effect. Flip one only with an operator-adjudicated retrain."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fv = (root / "execution" / "fair_value.py").read_text(encoding="utf-8")
    mn = (root / "main.py").read_text(encoding="utf-8")
    assert "st.basis_bps = (st.fair_value - st.kraken_mid)" in fv.replace(
        " \\n                ", " "), (
        "basis_bps subtraction order changed - Kraken-cheap-positive "
        "orientation broken")
    assert "disloc_bps = (km - vm) / vm * 1e4" in mn, (
        "venue_disloc subtraction order changed - Kraken-rich-positive "
        "orientation broken")
