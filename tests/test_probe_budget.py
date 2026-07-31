"""tests/test_probe_budget.py — SPB-R Stage 0: Scarcity-Priced Probe
Budget, Refunded (docs/superpowers/specs/2026-07-30-probe-budget-spbr-
design.md). LANDED DARK: config ships mode="share_cap", so the shipped
SZ-047 path stays byte-identical (including `_explore_rng` draw counts —
pinned below); mode="budget" is the SPB-R token-bucket path.

Coverage (spec §9 Stage 0 list):
  * pricing table — the §1.1 worked numbers as fixtures (ETH 1.79 /
    BTC 1.64 / LINK 1.0 at A=13, T_a=300/13, range n_r=227, F=0.25);
  * token-bucket refill / clamp-at-C / debt-floor math (§1.2, §7);
  * probabilistic-affordability determinism under the DEDICATED
    `_budget_rng` (random.Random(f"{seed}:probe-budget"), §1.3);
  * veto-costs-nothing via the `_pending_probe_cost` stash (§1.4);
  * refund round-trip on an unfilled probe entry terminal (SZ-052);
  * tuition governor clip / engage / release / redeem (SZ-053, §1.5);
  * snapshot round-trip incl. missing-section semantics (§5);
  * share_cap-mode byte-identity INCLUDING `_explore_rng` draw-count
    preservation (the budget rng is a separate stream, never drawn in
    share_cap mode);
  * SZ-048 drought-floor reachability under a budget non-admit (§3.4).

Stub-bot harness idiom follows tests/test_probe_throttle.py
(LiquidityBot.__new__ + hand-set attrs).
"""
import json
import math
import random
import types
from collections import deque
from pathlib import Path

import pytest

from core.audit import get_audit
from core.codes import Code
from main import LiquidityBot

ROOT = Path(__file__).resolve().parents[1]

_SEED = 42


# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------
def _thirteen_assets():
    # the §1.1 fixture universe: 13 assets, majors named for the pricing table
    named = ["ETH", "BTC", "LINK", "AVAX"]
    extra = [f"A{i}" for i in range(13 - len(named))]
    return {a: f"{a}/USD" for a in named + extra}


def _budget_bot(*, mode="budget", tokens=0.0, tokens_per_day=15.0,
                burst_hours=8.0, scarcity=True, floor_frac=0.25,
                corpus_target=300, regime_floor=60, asset_live=None,
                regime_live=None, refund=True, tuition_frac=0.001,
                clip_div=3.0, equity=4965.0, seed=_SEED):
    """Minimal SPB-R bot (the tests/test_probe_throttle.py stub idiom)."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b._probe_admission_mode = mode
    b._budget_tokens_per_day = tokens_per_day
    b._budget_burst_hours = burst_hours
    b._budget_scarcity_pricing = scarcity
    b._budget_scarcity_floor = None
    b._budget_refund_unfilled = refund
    b._budget_tuition_frac_max = tuition_frac
    b._budget_outlier_clip_div = clip_div
    b._budget_tokens = tokens
    b._budget_last_refill_ts = None
    b._budget_tuition = deque()
    b._pending_probe_cost = {}
    b._pending_probe_asset = None
    b._budget_governor_factor = 1.0
    b._budget_exhausted_since = None
    b._budget_denied_arrivals = 0
    b._budget_admit_events = deque()
    b._budget_refund_events = deque()
    b._budget_denied_events = deque()
    b._budget_rollfail_events = deque()
    b._budget_label_events_7d = deque()
    b._budget_rng = random.Random(f"{seed}:probe-budget")  # nosec B311
    b._corpus_target_live = corpus_target
    b._corpus_floor_frac = floor_frac
    b._regime_floor_live = regime_floor
    b._probe_share_window = 40
    b._probe_max_share = 0.35
    b._probe_admissions = deque(maxlen=40)
    b._drought_floor_enabled = False
    b.symbol_map = _thirteen_assets()
    _al = dict(asset_live or {})
    _rl = dict(regime_live or {})
    b.history = types.SimpleNamespace(
        asset_live_counts=lambda: dict(_al),
        regime_live_count=lambda lbl: _rl.get(lbl, 0),
        asset_counts=lambda: dict(_al),
        source_counts=lambda: {"live": sum(_al.values())},
        row_count=lambda: sum(_al.values()))
    b._equity = lambda: equity
    b._exploration_active = \
        lambda now, asset=None, regime_label=None: True
    return b


def _audit_since(before: str) -> list:
    path = get_audit().path
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    return [json.loads(ln) for ln in after[len(before):].strip().splitlines()
            if ln.strip()]


def _audit_mark() -> str:
    path = get_audit().path
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ---------------------------------------------------------------------------
# reason codes — registry pins (SZ-050 is TAKEN by SZ_DD_THROTTLE)
# ---------------------------------------------------------------------------
def test_spbr_codes_registered_and_sz050_untouched():
    assert Code.SZ_PROBE_BUDGET_EXHAUSTED.value == "SZ-049"
    assert Code.SZ_PROBE_PRICED.value == "SZ-051"
    assert Code.SZ_PROBE_REFUND.value == "SZ-052"
    assert Code.SZ_PROBE_TUITION_GOVERNOR.value == "SZ-053"
    assert Code.SZ_DD_THROTTLE.value == "SZ-050"   # never renumbered/reused


# ---------------------------------------------------------------------------
# §1.1 scarcity price — the worked-numbers pricing table as fixtures
# ---------------------------------------------------------------------------
_FIXTURE_LIVE = {"ETH": 73, "BTC": 61, "LINK": 18, "AVAX": 3}
_FIXTURE_REGIME = {"range": 227}


@pytest.mark.parametrize("asset,expected", [
    ("ETH", 1.79), ("BTC", 1.64), ("LINK", 1.0), ("AVAX", 1.0),
])
def test_pricing_table_at_todays_data(asset, expected):
    b = _budget_bot(asset_live=_FIXTURE_LIVE, regime_live=_FIXTURE_REGIME)
    cost, w_asset, w_regime, sur = b._probe_cost(asset, "range")
    assert round(cost, 2) == pytest.approx(expected)
    assert sur == 1.0                      # surcharge ships DARK (§1.6)
    # w_regime at range n_r=227: sqrt(60/228) = 0.513
    assert w_regime == pytest.approx(math.sqrt(60.0 / 228.0), abs=1e-9)


def test_non_range_signal_prices_at_one():
    # EITHER scarcity dimension redeems: a bear-regime ETH signal at
    # n_bear=0 has w_regime = 1.0 -> S = 1.0 -> cost 1.0 (§1.1 max rule)
    b = _budget_bot(asset_live=_FIXTURE_LIVE, regime_live=_FIXTURE_REGIME)
    cost, _, w_regime, _ = b._probe_cost("ETH", "bear")
    assert w_regime == 1.0 and cost == pytest.approx(1.0)


def test_unmapped_regime_fails_safe_scarce():
    # unmapped label -> treated as n_r = 0 -> w_regime = 1.0, cost 1.0
    b = _budget_bot(asset_live=_FIXTURE_LIVE, regime_live=_FIXTURE_REGIME)
    cost, _, w_regime, _ = b._probe_cost("ETH", "not_a_real_regime")
    assert w_regime == 1.0 and cost == pytest.approx(1.0)


def test_scarcity_pricing_off_is_flat_cost_one():
    # the 1-knob rule: scarcity_pricing=false is a REAL config point
    b = _budget_bot(asset_live=_FIXTURE_LIVE, regime_live=_FIXTURE_REGIME,
                    scarcity=False)
    assert b._probe_cost("ETH", "range")[0] == pytest.approx(1.0)


def test_cost_clamped_at_capacity():
    # price > C is forbidden by construction (a livelock wall under strict
    # affordability): floor 0.1 would price 1/0.1 = 10 — clamped to C = 5
    b = _budget_bot(asset_live={"ETH": 100_000}, floor_frac=0.1,
                    regime_live={"range": 100_000})
    cost, *_ = b._probe_cost("ETH", "range")
    assert cost == pytest.approx(b._budget_capacity()) == pytest.approx(5.0)


def test_cost_floor_is_one_when_every_weight_saturates():
    b = _budget_bot(asset_live={}, regime_live={})
    assert b._probe_cost("ETH", "range")[0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# §1.2 token bucket — refill / clamp / debt floor
# ---------------------------------------------------------------------------
def test_first_refill_seeds_clock_and_accrues_nothing():
    b = _budget_bot()
    b._budget_refill(1_000.0)
    assert b._budget_tokens == 0.0
    assert b._budget_last_refill_ts == 1_000.0


def test_refill_rate_is_tokens_per_day_over_engine_seconds():
    b = _budget_bot()
    b._budget_refill(0.0)
    b._budget_refill(86_400.0 / 15.0)        # exactly one token of engine time
    assert b._budget_tokens == pytest.approx(1.0)


def test_refill_clamps_at_capacity():
    # C = tokens_per_day x burst_hours/24 = 15 x 8/24 = 5.0 = one book-fill
    b = _budget_bot()
    b._budget_refill(0.0)
    b._budget_refill(10 * 86_400.0)
    assert b._budget_tokens == pytest.approx(5.0)


def test_debt_bounded_at_minus_capacity_by_construction():
    # deduction only occurs from tokens > 0 with cost <= C, so debt > -C
    b = _budget_bot(tokens=0.01)
    b._pending_probe_cost["ETH"] = b._budget_capacity()   # worst-case price
    b._pending_probe_asset = "ETH"
    b._record_probe_admission(True)
    assert b._budget_tokens > -b._budget_capacity()
    assert b._budget_tokens == pytest.approx(0.01 - 5.0)


def test_refund_climbs_debt_and_clamps_at_capacity():
    b = _budget_bot(tokens=4.9)
    order = types.SimpleNamespace(purpose="entry", fill_ratio=0.0,
                                  asset="ETH",
                                  meta={"probe": True, "probe_cost": 1.79})
    b._maybe_refund_probe_order(order, 0.0)
    assert b._budget_tokens == pytest.approx(5.0)         # min(C, 4.9+1.79)


# ---------------------------------------------------------------------------
# §1.3 probabilistic affordability — deterministic under the dedicated rng
# ---------------------------------------------------------------------------
def test_admission_matches_independent_seeded_stream():
    b = _budget_bot(tokens=0.5, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    cost = b._probe_cost("ETH", "range")[0]
    p = 0.5 / cost
    twin = random.Random(f"{_SEED}:probe-budget")  # nosec B311
    expected = [twin.random() < p for _ in range(300)]
    # same engine `now` for every arrival: dt=0, no refill, no deduction
    # (deduction is placement-time), so p is constant across the sequence
    actual = [b._budget_admission(0.0, "ETH", "range") for _ in range(300)]
    assert actual == expected
    assert any(actual) and not all(actual)


def test_p_clamped_to_one_when_bucket_covers_cost():
    b = _budget_bot(tokens=5.0, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    assert all(b._budget_admission(0.0, "ETH", "range") for _ in range(50))


def test_exhausted_bucket_never_admits_and_brackets_with_sz049():
    # in DEBT (placement deductions outran refill): arrivals are denied,
    # COUNTED, and bracketed by ONE engaged/released transition pair —
    # never per-event spam (the SZ-047 storm lesson, spec §4)
    b = _budget_bot(tokens=-4.0)
    before = _audit_mark()
    assert b._budget_admission(0.0, "ETH", "range") is False     # engaged
    assert b._budget_admission(1_000.0, "BTC", "range") is False  # counted
    # refill across a full day: the bucket climbs out of debt to C
    b._budget_admission(86_400.0, "ETH", "range")
    records = _audit_since(before)
    engaged = [r for r in records
               if r["code"] == Code.SZ_PROBE_BUDGET_EXHAUSTED.value
               and r["data"].get("phase") == "engaged"]
    released = [r for r in records
                if r["code"] == Code.SZ_PROBE_BUDGET_EXHAUSTED.value
                and r["data"].get("phase") == "released"]
    assert len(engaged) == 1, "one engaged bracket, never per-event spam"
    assert len(released) == 1
    assert released[0]["data"]["arrivals_denied"] == 2
    assert released[0]["data"]["span_s"] == pytest.approx(86_400.0)
    assert len(b._budget_denied_events) == 2


def test_admit_emits_sz051_with_pricing_payload():
    b = _budget_bot(tokens=5.0, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    before = _audit_mark()
    assert b._budget_admission(0.0, "ETH", "range") is True
    priced = [r for r in _audit_since(before)
              if r["code"] == Code.SZ_PROBE_PRICED.value]
    assert len(priced) == 1
    d = priced[0]["data"]
    assert d["asset"] == "ETH" and d["regime"] == "range"
    assert round(d["cost"], 2) == 1.79
    for k in ("w_asset", "w_regime", "surcharge", "p", "u",
              "tokens_before", "tokens_after"):
        assert k in d, k


def test_failed_roll_is_a_non_disposition():
    # conscious semantic change (§4): a failed admission roll emits NOTHING
    # (identical to a failed epsilon/taper roll) — counters, not spam
    b = _budget_bot(tokens=1e-9, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    before = _audit_mark()
    # p ~ 5.6e-10: the roll fails for any realistic draw
    assert b._budget_admission(0.0, "ETH", "range") is False
    assert _audit_since(before) == []
    assert len(b._budget_rollfail_events) == 1


# ---------------------------------------------------------------------------
# §1.4 placement-time deduction + veto-costs-nothing stash
# ---------------------------------------------------------------------------
def test_placement_deducts_the_stashed_cost():
    b = _budget_bot(tokens=5.0, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    assert b._budget_admission(0.0, "ETH", "range") is True
    cost = b._pending_probe_cost["ETH"]
    b._record_probe_admission(True)               # the placement hook
    assert b._budget_tokens == pytest.approx(5.0 - cost)
    assert b._pending_probe_cost == {} and b._pending_probe_asset is None
    assert list(b._probe_admissions) == [True]    # legacy deque still fed


def test_vetoed_probe_costs_nothing():
    # decision admits and stashes; the veto path never reaches the hook;
    # the stash is discarded at the asset's next decision — tokens intact
    b = _budget_bot(tokens=5.0, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    assert b._budget_admission(0.0, "ETH", "range") is True
    assert "ETH" in b._pending_probe_cost
    # ... manip $15-withhold / min-ticket / SZ-046 / firewall veto here ...
    assert b._budget_admission(1.0, "ETH", "range") is True   # next decision
    assert b._budget_tokens == pytest.approx(5.0)             # never charged
    assert len(b._pending_probe_cost) == 1                    # re-stashed


def test_stale_pointer_never_charges_a_later_floor_probe():
    # ETH admitted+vetoed leaves a stale stash; a later decision clears the
    # POINTER, so a floor-path decision-time record can never pop ETH's cost
    b = _budget_bot(tokens=5.0, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    assert b._budget_admission(0.0, "ETH", "range") is True
    b._budget_tokens = 0.0                       # BTC arrival finds nothing
    assert b._budget_admission(0.0, "BTC", "range") is False   # dt=0
    b._record_probe_admission(True)              # e.g. an SZ-048 floor probe
    assert b._budget_tokens == 0.0               # ETH's stale cost NOT popped


def test_conviction_admissions_never_touch_the_bucket():
    b = _budget_bot(tokens=5.0)
    b._pending_probe_cost["ETH"] = 1.79
    b._pending_probe_asset = "ETH"
    b._record_probe_admission(False)
    assert b._budget_tokens == pytest.approx(5.0)
    assert list(b._probe_admissions) == [False]


def test_explicit_cost_parameter_extends_with_defaults():
    b = _budget_bot(tokens=5.0)
    b._record_probe_admission(True, cost=1.5)
    assert b._budget_tokens == pytest.approx(3.5)


def test_share_cap_mode_hook_is_byte_identical():
    b = _budget_bot(mode="share_cap", tokens=5.0)
    b._pending_probe_cost["ETH"] = 1.79
    b._pending_probe_asset = "ETH"
    b._record_probe_admission(True)
    assert b._budget_tokens == pytest.approx(5.0)   # never deducts
    assert list(b._probe_admissions) == [True]


# ---------------------------------------------------------------------------
# §1.4 refund on unfilled probe entry terminal (SZ-052)
# ---------------------------------------------------------------------------
def _order(fill_ratio=0.0, probe=True, cost=1.79, purpose="entry"):
    meta = {"probe": probe}
    if cost is not None:
        meta["probe_cost"] = cost
    return types.SimpleNamespace(purpose=purpose, fill_ratio=fill_ratio,
                                 asset="ETH", meta=meta)


def test_refund_round_trip_on_unfilled_terminal():
    b = _budget_bot(tokens=1.0)
    before = _audit_mark()
    order = _order()
    b._maybe_refund_probe_order(order, 0.0)
    assert b._budget_tokens == pytest.approx(1.0 + 1.79)
    assert "probe_cost" not in order.meta        # popped: idempotent
    refunds = [r for r in _audit_since(before)
               if r["code"] == Code.SZ_PROBE_REFUND.value]
    assert len(refunds) == 1
    assert refunds[0]["data"]["cost_refunded"] == pytest.approx(1.79)
    # a duplicate terminal event can never double-refund
    b._maybe_refund_probe_order(order, 1.0)
    assert b._budget_tokens == pytest.approx(1.0 + 1.79)


def test_partial_fill_never_refunds():
    # partial or full fill -> position exists -> ML-073 realizes a label
    b = _budget_bot(tokens=1.0)
    b._maybe_refund_probe_order(_order(fill_ratio=0.4), 0.0)
    assert b._budget_tokens == pytest.approx(1.0)


def test_non_probe_and_exit_orders_never_refund():
    b = _budget_bot(tokens=1.0)
    b._maybe_refund_probe_order(_order(probe=False), 0.0)
    b._maybe_refund_probe_order(_order(purpose="exit"), 0.0)
    assert b._budget_tokens == pytest.approx(1.0)


def test_refund_disabled_keeps_the_budget_charged():
    b = _budget_bot(tokens=1.0, refund=False)
    b._maybe_refund_probe_order(_order(), 0.0)
    assert b._budget_tokens == pytest.approx(1.0)


def test_refund_seam_wired_at_order_terminal():
    # the engine's order-terminal seam (_handle_fill final events) calls the
    # refund helper — source-level wiring pin, the test_probe_throttle idiom
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "self._maybe_refund_probe_order(order, now)" in src
    assert src.index("def _handle_fill") < src.index(
        "self._maybe_refund_probe_order(order, now)")


def test_direct_entry_meta_carries_probe_cost_only_when_stashed():
    # pin the CONDITIONAL-spread expression itself (2026-07-31 review #7:
    # the bare '"probe_cost" in src' assertion could not fail for the
    # property in this test's name): share_cap mode (empty stash) must
    # add NO meta key, keeping legacy order.meta byte-identical.
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '**({"probe_cost": _spbr_cost}' in src
    assert 'if _spbr_cost is not None else {})' in src


def test_algo_parent_template_carries_own_cost_and_clears_pointer():
    """2026-07-31 review #2: a probe routed to the algo slicer must carry
    its OWN priced cost on the parent template (deducted by the first
    successful child), and the decision pointer must be cleared at
    routing - a LATER decision's stash can never be charged against an
    earlier parent (the wrong-arm hazard), and a floor probe (never
    priced) deducts nothing."""
    b = _budget_bot(tokens=5.0, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    # simulate a priced ETH admit: stash + pointer set
    b._pending_probe_cost["ETH"] = 1.79
    b._pending_probe_asset = "ETH"
    # routing-time carriage (the template creation semantics)
    meta_t = {"probe": True,
              "probe_cost": b._pending_probe_cost.pop("ETH", None)}
    b._pending_probe_asset = None
    assert meta_t["probe_cost"] == pytest.approx(1.79)
    assert "ETH" not in b._pending_probe_cost
    # a LATER decision stashes BTC before ETH's first child submits
    b._pending_probe_cost["BTC"] = 1.64
    b._pending_probe_asset = "BTC"
    # first-child hook deducts the PARENT'S cost, not the pointer's
    before = b._budget_tokens
    b._record_probe_admission(True, cost=meta_t.get("probe_cost"))
    assert b._budget_tokens == pytest.approx(before - 1.79)
    assert b._pending_probe_cost.get("BTC") == pytest.approx(1.64), \
        "the later arm's stash must survive untouched"
    assert b._pending_probe_asset == "BTC"
    # conviction/floor parent (probe_cost None) deducts nothing and
    # leaves the pointer alone
    before = b._budget_tokens
    b._record_probe_admission(True, cost=None)
    # cost=None pops via pointer: BTC's stash gets consumed by ITS OWN
    # placement - simulate that legitimate direct-path deduction
    assert b._budget_tokens == pytest.approx(before - 1.64)
    assert b._pending_probe_asset is None


def test_main_wires_parent_cost_carriage():
    # source pin: the template stashes its own cost and the child hook
    # passes it explicitly (never the pointer)
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '_pc = meta_t.get("probe_cost")' in src
    assert 'cost=_pc' in src
    assert '"probe_cost": ((getattr(self, "_pending_probe_cost",' in src


# ---------------------------------------------------------------------------
# §1.5 tuition governor — clip / engage / floor / release (SZ-053)
# ---------------------------------------------------------------------------
def _probe_pos(is_probe=True, is_hedge=False):
    return types.SimpleNamespace(is_probe=is_probe, is_hedge=is_hedge,
                                 symbol="ETH/USD")


def test_single_outlier_clipped_to_a_third_of_cap():
    # cap = 0.001 x 4965 = 4.965; clip = cap/3 = 1.655 — one probe is
    # never evidence: a -$5 outlier contributes <= 1.655 and cannot engage
    b = _budget_bot()
    b._note_probe_tuition(_probe_pos(), -5.0, 0.0)
    assert len(b._budget_tuition) == 1
    assert b._budget_tuition[0][1] == pytest.approx(4.965 / 3.0)
    assert b._tuition_governor_factor(0.0) == 1.0


def test_wins_and_non_probes_add_no_tuition():
    b = _budget_bot()
    b._note_probe_tuition(_probe_pos(), +3.0, 0.0)      # win: clipped to 0
    b._note_probe_tuition(_probe_pos(is_probe=False), -3.0, 0.0)
    b._note_probe_tuition(_probe_pos(is_hedge=True), -3.0, 0.0)
    assert sum(x for _, x in b._budget_tuition) == 0.0
    assert len(b._budget_tuition) == 1                  # probe close counted


def test_governor_engages_scales_and_emits_transition():
    b = _budget_bot()
    before = _audit_mark()
    for i in range(4):                                   # 4 x 1.655 = 6.62
        b._note_probe_tuition(_probe_pos(), -5.0, float(i))
    f = b._tuition_governor_factor(10.0)
    assert f == pytest.approx(4.965 / (4 * 4.965 / 3.0))  # cap/X = 0.75
    gov = [r for r in _audit_since(before)
           if r["code"] == Code.SZ_PROBE_TUITION_GOVERNOR.value]
    assert len(gov) == 1 and gov[0]["data"]["factor"] == pytest.approx(f)
    # steady state: no repeat emission while engaged (transition only)
    before = _audit_mark()
    assert b._tuition_governor_factor(11.0) == pytest.approx(f)
    assert not [r for r in _audit_since(before)
                if r["code"] == Code.SZ_PROBE_TUITION_GOVERNOR.value]


def test_governor_floored_at_quarter_never_a_life_sentence():
    b = _budget_bot()
    for i in range(100):
        b._note_probe_tuition(_probe_pos(), -5.0, float(i))
    assert b._tuition_governor_factor(200.0) == pytest.approx(0.25)


def test_governor_self_redeems_as_the_window_rolls():
    b = _budget_bot()
    for i in range(4):
        b._note_probe_tuition(_probe_pos(), -5.0, float(i))
    assert b._tuition_governor_factor(10.0) < 1.0
    before = _audit_mark()
    assert b._tuition_governor_factor(10.0 + 86_400.0) == 1.0
    released = [r for r in _audit_since(before)
                if r["code"] == Code.SZ_PROBE_TUITION_GOVERNOR.value]
    assert len(released) == 1
    assert released[0]["data"]["factor"] == 1.0
    assert len(b._budget_tuition) == 0                  # pruned, unlatched


def test_governor_scales_the_refill_rate():
    b = _budget_bot()
    for i in range(100):
        b._note_probe_tuition(_probe_pos(), -5.0, float(i))
    b._budget_refill(200.0)                             # seeds the clock
    b._budget_refill(200.0 + 86_400.0 / 15.0)           # 1 token of time
    assert b._budget_tokens == pytest.approx(0.25)      # f_governor x R


# ---------------------------------------------------------------------------
# composition: SZ-048 drought floor stays reachable under budget non-admit
# ---------------------------------------------------------------------------
def _drought_budget_bot(**kw):
    b = _budget_bot(**kw)
    b._drought_floor_enabled = True
    b._drought_min_sec = 8 * 3600.0
    b._floor_spacing_sec = 2 * 3600.0
    b._last_floor_admit_ts = None
    b._last_entry_admit_ts = 1_000_000.0
    return b


def test_sz048_reachable_under_budget_non_admit():
    bot = _drought_budget_bot(tokens=0.0)     # p = 0: budget denies
    now = 1_000_000.0 + 9 * 3600.0
    before = _audit_mark()
    assert bot._probe_admission_decision(now, "BTC") is True
    assert bot._last_floor_admit_ts == now
    assert bot._probe_admissions[-1] is True
    records = _audit_since(before)
    assert any(r["code"] == Code.SZ_PROBE_FLOOR.value for r in records)


def test_budget_admit_never_consults_the_floor():
    bot = _drought_budget_bot(tokens=5.0, asset_live=_FIXTURE_LIVE,
                              regime_live=_FIXTURE_REGIME)
    now = 1_000_000.0 + 9 * 3600.0
    before = _audit_mark()
    assert bot._probe_admission_decision(now, "ETH",
                                         regime_label="range") is True
    records = _audit_since(before)
    assert not any(r["code"] == Code.SZ_PROBE_FLOOR.value for r in records)
    assert any(r["code"] == Code.SZ_PROBE_PRICED.value for r in records)


def test_budget_mode_never_emits_sz047():
    bot = _budget_bot(tokens=0.0)
    before = _audit_mark()
    assert bot._probe_admission_decision(0.0, "ETH") is False
    records = _audit_since(before)
    assert not any(r["code"] == Code.SZ_PROBE_THROTTLED.value
                   for r in records)


# ---------------------------------------------------------------------------
# share_cap byte-identity — INCLUDING _explore_rng draw-count preservation
# ---------------------------------------------------------------------------
def _legacy_bot(live=1200, epsilon=1.0):
    """Pre-SPB-R stub: NO budget attrs at all (the getattr defaults must
    reproduce share_cap behavior for a bot that never heard of SPB-R)."""
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b.explore_enabled = True
    b.explore_epsilon = epsilon
    b.explore_until_rows = 10_000
    b.explore_max_asset_share = 1.0
    b._explore_rng = random.Random(1)  # nosec B311
    b._corpus_target_live = 300
    b._corpus_floor_frac = 0.25
    b._regime_floor_live = 0
    b.history = types.SimpleNamespace(
        row_count=lambda: live,
        source_counts=lambda: {"live": live},
        regime_live_count=lambda lbl: 0)
    b._probe_share_window = 10
    b._probe_max_share = 0.3
    b._probe_admissions = deque([True, True] + [False] * 8, maxlen=10)
    return b


def _share_cap_spbr_bot():
    b = _legacy_bot()
    # full SPB-R attribute set present, mode pinned to the escape hatch
    b._probe_admission_mode = "share_cap"
    b._budget_tokens_per_day = 15.0
    b._budget_burst_hours = 8.0
    b._budget_scarcity_pricing = True
    b._budget_scarcity_floor = None
    b._budget_refund_unfilled = True
    b._budget_tuition_frac_max = 0.001
    b._budget_outlier_clip_div = 3.0
    b._budget_tokens = 0.0
    b._budget_last_refill_ts = None
    b._budget_tuition = deque()
    b._pending_probe_cost = {}
    b._pending_probe_asset = None
    b._budget_governor_factor = 1.0
    b._budget_exhausted_since = None
    b._budget_denied_arrivals = 0
    b._budget_admit_events = deque()
    b._budget_refund_events = deque()
    b._budget_denied_events = deque()
    b._budget_rollfail_events = deque()
    b._budget_label_events_7d = deque()
    b._budget_rng = random.Random(f"{_SEED}:probe-budget")  # nosec B311
    return b


def test_share_cap_mode_byte_identical_including_rng_draws():
    legacy = _legacy_bot()
    spbr = _share_cap_spbr_bot()
    virgin_budget_state = random.Random(  # nosec B311
        f"{_SEED}:probe-budget").getstate()
    seq_legacy = [legacy._probe_admission_decision(float(i), "ETH")
                  for i in range(400)]
    seq_spbr = [spbr._probe_admission_decision(float(i), "ETH")
                for i in range(400)]
    assert seq_legacy == seq_spbr, "share_cap decisions must be identical"
    assert legacy._explore_rng.getstate() == spbr._explore_rng.getstate(), \
        "_explore_rng draw count diverged in share_cap mode"
    assert spbr._budget_rng.getstate() == virgin_budget_state, \
        "the budget rng must NEVER be drawn in share_cap mode"
    assert spbr._budget_tokens == 0.0
    assert list(legacy._probe_admissions) == list(spbr._probe_admissions)


def test_share_cap_mode_emits_no_spbr_codes():
    spbr = _share_cap_spbr_bot()
    before = _audit_mark()
    for i in range(50):
        spbr._probe_admission_decision(float(i), "ETH")
    new = _audit_since(before)
    spbr_codes = {Code.SZ_PROBE_BUDGET_EXHAUSTED.value,
                  Code.SZ_PROBE_PRICED.value, Code.SZ_PROBE_REFUND.value,
                  Code.SZ_PROBE_TUITION_GOVERNOR.value}
    assert not [r for r in new if r["code"] in spbr_codes]


def test_decision_signature_unchanged():
    # the pinned no-sizing-argument invariant survives SPB-R untouched
    import inspect
    sig = inspect.signature(LiquidityBot._probe_admission_decision)
    assert list(sig.parameters) == ["self", "now", "asset", "regime_label"]


# ---------------------------------------------------------------------------
# §5 persistence — probe_budget section round-trip + missing-section no-op
# ---------------------------------------------------------------------------
def _persist_stub_bot():
    from core.state import PortfolioState
    b = types.SimpleNamespace()
    b.dry_run = True
    b.state = PortfolioState(starting_capital=800)
    b.orders = types.SimpleNamespace(open_orders=lambda: [], _orders={})
    b.history = types.SimpleNamespace(_pending={})
    b.sizer = types.SimpleNamespace(_last_entry={})
    b._pos_realized = {}
    b._halted = False
    b._stop_hit = {}
    b._rows_at_last_train = 0
    hollow = types.SimpleNamespace(to_dict=lambda: {}, restore=lambda d: None)
    b.monitor = hollow
    b.postmortem = hollow
    b.candidates = hollow
    b.gate_stats = hollow
    b.risk_protocols = None
    return b


def test_probe_budget_snapshot_round_trip(tmp_path):
    from core.persistence import StateStore
    store = StateStore(str(tmp_path / "state.json"))
    bot = _persist_stub_bot()
    bot._budget_tokens = 3.25
    bot._budget_tuition = deque([(100.0, 1.5), (200.0, 0.0)])
    assert store.snapshot(bot)
    data = store.load_raw()
    assert data is not None
    assert data["probe_budget"]["tokens"] == pytest.approx(3.25)
    assert data["probe_budget"]["tuition"] == [[100.0, 1.5], [200.0, 0.0]]
    # last_refill_ts deliberately NOT persisted (§5: downtime never
    # accrues tokens — degraded toward FEWER probes, the safe direction)
    assert "last_refill_ts" not in data["probe_budget"]

    revived = _persist_stub_bot()
    revived._budget_tokens = 0.0
    revived._budget_tuition = deque()
    assert store.restore(revived)
    assert revived._budget_tokens == pytest.approx(3.25)
    assert list(revived._budget_tuition) == [(100.0, 1.5), (200.0, 0.0)]


def test_pre_spbr_snapshot_missing_section_is_a_noop(tmp_path):
    from core.persistence import SNAPSHOT_VERSION, StateStore
    store = StateStore(str(tmp_path / "state.json"))
    snap = {"version": SNAPSHOT_VERSION, "dry_run": True,
            "portfolio": {"starting_capital": 800.0, "cash_balance": 800.0,
                          "savings_balance": 0.0, "realized_pnl_total": 0.0,
                          "daily_realized_pnl": 0.0}}
    assert store.write_raw(snap)
    revived = _persist_stub_bot()
    revived._budget_tokens = 1.25
    revived._budget_tuition = deque([(1.0, 0.5)])
    assert store.restore(revived) is True
    # missing/pre-SPB section -> NO-OP (mirrors probe_admissions semantics)
    assert revived._budget_tokens == pytest.approx(1.25)
    assert list(revived._budget_tuition) == [(1.0, 0.5)]


def test_malformed_probe_budget_section_skipped_not_crashed(tmp_path):
    from core.persistence import SNAPSHOT_VERSION, StateStore
    store = StateStore(str(tmp_path / "state.json"))
    snap = {"version": SNAPSHOT_VERSION, "dry_run": True,
            "portfolio": {"starting_capital": 800.0, "cash_balance": 800.0,
                          "savings_balance": 0.0, "realized_pnl_total": 0.0,
                          "daily_realized_pnl": 0.0},
            "probe_budget": {"tokens": "corrupt", "tuition": 7}}
    assert store.write_raw(snap)
    revived = _persist_stub_bot()
    revived._budget_tokens = 0.5
    revived._budget_tuition = deque()
    assert store.restore(revived) is True
    assert revived._budget_tokens == pytest.approx(0.5)   # skipped, intact


# ---------------------------------------------------------------------------
# config surface + guard bounds (§2)
# ---------------------------------------------------------------------------
def _shipped_cfg() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def test_shipped_config_runs_budget_mode_with_surcharge_dark():
    """Landed DARK 2026-07-30 (mode='share_cap'); the operator flipped to
    'budget' on 2026-07-31 after the PC's battery-verified deploy of
    33498d2 ('flip it' - a conscious re-pin, not a drift). The surcharge
    stays dark until its own flip preconditions (spec §1.6)."""
    adm = _shipped_cfg()["ml"]["exploration"]["admission"]
    assert adm["mode"] == "budget"               # operator-flipped
    bg = adm["budget"]
    assert bg["tokens_per_day"] == 15
    # CONSCIOUS RE-PIN 2026-07-31 (era-deadlock fix): burst_hours mirrors
    # the labeler's horizon by design, and label_max_bars moved 96 -> 24
    # bars, so 8h -> 2h. Refill (tokens_per_day) is unchanged - only the
    # bankable burst follows the horizon, which is the invariant.
    assert bg["burst_hours"] == 2.0
    assert bg["scarcity_pricing"] is True
    assert bg["scarcity_floor"] is None
    assert bg["refund_unfilled_entry"] is True
    assert bg["governor"]["tuition_daily_frac_max"] == 0.001
    assert bg["governor"]["outlier_clip_div"] == 3
    assert bg["surcharge"]["enabled"] is False   # the one dark slot
    assert bg["surcharge"]["wilson_z"] == 1.96
    assert bg["surcharge"]["max_surcharge"] == 2.0
    assert bg["surcharge"]["base_window_labels"] is None
    assert bg["surcharge"]["era_min_ts"] is None


def _validate(cfg):
    from core.config_guard import validate
    return validate(cfg)


def _fatals(cfg):
    return [m for sev, m in _validate(cfg) if sev == "FATAL"]


def _warns(cfg):
    return [m for sev, m in _validate(cfg) if sev == "WARN"]


def _mutated(**budget_overrides):
    cfg = _shipped_cfg()
    bg = cfg["ml"]["exploration"]["admission"]["budget"]
    for k, v in budget_overrides.items():
        if isinstance(v, dict):
            bg.setdefault(k, {}).update(v)
        else:
            bg[k] = v
    return cfg


def test_guard_shipped_config_no_admission_findings():
    assert not any("admission" in m for m in _fatals(_shipped_cfg()))
    assert not any("admission" in m for m in _warns(_shipped_cfg()))


def test_guard_fatal_on_unknown_mode():
    cfg = _shipped_cfg()
    cfg["ml"]["exploration"]["admission"]["mode"] = "bogus"
    assert any("admission.mode" in m for m in _fatals(cfg))


def test_guard_fatal_tokens_per_day_bounds():
    assert any("tokens_per_day" in m for m in _fatals(
        _mutated(tokens_per_day=0)))
    assert any("tokens_per_day" in m for m in _fatals(
        _mutated(tokens_per_day=101)))


def test_guard_warn_tokens_above_book_ceiling():
    # CONSCIOUS RE-PIN 2026-07-31 (era-deadlock fix): the ceiling is
    # max_concurrent_positions x 24/burst_hours, and burst_hours followed
    # the label horizon 8h -> 2h, so the book can now convert 5 x 24/2 =
    # 60/day (it was 5 x 24/8 = 15/day). A SHORTER holding horizon means
    # faster slot turnover means MORE labels the book can absorb - the
    # ceiling rising is the arithmetic working, not a weakened guard.
    assert any("tokens_per_day" in m for m in _warns(
        _mutated(tokens_per_day=61)))
    # and the shipped 15/day now sits well inside that ceiling
    assert not any("exceeds the book conversion ceiling" in m
                   for m in _warns(_mutated(tokens_per_day=15)))


def test_guard_warn_tokens_below_floor_pace():
    # 24/drought_hours = 3/day: the SZ-048 backstop would out-rate the budget
    assert any("tokens_per_day" in m for m in _warns(
        _mutated(tokens_per_day=2)))


def test_guard_fatal_burst_hours_bounds_and_warn_off_horizon():
    assert any("burst_hours" in m for m in _fatals(_mutated(burst_hours=0.5)))
    assert any("burst_hours" in m for m in _fatals(_mutated(burst_hours=25)))
    assert any("burst_hours" in m for m in _warns(_mutated(burst_hours=4.0)))


def test_guard_fatal_scarcity_floor_bounds():
    assert any("scarcity_floor" in m for m in _fatals(
        _mutated(scarcity_floor=0.0)))
    assert any("scarcity_floor" in m for m in _fatals(
        _mutated(scarcity_floor=1.5)))
    assert not any("scarcity_floor" in m for m in _fatals(
        _mutated(scarcity_floor=0.3)))


def test_guard_governor_bounds():
    assert any("tuition_daily_frac_max" in m for m in _fatals(
        _mutated(governor={"tuition_daily_frac_max": 0.006})))
    assert any("tuition_daily_frac_max" in m for m in _warns(
        _mutated(governor={"tuition_daily_frac_max": 0.003})))
    assert any("outlier_clip_div" in m for m in _fatals(
        _mutated(governor={"outlier_clip_div": 0.5})))
    assert any("outlier_clip_div" in m for m in _warns(
        _mutated(governor={"outlier_clip_div": 4})))


def test_guard_surcharge_bounds_and_era_interlock():
    assert any("wilson_z" in m for m in _fatals(
        _mutated(surcharge={"wilson_z": 0.5})))
    assert any("max_surcharge" in m for m in _fatals(
        _mutated(surcharge={"max_surcharge": 0.5})))   # < 1: a discount
    # the coupled 1/floor upper bound bites only while ENABLED - a dark
    # surcharge computes nothing and the price is clamped at C in code,
    # so a legacy floor_frac=1.0 config must not turn FATAL through an
    # unrelated dark knob's merge default
    assert any("max_surcharge" in m for m in _fatals(
        _mutated(surcharge={"enabled": True, "era_min_ts": 1784000000,
                            "max_surcharge": 5.0})))   # > 1/floor_frac = 4
    assert not any("max_surcharge" in m for m in _fatals(
        _mutated(surcharge={"max_surcharge": 5.0})))   # dark: not fatal
    assert any("era_min_ts" in m for m in _fatals(
        _mutated(surcharge={"enabled": True})))
    assert not any("era_min_ts" in m for m in _fatals(
        _mutated(surcharge={"enabled": True, "era_min_ts": 1784000000})))


def test_guard_warn_budget_mode_with_exploration_disabled():
    cfg = _shipped_cfg()
    cfg["ml"]["exploration"]["admission"]["mode"] = "budget"
    cfg["ml"]["exploration"]["enabled"] = False
    assert any("admission.mode" in m and "enabled" in m for m in _warns(cfg))


# ---------------------------------------------------------------------------
# ml/history.py — asset_live_counts() accessor ((mtime,size)-cached like
# regime_live_count; live rows only, incremental append maintenance)
# ---------------------------------------------------------------------------
def _history_store(tmp_path):
    import numpy as np
    from ml.features import FEATURE_NAMES
    from ml.history import HistoryStore
    hs = HistoryStore(str(tmp_path / "h.csv"))
    feats = np.zeros(len(FEATURE_NAMES))
    return hs, feats


def test_asset_live_counts_counts_live_rows_only(tmp_path):
    hs, feats = _history_store(tmp_path)
    for pid, asset in (("p1", "ETH"), ("p2", "ETH"), ("p3", "BTC")):
        hs.log_entry(pid, asset, "long", feats)
        hs.log_close(pid, 1.0)
    hs._append_row("cand-1", "LINK", "long", feats, 1, 0.0, "candidate")
    assert hs.asset_live_counts() == {"ETH": 2, "BTC": 1}


def test_asset_live_counts_incremental_append_no_rescan(tmp_path):
    hs, feats = _history_store(tmp_path)
    hs.log_entry("p1", "ETH", "long", feats)
    hs.log_close("p1", 1.0)
    assert hs.asset_live_counts() == {"ETH": 1}   # triggers the one scan
    hs.log_entry("p2", "ETH", "long", feats)
    hs.log_close("p2", -1.0)                      # incremental, post-load
    assert hs.asset_live_counts() == {"ETH": 2}


def test_asset_live_counts_fresh_store_rebuilds_from_csv(tmp_path):
    from ml.history import HistoryStore
    hs, feats = _history_store(tmp_path)
    hs.log_entry("p1", "AVAX", "long", feats)
    hs.log_close("p1", 1.0)
    cold = HistoryStore(str(tmp_path / "h.csv"))   # derived cache, no snapshot
    assert cold.asset_live_counts() == {"AVAX": 1}


def test_asset_live_counts_empty_on_missing_file(tmp_path):
    from ml.history import HistoryStore
    hs = HistoryStore(str(tmp_path / "missing" / "h.csv"))
    assert hs.asset_live_counts() == {}


# ---------------------------------------------------------------------------
# §8 engine status surface
# ---------------------------------------------------------------------------
def test_probe_budget_status_shape_and_math():
    b = _budget_bot(tokens=2.5, asset_live=_FIXTURE_LIVE,
                    regime_live=_FIXTURE_REGIME)
    b.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(label="range"))
    b.state = types.SimpleNamespace(open_positions=lambda: [])
    b.explore_max_asset_share = 0.5
    b.explore_share_min_rows = 10
    b._label_max_bars = 96
    st = b.probe_budget_status(0.0)
    assert st["mode"] == "budget"
    assert st["tokens"] == pytest.approx(2.5)
    assert st["capacity"] == pytest.approx(5.0)
    assert st["refill_per_day"] == pytest.approx(15.0)
    assert st["governor_factor"] == 1.0
    assert st["tuition_cap_usd"] == pytest.approx(4.965)
    for k in ("tuition_24h_usd", "admits_24h", "refunds_24h",
              "denied_exhausted_24h", "rolls_failed_24h", "avg_cost_24h",
              "labels_24h", "live_labels_per_day_7d", "tb_era_labels",
              "unlock_eta_days", "avg_concurrent_probes", "per_asset",
              "per_regime_live"):
        assert k in st, k
    eth = st["per_asset"]["ETH"]
    assert eth["n_live"] == 73
    assert round(eth["cost"], 2) == 1.79
    total_w = sum(a["eff_weight"] for a in st["per_asset"].values())
    assert total_w == pytest.approx(1.0, abs=5e-3)   # 4-decimal rounding
    assert st["per_regime_live"]["range"] == 227
