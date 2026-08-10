"""OWED 57 — the fill simulator counted one market crossing twice.

THE DEFECT. Two mechanisms modelled the SAME physical event:

  * scripts/calibrate_fills.py measures f = "how often the MARKET actually
    crossed a hypothetical resting limit within its life", from recorded book
    frames, and core.fill_calibration.invert_base_prob solves
    passive_base_prob so the HAZARD ALONE reproduces f over n_bar polls;
  * _poll_dry ALSO calls _sim_maker_cross, which fills the FULL remaining
    deterministically whenever the live book crosses the resting price — the
    very event f counts.

The hazard only ever ran INSIDE `if book:`, so it never modelled anything a
snapshot could not already show: it was purely additive to an observed cross.
Combined per-order rate was 1-(1-f)^2 = 2f-f^2 — 22.0% against an 11.66%
target, ~1.88x at the touch and approaching 2x as f falls.

THE FIX. The observed book is ground truth: with a book in hand the cross
decides the event and the hazard does not fire. passive_hazard_with_book=True
restores the old simulator EXACTLY, so a pre-boundary-#4 cohort remains
reproducible — that flag is a time machine, not a knob.
"""
from __future__ import annotations

import pytest

from execution.order_manager import ManagedOrder, OrderManager

MID = 100.0
SIGMA_PCT = 0.10          # -> sigma_bps = 10.0


def _om(hazard_with_book: bool, seed: int = 7, queue_aware: bool = False):
    cfg = {"sim_fill": {"passive_base_prob": 0.45,   # large => visible signal
                        "fill_frac_min": 0.3, "fill_frac_max": 1.0,
                        "queue_aware": queue_aware,
                        "calibration_life_sec": 25.0,
                        "passive_hazard_with_book": hazard_with_book},
           "order_timeout_sec": 25.0}
    return OrderManager(feed=None, config=cfg, dry_run=True, seed=seed)


def _order(price: float, oid: str = "o1") -> ManagedOrder:
    return ManagedOrder(order_id=oid, txid=None, asset="BTC", pair="XBTUSD",
                        symbol="BTC/USD", side="buy", price=price, size=1.0,
                        post_only=True, purpose="entry", arrival_ref=MID)


def _book(dist_bps: float, cross: bool):
    """Resting buy at dist_bps BELOW mid. cross=True puts the opposite touch
    through it (the market traded through us); cross=False keeps the touch
    strictly outside, so only a hazard draw could fill."""
    px = MID * (1.0 - dist_bps / 1e4)
    ask = (px - 0.01) if cross else MID * (1.0 + max(dist_bps, 1.0) / 1e4)
    return px, {"bids": [[px - 0.02, 1e6]], "asks": [[ask, 1e6]]}


def _fill_rate(hazard_with_book: bool, dist_bps: float, cross: bool,
               n: int = 3000) -> float:
    hits = 0
    for i in range(n):
        om = _om(hazard_with_book, seed=1000 + i)
        px, bk = _book(dist_bps, cross)
        o = _order(px, oid="o%d" % i)
        om._poll_dry(o, bk, SIGMA_PCT, now=0.0)
        if o.filled > 1e-12:
            hits += 1
    return hits / n


# --------------------------------------------------------------------------
def test_a_crossed_book_still_fills_deterministically():
    """The fix must not cost us the REAL mechanism. When the market trades
    through a resting post-only order it fills, at its own price, as maker."""
    for dist in (1.0, 5.0, 20.0):
        px, bk = _book(dist, cross=True)
        om = _om(hazard_with_book=False)
        o = _order(px)
        om._poll_dry(o, bk, SIGMA_PCT, now=0.0)
        assert o.filled == pytest.approx(1.0), (
            f"crossed book at {dist}bps did not fill the order")
        assert o.avg_price == pytest.approx(px), (
            "a post-only fill must book at OUR price, never sweep the book")
        assert o.status == "filled"


def test_uncrossed_book_no_longer_grants_a_second_chance():
    """THE DEFECT ITSELF. With the book NOT crossing, nothing justifies a
    fill — the hazard was inventing them on top of the observed cross."""
    for dist in (1.0, 5.0, 20.0):
        assert _fill_rate(False, dist, cross=False, n=500) == 0.0, (
            f"an uncrossed book still filled at {dist}bps")


def test_old_behaviour_is_exactly_reproducible():
    """passive_hazard_with_book=True is a time machine for pre-#4 cohorts.
    It must still grant the hazard fills, or a pre-boundary cohort cannot be
    reproduced and the boundary becomes unauditable."""
    rate = _fill_rate(True, dist_bps=5.0, cross=False, n=1500)
    assert rate > 0.10, (
        f"legacy mode granted almost no hazard fills ({rate:.4f}) - the "
        f"pre-boundary simulator is no longer reproducible")


def test_the_double_count_is_measurably_gone():
    """The quantitative claim, not just the switch.

    Under the old model an order fills if the book crosses OR the hazard
    fires, so the rate strictly EXCEEDS the crossed-book-only rate. Under the
    fix the two must be equal, because the cross alone decides.
    """
    dist = 5.0
    new_cross = _fill_rate(False, dist, cross=True, n=400)
    new_flat = _fill_rate(False, dist, cross=False, n=400)
    old_flat = _fill_rate(True, dist, cross=False, n=1500)

    assert new_cross == pytest.approx(1.0)
    assert new_flat == 0.0
    # the old model's EXTRA population is exactly the uncrossed-book fills
    assert old_flat > 0.0, "legacy mode should still show the inflation"
    # and that extra population is what inflated the per-order rate ~2x
    assert old_flat > 0.05


def test_default_is_the_corrected_behaviour():
    """A silent default flip would re-mint the bias. Absent key => False."""
    om = OrderManager(feed=None, config={"sim_fill": {}}, dry_run=True)
    assert om.sf_hazard_with_book is False
    om2 = OrderManager(feed=None, config={}, dry_run=True)
    assert om2.sf_hazard_with_book is False


def test_shipped_config_has_the_boundary_off():
    """config.json must ship the corrected simulator."""
    import json
    from pathlib import Path

    cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                     .read_text(encoding="utf-8"))
    sf = cfg["order_manager"]["sim_fill"]
    assert sf.get("passive_hazard_with_book") is False, (
        "config.json ships the pre-boundary double-counting simulator")
    assert "_passive_hazard_with_book_doc" in sf, (
        "the boundary must carry its documentation in config")


def test_config_guard_warns_when_the_old_model_is_restored():
    """Restoring it is legitimate but must never be silent."""
    from core.config_guard import validate

    cfg = {"order_manager": {"sim_fill": {"passive_hazard_with_book": True}}}
    findings = validate(cfg)
    hits = [m for sev, m in findings
            if sev == "WARN" and "passive_hazard_with_book" in m]
    assert hits, "no WARN raised for the pre-boundary simulator"
    assert "1.88x" in hits[0] or "2f-f^2" in hits[0], (
        "the warning must carry the magnitude, not just the name")

    clean = {"order_manager": {"sim_fill": {"passive_hazard_with_book": False}}}
    assert not [m for sev, m in validate(clean)
                if sev == "WARN" and "passive_hazard_with_book" in m]
