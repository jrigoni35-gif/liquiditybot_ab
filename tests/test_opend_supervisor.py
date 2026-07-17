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


# ---------------- supervisor self-restart on source change ----------------

def _fake_self(monkeypatch, tmp_path, content="x"):
    f = tmp_path / "pc_supervisor.py"
    f.write_text(content, encoding="utf-8")
    monkeypatch.setattr(sup, "_SELF", f)
    monkeypatch.setattr(sup, "_SELF_MTIME", f.stat().st_mtime)
    return f


def test_unchanged_source_does_not_restart(monkeypatch, tmp_path):
    _fake_self(monkeypatch, tmp_path)
    assert sup._source_changed() is False


def test_changed_source_triggers_restart(monkeypatch, tmp_path):
    import os
    f = _fake_self(monkeypatch, tmp_path)
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 5))
    assert sup._source_changed() is True


def test_empty_or_missing_source_never_hands_over(monkeypatch, tmp_path):
    # a half-written file (mid-checkout) must not spawn a broken successor
    import os
    f = _fake_self(monkeypatch, tmp_path, content="x")
    f.write_text("", encoding="utf-8")
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 5))
    assert sup._source_changed() is False
    f.unlink()
    assert sup._source_changed() is False
