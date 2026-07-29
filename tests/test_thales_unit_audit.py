"""tests/test_thales_unit_audit.py — 2026-07-29 THALES unit-coherence
audit corrections (docs/quant/2026-07-29_thales_unit_audit.md):

  A-2  stop-zone proximity null subtraction: the raw score's geometric
       base rate (tol / magnet spacing — 30-62% of the gap at the
       shipped 0.15% tol vs the 0.30%-of-mark step floor) is subtracted
       per grid magnet, so a random mark reads ~0 while an at-magnet
       mark still reads ~1 (corpus evidence: th_stopzone > 0.5 on 43.4%
       of 6,462 rows with ZERO realized-PnL discrimination — the gauge
       reported its own null).
  A-3  spoof-flicker EWMA wall-time normalization: the same physical
       spoofer must score the same at 2.5s / 5s / 10s poll cadences
       (pre-fix: never-fires / ~0.50 / saturates-at-1.0 respectively).
  B-2 + B-1b wiring pins: shadow-mode grading reaches the reliability
       ledger; the explore floor no longer re-inflates a manip-downsized
       probe; ML-083 era-orphan deploy unlock is wired.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code
from strategies.thales import ThalesEngine, _round_number_steps

ROOT = Path(__file__).resolve().parents[1]

CFG = {
    "enabled": True, "influence": "advise",
    "stops": {"swing_lookback": 48, "zone_tol_pct": 0.15,
              "pre_gain": 0.1, "post_gain": 0.1, "revert_decay_sec": 1800},
    "spoof": {"top_levels": 5, "big_ratio": 3.0, "drop_frac": 0.8,
              "decay": 0.85, "score_thr": 0.35},
}


# ---------------------------------------------------------------------
# A-2: stop-zone geometric-null subtraction
# ---------------------------------------------------------------------
def _zone_engine(mark: float, n_hist: int = 24, tick: float = 1e-4):
    """Engine with a fine-tick candle history ~1% ABOVE `mark` so the
    degeneracy guard stays open (tick << tol band) while the swing
    hi/lo magnets - which are correctly NOT null-subtracted - sit far
    outside the tolerance band and cannot mask the grid-magnet score
    under test."""
    eng = ThalesEngine(CFG)
    st = eng._st("X")
    for i in range(n_hist):
        px = mark * 1.01 + (i % 5) * tick
        st.candle_hist.append((1000.0 + 300.0 * i, px, px + tick,
                               px - tick, px))
    return eng, st


def test_stop_zone_at_magnet_still_scores_high():
    # mark exactly ON a round-number magnet: null subtraction must not
    # dull a genuine at-magnet reading ((1 - mu)/(1 - mu) == 1)
    mark = 0.52                      # magnet for steps .0025/.005/.01
    eng, st = _zone_engine(mark)
    prox, _ = eng._stop_zones(st, mark)
    assert prox > 0.95


def test_stop_zone_mid_band_base_rate_reads_zero():
    """A mark inside the tolerance band but scoring BELOW the geometric
    null must read 0 (pre-fix: 0.23 of pure base rate). mark 0.5206:
    nearest magnet 0.52, d/mark = 0.00115 < tol 0.0015 -> raw 0.231;
    mu_null = tol_abs/finest step = 0.00078/0.0025 = 0.312 > raw -> 0."""
    eng, st = _zone_engine(0.5206)
    prox, _ = eng._stop_zones(st, 0.5206)
    assert prox == 0.0


def test_stop_zone_null_scaling_between_band_edges():
    # closer than the null but not at the magnet: 0 < prox < raw
    mark = 0.5202                    # d/mark = 0.000384, raw = 0.7435
    eng, st = _zone_engine(mark)
    prox, _ = eng._stop_zones(st, mark)
    raw = 1.0 - (0.0002 / mark) / 0.0015
    mu = (0.0015 * mark) / min(_round_number_steps(mark))
    expect = (raw - mu) / (1.0 - mu)
    assert abs(prox - expect) < 0.02
    assert 0.0 < prox < raw


def test_round_number_steps_matches_grid_acceptance():
    # the split-out step helper accepts exactly the [0.3%, 3%] band
    steps = _round_number_steps(0.52)
    assert steps == [0.0025, 0.005, 0.01]
    assert _round_number_steps(0.0) == []


# ---------------------------------------------------------------------
# A-3: spoof flicker cadence invariance
# ---------------------------------------------------------------------
def _run_spoofer(dt: float, seconds: float = 600.0) -> float:
    """Drive _update_spoof at poll interval `dt` against a spoofer that
    rests a 10x wall on the bid side for 5s then pulls it for 5s (10s
    flip period), mid never crossing the wall. Returns the steady-state
    bid-side score."""
    eng = ThalesEngine(CFG)
    st = eng._st("X")
    base_bids = [[100.0, 1.0], [99.9, 1.0], [99.8, 1.0],
                 [99.7, 1.0], [99.6, 1.0]]
    asks = [[100.1, 1.0], [100.2, 1.0], [100.3, 1.0],
            [100.4, 1.0], [100.5, 1.0]]
    t, tail = 0.0, []
    while t < seconds:
        phase = t % 10.0
        bids = ([[100.0, 1.0], [99.85, 10.0], [99.9, 1.0],
                 [99.8, 1.0], [99.7, 1.0]]
                if phase < 5.0 else list(base_bids))
        eng._update_spoof(st, bids, asks, 100.05, now=1000.0 + t)
        if t > 0.8 * seconds:            # steady-state window: average
            tail.append(st.spoof_ewma.get("bids", 0.0))   # out the
        t += dt                                           # cycle phase
    return sum(tail) / max(len(tail), 1)


def test_spoof_score_is_cadence_invariant():
    """The SAME physical spoofer (10s flip period: wall rests 5s, pulled
    5s) must land in the same scoring band at every cadence that can
    OBSERVE it (dt < flip period; sampling AT the period aliases the
    flicker away for any estimator - physics, not scoring). Pre-fix
    (per-poll EWMA): 2s/2.5s cadences could never cross thr 0.35 while
    5s scored ~0.50 - the verdict was chosen by the sampler, not the
    spoofer."""
    s20, s25, s5 = _run_spoofer(2.0), _run_spoofer(2.5), _run_spoofer(5.0)
    for s, label in ((s20, "2.0s"), (s25, "2.5s"), (s5, "5s")):
        assert 0.35 < s < 0.70, f"{label} cadence out of band: {s:.3f}"
    assert max(s20, s25, s5) - min(s20, s25, s5) < 0.15


def test_spoof_quiet_book_stays_quiet_at_any_cadence():
    eng = ThalesEngine(CFG)
    st = eng._st("X")
    bids = [[100.0, 1.0], [99.9, 1.1], [99.8, 0.9], [99.7, 1.0],
            [99.6, 1.2]]
    asks = [[100.1, 1.0], [100.2, 1.0], [100.3, 1.0], [100.4, 1.0],
            [100.5, 1.0]]
    for k in range(60):
        eng._update_spoof(st, bids, asks, 100.05, now=1000.0 + 2.5 * k)
    assert st.spoof_ewma.get("bids", 0.0) == 0.0


# ---------------------------------------------------------------------
# wiring pins (B-2 shadow grading, B-1b floor withhold, ML-083 unlock)
# ---------------------------------------------------------------------
def test_shadow_mode_grading_reaches_the_ledger_wiring():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    # B-2: fired detectors recorded in BOTH modes (grading is
    # observational; the old advise-only gate was the chicken-and-egg
    # that kept the reliability ledger empty forever)
    assert "self._thales_fired[asset] = list(th.fired)" in src
    assert 'if self.thales.influence == "advise" else []' not in src
    # every graded close (empty fired included) feeds the __base__ null
    assert "if fired is not None:" in src


def test_probe_floor_withheld_under_manip_downsize():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    sites = re.findall(
        r"floor_to_min=\(explored and not aggressive\s*"
        r"and manip_scale >= 1\.0 - 1e-9\)", src)
    assert len(sites) == 2, (
        "both sizer call sites (PASS-1 direct and PASS-2 bracket) must "
        "withhold the explore floor when the manip gate downsized the "
        "probe - re-inflating to the $15 floor voided the 0.6-0.9 band")


def test_era_orphan_deploy_unlock_wired_and_registered():
    assert Code.ML_CHAMPION_ERA_ORPHAN.value == "ML-083"
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "elif int(self.meta.trained_rows) > len(X):" in src
    assert "Code.ML_CHAMPION_ERA_ORPHAN" in src
