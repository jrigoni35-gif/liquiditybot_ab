"""MP-7 queue-position model for DRY-RUN passive fills.

State-independent Poisson fill models over-credit passive execution
(Huang-Lehalle-Rosenbaum queue-reactive; Moallemi-Yuan queue value):
a limit resting behind a wall shouldn't fill as readily as one at the
touch. Contract under test:
  - depth_ahead sums resting size at-or-better than our price;
  - an order INSIDE the spread (improves the touch) is queue-eligible at
    once (nothing ahead);
  - an order behind a persistent wall never becomes eligible (and thus
    never fills passively) until the wall clears;
  - the ratchet advances only downward (new joiners don't push us back);
  - queue_aware=False reproduces the old flat-probability behavior
    exactly (a deep-book order can fill);
  - the field round-trips through persistence;
  - config_guard rejects a zero base prob / inverted frac window.
"""
import pytest

from core.config_guard import validate
from core.persistence import order_from_dict, order_to_dict
from execution.order_manager import ManagedOrder, OrderManager


def _om(**sf):
    # MP-7's queue gate guards the PASSIVE HAZARD and nothing else - queue_ok
    # is consumed only by that branch. Since owed 57 / execution-era boundary
    # #4 the hazard does not fire while a book is present, so these tests opt
    # into the legacy simulator explicitly: their SUBJECT is the gate, and the
    # gate needs the path it gates to exist. See
    # test_queue_gate_is_inert_on_the_default_path below, which pins the
    # consequence so it stays visible rather than implied.
    sf.setdefault("passive_hazard_with_book", True)
    cfg = {"taker_fee_bps": 40.0, "maker_fee_bps": 25.0,
           "order_timeout_sec": 1e9, "sim_fill": sf}
    return OrderManager(feed=None, config=cfg, dry_run=True, seed=1)


def _buy(price=100.0, size=1.0):
    return ManagedOrder(order_id="q", txid=None, asset="ETH", pair="ETHUSD",
                        symbol="ETH/USD", side="buy", price=price, size=size,
                        ordertype="limit", post_only=True)


# ---------------------------------------------------------------- depth_ahead
def test_depth_ahead_counts_at_or_better_only():
    o = _buy(price=100.0)
    book = {"bids": [[100.5, 2.0], [100.0, 3.0], [99.5, 5.0]],
            "asks": [[100.6, 1.0]]}
    # ahead = bids priced >= 100.0 -> 2.0 + 3.0 (99.5 is worse, excluded)
    assert OrderManager._depth_ahead(o, book) == pytest.approx(5.0)


def test_order_inside_spread_has_no_queue_ahead():
    o = _buy(price=100.4)          # better than the 100.0 best bid
    book = {"bids": [[100.0, 3.0]], "asks": [[100.6, 1.0]]}
    assert OrderManager._depth_ahead(o, book) == 0.0


# ---------------------------------------------------------------- eligibility
def test_touch_improving_order_is_eligible_immediately():
    om = _om(queue_aware=True)
    o = _buy(price=100.4, size=1.0)
    book = {"bids": [[100.0, 3.0]], "asks": [[100.6, 1.0]]}
    assert om._queue_eligible(o, book, 0.05) is True
    assert o.queue_ahead == 0.0


def test_order_behind_persistent_wall_never_fills():
    om = _om(queue_aware=True, passive_base_prob=1.0)   # would always fill
    o = _buy(price=99.0, size=0.1)
    # a big wall rests at/above our price and never clears
    wall = {"bids": [[100.0, 50.0], [99.0, 50.0]], "asks": [[100.2, 1.0]]}
    events = []
    for t in range(20):
        events += om._poll_dry(o, wall, 0.05, float(t))
    assert o.filled == 0.0                      # queue never cleared
    assert not any(e.fill_size > 0 for e in events)


def test_partial_fill_does_not_strand_a_front_of_queue_order():
    # review finding (HIGH): the eligibility yardstick must be order.SIZE,
    # not order.remaining. With `remaining`, the first partial fill shrank
    # the RHS below queue_ahead and flipped an at-the-front order back to
    # ineligible, stranding it as a never-completing partial. Here: a thin
    # wall (0.4 < size 1.0) makes the order eligible; once it starts
    # filling it must KEEP filling to completion, never re-block.
    # deterministic 30%-of-remaining fills make the stall visible: queue_ahead
    # is 0.4, so the OLD `remaining` yardstick re-blocks once remaining < 0.4
    # (i.e. filled > 0.6), capping the order near ~0.66; the `size` yardstick
    # keeps it eligible all the way to ~full.
    om = _om(queue_aware=True, passive_base_prob=1.0, queue_drain_frac=0.0,
             queue_tol_frac=1.0, fill_frac_min=0.3, fill_frac_max=0.3)
    o = _buy(price=100.0, size=1.0)
    book = {"bids": [[100.0, 0.4]], "asks": [[100.2, 5.0]]}   # static, no turnover
    for t in range(30):
        om._poll_dry(o, book, 5.0, float(t))
    assert o.filled > 0.9                        # not stranded past filled≈0.66
    assert o.remaining < 0.1


def test_queue_ratchets_down_then_fills_when_wall_clears():
    om = _om(queue_aware=True, passive_base_prob=1.0, queue_tol_frac=1.0)
    o = _buy(price=100.0, size=1.0)
    thick = {"bids": [[100.0, 10.0]], "asks": [[100.2, 1.0]]}
    om._poll_dry(o, thick, 5.0, 0.0)            # wide sigma: exp term ~1
    assert o.queue_ahead == pytest.approx(10.0) and o.filled == 0.0
    # the wall thins below our own size -> the observed shrink advances us to
    # the front -> eligible; base_prob 1.0 + wide sigma fills within a few polls
    thin = {"bids": [[100.0, 0.5]], "asks": [[100.2, 1.0]]}
    for t in range(1, 12):
        om._poll_dry(o, thin, 5.0, float(t))
    assert o.queue_ahead < 1.0                   # cleared below the tol
    assert o.filled > 0.0


def test_ratchet_is_monotone_down_only():
    # drain_frac=0 isolates the observed-shrink ratchet from vol turnover
    om = _om(queue_aware=True, passive_base_prob=0.0, queue_drain_frac=0.0)
    o = _buy(price=100.0, size=1.0)
    om._poll_dry(o, {"bids": [[100.0, 4.0]], "asks": [[100.2, 1.0]]}, 0.05, 0.0)
    assert o.queue_ahead == pytest.approx(4.0)
    om._poll_dry(o, {"bids": [[100.0, 2.0]], "asks": [[100.2, 1.0]]}, 0.05, 1.0)
    assert o.queue_ahead == pytest.approx(2.0)          # ratcheted down
    om._poll_dry(o, {"bids": [[100.0, 9.0]], "asks": [[100.2, 1.0]]}, 0.05, 2.0)
    assert o.queue_ahead == pytest.approx(2.0)          # joiners don't push back


def test_vol_turnover_drains_a_static_book():
    # a book whose aggregate snapshot never changes is still continuously
    # traded: the vol-driven turnover must drain the queue so fills are not
    # starved on static replays (the smoke-test regression that surfaced it)
    om = _om(queue_aware=True, passive_base_prob=0.0, queue_drain_frac=0.5)
    o = _buy(price=100.0, size=1.0)
    static = {"bids": [[100.0, 8.0]], "asks": [[100.2, 1.0]]}
    om._poll_dry(o, static, 0.30, 0.0)          # init -> 8.0
    q0 = o.queue_ahead
    for t in range(1, 15):
        om._poll_dry(o, static, 0.30, float(t))  # observed shrink is 0 here
    assert o.queue_ahead < q0                     # turnover still drained it
    assert o.queue_ahead <= om.sf_queue_tol_frac * o.remaining  # to eligible


def test_queue_aware_off_reproduces_old_behavior():
    # deep book behind a wall: with the gate OFF the flat prob can still fill
    om = _om(queue_aware=False, passive_base_prob=1.0)
    o = _buy(price=100.0, size=0.1)
    book = {"bids": [[100.0, 99.0]], "asks": [[100.05, 1.0]]}
    om._poll_dry(o, book, 5.0, 0.0)             # wide sigma -> exp term ~1
    assert o.filled > 0.0                       # filled despite the wall
    assert o.queue_ahead == -1.0                # gate never touched the field


# ---------------------------------------------------------------- persistence
def test_queue_ahead_round_trips():
    o = _buy()
    o.queue_ahead = 7.5
    back = order_from_dict(order_to_dict(o))
    assert back.queue_ahead == pytest.approx(7.5)
    # pre-upgrade snapshot without the key defaults to -1.0
    d = order_to_dict(o)
    del d["queue_ahead"]
    assert order_from_dict(d).queue_ahead == -1.0


# ---------------------------------------------------------------- config_guard
def test_guard_rejects_incoherent_sim_fill():
    def fatals(cfg):
        return [m for s, m in validate(cfg) if s == "FATAL"]
    assert any("passive_base_prob" in m for m in fatals(
        {"order_manager": {"sim_fill": {"passive_base_prob": 0.0}}}))
    assert any("fill_frac" in m for m in fatals(
        {"order_manager": {"sim_fill": {"fill_frac_min": 0.8,
                                        "fill_frac_max": 0.3}}}))
    assert any("queue_tol_frac" in m for m in fatals(
        {"order_manager": {"sim_fill": {"queue_tol_frac": -1.0}}}))
    # defaults coherent: the RANGE checks stay silent on an empty block. Since
    # 2026-09-08 the ABSENCE check does not - passive_base_prob and queue_aware
    # are era-booked keys whose code defaults (0.45 / False) are the pre-XV-021
    # flattering simulator (tests/test_config_guard_absent_keys.py) - so that
    # one FATAL is filtered out here and pinned positively right after.
    empty = fatals({"order_manager": {"sim_fill": {}}})
    assert not any("sim_fill" in m and "absent from config" not in m
                   for m in empty)
    assert any("order_manager.sim_fill.passive_base_prob" in m
               and "order_manager.sim_fill.queue_aware" in m for m in empty)


# ------------------------------------------- owed 57 / era boundary #4
def test_queue_gate_is_inert_on_the_default_path():
    """THE CONSEQUENCE OF THE DOUBLE-COUNT FIX, pinned so it stays visible.

    `queue_ok` is consumed ONLY by the passive-hazard branch. Since the
    hazard no longer fires while a book is present, MP-7 queue gating has no
    effect on the shipped configuration: `_sim_maker_cross` fills the FULL
    remaining with no depth constraint, exactly as it always did.

    This is NOT an endorsement. It is a dead control, of the same family this
    codebase keeps finding, and it is registered as owed 61 - the surviving
    maker-cross path arguably SHOULD carry the queue constraint (a trade-
    through fills the queue in order, so we fill only after the depth ahead
    of us clears). That is a second, uncalibrated change to the fill model
    and was deliberately not compounded into the same commit.

    The test exists so nobody reads `queue_aware: true` in config.json and
    believes it is protecting them.
    """
    cfg = {"order_timeout_sec": 1e9,
           "sim_fill": {"queue_aware": True, "passive_base_prob": 1.0,
                        "queue_tol_frac": 1.0, "queue_drain_frac": 0.0}}
    om = OrderManager(feed=None, config=cfg, dry_run=True, seed=1)
    assert om.sf_queue_aware is True          # gate is ON in config...
    assert om.sf_hazard_with_book is False    # ...but its only consumer is off

    # an enormous wall ahead of us must NOT prevent a crossed-book fill,
    # because the maker-cross path never consults the queue at all
    o = _buy(price=100.0, size=1.0)
    crossed = {"bids": [[100.0, 1e9]], "asks": [[99.99, 1.0]]}
    om._poll_dry(o, crossed, 0.05, 0.0)
    assert o.filled == pytest.approx(1.0), (
        "maker-cross ignored the queue - if this ever fails, the gate was "
        "wired onto the cross path and owed 61 is closed; update this test")
