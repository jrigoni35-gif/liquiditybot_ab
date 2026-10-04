"""SMOKE-CWD-1 pin: smoke section [20] builds a real BotRunner, whose control
queue and risk-off sentinels resolve against cwd. It must run in a scratch
cwd, never the checkout it was launched from (that is the live outputs/ on
the PC). Injection evidence: docs/HANDOFF.md, IN FLIGHT / BLOCKED."""
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import smoke_test  # noqa: E402


def test_section_20_is_dispatched_through_the_scratch_cwd():
    src = (ROOT / "scripts" / "smoke_test.py").read_text(encoding="utf-8")
    assert "_in_scratch_cwd(test_runtime_and_runner)" in src
    # a bare call anywhere (not the def) would bypass the scratch cwd
    assert not re.search(r"(?<!def )\btest_runtime_and_runner\(\)", src)


def test_scratch_cwd_leaves_the_launch_dir_and_restores_it(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    seen = []
    smoke_test._in_scratch_cwd(lambda: seen.append(Path.cwd().resolve()))
    assert seen and seen[0] != tmp_path.resolve()
    assert Path.cwd().resolve() == tmp_path.resolve()


def test_scratch_cwd_restores_even_when_the_section_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def boom():
        raise RuntimeError("section failed")
    with pytest.raises(RuntimeError):
        smoke_test._in_scratch_cwd(boom)
    assert Path(os.getcwd()).resolve() == tmp_path.resolve()
