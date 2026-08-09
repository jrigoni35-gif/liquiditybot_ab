"""The sizer must actually SEE the open book (2026-08-09 incident).

THE DEFECT. PositionSizer's three heat/inventory readers each did
`getattr(state, "positions", {}).values()`. PortfolioState keeps the book
in `_positions` and exposes `open_positions()`; it has no `positions`
attribute at all, so the getattr DEFAULT was taken unconditionally and
every reader saw an empty book forever. Measured live against a real book
of 5 positions / 11.8% gross heat, all three read 0.0.

Three risk controls were dead, every one of them failing PERMISSIVE:
  * the portfolio-heat veto (RiskProtocolStack, max_portfolio_heat_frac
    0.35, RP_HEAT_FULL) - unreachable, because heat was always 0;
  * the signed-inventory reservation skew (SZ-061) - never applied;
  * the inventory-aggression taper - pinned at light_boost 1.10, a
    permanent 10% size-UP as if the book were empty, where it should
    fall toward heavy_cut 0.65 as the book fills.

It hid because BOTH failure paths produce the same benign number: the
missing attribute yields {} -> 0.0, and the surrounding `except` yields
0.0 as well. A dead risk reading is indistinguishable from a genuinely
flat book - "zero is not a reading", on the sizing path.
"""
from datetime import datetime, timedelta, timezone

from core.state import PortfolioState, Position
from risk.position_sizer import PositionSizer


def _state(*specs) -> PortfolioState:
    """specs: (direction, entry, size, symbol, age_hours)"""
    p = PortfolioState(starting_capital=1000.0)
    for i, (direction, entry, size, symbol, age_h) in enumerate(specs):
        p.add_position(Position(
            position_id=f"p{i}", symbol=symbol, direction=direction,
            entry_price=entry, size=size, original_size=size,
            opened_at=datetime.now(timezone.utc) - timedelta(hours=age_h)))
    return p


def _sizer() -> PositionSizer:
    """Constructed against the SHIPPED config so the taper is measured at
    the real light_boost/heavy_cut/full_book_heat_frac, not at defaults
    that might diverge from what the bot actually sizes with."""
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                     .read_text(encoding="utf-8"))
    return PositionSizer(cfg["position_sizer"], cfg["profit_taking"],
                         cfg["risk"], pretrade_cfg=cfg["pretrade"],
                         capital_cfg=cfg["capital_management"])


# ------------------------------------------------------------ gross heat
def test_open_heat_sees_a_real_book():
    """The headline regression: a book with real notional must not read
    as an empty one."""
    st = _state(("long", 100.0, 1.0, "ETH/USD", 1.0))     # $100 on $1000
    heat = PositionSizer._open_heat_frac(st, {"ETH/USD": 100.0}, 1000.0)
    assert heat > 0.0, "an open book must never read as zero heat"
    assert abs(heat - 0.10) < 1e-9


def test_open_heat_is_gross_so_a_hedge_adds():
    """Gross exposure counts both sides - a hedge is real risk, not a
    cancellation, for the heat cap's purposes."""
    st = _state(("long", 100.0, 1.0, "ETH/USD", 1.0),
                ("short", 100.0, 1.0, "BTC/USD", 1.0))
    heat = PositionSizer._open_heat_frac(
        st, {"ETH/USD": 100.0, "BTC/USD": 100.0}, 1000.0)
    assert abs(heat - 0.20) < 1e-9


def test_signed_heat_is_sign_aware_and_nonzero():
    st = _state(("long", 100.0, 1.0, "ETH/USD", 1.0),
                ("short", 100.0, 0.4, "BTC/USD", 1.0))
    net = PositionSizer._signed_heat_frac(
        st, {"ETH/USD": 100.0, "BTC/USD": 100.0}, 1000.0)
    assert abs(net - 0.06) < 1e-9, "long 100 - short 40 = +60 on 1000"


def test_empty_book_still_reads_zero():
    """The honest zero must survive: a genuinely flat book is 0.0."""
    assert PositionSizer._open_heat_frac(_state(), {}, 1000.0) == 0.0
    assert PositionSizer._signed_heat_frac(_state(), {}, 1000.0) == 0.0


# -------------------------------------------------- inventory aggression
def test_aggression_tapers_as_the_book_fills():
    """The multiplier must MOVE. Pinned at light_boost it was sizing UP
    exactly when risk was already on."""
    s = _sizer()
    empty = s._inventory_aggression(_state(), {}, 1000.0, now=0.0)[0]
    # heat at/above full_book_heat_frac -> the heavy end
    full_state = _state(("long", 100.0, 4.0, "ETH/USD", 100.0))
    full = s._inventory_aggression(
        full_state, {"ETH/USD": 100.0}, 1000.0, now=0.0)[0]
    assert empty > full, (
        f"aggression must FALL as the book fills, got empty={empty} "
        f"full={full} - a constant here is the pinned-multiplier bug")
    assert abs(empty - s.ia_light_boost) < 1e-9
    assert abs(full - s.ia_heavy_cut) < 1e-9


def test_aggression_u_long_tracks_measured_heat():
    s = _sizer()
    st = _state(("long", 100.0, 1.0, "ETH/USD", 100.0))    # 10% heat
    _mult, u_long, _u_short = s._inventory_aggression(
        st, {"ETH/USD": 100.0}, 1000.0, now=0.0)
    assert u_long > 0.0, "u_long must reflect a non-empty book"
    assert abs(u_long - (0.10 / s.ia_full_heat)) < 1e-9


def test_recent_entry_clustering_is_counted():
    """u_short counts positions opened inside the window - with the empty
    book it was always 0, so a burst of entries never throttled size."""
    s = _sizer()
    fresh = _state(*[("long", 100.0, 0.01, f"A{i}/USD", 0.0)
                     for i in range(3)])
    _m, _ul, u_short = s._inventory_aggression(fresh, {}, 1_000_000.0,
                                               now=datetime.now(
                                                   timezone.utc).timestamp())
    assert u_short > 0.0, "recent entries must register"


# ------------------------------------------------------------- fail-safe
def test_a_state_without_the_accessor_degrades_to_zero_not_a_crash():
    """Duck-typed doubles that expose neither accessor must still not
    raise on the sizing path (the pre-existing contract)."""
    class Bare:
        pass
    assert PositionSizer._open_heat_frac(Bare(), {}, 1000.0) == 0.0
    assert PositionSizer._signed_heat_frac(Bare(), {}, 1000.0) == 0.0


def test_no_site_reads_the_nonexistent_positions_attribute():
    """AST pin: no getattr(state, "positions", ...) may return to the
    sizer. Parsed rather than grepped on purpose - the incident is
    DESCRIBED in this module's own prose, and a substring check would
    match the documentation that exists to prevent it (it did, first
    run). Pinned because the bug is invisible at runtime: the missing
    attribute and the surrounding except produce the same benign 0.0."""
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "risk"
           / "position_sizer.py").read_text(encoding="utf-8")
    bad = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "positions"):
            bad.append(node.lineno)
    assert not bad, (
        f"position_sizer.py:{bad} reads a `positions` attribute "
        f"PortfolioState does not have - that silently yields an empty "
        f"book and kills the heat veto, the signed skew and the taper")
    assert not hasattr(PortfolioState(starting_capital=1.0), "positions"), (
        "if PortfolioState ever grows a real `positions` attribute this "
        "pin should be revisited deliberately, not deleted")
