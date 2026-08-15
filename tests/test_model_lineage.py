"""Model lineage: the registry must be able to say WHICH model was deciding.

Found 2026-08-14: outputs/models/registry.jsonl held 134 `registered` events,
2 `integrity_fail`, and ZERO `deployed` or `retired` ones — so the ledger could
not answer the question its own module docstring promises ("exactly which model
was making decisions at 3:47am on Tuesday"). `note()` supported both events;
nothing called either.

Also pinned here: the orphan-ratio telemetry. ML-083's era-orphan unlock keys on
`trained_rows > n_rows`, and that ratio was recoverable only by hand-joining two
ledgers — which is why a 48x orphan promoted a negative-skill model unnoticed.
These are REPORT-ONLY fields; no test here asserts any deploy DECISION, because
the decision path is frozen under the era-4 moratorium.
"""
import json

from ml.registry import ModelRegistry
from ml.retrain_log import retrain_record

RESULTS = {"selected": "logistic", "admitted": ["logistic"],
           "gated": ["gbt", "blend", "mlp", "adaptive_gbt"],
           "logistic": {"mean_brier": 0.33105, "calib_gap": 0.06356}}


# --- orphan-ratio telemetry -------------------------------------------------
def test_orphan_ratio_reproduces_the_live_48x():
    """The real 2026-08-14 promotion: champion watermark 10,217 vs a 211-row
    matrix. ML-083's own comment records it was designed for 3.2x."""
    rec = retrain_record(1000.0, "auto", RESULTS, 211, 5,
                         oof_brier=0.21887, champion_bar=0.21936,
                         deployed=True, trained_rows=10217)
    assert rec["trained_rows"] == 10217
    assert rec["orphan_ratio"] == round(10217 / 211, 4)
    assert rec["orphan_ratio"] > 48.0, "the finding is the SCALE of the orphan"


def test_trained_rows_is_optional_and_back_compatible():
    """Every pre-existing caller omits it (public interfaces stay stable —
    invariant 7). Omitting must log None, never raise."""
    rec = retrain_record(1000.0, "auto", RESULTS, 2000, 71,
                         oof_brier=0.19, champion_bar=0.144, deployed=False)
    assert rec["trained_rows"] is None
    assert rec["orphan_ratio"] is None
    assert rec["deployed"] is False and rec["rows"] == 2000


def test_orphan_ratio_none_on_cold_start_and_empty_matrix():
    """No champion (trained_rows 0/None) and an empty matrix must both yield
    None rather than 0.0 or ZeroDivisionError — a missing ratio is not a
    ratio of zero, and this file exists because silent numbers cost a day."""
    cold = retrain_record(1.0, "auto", RESULTS, 500, 5, 0.2, None,
                          False, trained_rows=0)
    assert cold["orphan_ratio"] is None
    empty = retrain_record(1.0, "auto", RESULTS, 0, 0, 0.2, None,
                           False, trained_rows=900)
    assert empty["orphan_ratio"] is None


def test_record_is_json_serializable():
    """It is appended as JSONL; a non-serializable value silently loses the
    row through append_retrain's never-raise contract."""
    rec = retrain_record(1.0, "auto", RESULTS, 211, 5, 0.21887, 0.21936,
                         True, trained_rows=10217)
    assert json.loads(json.dumps(rec))["orphan_ratio"] == rec["orphan_ratio"]


# --- registry lifecycle -----------------------------------------------------
def _events(reg):
    return [json.loads(x) for x in
            reg.ledger.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_deployed_and_retired_events_are_recorded_and_chained(tmp_path):
    reg = ModelRegistry(str(tmp_path))
    art = tmp_path / "meta_model.json"
    art.write_text(json.dumps({"kind": "logistic"}), encoding="utf-8")
    old = reg.register(str(art), {"kind": "gbt", "rows": 10217})
    assert old, "registration must return a model_id"

    reg.note("deployed", "aaaabbbbcccc",
             {"oof_brier": 0.21887, "rows": 211, "source": "auto_retrain"})
    reg.note("retired", old, {"superseded_by": "aaaabbbbcccc",
                              "reason": "auto_retrain_promotion"})

    kinds = [e.get("event") for e in _events(reg)]
    assert kinds == ["registered", "deployed", "retired"]
    # the whole point of the ledger: it must remain verifiable afterwards
    chain = reg.verify_chain()
    assert chain["ok"] is True, chain.get("reason")
    assert chain["chained"] == 3


def test_deployed_event_carries_the_promotion_context(tmp_path):
    """A bare `deployed` row answers 'which' but not 'on what evidence'."""
    reg = ModelRegistry(str(tmp_path))
    reg.note("deployed", "aaaabbbbcccc",
             {"oof_brier": 0.21887, "rows": 211, "prev_trained_rows": 10217,
              "source": "auto_retrain"})
    d = _events(reg)[0]["detail"]
    assert d["rows"] == 211 and d["prev_trained_rows"] == 10217
    assert d["source"] == "auto_retrain"


def test_note_never_raises_when_the_ledger_is_unwritable(tmp_path):
    """Lineage must never take down the retrain path it only observes."""
    reg = ModelRegistry(str(tmp_path / "nested"))
    reg.ledger = tmp_path / "nested" / "does" / "not" / "exist" / "r.jsonl"
    reg.note("deployed", "aaaabbbbcccc", {"source": "auto_retrain"})


def test_lineage_reads_on_meta_are_attribute_guarded():
    """Source-level pin, and it earned its place the hard way.

    The first cut of this feature captured the outgoing champion with a bare
    `self.meta.model_id`. It sat OUTSIDE the try/except guarding the registry
    call, so a harness whose `meta` double lacked the attribute raised into
    `_maybe_auto_retrain`'s outer fail-safe and ABORTED THE DEPLOY —
    test_auto_retrain_stale_gate_cas went red on `reload_calls == []`.

    Observability may degrade to "unknown"; it may never decide whether a
    retrain completes. Guarded reads are the mechanism, so pin the mechanism —
    a future bare read reintroduces exactly this failure and the unit tests
    above would all still pass.
    """
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    for attr in ("model_id", "trained_rows"):
        bare = f"self.meta.{attr}"
        guarded = f'getattr(self.meta, "{attr}"'
        assert guarded in src, f"lineage must read meta.{attr} via getattr"
        # the deploy GATE legitimately reads trained_rows bare (ML-083 keys on
        # it and a missing watermark there must fail loudly, not silently) —
        # so this asserts presence of the guard, not absence of every bare read
        assert src.count(guarded) >= 1, f"no guarded read of meta.{attr}"
        del bare
