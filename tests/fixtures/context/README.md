# Context source fixtures (Task B2)

Real, verbatim fetches — every non-`*_malformed`/`*_no_bitcoin` file below is
byte-for-byte what the endpoint returned (through this container's transparent
proxy), never fabricated. Malformed variants are hand-crafted from that real
data (or a hand-written HTTP error page) to exercise the "never raise, return
None" contract.

## Real fetches

| file | source | fetched with |
| --- | --- | --- |
| `fred_dff.csv` | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF` | `curl -sS <url> -o fred_dff.csv` |
| `fred_t10y2y.csv` | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y` | same pattern |
| `fred_vixcls.csv` | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS` | same pattern |
| `stablecoins.json` | `https://stablecoins.llama.fi/stablecoins?includePrices=false` | same pattern |
| `cot_finfut.txt` | `https://www.cftc.gov/dea/newcot/FinFutWk.txt` | same pattern |

All fetched 2026-07-24, HTTP 200. `stablecoins.json` is 537,134 bytes — well
under the 2MB cap in the brief, so it ships **untruncated** (no truncation
was necessary; noting it per the brief's instruction to say so either way).

The FRED files' real header is `observation_date,<ID>` (not the `DATE,<ID>`
the interface doc names as the general format) — the parser does not depend
on the header's literal text, only on skipping row 0.

`cot_finfut.txt` is the CFTC "Traders in Financial Futures — Futures Only"
short/headerless format (dea/newcot). Column positions (`Lev_Money_
Positions_Long_All` at index 14, `_Short_All` at index 15, 0-indexed,
87 fields/row) were verified against the real fixture by cross-referencing
the column-identical, header-carrying annual equivalent report
(`https://www.cftc.gov/files/dea/history/fut_fin_txt_2025.zip`, member
`FinFutYY.txt`) — same field count (87), same field order confirmed by
aligning date/exchange-code fields across several distinct market rows
(BITCOIN, MICRO BITCOIN, NANO BITCOIN, BITCOIN CASH). See
`.superpowers/sdd/task-B2-report.md` for the full verification transcript.
The first "BITCOIN" + "CHICAGO MERCANTILE" row in the real fixture is line 69
(`BITCOIN - CHICAGO MERCANTILE EXCHANGE`, the standard 5-BTC contract, not
the MICRO variant that follows it).

## Crafted malformed / edge variants

- `fred_malformed_empty.csv` — empty file.
- `fred_malformed_truncated.csv` — header line only, cut off mid-token
  (`observation_date,DF`), no complete data row survives.
- `fred_malformed_html.csv` — hand-written HTML 404 page (no commas in any
  line, so nothing numeric-parseable survives).
- `stablecoins_malformed_empty.json` — empty file.
- `stablecoins_malformed_truncated.json` — first 500 bytes of the real
  fetch, confirmed invalid JSON (`json.loads` raises `Unterminated string`).
- `stablecoins_malformed_html.json` — hand-written HTML 503 page.
- `cot_malformed_empty.txt` — empty file.
- `cot_malformed_truncated.txt` — first 60 bytes of the real fetch (one
  partial non-BTC row, no BITCOIN match survives).
- `cot_malformed_html.txt` — hand-written HTML 500 page.
- `cot_no_bitcoin.txt` — real, complete first 5 rows of the real fetch
  (CAD/CHF/GBP/JPY/EUR futures), none of which mention BITCOIN — exercises
  the "no BTC row found" -> None path with genuine (not fabricated) data.
