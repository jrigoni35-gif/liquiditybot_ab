"""Pins for scripts/instrument_contract.py.

The contract is a detector, so the pins that matter are the REFUSALS. Its
first run produced four false positives out of five findings, and a detector
with that rate gets ignored - which is the same failure one level up. Both
sources are pinned here so they cannot come back:

  C1  a backticked PATH in prose, and a script passed as an ARGUMENT to
      another command, are not commands. The first cut reported
      quant_trials (an argument to ruff) and gate_truth_report/cohort_eval
      (prose about degraded gates) as "named but never run".
  C2  a file that merely CONTAINS the string "--self-test" is not an
      instrument that ships one. The first cut matched its own docstring and
      ran itself with an invalid flag.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "instrument_contract.py"


def _load():
    spec = importlib.util.spec_from_file_location("instrument_contract", _SRC)
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.skip("instrument_contract.py not importable")
    m = importlib.util.module_from_spec(spec)
    sys.modules["instrument_contract"] = m
    spec.loader.exec_module(m)
    return m


ic = _load()


# --- C1: only an invocation is a command --------------------------------

def test_dod_parse_finds_the_real_gates():
    named = ic.dod_commands()
    for expected in ("pytest", "smoke_test", "assurance_check",
                     "overfit_check", "ruff", "bandit", "compileall"):
        assert expected in named, f"DoD gate {expected} not parsed"


def test_a_script_passed_as_an_argument_is_not_a_command():
    """quant_trials.py appears inside the ruff invocation's file list. It is
    a lint TARGET, not a gate the battery must run."""
    assert "quant_trials" not in ic.dod_commands()


def test_a_backticked_path_in_prose_is_not_a_command():
    """gate_truth_report / cohort_eval are named in the DoD's prose about
    gates that degrade honestly - they are not commands to execute."""
    named = ic.dod_commands()
    assert "gate_truth_report" not in named
    assert "cohort_eval" not in named


def test_rootedness_is_clean_on_the_current_tree():
    r = ic.check_rootedness()
    assert r["missing"] == [], f"DoD gate named but never run: {r['missing']}"
    assert r["ok"] is True


def test_a_commented_out_gate_does_not_count_as_executed(tmp_path,
                                                         monkeypatch):
    """THE MUTATION THAT CAUGHT THIS. Commenting out the smoke entry left the
    text 'scripts/smoke_test.py' inside the tuple, and the first parser still
    reported 'every named gate is executed' - it could not see its own target
    being switched off. A detector blind to that is theatre."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "auto_update.py").write_text(
        '_HARD_GATES = (\n'
        '    ("ruff", ["-m", "ruff", "check", "core"]),\n'
        '    # ("smoke", ["scripts/smoke_test.py"]),   # disabled\n'
        ')\n', encoding="utf-8")
    monkeypatch.setattr(ic, "ROOT", tmp_path)
    got = ic.battery_gates()
    assert "ruff" in got
    assert "smoke_test" not in got, "a commented-out gate read as executed"


def test_exemptions_are_declared_not_silent():
    """pyright is not run by the battery. That must be an explicit, reasoned
    exemption rather than a quiet omission."""
    assert "pyright" in ic.C1_EXEMPT
    assert ic.C1_EXEMPT["pyright"]


# --- C2: registered, not merely mentioned -------------------------------

def test_the_detector_does_not_detect_itself():
    names = {p.name for p in ic.instruments_with_self_test()}
    assert _SRC.name not in names


def test_only_files_that_REGISTER_the_flag_count(tmp_path, monkeypatch):
    mentions = tmp_path / "scripts" / "mentions.py"
    registers = tmp_path / "scripts" / "registers.py"
    mentions.parent.mkdir(parents=True)
    mentions.write_text('"""docs mention --self-test in prose."""\n',
                        encoding="utf-8")
    registers.write_text(
        'import argparse\n'
        'ap = argparse.ArgumentParser()\n'
        'ap.add_argument("--self-test", action="store_true")\n',
        encoding="utf-8")
    monkeypatch.setattr(ic, "ROOT", tmp_path)
    found = {p.name for p in ic.instruments_with_self_test()}
    assert "registers.py" in found
    assert "mentions.py" not in found


# --- C3: an impossible pair must fire, and live state must not be read ---

def test_effective_exceeding_count_is_caught():
    bad = ic._scan_populations({"ml": {"load_stats": {"rows": 100,
                                                      "ess_kish": 120.0}}})
    assert len(bad) == 1
    assert bad[0]["ratio"] == pytest.approx(1.2)


def test_a_legal_pair_does_not_fire():
    assert ic._scan_populations({"a": {"rows": 100, "ess_kish": 40.0}}) == []
    assert ic._scan_populations({"a": {"n": 50, "effective_n": 12.9}}) == []


def test_equality_is_legal():
    """ESS == n is the all-equal-weights case, not a violation."""
    assert ic._scan_populations({"a": {"rows": 10, "ess_kish": 10.0}}) == []


def test_c3_skips_rather_than_reading_live_state():
    """Reading status.json in a BLOCKING gate is itself one of the defects
    this contract exists to stop, so the default must skip and say so."""
    r = ic.check_one_population(None)
    assert r["skipped"] is True
    assert r["ok"] is True
    assert "LIVE MUTABLE" in r["why"]


def test_c3_reports_the_path_of_a_violation(tmp_path):
    import json
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"deep": {"nest": {"n": 10, "n_eff": 11}}}),
                 encoding="utf-8")
    r = ic.check_one_population(p)
    assert r["ok"] is False
    assert r["violations"][0]["path"] == "deep.nest"


# --- C2: UNVERIFIED is not WEAK (2026-09-03) ----------------------------
# scripts/rpe_factor.py ships a POWER ARM in its own source, but imports
# pandas at module scope, so on any box without the optional analysis stack
# `--self-test` exits 1 before printing a line. The checker required
# returncode==0 and therefore reported it as "null-arm-only" - a confident,
# specific, WRONG diagnosis of an instrument that is fine. "0 findings" and
# "the scan is broken" are the SAME OBSERVATION until separated (CLAUDE.md
# mindset #3), and assurance_check's own C1 branch already applies exactly
# this rule to a missing tool ("TOOL UNAVAILABLE IS NOT A FINDING ... how the
# replay gate bricked deploys 2026-07-21/22").
#
# The asymmetry is the whole point and is pinned in both directions: a
# THIRD-PARTY absence is excusable, a REPO module absence is a real breakage.

def _probe(tmp_path, monkeypatch, body: str):
    """Register one synthetic instrument and run the C2 clause over it."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "probe.py").write_text(body, encoding="utf-8")
    monkeypatch.setattr(ic, "ROOT", tmp_path)
    res = ic.check_self_tests(timeout=60)
    return res, {r["file"]: r for r in res["instruments"]}


_REGISTERS = ('import argparse\n'
              'ap = argparse.ArgumentParser()\n'
              'ap.add_argument("--self-test", action="store_true")\n')


def test_absent_third_party_dep_is_unverified_not_weak(tmp_path, monkeypatch):
    res, by = _probe(tmp_path, monkeypatch,
                     "import nonexistent_third_party_pkg\n" + _REGISTERS)
    rec = by["probe.py"]
    assert rec["could_not_run"] == "nonexistent_third_party_pkg", rec
    assert res["unverified"] == ["probe.py"], res
    # and it must NOT drag the clause red - it is unproven, not disproven
    assert res["ok"] is True, res


def test_absent_REPO_module_is_still_a_real_failure(tmp_path, monkeypatch):
    """The excuse must never extend to our own packages."""
    res, by = _probe(tmp_path, monkeypatch,
                     "from core import not_a_real_module\n" + _REGISTERS)
    rec = by["probe.py"]
    assert rec["could_not_run"] is None, rec
    assert rec["ok"] is False and res["ok"] is False, res


def test_a_self_test_that_RUNS_without_a_negative_arm_still_fails(
        tmp_path, monkeypatch):
    """The gate's teeth: this is the case the clause exists for."""
    res, by = _probe(tmp_path, monkeypatch,
                     _REGISTERS + 'print("SELF-TEST PASS")\n')
    rec = by["probe.py"]
    assert rec["could_not_run"] is None and rec["exit"] == 0, rec
    assert rec["ok"] is False and res["ok"] is False, res


def test_a_real_power_arm_passes(tmp_path, monkeypatch):
    res, by = _probe(
        tmp_path, monkeypatch,
        _REGISTERS + 'print("NULL CONTROL ok")\nprint("POWER ARM 1/1")\n')
    assert by["probe.py"]["ok"] is True, by["probe.py"]
    assert res["ok"] is True and res["unverified"] == [], res
