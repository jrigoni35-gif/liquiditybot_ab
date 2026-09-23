# Operator Page — one page that tells the correct thing (design)

Date: 2026-09-22
Status: APPROVED by operator 2026-09-22 19:48 ("I approve", after choosing
"B with A folded in" — one operator page, board renders folded in).
Moratorium compliance: SAFE class — read-only measurement/report tooling
over `outputs/` files and the Grafana Cloud render API. No engine imports,
no engine writes, no cloud writes, no decisioning contact. EXEC_ERA
`12-10d4d0c2` unchanged.

## 1. Origin

The Grafana boards work but are a hassle: cloud login, one retired nav
anchor, tiles that read "window filling" without a number, a trading board
invisible to folder search, and a local instance blocked on a
metrics:read token. Operator directive: "when I'm looking at it, it tells
me the correct thing" — seamless, truthful at a glance.

## 2. What it is

`scripts/operator_page.py` — single script, stdlib + repo-local files only.

- **Serve mode (default):** stdlib `http.server` on `127.0.0.1:8787`
  (localhost only), opens the browser once at start. The page JS polls
  `/state` every 30 s; the server rebuilds the state JSON per poll from
  the sources below. No framework, no build step, no dependencies.
- **`--once` mode:** writes a static HTML snapshot with the state baked in
  (for records/handoffs/zips).

## 3. Page layout (one screen, dark, desk-style)

1. **Posture strip** — runner state, PAPER/LIVE, armed/halted, entries
   open/blocked, active fault. Source: `outputs/status.json` (runner's own
   write; carries `ts`).
2. **Money row** — equity, today / week / month PnL, savings, reserve.
   Equity requires agreement between `status.json` and the `equity.csv`
   tail within tolerance **$0.01** (same quantity written twice; cents
   rounding only); disagreement renders **MISMATCH**, never a
   picked winner.
3. **Positions table** — from `outputs/state.json` `portfolio`: symbol,
   side, notional, age. Fields the file does not carry are not shown
   (no fabricated marks or uP&L).
4. **Judge / learning row** — judge scoring-window progress, drift share,
   model-in-use. Sources: `outputs/session_digest.json` and
   `outputs/monitor/` artifacts where present; else NO SOURCE.
5. **Era row** — era stamp, days into era-9 vs the 14-day floor, n toward
   the registered n=50 read point. Source: `outputs/boundary_payload.json`
   (Lane C), age-stamped; refreshed by re-running the payload, not by this
   page recomputing it.
6. **Board strip (A folded in)** — the four dashboard PNGs rendered via
   the Grafana Cloud render API with the SA token
   (`~/.liquiditybot/grafana-sa-token`, read, never printed). Rendered on
   a slower cadence (default 5 min) into `outputs/boards/`; each image
   captioned with its render time. Render failure → last cached PNG + red
   age badge; never a blank frame.

## 4. The correctness contract (the reason this exists)

- Every tile carries `source`, `as_of`, `age_s`.
- **STALE:** age > 2× the source's expected cadence → tile flips red
  STALE, value greyed. An old number is never shown as if current.
- **NO SOURCE:** source file absent/unreadable → explicit NO SOURCE
  state, never 0, never a placeholder number.
- **MISMATCH:** two sources for the same quantity disagree beyond
  tolerance → MISMATCH state; the page never silently arbitrates.
- An all-STALE page still renders. A page full of red badges is a
  truthful page.

## 5. Error handling and failure shape

- Every source read is isolated: one unreadable file degrades its own
  tiles only (STALE/NO SOURCE), never the page.
- The server never writes outside `outputs/boards/` (render cache) and
  the `--once` snapshot path.
- Render API failures are caught per board; the SA token is read from
  disk per render cycle (no env persistence).

## 6. Testing

`tests/test_operator_page.py` — synthetic fixtures in tmp_path:
- tile builder per source: fresh → ok; aged → STALE; absent → NO SOURCE.
- equity agreement: matching sources → value; diverging → MISMATCH.
- state assembly never raises on empty/garbage inputs (all-STALE page).
- `--once` produces parseable HTML with the state JSON embedded.
- No network in tests: the render fetch is injected/faked; real API is
  exercised only by a manual live run, not the suite.

## 7. Out of scope (explicit)

Editing the cloud dashboards; alert rules; the runner; any engine module;
a metrics:read token for the local Grafana instance (optional, parked);
promoting the page beyond localhost.

## 8. Definition of done

Scoped battery on the touched files (foreign in-flight diff in the tree
makes a full-matrix claim unowned): pytest for the new test file +
adjacent suites (test_code_registry, test_dependency_hygiene), ruff,
bandit, compileall — plus a live `--once` run and a live serve smoke
against real `outputs/`, verified by opening the produced page.
