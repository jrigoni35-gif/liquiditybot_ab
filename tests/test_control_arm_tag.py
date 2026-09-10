"""Pins for the control-arm stratification tag (schema 94->95, sandbox
prototype, 2026-08-27).

THE DEFECT THIS CURES AT THE ROOT. gate_efficacy_report's baseline arm is
the 2026-07-20 migration-backfilled blank-disposition cohort: n=0 rows
since, zero label_era overlap with current veto cohorts (a94b5751 shipped
a CONFOUNDED_BASELINE refusal rather than a fix - a frozen baseline can
never be re-earned by any amount of report-side cleverness). This column
makes the confound structurally impossible going forward: CONTROL_ARM_
FRACTION of every new row is deterministically tagged as it is written, so
the learning loop grows its own contemporaneous control arm forever.

These pins protect three properties, in order of how badly a silent
regression would hurt: (1) the tag is NEVER read by decision code anywhere
in this tree - a structural grep guard, not just an absence of call sites
today; (2) the assignment is deterministic and seedless - the same
(asset, ts) must land in the same arm on every machine, forever, which is
what makes an "arm" meaningful evidence rather than a per-run coin flip;
(3) a mixed old/new corpus loads cleanly and the tag never contaminates
FEATURE_NAMES or the trained matrix (2026-08-08 DoF adjudication, model
freeze).
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from ml.features import FEATURE_NAMES
from ml.history import (CONTROL_ARM_BUCKET_SECONDS, CONTROL_ARM_FRACTION,
                        HistoryStore, _control_arm_tag)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _store(tmp_path) -> tuple[HistoryStore, Path]:
    p = tmp_path / "outputs" / "signal_history.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    return HistoryStore(str(p)), p


def _read(p: Path):
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# --- determinism / known-value regression pins -----------------------------

def test_determinism_repeated_calls_agree():
    """No RNG, no process/global state: calling twice, in any order,
    against other inputs interleaved, must give the identical answer."""
    a = _control_arm_tag("BTC", 1_700_000_000.0)
    _control_arm_tag("ETH", 42.0)     # interleave a different input
    _control_arm_tag("SOL", 999.0)
    b = _control_arm_tag("BTC", 1_700_000_000.0)
    assert a == b


@pytest.mark.parametrize("asset,ts,expected", [
    # Regression pins against the shipped sha256/bucket/fraction formula.
    # A formula change (hash function, byte slice, normalization, bucket
    # width, fraction constant) flips at least one of these - that is the
    # point: this table is the mutation trip-wire for the tagging rule.
    ("BTC", 0.0, False),
    ("BTC", 3599.0, False),      # same CONTROL_ARM_BUCKET_SECONDS bucket
    ("BTC", 3600.0, True),       # next bucket - demonstrates the boundary
    ("ETH", 1000.0, False),
    ("ETH", 1_000_000.0, False),
    ("SOL", 999_000.0, False),
    ("ADA", 42.0, False),
    ("ADA", 126_938_843.0, True),
    ("XRP", 1_752_618_007.0, True),
])
def test_known_value_pins(asset, ts, expected):
    assert _control_arm_tag(asset, ts) is expected


def test_normalization_boundary_integers(monkeypatch):
    """Pin the ARM BOUNDARY itself, through the real function (2026-08-28
    review verdict on the /0xFFFFFFFF divisor). The divisor maps the
    8-hex int onto [0, 1] inclusive; at fraction 0.05 both candidate
    divisors (0xFFFFFFFF and 0x100000000) admit exactly h <= 214748364
    (0x0CCCCCCC) - the thresholds 214748364.75 and 214748364.8 straddle
    no integer - so the admitted SET, not the formula, is the contract.
    Drive digest[:8] directly by faking sha256 so the pins sit ON the
    boundary instead of wherever real digests happen to land. A fraction
    typo, an inverted comparison, or a genuinely wrong normalization
    (e.g. /0xFFFF) goes red here; swapping to the other [0,1) divisor
    stays green because behavior is identical - which is the point: this
    pins behavior, and the docstring forbids touching the formula."""
    import ml.history as mh

    class _FakeDigest:
        def __init__(self, hex8: str):
            self._hex = hex8 + "0" * 56
        def hexdigest(self) -> str:
            return self._hex

    def _drive(hex8: str) -> bool:
        monkeypatch.setattr(mh.hashlib, "sha256",
                            lambda _b, _h=hex8: _FakeDigest(_h))
        return mh._control_arm_tag("BTC", 3600.0)

    assert _drive("00000000") is True     # floor of the range
    assert _drive("0ccccccc") is True     # 214748364: last admitted int
    assert _drive("0ccccccd") is False    # 214748365: first rejected int
    assert _drive("ffffffff") is False    # frac == 1.0 endpoint: never
    # admitted, never an error - the documented inclusive-range case
    assert int("0ccccccc", 16) == 214748364   # the pin's own arithmetic


def test_bucket_floors_within_the_window():
    """CONTROL_ARM_BUCKET_SECONDS=3600 is a documented design choice, not
    an accident of the literal 3600 in the pins above - assert the
    constant directly so a future config-lift changes this test's
    expectation deliberately, not silently."""
    assert CONTROL_ARM_BUCKET_SECONDS == 3600
    assert CONTROL_ARM_FRACTION == 0.05


def test_fraction_matches_target_over_a_large_distinct_sample():
    """Controlled experiment (many distinct asset/timestamp draws), not a
    read of the formula: the empirical membership rate must land near
    CONTROL_ARM_FRACTION. Tolerance is generous (+-0.01 absolute on
    n=20,000, expected std error ~0.0015) to avoid flaking on the sha256
    tail's own sampling noise while still catching a fraction that is
    badly wrong (e.g. an inverted comparison, or a fraction typo)."""
    n = 20_000
    hits = sum(
        1 for i in range(n)
        if _control_arm_tag(f"ASSET{i % 37}", float(i * 137 + 11)))
    frac = hits / n
    assert abs(frac - CONTROL_ARM_FRACTION) < 0.01, (
        f"empirical fraction {frac} far from target {CONTROL_ARM_FRACTION}")


def test_different_assets_same_bucket_are_independent_draws():
    """The hash keys on asset too, not just the time bucket - two assets
    signalling in the identical bucket must not be forced into the same
    arm (that would silently halve the effective granularity of the
    stratification)."""
    ts = 5_000_000.0
    results = {a: _control_arm_tag(a, ts)
              for a in ("BTC", "ETH", "SOL", "ADA", "XRP", "DOGE", "AVAX")}
    # Not all seven need to agree; if they DID all agree that would be
    # strong evidence the asset string is not actually mixed into the
    # hash. Assert the concrete observed split instead of hand-waving.
    assert not all(v == next(iter(results.values())) for v in results.values())


# --- not a feature -----------------------------------------------------

def test_control_arm_never_enters_feature_names():
    """HARD CONSTRAINT: the tag must never be added to FEATURE_NAMES or
    any trainer input (2026-08-08 DoF adjudication keeps the feature
    ledger closed; the model freeze is untouched)."""
    assert "control_arm" not in FEATURE_NAMES


def test_control_arm_absent_from_decision_code():
    """Structural guard, not just an absence of call sites TODAY: outside
    the write path (ml/history.py, scripts/migrate_history.py) and the
    test tree (free to name the column in assertions), the string
    'control_arm' must appear NOWHERE - a gate, a sizer, an order path, a
    veto check picking it up is exactly the HARD CONSTRAINT violation
    ("the tag is written, never read by decision code") and must fail
    loudly here rather than be discovered later by a live behavior
    change."""
    allow = {
        REPO_ROOT / "ml" / "history.py",
        REPO_ROOT / "scripts" / "migrate_history.py",
    }
    hits = []
    for path in REPO_ROOT.rglob("*.py"):
        parts = path.parts
        # `.claude` holds agent-tooling state, including git worktrees created
        # under .claude/worktrees/. A nested checkout carries byte-copies of
        # ml/history.py at a DIFFERENT absolute path, so it misses the
        # canonical-path `allow` set below and reads as a violation. Measured
        # 2026-08-30: a stray isolation worktree turned this pin red on an
        # unmodified tree. Nothing under `.claude` is decision code, so
        # excluding it narrows the scan to what the guard is actually about.
        if (
            ".venv" in parts
            or "__pycache__" in parts
            or "tests" in parts
            or ".claude" in parts
            # `outputs` is gitignored runtime state and agent scratch
            # (outputs/reports/<study>/scratch/*.py). Measured 2026-09-09: a
            # measurement study's scripts mentioning the column turned this
            # pin red on a clean decision path - the scan was reading a
            # corpus nothing ships. Same fix as test_ofi_feature.py.
            or "outputs" in parts
        ):
            continue
        if path.resolve() in allow:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "control_arm" in text:
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert hits == [], f"control_arm referenced outside the write path: {hits}"


# --- write-path wiring ---------------------------------------------------

def test_new_row_carries_the_real_computed_tag(tmp_path):
    store, p = _store(tmp_path)
    store._append_row("c1", "BTC", "long", np.zeros(len(FEATURE_NAMES)),
                      1, 0.0, "candidate", signal_ts=3600.0, barrier="tb_pt")
    r = _read(p)[0]
    assert r["control_arm"] == ("1" if _control_arm_tag("BTC", 3600.0)
                                else "0")
    assert r["control_arm"] in ("0", "1")   # never blank for a new row


def test_row_ts_used_for_the_tag_is_the_same_one_written_to_signal_ts(
        tmp_path):
    """The tag must key off the SAME timestamp the row's own signal_ts
    column carries - a divergent second clock read would make the tag
    unreproducible from the row's own recorded fields."""
    store, p = _store(tmp_path)
    store._append_row("c1", "ETH", "long", np.zeros(len(FEATURE_NAMES)),
                      0, 0.0, "candidate", signal_ts=777_000.0,
                      barrier="tb_sl")
    r = _read(p)[0]
    assert float(r["signal_ts"]) == 777_000.0
    assert r["control_arm"] == (
        "1" if _control_arm_tag("ETH", float(r["signal_ts"])) else "0")


def test_no_signal_ts_falls_back_to_append_time_consistently(
        tmp_path, monkeypatch):
    """signal_ts=None -> the row's `ts`/`signal_ts` columns both fall back
    to time.time(); the tag must use that SAME fallback value, not a
    second, later time.time() read."""
    import ml.history as history_mod
    monkeypatch.setattr(history_mod.time, "time", lambda: 42_000.0)
    store, p = _store(tmp_path)
    store._append_row("c1", "SOL", "long", np.zeros(len(FEATURE_NAMES)),
                      1, 0.0, "candidate", barrier="tb_pt")
    r = _read(p)[0]
    assert r["signal_ts"] == "42000"
    assert r["control_arm"] == ("1" if _control_arm_tag("SOL", 42_000.0)
                                else "0")


def test_row_stays_width_aligned(tmp_path):
    store, p = _store(tmp_path)
    store._append_row("c1", "BTC", "long", np.zeros(len(FEATURE_NAMES)),
                      1, 0.0, "candidate", signal_ts=1.0, barrier="tb_pt")
    with p.open(encoding="utf-8", newline="") as f:
        raw = list(csv.reader(f))
    assert len(raw[0]) == len(raw[1])
    assert raw[0][-1] == "control_arm"


# --- mixed old/new corpus loads cleanly -----------------------------------

def test_mixed_legacy_and_new_rows_load_cleanly(tmp_path):
    """A merged corpus (post-rotation-recovery) genuinely mixes rows that
    predate this column (blank control_arm) with rows written under it
    (real "0"/"1"). load_training_data must not crash, drop rows, or leak
    the tag into the feature matrix."""
    store, p = _store(tmp_path)
    store._append_row("new1", "BTC", "long", np.zeros(len(FEATURE_NAMES)),
                      1, 5.0, "live", signal_ts=1.0, barrier="tb_pt")
    header = store._header
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        legacy_row = ["legacy1", "ETH", "short",
                     *["0.000000"] * len(FEATURE_NAMES),
                     "0", "-2.00", "live", "1", "1", "tb_sl", "", "",
                     "", "5m", "triple_barrier_h432", "0.02", "0.01",
                     *["0.0000"] * 7, "0", "0", "", "", "", "", "", ""]
        assert len(legacy_row) == len(header), (
            "fixture drifted from the live schema width - update it")
        w.writerow(legacy_row)

    X, y, w_arr = store.load_training_data()
    assert X.shape[1] == len(FEATURE_NAMES)      # tag never leaks into X
    assert len(y) == 2 and len(w_arr) == 2

    rows = _read(p)
    by_id = {r["position_id"]: r for r in rows}
    assert by_id["legacy1"]["control_arm"] == ""       # UNKNOWN, never "0"
    assert by_id["new1"]["control_arm"] in ("0", "1")


def test_migrate_rows_pads_blank_never_backfills(tmp_path):
    """scripts/migrate_history.py must pad "" for a row that predates the
    column - NEVER compute a retroactive assignment, even though the
    function is deterministic and technically could: doing so would claim
    a legacy row was drawn under a control-arm design that did not exist
    at write time."""
    from scripts.migrate_history import migrate_rows
    src = tmp_path / "old.csv"
    old_feats = ["ret_1", "imbalance", "direction", "gate_confidence"]
    with open(src, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["position_id", "asset", "side", *old_feats,
                    "label", "net_pnl_usd", "source", "ts"])
        w.writerow(["p0", "BTC", "long", "0.1", "0.2", "1.0", "0.75",
                    "1", "5.00", "live", "1700000000"])
    rows, _padded = migrate_rows(str(src))
    store, _ = _store(tmp_path)
    idx = store._header.index("control_arm")
    assert rows[0][idx] == ""


def test_migrate_rows_passes_real_value_through_unchanged(tmp_path):
    """Idempotence precedent (same as every prior bump): migrating an
    ALREADY-current-schema file must pass a row's real "1"/"0" through
    unchanged, never re-derive or blank it."""
    from scripts.migrate_history import migrate_rows
    store, p = _store(tmp_path)
    store._append_row("p1", "BTC", "long", np.zeros(len(FEATURE_NAMES)),
                      1, 5.0, "live", signal_ts=3600.0, barrier="tb_pt")
    rows, padded = migrate_rows(str(p))
    assert padded == []
    idx = store._header.index("control_arm")
    expected = "1" if _control_arm_tag("BTC", 3600.0) else "0"
    assert rows[0][idx] == expected
