from functools import lru_cache
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .artifacts import ArtifactValidationError, SkillArchiveNormalizer, SupabaseArtifactStore
from .config import Settings, get_settings
from .models import (
    CreateJobRequest,
    BatchEvalRequest,
    BatchEvalResult,
    EvalCase,
    EvalCaseCreate,
    EvalDataset,
    EvalDatasetCreate,
    EvalGateDecision,
    EvalRun,
    EvalRunRequest,
    EvidenceCreate,
    EvidenceItem,
    ImportResult,
    Job,
    OpenWorldRequest,
    PersonalizeRequest,
    PromoteRequest,
    Release,
    RepoDistillRequest,
    RollbackRequest,
    Skill,
    SkillCreate,
    SkillVersion,
)
from .repository import RepositoryError, SupabaseRegistryRepository
from .services import EvaluationService, LifecycleError, LifecycleService
from .safety import redact_secrets

app = FastAPI(title="Skill Factory API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@lru_cache
def get_service() -> LifecycleService:
    settings = get_settings()
    return LifecycleService(
        SupabaseRegistryRepository(settings),
        SupabaseArtifactStore(settings),
        SkillArchiveNormalizer(settings.artifact_max_bytes),
    )


@lru_cache
def get_evaluation_service() -> EvaluationService:
    return EvaluationService(get_service().repository)


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ArtifactValidationError, LifecycleError)):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, RepositoryError):
        return HTTPException(status_code=502, detail="The registry is currently unavailable.")
    return HTTPException(status_code=500, detail="Unexpected lifecycle failure.")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/skills", response_model=list[Skill])
async def list_skills(service: LifecycleService = Depends(get_service)) -> list[Skill]:
    try:
        return await service.repository.list_skills()
    except Exception as exc:
        raise translate_error(exc) from exc


async def queue_job(job_type: str, request: CreateJobRequest, service: LifecycleService) -> Job:
    try:
        if request.idempotency_key:
            existing = await service.repository.get_job_by_idempotency_key(request.idempotency_key)
            if existing is not None:
                return existing
        job = await service.repository.create_job(
            {
                "job_type": job_type,
                "engine": request.engine,
                "input": request.input,
                "idempotency_key": request.idempotency_key,
            }
        )
        await service.repository.create_audit_event(
            {"aggregate_type": "job", "aggregate_id": str(job.id), "event_type": "job.queued", "payload": {"type": job_type}}
        )
        return job
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/jobs/distill/repo", response_model=Job, status_code=201)
async def queue_repo_distillation(
    request: RepoDistillRequest, service: LifecycleService = Depends(get_service)
) -> Job:
    payload = {"repo_url": request.repo_url, "ref": request.ref, "objective": request.objective}
    return await queue_job("distill_repo", request.model_copy(update={"input": payload}), service)


@app.post("/jobs/distill/open-world", response_model=Job, status_code=201)
async def queue_open_world_creation(
    request: OpenWorldRequest, service: LifecycleService = Depends(get_service)
) -> Job:
    payload = {
        "brief": request.brief,
        "skill_slug": request.skill_slug,
        "skill_name": request.skill_name,
        "constraints": request.constraints,
    }
    return await queue_job("distill_open_world", request.model_copy(update={"input": payload}), service)


@app.post("/jobs/personalize", response_model=Job, status_code=201)
async def queue_personalization(request: PersonalizeRequest, service: LifecycleService = Depends(get_service)) -> Job:
    """Queue a candidate-only revision from selected evidence and dev examples."""
    try:
        baseline = await service.repository.get_version(request.baseline_version_id)
        if baseline is None:
            raise HTTPException(status_code=404, detail="Baseline Skill version was not found.")
        evidence = await service.repository.get_evidence_by_ids(baseline.skill_id, request.evidence_ids)
        if {item.id for item in evidence} != set(request.evidence_ids):
            raise HTTPException(status_code=422, detail="Every selected evidence item must belong to the baseline Skill.")
        dev_examples = []
        for dataset_id in request.dev_dataset_ids:
            dataset = await service.repository.get_dataset(dataset_id)
            if dataset is None or dataset.skill_id != baseline.skill_id or dataset.split != "dev":
                raise HTTPException(status_code=422, detail="Personalization accepts only dev datasets from the baseline Skill.")
            dev_examples.extend((await service.repository.get_dev_eval_cases(dataset_id)))
        payload = {
            "baseline_version_id": str(baseline.id), "skill_id": str(baseline.skill_id),
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "dev_examples": [item.model_dump(mode="json") for item in dev_examples],
        }
        return await queue_job("personalize", request.model_copy(update={"input": payload}), service)
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc) from exc


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: UUID, service: LifecycleService = Depends(get_service)) -> Job:
    try:
        job = await service.repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job was not found.")
        return job
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc) from exc


@app.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: UUID, service: LifecycleService = Depends(get_service)) -> dict[str, str]:
    try:
        job = await service.repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job was not found.")
        if not job.workspace_path:
            return {"stdout": "", "stderr": ""}
        workspace = Path(job.workspace_path).resolve()
        root = Path(get_settings().workspace_root).resolve()
        if root not in workspace.parents:
            raise HTTPException(status_code=422, detail="Job workspace path is unsafe.")
        def read_log(filename: str) -> str:
            path = workspace / "logs" / filename
            return redact_secrets(path.read_text(errors="replace")[-100_000:]) if path.is_file() else ""
        return {"stdout": read_log("stdout.log"), "stderr": read_log("stderr.log")}
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc) from exc


@app.get("/settings/engines")
async def engine_health() -> dict[str, dict[str, str | bool]]:
    from adapters.arex import ArexDiscoAdapter
    from adapters.fixture import FixtureSkillEngine
    from adapters.skillalchemy import SkillAlchemyAdapter

    settings = get_settings()
    adapters = {
        "fixture": FixtureSkillEngine(),
        "arex": ArexDiscoAdapter(settings.arex_disco_bin),
        "skillalchemy": SkillAlchemyAdapter(settings.skillalchemy_agent_bin),
    }
    health = {}
    for engine, adapter in adapters.items():
        result = await adapter.healthcheck()
        health[engine] = {"available": result.available, "detail": result.detail}
    return health


@app.get("/skills/{skill_id}/versions", response_model=list[SkillVersion])
async def list_versions(skill_id: UUID, service: LifecycleService = Depends(get_service)) -> list[SkillVersion]:
    try:
        return await service.repository.list_versions(skill_id)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.get("/skills/{skill_id}/evidence", response_model=list[EvidenceItem])
async def list_evidence(skill_id: UUID, service: LifecycleService = Depends(get_service)) -> list[EvidenceItem]:
    try:
        if await service.repository.get_skill(skill_id) is None:
            raise HTTPException(status_code=404, detail="Skill was not found.")
        return await service.repository.list_evidence(skill_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/skills/{skill_id}/evidence", response_model=EvidenceItem, status_code=201)
async def create_evidence(
    skill_id: UUID, request: EvidenceCreate, service: LifecycleService = Depends(get_service)
) -> EvidenceItem:
    try:
        if await service.repository.get_skill(skill_id) is None:
            raise HTTPException(status_code=404, detail="Skill was not found.")
        evidence = await service.repository.create_evidence({"skill_id": str(skill_id), **request.model_dump(mode="json")})
        await service.repository.create_audit_event(
            {"aggregate_type": "evidence_item", "aggregate_id": str(evidence.id), "event_type": "evidence.created", "payload": {"skill_id": str(skill_id), "type": evidence.evidence_type}}
        )
        return evidence
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc) from exc


@app.get("/eval-datasets", response_model=list[EvalDataset])
async def list_datasets(skill_id: UUID | None = None, service: LifecycleService = Depends(get_service)) -> list[EvalDataset]:
    try:
        return await service.repository.list_datasets(skill_id)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/eval-datasets", response_model=EvalDataset, status_code=201)
async def create_dataset(request: EvalDatasetCreate, service: LifecycleService = Depends(get_service)) -> EvalDataset:
    try:
        if request.skill_id and await service.repository.get_skill(request.skill_id) is None:
            raise HTTPException(status_code=404, detail="Skill was not found.")
        return await service.repository.create_dataset(request.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/eval-datasets/{dataset_id}/cases", response_model=EvalCase, status_code=201)
async def create_eval_case(
    dataset_id: UUID, request: EvalCaseCreate, service: LifecycleService = Depends(get_service)
) -> EvalCase:
    try:
        dataset = await service.repository.get_dataset(dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Evaluation dataset was not found.")
        if dataset.is_locked:
            raise HTTPException(status_code=422, detail="Locked evaluation datasets are immutable.")
        return await service.repository.create_eval_case({"dataset_id": str(dataset_id), **request.model_dump(mode="json")})
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/eval-runs", response_model=EvalRun)
async def run_evaluation(
    request: EvalRunRequest, evaluator: EvaluationService = Depends(get_evaluation_service)
) -> EvalRun:
    try:
        run, _ = await evaluator.run(request)
        return run
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/versions/{version_id}/evaluate-holdouts", response_model=BatchEvalResult)
async def evaluate_holdouts(
    version_id: UUID, request: BatchEvalRequest, evaluator: EvaluationService = Depends(get_evaluation_service)
) -> BatchEvalResult:
    try:
        runs, decision = await evaluator.run_holdouts(
            version_id, baseline_version_id=request.baseline_version_id, engine=request.engine
        )
        return BatchEvalResult(runs=runs, decision=decision)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.get("/versions/{version_id}/eval-summary", response_model=EvalGateDecision | None)
async def eval_summary(version_id: UUID, service: LifecycleService = Depends(get_service)) -> EvalGateDecision | None:
    try:
        return await service.repository.get_latest_gate_decision(version_id)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.get("/skills/{skill_id}/releases", response_model=list[Release])
async def list_releases(skill_id: UUID, service: LifecycleService = Depends(get_service)) -> list[Release]:
    try:
        return await service.repository.list_releases(skill_id)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/skills/import", response_model=ImportResult, status_code=201)
async def import_skill(
    archive: UploadFile = File(...),
    slug: str = Form(..., pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
    name: str = Form(..., min_length=1, max_length=160),
    description: str = Form(""),
    service: LifecycleService = Depends(get_service),
) -> ImportResult:
    try:
        skill, version = await service.import_skill(
            request=SkillCreate(slug=slug, name=name, description=description),
            archive=await archive.read(),
            filename=archive.filename or "uploaded-skill.zip",
        )
        return ImportResult(skill=skill, version=version)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/skills/{skill_id}/versions/import", response_model=ImportResult, status_code=201)
async def import_version(
    skill_id: UUID,
    archive: UploadFile = File(...),
    version: str = Form(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$"),
    service: LifecycleService = Depends(get_service),
) -> ImportResult:
    try:
        skill, skill_version = await service.import_version(
            skill_id=skill_id,
            version=version,
            archive=await archive.read(),
            filename=archive.filename or "uploaded-skill.zip",
        )
        return ImportResult(skill=skill, version=skill_version)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/versions/{version_id}/promote", response_model=Release)
async def promote(
    version_id: UUID, request: PromoteRequest, service: LifecycleService = Depends(get_service)
) -> Release:
    try:
        return await service.promote(version_id, request)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.post("/skills/{skill_id}/rollback", response_model=Release)
async def rollback(
    skill_id: UUID, request: RollbackRequest, service: LifecycleService = Depends(get_service)
) -> Release:
    try:
        return await service.rollback(skill_id, request.target_release_id, request.reason)
    except Exception as exc:
        raise translate_error(exc) from exc


@app.get("/versions/{version_id}/export")
async def export(version_id: UUID, service: LifecycleService = Depends(get_service)) -> Response:
    try:
        version = await service.repository.get_version(version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="Skill version was not found.")
        archive = await service.artifacts.get(version.artifact_storage_path)
        return Response(
            archive,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{version_id}-{version.version}.zip"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise translate_error(exc) from exc
