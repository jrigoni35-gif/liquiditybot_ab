"""tests/test_grafana_import_manifest.py — the import tool's manifest stays
true: every dashboard it would push exists in the repo, is an UNWRAPPED
top-level model (the tool wraps at POST time — double-wrapping would 400),
and carries a stable uid so overwrite=true updates in place."""
import json
from pathlib import Path

from scripts.grafana_import import DASHBOARDS

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_files_exist_unwrapped_with_uids():
    seen_uids = set()
    for name in DASHBOARDS:
        p = ROOT / "docs" / "grafana" / name
        assert p.exists(), f"{name} listed in the import manifest but missing"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert "dashboard" not in d, f"{name} is API-wrapped; store unwrapped"
        assert d.get("schemaVersion"), f"{name} lacks schemaVersion"
        uid = d.get("uid")
        assert uid and uid not in seen_uids, f"{name}: missing/duplicate uid"
        seen_uids.add(uid)
