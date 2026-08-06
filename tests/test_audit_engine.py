"""tests/test_audit_engine.py — 2026-08-01 whole-codebase audit, engine
group (main.py). One regression per finding; each is written to FAIL
against the pre-fix engine.

  H1  averaging fills re-base entry_price but not high_water, so the
      give-back ratchet arms on a peak that never happened and
      full-closes a never-profitable long-book position at a loss.
  H13 the deploy gate's challenger Brier is calibration-IN-SAMPLE (the
      isotonic calibrator is fit on the exact OOF rows it scores) while
      the champion is rescored out-of-sample - a systematic, always
      pro-challenger tilt worth 25-150% of challenger_brier_margin.
  H16 the ladder entry path deducts a probe-budget token but stamps
      `probe_cost` on no rung, so the SZ-052 unfilled-entry refund is
      structurally unreachable there.
  C2  (engine side) Position carries no live/paper provenance, so after
      `force_dry` the engine simulates exits against a real Kraken book
      and marks REAL positions closed.

Harness idiom: LiquidityBot.__new__(LiquidityBot) + hand-set stub attrs
(tests/test_ladder_integration.py, tests/test_probe_budget.py).
"""
import json
import math
import types
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from core.fault import FaultManager, OpState, Severity
from core.state import PortfolioState, Position
from execution.grid_ladder import GridLadderEngine
from execution.order_manager import FillEvent
from execution.pretrade import PreTradeGate
from main import LiquidityBot, cross_fitted_calibrated_oof
from ml.calibration import IsotonicCalibrator, brier_score
from ml.models import LogisticModel, load_model
from ml.monitor import ModelMonitor
from risk.profit_tiers import ProfitTierEngine

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
LONG_PT = SHIPPED["long_book"]["profit_taking"]
LONG_BOOK_CFG = {"long_book": {"thesis_stop_pct": float(
    SHIPPED["long_book"].get("thesis_stop_pct", 12.0))}}


# =====================================================================
# H1 — averaging fills must carry the peak-gain FRACTION, not a stale
#      absolute high-water price.
# =====================================================================
def _fill_bot(pos):
    """Minimal stub `self` for the _handle_fill entry/averaging branch."""
    return types.SimpleNamespace(
        config=LONG_BOOK_CFG,
        state=types.SimpleNamespace(
            get_position=lambda pid: pos,
            record_fees=lambda a: None,
            record_entry_fee=lambda a: None),
        _asset_of=lambda symbol: symbol.split("/")[0],
        _ledger_fill=lambda *a, **k: None,
        _long_last_add_ts={},
        _px=lambda s, p: f"{p:.4f}",
    )


def _entry_order(symbol="ETH/USD", side="buy", position_id="p1"):
    return types.SimpleNamespace(
        order_id="o1", txid="TX-1", asset=symbol.split("/")[0],
        symbol=symbol, side=side, purpose="entry",
        position_id=position_id, fees_usd=0.0, meta={}, leverage=1.0,
        remaining=0.0, fill_ratio=1.0)


def _average_in(pos, price, size, book="long"):
    """Drive the REAL _handle_fill averaging branch."""
    pos.book = book
    order = _entry_order(symbol=pos.symbol,
                         side="buy" if pos.direction == "long" else "sell",
                         position_id=pos.position_id)
    LiquidityBot._handle_fill(_fill_bot(pos),
                             FillEvent(order, size, price, final=False),
                             now=1000.0)


def _long_book_position(entry, size=1.0):
    return Position(position_id="lb1", symbol="ETH/USD", direction="long",
                    entry_price=entry, size=size, original_size=size,
                    opened_at=datetime.now(timezone.utc), book="long")


def test_averaging_down_leaves_the_giveback_ratchet_disarmed():
    """The money-losing arm of H1, end to end against the SHIPPED long-book
    geometry: a 3-rung equal-size accumulation ladder through a drawdown,
    never once in profit. Pre-fix, high_water stayed pinned at the FIRST
    rung's price while entry_price averaged down, so _mfe_pct reported a
    ~5.5% phantom peak, cleared arm_gain_pct=5.0, and _exit_floor_hit
    liquidated 100% of the book at a loss with the 12% thesis stop still
    far away."""
    pos = _long_book_position(entry=100.0, size=1.0)
    engine = ProfitTierEngine(LONG_PT)

    # rung 1 rests and the market only ever goes DOWN: the tier engine
    # ratchets high_water to the entry itself (max(hw, px, e)) - a real
    # position's high_water is never None once it has been evaluated.
    engine.evaluate(pos, 100.0)
    assert pos.high_water == 100.0

    _average_in(pos, price=95.0, size=1.0)     # rung 2
    engine.evaluate(pos, 95.0)
    _average_in(pos, price=90.0, size=1.0)     # rung 3
    assert pos.entry_price == pytest.approx(95.0)

    # the position has NEVER been in profit: peak gain is 0%, so the
    # give-back ratchet must stay disarmed and must not produce an exit.
    action = engine.evaluate(pos, 90.0)
    assert not action.should_close_partial and action.close_pct == 0.0, (
        "the give-back ratchet armed on a peak that never happened and "
        "liquidated the accumulation book at a loss - averaging down "
        "re-based entry_price without re-basing high_water")
    assert ProfitTierEngine._mfe_pct(pos) == pytest.approx(0.0), \
        "a never-profitable position must carry a 0% MFE after averaging"
    assert engine._give_back_candidate(pos, None) is None


def test_averaging_up_preserves_the_exact_peak_gain_fraction():
    """A genuine winner must keep its MFE% across an averaging fill - the
    fraction is the invariant, not the absolute high-water price."""
    pos = _long_book_position(entry=100.0, size=1.0)
    pos.high_water = 110.0                       # a real +10% excursion
    assert ProfitTierEngine._mfe_pct(pos) == pytest.approx(10.0)

    _average_in(pos, price=110.0, size=1.0)      # add at the peak
    assert pos.entry_price == pytest.approx(105.0)
    assert ProfitTierEngine._mfe_pct(pos) == pytest.approx(10.0), \
        "an averaging fill must not inflate OR deflate a real MFE"
    assert pos.high_water == pytest.approx(115.5)


def test_short_averaging_reanchors_high_water_on_the_new_basis():
    """Short side mirror: high_water is the LOWEST price seen, so the peak
    fraction re-anchors as entry * (1 - peak_frac)."""
    pos = Position(position_id="s1", symbol="ETH/USD", direction="short",
                   entry_price=100.0, size=1.0, original_size=1.0,
                   opened_at=datetime.now(timezone.utc))
    engine = ProfitTierEngine(LONG_PT)
    engine.evaluate(pos, 100.0)                  # never profitable
    assert pos.high_water == 100.0

    _average_in(pos, price=110.0, size=1.0, book="5m")   # adverse add
    assert pos.entry_price == pytest.approx(105.0)
    assert pos.high_water == pytest.approx(105.0)
    assert ProfitTierEngine._mfe_pct(pos) == pytest.approx(0.0)
    assert engine._give_back_candidate(pos, None) is None, \
        "a short that never went favorable must stay disarmed"


def test_short_winner_keeps_its_mfe_fraction():
    pos = Position(position_id="s2", symbol="ETH/USD", direction="short",
                   entry_price=100.0, size=1.0, original_size=1.0,
                   opened_at=datetime.now(timezone.utc), high_water=90.0)
    assert ProfitTierEngine._mfe_pct(pos) == pytest.approx(10.0)
    _average_in(pos, price=90.0, size=1.0, book="5m")
    assert pos.entry_price == pytest.approx(95.0)
    assert pos.high_water == pytest.approx(85.5)
    assert ProfitTierEngine._mfe_pct(pos) == pytest.approx(10.0)


def test_never_evaluated_position_keeps_high_water_none():
    """high_water None means the tier engine has never seen this position;
    materialising it on an averaging fill would be a silent behaviour
    change, so the re-anchor must be a no-op there."""
    pos = _long_book_position(entry=100.0, size=1.0)
    assert pos.high_water is None
    _average_in(pos, price=90.0, size=1.0)
    assert pos.high_water is None
    assert pos.entry_price == pytest.approx(95.0)


# =====================================================================
# H16 — one ladder decision = one token deduction = one refundable tag.
# =====================================================================
LADDER_CFG = {"enabled": True, "rungs": 3, "spacing_vol_mult": 0.35,
             "min_spacing_bps": 8.0, "size_decay": 0.7,
             "p_win_arm": 0.60, "p_win_disarm": 0.55}


def _ladder_bot(*, tokens=5.0, mode="budget", cost=1.79):
    b = LiquidityBot.__new__(LiquidityBot)
    b.ladder = GridLadderEngine(dict(LADDER_CFG))
    b.pretrade = PreTradeGate({"maker_fee_bps": 25.0, "taker_fee_bps": 40.0})
    b.capital = types.SimpleNamespace(
        max_concurrent_positions=10,
        can_open_new_position=lambda state, reserved: True)
    b.state = PortfolioState(starting_capital=10_000.0)
    b.inventory = types.SimpleNamespace(max_same_side=5)
    b.postmortem = types.SimpleNamespace(register_entry=lambda t: None)
    b._submitted_orders = []
    b._reject_position_ids = set()

    def submit(**kwargs):
        order = types.SimpleNamespace(**kwargs)
        order.fees_usd = 0.0
        order.fill_ratio = 0.0
        order.remaining = kwargs.get("size", 0.0)
        b._submitted_orders.append(order)
        if kwargs.get("position_id") in b._reject_position_ids:
            b._submitted_orders.pop()
            return None
        return order
    b.orders = types.SimpleNamespace(
        submit=submit, pair_meta={},
        open_orders=lambda: list(b._submitted_orders))
    b.marks = {}
    b.kraken_books = {}
    b.kraken = types.SimpleNamespace(kraken_pair=lambda s: s.replace("/", ""))
    b._thales_fired = {}
    b.sizer = types.SimpleNamespace(note_entry=lambda asset, now: None)
    b._mark_cand = lambda asset, direction, code: None
    b._last_entry_admit_ts = 0.0
    b.monitor = types.SimpleNamespace(use_model=True)
    b.meta = types.SimpleNamespace(trained=True)
    # ---- SPB-R budget state (tests/test_probe_budget.py idiom) ----
    b.dry_run = True
    b._probe_admission_mode = mode
    b._probe_share_window = 40
    b._probe_max_share = 0.35
    b._probe_admissions = deque(maxlen=40)
    b._budget_tokens = tokens
    b._budget_tokens_per_day = 15.0
    b._budget_burst_hours = 8.0
    b._budget_refund_unfilled = True
    b._budget_refund_events = deque()
    b._pending_probe_cost = {"ETH": cost} if mode == "budget" else {}
    b._pending_probe_asset = "ETH" if mode == "budget" else None
    return b


def _ladder_kwargs(explored=True, p_win=0.65):
    signal = types.SimpleNamespace(direction="long")
    decision = types.SimpleNamespace(est_cost_bps=5.0, size_units=3.0,
                                     est_edge_bps=10.0, taker=False)
    vol_state = types.SimpleNamespace(sigma_bar_pct=0.30,
                                      sigma_daily_pct=0.30 * math.sqrt(288))
    return dict(position_id="p1", asset="ETH", symbol="ETH/USD",
                side="buy", signal=signal, entry_price=100.0,
                decision=decision,
                sized=types.SimpleNamespace(usd=300.0, units=3.0),
                lev=types.SimpleNamespace(allowed_leverage=1.0),
                equity=10_000.0, vol_state=vol_state,
                fv_state=types.SimpleNamespace(fair_value=100.0),
                macro_state=types.SimpleNamespace(label="bull_quiet",
                                                  playbook={}),
                liq_state=types.SimpleNamespace(label="liquid"),
                verdict=types.SimpleNamespace(label="neutral"),
                feats=None, explored=explored, p_win=p_win, model_p=p_win,
                shadow_p=p_win, ev_pct=1.0, stop_pct_eff=1.0,
                target_pct=1.0, now=1000.0, reserved_entries=0,
                can_enter=True)


def _tagged(bot):
    return [o for o in bot._submitted_orders if "probe_cost" in o.meta]


def test_ladder_stamps_probe_cost_on_exactly_one_submitted_rung():
    b = _ladder_bot()
    _, _, handled = b._ladder_entry(**_ladder_kwargs())
    assert handled is True and len(b._submitted_orders) >= 2
    tagged = _tagged(b)
    assert len(tagged) == 1, (
        "the ladder path deducts ONE token, so exactly one rung may carry "
        "the refundable probe_cost tag (0 => SZ-052 unreachable, N => the "
        "refund fires N times for one deduction)")
    assert tagged[0].meta["probe_cost"] == pytest.approx(1.79)
    assert tagged[0] is b._submitted_orders[0]


def test_probe_tag_lands_on_the_first_rung_that_actually_submits():
    """A rejected rung (firewall / collar / venue-min) never rests, so it
    must not carry the tag - the tag follows the first order that really
    went out."""
    b = _ladder_bot()
    b._reject_position_ids = {"p1"}              # rung 0 refused
    _, _, handled = b._ladder_entry(**_ladder_kwargs())
    assert handled is True
    tagged = _tagged(b)
    assert len(tagged) == 1
    assert tagged[0].position_id == "p1-r1"


def test_ladder_probe_deduction_is_refunded_when_no_rung_fills():
    """SZ-052 round trip on the ladder path: one deduction at placement,
    one refund at the unfilled entry terminal, back to the starting
    token balance."""
    b = _ladder_bot(tokens=5.0)
    before = b._budget_tokens
    b._ladder_entry(**_ladder_kwargs())
    assert b._budget_tokens == pytest.approx(before - 1.79), \
        "the ladder path must still deduct exactly once"
    order = _tagged(b)[0]
    order.fill_ratio = 0.0                        # unfilled terminal
    b._maybe_refund_probe_order(order, 2000.0)
    assert b._budget_tokens == pytest.approx(before), \
        "an unfilled ladder probe must get its token back (SZ-052)"
    assert "probe_cost" not in order.meta         # popped: idempotent
    b._maybe_refund_probe_order(order, 2001.0)
    assert b._budget_tokens == pytest.approx(before)


def test_sibling_rung_fill_retires_the_refund_tag():
    """The refund's precondition is 'this DECISION bought no label'. A fill
    on ANY rung means a label was bought, so the single tag must die even
    though the tagged rung itself later expires unfilled."""
    b = _ladder_bot(tokens=5.0)
    b._ladder_entry(**_ladder_kwargs())
    tagged = _tagged(b)[0]
    sibling = [o for o in b._submitted_orders if o is not tagged][0]

    # a real fill on the sibling rung, through the REAL _handle_fill seam
    pos = Position(position_id=sibling.position_id, symbol="ETH/USD",
                   direction="long", entry_price=99.0, size=1.0,
                   original_size=1.0, opened_at=datetime.now(timezone.utc))
    b.state.add_position(pos)
    b._ledger_fill = lambda *a, **k: None
    sibling.purpose = "entry"
    LiquidityBot._handle_fill(
        b, FillEvent(sibling, 0.5, 99.0, final=False), now=1500.0)

    assert "probe_cost" not in tagged.meta, \
        "a filled sibling rung must retire the ladder's refundable tag"
    charged = b._budget_tokens
    tagged.fill_ratio = 0.0
    b._maybe_refund_probe_order(tagged, 2000.0)
    assert b._budget_tokens == pytest.approx(charged), \
        "a ladder that DID open a position must never be refunded"


def test_share_cap_ladder_meta_stays_byte_identical():
    """share_cap mode has an empty stash, so no rung may gain the key at
    all - legacy order.meta unchanged."""
    b = _ladder_bot(mode="share_cap")
    b._ladder_entry(**_ladder_kwargs(explored=True))
    assert _tagged(b) == []


def test_conviction_ladder_entry_carries_no_probe_cost():
    b = _ladder_bot()
    b._ladder_entry(**_ladder_kwargs(explored=False))
    assert _tagged(b) == [], \
        "a conviction (non-probe) entry never carries a probe tag"


# =====================================================================
# C2 (engine side) — a simulated fill may not close a live-born book.
# =====================================================================
def _c2_bot(config_dry_run, tmp_path):
    b = LiquidityBot.__new__(LiquidityBot)
    b.config = {"system": {"fills_ledger_path": str(tmp_path / "fills.csv")},
                **LONG_BOOK_CFG}
    b._config_dry_run = config_dry_run
    b._sim_fill_on_live_latched = False
    b.dry_run = True                      # force_dry already flipped it
    b.fault = FaultManager(alerts=None)
    b.fault.arm()
    b.state = PortfolioState(starting_capital=10_000.0)
    b.capital = types.SimpleNamespace(
        record_realized_profit=lambda n, s, **kw: None,
        skim_trade=lambda n, s: None)
    b._exit_attempts = {}
    b._pos_realized = {}
    b._ledger_fill = lambda *a, **k: None
    b._px = lambda s, p: f"{p:.2f}"
    b._finalized = []
    b._finalize_position = lambda p, n, t, close_reason="": \
        b._finalized.append(p.position_id)
    return b


def _exit_order(txid, position_id="live1"):
    return types.SimpleNamespace(
        order_id="x1", txid=txid, asset="ETH", symbol="ETH/USD",
        side="sell", purpose="exit", position_id=position_id,
        fees_usd=0.0, meta={}, remaining=0.0, fill_ratio=1.0)


def _live_position(state):
    pos = Position(position_id="live1", symbol="ETH/USD", direction="long",
                   entry_price=2000.0, size=1.0, original_size=1.0,
                   opened_at=datetime.now(timezone.utc))
    state.add_position(pos)
    return pos


def test_simulated_fill_cannot_close_a_live_configured_book(tmp_path):
    """C2: after force_dry, OrderManager mints DRY- txids and _sim_cross
    fabricates fills off the still-real Kraken book. Applying one would
    decrement pos.size, book paper PnL and _finalize_position a position
    the venue still holds."""
    b = _c2_bot(config_dry_run=False, tmp_path=tmp_path)
    pos = _live_position(b.state)
    order = _exit_order("DRY-2bd81723")

    LiquidityBot._handle_fill(b, FillEvent(order, 1.0, 1999.0, final=True),
                             now=1000.0)

    assert pos.size == pytest.approx(1.0), \
        "a fabricated fill must not decrement a live-born position"
    assert b._finalized == [], "a real position was marked closed by a sim"
    assert b.state.get_position("live1") is not None
    assert b.fault.state is OpState.HALTED
    assert "simulated_fill_on_live_book" in b.fault.status()["faults"]


def test_simulated_fill_latches_the_fault_exactly_once(tmp_path):
    b = _c2_bot(config_dry_run=False, tmp_path=tmp_path)
    _live_position(b.state)
    for _ in range(4):
        LiquidityBot._handle_fill(
            b, FillEvent(_exit_order("DRY-abc"), 1.0, 1999.0, final=True),
            now=1000.0)
    rec = b.fault.status()["faults"]["simulated_fill_on_live_book"]
    assert rec["count"] == 1, \
        "the CRITICAL latch/alert must fire once, not once per sim fill"
    assert rec["severity"] == Severity.CRITICAL.value


def test_paper_session_applies_dry_fills_normally(tmp_path):
    """Negative control: a session CONFIGURED dry_run is the normal paper
    engine - DRY- txids are its only txids and must be applied."""
    b = _c2_bot(config_dry_run=True, tmp_path=tmp_path)
    pos = _live_position(b.state)
    LiquidityBot._handle_fill(
        b, FillEvent(_exit_order("DRY-2bd81723"), 1.0, 1999.0, final=True),
        now=1000.0)
    assert pos.size == pytest.approx(0.0)
    assert b._finalized == ["live1"]
    assert b.fault.state is OpState.ARMED


def test_live_session_applies_real_venue_fills(tmp_path):
    """Negative control: a genuine Kraken txid on a live-configured book is
    the whole point of live trading - never blocked."""
    b = _c2_bot(config_dry_run=False, tmp_path=tmp_path)
    pos = _live_position(b.state)
    LiquidityBot._handle_fill(
        b, FillEvent(_exit_order("OQCLML-BW3P3-BUCMWZ"), 1.0, 1999.0,
                     final=True), now=1000.0)
    assert pos.size == pytest.approx(0.0)
    assert b._finalized == ["live1"]
    assert b.fault.state is OpState.ARMED


def test_provenance_reads_the_configured_flag_not_the_runtime_one(tmp_path):
    """The guard must key on the IMMUTABLE configured mode: `bot.dry_run`
    is exactly what force_dry rewrites, so reading it would make the guard
    disable itself in the only situation it exists for."""
    b = _c2_bot(config_dry_run=False, tmp_path=tmp_path)
    b.dry_run = True
    assert b._simulated_fill_on_live_book(_exit_order("DRY-1")) is True
    b.dry_run = False
    assert b._simulated_fill_on_live_book(_exit_order("DRY-1")) is True


# =====================================================================
# H13 — the deploy gate's challenger Brier must be calibration-honest.
# =====================================================================
class _ConstModel:
    def __init__(self, p):
        self.p = p

    def predict_proba(self, X):
        return np.full(len(X), self.p)


def _zero_skill_fixture(n=100, seed=2):
    """oof_p is drawn INDEPENDENTLY of y: the challenger has literally no
    skill, so an honest score cannot beat the base-rate constant champion.
    Fixed seed/size - these are the measured numbers this test pins."""
    rng = np.random.default_rng(seed)
    y = np.array([1.0] * (n // 2) + [0.0] * (n - n // 2))
    rng.shuffle(y)
    oof_p = rng.random(n)
    return y, oof_p


def test_in_sample_calibration_flatters_a_zero_skill_challenger():
    """Pins the defect's mechanism on the shipped IsotonicCalibrator: PAV
    fit on the very rows it is scored on turns a no-skill score into one
    that beats a coin, while the cross-fitted score does not."""
    y, p = _zero_skill_fixture()
    in_sample = brier_score(y, IsotonicCalibrator().fit(p, y).transform(p))
    honest = brier_score(y, cross_fitted_calibrated_oof(p, y))
    assert in_sample < 0.25 < honest, (
        f"in-sample {in_sample:.4f} / honest {honest:.4f} - the fixture "
        f"must straddle the coin-flip bar for the gate test below")
    assert honest > in_sample


def test_cross_fitted_calibration_never_scores_a_row_with_its_own_fit():
    """Every returned probability must come from a calibrator that did not
    see that row. Constructed so one fold's complement carries a strictly
    different mapping than the full-pool fit would give it."""
    y, p = _zero_skill_fixture(n=200, seed=5)
    full = IsotonicCalibrator().fit(p, y).transform(p)
    cf = cross_fitted_calibrated_oof(p, y, folds=5)
    assert len(cf) == len(p)
    assert not np.allclose(cf, full)
    # k folds, k complements: reproduce fold 0 by hand and check it matches
    idx = np.arange(len(p))
    part = idx % 5 == 0
    expect = IsotonicCalibrator().fit(p[~part], y[~part]).transform(p[part])
    assert np.allclose(cf[part], expect)


def _retrain_bot(tmp_path, monitor, X, y, champion, trained_rows):
    b = LiquidityBot.__new__(LiquidityBot)
    b.config = {"ml": {"retrain_history_path":
                       str(tmp_path / "retrain_history.jsonl")}}
    n = len(X)
    b.history = types.SimpleNamespace(
        row_count=lambda: n,
        load_training_data=lambda **k: (X, y, np.ones(n),
                                        np.arange(n, dtype=float),
                                        np.zeros(n)),
        last_load_stats={"live_clean": n})
    b.monitor = monitor
    b.meta = types.SimpleNamespace(
        trained=True, model=champion, calibrator=None,
        trained_rows=trained_rows,
        model_path=str(tmp_path / "meta_model.json"), reload=lambda: None)
    b._retrain_attempted = False
    b._rows_at_last_train = 0
    b._retrain_failures = 0
    monitor.flag_path.parent.mkdir(parents=True, exist_ok=True)
    monitor.flag_path.touch()
    return b


def _stub_pipeline(monkeypatch, results):
    import ml.contracts as contracts_mod
    import ml.interpret as interpret_mod
    import ml.walkforward as wf_mod
    monkeypatch.setattr(
        contracts_mod, "get_contract",
        lambda: types.SimpleNamespace(
            check_matrix=lambda X: {"keep": np.ones(len(X), bool)}))
    monkeypatch.setattr(interpret_mod, "background_sample", lambda X, n: [])
    monkeypatch.setattr(wf_mod, "evaluate_and_select", lambda *a, **k: results)


def test_deploy_gate_refuses_a_challenger_that_only_wins_in_sample(
        tmp_path, monkeypatch):
    """End-to-end at the real _maybe_auto_retrain call site. The challenger
    has ZERO skill (probabilities independent of the labels) and the frozen
    champion is the honest base-rate constant. Scoring the challenger with
    a calibrator fit on its own OOF rows drops its Brier below the 0.25
    coin bar, so should_deploy's 'beat a coin' clause DEPLOYS a worthless
    model over a working champion. Cross-fitted, it stays above 0.25 and is
    correctly rejected."""
    y, oof_p = _zero_skill_fixture()
    n = len(y)
    X = np.random.default_rng(0).normal(size=(n, 4))
    results = {"selected": "logistic", "gated": None,
              "oof_idx": np.arange(n),
              "logistic": {"oof_p": oof_p, "oof_y": y.copy()},
              "model": LogisticModel(seed=7).fit(X, y), "importance": []}
    monitor = ModelMonitor({"retrain_flag_path": str(tmp_path / "r.flag"),
                            "retrain_min_rows": 60, "deploy_min_oof": 30})
    b = _retrain_bot(tmp_path, monitor, X, y, _ConstModel(0.5),
                     trained_rows=0)
    _stub_pipeline(monkeypatch, results)

    b._maybe_auto_retrain()

    assert not Path(b.meta.model_path).exists(), (
        "a zero-skill challenger was deployed - the gate is scoring it "
        "with a calibrator fit on the exact rows it is scored on while "
        "the champion is rescored out-of-sample")
    assert monitor.champion_brier == pytest.approx(0.25), \
        "the badge must not move on a rejected challenger"


def test_deployed_artifact_still_ships_the_full_pool_calibrator(
        tmp_path, monkeypatch):
    """The honesty fix is scoped to the GATE SCORE. A genuinely better
    challenger must still deploy, and the artifact's calibration must be
    the full-pool PAV fit (more data = the better live mapping), not one
    of the cross-fit folds."""
    n = 200
    rng = np.random.default_rng(11)
    z = rng.normal(size=n)
    y = (rng.random(n) < 1 / (1 + np.exp(-2.0 * z))).astype(float)
    oof_p = np.clip(0.5 + 0.18 * z, 0.02, 0.98)     # informative, squashed
    X = rng.normal(size=(n, 4))
    results = {"selected": "logistic", "gated": None,
              "oof_idx": np.arange(n),
              "logistic": {"oof_p": oof_p, "oof_y": y.copy()},
              "model": LogisticModel(seed=3).fit(X, y), "importance": []}
    monitor = ModelMonitor({"retrain_flag_path": str(tmp_path / "r.flag"),
                            "retrain_min_rows": 60, "deploy_min_oof": 30})
    b = _retrain_bot(tmp_path, monitor, X, y, _ConstModel(0.5),
                     trained_rows=0)
    _stub_pipeline(monkeypatch, results)

    b._maybe_auto_retrain()

    assert Path(b.meta.model_path).exists(), \
        "a genuinely skilful challenger must still deploy"
    artifact = json.loads(Path(b.meta.model_path).read_text(encoding="utf-8"))
    full_pool = IsotonicCalibrator().fit(oof_p, y).to_dict()
    assert artifact["calibration"] == full_pool, \
        "the SHIPPED calibrator must stay the full-pool fit (unchanged)"
    # the badge is now the honest (cross-fitted) score, not the flattered one
    honest = brier_score(y, cross_fitted_calibrated_oof(oof_p, y))
    assert artifact["oof_brier"] == pytest.approx(honest)
    assert load_model(b.meta.model_path) is not None
