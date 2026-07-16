"""Small-account ($500-$800) viability.

The percentage-based machinery (fees in bps, stops, caps, Kelly) is
scale-free; what breaks a small account is the FIXED-DOLLAR floors. These
tests pin the shipped config's arithmetic at the target ledger sizes so a
future floor bump can't silently starve a small book:

  * sizer: kelly-cap ticket at $500 must clear min_ticket_usd, else every
    entry is SZ-042 vetoed and the bot idles (the 45h-starvation failure
    mode, small-account edition)
  * config_guard: shipped config at $500/$800 must produce zero findings
    (the untradeable-by-construction check is the guard-side twin)
  * exits are already dust-safe by construction (main._submit_exit: sub-
    ordermin remainders DUST-FLAT locally, dust slices escalate to full
    close) - not re-tested here.

Known, accepted limit (documented, not a bug): Kraken venue minimums make
FLOW (~200 FLOW ordermin) untradeable below roughly $700 equity at 10%
max position; OM-012 rejects those orders gracefully.
"""
import json
from pathlib import Path

from core.config_guard import validate
from risk.position_sizer import PositionSizer

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _shipped_sizer():
    return PositionSizer(_CFG["position_sizer"],
                         profit_cfg=_CFG.get("profit_taking", {}),
                         risk_cfg=_CFG.get("risk", {}),
                         pretrade_cfg=_CFG.get("pretrade", {}),
                         capital_cfg=_CFG.get("capital_management", {}))


def test_kelly_ticket_clears_floor_at_500():
    s = _shipped_sizer()
    for equity in (500.0, 650.0, 800.0):
        kelly_ticket = equity * s.kelly_cap
        assert kelly_ticket > s.min_ticket_usd, (
            f"at ${equity:.0f} the kelly-cap ticket ${kelly_ticket:.0f} is "
            f"under the ${s.min_ticket_usd:.0f} floor - entries starve")
    # the floor itself must stay above the majors' venue minimums
    # (ETH 0.002 / BTC 0.00005 base units are single-digit USD)
    assert s.min_ticket_usd >= 10.0


def test_pretrade_floor_matches_sizer_floor_scale():
    # two independent dollar floors gate one order; if pretrade's is above
    # the sizer's, orders the sizer approves die at the EV gate
    assert float(_CFG["pretrade"]["min_order_usd"]) <= \
        float(_CFG["position_sizer"]["min_ticket_usd"])


def test_hedge_floor_usable_at_small_equity():
    # min_hedge_usd 50 at a $500 book meant no hedge under 10% of equity
    # could ever fire; floor must stay within ~3% of the small-account low
    assert float(_CFG["hedging"]["min_hedge_usd"]) <= 500 * 0.03


def test_guard_clean_at_small_capital():
    for cap in (500, 800):
        cfg = json.loads(json.dumps(_CFG))          # deep copy
        cfg["capital_management"]["starting_capital_usd"] = cap
        fatals = [m for s, m in validate(cfg) if s == "FATAL"]
        assert not fatals, f"at ${cap}: {fatals}"   # WARNs are advisory
