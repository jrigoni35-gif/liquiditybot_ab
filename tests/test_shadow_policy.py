"""Items 1b + 3 (2026-09-29): the shadow policy store.

It must record the model's p AT registration for every real candidate, never
break the loop, and never be read by anything that places, sizes or exits an
order - that last property is what keeps a shadow a shadow.
"""
import csv
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from ml.shadow_policy import HEADER, ShadowPolicyStore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))


def _rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_store_writes_header_and_row(tmp_path):
    s = ShadowPolicyStore(str(tmp_path / "sp.csv"))
    assert s.log(ts=1.5, candidate_id="cand-a-1", asset="ETH",
                 direction="long", model_p=0.41, decision_fp="abc")
    rows = _rows(tmp_path / "sp.csv")
    assert list(rows[0]) == HEADER
    assert rows[0]["candidate_id"] == "cand-a-1"
    assert rows[0]["model_p"] == "0.410000" and rows[0]["decision_fp"] == "abc"


def test_store_rejects_garbage_and_never_raises(tmp_path):
    s = ShadowPolicyStore(str(tmp_path / "sp.csv"))
    assert not s.log(ts=1, candidate_id="", asset="ETH", direction="long",
                     model_p=0.5, decision_fp="")          # no id
    assert not s.log(ts=1, candidate_id="c", asset="ETH", direction="long",
                     model_p=1.7, decision_fp="")          # p out of range
    assert not s.log(ts=1, candidate_id="c", asset="ETH", direction="long",
                     model_p="nan-ish", decision_fp="")    # unparseable
    bad = ShadowPolicyStore(str(tmp_path))                  # path is a dir
    assert not bad.log(ts=1, candidate_id="c", asset="ETH",
                       direction="long", model_p=0.5, decision_fp="")
    assert bad.dropped == 1


def test_engine_logs_one_shadow_row_per_real_registration(tmp_path,
                                                           monkeypatch):
    from test_decision_events import _bot
    monkeypatch.chdir(tmp_path)
    bot = _bot(tmp_path)
    assert bot.shadow_policy is not None
    bot.gate_stats.enabled = False
    bot.gates.evaluate_asset = lambda asset, v: SimpleNamespace(
        direction="long", all_confirmed=True, confidence=0.61,
        gates_passed={"rsi": True, "mom": True}, urgency=0.0,
        evidence_concentration=0.0, components={})
    for a in list(bot._scs_pending):
        bot._scs_pending[a] = True
    bot.slow_cycle(1_700_000_000.0)
    path = Path(bot.shadow_policy.path)
    assert path.exists(), "no shadow row written for a real registration"
    rows = _rows(path)
    assert rows and all(r["candidate_id"].startswith("cand-") for r in rows)
    assert all(0.0 <= float(r["model_p"]) <= 1.0 for r in rows)
    assert all(r["decision_fp"] == bot.decision_fp["fp"] for r in rows)
    for r in rows:                     # each row names a REAL open candidate
        assert bot.candidates.open_candidate_id(
            r["asset"], r["direction"]) == r["candidate_id"]


def test_no_order_path_module_reads_the_shadow_store():
    """Shadow purity: only main.py (the writer) and the report may touch it.
    A decision module reading it would promote the rule without the law."""
    pat = re.compile(r"shadow_policy|ShadowPolicyStore")
    allowed = {"ml/shadow_policy.py", "main.py"}
    offenders = []
    for sub in ("execution", "risk", "strategies", "regime", "core", "ml"):
        for f in sorted((ROOT / sub).rglob("*.py")):
            rel = f.relative_to(ROOT).as_posix()
            if rel in allowed or "__pycache__" in rel:
                continue
            if pat.search(f.read_text(encoding="utf-8", errors="replace")):
                offenders.append(rel)
    assert offenders == [], f"order-path modules read the shadow: {offenders}"
