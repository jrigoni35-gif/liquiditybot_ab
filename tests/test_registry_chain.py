"""ml/registry.py must actually be hash-chained, not just called one.

Round-2 finding (2026-08-05), and a citation hazard as much as a bug: the
corpus's decisive provenance argument is membership in the HASH-CHAINED
audit trail, and the model registry borrowed the same adjective while
carrying no prev-hash and no sequence at all. verify() scanned for the last
matching row and compared ONE unauthenticated sha256 string, so:

  * deleting, truncating or reordering the ledger was undetectable;
  * editing the last registered row's hash (or appending a newer row)
    legitimized a swapped artifact with full "verified" provenance;
  * deleting registry.jsonl entirely downgraded every load to ok=None
    ("unknown provenance"), which the loader accepts - the ML-011 tamper
    gate degraded to a log line for anyone with the same write access the
    artifact itself needs.

These tests pin the chain and, crucially, that a BROKEN chain is no longer
treated as evidence.
"""
import json

from ml.registry import GENESIS, ModelRegistry


def _reg(tmp_path) -> ModelRegistry:
    return ModelRegistry(str(tmp_path / "models"))


def _artifact(tmp_path, body='{"kind": "gbt"}'):
    p = tmp_path / "meta_model.json"
    p.write_text(body, encoding="utf-8")
    return p


def _rows(reg) -> list:
    return [json.loads(ln) for ln in
            reg.ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]


# --- the chain exists ------------------------------------------------------
def test_rows_carry_seq_and_prev_links(tmp_path):
    # was a bare-pass stub (2026-08-20 test-honesty sweep): a hardening
    # file's first test asserted nothing. Now pins the actual chain shape.
    reg = ModelRegistry(str(tmp_path / "models"))
    reg.note("deployed", "m1", {"a": 1})
    reg.note("deployed", "m2", {"a": 2})
    rows = _rows(reg)
    assert len(rows) == 2
    assert all("h" in r and "prev" in r for r in rows)
    assert rows[1]["prev"] == rows[0]["h"]        # each links its predecessor
    assert rows[0]["prev"] != rows[0]["h"]        # genesis link, not self
    assert reg.verify_chain()["ok"] is True


def test_appended_unchained_row_after_chain_is_tamper(tmp_path):
    # the 2026-08-20 finding: a well-formed row with no `h` appended after a
    # real chained row must FAIL, not count as benign 'unchained'.
    reg = ModelRegistry(str(tmp_path / "models"))
    reg.note("deployed", "real", {})
    with open(reg.ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "registered", "model_id": "forged",
                            "detail": {}}) + "\n")
    v = reg.verify_chain()
    assert v["ok"] is False and "unchained row after" in v["reason"]


def test_append_past_forgery_still_condemned(tmp_path):
    """_tail_link deliberately links PAST a no-`h` row (nothing to adopt),
    so a legitimate append lands cleanly after a forged row — verify_chain
    must still condemn the ledger at the forgery (injection-verified
    2026-08-19: the append-past-forgery sequence)."""
    reg = ModelRegistry(str(tmp_path / "models"))
    reg.note("deployed", "real-1", {})
    reg.note("deployed", "real-2", {})
    with open(reg.ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "registered", "model_id": "forged",
                            "detail": {}}) + "\n")
    reg.note("deployed", "real-3", {})            # links past the forgery
    rows = _rows(reg)
    linked = [r for r in rows if r.get("h")]
    assert linked[-1]["prev"] == linked[-2]["h"], \
        "the post-forgery append must link from the last REAL row"
    v = reg.verify_chain()
    assert v["ok"] is False and "unchained row after" in v["reason"], \
        "a ledger holding a post-chain forgery stays condemned forever"


def test_first_row_links_to_genesis(tmp_path):
    reg = _reg(tmp_path)
    reg.register(str(_artifact(tmp_path)), {"kind": "gbt"})
    rows = _rows(reg)
    assert rows[0]["seq"] == 1
    assert rows[0]["prev"] == GENESIS
    assert len(rows[0]["h"]) == 16


def test_each_row_links_to_its_predecessor(tmp_path):
    reg = _reg(tmp_path)
    art = _artifact(tmp_path)
    reg.register(str(art), {"kind": "gbt"})
    reg.note("deployed", "abc123")
    art.write_text('{"kind": "mlp"}', encoding="utf-8")
    reg.register(str(art), {"kind": "mlp"})
    rows = _rows(reg)
    assert [r["seq"] for r in rows] == [1, 2, 3]
    for earlier, later in zip(rows, rows[1:], strict=False):
        assert later["prev"] == earlier["h"], "chain link broken"
    assert reg.verify_chain()["ok"] is True


def test_intact_chain_verifies(tmp_path):
    reg = _reg(tmp_path)
    reg.register(str(_artifact(tmp_path)), {"kind": "gbt"})
    reg.note("deployed", "abc123")
    v = reg.verify_chain()
    assert v["ok"] is True and v["chained"] == 2


# --- tamper detection ------------------------------------------------------
def test_edited_row_is_detected(tmp_path):
    """The laundering path: rewrite a registered row's sha256 so a swapped
    artifact verifies. The recomputed content hash no longer matches."""
    reg = _reg(tmp_path)
    reg.register(str(_artifact(tmp_path)), {"kind": "gbt"})
    rows = _rows(reg)
    rows[0]["sha256"] = "deadbeef" * 8
    reg.ledger.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    v = reg.verify_chain()
    assert v["ok"] is False and "edited" in v["reason"]


def test_deleted_row_is_detected(tmp_path):
    reg = _reg(tmp_path)
    art = _artifact(tmp_path)
    reg.register(str(art), {"kind": "gbt"})
    reg.note("deployed", "abc123")
    art.write_text('{"kind": "mlp"}', encoding="utf-8")
    reg.register(str(art), {"kind": "mlp"})
    rows = _rows(reg)
    del rows[1]                                   # excise the middle row
    reg.ledger.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    v = reg.verify_chain()
    assert v["ok"] is False and "deleted" in v["reason"]


def test_reordered_rows_are_detected(tmp_path):
    reg = _reg(tmp_path)
    art = _artifact(tmp_path)
    reg.register(str(art), {"kind": "gbt"})
    art.write_text('{"kind": "mlp"}', encoding="utf-8")
    reg.register(str(art), {"kind": "mlp"})
    rows = _rows(reg)
    rows.reverse()
    reg.ledger.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert reg.verify_chain()["ok"] is False


# --- the load gate must not trust a broken ledger --------------------------
def test_verify_refuses_a_pedigree_from_a_broken_chain(tmp_path):
    """THE point of chaining it: an attacker who can edit the ledger could
    previously mint provenance for any artifact. A broken chain must fail
    the load gate rather than authorize it."""
    reg = _reg(tmp_path)
    art = _artifact(tmp_path)
    reg.register(str(art), {"kind": "gbt"})
    assert reg.verify(str(art))["ok"] is True     # honest baseline

    # swap the artifact AND rewrite the ledger row to match it
    art.write_text('{"kind": "attacker"}', encoding="utf-8")
    from ml.registry import sha256_file
    rows = _rows(reg)
    rows[0]["sha256"] = sha256_file(str(art))
    reg.ledger.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    out = reg.verify(str(art))
    assert out["ok"] is False, \
        "a rewritten ledger row must not mint provenance for a swapped model"
    assert "chain" in out


def test_torn_final_row_neither_forks_nor_fuses(tmp_path):
    """A crash mid-append leaves a fragment with no newline. Two things
    must hold: the next append LINKS from the last COMPLETE row (not the
    fragment), and it does not FUSE onto that fragment - appending straight
    onto a torn line welds two records into one unparseable line, taking
    the good record down with the bad one (the same defect class as the
    fills-ledger torn row, found by this test)."""
    reg = _reg(tmp_path)
    art = _artifact(tmp_path)
    reg.register(str(art), {"kind": "gbt"})
    with open(reg.ledger, "a", encoding="utf-8") as f:
        f.write('{"event": "registered", "seq": 2')      # torn, no newline
    art.write_text('{"kind": "mlp"}', encoding="utf-8")
    reg.register(str(art), {"kind": "mlp"})

    lines = [ln for ln in reg.ledger.read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    parsed, bad = [], 0
    for ln in lines:
        try:
            parsed.append(json.loads(ln))
        except ValueError:
            bad += 1
    assert bad == 1, "exactly the torn fragment should be unparseable"
    linked = [r for r in parsed if r.get("h")]
    assert len(linked) == 2, "both real records must survive intact"
    assert linked[-1]["prev"] == linked[0]["h"], \
        "the post-crash append must link from the last complete row"
