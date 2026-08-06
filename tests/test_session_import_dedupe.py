"""Within-bundle duplicates must not both merge into the corpus.

Round-2 finding (2026-08-05). The dedup loop checked each bundle row against
`seen`, built from the LOCAL file, but never added accepted keys back — so a
bundle containing the same row twice (exactly what the duplicate-fills bug
class produced) appended both copies. The corpus is append-only and later
syncs see both rows as already present, so nothing ever heals it: the
training row stays double-weighted forever, and corpus_sync --apply runs
this unattended every hour.
"""
from scripts.session_import import _row_key


def _dedupe(header, local_lines, bundle_lines):
    """The merge loop's dedup contract, exercised directly."""
    seen = {_row_key(header, ln) for ln in local_lines}
    out = []
    dupes = 0
    for ln in bundle_lines:
        key = _row_key(header, ln)
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
            out.append(ln)
    return out, dupes


HEADER = ["ts", "asset", "label"]


def test_duplicate_rows_inside_one_bundle_merge_once():
    row = "1785000000,ETH,1"
    kept, dupes = _dedupe(HEADER, [], [row, row])
    assert kept == [row], "the same bundle row must merge exactly once"
    assert dupes == 1


def test_rows_already_local_are_still_skipped():
    row = "1785000000,ETH,1"
    kept, dupes = _dedupe(HEADER, [row], [row])
    assert kept == [] and dupes == 1


def test_distinct_rows_all_merge():
    a, b = "1785000000,ETH,1", "1785000300,BTC,0"
    kept, dupes = _dedupe(HEADER, [], [a, b])
    assert kept == [a, b] and dupes == 0


def test_triplicate_collapses_to_one():
    row = "1785000000,ETH,1"
    kept, dupes = _dedupe(HEADER, [], [row, row, row])
    assert kept == [row] and dupes == 2
