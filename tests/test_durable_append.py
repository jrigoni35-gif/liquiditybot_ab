"""Torn-append fusion: the shared heal, and the writers that now use it.

THE DEFECT. An append-mode writer killed mid-write (auto_update's
`taskkill /F`, power loss) leaves a final line with no trailing newline.
The next append concatenates onto that fragment, welding two records into
one malformed line - and the reader drops BOTH. One kill destroys the torn
record AND the next good one.

It was found and fixed twice in isolation (core/fill_ledger.py 2026-08-05,
ml/registry.py 2026-08-05) before a sweep on 2026-08-06 found the same
shape in seven more writers, including the 89-column training corpus and
the point-in-time macro history whose own contract makes a lost snapshot
permanently unrecoverable. Rather than a ninth copy of the same eight
lines, the heal now lives once in core/runtime.durable_append, beside
atomic_write_json - its whole-file sibling.

A SECOND, QUIETER DEFECT rode along with it: `new_file = not
path.exists()`. A kill in the create-to-first-flush window leaves a
ZERO-LENGTH file, which passes that test, so the header is never written
and csv.DictReader silently adopts the first DATA ROW as its column
names. Every consumer then misparses the whole file with no error at all.
Proven live on outputs/horizon_shadow.csv before this fix.
"""
import csv
import json

import pytest

from core.runtime import durable_append


def _torn(path, text: str) -> None:
    """Leave `text` on disk with NO trailing newline - a killed append."""
    path.write_bytes(text.encode("utf-8"))


# --- the helper itself -----------------------------------------------------
def test_size_zero_file_still_gets_its_header(tmp_path):
    """`not exists()` is not enough: a size-0 file must count as NEW."""
    p = tmp_path / "led.csv"
    p.touch()                                   # exists, zero length
    assert p.stat().st_size == 0
    durable_append(p, lambda f: csv.writer(f).writerow(["a", "b"]),
                   header="c1,c2\r\n")
    rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    assert list(rows[0].keys()) == ["c1", "c2"], \
        "DictReader adopted the DATA row as the header"
    assert rows[0]["c1"] == "a"


def test_torn_tail_is_isolated_not_fused(tmp_path):
    """The fragment becomes its own junk row; the new record stays whole."""
    p = tmp_path / "led.csv"
    _torn(p, "c1,c2\r\nGOOD,1\r\nTORN,")        # killed mid-row
    durable_append(p, lambda f: csv.writer(f).writerow(["NEW", "2"]))
    rows = list(csv.reader(open(p, newline="", encoding="utf-8")))
    flat = [",".join(r) for r in rows]
    assert not any("TORN,NEW" in s for s in flat), "records were FUSED"
    assert ["NEW", "2"] in rows, "the new record must survive intact"
    assert ["GOOD", "1"] in rows, "the previous good record is untouched"


def test_intact_tail_is_not_padded(tmp_path):
    """A file already ending in a newline gets no separator - otherwise
    every append would insert a blank row."""
    p = tmp_path / "led.csv"
    # write_bytes, not write_text: on Windows text mode translates \n to
    # \r\n, so a literal "\r\n" in the source becomes "\r\r\n" on disk and
    # csv.reader yields a blank row between every real one.
    p.write_bytes(b"c1,c2\r\nGOOD,1\r\n")
    durable_append(p, lambda f: csv.writer(f).writerow(["NEW", "2"]))
    rows = [r for r in csv.reader(open(p, newline="", encoding="utf-8"))]
    assert rows == [["c1", "c2"], ["GOOD", "1"], ["NEW", "2"]]


def test_jsonl_shape_heals_with_a_bare_newline(tmp_path):
    p = tmp_path / "led.jsonl"
    _torn(p, '{"seq": 1}\n{"seq": 2, "tr')
    line = json.dumps({"seq": 3}) + "\n"
    durable_append(p, lambda f: f.write(line), newline="\n", torn_sep="\n")
    good, bad = 0, 0
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            json.loads(ln)
            good += 1
        except json.JSONDecodeError:
            bad += 1
    assert good == 2, "seq 1 and seq 3 must both parse"
    assert bad == 1, "exactly the torn fragment stays unparseable"


def test_returns_false_and_never_raises_on_oserror(tmp_path):
    """Every call site is bookkeeping AFTER the trade already happened -
    a lost log row must never unwind it (CLAUDE.md invariant 5)."""
    p = tmp_path / "sub" / "led.csv"

    def _boom(_f):
        raise OSError("disk full")

    assert durable_append(p, _boom) is False


def test_file_ends_with_a_newline_after_every_append(tmp_path):
    """The invariant the next append depends on."""
    p = tmp_path / "led.csv"
    for i in range(5):
        durable_append(p, lambda f, i=i: csv.writer(f).writerow([i]),
                       header="n\r\n")
    assert p.read_bytes().endswith(b"\n")


# --- the writers that adopted it ------------------------------------------
def test_horizon_shadow_writes_its_header_to_a_size_zero_file(tmp_path):
    """The size-0 hole, proven live on outputs/horizon_shadow.csv: _ensure
    creates the header only under `not exists()`, and DictReader then read
    the first RESEARCH ROW as its column names."""
    from ml.history import HorizonShadowStore

    p = tmp_path / "horizon_shadow.csv"
    p.touch()
    store = HorizonShadowStore(str(p))
    store.append("cand-1", "BTC", "long", 432, 1, 1.5, "pt",
                 sigma_bar_frac=0.001, pt_frac=0.02, sl_frac=0.015)
    rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    assert list(rows[0].keys()) == HorizonShadowStore.HEADER
    assert rows[0]["candidate_id"] == "cand-1"


def test_horizon_shadow_does_not_fuse_two_research_rows(tmp_path):
    from ml.history import HorizonShadowStore

    p = tmp_path / "horizon_shadow.csv"
    hdr = ",".join(HorizonShadowStore.HEADER)
    _torn(p, f"{hdr}\r\ncand-GOOD,BTC,long,432,1,1.5,pt,1786000000,"
              f"0.001,0.02,0.015")
    HorizonShadowStore(str(p)).append(
        "cand-NEW", "ETH", "short", 432, 0, -1.0, "sl",
        sigma_bar_frac=0.001, pt_frac=0.02, sl_frac=0.015)
    ids = [r[0] for r in csv.reader(open(p, newline="", encoding="utf-8"))]
    assert "cand-NEW" in ids, "the new row must not be welded to the torn one"
    assert not any("0.015cand-NEW" in c
                   for r in csv.reader(open(p, newline="", encoding="utf-8"))
                   for c in r), "fields fused across the record boundary"


def test_corpus_append_does_not_fuse_two_labelled_rows(tmp_path):
    """signal_history.csv is the ground-truth training corpus: a fused row
    destroys TWO labelled outcomes and their 64-feature vectors, and
    load_training_data drops the chimera with no counter."""
    import numpy as np

    from ml.features import FEATURE_NAMES
    from ml.history import HistoryStore

    p = tmp_path / "signal_history.csv"
    store = HistoryStore(str(p))
    feats = np.zeros(len(FEATURE_NAMES), dtype=float)
    store._append_row("POS-AAA", "BTC", "long", feats, 1, 1.0, "live")
    # simulate the kill: strip the trailing newline mid-row
    raw = p.read_bytes()
    p.write_bytes(raw[:-12])
    store._append_row("POS-BBB", "ETH", "long", feats, 0, -1.0, "live")
    widths = [len(r) for r in csv.reader(open(p, newline="",
                                              encoding="utf-8"))]
    assert widths.count(len(store._header)) >= 2, \
        "the header and the new row must both be full width"
    ids = [r[0] for r in csv.reader(open(p, newline="", encoding="utf-8"))]
    assert "POS-BBB" in ids, "the new label was fused into the torn fragment"


# --- the schema-shape constants -------------------------------------------
def test_row_shape_constants_match_the_live_header(tmp_path):
    """_N_LEAD/_N_TRAIL feed BOTH the width guard and the message it
    prints. They were two independent literals (a correct 22 and a stale
    20) and the message reported a phantom 69-column schema against a true
    64. Derived from one source, they cannot drift apart again."""
    from ml.features import FEATURE_NAMES
    from ml.history import _N_LEAD, _N_TRAIL, HistoryStore

    hdr = HistoryStore(str(tmp_path / "h.csv"))._header
    assert _N_LEAD + len(FEATURE_NAMES) + _N_TRAIL == len(hdr)
    assert len(hdr) - _N_LEAD - _N_TRAIL == len(FEATURE_NAMES)


@pytest.mark.parametrize("n_bad", [1, 5])
def test_width_guard_refuses_a_stale_feature_vector(tmp_path, n_bad):
    import numpy as np

    from ml.features import FEATURE_NAMES
    from ml.history import HistoryStore

    p = tmp_path / "h.csv"
    store = HistoryStore(str(p))
    short = np.zeros(len(FEATURE_NAMES) - n_bad, dtype=float)
    store._append_row("POS-X", "BTC", "long", short, 1, 1.0, "live")
    rows = list(csv.reader(open(p, newline="", encoding="utf-8")))
    assert len(rows) == 1, "a misaligned row must never be appended"
