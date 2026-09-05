"""
tests/test_config_guard_governor_floor_and_exit_leg.py

Two config_guard FATALs whose subject is a SILENT degradation - a knob
whose bad value makes an instrument read CLEAN rather than read wrong.
Both were unguarded at ship; both are verified here against the running
system, not against prose.

1. `ml.monitor.min_trades_to_judge` had only an UPPER bound (<=
   window_trades, core/config_guard.py's monitor block). Below 5 the
   governor opens its judged window on 1-4 scored closes, and
   ml/calibration.py's `calibration_gap(..., n_bins=5)` returns **0.0**
   - the perfectly-calibrated value - for any window shorter than
   n_bins. ml/monitor.py `_judge` consumes that raw in two of its three
   verdict clauses (`gap > calib_gap_max`, and the `failing` conjunct),
   so on exactly the windows a sub-5 floor uniquely admits, the
   calibration test cannot convict. It does not read "unknown"; it reads
   "perfect".

2. `pretrade.price_exit_leg` was a wholly unguarded boolean. Falsy
   deletes the unwind leg (taker fee + half the spread) from the
   pre-trade EV cost stack in execution/pretrade.py, measured at
   39.0-45.0 bps over spread 2-14 bps at the shipped 22/38 tier - the
   cost stack drops to ~40% of its true value and the PT-041 edge bar
   falls with it. Cost-stack completeness is not a tunable; pricing
   entry-only is the documented way an 86%-hit-rate book still nets red.

MIRROR CONTRACT (same as _CAND_QUEUE_CODE_DEFAULT / _OVERFIT_ROWS_PER_
FEATURE elsewhere in config_guard): neither number is CHOSEN here. Both
track a literal in the module that will actually run, and the pins below
parse that module's own source so the mirror cannot drift silently.
"""
import json
import re
from pathlib import Path

import numpy as np
import pytest

from core.config_guard import _CALIBRATION_MIN_BINS, validate

ROOT = Path(__file__).resolve().parents[1]
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _fatals(cfg) -> list:
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def _monitor_cfg(**over) -> dict:
    """Minimal config exercising the monitor block only."""
    mon = {"window_trades": 30, "min_trades_to_judge": 15}
    mon.update(over)
    return {"system": {"dry_run": True}, "ml": {"monitor": mon}}


def _pretrade_cfg(**over) -> dict:
    """Minimal config exercising the pretrade block only. Fee keys are
    carried at the shipped tier so the sub-floor fee FATAL (a DIFFERENT
    finding) cannot contaminate a price_exit_leg assertion."""
    pt = {"maker_fee_bps": 22.0, "taker_fee_bps": 38.0,
          "allow_sub_floor_fees": True}
    pt.update(over)
    return {"system": {"dry_run": True}, "pretrade": pt,
            "order_manager": {"maker_fee_bps": 22.0, "taker_fee_bps": 38.0}}


# =========================================================================
# GUARD 1 - ml.monitor.min_trades_to_judge lower bound
# =========================================================================

@pytest.mark.parametrize("floor", [1, 2, 3, 4])
def test_min_trades_to_judge_below_calibration_bins_is_fatal(floor):
    """The whole defect band. Each of these opens a judged window on
    fewer samples than calibration_gap can bin."""
    hits = [m for m in _fatals(_monitor_cfg(min_trades_to_judge=floor))
            if "min_trades_to_judge" in m]
    assert hits, f"min_trades_to_judge={floor} must be FATAL"


def test_the_fatal_names_the_binning_reason():
    """A guard whose message does not say WHY sends the next operator to
    'fix' it by lowering the floor - the exact move CLAUDE.md forbids."""
    hits = [m for m in _fatals(_monitor_cfg(min_trades_to_judge=2))
            if "min_trades_to_judge" in m]
    assert hits
    msg = hits[0]
    assert "calibration" in msg.lower(), msg
    assert str(_CALIBRATION_MIN_BINS) in msg, msg


# --- anti-rubber-stamp: the guard must also PASS -------------------------

@pytest.mark.parametrize("floor", [5, 6, 15, 30])
def test_min_trades_to_judge_at_or_above_the_floor_is_clean(floor):
    """Proves the FATAL is CONDITIONAL. A guard that fires on every value
    is indistinguishable from a broken one."""
    hits = [m for m in _fatals(_monitor_cfg(min_trades_to_judge=floor))
            if "min_trades_to_judge" in m]
    assert not hits, f"min_trades_to_judge={floor} must be clean; got {hits}"


def test_absent_monitor_key_is_clean():
    """An undeclared key runs ml/monitor.py's own default (15), which is
    above the floor - the guard must not invent a finding for it."""
    cfg = {"system": {"dry_run": True}, "ml": {"monitor": {}}}
    assert not [m for m in _fatals(cfg) if "min_trades_to_judge" in m]


# --- the PREMISE, asked of the runtime rather than asserted in prose -----

def test_calibration_gap_reads_perfect_below_the_floor():
    """RUNTIME premise of guard 1. A maximally miscalibrated window
    (promised 0.99, lost every single time) must report a gap of exactly
    0.0 below the floor and the true ~0.99 at/above it. If this ever
    stops being true, guard 1's stated reason is stale."""
    from ml.calibration import calibration_gap
    for n in range(1, _CALIBRATION_MIN_BINS):
        gap = calibration_gap(np.zeros(n), np.full(n, 0.99))
        assert gap == 0.0, f"n={n} expected the 'perfect' 0.0, got {gap}"
    for n in (_CALIBRATION_MIN_BINS, _CALIBRATION_MIN_BINS + 1):
        gap = calibration_gap(np.zeros(n), np.full(n, 0.99))
        assert gap > 0.9, f"n={n} expected a real gap, got {gap}"


def test_governor_judges_a_blind_window_below_the_floor(tmp_path):
    """The CONSEQUENCE in the real consumer, not the helper. With a
    sub-floor min_trades_to_judge the governor publishes
    calibration_gap=0.0 for a window that is maximally miscalibrated -
    the clause reads CLEAN, not unavailable. At the floor the same
    evidence reports the true gap."""
    from ml.monitor import ModelMonitor

    def _gap_after(floor: int):
        m = ModelMonitor({"window_trades": 30, "min_trades_to_judge": floor,
                          "retrain_flag_path": str(tmp_path / f"r{floor}.flag")})
        for _ in range(floor):              # promised .99, lost every time
            m.record_close(0.99, 0, True)
        return m.status().get("calibration_gap")

    assert _gap_after(4) == 0.0, "sub-floor window should read 'perfect'"
    assert _gap_after(_CALIBRATION_MIN_BINS) > 0.9, \
        "at the floor the gap must become real"


def test_guard_floor_mirrors_calibration_gap_n_bins():
    """MIRROR PIN. _CALIBRATION_MIN_BINS is not a chosen number - it
    tracks ml/calibration.py's own `n_bins` default. Parsed from the
    `def` line itself, never from a comment (a pin a comment can satisfy
    is a known local failure mode)."""
    src = (ROOT / "ml" / "calibration.py").read_text(encoding="utf-8")
    m = re.search(r"def\s+calibration_gap\s*\([^)]*?n_bins\s*:\s*int\s*=\s*"
                  r"(\d+)", src, re.S)
    assert m, "could not locate calibration_gap's n_bins default"
    assert int(m.group(1)) == _CALIBRATION_MIN_BINS, (
        f"ml/calibration.py n_bins={m.group(1)} has drifted from "
        f"config_guard._CALIBRATION_MIN_BINS={_CALIBRATION_MIN_BINS}")


def test_upper_bound_still_binds():
    """Regression fence: adding a lower bound must not displace the
    pre-existing min > window_trades FATAL."""
    hits = [m for m in _fatals(
        _monitor_cfg(window_trades=10, min_trades_to_judge=15))
        if "min_trades_to_judge" in m]
    assert hits


# =========================================================================
# GUARD 2 - pretrade.price_exit_leg completeness
# =========================================================================

def test_price_exit_leg_false_is_fatal():
    hits = [m for m in _fatals(_pretrade_cfg(price_exit_leg=False))
            if "price_exit_leg" in m]
    assert hits, "price_exit_leg=false must be FATAL"


@pytest.mark.parametrize("falsy", [False, 0, 0.0, "", []])
def test_every_falsy_form_is_fatal(falsy):
    """execution/pretrade.py reads this through bool(), so 0 and "" turn
    the leg off exactly as False does. This pin asserts the whole
    read-site-falsy SET is refused; it deliberately does not care which
    clause refuses it (measured: `False` is caught by the falsy clause,
    the rest by the non-bool clause, because only False is a real bool).
    Mutation-checked by deleting BOTH clauses at once - either one alone
    leaves part of the set covered, which is why one mutation cannot
    prove this pin non-vacuous on its own."""
    hits = [m for m in _fatals(_pretrade_cfg(price_exit_leg=falsy))
            if "price_exit_leg" in m]
    assert hits, f"price_exit_leg={falsy!r} disables the leg; must be FATAL"


def test_truthy_non_bool_is_fatal():
    """bool("false") is True, so a config author's "false" silently
    LEAVES THE LEG ON - the opposite of the intent it expresses. Same
    coercion trap long_book.context.pause_in_crisis already FATALs."""
    hits = [m for m in _fatals(_pretrade_cfg(price_exit_leg="false"))
            if "price_exit_leg" in m]
    assert hits, "a non-bool price_exit_leg must be FATAL"


def test_the_exit_leg_fatal_explains_the_cost_stack():
    hits = [m for m in _fatals(_pretrade_cfg(price_exit_leg=False))
            if "price_exit_leg" in m]
    assert hits
    assert "cost" in hits[0].lower(), hits[0]


# --- anti-rubber-stamp: the guard must also PASS -------------------------

def test_price_exit_leg_true_is_clean():
    assert not [m for m in _fatals(_pretrade_cfg(price_exit_leg=True))
                if "price_exit_leg" in m]


def test_absent_price_exit_leg_is_clean():
    """Absent runs execution/pretrade.py's own default (True), which is
    the correct round-trip pricing - no finding is owed."""
    cfg = _pretrade_cfg()
    cfg["pretrade"].pop("price_exit_leg", None)
    assert not [m for m in _fatals(cfg) if "price_exit_leg" in m]


def test_guard_mirrors_the_pretrade_read_site_default():
    """MIRROR PIN. The 'absent is clean' branch above is only correct
    while execution/pretrade.py defaults the key to True. Parsed from
    the assignment, not a comment."""
    src = (ROOT / "execution" / "pretrade.py").read_text(encoding="utf-8")
    m = re.search(r"self\.price_exit_leg\s*=\s*bool\(\s*cfg\.get\(\s*"
                  r"[\"']price_exit_leg[\"']\s*,\s*(True|False)\s*\)\s*\)", src)
    assert m, "could not locate pretrade.py's price_exit_leg read-site"
    assert m.group(1) == "True", (
        "execution/pretrade.py no longer defaults price_exit_leg to True; "
        "the guard's 'absent is clean' branch is now wrong")


def test_exit_leg_is_a_material_share_of_the_cost_stack():
    """RUNTIME premise of guard 2, at the SHIPPED fee tier. Deleting the
    leg must measurably gut the stack - if it were immaterial the guard
    would be ceremony."""
    from execution.pretrade import PreTradeContext, PreTradeGate
    pt = dict(_CFG["pretrade"])
    book = {"bids": [[99.9, 50]], "asks": [[100.1, 50]]}
    ctx = PreTradeContext(kraken_book=book, sigma_daily_pct=3.0, adv_usd=5e7,
                          liq_label="liquid", spread_bps=10.0,
                          staleness_ms=100.0)

    def _cost(leg: bool) -> float:
        g = PreTradeGate(dict(pt, price_exit_leg=leg))
        return g.evaluate("buy", 1.0, 100.0, exp_alpha_bps=1e4,
                          fv_edge_bps=10.0, ctx=ctx).est_cost_bps

    on, off = _cost(True), _cost(False)
    # the leg is exactly taker_fee + half the spread
    assert on - off == pytest.approx(
        float(pt["taker_fee_bps"]) + 0.5 * 10.0, abs=1e-6)
    assert off < 0.5 * on, (
        f"leg-off stack {off} is not even half of {on}; the guard's "
        f"materiality premise no longer holds")


# =========================================================================
# THE FENCE - the shipped config must pass both, or this is not SAFE
# =========================================================================

def test_shipped_config_passes_both_new_guards():
    """If this ever reds, the change stops being measurement-only and
    becomes cohort-affecting: it would alter which orders are placed.
    That is an operator adjudication, never a config edit."""
    fatals = _fatals(_CFG)
    assert not [m for m in fatals if "min_trades_to_judge" in m], fatals
    assert not [m for m in fatals if "price_exit_leg" in m], fatals


def test_shipped_config_has_no_fatals_at_all():
    """Broader fence: the two new guards must not have collateral'd any
    other shipped value."""
    assert not _fatals(_CFG)
