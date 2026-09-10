"""Absence is not a value: six era-booked keys whose DELETION the guard missed.

Measured 2026-09-08 (config debug pass, branch cut12, shipped config): with
each of the six keys below deleted from a deep copy of config.json,
core.config_guard.validate() returned 0 FATAL for every one (deleting
queue_aware also silently dropped the starvation WARN, 3 -> 2). Each consumer
then reads a code default the accruing era was never booked at: label cost
0.5 (ml/history.py), the pre-XV-021 fill simulator (passive_base_prob 0.45,
queue_aware False; execution/order_manager.py), min ticket 25.0 in
risk/position_sizer.py (and 15 in the guard's own probe-floor check), a 0.25
probe shrink (main.py size_scale), and the hedger ON (execution/hedging.py
`cfg.get("enabled", True)`). The fee keys got this pin at cut #10 (est_fee_bps)
and 2026-09-05 (the four bps keys); these six get it here.

The pins assert against the SHIPPED config, not a synthetic fixture, so they
also fail the day someone removes one of these keys from config.json itself.
"""
import json
from pathlib import Path

import pytest

from core.config_guard import validate

ROOT = Path(__file__).resolve().parents[1]

# the six keys added 2026-09-08 - the subject of this file
ERA_KEYS = (
    "ml.label_round_trip_cost_pct",
    "order_manager.sim_fill.passive_base_prob",
    "order_manager.sim_fill.queue_aware",
    "position_sizer.min_ticket_usd",
    "ml.exploration.size_scale",
    "hedging.enabled",
)
# the positive controls: absence FATALs that already existed before this file
FEE_KEYS = (
    "pretrade.maker_fee_bps",
    "pretrade.taker_fee_bps",
    "order_manager.maker_fee_bps",
    "order_manager.taker_fee_bps",
    "profit_taking.est_fee_bps",
)


def _shipped() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _fatals(cfg) -> list:
    out = []
    for f in validate(cfg):
        sev = f[0] if isinstance(f, (tuple, list)) else getattr(f, "severity", "")
        msg = f[1] if isinstance(f, (tuple, list)) else str(f)
        if str(sev).upper() == "FATAL":
            out.append(str(msg))
    return out


def _absent_fatals(cfg) -> list:
    return [m for m in _fatals(cfg) if "absent from config" in m]


def _walk(cfg: dict, path: str):
    d = cfg
    parts = path.split(".")
    for p in parts[:-1]:
        d = d[p]
    return d, parts[-1]


def _pop(cfg: dict, path: str) -> None:
    d, leaf = _walk(cfg, path)
    assert leaf in d, f"{path} is not in the shipped config - fixture is stale"
    del d[leaf]


# ------------------------------------------------------------ the shipped file
def test_shipped_config_has_no_absent_key_fatal():
    """The pin needs a clean baseline or it cannot isolate the deletion."""
    assert _absent_fatals(_shipped()) == []


@pytest.mark.parametrize("path", ERA_KEYS + FEE_KEYS)
def test_shipped_config_declares_every_pinned_key(path):
    d, leaf = _walk(_shipped(), path)
    assert leaf in d, f"{path} missing from config.json"


# --------------------------------------------------------------- the deletion
@pytest.mark.parametrize("path", ERA_KEYS + FEE_KEYS)
def test_deleting_a_pinned_key_is_a_fatal_that_names_it(path):
    cfg = _shipped()
    _pop(cfg, path)
    msgs = _absent_fatals(cfg)
    assert any(path in m for m in msgs), (
        f"deleted {path} and no absent-key FATAL named it; FATALs were: "
        f"{msgs or _fatals(cfg)}")


def test_deleting_all_six_era_keys_names_all_six_in_one_fatal():
    cfg = _shipped()
    for path in ERA_KEYS:
        _pop(cfg, path)
    msgs = [m for m in _absent_fatals(cfg) if "era-booked" in m]
    assert len(msgs) == 1, msgs
    for path in ERA_KEYS:
        assert path in msgs[0]


# ------------------------------------------------------ anti-rubber-stamp pins
def test_deleting_a_doc_key_is_not_an_absent_key_fatal():
    """Only the named keys are load-bearing; a doc string is not."""
    cfg = _shipped()
    _pop(cfg, "ml._label_pt_cost_mult_doc")
    assert _absent_fatals(cfg) == []


def test_a_false_valued_key_is_present_not_absent():
    """hedging.enabled ships False and queue_aware could; a sentinel that
    treated falsy as missing would FATAL the shipped file. It must not."""
    cfg = _shipped()
    assert cfg["hedging"]["enabled"] is False, "fixture premise: hedger OFF"
    cfg["order_manager"]["sim_fill"]["queue_aware"] = False
    cfg["ml"]["exploration"]["size_scale"] = 0.01
    assert not [m for m in _absent_fatals(cfg) if "era-booked" in m]


def test_deleting_an_era_key_changes_exactly_the_fatal_count():
    """The new FATAL is additive: it must not perturb the guard's WARNs (the
    shipped file carries three known WARNs; deleting a key other than
    queue_aware must leave them untouched)."""
    base = validate(_shipped())
    base_warns = sorted(str(m) for s, m in base if str(s).upper() == "WARN")
    cfg = _shipped()
    _pop(cfg, "position_sizer.min_ticket_usd")
    out = validate(cfg)
    warns = sorted(str(m) for s, m in out if str(s).upper() == "WARN")
    assert warns == base_warns
    assert len(_fatals(cfg)) == len(_fatals(_shipped())) + 1
