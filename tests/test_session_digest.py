"""Acceptance tests for core/session_digest.py — the reconciled run summary
and its SD-* detectors. Fixtures are minimal synthetic outputs dirs; the audit
chain is written through the real AuditTrail so chain verification is exercised."""
import json
import time
from pathlib import Path

from core.audit import AuditTrail
from core.session_digest import (ERA_ABSENT, ERA_PRESTAMP, SD_AUDIT_NOISE,
                                 SD_ERA_POOLING_HAZARD, SD_LIQUIDITY_VETO,
                                 SD_MODEL_STARVATION, SD_STREAM_INCONSISTENCY,
                                 _eras_section, build_digest, render_markdown,
                                 write_digest)

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


def test_lens_labels_are_display_honest(tmp_path):
    """The 2026-08-27 misreads, pinned: the spoofy share must NAME its
    non-liquid denominator everywhere it renders (liquid cycles are never
    logged - liquidity_regime.py emits only label != 'liquid'), and the
    realized/fees headline must carry the netting asymmetry (realized is
    post-close-fee, fees are both legs) so the two lines cannot be
    naively ratioed."""
    _fixture(tmp_path, spoofy_cycles=15, retrain=60, live_rows=0)
    d = build_digest(tmp_path / "outputs")
    assert d["events"]["liq_lens"] == "non_liquid_cycles_only"
    md = render_markdown(d)
    assert "of non-liquid cycles" in md
    assert "of classified cycles" not in md
    assert "realized PnL (post-close-fee)" in md
    assert "fees (all legs)" in md
    sd3 = next(g for g in d["diagnostics"] if g["id"] == SD_LIQUIDITY_VETO)
    assert "NON-LIQUID" in sd3["detail"]


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


# ---------------------------------------------------------------------------
# capital-epoch equity lens + chain headline word (2026-08-25)
# ---------------------------------------------------------------------------
def _equity_csv(o: Path, values, start_ts=None):
    now = start_ts or time.time() - len(values) * 15
    rows = ["ts,equity,daily_pnl"] + [
        f"{now + i * 15:.0f},{v:.2f},0.00" for i, v in enumerate(values)]
    (o / "equity.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_equity_headline_reads_the_current_epoch_not_the_lifetime(tmp_path):
    """The false alarm this fixes: a series holding four capital resets
    reported '$25,000 -> $803 (range $99,208)' as if one book lost 97%.
    The equity_* keys must describe the slice after the LAST reset; the
    lifetime extremes stay available but labelled."""
    o = _fixture(tmp_path)
    _equity_csv(o, [25000.0, 24990.0, 100000.0, 99999.0,
                    800.0, 801.0, 803.0, 802.0])
    d = build_digest(tmp_path / "outputs")
    pnl = d["pnl"]
    assert pnl["capital_epochs"] == 3
    assert pnl["equity_start"] == 800.0
    assert pnl["equity_max"] == 803.0
    assert pnl["equity_range"] == 3.0            # NOT 99,200
    assert pnl["lifetime_equity_max"] == 100000.0
    assert pnl["lifetime_equity_range"] == 99200.0
    md = render_markdown(d)
    assert "current capital epoch" in md
    assert "$800.00 -> $802.00" in md
    assert "3 epochs lifetime" in md


def test_single_epoch_series_is_unchanged_and_unannotated(tmp_path):
    """No reset -> the keys mean exactly what they always meant, and the
    headline does not grow an epochs clause for a series with one book."""
    o = _fixture(tmp_path)
    _equity_csv(o, [10000.0, 10010.0, 9990.0, 10005.0])
    d = build_digest(tmp_path / "outputs")
    pnl = d["pnl"]
    assert pnl["capital_epochs"] == 1
    assert pnl["equity_start"] == pnl["lifetime_equity_start"] == 10000.0
    assert pnl["equity_range"] == pnl["lifetime_equity_range"] == 20.0
    assert "epochs lifetime" not in render_markdown(d)


def test_market_moves_do_not_mint_epochs(tmp_path):
    """A 30% drawdown inside one book is a market event, not a reset —
    the threshold is per-SAMPLE (seconds apart), where real resets moved
    83-530% and the worst transient bad read moved 0.8%."""
    o = _fixture(tmp_path)
    _equity_csv(o, [10000.0, 9000.0, 7000.0, 8000.0, 9500.0])
    d = build_digest(tmp_path / "outputs")
    assert d["pnl"]["capital_epochs"] == 1
    assert d["pnl"]["equity_range"] == 3000.0


def test_flat_epoch_after_reset_fires_sd008(tmp_path):
    """SD-008 was structurally dead after any reset: the lifetime range
    stayed inflated by history, so a flatlined book never read as flat.
    On the epoch lens it fires."""
    from core.session_digest import SD_FLAT_EQUITY
    o = _fixture(tmp_path)
    _equity_csv(o, [25000.0, 24990.0] + [800.0] * 12)
    d = build_digest(tmp_path / "outputs")
    assert d["pnl"]["equity_range"] == 0.0
    assert SD_FLAT_EQUITY in _ids(d)


def test_chain_word_names_every_state_and_never_cries_wolf():
    """Display layer only — the JSON keys are untouched (checkin.py reads
    them). The word must alarm ONLY on the alarm class: benign seams read
    'chain_ok=False' in the headline for weeks while the same report
    classified them benign eight lines down."""
    from core.session_digest import _chain_word
    assert _chain_word({"chain_ok": True}) == "OK"
    seam = _chain_word({"chain_ok": False, "chain_tamper": False,
                        "chain_seams": 8})
    assert "SEAMS(8" in seam and "benign" in seam and "False" not in seam
    tam = _chain_word({"chain_ok": False, "chain_tamper": True,
                       "chain_first_break": 41})
    assert tam == "TAMPER(first_break=41)"
    torn = _chain_word({"chain_ok": False, "chain_tamper": False,
                        "chain_seams": 0, "chain_torn_tail": True})
    assert "TORN_TAIL" in torn and "benign" in torn
    # unreadable outranks the tamper bit verify_chain sets alongside it:
    # "the stream is missing" and "a record was edited" are different
    # operator actions and must not share a word
    unread = _chain_word({"chain_ok": False, "chain_tamper": True,
                          "chain_error": "unreadable"})
    assert unread == "UNREADABLE(unreadable)"
    assert _chain_word({"chain_ok": None}) == "UNVERIFIED"


def test_chain_word_reaches_the_rendered_headline(tmp_path):
    _fixture(tmp_path)
    d = build_digest(tmp_path / "outputs")
    assert d["audit"]["chain_ok"] is True
    md = render_markdown(d)
    assert "chain=OK" in md
    assert "chain_ok=" not in md


# --- SD-011 fork divergence (AUDIT-SEAM-0829, 2026-09-01) -----------------
# A forked writer's rows share seq numbers with the canonical chain while
# DISAGREEING on payload; measured live 2026-08-29 a 62-second fork's
# planted OM-080 was consumed as a venue fee reading for two days. The
# firing rule is data-driven: divergent (code, h) under one seq fires;
# an idempotent double-write of the identical record must NOT.

def _mk_audit_rows(tmp_path, rows):
    o = tmp_path / "outputs"
    o.mkdir(exist_ok=True)
    (o / "audit.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return o


def test_sd011_fires_on_divergent_forked_seq(tmp_path):
    rows = [
        {"seq": 1, "code": "FT-020", "h": "aa", "prev": "", "ts": 100.0,
         "src": "fault", "msg": "m"},
        {"seq": 2, "code": "ML-050", "h": "bb", "prev": "aa", "ts": 101.0,
         "src": "ml_governor", "msg": "m"},
        # fork: a second writer reuses seq 2 with a DIFFERENT payload -
        # the exact 08-29 shape (OM-080 riding a forked lineage)
        {"seq": 2, "code": "OM-080", "h": "cc", "prev": "aa", "ts": 101.5,
         "src": "order_manager", "msg": "planted"},
    ]
    d = build_digest(_mk_audit_rows(tmp_path, rows))
    aud = d["audit"]
    assert aud["dup_seqs"] == 1
    assert aud["fork_divergent_seqs"] == 1
    assert "OM-080" in aud["fork_codes"]
    ids = {x["id"] for x in d["diagnostics"]}
    assert "SD-011" in ids, "divergent fork must warn"
    sd11 = next(x for x in d["diagnostics"] if x["id"] == "SD-011")
    assert sd11["severity"] == "warn"
    assert "OM-080" in sd11["detail"], "the riding code must be findable"


def test_sd011_silent_on_idempotent_double_write(tmp_path):
    row = {"seq": 7, "code": "LB-000", "h": "dd", "prev": "cc", "ts": 200.0,
           "src": "long_book", "msg": "m"}
    rows = [
        {"seq": 6, "code": "FT-020", "h": "cc", "prev": "", "ts": 199.0,
         "src": "fault", "msg": "m"},
        row, dict(row),                       # identical record twice
    ]
    d = build_digest(_mk_audit_rows(tmp_path, rows))
    aud = d["audit"]
    assert aud["dup_seqs"] == 1               # counted as a dup...
    assert aud["fork_divergent_seqs"] == 0    # ...but NOT divergent
    ids = {x["id"] for x in d["diagnostics"]}
    assert "SD-011" not in ids, "idempotent double-write must stay benign"


def test_sd011_silent_on_clean_chain(tmp_path):
    rows = [
        {"seq": i, "code": "LB-000", "h": f"h{i}", "prev": f"h{i-1}",
         "ts": 300.0 + i, "src": "long_book", "msg": "m"}
        for i in range(1, 6)
    ]
    d = build_digest(_mk_audit_rows(tmp_path, rows))
    aud = d["audit"]
    assert aud["dup_seqs"] == 0
    assert aud["fork_divergent_seqs"] == 0
    assert "SD-011" not in {x["id"] for x in d["diagnostics"]}


# --- eras section + SD-012 era pooling hazard (2026-08-31) ----------------
# Measured 2026-09-01: outputs/signal_history.csv (95 columns) carries NO
# exec_era column - only label_era, a different axis - while outputs/fills.csv
# carries exec_era as its last column (core/fill_ledger.COLS). The fixtures
# below mirror both shapes: the production one (stamp on fills only) and the
# hypothetical one (stamp on signal_history) so the preferred-source rule is
# pinned in both directions.
FILLS_HEADER = ("ts,order_id,position_id,purpose,symbol,side,ordertype,"
                "post_only,attempt,fill_size,fill_price,arrival_ref,slip_bps,"
                "fees_delta_usd,remaining,reason,exec_era")
DAY = 86400.0
T0 = 1_783_946_147.0                       # 2026-07-13T12:35:47Z


def _fill_row(ts, era):
    return (f"{ts:.3f},oid,pid,entry,ETH/USD,buy,limit,1,1,0.5,3000.0,"
            f"3000.0,0.0,0.33,0,fill,{era}")


def _era_fixture(tmp_path, *, fill_eras=(), sig_eras=None, sig_ts=(T0,),
                 sig_col=True):
    """outputs/ with a signal_history.csv (signal_ts + label_era, optional
    exec_era when `sig_eras` is given) and a fills.csv stamped per
    `fill_eras`. `sig_col=False` writes a signal_history with no signal_ts."""
    o = _fixture(tmp_path)
    cols = ["position_id", "asset", "direction", "source", "label", "label_era"]
    if sig_col:
        cols.append("signal_ts")
    if sig_eras is not None:
        cols.append("exec_era")
    rows = [",".join(cols)]
    for i, ts in enumerate(sig_ts):
        r = [f"p{i}", "ETH", "long", "live", "1", "triple_barrier_h24"]
        if sig_col:
            r.append(f"{ts:.1f}")
        if sig_eras is not None:
            r.append(sig_eras[i % len(sig_eras)])
        rows.append(",".join(r))
    (o / "signal_history.csv").write_text("\n".join(rows) + "\n",
                                          encoding="utf-8")
    if fill_eras:
        frows = [FILLS_HEADER] + [_fill_row(T0 + i, e)
                                  for i, e in enumerate(fill_eras)]
        (o / "fills.csv").write_text("\n".join(frows) + "\n", encoding="utf-8")
    return o


def test_signal_history_without_exec_era_reports_unavailable_not_empty(tmp_path):
    """The production shape. An empty dict would read as 'one era'; the
    section must SAY the column is absent and still name the label axis."""
    o = _era_fixture(tmp_path, fill_eras=("9-16ec821e",))
    e = build_digest(o)["eras"]
    assert "unavailable" in e["rows_per_era"]
    assert "no exec_era column" in e["rows_per_era"]["unavailable"]
    assert e["rows_per_label_era"] == {"triple_barrier_h24": 1}
    assert e["current_era"] == "9-16ec821e"     # core/fill_ledger.EXEC_ERA
    assert e["era_source"] == "core.fill_ledger.EXEC_ERA"


def test_two_fill_eras_in_one_file_fire_sd012(tmp_path):
    o = _era_fixture(tmp_path, fill_eras=("8-ca55e2ba", "9-16ec821e",
                                          "9-16ec821e"))
    d = build_digest(o)
    e = d["eras"]
    assert e["fills_rows"] == 3
    assert e["fills_per_era"] == {"9-16ec821e": 2, "8-ca55e2ba": 1}
    assert e["pooling_hazard"] is True
    assert e["pooling_hazard_source"] == "fills.exec_era"
    sd12 = next(x for x in d["diagnostics"] if x["id"] == SD_ERA_POOLING_HAZARD)
    assert sd12["severity"] == "warn"
    assert "8-ca55e2ba" in sd12["detail"] and "9-16ec821e" in sd12["detail"]
    assert "ABSENT" in sd12["detail"]            # names the signal_history gap
    md = render_markdown(d)
    assert "pooling_hazard=True" in md and "SD-012" in md
    md.encode("ascii")


def test_single_fill_era_is_no_hazard(tmp_path):
    o = _era_fixture(tmp_path, fill_eras=("9-16ec821e",) * 4)
    d = build_digest(o)
    e = d["eras"]
    assert e["fills_per_era"] == {"9-16ec821e": 4}
    assert e["pooling_hazard"] is False
    assert e["pooling_hazard_source"] == "fills.exec_era"
    assert SD_ERA_POOLING_HAZARD not in _ids(d)


def test_prestamp_and_absent_stamps_are_distinct_eras(tmp_path):
    """Blank exec_era (stamp-aware writer, pre-stamp row) and a MISSING
    trailing field (a stale binary's COLS) are different populations -
    cohort_eval's three-way rule - and each counts as an era for pooling."""
    o = _era_fixture(tmp_path, fill_eras=("9-16ec821e",))
    p = o / "fills.csv"
    body = p.read_text(encoding="utf-8")
    short = _fill_row(T0 + 9, "").rsplit(",", 1)[0]      # 16 fields: absent
    p.write_text(body + _fill_row(T0 + 8, "") + "\n" + short + "\n",
                 encoding="utf-8")
    e = build_digest(o)["eras"]
    assert e["fills_per_era"] == {"9-16ec821e": 1, ERA_PRESTAMP: 1,
                                  ERA_ABSENT: 1}
    assert e["pooling_hazard"] is True


def test_signal_history_exec_era_is_preferred_when_present(tmp_path):
    """If the corpus ever grows the stamp, it outranks fills as the source
    (both directions: two eras there -> hazard even with single-era fills;
    one era there -> no hazard even with two-era fills)."""
    o = _era_fixture(tmp_path, sig_eras=("8-ca55e2ba", "9-16ec821e"),
                     sig_ts=(T0, T0 + DAY), fill_eras=("9-16ec821e",))
    e = build_digest(o)["eras"]
    assert e["rows_per_era"] == {"8-ca55e2ba": 1, "9-16ec821e": 1}
    assert e["pooling_hazard"] is True
    assert e["pooling_hazard_source"] == "signal_history.exec_era"
    o2 = _era_fixture(tmp_path / "b", sig_eras=("9-16ec821e",),
                      sig_ts=(T0, T0 + DAY),
                      fill_eras=("8-ca55e2ba", "9-16ec821e"))
    e2 = build_digest(o2)["eras"]
    assert e2["rows_per_era"] == {"9-16ec821e": 2}
    assert e2["pooling_hazard"] is False
    assert e2["pooling_hazard_source"] == "signal_history.exec_era"


def test_corpus_span_is_derived_from_signal_ts(tmp_path):
    """first/last ISO UTC + span days to 2 dp; a blank signal_ts is counted,
    never silently averaged in."""
    o = _era_fixture(tmp_path, sig_ts=(T0 + 3 * DAY, T0, T0 + 50.25 * DAY))
    e = build_digest(o)["eras"]
    assert e["corpus_rows"] == 3
    assert e["corpus_first_ts"] == "2026-07-13T12:35:47Z"
    assert e["corpus_last_ts"] == "2026-09-01T18:35:47Z"
    assert e["corpus_span_days"] == 50.25
    assert e["signal_ts_missing"] == 0
    p = o / "signal_history.csv"
    p.write_text(p.read_text(encoding="utf-8")
                 + "p9,ETH,long,live,1,triple_barrier_h24,\n", encoding="utf-8")
    e = build_digest(o)["eras"]
    assert e["corpus_rows"] == 4 and e["signal_ts_missing"] == 1
    assert e["corpus_span_days"] == 50.25
    md = render_markdown(build_digest(o))
    assert "2026-07-13T12:35:47Z -> 2026-09-01T18:35:47Z (50.25d" in md
    assert "1 rows without signal_ts" in md


def test_eras_section_degrades_without_streams(tmp_path):
    e = _eras_section([], tmp_path / "nowhere")
    assert e["rows_per_era"] == {"unavailable": "signal_history.csv not present"}
    assert e["corpus_first_ts"] is None and e["corpus_span_days"] is None
    assert e["fills_per_era"] == {} and e["pooling_hazard"] is False
    assert e["pooling_hazard_source"] is None
    d = build_digest(tmp_path / "nowhere")
    assert SD_ERA_POOLING_HAZARD not in _ids(d)
    assert d["streams_present"]["fills.csv"] is False


def test_millisecond_epoch_signal_ts_degrades_not_raises(tmp_path):
    """Saboteur: a ms-epoch cell (the data-quality audit's unit-mixing
    class) makes Windows gmtime raise OSError. The digest must survive it
    with None ISO stamps, never take the hourly checkin down."""
    o = _era_fixture(tmp_path, sig_ts=(T0, T0 * 1000.0))
    e = build_digest(o)["eras"]
    assert e["corpus_first_ts"] == "2026-07-13T12:35:47Z"
    assert e["corpus_last_ts"] is None            # unrepresentable, said so
    assert e["corpus_span_days"] is not None       # arithmetic still reported
    render_markdown(build_digest(o)).encode("ascii")


def test_torn_fill_row_is_dropped_and_counted_not_bucketed_absent(tmp_path):
    """A crash mid-append leaves a row short in MANY fields; that is half an
    observation, not a stale-binary row (short in exec_era ONLY)."""
    o = _era_fixture(tmp_path, fill_eras=("9-16ec821e", "9-16ec821e"))
    p = o / "fills.csv"
    p.write_text(p.read_text(encoding="utf-8") + f"{T0 + 5:.3f},oid,pid\n",
                 encoding="utf-8")
    e = build_digest(o)["eras"]
    assert e["fills_rows"] == 2 and e["fills_torn_rows"] == 1
    assert e["fills_per_era"] == {"9-16ec821e": 2}
    assert e["pooling_hazard"] is False
