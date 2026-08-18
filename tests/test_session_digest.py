"""Acceptance tests for core/session_digest.py — the reconciled run summary
and its SD-* detectors. Fixtures are minimal synthetic outputs dirs; the audit
chain is written through the real AuditTrail so chain verification is exercised."""
import json
import time
from pathlib import Path

from core.audit import AuditTrail
from core.session_digest import (SD_AUDIT_NOISE, SD_LIQUIDITY_VETO,
                                 SD_MODEL_STARVATION, SD_STREAM_INCONSISTENCY,
                                 build_digest, render_markdown, write_digest)

PM_HEADER = ("ts,position_id,asset,direction,p_win,expected_pct,realized_pct,"
             "shortfall_pct,cause,cost_overrun_bps,mfe_pct,mae_pct,"
             "recovered_after_stop,regime_entry,regime_exit")


def _fixture(tmp: Path, *, spoofy_cycles=0, retrain=0, live_rows=0,
             candidate_rows=0, postmortems=(), realized_pnl=0.0,
             events_age_h=0.0):
    """Build a minimal outputs/ dir. `postmortems` is a list of
    (realized_pct, mae_pct, cause) tuples. Timestamps anchor to NOW (the
    AuditTrail stamps wall clock, so everything else must live on the same
    timeline for the recent lens to see it); `events_age_h` pushes the
    spoofy events into the past to exercise the lens cut."""
    o = tmp / "outputs"
    o.mkdir(parents=True, exist_ok=True)
    now = time.time()

    at = AuditTrail(str(o / "audit.jsonl"))
    at.log("fault", "FT-020", "startup validation passed",
           {"from": "INIT", "to": "ARMED"})
    for _ in range(retrain):
        at.log("ml_governor", "ML-032", "retrain requested", {})

    ev = []
    ev_ts = now - events_age_h * 3600.0
    for i in range(spoofy_cycles):
        ev.append(json.dumps({"ts": ev_ts + i, "level": "INFO", "logger": "m",
                              "msg": f"[btc] liquidity=spoofy spread=0.0bps d={i}"}))
    (o / "events.jsonl").write_text(
        ("\n".join(ev) + "\n") if ev else "", encoding="utf-8")

    eq = ["ts,equity,daily_pnl"] + [f"{now - 600 + i:.0f},10000.00,0.00"
                                    for i in range(20)]
    (o / "equity.csv").write_text("\n".join(eq) + "\n", encoding="utf-8")

    state = {"portfolio": {"starting_capital": 10000.0,
                           "realized_pnl_total": realized_pnl,
                           "fees_paid_total": 0.0, "positions": []},
             "monitor": {"level": 0, "use_model": True, "brier": None}}
    (o / "state.json").write_text(json.dumps(state), encoding="utf-8")

    sig = ["position_id,asset,direction,source,label"]
    sig += [f"live-{i},ETH,long,live,1" for i in range(live_rows)]
    sig += [f"cand-{i},ETH,long,candidate,0" for i in range(candidate_rows)]
    (o / "signal_history.csv").write_text("\n".join(sig) + "\n", encoding="utf-8")

    if postmortems:
        rows = [PM_HEADER]
        for k, (rp, mae, cause) in enumerate(postmortems):
            rows.append(f"{2000 + k},pid{k},ETH,long,0.62,0.18,{rp},0,{cause},"
                        f"16,2.5,{mae},0,bull_quiet,bull_quiet")
        (o / "postmortem_summary.csv").write_text("\n".join(rows) + "\n",
                                                  encoding="utf-8")
    return o


def _ids(digest):
    return {g["id"] for g in digest["diagnostics"]}


def test_empty_dir_is_safe(tmp_path):
    """Missing streams must degrade to a partial digest, never raise."""
    d = build_digest(tmp_path / "nope")
    assert "verdict" in d and isinstance(d["diagnostics"], list)
    assert d["pnl"]["open_positions"] == 0


def test_detects_starvation_noise_and_liquidity(tmp_path):
    # 60 retrain records -> audit trail large enough (>50) and dominated,
    # exercising SD-004 alongside the starvation/liquidity detectors
    _fixture(tmp_path, spoofy_cycles=15, retrain=60, live_rows=0)
    d = build_digest(tmp_path / "outputs")
    ids = _ids(d)
    assert SD_MODEL_STARVATION in ids      # cold model + repeated retrain
    assert SD_AUDIT_NOISE in ids           # ML-032 dominates
    assert SD_LIQUIDITY_VETO in ids        # spoofy 100% of cycles
    assert d["audit"]["retrain_requests"] == 60
    assert d["events"]["spoofy_frac"] == 1.0
    assert d["audit"]["chain_ok"] is True  # real chain verifies


def test_detects_fabricated_postmortem(tmp_path):
    # realized -18% with MAE ~0 is internally impossible -> SD-005 error
    _fixture(tmp_path, live_rows=2, postmortems=[(-18.47, 0.0, "underperformance")])
    d = build_digest(tmp_path / "outputs")
    assert SD_STREAM_INCONSISTENCY in _ids(d)
    top = d["diagnostics"][0]
    assert top["id"] == SD_STREAM_INCONSISTENCY and top["severity"] == "error"
    assert d["postmortems"]["impossible_count"] == 1


def test_real_loss_with_matching_excursion_is_not_flagged(tmp_path):
    # a genuine loss whose MAE explains it must NOT trip SD-005
    _fixture(tmp_path, live_rows=3, postmortems=[(-6.0, -7.5, "alpha_wrong")])
    d = build_digest(tmp_path / "outputs")
    assert SD_STREAM_INCONSISTENCY not in _ids(d)
    assert d["postmortems"]["impossible_count"] == 0


def test_chain_break_detected(tmp_path):
    o = _fixture(tmp_path, live_rows=1)
    # corrupt a middle record to break the hash chain
    p = o / "audit.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    lines.insert(1, json.dumps({"seq": 99, "ts": 1.0, "src": "x", "code": "Z",
                                "msg": "tamper", "data": {}, "prev": "dead",
                                "h": "beef"}))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    d = build_digest(o)
    assert d["audit"]["chain_ok"] is False
    assert "SD-007" in _ids(d)


def test_render_markdown_is_ascii(tmp_path):
    """The report is printed to a Windows cp1252 console, so it must encode
    cleanly as ASCII (no em-dashes, arrows, or emoji)."""
    _fixture(tmp_path, spoofy_cycles=12, retrain=6)
    d = build_digest(tmp_path / "outputs")
    md = render_markdown(d)
    md.encode("ascii")  # raises UnicodeEncodeError if any non-ascii slipped in


def test_write_digest_persists_both_artifacts(tmp_path):
    _fixture(tmp_path, live_rows=1)
    d = write_digest(tmp_path / "outputs")
    assert (tmp_path / "outputs" / "session_digest.json").exists()
    assert (tmp_path / "outputs" / "session_digest.md").exists()
    reloaded = json.loads(
        (tmp_path / "outputs" / "session_digest.json").read_text(encoding="utf-8"))
    assert reloaded["verdict"] == d["verdict"]


def test_recent_lens_ignores_cured_history(tmp_path):
    """The 2026-08-18 fix: spoofy spam that ended days ago must not keep
    firing SD-003 every session. Same data, old timestamps -> no verdict;
    the whole-window tally still records the history (nothing hidden)."""
    _fixture(tmp_path, spoofy_cycles=15, live_rows=2, events_age_h=200.0)
    d = build_digest(tmp_path / "outputs")
    assert SD_LIQUIDITY_VETO not in _ids(d)
    assert d["events"]["spoofy_frac"] == 1.0          # history still visible
    assert d["recent"]["events"]["spoofy_frac"] == 0.0  # lens sees it cured


def test_recent_lens_still_fires_on_current_conditions(tmp_path):
    _fixture(tmp_path, spoofy_cycles=15, retrain=60, live_rows=0)
    d = build_digest(tmp_path / "outputs")
    ids = _ids(d)
    assert SD_LIQUIDITY_VETO in ids and SD_MODEL_STARVATION in ids
    for g in d["diagnostics"]:
        if g["id"] in (SD_LIQUIDITY_VETO, SD_MODEL_STARVATION, SD_AUDIT_NOISE):
            assert "last 48h" in g["detail"]          # lens named in the claim


def test_recent_lens_disabled_reverts_to_whole_window(tmp_path):
    # recent_hours<=0 must reproduce the pre-fix behavior exactly
    _fixture(tmp_path, spoofy_cycles=15, live_rows=2, events_age_h=200.0)
    d = build_digest(tmp_path / "outputs", recent_hours=0.0)
    assert d["recent"] == {}
    assert SD_LIQUIDITY_VETO in _ids(d)               # whole-window fallback


def test_trained_champion_is_not_cold(tmp_path):
    """Judge brier n/a only means a thin recent-close window; a present
    champion_brier proves a trained model is deployed (measured 2026-08-18:
    SD-002 called a trained, improving model cold every session)."""
    o = _fixture(tmp_path, retrain=60, live_rows=3)
    state = json.loads((o / "state.json").read_text(encoding="utf-8"))
    state["monitor"]["champion_brier"] = 0.169
    (o / "state.json").write_text(json.dumps(state), encoding="utf-8")
    d = build_digest(tmp_path / "outputs")
    assert d["model"]["cold"] is False
    assert SD_MODEL_STARVATION not in _ids(d)


def test_recent_section_schema_and_md_line(tmp_path):
    _fixture(tmp_path, spoofy_cycles=12, retrain=6, live_rows=1)
    d = build_digest(tmp_path / "outputs")
    rec = d["recent"]
    assert rec["hours"] == 48.0
    assert {"records", "dominant_code", "retrain_requests"} <= set(rec["audit"])
    assert "spoofy_frac" in rec["events"]
    assert "Recent (48h lens)" in render_markdown(d)
