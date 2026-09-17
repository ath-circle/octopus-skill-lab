import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from apps.api.app.benchmark import BenchmarkCaseResult
from apps.api.app.models import EvalCase, EvalDataset, EvalRun, EvalRunRequest, SkillVersion
from apps.api.app.services import EvaluationService


class Repository:
    def __init__(self) -> None:
        self.skill_id, self.candidate_id, self.baseline_id, self.dataset_id = uuid4(), uuid4(), uuid4(), uuid4()
        self.results = []

    async def get_version(self, version_id):
        return SkillVersion(
            id=version_id, skill_id=self.skill_id,
            version="0.1.0" if version_id == self.baseline_id else "0.2.0",
            layer_type="compiled", status="candidate", artifact_storage_path=f"{version_id}.zip",
            artifact_hash="0" * 64, created_by_engine="fixture", created_at=datetime.now(UTC),
        )

    async def get_dataset(self, _):
        return EvalDataset(
            id=self.dataset_id, skill_id=self.skill_id, name="locked", dataset_type="functional",
            split="holdout", version=1, parent_dataset_id=None, is_locked=True, created_at=datetime.now(UTC),
        )

    async def lock_dataset(self, _):
        raise AssertionError("locked holdout must be reused")

    async def list_eval_cases(self, _):
        return [EvalCase(
            id=uuid4(), dataset_id=self.dataset_id, prompt="p", expected_output=None,
            expectations={"rubric": "correct"}, files=[], tags=[], source_evidence_id=None,
            created_at=datetime.now(UTC),
        )]

    async def create_eval_run(self, values):
        return EvalRun(
            id=uuid4(), skill_version_id=self.candidate_id, baseline_version_id=self.baseline_id,
            dataset_id=self.dataset_id, engine=values["engine"], grader_metadata=values["grader_metadata"],
            status="running", summary={},
        )

    async def create_eval_case_result(self, values):
        self.results.append(values)

    async def finish_eval_run(self, run_id, *, status, summary):
        return EvalRun(
            id=run_id, skill_version_id=self.candidate_id, baseline_version_id=self.baseline_id,
            dataset_id=self.dataset_id, engine="codex", grader_metadata={}, status=status, summary=summary,
        )

    async def list_eval_runs_for_version(self, _):
        return [{
            "id": "run", "status": "succeeded",
            "summary": {"candidate_score": 1.0, "baseline_score": 0.0},
            "dataset_type": "functional", "split": "holdout",
            "baseline_version_id": str(self.baseline_id),
        }]

    async def list_datasets(self, _):
        return [await self.get_dataset(self.dataset_id)]

    async def create_gate_decision(self, values):
        from apps.api.app.models import EvalGateDecision
        return EvalGateDecision(
            id=uuid4(), skill_version_id=self.candidate_id, decision=values["decision"],
            policy=values["policy"], summary=values["summary"], created_at=datetime.now(UTC),
        )

    async def set_version_status(self, *_):
        pass


class Artifacts:
    async def get(self, path):
        return path.encode()


class Benchmark:
    metadata = {"mode": "isolated-blind-codex"}

    async def run_case(self, **_):
        return BenchmarkCaseResult(
            candidate_output="candidate", baseline_output="baseline",
            candidate_output_path="candidate.txt", baseline_output_path="baseline.txt",
            candidate_pass=True, baseline_pass=False, candidate_score=0.9, baseline_score=0.2,
            winner="candidate", grader_output={"grader": "blind_codex"}, latency_ms=12,
        )


def test_codex_evaluation_reuses_locked_holdout_and_persists_comparison() -> None:
    repo = Repository()
    request = EvalRunRequest(
        skill_version_id=repo.candidate_id,
        dataset_id=repo.dataset_id,
        baseline_version_id=repo.baseline_id,
    )
    run, gate = asyncio.run(EvaluationService(repo, Artifacts(), Benchmark()).run(request))
    assert run.status == "succeeded"
    assert run.summary == {
        "case_count": 1, "candidate_score": 1.0, "baseline_score": 0.0,
        "candidate_wins": 1, "baseline_wins": 0, "ties": 0, "mode": "isolated-blind-codex",
    }
    assert gate.decision == "passed"
    assert repo.results[0]["grader_output"]["grader"] == "blind_codex"
    assert repo.results[0]["candidate_output_path"] == "candidate.txt"
    assert repo.results[0]["baseline_output_path"] == "baseline.txt"
