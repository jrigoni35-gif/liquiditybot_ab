"""tests/test_code_registry.py — W2-19: unregistered disposition strings.

Every machine disposition is supposed to carry a code registered in
core/codes.py's prefix map (CLAUDE.md invariant #6: "new behavior = new
registered code, never a bare string"). Two gaps were found by source scan:

  1. main.py's session-start audit event passed the bare string "CG-000"
     to get_audit().log() - the prefix map has advertised a CG family
     (core.config_guard) since the registry's docstring was written, but
     no CG member ever existed. Fixed: Code.CG_SESSION_START = "CG-000".

  2. execution/algos.py aborts a parent order with reason strings like
     "EX-ALGO-HORIZON: horizon expired" - main.py's _step_exec_algos
     reuses the SAME "EX-ALGO-*" shape for its own abort_all() calls
     (EX-ALGO-ENTRIES-OFF, EX-ALGO-WATCHDOG). This is algos.py's own
     documented internal reason-coded scheme (module docstring: "a parent
     ABORTS remaining slices ... reason-coded EX-ALGO-*") - stored only on
     ParentOrder.abort_reason and plain log.info() lines, never passed to
     get_audit()/tag(), never code_stats-bumped. Registering it in
     core/codes.py would mean two parallel vocabularies for the exact same
     four-tag family (the two in algos.py that were never audited either -
     EX-ALGO-HORIZON, EX-ALGO-REJECTS - would need it too, or the split is
     arbitrary). Decision: pin the whole "EX-ALGO-*" family as an ALLOWED
     INTERNAL VOCABULARY here instead, so a NEW tag silently appearing
     anywhere in this family must be a reviewed decision (extend the
     allowlist, or promote to a real registered code if it starts flowing
     into the audit chain) rather than slip past unnoticed.

  3. _mark_cand's candidate-ledger dispositions ("capped", "entered", and
     truncated sizer/pretrade veto-reason strings) are excluded from the
     canonical scan entirely: ml/history.py CandidateLabeler.mark_disposition
     stores `code` only in _cands[i]["disp"] (truncated to 40 chars) for the
     labeler's OWN bookkeeping - never audited, never tag()'d, never
     code_stats-bumped, confirmed directly below. Where a registered code's
     .value already flows in there (e.g. Code.SZ_CIRCUIT_BREAKER.value)
     that's incidental reuse, not a registry gap.

The scan is AST-based (not a blind text regex) so it does not false-positive
on prose: several comments/docstrings in main.py mention audit-finding IDs
that look code-shaped (SD-002, SD-003) or accidental substrings (CCXT-001
contains "XT-001") - those live inside much longer string constants /
comments, never as a standalone literal argument, and must never fail this
test.
"""
import ast
import re
from pathlib import Path

from core import code_stats
from core.codes import Code
from ml.history import CandidateLabeler, HistoryStore

ROOT = Path(__file__).resolve().parent.parent

# execution/algos.py's own documented internal reason-coded scheme (module
# docstring: "reason-coded EX-ALGO-*") - log-line / abort_reason bookkeeping
# only, deliberately NOT part of core/codes.py's audited registry.
EX_ALGO_ALLOWLIST = {
    "EX-ALGO-ENTRIES-OFF",   # main.py _step_exec_algos: kill switch abort
    "EX-ALGO-WATCHDOG",      # main.py _step_exec_algos: watchdog data-quality abort
    "EX-ALGO-HORIZON",       # execution/algos.py: horizon-expiry abort
    "EX-ALGO-REJECTS",       # execution/algos.py: consecutive child rejects abort
}

# candidate-ledger disposition vocabulary (ml/history.py mark_disposition) -
# internal labeler bookkeeping, never audited. Registered Code .value
# strings are also accepted here incidentally (sizer/pretrade veto codes
# reused as disposition labels); only these bare, non-code labels need an
# explicit allowlist entry.
CANDIDATE_DISPOSITION_ALLOWLIST = {"capped", "entered"}

_CANON = re.compile(r'^[A-Z]{2}-\d{3}$')                    # e.g. "CG-000"
_EX_ALGO = re.compile(r'^(EX-ALGO-[A-Z-]+?)(?::.*)?$')      # e.g. "EX-ALGO-X: detail"


def _scan(path: Path):
    """AST walk collecting bare string constants that look like a reason
    code (exact "XX-NNN" shape) or an EX-ALGO-* tag (with an optional
    ": detail" suffix collapsed off) - never matches inside a longer
    docstring/comment string, since those don't fullmatch either pattern."""
    tree = ast.parse(path.read_text(), filename=str(path))
    canon, ex_algo = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
            if _CANON.fullmatch(s):
                canon.add(s)
            m = _EX_ALGO.match(s)
            if m:
                ex_algo.add(m.group(1))
    return canon, ex_algo


def test_every_canonical_code_literal_is_registered():
    registered = {c.value for c in Code}
    for name in ("main.py", "runner.py"):
        canon, _ = _scan(ROOT / name)
        unregistered = canon - registered
        assert not unregistered, (
            f"{name} emits bare code literal(s) {unregistered} not present "
            f"in core/codes.py - register them (never a bare string)")


def test_ex_algo_internal_tags_are_a_closed_pinned_vocabulary():
    _, main_ex = _scan(ROOT / "main.py")
    _, algos_ex = _scan(ROOT / "execution" / "algos.py")
    found = main_ex | algos_ex
    assert found, "expected to find the known EX-ALGO-* literals"
    unexpected = found - EX_ALGO_ALLOWLIST
    assert not unexpected, (
        f"new EX-ALGO-* tag(s) {unexpected} appeared - either add to the "
        f"pinned internal allowlist (still log-only/never audited) or "
        f"register a real core/codes.py code (if it now flows into "
        f"get_audit()/tag())")
    missing = EX_ALGO_ALLOWLIST - found
    assert not missing, (
        f"allowlisted EX-ALGO-* tag(s) {missing} no longer found in source - "
        f"prune the allowlist so it stays a precise pin, not dead weight")


def test_candidate_dispositions_never_reach_the_audit_chain_or_code_stats(tmp_path):
    """Confirms the reasoning above with code, not just a comment: marking
    a candidate's disposition (however it is spelled) never bumps
    code_stats and is invisible to the registry-completeness scan by
    construction - it only ever lands in the labeler's own _cands ledger."""
    store = HistoryStore(str(tmp_path / "hist.csv"))
    lab = CandidateLabeler(store, {"exploration": {}})
    import numpy as np
    feats = np.zeros(8)
    lab.register("BTC", "long", feats, 0.01, 1000.0)

    code_stats.reset()
    for disp in CANDIDATE_DISPOSITION_ALLOWLIST:
        lab.mark_disposition("BTC", "long", disp)
    assert code_stats.snapshot() == {}, \
        "candidate-ledger dispositions must never bump code_stats - they " \
        "are an internal vocabulary, not audited codes"
    assert lab._cands[-1]["disp"] in CANDIDATE_DISPOSITION_ALLOWLIST
