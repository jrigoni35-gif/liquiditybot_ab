"""tests/test_long_trials.py — bind the long-book quant-trial gates
(G-L1..3, scripts/quant_trials.py's run_long_trials) to CI.

Compounder Phase C, task C5: the long-horizon accumulation book gets its
OWN harness function + OWN gate list, entirely separate from run_trials'
G1-G5 above (task-C5-brief.md's T6 warning - G1-G5 and their test are
untouched by this file). Mirrors tests/test_quant_trials.py's own
structure: fixed seed, cached run, generic gate iteration, a
determinism pin.

Small-N, fixed-seed (40 paths x 4000 bars, seed 7): deterministic,
~2.4s, verified to pass every gate with real margin at commit time
(G-L1 p95 1.46% vs a 13.18% cap; G-L2 ruin 0.00%; G-L3 $10,030 vs an
$8,732 floor). If a legitimate long-book geometry change moves the
numbers, re-run at a larger paths x bars and re-baseline consciously -
do not widen the gates to make CI quiet (same discipline
tests/test_quant_trials.py's own docstring documents for G1-G5).
"""
import importlib.util
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_spec = importlib.util.spec_from_file_location(
    "quant_trials", _ROOT / "scripts" / "quant_trials.py")
assert _spec is not None and _spec.loader is not None
_qt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_qt)

_PATHS, _BARS, _SEED = 40, 4000, 7
_CACHE = {}


def _trials():
    if "r" not in _CACHE:
        _CACHE["r"] = _qt.run_long_trials(_PATHS, _BARS, _SEED)
    return _CACHE["r"]


def test_all_long_book_gates_hold_on_fixed_seed():
    _, _, gates = _trials()
    failed = [f"{name}: {detail}" for name, ok, detail in gates if not ok]
    assert not failed, "long-book quant-trial gate regression: " + \
        "; ".join(failed)


def test_protocol_arm_bounds_tail_risk_and_keeps_capture():
    b, p, _ = _trials()
    # the two headline claims, asserted directly and independently of
    # gate thresholds: the ladder/thesis-stop/tier geometry bounds tail
    # drawdown far tighter than blind periodic-buy accumulation, without
    # giving up meaningful terminal capture
    assert p["dd_p95"] < b["dd_p95"]
    assert p["ruin"] == 0.0
    assert p["term_value_med"] >= 0.9 * b["term_value_med"]


def test_gates_are_g_l_named_and_separate_from_g1_g5():
    # T6 precedent: this is a SEPARATE gate list, never appended to
    # run_trials' own G1-G5 - every gate name here starts "G-L", and
    # run_trials' gates list is untouched (still exactly 5, G1-G5 named).
    _, _, gates = _trials()
    names = [name for name, _ok, _detail in gates]
    assert len(names) == 3
    assert all(n.startswith("G-L") for n in names)

    _, _, g1_g5 = _qt.run_trials(12, 400, 3)
    g1_g5_names = [name for name, _ok, _detail in g1_g5]
    assert g1_g5_names == ["G1 tail drawdown", "G2 tail outcome",
                           "G3 upside intact", "G4 ruin rate", "G5 capture"]


def test_arms_share_identical_worlds():
    # same seed twice -> byte-identical stats: the harness is
    # deterministic, so gate results are reproducible evidence
    b1, p1, _ = _qt.run_long_trials(6, 500, 3)
    b2, p2, _ = _qt.run_long_trials(6, 500, 3)
    assert b1 == b2 and p1 == p2
