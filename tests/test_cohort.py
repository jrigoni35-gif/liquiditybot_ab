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
