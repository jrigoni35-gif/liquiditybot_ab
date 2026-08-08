"""Security regressions from the 2026-08 whole-codebase audit.

C3 — scripts/session_import.py: the manifest is ATTACKER-AUTHORED and
scripts/corpus_sync.py applies bundles UNATTENDED every hour, so `label`
and every `files` key are untrusted strings that used to be spliced
straight into a filesystem path. `"../.."` escaped to the repo root and an
absolute label made pathlib discard the left side of the join outright —
an arbitrary write into the live checkout that bypassed both the human
"proof-read" gate and auto_update's test-gated deploy gate. Pinned here:
every rejection class (separators, absolute paths, drive letters, UNC,
"..", trailing dots, Windows reserved device names, over-length,
non-strings, symlinks), that refusal happens at VERIFY time so plan-only
runs refuse too, that nothing is written outside the record dir, and that
real bundles still import unchanged.

M5 — api/rest_server.py: /control had no CSRF defence. Loopback binding is
not a defence against a browser: every page the operator opens runs on this
host. A cross-site `fetch(..., {mode:'no-cors'})` or a plain HTML form with
enctype="text/plain" is a CORS *simple* request, so no preflight was ever
issued and `flatten_all` / `start` / `entries_on` dispatched on HTTP 200.
Pinned here: cross-site Origin/Referer/Sec-Fetch-Site refused, the
text/plain form vector refused, no do_OPTIONS handler exists (so the
preflight forced by requiring application/json cannot succeed), while the
documented non-browser client path and the X-Auth-Token parity with gRPC
keep working and arm_live stays unexposed.
"""
import contextlib
import http.client
import json
import re
from pathlib import Path

import pytest

from core.audit import AuditTrail
from core.codes import Code
from ml.history import HistoryStore

import api.rest_server as rest
import scripts.session_export as sx
import scripts.session_import as si


# ---------------------------------------------------------------- C3 setup
def _row(pid):
    header = HistoryStore("unused.csv")._header
    vals = []
    for col in header:
        if col == "position_id":
            vals.append(pid)
        elif col == "asset":
            vals.append("ETH")
        elif col == "side":
            vals.append("long")
        elif col == "label":
            vals.append("1")
        elif col == "source":
            vals.append("live")
        else:
            vals.append("0.0")
    return ",".join(vals)


def _seed_outputs(root):
    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    header = HistoryStore(str(out / "signal_history.csv"))._header
    (out / "signal_history.csv").write_text(
        ",".join(header) + "\n" + _row("p1") + "\n" + _row("p2") + "\n",
        encoding="utf-8")
    AuditTrail(str(out / "audit.jsonl")).log("qa", Code.FW_FAULT_DEGRADED,
                                             "seed record")
    (out / "equity.csv").write_text("ts,equity,daily_pnl\n1,800.0,0.0\n",
                                    encoding="utf-8")
    return out


def _bundle(root, label="qa"):
    """A genuine, sha-consistent bundle; the caller then edits the manifest
    the way a hostile telemetry-branch writer would."""
    out = _seed_outputs(root)
    dst = root / "bundle"
    sx.export(str(out), str(dst), label)
    return dst


def _rewrite_manifest(bundle: Path, **edits) -> dict:
    mf = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    mf.update(edits)
    (bundle / "manifest.json").write_text(json.dumps(mf), encoding="utf-8")
    return mf


def _home(root):
    home = root / "home" / "outputs"
    home.mkdir(parents=True)
    return home


# Every rejection class the fix must cover. Kept as one table so a future
# loosening of the charset shows up as N failures, not one.
_BAD_LABELS = [
    "..",                       # bare parent
    ".",                        # bare self
    "../..",                    # posix traversal
    "..\\..",                   # windows traversal
    "sessions/../../evil",      # traversal mid-string
    "/etc/passwd",              # posix absolute
    "C:/Windows/Temp/pwn",      # windows drive-absolute (pathlib DISCARDS
    "C:pwn",                    #   the left side of the join for these)
    "\\\\server\\share\\pwn",   # UNC
    "evil:stream",              # NTFS alternate data stream
    "NUL", "CON", "COM1", "LPT1", "nul",   # reserved device names
    "CON.csv",                  # ... which stay reserved with a suffix
    "trailing.",                # windows strips trailing dots -> aliasing
    "-leading-dash",            # would read as a CLI flag downstream
    "a" * 65,                   # over the 64-char cap
    "has space",
    "unicode\u202e",            # RTL-override display spoof
]


@pytest.mark.parametrize("label", _BAD_LABELS)
def test_verify_bundle_refuses_unsafe_label(tmp_path, label):
    """Refusal is at VERIFY time, so the plan-only run refuses too — that
    is what makes --apply unreachable for a hostile bundle."""
    b = _bundle(tmp_path)
    _rewrite_manifest(b, label=label)
    assert si.verify_bundle(b)["rc"] == 4
    assert si.run(str(b), str(_home(tmp_path)), apply=False) == 4


@pytest.mark.parametrize("key", _BAD_LABELS)
def test_verify_bundle_refuses_unsafe_files_key(tmp_path, key):
    b = _bundle(tmp_path)
    mf = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
    mf["files"][key] = {"sha256": "0" * 64, "bytes": 1}
    (b / "manifest.json").write_text(json.dumps(mf), encoding="utf-8")
    assert si.verify_bundle(b)["rc"] == 4


def test_apply_refuses_traversal_label_and_writes_nothing_outside(tmp_path):
    """The C3 end-to-end shape: a label of '../..' escaping into the live
    checkout, with a payload file listed in the manifest so the copy loop
    lands it. Old behavior: rc=0 and <checkout>/main.py overwritten."""
    b = _bundle(tmp_path)
    payload = b / "main.py"
    payload.write_text("import os; os.system('whoami')\n", encoding="utf-8")
    mf = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
    mf["label"] = "../.."
    mf["files"]["main.py"] = {"sha256": sx._sha256(payload),
                              "bytes": payload.stat().st_size}
    (b / "manifest.json").write_text(json.dumps(mf), encoding="utf-8")

    home = _home(tmp_path)
    checkout = home.parent                  # where '../..' lands
    assert si.run(str(b), str(home), apply=True) == 4
    assert not (checkout / "main.py").exists()
    assert not (home / "main.py").exists()
    assert not (home / "imported_sessions").exists()


def test_apply_refuses_absolute_label(tmp_path):
    """pathlib discards everything left of an absolute component, so an
    absolute label wrote wherever the manifest said — no '..' needed."""
    b = _bundle(tmp_path)
    target = tmp_path / "pwned_absolute"
    _rewrite_manifest(b, label=str(target))
    assert si.run(str(b), str(_home(tmp_path)), apply=True) == 4
    assert not target.exists()


def test_apply_refuses_traversal_files_key(tmp_path):
    """Second, independent vector: the files keys are used for BOTH
    `srcp / name` and `record / dst_name`."""
    b = _bundle(tmp_path)
    escaped = tmp_path / "pwn_payload.txt"
    escaped.write_text("owned", encoding="utf-8")
    mf = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
    mf["files"]["../pwn_payload.txt"] = {"sha256": sx._sha256(escaped),
                                         "bytes": escaped.stat().st_size}
    (b / "manifest.json").write_text(json.dumps(mf), encoding="utf-8")

    home = _home(tmp_path)
    assert si.run(str(b), str(home), apply=True) == 4
    assert not (home / "imported_sessions" / "pwn_payload.txt").exists()


def test_refuses_non_string_label_and_files_block(tmp_path):
    b = _bundle(tmp_path)
    _rewrite_manifest(b, label=["../..", "x"])
    assert si.verify_bundle(b)["rc"] == 4
    _rewrite_manifest(b, label="qa", files=["signal_history.csv"])
    assert si.verify_bundle(b)["rc"] == 4


def test_refuses_symlinked_record_dir(tmp_path, monkeypatch):
    """A pre-existing symlink at outputs/imported_sessions/<label> makes
    mkdir(exist_ok=True) succeed and every copy write through it. Windows
    needs a privilege to create real symlinks, so the predicate is faked —
    the containment branch under test is the same one either way."""
    b = _bundle(tmp_path, label="qa")
    home = _home(tmp_path)
    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink",
                        lambda self: self.name == "qa" or real_is_symlink(self))
    assert si.run(str(b), str(home), apply=True) == 4
    # containment is checked BEFORE the first write, so --apply stays
    # all-or-nothing: a refusal must not leave merged rows behind
    assert not (home / "signal_history.csv").exists()
    assert not (home / "imported_sessions" / "qa").exists()


def test_legit_labels_and_default_stamp_still_import(tmp_path):
    """Behavior preservation: the allow-list must admit every label
    session_export can produce, or the hand-off silently stops working."""
    for i, label in enumerate(["qa", "pc-live", "cloud-mirror",
                               "hourly-latest", "20260713-dayshift",
                               "20260714-v6", "night_shift.2"]):
        root = tmp_path / f"case{i}"
        root.mkdir()
        b = _bundle(root, label=label)
        home = _home(root)
        assert si.run(str(b), str(home), apply=True) == 0
        assert (home / "imported_sessions" / label / "manifest.json").exists()

    # a manifest with no label at all falls back to the UTC stamp, unchanged
    root = tmp_path / "nolabel"
    root.mkdir()
    b = _bundle(root, label="qa")
    _rewrite_manifest(b, label="")
    home = _home(root)
    assert si.run(str(b), str(home), apply=True) == 0
    stamped = list((home / "imported_sessions").iterdir())
    assert len(stamped) == 1 and stamped[0].name[:2] == "20"


def test_safe_component_accepts_only_bare_names():
    assert si.safe_component("signal_history.csv", "files key") == \
        "signal_history.csv"
    assert si.safe_component("20260713-dayshift", "label") == \
        "20260713-dayshift"
    for bad in _BAD_LABELS + [None, 0, "", b"qa"]:
        assert si.safe_component(bad, "label") is None


# ---------------------------------------------------------------- M5 setup
@contextlib.contextmanager
def _server(auth_token=""):
    sent = []
    srv = rest.RestStatusServer(
        {"enabled": True, "port": 0, "auth_token": auth_token},
        status_provider=lambda: {"positions": [], "mode": "DRY_RUN"},
        control_send=lambda cmd, payload: sent.append((cmd, payload)))
    assert srv.start() is True
    try:
        yield srv._httpd.server_address[1], sent
    finally:
        srv.stop()


def _request(port, method, path, body=None, headers=None):
    # timeout 30, not 5 (2026-08-07): under pytest-xdist -n 8 the box's 12
    # logical cores are saturated and a ThreadingHTTPServer handler thread
    # can miss a 5s window - observed as a one-off flake on this file's
    # hdrs3 case while the server's OWN log showed the refusal had already
    # happened. 30s still detects a genuinely hung server; it just stops
    # detecting a busy scheduler. Serial behavior is unchanged (responses
    # arrive in milliseconds).
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


_JSON = {"Content-Type": "application/json"}


def test_control_refuses_no_cors_cross_site_fetch():
    """The reproduced attack: fetch(mode:'no-cors') from a hostile page.
    text/plain is CORS-safelisted, so no preflight is ever issued."""
    with _server() as (port, sent):
        st, _ = _request(port, "POST", "/control",
                         body=json.dumps({"cmd": "flatten_all"}),
                         headers={"Content-Type": "text/plain;charset=UTF-8",
                                  "Origin": "https://evil.example",
                                  "Sec-Fetch-Site": "cross-site",
                                  "Sec-Fetch-Mode": "no-cors"})
        assert st == 403
        assert sent == []


def test_control_refuses_html_form_text_plain_post():
    """No JS required: <form enctype="text/plain"> emits a valid JSON body.
    Content-Type alone must stop it, even with no Origin header at all."""
    with _server() as (port, sent):
        st, _ = _request(port, "POST", "/control",
                         body=json.dumps({"cmd": "entries_on"}),
                         headers={"Content-Type":
                                  "text/plain;charset=UTF-8"})
        assert st == 415
        assert sent == []


@pytest.mark.parametrize("hdrs", [
    {"Origin": "https://evil.example"},
    {"Origin": "null"},                      # sandboxed iframe / data: URL
    {"Referer": "https://evil.example/x.html"},
    {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-site"},         # a sibling subdomain is not us
])
def test_control_refuses_cross_site_markers_even_with_json(hdrs):
    with _server() as (port, sent):
        st, _ = _request(port, "POST", "/control",
                         body=json.dumps({"cmd": "start"}),
                         headers={**_JSON, **hdrs})
        assert st == 403
        assert sent == []


@pytest.mark.parametrize("cmd", ["flatten_all", "start", "entries_on"])
def test_cross_site_cannot_clear_durable_risk_off_sentinels(cmd):
    """`start` and `entries_on` clear outputs/paused.on / entries_off.on —
    the durable sentinels that exist so an operator's risk-off survives a
    restart. The old docstring called every exposed verb risk-neutral."""
    with _server() as (port, sent):
        st, _ = _request(port, "POST", "/control",
                         body=json.dumps({"cmd": cmd}),
                         headers={"Content-Type": "text/plain",
                                  "Origin": "https://evil.example",
                                  "Sec-Fetch-Site": "cross-site"})
        assert st in (403, 415)
        assert sent == []


def test_get_endpoints_refuse_cross_site():
    with _server() as (port, _sent):
        st, _ = _request(port, "GET", "/status",
                         headers={"Sec-Fetch-Site": "cross-site",
                                  "Origin": "https://evil.example"})
        assert st == 403


def test_no_options_handler_so_the_forced_preflight_fails():
    """Requiring application/json only helps because the preflight it
    forces goes unanswered. Adding a do_OPTIONS handler reopens the hole."""
    with _server() as (port, _sent):
        st, _ = _request(port, "OPTIONS", "/control",
                         headers={"Origin": "https://evil.example",
                                  "Access-Control-Request-Method": "POST"})
        assert st == 501


def test_deny_drains_declared_body_before_responding():
    """The RST race behind both xdist flakes in this file (2026-08-07):
    _deny used to respond and close with the POST body still unread, so
    closesocket() with unread bytes raised TCP RST — under -n 8 load the
    RST could beat the queued response and the client saw a reset while
    the server's own log showed the refusal had fired (REST-003 captured
    in the 48a63610 battery). The observable contract of the fix: a
    refused POST's response is written only AFTER the declared body is
    drained, so a slow-sending client can never be reset mid-response.

    Deterministic both ways: pre-fix the 415 arrives while the body is
    still unsent; post-fix the server visibly waits for it."""
    import socket
    with _server() as (port, _sent):
        body = json.dumps({"cmd": "entries_on"}).encode()
        s = socket.create_connection(("127.0.0.1", port), timeout=10)
        try:
            s.sendall(b"POST /control HTTP/1.1\r\n"
                      b"Host: 127.0.0.1\r\n"
                      b"Content-Type: text/plain;charset=UTF-8\r\n"
                      + f"Content-Length: {len(body)}\r\n\r\n".encode())
            s.settimeout(1.0)
            try:
                early = s.recv(1024)
            except socket.timeout:
                early = b""
            assert early == b"", ("server responded before draining the "
                                  "declared body - the RST race is open")
            s.sendall(body)
            s.settimeout(10.0)
            chunks = []
            while True:
                try:
                    c = s.recv(4096)
                except socket.timeout:
                    break
                if not c:
                    break
                chunks.append(c)
            resp = b"".join(chunks)
            assert b" 415 " in resp.split(b"\r\n", 1)[0]
        finally:
            s.close()


def test_oversize_declared_body_is_refused_413_without_draining():
    """The drain must be bounded: an attacker-declared Content-Length may
    not pin the handler thread reading garbage. Past the cap the server
    refuses 413 IMMEDIATELY - before any body bytes exist to read."""
    import socket
    with _server() as (port, sent):
        s = socket.create_connection(("127.0.0.1", port), timeout=10)
        try:
            s.sendall(b"POST /control HTTP/1.1\r\n"
                      b"Host: 127.0.0.1\r\n"
                      b"Content-Type: application/json\r\n"
                      b"Content-Length: 2097152\r\n\r\n")
            s.settimeout(5.0)
            resp = s.recv(4096)
            assert b" 413 " in resp.split(b"\r\n", 1)[0]
            assert sent == []
        finally:
            s.close()


# ---- the paths that must keep working -----------------------------------
def test_non_browser_client_still_dispatches():
    """curl / requests / the checkin scripts send no Origin, no Referer and
    no Sec-Fetch-* — the documented loopback client path is untouched."""
    with _server() as (port, sent):
        st, body = _request(port, "POST", "/control",
                            body=json.dumps({"cmd": "flatten_all",
                                             "payload": {"why": "qa"}}),
                            headers=_JSON)
        assert st == 200
        assert json.loads(body) == {"sent": "flatten_all"}
        assert sent == [("flatten_all", {"why": "qa"})]


def test_same_origin_loopback_page_still_dispatches():
    with _server() as (port, sent):
        st, _ = _request(port, "POST", "/control",
                         body=json.dumps({"cmd": "pause"}),
                         headers={**_JSON,
                                  "Origin": f"http://127.0.0.1:{port}",
                                  "Referer": f"http://localhost:{port}/x",
                                  "Sec-Fetch-Site": "same-origin"})
        assert st == 200
        assert sent == [("pause", {})]
    with _server() as (port, sent):
        st, _ = _request(port, "GET", "/status",
                         headers={"Sec-Fetch-Site": "none"})
        assert st == 200


def test_auth_token_parity_with_grpc_preserved():
    """X-Auth-Token stays the shared secret (gRPC mirrors it as
    x-auth-token metadata); the CSRF checks are additive, not a swap."""
    with _server(auth_token="s3cret") as (port, sent):
        assert _request(port, "POST", "/control",
                        body=json.dumps({"cmd": "pause"}),
                        headers=_JSON)[0] == 401
        assert _request(port, "POST", "/control",
                        body=json.dumps({"cmd": "pause"}),
                        headers={**_JSON, "X-Auth-Token": "wrong"})[0] == 401
        assert sent == []
        assert _request(port, "POST", "/control",
                        body=json.dumps({"cmd": "pause"}),
                        headers={**_JSON,
                                 "X-Auth-Token": "s3cret"})[0] == 200
        assert sent == [("pause", {})]


# ------------------------------------------- README label-horizon drift
_REPO = Path(__file__).resolve().parents[1]


def test_readme_states_the_label_horizon_symbolically():
    """README.md documented `ml.label_max_bars` as 96 (8h) long after the
    2026-07-31 era-deadlock fix shipped 24 — and 96 now FATALs config_guard,
    so the documented value refuses to start. A quoted number goes stale
    every time the knob moves; a symbolic horizon cannot. Pinned rather
    than merely corrected, since correcting it once is what failed before.
    """
    readme = (_REPO / "README.md").read_text(encoding="utf-8")
    shipped = json.loads((_REPO / "config.json").read_text(encoding="utf-8"))
    lmb = int(shipped["ml"]["label_max_bars"])

    # no "(96 = 8h horizon)"-shaped literal anywhere near the knob
    assert re.search(r"label_max_bars[^\n]{0,40}\(\s*\d+\s*[=)]",
                     readme) is None, "README hardcodes a label horizon"
    for line in readme.splitlines():
        if "label_max_bars" not in line:
            continue
        # the CURRENT value is just as stale-prone as the old one
        assert not re.search(rf"(?<!\d){lmb}(?!\d)", line), \
            f"README pins label_max_bars to the shipped {lmb}: {line!r}"
    assert "label_max_bars × 5m" in readme, \
        "README must state the horizon as label_max_bars x 5m bars"


def test_arm_live_stays_unexposed_under_every_valid_credential():
    assert "arm_live" not in rest.ALLOWED_CONTROL
    assert not {"stop", "sim_shock", "sim_clear"} & rest.ALLOWED_CONTROL
    with _server(auth_token="s3cret") as (port, sent):
        st, _ = _request(port, "POST", "/control",
                         body=json.dumps({"cmd": "arm_live"}),
                         headers={**_JSON, "X-Auth-Token": "s3cret",
                                  "Origin": f"http://127.0.0.1:{port}",
                                  "Sec-Fetch-Site": "same-origin"})
        assert st == 403
        assert sent == []
