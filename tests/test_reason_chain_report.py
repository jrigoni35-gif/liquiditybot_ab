"""Pins for scripts/reason_chain_report.py — shipped UNPINNED, which is the
finding as much as anything in it.

ec08c3e9 landed a 410-line statistical instrument with zero tests, in a session
whose three sibling instruments (regime_chain_report, order_chain_report,
audit_quarantine) carry 25, 17 and 13 pins each. CLAUDE.md is explicit: "New
behavior gets a test in the same commit." It did not.

That matters more than usual for THIS file. It is a measurement instrument, and
this repo's own standing orientation is that the measurement plane is the
least-governed code in the tree - "the code that tells you whether the governed
code works is the code nothing governs". An unpinned chi-square is exactly that
shape: it cannot fail loudly, it can only be quietly wrong.

THE PIN THAT MATTERS MOST is the vacuity control. `markov_information_test`
exists to answer "does knowing the current code tell you anything about the
next one", and its own docstring names the failure it guards: "a chain whose
rows all match the pooled distribution is a histogram wearing a matrix's
clothes". So the tests below feed it exactly that - a chain built so every row
EQUALS the pooled successor distribution - and require it to report NOT
informative. A test that only fed it real data could never separate "the
instrument works" from "the instrument always says yes".
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.reason_chain_report import (  # noqa: E402
    MIN_EXITS_FOR_RATES, _wilson, load_transitions, markov_information_test,
    registered_codes, steady_state)


# --------------------------------------------------------------------------
# Wilson interval
# --------------------------------------------------------------------------

def test_wilson_on_no_observations_is_not_a_claim():
    assert _wilson(0, 0) == (0.0, 0.0)


def test_wilson_brackets_the_point_estimate():
    lo, hi = _wilson(30, 100)
    assert lo < 0.30 < hi
    assert 0.0 <= lo and hi <= 1.0


def test_wilson_narrows_as_n_grows():
    """The whole reason to use an interval: more evidence, tighter claim."""
    w_small = _wilson(3, 10)
    w_big = _wilson(300, 1000)
    assert (w_big[1] - w_big[0]) < (w_small[1] - w_small[0])


def test_wilson_stays_inside_the_unit_interval_at_the_edges():
    """A naive normal interval goes negative at k=0 and past 1 at k=n. Wilson
    is chosen precisely so a rate at the boundary is still reportable.

    NOTE the tolerance on the upper edge: _wilson(20, 20) returns
    0.9999999999999998, not 1.0. Asserting equality there is a float trap, and
    the first cut of this test fell into it."""
    lo, hi = _wilson(0, 20)
    assert lo == 0.0 and 0.0 < hi < 1.0
    lo, hi = _wilson(20, 20)
    assert 0.0 < lo < 1.0 and hi <= 1.0 and hi > 0.99


# --------------------------------------------------------------------------
# THE VACUITY CONTROL
# --------------------------------------------------------------------------

def _uninformative_chain(n_per_row: int = 200):
    """Every row IS the pooled distribution: successors are independent of the
    current state. A transition matrix in shape, a histogram in fact."""
    pooled = {"B": 0.5, "C": 0.3, "D": 0.2}
    trans, exits = {}, Counter()
    for a in ("X", "Y", "Z"):
        trans[a] = Counter({b: int(p * n_per_row) for b, p in pooled.items()})
        exits[a] = sum(trans[a].values())
    return trans, exits


def _informative_chain(n_per_row: int = 200):
    """Each state has a strongly preferred successor - knowing where you are
    genuinely tells you where you go."""
    rows = {"X": {"B": 190, "C": 5, "D": 5},
            "Y": {"B": 5, "C": 190, "D": 5},
            "Z": {"B": 5, "C": 5, "D": 190}}
    trans = {a: Counter(v) for a, v in rows.items()}
    exits = Counter({a: sum(v.values()) for a, v in rows.items()})
    return trans, exits


def test_a_histogram_wearing_a_matrix_is_reported_as_UNINFORMATIVE():
    """THE control. If this ever passes as informative the instrument is
    asserting structure that is not there, which is worse than silence."""
    trans, exits = _uninformative_chain()
    res = markov_information_test(trans, exits)
    assert res.get("applicable") is True
    assert res.get("codes_tested", 0) > 0, (
        "nothing was tested, so 'not informative' proves nothing - that is the "
        "broken-scan reading, not the null reading")
    assert res.get("codes_informative") == 0, (
        f"rows identical to the pooled distribution were reported as "
        f"informative: {res.get('top')}")


def test_a_genuinely_state_dependent_chain_IS_detected():
    """The other half of the control. Without this, a test suite that only
    checked the null case would pass on an instrument hard-wired to say no."""
    trans, exits = _informative_chain()
    res = markov_information_test(trans, exits)
    assert res.get("codes_informative", 0) == 3, (
        f"a chain where each state has a 95% preferred successor was not "
        f"detected as informative - the test cannot distinguish signal: {res}")
    assert "CARRIES information" in res.get("verdict", "")


def test_thin_rows_are_not_tested_rather_than_tested_badly():
    """Below MIN_EXITS_FOR_RATES a chi-square on a handful of counts is noise.
    The instrument must DECLINE, not guess."""
    trans = {"X": Counter({"B": 2, "C": 1})}
    exits = Counter({"X": 3})
    assert 3 < MIN_EXITS_FOR_RATES
    res = markov_information_test(trans, exits)
    assert res.get("codes_tested", 0) == 0
    assert not res.get("codes_informative")


def test_an_empty_corpus_is_declared_inapplicable_not_answered():
    res = markov_information_test({}, Counter())
    assert res.get("applicable") is False


# --------------------------------------------------------------------------
# steady state
# --------------------------------------------------------------------------

def test_steady_state_is_a_distribution():
    trans, exits = _informative_chain()
    ss = steady_state(trans, exits)
    assert ss, "no steady state returned for a well-formed chain"
    assert abs(sum(ss.values()) - 1.0) < 1e-6, f"does not sum to 1: {sum(ss.values())}"
    assert all(v >= 0.0 for v in ss.values())


def test_steady_state_on_an_empty_chain_is_empty_not_a_crash():
    assert steady_state({}, Counter()) == {}


def test_steady_state_favours_the_absorbing_direction():
    """A chain that funnels into D must put more long-run mass on D than on a
    state nothing points at."""
    trans = {"X": Counter({"D": 100}), "D": Counter({"D": 100})}
    exits = Counter({"X": 100, "D": 100})
    ss = steady_state(trans, exits)
    assert ss.get("D", 0.0) > ss.get("X", 0.0)


# --------------------------------------------------------------------------
# corpus handling
# --------------------------------------------------------------------------

def test_registered_codes_is_not_empty_and_holds_real_codes():
    """If this ever returns empty, every 'unregistered code' judgement the
    report makes becomes vacuously true."""
    codes = registered_codes()
    assert len(codes) > 50, f"only {len(codes)} registered codes discovered"
    assert "PT-040" in codes or "SZ-023" in codes


def test_a_missing_corpus_REPORTS_not_raises(tmp_path):
    """It must SAY it could not read, rather than raising into the caller or -
    worse - returning an empty chain, which reads exactly like a quiet system.
    'No transitions' and 'no corpus' are the same observation until separated."""
    out = load_transitions(tmp_path / "nope.jsonl")
    assert isinstance(out, dict)
    assert out.get("error"), f"a missing corpus returned no error marker: {out}"


def test_unparseable_rows_are_skipped_not_fatal(tmp_path):
    """One torn line must not silence the whole corpus - the audit trail is
    append-only under a live writer and a torn tail is expected, not exotic."""
    p = tmp_path / "audit.jsonl"
    p.write_text('{"code": "PT-040", "data": {"asset": "ETH"}, "ts": 1}\n'
                 'not json at all\n'
                 '{"code": "SZ-023", "data": {"asset": "ETH"}, "ts": 2}\n',
                 encoding="utf-8")
    out = load_transitions(p)
    assert not out.get("error"), f"a single bad line killed the corpus: {out}"
