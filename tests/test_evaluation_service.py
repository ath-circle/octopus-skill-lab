import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from apps.api.app.models import EvalCase, EvalDataset, EvalRun, EvalRunRequest, SkillVersion
from apps.api.app.services import EvaluationService


class LockedDatasetRepository:
    def __init__(self) -> None:
        self.skill_id, self.version_id, self.dataset_id = uuid4(), uuid4(), uuid4()
        self.lock_called = False

    async def get_version(self, version_id):
        return SkillVersion(id=self.version_id, skill_id=self.skill_id, version="0.2.0", layer_type="compiled", status="candidate", artifact_storage_path="x", artifact_hash="0" * 64, created_by_engine="fixture", created_at=datetime.now(UTC))

    async def get_dataset(self, dataset_id):
        return EvalDataset(id=self.dataset_id, skill_id=self.skill_id, name="locked", dataset_type="functional", split="holdout", version=1, parent_dataset_id=None, is_locked=True, created_at=datetime.now(UTC))

    async def lock_dataset(self, dataset_id):
        self.lock_called = True

    async def list_eval_cases(self, dataset_id):
        return [EvalCase(id=uuid4(), dataset_id=self.dataset_id, prompt="p", expected_output=None, expectations={"fixture_pass": True}, files=[], tags=[], source_evidence_id=None, created_at=datetime.now(UTC))]

    async def create_eval_run(self, values):
        return EvalRun(id=uuid4(), skill_version_id=self.version_id, baseline_version_id=None, dataset_id=self.dataset_id, engine="fixture", grader_metadata={}, status="running", summary={})

    async def create_eval_case_result(self, values): pass
    async def finish_eval_run(self, run_id, *, status, summary):
        return EvalRun(id=run_id, skill_version_id=self.version_id, baseline_version_id=None, dataset_id=self.dataset_id, engine="fixture", grader_metadata={}, status=status, summary=summary)
    async def list_eval_runs_for_version(self, version_id): return [{"id": "run", "status": "succeeded", "summary": {"candidate_score": 1.0}, "dataset_type": "functional", "split": "holdout", "baseline_version_id": None}]
    async def list_datasets(self, skill_id): return [await self.get_dataset(self.dataset_id)]
    async def create_gate_decision(self, values):
        from apps.api.app.models import EvalGateDecision
        return EvalGateDecision(id=uuid4(), skill_version_id=self.version_id, decision=values["decision"], policy=values["policy"], summary=values["summary"], created_at=datetime.now(UTC))
    async def set_version_status(self, version_id, status): pass


def test_evaluation_reuses_locked_holdout() -> None:
    repository = LockedDatasetRepository()
    run, gate = asyncio.run(EvaluationService(repository).run(EvalRunRequest(skill_version_id=repository.version_id, dataset_id=repository.dataset_id)))
    assert run.status == "succeeded"
    assert gate.decision == "passed"
    assert repository.lock_called is False
