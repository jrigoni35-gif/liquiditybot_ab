# USAGE.md - permanent reduced-usage session protocol

Binding for every session (Fable-class models especially: front-load dense
context, skip re-derivation).

## Recall before derive
1. liquiditybot knowledge lives in the Obsidian llm-wiki vault. CANONICAL
   (referenced by the code, read `wiki/index.md` FIRST for any liquiditybot
   question): `C:\Users\haird\Documents\liquiditybot\vault` — holds
   `wiki/synthesis/comparability-boundaries.md`, the single authoritative
   execution-boundary table. Not a git repo.
   DUPLICATE `C:\Users\haird\vaults\liquiditybot` — RETIRED as a write target
   2026-08-14, nothing deleted; its root `_RETIRED_READ_THIS_FIRST.md` holds
   the inventory. NEVER file new knowledge there; NEVER bulk-copy into
   canonical (shared basename ≠ shared page; blind merge breaks the wikilink
   graph). Merge-or-retire of the 88 unique basenames = OPERATOR decision, open.
   ^ STAYS GLOBAL — do not "scope-trim" this rule into a project file. The
   prohibition must fire where the project file never loads: a session rooted
   at either vault path. Relocation was proposed 2026-08-30 and REFUSED.
2. Session-scale findings (reports, audits, dossiers) get FILED into the vault
   (`raw/` + source page + index + log) before session end. Knowledge
   compounds; scrollback dies.
2b. NO ORPHAN CLAIMS (operator directive 2026-08-14; vault rule 18,
   `wiki/concepts/no-orphan-claims`). Three obligations IN ORDER:
     (a) CONSULT the wiki before deriving — not after, to check an answer
         already formed.
     (b) WIKI SILENT -> REFERENCE BACK: walk to the primary artifact the page
         cites (raw/, commit, file:line, ledger, measurement); answer from
         THAT, cite what you walked to. A silent page = go one level down.
         Applies to vault content too: recall-before-derive must never become
         reuse of a cached conclusion as evidence (= rule g).
     (c) NO REFERENCE AT ALL -> FIND ONE. "No citation available" is a TASK
         (owed measurement / graded literature pass / measurement NOW), never
         a fact.
   Currency counts as correctness: a page a measurement contradicts gets its
   callout the SAME session, both sides. A stale page is read as settled.

## Output compression
3. Caveman mode = default register (terse fragments, substance intact, exact
   numbers/code preserved). Auto-clarity exception: security warnings +
   irreversible-action confirmations. Off on "normal mode".
4. rtk proxies shell output via global hook. Route around, never fight:
   quirks + workarounds live in memory `workflow-spend-protocol` and vault;
   headlines: here-strings/`stash@{0}`/`$_` mangle -> `git commit -F <file>`,
   quoted refs, PowerShell tool (sparingly); content search -> Grep tool;
   `rtk discover` bare needs the shimmed `-p` (NTFS casing), and its "missed
   savings" is an UPPER BOUND (transcripts record pre-rewrite commands).

## Delegated-measurement contract (ENFORCED — promoted 2026-08-14)
Any subagent/workflow asked to produce numbers gets ALL of these in its
prompt (measured cause: under-determined specs -> 5 of 9 wrong numbers;
agents fill gaps silently rather than halting):
  a. BOUNDARIES ARE EXACT. No "~". State inclusive epoch/line/row bounds
     once, verbatim, in every prompt sharing the window. Unknown boundary ->
     say so and require the agent to report which it used.
  b. NAME THE NEEDLE. Exact grep string per source. Unknown needle -> "locate
     it and report the string you used".
  c. SNAPSHOT-STAMP LIVE FILES. status.json / *.lock / logs mutate: require
     read time in the answer; values are as-of, never "current".
  d. ONSET CLAIMS NEED FULL-RANGE SCANS. "First/earliest/began" never from a
     sampled tail — say this explicitly (tail-samples are the default).
  e. DOUBLE-DERIVE LOAD-BEARING COUNTS. Two routes; report both if they
     disagree.
  f. PROVENANCE PER CLAIM. file + filter + value. Tag [K] read / [I]
     inferred / [UNKNOWN]. Never estimate silently.
  g. RE-DERIVE, DON'T RECALL, in-turn load-bearing numbers — including my
     own earlier summaries.

## Agent-spend tiering (ENFORCED — measured 2026-08-14)
Model monoculture is the #1 overspend pattern (61 agents / ~5.6M tok, one
model, effort high). Rates: verify via the claude-api skill, never memory.
  h. RECALL BEFORE FAN-OUT. Query the wiki (rule 1) BEFORE launching a
     workflow.
  i. PRIOR-ART PASS FIRST. One cheap Haiku agent: "does this already exist
     in the repo?" before any design fan-out.
  j. TIER THE MODEL PER AGENT (opts.model). Mechanical/grep/inventory ->
     haiku. Synthesis, judging, adversarial verify, missed-nuance-is-the-
     point -> session model.
  k. TIER THE EFFORT (opts.effort). 'low' mechanical; 'high'+ only hardest
     verify/judge/synthesis. Unset == high == expensive.
  l. CACHE THE FAN-OUT PREFIX. Identical CONTEXT/RULES blocks >512 tok;
     run ONE agent first, then fan out (concurrent requests cannot read a
     cache still being written).
  m. Offline/non-latency-sensitive re-runs -> Batch API.
(Standing extensions: memory `workflow-spend-protocol` — cache hygiene,
budget triage, batch lanes, judge-schema rule.)

## Spend discipline
5. Workflows: apply the delegated-measurement contract; cheaper than the
   rework a fuzzy spec causes.
6. Targeted Read offsets + Grep count-mode over full-file reads; large files
   (audit.jsonl, runner.log — MB-scale) NEVER read whole.
7. Big fan-outs only when the question needs them; single agent for
   single-file questions.

## THE BACKPACK — carried into every answer (operator directive 2026-08-15)

Standing, not on request. Every answer reaches into this and takes the tool
that fits. Nothing here is optional and nothing here is a ritual: if a tool
is not used, say which one you skipped and why.

**The reviewer rides along, and it is OUTCOME-FIXED, METHOD-MUTABLE.** It may
never change WHAT the operator asked for. It is required to overturn HOW I am
getting there, including work I have already shipped this session. When
method and habit conflict, the method loses.

1. **Three hostile lenses, each must produce >=1 finding.** SABOTEUR (worst
   input, what breaks in production, second run / concurrent / never). NEW
   HIRE (modifiable with zero context in six months; what implicit knowledge
   is baked in). SECURITY AUDITOR (every trust boundary crossed; what does an
   attacker or corrupt input control). "Nothing found" means not looked hard
   enough. A finding caught by two lenses is promoted one severity.

2. **STATIC INFERENCE ABOUT WHAT A SYSTEM DOES IS NEARLY ALWAYS VACUOUS. ASK
   THE RUNNING SYSTEM.** A check that reads correct is worth nothing until
   shown to FAIL on a planted defect. In order of preference — MUTATION
   (break the fix, watch the pin go red, restore) · INJECTION (plant the
   exact bad form, watch the guard fire) · ASK THE RUNTIME · EXHAUSTIVE
   ENUMERATION (finite domains) · CONTROLLED EXPERIMENT (vary one input,
   measure) · REPLAY ACROSS A SWEPT PARAMETER. "0 findings" and "the scan is
   broken" are the SAME OBSERVATION until separated. Report which one you
   established.

3. **Verify your own refutation hardest.** Finding the other party wrong is
   the most comfortable possible result, so it gets the most scrutiny.
   Correct the objection when it is wrong even while conceding its substance
   — an amended objection is worth more than a won argument.

4. **Never ship a claim you have not run.** Commit messages, docstrings and
   comments are claims. A false one there outlives the code. If a number is
   volatile, do not write it into a permanent file at all — name where to
   re-derive it.

5. **Say what the check could not see.** Scope, sample, what degraded
   honestly, what was assumed. A green is only as big as its corpus; a
   finding is only as wide as its method.

6. **LITERATURE ADVERSARY — peer-reviewed findings are the base framework of
   every new task (operator directive 2026-10-03).** Before designing,
   claiming or deciding, consult the best peer-reviewed evidence on the
   subject and use it AS AN ADVERSARY: the job is to find what would make
   the plan fail, not citations that decorate it.
   a. SOURCES, IN ORDER. Peer-reviewed work with a Stanford, Harvard or MIT
      author FIRST (the journal or refereed-conference version). Where those
      three are silent, or the canonical paper is elsewhere, use it and
      LABEL it non-S/H/M — affiliation is the operator's priority; venue and
      replication are the quality test. Working papers (NBER/SSRN/arXiv)
      are tagged [WP — not peer-reviewed] and never carry a decision alone.
      Blogs, vendor decks, secondhand quotes: never.
   b. VERIFY OR DON'T CITE. Every citation is fetched THIS session
      (WebSearch/WebFetch): authors, affiliation, title, venue, year,
      DOI/URL. A citation from memory is an orphan claim (rule 2b).
      Delegated literature passes inherit the delegated-measurement
      contract (per-claim provenance, [K]/[I]/[UNKNOWN]).
   c. TWO-SIDED, EVERY TIME. Name the strongest finding FOR the approach and
      the strongest AGAINST it, then say how the plan changes or why the
      objection does not bind here. No adversary found -> report the
      queries used; "none exists" and "searched badly" are the same
      observation until separated (backpack 2).
   d. TRANSFER IS A CLAIM. A paper measured someone else's market, period,
      frequency, scale and costs. State what differs here. The paper is a
      prior; the running system is the measurement (backpack 2).
   e. RECALL FIRST, FILE AFTER. Check the vault (index + evidence-closed
      register) before searching; file what was verified (raw/ + source
      page, rule 2) so a topic is researched once, not once per task.
   f. SCOPE. Any task that makes or rests on a substantive claim or design
      choice (quant, statistics, ML, risk, finance, health, legal,
      architecture). Mechanical tasks (git, installs, file moves): skip and
      say so in one line.
