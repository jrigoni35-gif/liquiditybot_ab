"""Performance-record layer + restart-coupling continuity (2026-07-20).

RECORDS — capture-only, no trading behavior reads them:
  outputs/fills.csv            per-fill implementation-shortfall record
  outputs/retrain_history.jsonl one row per retrain, deployed or rejected
  signal_history 'disp' column  the pipeline's final verdict per candidate

CONTINUITY — the auto-updater restarts the bot on every deploy; temporal
anchors that lived only in memory silently reset each time: the exit
escalation ladder, the ML-073 drought clock, and the state-change sampler
(one phantom bootstrap event per asset per restart). All three now ride
the snapshot.
"""
from pathlib import Path
from types import SimpleNamespace

from core.fill_ledger import COLS, append_fill, fill_row
from ml.retrain_log import append_retrain, retrain_record

ROOT = Path(__file__).resolve().parents[1]


# --- fills ledger ------------------------------------------------------------
def _order(side="buy", arrival=100.0):
    return SimpleNamespace(order_id="o1", position_id="p1", purpose="entry",
                           symbol="ETH/USD", side=side, ordertype="limit",
                           post_only=True, arrival_ref=arrival,
                           meta={"attempt": 2, "reason": "hard stop"},
                           remaining=0.5)


def test_fill_row_signs_slippage_adversely():
    ev = SimpleNamespace(fill_size=0.5, fill_price=100.1)
    r = fill_row(_order("buy"), ev, fees_delta=0.02, now=1000.0)
    assert r["slip_bps"] == 10.0            # bought above arrival = adverse
    r = fill_row(_order("sell"), ev, fees_delta=0.02, now=1000.0)
    assert r["slip_bps"] == -10.0           # sold above arrival = improvement
    r = fill_row(_order("buy", arrival=0.0), ev, 0.0, 1000.0)
    assert r["slip_bps"] == "" and r["arrival_ref"] == ""   # no mark: blank


def test_fill_ledger_appends_with_header(tmp_path):
    p = tmp_path / "fills.csv"
    ev = SimpleNamespace(fill_size=0.5, fill_price=100.1)
    append_fill(p, fill_row(_order(), ev, 0.02, 1000.0))
    # the second fill must be a DIFFERENT fill: two identical
    # (order_id, size, price, remaining) rows are the restart-replay
    # signature OM-085 now refuses (owed 62), and this test's subject is
    # the header, not the guard - test_fill_ledger_provenance owns that.
    ev2 = SimpleNamespace(fill_size=0.5, fill_price=100.2)
    append_fill(p, fill_row(_order(), ev2, 0.01, 1030.0))
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == ",".join(COLS)
    assert len(lines) == 3


def test_engine_ledgers_both_fill_branches():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert src.count("self._ledger_fill(order, event") == 2, \
        "entry AND exit fills must both reach the ledger"


# --- retrain history ---------------------------------------------------------
def test_retrain_record_shape_and_append(tmp_path):
    results = {"selected": "logistic", "admitted": ["logistic", "gbt"],
               "gated": ["mlp"],
               "logistic": {"mean_brier": 0.21}, "gbt": {"mean_brier": 0.23}}
    rec = retrain_record(1000.0, "auto", results, 2000, 71,
                         oof_brier=0.19, champion_bar=0.144, deployed=False)
    assert rec["family_brier"] == {"logistic": 0.21, "gbt": 0.23}
    assert rec["deployed"] is False and rec["live"] == 71
    p = tmp_path / "rh.jsonl"
    append_retrain(p, rec)
    append_retrain(p, dict(rec, deployed=True))
    import json
    rows = [json.loads(x) for x in
            p.read_text(encoding="utf-8").strip().splitlines()]
    assert len(rows) == 2 and rows[1]["deployed"] is True


def test_both_retrain_paths_write_history():
    # The destination literal used to be inlined at BOTH call sites. It now
    # lives once in ml/retrain_log.py as RETRAIN_HISTORY_PATH_DEFAULT, read
    # through the module so tests can rebind it (2026-07-31: the suite was
    # appending fixtures to the operator's real retrain_history.jsonl -
    # 305 of its 306 records). Pin the same contract against the new shape:
    # exactly one literal, and both paths resolving their default from it.
    owner = (ROOT / "ml" / "retrain_log.py").read_text(encoding="utf-8")
    assert 'RETRAIN_HISTORY_PATH_DEFAULT = "outputs/retrain_history.jsonl"' \
        in owner
    for path in ("main.py", "scripts/train_meta.py"):
        src = (ROOT / path).read_text(encoding="utf-8")
        assert "append_retrain(" in src, path
        assert "RETRAIN_HISTORY_PATH_DEFAULT" in src, path
        # CODE lines only. The first version of this pin tested the whole
        # file, so a COMMENT that merely named the path failed it - and
        # because scripts/auto_update.py gates every deploy on
        # `pytest -q -x`, that failure would refuse all updates including
        # its own repair. That is the identical self-bricking shape
        # 3f777aa fixed one commit earlier; caught here on 2026-08-01 when
        # the audit branch added exactly such a comment to train_meta.py.
        # The contract being pinned is that no CALL SITE re-inlines the
        # destination; prose about it is harmless.
        code = "\n".join(ln for ln in src.splitlines()
                         if not ln.lstrip().startswith("#"))
        assert "retrain_history.jsonl" not in code, \
            f"{path} re-inlined the destination - rebinding the shared " \
            f"default would no longer reach it"
    # the auto path records REJECTED challengers too (before the early return)
    eng = (ROOT / "main.py").read_text(encoding="utf-8")
    assert eng.index("append_retrain(") < eng.index("if not _deploy_ok:")


def test_retrain_record_family_calib_gap():
    results = {"selected": "logistic",
               "logistic": {"mean_brier": 0.21, "calib_gap": 0.041},
               "gbt": {"mean_brier": 0.23}}          # no calib_gap: omitted
    rec = retrain_record(1000.0, "auto", results, 2000, 71,
                         oof_brier=0.19, champion_bar=None, deployed=False)
    assert rec["family_calib_gap"] == {"logistic": 0.041}
    assert rec["family_brier"] == {"logistic": 0.21, "gbt": 0.23}


def test_family_metric_helper_rounds_and_filters():
    from ml.retrain_log import family_metric
    results = {"gbt": {"calib_gap": 0.123456}, "mlp": "not-a-dict"}
    assert family_metric(results, "calib_gap") == {"gbt": 0.12346}
    assert family_metric(results, "absent") == {}


# --- disposition column ------------------------------------------------------
def test_disposition_reaches_the_candidate_row(tmp_path):
    import numpy as np

    from ml.features import FEATURE_NAMES
    from ml.history import CandidateLabeler, HistoryStore
    hs = HistoryStore(str(tmp_path / "h.csv"))
    cb = CandidateLabeler(hs, {})
    f = np.zeros(len(FEATURE_NAMES))
    cb.register("ETH", "long", f, 0.003, 1000)
    cb.mark_disposition("ETH", "long", "SZ-030")
    assert cb._cands[-1]["disp"] == "SZ-030"
    cb.mark_disposition("BTC", "short", "entered")   # no match: silent no-op
    assert cb._cands[-1]["disp"] == "SZ-030"


def test_live_rows_carry_entered_disposition(tmp_path):
    import csv

    import numpy as np

    from ml.features import FEATURE_NAMES
    from ml.history import HistoryStore
    hs = HistoryStore(str(tmp_path / "h.csv"))
    hs.log_entry("p1", "ETH", "long",
                 np.zeros(len(FEATURE_NAMES)))
    hs.log_close("p1", 5.0)
    row = next(csv.DictReader(open(hs.path, encoding="utf-8")))
    assert row["disp"] == "entered"


def test_engine_marks_all_verdicts():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert src.count("self._mark_cand(asset, signal.direction") >= 7, \
        "capped, breaker, manip, sizer, pretrade + both entry routes"


# --- restart continuity ------------------------------------------------------
def test_sampler_state_survives_restore():
    from ml.event_sampler import StateChangeSampler
    a = StateChangeSampler({"cusum_enabled": True, "cusum_k": 3.0})
    a.observe("ETH", 100.0, sigma_bar_pct=0.3)
    b = StateChangeSampler({"cusum_enabled": True, "cusum_k": 3.0})
    b.from_dict(a.to_dict())
    assert b.observe("ETH", 100.0, sigma_bar_pct=0.3) is False, \
        "restore must not re-fire the bootstrap event"


def test_snapshot_carries_the_continuity_anchors():
    src = (ROOT / "core" / "persistence.py").read_text(encoding="utf-8")
    for key in ("exit_attempts", "drought_elapsed_s", '"scs"'):
        assert key in src, key
    # drought stores elapsed RUNNING time, restored against now (downtime
    # never counts as a signal drought)
    assert "time.time() - float(data[\"drought_elapsed_s\"])" in src
