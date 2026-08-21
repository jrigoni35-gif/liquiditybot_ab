"""
api/rest_server.py — local REST API, rev 4

Read-mostly HTTP surface over the bot's live status plus a guarded
subset of the control channel, for dashboards, scripts and monitoring
that shouldn't have to tail status.json. Standard library only
(http.server) — zero new dependencies.

Security posture, in order of importance:
  * binds 127.0.0.1 HARD-CODED — the bind address is not configurable,
    and any request whose peer isn't loopback is rejected anyway
    (belt and braces against socket-level surprises). NOTE: loopback is
    NOT a defence against a browser — every page the operator opens
    runs on this host and can reach 127.0.0.1. Cross-site request
    forgery is defended separately, below;
  * ARM_LIVE IS NOT EXPOSED. The allowed control verbs are exactly
    {pause, start, step, snapshot, entries_on, entries_off,
    disarm_live, flatten_all}. Most are risk-neutral or risk-REDUCING,
    but `flatten_all` market-exits the live book and `start` /
    `entries_on` CLEAR the durable risk-off sentinels
    (outputs/paused.on, outputs/entries_off.on) — so the verb list is a
    blast-radius cap, not an authorisation. Arming live trading remains
    a console act with the exact phrase, as designed. sim_* and stop
    are not exposed;
  * CSRF: /control requires Content-Type: application/json (which is
    not a CORS-safelisted value, so a cross-site sender must first pass
    a preflight this server deliberately does not answer — there is no
    do_OPTIONS, and adding one would reopen the hole), and any request
    carrying a cross-site Origin / Referer / Sec-Fetch-Site is refused.
    Together these reject the no-JS attack too: an HTML form with
    enctype="text/plain" can emit a valid JSON body but cannot set a
    non-safelisted Content-Type;
  * optional shared-secret: if api_server.rest.auth_token is set, every
    request must carry it in the X-Auth-Token header (parity with
    gRPC's x-auth-token metadata). It ships EMPTY, so the CSRF checks
    above — not the token — are what close the browser vector by
    default;
  * GET endpoints serve the same snapshot dict the runner already
    publishes to status.json — no new information surface.

Endpoints:
  GET  /health /status /positions /orders /signals /regimes /algos
  POST /control        {"cmd": "...", "payload": {...}}
                       Content-Type: application/json (required)
"""

import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

log = logging.getLogger("liquiditybot.api.rest")

ALLOWED_CONTROL = {"pause", "start", "step", "snapshot", "entries_on",
                   "entries_off", "disarm_live", "flatten_all"}
_GET_KEYS = {"/positions": "positions", "/orders": "open_orders",
             "/signals": "signals", "/regimes": "regimes",
             "/algos": "exec_algos"}
# Hostnames a same-origin caller on this box can legitimately present. The
# bind is 127.0.0.1, but a browser page served from http://localhost:<port>
# sends Origin: http://localhost:<port>, so both spellings must pass.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
# Sec-Fetch-Site values that are NOT operator-initiated: modern browsers stamp
# every request with this, and "none" (address bar / script with no initiator)
# plus "same-origin" are the only ones a legitimate caller produces. Absent =
# a non-browser client (curl, requests, the checkin scripts) — allowed, because
# a non-browser client already has whatever host access it needs.
_SAFE_FETCH_SITE = {"same-origin", "none"}


def _token_ok(candidate, expected) -> bool:
    """Constant-time shared-secret compare (2026-08-19 sweep tail): plain
    `==`/`!=` short-circuits per byte, a timing side-channel for anything
    that can reach the loopback bind. encode() both sides — compare_digest
    raises TypeError on non-ASCII str, and a header value is not
    guaranteed ASCII. Shared with the gRPC surface."""
    return hmac.compare_digest(
        str(candidate).encode("utf-8", "surrogateescape"),
        str(expected).encode("utf-8", "surrogateescape"))

# Body-handling bounds (2026-08-07, xdist-flake root cause). DRAIN cap:
# _deny reads at most this much unconsumed request body before closing,
# so a refused legit client is never TCP-reset mid-response, while a
# hostile Content-Length cannot pin the thread. BODY cap: do_POST refuses
# 413 before reading anything larger - control bodies are tens of bytes.
_DENY_DRAIN_CAP = 64 * 1024
_MAX_BODY = 1024 * 1024


def _origin_is_loopback(value: str) -> bool:
    """True when an Origin/Referer header names this host. 'null' (sandboxed
    iframe, data: URL, some file:// contexts) is NOT loopback — it is exactly
    what a hostile embedder produces, so it must fail closed."""
    try:
        parts = urlsplit(value.strip())
    except ValueError:                              # malformed -> fail closed
        return False
    return bool(parts.hostname) and parts.hostname.lower() in _LOOPBACK_HOSTS


class RestStatusServer:
    def __init__(self, config: dict, status_provider, control_send):
        """status_provider: () -> dict (runner's latest status snapshot)
        control_send: (cmd:str, payload:dict) -> None (ControlChannel)"""
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.port = int(cfg.get("port", 8899))
        self.auth_token = str(cfg.get("auth_token", "") or "")
        self._provider = status_provider
        self._control = control_send
        self._httpd = None
        self._thread = None

    # ------------------------------------------------------------------
    def start(self):
        if not self.enabled or self._httpd is not None:
            return False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):          # route to our log
                log.debug("rest %s", fmt % args)

            # ---- helpers -------------------------------------------
            def _deny(self, code: int, msg: str):
                # Drain the unread declared body (bounded) BEFORE writing
                # the refusal: closing a socket with unread bytes raises
                # TCP RST, and an RST can destroy the queued response on
                # the client side - a legit refused caller then sees a
                # reset instead of this 4xx (observed as the 2026-08-07
                # xdist flakes: REST-003 logged server-side, client reset;
                # ConnectionAbortedError reproduced in the red test). The
                # cap keeps an attacker-declared Content-Length from
                # pinning the handler thread; a real control body is tens
                # of bytes, and past the cap we accept the RST risk on
                # what is by definition a hostile request.
                if not getattr(self, "_body_consumed", False):
                    try:
                        n = int(self.headers.get("Content-Length", 0) or 0)
                        if 0 < n <= _DENY_DRAIN_CAP:
                            self.rfile.read(n)
                            self._body_consumed = True
                    except (ValueError, OSError):
                        pass
                body = json.dumps({"error": msg}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                # a refused POST's remaining body (over-cap case) is still
                # unread; on a keep-alive HTTP/1.1 connection the next
                # parse would read it as a request line. Close instead.
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

            def _ok(self, obj):
                body = json.dumps(obj, default=str).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _gate(self) -> bool:
                if self.client_address[0] not in ("127.0.0.1", "::1"):
                    self._deny(403, "loopback only")
                    return False
                if not self._same_site():
                    return False
                if outer.auth_token and not _token_ok(
                        self.headers.get("X-Auth-Token", ""),
                        outer.auth_token):
                    self._deny(401, "bad or missing X-Auth-Token")
                    return False
                return True

            def _same_site(self) -> bool:
                """Refuse anything a foreign web page initiated. Applied to
                GET as well as POST: an opaque cross-site GET cannot read the
                body, but there is no reason to serve the live book to one."""
                site = (self.headers.get("Sec-Fetch-Site", "") or "").lower()
                if site and site not in _SAFE_FETCH_SITE:
                    return self._csrf_deny("Sec-Fetch-Site", site)
                for h in ("Origin", "Referer"):
                    v = self.headers.get(h, "") or ""
                    if v and not _origin_is_loopback(v):
                        return self._csrf_deny(h, v)
                return True

            def _csrf_deny(self, header: str, value: str) -> bool:
                log.warning("REST-002: cross-site %s refused on %s (%s: %r)",
                            self.command, self.path, header, value[:120])
                self._deny(403, f"cross-site request refused ({header})")
                return False

            # ---- verbs ---------------------------------------------
            def do_GET(self):
                if not self._gate():
                    return
                if self.path == "/health":
                    return self._ok({"ok": True})
                try:
                    snap = outer._provider() or {}
                except Exception:
                    log.exception("rest status provider fault")
                    return self._deny(500, "status unavailable")
                if self.path == "/status":
                    return self._ok(snap)
                key = _GET_KEYS.get(self.path)
                if key is not None:
                    return self._ok({key: snap.get(key)})
                return self._deny(404, "unknown endpoint")

            def do_POST(self):
                if not self._gate():
                    return
                if self.path != "/control":
                    return self._deny(404, "unknown endpoint")
                # application/json is NOT a CORS-safelisted Content-Type, so
                # requiring it forces any cross-origin sender through a
                # preflight this server never answers (no do_OPTIONS -> 501).
                # It is also unforgeable by an HTML form: enctype only offers
                # urlencoded / multipart / text/plain, and the text/plain
                # trick that emits a valid JSON body dies here. Parameters
                # (";charset=utf-8") are allowed; the media type is not.
                ctype = (self.headers.get("Content-Type", "") or "")
                if ctype.split(";", 1)[0].strip().lower() != \
                        "application/json":
                    log.warning("REST-003: /control refused, Content-Type "
                                "%r is not application/json", ctype[:80])
                    return self._deny(415, "Content-Type must be "
                                           "application/json")
                try:
                    n = int(self.headers.get("Content-Length", 0))
                    if n > _MAX_BODY:
                        # refuse BEFORE reading: an attacker-declared
                        # length may not buy an unbounded read into memory
                        # (control bodies are tens of bytes). Over-cap
                        # skips _deny's drain too - fast close, RST is
                        # acceptable on a hostile request.
                        log.warning("REST-004: /control refused, declared "
                                    "Content-Length %d exceeds %d", n,
                                    _MAX_BODY)
                        return self._deny(413, "body too large")
                    raw = self.rfile.read(n)
                    self._body_consumed = True
                    req = json.loads(raw or b"{}")
                except (ValueError, TypeError):
                    return self._deny(400, "malformed JSON body")
                if not isinstance(req, dict):
                    # valid JSON but not an object (e.g. [1,2] / 5) -> req.get
                    # would AttributeError; reject cleanly instead of a 500
                    return self._deny(400, "body must be a JSON object")
                cmd = str(req.get("cmd", ""))
                if cmd not in ALLOWED_CONTROL:
                    # arm_live / sim_* / stop are deliberately absent
                    return self._deny(403, f"command {cmd!r} not exposed "
                                           f"over REST")
                payload = req.get("payload") or {}
                if not isinstance(payload, dict):
                    return self._deny(400, "payload must be an object")
                try:
                    outer._control(cmd, payload)
                except Exception:
                    log.exception("rest control dispatch fault")
                    return self._deny(500, "dispatch failed")
                return self._ok({"sent": cmd})

        try:
            self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port),
                                              Handler)
        except OSError as e:
            log.error("REST-001: cannot bind 127.0.0.1:%d (%s) — API "
                      "disabled", self.port, e)
            self._httpd = None
            return False
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        name="rest-api", daemon=True)
        self._thread.start()
        log.info("REST API serving on 127.0.0.1:%d (auth=%s)", self.port,
                 "token" if self.auth_token else "loopback-only")
        return True

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
