export const meta = {
  name: 'red-team-panel',
  description: 'Five mandated-position panelists attack a change, cross-examine each other, and return a docket the author MUST answer on the record',
  whenToUse: 'Before pushing anything the author also wrote. Especially when a prior review came back clean, or after a long session.',
  phases: [
    { title: 'Prosecute', detail: 'five lenses, each ARGUING an assigned position - not reviewing' },
    { title: 'CrossExam', detail: 'a different panelist must ESCALATE or WITHDRAW each objection' },
    { title: 'Docket', detail: 'surviving objections, ranked, with the disposition the author owes' },
  ],
}

// ---------------------------------------------------------------------------
// WHY THIS EXISTS, in one paragraph, because a tool without its reason decays.
//
// On 2026-08-15 this repo ran three adversarial-verification fan-outs. The
// refuters killed 2 of 232 and 3 of 507 candidate findings - under 1%. The
// strictness that mattered lived in the FINDER's ship-criteria, not in the
// reviewer. Separately, the session author shipped FOUR instances of defect
// classes he had personally catalogued hours earlier (comment-matching test
// pins, a falsifier that could not arm, a fixture on the wrong median
// convention, a duplicated string predicate). Every one was caught by the
// next layer down; none by the author at the time of writing.
//
// The conclusion is not "review harder". It is that AGREEMENT IS THE CHEAP
// DEFAULT and must be made structurally unavailable:
//   1. Panelists are assigned a POSITION TO ARGUE, not asked for an opinion.
//      You cannot rubber-stamp a thesis you were told to prosecute.
//   2. Every objection is CROSS-EXAMINED by a different lens that must
//      ESCALATE or WITHDRAW it - which kills rubber-stamping AND pile-on.
//   3. The output is a DOCKET, not a verdict. The author must record
//      CONCEDE / CONTEST / DEFER per objection, and a CONTEST requires
//      evidence, not confidence.
//   4. CONCESSION RATE IS THE HEALTH METRIC. 0% means the panel is theatre;
//      100% means the author stopped thinking. Track it across runs.
// ---------------------------------------------------------------------------

const A = (typeof args === 'object' && args) || {}
const TARGET = A.target || 'the working-tree diff (git diff HEAD)'
const CODE = A.code_root || String.raw`c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\liquidity-bot-isolation-2bd01a`
const DATA = A.data_root || String.raw`c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs`
const CLAIMS = (A.claims && A.claims.length)
  ? A.claims.map((c, i) => `  C${i + 1}. ${c}`).join('\n')
  : '  (none supplied - derive the author\'s claims from the diff and commit message,\n   and say which you derived, since an unstated claim is still a claim)'

const BASE = `
=== WHAT IS ON TRIAL ===
${TARGET}

=== THE AUTHOR'S CLAIMS (attack these specifically) ===
${CLAIMS}

=== ROOTS ===
CODE: ${CODE}
DATA: ${DATA}   <-- outputs/ lives ONLY here. A worktree's outputs/ is EMPTY, and
                    one agent's entire result was once VOID for missing this.
You are READ-ONLY. Write nothing.

=== BINDING LAW OF THIS REPO ===
* Kraken is the SOLE execution venue; moomoo/OKX/Binance.US/ccxt are read-only data.
* Exits are ALWAYS allowed. Anything that gates an exit is a SAFETY REGRESSION.
* MODEL FREEZE: no new families, features, meta-labeling.
* ERA-4 MORATORIUM: entry decisioning, position sizing, stop/exit geometry, the
  fill simulator, fee booking, and the order lifecycle are COHORT-RESETTING and
  forbidden without operator adjudication.
* Measurement standards are NOT tunables (the overfit row floor, SG_MIN_ROWS,
  era-4 n=50). Moving one so a gate reads "real" is gate-widening.
* Paper/DRY_RUN: every fill, fee and dollar is SIMULATED, never venue truth.

=== HOW TO OBJECT ===
An objection SHIPS only with: the exact claim or file:line it targets; what is
wrong; and EVIDENCE YOU GATHERED (a file you read, a number you recomputed, a
test you traced). "This might be fragile" is not an objection. "Line 704
already derives this and line 1105 derives it again; reword the string at 704
and 1105 silently stops firing" is.

YOU MAY NOT RETURN ZERO OBJECTIONS. If the change is genuinely sound, your
objection is the strongest ASSUMPTION it rests on and what would falsify it.
Softening, hedging, or "looks reasonable but" is a failed run.
`

const OBJ = {
  type: 'object', additionalProperties: false,
  required: ['lens', 'position_argued', 'objections'],
  properties: {
    lens: { type: 'string' },
    position_argued: { type: 'string' },
    objections: {
      type: 'array', minItems: 1,
      items: {
        type: 'object', additionalProperties: false,
        required: ['targets', 'objection', 'evidence', 'severity', 'demand'],
        properties: {
          targets: { type: 'string', description: 'claim id or file:line' },
          objection: { type: 'string' },
          evidence: { type: 'string', description: 'what you READ or RECOMPUTED' },
          severity: { type: 'string', enum: ['BLOCKING', 'SERIOUS', 'MINOR'] },
          demand: { type: 'string', description: 'what the author must do or prove' },
        },
      },
    },
  },
}

const XEX = {
  type: 'object', additionalProperties: false,
  required: ['ruling', 'reason'],
  properties: {
    ruling: { type: 'string', enum: ['ESCALATE', 'UPHOLD', 'WITHDRAW'] },
    reason: { type: 'string' },
    corrected_severity: { type: 'string' },
  },
}

// Five lenses. Each is grounded in a defect this repo actually shipped -
// generic personas produce generic objections.
const PANEL = [
  {
    key: 'RE-DERIVER',
    position: 'THE NUMBERS ARE WRONG.',
    brief: `Recompute EVERY figure the change or its message asserts, from the raw
artifact, by a route the author did not use. Do not accept a number because it
appears in a commit message, a report, or an agent's output.
GROUNDED IN: on 2026-08-15 two of three fan-out headline numbers failed
re-derivation - "fee-free negative on both statistics over 414" did not
reproduce, and "era-matched -15.83pp" measured -1.57pp. A falsifier built on
the first one refused to arm, which is how it was caught.
Ask of each number: which population? which era? nominal n or effective n?
does the median convention match (this repo takes sorted(x)[n//2], the UPPER
median)? Report BOTH values whenever yours differs.`,
  },
  {
    key: 'CLASS-DETECTIVE',
    position: 'THIS IS AN INSTANCE OF A DEFECT CLASS ALREADY CATALOGUED HERE.',
    brief: `Match the change against the classes this corpus has already named, and say
which one it repeats. Non-exhaustive, all with shipped specimens:
  * a check that CANNOT FAIL (a pin matching its own comment; a battery whose
    green does not entail the work ran; an assert on a value the test set)
  * ONE QUANTITY, TWO DERIVATIONS (a gauge computed differently from the
    decision it represents; a predicate copied instead of reused)
  * a SENTINEL read as a value (0.0, "", None, a non-numeric id in arithmetic)
  * a READER that WRITES (a constructor with side effects in an audit path)
  * FALSE INDEPENDENCE (a mean/CI over concurrent or pooled observations)
  * a number written into a file loaded every session, which then DECAYS
GROUNDED IN: the author shipped FOUR of these on the same day he catalogued
them. Assume this change is the fifth and go find it.`,
  },
  {
    key: 'LAW-READER',
    position: 'THE SAFE/SHIP-BLOCKED TAG IS WRONG, OR AN INVARIANT IS BREACHED.',
    brief: `Read the binding law above, then the diff, and argue the classification is
wrong. Anything that alters which orders are placed, how they fill, what the
model sees, fee booking, or label geometry is SHIP-BLOCKED - and mislabelling
one SAFE is the single disqualifying error, because a SAFE tag is what lets a
change skip operator adjudication.
Check specifically: does a "report-only" tool mutate anything? Does a default
argument leak a fenced behaviour into the default path? Does a docs change
alter a threshold by describing it differently? Would this mint an execution
era boundary?`,
  },
  {
    key: 'NULL-HYPOTHESIS',
    position: 'THIS CHANGE SHOULD NOT EXIST.',
    brief: `Argue for deletion. If the change were reverted entirely, what actually
breaks - name it concretely, or concede the change is optional.
Then: does this duplicate something already in the repo? GROUNDED IN: this
codebase already carries gate_efficacy_report, gate_truth_report,
cost_truth_report, defensive_cadence_report, cohort_eval, overfit_check,
quant_trials and breakeven_test. A ninth reporter beside eight is a cost, not
a feature, and one session was one edit away from writing it before prior art
stopped him.
Also argue the cheaper alternative: could a comment, a test, or a docs line
have done this? Is the author solving a problem or performing thoroughness?`,
  },
  {
    key: 'FUTURE-READER',
    position: 'THIS WILL DECAY INTO A FALSE CLAIM.',
    brief: `You are reading this in six months with no context. Argue that it now
misleads.
Hunt: measurements written into files loaded every session; comments naming
numbers that move; a docstring describing behaviour the code no longer has; a
test NAME that asserts more than the test body; a claim true only of the
corpus size on the day it was written.
GROUNDED IN: on 2026-08-15 a CLAUDE.md paragraph was written with the loaded
row count in it, and that count read 346, then 352, then 347 WITHIN THE HOUR -
the claim decayed before the commit landed. The corpus keeps a
documentation-drift register precisely because this recurs.
Also: what does this change make HARDER to discover for the next reader?`,
  },
]

phase('Prosecute')
const prosecuted = await parallel(PANEL.map((p) => () =>
  agent(`${BASE}\n\n=== YOUR LENS: ${p.key} ===\nPOSITION YOU MUST ARGUE: ${p.position}\n\n${p.brief}\n\n` +
    `You are not a reviewer. You are prosecuting an assigned position. Gather evidence first, then argue it.`,
    { label: `prosecute:${p.key}`, phase: 'Prosecute', schema: OBJ })
))

const raised = []
for (const r of prosecuted.filter(Boolean)) {
  for (const o of (r.objections || [])) raised.push({ ...o, lens: r.lens || 'unknown' })
}
log(`${raised.length} objections raised across ${prosecuted.filter(Boolean).length} lenses`)

// Cross-examination: a DIFFERENT lens rules on each objection. Withdrawal is
// as valuable as escalation - a panel that only escalates is pile-on, and a
// panel that only withdraws is the rubber stamp this exists to replace.
phase('CrossExam')
const ruled = await parallel(raised.slice(0, 20).map((o, i) => () => {
  const other = PANEL[(PANEL.findIndex((p) => p.key === o.lens) + 1 + i) % PANEL.length]
  return agent(
    `${BASE}\n\n=== CROSS-EXAMINATION ===\nYou hold the ${other.key} lens. Another panelist raised this:\n\n` +
    `TARGETS: ${o.targets}\nOBJECTION: ${o.objection}\nEVIDENCE CLAIMED: ${o.evidence}\n` +
    `SEVERITY: ${o.severity}\nDEMAND: ${o.demand}\n\n` +
    `Rule on it by READING the artifact yourself - do not reason from this summary.\n` +
    `  WITHDRAW - the evidence does not hold, the line does not say that, a guard or test\n` +
    `             already covers it, or it is style wearing defect language.\n` +
    `  UPHOLD   - it holds as stated.\n` +
    `  ESCALATE - it holds AND is worse than claimed; say why and correct the severity.\n` +
    `WITHDRAW is a valuable ruling. A panel that never withdraws is pile-on, and an\n` +
    `objection that survives a genuine attempt to kill it is worth far more than one\n` +
    `nobody tested.`,
    { label: `xexam:${(o.targets || '').slice(0, 20)}`, phase: 'CrossExam', schema: XEX, effort: 'high' })
    .then((v) => ({ o, v, judge: other.key }))
}))

const kept = ruled.filter(Boolean).filter((r) => r.v && r.v.ruling !== 'WITHDRAW')
const dropped = ruled.filter(Boolean).filter((r) => r.v && r.v.ruling === 'WITHDRAW')
log(`cross-exam: ${kept.length} survive, ${dropped.length} withdrawn`)

phase('Docket')
const RANK = { BLOCKING: 0, SERIOUS: 1, MINOR: 2 }
kept.sort((a, b) => (RANK[a.v.corrected_severity || a.o.severity] ?? 9)
  - (RANK[b.v.corrected_severity || b.o.severity] ?? 9))

const body = kept.map((r, i) =>
  `### OBJ-${i + 1} [${r.v.corrected_severity || r.o.severity}] [${r.o.lens} -> ${r.v.ruling} by ${r.judge}]\n` +
  `TARGETS: ${r.o.targets}\nOBJECTION: ${r.o.objection}\nEVIDENCE: ${r.o.evidence}\n` +
  `CROSS-EXAM: ${r.v.reason}\nDEMAND: ${r.o.demand}`).join('\n\n')

const docket = await agent(
  `${BASE}\n\n=== SURVIVING OBJECTIONS (${raised.length} raised, ${dropped.length} withdrawn on cross-exam) ===\n\n` +
  `${body || '(none survived - report that plainly and name the strongest assumption the change rests on)'}\n\n` +
  `=== YOUR TASK: WRITE THE DOCKET ===\nThis is NOT a verdict and you may not issue one. It is a list the author must answer.\nSections:\n` +
  `1. "## Docket" - numbered table: OBJ | severity | targets | the objection in one line | what the author must PROVE to contest it.\n` +
  `2. "## Withdrawn on cross-examination" - one line each, with WHY. This section is as important as the first: it is the evidence the panel was not piling on.\n` +
  `3. "## The single objection most likely to be right" - name one and say why it is the one to answer first.\n` +
  `4. "## What the panel could NOT assess" - honest residual for a read-only pass.\n\n` +
  `No approval language. No "looks good". The author's job is to answer this docket item by item with CONCEDE / CONTEST / DEFER, and a CONTEST requires evidence rather than confidence.`,
  { label: 'docket', phase: 'Docket', effort: 'high' })

return {
  objections_raised: raised.length,
  withdrawn_on_cross_exam: dropped.length,
  surviving: kept.length,
  by_severity: kept.reduce((a, r) => {
    const s = r.v.corrected_severity || r.o.severity
    return { ...a, [s]: (a[s] || 0) + 1 }
  }, {}),
  by_lens: kept.reduce((a, r) => ({ ...a, [r.o.lens]: (a[r.o.lens] || 0) + 1 }), {}),
  docket,
}
