"""tests/test_boundary5_stage.py — regression pins for
scripts/boundary5_stage.py (the boundary-#5 fee-truth cut: staged and
INERT until an operator runs --apply after the era-4 n=50 readout).

Task-2 verification (scratchpad sdd/task-2-report.md, 2026-08-27) ran
these four checks by hand against a scratch temp copy and flagged the
gap: no persisted test exists for the stager despite its own commit
message's "mutation-verified" claims. This file closes that gap by
pinning exactly those four checks as regression tests.

ALL tests operate on TMP COPIES of config.json's CONTENT — never the
tracked repo file. `scripts.boundary5_stage.CONFIG` is monkeypatched to
a tmp path per test, and `sys.argv` is monkeypatched for the --apply
tests, so nothing here can ever write to (or even open for writing) the
live config.json. The FATAL/breakeven numbers are asked of the running
guard (core.config_guard.validate + risk.position_sizer), never
hardcoded from memory - see the derivation note on each pin below.
"""
import copy
import json
import sys

import scripts.boundary5_stage as b5
from core.config_guard import validate


def _real_config() -> dict:
    """A read-only snapshot of the TRACKED config.json's content (never
    its path/object) — the guard's breakeven/FATAL math depends on the
    real sizing/profit-taking geometry; a hand-built minimal dict would
    not reproduce it faithfully. b5.CONFIG.read_text() only ever reads
    here, never written to."""
    return json.loads(b5.CONFIG.read_text(encoding="utf-8"))


def _candidate(edits) -> dict:
    cand = copy.deepcopy(_real_config())
    for key, _frm, to in edits:
        b5._set(cand, key, to)
    return cand


# ---------------------------------------------------------------------
# 1. fees-only candidate (p_win deliberately pinned at the pre-cut 0.70,
#    NOT read from whatever the live config currently has) -> exactly 1
#    FATAL, at the net-Kelly breakeven the fee jump alone creates.
#    Derivation asked of the runtime this session: b_net 0.4488 -> 0.1998,
#    breakeven 1/(1+b_net) = 0.8334961740851363 (raw) -> the guard's own
#    ":.3f" formatting renders "0.833" in the FATAL text.
# ---------------------------------------------------------------------
def test_fees_only_candidate_is_exactly_one_fatal_at_breakeven():
    fees_only = [e for e in b5.EDITS if e[0] != "ml.exploration.p_win"]
    cand = _candidate(fees_only)
    b5._set(cand, "ml.exploration.p_win", 0.7)   # explicit, not live-read

    fatals = [m for s, m in validate(cand) if s == "FATAL"]
    assert len(fatals) == 1
    assert "ml.exploration.p_win=0.700" in fatals[0]
    assert "net-Kelly breakeven 0.833" in fatals[0]
    assert "SZ-030" in fatals[0]


# ---------------------------------------------------------------------
# 2. the full 7-key package (p_win raised to 0.85 alongside the fees)
#    clears the guard with zero FATALs — the coherence edit is WHY the
#    package bundles p_win with the fee truth rather than shipping fees
#    alone.
# ---------------------------------------------------------------------
def test_full_package_candidate_is_zero_fatal():
    cand = _candidate(b5.EDITS)
    fatals = [m for s, m in validate(cand) if s == "FATAL"]
    assert fatals == []


# ---------------------------------------------------------------------
# 3. a hand-edited config (drift from the staged FROM values) refuses at
#    --apply time: rc=2, no write, no backup. The drift guard is the
#    FIRST check main() performs, before the guard sweep and before any
#    file I/O.
# ---------------------------------------------------------------------
def test_apply_refuses_on_drifted_from_value(tmp_path, monkeypatch, capsys):
    cfg = _real_config()
    # hand-edit ONE staged key to neither its FROM nor its TO
    b5._set(cfg, "pretrade.maker_fee_bps", 30.0)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    before = cfg_path.read_text(encoding="utf-8")

    monkeypatch.setattr(b5, "CONFIG", cfg_path)
    monkeypatch.setattr(sys, "argv", ["boundary5_stage.py", "--apply"])

    rc = b5.main()

    assert rc == 2
    out = capsys.readouterr().out
    assert "REFUSING" in out
    assert "do not match the staged FROM values" in out
    assert cfg_path.read_text(encoding="utf-8") == before   # untouched
    assert not list(tmp_path.glob("config.json.pre-boundary5-*"))  # no backup


# ---------------------------------------------------------------------
# 4. a clean --apply on an undrifted copy writes the candidate AND backs
#    up the original beside it before writing.
# ---------------------------------------------------------------------
def test_clean_apply_writes_and_backs_up(tmp_path, monkeypatch):
    cfg = _real_config()
    for key, frm, _to in b5.EDITS:
        assert b5._get(cfg, key) == frm, (
            f"{key}: live config.json no longer matches boundary5_stage's "
            "staged FROM value - the package needs re-derivation, this "
            "test's fixture cannot silently paper over real drift")
    cfg_path = tmp_path / "config.json"
    original_text = json.dumps(cfg, indent=2) + "\n"
    cfg_path.write_text(original_text, encoding="utf-8")

    monkeypatch.setattr(b5, "CONFIG", cfg_path)
    monkeypatch.setattr(sys, "argv", ["boundary5_stage.py", "--apply"])

    rc = b5.main()

    assert rc == 0
    written = json.loads(cfg_path.read_text(encoding="utf-8"))
    for key, _frm, to in b5.EDITS:
        assert b5._get(written, key) == to

    backups = list(tmp_path.glob("config.json.pre-boundary5-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == original_text
