"""config_guard: system.deploy_branch (the auto-updater's deploy channel).

Why FATAL on a malformed pin rather than WARN: scripts/auto_update.py
IGNORES a name that fails its _BRANCH_RE (fail-safe — a bad pin must never
wedge the updater) and silently falls back to following the checkout. The
operator then believes the box follows the pin while it follows something
else, and the divergence only surfaces when a deploy never arrives. The
guard is the loud half of that pairing.
"""
from core.config_guard import validate


def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"]


def test_absent_key_is_not_checked():
    cfg = {"system": {"dry_run": True}}
    assert not any("deploy_branch" in m for m in _fatals(cfg))


def test_valid_branch_names_pass():
    for name in ("main", "release/1.2", "claude/remote-control-e3h815",
                 "v2.0-rc.1"):
        cfg = {"system": {"dry_run": True, "deploy_branch": name}}
        assert not any("deploy_branch" in m for m in _fatals(cfg)), name


def test_leading_dash_is_fatal():
    # '-upload-pack' in git argv parses as an OPTION, not a ref
    cfg = {"system": {"dry_run": True, "deploy_branch": "-upload-pack"}}
    assert any("deploy_branch" in m for m in _fatals(cfg))


def test_whitespace_and_non_string_are_fatal():
    for bad in ("two words", "", 7, 3.5, ["main"]):
        cfg = {"system": {"dry_run": True, "deploy_branch": bad}}
        assert any("deploy_branch" in m for m in _fatals(cfg)), repr(bad)
