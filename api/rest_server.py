"""
api/rest_server.py — local REST API, rev 4

Read-mostly HTTP surface over the bot's live status plus a guarded
subset of the control channel, for dashboards, scripts and monitoring
that shouldn't have to tail status.json. Standard library only
(http.server) — zero new dependencies.

Security posture, in order of importance:
  * binds 127.0.0.1 HARD-CODED — the bind address is not configurable,
    and any request whose peer isn't loopback is rejected anyway
    (belt and braces against socket-level surprises);
  * ARM_LIVE IS NOT EXPOSED. The allowed control verbs are exactly
    {pause, start, step, snapshot, entries_on, entries_off,
    disarm_live, flatten_all} — every one of them is risk-neutral or
    risk-REDUCING. Arming live trading remains a dashboard act with
    the exact phrase, as designed. sim_* and stop are not exposed.
  * optional shared-secret: if api_server.auth_token is set, every
    request must carry it in the X-Auth-Token header;
  * GET endpoints serve the same snapshot dict the runner already
    publishes to status.json — no new information surface.

Endpoints:
  GET  /health /status /positions /orders /signals /regimes /algos
  POST /control        {"cmd": "...", "payload": {...}}
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("liquiditybot.api.rest")

ALLOWED_CONTROL = {"pause", "start", "step", "snapshot", "entries_on",
                   "entries_off", "disarm_live", "flatten_all"}
_GET_KEYS = {"/positions": "positions", "/orders": "open_orders",
             "/signals": "signals", "/regimes": "regimes",
             "/algos": "exec_algos"}


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
                body = json.dumps({"error": msg}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

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
                if outer.auth_token and \
                        self.headers.get("X-Auth-Token", "") != \
                        outer.auth_token:
                    self._deny(401, "bad or missing X-Auth-Token")
                    return False
                return True

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
                try:
                    n = int(self.headers.get("Content-Length", 0))
                    req = json.loads(self.rfile.read(n) or b"{}")
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
