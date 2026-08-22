"""tests/test_turbulence_observability.py — REG-8 Phase 0 (SAFE class).

`regime/correlation.py`'s cross-asset `turbulence_pct` can set
`macro=crisis` on every asset at once (regime/macro_regime.py:441-442 ->
playbook `allow_new: False`), yet before this change:

  * D6 — five early returns in `update_turbulence` held the PREVIOUS
    reading indefinitely with no timestamp, no sample count, no staleness
    flag and no reason code. A held crisis value was byte-identical to a
    freshly computed one.
  * D7 — `grep -rn "turbulence" core/ api/` returned nothing: the scalar
    reached no operator surface at all.
  * §4 — `regime.crisis_vol_pct` and the whole `correlation` config block
    were unguarded, and `correlation.py`'s operator warning carried its
    OWN hardcoded `95`, a second copy of the threshold the decision uses.

Evidence: docs/quant/2026-08-22_turbulence_instrument_verification.md and
docs/quant/2026-08-22_REG8_crisis_predicate_algorithm.md §7.

OBSERVABILITY ONLY. Every assertion below is about provenance, status
export, guard coverage and log/code hygiene; the decision path (which
orders are placed) is untouched, and the last section pins that the
turbulence NUMBERS themselves are unchanged by this work.
"""
import ast
import json
import math
from pathlib import Path

import numpy as np
import pytest

from core import code_stats
from core.codes import Code
from core.config_guard import validate
from regime.correlation import CorrelationEngine, CorrState

_ROOT = Path(__file__).resolve().parents[1]
_CORR_SRC = (_ROOT / "regime" / "correlation.py").read_text(encoding="utf-8")
_SHIPPED = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))

DAY = 86400.0


# ---------------------------------------------------------------------------
# fixtures (same shape as tests/test_audit_regime_strategy.py's M7 block)
# ---------------------------------------------------------------------------
def _daily(returns, t0=1_600_000_000.0, px0=100.0):
    out, px = [], px0
    for i, r in enumerate([0.0] + list(returns)):
        px *= math.exp(r)
        out.append({"time": t0 + i * DAY, "open": px, "high": px * 1.001,
                    "low": px * 0.999, "close": px, "volume": 10.0})
    return out


def _good_fixture(n=200, seed=5):
    """Two co-moving assets with a violent final-day divergence — enough
    shared bars for a real computation."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, 0.01, n)
    ra, rb = r.copy(), r.copy()
    ra[n - 3], rb[n - 3] = 0.15, -0.15
    return {"A": _daily(ra), "B": _daily(rb)[:-1]}


def _disjoint_fixture():
    """Both series long enough to be PREPPED, but their day lattices do not
    intersect — the `len(shared) < 41` floor."""
    fx = _good_fixture()
    return {"A": fx["A"],
            "B": [dict(c, time=c["time"] + 500 * DAY) for c in fx["B"]]}


# ===========================================================================
# 1. CorrState grew four fields — with defaults, breaking no caller
# ===========================================================================
def test_corrstate_provenance_fields_default_to_the_legacy_state():
    st = CorrState()
    assert st.computed_at == 0.0        # never computed
    assert st.sample_count == 0
    assert st.stale is False
    assert st.hold_reason == ""


def test_corrstate_pre_existing_positional_construction_still_works():
    """Invariant #7: extend with defaults, never break existing callers.
    The legacy positional order (through `samples`) must be untouched."""
    st = CorrState({("A", "B"): 0.9}, {}, {}, {}, 12.5, 97.0, True,
                   {"A": 40, "B": 40})
    assert st.corr("A", "B") == 0.9
    assert st.turbulence == 12.5 and st.turbulence_pct == 97.0
    assert st.shifted is True and st.pair_samples("A", "B") == 40
    # the appended fields fall back to the legacy meaning
    assert (st.computed_at, st.sample_count, st.stale, st.hold_reason) == \
        (0.0, 0, False, "")


# ===========================================================================
# 2. the success path stamps provenance
# ===========================================================================
def test_successful_computation_stamps_ts_samples_and_clears_stale():
    eng = CorrelationEngine({})
    st = eng.update_turbulence(_good_fixture())
    assert st.turbulence > 0.0
    assert st.computed_at > 1_600_000_000.0      # a real wall-clock stamp
    assert st.stale is False and st.hold_reason == ""
    # sample_count is the RETURN count = the percentile denominator, i.e.
    # the unit the >= 40 floor and the "window n=250" reading are stated in
    assert st.sample_count >= 40
    assert st.turbulence_pct == pytest.approx(
        100.0 * round(st.turbulence_pct / (100.0 / st.sample_count)) /
        st.sample_count, abs=1e-6)


# ===========================================================================
# 3. every early return marks the reading HELD, with its own slug
# ===========================================================================
def test_hold_few_assets_keeps_the_prior_reading_and_flags_it():
    eng = CorrelationEngine({})
    eng.update_turbulence(_good_fixture())
    prior_t, prior_p = eng.state.turbulence, eng.state.turbulence_pct
    prior_ts, prior_n = eng.state.computed_at, eng.state.sample_count

    st = eng.update_turbulence({"A": _good_fixture()["A"]})     # one asset
    assert st.stale is True and st.hold_reason == "few_assets"
    # the reading itself is HELD, not recomputed and not cleared
    assert (st.turbulence, st.turbulence_pct) == (prior_t, prior_p)
    assert (st.computed_at, st.sample_count) == (prior_ts, prior_n)


def test_hold_few_shared_bars():
    eng = CorrelationEngine({})
    st = eng.update_turbulence(_disjoint_fixture())
    assert st.stale is True and st.hold_reason == "few_shared_bars"
    assert st.computed_at == 0.0        # never computed at all


def test_hold_few_returns():
    """A lookback under the engine's own 40-return floor can never produce a
    reading — the exact configuration config_guard now FATALs (§5)."""
    eng = CorrelationEngine({"turbulence_lookback_days": 20})
    st = eng.update_turbulence(_good_fixture())
    assert st.stale is True and st.hold_reason == "few_returns"


def test_hold_step_slugs_are_reachable_through_the_one_helper():
    """`no_step` / `bad_step` are DEFENSIVE branches (a sorted distinct-
    timestamp series always yields a positive median step), so they are
    pinned at the helper they route through rather than faked with an
    impossible fixture."""
    eng = CorrelationEngine({})
    for slug in ("no_step", "bad_step"):
        eng._turb_held = False
        st = eng._hold_turbulence(slug)
        assert st.stale is True and st.hold_reason == slug


def test_no_early_return_bypasses_the_hold_stamp():
    """Source pin: the ONLY bare `return self.state` left in
    `update_turbulence` is the success path's final statement — every
    non-success exit routes through `_hold_turbulence`, so a future sixth
    early return cannot silently re-introduce an unstamped hold."""
    fn = next(n for n in ast.walk(ast.parse(_CORR_SRC))
              if isinstance(n, ast.FunctionDef) and n.name == "update_turbulence")
    bare = [n for n in ast.walk(fn) if isinstance(n, ast.Return)
            and isinstance(n.value, ast.Attribute)
            and ast.unparse(n.value) == "self.state"]
    assert len(bare) == 1 and bare[0] is fn.body[-1], \
        "an early return in update_turbulence skips the hold stamp"
    holds = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and ast.unparse(n.func) == "self._hold_turbulence"]
    assert len(holds) == 5, f"expected the five early returns, found {len(holds)}"


# ===========================================================================
# 4. the reason code is registered AND rate-limited
# ===========================================================================
def test_held_and_recovered_codes_are_registered():
    assert Code.CR_TURBULENCE_HELD.value == "CR-010"
    assert Code.CR_TURBULENCE_FRESH.value == "CR-011"
    assert "CR  regime.correlation" in (
        __import__("core.codes", fromlist=["x"]).__doc__ or ""), \
        "the prefix map must advertise the family (registry-hygiene pass)"


def test_hold_code_fires_once_per_episode_not_once_per_cycle():
    """SZ-047 was 63% of a 35,530-record audit trail. update_turbulence runs
    hourly and a feed outage persists for hours, so the code MUST latch."""
    eng = CorrelationEngine({})
    eng.update_turbulence(_good_fixture())            # warm: a live reading
    code_stats.reset()

    for _ in range(25):                               # a long hold episode
        eng.update_turbulence({"A": _good_fixture()["A"]})
    snap = code_stats.snapshot()
    assert snap.get("CR-010") == 1, snap
    assert "CR-011" not in snap
    # ...but the CURRENT reason stays continuously readable
    assert eng.state.stale is True and eng.state.hold_reason == "few_assets"

    for _ in range(5):                                # recovery, also once
        eng.update_turbulence(_good_fixture())
    snap = code_stats.snapshot()
    assert snap.get("CR-010") == 1 and snap.get("CR-011") == 1, snap
    assert eng.state.stale is False

    for _ in range(5):                                # a SECOND episode re-arms
        eng.update_turbulence({"A": _good_fixture()["A"]})
    assert code_stats.snapshot().get("CR-010") == 2
    code_stats.reset()


# ===========================================================================
# 5. the duplicated `95` is collapsed to one config read
# ===========================================================================
def test_no_hardcoded_crisis_percentile_left_in_update_turbulence():
    fn = next(n for n in ast.walk(ast.parse(_CORR_SRC))
              if isinstance(n, ast.FunctionDef) and n.name == "update_turbulence")
    lits = [n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool) and n.value == 95]
    assert not lits, ("a second copy of regime.crisis_vol_pct is back in "
                      "update_turbulence - it must read self.crisis_pct")


def test_operator_warning_tracks_the_configured_threshold(caplog):
    """Behavioral proof, not just a source pin: at a threshold ABOVE this
    fixture's reading the warning must stay silent (the old hardcoded 95
    would have fired), and at a threshold below it must fire."""
    fx = _good_fixture()
    quiet = CorrelationEngine({}, crisis_pct=99.99)
    with caplog.at_level("WARNING", logger="liquiditybot.regime.correlation"):
        quiet.update_turbulence(fx)
    assert 95.0 <= quiet.state.turbulence_pct < 99.99, quiet.state.turbulence_pct
    assert not [r for r in caplog.records if "turbulence spike" in r.message]

    caplog.clear()
    loud = CorrelationEngine({}, crisis_pct=50.0)
    with caplog.at_level("WARNING", logger="liquiditybot.regime.correlation"):
        loud.update_turbulence(fx)
    assert [r for r in caplog.records if "turbulence spike" in r.getMessage()]


def test_default_crisis_pct_reproduces_the_shipped_value():
    """Behavior-identical today: config.json ships 95 and the parameter's
    default is 95, so no caller's warning moved."""
    assert CorrelationEngine({}).crisis_pct == 95.0
    assert float(_SHIPPED["regime"]["crisis_vol_pct"]) == 95.0


# ===========================================================================
# 6. config_guard coverage — and it must pass on the SHIPPED config
# ===========================================================================
def _msgs(cfg, sev):
    return [m for s, m in validate(cfg) if s == sev]


def test_shipped_config_trips_none_of_the_new_checks():
    findings = validate(_SHIPPED)
    assert not [m for s, m in findings if s == "FATAL"]
    noisy = [m for s, m in findings
             if ("crisis_vol_pct" in m or "correlation." in m)]
    assert not noisy, noisy


def test_crisis_vol_pct_must_be_a_percentile():
    for bad in (0.0, -5.0, 100.1):
        cfg = json.loads(json.dumps(_SHIPPED))
        cfg["regime"]["crisis_vol_pct"] = bad
        assert any("crisis_vol_pct" in m for m in _msgs(cfg, "FATAL")), bad
    cfg = json.loads(json.dumps(_SHIPPED))
    cfg["regime"]["crisis_vol_pct"] = 100.0            # the boundary is legal
    assert not any("crisis_vol_pct" in m for m in _msgs(cfg, "FATAL"))


def test_crisis_cut_must_sit_above_the_volatile_band():
    cfg = json.loads(json.dumps(_SHIPPED))
    cfg["regime"]["crisis_vol_pct"] = 60.0             # below bull_volatile 70
    assert any("crisis_vol_pct" in m for m in _msgs(cfg, "WARN"))


def test_turbulence_lookback_below_the_return_floor_is_fatal():
    cfg = json.loads(json.dumps(_SHIPPED))
    cfg["correlation"]["turbulence_lookback_days"] = 30
    assert any("turbulence_lookback_days" in m for m in _msgs(cfg, "FATAL"))
    cfg["correlation"]["turbulence_lookback_days"] = "many"
    assert any("turbulence_lookback_days" in m for m in _msgs(cfg, "FATAL"))


def test_correlation_lambdas_and_shift_threshold_are_bounded():
    cfg = json.loads(json.dumps(_SHIPPED))
    cfg["correlation"]["lambda_fast"] = 1.4
    assert any("lambda_fast" in m for m in _msgs(cfg, "FATAL"))
    cfg = json.loads(json.dumps(_SHIPPED))
    cfg["correlation"]["lambda_fast"] = 0.999          # slower than lambda_slow
    assert any("lambda_fast" in m for m in _msgs(cfg, "WARN"))
    cfg = json.loads(json.dumps(_SHIPPED))
    cfg["correlation"]["shift_threshold"] = 0.0
    assert any("shift_threshold" in m for m in _msgs(cfg, "WARN"))


# ===========================================================================
# 7. the number finally reaches an operator surface (D7)
# ===========================================================================
def test_status_carries_the_correlation_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from main import LiquidityBot, load_config
    from runner import BotRunner
    from scripts.smoke_test import MockBinanceUS, MockKraken, MockOKX

    cfg = load_config(str(_ROOT / "config.json"))
    cfg["system"]["dry_run"] = True
    for k in ("sentiment", "webdata", "moomoo"):
        cfg[k]["enabled"] = False
    prices = {"ETH": 2000.0, "BTC": 60000.0}
    bot = LiquidityBot(cfg, okx=MockOKX(prices), binanceus=MockBinanceUS(prices),
                       kraken=MockKraken(prices), resume=False)

    # the collapse, end to end: the engine's warning threshold IS the value
    # regime/macro_regime.py decides on — one quantity, one derivation
    assert bot.corr.crisis_pct == bot.macro.crisis_vol_pct

    runner = BotRunner(bot.config, bot=bot)
    st = runner.build_status(1_700_000_000.0)
    assert set(st["correlation"]) == {"turbulence", "turbulence_pct",
                                      "computed_at", "sample_count",
                                      "stale", "hold_reason"}
    assert st["correlation"]["computed_at"] == 0.0     # no daily bars yet
    json.dumps(st)                                     # stays JSON-safe

    bot.corr.state.turbulence = 41.5
    bot.corr.state.turbulence_pct = 97.2
    bot.corr.state.computed_at = 1_700_000_000.0
    bot.corr.state.sample_count = 250
    bot.corr.state.stale = True
    bot.corr.state.hold_reason = "few_shared_bars"
    st = runner.build_status(1_700_000_000.0)
    assert st["correlation"] == {"turbulence": 41.5, "turbulence_pct": 97.2,
                                 "computed_at": 1_700_000_000.0,
                                 "sample_count": 250, "stale": True,
                                 "hold_reason": "few_shared_bars"}
    # load-bearing schema keys are EXTENDED, never displaced
    for k in ("mode", "positions", "regimes", "monitor", "ml", "equity",
              "runner_state", "sim"):
        assert k in st


# ===========================================================================
# 8. ZERO decision-path change: the numbers themselves did not move
# ===========================================================================
def test_turbulence_values_are_unchanged_by_the_observability_work():
    """The Mahalanobis reading and its percentile are what
    regime/macro_regime.py consumes. Recomputed here independently from the
    fixture, exactly as the shipped estimator does, so a drift in the
    computation (not just in the stamping around it) reds this test."""
    fx = _good_fixture()
    eng = CorrelationEngine({})
    eng.update_turbulence(fx)

    assets = sorted(fx)
    keyed = {}
    for a in assets:
        by_ts = {c["time"]: c["close"] for c in fx[a][:-1]}
        keyed[a] = by_ts
    shared = sorted(set.intersection(*(set(k) for k in keyed.values())))
    R = np.column_stack([
        np.diff(np.log(np.array([keyed[a][d] for d in shared], float)))
        for a in assets])
    mu, cov = R.mean(axis=0), np.cov(R, rowvar=False)
    cov += np.eye(cov.shape[0]) * (np.trace(cov) / cov.shape[0]) * 0.05
    d = np.einsum("ij,jk,ik->i", R - mu, np.linalg.inv(cov), R - mu)

    assert eng.state.turbulence == pytest.approx(float(d[-1]), rel=1e-9)
    assert eng.state.turbulence_pct == pytest.approx(
        float((d < d[-1]).mean() * 100.0), rel=1e-9)
    assert eng.state.sample_count == R.shape[0]
