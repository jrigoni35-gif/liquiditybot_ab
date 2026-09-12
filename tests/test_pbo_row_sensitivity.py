"""Pins for scripts/pbo_row_sensitivity.py.

The tool exists because a published stability claim had no reproduction path.
Its three pure helpers decide the axis of the sweep and the finding-or-not
predicate, so a silent defect in any of them would move a number that ships in
docs/HANDOFF.md. Each pin carries BOTH arms - a predicate that can only fire
one way is not a referee.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "pbo_row_sensitivity", REPO / "scripts" / "pbo_row_sensitivity.py")
assert _SPEC and _SPEC.loader
prs = importlib.util.module_from_spec(_SPEC)
sys.modules["pbo_row_sensitivity"] = prs
_SPEC.loader.exec_module(prs)


class TestParseDrops:
    def test_parses_sorts_and_dedupes(self):
        assert prs.parse_drops("0,1,2,3,5,10") == [0, 1, 2, 3, 5, 10]
        assert prs.parse_drops("10,1,1,0") == [0, 1, 10]

    def test_tolerates_whitespace_and_trailing_comma(self):
        assert prs.parse_drops(" 0 , 2 ,") == [0, 2]

    def test_rejects_negative(self):
        # a negative drop would LENGTHEN the slice via X[:T+k] and silently
        # score a different corpus than the label says
        with pytest.raises(ValueError):
            prs.parse_drops("0,-1")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            prs.parse_drops(" , ")

    def test_rejects_non_integer(self):
        with pytest.raises(ValueError):
            prs.parse_drops("0,two")


class TestBand:
    def test_spread_of_many(self):
        assert prs.band([0.1857, 0.9000, 0.6286]) == pytest.approx(0.7143)

    def test_single_reading_has_no_band(self):
        # NEGATIVE ARM: one point must not manufacture a spread
        assert prs.band([0.42]) == 0.0

    def test_identical_readings_have_no_band(self):
        assert prs.band([0.3, 0.3, 0.3]) == 0.0


class TestStraddles:
    def test_fires_when_readings_land_both_sides(self):
        assert prs.straddles([0.1857, 0.9000, 0.6286], 0.5) is True

    def test_silent_when_all_below(self):
        # NEGATIVE ARM: an imprecise gauge on a part that is comfortably in
        # spec is still fit to disposition - this must NOT report a finding
        assert prs.straddles([0.01, 0.19, 0.34], 0.5) is False

    def test_silent_when_all_above(self):
        assert prs.straddles([0.62, 0.90, 0.71], 0.5) is False

    def test_boundary_is_inclusive_green(self):
        # the shipped gate is `pbo <= 0.5` -> exactly 0.5 is a PASS, so a
        # sweep of {0.5, 0.4} does not straddle
        assert prs.straddles([0.5, 0.4], 0.5) is False
        assert prs.straddles([0.5, 0.6], 0.5) is True


def test_module_writes_nothing_on_import():
    """The tool is read-only; importing it must not touch the corpus."""
    src = (REPO / "scripts" / "pbo_row_sensitivity.py").read_text(
        encoding="utf-8")
    body = "\n".join(
        ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    for needle in ("open(", ".write(", ".write_text(", "to_csv("):
        assert needle not in body, f"{needle} present - tool claims read-only"


def test_docstring_names_why_it_is_committed():
    """The reason this file exists is the reason it must not be deleted.

    A future reader deciding whether to prune a one-off study script needs to
    see that a shipped claim in docs/HANDOFF.md points AT this tool.
    """
    doc = prs.__doc__ or ""
    assert "HANDOFF" in doc
    assert "overfit_check.py" in doc
