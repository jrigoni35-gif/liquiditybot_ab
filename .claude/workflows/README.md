# `.claude/workflows/` — reusable multi-agent workflows

Invoke with `Workflow({name: "<file stem>", args: {...}})`.

---

## `red-team-panel` — make disagreement structural

**Use it before pushing anything you also wrote.** Especially when a prior
review came back clean, and especially after a long session.

```
Workflow({name: "red-team-panel", args: {
  target: "commit abc1234 — one line on what it does and how to inspect it",
  claims: ["the assertions you are making", "one per entry"],
}})
```

### The problem it solves, measured rather than assumed

On 2026-08-15 this repo ran three adversarial-verification fan-outs:

| run | candidates | killed by the **finders** | killed by the **refuters** |
|---|---:|---:|---:|
| preventive-maintenance scan | 232 | 215 | **2** (0.9%) |
| defect-class scan | 507 | 494 | **3** (0.6%) |

**Adversarial review, as conventionally implemented, killed under 1%.** The
strictness that did the work lived in the *finder's* ship-criteria.

Separately and on the same day, the session author shipped **four** instances
of defect classes he had personally catalogued hours earlier: test pins that
matched their own comments, a falsifier that could not arm, a fixture on the
wrong median convention, and a duplicated string predicate. Every one was
caught by the next layer down. **None by the author at the time of writing.**

The conclusion is not "review harder". It is that **agreement is the cheap
default**, and a reviewer who is *allowed* to agree usually will.

### The four mechanisms

1. **Mandated positions, not opinions.** Each panelist is assigned a thesis to
   prosecute. You cannot rubber-stamp a position you were told to argue.
2. **Cross-examination by a different lens.** Every objection must be
   `ESCALATE`d, `UPHOLD`ed or `WITHDRAW`n by a panelist who did not raise it.
   This kills rubber-stamping *and* pile-on. **A high withdrawal count is a
   healthy signal**, not a wasted run — it is the evidence the panel was not
   simply agreeing with itself in the other direction.
3. **The output is a docket, not a verdict.** The workflow is forbidden from
   issuing approval language. It returns objections the author must answer.
4. **Concession rate is the health metric.** The author records
   `CONCEDE / CONTEST / DEFER` per objection, and a `CONTEST` requires
   evidence, not confidence.
   - **0% conceded → the panel is theatre.** Either the prompts went soft or
     the author is rationalising. Investigate the run, not the code.
   - **100% conceded → the author stopped thinking.** Objections are not
     automatically right; several *should* be contested.
   - Track it across runs. It is the only number that says whether this tool
     is working.

### The five lenses

Each is grounded in a defect this repo actually shipped. Generic personas
produce generic objections, which is how "LGTM" survives a review process.

| lens | prosecutes | grounded in |
|---|---|---|
| **RE-DERIVER** | "the numbers are wrong" | 2 of 3 fan-out headline numbers failed re-derivation; a falsifier built on one refused to arm |
| **CLASS-DETECTIVE** | "this repeats a catalogued class" | four such instances shipped in one day |
| **LAW-READER** | "the SAFE tag is wrong" | mislabelling SAFE is the one disqualifying error — it is what lets a change skip adjudication |
| **NULL-HYPOTHESIS** | "this should not exist" | eight report tools already exist; one session was one edit from writing a ninth |
| **FUTURE-READER** | "this will decay into a false claim" | a CLAUDE.md number read 346, 352 and 347 within one hour — it decayed before the commit landed |

### Reading the result

`objections_raised`, `withdrawn_on_cross_exam`, `surviving`, `by_severity`,
`by_lens`, and the `docket` markdown.

**The docket is not closed until every objection has a recorded disposition.**
The workflow cannot make you answer it — that part is discipline, and saying
so plainly is more honest than pretending the tool enforces it.

### What it does not do

It is read-only, cannot run the test suite, and cannot judge whether a
*measurement* is true — only whether it reproduces. It is not a substitute for
the definition-of-done matrix, and a clean docket is not a green build.
