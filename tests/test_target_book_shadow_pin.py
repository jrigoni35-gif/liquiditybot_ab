"""The target book + idea lab are SHADOW: nothing that can place an order may
read them. That is the ONLY ground for `target_book` sitting in
core/cohort.py NON_DECISION_SECTIONS - if a decision module ever reads it,
this file goes red and the section must leave the exclusion (a cohort fork,
with an operator decision record)."""
import csv
import json
import math
import re
from pathlib import Path

from core import cohort
from core.config_guard import validate

ROOT = Path(__file__).resolve().parents[1]
PAT = re.compile(r"target_book|idea_lab|TargetBook|IdeaLab")


def _decision_files():
    return [f.relative_to(ROOT).as_posix() for f in cohort._module_files(ROOT)]


def test_no_decision_module_reads_the_shadow_book():
    offenders = [rel for rel in _decision_files()
                 if PAT.search((ROOT / rel).read_text(encoding="utf-8",
                                                      errors="replace"))]
    assert offenders == [], (
        f"decision modules reference the shadow book: {offenders} - remove "
        f"'target_book' from NON_DECISION_SECTIONS (cohort fork) and file "
        f"the operator decision record before wiring it")


def test_section_is_fingerprint_neutral_only_as_shadow():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    assert "target_book" in cohort.NON_DECISION_SECTIONS
    assert cfg["target_book"]["enabled"] is False
    assert cfg["target_book"]["mode"] == "shadow"
    stripped = {k: v for k, v in cfg.items() if k != "target_book"}
    assert cohort.config_fingerprint(cfg) == cohort.config_fingerprint(stripped)


def test_shipped_config_is_clean_and_live_claims_are_fatal():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    assert [m for s, m in validate(cfg) if "target_book" in m] == []
    for patch in ({"enabled": True}, {"mode": "live"}, {"gamma": 0},
                  {"aim_rate": 1.5}, {"tilt_cap": 1.0}, {"invest_frac": 1.2},
                  {"assets": ["BTC", "DOGE"]}, {"quote_offset_bps": -1}):
        bad = json.loads(json.dumps(cfg))
        bad["target_book"].update(patch)
        fat = [m for s, m in validate(bad) if s == "FATAL" and "target_book" in m]
        assert fat, f"no FATAL for {patch}"
    bad = json.loads(json.dumps(cfg))
    bad["target_book"]["idea_lab"]["min_evidence_steps"] = 10
    bad["target_book"]["idea_lab"]["retire_after_steps"] = 50
    assert any("min_evidence_steps" in m for s, m in validate(bad) if s == "FATAL")
    bad = json.loads(json.dumps(cfg))
    bad["target_book"]["pressure"]["max_band_mult"] = 0.5
    assert any("max_band_mult" in m for s, m in validate(bad) if s == "FATAL")


def test_replay_runs_offline_and_writes_only_where_told(tmp_path):
    from scripts import target_book_replay as rp
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    csv_dir = tmp_path / "ohlc"
    csv_dir.mkdir()
    for k, a in enumerate(cfg["target_book"]["assets"]):
        with (csv_dir / f"{a}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_open_s", "high", "low", "close"])
            for i in range(120):
                c = 100 * math.exp(0.05 * math.sin(i / (5 + k)))
                w.writerow([1_700_000_000 + 14400 * i, c * 1.01, c * 0.99, c])
    out = tmp_path / "out"
    assert rp.main(["--csv-dir", str(csv_dir), "--out", str(out)]) == 0
    reps = list(out.glob("replay_*.json"))
    assert len(reps) == 1
    rep = json.loads(reps[0].read_text(encoding="utf-8"))
    lab = rep["lab"]
    assert lab["n_trials"] == lab["alive"] + lab["retired"]
    assert set(rep["arms"]) == {"buy_hold", "no_band", "target_book"}
