"""OF-1b null-model floor (2026-07-31 era-deadlock debate, item G).

A model that scores a WORSE OOF Brier than a constant predicting the
corpus base rate has negative skill: sizing on its p(win) is worse than
sizing on the base rate. Both debate arms measured exactly this on the
live corpus and NOTHING in the battery reported it - the system kept
saying "we need more labels" while the honest statement was "every rung
loses to the average". Measured at the fix on 1,780 OOF rows (base
0.247): logistic 0.2910, gbt 0.2382, mlp 0.2798 vs a 0.1861 null.

Report-only by design: gating here would block every deploy while the
model is cold - i.e. precisely while the operator is trying to fix it.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]


def _brier(p, y):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def test_null_floor_arithmetic_discriminates():
    """The comparison must actually separate a skilled model from an
    anti-informative one - not merely run."""
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.25).astype(float)
    base = y.mean()
    null = _brier(np.full_like(y, base), y)
    # a model that leaks the label a little must BEAT the null
    skilled = np.clip(0.25 + 0.5 * (y - 0.25), 0.01, 0.99)
    assert _brier(skilled, y) < null
    # an anti-informative model (confident and backwards) must LOSE
    backwards = np.clip(0.9 - 0.8 * y, 0.01, 0.99)
    assert _brier(backwards, y) > null


def test_overfit_check_emits_the_null_floor_per_family():
    src = (ROOT / "scripts" / "overfit_check.py").read_text(encoding="utf-8")
    assert 'null-floor[' in src, "per-family null floor must be reported"
    assert "brier_null" in src and "brier_model" in src
    assert "LOSES TO THE NULL" in src, "the failing case must be legible"
    # report-only: it must NOT be wired as a battery check()
    i = src.index("OF-1b")
    block = src[i:i + 2600]
    assert "info(f\"null-floor[" in block
    assert "check(f\"null-floor[" not in block, "must stay report-only"


def test_null_floor_uses_oof_predictions_not_in_sample():
    """An in-sample comparison would flatter the model and defeat the
    instrument."""
    src = (ROOT / "scripts" / "overfit_check.py").read_text(encoding="utf-8")
    i = src.index("OF-1b")
    block = src[i:i + 2600]
    assert 'g.get("oof_idx")' in block and 'g.get("oof_pred")' in block
