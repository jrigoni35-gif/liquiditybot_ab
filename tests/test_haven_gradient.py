"""The tangible-value gradient (regime/haven.py): gold > BTC > ETH > alts.

Pins the MECHANISM, not a market opinion: fear travels down the ladder
(capital abandons the least tangible claim first), greed travels up it,
and the adjacent-rung spreads are what make that visible. Report-only -
these tests also pin that nothing here sizes, gates or directs a trade.
"""
import pytest

from regime import haven


def _series(pct_change: float, n: int = 288, base: float = 100.0):
    """A close series that ends `pct_change` percent from where it began.

    n defaults to the evaluate() lookback so the whole series IS the
    window - a longer ramp would be truncated to its tail and the realized
    change would come out smaller than the one asked for.
    """
    end = base * (1.0 + pct_change / 100.0)
    step = (end - base) / (n - 1)
    return [base + step * i for i in range(n)]


# --- the ladder itself -------------------------------------------------------
def test_classify_puts_every_asset_on_a_rung():
    assert haven.classify_asset("PAXG") == "PAXG"
    assert haven.classify_asset("XAUT") == "PAXG"      # the other gold token
    assert haven.classify_asset("XBT") == "BTC"        # Kraken's ticker
    assert haven.classify_asset("btc") == "BTC"        # case-insensitive
    assert haven.classify_asset("ETH") == "ETH"
    assert haven.classify_asset("SUI") == "ALT"
    assert haven.classify_asset("") == "ALT"           # unknown -> venture bet


def test_ladder_order_is_the_tangibility_claim():
    # the ORDER is the whole thesis: a bar in a vault, then a network with
    # a security budget, then a platform contingent on usage, then bets
    assert haven.RUNGS == ("PAXG", "BTC", "ETH", "ALT")


# --- the two regimes the ladder is built to tell apart -----------------------
def test_flight_to_quality_when_capital_moves_toward_the_tangible():
    """Gold flat, BTC down a little, ETH down more, alts routed: fear
    travelling DOWN the ladder. Positive gradient."""
    closes = {"PAXG": _series(+0.5), "BTC": _series(-2.0),
              "ETH": _series(-4.0), "SUI": _series(-8.0),
              "ARB": _series(-7.0)}
    st = haven.evaluate(closes)
    assert st.state == haven.FLIGHT
    assert st.gradient > 0
    assert st.rungs_seen == 4


def test_risk_on_when_capital_reaches_for_beta():
    """The same ladder in reverse - alts outrunning everything."""
    closes = {"PAXG": _series(+0.2), "BTC": _series(+2.0),
              "ETH": _series(+5.0), "SUI": _series(+11.0)}
    st = haven.evaluate(closes)
    assert st.state == haven.RISK_ON
    assert st.gradient < 0


def test_neutral_inside_the_band():
    closes = {"PAXG": _series(+0.1), "BTC": _series(0.0),
              "ETH": _series(-0.1), "SUI": _series(-0.2)}
    st = haven.evaluate(closes)
    assert st.state == haven.NEUTRAL
    assert abs(st.gradient) < haven.DEFAULT_BAND_PCT


# --- honesty about insufficient evidence ------------------------------------
def test_unknown_rather_than_a_guessed_number():
    """One rung cannot produce a spread. UNKNOWN is a STATE, never a zero
    dressed up as a reading (the context engine's rule, kept)."""
    st = haven.evaluate({"BTC": _series(-3.0)})
    assert st.state == haven.UNKNOWN
    assert st.gradient is None
    assert "insufficient rungs" in st.detail


def test_non_adjacent_rungs_alone_are_not_enough():
    # PAXG and ETH are not adjacent; without BTC there is no adjacent pair
    st = haven.evaluate({"PAXG": _series(+1.0), "ETH": _series(-5.0)})
    assert st.state == haven.UNKNOWN


def test_degenerate_series_are_skipped_not_faulted():
    closes = {"PAXG": [100.0], "BTC": _series(-2.0), "ETH": _series(-5.0),
              "SUI": [float("nan")] * 288, "ARB": [0.0] * 288}
    st = haven.evaluate(closes)
    assert st.rungs_seen == 2                 # BTC + ETH only
    assert st.state in (haven.FLIGHT, haven.NEUTRAL, haven.RISK_ON)


# --- the ALT rung is a rung, not a coin -------------------------------------
def test_alt_rung_averages_so_one_coin_cannot_impersonate_a_regime():
    """One alt ripping is a coin story; the RUNG moving is a regime. The
    average is what keeps a single microcap from writing the headline."""
    quiet = {"BTC": _series(0.0), "ETH": _series(0.0),
             "SUI": _series(0.0), "ARB": _series(0.0), "MINA": _series(0.0)}
    loud = dict(quiet, SUI=_series(+30.0))
    assert haven.evaluate(quiet).state == haven.NEUTRAL
    st = haven.evaluate(loud)
    # 30% on one of three alts moves the rung by ~10%, not by 30%
    assert st.returns["ALT"] == pytest.approx(10.0, abs=0.5)


def test_gradient_is_the_mean_of_adjacent_spreads():
    closes = {"PAXG": _series(+2.0), "BTC": _series(+1.0),
              "ETH": _series(0.0), "SUI": _series(-1.0)}
    st = haven.evaluate(closes)
    assert set(st.spreads) == {"PAXG-BTC", "BTC-ETH", "ETH-ALT"}
    for v in st.spreads.values():
        assert v == pytest.approx(1.0, abs=0.01)
    assert st.gradient == pytest.approx(1.0, abs=0.01)


# --- report-only contract ----------------------------------------------------
def test_module_cannot_touch_a_trade():
    """Report-first, in the house style: the skimmer, conviction and the
    context engine all shipped as instruments and earned their wiring with
    evidence. Nothing here may size, gate or veto.

    Asserted over the PARSED module, not its text: a prose scan matches the
    docstring that promises the very restraint it is checking for, which
    would make this test fail on an honest module and pass on a silent
    one. Imports and call targets are the real surface."""
    import ast
    tree = ast.parse(open(haven.__file__, encoding="utf-8").read())
    forbidden_mods = ("execution", "risk", "main", "order_manager",
                      "position_sizer")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] not in forbidden_mods, \
                    f"haven.py imports the trading path: {a.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert root not in forbidden_mods, \
                f"haven.py imports the trading path: {node.module}"
        elif isinstance(node, ast.Call):
            fn = node.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else getattr(fn, "id", ""))
            assert name not in ("submit", "cancel_order", "size", "veto"), \
                f"haven.py calls a trading action: {name}()"


def test_state_serializes_for_telemetry():
    st = haven.evaluate({"PAXG": _series(+1.0), "BTC": _series(-1.0),
                         "ETH": _series(-3.0), "SUI": _series(-6.0)})
    d = st.to_dict()
    assert d["state"] == haven.FLIGHT
    assert isinstance(d["gradient"], float)
    assert set(d["returns"]) <= set(haven.RUNGS)
    assert d["rungs_seen"] == 4
