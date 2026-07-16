"""tests/test_exploration_entry.py — dry-run exploration can TAKE a net-thin
signal to acquire a real-fill label.

The bot was learning only from shadow candidates: every entry the model liked
was net-thin (edge ~60bps < ~70bps cost) so the pre-trade PROFIT gate vetoed it
(PT-041 / PT-040) and no live-fill labels ever accrued. Two fixes:
  * pre-trade `exploring` bypasses the two PROFIT gates (edge/cost, EV) but
    keeps EVERY safety gate (input, stale, spread, spoofy, participation,
    min-order) — and records the bypass (PT-050).
  * the sizer floors an exploration ticket a margin above pretrade.min_order_usd
    so it still clears PT-031 after the quote-vs-mark gap (the sizer floors at
    the mark; the gate recomputes notional at the lower maker quote).
"""
import json
from pathlib import Path

from execution.pretrade import PreTradeContext, PreTradeGate
from risk.position_sizer import PositionSizer

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _gate():
    return PreTradeGate(_CFG["pretrade"])


def _ctx(spread_bps=8.0, staleness_ms=0.0, liq="normal"):
    book = {"bids": [[100.0, 5000.0]], "asks": [[100.1, 5000.0]]}
    return PreTradeContext(kraken_book=book, sigma_daily_pct=3.0, adv_usd=1e9,
                           liq_label=liq, spread_bps=spread_bps,
                           staleness_ms=staleness_ms)


def _codes(dec):
    return [str(r).split(":")[0] for r in dec.reasons]


# --- the profit gate blocks a thin signal; exploration takes it -------------
def test_thin_edge_vetoed_normally_but_taken_when_exploring():
    g = _gate()
    # edge 30bps is far below 1.3x the cost stack -> PT-041 normally
    base = g.evaluate("buy", 1.0, 100.0, exp_alpha_bps=30.0, fv_edge_bps=0.0,
                      ctx=_ctx())
    assert not base.approved and "PT-041" in _codes(base)

    exp = g.evaluate("buy", 1.0, 100.0, exp_alpha_bps=30.0, fv_edge_bps=0.0,
                     ctx=_ctx(), exploring=True)
    assert exp.approved, "exploration must take a net-thin signal for the label"
    assert "PT-050" in _codes(exp)            # the bypass is recorded/auditable


def test_exploration_still_respects_every_safety_gate():
    g = _gate()
    # stale data -> PT-020 even when exploring
    stale = g.evaluate("buy", 1.0, 100.0, 30.0, 0.0,
                       _ctx(staleness_ms=99_999.0), exploring=True)
    assert not stale.approved and "PT-020" in _codes(stale)
    # wide spread -> PT-021 even when exploring
    wide = g.evaluate("buy", 1.0, 100.0, 30.0, 0.0,
                      _ctx(spread_bps=999.0), exploring=True)
    assert not wide.approved and "PT-021" in _codes(wide)
    # below min order -> PT-031 even when exploring (a venue reality)
    tiny = g.evaluate("buy", 0.0001, 100.0, 30.0, 0.0, _ctx(), exploring=True)
    assert not tiny.approved and "PT-031" in _codes(tiny)


# --- the sizer floor clears the pretrade min-order after the quote gap -------
def _sizer():
    return PositionSizer(_CFG["position_sizer"],
                         profit_cfg=_CFG.get("profit_taking", {}),
                         risk_cfg=_CFG.get("risk", {}),
                         pretrade_cfg=_CFG.get("pretrade", {}),
                         capital_cfg=_CFG.get("capital_management", {}))


def test_exploration_floor_clears_min_order_with_margin():
    s = _sizer()
    min_order = float(_CFG["pretrade"]["min_order_usd"])
    floor = max(s.min_ticket_usd, s.min_order_usd * s.explore_floor_mult)
    # the floored exploration ticket must exceed min_order with enough margin
    # to survive the maker-quote gap (a few bps below the mark on a buy)
    assert floor > min_order
    assert floor >= min_order * 1.1              # comfortable margin
