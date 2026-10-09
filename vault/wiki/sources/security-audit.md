---
title: Security Audit
category: source
summary: Bandit, pip-audit and manual trust-boundary audit reporting zero static-analysis issues with five fixed findings, framed by the insight that the attack surface is inbound data not inbound connections
tags: [security, sanitize, trust-boundary]
sources: 1
updated: 2026-08-01
---

# Security Audit

**Raw source:** `raw/architecture/SECURITY_AUDIT.md`

## Threat model
**The attack surface is untrusted inbound *data*, not inbound connections.** The bot opens no
listening sockets and exposes no network service.

Three surfaces ranked: (1) external web feeds — primary risk; (2) **exchange REST responses — highest
consequence**, because prices and books feed execution; (3) local files — **trusted**, since anyone who
can write them already owns the machine.

## Five findings, all fixed
- **HIGH — non-finite number injection.** Python's `json` accepts `NaN`/`Infinity` by default; a single
  `NaN` poisons every downstream comparison (all comparisons return False) and `Infinity` blows out
  position sizing. PoC injected `inf` into dominance and `NaN` into a sentiment value. Fixed with
  `loads_bounded()` (rejects non-finite tokens) and `safe_float()`.
- **HIGH — poisoned books/candles reaching execution.** `clean_book()`/`clean_candles()` now drop
  non-finite/non-positive levels, cap level counts, and reject crossed or empty books.
- **MEDIUM — XML entity-expansion DoS** ("billion laughs") in RSS parsing -> `defusedxml`, pinned.
- **LOW — response-size exhaustion** -> 5 MB cap before parsing.
- **LOW — `assert` in a hot path** (stripped under `python -O`) -> explicit `raise`.
- **LOW — bare `try/except/pass`** -> now logs at debug.

## Standing invariants
Zero `eval`, `exec`, `pickle`, `yaml.load`, `os.system`, `subprocess`, or `shell=True`. TLS never
disabled; all HTTP calls have timeouts. Secrets never logged (grep-verified). **Withdrawals impossible
at the code level** — deny list checked *before any network call*. Live trading gated by typed
`ARM LIVE`; `live_armed` deliberately **not persisted**, so every restart comes up disarmed. Nonce
monotonic against a backward clock step. The UI cannot block the engine (atomic files only).

## Structural control
**Filter-only clamping as a security control** — sentiment feeds are structurally incapable of
triggering, sizing, or flipping a trade, which is also the mitigation for the fact that **feed
authenticity cannot be verified beyond TLS**.

## Stale claims
The "153/153 tests passing" count and the "no subprocess anywhere" claim are both superseded — the ops
sidecars post-date this audit and do shell out. See [[synthesis/documentation-drift-register]].

## Related
[[entities/read-only-venues]] · [[entities/kraken]] · [[concepts/assurance-spine]]
