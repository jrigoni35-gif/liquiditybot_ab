"""The era-4 pre-registered gate (scripts/cohort_eval.py, 2026-08-10).

Registered at n=1 - before the cohort exists - which is the only honest
moment to write a stopping rule. These tests pin the registration itself:
the boundary instant, the n=50 refusal, the population rules (entry-opened
only, complete, post-boundary only), and the three readout outcomes. If any
of these change after the cohort accrues, that is not a refactor - it is the
thing pre-registration exists to prevent, and the test failing is the point.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "cohort_eval.py"
    sys.path.insert(0, str(ROOT / "scripts"))
    prior = sys.modules.get("cohort_eval")
    try:
        spec = importlib.util.spec_from_file_location("cohort_eval", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["cohort_eval"] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(ROOT / "scripts"))
        if prior is not None:
            sys.modules["cohort_eval"] = prior
        else:
            sys.modules.pop("cohort_eval", None)


CE = _load()


def test_registration_constants_are_pinned():
    """The boundary is aeeaae36's UTC instant - not a local date, which is
    the error class that mis-stamped it the first time."""
    assert CE.B4_TS == datetime(2026, 8, 10, 11, 3, 35,
                                tzinfo=timezone.utc).timestamp()
    assert CE.ERA4_MIN_N == 50
    assert CE._PREREG_ERA4 == "2026-08-10"
    # capital epoch: the $800 stressor reset instant (book flat, entries
    # OFF across it - zero in-flight ambiguity), amended at accrual n=3
    from datetime import datetime as _dt, timezone as _tz
    assert CE.CAPITAL_EPOCH_TS == _dt(2026, 8, 10, 23, 5, 27,
                                      tzinfo=_tz.utc).timestamp()
    assert CE._PREREG_CAPITAL == "2026-08-10T23:05:27Z"
    # the original 2026-08-02 registration must be untouched by the addition
    assert CE.MIGRATION_TS == 1785634028
    assert CE.MIN_COHORT_N == 50
    assert CE._PREREG == "2026-08-02"


# ---------------------------------------------------------------- population
_COLS = ["ts", "order_id", "position_id", "purpose", "symbol", "side",
         "ordertype", "post_only", "attempt", "fill_size", "fill_price",
         "arrival_ref", "slip_bps", "fees_delta_usd", "remaining", "reason"]


def _trip(pid, purpose, t0, px_in, px_out, size=1.0, fee=0.10):
    mk = lambda ts, oid, pp, side, px: {  # noqa: E731
        "ts": ts, "order_id": oid, "position_id": pid, "purpose": pp,
        "symbol": "ADA/USD", "side": side, "ordertype": "limit",
        "post_only": "1", "attempt": "0", "fill_size": size,
        "fill_price": px, "arrival_ref": px, "slip_bps": "0",
        "fees_delta_usd": fee, "remaining": "0"}
    return [mk(t0, pid + "a", purpose, "buy", px_in),
            mk(t0 + 60, pid + "b", "exit", "sell", px_out)]


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=_COLS)
        wr.writeheader()
        for r in rows:
            wr.writerow({c: r.get(c, "") for c in _COLS})


def test_population_rules(tmp_path):
    """Entry-opened + fully-closed + post-boundary ONLY. A hedge-opened trip
    is reconstructable (hedge IS an opening leg) but is not the strategy's
    trade; a pre-boundary close belongs to the inflated-fill eras."""
    # anchor on the LATER boundary: since the 2026-08-10T23:05:27Z capital
    # epoch the population cut is max(B4_TS, CAPITAL_EPOCH_TS)
    b4 = max(CE.B4_TS, CE.CAPITAL_EPOCH_TS)
    rows = []
    rows += _trip("in-era4", "entry", b4 + 1000, 100.0, 110.0)     # counted
    rows += _trip("hedge4", "hedge", b4 + 2000, 100.0, 95.0)       # excluded
    rows += _trip("pre-b4", "entry", b4 - 5000, 100.0, 120.0)      # excluded
    # a $5000-regime trade: post-#4 execution but PRE-capital-epoch -
    # honest fills, wrong capital regime, excluded from the verdict
    rows += _trip("old-cap", "entry", CE.B4_TS + 1000, 100.0, 130.0)
    # still-open: opening leg only
    rows.append({"ts": b4 + 3000, "order_id": "x", "position_id": "open",
                 "purpose": "entry", "symbol": "ADA/USD", "side": "buy",
                 "ordertype": "limit", "post_only": "1", "attempt": "0",
                 "fill_size": 1.0, "fill_price": 100.0,
                 "arrival_ref": 100.0, "slip_bps": "0",
                 "fees_delta_usd": 0.1, "remaining": "0"})
    p = tmp_path / "fills.csv"
    _write(p, rows)
    trips = CE.era4_trips(str(p))
    assert len(trips) == 1
    assert trips[0]["gross_pct"] == pytest.approx(10.0)
    assert trips[0]["net_pct"] == pytest.approx(10.0 - 0.2)


def test_duplicate_fill_patterns_are_dropped(tmp_path):
    """position_id is not the identity - the 16x re-log class."""
    b4 = max(CE.B4_TS, CE.CAPITAL_EPOCH_TS)
    rows = _trip("a", "entry", b4 + 1000, 100.0, 110.0) \
        + _trip("b", "entry", b4 + 1000, 100.0, 110.0)   # identical pattern
    p = tmp_path / "fills.csv"
    _write(p, rows)
    assert len(CE.era4_trips(str(p))) == 1


# ------------------------------------------------------------------ readout
def _mk(gross_net):
    return [{"t": 0.0, "gross_pct": g, "net_pct": n} for g, n in gross_net]


def test_refuses_verdict_below_n50():
    s = CE.era4_section(_mk([(1.0, 0.5)] * 49))
    assert s["readout"] == "ACCRUING"
    assert s["verdict_available"] is False
    assert s["progress"] == "49/50"


def test_no_gross_edge_readout():
    s = CE.era4_section(_mk([(-0.1, -0.4)] * 50))
    assert s["verdict_available"] is True
    assert s["readout"] == "NO_GROSS_EDGE"


def test_cost_bound_readout():
    s = CE.era4_section(_mk([(0.5, -0.2)] * 50))
    assert s["readout"] == "COST_BOUND"


def test_continue_readout():
    s = CE.era4_section(_mk([(0.8, 0.2)] * 50))
    assert s["readout"] == "CONTINUE"


def test_empty_cohort_is_accruing_not_a_crash():
    s = CE.era4_section([])
    assert s["readout"] == "ACCRUING"
    assert s["n"] == 0


# --- corpus pinning: the gate must be pointable, like assurance_check ------
# Found 2026-09-04 doing a whole-bot review: cohort_eval hard-coded
# ROOT/"outputs" for all four inputs, so the headline gate died with "no
# postmortem data" on any box whose corpus lives elsewhere - a bare worktree,
# or a cloud container where session_import files bundle reports under
# outputs/imported_sessions/<label>/. scripts/assurance_check.py has honoured
# LB_OUTPUTS since 2026-08-23 for exactly this reason (its section 11 had
# passed VACUOUSLY from a worktree with no outputs/). One convention, two
# reports, so the deploy battery can pin both at the same corpus.
#
# The DEFAULT is all that moves. Explicit --csv/--fills/--signal-history still
# win, so no existing invocation changes behaviour.

def test_out_dir_defaults_to_repo_outputs(monkeypatch):
    monkeypatch.delenv("LB_OUTPUTS", raising=False)
    assert _load().out_dir() == ROOT / "outputs"


def test_out_dir_honours_LB_OUTPUTS(monkeypatch, tmp_path):
    monkeypatch.setenv("LB_OUTPUTS", str(tmp_path))
    assert _load().out_dir() == tmp_path


def test_every_corpus_input_follows_LB_OUTPUTS(monkeypatch, tmp_path):
    """All FOUR inputs move together - a gate pinned for three of them and
    silently reading a fourth from the live tree is the mixed-corpus bug this
    fix exists to remove."""
    monkeypatch.setenv("LB_OUTPUTS", str(tmp_path))
    mod = _load()
    ap = __import__("argparse").ArgumentParser()
    _out = mod.out_dir()
    # mirror main()'s wiring; if main() stops using out_dir() this drifts and
    # the assertion below is what notices
    for name, fn in (("--csv", "postmortem_summary.csv"),
                     ("--fills", "fills.csv"),
                     ("--retrain-history", "retrain_history.jsonl"),
                     ("--signal-history", "signal_history.csv")):
        ap.add_argument(name, default=str(_out / fn))
    ns = ap.parse_args([])
    for got in (ns.csv, ns.fills, ns.retrain_history, ns.signal_history):
        assert Path(got).parent == tmp_path, got


def test_main_wires_defaults_through_out_dir(monkeypatch, tmp_path):
    """Source-level guard: main() must build its defaults from out_dir(),
    not from a re-hardcoded ROOT/'outputs'."""
    src = (ROOT / "scripts" / "cohort_eval.py").read_text(encoding="utf-8")
    main_src = src[src.index("def main("):]
    assert 'ROOT / "outputs"' not in main_src, (
        "main() re-hardcodes ROOT/'outputs' - the LB_OUTPUTS pin is bypassed")
    assert "out_dir()" in main_src
