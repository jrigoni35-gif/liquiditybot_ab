"""scripts/calling_card.py: the bot's self-introduction must be composed
from real telemetry, degrade gracefully when files are absent, and never
overstate (calibrated verdicts track the actual Brier)."""
import json

from scripts.calling_card import compose


def _setup(o):
    (o / "status.json").write_text(json.dumps({
        "regimes": {"BTC": {}, "ETH": {}, "SUI": {}},
        "ml": {"model_kind": "ensemble_mlp", "history_rows": 40},
        "monitor": {"level": 1},
    }), encoding="utf-8")
    (o / "meta_model.json").write_text(json.dumps({
        "kind": "ensemble_mlp", "oof_brier": 0.157,
        "calibration": {"x": [0.1], "y": [0.1]},
        "wf_importance": [["mom_dir", 0.13], ["ret_6_dir", 0.08]],
    }), encoding="utf-8")
    import csv
    with open(o / "signal_history.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["asset", "source", "label"])
        w.writerow(["BTC", "live", "1"])
        w.writerow(["BTC", "candidate", "0"])
    (o / "audit.jsonl").write_text("a\nb\nc\n", encoding="utf-8")


def test_introduction_is_backed_by_telemetry(tmp_path):
    _setup(tmp_path)
    card = compose(str(tmp_path))
    assert "An introduction." in card
    assert "3 markets" in card                      # regime count
    assert "0.157" in card and "sharper than a coin" in card
    assert "longer-horizon momentum" in card        # top insight, humanized
    assert "deliberately throttled" in card         # governor level 1
    assert "1 live trade" in card                   # exactly one live row
    assert "3 records" in card                       # audit line count


def test_weak_model_is_stated_honestly(tmp_path):
    _setup(tmp_path)
    (tmp_path / "meta_model.json").write_text(json.dumps(
        {"kind": "logistic", "oof_brier": 0.31}), encoding="utf-8")
    card = compose(str(tmp_path))
    assert "still finding its feet" in card          # no overstatement
    assert "sharper than a coin" not in card


def test_no_outputs_still_composes_without_crashing(tmp_path):
    card = compose(str(tmp_path))                    # empty dir
    assert "An introduction." in card
    assert "worth an introduction" in card
