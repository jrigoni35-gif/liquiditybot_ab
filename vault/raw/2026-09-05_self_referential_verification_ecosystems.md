---
title: "Self-referential verification — ecosystem incident register and the agentic amplification"
date: 2026-09-05
kind: raw
source: deep-research, lanes 2-3 (registries/SBOM/token-lists; LLM-agent amplification)
see_also: raw/2026-09-05_self_referential_verification_research
---

# Companion to [[raw/2026-09-05_self_referential_verification_research]]

Lane 1 (framing + identity protocols) is in the sibling file. This carries the
package-ecosystem register and the agent-specific amplification.

## THE CROSS-LANE SYNTHESIS

> **One property separates every working mitigation from every failed one: the
> authority must be bound by a party that is NOT the submitter and CANNOT be
> chosen by the submitter.**

> **The recurring wrong answer is a signature.** Three of five ecosystems
> responded to this pattern by adding one. A signature binds a document to its
> author; it does not move the trust anchor.

> **A mitigation that is not machine-readable is not deployed.** PyPI built the
> verified/unverified distinction and put it in HTML. OpenSSF Scorecard reads
> the JSON API. The mitigation and the consumer never meet.

## The composed pattern is named NOWHERE

Every ingredient is documented; nobody joins them up.

| ingredient | named at |
|---|---|
| attacker-controlled retrieved content | Greshake §3.1 Passive Methods; ATLAS **AML.T0051.001** |
| attacker controls the metadata asserting authority | ATLAS **AML.T0071** |
| the checked party controls the bytes the checker reads | **JudgeDeceiver**, CCS 2024 |
| right citation, adversary-supplied data | ATLAS **AML.T0067.000** |
| confirm-framing collapses a checker | arXiv 2603.18740 |
| retrieved content overrides a correct prior >60% | ClashEval 2404.10198 |
| a polished report induces approval | OWASP **ASI09**; Perry CCS'23 |

Closest primary text, one unelaborated sentence — **Greshake §5.6**: *"Verifying
against retrieved sources will induce a similar dilemma to the one explained
above."*

## 🔴 OWASP's own mitigation PRESCRIBES the ingredient

LLM Top 10 v2025, LLM01 prevention #2, byte-verbatim from the official PDF:

> *"Define and validate expected output formats — Specify clear output formats,
> **request detailed reasoning and source citations**, and use deterministic
> code to validate adherence to these formats."*

Nothing in the document requires the citation to originate from a party OTHER
than the one being validated. **A team following the standard to the letter
builds this hole.**

NIST AI 600-1 **MS-2.5-003** has the same shape: *"Review and verify sources and
citations in GAI system outputs"* — **without asking who supplied them.**

## The defences do not cover it, and CaMeL says so

**CaMeL §3.1 explicit non-goals** (arXiv 2503.18813 — 0 successful attacks /
949 on AgentDojo, the strongest published result):

> *"it cannot defend against text-to-text attacks which have no consequences on
> the data flow."*

The fetch is exactly the fetch the designer intended, of exactly the URL the
record named; only the CONTENT is adversarial and the only thing it changes is
**the text of the conclusion**. That is the carve-out verbatim. The same
reasoning voids every capability/dataflow control, the lethal trifecta, and
Rule of Two: **all constrain what the agent DOES; this harm is entirely in what
the agent CONCLUDES.**

The lethal trifecta fails on three independent grounds: no private data needed
(leg 1 absent, attack works); no exfiltration (leg 3 is specifically theft of
data — here the harm is a false attestation deposited in the gate's own
record); and the remedy fails — "removing any one leg is enough", yet two are
already absent and the failure persists. **A one-leg system that is not safe is
a counterexample to the one-leg rule for this harm class.** Fair caveat: it is
published as a heuristic for the confidentiality class, not a complete taxonomy.

## Why an LLM verifier is worse — graded

**[K] confirm-framing, large effect.** arXiv 2603.18740, 250 CVE patch pairs ×
5 framings × 6 models: **"Framing a change as bug-free reduces vulnerability
detection rates by 16-93%."** The asymmetry is load-bearing: **false negatives
rise sharply, false positives barely move — FN bias exceeds FP bias 4x to
114x.** GPT-4o-mini 97.2% → 3.6%. *A record saying "here is the value and here
is the source confirming it" IS the strong bug-free framing.* Mitigation that
worked: **"metadata redaction and explicit instructions restores detection in
all affected cases."**

**[K] the report is what humans read.** Perry et al. CCS'23: participants with
an AI assistant *"wrote significantly less secure code"* AND *"were more likely
to believe they wrote secure code."*

**[I] "a 200 means the proposition is true" — UNMEASURED.** Bounded from
outside: *Cited but Not Verified* (2605.06635) link validity >94% but factual
accuracy **39-77%**, and accuracy **drops ~42% as tool calls rise 2 → 150**.
**A runnable experiment, not a literature question.**

**No reliable model-side defence.** *The Attacker Moves Second* (2510.09023):
**12 defences bypassed at >90% ASR — "the majority originally reported
near-zero."** Prompt-level reframing is worth ~14pp (*Failing to Falsify*:
42% → 56%) and will not carry a gate.

## Ecosystem register

**OpenSSF Scorecard** — the pattern fully mechanised, and the sharpest instance
found. `cmd/package_managers.go` resolves a repo URL from the package's own
`repository` field (npm), `info.project_urls` (PyPI), `source_code_uri`
(RubyGems), with **no verification step anywhere in the resolver**.
`scorecard --npm=<pkg>` emits *"Branch-Protection: 9, Code-Review: 10"* against
a repository the package nominated. No documented weaponisation found — a
search limit, not an absence result.

**npm provenance step 7 — the ONE deployed mechanism in scope that relocates
the anchor.** *"Verify the `repository`/`repository.url` in the uploaded
package.json matches what's in the signing certificate `Source Repository URI`
extension."* The extension is minted by the OIDC issuer, which the publisher
does not control. Confirmed live via npm/cli #8036, where the check fires with
an explicit mismatch error. **OPT-IN** (attestation present for sigstore@3.1.0,
404 for chalk@5.6.2; n=2, an existence proof not a rate). Note npm's
`dist.signatures` covers only `name@version:integrity` — **not the URL
metadata.**

**PyPI** — warehouse **#8635** (dstufft, 2020-09-30, **still OPEN**) states the
pattern in the registry's own words: *"there's no way to verify that a project
that has `https://github.com/pypa/pip` in its home page is actually the real
pip."* The verified/unverified UI split shipped, but `docs.pypi.org` scopes it
honestly: *"A URL being verified only attests that the URL is under control of
the PyPI package owner **at the time of verification**"* and is *"not repeated
afterwards"* — a point-in-time claim that outlives its evidence. **MEASURED GAP:
`/pypi/requests/json` `info` keys containing "verif" = `[]`.** The mitigation is
HTML-only; Scorecard reads the JSON. PEP 740 attestations bind a FILE to a
builder and say nothing about URLs.

**crates.io** — no repository verification at all; RFC 3691 puts provenance
explicitly out of scope. The `documentation` field is the escape hatch drawn:
the default authority is *derived from the artifact* (docs.rs, network-blocked
sandbox), and setting the field **replaces it with a submitter-declared URL**.
The registry's own answer (Code tab, 2026-07-13): *"the exact files that cargo
downloads... **which might differ from the linked repository**"* — the registry
telling users the link is not evidence.

**SBOM — the governing US federal spec places accuracy OUT OF SCOPE.** CISA
2026 Minimum Elements, byte-verbatim: the SBOM Author Signature *"provides
assurance that the claimed signatory signed the information"*, and *"organizations
may seek to confirm the accuracy, coverage, and completeness of SBOM data.
**These process-based properties... are out of the scope of the SBOM Minimum
Elements.**"* A mandated signature that binds the document to its own writer,
with accuracy disclaimed in the same section. SPDX 2.3 permits `NOASSERTION` on
supplier/originator/downloadLocation. **CycloneDX 1.6 is the one spec in scope
that gets it right**, with normative field text: purl *"**Asserts** the identity"*,
and `evidence.identity.methods[].technique` forces you to say WHICH technique —
distinguishing `manifest-analysis` (the submitter's declaration) from
`binary-analysis`/`hash-comparison` (independent of it), with a confidence
score. **OPT-IN** ("optionally").

**Token lists — peer-reviewed in the wild.** Gao et al., SIGMETRICS 2020
(arXiv 2011.02673): **2,117 counterfeit tokens**, 94 of the top-100 targeted,
7,104 victims, ≥$17M. **Figure 10 is the pattern drawn**: the fraudster supplied
the counterfeit address AND the *"CoinMarketCap official website"* pointer, with
*"the screenshot the fraudster provided"* as *"proof of the authenticity."* The
victim fetched the authority the submitter named, found agreement, and was
defrauded. The paper's own remedy is exactly the out-of-band anchor: *"As long
as users input the official address during the transaction, the counterfeit
cryptocurrency scams will not succeed."* Base rate for "listed on Uniswap" as a
credential: **~50% of listed tokens are scams** (arXiv 2109.00229, >10,000
tokens, ≥$16M from 39,762 victims).

## Instrument caveats — measured, not assumed

The research agents' own fetch-summariser was **wrong three times this session**,
each caught only by re-deriving from raw bytes:
1. mis-titled arXiv 2603.18740 as *"**Confirmation** Bias"* (actual:
   *"**Contextual** Bias"*)
2. **fabricated a quotation** in the CISA 2026 PDF summary — the phrase
   *"asserted by the SBOM author"*, in quote marks, does not appear in the PDF
3. inverted the docs.rs build source (claimed it builds from the repository;
   the network-blocked sandbox contradicts that)

**A confident summary of a spec is not the spec.** Quotes marked [K-direct]
(Greshake, OWASP LLM Top 10, NIST 600-1, ATLAS YAML, CISA PDF, Scorecard Go
source, CycloneDX schema, the counterfeit-token paper) were byte-extracted
locally and are citable. Everything else is summariser-mediated and must be
re-derived before permanent use.

**Not established:** npm/PyPI named incidents (0 primary-sourced found; vendor
blogs excluded) · SBOM consumer tools (spec level only) · CoinGecko/CMC listing
criteria · OWASP ASI09 full text (both PDFs 404'd) · Bansal CHI 2021 ·
Ermakova CHIIR 2026 (dl.acm 403) · adoption rates (n=2 probes).

## Related

[[concepts/tautological-instrument]] ·
[[raw/2026-09-05_self_referential_verification_research]] ·
[[concepts/the-method]] · [[concepts/wrong-null-calibration]]
