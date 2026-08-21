"""REST surface test matrix - the non-security axes (api/rest_server.py).

tests/test_audit_security.py owns the CSRF/cross-site matrix (Origin/
Referer/Sec-Fetch-Site refusals, the text/plain form trick, the deliberate
absence of do_OPTIONS, drain-before-deny, 413). This file fills the axes an
API test matrix expects AROUND that: response shapes on every GET endpoint,
the 404s, every body-validation branch of /control, the auth-token matrix
with a token actually set, both 500 fault paths, and the Content-Length edge
cases (including a hand-rolled negative declared length - verified
empirically 2026-08-10 to 400 cleanly, pinned here so a refactor cannot
regress it into the read()-to-EOF hang it looks like it should be).

Deliberately absent, because the surface honestly lacks them: pagination,
file uploads, rate limiting (loopback-only operator API; the blast-radius
cap is the ALLOWED_CONTROL verb list, tested here and in audit_security).
"""
from __future__ import annotations

import contextlib
import http.client
import json

import pytest

from api import rest_server as rest

_JSON = {"Content-Type": "application/json"}

_SNAP = {"positions": [{"symbol": "ADA/USD"}], "open_orders": ["o1"],
         "signals": {"ADA": {"confirmed": False}}, "regimes": {"ADA": "bull"},
         "exec_algos": {"active": 0}, "mode": "DRY_RUN"}


@contextlib.contextmanager
def _server(auth_token="", provider=None, control=None):
    sent = []
    srv = rest.RestStatusServer(
        {"enabled": True, "port": 0, "auth_token": auth_token},
        status_provider=provider or (lambda: dict(_SNAP)),
        control_send=control or (lambda cmd, payload: sent.append((cmd,
                                                                   payload))))
    assert srv.start() is True
    try:
        yield srv._httpd.server_address[1], sent
    finally:
        srv.stop()


def _req(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        r = conn.getresponse()
        return r.status, json.loads(r.read() or b"null")
    finally:
        conn.close()


# ------------------------------------------------------------ GET shapes
def test_health_shape():
    with _server() as (port, _):
        assert _req(port, "GET", "/health") == (200, {"ok": True})


def test_status_returns_the_whole_snapshot():
    with _server() as (port, _):
        code, body = _req(port, "GET", "/status")
        assert code == 200 and body == _SNAP


@pytest.mark.parametrize("path,key", [
    ("/positions", "positions"), ("/orders", "open_orders"),
    ("/signals", "signals"), ("/regimes", "regimes"),
    ("/algos", "exec_algos")])
def test_each_get_endpoint_serves_exactly_its_key(path, key):
    """Response shape: {key: snapshot[key]} - the endpoint must not leak the
    rest of the snapshot and must not rename the key."""
    with _server() as (port, _):
        code, body = _req(port, "GET", path)
        assert code == 200
        assert body == {key: _SNAP[key]}


def test_get_unknown_endpoint_404():
    with _server() as (port, _):
        code, body = _req(port, "GET", "/nope")
        assert code == 404 and "error" in body


def test_post_non_control_path_404():
    with _server() as (port, _):
        code, _b = _req(port, "POST", "/status", body=b"{}", headers=_JSON)
        assert code == 404


# ------------------------------------------------- /control body validation
def _ctl(port, body_bytes, headers=None):
    return _req(port, "POST", "/control", body=body_bytes,
                headers=headers or _JSON)


def test_malformed_json_400():
    with _server() as (port, sent):
        code, body = _ctl(port, b"{not json")
        assert code == 400 and "malformed" in body["error"]
        assert sent == []


@pytest.mark.parametrize("payload", [b"[1,2]", b"5", b'"pause"', b"null"])
def test_json_non_object_400(payload):
    """Valid JSON that is not an object would AttributeError on .get - the
    handler must 400, never 500."""
    with _server() as (port, sent):
        code, body = _ctl(port, payload)
        assert code == 400 and "object" in body["error"]
        assert sent == []


def test_empty_object_is_an_unexposed_command_403():
    with _server() as (port, sent):
        code, _b = _ctl(port, b"{}")
        assert code == 403 and sent == []


@pytest.mark.parametrize("cmd", ["stop", "sim_open", "sim_close",
                                 "arm_live", "force_dry", "flatten"])
def test_unexposed_commands_403_and_never_dispatch(cmd):
    """The verb list is a blast-radius cap: anything off it must 403 and
    must NOT reach the control channel."""
    with _server() as (port, sent):
        code, _b = _ctl(port, json.dumps({"cmd": cmd}).encode())
        assert code == 403
        assert sent == []


def test_non_object_payload_400():
    with _server() as (port, sent):
        code, body = _ctl(port, json.dumps(
            {"cmd": "pause", "payload": [1]}).encode())
        assert code == 400 and "payload" in body["error"]
        assert sent == []


def test_allowed_command_dispatches_with_payload():
    with _server() as (port, sent):
        code, body = _ctl(port, json.dumps(
            {"cmd": "pause", "payload": {"why": "test"}}).encode())
        assert code == 200 and body == {"sent": "pause"}
        assert sent == [("pause", {"why": "test"})]


def test_every_allowed_verb_round_trips():
    """The whole exposed verb list dispatches - and nothing else does (the
    complement is pinned above and in audit_security's arm_live matrix)."""
    with _server() as (port, sent):
        for cmd in sorted(rest.ALLOWED_CONTROL):
            code, _b = _ctl(port, json.dumps({"cmd": cmd}).encode())
            assert code == 200, cmd
        assert [c for c, _p in sent] == sorted(rest.ALLOWED_CONTROL)


# ------------------------------------------------------------- auth matrix
def test_auth_missing_token_401_get_and_post():
    with _server(auth_token="s3cret") as (port, sent):
        assert _req(port, "GET", "/health")[0] == 401
        assert _ctl(port, b'{"cmd":"pause"}')[0] == 401
        assert sent == []


def test_auth_wrong_token_401():
    with _server(auth_token="s3cret") as (port, sent):
        code, _b = _req(port, "GET", "/health",
                        headers={"X-Auth-Token": "wrong"})
        assert code == 401 and sent == []


def test_auth_correct_token_passes_both_verbs():
    hdr = {"X-Auth-Token": "s3cret"}
    with _server(auth_token="s3cret") as (port, sent):
        assert _req(port, "GET", "/health", headers=hdr) == (200, {"ok": True})
        code, _b = _req(port, "POST", "/control",
                        body=b'{"cmd":"pause"}',
                        headers={**_JSON, **hdr})
        assert code == 200 and sent == [("pause", {})]


def test_token_is_never_echoed_in_a_response():
    """Sensitive-field rule: the secret must not appear in any body."""
    hdr = {"X-Auth-Token": "s3cret"}
    with _server(auth_token="s3cret") as (port, _):
        for path in ("/health", "/status", "/nope"):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            try:
                conn.request("GET", path, headers=hdr)
                raw = conn.getresponse().read()
            finally:
                conn.close()
            assert b"s3cret" not in raw, path


# ------------------------------------------------------------- fault paths
def test_provider_fault_is_500_not_a_hang():
    def boom():
        raise RuntimeError("provider down")
    with _server(provider=boom) as (port, _):
        code, body = _req(port, "GET", "/status")
        assert code == 500 and "unavailable" in body["error"]
        # /health never touches the provider - liveness stays green
        assert _req(port, "GET", "/health")[0] == 200


def test_dispatch_fault_is_500_after_validation():
    def boom(cmd, payload):
        raise RuntimeError("channel wedged")
    with _server(control=boom) as (port, _):
        code, body = _ctl(port, b'{"cmd":"pause"}')
        assert code == 500 and "dispatch" in body["error"]


# ------------------------------------------------- content-length edges
def test_non_numeric_content_length_400():
    with _server() as (port, sent):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        try:
            conn.putrequest("POST", "/control")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", "banana")
            conn.endheaders()
            r = conn.getresponse()
            assert r.status == 400
        finally:
            conn.close()
        assert sent == []


def test_negative_content_length_400_without_hanging():
    """Looks like it should hang (read(-n) reads to EOF on a buffered
    stream); verified empirically it does not - the connection's buffered
    reader returns immediately and json.loads fails to 400. Pinned so a
    refactor of the body read cannot regress this into a thread-pinning
    primitive."""
    with _server() as (port, sent):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        try:
            conn.putrequest("POST", "/control")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", "-5")
            conn.endheaders()
            r = conn.getresponse()
            assert r.status == 400
        finally:
            conn.close()
        assert sent == []


def test_declared_length_shorter_than_body_truncates_never_leaks():
    """Content-Length 2 with a longer JSON body: the handler must read
    exactly 2 bytes ('{\"'), fail JSON parse, and 400 - remainder handled
    by the close, not parsed as a second request."""
    with _server() as (port, sent):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        try:
            conn.putrequest("POST", "/control")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", "2")
            conn.endheaders()
            conn.send(b'{"cmd":"pause"}')
            r = conn.getresponse()
            assert r.status == 400
        finally:
            conn.close()
        assert sent == []


def test_token_compare_is_constant_time():
    """Sweep-tail fix (2026-08-19): both control surfaces compare the
    shared secret via hmac.compare_digest (through _token_ok), not
    short-circuiting == — a timing side-channel for anything reaching the
    loopback bind. Functional auth behavior (correct/wrong/missing token)
    is pinned by the matrix tests above; this pins the helper's contract
    and that both surfaces route through it."""
    import inspect

    import api.grpc_server as grpc_mod
    import api.rest_server as rest_mod
    from api.rest_server import _token_ok
    assert _token_ok("secret-1", "secret-1")
    assert not _token_ok("secret-1", "secret-2")
    assert not _token_ok("", "secret-1")
    assert _token_ok("åß∂", "åß∂"), \
        "non-ASCII must compare cleanly, not raise (the encode() guard)"
    assert "hmac.compare_digest" in inspect.getsource(rest_mod)
    assert "_token_ok(" in inspect.getsource(grpc_mod)
