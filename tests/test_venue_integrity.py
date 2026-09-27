"""Pins for core/venue_integrity.py + scripts/venue_integrity_report.py
(conduct standard VG-1..VG-11). SAFE class: measurement only.

Every check here is fed a planted bad form (INJECTION) and a clean form, so a
green is not the vacuous "found nothing" - each detector is shown to fire.
The kraken_feed hook tests prove the feed's RETURN VALUE is unchanged by the
VG-4/VG-5 counters, including when the counter itself blows up.
"""
import base64
import json
import re
from pathlib import Path

import pytest

from core import code_stats
from core import venue_integrity as vi
from core.codes import Code

ROOT = Path(__file__).resolve().parents[1]

T0 = 1_790_000_000.0


def _cg(ts, dry, maker=15, taker=30):
    return {"code": "CG-000", "ts": ts,
            "data": {"dry_run": dry, "maker_fee_bps": maker,
                     "taker_fee_bps": taker}}


def _fill(ts, oid="o1", side="buy", purpose="entry", size="1", px="100",
          fee="0.15", post_only="1", slip="0.0", symbol="ETH/USD", book="5m"):
    return {"ts": str(ts), "order_id": oid, "side": side, "purpose": purpose,
            "fill_size": size, "fill_price": px, "fees_delta_usd": fee,
            "post_only": post_only, "slip_bps": slip, "symbol": symbol,
            "book": book, "exec_era": "12-x"}


LIVE = vi.Posture([_cg(T0 - 100, False)])
DRY = vi.Posture([_cg(T0 - 100, True)])


# ------------------------------------------------------------ plumbing

def test_userref_matches_the_order_manager_derivation():
    from execution.order_manager import OrderManager
    ids = ["o1", "e8cee531", "298cf168", "x" * 40, ""]
    assert [vi.userref_for(i) for i in ids] == [
        OrderManager._userref(i) for i in ids]


def test_posture_timeline_live_dry_unknown():
    p = vi.Posture([_cg(10, True), _cg(20, False), _cg(30, "yes"),
                    {"code": "CG-000", "ts": 40}, None])
    assert p.sessions == 2                  # non-bool dry_run ignored
    assert [p.at(5), p.at(10), p.at(15), p.at(25), p.at(99), p.at("")] == [
        "unknown", "dry", "dry", "live", "live", "unknown"]
    assert p.latest_booked_fees() == (15.0, 30.0)


# ------------------------------------------------------------ VG-1

def test_vg1_fee_mismatch_detected_and_clean_when_on_the_row():
    # Tier 5 at $60k: 15/30. 0.15 on $100 = 15 bps maker (clean);
    # 0.25 on $100 = 25 bps maker (planted mismatch).
    good = _fill(T0, fee="0.15")
    bad = _fill(T0 + 1, oid="o2", fee="0.25")
    taker = _fill(T0 + 2, oid="o3", fee="0.30", post_only="0")
    rep = vi.fee_check([good, bad, taker], LIVE, 60_000)
    assert rep["binding_row"] == [15.0, 30.0]
    assert [m["order_id"] for m in rep["mismatches"]] == ["o2"]
    assert rep["mismatches"][0]["charged_bps"] == pytest.approx(25.0)
    assert rep["codes"] == [Code.VI_FEE_MISMATCH.value]
    assert vi.fee_check([good, taker], LIVE, 60_000)["codes"] == [
        Code.VI_CLEAN.value]


def test_vg1_unknown_volume_never_defaults_to_a_row():
    rep = vi.fee_check([_fill(T0, fee="9.99")], LIVE, None)
    assert rep["binding_row"] is None and rep["mismatches"] == []
    assert rep["verdict"] == "UNRESOLVED"
    assert Code.VI_FEE_UNRESOLVED.value in rep["codes"]


def test_vg1_dry_rows_are_labelled_and_verdict_is_absent_not_clean():
    rep = vi.fee_check([_fill(T0, fee="0.15")], DRY, 60_000)
    assert rep["by_posture"] == {"dry": 1}
    assert rep["verdict"] == "NO_LIVE_DATA"
    assert Code.VI_NO_LIVE_DATA.value in rep["codes"]


def test_vg1_trades_history_uses_the_venue_maker_flag():
    th = {"result": {"trades": {
        "T1": {"ordertxid": "O1", "cost": "100", "fee": "0.15", "maker": True},
        "T2": {"ordertxid": "O2", "cost": "100", "fee": "0.15", "maker": False},
    }}}
    rep = vi.trades_fee_check(th, 60_000)
    assert [m["trade"] for m in rep["mismatches"]] == ["T2"]   # taker @15
    assert rep["codes"] == [Code.VI_FEE_MISMATCH.value]


# ------------------------------------------------------------ VG-2

def test_vg2_registration_is_pinned_and_mirrored_in_the_checklist():
    reg = vi.LIVE_FILL_ACCEPTANCE
    assert reg == {"registered": "2026-09-27", "n_lean": 50, "n_verdict": 100,
                   "entry_slip_p90_max": "taker_bps - maker_bps",
                   "alpha_markout_30s_mean_min": "-maker_bps",
                   "entry_post_only_share_min": 0.5}, (
        "the registration is the law: a change here is a re-registration "
        "and must be dated, argued and operator-ratified, never a retune")
    doc = (ROOT / "docs" / "law" / "pre_live_checklist.md").read_text(encoding="utf-8")
    for needle in ("taker_bps - maker_bps", "-maker_bps", "0.5", "n=50",
                   "n=100", "LIVE_FILL_ACCEPTANCE"):
        assert needle in doc, needle


def _entries(n, slip, po="1", t0=T0):
    return [_fill(t0 + i, oid=f"e{i}", slip=str(slip), post_only=po)
            for i in range(n)]


def test_vg2_pass_breach_lean_and_under_n():
    marks = [0.0] * 120
    ok = vi.fill_acceptance(_entries(120, 2.0), LIVE, 15, 30, marks)
    assert ok["verdict"] == "PASS"
    assert {m["status"] for m in ok["metrics"]} == {"PASS"}
    bad = vi.fill_acceptance(_entries(120, 20.0), LIVE, 15, 30, marks)
    slip = next(m for m in bad["metrics"] if m["metric"] == "entry_slip_p90_max")
    assert slip["status"] == "BREACH" and bad["verdict"] == "BREACH"
    assert Code.VI_FILL_ACCEPT_BREACH.value in bad["codes"]
    lean = vi.fill_acceptance(_entries(60, 20.0), LIVE, 15, 30, [0.0] * 60)
    assert next(m for m in lean["metrics"]
                if m["metric"] == "entry_slip_p90_max")["status"] == "BREACH_LEAN"
    few = vi.fill_acceptance(_entries(49, 20.0), LIVE, 15, 30)
    assert few["verdict"] == "UNDER_N"
    assert few["codes"] == [Code.VI_FILL_ACCEPT_UNDER_N.value]
    maker_share = vi.fill_acceptance(_entries(120, 0.0, po="0"), LIVE, 15, 30, marks)
    assert next(m for m in maker_share["metrics"]
                if m["metric"] == "entry_post_only_share_min")["status"] == "BREACH"
    toxic = vi.fill_acceptance(_entries(120, 0.0), LIVE, 15, 30, [-16.0] * 120)
    assert next(m for m in toxic["metrics"]
                if m["metric"] == "alpha_markout_30s_mean_min")["status"] == "BREACH"


def test_vg2_simulator_fills_never_produce_a_live_verdict():
    rows = _entries(120, 2.0)
    rep = vi.fill_acceptance(rows, DRY, 15, 30, [0.0] * 120)
    assert rep["verdict"] == "NO_LIVE_DATA"
    graded = {m["metric"]: m["n"] for m in rep["metrics"]}
    assert graded["entry_slip_p90_max"] == 0            # dry rows not graded
    assert graded["entry_post_only_share_min"] == 0
    ref = vi.fill_acceptance(rows, DRY, 15, 30, [0.0] * 120,
                             include_postures=("live", "dry"))
    assert ref["verdict"] == "SIM_REFERENCE(PASS)"
    assert Code.VI_NO_LIVE_DATA.value in ref["codes"]


# ------------------------------------------------------------ VG-3

def _term(ts, oid, pair="ETHUSD", side="buy", purpose="entry",
          terminal="filled", how="sim cross", created=None, code="OM-000"):
    return {"code": code, "ts": ts,
            "msg": f"{oid} {side} {pair} terminal={terminal} fill_ratio=1.00 ({how})",
            "data": {"order_id": oid, "pair": pair, "side": side,
                     "purpose": purpose, "terminal": terminal,
                     "created_ts": created}}


def test_vg3_gap_measured_only_when_both_postures_exist():
    recs = [_cg(T0, True)]
    recs += [_term(T0 + i, f"s{i}", terminal="filled" if i < 5 else "expired")
             for i in range(10)]
    recs += [_cg(T0 + 100, False)]
    recs += [_term(T0 + 101 + i, f"l{i}", how="venue closed",
                   terminal="filled" if i < 2 else "expired") for i in range(10)]
    p = vi.Posture(recs)
    rep = vi.sim_live_gap(recs, p)
    assert rep["gaps"] == [{"pair": "ETHUSD", "sim_rate": 0.5, "live_rate": 0.2,
                            "n_sim": 10, "n_live": 10,
                            "gap": pytest.approx(-0.3)}]
    assert rep["codes"] == [Code.VI_SIM_LIVE_GAP.value]
    only_sim = recs[:11]
    rep2 = vi.sim_live_gap(only_sim, vi.Posture(only_sim))
    assert rep2["verdict"] == "NO_LIVE_DATA" and rep2["gaps"] == []


def test_vg3_live_shaped_terminal_in_a_dry_session_is_counted():
    # the shape a test's records leave when they leak into the production
    # trail: a live-poller terminal inside a dry session
    recs = [_cg(T0, True), _term(T0 + 1, "o1", how="venue closed"),
            _term(T0 + 2, "o2")]
    assert vi.sim_live_gap(recs, vi.Posture(recs))[
        "marker_posture_disagreements"] == 1


# ------------------------------------------------------------ VG-4

@pytest.mark.parametrize("err,code", [
    ("EAPI:Rate limit exceeded", Code.VI_ERR_RATE_LIMIT),
    ("EOrder:Rate limit exceeded", Code.VI_ERR_RATE_LIMIT),
    ("EGeneral:Temporary lockout", Code.VI_ERR_RATE_LIMIT),
    ("EOrder:Post only order", Code.VI_ERR_POST_ONLY),
    ("EOrder:Insufficient funds", Code.VI_ERR_FUNDS),
    ("EOrder:Margin level too low", Code.VI_ERR_FUNDS),
    ("EAPI:Invalid nonce", Code.VI_ERR_NONCE),
    ("EGeneral:Permission denied", Code.VI_ERR_PERMISSION),
    ("EAPI:Invalid key", Code.VI_ERR_PERMISSION),
    ("EService:Unavailable", Code.VI_ERR_UNAVAILABLE),
    ("EGeneral:Internal error", Code.VI_ERR_UNAVAILABLE),
    ("EOrder:Order minimum not met", Code.VI_ERR_ORDER_REJECT),
    ("EQuery:Unknown asset pair", Code.VI_ERR_OTHER),
])
def test_vg4_classification_table(err, code):
    assert vi.classify_venue_error(err) is code


def test_vg4_note_bumps_code_stats_and_never_raises():
    code_stats.reset()
    vi.reset_venue_error_counts()
    vi.note_venue_errors(["EAPI:Invalid nonce", "EOrder:Insufficient funds"])
    vi.note_venue_errors(object())          # garbage: classified OTHER, no raise
    vi.note_venue_errors(None)
    snap = code_stats.snapshot()
    assert snap["VI-043"] == 1 and snap["VI-042"] == 1 and snap["VI-047"] == 2
    assert vi.venue_error_counts()["VI-043"] == 1


def test_vg4_offline_log_classifier():
    lines = [
        "WARNING Kraken private API error on AddOrder: ['EOrder:Post only order']",
        "WARNING Kraken private API error on AddOrder: ['EAPI:Rate limit exceeded']",
        "WARNING Kraken public API error on Depth: ['EService:Unavailable']",
        "ERROR Kraken private request failed for QueryOrders: timeout",
        "INFO unrelated line",
    ]
    rep = vi.classify_log_lines(lines)
    assert rep["by_code"] == {"VI-041": 1, "VI-040": 1, "VI-045": 1, "VI-048": 1}
    assert rep["by_endpoint"]["AddOrder"] == {"VI-041": 1, "VI-040": 1}


class _Resp:
    def __init__(self, body):
        self.text = json.dumps(body)

    def raise_for_status(self):
        return None


def _feed(body):
    from data.kraken_feed import KrakenFeed
    f = KrakenFeed({"rate_limit_per_sec": 1000, "api_key": "k",
                    "api_secret": base64.b64encode(b"secret").decode()})
    f.session.post = lambda *a, **k: _Resp(body)      # type: ignore[method-assign]
    return f


def test_vg4_feed_return_value_unchanged_even_if_the_counter_explodes(monkeypatch):
    err = {"error": ["EOrder:Insufficient funds"], "result": {}}
    ok = {"error": [], "result": {"txid": ["OABC"]}}
    baseline = (_feed(err)._private_post("AddOrder", {}),
                _feed(ok)._private_post("AddOrder", {}))
    assert baseline == (None, {"txid": ["OABC"]})

    def boom(*_a, **_k):
        raise RuntimeError("counter broke")
    # INJECTION: the classifier itself raises; the guard inside the hook must
    # swallow it and the feed must return exactly what it returned before.
    monkeypatch.setattr(vi, "classify_venue_error", boom)
    monkeypatch.setattr(vi, "is_post_only_cancel", boom)
    assert _feed(err)._private_post("AddOrder", {}) is None
    assert _feed(ok)._private_post("AddOrder", {}) == {"txid": ["OABC"]}
    q = {"error": [], "result": {"O1": {"status": "canceled",
                                        "reason": "Post only order"}}}
    assert _feed(q)._private_post("QueryOrders", {}) == q["result"]


def test_vg4_feed_counts_errors_through_the_real_path():
    code_stats.reset()
    assert _feed({"error": ["EAPI:Invalid nonce"]})._private_post("Balance") is None
    assert code_stats.snapshot().get("VI-043") == 1


# ------------------------------------------------------------ VG-5

def test_vg5_post_only_cancel_counted_once_per_txid_result_untouched():
    code_stats.reset()
    vi.reset_venue_error_counts()
    res = {"O1": {"status": "canceled", "reason": "Post only order"},
           "O2": {"status": "canceled", "reason": "User requested"},
           "O3": {"status": "open"}}
    before = json.dumps(res, sort_keys=True)
    f = _feed({"error": [], "result": res})
    out1 = f._private_post("QueryOrders", {})
    out2 = f._private_post("QueryOrders", {})
    assert out1 == res and out2 == res
    assert json.dumps(res, sort_keys=True) == before
    assert code_stats.snapshot().get("VI-050") == 1      # deduped by txid
    # the counter is scoped to QueryOrders: other endpoints never scan
    _feed({"error": [], "result": {"O9": res["O1"]}})._private_post("OpenOrders")
    assert code_stats.snapshot().get("VI-050") == 1


def test_vg5_offline_closed_orders_split():
    closed = {"result": {"closed": {
        "O1": {"status": "canceled", "reason": "Post only order"},
        "O2": {"status": "canceled", "reason": "User requested"},
        "O3": {"status": "closed", "reason": None}}}}
    rep = vi.post_only_cancels(closed)
    assert rep["post_only_cancels"] == 1
    assert rep["other_cancel_reasons"] == {"User requested": 1}
    assert rep["codes"] == [Code.VI_POST_ONLY_CANCEL.value]


# ------------------------------------------------------------ VG-6

def test_vg6_orphan_stranded_tracked():
    ref = vi.userref_for
    opened = {"result": {"open": {
        "TX1": {"userref": int(ref("live1")), "descr": {"pair": "ETHUSD"}},
        "TX2": {"userref": int(ref("done1")), "descr": {"pair": "ETHUSD"}},
        "TX3": {"userref": 0, "descr": {"pair": "XBTUSD"}},
        "TX4": {"descr": {"pair": "XBTUSD"}}}}}
    rep = vi.orphan_diff(opened, {"live1", "done1"}, {"done1"})
    assert [o["txid"] for o in rep["tracked"]] == ["TX1"]
    assert [o["txid"] for o in rep["stranded"]] == ["TX2"]
    assert rep["stranded"][0]["order_id"] == "done1"
    assert sorted(o["txid"] for o in rep["orphans"]) == ["TX3", "TX4"]
    assert rep["codes"] == [Code.VI_ORPHAN_ORDER.value, Code.VI_STRANDED_ORDER.value]
    clean = vi.orphan_diff({"open": {"TX1": opened["result"]["open"]["TX1"]}},
                           {"live1"}, set())
    assert clean["codes"] == [Code.VI_CLEAN.value]


# ------------------------------------------------------------ VG-7

def _venue(oid, tx, vol="1", px="100", fee="0.15"):
    closed = {tx: {"userref": int(vi.userref_for(oid)), "status": "closed"}}
    trades = {f"T{tx}": {"ordertxid": tx, "vol": vol, "price": px, "fee": fee}}
    return closed, trades


def test_vg7_reconcile_clean_mismatch_and_unmatched():
    c1, t1 = _venue("o1", "TX1")
    rep = vi.reconcile([_fill(T0, "o1")], LIVE, {"closed": c1}, {"trades": t1})
    assert rep["verdict"] == "CLEAN" and rep["codes"] == [Code.VI_CLEAN.value]

    c2, t2 = _venue("o1", "TX1", vol="0.9", fee="0.30")
    rep = vi.reconcile([_fill(T0, "o1")], LIVE, {"closed": c2}, {"trades": t2})
    assert rep["mismatches"][0]["fields"] == ["qty", "fee"]
    assert rep["codes"] == [Code.VI_RECON_MISMATCH.value]

    c3, t3 = _venue("zz", "TX9")
    rep = vi.reconcile([_fill(T0, "o1")], LIVE, {"closed": c3}, {"trades": t3})
    assert sorted(u["side"] for u in rep["unmatched"]) == ["bot_only", "venue_only"]
    assert rep["codes"] == [Code.VI_RECON_UNMATCHED.value]


def test_vg7_simulated_fills_are_excluded_not_reported_as_bot_only():
    rep = vi.reconcile([_fill(T0, "o1")], DRY, {}, {})
    assert rep["skipped_non_live_rows"] == {"dry": 1}
    assert rep["unmatched"] == [] and rep["verdict"] == "NO_LIVE_DATA"


# ------------------------------------------------------------ VG-8

def test_vg8_stp_default_is_cited():
    assert vi.STP_DEFAULT["value"] == "cancel-newest"
    assert vi.STP_DEFAULT["source"].startswith("https://docs.kraken.com/")


def test_vg8_self_cross_scan_fires_on_own_opposite_fills():
    a = _fill(T0, "o1", side="buy", px="100")
    b = _fill(T0 + 0.5, "o2", side="sell", px="100.005")
    far = _fill(T0 + 5, "o3", side="sell", px="100")
    same_order = _fill(T0 + 0.2, "o1", side="sell", px="100")
    rep = vi.self_cross_scan([a, b, far, same_order], LIVE)
    assert [h["orders"] for h in rep["hits_live"]] == [["o1", "o2"]]
    assert rep["codes"] == [Code.VI_SELF_CROSS.value]
    dry = vi.self_cross_scan([a, b], DRY)
    assert dry["hits_live"] == [] and dry["hits_non_live"] == 1
    assert dry["verdict"] == "NO_LIVE_DATA"


def test_vg8_coexistence_uses_fill_time_not_terminal_time():
    # entry e1 fills at T0+10 and its terminal is written at T0+10.2; the
    # exit x1 that closes it is created at T0+10.0 -> NOT an overlap.
    # entry e2 rests T0+20..T0+40 while exit x2 (T0+25..T0+26) is live -> overlap.
    recs = [
        _term(T0 + 10.2, "e1", created=T0 + 1),
        _term(T0 + 12, "x1", side="sell", purpose="exit", created=T0 + 10.0),
        _term(T0 + 40, "e2", terminal="expired", how="sim timeout",
              created=T0 + 20, code="OM-040"),
        _term(T0 + 26, "x2", side="sell", purpose="exit", created=T0 + 25),
    ]
    fills = [_fill(T0 + 10, "e1"),
             _fill(T0 + 26, "x2", side="sell", purpose="exit", post_only="0")]
    rep = vi.coexistence_scan(recs, fills)
    assert [(o["exit"], o["entry"]) for o in rep["examples"]] == [("x2", "e2")]
    assert rep["unguarded_marketable_exit"] == 1
    assert rep["codes"] == [Code.VI_SELF_CROSS.value]


# ------------------------------------------------------------ VG-9

def test_vg9_status_flags():
    ap = {"result": {
        "XETHZUSD": {"altname": "ETHUSD", "wsname": "ETH/USD", "status": "online"},
        "XXBTZUSD": {"altname": "XBTUSD", "wsname": "XBT/USD", "status": "cancel_only"},
    }}
    rep = vi.venue_status(ap, {"result": {"status": "online"}},
                          ["ETH/USD", "BTC/USD", "LINK/USD"])
    assert {r["pair"]: r["status"] for r in rep["pairs"]} == {
        "ETH/USD": "online", "BTC/USD": "cancel_only", "LINK/USD": "MISSING"}
    assert rep["flagged"] == ["BTC/USD", "LINK/USD"]
    assert rep["codes"] == [Code.VI_VENUE_STATUS.value]
    ok = vi.venue_status(ap, {"status": "online"}, ["ETH/USD"])
    assert ok["codes"] == [Code.VI_CLEAN.value]
    maint = vi.venue_status(ap, {"status": "maintenance"}, ["ETH/USD"])
    assert maint["flagged"] == ["SystemStatus"]


# ------------------------------------------------------------ VG-10

def test_vg10_custody():
    assert vi.custody(1500, 1000)["codes"] == [Code.VI_CUSTODY_OVER_TARGET.value]
    assert vi.custody(1500, 1000)["excess_usd"] == 500
    assert vi.custody(500, 1000)["verdict"] == "WITHIN_TARGET"
    assert vi.custody(None, 1000)["verdict"] == "UNKNOWN"
    assert vi.trade_balance_usd({"result": {"eb": "1234.5"}}) == 1234.5


# ------------------------------------------------------------ VG-11 + docs

def test_vg11_checklist_item_and_deny_list_intact():
    doc = (ROOT / "docs" / "law" / "pre_live_checklist.md").read_text(encoding="utf-8")
    assert "VG-11" in doc and "withdraw" in doc.lower()
    from data.kraken_feed import _endpoint_is_forbidden
    for ep in ("Withdraw", "WithdrawInfo", "WalletTransfer", "WithdrawAddresses"):
        assert _endpoint_is_forbidden(ep), ep
    for ep in ("OpenOrders", "TradeBalance", "QueryOrders", "ClosedOrders",
               "TradesHistory"):
        assert not _endpoint_is_forbidden(ep), ep


def test_conduct_standard_names_a_shipped_tool_for_every_vg_item():
    t = (ROOT / "docs" / "law" / "conduct_standard.md").read_text(encoding="utf-8")
    sec = t.split("## 3. VENUE INTEGRITY", 1)[1]
    for n in range(1, 12):
        m = re.search(rf"\*\*VG-{n} \(SAFE[^)]*\)\.\*\*(.*?)(?=\*\*VG-\d+ |\| *$)",
                      sec, re.S | re.M)
        assert m, f"VG-{n} row not found"
        assert "Shipped" in m.group(1), f"VG-{n} does not name what shipped"
    assert "venue_integrity_report.py" in sec and "test_venue_integrity.py" in sec


# ------------------------------------------------------------ CLI

def test_cli_runs_every_offline_subcommand_and_writes_nothing(tmp_path, capsys):
    import scripts.venue_integrity_report as cli
    fills = tmp_path / "fills.csv"
    fills.write_text("ts,order_id,purpose,symbol,side,post_only,fill_size,"
                     "fill_price,slip_bps,fees_delta_usd,book\n"
                     f"{T0},o1,entry,ETH/USD,buy,1,1,100,0.1,0.15,5m\n",
                     encoding="utf-8")
    audit = tmp_path / "audit.jsonl"
    audit.write_text(json.dumps(_cg(T0 - 5, True)) + "\n", encoding="utf-8")
    js = tmp_path / "x.json"
    js.write_text(json.dumps({"result": {}}), encoding="utf-8")
    log = tmp_path / "bot.log"
    log.write_text("Kraken private API error on AddOrder: ['EAPI:Invalid nonce']\n",
                   encoding="utf-8")
    before = sorted(p.name for p in tmp_path.iterdir())
    fa = ["--fills", str(fills), "--audit", str(audit)]
    runs = [["fees", *fa, "--volume-30d", "60000"], ["fill-accept", *fa],
            ["fill-gap", "--audit", str(audit)], ["errors", "--log", str(log)],
            ["post-only", "--closed", str(js)],
            ["orphans", *fa, "--open", str(js)],
            ["reconcile", *fa, "--closed", str(js), "--trades", str(js)],
            ["self-cross", *fa],
            ["venue-status", "--asset-pairs", str(js), "--system-status",
             str(js), "--pairs", "ETH/USD"],
            ["custody", "--target-usd", "100", "--equity-usd", "50"]]
    for argv in runs:
        assert cli.main([*argv, "--json"]) == 0, argv
        rep = json.loads(capsys.readouterr().out)
        assert rep["codes"] and all(re.fullmatch(r"VI-\d{3}", c) for c in rep["codes"])
    assert sorted(p.name for p in tmp_path.iterdir()) == before
