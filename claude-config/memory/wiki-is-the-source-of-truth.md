---
name: wiki-is-the-source-of-truth
description: "Operator directive 2026-08-02: the vault wiki is THE source of truth - every confirmed finding must be injected into it via /llm-wiki, every session"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 63d8f842-8108-448c-b2d9-fa9a4c8a2da4
  modified: 2026-08-03T01:57:07.474Z
---

Operator directive, 2026-08-02, verbatim intent: *"From now on the corpus's
Wiki is the truth and everything that is determined correct or has been
determined correct needs to be injected into the corpus's wiki."*

**Why:** the operator uses the vault (`C:\Users\haird\Documents\liquiditybot\vault`)
as the bot's persistent brain across sessions and models. Findings that live
only in a chat transcript or commit message die with the session; three
binding-constraint headlines went stale in nine days because corrections
outran the places they were written.

**How to apply:**
- After any finding is *confirmed* (measured, battery-green, committed),
  file it via `/llm-wiki` in the same session — numbers, commit hash, and
  what it supersedes. Don't batch across sessions.
- The wiki distinguishes touch-space vs label-space, snapshots vs live
  numbers — preserve its supersession chains; never overwrite a claim
  without recording what replaced it and why.
- "Determined correct" means measured and verified — hypotheses and
  in-flight experiments go in as owed measurements / open questions, not
  as facts.
- The corpus itself (`signal_history.csv`) is NOT the wiki: nothing
  synthetic or relabeled is ever injected there. "Inject into the wiki" ≠
  "inject into training data."

Related: [[cost-is-the-binding-constraint]], [[fills-duplicate-on-restart]]
