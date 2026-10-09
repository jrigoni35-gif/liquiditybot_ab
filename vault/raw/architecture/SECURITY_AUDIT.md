# Security audit — liquiditybot v2

Audit performed with automated tooling (bandit static analysis,
pip-audit dependency scanning) plus a manual threat-model review of
every trust boundary. Result: **0 bandit issues at any severity, 0
known dependency vulnerabilities, 153/153 tests passing** including a
dedicated 30-check security suite (test 23).

## Threat model

This bot's attack surface is **untrusted inbound data**, not inbound
connections — it opens no listening sockets and exposes no network
service. The dashboard talks to the engine only through local files.
The surfaces that matter:

1. **External web feeds** (Google News RSS, CoinGecko, alternative.me
   Fear&Greed, Reddit) — third-party endpoints you don't control. A
   compromised, spoofed (DNS/MITM), or merely buggy response is the
   primary risk.
2. **Exchange REST responses** (OKX, Binance.US data; Kraken data +
   private) — highest *consequence* because prices/books feed execution.
3. **Local files** (config, snapshots, control commands) — trusted;
   anyone who can write them already owns the machine.

## Findings & fixes

### HIGH — non-finite number injection (FIXED)

Python's `json` module accepts `NaN`, `Infinity`, `-Infinity` by
default. A single `NaN` poisons every downstream comparison (all
comparisons return False, corrupting regime/risk logic); `Infinity`
blows out position sizing. Proof-of-concept during the audit put `inf`
into `btc_dominance` and `NaN` into the Fear&Greed value from poisoned
responses.
**Fix:** `core/sanitize.py`. `loads_bounded()` parses JSON with
`parse_constant` set to reject the non-finite tokens outright.
`safe_float()` coerces every externally-sourced number to a *finite*
float or a safe default, with optional domain clamps. Every feed's
numeric parsing now routes through it. Verified: poisoned webdata falls
back to 50.0 / 0.0, never NaN/Inf.

### HIGH — poisoned order books / candles reaching execution (FIXED)

A malicious or corrupt order book with a `NaN`, negative, or `Infinity`
price would flow straight into fair value, the Avellaneda-Stoikov
quoter, and stop-loss math.
**Fix:** `clean_book()` and `clean_candles()` drop any level/row whose
price or size isn't finite and positive, cap level counts, and reject
crossed or empty books (returns `None`, treated as "no data"). Applied
across all three exchange feeds (OKX, Binance.US, Kraken) including the
execution-critical `get_ticker_price` and `get_order_book`.

### MEDIUM — XML entity-expansion DoS (FIXED)

RSS feeds were parsed with stdlib `ElementTree`, vulnerable to the
"billion laughs" entity-expansion attack from a hostile feed.
**Fix:** parsing now uses `defusedxml` (pinned as a hard requirement),
which disables entity expansion and external-entity resolution.
Verified: an entity bomb is rejected at parse time
(`EntitiesForbidden`). A guarded stdlib fallback exists only for a
broken install and is annotated `# nosec`.

### LOW — response-size exhaustion (FIXED)

No bound on response body size before parsing.
**Fix:** 5 MB cap on all JSON/XML/text responses (`loads_bounded`,
`safe_rss_root`, `cap_text`) before parsing.

### LOW — assert in a hot path (FIXED)

`ml/features.py` used `assert` to check feature-vector length; asserts
are stripped under `python -O`, silently disabling the check.
**Fix:** replaced with an explicit `raise ValueError`.

### LOW — bare `try/except/pass` (FIXED)

Three swallow-everything blocks (moomoo cleanup, runner shutdown) could
hide errors.
**Fix:** all now log at debug; the two genuinely best-effort
context-close calls are annotated `# nosec B110` with rationale.

## Verified already-correct (no change needed)

- **No dangerous constructs:** zero `eval`, `exec`, `pickle`,
  `yaml.load`, `os.system`, `subprocess`, or `shell=True` anywhere.
- **TLS never disabled:** no `verify=False`; all HTTP calls have
  timeouts.
- **Secrets never logged:** the Kraken API secret and HMAC signature
  appear in no log or print statement. Grep-verified.
- **HMAC signing correct:** Kraken private-request signing follows the
  documented scheme (nonce + SHA256 + HMAC-SHA512 over the API secret).
- **Withdrawals impossible at the code level:** `Withdraw`,
  `WithdrawInfo`, `WalletTransfer`, `WithdrawAddresses`, and related
  endpoints are on a hard deny list checked *before any network call*
  in `_private_post`. Re-asserted by tests.
- **Live trading gated:** real orders require the operator to type
  `ARM LIVE`; `live_armed` is deliberately NOT persisted, so every
  restart comes up disarmed.
- **Nonce monotonic:** a backward NTP clock step cannot emit a
  decreasing nonce (guards against `EAPI:Invalid nonce`).
- **UI cannot block the engine:** dashboard and engine share only
  atomic files; no shared process, no locks.

## Residual risks (operational, not code)

- **API-key hygiene is yours:** create the Kraken key with trade +
  query rights only, **no withdrawal permission**, as defense in depth
  behind the deny list. Never commit keys; they live in config.json
  which should never enter version control.
- **Feed authenticity:** the bot validates the *shape and sanity* of
  feed data but cannot verify a remote is genuine beyond TLS. Sentiment
  and web-context feeds are filter-only and clamped, so even a fully
  hostile sentiment source can at most nudge risk within bounded limits
  — it can never trigger, size, or flip a trade.
- **Host security:** anyone who can write `outputs/control/` can send
  commands, and anyone who can edit config.json controls the bot. Run
  it on a machine you control; the control channel is not authenticated
  because it is a local-trust boundary by design.
- **Dependency drift:** re-run `pip-audit -r requirements.txt`
  periodically; new CVEs appear over time.

## Re-running the audit

```bash
pip install bandit pip-audit defusedxml
bandit -r . -x ./scripts/smoke_test.py        # expect: 0 issues
pip-audit -r requirements.txt                 # expect: no vulnerabilities
python scripts/smoke_test.py                  # expect: passed 153, failed 0
```
