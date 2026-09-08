"""Pins for the second batch of verified 2026-09-05 findings (S2, S3, S8-S16).

All SAFE: measurement, observability and honesty fixes. Nothing here changes
which orders are placed or how they fill. Mutation-verified.

  S2   ml/history.py                 1-second .bak name clobbered the prior
                                     rotation; ns+pid makes it unique.
  S3   runner.py                     prune ran ONCE at __init__.
  S8   fee_anatomy / cost_attribution defaulted to 40/80 - not a published
                                     Kraken row, ~2x the booked 22/38.
  S9   test_hard_invariants /        permanent files claimed the router is on
       venue_adapters                the LIVE path (it is not) and that the
                                     rule is subclass-proof (it is not).
  S10  core/fill_ledger.py           dedup disarmed SILENTLY on a read failure.
  S11  scripts/smoke_test.py         DoD gate sized Kelly at the retired 25/40.
  S13  scripts/outputs_gc.py         "git failed" read as "0 references".
  S14  cohort_eval / ground_truth /  label era was a literal in 3 consumers.
       defensive_cadence
  S15  risk/protocols.py             anchor skip silent; board could not tell a
                                     DEAD guard from a healthy day.
  S16  scripts/pc_supervisor.py      IsProcessInJob had NEVER once succeeded
                                     (13/13 failures in the live log).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ S13
def test_git_failure_is_not_read_as_zero_references(tmp_path):
    """THE FAIL-OPEN THAT MOVED DATA. On a non-git root `git grep` exits 128
    with empty stdout, which the old code rendered as [] - "nothing references
    this, safe to collect". Measured: {'moved': 1, 'bytes_freed': 31}.
    The function already failed closed for the EXCEPTION path two lines up."""
    from scripts.outputs_gc import reachable
    refs = reachable("signal_history.csv", tmp_path)      # tmp_path is not a repo
    assert refs != [], (
        "a non-git root produced '0 references' - a referenced corpus file "
        "would be archived")
    assert "git unavailable" in " ".join(refs)


def test_a_real_no_match_is_still_a_real_no_match():
    """ANTI-RUBBER-STAMP: rc=1 is git successfully reporting no matches. If
    that also fails closed, nothing is ever collectable and the tool is inert."""
    import uuid
    from scripts.outputs_gc import reachable
    # RUNTIME-BUILT NEEDLE. The first draft used a literal string - which then
    # appeared in exactly one tracked file: this test. It passed only while the
    # file was untracked and self-matched the moment it was committed
    # (2026-09-06). A needle that exists in no file cannot be written into one.
    needle = "no-such-file-" + uuid.uuid4().hex
    refs = reachable(needle, ROOT)
    assert refs == [], f"a genuine no-match failed closed: {refs}"


# ------------------------------------------------------------------- S2
def test_same_second_rotations_do_not_clobber(tmp_path, monkeypatch):
    """Two schema rotations inside one second shared a .bak name and the
    second os.replace overwrote the first - while the log said "old file kept
    at ..." BOTH times. A second writer to this corpus is documented, not
    hypothetical (scripts/corpus_sync.py:176)."""
    import ml.history as H

    monkeypatch.setattr(time, "time", lambda: 1_788_664_596.0)   # frozen clock
    p = tmp_path / "signal_history.csv"

    made = []
    for i in range(3):
        p.write_text(f"col_{i}\nrow{i}\n", encoding="utf-8")
        st = H.HistoryStore(path=str(p))
        st._header = [f"different_{i}"]
        try:
            st._ensure_schema()
        except Exception:
            pass
        made += [q for q in tmp_path.glob("*.bak_*") if q not in made]

    baks = sorted(tmp_path.glob("*.bak_*"))
    assert len(baks) >= 2, (
        f"rotations under a FROZEN clock produced {len(baks)} backup(s) - the "
        f"name is still second-resolution and one corpus overwrote another")
    bodies = {q.read_text(encoding="utf-8") for q in baks}
    assert len(bodies) >= 2, "backups exist but hold identical content"


# ------------------------------------------------------------------- S3
def test_recording_prune_has_a_call_site_outside_init():
    """AST pin. The only prune_recordings call lived in BotRunner.__init__, so
    a process that stays up never pruned again - and on a box restarting every
    ~27s the opposite harm appeared: ~1.3 days of recording history evicted per
    9 minutes, because retention counts SESSIONS."""
    import ast
    tree = ast.parse((ROOT / "runner.py").read_text(encoding="utf-8"))
    # The enclosing function must be neither __init__ NOR the helper itself.
    # The first draft of this pin accepted any site outside __init__, which
    # `_prune_recordings_now`'s own body satisfies - so it passed with the
    # cadence call deleted. Caught by mutation 2026-09-06.
    callers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and \
                node.name not in ("__init__", "_prune_recordings_now"):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    name = (getattr(sub.func, "attr", None)
                            or getattr(sub.func, "id", None))
                    if name in ("prune_recordings", "_prune_recordings_now"):
                        callers.append((node.name, sub.lineno))
    assert callers, (
        "recording retention has no CADENCE caller - it is reachable only "
        "from __init__ (and its own helper), so it runs once per process and "
        "never again")


def test_prune_is_fail_soft_without_recording():
    """A runner constructed with no recording config must not raise."""
    import runner as R
    r = R.BotRunner.__new__(R.BotRunner)
    r._rec_prune_args = None
    r._prune_recordings_now(time.time())          # must not raise


# ------------------------------------------------------------------- S8
def test_cost_tools_read_the_BOOKED_schedule_not_a_fictional_row():
    """40/80 is not a row Kraken publishes at ANY volume (the live schedule is
    25/40, 20/35, 14/24, 12/22 ... 0/5) and is ~2x the booked 22/38. Every
    'VENUE-TRUE' figure these tools emitted was inflated: median 120.85 ->
    60.41 bps, aggregate $775.84 -> $371.38."""
    import scripts.cost_attribution as ca
    import scripts.fee_anatomy_report as far
    pt = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["pretrade"]
    for mod in (far, ca):
        assert mod.KRAKEN_T1_MAKER_BPS == float(pt["maker_fee_bps"])
        assert mod.KRAKEN_T1_TAKER_BPS == float(pt["taker_fee_bps"])
        assert (mod.KRAKEN_T1_MAKER_BPS,
                mod.KRAKEN_T1_TAKER_BPS) != (40.0, 80.0), \
            "still defaulting to the fictional 40/80 row"


def test_the_cost_tool_fallback_is_a_PUBLISHED_row():
    """If config is unreadable the fallback must be a row that EXISTS. Over-
    stating cost with a real row is conservative; a fictional row is not
    conservative, it is just wrong."""
    from core.venue_fees import is_a_published_row, worst_row
    import scripts.fee_anatomy_report as far
    from scripts.fee_anatomy_report import _booked_fees
    # UNREADABLE CONFIG -> the fallback. (The 09-06 version of this pin
    # asserted a literal 25/40 - the legacy ladder's bottom row - which the
    # 2026-09-08 schedule correction rightly reddened: pin the PROPERTY.)
    _orig = far.json.loads
    far.json.loads = lambda *_a, **_k: (_ for _ in ()).throw(ValueError("planted"))
    try:
        fb = _booked_fees()
    finally:
        far.json.loads = _orig
    assert is_a_published_row(*fb), f"fallback row {fb} is not on the schedule"
    assert fb == worst_row(), "fallback must be the venue's worst row, derived"
    # DERIVED, not a literal - this pin hardcoded (22.0, 38.0) in the very
    # batch whose lesson was "derive, don't hardcode", and cut #10's fee
    # correction to 20/35 reddened it the next day. The property is that the
    # tool reads what the BOOK says, whatever the book says.
    pt = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["pretrade"]
    assert _booked_fees() == (float(pt["maker_fee_bps"]), float(pt["taker_fee_bps"]))


# ------------------------------------------------------------------ S14
def test_no_consumer_hardcodes_the_label_era():
    """The era selects which rows the cohort gate - the number the project
    waits on - may even see. Three consumers spelled it out while two others
    already derived it correctly."""
    import re
    bad = []
    for rel in ("scripts/cohort_eval.py", "scripts/ground_truth_metrics.py",
                "scripts/defensive_cadence_report.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        for i, line in enumerate(src.splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or s.startswith("*"):
                continue                       # prose/comments may name it
            if re.search(r'["\']triple_barrier_h\d+["\']', line):
                bad.append(f"{rel}:{i}")
    assert not bad, f"label era still hardcoded at {bad}"


def test_the_derived_era_matches_the_shipped_config():
    """ANTI-RUBBER-STAMP: deriving to the WRONG value would silently re-cut
    every era-filtered report."""
    from scripts.cohort_eval import CURRENT_LABEL_ERA
    from scripts.defensive_cadence_report import H432
    from scripts.ground_truth_metrics import CURRENT_LABEL_ERA as GTM
    n = int(json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
            ["ml"]["label_max_bars"])
    want = "triple_barrier" if n == 96 else f"triple_barrier_h{n}"
    assert CURRENT_LABEL_ERA == H432 == GTM == want


# ------------------------------------------------------------------ S10
def test_fill_ledger_dedup_failure_is_logged(tmp_path, caplog):
    """A read failure left the key cache EMPTY - indistinguishable from "no
    rows yet" - so a replayed fill re-landed in realized P&L with ZERO output.
    The append path in the same file logs its OSError; this one did not."""
    import logging

    import core.fill_ledger as FL
    before = FL.dedup_disarmed
    missing = tmp_path / "nope" / "fills.csv"       # parent does not exist
    with caplog.at_level(logging.ERROR):
        keys = FL._load_keys(missing)
    # cut #10 (B5): the failure returns None ("unknown"), never an empty set
    # ("clean") - the append path then scans directly or refuses.
    assert keys is None
    assert FL.dedup_disarmed == before + 1, "the disarm was not counted"
    assert caplog.records, "dedup disarmed with no log record at all"


# ------------------------------------------------------------------ S15
def test_a_nonfinite_equity_anchor_skip_is_visible(caplog):
    """The every-cycle hot path skipped the anchor roll with no return, no log
    and no reason code, while the status triple stayed byte-identical to a
    healthy day."""
    import logging

    from risk.protocols import RiskProtocolStack
    rp = RiskProtocolStack({})
    with caplog.at_level(logging.WARNING):
        rp.observe(float("nan"))
    assert rp.anchor_skips == 1, "the skip was not counted"
    assert caplog.records, "anchors stopped rolling with no log record"


def test_a_healthy_equity_does_not_count_a_skip():
    """ANTI-RUBBER-STAMP: counting every cycle would make the signal useless."""
    from risk.protocols import RiskProtocolStack
    rp = RiskProtocolStack({})
    rp.observe(10_000.0)
    assert rp.anchor_skips == 0


# ------------------------------------------------------------------ S16
def test_is_process_in_job_actually_answers():
    """13 of 13 occurrences in outputs/pc_supervisor.log (631,479 B,
    2026-07-15 -> 2026-09-05) were 'unknown (IsProcessInJob failed)' - ZERO
    successes ever, because ctypes truncated the -1 pseudo-handle to a C int
    without argtypes. NOTE this reports the CALLING process's job."""
    import sys
    from scripts.pc_supervisor import _job_status
    r = _job_status()
    if sys.platform != "win32":
        assert "n/a" in r
        return
    assert "IsProcessInJob failed" not in r, (
        f"the job query still cannot answer: {r!r}")


# ------------------------------------------------------------------- S9
def test_permanent_files_do_not_claim_the_router_is_on_the_live_path():
    """`import runner, main` succeeds with execution.venue_adapters
    un-importable; `.route(` appears repo-wide only in tests; audit.jsonl
    carries ZERO VN- codes. The header said "(LIVE PATH)" anyway."""
    src = (ROOT / "tests/test_hard_invariants.py").read_text(encoding="utf-8")
    assert "INVARIANT #3 (LIVE PATH)" not in src, (
        "a permanent file still claims the router section covers the live path")
    assert "ADAPTER CONTRACT" in src


def test_venue_adapters_does_not_claim_subclass_immunity():
    """A plain @property cannot be made un-overridable in Python; a LiarAdapter
    overriding it reached the wire."""
    src = (ROOT / "execution/venue_adapters.py").read_text(encoding="utf-8")
    assert "impossible to bypass by subclassing" not in src


def test_the_router_STILL_refuses_a_non_kraken_venue():
    """ANTI-RUBBER-STAMP: correcting the CLAIM must not weaken the RULE. Every
    adapter that does not override the property is still held to kraken-only."""
    from execution.venue_adapters import VenueAdapter
    a = VenueAdapter.__new__(VenueAdapter)
    a.enabled = True
    a.can_be_execution_eligible = True
    a.name = "binanceus"
    assert a.execution_eligible is False
    a.name = "kraken"
    assert a.execution_eligible is True


# ------------------------------------------------------------------ S11
def test_no_bare_position_sizer_construction_outside_tests():
    """AST pin. The single bare `PositionSizer(` outside tests/ meant a DoD
    gate sized Kelly at the retired 25/40 while live books 22/38. Injecting
    22/38 keeps smoke green (220/0); injecting 40/80 REDS it on SZ-030 - the
    gate is live, it was just aimed at the wrong manifold."""
    import ast
    bad = []
    for py in ROOT.glob("scripts/*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and \
                    getattr(node.func, "id", None) == "PositionSizer":
                kw = {k.arg for k in node.keywords}
                if "pretrade_cfg" not in kw and len(node.args) < 4:
                    bad.append(f"{py.name}:{node.lineno}")
    assert not bad, (
        f"PositionSizer built without a cost block at {bad} - it falls back "
        f"to the retired 25/40 schedule")


def test_the_false_breakeven_literal_is_not_asserted_anywhere():
    """0.632 was never what that construction computed - it gave 0.6902 the day
    the comment was written (86c62fd8). Wrong when written, not merely stale.
    The number may still be NAMED in a warning; it may not be ASSERTED."""
    src = (ROOT / "scripts/smoke_test.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        if "0.632" in line:
            assert ("never" in line or "NO LITERAL" in line
                    or "wrong" in line.lower()), \
                f"smoke_test.py:{i} still asserts 0.632 as a real breakeven"
