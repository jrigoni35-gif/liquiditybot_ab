"""tests/test_quant_trials.py — bind the quant-trial gates to CI.

scripts/quant_trials.py proves the rev-4 protocol stack earns its keep
(tail drawdown, CVaR, ruin, give-back capture) on fat-tailed regime
worlds. This file makes that proof a standing obligation: a change to
RiskProtocolStack, ProfitTierEngine, or Position that erodes the gates
fails pytest instead of waiting for someone to run the script by hand.

Small-N, fixed-seed (80 paths x 1000 bars, seed 7): deterministic,
~2s, verified to pass every gate with ~10% margin on G1 at commit
time. If a legitimate protocol change moves the numbers, rerun the
full script (200x1200) and re-baseline consciously — do not widen the
gates to make CI quiet.

WARNING (#103 T6, 2026-07-23): this small-N pin is NOT a reliable
early-warning for full-scale G1 movement — under the deployed-geometry
enablement experiment it stayed green while its G1 margin collapsed to
~1% and the 200x1200 run failed G1 outright. Judge geometry changes at
200x1200 only; see docs/quant/2026-07-23_harness_enablement_finding.md.
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

_PATHS, _BARS, _SEED = 80, 1000, 7
_CACHE = {}


def _trials():
    if "r" not in _CACHE:
        _CACHE["r"] = _qt.run_trials(_PATHS, _BARS, _SEED)
    return _CACHE["r"]


def test_all_quant_gates_hold_on_fixed_seed():
    _, _, gates = _trials()
    failed = [f"{name}: {detail}" for name, ok, detail in gates if not ok]
    assert not failed, "quant-trial gate regression: " + "; ".join(failed)


def test_protocol_arm_shrinks_tail_risk_and_keeps_capture():
    b, p, _ = _trials()
    # the two headline claims, asserted directly and independently of
    # gate thresholds: fatter protection in the tail, no capture cost
    assert p["dd_p95"] < b["dd_p95"]
    assert p["cvar5"] > b["cvar5"]
    assert p["capture"] >= b["capture"]
    assert p["ruin"] <= b["ruin"]


def test_arms_share_identical_worlds():
    # same seed twice -> byte-identical stats: the harness is
    # deterministic, so gate results are reproducible evidence
    b1, p1, _ = _qt.run_trials(12, 400, 3)
    b2, p2, _ = _qt.run_trials(12, 400, 3)
    assert b1 == b2 and p1 == p2
