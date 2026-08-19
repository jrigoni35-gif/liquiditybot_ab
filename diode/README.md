# diode — C++ referee (placeholder)

`lb_diode.cpp` is the first compiled referee: an offline, SAFE-class analyst that reads an `outputs/` tree and prints one JSON report (era-4 trips, corpus, ledger scan); it feeds nothing back into any decision path. Build: `g++ -std=c++17 -O2 -Wall -Wextra -Werror -o lb_diode lb_diode.cpp`. (Full README — scope table, MSVC line, exclusions — is controller-authored, forthcoming.)

## Known v2 items

- `truncated_by_quote` counter: a single unterminated quote in a CSV
  collapses the file remainder into one record (Python csv behaves the
  same, so the differential holds) - v1 reports it as low row count, not
  loudly. Security review M2, 2026-08-19.

## v1.1 (2026-08-19): fills reads in DictReader mode

The lattice's FIRST real-data differential caught v1 undercounting the
era-4 accrual 16 vs 21: fills.csv legitimately contains 16-column rows
written by a pre-exec_era binary (the stale-binary law), which Python's
csv.DictReader keeps with the missing field as None — the exact
absent-vs-blank distinction cohort_eval's era classification keys on.
v1's strict drop-short rule was stricter than the pre-registered
reference; the referee must match, never improve. fills now mirrors
DictReader (short/long rows kept + counted as short_rows/long_rows);
equity/signal keep strict ingest, whose Python reference (the digest's
drop-malformed law) drops. Verified: full 21-trip agreement with the PC
telemetry and the Python reference at 1e-9, per-trip, era stamps and
stale-leg counts included.
