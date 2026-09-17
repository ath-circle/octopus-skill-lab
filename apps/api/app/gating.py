from dataclasses import dataclass
from typing import Any


PASS_THRESHOLD = 0.8


@dataclass(frozen=True)
class GateDecision:
    decision: str
    policy: dict[str, Any]
    summary: dict[str, Any]


def evaluate_gate(runs: list[dict[str, Any]], *, personal_required: bool) -> GateDecision:
    """Evaluate holdout results only; dev evaluations never release a version."""
    policy = {"functional_holdout_min": PASS_THRESHOLD, "personal_holdout_min": PASS_THRESHOLD, "must_not_regress": True}
    eligible = [run for run in runs if run["split"] == "holdout" and run["status"] == "succeeded"]
    categories = {kind: [run for run in eligible if run["dataset_type"] == kind] for kind in ("functional", "personal")}
    missing = ["functional"] if not categories["functional"] else []
    if personal_required and not categories["personal"]:
        missing.append("personal")
    if missing:
        return GateDecision("incomplete", policy, {"missing_holdout": missing, "runs": eligible})

    failures: list[str] = []
    for kind, threshold in (("functional", PASS_THRESHOLD), ("personal", PASS_THRESHOLD)):
        if categories[kind] and any(float(run["candidate_score"]) < threshold for run in categories[kind]):
            failures.append(f"{kind}_threshold")
    regressions = [run for run in eligible if run.get("baseline_score") is not None and float(run["candidate_score"]) < float(run["baseline_score"])]
    if regressions:
        failures.append("baseline_regression")
    return GateDecision("failed" if failures else "passed", policy, {"failures": failures, "runs": eligible})
