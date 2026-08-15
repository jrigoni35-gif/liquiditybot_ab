"""DL-2: headless sidecars must make git FAIL rather than ASK.

Measured 2026-08-13 (14h auth outage): a git call needing credentials popped
an interactive Git-Credential-Manager dialog that nobody could answer, and
timeout= could not rescue it — the credential helper is a GRANDCHILD holding
the inherited capture_output pipe, so after subprocess killed the direct child
communicate() still blocked waiting for an EOF the survivor never sent. Twelve
stacked pushers released simultaneously 14 hours later.

These pin the fix at the level it can actually regress: a new git call site
added without env= silently reopens the hole, and no behavioural test would
notice because the failure needs a credential prompt to reproduce.
"""
import inspect

import pytest

from scripts import auto_update, corpus_sync, remote_control, telemetry_backup

SIDECARS = [auto_update, corpus_sync, remote_control, telemetry_backup]

# Present in EVERY sidecar or a headless git call can still block.
REQUIRED = {
    "GIT_TERMINAL_PROMPT": "0",          # core git: never prompt on a terminal
    "GCM_INTERACTIVE": "never",          # Git-Credential-Manager: no UI
    "GIT_CONFIG_COUNT": "1",             # env-injected config (git >= 2.31),
    "GIT_CONFIG_KEY_0": "credential.interactive",   # == -c credential.
    "GIT_CONFIG_VALUE_0": "false",                  #    interactive=false
}

# (module, helper) for every function that shells out to git in these sidecars
GIT_HELPERS = [
    (auto_update, "_git"),
    (corpus_sync, "_git"),
    (corpus_sync, "_git_bytes"),
    (remote_control, "_git"),
    (telemetry_backup, "_run"),
    (telemetry_backup, "_run_bytes"),
]
_HELPER_IDS = [f"{m.__name__.split('.')[-1]}.{f}" for m, f in GIT_HELPERS]


@pytest.mark.parametrize("mod", SIDECARS, ids=lambda m: m.__name__.split(".")[-1])
def test_noprompt_table_complete(mod):
    for key, val in REQUIRED.items():
        assert mod._NOPROMPT.get(key) == val, \
            f"{mod.__name__}: _NOPROMPT missing {key}={val!r}"


@pytest.mark.parametrize("mod", SIDECARS, ids=lambda m: m.__name__.split(".")[-1])
def test_askpass_neutralized(mod):
    """A configured GUI askpass answers BEFORE GIT_TERMINAL_PROMPT is ever
    consulted, so disabling the terminal prompt alone is not sufficient."""
    assert mod._NOPROMPT.get("GIT_ASKPASS") == ""
    assert mod._NOPROMPT.get("SSH_ASKPASS") == ""


@pytest.mark.parametrize("mod", SIDECARS, ids=lambda m: m.__name__.split(".")[-1])
def test_git_env_extends_environ_and_overrides_win(mod, monkeypatch):
    monkeypatch.setenv("LB_SENTINEL_PASSTHROUGH", "kept")
    # a hostile inherited value must not survive
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "1")
    env = mod._git_env()
    assert env["LB_SENTINEL_PASSTHROUGH"] == "kept", \
        "must EXTEND os.environ, not replace it (PATH/HOME are needed)"
    assert env["GIT_TERMINAL_PROMPT"] == "0", "overrides must win"


@pytest.mark.parametrize("mod,fn", GIT_HELPERS, ids=_HELPER_IDS)
def test_git_helper_passes_env_and_timeout(mod, fn):
    """Both halves are load-bearing: env= stops the prompt happening, and
    timeout= bounds the call if some OTHER helper ever blocks anyway."""
    src = inspect.getsource(getattr(mod, fn))
    assert "env=_git_env()" in src, f"{mod.__name__}.{fn}: git call without env="
    assert "timeout=" in src, f"{mod.__name__}.{fn}: git call without timeout="


@pytest.mark.parametrize("mod", SIDECARS, ids=lambda m: m.__name__.split(".")[-1])
def test_no_unbounded_subprocess_run(mod):
    """telemetry_backup shipped two subprocess.run calls with NO timeout at
    all (_run, _run_bytes). An unbounded call in a sidecar has no ceiling
    whatsoever, so pin the whole module, not just the two that were fixed."""
    src = inspect.getsource(mod)
    for i, chunk in enumerate(src.split("subprocess.run(")[1:]):
        assert "timeout=" in chunk[:500], \
            f"{mod.__name__}: subprocess.run #{i + 1} has no timeout="
