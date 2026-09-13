"""Pins for scripts/agent_brief.py.

The tool exists because hand-copied briefing blocks went stale and a
hand-copied fence under-published the law by four axes. Its value is entirely
in two properties, and both are pinned here with BOTH arms:

  1. It DERIVES rather than stores. A volatile number hardcoded into the file
     would silently reintroduce the defect the tool was built to remove, so
     there is a test that reads the SOURCE and refuses literals that look like
     corpus figures.
  2. Its fence comes from CLAUDE.md and DEGRADES CLOSED. A parse failure must
     produce an explicit refusal, never a plausible remembered list.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_SRC = REPO / "scripts" / "agent_brief.py"
_SPEC = importlib.util.spec_from_file_location("agent_brief", _SRC)
assert _SPEC and _SPEC.loader
ab = importlib.util.module_from_spec(_SPEC)
sys.modules["agent_brief"] = ab
_SPEC.loader.exec_module(ab)


# --------------------------------------------------------------------------
# 1. the fence comes from the law, and degrades CLOSED
# --------------------------------------------------------------------------

def test_the_fence_is_parsed_and_matches_the_law():
    """Every axis CLAUDE.md names must appear, by substring, in the parse.

    Keyed on the four that a hand-copy in docs/HANDOFF.md actually dropped
    (2026-09-12, c0807f7f): the universe, the hedger, the probe ticket, the
    heat cap. Those are cut #11's own levers, which is what made the omission
    dangerous rather than cosmetic.
    """
    axes, note = ab.moratorium_axes()
    assert axes, f"fence parse failed: {note}"
    joined = " | ".join(axes).lower()
    for required in ("entry decisioning", "position sizing",
                     "stop/exit geometry", "fill simulator", "fee booking",
                     "order lifecycle", "universe", "hedger", "probe ticket",
                     "heat cap"):
        assert required in joined, f"fence is missing {required!r}: {axes}"


def test_the_fence_count_matches_claude_md_not_a_remembered_number():
    """Non-vacuity: assert the parse found TEN, the count in the law today.

    If CLAUDE.md legitimately gains or loses an axis this goes red and a human
    reads the law - which is the correct outcome. It must never be 'fixed' by
    editing this number without reading CLAUDE.md.
    """
    axes, _ = ab.moratorium_axes()
    law = (REPO / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
    assert "COHORT-RESETTING" in law
    assert len(axes) == 10, (
        f"parsed {len(axes)} axes: {axes}. Read CLAUDE.md before changing this "
        f"pin - a fence short by one axis restarts an era by accident.")


def test_a_broken_fence_parse_refuses_rather_than_substituting(tmp_path,
                                                               monkeypatch):
    """DEGRADE CLOSED. With the law unreadable the tool must return an empty
    list and a reason, and the rendered block must SAY it could not parse -
    not quietly omit the section and not emit a remembered list."""
    monkeypatch.setattr(ab, "REPO", tmp_path)          # no CLAUDE.md there
    axes, note = ab.moratorium_axes()
    assert axes == []
    assert note and note != ""
    facts = {"generated_utc": "X", "exec_era": "X", "era_ordinal": "X",
             "cohort_resetting_axes": ab.UNKNOWN, "cohort_resetting_source": note,
             "cohort_resetting_count": ab.UNKNOWN, "mode": "X",
             "runner_state": "X", "status_stamp": "X", "dry_run_config": True,
             "force_dry_sentinel_present": True, "maker_fee_bps": 1,
             "taker_fee_bps": 1, "config_stamp": "X",
             "label_round_trip_cost_pct": 1, "label_pt_vol_mult": 8,
             "label_sl_vol_mult": 6, "label_pt_cost_mult": 4,
             "label_max_bars": 432, "label_pt_bps": 1, "label_sl_bps": 1,
             "meef_dpt_dcost": 4, "corpus_rows": 1, "mean_uniqueness": 1,
             "n_eff_routes": {}, "n_eff_note": "x", "edge_ratio_bump": 0.0,
             "stop_widen": 1.0, "kelly_mult": 1.0, "ws_kraken": {},
             "moomoo_available": True, "overfit_report_stamp": "X",
             "overfit_summary": "X"}
    text = ab.render(facts)
    assert "COULD NOT PARSE THE FENCE" in text
    assert "read CLAUDE.md yourself" in text.lower() or \
           "read CLAUDE.md" in text


# --------------------------------------------------------------------------
# 2. the design rule, made enforceable: DERIVE, never store
# --------------------------------------------------------------------------

def test_no_volatile_number_is_hardcoded_in_the_source():
    """The tool exists because hand-typed corpus figures go stale. A literal
    that looks like one, in the CODE, would reintroduce exactly that.

    Deliberately narrow: five-digit row counts and the specific stale figures
    from the briefs that motivated this file. It does not ban all numbers -
    neutral values (0.0/1.0), the era-ordinal regex bounds and multipliers are
    legitimate.
    """
    src = _SRC.read_text(encoding="utf-8")
    code = "\n".join(
        ln for ln in src.splitlines()
        if not ln.lstrip().startswith("#"))
    # strip the module docstring, which legitimately CITES the stale numbers
    # as the motivating incident
    body = code.split('"""', 2)[-1] if code.count('"""') >= 2 else code
    for stale in ("18020", "18052", "0.0868", "0.0867", "1563", "1565"):
        assert stale not in body, (
            f"{stale!r} is hardcoded in agent_brief.py - the tool must DERIVE "
            f"corpus figures, never store them")
    assert not re.search(r"(?<![\w.])1[0-9]{4}(?![\w.])", body), (
        "a five-digit literal that looks like a row count is present")


def test_the_tool_writes_nothing():
    src = _SRC.read_text(encoding="utf-8")
    body = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    for needle in (".write_text(", ".write(", "open(", "to_csv("):
        # read_text is fine; the ban is on write paths
        assert needle not in body.replace(".read_text(", ""), \
            f"{needle} present - the brief must be read-only"


# --------------------------------------------------------------------------
# 3. live values are stamped, and unknowns are explicit
# --------------------------------------------------------------------------

def test_every_live_value_carries_a_stamp():
    facts = ab.collect()
    for key in ("status_stamp", "config_stamp", "generated_utc"):
        assert facts.get(key), f"{key} missing - a live value with no as-of"


def test_n_eff_is_published_as_ROUTES_not_as_a_number():
    """Three derivations are in the record and they disagree. Publishing one
    scalar would pick a side silently - the exact failure the note exists for.
    """
    facts = ab.collect()
    assert isinstance(facts["n_eff_routes"], dict)
    assert "disagree" in facts["n_eff_note"].lower()
    assert "n_eff" not in {k for k in facts if k == "n_eff"}, \
        "a single n_eff scalar is published - publish the routes instead"


def test_unknowns_are_explicit_never_guessed():
    """collect() must emit the UNKNOWN sentinel rather than a plausible value
    when a source is missing."""
    assert ab.UNKNOWN == "[UNKNOWN]"
    src = _SRC.read_text(encoding="utf-8")
    assert src.count("UNKNOWN") > 10, \
        "few UNKNOWN sentinels - the tool is probably guessing somewhere"


def test_render_is_non_empty_and_names_its_own_generator():
    facts = ab.collect()
    text = ab.render(facts)
    assert "scripts/agent_brief.py" in text
    assert "RE-DERIVED AT GENERATION TIME" in text
    assert len(text.splitlines()) > 30
