"""tests/test_dash_autoimport.py — unattended dashboard import
(2026-07-30, operator away from the PC).

Contract under test:
  - grafana_import resolves its token from GRAFANA_SA_TOKEN env first,
    then the persisted ~/.liquiditybot/grafana-sa-token file (the
    gc-token durable pattern); no token -> exit 2 and NO stamp write.
  - pc_supervisor detects dashboard changes by CONTENT fingerprint and
    declares an import due only when (a) a token is available and
    (b) the fingerprint differs from the last SUCCESSFUL import's stamp
    (the stamp is written by the import child on success, never by the
    supervisor - failures stay due and retry).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import grafana_import as gi
import pc_supervisor as sup


def _home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))


# ---------------------------------------------------------------------
# token resolution
# ---------------------------------------------------------------------
def test_resolve_token_env_wins(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    d = tmp_path / ".liquiditybot"
    d.mkdir()
    (d / "grafana-sa-token").write_text("glsa_file", encoding="utf-8")
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "glsa_env")
    assert gi._resolve_token() == "glsa_env"


def test_resolve_token_file_fallback(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    monkeypatch.delenv("GRAFANA_SA_TOKEN", raising=False)
    d = tmp_path / ".liquiditybot"
    d.mkdir()
    (d / "grafana-sa-token").write_text("  glsa_file\n", encoding="utf-8")
    assert gi._resolve_token() == "glsa_file"


def test_resolve_token_absent(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    monkeypatch.delenv("GRAFANA_SA_TOKEN", raising=False)
    assert gi._resolve_token() == ""


def test_main_without_token_exits_2_and_never_stamps(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    monkeypatch.delenv("GRAFANA_SA_TOKEN", raising=False)
    stamp = tmp_path / "stamp"
    monkeypatch.setattr(sys, "argv",
                        ["grafana_import.py", "--stamp", str(stamp),
                         "--fingerprint", "abc"])
    assert gi.main() == 2
    assert not stamp.exists(), "no import happened -> no success stamp"


# ---------------------------------------------------------------------
# supervisor change detection + due logic
# ---------------------------------------------------------------------
def _dash_dir(tmp_path):
    d = tmp_path / "grafana"
    d.mkdir()
    (d / "a.json").write_text('{"uid": "a"}', encoding="utf-8")
    (d / "b.json").write_text('{"uid": "b"}', encoding="utf-8")
    return d


def test_fingerprint_stable_and_content_sensitive(tmp_path):
    d = _dash_dir(tmp_path)
    fp1 = sup._dash_fingerprint(d)
    assert fp1 and fp1 == sup._dash_fingerprint(d)
    (d / "a.json").write_text('{"uid": "a", "v": 2}', encoding="utf-8")
    assert sup._dash_fingerprint(d) != fp1
    empty = tmp_path / "empty"
    empty.mkdir()
    assert sup._dash_fingerprint(empty) == ""


def test_import_due_requires_token(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    monkeypatch.delenv("GRAFANA_SA_TOKEN", raising=False)
    d = _dash_dir(tmp_path)
    stamp = tmp_path / "stamp"
    assert sup._dash_import_due(d, stamp) == ""


def test_import_due_on_change_and_quiet_after_success(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "glsa_x")
    d = _dash_dir(tmp_path)
    stamp = tmp_path / "stamp"
    fp = sup._dash_import_due(d, stamp)
    assert fp == sup._dash_fingerprint(d), "no stamp yet -> first import due"
    # the import child records the fingerprint on success -> quiet
    stamp.write_text(fp, encoding="utf-8")
    assert sup._dash_import_due(d, stamp) == ""
    # a deploy changes a board -> due again with the NEW fingerprint
    (d / "a.json").write_text('{"uid": "a", "v": 3}', encoding="utf-8")
    fp2 = sup._dash_import_due(d, stamp)
    assert fp2 and fp2 != fp


def test_failed_import_stays_due(monkeypatch, tmp_path):
    """The supervisor never writes the stamp itself (only the child does,
    on success) - so a failed import remains due next tick."""
    _home(monkeypatch, tmp_path)
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "glsa_x")
    d = _dash_dir(tmp_path)
    stamp = tmp_path / "stamp"
    assert sup._dash_import_due(d, stamp) != ""
    assert sup._dash_import_due(d, stamp) != "", "still due until stamped"


def test_supervisor_wires_the_autoimport_step():
    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "pc_supervisor.py").read_text(encoding="utf-8")
    assert "LB_NO_DASH_IMPORT" in src, "kill switch must exist"
    assert '"--stamp", str(_DASH_IMPORT_STAMP)' in src
    assert '_spawn_gated(' in src and '"dash_import"' in src

def test_import_due_no_token_warns_once(monkeypatch, tmp_path, capsys):
    """Silent-degrade fix: dashboards changed + no token = a WARN once per
    process (then quiet), never an exception, and never 'due'."""
    _home(monkeypatch, tmp_path)
    monkeypatch.delenv("GRAFANA_SA_TOKEN", raising=False)
    monkeypatch.setattr(sup, "_dash_no_token_warned", False)
    monkeypatch.setattr(sup, "OUT", tmp_path / "out")
    d = _dash_dir(tmp_path)
    stamp = tmp_path / "stamp"
    assert sup._dash_import_due(d, stamp) == ""
    assert sup._dash_import_due(d, stamp) == ""
    assert capsys.readouterr().out.count("no Grafana token") == 1
