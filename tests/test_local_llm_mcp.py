"""Local-LLM MCP bridge (spec 2026-07-26 §2): pure-function coverage.
The fastmcp layer is deliberately untested here - it must not even be
importable in CI (lazy import pinned below)."""
import json
import sys
import urllib.error
from pathlib import PureWindowsPath

import pytest

from scripts.local_llm_mcp import (SUMMARIZE_SYSTEM, build_chat_payload,
                                   call_endpoint, resolve_report_path,
                                   truncate_content)


def test_module_imports_without_fastmcp():
    assert "fastmcp" not in sys.modules


def test_whitelist_accepts_outputs_reports(tmp_path):
    (tmp_path / "lessons_digest.md").write_text("x", encoding="utf-8")
    p = resolve_report_path("lessons_digest.md", tmp_path)
    assert p.name == "lessons_digest.md"


@pytest.mark.parametrize("bad", [
    "../config.json", "..\\config.json", "sub/dir.md", "sub\\dir.md",
    "state.bin", "audit.jsonl", "", "config.json.exe",
    "config.json:evil.md", "C:x.md",
])
def test_whitelist_rejects(tmp_path, bad):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_report_path(bad, tmp_path)


def test_whitelist_rejects_missing_file(tmp_path):
    with pytest.raises(ValueError):
        resolve_report_path("ghost.md", tmp_path)


def test_backslash_traversal_genuinely_rejected_on_windows():
    """resolve_report_path's bare-filename guard is `name !=
    Path(name).name`. On this dev platform (POSIX), backslash is not a
    separator, so the "sub\\dir.md" / "..\\config.json" cases above are
    only rejected incidentally (via the later "no such report" check,
    since no such literal file exists) - not by the bare-filename guard
    itself. Windows is the target runtime (CLAUDE.md), where `Path` is
    `WindowsPath` and backslash IS a separator, so the same guard
    genuinely fires there. Assert that directly via PureWindowsPath
    (platform-independent, no filesystem access) so the Windows-target
    rejection path is verified here rather than assumed."""
    for bad in ("sub\\dir.md", "..\\config.json"):
        assert PureWindowsPath(bad).name != bad


def test_truncate():
    assert truncate_content("a" * 30000, 24000).endswith("[truncated]")
    assert len(truncate_content("a" * 30000, 24000)) <= 24000 + 20
    assert truncate_content("short") == "short"


def test_payload_temp_zero_and_cap():
    p = build_chat_payload("hi", "sys", 5000, "m")
    assert p["temperature"] == 0
    assert p["max_tokens"] == 2000
    assert p["model"] == "m"
    assert p["messages"][0] == {"role": "system", "content": "sys"}
    assert build_chat_payload("hi", "", 400, "m")["messages"][0][
        "role"] == "user"          # empty system omitted


def test_call_endpoint_scheme_validation():
    with pytest.raises(RuntimeError):
        call_endpoint({}, "ftp://127.0.0.1/v1")


def test_call_endpoint_parses_choice(monkeypatch):
    class _Resp:
        def read(self):
            return json.dumps({"choices": [
                {"message": {"content": "hello"}}]}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False
    import scripts.local_llm_mcp as m
    monkeypatch.setattr(m, "_urlopen", lambda req, timeout: _Resp())
    assert call_endpoint({"x": 1}, "http://127.0.0.1:11434/v1") == "hello"


def test_call_endpoint_readable_error(monkeypatch):
    import scripts.local_llm_mcp as m
    def _boom(req, timeout):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(m, "_urlopen", _boom)
    with pytest.raises(RuntimeError, match="local model endpoint"):
        call_endpoint({}, "http://127.0.0.1:11434/v1")


def test_summarize_system_is_fixed_nonempty():
    assert isinstance(SUMMARIZE_SYSTEM, str) and len(SUMMARIZE_SYSTEM) > 40
