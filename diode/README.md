# diode — C++ referee (placeholder)

`lb_diode.cpp` is the first compiled referee: an offline, SAFE-class analyst that reads an `outputs/` tree and prints one JSON report (era-4 trips, corpus, ledger scan); it feeds nothing back into any decision path. Build: `g++ -std=c++17 -O2 -Wall -Wextra -Werror -o lb_diode lb_diode.cpp`. (Full README — scope table, MSVC line, exclusions — is controller-authored, forthcoming.)

## Known v2 items

- `truncated_by_quote` counter: a single unterminated quote in a CSV
  collapses the file remainder into one record (Python csv behaves the
  same, so the differential holds) - v1 reports it as low row count, not
  loudly. Security review M2, 2026-08-19.
