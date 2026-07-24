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
import json
import math
import types
from pathlib import Path

import pytest

from core.codes import Code
from core.state import PortfolioState, Position
from data.context_engine import ContextState
from execution.inventory import InventoryManager
from main import LiquidityBot, load_config
from regime import LiquidityRegimeEngine, MacroRegimeEngine, VolRegimeEngine
from risk.conviction import ConvictionFormula
from risk.long_book import AddPlan, EvidenceLadder, thesis_stop_price
from risk.position_sizer import PositionSizer
from risk.profit_tiers import ProfitTierEngine
from risk.protocols import RiskProtocolStack
from runner import BotRunner
from scripts.smoke_test import MockBinanceUS, MockKraken, MockOKX

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
    """Records every submit() call; never touches Kraken/the firewall.
    `accept=False` simulates every OTHER order-manager-side refusal
    (firewall/venue-min/zero-format) a real OrderManager can return None
    for - _place_long_book_add must degrade to a no-op, never raise."""
    def __init__(self, accept: bool = True):
        self.calls: list = []
        self.accept = accept

    def submit(self, **kwargs):
        self.calls.append(kwargs)
        if not self.accept:
            return None
        return types.SimpleNamespace(**kwargs)

    def open_orders(self):
        return []

    def has_open(self, asset, purpose):
        return False


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
    assert bot._long_adds_placed >= 1
    assert bot._long_last_add_ts["BTC"] == 1_700_000_000.0
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
             context_aligned=None):
        calls.append(context_aligned)
        return real(asset, signal, decision, regime_label, explored,
                    context_aligned=context_aligned)
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
# 7. persistence round-trips ladder + book across snapshot/restore (FULL bot)
# ---------------------------------------------------------------------------

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
