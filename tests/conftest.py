"""Shared pytest plumbing.

Tests construct engines (firewall, order manager, ML governor) whose
internals write the process-wide audit singleton. Redirect it to a
session tmp file so synthetic QA records never enter the production
outputs/audit.jsonl trail - live audit pollution both buries real
dispositions and breaks the running bot's hash chain (SD-007).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_audit_trail(tmp_path_factory):
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(tmp_path_factory.mktemp("audit") / "audit.jsonl")
    configure_registry(tmp_path_factory.mktemp("models"))
