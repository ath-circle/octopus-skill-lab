from apps.api.app.gating import evaluate_gate


def run(kind: str, score: float, baseline: float | None = None) -> dict:
    return {"dataset_type": kind, "split": "holdout", "status": "succeeded", "candidate_score": score, "baseline_score": baseline}


def test_gate_requires_functional_holdout() -> None:
    result = evaluate_gate([], personal_required=False)
    assert result.decision == "incomplete"
    assert result.summary["missing_holdout"] == ["functional"]


def test_gate_rejects_regression_even_above_threshold() -> None:
    result = evaluate_gate([run("functional", 0.9, 1.0)], personal_required=False)
    assert result.decision == "failed"
    assert "baseline_regression" in result.summary["failures"]


def test_gate_passes_required_personal_and_functional_holdouts() -> None:
    result = evaluate_gate([run("functional", 1.0, 1.0), run("personal", 0.8, 0.8)], personal_required=True)
    assert result.decision == "passed"
