---
title: The Tautological Instrument
category: concept
summary: "A measurement whose value is fixed by construction over most of its population — it reports agreement it cannot fail to report, so its reading is definitional rather than empirical. Extended 2026-08-07: the latency plane held two clock-shaped specimens — a staleness veto that ages a timestamp with the same frozen now that stamped it (always ~0ms vs a 4000ms ceiling, STILL OPEN) and a marks_age_sec gauge that read 0.0 by the same arithmetic — the gauge REPAIRED same night (915b362f, telemetry-only wall-clock twins) and proved non-tautological live: 16.7s and climbing while the bot was stopped; the VETO specimen repaired 2026-08-08 by 36fcfd6e and then CORRECTED 2026-08-09 — it was tautological on the SUCCESS path only (the failure path grew ~5s/cycle), the repair is real on the WS path only (REST is sign-inverted), and a quantity capped at 3.5s cannot feed a 120s gate. Extended 2026-08-15 with the FOURTH specimen class — the tautological CHECK: four vacuous verifications in one session, three written while fixing this class (the docket's two BLOCKING pins, the anti-tautology guard whose own first draft was blind to the spelling it existed to catch, and a Grafana coverage analysis that returned a confident 0-dead-of-181 twice before asking the runtime returned 27). Supplies the answer to this page's own diagnostic question: static inference is nearly always vacuous — mutation, injection, exhaustive enumeration, controlled experiment, or ask the running system"
tags: [instruments, honesty, telemetry, measurement, defect-class, latency]
sources: 5
updated: 2026-08-15
---

# The Tautological Instrument

## Definition
An instrument whose reported value is **determined by construction** for most or all of the
population it measures. It emits a number that **looks like evidence** and is in fact
**definitional** — the measurement could not have come out any other way.

Distinct from a *broken* instrument (which reports a wrong number) and from an *absent* one
(which reports nothing). This one is **working exactly as written** and still carries **zero
information**.

## The type specimen — the bracket-divergence gauge (2026-08-06)

`bracket_divergence_summary` (ML-082) exists to answer: *did the **traded** bet resolve where the
**label** says it should?* It published `agree_rate` to Grafana as
`liquiditybot_bracket_divergence_rate`.

But a **`tb_time`** record's counterfactual **IS its realized value**. Its delta is **0 by
construction**, so it **always "agrees"**.

**Measured over the instrument's entire production lifetime: 33 of 35 records (94.3%) were
`tb_time`.**

> The gauge read **1.0000** and was **94% arithmetically incapable of reading anything else.**

The operator watching that panel was being told, in the language of measurement, that label and
trade were in perfect agreement. What the panel actually reported was that **most closes were
time-barrier closes** — a fact about the *population*, dressed as a fact about *agreement*.

## The diagnostic question
> **"What would this instrument have to see in order to read differently?"**

If the answer is *"a subpopulation that is 6% of the sample"*, or *"nothing — the arithmetic
forbids it"*, the number is not a measurement. Ask it of every gauge, ratio and rate **before**
believing a reading, and especially before believing a **flattering** one.

## Absence was handled; vacuity was not
The strongest lesson from the instance is that **the author had already seen the adjacent
hazard**. The function's original docstring reads:

> `n=0` / `agree_rate: None` whenever no bracket close has been recorded — *"deliberately None
> rather than a 1.0 that would read as 'perfect agreement' instead of 'not measured'."*

The **empty** case was guarded with exactly the right reasoning. The **definitionally-empty**
case — records present, but none of them capable of disagreeing — **walked straight through the
same door**. A guard against *no data* is not a guard against *no information*.

## The honest fix pattern
Not *"drop the uninformative rows"* — they are real closes and dropping them would lie about
volume. Instead, **publish the two numbers the blend was hiding**:

- Compute the rate over the **measurable subset only** (here: `tb_pt`/`tb_sl`, the **priced**
  barriers), and return **`None` until one exists**.
- **Keep the total count** as its own field, and add the measurable count beside it (`n`,
  `n_priced`).

So the pair reads **"of N closes, only M could be measured"** — which is the fact an operator
needs, and which **a single blended rate structurally cannot express**. Reporting **None rather
than a flattering zero** is the same discipline the function already applied to emptiness, now
applied to vacuity.

## The test was right about the mechanism and wrong about the publication
The existing test **asserted the old `1.0`**. It was not a bad test — it correctly pinned what the
code did. It was **pinning a tautology as a contract**. It was **updated with a docstring
recording why**, not deleted: a test that encoded a defect is evidence about how the defect
survived, and that evidence is worth more than a clean diff. Compare the 2026-08-05 finding of a
**green test standing on a defect** (`test_monitor_deescalate_deadband`'s fixture depending on the
old oracle baseline).

## Second and third specimens — the clock that reads its own stamp (2026-08-07 night)

The fleet sweep ([[sources/session-20260807-fleet-findings]] §4) found the class in the latency
plane, twice, both verified on the box:

- **The pre-trade staleness veto.** `main.py:2420` stamps `book_ts[asset] = now`;
  `main.py:4403` computes `staleness_ms = (now − book_ts) × 1000` **with the same cycle-frozen
  `now`** — so the veto reads ~0ms **by construction**, against a 4000ms ceiling
  (`pretrade.py:96,236`) the arithmetic can never reach. Ask the diagnostic question: *what
  would this gate have to see to fire?* Answer: nothing — a REST hang, a stalled feed and a
  slow cycle are all invisible, because the timestamp being aged and the clock aging it are
  the same write.
- **`marks_age_sec`.** Live value 0.0; `runner.py:1163` computes `now − _mark_ts.get(s, now)`
  while the cycle re-stamps `_mark_ts` continuously (`main.py:2402/2438`) — and the
  `.get(s, now)` default makes a **missing** mark read as perfectly fresh: the absent case
  lands on the flattering side ([[concepts/zero-is-not-a-reading]]).

Both are **gate/gauge-side** instances where the type specimen was **rate-side**: the
bracket-divergence gauge could not read below 1.0; these clocks cannot read above ~0. The
sentiment `vol_z` (input pinned at its 200-item cap → z ≡ 0, spike gates dead) and the
`opt_iv_skew` at its −3.00 clip rail complete the family from the input plane. Fixes owed as
items 41–42: **age a timestamp only with a clock the stamped event does not own.**

### The gauge specimen repaired — and verified by a reading it could not have faked (2026-08-07 night)

`915b362f` ([[sources/session-20260807-closing-batch]] §2–3) fixed **`marks_age_sec`** by the
rule above: telemetry-only **`_mark_wall_ts` twins** written beside the loop-frozen stamps, read
by a wall-clock helper — **no decision path touches the wall stamps**, so replay determinism is
untouched. The verification is the instructive part: the same night, the gauge read **16.7s and
climbing while the bot was STOPPED** and 0.0 when fresh — a reading the old arithmetic was
**forbidden by construction from producing**. That is what discharge of this class looks like:
*the repaired instrument earns belief by producing a reading its predecessor could not.* The
new `cycle_duration_max_sec` gauge passed the same bar on its first boot (**45.56s** — the
warmup stall that previously left no trace in any exported number). The **staleness veto
specimen remains open** (owed 42a — it is a decision path, consciously excluded from the
telemetry-only tier), and FW-080 now gives the bar-age blind spot a detection-only instrument.

### The veto specimen repaired — with the claim CORRECTED and the gain bounded (2026-08-08/09)

`36fcfd6e` (owed 42a) resurrected the **pre-trade staleness veto** by the rule above: books
carry their own **receive stamp** (`recv_ts`), so the age is measured against a clock the
stamped event does not own. **But an adversarial audit of that commit the next day corrected
the diagnosis and bounded the gain** ([[sources/session-20260809-corpus-corruption]] §11):

**Correction to this page's own claim.** The pre-42a code was **NOT tautological on the
FAILURE path.** On a failed fetch `book_ts` retained the **last successful cycle's `now`**
and therefore grew at **~5s/cycle** — a perfectly real, climbing reading. The tautology was
**success-path only**: when a fetch succeeded, the book was stamped with the same frozen
`now` it was later compared against. This matters because **the failure path is exactly the
one `36fcfd6e`'s commit message led with**, so the repair was partly credited for fixing
something that already worked.

> **The refinement this forces on the class:** *"the instrument cannot produce an alternative
> reading"* must be qualified by **which population**. An instrument can be tautological over
> the majority case and informative over the rare one — and the rare one is usually the case
> you care about. **Always state the subset over which the value is fixed by construction**,
> which is the denominator this page's general rule already demands, applied to itself.

**And the repair's gain is narrower than claimed — two bounds:**

- **REST path: sign-inverted, not repaired.** `now` is frozen at cycle start while `recv_ts`
  is stamped **after** the blocking fetch, so `staleness_ms <= 0` for any book fetched this
  cycle; a **50s REST hang reads −50000ms**. **42a buys no new detection power on REST.** The
  genuine gain is the **WS path only**.
- **DL-10 cannot benefit.** The new measurement is **capped at `kraken_max_book_age_sec`
  (3.5s)** while DL-10/watchdog trip at `stale_critical_sec` = **120**. **A quantity capped
  at 3.5 cannot cross 120** — a *bounded* instrument is a second way to be structurally
  incapable of a reading, distinct from a *frozen* one, and it belongs in this family.

**Separately, repairing the veto exposed a live defect above it:** at
`kraken_max_book_age_sec` **5.0s** against `pretrade.max_data_staleness_ms` **4000ms**, books
aged 4–5s were **served then vetoed**, preempting a fresh REST read on ~0.6–3% of entry
evaluations ([[entities/pretrade-gate]]). Fixed **5.0 → 3.5** plus a `config_guard` **FATAL
on the relation** ([[entities/config-guard]]). **A dead instrument hides the defects
downstream of it: bringing it to life is a change in system behaviour, not just in
reporting** — which is the strongest argument for repairing tautological instruments early,
while nothing depends on their silence.

## Fourth specimen class — the tautological CHECK (2026-08-15)

Every specimen above is an instrument inside the running system. This one is
the **verification tooling the author writes to check their own work**, and it
matters more, because a vacuous check is what lets the other three ship.

**Four vacuous checks in a single session, three of them written while fixing
this very class.**

1. **The docket's two BLOCKING objections were both this.** `OBJ-2`: a test
   whose message asserted *"exactly ONE place may derive `on_synthetic`"* while
   its assertion counted the **assignment spelling** (`on_synthetic =
   source.startswith`) — 1 — against a file deriving that predicate **five**
   times (`overfit_check.py:704, 833, 1075, 1084, 1089`). `OBJ-14`: the same
   pin survives the exact mutation it forbids. Both passed. Both were written
   to prove a defect fixed; neither could observe it.

2. **The guard against tautological pins was tautological.** Writing
   `tests/test_pin_quality.py` to fail that form at authoring time, the first
   draft required the era literal on the same line — so it did **not** fire on
   `assert retired not in text`, which is precisely the spelling the author had
   just written and corrected minutes earlier. Detected only by **injecting**
   the bad form; invisible to reading.

3. **Its second draft then cried wolf** on `tests/test_cohort_homogeneity.py:208`
   (`assert "legacy" not in c["label_era"]`), where `label_era` holds a
   **collection** and membership is legitimate. A guard that fails on correct
   code gets deleted, which is its own route to vacuity.

4. **The Grafana coverage analysis was vacuous TWICE.** Asking "which panels
   query a series nothing emits", the first attempt matched every metric against
   a bare `liquiditybot_` prefix harvested from `gc_pusher.py:289`
   (`f"liquiditybot_{key}"`), so the coverage predicate was **always true** →
   *"0 dead of 181"*. The second expanded 18 f-string prefixes × ~425 string
   literals into **7,650 synthetic names** that match nearly anything → again
   *"0 dead"*. Two confident, clean, worthless answers.

   Only calling the exporter's own `collect()` against the live `status.json`
   produced a real number: **27 of 181 queried metrics (14%) are not produced**
   — 23 on the execution board — with two root causes (`ml.load_stats == {}`
   and `orders == {}`), not 27 problems.

## The method this class actually requires

This page already asks the right diagnostic question — *"what would this
instrument have to see in order to read differently?"* — and 2026-08-15 supplies
the answer to **how you answer it**: you cannot, by reading. Every vacuous check
above looked correct on inspection, and three were written by an author who had
that exact question in mind.

> **Static inference about what a system does is nearly always vacuous.
> Ask the running system.**

What worked, each time, was making the check *read differently*:

| method | what it settled that reading could not |
|---|---|
| **mutation** | reverting the era fix turned the new pin RED — proof it observes the property, not the name |
| **injection** | inserting `assert retired not in text` proved the guard's draft 1 blind to the spelling it existed to catch |
| **ask the runtime** | `collect()` on the live status file: 27 of 181 dead, where two static analyses said 0 |
| **exhaustive enumeration** | all 1,114,112 codepoints, 0 counterexamples — settling OBJ-10 where argument had gone in circles |
| **controlled experiment** | 4 pyright runs proved CLI paths override config `include` (OBJ-13a); reading the docs would have given the opposite answer |
| **replay across a swept parameter** | the loader returns an identical count over a **46-day clock span** on a byte-identical file — refuting OBJ-4's stated mechanism |

The common shape: **make the thing produce an output it could not produce if the
claim were false.** A check never subjected to that has an unknown information
content, and the prior from this corpus is that the content is zero.

Corollary for delegated work, now in `USAGE.md`'s measurement contract: an agent
that returns a clean result from a static scan has reported *nothing* until the
scan is shown to fail on a planted defect. "0 findings" and "the scan is broken"
are the same observation until separated.

## Siblings in this corpus
- [[concepts/ghost-badge]] — a champion's score measured on a **population that no longer
  exists**. There the number was real *once*; here it was never informative.
- [[concepts/wrong-null-calibration]] — the in-window-oracle baseline (`baseline_brier` equal to
  the window's own realized mean). Same family: **the comparator was derived from the thing it
  was supposed to judge independently.**
- [[concepts/honest-coverage-gap]] — the *deliberate* version, done right: when a signature is
  genuinely unobservable, **document the gap rather than ship a detector that appears to cover
  it.** A tautological instrument is the accidental version of exactly what that concept refuses
  to do on purpose.
- [[concepts/null-model-floor]] — the general demand that a result be stated **against something
  that could have beaten it**.

## Fifth specimen class — the tautological TRUST ANCHOR (2026-09-05)

The fourth class was a CHECK that could not fail. This one is a check that
cannot fail **because the thing being checked supplied the authority**. Same
defect, relocated from the measurement domain to the trust domain, and it is
the security-domain statement of CLAUDE.md's own law: *a gate's release
condition must never depend on the thing it blocks.*

**The shape.** A record carries both the value under scrutiny and a field
naming where to confirm it (`canonical_source`, `docs_url`, `jku`, `iss`,
`id`). The escape hatch says "re-confirm against the canonical source". The
verifier fetches it, finds agreement, and reports *"verified against canonical
documentation."* Agreement was guaranteed. **The report reads like independent
confirmation, which is why this is worse than no check at all.**

Operator framing, 2026-09-05: *"An attacker submitting a poisoned entry
supplies both the bad address and the 'authoritative' URL that confirms it."*

**It is catalogued.** CAPEC-693 "StarJacking" names the registry instance.
The general form's formal framing is trust-anchor provenance: RFC 6024 §2
(self-signed anchors *"provide no useful means of establishing validity"* —
confidence comes from out-of-band means) and RFC 4251 §4.1 (*"a priori
knowledge of the server's public host key"*).

**The type specimen — one variable.** CVE-2024-23832 (Mastodon, CVSS 9.4,
CWE-346): code paths *"passed down the `id` property of the fetched object
instead of the queried URL."* Correct code carries forward the URL **the
verifier chose**; vulnerable code carries forward the identity **the document
asserts about itself**. Same fetch, same TLS, same green, **identical log
line**. Universal remote-actor impersonation from a single-variable
substitution that no reviewer would see.

**The class is blessed by a standard.** RFC 7515 §4.1.2 requires TLS and
server-identity validation on a `jku` fetch and says *nothing about whose URL
it is* — every security requirement is about the transport, none about the
anchor (§10 contains no counterweight; established negative). RFC 8725 §3.10
patched it with a SHOULD and framed it as **SSRF**, naming the lesser harm —
so a team that filters egress still holds a full authentication bypass. See
[[raw/2026-09-05_self_referential_verification_research]] ·
[[raw/2026-09-05_self_referential_verification_ecosystems]] for the CVE register
(node-jose CVE-2018-0114 is the cleanest corpus statement: *"This public key is
then trusted for verification"*).

**The seam is in the normative text.** RFC 8725 §3.8: MUST validate that the
keys *"belong to the issuer"* — which the attacker's own JWKS satisfies
perfectly — while *"the means of determining the keys owned by an issuer is
application-specific"* and only **may** include confirming the issuer is
trusted. **MUST on the tautological half, `may` on the load-bearing half**, and
no fetched document states a normative MUST for a pre-registered allowlist.

### The repair, and why it is a SCOPE change rather than a stronger check

DKIM is the bad shape by construction — `d=` is submitter-supplied and names
where to fetch the key, so an attacker signs with `d=evil.com`, publishes there,
and **verification succeeds, correctly.** What saves it is not a better check.
RFC 6376 §1.5: verifying the signature *"asserts that the hashed content has not
changed since it was signed and **asserts nothing else**."* RFC 7489 §3.1.1:
*"merely bearing a valid signature is not enough to infer authenticity of the
Author Domain."* DMARC then supplies the external anchor (alignment with the
From: the human reads, policy at a verifier-derived location).

> **THE RULE THIS PAGE ADOPTS.** A self-confirmed record is not necessarily
> invalid — but its status is `self_consistent`, which is a DIFFERENT FIELD from
> `externally_corroborated`. Collapsing the two into one boolean *is* the defect;
> CVE-2024-23832 is what that collapse looks like in production.

This is the same discipline the fourth class already demanded ("say what the
green establishes, in the narrowest true form"), stated as a schema. did:web's
Path Limitations section is the sharpest published example: signed data proves
*"the entity in control of the file indicated in the path has the private
keys. It does not prove that the domain operator has the private keys."*

**The normative statement of the correct pattern** is SPIFFE Federation, the
only MUST found: clients MUST be configured with endpoint, profile and trust
domain explicitly, because **"the values cannot be securely inferred from each
other."**

**When the anchor cannot be moved out of reach, corroborate.** DigiCert 2024
dropped one `_` from the ACME dns-01 label, converting a verifier-chosen
location into an attacker-occupiable one: **83,267 certificates over five
years, every validation passing and logging as passed**, found by a researcher
asking a question rather than by any monitor. The industry answer (CA/B
SC-067v3) is Multi-Perspective Issuance Corroboration — independent vantage
points ≥500 km apart. *Corroboration replaces authority.*

### The formal statement — principal collapse, and it is one substitution

The pattern is not "circular reasoning" and not vacuity. It has an exact
statement in the **ABLP principal algebra** (Abadi, Burrows, Lampson, Plotkin,
*A Calculus for Access Control in Distributed Systems*, ACM TOPLAS 15(4), 1993),
whose definitions are:

> *"We write ... **A controls s as an abbreviation for (A says s) ⊃ s**, which
> expresses trust in A on the truth of s."*
> *"**A ⇒ B stands for A = A ∧ B** and means that A is at least as powerful as
> B; we pronounce this '**A speaks for B**.'"*
> *"⊢ (A ∧ B) says s ≡ (A says s) ∧ (B says s)"*
> *"⊢ (A ⇒ B) ⊃ ((A says s) ⊃ (B says s))"*

Let **S** = the submitter, **C** = the canonical source S nominated. The gate's
evidence is the joint principal **S ∧ C** saying X — a "joint signature", which
the paper says buys trust neither party has alone. But if the anchor sits inside
the submitter's trust domain, that is exactly **C ⇒ S**. Then:

> **S ∧ C = C**

Two independent derivations, both run 2026-09-05:
- **Order:** `C ⇒ S` is `C = C ∧ S`, i.e. `C ≤ S`. The meet of S with something
  below it is that lower element, so `S ∧ C = C`.
- **Semantics:** `(S ∧ C) says X ≡ (S says X) ∧ (C says X)`; the speaks-for axiom
  gives `C says X → S says X`, so the first conjunct is implied by the second and
  `(S ∧ C) says X ≡ C says X`.

**The two witnesses are one witness** — and since `C ⇒ S` means C's utterances
are attributable to S, that witness is the submitter's own word, laundered
through a channel the submitter chose. Not "weak evidence": *algebraically a
single principal*, in one substitution.

*(CORRECTION, recorded because the correction is the lesson. The research pass
that produced this stated the result as `S ∧ C = S`, named it the single most
important sentence in its report, and then flagged — correctly — that it had
derived it in ONE pass and wanted a second route before anyone relied on it.
Both routes above give `= C`. The substantive conclusion is unchanged and
slightly sharper; the equation as first written was wrong. An agent that asks to
be checked on its own headline is doing the thing this page is about.)*

**Why this is the right frame and vacuity is not.** Under Beer et al.'s
definition (FMSD 18(2), 2001), a sub-formula is vacuous if substituting it does
not change the verdict — a *mutation* definition, the backpack's rule 2
published in 1997. But substitute a different `canonical_source` and the verdict
DOES move: the fetch 404s, the strings mismatch, the gate rejects. **The check
is not vacuous; it fails to fail only against an adversary who controls both
halves.** Vacuity detection would give this gate a clean bill of health. The
correct predicate is the principal-collapse one, and it is a statement about a
threat model, not about a formula in a program.

**Consequence for detection:** the undecidable question is whether `C ⇒ S` — a
fact about who controls a hostname in the world, not a program property. So do
not detect it; **make it unrepresentable.** Collapse every anchor fetch to one
chokepoint taking an *enum, not a URL*, and lint that no HTTP client is imported
elsewhere in the validation package. That converts an undecidable dataflow
question into a grep. **Architecture beats analysis here, and it is not close.**

### The rule the ecosystem register converges on

Across npm, PyPI, crates.io, SBOM and token lists, **one property separates
every working mitigation from every failed one: the authority must be bound by
a party that is NOT the submitter and CANNOT be chosen by the submitter.**

**The recurring wrong answer is a signature.** Three of five ecosystems answered
this pattern by adding one, and a signature binds a document to its *author* —
it does not move the anchor. CISA's 2026 SBOM Minimum Elements is the purest
case: it mandates an Author Signature and, in the same section, places accuracy
*"out of the scope of the SBOM Minimum Elements."* Only npm's provenance step 7
both signs and constrains a declared field against an externally-issued
credential (the OIDC cert's `Source Repository URI`), and it is the only
loop-closing mechanism found in scope.

**Second rule, measured:** *a mitigation that is not machine-readable is not
deployed.* PyPI built the verified/unverified split and put it in HTML; OpenSSF
Scorecard reads the JSON API, where `info` keys containing "verif" number
**zero**. The mitigation and its consumer never meet.

**And the standards actively prescribe the ingredient.** OWASP LLM01 mitigation
#2 says *"request detailed reasoning and source citations"* with no independence
requirement anywhere in the document; NIST AI 600-1 MS-2.5-003 says *"verify
sources and citations"* without asking who supplied them. A team following
either to the letter builds the hole. See
[[raw/2026-09-05_self_referential_verification_ecosystems]].

### Detection is only partly mechanical — state that honestly

The signature (*a URL read from the record being validated, then fetched*) is
AST-visible while the flow stays local and invisible once it crosses a function
boundary, which is where the real cases live. No linter separates `object.id`
from `queried_url`: same type, same successful fetch, same log line. The
tractable move is not "find the bug" but **constrain the surface** — enumerate
every egress point, assert each URL derives from a constant or config, and
forbid location-shaped fields being extracted from remote payloads at all,
because extraction is the tripwire and "...and fetch it" is the next one-line
edit. Shipped as `tests/test_no_attacker_directed_fetch.py`, mutation-verified
(adding `findtext("link")` to the RSS parser reds it).

**Repo status at filing: CLEAN, and established rather than assumed.** The
ingestion parsers extract only `title`/`pubDate`; no `href` extraction exists
anywhere in `sentiment/`, `context_engine` or `webdata_feed`; every fetch URL
derives from a module constant or a config key. The fee-schedule reader written
the same session hardcodes its endpoint for exactly this reason — and its own
reference table is diffed against the live venue by
`scripts/fee_drift_report.py`, because **a constant cannot confirm itself.**

## The general rule
**An instrument earns belief only from the readings it could have produced and did not.** Publish
the denominator that makes that visible — the measurable subset alongside the total — or publish
`None`. A rate with no possible alternative reading is a **label**, not a **measurement**, and it
should never reach a panel dressed as one.

## Related
[[sources/session-20260806-geometry-filing]] · [[sources/session-20260807-fleet-findings]] ·
[[sources/session-20260807-closing-batch]] ·
[[concepts/ghost-badge]] ·
[[concepts/wrong-null-calibration]] · [[concepts/honest-coverage-gap]] ·
[[concepts/null-model-floor]] · [[concepts/calibration-check]] ·
[[concepts/iron-law-of-debugging]] · [[entities/observability-sidecars]] ·
[[synthesis/open-contradictions-register]] · [[entities/pretrade-gate]] ·
[[entities/config-guard]] · [[sources/session-20260809-corpus-corruption]] ·
[[sources/session-20260808-night-staleness-overfit]]
