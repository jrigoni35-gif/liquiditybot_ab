---
title: SMC vs THALES: One Primitive, Opposite Polarity
category: comparison
summary: Both modules consume the same swing-point primitive — one treats the resulting cluster as a target, the other as a hazard
tags: [comparison, features, design]
sources: 2
updated: 2026-08-01
---

# SMC vs THALES: One Primitive, Opposite Polarity

Two modules share a single swing-point primitive "rather than maintaining two drifting definitions of
'swing'." They then use it in **opposite directions**.

| | SMC | THALES |
|---|---|---|
| Reads the cluster as | **a target** — price is drawn toward resting liquidity | **a hazard** — our own stop would sit in the herd's cluster |
| Effect | shades the model's belief about `p(win)` | shades confidence **down** |
| Channel | 7 feature columns into the meta-model | a clamped advice multiplier |
| Direction allowed | model learns it | **down only** |
| Activation ladder | none — only an enable flag | shadow -> advise, evidence-gated |

## Why the shared primitive matters
Two definitions of "swing high" would drift apart, and the two modules would then be reasoning about
different objects while appearing to agree. Sharing the primitive makes the **opposition explicit and
intentional** rather than accidental.

## The design asymmetry worth noting
SMC ships as **features and lets the model decide**, with no shadow ladder and no evidence gate — its
only kill switch is a boolean. THALES ships with a full promotion ladder, a vindication ledger, and a
permanent asymmetry constraint.

The stated reason is channel, not importance: features enter a governed statistical pipeline that
already has purging, evidence floors and a dead-feature check, whereas an advice multiplier is a direct
influence on a live decision and therefore needs its own certificate.

## Shared contract
Both **degrade to a neutral value on short or garbage history rather than raising**, and neither may
touch direction or the confirmation flag — [[concepts/asymmetry-law]].

## Related
[[sources/smc-features]] · [[sources/thales-doctrine]]
