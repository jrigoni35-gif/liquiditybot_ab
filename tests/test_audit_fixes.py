"""
tests/test_audit_fixes.py — regressions for the codebase abnormality audit.

Collected here as each verified finding is fixed:
- protocol stack: a soft-cap error must NOT bypass the budget/heat HARD vetoes,
  and an error computing a hard veto fails CLOSED (no new risk), never open.
- hedge engine: the unwind decision reads SIGNAL-only delta, so a working hedge
  is not unwound the instant it pulls total net into the band (open/unwind
  thrash when beta >= 1).
"""
from datetime import datetime, timezone

import json
from pathlib import Path

from core.state import PortfolioState, Position
from execution.hedging import HedgeEngine
from risk.protocols import RiskProtocolStack

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


# --- config_guard now covers the Kraken v2 ws (was unguarded) ---------------
def test_config_guard_fatals_incoherent_book_age():
    """RENAMED + REWRITTEN 2026-08-09. This test previously asserted the
    guard FATALs "a book-age that reads stale books as fresh" - a premise
    commit 36fcfd6e (owed 42a) FALSIFIED: books now carry recv_ts and
    book_ts is DATA time, so an old book no longer reads fresh, it reports
    its true age. The test name and message survived the change and would
    have kept pinning the dead premise into the suite.

    The relation that binds NOW: the ws cache serves any book younger than
    kraken_max_book_age_sec, and the pre-trade gate vetoes any book older
    than pretrade.max_data_staleness_ms. Overlap = books served by the feed
    and then vetoed by the decision path (PT-020), preempting a REST read
    that would have been fresh."""
    import core.config_guard as g
    # "clean" = no FATAL findings (WARN findings are advisory and never block
    # startup); the shipped config carries advisory WARNs by design.
    assert not [m for s, m in g.validate(_CFG) if s == "FATAL"], \
        "shipped config must have no FATAL findings"

    bad = json.loads(json.dumps(_CFG))
    bad["websockets"]["kraken_max_book_age_sec"] = 300.0
    assert any("kraken_max_book_age" in str(x) for x in g.validate(bad)), \
        "guard must FATAL an absurd book age"

    # the incoherence itself: served-then-vetoed band
    band = json.loads(json.dumps(_CFG))
    band["websockets"]["kraken_max_book_age_sec"] = 5.0
    band["pretrade"]["max_data_staleness_ms"] = 4000
    fatals = [m for s, m in g.validate(band) if s == "FATAL"]
    assert any("max_data_staleness_ms" in m and "kraken_max_book_age" in m
               for m in fatals), (
        "a ws book age at/above the pre-trade staleness ceiling is a dead "
        "band - the feed serves what the gate refuses")

    # equality is NOT safe: at exactly the ceiling the gate's own > test
    # still admits the boundary book while any read delay pushes it over
    eq = json.loads(json.dumps(_CFG))
    eq["websockets"]["kraken_max_book_age_sec"] = 4.0
    eq["pretrade"]["max_data_staleness_ms"] = 4000
    assert [m for s, m in g.validate(eq) if s == "FATAL"], \
        "equal bounds leave no headroom for the cycle read delay"

    bad2 = json.loads(json.dumps(_CFG))
    bad2["websockets"]["kraken_depth"] = 7
    assert any("kraken_depth" in str(x) for x in g.validate(bad2))

MARKS = {"ETH/USD": 2000.0, "BTC/USD": 60000.0}
SYMBOLS = {"ETH": "ETH/USD", "BTC": "BTC/USD"}


def _pos(pid, symbol, direction, entry, size, is_hedge=False):
    p = Position(pid, symbol, direction, entry, size, size,
                 datetime.now(timezone.utc))
    p.is_hedge = is_hedge
    return p


# --- protocol stack: hard vetoes survive soft-cap errors --------------------
def _stack():
    return RiskProtocolStack({"enabled": True,
                              "vol_target": {"enabled": True},
                              "cvar": {"enabled": False},
                              "gap": {"enabled": False},
                              "budget": {"enabled": False},
                              "heat": {"enabled": True,
                                       "max_portfolio_heat_frac": 0.35}})


def test_soft_cap_error_does_not_bypass_heat_veto(monkeypatch):
    st = _stack()
    monkeypatch.setattr("risk.protocols.vol_target_mult",
                        lambda *a, **k: 1 / 0)          # soft cap blows up
    mult, _ = st.entry_multiplier(0.1, 10_000.0, 50.0, "ETH",
                                  open_heat_frac=0.40)  # over the 0.35 cap
    assert mult == 0.0, "heat-full hard veto must survive a soft-cap error " \
                        "(old single-try returned 1.0 and sized up a halted book)"


def test_hard_veto_error_fails_closed(monkeypatch):
    st = _stack()
    monkeypatch.setattr("risk.protocols.heat_headroom_frac",
                        lambda *a, **k: 1 / 0)          # hard-veto computation errors
    mult, _ = st.entry_multiplier(0.1, 10_000.0, 50.0, "ETH", open_heat_frac=0.1)
    assert mult == 0.0, "an error computing a hard veto must fail CLOSED"


def test_healthy_stack_still_sizes_normally():
    # sanity: with no error and headroom, the stack does not veto
    st = _stack()
    mult, _ = st.entry_multiplier(0.1, 10_000.0, 45.0, "ETH", open_heat_frac=0.05)
    assert mult > 0.0


# --- hedge: unwind reads signal-only delta ----------------------------------
def _hedger():
    return HedgeEngine({"enabled": True, "max_net_delta_pct_of_equity": 15,
                        "rebalance_band_pct": 5, "min_hedge_usd": 50}, SYMBOLS)


def _corr():
    from regime.correlation import CorrState
    return CorrState(corr_fast={("BTC", "ETH"): 0.85},
                     betas={("ETH", "BTC"): 1.2, ("BTC", "ETH"): 0.6})


# --- MTM drawdown: catastrophe hard-stop sees unrealized loss ---------------
def test_hard_stop_and_dd_use_mark_to_market_drawdown():
    import pytest
    from risk.capital_manager import CapitalManager
    st = PortfolioState(starting_capital=1000.0)
    st.note_equity(1000.0)                        # peak = 1000
    cm = CapitalManager({"hard_stop_drawdown_pct": 15})
    # nothing realized, but the book is -20% on marks
    assert st.drawdown_pct() == 0.0               # realized-only: blind
    assert st.drawdown_mtm_pct(800.0) == pytest.approx(20.0)
    assert cm.hard_stop_triggered(st, 800.0) is True   # MTM -> halt fires
    assert cm.hard_stop_triggered(st) is False         # realized-only fallback: no halt


def test_mtm_drawdown_is_peak_based():
    import pytest
    st = PortfolioState(starting_capital=1000.0)
    st.note_equity(1200.0)                         # grew to 1200 (new peak)
    st.note_equity(1100.0)                         # dipped; peak stays 1200
    assert st.drawdown_mtm_pct(1080.0) == pytest.approx(10.0)   # (1200-1080)/1200
    assert st.drawdown_mtm_pct(900.0) == pytest.approx(25.0)    # from the 1200 peak


# --- drift PSI: degenerate (binary) deciles do not fabricate drift ----------
def test_psi_binary_feature_no_false_drift():
    import numpy as np
    from ml.calibration import feature_deciles, psi
    rng = np.random.default_rng(0)
    train = (rng.random((500, 1)) < 0.28).astype(float)   # 28% ones
    live = (rng.random(500) < 0.28).astype(float)          # SAME distribution
    edges = feature_deciles(train)[0]
    assert psi(edges, live) == 0.0, \
        "a binary feature with an identical distribution must not read as drift"


def test_psi_continuous_feature_still_detects_real_shift():
    import numpy as np
    from ml.calibration import feature_deciles, psi
    rng = np.random.default_rng(1)
    train = rng.normal(0, 1, (600, 1))
    edges = feature_deciles(train)[0]
    assert psi(edges, rng.normal(0, 1, 600)) < 0.1     # same dist -> stable
    assert psi(edges, rng.normal(3, 1, 600)) > 0.25    # real shift -> flagged


def test_working_hedge_not_unwound_while_signal_delta_out_of_band():
    state = PortfolioState(starting_capital=10_000)
    state.add_position(_pos("eth1", "ETH/USD", "long", 2000.0, 1.0))     # signal +$2000
    # hedge short ~$1600 BTC -> TOTAL net = +$400 <= band $500, but the
    # SIGNAL-only net ($2000) is still well outside the band.
    state.add_position(_pos("hb", "BTC/USD", "short", 60000.0, 1600 / 60000,
                            is_hedge=True))
    acts = _hedger().evaluate(state, MARKS, 10_000.0, _corr())
    assert all(a.kind != "unwind" for a in acts), \
        "must not unwind a working hedge while signal delta is still out of band"
