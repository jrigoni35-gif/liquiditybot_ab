"""tests/test_opend_supervisor.py — the supervisor keeps a LOCAL moomoo OpenD
gateway alive alongside the bot.

OpenD is an optional read-only data gateway the bot connects to at
127.0.0.1:11111. The supervisor launches it if it isn't listening and the
operator has configured a path — throttled so a GUI-login OpenD that never
opens its port doesn't get relaunched (and stacked) every tick. A missing path,
a disabled feed, or a remote host are all safe no-ops (moomoo never affects
trading).
"""
import scripts.pc_supervisor as sup


def _patch(monkeypatch, *, enabled=True, path="C:/OpenD/OpenD.exe",
           host="127.0.0.1", port=11111, port_open=False, due=True):
    monkeypatch.setattr(sup, "_opend_cfg",
                        lambda: (enabled, path, host, port))
    monkeypatch.setattr(sup, "_port_open", lambda h, p, timeout=1.0: port_open)
    monkeypatch.setattr(sup, "_opend_relaunch_due", lambda: due)
    launched = []
    monkeypatch.setattr(sup, "_launch_opend", lambda p: launched.append(p))
    monkeypatch.setattr(sup, "_OPEND_STAMP", sup.Path("/tmp/_opend_test_stamp"))
    monkeypatch.setattr(sup.Path, "exists", lambda self: True)
    return launched


def test_launches_when_configured_and_port_closed(monkeypatch):
    launched = _patch(monkeypatch, port_open=False, due=True)
    assert sup._maybe_launch_opend() == "launched"
    assert launched == ["C:/OpenD/OpenD.exe"]


def test_noop_when_already_listening(monkeypatch):
    launched = _patch(monkeypatch, port_open=True)
    assert sup._maybe_launch_opend() == "up"
    assert launched == []


def test_noop_when_no_path_configured(monkeypatch):
    launched = _patch(monkeypatch, path="")
    assert sup._maybe_launch_opend() == "disabled"
    assert launched == []


def test_noop_when_feed_disabled(monkeypatch):
    launched = _patch(monkeypatch, enabled=False)
    assert sup._maybe_launch_opend() == "disabled"
    assert launched == []


def test_remote_opend_is_not_managed(monkeypatch):
    launched = _patch(monkeypatch, host="192.168.1.50", port_open=False)
    assert sup._maybe_launch_opend() == "remote"
    assert launched == []


def test_throttled_between_attempts(monkeypatch):
    launched = _patch(monkeypatch, port_open=False, due=False)
    assert sup._maybe_launch_opend() == "throttled"
    assert launched == []


def test_missing_exe_is_reported_not_launched(monkeypatch):
    launched = _patch(monkeypatch, port_open=False, due=True)
    monkeypatch.setattr(sup.Path, "exists", lambda self: False)
    assert sup._maybe_launch_opend() == "missing"
    assert launched == []


def test_cfg_reads_shipped_config_moomoo_block():
    # the shipped config enables moomoo at 127.0.0.1:11111 with an empty path
    en, path, host, port = sup._opend_cfg()
    assert en is True and host == "127.0.0.1" and port == 11111


def test_env_overrides_config_path(monkeypatch):
    monkeypatch.setenv("LB_OPEND_PATH", "D:/custom/OpenD.exe")
    _, path, _, _ = sup._opend_cfg()
    assert path == "D:/custom/OpenD.exe"
