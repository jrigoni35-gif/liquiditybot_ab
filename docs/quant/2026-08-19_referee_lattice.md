# The referee lattice — a feed-forward network with generational backprop

*2026-08-19. Drafted for the operator's llm-wiki vault
(`concepts/referee-lattice`); kept in-repo so the design and the code it
governs travel together. This answers the operator's request for "a hive
mind of analysis and learning, checked and checking others, leading from
it" — built as close to a neural network as the repo's law permits, and
the law turns out to be what makes the network shape work.*

## The request, and the one wire that must not exist

A hive mind where every node feeds every other is the mutual-network
topology, and this repo has already paid four incidents to learn its
failure mode: when a checker feeds the thing it checks, the check stops
measuring (gate-depends-on-what-it-blocks, 2026-08 coordination note;
"the readout never decides"; "alarms, never auto-tunes"; PBO on the
deployed rule, never argmax). So the lattice keeps every requested
property — many minds, mutual checking, learning, leadership — but
arranges them as a **directed acyclic graph**. Checking is mutual;
*feeding* is not.

## Topology

```
LAYER 0 — GROUND TRUTH (immutable streams)
  audit.jsonl   fills.csv   equity.csv   signal_history.csv
  postmortem_summary.csv    retrain_history.jsonl   recordings/
        |            (read-only, fan-out to every node above)
        v
LAYER 1 — ANALYSTS (independent referees; BLIND to each other)
  py.cohort_eval   py.gate_efficacy   py.overfit_battery   py.lessons
  py.learning_panel (runs the row concurrently)      cpp.diode (v1)
  [rust.diode — designed 2026-08-19, unbuilt]
        |            (each publishes NUMBERS + provenance, nothing else)
        v
LAYER 2 — CONSENSUS (the "checking others" layer)
  differential matrix: same quantity, N implementations, |delta| vs
  declared tolerance  ->  AGREE / FINDING per cell. An analyst is
  checked BY every other analyst's published numbers and checks them
  the same way — without ever reading another analyst's inputs or
  feeding one's outputs. Mutual checking, zero mutual feeding.
        |
        v
LAYER 3 — HEAD ("leading from it"): the operator
  adjudication docket: findings accumulate here with pre-registered
  decision criteria (the signed era-4 decision table is the template)
        |
        |  (the ONLY backward edge in the whole graph)
        v
LAYER L — THE LEARNER (exactly one)
  candidate labeling -> triple-barrier -> weighted corpus ->
  walk-forward champion -> Brier judge -> governor -> probes -> retrain
  (reads LAYER 0 only; observed by every analyst; observes none)
```

## Why this is "as close to a neural network as possible"

Read the lattice as a network, honestly:

- **Nodes and edges**: analysts are neurons; ground-truth streams are
  the input layer; the consensus matrix is a pooling layer; the
  operator is the output neuron. The forward pass runs continuously —
  every check-in, every panel run, every pc_status push.
- **The activation function is adjudication**: nothing propagates past
  Layer 3 without clearing a pre-registered threshold — exactly the
  role a nonlinearity plays: most signals die, the ones that clear the
  bar change downstream state.
- **Backpropagation exists but is GENERATIONAL**: weight updates — rule
  changes, geometry, model families — flow backward into the learner
  only at era boundaries, in batches, through the docket. Mid-era, the
  gradient accumulates (findings, the elimination read, ALGO-5
  evidence); at readout it applies in one step. One boundary per
  generation instead of seven per six weeks: the 2026-08-19 diode
  discussion, formalized.
- **What is deliberately NOT neural**: there is no continuous online
  weight update from evaluator to learner, because that edge is the one
  that destroys the referee property AND the era homogeneity the
  verdict gate depends on. The lattice trades update *speed* for
  update *truth* — the same trade pre-registration always makes.

## Where an actual neural network enters (the honest part)

Two facts before any NN romanticism:

1. **The bot already trains one.** `mlp` is a standing family in the
   retrain battery. On the 2026-08-18 live-corpus read it posted
   train/OOF gap +0.316 and OOF Brier 0.4350 against a base-rate null
   of 0.1649 — the deepest negative skill of the three families. The
   blocker on neural learning here is not architecture; it is ~600
   effective rows against 64 features and a 0.21 base rate. More
   hidden units cannot manufacture rows.
2. **New families are frozen** (2026-08-10 operator adjudication) until
   the era-4 readout. So the NN's legal entry point is the docket:
   pre-register the candidate NOW (architecture, feature set, OF-7 DoF
   budget, promotion gates), evaluate it AT the readout under the
   freeze-lift adjudication, alongside the pre-named ALGO-5. A
   candidate registered before its data exists inherits the full
   credibility of pre-registration — the same trick the era-4 gate
   itself uses.

Multiplying ANALYSTS is cheap and safe (each new referee adds a vote
against shared bugs; the C++ diode v1 is the first compiled one).
Multiplying LEARNERS is neither: every additional learner divides the
same starved corpus and multiplies degrees of freedom the overfit
battery must price. Hence the lattice's asymmetry — a hive of analysts
around exactly one learner — is not a compromise of the hive-mind idea;
at this corpus size it is its only working form.

## Build order (all SAFE-class except the last)

1. C++ diode v1 (this change): era-4 trips, corpus, ledger scan,
   differential harness vs the Python reference.
2. Consensus matrix: extend `scripts/learning_panel.py` with a
   differential section when a compiled diode's JSON is present
   (AGREE/FINDING per shared quantity). Analyst count becomes visible.
3. Rust diode per the 2026-08-19 analysis (label recomputation is its
   unique contribution — the one check no CSV-level referee can do).
4. NN candidacy registration in the era-4 docket (paper spec, no code).
5. Freeze-lift adjudication at readout — the only step that may touch
   the learner, and only through the head node. It is the operator's.
