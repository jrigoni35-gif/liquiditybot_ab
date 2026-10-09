---
title: Telemetry-Stack Audit (2026-08-05) — Taxonomy Strong, Dark Metrics, Probe-Admission Dominance, Log Skew
category: source
summary: "Report-only audit of the telemetry/event-tracking stack (analytics-tracking pass, measured by script): reason-code taxonomy is the strength (182 registered codes / 22 families, closed vocabulary at write, 36 distinct active in last 2k audit records); ~2 dozen metrics are emitted but on no Grafana board — including the hash chain's own health counters and the gate_divergence reward-misspecification watch; the probe-admission trio (SZ-047/SZ-051/SZ-049) is ~47% of the recent audit stream, corroborating the unshipped per-gate conversion instrument as the loudest untracked funnel stage; the log plane is 99.8% INFO with two namespaces at 73% of Loki volume; scorecard ≈80/100. Nothing changed — priorities filed as owed measurements. Methodology hazard found and filed: static regex over an f-string emitter produces phantom ghosts"
tags: [session, telemetry, observability, metrics, grafana, audit-trail, taxonomy]
sources: 2
updated: 2026-08-05
source_path: none — session work product (see Provenance)
source_date: 2026-08
authors: [claude]
ingested: 2026-08-05
---

# Telemetry-Stack Audit (2026-08-05)

## Provenance

Session work product — no `raw/` snapshot. An `/analytics-tracking` audit pass over the full
telemetry plane: `gc_pusher` (Prometheus metrics), `gc_log_pusher` (Loki logs),
`gc_trace_pusher` (OTLP traces), `status.json`, and the generated Grafana boards.
Ground truth is the measurement script (`telemetry_audit.py`, session scratchpad —
*"measure, don't recall"*), run 2026-08-05 21:05 UTC against `scripts/gc_pusher.py`,
`docs/grafana/*.json`, the last 8,000 `outputs/events.jsonl` lines, `core/codes.py`, and the
last 2,000 `outputs/audit.jsonl` records. **Report-only: no code, config, or board was
changed.**

**Filing history:** findings were measured 21:05 UTC; the same-session `/llm-wiki` filing was
**declined by the operator at 21:08 UTC** (held pending say-so) and **approved later the same
day** — this page is that approved filing. The wiki-is-truth rule
([[synthesis/governance-doctrine]] rule 12) was satisfied on operator cadence, not abandoned.

Five findings, then the scorecard.

---

## 1. TAXONOMY STRONG — the closed vocabulary is the stack's spine

**182 registered reason codes across 22 families** in `core/codes.py`
(FW 15 · PT 13 · VN 5 · OM 13 · SZ 24 · RP 10 · QT 1 · FV 2 · ML 30 · TP 3 · FT 3 · TH 11 ·
RT 1 · RC 2 · XV 18 · LT 1 · GL 6 · HG 1 · CG 2 · CV 7 · CX 4 · LB 11), closed vocabulary
enforced at write. **36 distinct codes active** in the last 2k audit records — the registry is
used, not decorative. This is the discipline half already established in
[[entities/reason-code-registry]]; the audit adds the measured size and live-usage numbers.

## 2. DARK METRICS — emitted, boarded nowhere

Raw scan: 112 metric names in the emitter vs 168 on boards, **36 emitted-but-on-no-board** —
of which ~a dozen are dynamic-name prefix artifacts (see finding 5), leaving **~2 dozen
genuinely dark**. The consequential ones:

- **`liquiditybot_audit_dropped_writes` + `liquiditybot_audit_tail_truncations`** — the hash
  chain's **own health counters have no visual alarm**. The audit trail is the provenance
  spine that convicted the fixture fills ([[concepts/default-path-fallback-writes]]); its
  failure counters going dark is the most consequential gap found.
- **`liquiditybot_gauges_dropped_nonfinite`** — telemetry self-health, undisplayed.
- **`liquiditybot_gate_divergence`** — the **reward-misspecification watch built in
  `07d38a51` — never displayed**. The realized-gates loop was proven working end-to-end on
  08-04 ([[synthesis/owed-measurements]] item 1b tripwire 1); its divergence alarm renders
  nowhere.
- **`liquiditybot_era_rows` / `era_reason_rows` / `era_excl_armed`** — the era-exclusion trio
  ([[concepts/era-exclusion]]), dark.
- Also dark: `bracket_divergence_n`, `longbook_context_aligned`, `code_count`, `command`.

Failure mode this enables (already seen once): an absent metric renders as an **empty panel
indistinguishable from zero** — the same class as the `slip_bps_notional_weighted` whitelist
gap ([[entities/observability-sidecars]]).

## 3. AUDIT-STREAM DOMINANCE — the exploration-admission machinery is the loudest voice

In the last 2k audit records: **SZ-047 probe-throttled 574 + SZ-051 probe-priced 260 +
SZ-049 probe-budget-exhausted 110 ≈ 47%** of the stream is exploration-admission machinery
(with ML-070 exploration entries at 255 beside them). Corroborated at full-trail scale by the
session digest's SD-004: SZ-047 alone is **86% of 25,988 non-routine records**.

This is not itself a defect — the probe throttle and budget are doing their jobs
([[concepts/probe-livelock]]) — but it **corroborates the still-unshipped per-gate conversion
instrument (`07d38a51`'s KNOWN GAP) as the loudest untracked funnel stage**: the stack records
every probe denial in detail while the gate→order conversion rate it implies is nowhere
measured.

## 4. LOG-PLANE SKEW — two namespaces are 73% of Loki volume

Last 8k events: **99.8% INFO** (7,985 INFO / 14 WARNING / 1 CRITICAL). Namespaces `regime`
(3,536) + `strategies` (2,304) = **73% of shipped volume**. Consequences: shipping cost and
query noise — a WARNING has to be found among 570x its own count. Candidate treatment:
demotion/sampling of the two chatty namespaces. (The 1 CRITICAL and low WARNING count are
themselves healthy signals; the skew is the issue, not the levels.)

## 5. METHODOLOGY HAZARD — phantom ghosts from static scans (finding about the audit itself)

The naive scan also reported **92 "displayed-but-not-emitted"** metrics and **16
"non-snake_case"** names. **Both sets are false positives**: `gc_pusher` builds metric names
in f-strings, so a static regex sees truncated prefixes (`liquiditybot_context_`,
`liquiditybot_gate_`, `liquiditybot_ml_`, …) and misses the constructed full names. The
repo's **own source-matching test is green (ghosts = 0)** and is the authority.

> ⚠️ **Citation hazard (filed in [[synthesis/open-contradictions-register]] and
> [[concepts/iron-law-of-debugging]]):** static metric-name scans over f-string emitters
> produce phantom ghosts. Never cite raw emitted/displayed set differences without resolving
> dynamic names; the dark-metrics list above was hand-adjudicated name-by-name.

## Scorecard ≈ 80/100

| Plane | Score | Basis |
|---|---|---|
| Taxonomy | 95 | 182 codes / 22 families, closed vocabulary, active use |
| Provenance / data quality | 90 | hash-chained audit + order_id crossref, post-quarantine week |
| Metrics | 75 | ~2 dozen dark, incl. audit-health pair and gate_divergence |
| Logs | 70 | 99.8% INFO, 73% of volume from two namespaces |
| Funnel coverage | 70 | gate→order conversion unmeasured (07d38a51 KNOWN GAP) |

## Priorities — filed as owed, not done

Filed as [[synthesis/owed-measurements]] items 26-28. In order: (a) board the audit-health
pair + `gauges_dropped_nonfinite` onto VITALS; (b) board `gate_divergence`; (c) ship the
per-gate conversion instrument; (d) log-volume diet for `regime`/`strategies`; (e) era trio
onto LEARNING BRAIN. All board changes go through the **board generator** — the JSON is
generated output, never hand-edited.

## Discharged the same evening (2026-08-05, commit `bc198aa5`) — (a) and (b) BOARDED

The operator-ordered boards redesign ([[sources/session-20260805-evening]]) gave
`problem_solution` an **AUDIT & TELEMETRY INTEGRITY row**: `audit_dropped_writes`,
`audit_tail_truncations` and `gauges_dropped_nonfinite` as **PROBLEM tiles**, and
**`gate_divergence` as a trend panel** — the `07d38a51` reward-misspecification watch is
**on screen for the first time**. Through the generator, UIDs unchanged. **Owed item 26 (a)+(b)
closed; (c), the era trio, remains open.** Priorities (c) the per-gate conversion instrument
[item 27] and (d) the log diet [item 28] are untouched.

Two follow-ons this audit earned the hard way, both recorded:

> **The fixture gap — the phantom-ghost lesson in reverse.** The synthetic status fixture
> **predated** the `gate_divergence` instrument, so `test_every_query_hits_an_emitted_metric`
> read the metric as **never emitted** and did not protect it. Finding 5 above describes a
> static scan **inventing** metrics that exist; this is a stale fixture **erasing** one that
> exists. Both are the same root error — **trusting a derived artifact over the source**.
> The fixture now carries the entry (and the later `haven` block was added to it at birth,
> commit `717b2e39`).

> **The new panel was wrong on arrival, and an adversarial pass caught it within one commit**
> (`46cdc19a`): the `gate_divergence` panel wrapped a **bare `max()`** while `gc_pusher` emits
> the metric **per gate with a `{gate}` label** — one gate trending to −0.4 while another sits
> at +0.05 plots the **+0.05 flatline**. The panel **hid exactly the sustained trend its own
> description tells the operator to watch for.** Fixed to `max by (gate)` with a `{{gate}}`
> legend, pinned by a test. **Boarding a dark metric is not the same as displaying it** — this
> audit's finding 2 should be read with that caveat attached.

The audit's other consequential dark metric now has a companion: `bc198aa5`'s desk keeps
geometry economics on the money board, where the **payoff-ratio tile carries its own 0.75
break-even threshold** instead of borrowing the profit-factor scale
([[concepts/payoff-asymmetry]]).

## Related

[[entities/observability-sidecars]] · [[entities/reason-code-registry]] ·
[[concepts/iron-law-of-debugging]] · [[concepts/probe-livelock]] ·
[[concepts/era-exclusion]] · [[synthesis/owed-measurements]] ·
[[sources/session-20260803-bug-sweep]] · [[sources/session-20260805-evening]] ·
[[synthesis/tangible-value-doctrine]]
