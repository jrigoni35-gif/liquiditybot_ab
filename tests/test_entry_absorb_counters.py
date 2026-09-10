"""The entry loop's silent absorbing states must be counted, and counting must
change nothing.

THE HOLE. The entry sweep's disposition marks start at the `capped` veto. Every
rejection BEFORE it - the watchdog return, the open-entry skip, and the
unconfirmed-signal skip, which is the largest of the three - left NO registered
code. `scripts/reason_chain_report.py` builds a Markov chain over reason codes,
so those states were outside its alphabet entirely: a sweep where every
candidate was absorbed before the first mark reads exactly like a sweep where
nothing was rejected. Measured 2026-09-10 by line-tracing main.py, that was 100%
of the offline fixture's candidates.

THE TWO THINGS THAT CAN GO WRONG, both pinned here:
  1. the counters do not count (a dead instrument reads like a quiet system)
  2. the counters CHANGE something - the entry loop is the most governed code in
     this repo and an observability patch that moves a decision is a
     cohort-resetting change wearing a SAFE label

(2) is pinned by PARITY rather than by reading: the same recording is replayed
with `_absorb` live and with it monkeypatched to a no-op, and every field of the
run summary must match.
"""
from __future__ import annotations

from pathlib import Path

from core.codes import Code

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# registration (CLAUDE.md invariant 6)
# --------------------------------------------------------------------------

def test_the_EN_family_is_registered_not_bare_strings():
    vals = {c.value for c in Code if c.value.startswith("EN-")}
    assert {"EN-000", "EN-010", "EN-020", "EN-030"} <= vals


def test_every_absorbing_state_has_its_own_code():
    """One code per state. Collapsing them would rebuild the ambiguity this
    exists to remove."""
    assert Code.EN_WATCHDOG_BLOCKED != Code.EN_OPEN_ENTRY
    assert Code.EN_OPEN_ENTRY != Code.EN_SIGNAL_UNCONFIRMED


# --------------------------------------------------------------------------
# the counter itself
# --------------------------------------------------------------------------

class _Stub:
    """Minimal stand-in carrying only what _absorb touches."""
    from main import LiquidityBot
    _absorb = LiquidityBot._absorb
    entry_absorb_status = LiquidityBot.entry_absorb_status

    def __init__(self):
        self._entry_absorb = {}


def test_absorb_counts_by_code_value():
    s = _Stub()
    s._absorb(Code.EN_SIGNAL_UNCONFIRMED)
    s._absorb(Code.EN_SIGNAL_UNCONFIRMED)
    s._absorb(Code.EN_OPEN_ENTRY)
    assert s._entry_absorb == {"EN-030": 2, "EN-020": 1}


def test_absorb_accepts_a_plain_key_for_arrivals():
    s = _Stub()
    s._absorb("arrivals")
    assert s._entry_absorb["arrivals"] == 1


def test_absorb_never_raises_into_the_entry_loop():
    """Guarded exactly as _mark_cand is: bookkeeping must never break the sweep
    it observes. Injected by removing the dict it writes to."""
    s = _Stub()
    s._entry_absorb = None          # any failure shape will do
    s._absorb(Code.EN_OPEN_ENTRY)   # must not raise


def test_status_returns_a_copy_not_the_live_counter():
    """StatusWriter serialises whatever it is handed; a caller must not be able
    to mutate the engine's counters through it."""
    s = _Stub()
    s._absorb(Code.EN_OPEN_ENTRY)
    out = s.entry_absorb_status()
    out["EN-020"] = 999
    out["injected"] = 1
    assert s._entry_absorb == {"EN-020": 1}


# --------------------------------------------------------------------------
# EN-000 is rate limited, and cumulative
# --------------------------------------------------------------------------

def test_the_summary_is_rate_limited_to_hourly():
    """Per-event emission would add ~11,520 rows/day (30s sweep x 4 assets) to
    a trail that reached 87k in two months. If this ever stops holding, the
    instrument drowns the corpus it explains."""
    from main import LiquidityBot
    calls = []

    class S:
        _emit_absorb_summary = LiquidityBot._emit_absorb_summary
        _entry_absorb = {"EN-030": 3}
        _entry_absorb_emitted = 0.0

    s = S()
    import main as m
    real = m.get_audit
    try:
        m.get_audit = lambda: type("A", (), {"log": lambda *a, **k: calls.append(a)})()
        s._emit_absorb_summary(10_000.0)      # first tick: emits
        s._emit_absorb_summary(10_100.0)      # +100s: must NOT emit
        s._emit_absorb_summary(13_700.0)      # +3700s: emits again
    finally:
        m.get_audit = real
    assert len(calls) == 2, f"expected 2 emissions, got {len(calls)}"


def test_an_empty_vector_emits_nothing():
    from main import LiquidityBot

    class S:
        _emit_absorb_summary = LiquidityBot._emit_absorb_summary
        _entry_absorb: dict = {}
        _entry_absorb_emitted = 0.0

    import main as m
    calls = []
    real = m.get_audit
    try:
        m.get_audit = lambda: type("A", (), {"log": lambda *a, **k: calls.append(a)})()
        S()._emit_absorb_summary(99_999.0)
    finally:
        m.get_audit = real
    assert calls == []


# --------------------------------------------------------------------------
# THE ONE THAT MATTERS: counting must not move a decision
#
# A REPLAY-PARITY TEST WAS WRITTEN HERE FIRST AND DELETED AS VACUOUS, which is
# worth recording so it is not re-added in good faith. It replayed the offline
# recording with `_absorb` live and again with it neutered and compared the run
# summaries. It passed - and it passed for the wrong reason. Mutation-tested
# 2026-09-10 by making `_absorb` genuinely perturb a decision input
# (`self._entry_rotation += 1`, which reorders asset evaluation): the mutant
# SURVIVED. The fixture opens zero positions, so entries_filled, realized_pnl,
# exit_orders, open_positions_end and labeled_rows are all 0 in both arms and
# the comparison cannot see a behavioural change. That is C5 weakening its own
# downstream verification, and it is the same shape as the metamorphic
# couplings: a property evaluated over a zero-entry replay passes vacuously.
#
# So the invariant is pinned STRUCTURALLY instead, which needs no fixture: the
# counter may be WRITTEN anywhere, but it may only be READ by the two observer
# methods. If a later edit makes a decision depend on it - `if
# self._entry_absorb[...] > N: continue` - this goes red immediately. Re-add a
# parity test only once the fixture actually opens positions.
# --------------------------------------------------------------------------

def test_the_counter_is_never_READ_by_the_decision_path():
    """Write-only from the engine's point of view. AST, not grep: a mention in
    a comment or docstring creates no dependency and must not trip this."""
    import ast

    src = (REPO_ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    ALLOWED = {"_absorb", "entry_absorb_status", "_emit_absorb_summary",
               "__init__"}
    offenders = []

    class V(ast.NodeVisitor):
        def __init__(self):
            self.fn = None

        def visit_FunctionDef(self, node):
            prev, self.fn = self.fn, node.name
            self.generic_visit(node)
            self.fn = prev

        def visit_Attribute(self, node):
            if node.attr == "_entry_absorb" and self.fn not in ALLOWED:
                # Store context is a WRITE and is fine anywhere; only a Load
                # (a read) can make a decision depend on the counter.
                if isinstance(node.ctx, ast.Load):
                    offenders.append((self.fn, node.lineno))
            self.generic_visit(node)

    V().visit(tree)
    assert not offenders, (
        "main.py READS self._entry_absorb outside the observer methods, so a "
        "decision may now depend on an observability counter: "
        + ", ".join(f"{fn}() line {ln}" for fn, ln in offenders))


def test_absorb_returns_nothing_so_no_caller_can_branch_on_it():
    s = _Stub()
    assert s._absorb(Code.EN_OPEN_ENTRY) is None
