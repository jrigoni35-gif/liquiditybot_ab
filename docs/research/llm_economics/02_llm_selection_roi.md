# 02 — LLM Selection: Earnings and RoI, a Decision-Theoretic Model

**Citation:** Geraldo Xexeo, Filipe Braida, Marcus Parreiras, Paulo
Xavier (COPPE/UFRJ + CEFET/RJ), "The Economic Implications of Large
Language Model Selection on Earnings and Return on Investment: A
Decision Theoretic Model", arXiv:2405.17637, 27 May 2024. arXiv
preprint, no peer-reviewed venue found. (Hint title was garbled —
"...on Business Decision Making" vs actual — substance matches.)
Status: FOUND.

## Core claims

- LLM selection is a decision-theoretic economics problem, not a
  leaderboard problem: E[E] = G·P − L·(1−P) − C·T and
  E[R] = (G·P − L·(1−P))/(C·T) − 1 over cost/token C, tokens T,
  success probability P, gain G, loss L.
- Earnings and RoI can rank models OPPOSITELY: the accurate
  20×-more-expensive model wins absolute earnings, loses RoI; which
  metric governs depends on whether spend or opportunity volume binds.
- Sensitivity ordering (local partials + Sobol): P and G/L magnitudes
  dominate; token costs second-order when G,L ≫ C·T. dE/dP = G+L is
  the steepest lever.
- Classification variant splits P into TP/TN/FP/FN with asymmetric
  losses.
- Corollary: when C·T is tiny vs G/L, prompt-compression effort is
  near-worthless and can reduce returns if it dents P.

## Key numbers (all ILLUSTRATIVE — inputs assumed, not measured)

- Worked example: GPT-4o C=$10/1M, P=0.95; GPT-3.5-turbo C=$0.50/1M,
  P=0.80; T=1,000, G=$10, L=$1.
- GPT-4o: E[E]=$9.44/txn, RoI 944×. GPT-3.5: E[E]=$7.80, RoI 15,599× —
  20× cheaper, ~17% lower earnings, ~16.5× higher RoI.
- dE[E]/dP = G+L = $11 (dominant); dE[E]/dC = −T = −1000; dE[E]/dG = P.
- Sobol: P dominant; costs "small influence on earnings".
- RoI Hessian non-zero (nonlinear behavior) at tiny C (~5e-6..1e-7
  $/token per the paper) [extractor inference: local RoI sensitivity
  numerically delicate]. *(Corrected 2026-08-27: page previously wrote
  "makes the RoI Hessian ill-conditioned (authors' own note)" — the
  paper says only that the RoI Hessian "does not show a large number of
  zeros" vs the mostly-zero E[E] Hessian, and that C is usually very
  small; "ill-conditioned"/fragility was the extractor's inference
  misattributed to the authors.)*

## Limitations

- Authors: P conflates LLM task success with business-outcome success;
  omits network/RAG/fine-tune/latency costs.
- Extractor: tiny C makes local RoI sensitivity numerically fragile
  (moved here from the Authors bullet 2026-08-27 — extractor inference,
  not an authors' claim); zero empirical grounding — P=0.95/0.80 invented, so every
  headline number is illustration; contribution is the algebra and the
  sensitivity ordering only. No uncertainty on P — a point estimate
  treated as known, no n, no CI (the sin `overfit_check.py` exists to
  catch); a 0.95-vs-0.80 gap smaller than P's estimation error flips
  the ranking, and dE/dP=G+L makes P-error the dominant unmodeled
  risk. Static single-shot — no information value of transactions, no
  portfolio effects, no failure correlation. Framing paper, not
  evidence.

## GAP ANALYSIS

### ALREADY AHEAD

- **The repo runs this equation at trade level, with P from a
  mechanism, not an assumption.** `execution/pretrade.py:174-189`
  maker_p_fill_ev: ev = p_fill·(edge_bps − cost_bps) −
  (1−p_fill)·miss_cost_bps — structurally E[E] = P·(G−C) − (1−P)·L,
  with p_fill derived (exp(−dist/σ) with floor, pretrade.py:184-186).
- **The repo prices what the paper's static model omits — information
  value**: the exploration bypass (pretrade.py:205-211) deliberately
  takes negative-E[E] transactions to buy labels (raise future P).
- **Metric-choice trap already resolved our way**: the 944-vs-15,599
  RoI reversal is the ratio-metric trap CLAUDE.md's overfit discipline
  names ("optimizes NET profit or it doesn't ship", G3/G5). We gate on
  net dollars through the full cost stack (pretrade.py:274 onward);
  POWER-2's cost-tolerance bar (43 bps distinguishable / 118 bps point,
  vs 67.04 bps booked) is denominated in bps of notional, not a
  compressible ratio. Never import RoI as a selection metric anywhere
  the denominator is compressible.
- **Agent tiering already encodes the paper's sharpest lesson**:
  USAGE.md rules h–m tier DOWN (Haiku $1/$5 vs Fable $10/$50) only on
  mechanical tasks where P is tier-insensitive; the delegated-
  measurement contract exists because the 5-of-9-wrong-numbers
  incident is a live (1−P) estimate for under-specified cheap agents —
  the contract raises P at zero C, the highest-leverage move by the
  paper's own dE/dP = G+L ordering. Found empirically here before the
  paper said it.

### ADOPTABLE

- **Agent-spend ledger** (SAFE, measurement plane): log (model tier,
  effort, tokens in/out, task class, verified-correct?) per delegated
  agent — turns USAGE.md rule-j tiering from taste into the paper's
  E[E] comparison with MEASURED P. Placement: a measurement script
  beside the existing report tooling; never touches trading code or
  gates. Validation: double-derived counts per the delegated-
  measurement contract; no tier-down becomes policy until the P
  estimate's CI separates tiers.
- **Budgeted P-probes on cheap models**: copy the repo's own
  exploration-bypass pattern into agent spend — deliberate cheap-model
  probes per task class to MEASURE P instead of assuming it. Feeds the
  ledger above; SAFE.

### NOT APPLICABLE

- The worked-example numbers (9.44 / 7.80 / 944 / 15,599) — invented
  inputs, May-2024 list prices; cite nothing.
- The binary-classification variant — our label pipeline already has
  asymmetric cost handling through the sizing/risk stack; nothing to
  bolt on.
- RoI as governing metric — rejected above, with the repo's mechanism
  as the reason.
