"""tests/test_gc_pusher_owed_metrics.py — the 2026-08-17 owed-metrics batch.

Five new series + the second presence-guard sweep, pinned planted-defect
style (each test writes the exact bad/good form and watches the code
respond, per the review that shipped this batch):

  * liquiditybot_ml_loaded_rows   status ml.load_stats.rows (ml/history.py
                                  :1774 rows=len(w), runner.py:1318)
  * liquiditybot_dry_run          status mode (runner.py:1193 vocabulary),
                                  presence-guarded FROM BIRTH — absent must
                                  never render as live
  * liquiditybot_ml_orphan_ratio  tail of outputs/retrain_history.jsonl
                                  (ml/retrain_log.py:57-61)
  * liquiditybot_cohort_closes/_min_n
                                  cached subprocess of cohort_eval.py
                                  --json era4 — NEVER the gross/net means
  * liquiditybot_ml_lineage_events{event=}
                                  outputs/models/registry.jsonl, BOUNDED
                                  vocabulary (the _ERA_KNOWN clamp law)

The ledger-derived series live in collect_aux(), NOT collect(): the
_ALWAYS_ON pin and the board coverage gate recompute their universes by
running collect(), and on-disk-ledger metrics inside it would make those
pins machine-dependent. These tests rebind the module path attributes
(the ml/retrain_log.py rebindable-default precedent) so nothing here
touches the real outputs/.

Absent->no-series directions for the guard-batch-2 bools are pinned in
tests/test_dashboard_no_value.py::test_absent_bool_keys_emit_no_series;
this file pins the present->right-value direction and the new series.
"""
import json
import textwrap
import time

import pytest

import scripts.gc_pusher as gp


def _names(metrics):
    return {m["name"] for m in metrics}


def _val(metrics, name, **labels):
    for mtr in metrics:
        if mtr["name"] != name:
            continue
        dp = mtr["gauge"]["dataPoints"][0]
        got = {a["key"]: a["value"]["stringValue"]
               for a in dp.get("attributes", [])}
        if all(got.get(k) == v for k, v in labels.items()):
            return dp["asDouble"]
    return None


def _collect(tmp_path, extra):
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(),
                             "runner_state": "RUNNING", **extra}),
                 encoding="utf-8")
    return gp.collect(str(p))


# ---- liquiditybot_ml_loaded_rows -----------------------------------------
def test_loaded_rows_emitted_from_load_stats(tmp_path):
    m = _collect(tmp_path, {"ml": {"load_stats": {"rows": 4897}}})
    assert _val(m, "liquiditybot_ml_loaded_rows") == 4897.0


def test_loaded_rows_absent_key_no_series(tmp_path):
    # load_stats present but rows missing (a pre-batch writer), and no
    # load_stats at all (no retrain yet): both must stay silent
    for ml in ({"load_stats": {"live_clean": 3}}, {}):
        m = _collect(tmp_path, {"ml": ml})
        assert "liquiditybot_ml_loaded_rows" not in _names(m)


def test_loaded_rows_bool_is_not_a_count(tmp_path):
    # bool is an int subclass; a corrupted rows=true must not emit 1.0
    m = _collect(tmp_path, {"ml": {"load_stats": {"rows": True}}})
    assert "liquiditybot_ml_loaded_rows" not in _names(m)


# ---- liquiditybot_dry_run ------------------------------------------------
@pytest.mark.parametrize("mode,expect", [
    ("DRY_RUN", 1.0),
    ("LIVE_ARMED", 0.0),
    ("LIVE_DISARMED", 0.0),     # bot.dry_run is False while disarmed too
    ("garbage", -1.0),          # unknown string -> UNKNOWN sentinel, never
                                # coerced onto either real state
])
def test_dry_run_mode_vocabulary(tmp_path, mode, expect):
    m = _collect(tmp_path, {"mode": mode})
    assert _val(m, "liquiditybot_dry_run") == expect


def test_dry_run_absent_mode_emits_no_series(tmp_path):
    # THE guard this metric was born with: an absent mode key must never
    # render as live (0.0) — no series at all
    m = _collect(tmp_path, {})
    assert "liquiditybot_dry_run" not in _names(m)


# ---- guard batch 2: present bools carry the right value ------------------
def test_guarded_bools_present_emit_truthful_values(tmp_path):
    m = _collect(tmp_path, {
        "positions": [],
        "ws_kraken": {"connected": False},
        "moomoo": {"available": True, "options_available": False},
        "monitor": {"use_model": True},
        "ml": {"retrain_flag": False},
    })
    assert _val(m, "liquiditybot_positions_open") == 0.0
    assert _val(m, "liquiditybot_ws_kraken_connected") == 0.0
    assert _val(m, "liquiditybot_moomoo_available") == 1.0
    assert _val(m, "liquiditybot_moomoo_options_available") == 0.0
    assert _val(m, "liquiditybot_ml_use_model") == 1.0
    assert _val(m, "liquiditybot_ml_retrain_flag") == 0.0


# ---- liquiditybot_ml_orphan_ratio ----------------------------------------
@pytest.fixture
def retrain_ledger(tmp_path, monkeypatch):
    p = tmp_path / "retrain_history.jsonl"
    monkeypatch.setattr(gp, "RETRAIN_HISTORY_PATH", p)
    return p


def test_orphan_ratio_reads_the_last_record(retrain_ledger):
    retrain_ledger.write_text(
        json.dumps({"ts": 1.0, "orphan_ratio": 2.5}) + "\n"
        + json.dumps({"ts": 2.0, "orphan_ratio": 48.4}) + "\n",
        encoding="utf-8")
    m = gp._orphan_ratio_metrics(1000.0)
    assert _val(m, "liquiditybot_ml_orphan_ratio") == 48.4


def test_orphan_ratio_steps_back_over_a_torn_tail(retrain_ledger):
    # durable_append heals tears, but the pusher may race a mid-write:
    # the torn final fragment is skipped, the last COMPLETE record wins
    retrain_ledger.write_text(
        json.dumps({"ts": 1.0, "orphan_ratio": 3.2}) + "\n"
        + '{"ts": 2.0, "orphan_ra', encoding="utf-8")
    m = gp._orphan_ratio_metrics(1000.0)
    assert _val(m, "liquiditybot_ml_orphan_ratio") == 3.2


def test_orphan_ratio_null_in_last_record_is_honest_absence(retrain_ledger):
    # the LAST record decides; a None ratio (no trained_rows watermark)
    # must NOT walk deeper into history for a stale value
    retrain_ledger.write_text(
        json.dumps({"ts": 1.0, "orphan_ratio": 9.9}) + "\n"
        + json.dumps({"ts": 2.0, "orphan_ratio": None}) + "\n",
        encoding="utf-8")
    assert gp._orphan_ratio_metrics(1000.0) == []


def test_orphan_ratio_absent_or_empty_file_no_series(retrain_ledger):
    assert gp._orphan_ratio_metrics(1000.0) == []      # file absent
    retrain_ledger.write_text("", encoding="utf-8")
    assert gp._orphan_ratio_metrics(1000.0) == []      # file empty


def test_orphan_ratio_unreadable_path_cannot_black_out_the_batch(
        tmp_path, monkeypatch):
    # a directory where the file should be: open() raises OSError; the
    # helper must swallow it (the _num isolation idiom) and emit nothing
    monkeypatch.setattr(gp, "RETRAIN_HISTORY_PATH", tmp_path)
    assert gp._orphan_ratio_metrics(1000.0) == []


# ---- liquiditybot_ml_lineage_events --------------------------------------
@pytest.fixture
def registry_ledger(tmp_path, monkeypatch):
    p = tmp_path / "registry.jsonl"
    monkeypatch.setattr(gp, "MODEL_REGISTRY_PATH", p)
    return p


def test_lineage_counts_and_vocabulary_clamp(registry_ledger):
    rows = [{"event": "registered", "model_id": "aaa"},
            {"event": "deployed", "model_id": "aaa"},
            {"event": "registered", "model_id": "bbb"},
            {"event": "rejected", "model_id": "bbb"},
            {"event": "retired", "model_id": "aaa"},        # -> other
            {"event": "integrity_fail", "model_id": "ccc"},  # -> other
            {"no_event_key": 1}]                             # -> other
    text = "\n".join(json.dumps(r) for r in rows) + "\n"
    # planted defect: a garbage line must be skipped, never counted
    text += "NOT JSON AT ALL\n"
    registry_ledger.write_text(text, encoding="utf-8")
    m = gp._lineage_metrics(1000.0)
    assert _val(m, "liquiditybot_ml_lineage_events", event="registered") == 2.0
    assert _val(m, "liquiditybot_ml_lineage_events", event="deployed") == 1.0
    assert _val(m, "liquiditybot_ml_lineage_events", event="rejected") == 1.0
    assert _val(m, "liquiditybot_ml_lineage_events", event="other") == 3.0
    # BOUNDED vocabulary: exactly these four labels, nothing echoed through
    labels = {a["value"]["stringValue"] for mtr in m
              for a in mtr["gauge"]["dataPoints"][0]["attributes"]}
    assert labels == {"registered", "deployed", "rejected", "other"}
    # NEVER model ids as labels — the _ERA_KNOWN cardinality law
    keys = {a["key"] for mtr in m
            for a in mtr["gauge"]["dataPoints"][0]["attributes"]}
    assert keys == {"event"}


def test_lineage_quiet_buckets_emit_zero_not_no_data(registry_ledger):
    registry_ledger.write_text(
        json.dumps({"event": "registered", "model_id": "aaa"}) + "\n",
        encoding="utf-8")
    m = gp._lineage_metrics(1000.0)
    # one parsed row -> ALL four buckets exist, zeros included, so a
    # rate() on a quiet bucket reads 0 rather than no-data
    assert _val(m, "liquiditybot_ml_lineage_events", event="rejected") == 0.0
    assert _val(m, "liquiditybot_ml_lineage_events", event="other") == 0.0


def test_lineage_absent_empty_or_all_garbage_file_no_series(registry_ledger):
    assert gp._lineage_metrics(1000.0) == []           # absent
    registry_ledger.write_text("", encoding="utf-8")
    assert gp._lineage_metrics(1000.0) == []           # empty
    registry_ledger.write_text("garbage\n\x00\n", encoding="utf-8")
    assert gp._lineage_metrics(1000.0) == []           # zero parseable rows


# ---- cohort subprocess cache ---------------------------------------------
_COHORT_JSON = {
    "era4": {"n": 37, "min_n": 50, "progress": "37/50",
             # the FORBIDDEN fields, planted on purpose: the parser must
             # never let them near a gauge (era-4 moratorium: the accruing
             # gate numbers are not a trend)
             "gross_mean_pct": -0.123, "net_mean_pct": -0.456,
             "gross_median_pct": -0.1, "net_median_pct": -0.4},
}


@pytest.fixture
def cohort_env(tmp_path, monkeypatch):
    """Planted cohort_eval stand-in that counts its own invocations."""
    calls = tmp_path / "calls.txt"
    script = tmp_path / "fake_cohort_eval.py"
    script.write_text(textwrap.dedent(f"""\
        import json, pathlib, sys
        c = pathlib.Path({str(calls)!r})
        c.write_text(c.read_text() + "x" if c.exists() else "x")
        print(json.dumps({json.dumps(_COHORT_JSON)}))
        """), encoding="utf-8")
    monkeypatch.setattr(gp, "COHORT_SCRIPT", script)
    monkeypatch.setattr(gp, "_cohort_cache",
                        {"next_attempt": 0.0, "values": None})
    return calls


def _n_calls(calls):
    return len(calls.read_text()) if calls.exists() else 0


def test_cohort_parses_only_n_and_min_n_never_the_means(cohort_env):
    m = gp._cohort_metrics(1000.0)
    assert _val(m, "liquiditybot_cohort_closes") == 37.0
    assert _val(m, "liquiditybot_cohort_min_n") == 50.0
    # the whole emitted surface is those two names — no gross, no net
    assert _names(m) == {"liquiditybot_cohort_closes",
                         "liquiditybot_cohort_min_n"}
    for name in _names(m):
        assert "gross" not in name and "net" not in name


def test_cohort_cache_no_per_push_subprocess(cohort_env):
    # planted defect the cache exists to prevent: a per-push invocation.
    # 28 more pushes inside the 1800s window (60s cadence keeps the last
    # at t+1740 < t+1800) must cost exactly ONE subprocess total.
    gp._cohort_metrics(1000.0)
    for i in range(28):
        m = gp._cohort_metrics(1000.0 + 60.0 * (i + 1))   # 60s push cadence
        assert _val(m, "liquiditybot_cohort_closes") == 37.0  # cache serves
    assert _n_calls(cohort_env) == 1
    # ...and the cadence boundary re-invokes
    gp._cohort_metrics(1000.0 + gp.COHORT_MIN_INTERVAL_SEC + 1.0)
    assert _n_calls(cohort_env) == 2


def test_cohort_failing_script_no_series_no_exception_no_hammering(
        tmp_path, monkeypatch):
    calls = tmp_path / "calls.txt"
    script = tmp_path / "failing_cohort_eval.py"
    script.write_text(textwrap.dedent(f"""\
        import pathlib, sys
        c = pathlib.Path({str(calls)!r})
        c.write_text(c.read_text() + "x" if c.exists() else "x")
        print("no postmortem data")
        sys.exit(1)
        """), encoding="utf-8")
    monkeypatch.setattr(gp, "COHORT_SCRIPT", script)
    monkeypatch.setattr(gp, "_cohort_cache",
                        {"next_attempt": 0.0, "values": None})
    assert gp._cohort_metrics(1000.0) == []          # absent = honest
    assert gp._cohort_metrics(1060.0) == []          # still inside window
    assert len(calls.read_text()) == 1               # failure cached too


def test_cohort_malformed_json_and_wrong_shape_no_series(
        tmp_path, monkeypatch):
    monkeypatch.setattr(gp, "_cohort_cache",
                        {"next_attempt": 0.0, "values": None})
    script = tmp_path / "bad_json.py"
    script.write_text("print('this is not json')", encoding="utf-8")
    monkeypatch.setattr(gp, "COHORT_SCRIPT", script)
    assert gp._cohort_metrics(1000.0) == []
    # right JSON, wrong shape: min_n missing -> refuse, never guess
    monkeypatch.setattr(gp, "_cohort_cache",
                        {"next_attempt": 0.0, "values": None})
    script2 = tmp_path / "wrong_shape.py"
    script2.write_text('import json; print(json.dumps({"era4": {"n": 3}}))',
                       encoding="utf-8")
    monkeypatch.setattr(gp, "COHORT_SCRIPT", script2)
    assert gp._cohort_metrics(1000.0) == []


def test_cohort_timeout_is_bounded_and_isolated(tmp_path, monkeypatch):
    # planted hang: the subprocess wall (COHORT_TIMEOUT_SEC) must cut it
    # and the failure must degrade to no-series, never an exception
    script = tmp_path / "hanging_cohort_eval.py"
    script.write_text("import time; time.sleep(30)", encoding="utf-8")
    monkeypatch.setattr(gp, "COHORT_SCRIPT", script)
    monkeypatch.setattr(gp, "COHORT_TIMEOUT_SEC", 1.0)
    monkeypatch.setattr(gp, "_cohort_cache",
                        {"next_attempt": 0.0, "values": None})
    assert gp._cohort_metrics(1000.0) == []


def test_cohort_missing_script_no_series(tmp_path, monkeypatch):
    monkeypatch.setattr(gp, "COHORT_SCRIPT", tmp_path / "does_not_exist.py")
    monkeypatch.setattr(gp, "_cohort_cache",
                        {"next_attempt": 0.0, "values": None})
    assert gp._cohort_metrics(1000.0) == []


def test_real_cohort_script_speaks_the_parsed_shape():
    """The parser trusts era4.n / era4.min_n; pin that the REAL script
    still writes both (a rename there would silently kill the series).
    Static source check, not an invocation — the real script needs the
    operator's outputs/ and a subprocess would drag the suite."""
    src = (gp.COHORT_SCRIPT).read_text(encoding="utf-8")
    assert '"min_n": ERA4_MIN_N, "n": n' in src, (
        "cohort_eval.py era4_section no longer writes the n/min_n shape "
        "gc_pusher._run_cohort_eval parses — update both together")


# ---- collect_aux composition ---------------------------------------------
def test_collect_aux_isolates_a_raising_collector(monkeypatch):
    def boom(_ts):
        raise RuntimeError("planted")
    ok = [gp.gauge("liquiditybot_ml_orphan_ratio", 1.5, ts=1000.0)]
    monkeypatch.setattr(gp, "_orphan_ratio_metrics", lambda ts: ok)
    monkeypatch.setattr(gp, "_lineage_metrics", boom)
    monkeypatch.setattr(gp, "_cohort_metrics", lambda now: [])
    monkeypatch.setattr(gp, "_veto_quality_metrics", lambda now: [])
    # 2026-08-31: ceiling-bar collector joined the composition; patched out
    # like its siblings so this pin tests ISOLATION, not live outputs/.
    monkeypatch.setattr(gp, "_ceiling_bar_metrics", lambda now: [])
    out = gp.collect_aux(1000.0)          # must not raise
    assert _names(out) == {"liquiditybot_ml_orphan_ratio"}


def test_collect_aux_rides_the_main_push(monkeypatch):
    # main() must push collect() + collect_aux() as ONE batch; pin the
    # composition at the source so a refactor cannot silently drop it
    src = (gp._REPO_ROOT / "scripts" / "gc_pusher.py") \
        .read_text(encoding="utf-8")
    body = src[src.index("def main("):]
    assert "collect(cfg[\"status\"]) + collect_aux()" in body


def test_aux_metrics_stay_out_of_collect(tmp_path):
    """The design line this batch drew: collect() must NEVER emit the
    ledger-derived names, or the _ALWAYS_ON pin and the board coverage
    gate become machine-dependent on real outputs/ content."""
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(),
                             "runner_state": "RUNNING"}), encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not names & {"liquiditybot_ml_orphan_ratio",
                        "liquiditybot_ml_lineage_events",
                        "liquiditybot_cohort_closes",
                        "liquiditybot_cohort_min_n"}


# ---- era-scoped cohort count (2026-09-05) --------------------------------
# The gauge published era4["n"], the ERA-4 pre-registered population, which
# CLAUDE.md declares CLOSED (read out COST_BOUND at n=54). That counter is not
# era-scoped - era4_trips() selects on timestamp and fill-honesty predicates
# and exec_era is in NONE of them - so it pools every execution era. On the
# board it renders as the gate headline OVERSHOOTING its target while the era
# actually accruing sits well short: "done" about a question still open.
_COHORT_JSON_ERAS = {
    "era4": {"n": 96, "min_n": 50, "progress": "96/50"},
    "homogeneity": {
        "current_era": "9-16ec821e",
        "by_era": {"7-e7d5ca1a": 56, "8-ca55e2ba": 3, "9-16ec821e": 26},
        "era_partial_stamp_trips": 4, "era_straddling_trips": 6,
        "era_unstamped_trips": 1,
    },
}


@pytest.fixture
def cohort_env_eras(tmp_path, monkeypatch):
    script = tmp_path / "fake_cohort_eval_eras.py"
    script.write_text(
        "import json\nprint(json.dumps(%s))\n" % json.dumps(_COHORT_JSON_ERAS),
        encoding="utf-8")
    monkeypatch.setattr(gp, "COHORT_SCRIPT", script)
    monkeypatch.setattr(gp, "_cohort_cache",
                        {"next_attempt": 0.0, "values": None})


def test_cohort_gauge_publishes_the_ACCRUING_era_not_the_pooled_count(
        cohort_env_eras):
    """THE REGRESSION. Pooled is 96 against a floor of 50 (reads overshot);
    the accruing era is 26."""
    m = gp._cohort_metrics(1000.0)
    n = _val(m, "liquiditybot_cohort_closes")
    assert n == 26.0, (
        f"gauge published {n} - 96 is the pooled era-4 population and reads "
        f"as the gate having overshot, while era-6 is at 26 of 50")
    assert _val(m, "liquiditybot_cohort_min_n") == 50.0


def test_cohort_gauge_still_only_emits_a_count_and_its_floor(cohort_env_eras):
    """The moratorium bound is unchanged by the era scoping: a COUNT and its
    pre-registered floor, never a gross/net trend."""
    m = gp._cohort_metrics(1000.0)
    assert _names(m) == {"liquiditybot_cohort_closes",
                         "liquiditybot_cohort_min_n"}


def test_cohort_gauge_falls_back_to_pooled_when_segmentation_absent(
        cohort_env):
    """An older cohort_eval emits no homogeneity block. The gauge must keep
    publishing something rather than going dark - a missing gauge and a zero
    gauge are indistinguishable on a board."""
    m = gp._cohort_metrics(1000.0)
    assert _val(m, "liquiditybot_cohort_closes") == 37.0
