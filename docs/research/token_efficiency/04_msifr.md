# 04 — MSIFR: multi-stage in-flight rejection

**Citation**: Chowdhury, Zawad, Yan. "Know When To Fold 'Em: Token-Efficient LLM
Synthetic Data Generation via Multi-Stage In-Flight Rejection." arXiv:2605.14062v1, May
2026. Adjacent lineage: Sun et al., "Fast Best-of-N Decoding via Speculative Rejection",
NeurIPS 2024, arXiv:2410.20290 (reward-model early halting, 16-32x compute claim).

## Claims

- Low-quality generation trajectories can be terminated at intermediate checkpoints using
  training-free deterministic rule validators (no reward models).
- Four stages: S1 well-posedness gate on the problem; S2 mid-solution audit at 50% of
  expected length (hallucination phrases, premature/duplicate answer markers, arithmetic,
  magnitude sanity); S3 full-solution convergence validation; S4 final judge + dedup.
  Reject the moment stage score ≤ threshold lambda_t.
- Theory: any non-trivial discard policy reduces expected tokens; rejection does not bias
  retained-sample utility (under the assumption validators only fire on genuine faults).
- Orthogonal to early-exit decoding; composing compounds (~5x throughput w/ LYNX).

## Numbers

- **78.2% headline = MSIFR COMBINED with LYNX, on GSM8K only** — not standalone, not an
  average. Standalone range 11–77% by model×benchmark; floor 1.4% (DeepSeek-7B,
  MMLU-Chem).
- Standalone GSM8K best: 77.4% token cut with accuracy 0.734 vs 0.720 baseline (up).
- False-rejection <5% claimed — self-measured, no external audit.
- 7-8B models only; 50% checkpoint is a tuned constant; validator overhead never
  isolated.

## Limitations

- Validators are hand-crafted to math-benchmark format — fitted literals in this repo's
  vocabulary; re-derivation needed per domain. No sensitivity/plateau analysis on the 50%
  checkpoint (OF-4-shaped gap).
- No held-out validation of the rejection policy; no random-rejection null to separate
  "validators find faults" from "any pruning at matched rate helps".
- Task is synthetic data generation, not interactive inference; transfer of the numbers
  to agentic settings asserted nowhere.
- Headline grades as plausible-direction / unvalidated-magnitude under this repo's
  discipline.

## APPLICABILITY

- **Decoding-level / serving-stack composition (LYNX, speculative rejection): NOT
  APPLICABLE — we do not run inference infrastructure.**
- **Transferable idea: a mid-trajectory checkpoint for delegated agents.** S2's cheap
  auditor maps to a validator over a subagent's partial output — detect the
  "agent silently filling an under-determined spec" failure the delegated-measurement
  contract was written against; kill-and-respawn with a corrected spec at 50% is cheaper
  than grading a finished wrong answer → plan item 7 (experimental).
- rtk IS an in-flight rejection policy at the tool-output boundary: deterministic cheap
  rules discarding low-utility tokens before they reach context. The 1.4–77% per-cell
  spread predicts rtk savings must be read per command class, never as one number —
  `rtk gain --history` already supports this (and shows it: read 99%+ vs grep 23.9%).
- Earliest-stage rejection saves the most = direct support for USAGE.md rule i
  (prior-art Haiku pass BEFORE any design fan-out). Already law; keep.
- Structured outputs as S3-only validation = catching format faults at the most expensive
  point; deferred tool schemas validating on first use are the S1 analogue. Matches the
  existing setup.
- Fixed prefix tolls (catalog, instruction files) are the OPPOSITE cost class — prefix,
  not generation; MSIFR does nothing for them. Do not conflate the two waste channels.
- Any local adoption must A/B against a random-truncation null at matched rejection rate
  before crediting the validators.
