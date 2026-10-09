---
title: "Self-referential verification — the trust anchor inside the artifact under test"
date: 2026-09-05
kind: raw
source: deep-research pass (framing + identity/discovery lane), operator-prompted
---

# The anchor inside the artifact

**The pattern.** A validator accepts a record carrying BOTH the value under
scrutiny AND a field naming where to confirm it (`canonical_source`,
`docs_url`, `jku`, `iss`, `id`). The escape hatch says "re-confirm against the
canonical source". The verifier fetches that location, finds agreement, and
reports "verified against canonical documentation."

The authority was supplied by the party being checked. Agreement is guaranteed
and carries zero evidential weight — while the REPORT reads like independent
confirmation. Worse than no check: it manufactures unearned confidence and
terminates scrutiny.

Operator framing, 2026-09-05: *"An attacker submitting a poisoned entry
supplies both the bad address and the 'authoritative' URL that confirms it."*
This is [[concepts/tautological-instrument]]'s fourth specimen class (the
tautological CHECK) relocated from the measurement domain to the trust domain,
and it is the security-domain statement of CLAUDE.md's own law: **a gate's
release condition must never depend on the thing it blocks.**

## It has a catalogued name

**CAPEC-693 "StarJacking"** (v3.9, submitted 2022-09-29) — *"exploits package
managers' lack of validation between packages and their claimed source code
repositories."* That is the registry instance. The general form has no single
accepted name; the closest formal framing is **trust-anchor provenance**: the
anchor must be established out-of-band (RFC 6024 §2 — self-signed anchors
*"provide no useful means of establishing the validity of the information
contained in the certificate"*) or known a priori (RFC 4251 §4.1 — *"the client
must have a priori knowledge of the server's public host key"*).

## The inverse, done right — and where the seam is

**OIDC issuer discovery is NOT an instance. It is the inverse**, and the
inversion is one design move: **the RP never learns the issuer from the token.**
The `iss` claim is never the input to discovery; it is the OBJECT of a
comparison against locally-held configuration.

- **OIDC Core §3.1.3.7(2)**: *"The Issuer Identifier for the OpenID Provider
  (which is typically obtained during Discovery) MUST exactly match the value
  of the `iss` Claim."* The subject is the configured value; the object is the
  claim. (Double-derived: two independent fetches, identical wording.)
- **RFC 8414 §3.3**: the `issuer` returned MUST equal the prefix used to build
  the metadata URL. **This is a BINDING, not evidence** — it only stops a
  legitimate issuer's NAME serving a third party's keys. If the prefix came
  from the attacker, §3.3 is satisfied trivially. (Double-derived: `.html` and
  raw `.txt`.)
- **RFC 8414 §6.2**: TLS cert MUST be valid *for the issuer identifier URL* —
  which presumes that URL is already known and correct.
- **RFC 9207**: compare `iss` *"to the issuer identifier of the authorization
  server where the authorization request was **sent to**"* — local state, no
  fetch.

**The deployment mistake that collapses it into the pattern:** a multi-tenant
or bring-your-own-IdP RP that takes `iss` from the *unverified* token, builds
the discovery URL from it, and validates. Every spec-mandated check passes —
§3.3 self-consistency passes because the attacker authored both documents; TLS
passes because they hold a valid cert for their own domain; the signature
passes because it is their key. **All greens, zero evidence.**

**THE SEAM IS IN THE BCP TEXT.** RFC 8725 §3.8 mandates the binding but leaves
the anchor optional: *"the application MUST validate that the cryptographic
keys used ... belong to the issuer"* — which the attacker's own JWKS satisfies
perfectly — then *"The means of determining the keys owned by an issuer is
application-specific"* and only *"**may** include confirming that the issuer is
trusted."* MUST on the tautological half; *may* on the load-bearing half.
**No fetched document states a normative MUST for a pre-registered issuer
allowlist.** That absence is the finding.

## jku/x5u — the spec blesses the bad shape

**RFC 7515 §4.1.2**: `jku` refers to a key set; the fetch MUST use TLS and the
server identity MUST be validated. **Nothing constrains WHOSE URL it is** — no
allowlist, no required relationship to `iss`, no trust requirement. All the
security requirements are about the transport and none about the anchor. §10
contains no counterweight (established negative). §4.1.3 (`jwk`) is worse: the
key is embedded outright.

**RFC 8725 §3.10** patched it eight years later with a SHOULD, and **framed it
as SSRF** (§2.9). That framing bias is visible in the scores below: a developer
concluding "our egress is filtered, so this doesn't apply" retains the full
authentication bypass.

| ID | Product | What was trusted | Score |
|---|---|---|---|
| CVE-2024-21643 | MS IdentityModel (SignedHttpRequest) | *"trusts the `jku` claim by default"* | 8.8 High, CWE-94 |
| CVE-2024-1233 | JBoss EAP / WildFly Elytron | `JwtValidator.resolvePublicKey` — *"no whitelisting or other filtering behavior is performed on the destination URL"* | 7.3, SSRF |
| CVE-2026-48522 | PyJWT `PyJWKClient` <2.13.0 | uri passed to `urlopen()`; `file://` reads | 4.2 |
| **CVE-2018-0114** | Cisco node-jose | *"a JWK representing a public key can be embedded within the header... **This public key is then trusted for verification**"* | 7.5, CWE-347 |
| GHSA-h5rg-8p7f-47g2 | SurrealDB | **redirect following** defeats a host allowlist — allowlist must apply to the FINAL origin | — |

CVE-2018-0114's description is the cleanest CVE-corpus statement of the class.
NVD keyword recall on "jku" is poor (3 results, one unrelated) — **a search
artifact, not a base rate.**

## The canonical worked example — one variable

**CVE-2024-23832, Mastodon, CVSS 9.4, CWE-346.** *"while Mastodon normally
ensures that the `id` property of every fetched object correctly reflects the
URL of the object, code paths involving `FetchRemoteResource` **passed down the
`id` property of the fetched object instead of the queried URL**."* Result:
impersonation of any remote actor, *"even if the remote server did not use
Mastodon."*

Correct code carries forward **the URL the verifier chose**. Vulnerable code
carries forward **the identity the document asserts about itself**. Same fetch,
same TLS, same "successful verification" — and the log line is indistinguishable.
**Register this as the type specimen: a single-variable substitution, invisible
in review.**

ActivityPub §B.2 states the defence: *"federated servers also should not trust
content received from a server other than the content's origin without some
form of verification"*, and §3: *"checking that the object appears as received
at its origin."* Origin-binding — **`id` must equal the URL you fetched from.**

## The remedy that generalises best: DKIM/DMARC

DKIM in isolation IS the bad shape — `d=` is submitter-supplied and names where
to fetch the key (RFC 6376 §3.6.2.1), so an attacker signs with `d=evil.com`,
publishes their key there, and **verification succeeds, correctly.**

**What saves it is not a stronger check; it is a narrower conclusion.**
RFC 6376 §1.5: *"Verifying the signature asserts that the hashed content has not
changed since it was signed and **asserts nothing else**."* RFC 7489 §3.1.1 then
states the pattern outright:

> *"a message can bear a valid signature from any domain, including domains used
> by a mailing list or even a bad actor. Therefore, merely bearing a valid
> signature is not enough to infer authenticity of the Author Domain."*

DMARC supplies the external anchor: `d=` must ALIGN with the RFC5322.From the
human reads, policy at a verifier-derived location (`_dmarc.example.com`).

**The transferable rule, and the one to adopt:** a self-confirmed record is not
necessarily invalid — but its status must be recorded as **`self_consistent`**,
structurally distinct from **`externally_corroborated`**, and the two must never
collapse into one boolean. *Collapsing them is exactly what CVE-2024-23832 was.*

## The normative statement of the correct pattern

**SPIFFE Federation** — the only place found where the rule is written as a MUST:

> *"clients MUST be configured with... (1) the URL of the SPIFFE bundle
> endpoint, (2) the endpoint profile type, and (3) the trust domain name... It
> is important that these three parameters are configured explicitly, **the
> values cannot be securely inferred from each other.**"*

SPIFFE explicitly forbids deriving the endpoint from the trust-domain name —
the move OIDC makes and survives only via the §3.3 fixed point plus an external
allowlist.

**did:web** is the bad shape, honestly labelled — the identifier IS the location
and the document declares its own verification methods. Defensible only because
the identifier is not attacker-chosen at use time. Its **Path Limitations**
section is the sharpest scope statement found anywhere:

> *"verification with signed data proves that the entity in control of the file
> indicated in the path has the private keys. **It does not prove that the
> domain operator has the private keys.**"*

Reusable register language: **state what the green establishes, in the narrowest
true form, then separately state whether that is what was needed.**

## When you cannot move the anchor: corroborate

**DigiCert 2024** (Mozilla Bugzilla #1910322): dropping the `_` prefix from the
ACME dns-01 validation label converted a verifier-chosen location into an
attacker-occupiable one. **83,267 certificates / 6,807 subscribers**, Aug 2019 →
June 2024. *The validation passed, logged as passed, for five years with no
signal.* Discovered by a researcher asking a question — not by a monitor.

ACME dns-01 done right has three load-bearing properties: the verifier fixes
the LOCATION (`_acme-challenge.` + the identifier), the verifier fixes the
CONTENT (CA-generated token bound to the account key), and the namespace is one
the applicant cannot occupy incidentally (`_`-prefixed is not a legal hostname).

Attacks that survive a correct anchor: **BGP hijack of the validation path**
(Birge-Lee et al., USENIX Security 2018 — first real-world bogus certs from top
CAs) and **off-path DNS cache poisoning** (Brandt et al., ACM CCS 2018 — a weak
off-path attacker subverts CAs covering 99% of the market). Industry response:
**CA/B Ballot SC-067v3** (Aug 2024) — Multi-Perspective Issuance Corroboration,
independent network perspectives ≥500 km apart.

> **When you cannot move the trust anchor outside the submitter's reach, make
> the observation redundant across channels the submitter cannot uniformly
> control. Corroboration replaces authority.**

Residual: BR 3.2.2.4.7 DNS resolution follows CNAMEs, reintroducing
submitter-chosen indirection at the delegation point (Ballot SC-082 constrains
this) [I].

## Mechanical detection — the honest answer

Partially. The detectable signature is narrow: *a URL read from the same record
being validated, then fetched.* That is AST-visible when the flow is local
(field → variable → fetch call) and invisible once it crosses a function or
service boundary, which is where the real cases live. CVE-2024-23832 was a
**one-variable substitution** — `object.id` for `queried_url` — with correct
types, a successful fetch, and an identical log line. **No linter distinguishes
those two variables; only the semantics do.**

The tractable version is not "find the bug" but "constrain the surface":
enumerate every egress point, assert each URL derives from a constant or config,
and forbid location-shaped fields being extracted from remote payloads at all —
extraction is the tripwire, because "...and fetch it" is the next one-line edit.
Applied here as `tests/test_no_attacker_directed_fetch.py` (mutation-verified).

## Instrument caveats

WebFetch passes each page through a summarisation model, so **every "verbatim"
quote is one hop from source.** High confidence for RFCs fetched as raw `.txt`
(8414, 7515, 8725, 9207, 8555, 6376, 7489); lower for HTML-rendered specs (OIDC
Core/Discovery, ActivityPub, did:web). Two load-bearing quotes were
double-derived and survived. **Re-verify exact strings before adversarial use.**

**NOT established:** SAML normative text (OASIS publishes as PDF; fetch returned
unextractable binary — the expected finding is architecturally consistent but
UNVERIFIED). CVE-2026-50128 (Mastodon `attributionDomains`) reported via
secondary aggregators only; if it holds it is a **distinct sub-pattern** — the
signature's coverage set narrower than the reader believes, i.e. a genuinely
valid signature that says nothing about the field relied on. **Not searched:**
Keycloak/Auth0/Okta advisories, RFC 9700, Fett/Küsters/Schmitz and
Mainka/Mladenov/Schwenk malicious-IdP papers.

## Related

[[concepts/tautological-instrument]] · [[concepts/wrong-null-calibration]] ·
[[concepts/deadlock-discipline]] · [[concepts/the-method]] ·
[[concepts/observational-equivalence]]
