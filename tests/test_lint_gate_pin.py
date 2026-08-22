"""The Definition-of-Done lint gate must not be coupled to ruff's defaults.

WHAT HAPPENED (2026-08-22). `[tool.ruff.lint]` carried
`extend-select = ["B", "C901"]`. `extend-select` extends whatever the
INSTALLED ruff defaults to — and ruff broadened its default rule set, so on
ruff 0.16.3 the CLAUDE.md battery's ruff line reported **958 errors across
the shipped scope on a tree nobody had touched**. Every one of them was a
rule this project never selected (UP045, RUF059, I001, BLE001, ...), and
none was a regression.

WHY IT MATTERS MORE THAN 958 LINT FINDINGS. A gate that goes red without a
change is indistinguishable from a gate that is broken, and the two
responses it invites are both destructive: mass-"fixing" findings the
project never opted into, or learning that the red line is background noise.
The battery's whole value is that a red line means someone did something.
Same failure shape the repo keeps meeting from the other direction — the
overfit battery printing green on a synthetic corpus. A gate must measure
what it claims, and must not silently change what it measures because an
upstream package shipped a release.

THE PIN. The rule set is now stated explicitly, so the gate measures the
same thing on every ruff version. Widening it is allowed and is a real
decision — this test does not freeze the list, it requires that the list be
STATED. Update the expected set here in the same commit that changes policy.
"""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The documented policy: ruff's historical defaults plus the curated breadth
# bump. Change deliberately, with the pyproject comment, in one commit.
EXPECTED = {"E4", "E7", "E9", "F", "B", "C901"}


def _lint_cfg() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["tool"]["ruff"]["lint"]


def test_rule_set_is_stated_not_inherited():
    cfg = _lint_cfg()
    assert "select" in cfg, (
        "the DoD lint gate must pin its rule set explicitly; without it the "
        "gate's meaning changes whenever ruff ships new defaults")
    assert set(cfg["select"]) == EXPECTED, (
        f"lint policy changed to {cfg['select']} without updating this pin")


def test_extend_select_does_not_come_back():
    """extend-select is exactly the coupling this file exists to remove."""
    assert "extend-select" not in _lint_cfg()


def test_per_file_ignores_do_not_waive_the_shipped_scope():
    """Waivers are for offline scripts. The engine trees and the two entry
    files stay un-waived — a waiver there would hide a real finding behind
    the same silence this gate is meant to break."""
    shipped = ("core/", "data/", "execution/", "ml/", "risk/", "regime/",
               "strategies/", "sentiment/", "api/", "main.py", "runner.py")
    waived = _lint_cfg().get("per-file-ignores", {})
    for pattern in waived:
        if pattern == "core/config_guard.py":
            continue          # documented C901 waiver, named in pyproject
        assert not pattern.startswith(shipped), \
            f"{pattern} waives lint rules inside the shipped scope"
