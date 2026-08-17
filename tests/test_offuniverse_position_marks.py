"""tests/test_offuniverse_position_marks.py — open positions OUTSIDE the
trading universe keep receiving marks (broken-exit-path fix, 2026-08-16).

The defect: symbol_map is built once at __init__ from the boot's (skimmer-
widened) trading_pairs, but positions outlive universe rotations across
reboots. fast_cycle's mark/book refresh covered ONLY symbol_map, and
marks/_mark_ts/kraken_books start empty every process — so a position whose
asset rotated out had NO mark at all: _manage_open_position early-returns on
a missing mark and the protective stop could never fire (live instance: the
SOL/USD trip orphaned at the 2026-08-15 boot, stop 0.7% below a price it
could never see).

Pinned here:
  * the batched Ticker call widens to union(universe, open-position assets)
    — still exactly ONE get_tickers call per cycle, never per-asset calls;
  * the refreshed mark REACHES the exit path: the protective stop fires when
    the fresh price crosses it;
  * the asset's book lands in kraken_books/book_ts (the dry-run fill
    simulator only fills exit orders against a book that is present);
  * the book-mid fallback also covers off-universe assets when the ticker
    stalls;
  * hedge positions get the same coverage (they exit on correlation floors,
    valued off these marks);
  * NO open position on an asset -> the asset is NOT fetched (no rate-limit
    waste; the set self-empties as positions close).
"""
import types
from datetime import datetime, timezone

from core.state import PortfolioState, Position
from core.watchdog import Watchdog
from main import LiquidityBot

ETH_PAIR = "ETHUSD"
SOL_PAIR = "SOLUSD"


def _noop(*a, **k):
    return None


def _bot():
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b._halted = False
    b.symbol_map = {"ETH": "ETH/USD"}          # SOL is NOT in the universe
    b._pair_of = {"ETH": ETH_PAIR}
    b._pair_list = [ETH_PAIR]
    b.marks, b._mark_ts, b._stop_ok, b.book_ts, b.kraken_books = \
        {}, {}, {}, {}, {}
    b.last_signals = {}
    b._stop_hit = {}
    b._mark_stale_sec = 20.0
    b._exit_eval_failures = 0

    b.state = PortfolioState(starting_capital=10_000.0)

    b.watchdog = Watchdog({"enabled": True, "tick_jump_quarantine_pct": 8.0})
    b.watchdog.evaluate = _noop

    # capturing venue mock: real kraken_pair semantics, per-call pair lists
    b._ticker_px = {}             # pair -> price (None/absent = no price)
    b._books = {}                 # pair -> book dict (absent = no book)
    b._ticker_calls = []          # one entry per get_tickers CALL (the batch)
    b._depth_calls = []           # one entry per get_order_book call
    def _get_tickers(pairs):
        b._ticker_calls.append(list(pairs))
        return {p: b._ticker_px[p] for p in pairs if b._ticker_px.get(p)}
    def _get_order_book(pair):
        b._depth_calls.append(pair)
        return b._books.get(pair)
    b.kraken = types.SimpleNamespace(
        get_tickers=_get_tickers,
        get_order_book=_get_order_book,
        kraken_pair=lambda s: s.replace("/", ""))
    b.kraken_ws = None

    b.thales = types.SimpleNamespace(observe_feed_health=_noop,
                                     observe_fast=_noop)
    b._step_exec_algos = _noop
    b._apply_sim = _noop
    b._poll_books = []            # books dicts orders.poll actually received
    b.orders = types.SimpleNamespace(
        poll=lambda books, sig, now: (b._poll_books.append(dict(books)),
                                      [])[1],
        open_orders=lambda: [],
        has_open=lambda *a, **k: False)
    b.store = types.SimpleNamespace(snapshot=_noop)
    b.vol = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(sigma_bar_pct=0.5))
    b.fv = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(fair_value=74.0))
    b.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(
            playbook={"tier_scale": 1.0}, is_counter_trend=lambda d: False))
    b.inventory = types.SimpleNamespace(
        inventory_ratio=lambda *a, **k: 0.0, soft_cap_pct=50.0,
        hard_cap_pct=100.0, derisk_actions=lambda *a, **k: [])
    b.hedger = types.SimpleNamespace(evaluate=lambda *a, **k: [])
    b.corr = types.SimpleNamespace(state=None)
    b.postmortem = types.SimpleNamespace(record_marks=_noop,
                                         poll=lambda now: [])
    b.markout = types.SimpleNamespace(poll=_noop, record_fill=_noop,
                                      snapshot=lambda: {})
    b.risk_protocols = types.SimpleNamespace(observe=_noop)
    b.monitor = types.SimpleNamespace(record_close=_noop)
    b.capital = types.SimpleNamespace(
        hard_stop_triggered=lambda *a, **k: False)

    b._tier_calls = []
    spy = types.SimpleNamespace(evaluate=lambda *a, **k: (
        b._tier_calls.append(1),
        types.SimpleNamespace(should_close_partial=False, close_pct=0.0,
                              tier_fired=0, is_profit_take=False))[1])
    b._tier_engine = lambda scale: spy

    b.exits = []
    b._submit_exit = lambda pos, pct, reason, **k: b.exits.append(
        (pos.position_id, pct, reason))
    b._px = lambda s, p: f"{p:.2f}"
    return b


def _sol_pos(stop_price=74.05, is_hedge=False, pid="sol1"):
    # mirrors the live orphan: SOL/USD long 0.14 @ 75.61, stop below mark
    pos = Position(pid, "SOL/USD", "long", 75.61, 0.14, 0.14,
                   datetime.now(timezone.utc))
    pos.stop_price = stop_price
    pos.is_hedge = is_hedge
    return pos


def _book(mid):
    return {"bids": [[mid - 0.05, 5.0]], "asks": [[mid + 0.05, 5.0]]}


# --- the mark updates AND the stop fires when price crosses ----------------
def test_offuniverse_mark_updates_and_stop_fires():
    b = _bot()
    b.state.add_position(_sol_pos(stop_price=74.05))
    b._ticker_px = {ETH_PAIR: 2000.0, SOL_PAIR: 74.5}
    b._books = {ETH_PAIR: _book(2000.0), SOL_PAIR: _book(74.5)}

    b.fast_cycle(1000.0)
    # ONE batched Ticker call carrying BOTH pairs, no duplicates
    assert len(b._ticker_calls) == 1
    pairs = b._ticker_calls[0]
    assert ETH_PAIR in pairs and SOL_PAIR in pairs
    assert len(pairs) == len(set(pairs))
    # the off-universe mark landed and is stamped fresh
    assert b.marks["SOL/USD"] == 74.5
    assert b._mark_ts["SOL/USD"] == 1000.0
    assert b._stop_ok.get("SOL") is True
    assert b.exits == []                       # 74.5 > 74.05: no exit yet

    # price crosses the stop -> the protective stop FIRES on the fresh mark
    b._ticker_px[SOL_PAIR] = 74.0
    b._books[SOL_PAIR] = _book(74.0)
    b.fast_cycle(1005.0)
    assert b.marks["SOL/USD"] == 74.0
    assert [(pid, pct) for pid, pct, _r in b.exits] == [("sol1", 100.0)]
    assert any(r.startswith("stop") for _pid, _pct, r in b.exits)


# --- no open position -> the asset is NOT fetched (no rate-limit waste) ----
def test_offuniverse_asset_not_fetched_without_position():
    b = _bot()
    b._ticker_px = {ETH_PAIR: 2000.0, SOL_PAIR: 74.5}
    b._books = {ETH_PAIR: _book(2000.0), SOL_PAIR: _book(74.5)}
    b.fast_cycle(1000.0)
    assert b._ticker_calls == [[ETH_PAIR]]     # SOLUSD never requested
    assert SOL_PAIR not in b._depth_calls
    assert "SOL/USD" not in b.marks

    # ...and the set self-empties: position closed -> next cycle stops
    # fetching (same bot, position added then removed)
    pos = _sol_pos()
    b.state.add_position(pos)
    b.fast_cycle(1005.0)
    assert SOL_PAIR in b._ticker_calls[-1]
    b.state.remove_position(pos.position_id)
    b.fast_cycle(1010.0)
    assert SOL_PAIR not in b._ticker_calls[-1]


# --- the book reaches the dry-run fill simulator's input -------------------
def test_offuniverse_book_reaches_fill_sim_inputs():
    b = _bot()
    b.state.add_position(_sol_pos())
    b._ticker_px = {ETH_PAIR: 2000.0, SOL_PAIR: 74.5}
    sol_book = _book(74.5)
    b._books = {ETH_PAIR: _book(2000.0), SOL_PAIR: sol_book}
    b.fast_cycle(1000.0)
    # kraken_books/book_ts carry the off-universe asset (keyed by ASSET,
    # exactly how orders.poll -> _poll_dry looks books up)...
    assert b.kraken_books.get("SOL") == sol_book
    assert b.book_ts.get("SOL") == 1000.0
    # ...and the SAME cycle's poll already received it
    assert b._poll_books and "SOL" in b._poll_books[-1]


# --- book-mid fallback covers a stalled ticker on the off-universe pair ----
def test_offuniverse_book_mid_fallback():
    b = _bot()
    b.state.add_position(_sol_pos(stop_price=None))
    b._ticker_px = {ETH_PAIR: 2000.0}          # NO SOL ticker price
    b._books = {ETH_PAIR: _book(2000.0), SOL_PAIR: _book(74.5)}
    b.fast_cycle(1000.0)
    assert b.marks["SOL/USD"] == 74.5          # mid of the fresh book
    assert b._mark_ts["SOL/USD"] == 1000.0


# --- hedge positions get the same coverage ---------------------------------
def test_offuniverse_hedge_position_also_fetched():
    b = _bot()
    b.state.add_position(_sol_pos(stop_price=None, is_hedge=True,
                                  pid="solh"))
    b._ticker_px = {ETH_PAIR: 2000.0, SOL_PAIR: 74.5}
    b._books = {ETH_PAIR: _book(2000.0), SOL_PAIR: _book(74.5)}
    b.fast_cycle(1000.0)
    assert SOL_PAIR in b._ticker_calls[0]
    assert b.marks["SOL/USD"] == 74.5          # hedger values off this mark
