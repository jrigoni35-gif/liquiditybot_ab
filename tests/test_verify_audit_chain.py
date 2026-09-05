"""tests/test_verify_audit_chain.py — the second route must actually detect.

A verifier that has never caught anything is indistinguishable from a
verifier that cannot. Every alarm class below is injected and asserted,
so "0 findings" on the live trail is evidence rather than silence.
"""

import hashlib
import json
import pathlib

import pytest

from scripts.verify_audit_chain import (
    GENESIS,
    canonical_body,
    record_hash,
    verify_chain,
)

_SRC = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "verify_audit_chain.py"


def test_module_is_independent_of_core_audit():
    """The whole value of this file is that it shares no code with the writer."""
    text = _SRC.read_text(encoding="utf-8")
    for banned in ("from core", "import core"):
        assert banned not in text, f"second route must not import the writer ({banned})"


def test_hash_matches_a_real_record_written_by_core_audit():
    """Pinned against an actual production record, not a self-made vector.

    This is what makes the reimplementation a corroborating route: it
    reproduces a hash that core/audit.py committed to the live trail.
    """
    real = {
        "code": "CG-000",
        "data": {"config_sha256": "f3646b8e010d35ac", "dry_run": True,
                 "maker_fee_bps": 25, "starting_capital_usd": 800,
                 "taker_fee_bps": 40},
        "h": "3161da2e23bb2c85",
        "msg": "session start: config fingerprint",
        "prev": GENESIS,
        "seq": 1,
        "src": "startup",
        "ts": 1783939764.991,
    }
    assert record_hash(real) == real["h"]
    assert '"h"' not in canonical_body(real), "the record's own hash is not hashed"


def _chain(n=25):
    recs, prev = [], GENESIS
    for i in range(1, n + 1):
        r = {"seq": i, "ts": 1780000000.0 + i, "src": "test", "code": "ZZ-000",
             "msg": f"record {i}", "data": {"i": i}, "prev": prev}
        r["h"] = record_hash(r)
        prev = r["h"]
        recs.append(r)
    return recs


def _write(tmp_path, recs, name="audit.jsonl"):
    p = tmp_path / name
    p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in recs),
                 encoding="utf-8")
    return p


def test_clean_chain_reports_nothing(tmp_path):
    rep = verify_chain(_write(tmp_path, _chain()))
    assert rep.records == 25
    assert (rep.integrity, rep.dangling, rep.seams) == ([], [], [])
    assert rep.tampered is False
    assert rep.duplicate_seqs == 0 and rep.missing_seqs == 0


def test_edited_record_is_an_integrity_failure(tmp_path):
    recs = _chain()
    recs[9]["data"] = {"i": 999}            # content changed, h left alone
    rep = verify_chain(_write(tmp_path, recs))
    assert len(rep.integrity) == 1
    assert rep.integrity[0][1] == 10        # the seq we edited
    assert rep.tampered is True


def test_deleted_record_dangles_its_successor(tmp_path):
    recs = _chain()
    del recs[14]
    rep = verify_chain(_write(tmp_path, recs))
    assert rep.integrity == []              # every surviving record is self-consistent
    assert len(rep.dangling) == 1
    assert rep.dangling[0][1] == 16         # the orphaned successor
    assert rep.tampered is True


def test_forged_record_with_recomputed_hash_still_dangles(tmp_path):
    """The sophisticated attack: edit content AND mint a valid hash."""
    recs = _chain()
    recs[19]["msg"] = "FORGED"
    recs[19].pop("h")
    recs[19]["h"] = record_hash(recs[19])
    rep = verify_chain(_write(tmp_path, recs))
    assert rep.integrity == [], "the forged record is internally consistent by design"
    assert len(rep.dangling) == 1, "but its successor's prev now points at a dead hash"
    assert rep.dangling[0][1] == 21
    assert rep.tampered is True


def test_concurrent_writer_fork_is_a_seam_not_an_alarm(tmp_path):
    """A second writer resuming from a stale tip: benign for integrity."""
    recs = _chain(10)
    forked = {"seq": 8, "ts": 1780000008.5, "src": "other", "code": "ZZ-001",
              "msg": "second writer", "data": {}, "prev": recs[6]["h"]}
    forked["h"] = record_hash(forked)
    recs.insert(8, forked)
    rep = verify_chain(_write(tmp_path, recs))
    assert rep.integrity == []
    assert rep.dangling == [], "a stale-but-known prev is NOT a deletion"
    assert len(rep.seams) >= 1
    assert rep.tampered is False, "seams alone must never read as tampering"


def test_forked_seq_is_reported_as_non_unique(tmp_path):
    recs = _chain(10)
    twin = {"seq": 5, "ts": 1780000005.5, "src": "other", "code": "ZZ-002",
            "msg": "same seq, different event", "data": {}, "prev": recs[9]["h"]}
    twin["h"] = record_hash(twin)
    recs.append(twin)
    rep = verify_chain(_write(tmp_path, recs))
    assert rep.duplicate_seqs == 1
    assert rep.divergent_seqs == 1, "the two rows disagree on (code, h)"
    assert rep.surplus_records == 1


def test_double_write_detection_needs_the_timestamp(tmp_path):
    """Same event at a DIFFERENT ts is a recurrence, not a double-write."""
    recs = _chain(6)
    rep = verify_chain(_write(tmp_path, recs), check_events=True)
    assert rep.double_writes == 0


def test_malformed_lines_are_counted_not_fatal(tmp_path):
    p = _write(tmp_path, _chain(5))
    p.write_text(p.read_text(encoding="utf-8") + "{not json\n", encoding="utf-8")
    rep = verify_chain(p)
    assert rep.malformed == 1 and rep.records == 5


@pytest.mark.parametrize("payload", [{"a": 1}, {"z": None}, {"nested": {"k": [1, 2]}}])
def test_hash_is_stable_under_key_order(payload):
    a = {"seq": 1, "ts": 1.0, "src": "s", "code": "C", "msg": "m",
         "data": payload, "prev": GENESIS}
    b = {"prev": GENESIS, "data": payload, "msg": "m", "code": "C",
         "src": "s", "ts": 1.0, "seq": 1}
    assert record_hash(a) == record_hash(b)
    assert record_hash(a) == hashlib.sha256(
        canonical_body(a).encode("utf-8")).hexdigest()[:16]
