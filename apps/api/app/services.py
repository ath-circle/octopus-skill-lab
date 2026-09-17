from pathlib import PurePosixPath
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .artifacts import NormalizedArtifact, SkillArchiveNormalizer, SupabaseArtifactStore
from .gating import evaluate_gate
from .models import EvalCase, EvalGateDecision, EvalRun, EvalRunRequest, PromoteRequest, Release, Skill, SkillCreate, SkillVersion, VersionStatus
from .repository import SupabaseRegistryRepository


class LifecycleError(ValueError):
    pass


class LifecycleService:
    def __init__(
        self,
        repository: SupabaseRegistryRepository,
        artifacts: SupabaseArtifactStore,
        normalizer: SkillArchiveNormalizer,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.normalizer = normalizer

    async def import_skill(
        self,
        request: SkillCreate,
        archive: bytes,
        filename: str,
        *,
        created_by_engine: str = "import",
        source_type: str = "existing_skill",
        source_uri: str | None = None,
        repo_ref: str | None = None,
    ) -> tuple[Skill, SkillVersion]:
        skill_id = uuid4()
        return await self._store_import(
            skill_id=skill_id,
            request=request,
            archive=archive,
            filename=filename,
            version="0.1.0",
            create_skill=True,
            created_by_engine=created_by_engine,
            source_type=source_type,
            source_uri=source_uri or filename,
            repo_ref=repo_ref,
        )

    async def import_version(
        self, skill_id: UUID, version: str, archive: bytes, filename: str, *,
        created_by_engine: str = "import", source_uri: str | None = None,
    ) -> tuple[Skill, SkillVersion]:
        skill = await self.repository.get_skill(skill_id)
        if skill is None:
            raise LifecycleError("Skill was not found.")
        return await self._store_import(
            skill_id=skill.id,
            request=SkillCreate(slug=skill.slug, name=skill.name, description=skill.description),
            archive=archive,
            filename=filename,
            version=version,
            create_skill=False,
            existing_skill=skill,
            created_by_engine=created_by_engine,
            source_type="existing_skill",
            source_uri=source_uri or filename,
        )

    async def _store_import(
        self,
        *,
        skill_id: UUID,
        request: SkillCreate,
        archive: bytes,
        filename: str,
        version: str,
        create_skill: bool,
        existing_skill: Skill | None = None,
        created_by_engine: str,
        source_type: str,
        source_uri: str,
        repo_ref: str | None = None,
    ) -> tuple[Skill, SkillVersion]:
        artifact = self.normalizer.normalize(
            archive, skill_id=skill_id, slug=request.slug, name=request.name, version=version
        )
        storage_path = str(PurePosixPath(str(skill_id)) / version / "skill.zip")
        await self.artifacts.put(storage_path, artifact.archive)
        try:
            skill = (
                await self.repository.create_skill({"id": str(skill_id), **request.model_dump()})
                if create_skill
                else existing_skill
            )
            assert skill is not None
            version = await self.repository.create_version(
                {
                    "skill_id": str(skill.id),
                    "version": version,
                    "artifact_storage_path": storage_path,
                    "artifact_hash": artifact.sha256,
                    "created_by_engine": created_by_engine,
                }
            )
            source_id = await self.repository.create_source(
                {
                    "source_type": source_type,
                    "uri": source_uri,
                    "repo_ref": repo_ref,
                    "metadata": {"artifact_hash": artifact.sha256, "filename": filename},
                }
            )
            await self.repository.link_source(version.id, source_id)
            await self.repository.create_audit_event(
                {
                    "aggregate_type": "skill_version",
                    "aggregate_id": str(version.id),
                    "event_type": "skill.imported",
                    "payload": {"filename": filename, "artifact_hash": artifact.sha256},
                }
            )
        except Exception as exc:
            # The artifact remains safely immutable as an orphan for operator review; it is never overwritten.
            raise LifecycleError("Artifact uploaded, but registry registration failed. No existing Skill was changed.") from exc
        return skill, version

    async def promote(self, version_id: UUID, request: PromoteRequest) -> Release:
        version = await self.repository.get_version(version_id)
        if version is None:
            raise LifecycleError("Skill version was not found.")
        if version.status is not VersionStatus.PASSED and not request.manual_override:
            raise LifecycleError("Only a passed candidate can be promoted without an explicit manual override.")
        if request.manual_override and not request.override_reason:
            raise LifecycleError("A manual override requires an override reason.")
        return await self.repository.promote_version(
            version.id,
            reason=request.reason,
            manual_override=request.manual_override,
            override_reason=request.override_reason,
        )

    async def rollback(self, skill_id: UUID, target_release_id: UUID, reason: str) -> Release:
        return await self.repository.rollback_release(skill_id, target_release_id, reason)


class EvaluationService:
    """Deterministic V1 evaluator; model-based graders can replace it behind this contract."""

    def __init__(self, repository) -> None:
        self.repository = repository

    async def run(self, request: EvalRunRequest) -> tuple[EvalRun, EvalGateDecision]:
        candidate = await self.repository.get_version(request.skill_version_id)
        dataset = await self.repository.get_dataset(request.dataset_id)
        if candidate is None or dataset is None:
            raise LifecycleError("Skill version or evaluation dataset was not found.")
        if dataset.skill_id is not None and dataset.skill_id != candidate.skill_id:
            raise LifecycleError("Evaluation dataset belongs to another Skill.")
        if request.baseline_version_id:
            baseline = await self.repository.get_version(request.baseline_version_id)
            if baseline is None or baseline.skill_id != candidate.skill_id:
                raise LifecycleError("Baseline version must belong to the same Skill.")

        # First use freezes a dataset; later candidate runs must be able to reuse
        # the same immutable holdout rather than treating the lock as an error.
        if not dataset.is_locked:
            await self.repository.lock_dataset(dataset.id)
        cases = await self.repository.list_eval_cases(dataset.id)
        if not cases:
            raise LifecycleError("An evaluation dataset needs at least one case.")
        run = await self.repository.create_eval_run(
            {"skill_version_id": str(candidate.id), "baseline_version_id": str(request.baseline_version_id) if request.baseline_version_id else None,
             "dataset_id": str(dataset.id), "engine": request.engine, "grader_metadata": {"mode": "deterministic-fixture"},
             "status": "running", "started_at": datetime.now(UTC).isoformat()}
        )
        try:
            candidate_passes, baseline_passes = 0, 0
            for case in cases:
                candidate_pass, baseline_pass = self._fixture_result(case, bool(request.baseline_version_id))
                candidate_passes += candidate_pass
                baseline_passes += baseline_pass
                await self.repository.create_eval_case_result(
                    {"eval_run_id": str(run.id), "eval_case_id": str(case.id), "passed": candidate_pass,
                     "score": 1 if candidate_pass else 0,
                     "grader_output": {"grader": "fixture", "candidate_pass": candidate_pass, "baseline_pass": baseline_pass}}
                )
            summary = {"case_count": len(cases), "candidate_score": candidate_passes / len(cases),
                       "baseline_score": baseline_passes / len(cases) if request.baseline_version_id else None}
            run = await self.repository.finish_eval_run(run.id, status="succeeded", summary=summary)
        except Exception:
            await self.repository.finish_eval_run(run.id, status="failed", summary={})
            raise

        runs = await self.repository.list_eval_runs_for_version(candidate.id)
        datasets = await self.repository.list_datasets(candidate.skill_id)
        personal_required = any(item.dataset_type == "personal" and item.split == "holdout" for item in datasets)
        gate = evaluate_gate([
            {**item, "candidate_score": item["summary"].get("candidate_score", 0), "baseline_score": item["summary"].get("baseline_score")}
            for item in runs
        ], personal_required=personal_required)
        decision = await self.repository.create_gate_decision(
            {"skill_version_id": str(candidate.id), "decision": gate.decision, "policy": gate.policy, "summary": gate.summary}
        )
        await self.repository.set_version_status(candidate.id, "passed" if gate.decision == "passed" else ("failed" if gate.decision == "failed" else "candidate"))
        return run, decision

    async def run_holdouts(self, version_id: UUID, *, baseline_version_id: UUID | None, engine: str) -> tuple[list[EvalRun], EvalGateDecision]:
        candidate = await self.repository.get_version(version_id)
        if candidate is None:
            raise LifecycleError("Skill version was not found.")
        datasets = await self.repository.list_datasets(candidate.skill_id)
        holdouts = [item for item in datasets if item.split == "holdout"]
        if not holdouts:
            raise LifecycleError("Create at least one holdout dataset before evaluating a candidate.")
        runs: list[EvalRun] = []
        for dataset in holdouts:
            run, _ = await self.run(EvalRunRequest(
                skill_version_id=candidate.id, dataset_id=dataset.id, baseline_version_id=baseline_version_id, engine=engine
            ))
            runs.append(run)
        decision = await self.repository.get_latest_gate_decision(candidate.id)
        assert decision is not None
        return runs, decision

    @staticmethod
    def _fixture_result(case: EvalCase, has_baseline: bool) -> tuple[bool, bool]:
        expectations = case.expectations
        candidate = bool(expectations.get("fixture_candidate_pass", expectations.get("fixture_pass", True)))
        baseline = bool(expectations.get("fixture_baseline_pass", candidate)) if has_baseline else False
        return candidate, baseline
