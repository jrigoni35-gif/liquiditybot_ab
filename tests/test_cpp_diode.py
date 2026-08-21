"""Differential harness for diode/lb_diode.cpp — the compiled referee.

The C++ diode must reproduce the PRE-REGISTERED Python rules on identical
inputs: ground truth here is computed by CALLING scripts.cohort_eval
(era4_trips, wilson) on the same fixture, never by hand-written expected
values. The 1e-9 tolerance on gross/net/wilson is a measurement standard,
not a tunable — if a rounding tie ever surfaces, move the FIXTURE values
off the tie (and say so in a comment), never widen the tolerance.

Skips when no C++ compiler is on PATH: the PC's Windows battery has none
and must stay green. A compile FAILURE with a compiler present is a test
failure — the file must always build.

Strict-ingest vs DictReader: the C++ S0 reader DROPS width-mismatched rows
where csv.DictReader None-fills them. The fixture keeps the two in
agreement by giving every torn/long row its own position_id, so the trip
it implies dies in BOTH implementations (parse-fail in Python, row-drop in
C++). A torn row sharing a pid with a valid trip would legitimately
diverge and is out of the diode's contract.

All writes stay under tmp_path (conftest outputs-guard).
"""
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.cohort_eval as ce
from core.fill_ledger import COLS
from ml.history import HistoryStore

_CXX = shutil.which("g++") or shutil.which("clang++")
_SKIP_REASON = ("no C++ compiler (g++/clang++) on PATH - the diode "
                "differential harness compiles diode/lb_diode.cpp; the "
                "Windows battery stays green by skipping")
pytestmark = pytest.mark.skipif(_CXX is None, reason=_SKIP_REASON)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "diode" / "lb_diode.cpp"
TOL = 1e-9


@pytest.fixture(scope="session")
def diode_bin(tmp_path_factory):
    exe = tmp_path_factory.mktemp("diode") / "lb_diode"
    proc = subprocess.run(
        [_CXX, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
         "-o", str(exe), str(SRC)],
        capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        pytest.fail("diode/lb_diode.cpp must always build:\n" + proc.stderr)
    return exe


def _run(exe, outdir):
    proc = subprocess.run([str(exe), str(outdir)],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.isascii(), "diode output must be ASCII"
    return json.loads(proc.stdout)


# --- fixture builders ------------------------------------------------------

_ERA = "7-e7d5ca1a"


def _fill(ts, oid, pid, purpose, side, size, price, fee, era=_ERA):
    # core.fill_ledger.COLS order: ts,order_id,position_id,purpose,symbol,
    # side,ordertype,post_only,attempt,fill_size,fill_price,arrival_ref,
    # slip_bps,fees_delta_usd,remaining,reason,exec_era
    row = {c: "" for c in COLS}
    row.update({"ts": str(ts), "order_id": oid, "position_id": pid,
                "purpose": purpose, "symbol": "ETH/USD", "side": side,
                "ordertype": "limit", "post_only": "1", "attempt": "1",
                "fill_size": repr(size), "fill_price": repr(price),
                "arrival_ref": repr(price), "slip_bps": "0.0",
                "fees_delta_usd": repr(fee), "remaining": "0.0",
                "reason": "qa", "exec_era": era})
    return [row[c] for c in COLS]


def _write_fills(path):
    """The differential fills fixture. Integer ts (exact under the diode's
    %.17g — the plan said %.10g, disproven by fuzz 2026-08-19, see the
    lb_diode.cpp S6 comment) and sizes/prices far from the
    round(.,6)/round(.,4) tie cases, per the plan's llround-vs-banker's
    note."""
    rows = [
        # (a) valid entry-opened era-4 round trip — exit row FIRST in file
        # order so the stable ts-sort is what reconstructs the trip
        _fill(1786503600, "oA2", "pA", "exit", "sell", 10.0, 1.2510, 0.06,
              era=" 7-e7d5ca1a "),        # padded stamp pins strip()
        _fill(1786500000, "oA1", "pA", "entry", "buy", 10.0, 1.2345, 0.05),
        # (b) hedge-opened trip: reconstructed, then excluded from the
        # verdict population (a hedge is insurance, not the thesis)
        _fill(1786505000, "oB1", "pB", "hedge", "buy", 3.0, 2.5, 0.01),
        _fill(1786508000, "oB2", "pB", "exit", "sell", 3.0, 2.6, 0.01),
        # (c) pre-epoch entry trip: closed before max(B4, CAPITAL_EPOCH),
        # excluded — but its signature is CONSUMED (see pF)
        _fill(1786000000, "oC1", "pC", "entry", "buy", 4.0, 5.0, 0.02),
        _fill(1786100000, "oC2", "pC", "exit", "sell", 4.0, 5.1, 0.02),
        # (d) duplicate fill pattern of pA (fees/ts differ; the signature
        # ignores both) — dropped by the dedupe
        _fill(1786600000, "oD1", "pD", "entry", "buy", 10.0, 1.2345, 0.07),
        _fill(1786600600, "oD2", "pD", "exit", "sell", 10.0, 1.2510, 0.01),
        # (e) short-side entry, pre-stamp blank exec_era, 1% size tear
        # (inside the 2% tolerance) — a valid LOSING era-4 trip
        _fill(1786520000, "oE1", "pE", "entry", "sell", 5.0, 2.0, 0.03,
              era=""),
        _fill(1786527200, "oE2", "pE", "exit", "buy", 4.95, 2.03, 0.03,
              era=""),
        # (f) era-4-valid trip whose pattern equals pre-epoch pC: blocked,
        # because the dedupe set is consulted BEFORE the epoch filter —
        # ordering the C++ must mirror
        _fill(1786700000, "oF1", "pF", "entry", "buy", 4.0, 5.0, 0.02),
        _fill(1786700600, "oF2", "pF", "exit", "sell", 4.0, 5.1, 0.02),
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        w.writerows(rows)
        # (e2) torn short row, own pid: BOTH None-fill (C++ dictreader
        # mode mirrors DictReader restval) and the trip dies on the
        # absent fill_size — both agree; C++ counts it in short_rows
        fh.write("1786530000,oT,pT,entry,ETH/USD\n")
        # (e3) over-wide row, own pid, entry-only: both keep it (extras
        # unaddressable) and the trip never closes — both agree; C++
        # counts it in long_rows
        w.writerow(_fill(1786540000, "oL1", "pL", "entry", "buy",
                         2.0, 3.0, 0.01) + ["extra-field"])
        # (g2) STALE-BINARY trip: two 16-column legs (no exec_era field
        # at all — the pre-stamp writer's schema), forming a VALID
        # era-4 entry-opened trip. The 2026-08-19 real-data differential
        # caught v1 dropping these (16 vs 21 accrued): DictReader keeps
        # them with exec_era=None -> stale_legs, and the accrual counts
        # the trip. The era4 differential below arbitrates via Python.
        fh.write("1786800000,oS1,pS,entry,ETH/USD,buy,limit,1,1,3.0,4.0,"
                 "4.0,0.0,0.02,0.0,fill\n")
        fh.write("1786803600,oS2,pS,exit,ETH/USD,sell,limit,1,1,3.0,4.1,"
                 "4.1,0.0,0.02,0.0,fill\n")


def _write_equity(path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write("ts,equity,daily_pnl\n")
        fh.write("1786400000,800.0,0.0\n")
        fh.write("1786450000,812.5,12.5\n")
        fh.write("1786460000,n/a,0.0\n")      # kept row, invalid equity
        fh.write("1786470000\n")              # torn short row: dropped
        fh.write("1786500000,790.25,-22.25\n")


def _sig_row(pid, source, label, disp="entered"):
    header = HistoryStore("unused.csv")._header
    vals = []
    for col in header:
        if col == "position_id":
            vals.append(pid)
        elif col == "asset":
            vals.append("ETH")
        elif col == "side":
            vals.append("long")
        elif col == "label":
            vals.append(label)
        elif col == "source":
            vals.append(source)
        elif col == "disp":
            vals.append(disp)
        else:
            vals.append("0.0")
    return vals


def _write_signal(path):
    header = HistoryStore("unused.csv")._header
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerow(_sig_row("s1", "live", "1"))
        w.writerow(_sig_row("s2", "live", "0"))
        w.writerow(_sig_row("s3", "live", "1"))
        # quoted embedded comma exercises the RFC-4180 path in S0
        w.writerow(_sig_row("s4", "candidate", "0", disp="capped, SZ-001"))
        w.writerow(_sig_row("s5", "candidate", ""))  # unlabeled candidate


_AUDIT_RECS = [
    {"ts": 1786400001, "code": "OM-011", "msg": "entry limit ok", "seq": 1},
    {"ts": 1786400002, "code": "OM-011", "seq": 2},
    {"ts": 1786400003, "code": "FW-070", "msg": "café", "seq": 3},
    {"ts": 1786400004, "code": "OM-011", "seq": 4},
    {"ts": 1786400005, "code": "FW-070", "seq": 5},
    {"ts": 1786400006, "code": "SZ-001",
     "data": {"nested": [1, 2, {"deep": True}]}, "seq": 6},
]


def _write_audit(path):
    with open(path, "w", encoding="utf-8") as fh:
        # json.dumps ensure_ascii -> the é escape exercises S1
        fh.writelines(json.dumps(rec) + "\n" for rec in _AUDIT_RECS)
        fh.write("{this is not json\n")        # counted, never coerced


@pytest.fixture()
def fixture_dir(tmp_path):
    out = tmp_path / "outputs"
    out.mkdir()
    _write_fills(out / "fills.csv")
    _write_equity(out / "equity.csv")
    _write_signal(out / "signal_history.csv")
    _write_audit(out / "audit.jsonl")
    return out


# --- the differential loop -------------------------------------------------

def test_era4_matches_python_reference(diode_bin, fixture_dir):
    rep = _run(diode_bin, fixture_dir)
    py_trips = ce.era4_trips(str(fixture_dir / "fills.csv"))

    # hand-known shape first, so a silent Python regression cannot make a
    # trivially-empty comparison "pass": pA and pE accrue; pB (hedge-opened),
    # pC (pre-epoch), pD (duplicate of pA) and pF (signature consumed by
    # pre-epoch pC before the epoch filter ran) all stay out
    assert [t["pid"] for t in py_trips] == ["pA", "pE", "pS"]

    e4 = rep["era4"]
    assert e4["accrual_n"] == len(py_trips) == 3
    assert e4["target"] == ce.ERA4_MIN_N
    assert len(e4["trips"]) == len(py_trips)
    for c_t, p_t in zip(e4["trips"], py_trips):
        assert c_t["pid"] == p_t["pid"]
        assert c_t["t"] == p_t["t"]
        assert c_t["t_open"] == p_t["t_open"]
        assert abs(c_t["gross_pct"] - p_t["gross_pct"]) < TOL
        assert abs(c_t["net_pct"] - p_t["net_pct"]) < TOL
        assert c_t["eras"] == p_t["eras"]
        assert c_t["stale_legs"] == p_t["stale_legs"]
        assert c_t["prestamp_legs"] == p_t["prestamp_legs"]

    # summary diffed against era4_section's own arithmetic on the same trips
    n = len(py_trips)
    g = sorted(t["gross_pct"] for t in py_trips)
    nt = sorted(t["net_pct"] for t in py_trips)
    assert abs(e4["gross_mean_pct"] - sum(g) / n) < TOL
    assert abs(e4["gross_median_pct"] - g[n // 2]) < TOL
    assert abs(e4["net_mean_pct"] - sum(nt) / n) < TOL
    assert abs(e4["net_median_pct"] - nt[n // 2]) < TOL
    assert e4["n_pos_gross"] == sum(1 for v in g if v > 0) == 2
    assert e4["tclose_min"] == min(t["t"] for t in py_trips)
    assert e4["tclose_max"] == max(t["t"] for t in py_trips)

    # the exec-era classification travelled through strip() correctly
    pa = e4["trips"][0]
    assert pa["eras"] == ["7-e7d5ca1a"] and pa["prestamp_legs"] == 0
    pe = e4["trips"][1]
    assert pe["eras"] == [] and pe["prestamp_legs"] == 2


def test_wilson_and_corpus_match_python_reference(diode_bin, fixture_dir):
    rep = _run(diode_bin, fixture_dir)
    lb = rep["labels"]
    assert lb["rows"] == 5
    assert lb["by_source"] == {"live": 3, "candidate": 2}
    assert lb["labeled"] == 4 and lb["wins"] == 2
    p, lo, hi = ce.wilson(lb["wins"], lb["labeled"])
    assert abs(lb["base_rate"] - 0.5) < TOL
    assert abs(lb["wilson"][0] - p) < TOL
    assert abs(lb["wilson"][1] - lo) < TOL
    assert abs(lb["wilson"][2] - hi) < TOL


def test_strict_ingest_counts_and_equity(diode_bin, fixture_dir):
    rep = _run(diode_bin, fixture_dir)
    ing = rep["ingest"]
    # fills reads in dictreader mode (the stale-binary law): short/long
    # rows KEPT and counted — 12 conforming + torn e2 + wide e3 + two
    # 16-col stale legs g2 = 16 kept, 3 short, 1 long
    assert ing["fills"] == {"present": True, "mode": "dictreader",
                            "rows": 16, "short_rows": 3, "long_rows": 1,
                            "quote_truncated": False}
    assert ing["equity"] == {"present": True, "mode": "strict", "rows": 4,
                             "dropped_short": 1, "dropped_long": 0,
                             "quote_truncated": False}
    assert ing["signal"] == {"present": True, "mode": "strict", "rows": 5,
                             "dropped_short": 0, "dropped_long": 0,
                             "quote_truncated": False}
    eq = rep["equity"]
    assert eq["rows"] == 4 and eq["valid"] == 3
    assert abs(eq["start"] - 800.0) < TOL
    assert abs(eq["end"] - 790.25) < TOL
    assert abs(eq["min"] - 790.25) < TOL
    assert abs(eq["max"] - 812.5) < TOL


def test_audit_counts(diode_bin, fixture_dir):
    rep = _run(diode_bin, fixture_dir)
    au = rep["ingest"]["audit"]
    assert au["present"] is True
    assert au["records"] == 6 and au["bad_lines"] == 1
    assert au["ts_min"] == 1786400001 and au["ts_max"] == 1786400006
    # count-desc then code-asc
    assert rep["audit_codes"] == {"OM-011": 3, "FW-070": 2, "SZ-001": 1}
    assert list(rep["audit_codes"]) == ["OM-011", "FW-070", "SZ-001"]
    assert rep["chain"] == "out-of-scope-v1"


def test_empty_outputs_dir_degrades_to_zeros(diode_bin, tmp_path):
    out = tmp_path / "empty"
    out.mkdir()
    rep = _run(diode_bin, out)
    assert rep["diode"] == "cpp" and rep["version"] == 1
    for name in ("equity", "signal"):
        assert rep["ingest"][name] == {"present": False, "mode": "strict",
                                       "rows": 0, "dropped_short": 0,
                                       "dropped_long": 0,
                                       "quote_truncated": False}
    assert rep["ingest"]["fills"] == {"present": False, "mode": "dictreader",
                                      "rows": 0, "short_rows": 0,
                                      "long_rows": 0,
                                      "quote_truncated": False}
    assert rep["ingest"]["audit"] == {"present": False, "records": 0,
                                      "bad_lines": 0}
    assert rep["era4"] == {"accrual_n": 0, "target": ce.ERA4_MIN_N,
                           "trips": []}
    assert rep["labels"]["rows"] == 0
    assert rep["labels"]["wilson"] == [0.0, 0.0, 0.0]
    assert rep["audit_codes"] == {}


def test_unreadable_outputs_dir_exits_2(diode_bin, tmp_path):
    proc = subprocess.run([str(diode_bin), str(tmp_path / "does-not-exist")],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    assert proc.stdout == ""


def test_skip_reason_names_both_compilers():
    # the reason string is what the Windows battery prints; it must say WHY
    assert "g++" in _SKIP_REASON and "clang++" in _SKIP_REASON


def test_unterminated_quote_sets_truncation_flag(diode_bin, tmp_path):
    """M2 (security review 2026-08-19): one stray quote swallows the file
    remainder into a single record - Python csv does the same, so the
    differential holds, but the collapse must be FLAGGED, never read as a
    clean short file. Injection-verified on Windows/WSL 2026-08-19
    (planted quote -> quote_truncated true, rows 1)."""
    o = tmp_path / "outputs"
    o.mkdir()
    (o / "fills.csv").write_text(
        "ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,"
        "attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,"
        "remaining,reason,exec_era\n"
        '1786900000,o1,pX,entry,ETH/USD,buy,limit,1,1,1.0,10.0,10.0,0.0,'
        '0.01,0.0,"swallows the rest\n'
        "1786903600,o2,pX,exit,ETH/USD,sell,limit,1,1,1.0,10.5,10.5,0.0,"
        "0.01,0.0,fill,7-e7d5ca1a\n",
        encoding="utf-8")
    rep = _run(diode_bin, o)
    f = rep["ingest"]["fills"]
    assert f["quote_truncated"] is True
    assert rep["era4"]["accrual_n"] == 0        # the trip never assembles
