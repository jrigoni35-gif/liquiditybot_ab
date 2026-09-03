"""SessionStart hook: ONE WRITER PER BUNDLE LABEL (ISO-1, 2026-09-03).

THE DEFECT THIS KILLS: every cloud container launched the learning-durability
sidecar unconditionally under the SAME hard-coded label 'cloud-mirror', and
`hostname` is 'vm' in all of them, so N containers raced ONE path on the shared
`paper-telemetry` branch, last-writer-wins. Measured: three pushes to
sessions/cloud-mirror/ in ten minutes, only one of them the container that was
looking. Traffic was bidirectional - a session adopted another workspace's
meta_model.json + skimmer_active.json at boot.

It bought nothing: the sidecar protects rows THIS box generated, and since the
2026-07-17 one-bot directive the cloud launches no runner, so it generates none.
Measured the same day: local corpus, pc-live bundle and cloud-mirror bundle all
exactly 23,586 rows - the mirror carried zero rows the PC lacked.

These pins run the REAL decision block out of the shipped hook (not a copy)
under stubbed log/pgrep/setsid, so a rewrite that reintroduces an
unconditional launch or a shared constant label goes red.

Record: docs/quant/2026-09-03_workspace_isolation.md
"""
from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "session-start.sh"
_ANCHOR = 'if [ "${LB_BACKUP_DISABLED:-}" = "1" ]; then'


def _block() -> str:
    """The shipped section-6 decision block, verbatim."""
    text = HOOK.read_text(encoding="utf-8")
    assert _ANCHOR in text, (
        f"section-6 anchor not found in {HOOK.name} - the sidecar gate was "
        "rewritten. Re-anchor this test on the new guard rather than "
        "deleting it; the ISO-1 property still has to hold.")
    return text[text.index(_ANCHOR):]


def _run(env: dict, *, alive: bool = False, home: Path,
         work: Path) -> tuple[str, str]:
    """Execute the real block with side effects stubbed AND redirected.

    `work` is the cwd, so the block's `>> outputs/telemetry_backup.log`
    lands in a throwaway tree. That redirect is not incidental: it is the
    only observable for "a launch happened", because the launch line sends
    the child's stdout straight into that file. It also keeps this test off
    the production outputs/ tree - writing there is exactly the 2026-07-31
    contamination class (a fabricated line in an operator forensics log is
    indistinguishable from a real one after the fact), and this test wrote
    8 such lines before the cwd was pinned.

    A trailing `wait` is appended so the backgrounded launch has flushed
    before the assertions read the file.
    """
    if os.name == "nt":
        # `.claude/hooks/session-start.sh` is a CLOUD-CONTAINER script: it
        # exits at line 17 unless CLAUDE_CODE_REMOTE=true, and the PC never
        # runs it. Exercising it through git-bash on Windows tested nothing
        # the PC needs and REJECTED a real deploy (2026-09-03, auto_update
        # battery_detail named this file). The static pin at the bottom of
        # this module is the cross-platform guard.
        pytest.skip("session-start.sh is POSIX/cloud-only; static pin covers nt")
    if not shutil.which("bash"):
        pytest.skip("bash unavailable")
    (work / "outputs").mkdir(parents=True, exist_ok=True)
    stubs = textwrap.dedent(f"""
        PY=/bin/echo
        log() {{ echo "LOG: $*"; }}
        pgrep() {{ return {0 if alive else 1}; }}
        setsid() {{ echo "LAUNCH: $*"; }}
        nohup() {{ echo "$@"; }}
    """)
    # INHERIT the ambient environment (a hand-built dict drops SYSTEMROOT /
    # COMSPEC and breaks subprocess spawn on Windows) and control only the
    # flags under test, popping any the caller happens to have set.
    child = {**os.environ, "HOME": str(home)}
    for k in ("LB_CLOUD_RUNNER", "LB_BACKUP_FORCE",
              "LB_BACKUP_DISABLED", "LB_BACKUP_LABEL"):
        child.pop(k, None)
    child.update(env)
    r = subprocess.run(
        ["bash", "-c", stubs + _block() + "\nwait\n"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=60,
        cwd=str(work), env=child)
    assert r.returncode == 0, f"block exited {r.returncode}: {r.stderr}"
    launched = work / "outputs" / "telemetry_backup.log"
    return r.stdout, (launched.read_text(encoding="utf-8")
                      if launched.exists() else "")


def test_one_bot_default_does_not_write_to_the_shared_branch(tmp_path):
    """THE fix: no cloud runner -> no rows to protect -> no push, ever."""
    out, launch = _run({}, home=tmp_path / "h", work=tmp_path / "w")
    assert "retired" in out, out
    assert launch == "", (
        "the default cloud session still launches the durability sidecar - "
        f"that is ISO-1: N containers racing one bundle label. Got: {launch!r}")


def test_explicit_disable_still_wins(tmp_path):
    out, launch = _run({"LB_BACKUP_DISABLED": "1"},
                   home=tmp_path / "h", work=tmp_path / "w")
    assert "LB_BACKUP_DISABLED=1" in out and launch == "", (out, launch)


@pytest.mark.parametrize("flag", ["LB_CLOUD_RUNNER", "LB_BACKUP_FORCE"])
def test_opt_in_launches_with_a_per_container_label(flag, tmp_path):
    """Opting in is allowed - but never under the old shared constant."""
    out, launch = _run({flag: "1"},
                   home=tmp_path / "h", work=tmp_path / "w")
    assert "LAUNCH:" in launch, (out, launch)
    assert "cloud-mirror" not in out + launch, (
        "opted-in sidecar still uses the shared 'cloud-mirror' label - two "
        "opted-in containers would collide exactly as before")
    assert "label cloud-" in out, out


def test_label_is_stable_per_box_and_distinct_across_boxes(tmp_path):
    """Stable across boots (one label per box, not per boot) and distinct
    across boxes - the property that makes a writer identifiable at all."""
    box_a, box_b = tmp_path / "a", tmp_path / "b"
    box_a.mkdir(), box_b.mkdir()
    a1, _ = _run({"LB_CLOUD_RUNNER": "1"}, home=box_a, work=tmp_path / "wa")
    a2, _ = _run({"LB_CLOUD_RUNNER": "1"}, home=box_a, work=tmp_path / "wa")
    b1, _ = _run({"LB_CLOUD_RUNNER": "1"}, home=box_b, work=tmp_path / "wb")

    def label(out: str) -> str:
        line = [x for x in out.splitlines() if "relaunched (label " in x][0]
        return line.rsplit("label ", 1)[1].rstrip(")")

    assert label(a1) == label(a2), "label must persist across boots"
    assert label(a1) != label(b1), "two boxes must not share a label"


def test_already_alive_does_not_double_launch(tmp_path):
    out, launch = _run({"LB_CLOUD_RUNNER": "1"}, alive=True,
                   home=tmp_path / "h", work=tmp_path / "w")
    assert "already alive" in out and launch == "", (out, launch)


def test_shared_constant_label_is_gone_from_the_hook():
    """Static belt to the behavioural braces: the old hard-coded default
    must not come back by any route."""
    assert "LB_BACKUP_LABEL:-cloud-mirror" not in HOOK.read_text(
        encoding="utf-8"), (
        "the shared 'cloud-mirror' default is back in the hook - that single "
        "constant IS ISO-1")
