"""environment JSON validity: .mcp.json and config.json must parse.

On 2026-09-19 an unescaped inner quote in .mcp.json's GitHits _doc made
the file unparseable for ~2 days. No test caught it because no test
loads these files; the first symptom was an agent failing to dispatch.
config_guard validates config.json only at bot start, and nothing at
all validates .mcp.json — this test is that missing gate. Docs-only
companion: docs/quant/2026-09-19_boundary_runbook.md (drift check).
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ENV_JSON_FILES = (".mcp.json", "config.json")


def _parse(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_env_json_files_exist():
    for name in ENV_JSON_FILES:
        assert (REPO_ROOT / name).is_file(), f"{name} missing at repo root"


def test_mcp_json_parses_and_has_servers():
    data = _parse(REPO_ROOT / ".mcp.json")
    servers = data.get("mcpServers")
    assert isinstance(servers, dict) and servers, "mcpServers must be a non-empty object"
    for name, entry in servers.items():
        assert isinstance(entry, dict), f"server {name!r} entry must be an object"


def test_config_json_parses():
    data = _parse(REPO_ROOT / "config.json")
    assert isinstance(data, dict) and data


def test_no_unescaped_inner_quotes_in_doc_strings():
    # regression shape of the 09-19 defect: _doc strings containing raw
    # double quotes. Parse per line: each _doc value line must have an
    # even quote structure; a cleaner check is simply that json.loads
    # succeeds (covered above), so here we assert the specific line that
    # broke is quote-balanced when re-emitted.
    raw = (REPO_ROOT / ".mcp.json").read_text(encoding="utf-8")
    for i, line in enumerate(raw.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith('"_doc"'):
            # count quotes not preceded by a backslash; must be exactly 4
            # (key open/close + value open/close); anything else is the defect
            n = sum(
                1
                for j, ch in enumerate(line)
                if ch == '"' and (j == 0 or line[j - 1] != "\\")
            )
            assert n == 4, f".mcp.json line {i}: {n} unescaped quotes (inner quotes must be escaped)"
