"""Grafana push must carry a per-instance identity. Without
service.instance.id every bot writes the SAME {job="liquiditybot"} series,
so a second bot (a local clone sharing the OTLP token) collides into one
series -> out-of-order-sample rejection + values flapping between the two
bots' states (the reported dashboard symptom). A unique instance id makes
them distinct series."""
import importlib


def _cfg(monkeypatch, tmp_path, **env):
    tok = tmp_path / "t.txt"
    tok.write_text("secret", encoding="utf-8")
    monkeypatch.setenv("GC_OTLP_URL", "https://x/otlp")
    monkeypatch.setenv("GC_INSTANCE_ID", "1722437")
    monkeypatch.setenv("GC_TOKEN_FILE", str(tok))
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    gp = importlib.import_module("scripts.gc_pusher")
    return gp, gp._cfg()


def test_instance_label_from_env(monkeypatch, tmp_path):
    gp, cfg = _cfg(monkeypatch, tmp_path, LB_INSTANCE="cloud")
    assert cfg["instance_label"] == "cloud"


def test_instance_label_falls_back_to_hostname(monkeypatch, tmp_path):
    monkeypatch.delenv("LB_INSTANCE", raising=False)
    gp, cfg = _cfg(monkeypatch, tmp_path)
    assert cfg["instance_label"] and cfg["instance_label"] != ""


def test_push_body_carries_service_instance_id(monkeypatch, tmp_path):
    gp, cfg = _cfg(monkeypatch, tmp_path, LB_INSTANCE="cloud")
    sent = {}

    class _Resp:
        status = 200

        def __enter__(self): return self

        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=30):
        sent["body"] = req.data.decode()
        return _Resp()

    monkeypatch.setattr(gp.urllib.request, "urlopen", fake_urlopen)
    gp.push(cfg, [gp.gauge("liquiditybot_equity", 800.0)])
    assert '"service.instance.id"' in sent["body"]
    assert '"cloud"' in sent["body"]
