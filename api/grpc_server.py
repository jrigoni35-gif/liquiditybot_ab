"""
api/grpc_server.py — optional gRPC surface, rev 4

Mirrors api/rest_server.py exactly: same status snapshot, same allowed
control verbs, same loopback bind, same arm_live exclusion, same optional
shared-secret (api_server.grpc.auth_token; when set, every RPC must carry
x-auth-token metadata — parity with REST's X-Auth-Token header). gRPC is
an OPTIONAL dependency (grpcio + generated stubs from api/liquiditybot
.proto); absence degrades with one warning and the bot runs on —
the moomoo optional-SDK pattern.
"""

import json
import logging

from api.rest_server import ALLOWED_CONTROL, _token_ok

log = logging.getLogger("liquiditybot.api.grpc")


class GrpcStatusServer:
    def __init__(self, config: dict, status_provider, control_send):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.port = int(cfg.get("port", 8900))
        # shared-secret parity with REST (api_server.rest.auth_token): when
        # set, every RPC must carry x-auth-token metadata. Empty = loopback
        # bind is the only guard (the historical default, unchanged).
        self.auth_token = str(cfg.get("auth_token", "") or "")
        self._provider = status_provider
        self._control = control_send
        self._server = None

    @staticmethod
    def _import_stack():
        """Seam, moomoo-style: patchable in tests, lazily imported in
        production, absence handled at the single call site."""
        import grpc                                    # noqa: F401
        # Use package-relative imports so the generated stubs are resolved
        # when this module is imported as part of the `api` package.
        from . import liquiditybot_pb2 as pb2        # type: ignore[attr-defined]  # noqa: F401, generated at build time
        from . import liquiditybot_pb2_grpc as pb2g  # type: ignore[attr-defined]  # noqa: F401, generated at build time
        return grpc, pb2, pb2g

    def start(self) -> bool:
        if not self.enabled or self._server is not None:
            return False
        try:
            grpc, pb2, pb2g = self._import_stack()
        except ImportError:
            log.warning("GRPC-001: gRPC surface enabled but grpcio/"
                        "generated stubs missing — run the protoc line in "
                        "api/liquiditybot.proto; continuing without gRPC")
            return False
        outer = self

        class Service(pb2g.BotServiceServicer):
            @staticmethod
            def _authed(context) -> bool:
                """Mirror REST's shared-secret check. No token configured ->
                open (loopback bind is the guard, as before). Token set ->
                the x-auth-token metadata entry must match on EVERY RPC."""
                if not outer.auth_token:
                    return True
                md = dict(context.invocation_metadata() or ())
                # constant-time, shared with REST (2026-08-19 sweep tail)
                return _token_ok(md.get("x-auth-token", ""),
                                 outer.auth_token)

            def GetStatus(self, request, context):
                if not self._authed(context):
                    context.abort(grpc.StatusCode.UNAUTHENTICATED,
                                  "bad or missing x-auth-token")
                try:
                    snap = outer._provider() or {}
                except Exception:
                    log.exception("grpc status provider fault")
                    snap = {"error": "status unavailable"}
                return pb2.StatusJson(json=json.dumps(snap, default=str))

            def SendControl(self, request, context):
                if not self._authed(context):
                    context.abort(grpc.StatusCode.UNAUTHENTICATED,
                                  "bad or missing x-auth-token")
                cmd = request.cmd
                if cmd not in ALLOWED_CONTROL:
                    return pb2.ControlReply(
                        accepted=False,
                        message=f"command {cmd!r} not exposed over gRPC")
                try:
                    payload = json.loads(request.payload_json or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError
                except ValueError:
                    return pb2.ControlReply(accepted=False,
                                            message="malformed payload_json")
                try:
                    outer._control(cmd, payload)
                except Exception:
                    log.exception("grpc control dispatch fault")
                    return pb2.ControlReply(accepted=False,
                                            message="dispatch failed")
                return pb2.ControlReply(accepted=True, message=f"sent {cmd}")

        from concurrent import futures
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        pb2g.add_BotServiceServicer_to_server(Service(), self._server)
        self._server.add_insecure_port(f"127.0.0.1:{self.port}")
        self._server.start()
        log.info("gRPC API serving on 127.0.0.1:%d", self.port)
        return True

    def stop(self):
        if self._server is not None:
            self._server.stop(grace=1.0)
            self._server = None
