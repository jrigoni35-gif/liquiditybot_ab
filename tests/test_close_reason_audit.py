"""I0 (2026-07-31 era-deadlock debate): every full close must NAME its
verbatim close_reason in the audit trail.

The corpus `barrier` column is lossy by design - anything that is not a
bracket leg collapses to "realized" - so neither the training data nor
the audit could say WHAT ended a position. Three of the eight bracket
probes ever closed died at 20-36 minutes: too early for PT-060 (180 min)
and too early for the post-381e870 give-back arm. The mechanism was
unnamed. PT-061 is the instrument; these tests pin that it fires, that it
carries the verbatim reason (not the collapsed barrier), and that a
bookkeeping fault can never block an exit (CLAUDE.md invariant 5).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codes import Code


def test_pt061_registered_and_distinct():
    assert Code.PT_CLOSE_REASON.value == "PT-061"
    vals = [c.value for c in Code]
    assert vals.count("PT-061") == 1, "code must be unique"


def test_finalize_emits_verbatim_reason_not_the_collapsed_barrier():
    """The audit payload must carry close_reason SEPARATELY from barrier -
    that separation is the whole point of the instrument."""
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    i = src.index('barrier = close_reason if close_reason in (')
    block = src[i:i + 2000]
    assert "Code.PT_CLOSE_REASON" in block, "PT-061 must fire at the close site"
    assert '"close_reason": close_reason or ""' in block, \
        "verbatim reason must be recorded, not just the collapsed barrier"
    assert '"barrier": barrier' in block, "both fields, so the loss is visible"
    assert '"bars_held"' in block and '"is_probe"' in block, \
        "adjudicating the deadlock needs hold-time and probe context"


def test_close_reason_audit_is_guarded():
    """Invariant 5: exits are ALWAYS allowed - instrumentation may never
    raise into the close path."""
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    i = src.index("I0 (2026-07-31)")
    block = src[i:i + 2200]
    assert "try:" in block and "except Exception:" in block
    assert "close unaffected" in block
