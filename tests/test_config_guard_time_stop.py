"""config_guard: profit_taking.time_stop bounds (Task 2, P2, PT-060).

max_bars_no_progress in [6, 500] FATAL — below 6 bars the time-stop would
scratch a position before even one confirmable bar of adverse noise
settles; above 500 bars (~41h at 5m bars) "no progress" stops meaning
anything distinct from "very patient". min_mfe_frac_of_tier1 in (0, 1]
FATAL — 0 or negative inverts the whole test (any MFE, even negative,
would "clear" it); above 1 demands MORE favorable excursion than tier 1's
own trigger, which tier 1 would already have closed on by then.

Coherence WARN: max_bars_no_progress below profit_taking.tighten_after_bars
means the time-stop scratches a no-progress position before the trail's
own time-tightening decay window (risk/profit_tiers.py's TIME TIGHTENING)
ever gets a chance to engage for it — informational (WARN, not FATAL): the
shipped defaults (36 vs 96) sit inside this band deliberately.
"""
import json
from pathlib import Path

from core.config_guard import validate

_ROOT = Path(__file__).resolve().parents[1]


def _cfg(bars=36, frac=0.5, enabled=True, tighten_after_bars=96):
    return {"system": {"dry_run": True},
            "profit_taking": {
                "tighten_after_bars": tighten_after_bars,
                "time_stop": {"enabled": enabled,
                              "max_bars_no_progress": bars,
                              "min_mfe_frac_of_tier1": frac}}}


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def test_shipped_defaults_no_fatal():
    assert not any("time_stop" in m for m in _fatals(_cfg()))


def test_default_absent_time_stop_no_fatal():
    assert not any("time_stop" in m for m in _fatals({}))


def test_bars_below_6_is_fatal():
    assert any("max_bars_no_progress" in m for m in _fatals(_cfg(bars=5)))


def test_bars_above_500_is_fatal():
    assert any("max_bars_no_progress" in m for m in _fatals(_cfg(bars=501)))


def test_bars_boundary_6_and_500_not_fatal():
    assert not any("max_bars_no_progress" in m for m in _fatals(_cfg(bars=6)))
    assert not any("max_bars_no_progress" in m
                  for m in _fatals(_cfg(bars=500)))


def test_frac_zero_is_fatal():
    assert any("min_mfe_frac_of_tier1" in m for m in _fatals(_cfg(frac=0.0)))


def test_frac_negative_is_fatal():
    assert any("min_mfe_frac_of_tier1" in m
              for m in _fatals(_cfg(frac=-0.1)))


def test_frac_above_1_is_fatal():
    assert any("min_mfe_frac_of_tier1" in m for m in _fatals(_cfg(frac=1.5)))


def test_frac_boundary_1_not_fatal():
    assert not any("min_mfe_frac_of_tier1" in m
                  for m in _fatals(_cfg(frac=1.0)))


def test_disabled_ignores_bad_bounds():
    cfg = _cfg(bars=0, frac=-5.0, enabled=False)
    assert not any("time_stop" in m for m in _fatals(cfg))


def test_coherence_warn_when_bars_below_tighten_after_bars():
    cfg = _cfg(bars=36, tighten_after_bars=96)
    assert any("shadows tighten_after_bars" in m for m in _warns(cfg))


def test_no_coherence_warn_when_bars_at_or_above_tighten_after_bars():
    cfg = _cfg(bars=96, tighten_after_bars=96)
    assert not any("shadows tighten_after_bars" in m for m in _warns(cfg))
    cfg2 = _cfg(bars=200, tighten_after_bars=96)
    assert not any("shadows tighten_after_bars" in m for m in _warns(cfg2))


def test_coherence_warn_disabled_time_stop_is_silent():
    cfg = _cfg(bars=1, tighten_after_bars=96, enabled=False)
    assert not any("shadows tighten_after_bars" in m for m in _warns(cfg))


def test_shipped_config_time_stop_matches_documented_defaults():
    shipped = json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))
    ts = shipped["profit_taking"]["time_stop"]
    assert ts["enabled"] is True
    assert ts["max_bars_no_progress"] == 36
    assert ts["min_mfe_frac_of_tier1"] == 0.5
    assert not any("time_stop" in m for m in
                  [m for sev, m in validate(shipped) if sev == "FATAL"])
    # shipped defaults sit inside the coherence WARN band (36 < 96)
    # deliberately — pinned so a change to either default is a conscious
    # decision, not silent drift
    assert any("shadows tighten_after_bars" in m
              for m in [m for sev, m in validate(shipped) if sev == "WARN"])
