# -*- coding: utf-8 -*-
"""The honest-absence presentation contract.

A panel that renders Grafana's stock "No data" tells the operator nothing
about WHY it is empty. Two unrelated facts render identically: the bot has
not yet done the thing the series counts, and the telemetry that should
always be there is gone. These tests pin that the board distinguishes them.

Every assertion here was mutation-verified: each one was made to fail by
breaking exactly the property it names.
"""
import json
import re
import time
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.gc_pusher as gp
from tests.test_trading_dashboard import _SYNTH_STATUS

ROOT = Path(__file__).resolve().parents[1]
MET = re.compile(r"liquiditybot_[a-z0-9_]+")


def _panels(d):
    for p in d.get("panels") or []:
        yield p
        for s in p.get("panels") or []:
            yield s


def _metrics(panel):
    out = set()
    for t in panel.get("targets") or []:
        out |= set(MET.findall(t.get("expr") or ""))
    return out


def _no_value(panel):
    return ((panel.get("fieldConfig") or {}).get("defaults") or {}).get("noValue")


def _all_panels():
    for f, d in gen.DASHBOARDS.items():
        for p in _panels(d):
            yield f, p


# --------------------------------------------------------------------------
def test_always_on_set_matches_the_exporter(tmp_path):
    """_ALWAYS_ON is a hand-written declaration; this recomputes it by
    RUNNING the exporter against a status.json that carries no content at
    all, so the declaration cannot drift from the code it describes."""
    p = tmp_path / "status.json"
    p.write_text(json.dumps({"written_at": time.time(),
                             "runner_state": "RUNNING"}), encoding="utf-8")
    emitted = {m["name"] for m in gp.collect(str(p))}
    assert gen._ALWAYS_ON == emitted, (
        "declared _ALWAYS_ON != what gc_pusher emits from an empty status; "
        f"only-declared={sorted(gen._ALWAYS_ON - emitted)} "
        f"only-emitted={sorted(emitted - gen._ALWAYS_ON)}")


def test_every_data_panel_declares_what_its_absence_means():
    """No queried data panel may fall back to Grafana's bare 'No data'."""
    bare = [(f, p["id"], p.get("title"))
            for f, p in _all_panels()
            if p.get("type") in gen._NV_TYPES and _metrics(p)
            and not _no_value(p)]
    assert not bare, f"panels with no honest empty-state text: {bare}"


def test_absence_of_an_always_on_series_reads_as_a_defect():
    """Both directions. A panel built only on always-on metrics must say
    'this is broken'; a panel built on event/section-gated metrics must
    never say that."""
    wrong_defect, wrong_honest = [], []
    for f, p in _all_panels():
        if p.get("type") not in gen._NV_TYPES:
            continue
        mets = _metrics(p)
        if not mets:
            continue
        nv = _no_value(p)
        if any(m in gen._ALWAYS_ON for m in mets):
            if nv != gen._NV_DEFECT:
                wrong_defect.append((f, p["id"], p.get("title"), nv))
        elif nv == gen._NV_DEFECT:
            wrong_honest.append((f, p["id"], p.get("title")))
    assert not wrong_defect, f"always-on panels not marked as defects: {wrong_defect}"
    assert not wrong_honest, f"honest-absence panels marked as defects: {wrong_honest}"


def test_defect_text_is_not_confusable_with_an_honest_absence(tmp_path):
    """The whole point is that an operator can tell them apart at a glance.

    FRAMEWORK, not content: the vocabulary (_NV_DEFECT, _NO_VALUE_BY_FAMILY)
    and the rule that chooses between its two halves (_panel_no_value) live
    in the generator, not in any panel, so they outlive the boards.

    This test used to close by scanning the SHIPPED panels for each half.
    That clause pinned deleted panels and is unsatisfiable on a board with
    zero of them, so it is replaced by asking the rule itself — driven with
    the real metric names gc_pusher puts on the wire, not hand-written ones.
    Strictly wider than the clause it replaces: the old version needed one
    panel per half, this one holds every emittable metric to its half."""
    honest = {v for _, v in gen._NO_VALUE_BY_FAMILY.values()}
    assert gen._NV_DEFECT not in honest
    for h in honest:
        assert h not in gen._NV_DEFECT and gen._NV_DEFECT not in h, h

    p = tmp_path / "status.json"
    p.write_text(json.dumps({**_SYNTH_STATUS, "written_at": time.time()}),
                 encoding="utf-8")
    emittable = {m["name"] for m in gp.collect(str(p))}

    def _nv_of(metric):
        return gen._panel_no_value({"type": "stat",
                                    "targets": [{"expr": metric}]})

    always = sorted(emittable & gen._ALWAYS_ON)
    gated = sorted(n for n in emittable if n not in gen._ALWAYS_ON
                   and any(n.startswith(k) for k in gen._NO_VALUE_BY_FAMILY))
    assert always, "exporter emits no always-on metric to test the defect half"
    assert gated, "exporter emits no gated metric to test the honest half"

    wrong_defect = [n for n in always if _nv_of(n) != gen._NV_DEFECT]
    wrong_honest = [n for n in gated if _nv_of(n) not in honest]
    assert not wrong_defect, f"always-on metrics not marked broken: {wrong_defect}"
    assert not wrong_honest, f"gated metrics not given an honest text: {wrong_honest}"


def test_no_always_on_metric_can_resolve_to_a_precondition():
    """An always-on metric has no precondition to await — resolving one
    would print a soothing lie over a telemetry outage. Family prefixes
    legitimately overlap always-on names (liquiditybot_ml_ vs
    liquiditybot_ml_use_model); what must hold is that the always-on
    short-circuit in _nv_family wins every time."""
    leaks = [n for n in sorted(gen._ALWAYS_ON) if gen._nv_family(n) is not None]
    assert not leaks, f"always-on metrics that resolve to a precondition: {leaks}"


def test_every_map_key_names_a_real_exporter_family(tmp_path):
    """No invented families: every key must prefix a metric gc_pusher can
    actually emit."""
    p = tmp_path / "status.json"
    p.write_text(json.dumps({**_SYNTH_STATUS, "written_at": time.time()}),
                 encoding="utf-8")
    emittable = {m["name"] for m in gp.collect(str(p))}
    bogus = [k for k in gen._NO_VALUE_BY_FAMILY
             if not any(n.startswith(k) for n in emittable)]
    assert not bogus, f"map keys matching no emittable metric: {bogus}"


def test_every_queried_metric_has_a_declared_precondition():
    """The build already raises on an undeclared family; this states the
    invariant as a readable failure instead of an import error."""
    undeclared = []
    for _, p in _all_panels():
        for m in _metrics(p):
            try:
                gen._nv_family(m)
            except KeyError:
                undeclared.append(m)
    assert not undeclared, (
        f"panels query metrics with no declared precondition: "
        f"{sorted(set(undeclared))}")


def test_no_value_strings_fit_on_a_panel():
    strings = [gen._NV_DEFECT] + [v for _, v in gen._NO_VALUE_BY_FAMILY.values()]
    for s in strings:
        assert s.strip() == s and "\n" not in s, repr(s)
        assert 0 < len(s) <= 60, f"{len(s)} chars is too long for a tile: {s!r}"


def test_tables_keep_the_cell_dot_never_a_sentence():
    """In a table, noValue fills every empty CELL. A sentence per cell is
    unreadable, so tables are excluded from the rewrite by design."""
    assert "table" not in gen._NV_TYPES
    for f, p in _all_panels():
        if p.get("type") == "table":
            assert _no_value(p) == "·", (f, p["id"], _no_value(p))


def test_timeseries_carry_every_precondition_in_the_description():
    """A timeseries can plot several families at once, and one noValue
    string cannot name them all — the description does."""
    for f, p in _all_panels():
        if p.get("type") != "timeseries" or not _metrics(p):
            continue
        desc = p.get("description") or ""
        assert "Empty means:" in desc, (f, p["id"], p.get("title"))
        for msg in gen._nv_all_preconditions(p):
            assert msg in desc, (f, p["id"], msg)


def test_regeneration_is_byte_deterministic_and_matches_disk():
    for fname, d in gen.DASHBOARDS.items():
        a = json.dumps(d, indent=2, ensure_ascii=False)
        b = json.dumps(d, indent=2, ensure_ascii=False)
        assert a == b, f"{fname} does not serialise deterministically"
        disk = (ROOT / "docs" / "grafana" / fname).read_text(encoding="utf-8")
        assert a == disk, f"{fname} on disk is stale — regenerate"
