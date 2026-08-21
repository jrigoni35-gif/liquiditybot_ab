"""#51 batch: data-layer cluster (DL-2/3/6/7/8/10/11 from the 2026-07-17
audit). Feed-integrity theme: bad or stale market data must surface as
UNAVAILABLE / fail-closed, never masquerade as a healthy reading.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from regime.liquidity_regime import LiquidityRegimeEngine, _spread_bps  # noqa: E402


# --- DL-2: crossed merged book ----------------------------------------------
def test_crossed_book_reads_unmeasurable_not_tight():
    crossed = {"bids": [[100.5, 5.0]], "asks": [[100.0, 5.0]]}
    assert _spread_bps(crossed) == 999.0, \
        "crossed = garbage = fail-closed wide, never spread 0.0"
    locked = {"bids": [[100.0, 5.0]], "asks": [[100.0, 5.0]]}
    assert _spread_bps(locked) == 999.0
    healthy = {"bids": [[99.9, 5.0]], "asks": [[100.1, 5.0]]}
    assert 0 < _spread_bps(healthy) < 999.0


def test_liquidity_state_flags_crossed_combined_book():
    lr = LiquidityRegimeEngine({})
    st = lr.update("ETH",
                   combined_book={"bids": [[100.5, 5.0]],
                                  "asks": [[100.0, 5.0]]},
                   kraken_book={"bids": [[99.9, 5.0]],
                                "asks": [[100.1, 5.0]]},
                   now=1000.0)
    assert st.combined_crossed is True
    assert st.combined_spread_bps == 999.0
    assert st.spread_bps < 999.0            # exec book healthy, unaffected


# --- DL-8 / DL-11: OKX fail-closed ------------------------------------------
def _okx(get_response):
    from data.okx_feed import OKXFeed
    feed = OKXFeed.__new__(OKXFeed)          # no network in __init__ path
    feed._ctval_cache = {}
    feed._get = get_response
    return feed


def test_ctval_lookup_failure_skips_the_book():
    feed = _okx(lambda path, params=None: None)      # instruments call fails
    assert feed._ctval("BTC-USDT-SWAP") is None
    # and get_order_book refuses to emit an unscalable book
    calls = {"n": 0}

    def fake_get(path, params=None):
        calls["n"] += 1
        if "books" in path:
            return [{"bids": [["100", "5"]], "asks": [["101", "5"]]}]
        return None                                   # ctVal still failing
    feed._get = fake_get
    assert feed.get_order_book("BTC-USDT-SWAP") is None


def test_ctval_failure_is_not_cached():
    feed = _okx(lambda path, params=None: None)
    assert feed._ctval("BTC-USDT-SWAP") is None
    assert "BTC-USDT-SWAP" not in feed._ctval_cache, \
        "a failed lookup must retry next cycle, not pin None forever"


def test_malformed_funding_is_unavailable_not_zero():
    feed = _okx(lambda path, params=None: [{"fundingRate": "garbage"}])
    assert feed.get_funding_rate("BTC-USDT-SWAP") is None, \
        "unparsable funding = UNAVAILABLE, never a fake 0.0 print"
    feed._get = lambda path, params=None: [{"fundingRate": "0.0001"}]
    assert feed.get_funding_rate("BTC-USDT-SWAP") == 0.0001
    feed._get = lambda path, params=None: [{"fundingRate": "0"}]
    assert feed.get_funding_rate("BTC-USDT-SWAP") == 0.0   # real zero kept


# --- DL-3: kraken malformed single-pair payload ------------------------------
def test_kraken_book_malformed_payload_returns_none():
    from data.kraken_feed import KrakenFeed
    feed = KrakenFeed.__new__(KrakenFeed)
    feed._public_get = lambda ep, params=None: {"XETHZUSD": "not-a-dict"}
    assert feed.get_order_book("XETHZUSD") is None


# --- DL-6: stale status pushes the alarm-only batch --------------------------
def test_stale_status_pushes_alarm_only(tmp_path):
    import json as _json
    import time as _time

    import gc_pusher
    p = tmp_path / "status.json"
    p.write_text(_json.dumps({
        "written_at": _time.time() - 600, "runner_state": "RUNNING",
        "equity": 5000.0, "cycle": 42, "positions": [{}, {}]}),
        encoding="utf-8")
    metrics = gc_pusher.collect(str(p))
    joined = "\n".join(str(m) for m in metrics)
    assert "liquiditybot_status_stale" in joined
    assert "liquiditybot_equity" not in joined, \
        "stale gauges must never masquerade as current state"
    # running is forced 0 even though the frozen file says RUNNING
    running = [m for m in metrics if "liquiditybot_running" in str(m)]
    assert running and "1" not in str(running[0]).split("running")[1][:20]


# --- W2-14 re-decision (2026-07-23): missing status is LOUD, not silent ----
def test_missing_status_pushes_alarm_batch(tmp_path):
    # a missing status.json used to raise out of collect() and abort the
    # push entirely — total silence, indistinguishable in Grafana from a
    # dead pusher or a network cut. Runner-not-writing is the single most
    # alarming state the metrics plane can report: alarm batch, always.
    import gc_pusher
    metrics = gc_pusher.collect(str(tmp_path / "absent.json"))
    joined = "\n".join(str(m) for m in metrics)
    assert "liquiditybot_status_missing" in joined
    assert "liquiditybot_status_stale" in joined
    assert "liquiditybot_equity" not in joined
    running = [m for m in metrics if "liquiditybot_running" in str(m)]
    assert running and "1" not in str(running[0]).split("running")[1][:20]


def test_unreadable_status_pushes_alarm_batch(tmp_path):
    import gc_pusher
    p = tmp_path / "status.json"
    p.write_text("{not json", encoding="utf-8")
    joined = "\n".join(str(m) for m in gc_pusher.collect(str(p)))
    assert "liquiditybot_status_missing" in joined
    assert "liquiditybot_equity" not in joined


def test_present_status_reports_missing_zero(tmp_path):
    # steady state and DL-6 stale state both carry status_missing=0 so the
    # alert rule can distinguish "runner frozen" from "file gone"
    import json as _json
    import time as _time

    import gc_pusher
    for written_at in (_time.time(), _time.time() - 600):
        p = tmp_path / "status.json"
        p.write_text(_json.dumps({"written_at": written_at,
                                  "equity": 5000.0}), encoding="utf-8")
        assert "liquiditybot_status_missing" in \
            "\n".join(str(m) for m in gc_pusher.collect(str(p)))


def test_fresh_status_pushes_the_full_batch(tmp_path):
    import json as _json
    import time as _time

    import gc_pusher
    p = tmp_path / "status.json"
    p.write_text(_json.dumps({
        "written_at": _time.time(), "runner_state": "RUNNING",
        "equity": 5000.0, "cycle": 42, "positions": []}),
        encoding="utf-8")
    joined = "\n".join(str(m) for m in gc_pusher.collect(str(p)))
    assert "liquiditybot_equity" in joined
    assert "liquiditybot_status_stale" in joined     # 0 in steady state


# --- DL-10: stale kraken book treated as absent for classification ----------
def test_stale_book_gate_source_contract():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "self.book_ts.get(asset, 0.0)) > \\\n" in src
    assert "self.watchdog.stale_critical_sec" in src
    i = src.index("self.watchdog.stale_critical_sec")
    assert "kbook = {}" in src[i:i + 120]


# --- DL-7: bounded response body ---------------------------------------------
def test_oversize_body_is_discarded():
    from data._http import _MAX_BODY_BYTES, ThrottledRestClient
    client = ThrottledRestClient.__new__(ThrottledRestClient)
    client.transport_retries = 0
    client._throttle = lambda: None
    client._note_rtt = lambda t0: None
    big = SimpleNamespace(
        headers={"content-length": str(_MAX_BODY_BYTES + 1)},
        raise_for_status=lambda: None,
        json=lambda: (_ for _ in ()).throw(AssertionError("must not decode")))
    client.session = SimpleNamespace(get=lambda url, params, timeout: big)
    import logging
    out = client._request("http://x", None, logging.getLogger("t"),
                          "TEST", 5.0, decode_json=True)
    assert out is None


def test_nan_token_body_is_rejected_whole():
    """Sweep-tail fix (2026-08-19): whether resp.json() accepts NaN was
    decided by ACCIDENT — this box's requests finds simplejson (via
    moomoo_api, allow_nan=False) while stdlib json parses NaN happily.
    The shared decode boundary now parses via loads_bounded, which
    rejects NaN/Infinity tokens BY DESIGN, uniformly with the
    Kraken/webdata paths."""
    import logging

    from data._http import ThrottledRestClient
    client = ThrottledRestClient.__new__(ThrottledRestClient)
    client.transport_retries = 0
    client._throttle = lambda: None
    client._note_rtt = lambda t0: None

    def _resp(body):
        return SimpleNamespace(
            headers={"content-length": str(len(body))},
            content=body.encode(), text=body,
            raise_for_status=lambda: None)

    poisoned = '{"code": "0", "data": [{"px": NaN, "sz": Infinity}]}'
    client.session = SimpleNamespace(
        get=lambda url, params, timeout: _resp(poisoned))
    out = client._request("http://x", None, logging.getLogger("t"),
                          "TEST", 5.0, decode_json=True)
    assert out is None, "non-finite JSON tokens must reject whole-payload"

    good = '{"code": "0", "data": []}'
    client.session = SimpleNamespace(
        get=lambda url, params, timeout: _resp(good))
    out = client._request("http://x", None, logging.getLogger("t"),
                          "TEST", 5.0, decode_json=True)
    assert out == {"code": "0", "data": []}       # finite JSON unchanged
