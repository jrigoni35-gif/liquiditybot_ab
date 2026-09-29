"""core/cohort.py - decision-fingerprint cohorts (operator ruling 2026-09-26).

The fingerprint is only worth something if it forks on EVERY decision change
and on NOTHING else. These pins plant each kind of edit and watch the digest.
"""
import json

from core import cohort

CFG = {"risk": {"stop_loss_pct": 2.0, "_doc": "prose"},
       "system": {"dry_run": True, "log_level": "INFO"},
       "alerts": {"webhook_url": "https://secret.example/hook"},
       "exchanges": {"kraken": {"api_key": "SECRET"}}}


def _tree(tmp_path, body="def f(x):\n    return x + 1\n"):
    (tmp_path / "ml").mkdir(exist_ok=True)
    (tmp_path / "main.py").write_text(
        '"""engine."""\n# a comment\n' + body, encoding="utf-8")
    (tmp_path / "ml" / "m.py").write_text("K = 1\n", encoding="utf-8")
    return tmp_path


def _cfg(**patch):
    c = json.loads(json.dumps(CFG))
    for dotted, val in patch.items():
        sec, key = dotted.split("__")
        c.setdefault(sec, {})[key] = val
    return c


# ---------------------------------------------------------------- config
def test_config_fingerprint_is_deterministic():
    assert cohort.config_fingerprint(CFG) == cohort.config_fingerprint(
        json.loads(json.dumps(CFG)))


def test_a_decision_key_forks_the_cohort():
    assert (cohort.config_fingerprint(_cfg(risk__stop_loss_pct=2.5))
            != cohort.config_fingerprint(CFG))


def test_doc_keys_and_non_decision_sections_never_fork():
    base = cohort.config_fingerprint(CFG)
    assert cohort.config_fingerprint(_cfg(risk___doc="rewritten")) == base
    assert cohort.config_fingerprint(_cfg(system__log_level="DEBUG")) == base
    assert cohort.config_fingerprint(
        _cfg(alerts__webhook_url="https://other")) == base


def test_credentials_never_reach_the_digest():
    c = _cfg()
    c["exchanges"]["kraken"]["api_key"] = "DIFFERENT-SECRET"
    assert cohort.config_fingerprint(c) == cohort.config_fingerprint(CFG)
    assert "SECRET" not in json.dumps(cohort.decision_config(CFG))


def test_an_unknown_new_section_forks_fail_closed():
    """A new feature's config must fork until argued out of the print."""
    assert (cohort.config_fingerprint(_cfg(new_feature__enabled=True))
            != cohort.config_fingerprint(CFG))


def test_dry_run_is_part_of_the_cohort():
    assert (cohort.config_fingerprint(_cfg(system__dry_run=False))
            != cohort.config_fingerprint(CFG))


# ------------------------------------------------------------------ code
def test_comment_and_docstring_edits_do_not_fork(tmp_path):
    root = _tree(tmp_path)
    before = cohort.code_fingerprint(root)
    (root / "main.py").write_text(
        '"""engine, reworded."""\n# other comment\n\n'
        'def f(x):\n    """now documented."""\n    return x + 1\n',
        encoding="utf-8")
    assert cohort.code_fingerprint(root) == before


def test_a_semantic_edit_forks(tmp_path):
    root = _tree(tmp_path)
    before = cohort.code_fingerprint(root)
    _tree(tmp_path, body="def f(x):\n    return x + 2\n")
    assert cohort.code_fingerprint(root) != before


def test_an_edit_in_a_decision_directory_forks(tmp_path):
    root = _tree(tmp_path)
    before = cohort.code_fingerprint(root)
    (root / "ml" / "m.py").write_text("K = 2\n", encoding="utf-8")
    assert cohort.code_fingerprint(root) != before


def test_unparseable_source_still_fingerprints(tmp_path):
    root = _tree(tmp_path)
    (root / "ml" / "broken.py").write_text("def (:\n", encoding="utf-8")
    assert len(cohort.code_fingerprint(root)) == 12


def test_real_repo_fingerprint_shape():
    fp = cohort.decision_fingerprint(CFG)
    assert fp["fp"] != cohort.UNKNOWN and len(fp["fp"]) == 12
    assert fp["fp"] == fp["cfg_fp"][:6] + fp["code_fp"][:6]


def test_failure_yields_unknown_never_raises(monkeypatch):
    def boom(_):
        raise RuntimeError("x")
    monkeypatch.setattr(cohort, "config_fingerprint", boom)
    assert cohort.decision_fingerprint(CFG)["fp"] == cohort.UNKNOWN


# ----------------------------------------------------------- equivalence
def test_equivalence_requires_evidence(tmp_path):
    p = tmp_path / "eq.json"
    p.write_text(json.dumps([
        {"fp": "a", "same_as": "b", "evidence": "SAFE telemetry edit, "
                                                "tests X/Y byte-equal"},
        {"fp": "c", "same_as": "b", "evidence": "  "},
        {"fp": "d", "same_as": "b"}]), encoding="utf-8")
    assert cohort.load_equivalence(p) == {"a": "b"}


def test_equivalence_missing_or_corrupt_is_empty(tmp_path):
    assert cohort.load_equivalence(tmp_path / "absent.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert cohort.load_equivalence(bad) == {}


def test_canonical_follows_chains_and_survives_cycles():
    assert cohort.canonical("a", {"a": "b", "b": "c"}) == "c"
    assert cohort.canonical("a", {"a": "b", "b": "a"}) in ("a", "b")
    assert cohort.canonical("z", {}) == "z"


# ---------------------------------------------------------------- wiring
def test_boot_stamps_the_ledger_and_the_session_record(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from core import fill_ledger
    from test_decision_events import _bot
    monkeypatch.chdir(tmp_path)
    bot = _bot(tmp_path)
    fp = bot.decision_fp["fp"]
    assert fp not in ("", cohort.UNKNOWN)
    assert fill_ledger.DECISION_FP == fp
    cg = [json.loads(x) for x in
          (tmp_path / "audit.jsonl").read_text().splitlines()
          if '"CG-000"' in x]
    assert cg and cg[-1]["data"]["decision_fp"] == fp
    order = SimpleNamespace(arrival_ref=0.0, side="buy", order_id="o",
                            position_id="p", purpose="entry", symbol="X",
                            ordertype="limit", post_only=True, meta={},
                            remaining=0.0)
    row = fill_ledger.fill_row(order, SimpleNamespace(fill_size=1.0,
                                                      fill_price=1.0),
                               0.0, 1.0)
    assert list(row)[-1] == "decision_fp" and row["decision_fp"] == fp
    assert fill_ledger.COLS[-1] == "decision_fp"


# ------------------------------------------- timeline (C1, 2026-09-28)
def _trail(tmp_path, monkeypatch):
    """A real hash-chained trail: legacy boot, fp 'aaa' boot, fp 'bbb' boot,
    plus a CG-000 'fork' record hanging off the FIRST record (off-chain)."""
    import core.audit as audit_mod
    from core.audit import AuditTrail
    p = tmp_path / "audit.jsonl"
    at = AuditTrail(str(p), fsync=False)
    clock = iter([100.0, 200.0, 300.0, 400.0])
    monkeypatch.setattr(audit_mod.time, "time", lambda: next(clock))
    at.log("startup", "CG-000", "boot", {"dry_run": True})          # legacy
    at.log("startup", "CG-000", "boot", {"decision_fp": "aaa"})
    at.log("startup", "CG-000", "boot", {"decision_fp": "bbb"})
    at.log("entry", "EN-000", "tick", {})
    first = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    fork = {"seq": 99, "ts": 250.0, "src": "startup", "code": "CG-000",
            "msg": "harness boot", "data": {"decision_fp": "fork"},
            "prev": first["h"], "h": "f0f0f0f0f0f0f0f0"}
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fork) + "\n")
    return p


def test_timeline_reads_main_chain_boots_and_ignores_forks(tmp_path,
                                                          monkeypatch):
    tl = cohort.fp_timeline(_trail(tmp_path, monkeypatch))
    assert tl == [(200.0, "aaa"), (300.0, "bbb")]


def test_fp_at_maps_timestamps_to_the_running_cohort():
    tl = [(200.0, "aaa"), (300.0, "bbb")]
    assert cohort.fp_at(150.0, tl) == cohort.LEGACY_FP
    assert cohort.fp_at(200.0, tl) == "aaa"
    assert cohort.fp_at(299.9, tl) == "aaa"
    assert cohort.fp_at(1e12, tl) == "bbb"
    assert cohort.fp_at("garbage", tl) == cohort.LEGACY_FP
    assert cohort.fp_at(500.0, []) == cohort.LEGACY_FP


def test_timeline_on_a_missing_trail_is_empty_not_a_crash(tmp_path):
    assert cohort.fp_timeline(tmp_path / "absent.jsonl") == []


def test_cohort_of_and_running_fp(tmp_path):
    assert cohort.cohort_of("") == cohort.cohort_of(None) == cohort.LEGACY_FP
    assert cohort.cohort_of(" abc ") == "abc"
    st = tmp_path / "status.json"
    st.write_text(json.dumps({"decision_fp": "abc"}), encoding="utf-8")
    assert cohort.running_fp(st) == "abc"
    assert cohort.running_fp(tmp_path / "none.json") == ""


def test_digest_counts_rows_and_legs_per_decision_cohort(tmp_path,
                                                          monkeypatch):
    """C1 (2026-09-28): the digest's era hazard cannot see a cohort mix once
    EXEC_ERA froze. Label rows (no stamp) map via the boot timeline; legs
    use their own stamp; the cohort hazard fires on a real mix."""
    import csv as _csv

    import core.audit as audit_mod
    from core.audit import AuditTrail
    from core.session_digest import _eras_section
    out = tmp_path / "outputs"
    out.mkdir()
    at = AuditTrail(str(out / "audit.jsonl"), fsync=False)
    clock = iter([200.0, 300.0])
    monkeypatch.setattr(audit_mod.time, "time", lambda: next(clock))
    at.log("startup", "CG-000", "boot", {"decision_fp": "aaa"})
    at.log("startup", "CG-000", "boot", {"decision_fp": "bbb"})
    sig = [{"signal_ts": "100"}, {"signal_ts": "250"}, {"signal_ts": "350"},
           {"signal_ts": "360"}]
    with open(out / "fills.csv", "w", newline="", encoding="utf-8") as fh:
        w = _csv.writer(fh)
        w.writerow(["ts", "exec_era", "decision_fp"])
        w.writerows([["1", "12-x", ""], ["2", "12-x", "aaa"],
                     ["3", "12-x", "bbb"]])
    e = _eras_section(sig, out)
    assert e["rows_per_cohort"] == {"bbb": 2, "legacy": 1, "aaa": 1}
    assert e["fills_per_cohort"] == {"legacy": 1, "aaa": 1, "bbb": 1}
    assert e["cohort_pooling_hazard"] is True


# ------------------------------------------ counting standard CS-1
def test_reconcile_ok_and_mismatch_never_raises():
    ok = cohort.reconcile(5, {"member": 3, "straddler": 1, "open": 1})
    assert ok["ok"] and ok["standard"] == cohort.COUNTING_STANDARD
    assert ok["line"].endswith("[OK]") and "n=5" in ok["line"]
    bad = cohort.reconcile(6, {"member": 3, "open": 1})
    assert not bad["ok"] and "MISMATCH: buckets sum to 4" in bad["line"]
    assert cohort.reconcile(0, {})["ok"]


def test_every_decision_fp_reader_uses_core_cohort():
    """CS-1 §2: attribution lives in ONE place. Any shipped module that
    reads the decision_fp field must interpret it through core.cohort - the
    five hand-rolled readers are how the cut-13 contamination happened.
    The writer (core/fill_ledger.py) and core/cohort.py itself are exempt."""
    import re
    from pathlib import Path
    root = Path(cohort.__file__).resolve().parents[1]
    exempt = {"core/cohort.py", "core/fill_ledger.py"}
    read = re.compile(r"""\.get\(\s*["']decision_fp["']|\[\s*["']decision_fp["']\s*\]""")
    offenders = []
    for sub in ("core", "scripts", "execution", "ml", "risk", "data"):
        for f in sorted((root / sub).rglob("*.py")):
            rel = f.relative_to(root).as_posix()
            if rel in exempt or "__pycache__" in rel:
                continue
            src = f.read_text(encoding="utf-8", errors="replace")
            if read.search(src) and "core.cohort" not in src:
                offenders.append(rel)
    for f in (root / "main.py", root / "runner.py"):
        src = f.read_text(encoding="utf-8", errors="replace")
        if read.search(src) and "core.cohort" not in src:
            offenders.append(f.name)
    assert offenders == [], (
        f"these read decision_fp without core.cohort: {offenders} - "
        f"see docs/law/counting_standard.md §2")
