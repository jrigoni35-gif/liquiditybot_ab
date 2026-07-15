"""Inventory hardening: maker-first PROFIT exits + cost-honest sizing.

Two coupled changes that kill the 8/8 cost_overrun bleed (35-54bps over a
~25bps estimate on every live close):

  * risk/position_sizer.py  round-trip cost = maker ENTRY (resting limit,
    OM-011) + taker EXIT, not 2*maker. b_net shrinks, so Kelly stops
    sizing marginal edges whose only realization was a cost overrun.
  * main.py::_submit_exit    a PROFIT-tier close (tier_fired>0) rests
    POST-ONLY on our own side of the book on its FIRST attempt (sell at
    the ask / buy at the bid) to CAPTURE the spread instead of paying it.
    RISK exits (tier_fired==0: stops, faults, derisk, unwind) stay
    marketable-first - being out fast beats the spread. An unfilled maker
    exit expires and escalates into the existing marketable ladder
    (attempt>=1 -> post_only False), so nothing is ever trapped.

The exit tests drive the REAL main.py::_submit_exit via the unbound method
against a minimal stub `self`, so the shipped price/side/post_only logic is
exercised without standing up a full LiquidityBot.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import main as main_mod
from core.state import Position
from risk.position_sizer import PositionSizer, payoff_ratio_from_config

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))
_MAKER = float(_CFG["pretrade"]["maker_fee_bps"])
_TAKER = float(_CFG["pretrade"]["taker_fee_bps"])


# ------------------------------------------------------- #2 cost-honest sizing
def _shipped_sizer():
    return PositionSizer(_CFG["position_sizer"],
                         profit_cfg=_CFG.get("profit_taking", {}),
                         risk_cfg=_CFG.get("risk", {}),
                         pretrade_cfg=_CFG.get("pretrade", {}),
                         capital_cfg=_CFG.get("capital_management", {}))


def test_rt_cost_is_maker_entry_plus_taker_exit():
    # the whole fix: round-trip = maker in + taker out, NOT 2*maker in
    s = _shipped_sizer()
    assert s.rt_cost_pct == (_MAKER + _TAKER) / 100.0
    # taker > maker on Kraken, so the honest cost is strictly above the old
    # optimistic 2*maker - the sizer can only get MORE conservative, never less
    assert s.rt_cost_pct > 2.0 * _MAKER / 100.0


def test_b_net_more_conservative_under_honest_cost():
    # same tier/stop structure, only the exit-leg convention changes:
    # honest cost -> lower net payoff ratio -> Kelly sizes marginal edges
    # toward zero (higher net p(win) breakeven).
    prof, risk = _CFG.get("profit_taking", {}), _CFG.get("risk", {})
    b_old = payoff_ratio_from_config(prof, risk, rt_cost_pct=2.0 * _MAKER / 100.0)
    b_new = payoff_ratio_from_config(prof, risk,
                                     rt_cost_pct=(_MAKER + _TAKER) / 100.0)
    assert b_new < b_old
    s = _shipped_sizer()
    assert s.b_net == b_new
    # gross payoff is unchanged (main derives the alpha estimate from it)
    assert s.b == payoff_ratio_from_config(prof, risk, rt_cost_pct=0.0)
    assert s.b_net < s.b
    # net-expectancy breakeven p(win) rises with the honest cost
    assert 1.0 / (1.0 + b_new) > 1.0 / (1.0 + b_old)


# --------------------------------------------------- #1 maker-first exits
def _run_exit(direction, tier_fired, *, attempts=0,
              bids=((99.0, 5.0),), asks=((101.0, 5.0),),
              maker_first_flag=True, profit_take=None):
    """Invoke the real _submit_exit against a stub self; return the kwargs
    captured from orders.submit (None if no order was submitted).

    profit_take defaults to (tier_fired > 0): a scheduled profit-target take.
    Pass profit_take=False with tier_fired>0 to model a protective floor/trail
    exit (risk-off despite tiers already closed)."""
    if profit_take is None:
        profit_take = tier_fired > 0
    captured = {}

    def fake_submit(**kw):
        captured.update(kw)
        return SimpleNamespace(order_id="o1", position_id="p1", purpose="exit")

    fake = SimpleNamespace(
        _asset_of=lambda sym: "ETH",
        kraken=SimpleNamespace(kraken_pair=lambda sym: "XETHZUSD"),
        orders=SimpleNamespace(open_orders=lambda: [],
                               _ordermin=lambda pair: 0.0,
                               submit=fake_submit),
        _exit_attempts=({"p1": attempts} if attempts else {}),
        max_slip_pct=0.5, esc_widen_mult=2.0,
        esc_max_slip_pct=3.0, esc_market_after=3,
        kraken_books={"ETH": {"bids": list(bids), "asks": list(asks)}},
        marks={"ETH/USD": 100.0},
        maker_first_profit_exits=maker_first_flag,
        _equity=lambda: 1000.0,
        vol=SimpleNamespace(state=lambda a: SimpleNamespace(sigma_bar_pct=0.3)),
    )
    pos = Position(position_id="p1", symbol="ETH/USD", direction=direction,
                   entry_price=100.0, size=1.0, original_size=1.0,
                   opened_at=datetime.now(timezone.utc))
    main_mod.LiquidityBot._submit_exit(fake, pos, close_pct=50.0,
                                       reason="tier", tier_fired=tier_fired,
                                       now=1000.0, profit_take=profit_take)
    return captured or None


def test_profit_tier_long_rests_post_only_at_the_ask():
    # long profit close: SELL, resting at the ask (maker), post_only on
    k = _run_exit("long", tier_fired=1)
    assert k["side"] == "sell"
    assert k["post_only"] is True
    assert k["price"] == 101.0                      # asks[0][0], our own side
    assert k["ordertype"] == "limit"


def test_profit_tier_short_rests_post_only_at_the_bid():
    # short profit close: BUY, resting at the bid (maker), post_only on
    k = _run_exit("short", tier_fired=2)
    assert k["side"] == "buy"
    assert k["post_only"] is True
    assert k["price"] == 99.0                        # bids[0][0], our own side


def test_risk_exit_stays_marketable_first():
    # tier_fired==0 (stop / fault / derisk / unwind): NOT post_only, and
    # priced through the touch (marketable), never resting at our own side
    k = _run_exit("long", tier_fired=0)
    assert k["side"] == "sell"
    assert k["post_only"] is False
    assert k["price"] < 99.0                         # below the bid: marketable
    assert k["price"] != 101.0                       # definitely not the ask


def test_unfilled_profit_exit_escalates_to_marketable():
    # a profit exit that already failed once (attempt 1) must NOT rest maker
    # again - it escalates into the marketable ladder so it cannot be trapped
    k = _run_exit("long", tier_fired=1, attempts=1)
    assert k["post_only"] is False
    assert k["price"] < 99.0                          # widened, marketable
    # slip cap widened by esc_widen_mult on the second attempt
    assert k["meta"]["attempt"] == 2


def test_maker_first_flag_off_keeps_legacy_marketable_exit():
    # config kill-switch: with the flag off, even a profit exit is marketable
    k = _run_exit("long", tier_fired=1, maker_first_flag=False)
    assert k["post_only"] is False
    assert k["price"] < 99.0


def test_profit_exit_degrades_to_marketable_without_book():
    # one-sided/empty book: maker-first needs a live two-sided touch; with no
    # ask it must fall back to marketable rather than price off a missing level
    k = _run_exit("long", tier_fired=1, asks=())
    assert k["post_only"] is False
    assert k["price"] != 101.0


def test_protective_floor_exit_stays_marketable_despite_tiers_fired():
    # THE review finding: a trailing-stop / chandelier / BE floor exit carries
    # tier_fired>0 (tiers already closed) for bookkeeping, but it is risk-off,
    # NOT a scheduled take (profit_take=False). It must stay marketable-first -
    # resting post-only while price reverses would give back the very profit
    # the trail is protecting.
    k = _run_exit("long", tier_fired=2, profit_take=False)
    assert k["post_only"] is False
    assert k["price"] < 99.0                          # marketable through the bid
    assert k["price"] != 101.0                        # never rests at the ask


def test_tier_engine_flags_only_scheduled_takes_as_profit_take():
    # contract behind the gate: the ProfitTierEngine marks is_profit_take True
    # ONLY when price reaches a tier trigger; a protective floor exit does not.
    from datetime import datetime, timedelta, timezone

    from core.state import Position
    from risk.profit_tiers import ProfitTierEngine

    cfg = {"tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
           "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
           "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
           "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25},
           "be_after_tier": 1, "be_buffer_bps": 10, "est_fee_bps": 40}
    eng = ProfitTierEngine(cfg)

    def _pos(tier=0):
        return Position(position_id="p1", symbol="ETH/USD", direction="long",
                        entry_price=100.0, size=1.0, original_size=1.0,
                        opened_at=datetime.now(timezone.utc)
                        - timedelta(minutes=1), tier_closed=tier)

    take = eng.evaluate(_pos(), 101.05)               # crosses tier-1 trigger
    assert take.should_close_partial and take.tier_fired == 1
    assert take.is_profit_take is True

    # tier 1 already closed, price dips through the break-even floor -> a
    # protective 100% close carrying tier_fired>0 but NOT a profit take
    prot = _pos(tier=1)
    eng.evaluate(prot, 101.0)                          # installs BE floor
    floor = eng.evaluate(prot, 100.0)                 # dip through it
    assert floor.should_close_partial and floor.close_pct == 100.0
    assert floor.tier_fired >= 1                       # bookkeeping: tiers closed
    assert floor.is_profit_take is False               # ...but risk-off, not a take
