"""
Regression for scripts/session_export.py + session_import.py, the
phone-session -> operator-machine learning hand-off. Pins the trust
gates: checksummed manifest (tamper -> refuse), audit-chain replay,
schema equality (drift routes through migrate_history, never silent),
position_id dedupe (re-import is idempotent), and the hard exclusion of
live-ledger files (state.json never travels, never gets written).
"""
import json

from core.audit import AuditTrail
from core.codes import Code
from ml.history import HistoryStore

import scripts.session_export as sx
import scripts.session_import as si


def _row(pid, label="1"):
    header = HistoryStore("unused.csv")._header
    vals = []
    for col in header:
        if col == "position_id":
            vals.append(pid)
        elif col == "asset":
            vals.append("ETH")
        elif col == "side":
            vals.append("long")
        elif col == "label":
            vals.append(label)
        elif col == "source":
            vals.append("live")
        else:
            vals.append("0.0")
    return ",".join(vals)


def _seed_outputs(root, pids=("p1", "p2")):
    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    header = HistoryStore(str(out / "signal_history.csv"))._header
    (out / "signal_history.csv").write_text(
        ",".join(header) + "\n" + "".join(_row(p) + "\n" for p in pids),
        encoding="utf-8")
    trail = AuditTrail(str(out / "audit.jsonl"))
    trail.log("qa", Code.FW_FAULT_DEGRADED, "seed record")
    (out / "equity.csv").write_text("ts,equity,daily_pnl\n1,800.0,0.0\n",
                                    encoding="utf-8")
    (out / "session_digest.json").write_text('{"verdict": "ok"}',
                                             encoding="utf-8")
    (out / "state.json").write_text('{"live": "ledger"}', encoding="utf-8")
    return out


def test_export_manifests_files_and_excludes_live_ledger(tmp_path):
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    m = sx.export(str(out), str(dst), "qa")
    assert m["history"]["rows"] == 2
    assert m["history"]["by_source"] == {"live": 2}
    assert "signal_history.csv" in m["files"]
    assert "audit.jsonl.gz" in m["files"]
    assert not (dst / "state.json").exists()
    assert "state.json" not in m["files"]


def test_export_gzips_audit_with_raw_digest(tmp_path):
    """audit.jsonl ships as audit.jsonl.gz (GitHub's 100 MB per-file limit
    refused every backup push from 2026-10-05). The manifest's sha256 covers
    the .gz as shipped; raw_sha256/raw_bytes cover the decompressed log. No
    plain copy may ride along, including a stale one in a re-used --dest."""
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    dst.mkdir()
    (dst / "audit.jsonl").write_text("stale plain copy\n", encoding="utf-8")
    m = sx.export(str(out), str(dst), "qa")
    meta = m["files"]["audit.jsonl.gz"]
    assert "audit.jsonl" not in m["files"]
    assert not (dst / "audit.jsonl").exists()
    assert meta["sha256"] == sx._sha256(dst / "audit.jsonl.gz")
    raw = (out / "audit.jsonl").read_bytes()
    assert meta["raw_bytes"] == len(raw)
    assert meta["raw_sha256"] == sx._sha256(out / "audit.jsonl")
    # byte-stable: identical input -> identical .gz (mtime=0 header)
    m2 = sx.export(str(out), str(tmp_path / "bundle2"), "qa")
    assert m2["files"]["audit.jsonl.gz"]["sha256"] == meta["sha256"]


def test_import_restores_gzipped_audit_byte_exact(tmp_path):
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    v = si.verify_bundle(dst)
    assert v["rc"] == 0 and v["chain"]["ok"]
    assert si.run(str(dst), str(home), apply=True) == 0
    rec = home / "imported_sessions" / "qa"
    assert (rec / "audit.jsonl").read_bytes() == \
        (out / "audit.jsonl").read_bytes()
    assert not (rec / "audit.jsonl.gz").exists()


def _rewrite_manifest(dst, mutate):
    mf = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    mutate(mf["files"])
    (dst / "manifest.json").write_text(json.dumps(mf), encoding="utf-8")


def test_import_refuses_gz_whose_payload_disagrees_with_manifest(tmp_path):
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    _rewrite_manifest(dst, lambda f: f["audit.jsonl.gz"].update(
        raw_sha256="0" * 64))
    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    assert si.run(str(dst), str(home), apply=True) == 2
    assert not (home / "imported_sessions").exists()


def test_import_caps_decompression_at_declared_raw_bytes(tmp_path):
    """The manifest is attacker-authored: a .gz that inflates past its own
    raw_bytes is refused mid-stream, never fully written."""
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    _rewrite_manifest(dst, lambda f: f["audit.jsonl.gz"].update(raw_bytes=8))
    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    assert si.run(str(dst), str(home), apply=False) == 2
    for bad in (None, -1, True, "123", si._MAX_AUDIT_RAW + 1):
        _rewrite_manifest(
            dst, lambda f, b=bad: f["audit.jsonl.gz"].update(raw_bytes=b))
        assert si.run(str(dst), str(home), apply=False) == 2, bad


def test_gunzip_aborts_mid_stream_past_limit(tmp_path):
    """The cap must stop the stream, not just reject afterwards: a bomb
    that is only measured after full inflation has already filled the disk.
    Nothing past `limit` may reach the output file."""
    import gzip
    bomb = tmp_path / "bomb.gz"
    bomb.write_bytes(gzip.compress(b"\0" * (8 << 20)))
    out = tmp_path / "out"
    try:
        si._gunzip_capped(bomb, out, 1 << 20)
    except ValueError:
        pass
    else:
        raise AssertionError("cap did not fire")
    assert out.stat().st_size <= 1 << 20


def test_import_refuses_both_plain_and_gz_audit(tmp_path):
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    (dst / "audit.jsonl").write_bytes((out / "audit.jsonl").read_bytes())
    _rewrite_manifest(dst, lambda f: f.update({"audit.jsonl": {
        "sha256": sx._sha256(dst / "audit.jsonl")}}))
    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    assert si.run(str(dst), str(home), apply=False) == 4


def test_import_still_accepts_legacy_plain_audit_bundle(tmp_path):
    """Bundles already on the telemetry branch carry a plain audit.jsonl;
    they must keep importing (restore reads the tip, whatever wrote it)."""
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    (dst / "audit.jsonl.gz").unlink()
    (dst / "audit.jsonl").write_bytes((out / "audit.jsonl").read_bytes())
    _rewrite_manifest(dst, lambda f: (f.pop("audit.jsonl.gz"), f.update(
        {"audit.jsonl": {"sha256": sx._sha256(dst / "audit.jsonl")}})))
    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    v = si.verify_bundle(dst)
    assert v["rc"] == 0 and v["chain"]["ok"]
    assert si.run(str(dst), str(home), apply=True) == 0
    assert (home / "imported_sessions" / "qa" / "audit.jsonl").exists()


def test_export_carries_fills_and_retrain_ledgers(tmp_path):
    """fills.csv + retrain_history.jsonl are append-only RECORDS (equity.csv
    class), added to PORTABLE 2026-08-19: without them every off-box
    cohort_eval run read MODEL-ERA UNKNOWN / accrual 0/50. Absent files
    still skip cleanly (fresh box)."""
    out = _seed_outputs(tmp_path)
    (out / "fills.csv").write_text(
        "ts,position_id,side,size,price,fee_usd\n1,p1,buy,1,10,0.01\n",
        encoding="utf-8")
    (out / "retrain_history.jsonl").write_text(
        '{"ts": 1.0, "deployed": true, "selected": "logistic"}\n',
        encoding="utf-8")
    dst = tmp_path / "bundle"
    m = sx.export(str(out), str(dst), "qa")
    assert "fills.csv" in m["files"] and (dst / "fills.csv").exists()
    assert "retrain_history.jsonl" in m["files"]
    # a box without them exports fine (copy-if-present, never required)
    out2 = _seed_outputs(tmp_path / "b2")
    m2 = sx.export(str(out2), str(tmp_path / "bundle2"), "qa2")
    assert "fills.csv" not in m2["files"]


def test_import_refuses_tampered_bundle(tmp_path):
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    hist = dst / "signal_history.csv"
    hist.write_text(hist.read_text(encoding="utf-8").replace("ETH", "BTC"),
                    encoding="utf-8")
    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    assert si.run(str(dst), str(home), apply=False) == 2


def test_import_refuses_schema_drift(tmp_path):
    out = _seed_outputs(tmp_path)
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")
    hist = dst / "signal_history.csv"
    lines = hist.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0] + ",mystery_col"
    body = "\n".join(lines) + "\n"
    hist.write_text(body, encoding="utf-8")
    mf = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    mf["files"]["signal_history.csv"]["sha256"] = sx._sha256(hist)
    (dst / "manifest.json").write_text(json.dumps(mf), encoding="utf-8")
    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    assert si.run(str(dst), str(home), apply=False) == 3


def test_import_merges_dedupes_and_never_touches_state(tmp_path):
    out = _seed_outputs(tmp_path, pids=("p1", "p2", "p3"))
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")

    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    header = HistoryStore(str(home / "signal_history.csv"))._header
    (home / "signal_history.csv").write_text(
        ",".join(header) + "\n" + _row("p2") + "\n" + _row("p9") + "\n",
        encoding="utf-8")
    (home / "state.json").write_text('{"home": "ledger"}', encoding="utf-8")

    assert si.run(str(dst), str(home), apply=True) == 0
    merged = (home / "signal_history.csv").read_text(encoding="utf-8")
    rows = [ln for ln in merged.splitlines()[1:] if ln.strip()]
    assert len(rows) == 4                       # p2,p9 + new p1,p3
    assert (home / "state.json").read_text(encoding="utf-8") == \
        '{"home": "ledger"}'
    assert list((home / "archive").glob("signal_history_pre_import_*")), \
        "backup of local history must exist"
    assert (home / "imported_sessions" / "qa" / "manifest.json").exists()

    # idempotent: importing the same bundle again adds nothing
    assert si.run(str(dst), str(home), apply=True) == 0
    rows2 = [ln for ln in (home / "signal_history.csv")
             .read_text(encoding="utf-8").splitlines()[1:] if ln.strip()]
    assert len(rows2) == 4


def test_model_travels_copy_if_absent(tmp_path):
    out = _seed_outputs(tmp_path)
    (out / "meta_model.json").write_text('{"kind": "gbt", "v": 1}',
                                         encoding="utf-8")
    dst = tmp_path / "bundle"
    m = sx.export(str(out), str(dst), "qa")
    assert "meta_model.json" in m["files"]

    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    assert si.run(str(dst), str(home), apply=True) == 0
    assert (home / "meta_model.json").read_text(encoding="utf-8") == \
        '{"kind": "gbt", "v": 1}'
    # the adopted brain must be REGISTERED in the destination ledger, or the
    # runner's integrity gate (ML-011) refuses it as tampered — the exact
    # cross-machine papercut this hand-off exists to avoid.
    from ml.registry import ModelRegistry
    v = ModelRegistry(str(home / "models")).verify(str(home / "meta_model.json"))
    assert v["ok"] is True


def test_model_never_overwrites_local(tmp_path):
    out = _seed_outputs(tmp_path)
    (out / "meta_model.json").write_text('{"v": "session"}', encoding="utf-8")
    dst = tmp_path / "bundle"
    sx.export(str(out), str(dst), "qa")

    home = tmp_path / "home" / "outputs"
    home.mkdir(parents=True)
    (home / "meta_model.json").write_text('{"v": "home-authoritative"}',
                                          encoding="utf-8")
    assert si.run(str(dst), str(home), apply=True) == 0
    assert (home / "meta_model.json").read_text(encoding="utf-8") == \
        '{"v": "home-authoritative"}'


def test_export_carries_the_forward_data_records(tmp_path):
    """The paper target book and the forward reads travel in the bundle so
    their results are readable off-box (2026-10-02)."""
    out = _seed_outputs(tmp_path)
    (out / "target_book" / "paper").mkdir(parents=True)
    (out / "target_book" / "paper" / "target_book_paper.json").write_text("{}", encoding="utf-8")
    (out / "reports" / "forward").mkdir(parents=True)
    (out / "reports" / "forward" / "forward_reads.json").write_text("{}", encoding="utf-8")
    m = sx.export(str(out), str(tmp_path / "bundle"), "qa")
    assert {"target_book_paper.json", "forward_reads.json"} <= set(m["files"])
