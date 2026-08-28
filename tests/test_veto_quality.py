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


# ---------------------------------------------------------------------------
# era-confound guard (2026-08-27) — the SZ-021/frozen-baseline defect,
# INJECTED: a code whose rows share zero `label_era` with the baseline
# must refuse a significance verdict even when its point estimate would
# otherwise read disjoint; a code that DOES share the baseline's era must
# still get the normal verdict (this fix must not blanket-suppress).
# ---------------------------------------------------------------------------
def _era_row(disp, label, ts, era, span=600.0):
    r = _row(disp, label, ts, span)
    r["label_era"] = era
    return r


def test_disjoint_label_era_yields_confounded_verdict():
    """INJECTION: SZ-321's 40 rows are 100% `triple_barrier_h432`; the
    baseline is 100% `legacy`. Zero era overlap. At 80% win rate vs a 25%
    baseline this WOULD read disjoint-CI 'ANTI-SELECTIVE' under the old
    disp-only comparison (the exact SZ-021 shape, docs/HANDOFF.md REG-6,
    2026-08-27 caveat) — the fix must refuse the verdict instead."""
    t = 1_786_500_000.0
    rows = [_era_row("", 1 if i < 10 else 0, t + i * 3600, "legacy")
            for i in range(40)]
    rows += [_era_row("SZ-321", 1 if i < 32 else 0, t + (100 + i) * 3600,
                      "triple_barrier_h432") for i in range(40)]
    eff = ger.efficacy(rows, 30)
    r = {x["code"]: x for x in eff["by_code"]}["SZ-321"]
    assert r["era_overlap"] == 0.0
    assert r["comparison"] == "CONFOUNDED_BASELINE"
    assert r["anti_selective"] is False and r["selective"] is False
    # rates/CIs are still reported, not suppressed by the confound guard
    assert r["n"] == 40 and abs(r["rate"] - 0.80) < 1e-9
    assert r["lo"] is not None and r["hi"] is not None


def test_same_era_corpus_still_yields_normal_verdicts():
    """Control for the injection above: code and baseline SHARE a
    label_era, so the ordinary significance machinery must still fire —
    this guard may only suppress the disjoint-era case, not every
    verdict."""
    t = 1_786_600_000.0
    rows = [_era_row("", 1 if i < 10 else 0, t + i * 3600, "legacy")
            for i in range(40)]
    rows += [_era_row("SZ-322", 0, t + (100 + i) * 3600, "legacy")
             for i in range(40)]
    eff = ger.efficacy(rows, 30)
    r = {x["code"]: x for x in eff["by_code"]}["SZ-322"]
    assert r["era_overlap"] == 1.0
    assert r["comparison"] == "selective"
    assert r["selective"] is True and r["anti_selective"] is False


# ---------------------------------------------------------------------------
# fix-wave (2026-08-27): C1 weighted overlap, C2 admitted-vs-baseline guard,
# C4 nominal-n disclosure, C7 per-disposition comparison field, I1 cross-
# variant pooling regression, I5 _row_era precedence pin
# ---------------------------------------------------------------------------
def test_single_baseline_row_cannot_unfire_the_guard_via_membership():
    """C1(i): the FIRST cut of the era-confound guard checked SET
    membership ('does the baseline have ANY row of this era'), so ONE
    contaminating baseline row bought a code full (1.0) overlap. The
    weighted (histogram-intersection) overlap fixes this: a baseline
    era carried by 1 row out of 101 contributes almost nothing."""
    t = 1_786_700_000.0
    rows = [_era_row("", 1 if i < 25 else 0, t + i * 3600, "legacy")
            for i in range(100)]
    rows.append(_era_row("", 1, t + 100 * 3600, "triple_barrier_h432"))
    rows += [_era_row("SZ-501", 1 if i < 35 else 0, t + (200 + i) * 3600,
                      "triple_barrier_h432") for i in range(40)]
    eff = ger.efficacy(rows, 30)
    r = {x["code"]: x for x in eff["by_code"]}["SZ-501"]
    assert r["era_overlap"] < ger.ERA_OVERLAP_FLOOR, r["era_overlap"]
    assert r["comparison"] == "CONFOUNDED_BASELINE"
    assert r["anti_selective"] is False


def test_majority_incomparable_sample_does_not_print_unflagged_verdict():
    """C1(ii): a sample that is 93%+ drawn from an era the baseline
    never touches used to clear the flat 0.05 floor on its own small
    shared-era slice alone (40/600 = 6.7%) and print an unflagged
    verdict. ERA_OVERLAP_MAJORITY catches what the floor alone could
    not: PARTIAL_OVERLAP, not a silent pass-through."""
    t = 1_786_800_000.0
    rows = [_era_row("", 1 if i < 3 else 0, t + i * 3600, "legacy")
            for i in range(10)]
    rows += [_era_row("SZ-502", 1 if i < 3 else 0, t + (20 + i) * 3600,
                      "legacy") for i in range(4)]
    rows += [_era_row("SZ-502", 1 if i < 50 else 0, t + (30 + i) * 3600,
                      "triple_barrier_h432") for i in range(56)]
    eff = ger.efficacy(rows, 30)
    r = {x["code"]: x for x in eff["by_code"]}["SZ-502"]
    assert ger.ERA_OVERLAP_FLOOR <= r["era_overlap"] < ger.ERA_OVERLAP_MAJORITY, \
        r["era_overlap"]
    assert r["comparison"] == "PARTIAL_OVERLAP"
    assert r["anti_selective"] is False and r["selective"] is False


def test_by_code_distinguishes_uncomputable_neff_from_a_vetted_null():
    """C4: 'not_significant' used to mean two different epistemic states
    under one string - an honest effective-n-vetted overlap, and 'n_eff
    was not computable at all, this is the raw nominal-n fallback'.
    SZ-503's rows carry no ts/signal_ts at all, so n_eff is uncomputable
    on the code side while the era is fully comparable (era_overlap
    1.0) - isolating the neff axis from the era axis."""
    t = 1_786_900_000.0
    rows = [_era_row("", 1 if i < 10 else 0, t + i * 3600, "legacy")
            for i in range(40)]
    for i in range(40):
        rows.append({"disp": "SZ-503", "label": str(1 if i < 15 else 0),
                     "label_era": "legacy"})
    eff = ger.efficacy(rows, 30)
    r = {x["code"]: x for x in eff["by_code"]}["SZ-503"]
    assert r["era_overlap"] == 1.0
    assert r["neff_ok"] is False
    assert r["comparison"] == "not_significant_nominal_n"
    assert r["anti_selective"] is False and r["selective"] is False


def test_admitted_vs_baseline_headline_is_era_gated():
    """C2: the file's most prominent claim ('Does the gate select?')
    used to skip the era-confound guard entirely - the exact defect
    species the guard exists to catch, unfixed in the one place a
    reader looks first."""
    t = 1_787_000_000.0
    rows = [_era_row("", 1 if i < 10 else 0, t + i * 3600, "legacy")
            for i in range(40)]
    rows += [_era_row("entered", 1 if i < 5 else 0, t + (100 + i) * 3600,
                      "triple_barrier_h432") for i in range(40)]
    eff = ger.efficacy(rows, 30)
    assert eff["admitted_era_overlap"] == 0.0
    assert eff["admitted_comparison"] == "CONFOUNDED_BASELINE"
    md = ger.render(eff, [], ger.concentration(rows))
    assert "baseline CONFOUNDED" in md
    for stale in ("significance NOT assessed",
                  "separation is significant on effective n",
                  "adverse separation is SIGNIFICANT",
                  "not significant at this effective sample size"):
        assert stale not in md, f"neff-branch text leaked through: {stale!r}"


def test_admitted_vs_baseline_headline_stays_normal_when_comparable():
    """Control for the injection above: admitted set SHARES a label_era
    with baseline, so the ordinary significance machinery must still
    render - this guard may only suppress the disjoint-era case."""
    t = 1_787_100_000.0
    rows = [_era_row("", 1 if i < 10 else 0, t + i * 3600, "legacy")
            for i in range(40)]
    rows += [_era_row("entered", 1 if i < 30 else 0, t + (100 + i) * 3600,
                      "legacy") for i in range(40)]
    eff = ger.efficacy(rows, 30)
    assert eff["admitted_comparison"] not in ("CONFOUNDED_BASELINE",
                                              "PARTIAL_OVERLAP")
    md = ger.render(eff, [], ger.concentration(rows))
    assert "baseline CONFOUNDED" not in md
    assert "baseline PARTIAL OVERLAP" not in md


# ---------------------------------------------------------------------------
# F1 (2026-08-28 final review): the admitted-vs-baseline headline used to
# call _comparison with is_veto=True - a lie to the parameter that leaked
# the VETO significance vocabulary inverted onto a TAKEN sample. The
# admitted headline now speaks admitted-appropriate tokens
# (selects_winners / adverse_selection); the veto tokens stay untouched
# for by_code/per-disposition, and the confound states remain shared.
# ---------------------------------------------------------------------------
def test_admitted_headline_beating_baseline_is_selects_winners():
    """INJECTION (the reviewer's exact plant): admitted 0.90 vs baseline
    0.10, same era, intervals disjoint on effective n. Under the old
    is_veto=True lie this exported 'anti_selective' - the harm word for
    brilliant selection."""
    t = 1_787_300_000.0
    rows = [_era_row("", 1 if i < 4 else 0, t + i * 3600, "legacy")
            for i in range(40)]                       # baseline 0.10
    rows += [_era_row("entered", 1 if i < 36 else 0, t + (100 + i) * 3600,
                      "legacy") for i in range(40)]   # admitted 0.90
    eff = ger.efficacy(rows, 30)
    assert eff["admitted_era_overlap"] == 1.0
    assert eff["admitted_comparison"] == "selects_winners"
    assert eff["admitted_comparison"] != "anti_selective"
    md = ger.render(eff, [], ger.concentration(rows))
    assert "separation is significant on effective n" in md
    assert "adverse separation is SIGNIFICANT" not in md
    # extend-never-repurpose: the per-disposition admitted row still
    # reads the pre-existing non-veto token, untouched by this fix
    d = {x["disposition"]: x for x in eff["dispositions"]}["entered"]
    assert d["comparison"] == "not_applicable"


def test_admitted_headline_worse_than_baseline_is_adverse_selection():
    """Symmetric inverse of the injection above: admitted 0.10 vs
    baseline 0.90, same era, disjoint. Under the old lie this exported
    'selective' - the veto praise word for a gate reliably taking
    losers."""
    t = 1_787_400_000.0
    rows = [_era_row("", 1 if i < 36 else 0, t + i * 3600, "legacy")
            for i in range(40)]                       # baseline 0.90
    rows += [_era_row("entered", 1 if i < 4 else 0, t + (100 + i) * 3600,
                      "legacy") for i in range(40)]   # admitted 0.10
    eff = ger.efficacy(rows, 30)
    assert eff["admitted_era_overlap"] == 1.0
    assert eff["admitted_comparison"] == "adverse_selection"
    assert eff["admitted_comparison"] != "selective"
    md = ger.render(eff, [], ger.concentration(rows))
    assert "adverse separation is SIGNIFICANT" in md


def test_per_disposition_rows_carry_the_comparison_field():
    """C7: HANDOFF overclaimed the per-rule markdown table already
    carried `comparison: "CONFOUNDED_BASELINE"` (it only ever emitted
    prose; per-disposition dicts had confounded_baseline/era_overlap
    but no `comparison`). Per-disposition rows now carry the SAME
    vocabulary by_code has always had."""
    t = 1_787_200_000.0
    rows = [_era_row("", 1 if i < 10 else 0, t + i * 3600, "legacy")
            for i in range(40)]
    rows += [_era_row("SZ-504", 1 if i < 32 else 0, t + (100 + i) * 3600,
                      "triple_barrier_h432") for i in range(40)]
    eff = ger.efficacy(rows, 30)
    d = next(x for x in eff["dispositions"] if x["disposition"] == "SZ-504")
    assert d["comparison"] == "CONFOUNDED_BASELINE"
    assert d["confounded_baseline"] is True


def test_cross_variant_era_pooling_is_additive_not_last_write_wins():
    """I1: `era_mix_by_code[...].update(...)` accumulates a code's era
    mix ACROSS its parametrized variants; a regression to plain `=`
    would silently keep only the LAST-processed variant's mix. Two
    variants of the SAME code in DIFFERENT eras, 30 rows each - only
    correctly-summed pooling reads era_overlap exactly 0.5
    (COMPARABLE); a last-write-wins bug reads whichever variant is
    processed last (here: 0.0, CONFOUNDED)."""
    t = 1_787_300_000.0
    rows = [_era_row("", 1 if i < 10 else 0, t + i * 3600, "legacy")
            for i in range(40)]
    rows += [_era_row("SZ-601: p 0.10 below bar 0.50",
                      1 if i < 5 else 0, t + (100 + i) * 3600, "legacy")
             for i in range(30)]
    rows += [_era_row("SZ-601: p 0.40 below bar 0.50",
                      1 if i < 25 else 0, t + (200 + i) * 3600,
                      "triple_barrier_h432") for i in range(30)]
    eff = ger.efficacy(rows, 30)
    r = {x["code"]: x for x in eff["by_code"]}["SZ-601"]
    assert abs(r["era_overlap"] - 0.5) < 1e-9, r["era_overlap"]
    assert r["comparison"] not in ("CONFOUNDED_BASELINE", "PARTIAL_OVERLAP")


def test_row_era_precedence_matches_ml_history_except_the_documented_gap():
    """I5: `_row_era`'s precedence (persisted column first, barrier-
    derived fallback second) must track `ml.history._row_label_era`'s
    own precedence - drift in either order would silently mis-tag rows.
    The ONE documented, deliberate divergence (C3: a fallback-derived
    bare "triple_barrier" routes to "unknown" here, because this file
    cannot see which horizon produced it) is asserted explicitly, not
    left as an accident of behavior a future reader has to rediscover."""
    from ml.history import _row_label_era

    persisted_row = {"label_era": "triple_barrier_h999", "barrier": "tb_pt"}
    assert ger._row_era(persisted_row) == _row_label_era(persisted_row) \
        == "triple_barrier_h999"

    unambiguous_fallback = {"barrier": "sl"}      # exit_sim, unambiguous
    assert ger._row_era(unambiguous_fallback) == \
        _row_label_era(unambiguous_fallback) == "exit_sim"

    ambiguous_fallback = {"barrier": "tb_sl"}     # bare triple_barrier
    assert _row_label_era(ambiguous_fallback) == "triple_barrier"
    assert ger._row_era(ambiguous_fallback) == "unknown", (
        "documented divergence from ml.history: gate_efficacy_report "
        "cannot horizon-qualify a fallback-derived bare 'triple_barrier', "
        "so it routes to LABEL_ERA_UNKNOWN instead of trusting it")


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
                 "n_eff": 41.0, "anti_selective": True, "selective": False,
                 "comparison": "anti_selective", "era_overlap": 0.87}],
}}

_CONFOUNDED = {"efficacy": {
    "baseline": {"rate": 0.25, "lo": 0.18, "hi": 0.33},
    "by_code": [{"code": "SZ-021", "rate": 0.51, "lo": 0.44, "hi": 0.58,
                 "n_eff": 189.0, "anti_selective": False, "selective": False,
                 "comparison": "CONFOUNDED_BASELINE", "era_overlap": 0.0}],
}}


def test_collector_exports_confounded_gauge_and_era_overlap(monkeypatch):
    """C5: the era-confound guard's own verdict was invisible on glass -
    a code reading CONFOUNDED_BASELINE and a code reading a genuine
    not-significant null both exported anti=0.0/good=0.0 identically.
    The new gauge distinguishes them without renaming anything."""
    _fake_report(monkeypatch, _CONFOUNDED)
    out = gp._veto_quality_metrics(time.time())
    names = {m["name"] for m in out}
    assert "liquiditybot_veto_confounded" in names
    assert "liquiditybot_veto_era_overlap" in names
    confounded = [m for m in out
                 if m["name"] == "liquiditybot_veto_confounded"][0]
    assert confounded["gauge"]["dataPoints"][0]["asDouble"] == 1.0
    overlap = [m for m in out
              if m["name"] == "liquiditybot_veto_era_overlap"][0]
    assert overlap["gauge"]["dataPoints"][0]["asDouble"] == 0.0
    anti = [m for m in out
           if m["name"] == "liquiditybot_veto_anti_selective"][0]
    assert anti["gauge"]["dataPoints"][0]["asDouble"] == 0.0


def test_collector_confounded_gauge_reads_zero_for_a_clean_verdict(monkeypatch):
    _fake_report(monkeypatch, _GOOD)
    out = gp._veto_quality_metrics(time.time())
    confounded = [m for m in out
                 if m["name"] == "liquiditybot_veto_confounded"][0]
    assert confounded["gauge"]["dataPoints"][0]["asDouble"] == 0.0


_WITH_ADMITTED = {"efficacy": {
    "baseline": {"rate": 0.25, "lo": 0.18, "hi": 0.33},
    "admitted_era_overlap": 0.42,
    "admitted_comparison": "PARTIAL_OVERLAP",
    "by_code": [{"code": "SZ-030", "rate": 0.06, "lo": 0.03, "hi": 0.10,
                 "n_eff": 30.0, "anti_selective": False, "selective": True,
                 "comparison": "PARTIAL_OVERLAP", "era_overlap": 0.16}],
}}


def test_collector_exports_admitted_era_overlap_when_present(monkeypatch):
    """ERA-8 fix-wave: the admitted-vs-baseline headline
    (gate_efficacy_report's `admitted_era_overlap`, computed alongside
    `admitted_comparison`) reaches glass as its own gauge, extend-only —
    no existing key renamed, by_code unaffected."""
    _fake_report(monkeypatch, _WITH_ADMITTED)
    out = gp._veto_quality_metrics(time.time())
    names = {m["name"] for m in out}
    assert "liquiditybot_admitted_era_overlap" in names
    dp = [m for m in out
          if m["name"] == "liquiditybot_admitted_era_overlap"][0]
    assert dp["gauge"]["dataPoints"][0]["asDouble"] == 0.42
    # by_code table is untouched by the extension
    assert "liquiditybot_veto_cf_rate" in names


def test_collector_omits_admitted_era_overlap_when_absent(monkeypatch):
    """MUTATION-style negative: a payload identical to _GOOD except it
    never carries the top-level admitted_era_overlap field must NOT
    fabricate the gauge. Proves the guard actually gates on presence
    rather than always emitting (the failure this test would catch:
    hardcoding a 0.0 fallback instead of skipping the gauge)."""
    _fake_report(monkeypatch, _GOOD)
    out = gp._veto_quality_metrics(time.time())
    names = {m["name"] for m in out}
    assert "liquiditybot_admitted_era_overlap" not in names


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
