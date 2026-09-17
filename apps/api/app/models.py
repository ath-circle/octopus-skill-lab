from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class LayerType(StrEnum):
    CORE = "core"
    DOMAIN = "domain"
    PERSONAL = "personal"
    COMPILED = "compiled"


class VersionStatus(StrEnum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    EVALUATING = "evaluating"
    PASSED = "passed"
    FAILED = "failed"
    ARCHIVED = "archived"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SkillCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=160)
    description: str = ""


class Skill(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class SkillVersion(BaseModel):
    id: UUID
    skill_id: UUID
    version: str
    layer_type: LayerType
    status: VersionStatus
    artifact_storage_path: str
    artifact_hash: str
    created_by_engine: str
    created_at: datetime
    promoted_at: datetime | None = None


class ImportResult(BaseModel):
    skill: Skill
    version: SkillVersion


class PromoteRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)
    manual_override: bool = False
    override_reason: str | None = Field(default=None, max_length=2000)


class RollbackRequest(BaseModel):
    target_release_id: UUID
    reason: str = Field(min_length=1, max_length=2000)


class Release(BaseModel):
    id: UUID
    skill_id: UUID
    skill_version_id: UUID
    environment: str
    release_state: str
    reason: str | None = None
    manual_override: bool
    override_reason: str | None = None
    released_at: datetime
    superseded_at: datetime | None = None
    rollback_from_release_id: UUID | None = None


class EvidenceType(StrEnum):
    DEMONSTRATION = "demonstration"
    CORRECTION = "correction"
    CHOICE = "choice"
    GOOD_EXAMPLE = "good_example"
    BAD_EXAMPLE = "bad_example"
    PREFERENCE = "preference"
    DECISION_RATIONALE = "decision_rationale"


class EvidenceCreate(BaseModel):
    evidence_type: EvidenceType
    title: str = Field(min_length=1, max_length=240)
    content: dict
    rationale: str | None = Field(default=None, max_length=10_000)
    rating: int | None = Field(default=None, ge=1, le=5)
    metadata: dict = Field(default_factory=dict)


class EvidenceItem(EvidenceCreate):
    id: UUID
    skill_id: UUID
    created_at: datetime
    archived_at: datetime | None = None


class EvalDatasetCreate(BaseModel):
    skill_id: UUID | None = None
    name: str = Field(min_length=1, max_length=240)
    dataset_type: str = Field(pattern=r"^(functional|personal|regression|generalization|trigger)$")
    split: str = Field(pattern=r"^(dev|holdout)$")
    version: int = Field(default=1, ge=1)
    parent_dataset_id: UUID | None = None


class EvalDataset(EvalDatasetCreate):
    id: UUID
    is_locked: bool
    created_at: datetime


class EvalCaseCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=50_000)
    expected_output: str | None = Field(default=None, max_length=100_000)
    expectations: dict = Field(default_factory=dict)
    files: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_evidence_id: UUID | None = None


class EvalCase(EvalCaseCreate):
    id: UUID
    dataset_id: UUID
    created_at: datetime


class EvalRunRequest(BaseModel):
    skill_version_id: UUID
    dataset_id: UUID
    baseline_version_id: UUID | None = None
    engine: str = Field(default="fixture", pattern=r"^fixture$")


class BatchEvalRequest(BaseModel):
    baseline_version_id: UUID | None = None
    engine: str = Field(default="fixture", pattern=r"^fixture$")


class EvalRun(BaseModel):
    id: UUID
    skill_version_id: UUID
    baseline_version_id: UUID | None = None
    dataset_id: UUID
    engine: str
    model: str | None = None
    grader_metadata: dict
    status: str
    summary: dict
    started_at: datetime | None = None
    finished_at: datetime | None = None


class EvalGateDecision(BaseModel):
    id: UUID
    skill_version_id: UUID
    decision: str
    policy: dict
    summary: dict
    created_at: datetime


class BatchEvalResult(BaseModel):
    runs: list[EvalRun]
    decision: EvalGateDecision


class Job(BaseModel):
    id: UUID
    job_type: str
    engine: str
    status: JobStatus
    input: dict
    output: dict | None = None
    workspace_path: str | None = None
    idempotency_key: str | None = None
    attempt_count: int
    lease_expires_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    created_at: datetime


class CreateJobRequest(BaseModel):
    engine: str = Field(default="fixture", min_length=1, max_length=80)
    input: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)


class RepoDistillRequest(CreateJobRequest):
    repo_url: str = Field(min_length=1, max_length=2_000)
    ref: str | None = Field(default=None, max_length=255)
    objective: str | None = Field(default=None, max_length=10_000)


class OpenWorldRequest(CreateJobRequest):
    brief: str = Field(min_length=1, max_length=20_000)
    skill_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    skill_name: str = Field(min_length=1, max_length=160)
    constraints: list[str] = Field(default_factory=list)


class PersonalizeRequest(CreateJobRequest):
    engine: str = Field(default="fixture", pattern=r"^(fixture|skillcreator|skillalchemy)$")
    baseline_version_id: UUID
    evidence_ids: list[UUID] = Field(min_length=1, max_length=100)
    dev_dataset_ids: list[UUID] = Field(default_factory=list, max_length=20)


class FuseRequest(CreateJobRequest):
    engine: str = Field(default="fixture", pattern=r"^(fixture|skillalchemy)$")
    source_version_ids: list[UUID] = Field(min_length=2, max_length=12)
    skill_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    skill_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=10_000)
    objective: str | None = Field(default=None, max_length=10_000)
