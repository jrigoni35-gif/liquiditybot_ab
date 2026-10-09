---
title: The Reason-Code Registry
category: entity
summary: "An append-only registry where every reject, clamp, fault and deploy carries a registered code, forming the system's intent record — 193 codes as of 2026-08-10 evening (OM-085 the fills-ledger replay guard, RP-072 the goal-ladder ratchet). 2026-08-10 found a code IN CIRCULATION that the registry never heard of: XV-023 is cited by config.json, core/fill_calibration.py and this vault, but core/codes.py stops at XV-022 — a code born in a docstring and propagated by citation has every appearance of registration and none of the guarantee, and it REMAINS unregistered at the head that added the other two. A code is registered when codes.py says so, not when a docstring uses it"
tags: [module, assurance, audit]
sources: 15
updated: 2026-08-10
---

# The Reason-Code Registry

An append-only registry of coded dispositions. **Every reject, clamp, fault and deploy carries one** —
"new behavior = new registered code, never a bare string."

## Families seen in the corpus
`FW-` firewall · `PT-` profit taking / pretrade · `QT-` quoting · `FV-` fair value · `SZ-` sizing ·
`OM-` order management · `ML-` machine learning · `TH-` THALES · `RP-` risk protocol ·
`LB-` long book · `XV-` cost/verification · `DF-` data feed (born 2026-08-08) ·
`SD-`, `IF-`, `TX-`, `SYS-`, `CG-`, `WD-`

## Measured size and live usage (2026-08-05 telemetry audit)
Scanned from `core/codes.py` ([[sources/telemetry-stack-audit]]): **182 registered codes
across 22 families** (FW 15 · PT 13 · VN 5 · OM 13 · SZ 24 · RP 10 · QT 1 · FV 2 · ML 30 ·
TP 3 · FT 3 · TH 11 · RT 1 · RC 2 · XV 18 · LT 1 · GL 6 · HG 1 · CG 2 · CV 7 · CX 4 · LB 11),
closed vocabulary enforced at write. **36 distinct codes active** in the last 2k audit
records — used, not decorative. The audit scored the taxonomy **95/100**, the strongest plane
of the telemetry stack.

**Dominance finding:** the exploration-admission trio — SZ-047 probe-throttled (574) +
SZ-051 probe-priced (260) + SZ-049 budget-exhausted (110) — is **≈47% of the last 2k audit
records** (SD-004 corroborates at full-trail scale: SZ-047 alone is 86% of 25,988 non-routine
records). Working as designed ([[concepts/probe-livelock]]), but it corroborates the
unshipped **per-gate conversion instrument** (`07d38a51`'s KNOWN GAP) as the loudest
untracked funnel stage — owed item 27.

## Newest codes: OM-085 / RP-072 (2026-08-10 evening) — 191 → 193

**Verified by scan of `core/codes.py` at the stressor-session filing: 193 registered codes.**

`OM-085` (`OM_LEDGER_DUP_REFUSED`, `core/codes.py:116`, commit `6fe6d98d`) — the fills-ledger
**restart-replay guard** refused a row whose `(order_id, fill_size, fill_price, remaining)`
already exists; the write-path defense the readers' dedupe never had (owed 62, registered and
shipped same day — [[sources/session-20260810-stressor-epoch]] §2).

`RP-072` (`RP_GOAL_ESCALATED`, `core/codes.py:233`, commit `38751d5b`) — the **goal ladder
ratcheted**: a month closed at ≥100% of its effective goal, mult ×1.5. AST-pinned to follow
`RP_MONTH_CLOSED` (RP-071) in `_close_periods` so a closed month is judged by the bar it ran
under; the RP-071-without-RP-072 signature is the **detector for owed 64** (the escalation-loss
crash window).

**`XV-023` remains UNREGISTERED at the same head** — the 2026-08-10 finding below is unchanged
by a session that added two codes while the one in circulation still is not in `codes.py`.

## DF-020 / DF-021 (2026-08-08 evening, commit `64724480`) — 189 → 191

`DF-020` / `DF-021` — **latched, once-per-episode transition codes registered with owed
41b's availability work** (the same episode discipline as DF-010/DF-011 and FW-080:
transitions, not spam). Shipped in the commit that records context-feed availability on
every corpus row (`avail_web`/`avail_equity`/`avail_options`/`quotes_frozen`, `""` =
UNKNOWN ≠ `"0"` = measured down) and puts `quotes_frozen` in the runner status moomoo
block ([[sources/session-20260808-evening-availability-persistence]] §1). Second pair of
the DF- family, born one commit-day after its first.

## DF-010 / DF-011 (2026-08-08, commit `01d59908`) — 187 → 189
**Verified by scan of `core/codes.py` at the afternoon filing: 189 registered codes.**

`DF-010` (`DF_QUOTES_FROZEN`, `core/codes.py:464`) / `DF-011` (`DF_QUOTES_RESUMED`, `:476`)
— **the moomoo basket froze (every per-ticker return identical to the previous poll: the
closed-market signature) / the basket is moving again.** Born from the input-feed audit's
#1 CRITICAL ([[sources/session-20260808-battery-split-freeze-gate]] §2, owed 41a): frozen
closed-market quotes were re-appended to the z window every poll, decaying z +0.39 → 0.00
by repetition. **Latched — one DF-010 per freeze episode, DF-011 on resume** — the same
episode discipline as FW-080, so a ~62h weekend freeze is two log lines, not 750. First
codes of the **DF- (data feed) family**. Until `quotes_frozen` reaches `status.json` (rides
with owed 41b), these transitions are the *only* operator-visible evidence of a freeze
episode — detection codes carrying visibility, exactly the registry's earn-their-keep
pattern (cf. ML-084). *(Discharged same day evening: 41b `64724480` landed
`quotes_frozen` in the runner status moomoo block — the status field now exists, and the
same truth is recorded on every corpus row.)*

## RP-042 (2026-08-08, commit `f07d60f8`) — 186 → 187

`RP-042` (`RP_BUDGET_REANCHORED`, `core/codes.py:221`) — **an operator re-anchored a loss
budget: audited override for bug-attributable consumption, reason required**. Born from the
weekly-budget lockout of 2026-08-08: the ADA hedge-churn class's ~$303 of simulated W32 fees
drove `weekly_budget_used_frac` to 1.09 and `taper_mult` to 0.0 **days after the churn itself
was fixed** — the budget anchors on persisted equity, so no restart clears it
([[sources/session-20260808-budget-reanchor]]). The verb `budget_reanchor_week` **refuses to
run without a reason**, and the RP-042 audit record carries **equity AND the full reason** in
the hash chain — first use is `audit.jsonl` seq 37983, whose reason names the bug, its three
fixes, and the attribution. The registry's rule applied to an *operator override*: the most
dangerous class of action (loosening a protective posture by hand) is exactly the one that
must be a registered code with a mandatory explanation, never a state-file edit. Sibling
codes: RP-040 taper active · RP-041 budget spent. Deliberately **absent from the REST
surface** — auditability is not reachability.

## FW-080 (2026-08-07 night, commit `915b362f`) — 185 → 186

`FW-080` (`FW_STALE_BARS`, `core/codes.py:51`) — **venue bars accepted into the view whose LAST
bar timestamp lags the engine clock**. Born from the latency audit's finding that fetch age
proved the *call* was recent, never the *data*: nothing anywhere validated
`candles[-1]['time']`. Warns **once per stale episode per asset** (latched, re-armed on
recovery) when the last committed bar lags **>1200s** (4 five-minute bars — thin pairs
legitimately gap). **Detection only** — the veto-grade response is consciously sequenced with
the staleness-veto resurrection ([[synthesis/owed-measurements]] item 42a), never bolted on.
Proven quiet on the live box the same night ([[sources/session-20260807-closing-batch]]).
*Namespace note recorded at the same filing:* `REST-004` (the 413 declared-body-too-large
refusal added by `1e7f882c`) lives in the REST server's **log namespace** beside
REST-002/003 — not in `core/codes.py`; the registry count is unaffected by it.

## FW-070 (2026-08-07, commit `cf454d5e`) — 184 → 185

`FW-070` (`FW_HEDGE_CHURN_LATCH`) — **≥ N hedge unwinds of one asset inside the window: re-hedging
frozen**. Opens only, auto-releases on window-elapsed + estimator-warm; born from the 2026-08-07
ADA churn (−$318 in 147 laps, [[sources/session-20260807-hedge-churn-guards]]). The HANDOFF's fix
spec demanded exactly this form: *"new registered FW-* fault code (core/codes.py, never a bare
string)"* — the registry's rule applied mid-incident. Two honesty notes travel with it:
**(1)** the latch currently emits only `log.warning` — no gauge, no board tile (owed item 35b;
task #148, the >2-unwinds/hour class alarm, is owned by the cloud session); **(2)** a stale
comment in `execution/hedging.py:75` annotates the latch dict "(FW-060)" — that is
`FW_NO_REFERENCE`; trust the registry, not the comment
([[synthesis/documentation-drift-register]]).

## ML-084 (2026-08-06, commit `ee0ac4ad`) — 183 → 184

`ML-084` (`ML_UNLABELED_CLOSE`) marks **a position that closed with NO pending feature vector**,
so **no training row was written**. Until this commit, `HistoryStore.log_close`'s
`if entry is None: return` was **the one exit in the entire corpus write path with no log line and
no counter** — which made **ground-truth attrition structurally invisible**
([[entities/historystore]]).

> **The code exists because of what its absence cost.** Resolving a suspected **10.9% hole** in
> the ground-truth sample on 2026-08-06 required **forensic reconstruction from `fills.csv`**,
> because the corpus emitted no signal of its own. It turned out to be **34 quarantined QA fills
> plus 3 legitimate `FEATURE_SCHEMA_VERSION` drops** — i.e. **nothing was wrong, and establishing
> that took hours.** The registry's rule earns its keep on the *null* result as much as on the
> positive one: an instrument that can cheaply prove nothing is wrong is worth as much as one that
> detects that something is.

Deliberately **a counter, not an alarm** — a `FEATURE_SCHEMA_VERSION` bump *legitimately* drops
pending vectors (`core/persistence.py`) — **but it must be VISIBLE**. Report-only: the close
itself is unaffected. ([[sources/session-20260806-geometry-filing]])

## OM-090 (2026-08-05 evening, commit `f3253f0d`) — 182 → 183
`OM-090` marks a **cancel whose venue confirmation never arrived**. Kraken orders carry no
`expiretm` and `feed._private_post` **returns `None` rather than raising** on a rate limit, 5xx or
error payload; both cancel paths discarded that result and forced local state terminal, leaving a
**live GTC order resting at the venue with no local record** ([[sources/session-20260805-evening]],
R2-3). The fix keeps the terminal transition — *a blocked escape is the worse failure* — and makes
the residue **audible** instead: OM-090 plus a `cancel_unconfirmed` counter in the status readout
plus a **hash-chained audit record** naming txid, path, symbol and remaining. Dry-run posts
nothing, so it never flags.

> **A textbook application of the registry's own rule.** The behavior could not be silently
> absorbed into an existing disposition or logged as a bare string: **new behavior = new
> registered code**. The resulting record is the difference between an operator who can query
> "which cancels are unconfirmed" and one who cannot.

## Codes that recur as landmarks
| Code | Meaning |
|---|---|
| ML-073 | live label banking |
| ML-074 | prior-drift detector |
| ML-075 | governor level |
| ML-076 | ghost-badge doctrine |
| ML-081 | era exclusion activated |
| ML-083 | era-orphan clause — **the registry's best case for enumerated codes, 2026-08-09**: a code minted 2026-07-29 for one polarity of a deadlock **fired unmodified on the opposite polarity** and unwedged a bug-promoted champion with no operator action. The record it wrote (`trained_rows 9708`, `corpus_rows 701`, `challenger_brier 0.24728`, `n_oof 464`) is what made the mechanism **provable** rather than inferred, and it sits **4ms** from the ML-040 DEPLOY it caused — see [[sources/session-20260809-gate-policy-and-self-heal]] |
| ML-084 | unlabeled close — a close with no pending vector, so no training row |
| PT-060 / PT-061 | no-progress time stop / close-reason audit |
| SZ-046 / SZ-047 / SZ-048 | per-asset breaker / probe throttle / drought floor |
| XV-033 / XV-052 | cost-truth verdict / fill-hazard verdict |
| OM-011 | limit-only entries |

## Why it matters beyond debugging
Under a legal standard where **intent is inferred from conduct**, the coded audit trail is the defense.
**"If a regulator asked 'why did the bot do X at time T,' the answer is a file, not a recollection."**
An independent criminology reading reaches the same conclusion and adds: **"protect it, don't extend
it."**

## Audited gap
Several dispositions carry **unregistered** codes despite the invariant, and one code claimed as
enforced in the assurance spec is listed by the audit as needing registration. See
[[comparisons/stated-invariants-vs-audited-reality]].

> ⚠️ **Scope of "hash-chained" (2026-08-05):** the provenance spine this page leans on is
> **`audit.jsonl`**, and there the chain is real. It was **not** real for the model registry —
> `ml/registry.py`'s `verify()` compared one **unauthenticated** sha256 from the last matching
> row, so edits, deletions and reordering were undetectable, and deleting the file downgraded
> every load to "unknown provenance" which `reload()` accepted ([[synthesis/owed-measurements]]
> item 30a). **RESOLVED same evening, commit `4799bfc7`** — the registry is now genuinely
> chained on `core/audit.py`'s construction and a broken chain fails the load gate. The lesson
> outlives the fix: same adjective, different guarantee — check the construction, not the
> vocabulary ([[synthesis/open-contradictions-register]]).

## A code in circulation that the registry never heard of — `XV-023` (found 2026-08-10)

`core/codes.py:364-366` registers the fill-calibration family as **`XV-020`, `XV-021`, `XV-022`
— and stops there.** But **`XV-023`** is cited as a live code by `config.json:371`
(`_calibration_life_sec_doc`: *"Recalibrate with per-TTL buckets … (XV-023)"*), by
`core/fill_calibration.py:17`, and by this vault ([[synthesis/owed-measurements]] items 40b and
57b). **It exists only in docstrings.**

Found by *not* minting a fourth: while closing owed 57 the obvious move was an `XV-024` for the
single-path recalibration residual — checking the registry first revealed that **XV-023 had never
been registered either**, so minting XV-024 would have put a *second* phantom code into
circulation ([[sources/session-20260810-fill-double-count]]).

> **This is the exact failure this page's own discipline exists to prevent, arriving through the
> back door.** Enumeration works because *the registry is the enumeration*. A code born in a
> docstring and propagated by citation has all the **appearance** of registration — it looks like
> a code, it is cited like a code, this vault has treated it as a code for two days — with none of
> the **guarantee**. Same shape as the registry-chain lesson above: **same vocabulary, different
> construction.**
>
> **The reading rule:** *a code is registered when `core/codes.py` says so, not when a docstring
> uses it.* Before citing an unfamiliar code, grep `codes.py` — and before minting one, check
> whether the family's last member was ever actually added. Filed to
> [[synthesis/documentation-drift-register]]; the register's older *"a config fingerprint code is
> enforced / the audit lists it as needing registration"* row is the same defect at a different
> family.

## Enumeration is discipline, not provenance (design QA, 2026-08-04)
Operator question answered in [[sources/session-20260804-deploy-gate]]: enumerated codes are
**the discipline half** of the design — exact category and lineage, O(1) filtering, drift
auditable. The `exit_reason`/label **separation** is what made the **25.1% cost wedge**
findable ([[sources/session-20260802-digest]]). **The confidence half is elsewhere**:
continuous companion fields plus the **independent provenance spine** (the hash-chained
`audit.jsonl`) to crossref against. The decisive example: the **136 quarantined fixture fills
carried perfectly VALID enumerated codes** — **enumeration validates form, not origin; the
audit chain convicted them.** A valid code proves the writer spoke the registry's language,
never that the event was real.
