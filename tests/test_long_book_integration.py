"""tests/test_long_book_integration.py — Compounder Phase C, Task C4:
engine integration for the long-horizon accumulation book
(_long_book_cycle, _place_long_book_add, _long_book_conviction_gate,
_long_book_deny in main.py; the book-aware exit routing in
_manage_open_position; the thesis-stop wiring in _handle_fill; the
"long_book" status section in runner.py; the ladder/last-add-ts/
history-pending-book persistence in core/persistence.py).

Two harnesses:
  * STUB bot (mirrors tests/test_conviction_integration.py's established
    pattern): a minimal `LiquidityBot.__new__(LiquidityBot)` with only the
    attributes _long_book_cycle/_manage_open_position/_handle_fill touch
    hand-set — real (cheap, network-free) engine instances
    (InventoryManager/RiskProtocolStack/PositionSizer/EvidenceLadder/
    ProfitTierEngine/regime engines), a FAKE OrderManager (records
    submit() calls, never touches Kraken/the firewall) and a FAKE
    Kraken. Used for the gate-chain/deny-path/routing/conviction-wiring/
    sizing-bound tests, where full-bot construction would be pure
    overhead.
  * FULL bot (mirrors tests/test_context_integration.py's established
    mocked-feeds harness): a real `LiquidityBot` over
    MockOKX/MockBinanceUS/MockKraken. Used for persistence round-trips
    (StateStore.snapshot/restore touches dozens of real bot attributes)
    and the one true end-to-end happy-path check (real OrderManager +
    RiskFirewall + collar, proving the wiring survives the real
    execution stack, not just a fake orders recorder).
"""
import csv
import json
import logging
import math
import types
from pathlib import Path

import numpy as np
import pytest

from core.codes import Code
from core.state import PortfolioState, Position
from data.context_engine import ContextState
from execution.inventory import InventoryManager
from execution.order_manager import ManagedOrder
from execution.pretrade import PreTradeGate
from main import LiquidityBot, load_config
from ml.features import FEATURE_NAMES
from regime import LiquidityRegimeEngine, MacroRegimeEngine, VolRegimeEngine
from risk.conviction import ConvictionFormula
from risk.long_book import AddPlan, EvidenceLadder, thesis_stop_price
from risk.position_sizer import PositionSizer
from risk.profit_tiers import ProfitTierEngine
from risk.protocols import RiskProtocolStack
from runner import BotRunner
from scripts.smoke_test import MockBinanceUS, MockKraken, MockOKX
from strategies.signal_gates import SignalResult

_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# shared config fixtures
# ---------------------------------------------------------------------------

# 5m book's own profit-tier geometry for the stub harness (tests/test_
# conviction_integration.py's sibling pattern: a small, self-contained
# config dict, not a read of config.json, so this module is not fragile
# to unrelated config.json tuning). Deliberately DIFFERENT close_pct from
# the long book's own tier_1 below - the "behavior pin" test tells the
# two engines apart by which close_pct actually fires.
_5M_PROFIT_TAKING = {
    "tier_1": {"trigger_pct_gain": 3.0, "close_pct_of_position": 25},
    "tier_2": {"trigger_pct_gain": 6.0, "close_pct_of_position": 25},
    "tier_3": {"trigger_pct_gain": 10.0, "close_pct_of_position": 25},
    "tier_4": {"trigger_pct_gain": 15.0, "close_pct_of_position": 25},
    "vol_scaled": False,
    "trailing_stop": {"enabled": False},
    "give_back": {"enabled": False},
    "time_stop": {"enabled": False},
}

LB_CFG = {
    "enabled": True,
    "assets": ["BTC", "ETH"],
    "add_usd_frac_of_ceiling": 0.5,
    "add_min_spacing_hours": 1.0,
    "add_offset_pct": 0.5,
    "zone_tol_pct": 0.15,
    "zone_buffer_pct": 0.2,
    "thesis_stop_pct": 12.0,
    "context": {"stress_max_for_add": 1.0, "require_known": True,
                "pause_in_event_window": True,
                "contraction_spacing_mult": 2.0},
    "ladder": {
        "r1": {"ceiling_frac": 0.1, "min_closed_paper": 10},
        "r2": {"ceiling_frac": 0.2, "min_closed_live": 15, "pf_floor": 1.2},
        "r3": {"ceiling_frac": 0.3, "min_closed_live": 30,
               "adverse_transitions_survived": 1},
        "dd_downgrade_pct": 6.0,
    },
    "profit_taking": {
        "tier_1": {"trigger_pct_gain": 8.0, "close_pct_of_position": 20},
        "tier_2": {"trigger_pct_gain": 15.0, "close_pct_of_position": 20},
        "tier_3": {"trigger_pct_gain": 25.0, "close_pct_of_position": 25},
        "tier_4": {"trigger_pct_gain": 40.0, "close_pct_of_position": 25},
        "vol_scaled": False,
        "trailing_stop": {"enabled": True, "activate_after_tier": 2,
                          "trail_pct": 8.0},
        "give_back": {"enabled": True, "arm_gain_pct": 5.0,
                     "giveback_frac": 0.35},
        "time_stop": {"enabled": False},
        "min_trigger_cost_mult": 3.0,
    },
}


def _aligned_ctx(**kw) -> ContextState:
    base = dict(halving_phase="expansion", stress=0.1, stress_known=True,
               in_event_window=False, calendar_known=True, ts=0.0)
    base.update(kw)
    return ContextState(**base)


def _unknown_ctx() -> ContextState:
    return ContextState(halving_phase="expansion", stress=None,
                        stress_known=False, in_event_window=False,
                        calendar_known=False, ts=0.0)


def _misaligned_ctx() -> ContextState:
    return _aligned_ctx(stress=5.0)   # > stress_max_for_add (1.0)


def _event_window_ctx() -> ContextState:
    return _aligned_ctx(in_event_window=True)


# ---------------------------------------------------------------------------
# STUB harness (fast, network-free, mirrors test_conviction_integration.py)
# ---------------------------------------------------------------------------

class _FakeOrders:
    """Records every submit() call (raw kwargs, `.calls` - unchanged shape,
    every existing call["..."] assertion keeps working) AND tracks
    accepted submissions as lightweight resting ManagedOrder objects
    (`.open_orders()`/`.cancel_order()`) so the C4-review cancel-and-
    replace / resting-notional-headroom / same-cycle double-commit tests
    can drive a SECOND _long_book_cycle pass against what the FIRST pass
    actually left resting - never touches Kraken/the firewall. `accept=
    False` simulates every OTHER order-manager-side refusal (firewall/
    venue-min/zero-format) a real OrderManager can return None for -
    _place_long_book_add must degrade to a no-op, never raise."""
    def __init__(self, accept: bool = True):
        self.calls: list = []
        self.accept = accept
        self._open: list = []
        self.cancelled: list = []

    def submit(self, **kwargs):
        self.calls.append(kwargs)
        if not self.accept:
            return None
        order = ManagedOrder(
            order_id=f"fake-{len(self.calls)}", txid=None,
            asset=kwargs.get("asset"), pair=kwargs.get("pair", ""),
            symbol=kwargs.get("symbol"), side=kwargs.get("side"),
            price=kwargs.get("price"), size=kwargs.get("size"),
            purpose=kwargs.get("purpose", "entry"),
            position_id=kwargs.get("position_id"),
            post_only=kwargs.get("post_only", True),
            leverage=kwargs.get("leverage", 1.0),
            meta=kwargs.get("meta") or {},
            created_ts=kwargs.get("now") or 0.0,
            ttl_sec=kwargs.get("ttl_sec"),
        )
        self._open.append(order)
        return order

    def open_orders(self):
        return list(self._open)

    def has_open(self, asset, purpose=None, book=None):
        return any(o.asset == asset
                   and (purpose is None or o.purpose == purpose)
                   and (book is None or o.meta.get("book", "5m") == book)
                   for o in self._open)

    def cancel_order(self, order, reason=""):
        self.cancelled.append((order.order_id, reason))
        if order in self._open:
            self._open.remove(order)
        order.status = "cancelled"
        return True


class _FakeKraken:
    def kraken_pair(self, symbol):
        return symbol.replace("/", "")


class _Hist:
    """Mirrors test_conviction_integration.py's own stub - regime_live_
    count feeds conviction's term-3 evidence-coverage floor."""
    def __init__(self, live=1000):
        self._live = live

    def regime_live_count(self, regime_label):
        return self._live


def _stub_bot(*, equity: float = 10_000.0, dry_run: bool = True,
              halted: bool = False, entries_enabled: bool = True,
              live_armed: bool = True, context_state=None,
              regime_live: int = 1000, regime_floor: int = 0,
              conviction_mode: str = "report", conviction_enabled: bool = True,
              accept_orders: bool = True, lb_cfg: dict = None,
              prices: dict = None, open_positions=()) -> LiquidityBot:
    bot = LiquidityBot.__new__(LiquidityBot)
    lbp = lb_cfg if lb_cfg is not None else LB_CFG
    bot.config = {"long_book": lbp}
    bot.state = PortfolioState(starting_capital=equity)
    for p in open_positions:
        bot.state.add_position(p)
    bot.symbol_map = {"BTC": "BTC/USD", "ETH": "ETH/USD"}
    bot.marks = dict(prices or {"BTC/USD": 60_000.0, "ETH/USD": 2_000.0})
    bot.kraken_books = {}
    bot.macro = MacroRegimeEngine({})
    bot.vol = VolRegimeEngine({})
    bot.liq = LiquidityRegimeEngine({})
    bot.inventory = InventoryManager({})
    bot.risk_protocols = RiskProtocolStack({})
    bot.long_sizer = PositionSizer({}, lbp.get("profit_taking", {}), {},
                                   protocols=bot.risk_protocols)
    bot.long_tier_engine = ProfitTierEngine(lbp.get("profit_taking", {}))
    bot.long_ladder = EvidenceLadder(lbp.get("ladder", {}))
    # 5m sibling engines, needed by _manage_open_position's untouched
    # else-branch (main._tier_engine reads self.tiers_base/_tier_engines)
    bot.tiers_base = _5M_PROFIT_TAKING
    bot._tier_engines = {}
    bot.orders = _FakeOrders(accept=accept_orders)
    bot.kraken = _FakeKraken()
    bot.pretrade = PreTradeGate({})   # Important #2: maker/taker_fee_bps
    bot.conviction = ConvictionFormula(
        {"enabled": conviction_enabled, "mode": conviction_mode})
    bot.history = _Hist(regime_live)
    bot._regime_floor_live = regime_floor
    bot.dry_run = dry_run
    bot.entries_enabled = entries_enabled
    bot.live_armed = live_armed
    bot._halted = halted
    bot._live_block_logged = 0.0
    bot._context_state = context_state if context_state is not None \
        else _aligned_ctx()
    bot._long_last_add_ts = {}
    bot._long_adds_placed = 0
    bot._long_context_aligned_last = None
    bot._long_last_deny = ""
    bot._long_retry_backoff_until = {}
    # task C5 items 3(a)/3(b)/6: equity-curve peak/drawdown, adverse-
    # episode tracker, deny-debounce state - mirrors main.__init__'s own
    # defaults exactly (this stub predates __init__, so every attribute
    # _long_book_cycle/_long_book_dd_frac/_long_book_ladder_maintenance/
    # _finalize_position touch must be hand-set here).
    bot._long_book_realized_pnl_total = 0.0
    bot._long_book_peak_value = 0.0
    bot._long_book_dd_breach_active = False
    bot._long_book_adverse_episode_start = None
    bot._long_book_adverse_held_exposure = True
    bot._long_book_adverse_dd_ok = True
    bot._long_book_deny_state = {}
    # Important #5: anti-scalp manip gate, mirroring the 5m book's own
    # __init__ defaults (risk.manip_gate config block) - empty scores +
    # enabled=True is a no-op (score 0.0 < downsize_at) unless a test
    # explicitly sets bot._manip_scores[asset].
    bot._manip_scores = {}
    bot._manip_gate_enabled = True
    bot._manip_downsize_at = 0.6
    bot._manip_veto_at = 0.9
    bot._manip_min_scale = 0.25
    bot._stop_ok = {}
    bot._stop_hit = {}
    bot.last_signals = {}
    bot._mark_stale_sec = 20.0
    now0 = 1_700_000_000.0
    bot._mark_ts = {sym: now0 for sym in bot.symbol_map.values()}
    return bot


class _FakeAudit:
    def __init__(self):
        self.entries: list = []

    def log(self, src, code, msg, data=None):
        self.entries.append((src, code, msg, data or {}))
        return len(self.entries)

    def codes(self):
        return [e[1] for e in self.entries]


@pytest.fixture
def fake_audit(monkeypatch):
    fa = _FakeAudit()
    monkeypatch.setattr("main.get_audit", lambda: fa)
    return fa


# ---------------------------------------------------------------------------
# 1. happy path (STUB): places a post_only buy, book="long" meta
# ---------------------------------------------------------------------------

def test_happy_path_places_post_only_buy_with_book_long_meta(fake_audit):
    bot = _stub_bot()
    bot._long_book_cycle(1_700_000_000.0)

    calls = bot.orders.calls
    assert calls, "no order submitted on an aligned, unconstrained cycle"
    btc_calls = [c for c in calls if c["asset"] == "BTC"]
    assert len(btc_calls) == 1
    call = btc_calls[0]
    assert call["side"] == "buy"
    assert call["purpose"] == "entry"
    assert call["post_only"] is True
    assert call["meta"]["book"] == "long"
    # Important #2: a real measured round-trip estimate, no longer the
    # hardcoded 0.0 that made the tier-1 cost floor provably inert.
    assert call["meta"]["est_cost_bps"] > 0.0
    # Critical #1a: the long TTL (config default 6h), not the shared
    # ~25s order_timeout_sec.
    assert call["ttl_sec"] == pytest.approx(6.0 * 3600.0)
    assert bot._long_adds_placed >= 1
    # Critical #1(c): the spacing clock keys on FILL, not submit - a bare
    # submit (no fill simulated here) must NOT stamp _long_last_add_ts.
    assert "BTC" not in bot._long_last_add_ts
    assert Code.LB_ADD_PLACED in fake_audit.codes()


def test_happy_path_averages_into_existing_long_book_position(fake_audit):
    existing = Position(
        position_id="existing-btc", symbol="BTC/USD", direction="long",
        entry_price=59_000.0, size=0.01, original_size=0.01,
        opened_at=__import__("datetime").datetime.fromtimestamp(
            1_699_000_000.0, tz=__import__("datetime").timezone.utc),
        book="long")
    bot = _stub_bot(open_positions=[existing])
    bot._long_book_cycle(1_700_000_000.0)

    btc_calls = [c for c in bot.orders.calls if c["asset"] == "BTC"]
    assert len(btc_calls) == 1
    # averaging add: SAME position_id as the existing long-book position,
    # never a second same-book position on the asset (Global Constraint)
    assert btc_calls[0]["position_id"] == "existing-btc"


def test_disabled_config_is_inert():
    bot = _stub_bot(lb_cfg=dict(LB_CFG, enabled=False))
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    assert bot._long_adds_placed == 0


def test_sizer_reject_leaves_no_order(fake_audit):
    # accept_orders is irrelevant here - the SIZER itself vetoes: p_win is
    # fixed at 1.0 (always clears p_bar) by design, so the only reachable
    # sizer veto is the SHARED InventoryManager.can_add's same-side
    # crowding cap (default max_same_side_positions_per_asset=2) - two
    # pre-existing non-hedge long positions on BOTH assets (their book tag
    # doesn't matter to InventoryManager, only direction+asset) exhausts
    # it for a NEW long-book add on either.
    import datetime
    opened = datetime.datetime.fromtimestamp(1_699_000_000.0,
                                             tz=datetime.timezone.utc)
    crowd = []
    for asset, sym in (("BTC", "BTC/USD"), ("ETH", "ETH/USD")):
        for i in range(2):
            crowd.append(Position(
                position_id=f"{asset}-crowd-{i}", symbol=sym,
                direction="long", entry_price=100.0, size=0.001,
                original_size=0.001, opened_at=opened, book="5m"))
    bot = _stub_bot(open_positions=crowd)
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    assert bot._long_adds_placed == 0
    assert any("sizer" in e[2].lower() or "SZ-" in e[2]
              for e in fake_audit.entries)


# ---------------------------------------------------------------------------
# 2. every deny path (STUB): coded, no order placed
# ---------------------------------------------------------------------------

def test_deny_halted_blocks_adds(fake_audit):
    bot = _stub_bot(halted=True)
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    assert "halted" in bot._long_last_deny


def test_deny_entries_disabled_blocks_adds(fake_audit):
    bot = _stub_bot(entries_enabled=False)
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []


def test_deny_live_not_armed_blocks_adds(fake_audit):
    bot = _stub_bot(dry_run=False, live_armed=False)
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []


def test_deny_spacing_blocks_rapid_readds(fake_audit):
    bot = _stub_bot()
    bot._long_last_add_ts["BTC"] = 1_700_000_000.0
    bot._long_last_add_ts["ETH"] = 1_700_000_000.0
    bot._long_book_cycle(1_700_000_030.0)   # 30s later, spacing = 1h
    assert bot.orders.calls == []


def test_deny_event_window_blocks_adds_and_logs_lb050(fake_audit):
    bot = _stub_bot(context_state=_event_window_ctx())
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    assert Code.LB_PAUSED in fake_audit.codes()


def test_deny_context_unknown_emits_cx030_and_no_order(fake_audit):
    bot = _stub_bot(context_state=_unknown_ctx())
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    codes = fake_audit.codes()
    assert Code.CX_CONTEXT_UNKNOWN in codes
    assert Code.LB_PAUSED in codes
    assert bot._long_context_aligned_last is None


def test_deny_context_misaligned_blocks_adds(fake_audit):
    bot = _stub_bot(context_state=_misaligned_ctx())
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    assert bot._long_context_aligned_last is False


def test_deny_ceiling_exhausted_blocks_adds(fake_audit):
    # rung 0 paper ceiling = r1.ceiling_frac(0.1) * equity - park an
    # existing long-book position AT the ceiling so headroom is zero.
    equity = 10_000.0
    ceiling_usd = 0.1 * equity
    existing = Position(
        position_id="parked", symbol="BTC/USD", direction="long",
        entry_price=60_000.0, size=ceiling_usd / 60_000.0,
        original_size=ceiling_usd / 60_000.0,
        opened_at=__import__("datetime").datetime.fromtimestamp(
            1_699_000_000.0, tz=__import__("datetime").timezone.utc),
        book="long")
    bot = _stub_bot(equity=equity, open_positions=[existing])
    bot._long_book_cycle(1_700_000_000.0)
    btc_calls = [c for c in bot.orders.calls if c["asset"] == "BTC"]
    assert btc_calls == []
    assert "ceiling" in bot._long_last_deny or "no headroom" in bot._long_last_deny


def test_deny_conviction_enforce_denies_via_lb010(fake_audit):
    # regime_floor > 0 with regime_live=0 starves term 3 (CV-030) in
    # enforce mode - conviction denies, LB-010 names the conviction code.
    bot = _stub_bot(conviction_mode="enforce", regime_live=0, regime_floor=60)
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    assert any("conviction" in e[2] for e in fake_audit.entries)


def test_conviction_report_mode_never_blocks(fake_audit):
    # report mode (the shipped default): conviction is evaluated and
    # logged but NEVER blocks - byte-identical to the enforce-denied
    # scenario above except for the actual order placement.
    bot = _stub_bot(conviction_mode="report", regime_live=0, regime_floor=60)
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls, "report mode must never block an otherwise-clean add"


# ---------------------------------------------------------------------------
# 3. halted blocks ADDS but never exits (thesis stop still fires)
# ---------------------------------------------------------------------------

def test_halted_blocks_adds_but_thesis_stop_still_fires(fake_audit, monkeypatch):
    bot = _stub_bot(halted=True)
    entry = 60_000.0
    stop = thesis_stop_price(entry, LB_CFG["thesis_stop_pct"])
    pos = Position(
        position_id="p1", symbol="BTC/USD", direction="long",
        entry_price=entry, size=0.01, original_size=0.01,
        opened_at=__import__("datetime").datetime.fromtimestamp(
            1_699_000_000.0, tz=__import__("datetime").timezone.utc),
        book="long", stop_price=stop)
    bot.state.add_position(pos)
    bot.marks["BTC/USD"] = stop - 1.0   # price BELOW the thesis stop

    exits = []
    monkeypatch.setattr(
        bot, "_submit_exit",
        lambda p, pct, reason, **kw: exits.append((p, pct, reason, kw)))

    # 1) adds are blocked while halted
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []

    # 2) but the exit path (invariant #5: exits always allowed) still
    # fires the thesis stop regardless of _halted - _manage_open_position
    # never even reads bot._halted for the protective-stop branch.
    bot._manage_open_position(pos, 1_700_000_000.0, bot.state.total_equity(),
                              {"BTC": bot.macro.state("BTC")})
    assert len(exits) == 1
    _, pct, _reason, kw = exits[0]
    assert pct == 100.0
    assert kw.get("reason_code") == Code.LB_THESIS_INVALIDATED.value


# ---------------------------------------------------------------------------
# 4. long position routed to the long tier engine; 5m position untouched
#    (behavior pin: distinguishable close_pct per engine's own config)
# ---------------------------------------------------------------------------

def _big_winner(book: str, entry: float = 2_000.0) -> Position:
    import datetime
    return Position(
        position_id=f"pin-{book}", symbol="ETH/USD", direction="long",
        entry_price=entry, size=1.0, original_size=1.0,
        opened_at=datetime.datetime.fromtimestamp(
            1_699_000_000.0, tz=datetime.timezone.utc),
        book=book, confidence=0.0)


def test_long_position_routed_to_long_tier_engine(monkeypatch):
    bot = _stub_bot()
    pos = _big_winner("long")
    bot.marks["ETH/USD"] = pos.entry_price * 1.50   # +50%: clears every tier

    exits = []
    monkeypatch.setattr(
        bot, "_submit_exit",
        lambda p, pct, reason, **kw: exits.append((pct, kw)))
    bot._manage_open_position(pos, 1_700_000_000.0, bot.state.total_equity(),
                              {"ETH": bot.macro.state("ETH")})
    assert len(exits) == 1
    pct, kw = exits[0]
    # LB_CFG's own tier_1.close_pct_of_position (20), NOT the 5m book's
    # (25) - proves the LONG tier engine instance fired, not _tier_engine
    assert pct == pytest.approx(20.0)
    assert kw.get("reason_code") == Code.LB_TIER_BANK.value


def test_5m_position_untouched_by_long_book_routing(monkeypatch):
    bot = _stub_bot()
    pos = _big_winner("5m")
    bot.marks["ETH/USD"] = pos.entry_price * 1.50

    exits = []
    monkeypatch.setattr(
        bot, "_submit_exit",
        lambda p, pct, reason, **kw: exits.append((pct, kw)))
    bot._manage_open_position(pos, 1_700_000_000.0, bot.state.total_equity(),
                              {"ETH": bot.macro.state("ETH")})
    assert len(exits) == 1
    pct, kw = exits[0]
    # _5M_PROFIT_TAKING's own tier_1.close_pct_of_position (25), NOT the
    # long book's (20) - the 5m branch's own computation is untouched.
    assert pct == pytest.approx(25.0)
    # 5m closes never carry an LB-* reason code
    assert kw.get("reason_code", "") == ""


def test_5m_position_default_book_is_5m_without_explicit_tag():
    # book defaults "5m" everywhere - zero 5m contamination by construction
    pos = Position(position_id="p", symbol="ETH/USD", direction="long",
                   entry_price=2000.0, size=1.0, original_size=1.0,
                   opened_at=__import__("datetime").datetime.now(
                       __import__("datetime").timezone.utc))
    assert pos.book == "5m"


# ---------------------------------------------------------------------------
# 5. conviction receives context_aligned ONLY on the long path
# ---------------------------------------------------------------------------

def test_long_book_conviction_call_passes_real_context_aligned(fake_audit):
    bot = _stub_bot(context_state=_aligned_ctx())
    calls = []
    real = bot._conviction_disposition

    def _spy(asset, signal, decision, regime_label, explored,
             context_aligned=None, feed_governor=True):
        calls.append(context_aligned)
        return real(asset, signal, decision, regime_label, explored,
                    context_aligned=context_aligned,
                    feed_governor=feed_governor)
    bot._conviction_disposition = _spy

    bot._long_book_cycle(1_700_000_000.0)
    assert calls, "the long-book path must call _conviction_disposition"
    assert all(c is not None for c in calls), \
        "the long-book admission must always pass a real bool, never None"


def test_conviction_default_stays_none_for_5m_style_calls():
    # every pre-existing 5m call site omits context_aligned - the
    # keyword's default must still be None (byte-identical pre-C4
    # behavior), independent of anything the long book does.
    bot = _stub_bot()
    signal = types.SimpleNamespace(gates_passed={"g1": True, "g2": True})
    decision = types.SimpleNamespace(est_edge_bps=100.0, est_cost_bps=10.0)
    deny = bot._conviction_disposition(
        "ETH", signal, decision, "range", False)
    assert deny is None   # report mode: never blocks


# ---------------------------------------------------------------------------
# 5b. C4 review Important #4: honest null terms, not fabricated 1.0/1.0/0.0
# ---------------------------------------------------------------------------

def test_long_book_conviction_audit_terms_are_null_not_fabricated(fake_audit):
    bot = _stub_bot(context_state=_aligned_ctx())
    bot._long_book_cycle(1_700_000_000.0)

    conv_entries = [e for e in fake_audit.entries if e[0] == "conviction"]
    assert conv_entries, "the long-book path must feed the conviction audit"
    terms = conv_entries[0][3]
    assert terms["agreement"] is None
    assert terms["est_edge_bps"] is None
    assert terms["est_cost_bps"] is None
    # term 3/4 are STILL live real values - only 1-2 are not-applicable
    assert terms["regime_known"] is True
    assert terms["context_aligned"] is True


# ---------------------------------------------------------------------------
# 5c. C4 review Important #3(b): long-book conviction evaluations must NOT
# feed the shared cadence governor (its windows were derived for the 5m
# book's per-signal selectivity, not this book's ~24h-scale cadence)
# ---------------------------------------------------------------------------

def test_long_book_conviction_does_not_feed_the_shared_governor():
    bot = _stub_bot(context_state=_aligned_ctx())
    bot._long_book_cycle(1_700_000_000.0)
    st = bot.conviction.status()
    assert st["evaluated"] == 0
    assert st["n"] == 0
    assert bot.conviction.cadence_alarms() == []


def test_5m_conviction_call_still_feeds_the_governor():
    # regression: the long-book fix must not accidentally disable the
    # governor feed for the 5m book's own (unrelated) call site.
    bot = _stub_bot()
    signal = types.SimpleNamespace(gates_passed={"g1": True, "g2": True})
    decision = types.SimpleNamespace(est_edge_bps=100.0, est_cost_bps=10.0)
    bot._conviction_disposition("ETH", signal, decision, "range", False)
    assert bot.conviction.status()["evaluated"] == 1


# ---------------------------------------------------------------------------
# 6. ladder ceiling bounds sizing
# ---------------------------------------------------------------------------

def test_ladder_ceiling_hard_caps_the_sizer_output():
    bot = _stub_bot(equity=1_000_000.0)   # huge equity: kelly wants much more
    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    bot._place_long_book_add("ETH", "ETH/USD", None, plan, 1_000_000.0,
                             1_700_000_000.0)
    assert len(bot.orders.calls) == 1
    call = bot.orders.calls[0]
    assert call["size"] * call["price"] <= plan.usd + 1e-6
    assert call["size"] == pytest.approx(plan.usd / plan.price, rel=1e-6)


def test_ladder_ceiling_binds_tighter_than_a_generous_sizer_at_normal_equity():
    bot = _stub_bot(equity=10_000.0)
    bot._long_book_cycle(1_700_000_000.0)
    btc_calls = [c for c in bot.orders.calls if c["asset"] == "BTC"]
    assert btc_calls
    usd = btc_calls[0]["size"] * btc_calls[0]["price"]
    ceiling_usd = bot.long_ladder.paper_ceiling_frac() * 10_000.0
    assert usd <= LB_CFG["add_usd_frac_of_ceiling"] * ceiling_usd + 1e-6


# ---------------------------------------------------------------------------
# 6b. C4 review Important #5: THALES manip gate on long adds (SZ-045 parity
# with the 5m entry loop's own veto/downsize, main.py ~2841)
# ---------------------------------------------------------------------------

def test_manip_score_above_veto_refuses_the_add_with_sz045_code(fake_audit):
    bot = _stub_bot()
    bot._manip_scores["ETH"] = 0.95   # >= veto_at (0.9)
    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    bot._place_long_book_add("ETH", "ETH/USD", None, plan, 10_000.0,
                             1_700_000_000.0)
    assert bot.orders.calls == []
    assert any(Code.SZ_MANIP_SUSPECT.value in e[2] for e in fake_audit.entries)
    # Important #3(a): a manip veto is a post-plan failure - it backs off
    # like any other sizing/submission refusal.
    assert bot._long_retry_backoff_until.get("ETH", 0.0) > 1_700_000_000.0


def test_manip_score_between_downsize_and_veto_scales_the_sizer_risk_scale():
    from main import manip_entry_scale
    bot = _stub_bot()
    bot._manip_scores["ETH"] = 0.75   # between downsize_at(0.6)/veto_at(0.9)
    captured = {}
    real_size = bot.long_sizer.size

    def _spy(*args, **kwargs):
        captured["risk_scale"] = kwargs.get("risk_scale")
        return real_size(*args, **kwargs)
    bot.long_sizer.size = _spy

    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    bot._place_long_book_add("ETH", "ETH/USD", None, plan, 10_000.0,
                             1_700_000_000.0)
    expected = manip_entry_scale(0.75, bot._manip_downsize_at,
                                 bot._manip_veto_at, bot._manip_min_scale)
    assert captured["risk_scale"] == pytest.approx(expected)
    assert captured["risk_scale"] < 1.0


def test_manip_score_below_downsize_leaves_risk_scale_untouched():
    bot = _stub_bot()
    bot._manip_scores["ETH"] = 0.1   # well below downsize_at (0.6)
    captured = {}
    real_size = bot.long_sizer.size

    def _spy(*args, **kwargs):
        captured["risk_scale"] = kwargs.get("risk_scale")
        return real_size(*args, **kwargs)
    bot.long_sizer.size = _spy

    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    bot._place_long_book_add("ETH", "ETH/USD", None, plan, 10_000.0,
                             1_700_000_000.0)
    assert captured["risk_scale"] == 1.0


def test_manip_gate_disabled_ignores_manip_score():
    bot = _stub_bot()
    bot._manip_gate_enabled = False
    bot._manip_scores["ETH"] = 0.99   # would veto if the gate were enabled
    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    bot._place_long_book_add("ETH", "ETH/USD", None, plan, 10_000.0,
                             1_700_000_000.0)
    assert len(bot.orders.calls) == 1


# ---------------------------------------------------------------------------
# 6c. C4 review Important #2: measured maker-entry/taker-exit round-trip
# est_cost_bps, replacing the prior hardcoded 0.0
# ---------------------------------------------------------------------------

def test_est_cost_bps_is_measured_not_hardcoded_zero():
    bot = _stub_bot()
    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    bot._place_long_book_add("ETH", "ETH/USD", None, plan, 10_000.0,
                             1_700_000_000.0)
    assert len(bot.orders.calls) == 1
    est_cost_bps = bot.orders.calls[0]["meta"]["est_cost_bps"]
    liq_state = bot.liq.state("ETH")
    expected = (bot.pretrade.maker_fee_bps + bot.pretrade.taker_fee_bps
               + 0.5 * liq_state.spread_bps)
    assert est_cost_bps == pytest.approx(expected)
    assert est_cost_bps > 0.0


def test_long_position_tier1_cost_floor_binds_with_measured_est_cost_bps():
    # Important #2's whole point: a non-zero est_cost_bps makes
    # profit_tiers.tier1_cost_floor_pct's min_trigger_cost_mult floor
    # ACTUALLY bind for a long-book position (it was provably inert at
    # est_cost_bps=0.0 - min_trigger_cost_mult * 0.0 == 0.0, never > 0).
    from risk.profit_tiers import tier1_cost_floor_pct
    bot = _stub_bot()
    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    bot._place_long_book_add("ETH", "ETH/USD", None, plan, 10_000.0,
                             1_700_000_000.0)
    est_cost_bps = bot.orders.calls[0]["meta"]["est_cost_bps"]
    min_trigger_cost_mult = LB_CFG["profit_taking"]["min_trigger_cost_mult"]
    floor_pct = tier1_cost_floor_pct(min_trigger_cost_mult, est_cost_bps)
    assert floor_pct > 0.0, \
        "a measured est_cost_bps must make the tier-1 cost floor bind"


# ---------------------------------------------------------------------------
# 6d. C4 review Critical #1(b): cancel-and-replace a stale resting bid
# ---------------------------------------------------------------------------

def test_fresh_resting_bid_is_left_alone_not_double_submitted(fake_audit):
    # a SINGLE long-book asset: add_usd_frac_of_ceiling=0.5 means one add
    # only ever consumes HALF the ceiling, leaving ample headroom on the
    # next pass regardless of equity - so the ONLY thing that could
    # prevent a duplicate submit is the resting-order dedup check itself,
    # NOT ceiling exhaustion (Minor #8's book_exposure_usd fix would
    # otherwise confound this test: with the default TWO-asset LB_CFG,
    # both assets' own $0.5-ceiling-frac adds exactly exhaust the shared
    # ceiling between them regardless of equity level, since ceiling and
    # add-size both scale proportionally with equity).
    bot = _stub_bot(lb_cfg=dict(LB_CFG, assets=["BTC"]))
    bot._long_book_cycle(1_700_000_000.0)
    btc_calls_1 = [c for c in bot.orders.calls if c["asset"] == "BTC"]
    assert len(btc_calls_1) == 1

    # a SECOND pass shortly after, mark unchanged: the resting bid is
    # still fresh - must NOT submit a second BTC order (the resting bid
    # IS the dedup lock).
    bot._long_book_cycle(1_700_000_030.0)
    btc_calls_2 = [c for c in bot.orders.calls if c["asset"] == "BTC"]
    assert len(btc_calls_2) == 1, \
        "a fresh resting bid must not be double-submitted"
    assert bot.orders.cancelled == []


def test_stale_resting_bid_is_cancelled_and_replaced_same_pass(fake_audit):
    bot = _stub_bot()
    bot._long_book_cycle(1_700_000_000.0)
    btc_calls_1 = [c for c in bot.orders.calls if c["asset"] == "BTC"]
    assert len(btc_calls_1) == 1
    old_price = btc_calls_1[0]["price"]

    # mark runs up 5% - drift now far exceeds the fresh band
    # (add_offset_pct 0.5% + zone_buffer_pct 0.2% = 0.7%).
    bot.marks["BTC/USD"] = bot.marks["BTC/USD"] * 1.05

    bot._long_book_cycle(1_700_000_030.0)   # well inside the 1h spacing
    btc_calls_2 = [c for c in bot.orders.calls if c["asset"] == "BTC"]
    assert len(btc_calls_2) == 2, \
        "the stale bid must be cancelled and a fresh one submitted"
    assert bot.orders.cancelled, "the stale resting order must be cancelled"
    new_price = btc_calls_2[-1]["price"]
    assert new_price != pytest.approx(old_price)
    # exactly ONE resting BTC order survives the replace - never two
    resting_btc = [o for o in bot.orders.open_orders() if o.asset == "BTC"]
    assert len(resting_btc) == 1
    assert resting_btc[0].price == pytest.approx(new_price)

    # F8 (market-conduct pass): the reprice cancel is coded LB-021
    # (Code.LB_BID_REPRICED), not the prior LB_ADD_DENIED kind="reprice"
    # overload - and the OM cancel reason IS the tagged string.
    cancel_reason = bot.orders.cancelled[0][1]
    assert Code.LB_BID_REPRICED.value in cancel_reason
    reprice_entries = [e for e in fake_audit.entries
                      if e[1] == Code.LB_BID_REPRICED]
    assert len(reprice_entries) == 1
    assert reprice_entries[0][3]["kind"] == "reprice"
    assert reprice_entries[0][3]["old_price"] == pytest.approx(old_price)


# ---------------------------------------------------------------------------
# 6e. C4 review Minor #8: resting long-book orders count into
# book_exposure_usd headroom - a same-cycle cross-asset double-commit test
# ---------------------------------------------------------------------------

def test_same_cycle_cross_asset_double_commit_is_prevented(fake_audit):
    # add_usd_frac_of_ceiling=1.0: each add wants the WHOLE ceiling
    # (headroom-limited) - if BTC's freshly-RESTING (unfilled) order
    # were NOT counted against book_exposure_usd, ETH (evaluated second
    # in the SAME pass) would ALSO see full headroom and get sized up to
    # the ceiling too, committing 2x the shared cap in one pass.
    cfg = dict(LB_CFG, add_usd_frac_of_ceiling=1.0)
    bot = _stub_bot(equity=10_000.0, lb_cfg=cfg)
    bot._long_book_cycle(1_700_000_000.0)

    btc_calls = [c for c in bot.orders.calls if c["asset"] == "BTC"]
    eth_calls = [c for c in bot.orders.calls if c["asset"] == "ETH"]
    assert btc_calls, "BTC (evaluated first) should get an add"
    ceiling_usd = bot.long_ladder.paper_ceiling_frac() * 10_000.0
    total_usd = sum(c["size"] * c["price"] for c in btc_calls + eth_calls)
    assert total_usd <= ceiling_usd + 1e-6, \
        "combined same-pass commitment across BOTH assets must stay " \
        "within the ONE shared book-wide ceiling"


# ---------------------------------------------------------------------------
# 6f. C4 review Important #3(a): per-asset retry backoff after a post-plan
# sizing/submission failure - stops the every-~30s re-attempt/re-audit flood
# ---------------------------------------------------------------------------

def _crowded_bot(**kw):
    # same crowding setup as test_sizer_reject_leaves_no_order: 2 pre-
    # existing non-hedge long positions per asset exhausts InventoryManager's
    # default same-side-per-asset cap (2), so the sizer reliably vetoes -
    # a real, reachable post-plan failure (not a fabricated stub veto).
    import datetime
    opened = datetime.datetime.fromtimestamp(1_699_000_000.0,
                                             tz=datetime.timezone.utc)
    crowd = []
    for asset, sym in (("BTC", "BTC/USD"), ("ETH", "ETH/USD")):
        for i in range(2):
            crowd.append(Position(
                position_id=f"{asset}-crowd-{i}", symbol=sym,
                direction="long", entry_price=100.0, size=0.001,
                original_size=0.001, opened_at=opened, book="5m"))
    return _stub_bot(open_positions=crowd, **kw)


def test_sizer_veto_backs_off_the_asset_for_retry_backoff_minutes(fake_audit):
    bot = _crowded_bot()
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    assert bot._long_retry_backoff_until.get("BTC", 0.0) \
        == pytest.approx(1_700_000_000.0 + 30 * 60.0)
    assert bot._long_retry_backoff_until.get("ETH", 0.0) \
        == pytest.approx(1_700_000_000.0 + 30 * 60.0)


def test_backed_off_asset_does_not_re_attempt_within_the_window(fake_audit):
    bot = _crowded_bot()
    bot._long_book_cycle(1_700_000_000.0)
    n_after_first = len(fake_audit.entries)

    # a cycle 5s later (well within the 30-minute backoff): no re-run of
    # decide_add/sizer at all - no new audit rows from this asset.
    bot._long_book_cycle(1_700_000_005.0)
    assert bot.orders.calls == []
    assert len(fake_audit.entries) == n_after_first, \
        "a backed-off asset must not re-run decide_add (and re-audit the " \
        "identical sizer veto) inside the backoff window"


def test_backoff_clears_after_retry_backoff_minutes_elapses(fake_audit):
    bot = _crowded_bot()
    bot._long_book_cycle(1_700_000_000.0)
    n_after_first = len(fake_audit.entries)

    later = 1_700_000_000.0 + 30 * 60.0 + 1.0
    bot._long_book_cycle(later)
    assert len(fake_audit.entries) > n_after_first, \
        "past the backoff window, the asset must be re-evaluated again"


def _full_cfg(tmp_path) -> dict:
    cfg = load_config(str(_ROOT / "config.json"))
    cfg["capital_management"]["starting_capital_usd"] = 10_000
    cfg["system"]["dry_run"] = True
    cfg["system"]["state_path"] = str(tmp_path / "state.json")
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["context"]["enabled"] = False
    return cfg


def _full_bot(cfg, prices, **kw) -> LiquidityBot:
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), **kw)
    if hasattr(bot, "context"):
        bot.context.fetch = lambda *a, **k: None
    return bot


def test_persistence_round_trips_ladder_and_last_add_ts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _full_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)

    bot.long_ladder.note_close(50.0, is_live=False)
    bot.long_ladder.note_close(-10.0, is_live=True)
    bot.long_ladder.note_close(30.0, is_live=True)
    bot._long_last_add_ts["BTC"] = 1_700_000_000.0
    bot._long_last_add_ts["ETH"] = 1_700_000_500.0

    assert bot.store.snapshot(bot)

    bot2 = _full_bot(cfg, dict(prices), resume=True)
    assert bot2.long_ladder.closed_paper == 1
    assert bot2.long_ladder.closed_live == 2
    assert bot2.long_ladder.pf_live == pytest.approx(bot.long_ladder.pf_live)
    assert bot2._long_last_add_ts == {"BTC": 1_700_000_000.0,
                                      "ETH": 1_700_000_500.0}


def test_persistence_round_trips_book_tag_on_open_positions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _full_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)

    import datetime
    pos = Position(
        position_id="long-pos", symbol="BTC/USD", direction="long",
        entry_price=60_000.0, size=0.01, original_size=0.01,
        opened_at=datetime.datetime.now(datetime.timezone.utc), book="long")
    bot.state.add_position(pos)
    assert bot.store.snapshot(bot)

    bot2 = _full_bot(cfg, dict(prices), resume=True)
    restored = bot2.state.get_position("long-pos")
    assert restored is not None
    assert restored.book == "long"


def test_persistence_round_trips_history_pending_book_tag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _full_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)

    import numpy as np
    feats = np.zeros(len(__import__("ml.features", fromlist=["FEATURE_NAMES"])
                        .FEATURE_NAMES))
    bot.history.log_entry("pend-1", "BTC", "long", feats, book="long")
    assert bot.store.snapshot(bot)

    bot2 = _full_bot(cfg, dict(prices), resume=True)
    entry = bot2.history._pending.get("pend-1")
    assert entry is not None
    assert entry[6] == "long"


def test_persistence_history_pending_defaults_5m_for_legacy_snapshot(
        tmp_path, monkeypatch):
    # C1's carried gap, pre-fix shape: a snapshot written before this task
    # has no "book" key in a history_pending entry at all.
    monkeypatch.chdir(tmp_path)
    cfg = _full_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)
    assert bot.store.snapshot(bot)

    raw = bot.store.load_raw()
    raw["history_pending"] = {"legacy-1": {
        "asset": "ETH", "direction": "long", "features": [0.0, 0.0],
        "signal_ts": 1_700_000_000.0, "probe": False,
        "candidate_id": None}}   # no "book" key at all
    assert bot.store.write_raw(raw)

    bot2 = _full_bot(cfg, dict(prices), resume=True)
    entry = bot2.history._pending.get("legacy-1")
    assert entry is not None
    assert entry[6] == "5m"


# ---------------------------------------------------------------------------
# 8. status shape JSON-safe
# ---------------------------------------------------------------------------

def test_status_shape_json_safe_and_complete():
    bot = _stub_bot()
    bot._long_adds_placed = 3
    bot._long_last_add_ts = {"BTC": 1_700_000_000.0}
    bot._long_last_deny = "ETH: some deny detail"
    bot._long_context_aligned_last = True
    status = BotRunner._long_book_status(bot, 1_700_003_600.0)

    expected = {"enabled", "rung", "ceiling_frac", "book_exposure_usd",
               "positions", "adds_placed", "last_add_age_h",
               "paused_reason", "closed_paper", "closed_live", "pf_live",
               "context_aligned_last"}
    assert expected <= set(status)
    dumped = json.dumps(status)
    assert isinstance(dumped, str)
    assert status["adds_placed"] == 3
    assert status["last_add_age_h"] == pytest.approx(1.0)
    assert status["context_aligned_last"] is True


def test_status_pf_live_infinite_serializes_as_none():
    bot = _stub_bot()
    bot.long_ladder.note_close(100.0, is_live=True)   # a win, zero losses
    assert math.isinf(bot.long_ladder.pf_live)
    status = BotRunner._long_book_status(bot, 1_700_000_000.0)
    assert status["pf_live"] is None
    assert json.dumps(status)


def test_status_missing_long_ladder_omits_section():
    bot = LiquidityBot.__new__(LiquidityBot)
    assert BotRunner._long_book_status(bot, 0.0) == {}


def test_status_no_adds_yet_reports_null_age():
    bot = _stub_bot()
    status = BotRunner._long_book_status(bot, 1_700_000_000.0)
    assert status["last_add_age_h"] is None
    assert status["positions"] == 0
    assert status["book_exposure_usd"] == 0.0


# ---------------------------------------------------------------------------
# 9. end-to-end happy path through the REAL execution stack (FULL bot):
#    proves the wiring survives OrderManager + RiskFirewall, not just a
#    fake orders recorder (task C4's own discovery: the shipped C2
#    add_offset_pct=1.5% used to price-collar-reject every single add -
#    config.json + core/config_guard.py now guard against a recurrence).
# ---------------------------------------------------------------------------

def test_end_to_end_slow_cycle_places_a_real_long_book_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _full_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)
    bot.context.maybe_poll = lambda now=None: _aligned_ctx()

    t = 1_700_000_000.0
    # self.marks only populates from fast_cycle's ticker poll - a bare
    # slow_cycle call with no preceding fast_cycle is not how the real
    # engine ever runs (slow_cycle fires every Nth fast_cycle); one
    # fast_cycle first mirrors real cadence and gives _long_book_cycle a
    # real mark to price its bid off.
    bot.fast_cycle(t)
    bot.slow_cycle(t)

    long_orders = [o for o in bot.orders.open_orders()
                  if o.meta.get("book") == "long"]
    assert long_orders, "a real slow_cycle must place a real long-book order"
    o = long_orders[0]
    assert o.post_only is True
    assert o.side == "buy"
    assert bot._long_adds_placed >= 1


# ---------------------------------------------------------------------------
# 10. Critical #1(d): a real-stack test (submit -> poll -> fill) through the
# REAL sim OrderManager - asserts a book="long" Position actually opens, the
# submitted order carries the long TTL, AND the spacing clock (Critical
# #1c): expiry (no fill) does NOT stamp _long_last_add_ts, a FILL does.
# ---------------------------------------------------------------------------

def _place_one_real_long_book_order(tmp_path, monkeypatch, asset="BTC"):
    monkeypatch.chdir(tmp_path)
    cfg = _full_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)
    bot.context.maybe_poll = lambda now=None: _aligned_ctx()

    t = 1_700_000_000.0
    bot.fast_cycle(t)
    bot.slow_cycle(t)

    orders = [o for o in bot.orders.open_orders()
             if o.meta.get("book") == "long" and o.asset == asset]
    assert orders, f"a real slow_cycle must place a real long-book order " \
        f"for {asset}"
    return bot, orders[0], t


def test_submit_poll_fill_opens_a_book_long_position_and_stamps_spacing(
        tmp_path, monkeypatch):
    bot, o, t = _place_one_real_long_book_order(tmp_path, monkeypatch)
    assert o.ttl_sec == pytest.approx(6.0 * 3600.0)   # Critical #1a

    # force a deterministic maker-cross fill: the ask touches AT/THROUGH
    # our resting bid (post_only fills AT its own price as maker,
    # execution/order_manager.py's _sim_maker_cross).
    fill_now = t + 10.0
    books = {"BTC": {"bids": [[o.price * 0.999, 5.0]],
                     "asks": [[o.price - 0.01, 5.0]]}}
    events = bot.orders.poll(books, {"BTC": 0.05, "ETH": 0.05}, now=fill_now)
    assert events, "the crossing book must produce at least one fill event"
    for ev in events:
        bot._handle_fill(ev, now=fill_now)

    positions = [p for p in bot.state.open_positions() if p.book == "long"]
    assert positions, "the fill must open a book='long' Position"
    assert positions[0].direction == "long"
    # Critical #1(c): the spacing clock stamps on FILL, at the FILL time
    # (not the earlier submit time t).
    assert bot._long_last_add_ts.get("BTC") == pytest.approx(fill_now)


def test_expiry_does_not_burn_the_spacing_window(tmp_path, monkeypatch):
    bot, o, t = _place_one_real_long_book_order(tmp_path, monkeypatch)
    assert "BTC" not in bot._long_last_add_ts   # not stamped at submit

    # poll well past the 6h TTL with a NON-crossing book - no fill, a
    # zero-fill expiry only.
    expire_now = t + 6.0 * 3600.0 + 10.0
    books = {"BTC": {"bids": [[o.price * 0.5, 5.0]],
                     "asks": [[o.price * 2.0, 5.0]]}}
    events = bot.orders.poll(books, {"BTC": 0.05, "ETH": 0.05}, now=expire_now)
    for ev in events:
        bot._handle_fill(ev, now=expire_now)

    assert o.status == "expired"
    assert "BTC" not in bot._long_last_add_ts, \
        "a zero-fill expiry must NEVER burn the spacing window"


# ---------------------------------------------------------------------------
# 11. C4 review Minor #10: the 5m entry loop's has_open("entry") skip must
# not trigger on a resting LONG-book bid (covered by #1(c)'s book-aware fix)
# ---------------------------------------------------------------------------

def test_5m_entry_loop_skip_is_not_triggered_by_a_resting_long_book_bid(
        tmp_path, monkeypatch):
    bot, o, t = _place_one_real_long_book_order(tmp_path, monkeypatch)
    asset = o.asset

    # the resting order IS a "long"-book entry for this asset...
    assert bot.orders.has_open(asset, "entry", book="long") is True
    # ...but is invisible to a book="5m" check - the exact filter the 5m
    # entry loop's own has_open(asset, "entry", book="5m") call now uses
    # (main.py's slow_cycle, Minor #10). The OLD book-BLIND call would
    # have reported busy, proving why this mattered: without the book=
    # filter, a resting long-book bid (now living for HOURS, not ~25s)
    # would have silently blocked the 5m book's own entries on this asset
    # for that entire window.
    assert bot.orders.has_open(asset, "entry", book="5m") is False
    assert bot.orders.has_open(asset, "entry") is True   # book-blind: busy

    # confirm the ACTUAL call site (the 5m entry loop inside slow_cycle)
    # passes book="5m", not a book-blind call.
    calls = []
    real_has_open = bot.orders.has_open

    def _spy(asset_, purpose=None, book=None):
        calls.append((asset_, purpose, book))
        return real_has_open(asset_, purpose, book=book)
    bot.orders.has_open = _spy

    bot.fast_cycle(t + 30.0)
    bot.slow_cycle(t + 30.0)
    assert any(c[0] == asset and c[2] == "5m" for c in calls), \
        "the 5m entry loop must call has_open(asset, 'entry', book='5m')"


# ---------------------------------------------------------------------------
# 11b. C5-discovered spec gap fix: long-book fills write book-tagged corpus
# rows with REAL features assembled at ADD time (main._place_long_book_add),
# mirroring the 5m entry loop's own build_features call site (main.py's 5m
# loop ~2814-2823: smc.compute then build_features). Spec §5 / acceptance
# §8.4: long-horizon labels must flow into the corpus under the book tag -
# the paper positions ARE the learning. Before this fix, _handle_fill's
# `if not pos.is_hedge and "features" in order.meta` guard never fired for
# a long-book fill because _place_long_book_add's meta never carried the
# key at all - long positions opened and closed leaving NO corpus trace.
# ---------------------------------------------------------------------------

def test_long_book_fill_stamps_features_and_writes_book_tagged_history_row(
        tmp_path, monkeypatch):
    """The RED pin (pre-fix): a real submit -> poll -> fill through the
    full stack must stamp meta["features"] on the resting order (mirrors
    the 5m entry loop's own real feature assembly, not a fabricated
    stand-in), and the resulting fill must log_entry a pending row that
    survives to a book="long", full-width, correctly-labeled CSV row on
    close - exactly the corpus trace a 5m fill already gets."""
    bot, o, t = _place_one_real_long_book_order(tmp_path, monkeypatch)
    assert "features" in o.meta, \
        "a real slow_cycle add must stamp a real feature vector - the " \
        "paper positions ARE the learning (spec §5/§8.4)"
    assert len(o.meta["features"]) == len(FEATURE_NAMES)
    assert np.all(np.isfinite(o.meta["features"]))

    fill_now = t + 10.0
    books = {"BTC": {"bids": [[o.price * 0.999, 5.0]],
                     "asks": [[o.price - 0.01, 5.0]]}}
    events = bot.orders.poll(books, {"BTC": 0.05, "ETH": 0.05}, now=fill_now)
    assert events, "the crossing book must produce at least one fill event"
    for ev in events:
        bot._handle_fill(ev, now=fill_now)

    positions = [p for p in bot.state.open_positions() if p.book == "long"]
    assert positions, "the fill must open a book='long' Position"
    pos = positions[0]
    assert pos.position_id in bot.history._pending, \
        "the fill must log_entry a pending row (main._handle_fill's " \
        "'features' in order.meta guard must now fire for a long fill)"
    (pend_asset, pend_dir, pend_feats, _pend_ts, pend_probe,
     _pend_cand, pend_book, _pend_gate,
     _pend_avail) = bot.history._pending[pos.position_id]
    assert pend_book == "long"
    assert pend_dir == "long"
    assert pend_asset == "BTC"
    assert len(pend_feats) == len(FEATURE_NAMES)

    bot.history.log_close(pos.position_id, 42.0)
    assert pos.position_id not in bot.history._pending
    with open(bot.history.path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["book"] == "long"
    assert rows[0]["asset"] == "BTC"
    assert rows[0]["side"] == "long"        # "side": FEATURE_NAMES also
    # contains "direction" - the header names this column "side" to avoid
    # a duplicate CSV header (ml/history.py's own __init__ comment).
    assert rows[0]["label"] == "1"          # net_pnl_usd=42.0 > 0


def test_long_book_add_without_market_view_still_places_no_features_no_crash(
        caplog):
    """Tolerance case: the STUB harness never sets `self.view` at all (the
    sharpest form of "no candles this cycle" - the feature-assembly
    helper's own defensive `getattr`/`.get` must degrade to skipping the
    stamp, never raise). Every other STUB-based test in this module
    already exercises this path implicitly (none of them set `self.view`
    either); this test pins it explicitly as the C5 fix's own contract:
    feature assembly must NEVER block the add itself."""
    bot = _stub_bot()
    assert not hasattr(bot, "view")
    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    with caplog.at_level(logging.DEBUG, logger="main"):
        bot._place_long_book_add("ETH", "ETH/USD", None, plan, 10_000.0,
                                 1_700_000_000.0)
    assert len(bot.orders.calls) == 1, \
        "feature assembly failure must never block the add itself"
    assert "features" not in bot.orders.calls[0]["meta"]


def test_long_book_add_tolerates_a_feature_assembly_exception(caplog):
    """A genuine exception mid-assembly (not just missing data) must be
    swallowed the same way - features absent, add still placed, no
    crash. Distinguishes the try/except's exception path from the plain
    "no candles" skip path above."""
    bot = _stub_bot()
    bot.view = {"ETH": {"candles": [{"close": 100.0, "volume": 10.0}] * 20,
                        "order_book": {}}}
    bot.symbol_map = {"BTC": "BTC/USD", "ETH": "ETH/USD"}
    bot.daily_candles = {}

    class _BoomSMC:
        def compute(self, *a, **k):
            raise RuntimeError("smc blew up mid-assembly")
    bot.smc = _BoomSMC()

    plan = AddPlan(price=2_000.0, usd=50.0, reason_detail="new add")
    with caplog.at_level(logging.DEBUG, logger="main"):
        bot._place_long_book_add("ETH", "ETH/USD", None, plan, 10_000.0,
                                 1_700_000_000.0)
    assert len(bot.orders.calls) == 1, \
        "an assembly exception must never block the add itself"
    assert "features" not in bot.orders.calls[0]["meta"]


def test_long_book_real_row_does_not_perturb_5m_training_data(
        tmp_path, monkeypatch):
    """C5's book=="long" load-filter (ml/history.py's load_training_data)
    is already proven against SYNTHETIC long-row vectors
    (tests/test_book_tag.py). This proves the same exclusion holds now
    that a long row carries a REAL, full-width feature vector assembled
    at add time by main._place_long_book_add, not a hand-built probe
    array - the exact row shape this fix newly produces."""
    bot, o, t = _place_one_real_long_book_order(tmp_path, monkeypatch)
    fill_now = t + 10.0
    books = {"BTC": {"bids": [[o.price * 0.999, 5.0]],
                     "asks": [[o.price - 0.01, 5.0]]}}
    events = bot.orders.poll(books, {"BTC": 0.05, "ETH": 0.05}, now=fill_now)
    for ev in events:
        bot._handle_fill(ev, now=fill_now)
    positions = [p for p in bot.state.open_positions() if p.book == "long"]
    pos = positions[0]
    bot.history.log_close(pos.position_id, 42.0)   # real book="long" row

    feats_5m = np.zeros(len(FEATURE_NAMES))
    bot.history.log_entry("5m-a", "ETH", "long", feats_5m)
    bot.history.log_close("5m-a", 10.0)

    X, y, w = bot.history.load_training_data()
    assert len(X) == 1, "the real long-book row must never enter 5m X/y"
    assert np.array_equal(X[0], feats_5m)


# ---------------------------------------------------------------------------
# 12. task C5: downgrade + adverse-transition ladder wiring, crisis cadence
#    pause, euphoria give-back phase wiring, deny-debounce
# ---------------------------------------------------------------------------

import datetime as _dt_mod   # noqa: E402


def _dt(ts: float):
    return _dt_mod.datetime.fromtimestamp(ts, tz=_dt_mod.timezone.utc)


def _stressed_ctx(stress=5.0):
    return ContextState(halving_phase="expansion", stress=stress,
                        stress_known=True, in_event_window=False,
                        calendar_known=True)


# ---- 12a. _long_book_dd_frac ----------------------------------------------

def test_dd_frac_zero_with_no_positions_and_no_realized_pnl():
    bot = _stub_bot()
    assert bot._long_book_dd_frac(10_000.0) == 0.0


def test_dd_frac_tracks_peak_and_current_drawdown():
    bot = _stub_bot()
    bot._long_book_realized_pnl_total = 500.0
    dd0 = bot._long_book_dd_frac(10_000.0)
    assert dd0 == 0.0
    assert bot._long_book_peak_value == 500.0

    pos = Position(position_id="p1", symbol="BTC/USD", direction="long",
                   entry_price=60_000.0, size=0.01, original_size=0.01,
                   opened_at=_dt(1_699_000_000.0), book="long")
    bot.state.add_position(pos)
    bot.marks["BTC/USD"] = 50_000.0   # unrealized -100 usd (0.01 * -10_000)
    dd1 = bot._long_book_dd_frac(10_000.0)
    # book_value = 500 (realized) - 100 (unrealized) = 400; peak stays 500
    assert dd1 == pytest.approx(100.0 / 10_000.0)
    assert bot._long_book_peak_value == 500.0


def test_dd_frac_peak_ratchets_up_never_down():
    bot = _stub_bot()
    bot._long_book_realized_pnl_total = 100.0
    bot._long_book_dd_frac(10_000.0)
    assert bot._long_book_peak_value == 100.0
    bot._long_book_realized_pnl_total = 50.0
    bot._long_book_dd_frac(10_000.0)
    assert bot._long_book_peak_value == 100.0


def test_dd_frac_guards_non_positive_equity():
    bot = _stub_bot()
    assert bot._long_book_dd_frac(0.0) == 0.0
    assert bot._long_book_dd_frac(-5.0) == 0.0


def test_dd_frac_zero_mark_does_not_fabricate_a_drawdown_spike():
    # Phase-C whole-phase review, Minor #5: a 0.0 mark (a bad/absent
    # tick, key PRESENT in self.marks with value 0.0) must fall back to
    # entry_price for the unrealized calc - the SAME `or p.entry_price`
    # guard _long_book_cycle's own book_exposure_usd sums already use -
    # not read literally, which would fabricate a huge phantom
    # unrealized loss (and a dd-ladder downgrade) from a single bad tick.
    bot = _stub_bot()
    bot._long_book_realized_pnl_total = 500.0
    pos = Position(position_id="p1", symbol="BTC/USD", direction="long",
                   entry_price=60_000.0, size=0.01, original_size=0.01,
                   opened_at=_dt(1_699_000_000.0), book="long")
    bot.state.add_position(pos)
    bot.marks["BTC/USD"] = 0.0
    assert bot._long_book_dd_frac(10_000.0) == 0.0


# ---- 12b. downgrade wiring (item 3(a)) ------------------------------------

def test_dd_breach_triggers_one_rung_downgrade_and_lb041(fake_audit):
    bot = _stub_bot()
    for _ in range(10):
        bot.long_ladder.note_close(1.0, is_live=False)
    assert bot.long_ladder.rung() == 1
    bot._long_book_peak_value = 1000.0
    bot._long_book_realized_pnl_total = 0.0   # dd_frac = 1000/10_000 = 10%
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.long_ladder.rung() == 0
    codes = [e[1] for e in fake_audit.entries]
    assert Code.LB_RUNG_DOWN in codes


def test_dd_breach_debounces_repeat_calls_until_recovery(fake_audit):
    bot = _stub_bot()
    for _ in range(10):
        bot.long_ladder.note_close(1.0, is_live=False)
    bot._long_book_peak_value = 1000.0
    bot._long_book_realized_pnl_total = 0.0
    bot._long_book_cycle(1_700_000_000.0)
    n1 = sum(1 for e in fake_audit.entries if e[1] == Code.LB_RUNG_DOWN)
    assert n1 == 1
    bot._long_book_cycle(1_700_000_030.0)      # still breached, 30s later
    n2 = sum(1 for e in fake_audit.entries if e[1] == Code.LB_RUNG_DOWN)
    assert n2 == 1, "a still-breached drawdown must not re-apply every cycle"


def test_dd_breach_can_refire_after_recovering_below_threshold(fake_audit):
    bot = _stub_bot()
    for _ in range(10):
        bot.long_ladder.note_close(1.0, is_live=False)
    bot._long_book_peak_value = 1000.0
    bot._long_book_realized_pnl_total = 0.0
    bot._long_book_cycle(1_700_000_000.0)
    assert bot._long_book_dd_breach_active is True
    bot._long_book_realized_pnl_total = 1000.0   # recovers to the peak
    bot._long_book_cycle(1_700_000_060.0)
    assert bot._long_book_dd_breach_active is False
    bot._long_book_realized_pnl_total = 0.0      # breaches again
    bot._long_book_cycle(1_700_000_120.0)
    n = sum(1 for e in fake_audit.entries if e[1] == Code.LB_RUNG_DOWN)
    assert n == 2


# ---- 12c. adverse-transition-survived episode (item 3(b)) -----------------

def test_adverse_transition_survived_after_sustained_episode(fake_audit):
    bot = _stub_bot()
    pos = Position(position_id="p1", symbol="BTC/USD", direction="long",
                   entry_price=60_000.0, size=0.01, original_size=0.01,
                   opened_at=_dt(1_699_000_000.0), book="long")
    bot.state.add_position(pos)
    t0 = 1_700_000_000.0
    bot._context_state = _stressed_ctx()
    bot._long_book_cycle(t0)                       # episode starts
    assert bot._long_book_adverse_episode_start == t0
    assert bot.long_ladder.adverse_transitions_survived == 0

    t1 = t0 + 25 * 3600.0                          # 25h later, still stressed
    bot._long_book_cycle(t1)
    assert bot.long_ladder.adverse_transitions_survived == 0, \
        "still mid-episode - must not fire early"

    t2 = t1 + 60.0
    bot._context_state = _aligned_ctx()            # episode ends
    bot._long_book_cycle(t2)
    assert bot.long_ladder.adverse_transitions_survived == 1
    codes = [e[1] for e in fake_audit.entries]
    assert Code.LB_ADVERSE_SURVIVED in codes


def test_adverse_transition_too_short_never_fires():
    bot = _stub_bot()
    pos = Position(position_id="p1", symbol="BTC/USD", direction="long",
                   entry_price=60_000.0, size=0.01, original_size=0.01,
                   opened_at=_dt(1_699_000_000.0), book="long")
    bot.state.add_position(pos)
    t0 = 1_700_000_000.0
    bot._context_state = _stressed_ctx()
    bot._long_book_cycle(t0)
    t1 = t0 + 2 * 3600.0                           # only 2h - below adverse_min_hours
    bot._context_state = _aligned_ctx()
    bot._long_book_cycle(t1)
    assert bot.long_ladder.adverse_transitions_survived == 0


def test_adverse_transition_lost_exposure_mid_episode_never_fires():
    bot = _stub_bot()
    pos = Position(position_id="p1", symbol="BTC/USD", direction="long",
                   entry_price=60_000.0, size=0.01, original_size=0.01,
                   opened_at=_dt(1_699_000_000.0), book="long")
    bot.state.add_position(pos)
    t0 = 1_700_000_000.0
    bot._context_state = _stressed_ctx()
    bot._long_book_cycle(t0)
    # exposure drops to zero mid-episode (position closed out elsewhere)
    bot.state.remove_position(pos.position_id)
    t1 = t0 + 25 * 3600.0
    bot._long_book_cycle(t1)
    t2 = t1 + 60.0
    bot._context_state = _aligned_ctx()
    bot._long_book_cycle(t2)
    assert bot.long_ladder.adverse_transitions_survived == 0, \
        "exposure must be held THROUGHOUT the episode to count"


def test_adverse_transition_dd_breach_mid_episode_never_fires():
    bot = _stub_bot()
    pos = Position(position_id="p1", symbol="BTC/USD", direction="long",
                   entry_price=60_000.0, size=0.01, original_size=0.01,
                   opened_at=_dt(1_699_000_000.0), book="long")
    bot.state.add_position(pos)
    t0 = 1_700_000_000.0
    bot._context_state = _stressed_ctx()
    bot._long_book_cycle(t0)
    # a drawdown breach fires mid-episode
    bot._long_book_peak_value = 1000.0
    bot._long_book_realized_pnl_total = 0.0
    t1 = t0 + 25 * 3600.0
    bot._long_book_cycle(t1)
    t2 = t1 + 60.0
    bot._context_state = _aligned_ctx()
    bot._long_book_cycle(t2)
    assert bot.long_ladder.adverse_transitions_survived == 0, \
        "dd must stay under the downgrade line THROUGHOUT the episode"


# ---- 12d. crisis cadence pause (item 4) ------------------------------------

def test_crisis_regime_pauses_adds_and_logs_lb050(fake_audit, monkeypatch):
    bot = _stub_bot()
    monkeypatch.setattr(bot.macro, "state",
                        lambda asset: types.SimpleNamespace(label="crisis"))
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls == []
    paused = [e for e in fake_audit.entries if e[1] == Code.LB_PAUSED]
    assert paused, "crisis regime must pause adds via the LB-050 path"
    assert any(e[3].get("kind") == "crisis" for e in paused)


def test_crisis_pause_disabled_via_config_flag(fake_audit, monkeypatch):
    lbp = dict(LB_CFG, context=dict(LB_CFG["context"], pause_in_crisis=False))
    bot = _stub_bot(lb_cfg=lbp)
    monkeypatch.setattr(bot.macro, "state",
                        lambda asset: types.SimpleNamespace(label="crisis"))
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.orders.calls, "pause_in_crisis=False must not block adds"


def test_non_crisis_regime_label_never_pauses(fake_audit):
    bot = _stub_bot()
    bot._long_book_cycle(1_700_000_000.0)          # default stub macro: "range"
    assert bot.orders.calls, "a non-crisis regime must never pause adds"


def test_crisis_never_blocks_the_thesis_stop_exit(monkeypatch):
    bot = _stub_bot()
    monkeypatch.setattr(bot.macro, "state",
                        lambda asset: types.SimpleNamespace(label="crisis"))
    entry = 60_000.0
    stop = thesis_stop_price(entry, LB_CFG["thesis_stop_pct"])
    pos = Position(position_id="p1", symbol="BTC/USD", direction="long",
                   entry_price=entry, size=0.01, original_size=0.01,
                   opened_at=_dt(1_699_000_000.0), book="long",
                   stop_price=stop)
    bot.state.add_position(pos)
    bot.marks["BTC/USD"] = stop - 1.0
    exits = []
    monkeypatch.setattr(
        bot, "_submit_exit",
        lambda p, pct, reason, **kw: exits.append((p, pct, reason, kw)))
    bot._manage_open_position(pos, 1_700_000_000.0, bot.state.total_equity(),
                              {"BTC": bot.macro.state("BTC")})
    assert len(exits) == 1
    assert exits[0][3].get("reason_code") == Code.LB_THESIS_INVALIDATED.value


# ---- 12e. euphoria give-back phase wiring (item 5) -------------------------

def test_long_book_cycle_calls_set_phase_with_current_halving_phase():
    bot = _stub_bot(context_state=_aligned_ctx(halving_phase="euphoria"))
    calls = []
    orig = bot.long_tier_engine.set_phase

    def _spy(phase):
        calls.append(phase)
        return orig(phase)
    bot.long_tier_engine.set_phase = _spy
    bot._long_book_cycle(1_700_000_000.0)
    assert calls == ["euphoria"]


def test_long_book_cycle_euphoria_phase_tightens_the_long_tier_engine():
    lbp = dict(LB_CFG)
    pt = dict(LB_CFG["profit_taking"])
    pt["give_back"] = dict(pt["give_back"], euphoria_giveback_frac=0.20)
    lbp["profit_taking"] = pt
    bot = _stub_bot(lb_cfg=lbp,
                    context_state=_aligned_ctx(halving_phase="euphoria"))
    assert bot.long_tier_engine.gb_frac == 0.35        # base, pre-cycle
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.long_tier_engine.gb_frac == 0.20


def test_long_book_cycle_non_euphoria_phase_keeps_base_gb_frac():
    lbp = dict(LB_CFG)
    pt = dict(LB_CFG["profit_taking"])
    pt["give_back"] = dict(pt["give_back"], euphoria_giveback_frac=0.20)
    lbp["profit_taking"] = pt
    bot = _stub_bot(lb_cfg=lbp,
                    context_state=_aligned_ctx(halving_phase="expansion"))
    bot._long_book_cycle(1_700_000_000.0)
    assert bot.long_tier_engine.gb_frac == 0.35


# ---- 12f. deny-debounce (item 6; "ceiling" folded in at task C6) ----------

def test_deny_debounce_ceiling_ten_denials_then_backoff_expiry(fake_audit):
    # Task C6 (C5 review, Minor 5 / progress.md "ceiling deny un-debounced
    # -> C6 one-liner"): "ceiling" joins the debounced set exactly like
    # event_window/context_unknown/context_misaligned/crisis - a book
    # parked at its ceiling with no closed position to free headroom
    # denies IDENTICALLY every ~30s tick, potentially for as long as the
    # ceiling holds. C5 deliberately left it undebounced ("not named in
    # the brief"); this closes that gap.
    lbp = dict(LB_CFG, assets=["BTC"])
    equity = 10_000.0
    # rung 0 paper ceiling = r1.ceiling_frac(0.1) * equity - park an
    # existing long-book position AT the ceiling so headroom is zero on
    # every pass (mirrors test_deny_ceiling_exhausted_blocks_adds).
    ceiling_usd = 0.1 * equity
    existing = Position(
        position_id="parked", symbol="BTC/USD", direction="long",
        entry_price=60_000.0, size=ceiling_usd / 60_000.0,
        original_size=ceiling_usd / 60_000.0,
        opened_at=_dt(1_699_000_000.0), book="long")
    bot = _stub_bot(lb_cfg=lbp, equity=equity, open_positions=[existing])
    t = 1_700_000_000.0
    for i in range(10):
        bot._long_book_cycle(t + i * 30.0)
    denies = [e for e in fake_audit.entries
             if e[1] == Code.LB_ADD_DENIED and e[3].get("kind") == "ceiling"]
    assert len(denies) == 1

    t_after = t + 9 * 30.0 + 31 * 60.0   # past the 30-minute retry backoff
    bot._long_book_cycle(t_after)
    denies2 = [e for e in fake_audit.entries
              if e[1] == Code.LB_ADD_DENIED and e[3].get("kind") == "ceiling"]
    assert len(denies2) == 2


def test_deny_debounce_context_misaligned_ten_denials_then_backoff_expiry(
        fake_audit):
    lbp = dict(LB_CFG, assets=["BTC"])
    bot = _stub_bot(lb_cfg=lbp, context_state=_misaligned_ctx())
    t = 1_700_000_000.0
    for i in range(10):
        bot._long_book_cycle(t + i * 30.0)
    denies = [e for e in fake_audit.entries
             if e[1] == Code.LB_ADD_DENIED
             and e[3].get("kind") == "context_misaligned"]
    assert len(denies) == 1

    t_after = t + 9 * 30.0 + 31 * 60.0   # past the 30-minute retry backoff
    bot._long_book_cycle(t_after)
    denies2 = [e for e in fake_audit.entries
              if e[1] == Code.LB_ADD_DENIED
              and e[3].get("kind") == "context_misaligned"]
    assert len(denies2) == 2


def test_deny_debounce_conviction_enforce_ten_denials_then_backoff_expiry(
        fake_audit):
    lbp = dict(LB_CFG, assets=["BTC"])
    bot = _stub_bot(lb_cfg=lbp, conviction_mode="enforce", regime_live=0,
                    regime_floor=60)
    t = 1_700_000_000.0
    for i in range(10):
        bot._long_book_cycle(t + i * 30.0)
    denies = [e for e in fake_audit.entries
             if e[1] == Code.LB_ADD_DENIED and "conviction_code" in e[3]]
    assert len(denies) == 1

    t_after = t + 9 * 30.0 + 31 * 60.0
    bot._long_book_cycle(t_after)
    denies2 = [e for e in fake_audit.entries
              if e[1] == Code.LB_ADD_DENIED and "conviction_code" in e[3]]
    assert len(denies2) == 2


def test_conviction_enforce_denial_backs_off_the_asset(fake_audit):
    # Phase-C whole-phase review, Important #2: the conviction-deny
    # branch must back the asset off via _long_book_note_failure exactly
    # like the sizer/submit failure branches (main.py's own
    # _long_book_note_failure docstring) - otherwise the unconditional
    # conviction-formula evaluation itself (not just its audit emission)
    # re-runs every ~30s slow_cycle tick for as long as the disposition
    # persists.
    lbp = dict(LB_CFG, assets=["BTC"])
    bot = _stub_bot(lb_cfg=lbp, conviction_mode="enforce", regime_live=0,
                    regime_floor=60)
    t = 1_700_000_000.0
    bot._long_book_cycle(t)
    assert bot.orders.calls == []
    assert bot._long_retry_backoff_until.get("BTC", 0.0) \
        == pytest.approx(t + 30 * 60.0)


def test_conviction_enforce_denial_evaluates_conviction_only_once_per_backoff(
        fake_audit):
    # the crux of Important #2: without the backoff wired, decide_add +
    # the conviction re-check re-run (and re-evaluate the SAME
    # disposition) every ~30s tick even though the audit row itself is
    # already debounced (test above). Spy directly on the evaluation
    # call, not just the audit trail.
    lbp = dict(LB_CFG, assets=["BTC"])
    bot = _stub_bot(lb_cfg=lbp, conviction_mode="enforce", regime_live=0,
                    regime_floor=60)
    real_gate = bot._long_book_conviction_gate
    calls = []

    def _spy(asset, context_aligned):
        calls.append(asset)
        return real_gate(asset, context_aligned)

    bot._long_book_conviction_gate = _spy
    t = 1_700_000_000.0
    for i in range(10):
        bot._long_book_cycle(t + i * 30.0)
    assert len(calls) == 1, \
        "a persistent conviction denial must back the asset off - not " \
        "re-run the conviction evaluation every ~30s tick"

    t_after = t + 9 * 30.0 + 31 * 60.0   # past the 30-minute retry backoff
    bot._long_book_cycle(t_after)
    assert len(calls) == 2, \
        "past the backoff window, conviction must be re-evaluated"


def test_deny_debounce_contraction_spacing_ten_denials_then_backoff_expiry(
        fake_audit):
    # Phase-C whole-phase review, Important #3: contraction-scaled
    # spacing denials were deliberately exempted from the deny-debounce
    # (C4/C5's own comments) on the theory they were rare and notable -
    # whole-phase math shows ~11.5k rows/day/asset during a (months-long)
    # contraction phase instead. Route it through the SAME
    # _long_book_deny_gate machinery as event_window/ceiling/etc.
    lbp = dict(LB_CFG, assets=["BTC"])
    # contraction_spacing_mult=2.0 x add_min_spacing_hours=1.0h = 2h
    # required; last add 1h ago means every cycle below denies with
    # "(contraction-scaled)" in the detail, throughout the whole window.
    bot = _stub_bot(lb_cfg=lbp,
                    context_state=_aligned_ctx(halving_phase="contraction"))
    t = 1_700_000_000.0
    bot._long_last_add_ts["BTC"] = t - 3600.0
    for i in range(10):
        bot._long_book_cycle(t + i * 30.0)
    denies = [e for e in fake_audit.entries
             if e[1] == Code.LB_ADD_DENIED and e[3].get("kind") == "spacing"]
    assert len(denies) == 1

    t_after = t + 9 * 30.0 + 31 * 60.0   # past the 30-minute retry backoff
    bot._long_book_cycle(t_after)
    denies2 = [e for e in fake_audit.entries
              if e[1] == Code.LB_ADD_DENIED and e[3].get("kind") == "spacing"]
    assert len(denies2) == 2


def test_deny_debounce_kind_change_reemits_immediately(fake_audit):
    # a DIFFERENT deny kind on the same asset is a transition, not a
    # repeat - it must emit immediately even inside the backoff window.
    lbp = dict(LB_CFG, assets=["BTC"])
    bot = _stub_bot(lb_cfg=lbp, context_state=_misaligned_ctx())
    t = 1_700_000_000.0
    bot._long_book_cycle(t)
    bot._context_state = _unknown_ctx()
    bot._long_book_cycle(t + 30.0)
    denies = [e for e in fake_audit.entries
             if e[1] == Code.LB_ADD_DENIED
             and e[3].get("kind") in ("context_misaligned", "context_unknown")]
    assert len(denies) == 2, \
        "a kind change must re-emit immediately, not wait for backoff"


# ---- 12g. persistence round-trip -------------------------------------------

def test_persistence_round_trips_long_book_equity_curve_and_episode(
        tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _full_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)

    bot._long_book_realized_pnl_total = 123.45
    bot._long_book_peak_value = 500.0
    bot._long_book_dd_breach_active = True
    bot._long_book_adverse_episode_start = 1_700_000_000.0
    bot._long_book_adverse_held_exposure = False
    bot._long_book_adverse_dd_ok = True

    assert bot.store.snapshot(bot)

    bot2 = _full_bot(cfg, dict(prices), resume=True)
    assert bot2._long_book_realized_pnl_total == pytest.approx(123.45)
    assert bot2._long_book_peak_value == pytest.approx(500.0)
    assert bot2._long_book_dd_breach_active is True
    assert bot2._long_book_adverse_episode_start == pytest.approx(
        1_700_000_000.0)
    assert bot2._long_book_adverse_held_exposure is False
    assert bot2._long_book_adverse_dd_ok is True


def test_persistence_defaults_adverse_episode_clean_for_fresh_snapshot(
        tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _full_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)
    assert bot.store.snapshot(bot)

    bot2 = _full_bot(cfg, dict(prices), resume=True)
    assert bot2._long_book_adverse_episode_start is None
    assert bot2._long_book_realized_pnl_total == 0.0
    assert bot2._long_book_peak_value == 0.0


# ---------------------------------------------------------------------------
# F6 (market-conduct pass): Rule 534 self-cross guard -
# main._clear_long_book_bid_before_sell, wired into _submit_exit BEFORE any
# marketable (non-post_only) sell. Mechanics: a long-book bid rests up to
# order_ttl_hours below mark on the SAME pair a risk-off exit escalation
# ladder (or a marketable short-entry/hedge-open sell) can reach down and
# trade against - cancel our own resting bid FIRST so the two can never
# self-cross. Minimal dedicated harness (real LiquidityBot instance via
# __new__, hand-set attributes) - mirrors tests/test_maker_first_exit.py's
# established pattern for driving _submit_exit directly, extended with a
# fake OrderManager that also carries a resting long-book bid.
# ---------------------------------------------------------------------------

class _FakeOrdersExit:
    """Records submit() calls and cancel_order() calls (with ordering, via
    `.events`) against a seeded resting-order book. `cancel_raises` models
    an unexpected cancel-path failure (venue double-fault, bug) - the guard
    must swallow it and let the exit go out regardless (documented
    backstop: the venue's own self-trade-prevention)."""
    def __init__(self, resting=None, cancel_raises=False):
        self.calls: list = []
        self.cancelled: list = []
        self.events: list = []
        self._open: list = list(resting or [])
        self.cancel_raises = cancel_raises

    def open_orders(self):
        return list(self._open)

    def has_open(self, asset, purpose=None, book=None):
        return any(o.asset == asset
                   and (purpose is None or o.purpose == purpose)
                   and (book is None or o.meta.get("book", "5m") == book)
                   for o in self._open)

    def _ordermin(self, pair):
        return 0.0

    def cancel_order(self, order, reason=""):
        if self.cancel_raises:
            raise RuntimeError("simulated cancel-path failure")
        self.cancelled.append((order.order_id, reason))
        self.events.append(("cancel", order.order_id))
        if order in self._open:
            self._open.remove(order)
        order.status = "cancelled"
        return True

    def submit(self, **kwargs):
        self.calls.append(kwargs)
        self.events.append(("submit", kwargs.get("side")))
        return ManagedOrder(
            order_id=f"exit-{len(self.calls)}", txid=None,
            asset=kwargs["asset"], pair=kwargs["pair"],
            symbol=kwargs["symbol"], side=kwargs["side"],
            price=kwargs["price"], size=kwargs["size"],
            purpose=kwargs.get("purpose", "exit"),
            position_id=kwargs.get("position_id"),
            post_only=kwargs.get("post_only", False),
            meta=kwargs.get("meta") or {})


def _resting_long_bid(asset="BTC", price=59_000.0):
    return ManagedOrder(
        order_id="lb-bid-1", txid=None, asset=asset, pair=f"{asset}USD",
        symbol=f"{asset}/USD", side="buy", price=price, size=0.01,
        purpose="entry", post_only=True, meta={"book": "long"})


def _exit_pos(symbol="BTC/USD", direction="long"):
    import datetime
    return Position(
        position_id="p1", symbol=symbol, direction=direction,
        entry_price=58_000.0, size=0.05, original_size=0.05,
        opened_at=datetime.datetime.now(datetime.timezone.utc))


def _exit_bot(*, resting=None, cancel_raises=False,
             bids=((59_500.0, 5.0),), asks=((59_520.0, 5.0),)):
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.orders = _FakeOrdersExit(resting=resting, cancel_raises=cancel_raises)
    bot.kraken = _FakeKraken()
    bot.marks = {"BTC/USD": 59_500.0}
    bot.kraken_books = {"BTC": {"bids": list(bids), "asks": list(asks)}}
    bot._mark_ts = {"BTC/USD": 1_700_000_000.0}
    bot._mark_stale_sec = 20.0
    bot._exit_attempts = {}
    bot._pos_realized = {}
    bot.max_slip_pct = 0.5
    bot.esc_widen_mult = 2.0
    bot.esc_max_slip_pct = 3.0
    bot.esc_market_after = 3
    bot.maker_first_profit_exits = True
    bot.fv = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(fair_value=59_500.0))
    bot.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.3))
    bot.state = PortfolioState(starting_capital=10_000.0)
    return bot


def test_marketable_exit_cancels_resting_bid_first_then_submits(fake_audit):
    resting = _resting_long_bid()
    bot = _exit_bot(resting=[resting])
    bot._submit_exit(_exit_pos(), 100.0, "hard stop",
                     now=1_700_000_000.0)          # profit_take defaults False

    # the exit actually went out, marketable (not post_only)
    assert len(bot.orders.calls) == 1
    assert bot.orders.calls[0]["side"] == "sell"
    assert bot.orders.calls[0]["post_only"] is False

    # the resting long-book bid was cancelled ...
    assert bot.orders.cancelled
    assert bot.orders.cancelled[0][0] == "lb-bid-1"
    assert Code.LB_BID_CLEARED.value in bot.orders.cancelled[0][1]

    # ... and cancelled BEFORE the exit was submitted (ordering)
    kinds = [e[0] for e in bot.orders.events]
    assert kinds.index("cancel") < kinds.index("submit")

    # LB-022 audited, carrying the exit's reason_code
    entries = [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED]
    assert len(entries) == 1
    assert entries[0][3]["asset"] == "BTC"
    assert entries[0][3]["reason_code"] == ""    # this call passed none


def test_marketable_exit_carries_reason_code_into_lb022_payload(fake_audit):
    resting = _resting_long_bid()
    bot = _exit_bot(resting=[resting])
    bot._submit_exit(_exit_pos(), 100.0, "PT-060 time stop",
                     now=1_700_000_000.0, reason_code="PT-060")
    entries = [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED]
    assert len(entries) == 1
    assert entries[0][3]["reason_code"] == "PT-060"


def test_post_only_maker_exit_does_not_cancel_resting_bid(fake_audit):
    # a scheduled profit-TARGET take rests post_only at our own side first
    # (maker-first) - passive-passive same-pair quoting is bona fide
    # two-sided market making, not a self-cross; the bid must survive.
    resting = _resting_long_bid()
    bot = _exit_bot(resting=[resting])
    bot._submit_exit(_exit_pos(), 50.0, "tier take", tier_fired=1,
                     now=1_700_000_000.0, profit_take=True)

    assert len(bot.orders.calls) == 1
    assert bot.orders.calls[0]["post_only"] is True      # maker-first rest
    assert bot.orders.cancelled == []
    assert bot.orders.open_orders() == [resting]         # bid still resting
    assert not [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED]


def test_cancel_failure_does_not_block_the_exit(fake_audit):
    resting = _resting_long_bid()
    bot = _exit_bot(resting=[resting], cancel_raises=True)
    bot._submit_exit(_exit_pos(), 100.0, "hard stop", now=1_700_000_000.0)

    # the cancel attempt blew up, but the exit still went out
    assert len(bot.orders.calls) == 1
    assert bot.orders.calls[0]["side"] == "sell"
    assert bot.orders.cancelled == []       # never recorded - it raised
    # no LB-022 audit row either (the raise happened before the log call) -
    # the venue's own STP is the documented backstop for this residual case
    assert not [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED]


def test_no_resting_bid_is_a_no_op(fake_audit):
    bot = _exit_bot(resting=None)
    bot._submit_exit(_exit_pos(), 100.0, "hard stop", now=1_700_000_000.0)

    assert len(bot.orders.calls) == 1
    assert bot.orders.cancelled == []
    assert not [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED]


def test_short_entry_marketable_sell_hedge_open_also_clears_the_bid(
        fake_audit):
    # main._hedge_actions' "open" branch: a SHORT hedge sells marketable
    # (post_only=False always) - covered by the SAME guard, not a
    # duplicated inline check.
    import types as _types

    from execution.hedging import HedgeEngine

    resting = _resting_long_bid()
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.orders = _FakeOrdersExit(resting=[resting])
    bot.kraken = _FakeKraken()
    bot.marks = {"BTC/USD": 30_000.0, "ETH/USD": 2_000.0}
    bot.kraken_books = {"BTC": {"bids": [[29_999.0, 1.0]],
                                "asks": [[30_001.0, 1.0]]}}
    bot._mark_ts = {"BTC/USD": 1_700_000_000.0, "ETH/USD": 1_700_000_000.0}
    bot._mark_stale_sec = 20.0
    bot._stop_ok = {"BTC": True, "ETH": True}
    bot.max_slip_pct = 0.5
    bot.symbol_map = {"BTC": "BTC/USD", "ETH": "ETH/USD"}
    bot.dry_run = True
    bot.live_armed = False
    bot._live_block_logged = 0.0
    bot._halted = False
    bot.entries_enabled = True
    bot.watchdog = _types.SimpleNamespace(
        state=_types.SimpleNamespace(entries_blocked=False))
    bot.vol = _types.SimpleNamespace(
        state=lambda a: _types.SimpleNamespace(sigma_bar_pct=0.5))
    bot.corr = _types.SimpleNamespace(
        state=_types.SimpleNamespace(corr=lambda a, b: 0.9,
                                     beta=lambda a, b: 1.0))
    # net-long ETH exposure breaches the hedger's rebalance band -> a real
    # HedgeEngine "open" action to short BTC
    bot.state = PortfolioState(starting_capital=10_000.0)
    import datetime
    bot.state.add_position(Position(
        "eth1", "ETH/USD", "long", 2_000.0, 2.5, 2.5,
        datetime.datetime.now(datetime.timezone.utc)))
    bot.hedger = HedgeEngine({}, bot.symbol_map)

    bot._hedge_actions(1_700_000_000.0, equity=10_000.0)

    assert bot.orders.calls, "the hedge open must have gone out"
    assert bot.orders.calls[0]["side"] == "sell"
    assert bot.orders.calls[0]["post_only"] is False
    assert bot.orders.cancelled and bot.orders.cancelled[0][0] == "lb-bid-1"
    assert [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED]


# ---------------------------------------------------------------------------
# F6 taker entry sites (direct and algo-child)
# ---------------------------------------------------------------------------


class _FakeOrdersEntry:
    """Records submit() calls and cancel_order() calls for entry testing.
    Similar to _FakeOrdersExit but captures entry-specific metadata."""
    def __init__(self, resting=None, cancel_raises=False):
        self.calls: list = []
        self.cancelled: list = []
        self.events: list = []
        self._open: list = list(resting or [])
        self.cancel_raises = cancel_raises

    def open_orders(self):
        return list(self._open)

    def has_open(self, asset, purpose=None, book=None):
        return any(o.asset == asset
                   and (purpose is None or o.purpose == purpose)
                   and (book is None or o.meta.get("book", "5m") == book)
                   for o in self._open)

    def _ordermin(self, pair):
        return 0.0

    def cancel_order(self, order, reason=""):
        if self.cancel_raises:
            raise RuntimeError("simulated cancel-path failure")
        self.cancelled.append((order.order_id, reason))
        self.events.append(("cancel", order.order_id))
        if order in self._open:
            self._open.remove(order)
        order.status = "cancelled"
        return True

    def submit(self, **kwargs):
        self.calls.append(kwargs)
        self.events.append(("submit", kwargs.get("side")))
        return ManagedOrder(
            order_id=f"entry-{len(self.calls)}", txid=None,
            asset=kwargs["asset"], pair=kwargs["pair"],
            symbol=kwargs["symbol"], side=kwargs["side"],
            price=kwargs["price"], size=kwargs["size"],
            purpose=kwargs.get("purpose", "entry"),
            position_id=kwargs.get("position_id"),
            post_only=kwargs.get("post_only", False),
            meta=kwargs.get("meta") or {})


def _entry_bot(*, resting=None, cancel_raises=False,
               bids=((59_500.0, 5.0),), asks=((59_520.0, 5.0),)):
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.orders = _FakeOrdersEntry(resting=resting, cancel_raises=cancel_raises)
    bot.kraken = _FakeKraken()
    bot.marks = {"BTC/USD": 59_500.0}
    bot.kraken_books = {"BTC": {"bids": list(bids), "asks": list(asks)}}
    bot._mark_ts = {"BTC/USD": 1_700_000_000.0}
    bot._mark_stale_sec = 20.0
    bot.view = {"BTC": {"candles": []}}
    bot.state = PortfolioState(starting_capital=10_000.0)
    bot.fv = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(fair_value=59_500.0, kraken_mid=59_500.0))
    bot.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.3))
    bot.liq = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(label="normal", spread_bps=2.0))
    bot.quoter = types.SimpleNamespace(
        quote=lambda *a, **k: types.SimpleNamespace(bid=59_490.0, ask=59_510.0))
    bot.tactics = types.SimpleNamespace(
        plan_entry=lambda *a, **k: types.SimpleNamespace(
            price=59_490.0, post_only=False, style="aggressive"))
    bot.pretrade = types.SimpleNamespace(maker_fee_bps=1.0)
    bot.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0)
    bot._equity = lambda: 10_000.0
    bot._algo_meta = {}
    bot._px = lambda s, p: f"{p:.2f}"
    bot._last_entry_admit_ts = 0.0
    bot.algo = types.SimpleNamespace(
        next_slice=lambda pid, now, vol: types.SimpleNamespace(
            units=0.01, seq=1, n_total=4),
        note_child_order=lambda pid, posid: None,
        note_child_rejected=lambda *a, **k: None)
    return bot


def _real_taker_entry_cfg(tmp_path) -> dict:
    """A full-bot config that funnels EVERY confirmed signal into the
    legacy single-entry path (main.py ~3186-3197), the exact site under
    review. Two structural alternates to that path exist:
    grid_ladder.plan arming -> _place_ladder, and algo.should_engage ->
    _submit_algo_child (config.json's "algo" section ships empty, so
    should_engage is already off by default - grid_ladder ships enabled,
    so it is explicitly disabled here). The algo-child site is already
    pinned for real by test_algo_child_taker_short_entry_cancels_
    resting_bid_first below; the ladder never reaches this guard at all
    (out of scope for this task). ml/pretrade/order_manager overrides
    mirror tests/test_context_integration.py's _cfg(force_fill=True) -
    the established recipe for making a programmatically-forced
    confirmed signal clear the sizer + pretrade EV gate into a real
    order instead of a silent veto."""
    cfg = _full_cfg(tmp_path)
    cfg["grid_ladder"] = dict(cfg.get("grid_ladder", {}), enabled=False)
    cfg["ml"]["cold_start_prior_p"] = 0.72
    cfg["pretrade"]["min_edge_cost_ratio"] = 0.1
    cfg["pretrade"]["price_exit_leg"] = False
    cfg.setdefault("order_manager", {}).setdefault(
        "sim_fill", {})["queue_aware"] = False
    return cfg


def _seed_real_resting_long_bid(bot, t: float):
    """Places one REAL long-book BUY bid for BTC through the actual
    _long_book_cycle machinery (same recipe as test_end_to_end_slow_
    cycle_places_a_real_long_book_order above): a genuine resting order
    the real OrderManager tracks, not a hand-built ManagedOrder double."""
    bot.context.maybe_poll = lambda now=None: _aligned_ctx()
    bot.fast_cycle(t)
    bot.slow_cycle(t)
    long_orders = [o for o in bot.orders.open_orders()
                  if o.asset == "BTC" and o.meta.get("book") == "long"]
    assert long_orders, "precondition: a real resting long-book BTC bid"
    return long_orders[0]


def _force_btc_short_signal(bot, urgency: float) -> None:
    """Monkeypatches the REAL SignalGateEngine instance's evaluate_asset
    (same technique as test_context_integration.py's
    _force_confirmed_signals) so slow_cycle's entry loop sees a
    confirmed SHORT on BTC at the given urgency - direction and urgency
    are the only things faked; sizing, pretrade, conviction, and
    submission all run for real. ETH gets an honest non-signal so it
    never competes with BTC for a position slot."""
    def _evaluate(base_asset, view):
        if base_asset == "BTC":
            return SignalResult(
                symbol="BTC/USD", direction="short", confidence=1.0,
                size=0.0, all_confirmed=True, gates_passed={},
                urgency=urgency)
        return SignalResult(
            symbol=f"{base_asset}/USD", direction=None, confidence=0.0,
            size=0.0, all_confirmed=False, gates_passed={})
    bot.gates.evaluate_asset = _evaluate


def _spy_orders(bot) -> list:
    """Wraps the REAL OrderManager's cancel_order/submit with an ordered
    event log, delegating to the originals for every call - proves
    cancel-before-submit ordering on the real object slow_cycle actually
    calls, the same property the algo-child test's fake recorder proves
    on its own (fake) orders double."""
    events: list = []
    orig_cancel, orig_submit = bot.orders.cancel_order, bot.orders.submit

    def _cancel(order, reason="cancelled"):
        events.append(("cancel", order.order_id, reason))
        return orig_cancel(order, reason=reason)

    def _submit(*a, **kw):
        result = orig_submit(*a, **kw)
        events.append(("submit", kw.get("side"), kw.get("post_only")))
        return result

    bot.orders.cancel_order = _cancel
    bot.orders.submit = _submit
    return events


def test_direct_taker_short_entry_cancels_resting_bid_first(
        fake_audit, tmp_path, monkeypatch):
    """Drives the REAL slow_cycle entry loop (never a hand-reconstructed
    call to the guard) to a genuine taker short entry on BTC: a confirmed
    SHORT signal at urgency 0.95 (>= execution_tactics.taker_at_urgency
    0.88) makes execution/tactics.py's plan_entry return
    EntryPlan("taker", price, True, post_only=False) (tactics.py:102-110).
    _ladder_entry (main.py:3991-3992) falls through unhandled for ANY
    taker plan regardless of grid_ladder.enabled, so this exercises the
    exact legacy single-entry site at main.py:3186-3197 the review named,
    not a stand-in. A real long-book BUY bid for BTC is seeded first
    through one genuine _long_book_cycle pass; the pin is that main.py's
    wiring cancels it (LB-022) BEFORE the taker sell reaches
    OrderManager.submit - proven with an ordered event log wrapped
    around the REAL OrderManager methods (not a fake orders recorder)."""
    monkeypatch.chdir(tmp_path)
    cfg = _real_taker_entry_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)

    t = 1_700_000_000.0
    resting = _seed_real_resting_long_bid(bot, t)

    _force_btc_short_signal(bot, urgency=0.95)
    events = _spy_orders(bot)

    t2 = t + 5.0
    bot.fast_cycle(t2)
    bot.slow_cycle(t2)

    sell_calls = [e for e in events if e[0] == "submit" and e[1] == "sell"]
    assert sell_calls, "the real slow_cycle entry loop must submit the " \
        "taker short entry"
    assert sell_calls[0][2] is False, "the taker plan must carry " \
        "post_only=False through to the submit"

    cancels = [e for e in events
              if e[0] == "cancel" and e[1] == resting.order_id]
    assert cancels, "the resting long-book bid must be cancelled"
    assert Code.LB_BID_CLEARED.value in cancels[0][2]

    kinds = [e[0] for e in events]
    assert kinds.index("cancel") < kinds.index("submit"), \
        "cancel must happen BEFORE the marketable sell is submitted"

    lb_orders = [o for o in bot.orders.open_orders()
                if o.order_id == resting.order_id]
    assert not lb_orders, "the original resting long-book bid must be gone"

    entries = [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED]
    assert entries, "LB-022 must be audited"
    assert entries[0][3]["asset"] == "BTC"


def test_algo_child_taker_short_entry_cancels_resting_bid_first(fake_audit):
    """Algo-child path (_submit_algo_child) with taker-style short entry
    (post_only=False) must cancel the resting long-book bid first (LB-022)."""
    resting = _resting_long_bid()
    bot = _entry_bot(resting=[resting])

    # Create a parent order for the algo (short direction → sell side)
    parent = types.SimpleNamespace(
        parent_id="algo-par1", asset="BTC", symbol="BTC/USD",
        side="sell", direction="short", arrival_price=59_500.0, urgency=0.0)

    # Set up _algo_meta for this parent
    bot._algo_meta["algo-par1"] = {
        "p_win": 0.6, "edge_bps": 10.0, "est_cost_bps": 5.0,
        "features": None, "leverage": 1.0, "post_only": False,
        "probe": False, "candidate_id": ""}

    # Call _submit_algo_child which should guard before submit
    bot._submit_algo_child(parent, now=1_700_000_000.0)

    # Child order submitted, bid cancelled first
    assert len(bot.orders.calls) == 1
    assert bot.orders.calls[0]["side"] == "sell"
    assert bot.orders.calls[0]["post_only"] is False

    assert bot.orders.cancelled
    assert bot.orders.cancelled[0][0] == "lb-bid-1"
    assert Code.LB_BID_CLEARED.value in bot.orders.cancelled[0][1]

    # Cancel happened before submit
    kinds = [e[0] for e in bot.orders.events]
    assert kinds.index("cancel") < kinds.index("submit")

    # LB-022 audited
    entries = [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED]
    assert len(entries) == 1


def test_post_only_maker_short_entry_does_not_cancel_resting_bid(
        fake_audit, tmp_path, monkeypatch):
    """Same REAL slow_cycle path as the taker test above, urgency 0.75
    (>= execution_tactics.improve_at_urgency 0.70, < taker_at_urgency
    0.88): plan_entry returns EntryPlan("improve", price, False,
    post_only=True) (tactics.py:112-121), still routed through the same
    unhandled-ladder legacy path (grid_ladder disabled in
    _real_taker_entry_cfg, same as the taker test, so this isn't
    reaching a DIFFERENT site than the one under review). The wiring at
    main.py:3195-3197 passes the PLAN's own post_only straight into the
    guard's no-op predicate (`side != "sell" or post_only`) - never a
    hardcoded value. This test's whole assertion IS that pin: the maker
    short entry still submits for real (side="sell", post_only=True),
    but the resting long-book bid is left completely untouched and
    LB-022 never fires - a no-op the guard reaches deliberately, not by
    skipping the site. Passive-passive same-pair quoting (our own
    resting long-book bid alongside our own resting maker short) is
    bona fide two-sided market making, not the wash-trade pattern Rule
    534 targets."""
    monkeypatch.chdir(tmp_path)
    cfg = _real_taker_entry_cfg(tmp_path)
    prices = {"ETH": 2000.0, "BTC": 60_000.0}
    bot = _full_bot(cfg, prices, resume=False)

    t = 1_700_000_000.0
    resting = _seed_real_resting_long_bid(bot, t)

    _force_btc_short_signal(bot, urgency=0.75)
    events = _spy_orders(bot)

    t2 = t + 5.0
    bot.fast_cycle(t2)
    bot.slow_cycle(t2)

    sell_calls = [e for e in events if e[0] == "submit" and e[1] == "sell"]
    assert sell_calls, "the maker-style short entry must still submit"
    assert sell_calls[0][2] is True, "the improve plan must carry " \
        "post_only=True through to the submit - not a hardcoded style"

    assert not [e for e in events if e[0] == "cancel"], \
        "a post_only short entry must never cancel the resting bid"
    lb_orders = [o for o in bot.orders.open_orders()
                if o.order_id == resting.order_id]
    assert lb_orders, "the resting long-book bid must still be open"
    assert lb_orders[0].status not in ("cancelled",)

    assert not [e for e in fake_audit.entries if e[1] == Code.LB_BID_CLEARED], \
        "LB-022 must never fire for a maker-first short entry"


def test_long_book_entry_meta_threads_avail_from_its_own_extras():
    """owed 68 (2026-08-11 ledger audit): the long-book entry path computed
    _feature_extras (which carries the avail feed flags) and threw the dict
    away, so every long-book live row shipped blank avail_*/quotes_frozen
    columns while the 5m path's rows were populated. The meta must thread
    avail from the SAME extras dict its features were built from."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    i = src.find('meta = {"book": "long"')
    assert i != -1, "long-book entry meta literal moved - re-pin"
    window = src[i:i + 900]
    assert '"features"' in window and '"avail"' in window, (
        "long-book entry meta no longer threads avail beside features - "
        "owed 68 regressed: long-book live rows will ship blank "
        "avail_*/quotes_frozen columns again")
    assert "_lb_extras" in window, (
        "avail must come from the SAME extras dict the features were "
        "built from (feature-build instant semantics), not a re-computation")
