"""core.audit.main_chain_indices - the reader-side filter that keeps forked
writers' rows out of code tallies (2026-09-27).

Forks are built with REAL AuditTrail writers (two instances on one file, the
second holding a stale prev), so the hashes are genuine and verify_chain
classifies the fork as a writer seam - the exact on-disk shape the PC trail
carries 2,241 of.
"""
import json

from core.audit import (AuditTrail, main_chain_indices, main_chain_records,
                        read_main_chain, verify_chain)


def _forked_trail(path, main_before=3, fork_n=2, main_after=4):
    """main writer A appends `main_before`; writer B syncs on A's tail and
    appends one record; A (stale prev) appends `main_after`; B (stale prev)
    appends `fork_n - 1` more. Returns (A_codes, B_codes)."""
    a = AuditTrail(str(path), fsync=False)
    for i in range(main_before):
        a.log("main", "LB-010", f"a{i}")
    b = AuditTrail(str(path), fsync=False)
    b.log("dup", "FT-010", "b0")               # B chains on A's tail
    for i in range(main_after):
        a.log("main", "LB-010", f"a{main_before + i}")   # A forks past B
    for i in range(fork_n - 1):
        b.log("dup", "RT-010", f"b{i + 1}")
    return a, b


def _lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()
            if x.strip()]


def test_main_chain_excludes_a_real_writer_fork(tmp_path):
    p = tmp_path / "audit.jsonl"
    _forked_trail(p, main_before=3, fork_n=2, main_after=4)
    recs = _lines(p)
    v = verify_chain(p)
    assert v["tamper"] is False and v["seams"] >= 1, v   # a benign seam
    main = main_chain_records(recs)
    assert [r["msg"] for r in main] == [f"a{i}" for i in range(7)]
    off = [r for i, r in enumerate(recs) if i not in main_chain_indices(recs)]
    assert sorted(r["msg"] for r in off) == ["b0", "b1"]
    assert {r["src"] for r in off} == {"dup"}


def test_loser_writing_the_last_line_does_not_hijack_the_walk(tmp_path):
    """The losing writer appends LAST. A 'walk back from the final line'
    rule would pick its 2-record branch and drop the 4 main records after
    the fork point; the longest-lineage rule keeps the main chain."""
    p = tmp_path / "audit.jsonl"
    _forked_trail(p, main_before=3, fork_n=2, main_after=4)
    recs = _lines(p)
    assert recs[-1]["src"] == "dup"                 # precondition: loser last
    keep = main_chain_indices(recs)
    assert len(keep) == 7
    assert len(recs) - 1 not in keep


def test_chainless_input_is_not_all_off_chain():
    recs = [{"code": "OM-011"}, {"code": "FW-070"}, None]
    assert main_chain_indices(recs) == {0, 1}


def test_unparseable_and_orphan_rows_are_off_chain(tmp_path):
    p = tmp_path / "audit.jsonl"
    a = AuditTrail(str(p), fsync=False)
    for i in range(3):
        a.log("main", "LB-010", f"a{i}")
    with open(p, "a", encoding="utf-8") as f:
        f.write('{"torn\n')
        f.write(json.dumps({"seq": 9, "code": "ZZ-1", "prev": "nowhere",
                            "h": "orphan"}) + "\n")
    recs, keep = read_main_chain(p)
    assert len(recs) == 5 and recs[3] is None
    assert keep == {0, 1, 2}


def test_prev_cycle_terminates():
    recs = [{"h": "x", "prev": "y"}, {"h": "y", "prev": "x"}]
    assert main_chain_indices(recs) <= {0, 1}


def test_read_main_chain_is_read_only(tmp_path):
    p = tmp_path / "audit.jsonl"
    _forked_trail(p)
    with open(p, "ab") as f:
        f.write(b'{"torn')                          # a torn final line
    before = p.read_bytes()
    read_main_chain(p)
    assert p.read_bytes() == before


def test_missing_file_degrades_to_empty(tmp_path):
    assert read_main_chain(tmp_path / "nope.jsonl") == ([], set())
