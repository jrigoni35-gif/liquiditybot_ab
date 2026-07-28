"""tests/test_t5_riding_minors.py — Task 5 (#103): four independent riding
minors from the profitability program's whole-program review and audit
Wave 2, batched into one commit.

1. PT-060 log string (main.py _manage_open_position): the tier-exit caller
   logged `f"tier {action.tier_fired or 'trail'}"` unconditionally, so a
   fired time-stop (reason_code PT-060, tier_fired 0) read "tier trail" in
   the operator-facing log/meta["reason"] — wrong for a scratch. The human
   reason string is now reason-aware; the meta["reason_code"] wiring
   (already correct, pinned separately in test_p35_label_sim_parity.py) is
   untouched.

2. Algo-parent admission asymmetry (main.py entry loop / _submit_algo_child):
   the algo path recorded a probe admission at PARENT CREATION, before any
   child order had even been attempted — the direct path only records on a
   successful submit. A parent whose first child got rejected still filled
   the probe-share window. Fixed by recording the ONE admission on the
   parent's FIRST successful child submit (same "an order actually went
   out" semantic as the direct path).

3. Sub-25s reclamp sliver (whole-program review Minor #6): a resting maker
   tier-1 take on a still-virgin position (tier_closed increments on FILL,
   not on submit) can be preempted by a PT-060 full-close when a vol spike
   reclamps the trigger during the submission-to-fill window — the tier
   engine can't distinguish "never took action" from "already resting a
   take, awaiting fill" since both read tier_closed==0. Fixed at the
   CALLER: suppress the PT-060 submission for exactly one cycle when the
   position already has an OPEN resting (post_only) profit-take exit
   order. Scoped strictly to the PT-060 branch — every other exit path
   (hard stop, floor/trail, give-back) is untouched (exits always
   allowed, invariant 5).

4. W2-28 checksum-resubscribe backoff (data/ws_feed.py) — see
   tests/test_ws_feed.py for the ws_feed.py-side pins; this file only
   covers the main.py-side fixes (1-3).
"""
import json
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import main as main_mod
from core.codes import Code
from core.state import Position
from execution.algos import ChildSlice
from risk.profit_tiers import ProfitTierEngine

_NOW = 1_700_000_000.0
_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


# ============================================================================
# Fix 1 + 3 shared harness — drives the REAL _manage_open_position against a
# minimal stub self, same idiom as
# test_p35_label_sim_parity.test_manage_open_position_threads_tier_action_reason_code_end_to_end
# ============================================================================
def _ts_engine():
    return ProfitTierEngine({
        "tier_1": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
        "vol_scaled": False,
        "time_stop": {"enabled": True, "max_bars_no_progress": 5,
                     "min_mfe_frac_of_tier1": 0.5}})


def _reclamp_bot(open_orders):
    captured = {}

    def fake_submit(**kw):
        captured.update(kw)
        return SimpleNamespace(order_id="o1", position_id="p1", purpose="exit")

    fake = SimpleNamespace(
        marks={"ETH/USD": 100.0}, state=SimpleNamespace(),
        _asset_of=lambda sym: "ETH", _stop_ok={}, _stop_hit={},
        _mark_fresh=lambda sym, now: True,
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=None)),
        inventory=SimpleNamespace(
            inventory_ratio=lambda *a, **k: 0.0,
            soft_cap_pct=1.0, hard_cap_pct=1.0),
        last_signals={}, _tier_engine=lambda scale: _ts_engine(),
        kraken=SimpleNamespace(kraken_pair=lambda sym: "XETHZUSD"),
        orders=SimpleNamespace(open_orders=lambda: open_orders,
                               _ordermin=lambda pair: 0.0, submit=fake_submit,
                               cancel_order=lambda o, reason=None: None),
        _exit_attempts={}, max_slip_pct=0.5, esc_widen_mult=2.0,
        esc_max_slip_pct=3.0, esc_market_after=3,
        kraken_books={"ETH": {"bids": [(99.0, 5.0)], "asks": [(101.0, 5.0)]}},
        maker_first_profit_exits=False,
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(fair_value=100.0)),
        _equity=lambda: 1000.0, _px=lambda s, p: f"{p:.2f}",
    )
    fake._submit_exit = types.MethodType(main_mod.LiquidityBot._submit_exit,
                                        fake)
    # real cold-sigma gate over the stub vol (duck-typed state has no
    # `measured` -> the stub's sigma_bar_pct passes through unchanged)
    fake._exit_sigma = types.MethodType(main_mod.LiquidityBot._exit_sigma,
                                        fake)
    fake._has_resting_profit_take = types.MethodType(
        main_mod.LiquidityBot._has_resting_profit_take, fake)
    return fake, captured


def _virgin_ts_pos(stop_price=None):
    p = Position(position_id="p1", symbol="ETH/USD", direction="long",
                entry_price=100.0, size=1.0, original_size=1.0,
                tier_closed=0, high_water=100.0,
                opened_at=(datetime.fromtimestamp(_NOW, tz=timezone.utc)
                          - timedelta(minutes=25.0)))
    p.stop_price = stop_price
    return p


_MACRO = {"ETH": SimpleNamespace(playbook={"tier_scale": 1.0})}


# ---------------------------------------------------------------------------
# Fix 1: PT-060 human reason string
# ---------------------------------------------------------------------------
def test_time_stop_close_logs_time_stop_scratch_not_tier_trail():
    fake, captured = _reclamp_bot([])          # no resting order -> fires
    main_mod.LiquidityBot._manage_open_position(fake, _virgin_ts_pos(), _NOW,
                                                1000.0, _MACRO)
    assert captured, "time-stop did not fire"
    assert captured["meta"]["reason_code"] == Code.PT_TIME_STOP.value
    assert captured["meta"]["reason"] == "time-stop scratch"
    assert "tier trail" not in captured["meta"]["reason"]


def test_ordinary_tier_take_reason_string_unchanged():
    """A scheduled profit-tier take (not PT-060) still logs 'tier N' -
    the reason-aware branch only changes the PT-060 case."""
    eng = ProfitTierEngine({
        "tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25}})
    fake, captured = _reclamp_bot([])
    fake._tier_engine = lambda scale: eng
    pos = Position(position_id="p1", symbol="ETH/USD", direction="long",
                  entry_price=100.0, size=1.0, original_size=1.0,
                  tier_closed=0, high_water=100.0,
                  opened_at=datetime.fromtimestamp(_NOW, tz=timezone.utc))
    fake.marks = {"ETH/USD": 101.5}            # clears the 1% tier-1 trigger
    main_mod.LiquidityBot._manage_open_position(fake, pos, _NOW, 1000.0, _MACRO)
    assert captured, "tier-1 take did not fire"
    assert captured["meta"]["reason"] == "tier 1"
    assert captured["meta"]["reason_code"] == ""


# ---------------------------------------------------------------------------
# Fix 3: sub-25s reclamp sliver — suppress PT-060 while a resting tier-1
# take is still open; fire once it's gone. Scoped to PT-060 only.
# ---------------------------------------------------------------------------
def test_pt060_suppressed_while_resting_profit_take_open():
    resting = SimpleNamespace(purpose="exit", position_id="p1", post_only=True)
    fake, captured = _reclamp_bot([resting])
    main_mod.LiquidityBot._manage_open_position(fake, _virgin_ts_pos(), _NOW,
                                                1000.0, _MACRO)
    assert captured == {}, ("PT-060 must be suppressed this cycle while a "
                            "resting tier-1 take order is still open")


def test_pt060_fires_once_resting_take_is_gone():
    fake, captured = _reclamp_bot([])          # resting order died unfilled
    main_mod.LiquidityBot._manage_open_position(fake, _virgin_ts_pos(), _NOW,
                                                1000.0, _MACRO)
    assert captured, "time-stop must fire next evaluation once the resting take is gone"
    assert captured["meta"]["reason_code"] == Code.PT_TIME_STOP.value


def test_resting_order_for_a_DIFFERENT_position_does_not_suppress():
    other_pos_order = SimpleNamespace(purpose="exit", position_id="OTHER",
                                      post_only=True)
    fake, captured = _reclamp_bot([other_pos_order])
    main_mod.LiquidityBot._manage_open_position(fake, _virgin_ts_pos(), _NOW,
                                                1000.0, _MACRO)
    assert captured, "a resting order on a different position must never suppress this one's time-stop"


def test_suppression_scoped_to_pt060_does_not_touch_hard_stop():
    """Invariant 5 pin: exits are ALWAYS allowed. The resting-take
    suppression must never reach the hard-stop branch, which fires
    unconditionally before the tier engine is even consulted."""
    resting = SimpleNamespace(purpose="exit", position_id="p1", post_only=True)
    fake, captured = _reclamp_bot([resting])
    pos = _virgin_ts_pos(stop_price=150.0)     # long stop far above mark=100 -> hit
    main_mod.LiquidityBot._manage_open_position(fake, pos, _NOW, 1000.0, _MACRO)
    assert captured, "hard stop must fire even with a resting profit-take open"
    assert "stop" in captured["meta"]["reason"]
    assert captured["meta"]["reason_code"] == ""


def test_suppression_does_not_touch_protective_floor_exit():
    """A protective floor/trail/BE close (tier_fired>0, reason_code=="")
    must fire normally even with a resting profit-take order open -
    the suppression is scoped to the PT-060 branch only."""
    eng = ProfitTierEngine({
        "trailing_stop": {"enabled": True, "activate_after_tier": 0,
                          "trail_pct": 1.0},
        "be_after_tier": 0, "be_buffer_bps": 1.0})
    resting = SimpleNamespace(purpose="exit", position_id="p1", post_only=True)
    fake, captured = _reclamp_bot([resting])
    fake._tier_engine = lambda scale: eng
    pos = Position(position_id="p1", symbol="ETH/USD", direction="long",
                  entry_price=100.0, size=1.0, original_size=1.0,
                  tier_closed=1, high_water=110.0,
                  opened_at=datetime.fromtimestamp(_NOW, tz=timezone.utc))
    fake.marks = {"ETH/USD": 100.5}             # below the BE/trail floor
    main_mod.LiquidityBot._manage_open_position(fake, pos, _NOW, 1000.0, _MACRO)
    assert captured, "protective floor exit must fire despite the resting take"
    assert captured["meta"]["reason_code"] == ""


# ---------------------------------------------------------------------------
# _has_resting_profit_take: direct predicate pins
# ---------------------------------------------------------------------------
def test_has_resting_profit_take_predicate_direct():
    pos = _virgin_ts_pos()
    resting = SimpleNamespace(purpose="exit", position_id="p1", post_only=True)
    fake = SimpleNamespace(
        orders=SimpleNamespace(open_orders=lambda: [resting]))
    assert main_mod.LiquidityBot._has_resting_profit_take(fake, pos) is True

    fake_none = SimpleNamespace(orders=SimpleNamespace(open_orders=lambda: []))
    assert main_mod.LiquidityBot._has_resting_profit_take(fake_none, pos) is False

    entry_order = SimpleNamespace(purpose="entry", position_id="p1",
                                  post_only=True)
    fake_entry = SimpleNamespace(
        orders=SimpleNamespace(open_orders=lambda: [entry_order]))
    assert main_mod.LiquidityBot._has_resting_profit_take(fake_entry, pos) is False

    # marketable (non-resting) exit order: not a maker take
    marketable = SimpleNamespace(purpose="exit", position_id="p1",
                                 post_only=False)
    fake_mkt = SimpleNamespace(
        orders=SimpleNamespace(open_orders=lambda: [marketable]))
    assert main_mod.LiquidityBot._has_resting_profit_take(fake_mkt, pos) is False


# ============================================================================
# Fix 2: algo-parent admission asymmetry
# ============================================================================
def _algo_bot_shell(order_results, recorded, algo_meta=None):
    """Minimal self for _submit_algo_child. order_results supplies
    sequential orders.submit() returns (None = rejected child).
    recorded captures every _record_probe_admission(is_probe) call."""
    results = iter(order_results)

    def fake_submit(**kw):
        return next(results)

    seqs = iter(range(1, 20))
    return SimpleNamespace(
        _algo_meta=algo_meta if algo_meta is not None else {"par1": {"probe": True}},
        view={"ETH": {"candles": []}}, state=SimpleNamespace(),
        marks={"ETH/USD": 2000.0},
        kraken_books={"ETH": {"bids": [[1999.0, 5]], "asks": [[2001.0, 5]]}},
        fv=SimpleNamespace(state=lambda a: SimpleNamespace(kraken_mid=2000.0,
                                                           fair_value=2000.0)),
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=0.3)),
        liq=SimpleNamespace(state=lambda a: SimpleNamespace(label="normal")),
        inventory=SimpleNamespace(inventory_ratio=lambda *a, **k: 0.0),
        quoter=SimpleNamespace(quote=lambda *a, **k: SimpleNamespace(
            bid=1999.0, ask=2001.0)),
        tactics=SimpleNamespace(plan_entry=lambda *a, **k: SimpleNamespace(
            price=2000.0, post_only=True, style="passive")),
        pretrade=SimpleNamespace(maker_fee_bps=1.0),
        kraken=SimpleNamespace(kraken_pair=lambda s: "XETHZUSD"),
        _equity=lambda: 10_000.0, _px=lambda s, p: f"{p:.2f}",
        orders=SimpleNamespace(submit=fake_submit),
        algo=SimpleNamespace(
            next_slice=lambda pid, now, vol: ChildSlice("par1", 1.0,
                                                        next(seqs), 4),
            note_child_order=lambda pid, posid: None,
            note_child_rejected=lambda *a, **k: None),
        _record_probe_admission=lambda is_probe: recorded.append(bool(is_probe)),
    )


def _parent1():
    return SimpleNamespace(parent_id="par1", asset="ETH", symbol="ETH/USD",
                           side="buy", direction="long", arrival_price=2000.0,
                           urgency=0.0)


def test_algo_rejected_first_child_leaves_admission_window_untouched():
    recorded = []
    b = _algo_bot_shell([None], recorded)          # the only child is rejected
    main_mod.LiquidityBot._submit_algo_child(b, _parent1(), now=1000.0)
    assert recorded == [], ("a parent whose first child is rejected must "
                            "record NO admission")


def test_algo_successful_children_record_exactly_one_admission_per_parent():
    recorded = []
    order = SimpleNamespace(order_id="o", position_id="algo-par1")
    b = _algo_bot_shell([order, order, order], recorded)
    for _ in range(3):
        main_mod.LiquidityBot._submit_algo_child(b, _parent1(), now=1000.0)
    assert recorded == [True], ("exactly ONE admission per parent - not "
                                "one per child")


def test_algo_admission_recorded_reject_then_success_records_once():
    """First child rejected (no admission), second child lands - THAT is
    the parent's first successful submit, so exactly one admission fires
    there, none earlier and none again on a third success."""
    recorded = []
    order = SimpleNamespace(order_id="o", position_id="algo-par1")
    b = _algo_bot_shell([None, order, order], recorded)
    for _ in range(3):
        main_mod.LiquidityBot._submit_algo_child(b, _parent1(), now=1000.0)
    assert recorded == [True]


def test_algo_conviction_parent_records_false():
    recorded = []
    order = SimpleNamespace(order_id="o", position_id="algo-par1")
    b = _algo_bot_shell([order], recorded, algo_meta={"par1": {"probe": False}})
    main_mod.LiquidityBot._submit_algo_child(b, _parent1(), now=1000.0)
    assert recorded == [False]


def test_engine_no_longer_records_admission_at_algo_parent_creation():
    """Structural pin: the algo-parent-creation call site (entry loop) must
    NOT call _record_probe_admission directly any more - only the direct
    and ladder paths do; the algo path's admission now lives inside
    _submit_algo_child, gated on the first successful child."""
    # locate the algo-engage block directly in main.py's source instead of
    # depending on a specific method name (kept resilient to refactors)
    full_src = Path(main_mod.__file__).read_text(encoding="utf-8")
    idx = full_src.index("self.algo.create_parent(")
    # the window between create_parent(...) and the first slice call must
    # NOT contain a probe-admission record - it now happens inside
    # _submit_algo_child on the first successful child submit
    window_end = full_src.index("self._submit_algo_child(parent, now)", idx)
    window = full_src[idx:window_end]
    assert "_record_probe_admission" not in window


# ============================================================================
# Fix 4 (config side): W2-28 checksum-backoff config_guard validation. The
# ws_feed.py-side backoff behavior itself is pinned in tests/test_ws_feed.py.
# ============================================================================
def test_shipped_config_has_no_fatal_findings():
    import core.config_guard as g
    assert not [m for s, m in g.validate(_CFG) if s == "FATAL"]


def test_config_guard_fatals_nonpositive_checksum_backoff_base():
    import core.config_guard as g
    bad = json.loads(json.dumps(_CFG))
    bad["websockets"]["kraken_checksum_backoff_base_s"] = 0.0
    assert any("kraken_checksum_backoff_base_s" in str(x)
              for s, x in [(s, m) for s, m in g.validate(bad) if s == "FATAL"])


def test_config_guard_fatals_cap_below_base():
    import core.config_guard as g
    bad = json.loads(json.dumps(_CFG))
    bad["websockets"]["kraken_checksum_backoff_base_s"] = 5.0
    bad["websockets"]["kraken_checksum_backoff_cap_s"] = 1.0
    findings = g.validate(bad)
    assert any(s == "FATAL" and "kraken_checksum_backoff_cap_s" in m
              for s, m in findings)


def test_config_guard_warns_excessive_checksum_backoff_cap():
    import core.config_guard as g
    bad = json.loads(json.dumps(_CFG))
    bad["websockets"]["kraken_checksum_backoff_cap_s"] = 1000.0
    findings = g.validate(bad)
    assert any("kraken_checksum_backoff_cap_s" in m for s, m in findings)
    assert not any(s == "FATAL" and "kraken_checksum_backoff_cap_s" in m
                  for s, m in findings)
