"""tests/test_learning_panel.py — the concurrent multi-route orchestrator.

Pins two things: the registry (every route names a script that actually
exists under scripts/, so a typo'd entry fails loudly at test time rather
than as a silent per-run ERROR), and the isolation contract (one route's
crash/timeout/nonzero-exit must never take down the panel or another
route, and the panel's own write path must never touch the operator's
real outputs/ tree — tests/conftest.py's audit hook fails any test that
does).
"""
import json
import subprocess

import scripts.learning_panel as lp


def test_registry_names_are_unique():
    names = [r.name for r in lp.ROUTES]
    assert len(names) == len(set(names))


def test_registry_scripts_exist():
    for route in lp.ROUTES:
        assert (lp.SCRIPTS_DIR / route.script).exists(), route.script


def test_registry_timeouts_are_positive():
    for route in lp.ROUTES:
        assert route.timeout_sec > 0


def _rebind_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(lp, "PANEL_MD", tmp_path / "learning_panel.md")
    monkeypatch.setattr(lp, "PANEL_JSON", tmp_path / "learning_panel.json")


def test_isolation_four_outcomes(monkeypatch, tmp_path):
    """Route A: rc 0 (OK). Route B: rc 1 (FAILED). Route C: raises
    TimeoutExpired (TIMEOUT). Route D: raises OSError (ERROR). The panel
    must finish and write both files regardless."""
    _rebind_outputs(monkeypatch, tmp_path)
    names = [r.name for r in lp.ROUTES]
    a, b, c, d = names[0], names[1], names[2], names[3]

    def fake_run(argv, **kwargs):
        target = argv[1]
        if a in target:
            return subprocess.CompletedProcess(
                argv, 0, stdout="head line one\ntail line\n", stderr="")
        if b in target:
            return subprocess.CompletedProcess(
                argv, 1, stdout="some output\n", stderr="boom\n")
        if c in target:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=1)
        if d in target:
            raise OSError("spawn failed")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    result = lp.run_panel(only=[a, b, c, d])

    by_name = {r["name"]: r for r in result["routes"]}
    assert by_name[a]["status"] == "OK"
    assert by_name[b]["status"] == "FAILED"
    assert by_name[c]["status"] == "TIMEOUT"
    assert by_name[d]["status"] == "ERROR"
    assert result["counts"] == {"ok": 1, "failed": 1, "timeout": 1, "error": 1}

    lp.write_panel(result)
    assert lp.PANEL_MD.exists()
    assert lp.PANEL_JSON.exists()


def test_only_unknown_route_exits_2(monkeypatch, tmp_path, capsys):
    _rebind_outputs(monkeypatch, tmp_path)
    assert lp.main(["--only", "not_a_real_route"]) == 2


def test_list_prints_route_names(capsys):
    rc = lp.main(["--list"])
    assert rc == 0
    out = capsys.readouterr().out
    for route in lp.ROUTES:
        assert route.name in out


def test_json_output_parses_and_md_has_every_route_and_caveat(
        monkeypatch, tmp_path, capsys):
    _rebind_outputs(monkeypatch, tmp_path)
    names = [r.name for r in lp.ROUTES[:2]]

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, 0, stdout="line one\nline two\n", stderr="")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    rc = lp.main(["--only", ",".join(names), "--json"])
    assert rc == 0

    printed = capsys.readouterr().out
    parsed = json.loads(printed)
    assert {r["name"] for r in parsed["routes"]} == set(names)

    md = lp.PANEL_MD.read_text(encoding="utf-8")
    for name in names:
        assert name in md
    assert ("A green is only as big as its corpus — each route's own "
            "output states what it actually measured; a route that "
            "degraded honestly answers a different question.") in md

    on_disk = json.loads(lp.PANEL_JSON.read_text(encoding="utf-8"))
    assert {r["name"] for r in on_disk["routes"]} == set(names)


def test_no_production_outputs_writes_without_rebinding_only_json_mode(
        monkeypatch, tmp_path):
    """--json prints to stdout on top of (not instead of) the file writes;
    confirm both files still land at the rebound tmp path, never outputs/."""
    _rebind_outputs(monkeypatch, tmp_path)
    name = lp.ROUTES[0].name

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    lp.main(["--only", name])
    assert lp.PANEL_MD.parent == tmp_path
    assert lp.PANEL_JSON.parent == tmp_path
