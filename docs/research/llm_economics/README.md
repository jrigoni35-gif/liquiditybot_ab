# LLM economics literature — vs this repo's standards

Purpose: graded literature pass on LLM training/selection economics and
LLM-agent trading evaluation, measured against this repo's own bars —
era-4 pre-registration, the OF-1..OF-7 overfit battery (PBO on the
DEPLOYED rule, never argmax), effective-n reporting
(`gate_truth_report.py` since 2026-07-29, `cohort_eval.py` since
2026-08-15), the POWER-2 cost-tolerance bar (43 bps demanding
distinguishability / 118 bps point estimate, vs 67.04 bps booked), and
the operator's agent-spend tiering law (USAGE.md rules h–m: recall
before fan-out, prior-art pass first, model-per-task tiering, effort
tiering, cache-the-prefix, Batch API offline).

Each page: citation, claims, numbers, limitations, then GAP ANALYSIS
(ALREADY AHEAD / ADOPTABLE / NOT APPLICABLE). Everything ADOPTABLE is
SAFE-class only — the era-4 moratorium and the 2026-08-10 model freeze
forbid decision-path or model-family changes until the gate readout.

All four papers FOUND. Extraction date 2026-08-27. Paper 03 is
abstract-only (MDPI full text 403-blocked on every route) — flagged on
its page; its numbers are unread-methods claims.

## Status

| paper | status | citation | one-line verdict |
|---|---|---|---|
| 01 Profit-optimal LLM training | FOUND | Hao & Merrill, arXiv:2605.16430 (2026) | Pure theory; data-bound regime (Thm 3) is the formal case for our capacity-admission floor; import zero constants |
| 02 LLM selection RoI | FOUND | Xexeo et al., arXiv:2405.17637 (2024) | Algebra we already run at trade level (`pretrade.py` EV gate); lesson: dE/dP=G+L dominates cost — tier down only where P is tier-insensitive |
| 03 Integrated BI framework | FOUND (abstract only) | Theodorakopoulos et al., BDCC 10(4):110 (2026), DOI 10.3390/bdcc10040110 | Anti-pattern specimen: five simultaneous wins, no visible holdout; nothing to adopt, cite as how-not-to-report |
| 04 FINSABER | FOUND | Li, Kim, Cucuringu, Ma, KDD 2026 / arXiv:2505.07078 | Empirical vindication of breadth+span evaluation; LLM timing agents lose to B&H/ARIMA over 20y; confirms our no-LLM-in-decision-loop rejection |

## Pages

- `01_profit_optimal_training.md`
- `02_llm_selection_roi.md`
- `03_integrated_bi.md`
- `04_finsaber.md` (includes FINSABER-vs-repo standards-compliance table)
