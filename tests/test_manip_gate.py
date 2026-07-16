"""tests/test_manip_gate.py — the anti-scalp entry gate.

manip_suspect_score used to feed three passive places (feature, training-weight
discount, status panel), "none a new gate". This promotes it to a LIVE, NEW-
ENTRY-ONLY risk action: don't post fresh limit liquidity into a book a bigger
fish is painting to scalp. The band is config-driven (risk.manip_gate):

    score < downsize_at            -> 1.0   (untouched)
    downsize_at <= score < veto_at -> linear taper 1.0 -> min_scale
    score >= veto_at               -> None  (veto the entry, SZ-045)

EXITS never call this path (the gate is a new-risk brake, never an escape
brake). Two surfaces are pinned: the pure sizing math (manip_entry_scale) and
the config_guard coherence checks that keep a 2am config edit from collapsing
the band.
"""
import json
from pathlib import Path

import pytest

from core.config_guard import validate
from main import manip_entry_scale

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))

# shipped band
_D, _V, _M = 0.6, 0.9, 0.25


def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"]


# --- pure sizing math -------------------------------------------------------
def test_below_downsize_untouched():
    assert manip_entry_scale(0.0, _D, _V, _M) == 1.0
    assert manip_entry_scale(0.59, _D, _V, _M) == 1.0


def test_at_downsize_edge_is_still_full_size():
    # frac 0 at the lower edge -> exactly 1.0 (no discontinuity entering band)
    assert manip_entry_scale(_D, _D, _V, _M) == pytest.approx(1.0)


def test_midband_is_linear():
    # halfway across [0.6, 0.9] -> halfway from 1.0 to 0.25 = 0.625
    mid = manip_entry_scale((_D + _V) / 2.0, _D, _V, _M)
    assert mid == pytest.approx(1.0 - 0.5 * (1.0 - _M))     # 0.625


def test_just_below_veto_approaches_min_scale():
    s = manip_entry_scale(_V - 1e-6, _D, _V, _M)
    assert _M < s < _M + 1e-3
    assert s > _M                    # still a trade, just a small one


def test_at_and_above_veto_returns_none():
    assert manip_entry_scale(_V, _D, _V, _M) is None
    assert manip_entry_scale(0.95, _D, _V, _M) is None
    assert manip_entry_scale(1.0, _D, _V, _M) is None


def test_scale_never_leaves_min_scale_to_one():
    for i in range(101):
        s = manip_entry_scale(i / 100.0, _D, _V, _M)
        if s is not None:
            assert _M <= s <= 1.0


def test_degenerate_span_never_divides_by_zero():
    # veto == downsize: no linear region; any score in-band saturates but the
    # 1e-9 span floor keeps it finite (config_guard FATALs this combo anyway)
    s = manip_entry_scale(0.7, 0.7, 0.7, _M)
    assert s is None                 # 0.7 >= veto 0.7 -> veto first


# --- config_guard coherence -------------------------------------------------
def test_shipped_manip_gate_is_coherent():
    assert not any("manip_gate" in m for m in _fatals(_CFG))


def test_veto_not_above_downsize_is_fatal():
    cfg = json.loads(json.dumps(_CFG))
    cfg["risk"]["manip_gate"]["veto_at"] = 0.6      # == downsize_at
    assert any("manip_gate" in m for m in _fatals(cfg))
    cfg["risk"]["manip_gate"]["veto_at"] = 0.5      # < downsize_at
    assert any("manip_gate" in m for m in _fatals(cfg))


def test_out_of_range_thresholds_are_fatal():
    cfg = json.loads(json.dumps(_CFG))
    cfg["risk"]["manip_gate"]["veto_at"] = 1.5      # > 1
    assert any("manip_gate" in m for m in _fatals(cfg))


def test_min_scale_above_one_is_fatal():
    cfg = json.loads(json.dumps(_CFG))
    cfg["risk"]["manip_gate"]["min_scale"] = 1.5    # not a [0,1] size factor
    assert any("manip_gate" in m for m in _fatals(cfg))


def test_disabled_gate_skips_coherence_checks():
    # an operator who turns the gate off should not be blocked by stale,
    # now-irrelevant band values sitting in the disabled block
    cfg = json.loads(json.dumps(_CFG))
    cfg["risk"]["manip_gate"] = {"enabled": False, "veto_at": 0.1,
                                 "downsize_at": 0.9, "min_scale": 5.0}
    assert not any("manip_gate" in m for m in _fatals(cfg))
