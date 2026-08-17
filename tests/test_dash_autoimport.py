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

Hardened 2026-08-17 (import-loop review), each with a planted defect
below:
  - the fingerprint is MANIFEST-scoped (grafana_import.DASHBOARDS), so a
    stray json in docs/grafana cannot hold an import permanently due;
  - a network-level failure (URLError: DNS, refused, timeout) is one FAIL
    line and a nonzero exit, never a traceback crash-loop;
  - retire failures WARN and do not block the stamp — a 403 on DELETE
    must not re-import four unchanged boards every 180s forever;
  - the supervisor backs off exponentially (BOOT_GRACE_SEC doubling to a
    1h cap) on observed import failures, resetting on success or content
    change.
"""
import io
import sys
import urllib.error
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
# The fingerprint is scoped to the import MANIFEST, so the fixture writes
# two real manifest names — a stray json is a separate test below.
_MANIFEST_A = gi.DASHBOARDS[0]
_MANIFEST_B = gi.DASHBOARDS[1]


def _dash_dir(tmp_path):
    d = tmp_path / "grafana"
    d.mkdir()
    (d / _MANIFEST_A).write_text('{"uid": "a"}', encoding="utf-8")
    (d / _MANIFEST_B).write_text('{"uid": "b"}', encoding="utf-8")
    return d


def _reset_backoff(monkeypatch):
    monkeypatch.setattr(sup, "_dash_retry",
                        {"fails": 0, "next_ok": 0.0, "spawned_fp": ""})


def test_fingerprint_stable_and_content_sensitive(tmp_path):
    d = _dash_dir(tmp_path)
    fp1 = sup._dash_fingerprint(d)
    assert fp1 and fp1 == sup._dash_fingerprint(d)
    (d / _MANIFEST_A).write_text('{"uid": "a", "v": 2}', encoding="utf-8")
    assert sup._dash_fingerprint(d) != fp1
    empty = tmp_path / "empty"
    empty.mkdir()
    assert sup._dash_fingerprint(empty) == ""


def test_fingerprint_ignores_stray_json_but_sees_deletion(tmp_path):
    """Manifest-scoped (2026-08-17): a stray/leftover json used to hold
    the fingerprint permanently ahead of the stamp and re-trigger imports
    forever; a DELETED manifest board must still register as a change."""
    d = _dash_dir(tmp_path)
    fp1 = sup._dash_fingerprint(d)
    (d / "stray_scratch_export.json").write_text('{"uid": "stray"}',
                                                 encoding="utf-8")
    assert sup._dash_fingerprint(d) == fp1, \
        "a non-manifest json changed the fingerprint"
    (d / _MANIFEST_B).unlink()
    assert sup._dash_fingerprint(d) != fp1, \
        "deleting a manifest board did not change the fingerprint"


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
    (d / _MANIFEST_A).write_text('{"uid": "a", "v": 3}', encoding="utf-8")
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


# ---------------------------------------------------------------------
# import-loop hardening (2026-08-17) — planted defects, one per fix
# ---------------------------------------------------------------------
def _main_with_args(monkeypatch, stamp):
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "glsa_x")
    monkeypatch.setattr(sys, "argv",
                        ["grafana_import.py", "--stamp", str(stamp),
                         "--fingerprint", "fp-test"])


def test_urlerror_is_one_fail_line_not_a_crash(monkeypatch, tmp_path, capsys):
    """Planted defect: the network is down (URLError on every call). The
    import must print FAIL/WARN lines and return nonzero — never raise a
    traceback out of main() (the old behavior: only HTTPError was caught,
    so an offline PC crash-looped the child every 180s)."""
    _home(monkeypatch, tmp_path)
    stamp = tmp_path / "stamp"
    _main_with_args(monkeypatch, stamp)

    def _dead(*a, **k):
        raise urllib.error.URLError("name resolution failed (planted)")
    monkeypatch.setattr(gi, "_req", _dead)
    rc = gi.main()          # must not raise
    assert rc == 1
    assert not stamp.exists(), "network-dead run must not stamp"
    out = capsys.readouterr().out
    assert "FAIL" in out and "planted" in out


def test_retire_403_warns_but_still_stamps(monkeypatch, tmp_path, capsys):
    """Planted defect: boards POST fine, but DELETE of a retired uid is
    permission-denied (403). The stamp must still be written — the boards
    ARE current — with a WARN, so the supervisor does not re-import four
    unchanged boards every 180s forever. Exit code stays 0 (board
    success is what the exit code reports)."""
    _home(monkeypatch, tmp_path)
    stamp = tmp_path / "stamp"
    _main_with_args(monkeypatch, stamp)

    def _req(url, token, payload=None, method=None):
        if method == "DELETE":
            raise urllib.error.HTTPError(url, 403, "Forbidden", None,
                                         io.BytesIO(b"denied"))
        if url.endswith("/api/folders/liquiditybot-ops"):
            return {"uid": "liquiditybot-ops"}
        return {"url": "/d/x", "version": 1}
    monkeypatch.setattr(gi, "_req", _req)
    rc = gi.main()
    assert rc == 0
    assert stamp.read_text(encoding="utf-8") == "fp-test", \
        "retire failure held back the stamp - the 180s re-import loop"
    out = capsys.readouterr().out
    assert "WARN retire" in out


def test_backoff_doubles_on_observed_failure_and_resets(monkeypatch,
                                                        tmp_path):
    """The supervisor observes an import failure as 'I spawned for
    fingerprint X and the stamp still is not X'. Each observed failure
    doubles the retry gap from BOOT_GRACE_SEC toward the 1h cap; a
    success (stamp matches) resets everything."""
    _home(monkeypatch, tmp_path)
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "glsa_x")
    _reset_backoff(monkeypatch)
    d = _dash_dir(tmp_path)
    stamp = tmp_path / "stamp"
    fp = sup._dash_import_due(d, stamp)
    assert fp
    now = 1_000_000.0
    monkeypatch.setattr(sup.time, "time", lambda: now)
    sup._dash_mark_spawn(fp)                       # attempt 1
    assert sup._dash_retry["fails"] == 0
    assert sup._dash_retry["next_ok"] == now + sup.BOOT_GRACE_SEC
    assert sup._dash_import_due(d, stamp) == "", "no backoff after spawn"
    now += sup.BOOT_GRACE_SEC + 1                  # gap passes, still no stamp
    assert sup._dash_import_due(d, stamp) == fp
    sup._dash_mark_spawn(fp)                       # attempt 2 = 1st failure
    assert sup._dash_retry["fails"] == 1
    assert sup._dash_retry["next_ok"] == now + 2 * sup.BOOT_GRACE_SEC
    for _ in range(10):                            # cap at one hour
        now = sup._dash_retry["next_ok"] + 1
        assert sup._dash_import_due(d, stamp) == fp
        sup._dash_mark_spawn(fp)
    assert sup._dash_retry["next_ok"] - now <= sup._DASH_BACKOFF_CAP_SEC
    # success: the child stamps -> due goes quiet AND the ladder resets
    stamp.write_text(fp, encoding="utf-8")
    assert sup._dash_import_due(d, stamp) == ""
    assert sup._dash_retry == {"fails": 0, "next_ok": 0.0, "spawned_fp": ""}


def test_backoff_resets_on_content_change(monkeypatch, tmp_path):
    """A new deploy (new fingerprint) is a new fact — the ladder must not
    carry a stale failure count against fresh content."""
    _home(monkeypatch, tmp_path)
    monkeypatch.setenv("GRAFANA_SA_TOKEN", "glsa_x")
    _reset_backoff(monkeypatch)
    d = _dash_dir(tmp_path)
    stamp = tmp_path / "stamp"
    fp1 = sup._dash_import_due(d, stamp)
    sup._dash_mark_spawn(fp1)
    sup._dash_mark_spawn(fp1)
    assert sup._dash_retry["fails"] == 1
    (d / _MANIFEST_A).write_text('{"uid": "a", "v": 9}', encoding="utf-8")
    fp2 = sup._dash_fingerprint(d)
    assert fp2 != fp1
    sup._dash_mark_spawn(fp2)
    assert sup._dash_retry["fails"] == 0, \
        "failure count carried across a content change"
