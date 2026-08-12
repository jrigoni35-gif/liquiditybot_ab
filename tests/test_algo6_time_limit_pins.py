"""ALGO-6 pins: the hard time-limit machinery EXISTS - keep it that way.

The Grand Synthesis verification sweep found that both halves of the
engineering world's convergent fix for holding-time asymmetry are already
deployed here: the bracket deadline fires a FULL close at label_max_bars
regardless of P&L (tb_time - hummingbot's time-limit barrier, main.py), and
PT-060's no-progress scratch covers the no-early-MFE cohort with LOCAL
evidence (measured MFE 0.16% vs MAE -1.44%, recovered 0/17). The
adjudicated package therefore ships PINS, not duplicates - a second
time-exit path beside these would be the two-paths-one-quantity defect.
The time-DECAY ladder (required profit decaying with age) is deliberately
deferred to the ALGO-5 replay amendment: its parameters come from data,
and freqtrade's own tracker documents aggressive decay tables reproducing
the exact near-TP/far-SL geometry they exist to fix.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src():
    return (ROOT / "main.py").read_text(encoding="utf-8")


def test_tb_time_fires_a_full_close():
    """The deadline exit is 100% of the position, P&L-blind - the hard cap
    that structurally bounds loser holding time."""
    src = _src()
    assert 'self._submit_exit(pos, 100.0, "tb_time"' in src, (
        "the bracket deadline no longer fires a full close - ALGO-6's hard "
        "time-limit is gone")


def test_deadline_maturity_is_per_position_not_global():
    """A bracket matures on ITS OWN deadline (bracket_deadline_ts), never on
    a global clock - the property that makes the time-limit a per-trade
    barrier rather than a portfolio sweep."""
    src = _src()
    assert "bracket_deadline_ts" in src
    tree = ast.parse(src)
    cmps = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)
            and "bracket_deadline_ts" in ast.dump(n)]
    assert cmps, "no comparison against bracket_deadline_ts found"


def test_pt060_time_stop_is_configured_and_documented():
    """PT-060 covers the no-early-progress cohort with local evidence; its
    config block must stay present and carry that evidence."""
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    ts = cfg["profit_taking"]["time_stop"]
    assert isinstance(ts, dict) and ts, "PT-060 time_stop block missing"
    doc = ts.get("_doc", "")
    assert "recovered" in doc and "MFE" in doc, (
        "the time_stop _doc no longer carries its own local evidence - the "
        "justification must travel with the knob")


def test_no_second_time_exit_path_appeared():
    """Exactly ONE tb_time SUBMIT site: a duplicate time-exit path is the
    two-paths-one-quantity defect this package refuses to introduce.

    Pinned on the submit call, not the raw string - main.py legitimately
    mentions tb_time six times (comments, the label-era membership tuple,
    and the bracket_backstop reason-threading at log_close), and a raw
    count over those is exactly the truncated-evidence mistake this test's
    own first version made (its <=4 threshold came from a head-cut grep
    and failed battery 16 against reality)."""
    assert _src().count('self._submit_exit(pos, 100.0, "tb_time"') == 1, (
        "the bracket-deadline submit site count changed - verify no "
        "parallel time-exit path was added (or the one path was removed)")
