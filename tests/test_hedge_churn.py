"""The 2026-08-07 ADA hedge churn (docs/quant/2026-08-07_ada_hedge_churn_
HANDOFF.md): 147 unwind/re-open laps in 25 min, -$318.27, driven by a COLD
correlation estimator oscillating between |rho|~1 (2-sample EWMA: open
passes) and 0.0 (variance <= EPS / missing pair: unwind fires). Contract
under test, per the handoff's DEADLOCK DISCIPLINE:

  * re-hedge (OPEN) requires WARM correlation evidence; the UNWIND is
    never gated (invariant 5 - exits always allowed)
  * per-asset cooldown after any unwind blocks re-OPENING only
  * >= churn_max_unwinds inside churn_window_sec latches the asset
    (FW-070), blocking OPENS only, and AUTO-releases on warm + window
    elapsed - release independent of the gated action
  * all clocks/latches survive a snapshot round-trip
  * a legacy CorrState with no samples info stays warm-assumed so every
    pre-existing caller keeps byte-identical behavior
"""
import types

from execution.hedging import HedgeEngine
from regime.correlation import CorrState

SYMS = {"ETH": "ETH/USD", "ADA": "ADA/USD"}


def _pos(pid, sym, direction, size, px, hedge=False):
    return types.SimpleNamespace(position_id=pid, symbol=sym,
                                 direction=direction, size=size,
                                 entry_price=px, is_hedge=hedge)


class _State:
    def __init__(self, positions):
        self._p = positions

    def open_positions(self):
        return list(self._p)


def _corr(rho, n_pairs=None):
    st = CorrState(corr_fast={("ETH", "ADA"): rho})
    if n_pairs is not None:
        st.samples = {"ETH": n_pairs, "ADA": n_pairs}
    return st


def _engine(**over):
    cfg = {"enabled": True,
           "max_net_delta_pct_of_equity": 10.0, "rebalance_band_pct": 4.0,
           "min_hedge_usd": 5.0, "corr_min_samples": 12,
           "rehedge_cooldown_sec": 600.0, "churn_max_unwinds": 3,
           "churn_window_sec": 900.0}
    cfg.update(over)
    return HedgeEngine(cfg, SYMS)


BOOK = [_pos("s1", "ETH/USD", "long", 1.0, 2000.0)]   # $2000 long, cap $1000


def test_cold_estimator_never_opens_a_hedge():
    """The churn's engine: a cold estimator flapping |rho|~1 <-> 0.0.
    With warmth gating, NO open is ever emitted while cold - the loop's
    re-opening half is dead regardless of what rho reads."""
    eng = _engine()
    state = _State(list(BOOK))
    opens = unwinds = 0
    for k in range(20):                       # 20 laps of the 08-07 shape
        rho = 1.0 if k % 2 == 0 else 0.0      # cold-EWMA oscillation
        acts = eng.evaluate(state, {}, 10_000.0, _corr(rho, n_pairs=k % 3),
                            now=1000.0 + 10 * k)
        for a in acts:
            if a.kind == "open":
                opens += 1
            elif a.kind == "unwind":
                unwinds += 1
    assert opens == 0, "cold correlation evidence must never buy new risk"
    assert unwinds == 0                        # no hedge existed to unwind


def test_cold_estimator_still_unwinds_once_and_only_once():
    """Exits are never gated: an existing hedge under cold corr unwinds
    (once - idempotent, it is gone afterwards). The $318 came from
    re-opening, not closing."""
    eng = _engine()
    hedge = _pos("h1", "ADA/USD", "short", 100.0, 1.0, hedge=True)
    state = _State(BOOK + [hedge])
    acts = eng.evaluate(state, {}, 10_000.0, _corr(0.0, n_pairs=2),
                        now=1000.0)
    assert [a.kind for a in acts] == ["unwind"]
    # hedge executed away; subsequent cold cycles may not re-open
    state2 = _State(list(BOOK))
    for k in range(10):
        acts = eng.evaluate(state2, {}, 10_000.0,
                            _corr(1.0, n_pairs=2), now=1010.0 + 10 * k)
        assert not [a for a in acts if a.kind == "open"]


def test_warm_low_correlation_unwind_still_fires():
    """The 02:01Z case: warm estimator, genuinely low corr 0.34 - the
    legitimate unwind must not be suppressed by any of the new guards."""
    eng = _engine()
    hedge = _pos("h1", "ADA/USD", "short", 100.0, 1.0, hedge=True)
    acts = eng.evaluate(_State(BOOK + [hedge]), {}, 10_000.0,
                        _corr(0.34, n_pairs=50), now=1000.0)
    assert [a.kind for a in acts] == ["unwind"]


def test_warm_open_works_and_cooldown_blocks_reopen_until_elapsed():
    eng = _engine()
    state = _State(list(BOOK))
    warm = _corr(0.80, n_pairs=50)
    acts = eng.evaluate(state, {}, 10_000.0, warm, now=1000.0)
    assert [a.kind for a in acts] == ["open"]          # baseline preserved
    # an unwind stamps the cooldown clock
    hedge = _pos("h1", "ADA/USD", "short", 100.0, 1.0, hedge=True)
    eng.evaluate(_State(BOOK + [hedge]), {}, 10_000.0,
                 _corr(0.34, n_pairs=50), now=2000.0)
    assert not [a for a in eng.evaluate(state, {}, 10_000.0, warm,
                                        now=2000.0 + 599.0)
                if a.kind == "open"], "inside cooldown: no re-open"
    assert [a.kind for a in eng.evaluate(state, {}, 10_000.0, warm,
                                         now=2000.0 + 601.0)] == ["open"]


def test_churn_latch_blocks_opens_and_auto_releases():
    eng = _engine(rehedge_cooldown_sec=1.0)    # isolate the latch
    warm = _corr(0.80, n_pairs=50)
    low = _corr(0.34, n_pairs=50)
    hedge = _pos("h1", "ADA/USD", "short", 100.0, 1.0, hedge=True)
    for k in range(3):                          # 3 unwinds inside window
        eng.evaluate(_State(BOOK + [hedge]), {}, 10_000.0, low,
                     now=1000.0 + 10 * k)
    state = _State(list(BOOK))
    assert not [a for a in eng.evaluate(state, {}, 10_000.0, warm,
                                        now=1100.0) if a.kind == "open"], \
        "latched asset must not re-open even warm + past cooldown"
    # AUTO-release: warm AND churn_window elapsed since the latch - the
    # release depends on time + evidence, never on the gated action
    assert [a.kind for a in eng.evaluate(state, {}, 10_000.0, warm,
                                         now=1020.0 + 901.0)] == ["open"]


def test_churn_state_survives_snapshot_round_trip():
    eng = _engine()
    low = _corr(0.34, n_pairs=50)
    hedge = _pos("h1", "ADA/USD", "short", 100.0, 1.0, hedge=True)
    for k in range(3):
        eng.evaluate(_State(BOOK + [hedge]), {}, 10_000.0, low,
                     now=1000.0 + 10 * k)
    eng2 = _engine()
    eng2.from_dict(eng.to_dict())
    warm = _corr(0.80, n_pairs=50)
    assert not [a for a in eng2.evaluate(_State(list(BOOK)), {}, 10_000.0,
                                         warm, now=1100.0)
                if a.kind == "open"], \
        "a restart must not amnesia the latch (median uptime 0.5h)"


def test_legacy_corr_state_without_samples_stays_warm_assumed():
    """Extend-with-defaults: every pre-existing caller/stub constructs
    CorrState with no samples info - their behavior must stay
    byte-identical (warm-assumed), or this fix silently disables hedging
    for old snapshots and half the test fleet."""
    eng = _engine()
    legacy = CorrState(corr_fast={("ETH", "ADA"): 0.80})
    acts = eng.evaluate(_State(list(BOOK)), {}, 10_000.0, legacy,
                        now=1000.0)
    assert [a.kind for a in acts] == ["open"]


def test_now_is_optional_for_legacy_callers():
    eng = _engine()
    acts = eng.evaluate(_State(list(BOOK)), {}, 10_000.0,
                        _corr(0.80, n_pairs=50))
    assert [a.kind for a in acts] == ["open"]
