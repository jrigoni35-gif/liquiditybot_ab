"""tests/test_config_guard_label_mode.py — config_guard FATALs on an
unsupported ml.label_mode (2026-07-26 signal-quality task,
task-signalquality-brief.md).

Previously unvalidated: CandidateLabeler's own dispatch (ml/history.py)
only special-cases the literal string "exit_policy"; anything else
(including a config typo like "eixt_policy") silently fell back to
triple_barrier with no error at all, masking an operator's actual intent.
Only "exit_policy" (the rollback path / A-B arm) and "triple_barrier" (the
signal-quality default this task ships) are wired
(ml/history.py CandidateLabeler.__init__, scripts/train_meta.py).
"""
from core.config_guard import validate


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_absent_label_mode_no_fatal():
    assert not any("label_mode" in m for m in _fatals({}))


def test_shipped_triple_barrier_default_no_fatal():
    cfg = {"ml": {"label_mode": "triple_barrier"}}
    assert not any("label_mode" in m for m in _fatals(cfg))


def test_rollback_exit_policy_no_fatal():
    cfg = {"ml": {"label_mode": "exit_policy"}}
    assert not any("label_mode" in m for m in _fatals(cfg))


def test_typo_value_is_fatal():
    cfg = {"ml": {"label_mode": "eixt_policy"}}
    assert any("label_mode" in m for m in _fatals(cfg))


def test_empty_string_is_fatal():
    cfg = {"ml": {"label_mode": ""}}
    assert any("label_mode" in m for m in _fatals(cfg))


def test_non_string_value_is_fatal():
    cfg = {"ml": {"label_mode": 1}}
    assert any("label_mode" in m for m in _fatals(cfg))


def test_fatal_regardless_of_dry_run():
    """Structural config-nonsense check, not a live-risk bound - FATALs
    even in dry_run (unlike e.g. the sub-floor-fee check)."""
    cfg = {"system": {"dry_run": True}, "ml": {"label_mode": "bogus"}}
    assert any("label_mode" in m for m in _fatals(cfg))
    cfg_live = {"system": {"dry_run": False}, "ml": {"label_mode": "bogus"}}
    assert any("label_mode" in m for m in _fatals(cfg_live))
