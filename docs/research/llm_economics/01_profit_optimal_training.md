# 01 — A Theory of Training Profit-Optimal LLMs

**Citation:** Sophie Hao (Boston University) & William Merrill (Allen
Institute for AI), "A Theory of Training Profit-Optimal LLMs",
arXiv:2605.16430 [cs.LG], v1 2026-05-14, v3 2026-06-11.
https://arxiv.org/abs/2605.16430. Status: FOUND.

## Core claims

- Extends compute-optimal (Chinchilla) scaling to PROFIT-optimal
  training: Leontief quality law q(n,d)=min{a·n^α, b·d^β} coupled to a
  microeconomic demand model (power-law reservation-quality density
  1/q*^(1+γ); monopolist maximizes revenue minus training+inference
  compute cost).
- Compute-bound regime: profit-optimal training spend grows
  SUB-quadratically in hardware efficiency E for γ > −1; at γ=0
  (log-quasilinear demand) n*, d*, C*_train all scale LINEARLY in E.
- Data-bound regime (tokens capped at D): optimal spend
  ~D^(1+β/α)/(ρE) — quadratic-ish in available data, DECREASING in
  hardware efficiency. Better hardware lowers optimal spend when data
  is the binding constraint.
- Data-efficiency gains raise profit-optimal training spend;
  parameter-efficiency effects sign-ambiguous (depends on γ).
- Calibration vs Epoch.ai: observed 5×/yr training-compute growth
  exceeds profit-optimality at baseline γ=0 (~4.11^t permitted);
  rationalizable only at γ̂ ≈ −0.77 or continued joint
  hardware+algorithmic exponential growth with abundant data.

## Key numbers

- α ≈ β ≈ 0.3 (Chinchilla); implied elasticity of substitution σ ≈ 0.76.
- Thm 1 (γ≠0, compute-bound): n* = O((E/(ρa^γ))^(1/(1+αγ))); at α=0.3,
  γ=−1: n*,d* ≲ E^1.43, C*_train ≲ E^1.86.
- Thm 2 (γ=0): n* = O(aE/ρ), d* = O(aE), C*_train = O(a²E/ρ) — linear in E.
- Thm 3 (data-bound, d ≤ D): n* = ρ⁻¹·D^(β/α), d* = D,
  C*_train = Θ(D^(1+β/α)/(ρE)).
- Trend inputs (Epoch.ai): compute ~5^t/yr, E ~1.37^t, algorithmic
  efficiency ~√(3^t). Breakeven γ̂ ≈ −0.77. Spend bounds: γ=−1 permits
  ≲7.59^t; γ=0 permits ≲4.11^t (observed 5^t exceeds); hardware
  stagnation + γ=−1 still permits ≲4.66^t.
- All headline results asymptotic O/Θ — no CIs, no residuals, no
  out-of-sample test; only "n" is the Epoch.ai trend series.

## Limitations

- Authors: monopoly market; Leontief min{} idealizes Chinchilla; needs
  γ ≥ −1; no recursive self-improvement; training data free; inference
  cost linear in n; binary consumer thresholds; demand linking f(q)
  never measured — calibration is assumption-laden.
- Extractor: zero empirical demand data — γ̂ ≈ −0.77 "reconciliation"
  is an identification exercise, not evidence (any spend trend is
  rationalizable by picking γ); asymptotics suppress constants, so no
  actionable dollar figure; one-directional validation is
  unfalsifiable in-sample — analogous to fitting a selection rule to
  the backtest peak (the shape OF-4 forbids).
- No leakage concerns in the strategy-paper sense (pure theory), but
  the calibration-to-trend step has unregistered-backtest epistemics:
  parameters chosen after seeing the data they explain.

## GAP ANALYSIS

### ALREADY AHEAD

- **Data-bound capacity admission is Thm 3, implemented.**
  `ml/walkforward.py:64-92` admits higher-capacity model families ONLY
  at a minimum sample-per-effective-parameter, logistic always
  baseline. The paper's result that optimal model size is set by D
  (n* ~ D^(β/α)), not by available compute, is the external theoretical
  justification for that gate. At a ~200-label live corpus the bot is
  firmly data-bound: cheaper compute does NOT justify bigger models.
- **The era-4 model freeze** (2026-08-10 adjudication, CLAUDE.md
  moratorium: no new families/features/meta-labeling) is the
  profit-rational posture in the paper's data-bound regime — model-side
  spend has no return until D grows.
- **Selection under scarcity is already profit-shaped, not
  compute-shaped**: the simplicity ladder with PBO measured on the
  DEPLOYED rule (`scripts/overfit_check.py:877-903`), never argmax.
- **Evaluation standard exceeds the paper's own**: its calibration is
  in-sample parameter-picking; our battery (OF-2 shuffle-null, OF-3
  PBO, OF-4 plateau, OF-5 DSR) exists specifically to reject that move.

### ADOPTABLE

- **Doctrinal citation only** — a vault concepts-page reference
  (canonical vault, `wiki/`) for why the ladder's data-floor and the
  model freeze are profit-rational in a data-bound regime. Placement:
  wiki, SAFE. No code target; no validation gate needed because
  nothing numeric is imported.
- **Agent-spend framing** (USAGE.md h–m): compute-bound tasks
  (grep/inventory) → spend tracks efficiency, use Haiku (Thm 2 shape);
  data-bound tasks (synthesis/judging in scarce context) → quality is
  the binding constraint, pay for the session model. Thm 3's inversion
  is the formal "don't buy a bigger fan-out when the vault already
  holds the answer" (rule h). Already operator law; the paper adds
  vocabulary, not policy.

### NOT APPLICABLE

- α=β=0.3 and every other constant — LLM loss exponents, unrelated to
  trade-label learnability; import nothing numeric.
- Monopolist demand model — no analog in a price-taking liquidity bot.
- γ̂ ≈ −0.77 calibration — unvalidated by this repo's standard;
  relaxes no gate.
