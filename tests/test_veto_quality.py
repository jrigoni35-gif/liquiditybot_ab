"""The veto-quality instrument chain: by_code pooling in
gate_efficacy_report, and the gc_pusher collector that puts it on glass.

WHY THESE PINS. The "Why entries die" panel counted veto fires for months
while the corpus held every veto's counterfactual outcome unread — a gate
that anti-selects (rejects candidates that win MORE than baseline) looked
identical to one earning its keep. The pooling that fixes this has one
subtle obligation and one incident behind it:

  * POOLING IS ONLY SOUND BECAUSE DISPOSITIONS PARTITION THE CORPUS —
    each labeled row carries exactly one disposition string, so summing a
    code's parametrized variants ("p 0.28 below bar 0.63", "p 0.51 below
    bar 0.69", ...) adds disjoint samples. The tests plant a fixture
    where the pooled answer differs from every variant's own answer and
    pin the pooled arithmetic exactly.
  * THE FIRST IMPLEMENTATION SHIPPED BLIND: literal backspace bytes
    (\\x08) landed inside the code regex via shell escaping, matched
    nothing, and the terminal ERASED them on display so every visual
    inspection read clean. by_code returned [] on a corpus with 10
    active codes. Hence the byte-level pin below — grep cannot be
    trusted to see this class.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.gate_efficacy_report as ger  # noqa: E402
import scripts.gc_pusher as gp              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# fixture corpus: dispositions partition rows; one code has two variants
# ---------------------------------------------------------------------------
def _row(disp, label, ts, span=600.0):
    # gate_efficacy's effective-n reads signal_ts + label window columns;
    # keep rows temporally spread so n_eff is computable and near-nominal
    return {"disp": disp, "label": str(label), "signal_ts": str(ts),
            "ts": str(ts), "label_resolved_ts": str(ts + span)}


def _corpus():
    rows = []
    t = 1_786_000_000.0
    # baseline (blank disp): 40 rows, 10 winners -> rate 0.25
    for i in range(40):
        rows.append(_row("", 1 if i < 10 else 0, t + i * 3600))
    # SZ-777 variant A: 30 rows, 3 winners; variant B: 30 rows, 24 winners
    # pooled: 60 rows, 27 winners -> 0.45; NEITHER variant equals that
    for i in range(30):
        rows.append(_row("SZ-777: p 0.10 below bar 0.50",
                         1 if i < 3 else 0, t + (100 + i) * 3600))
    for i in range(30):
        rows.append(_row("SZ-777: p 0.40 below bar 0.50",
                         1 if i < 24 else 0, t + (200 + i) * 3600))
    # SZ-888: strongly selective veto - 40 rows, 0 winners
    for i in range(40):
        rows.append(_row("SZ-888", 0, t + (300 + i) * 3600))
    # admitted rows must stay out of by_code
    for i in range(35):
        rows.append(_row("entered", 1 if i < 12 else 0,
                         t + (400 + i) * 3600))
    return rows


def _by_code(min_n=30):
    eff = ger.efficacy(_corpus(), min_n)
    return eff, {r["code"]: r for r in eff["by_code"]}


def test_variants_pool_into_one_code_with_summed_counts():
    _, codes = _by_code()
    assert set(codes) == {"SZ-777", "SZ-888"}
    r = codes["SZ-777"]
    assert (r["n"], r["wins"], r["variants"]) == (60, 27, 2)
    assert abs(r["rate"] - 0.45) < 1e-9


def test_admitted_and_baseline_rows_never_enter_by_code():
    eff, codes = _by_code()
    total_pooled = sum(r["n"] for r in codes.values())
    assert total_pooled == 100          # 60 + 40; not 40 baseline, not 35 entered
    assert eff["baseline"]["n"] == 40


def test_min_n_gates_the_pooled_code_not_the_variants():
    # each SZ-777 variant is 30 rows; at min_n=50 the code still appears
    # because POOLED n=60 clears it - the whole point of pooling
    _, codes = _by_code(min_n=50)
    assert "SZ-777" in codes
    assert "SZ-888" not in codes or codes["SZ-888"]["n"] >= 50


def test_selective_flag_fires_on_the_all_loser_veto():
    _, codes = _by_code()
    r = codes["SZ-888"]
    assert r["rate"] == 0.0
    assert r["selective"] is True and r["anti_selective"] is False


def test_flags_require_effective_n_on_both_sides():
    """The significance discipline: no effective n, no flag - same rule
    the per-disposition section enforces."""
    rows = [_row("", 1 if i < 2 else 0, 1e9) for i in range(8)]
    rows += [_row("SZ-999", 0, 1e9) for _ in range(40)]
    eff = ger.efficacy(rows, 5)
    r = {x["code"]: x for x in eff["by_code"]}.get("SZ-999")
    if r is not None and not (r["neff_ok"] and eff["baseline"]["neff_ok"]):
        assert r["anti_selective"] is False and r["selective"] is False


def test_code_regex_contains_no_control_bytes():
    """The \\x08 incident, pinned at byte level: shell-mangled escapes
    became literal backspaces inside the regex, matched nothing, and were
    INVISIBLE in terminal output. No control byte may appear anywhere in
    the source file."""
    data = (ROOT / "scripts" / "gate_efficacy_report.py").read_bytes()
    bad = [b for b in set(data) if b < 9 or (13 < b < 32)]
    assert not bad, f"control bytes {bad!r} in gate_efficacy_report.py"
    src = data.decode("utf-8")
    m = re.search(r'code_re = re\.compile\(r"(.+?)"\)', src)
    assert m, "by_code pooling regex missing"
    assert re.search(m.group(1), "SZ-023: p 0.28 below bar 0.63")


# ---------------------------------------------------------------------------
# gc_pusher collector
# ---------------------------------------------------------------------------
def _fake_report(monkeypatch, payload, rc=0):
    class _P:
        returncode = rc
        stdout = json.dumps(payload).encode()
        stderr = b""

    monkeypatch.setattr(gp.subprocess, "run", lambda *a, **k: _P())
    monkeypatch.setattr(gp, "_veto_cache",
                        {"next_attempt": 0.0, "values": None})


_GOOD = {"efficacy": {
    "baseline": {"rate": 0.25, "lo": 0.18, "hi": 0.33},
    "by_code": [{"code": "SZ-777", "rate": 0.45, "lo": 0.32, "hi": 0.58,
                 "n_eff": 41.0, "anti_selective": True, "selective": False}],
}}


def test_collector_exports_baseline_band_and_per_code_gauges(monkeypatch):
    _fake_report(monkeypatch, _GOOD)
    out = gp._veto_quality_metrics(time.time())
    names = {m["name"] for m in out}
    assert {"liquiditybot_veto_baseline_rate", "liquiditybot_veto_cf_rate",
            "liquiditybot_veto_anti_selective"} <= names
    anti = [m for m in out
            if m["name"] == "liquiditybot_veto_anti_selective"][0]
    dp = anti["gauge"]["dataPoints"][0]
    assert dp["asDouble"] == 1.0
    assert dp["attributes"] == [
        {"key": "code", "value": {"stringValue": "SZ-777"}}]


def test_collector_is_all_or_nothing_on_a_missing_baseline(monkeypatch):
    """A quality table judged against no baseline band is unreadable -
    the collector must emit NOTHING, not a partial batch that renders as
    bars with no reference."""
    broken = {"efficacy": {"baseline": {"rate": 0.25},
                           "by_code": _GOOD["efficacy"]["by_code"]}}
    _fake_report(monkeypatch, broken)
    assert gp._veto_quality_metrics(time.time()) == []


def test_collector_drops_stale_values_on_failure(monkeypatch):
    """Same contract as _cohort_metrics: a failed refresh DROPS the prior
    values - absent is the honest shape of a number that can no longer be
    re-derived."""
    _fake_report(monkeypatch, _GOOD)
    now = time.time()
    assert gp._veto_quality_metrics(now)
    _fake_report(monkeypatch, {}, rc=1)
    gp._veto_cache["next_attempt"] = 0.0
    gp._veto_cache["values"] = gp._run_veto_quality()
    assert gp._veto_quality_metrics(now) == []


def test_collector_caches_between_attempts(monkeypatch):
    calls = []
    _fake_report(monkeypatch, _GOOD)
    real_run = gp._run_veto_quality
    monkeypatch.setattr(gp, "_run_veto_quality",
                        lambda: (calls.append(1) or real_run()))
    now = time.time()
    gp._veto_quality_metrics(now)
    gp._veto_quality_metrics(now + 1.0)      # inside the cadence window
    assert len(calls) == 1
