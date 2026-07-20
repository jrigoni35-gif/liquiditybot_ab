"""gRPC shared-secret parity with REST (audit fix, 0da246c).

grpcio + generated stubs are OPTIONAL dependencies, so the servicer closure
cannot be driven end-to-end here; what IS testable without them: the config
surface (auth_token read exactly like REST's), and the source contract that
BOTH RPCs gate on the metadata check and abort UNAUTHENTICATED — mirroring
how the repo pins other optional-dependency surfaces.
"""
from pathlib import Path

from api.grpc_server import GrpcStatusServer

ROOT = Path(__file__).resolve().parents[1]


def test_auth_token_read_from_config():
    s = GrpcStatusServer({"enabled": False, "auth_token": "s3cret"},
                         lambda: {}, lambda cmd, payload: None)
    assert s.auth_token == "s3cret"
    s2 = GrpcStatusServer({}, lambda: {}, lambda c, p: None)
    assert s2.auth_token == ""                 # unset -> loopback-only mode


def test_both_rpcs_gate_on_the_shared_secret():
    src = (ROOT / "api" / "grpc_server.py").read_text(encoding="utf-8")
    # one _authed helper, called by BOTH RPCs before any work
    assert src.count("def _authed") == 1
    assert src.count("self._authed(context)") == 2       # GetStatus + SendControl
    assert "x-auth-token" in src
    assert "UNAUTHENTICATED" in src
    # empty token preserves the historical loopback-only behavior
    assert "if not outer.auth_token" in src
    # the gate runs before the status snapshot / control dispatch
    assert src.index("_authed(context)") < src.index("outer._provider()")


def test_config_json_documents_the_knob():
    import json
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    grpc_cfg = cfg["api_server"]["grpc"]
    assert "auth_token" in grpc_cfg and grpc_cfg["auth_token"] == ""
