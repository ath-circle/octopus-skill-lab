from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from .config import Settings
from .models import (
    EvalCase,
    EvalDataset,
    EvalGateDecision,
    EvalRun,
    EvidenceItem,
    Execution,
    Job,
    Release,
    Skill,
    SkillVersion,
)


class RepositoryError(RuntimeError):
    pass


class SupabaseRegistryRepository:
    """Small PostgREST adapter; Supabase remains storage, not domain logic."""

    def __init__(self, settings: Settings) -> None:
        self.base_url = f"{settings.supabase_url}/rest/v1"
        self.headers = {
            "apikey": settings.spb_secret_key,
            "Authorization": f"Bearer {settings.spb_secret_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self, method: str, table: str, *, params: dict[str, str] | None = None, json: Any = None, prefer: str | None = None
    ) -> list[dict[str, Any]]:
        headers = self.headers if prefer is None else {**self.headers, "Prefer": prefer}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, f"{self.base_url}/{table}", params=params, json=json, headers=headers)
        if response.is_error:
            raise RepositoryError(f"Supabase request to {table} failed ({response.status_code}).")
        if not response.content:
            return []
        payload = response.json()
        return payload if isinstance(payload, list) else [payload]

    async def create_skill(self, values: dict[str, Any]) -> Skill:
        rows = await self._request("POST", "skills", json=values, prefer="return=representation")
        return Skill.model_validate(rows[0])

    async def create_version(self, values: dict[str, Any]) -> SkillVersion:
        rows = await self._request("POST", "skill_versions", json=values, prefer="return=representation")
        return SkillVersion.model_validate(rows[0])

    async def create_source(self, values: dict[str, Any]) -> UUID:
        rows = await self._request("POST", "sources", json=values, prefer="return=representation")
        return UUID(rows[0]["id"])

    async def link_source(self, version_id: UUID, source_id: UUID, role: str = "primary") -> None:
        await self._request(
            "POST",
            "skill_version_sources",
            json={"skill_version_id": str(version_id), "source_id": str(source_id), "role": role},
        )

    async def create_audit_event(self, values: dict[str, Any]) -> None:
        await self._request("POST", "audit_events", json=values)

    async def list_skills(self) -> list[Skill]:
        rows = await self._request("GET", "skills", params={"select": "*", "order": "updated_at.desc"})
        return [Skill.model_validate(row) for row in rows]

    async def get_version(self, version_id: UUID) -> SkillVersion | None:
        rows = await self._request("GET", "skill_versions", params={"select": "*", "id": f"eq.{version_id}"})
        return SkillVersion.model_validate(rows[0]) if rows else None

    async def list_versions(self, skill_id: UUID) -> list[SkillVersion]:
        rows = await self._request("GET", "skill_versions", params={"select": "*", "skill_id": f"eq.{skill_id}", "order": "created_at.desc"})
        return [SkillVersion.model_validate(row) for row in rows]

    async def get_skill(self, skill_id: UUID) -> Skill | None:
        rows = await self._request("GET", "skills", params={"select": "*", "id": f"eq.{skill_id}"})
        return Skill.model_validate(rows[0]) if rows else None

    async def create_evidence(self, values: dict[str, Any]) -> EvidenceItem:
        rows = await self._request("POST", "evidence_items", json=values, prefer="return=representation")
        return EvidenceItem.model_validate(rows[0])

    async def list_evidence(self, skill_id: UUID) -> list[EvidenceItem]:
        rows = await self._request(
            "GET", "evidence_items", params={"select": "*", "skill_id": f"eq.{skill_id}", "archived_at": "is.null", "order": "created_at.desc"}
        )
        return [EvidenceItem.model_validate(row) for row in rows]

    async def get_evidence_by_ids(self, skill_id: UUID, evidence_ids: list[UUID]) -> list[EvidenceItem]:
        if not evidence_ids:
            return []
        requested = ",".join(str(item) for item in evidence_ids)
        rows = await self._request(
            "GET", "evidence_items",
            params={"select": "*", "skill_id": f"eq.{skill_id}", "id": f"in.({requested})", "archived_at": "is.null"},
        )
        return [EvidenceItem.model_validate(row) for row in rows]

    async def create_dataset(self, values: dict[str, Any]) -> EvalDataset:
        rows = await self._request("POST", "eval_datasets", json=values, prefer="return=representation")
        return EvalDataset.model_validate(rows[0])

    async def get_dataset(self, dataset_id: UUID) -> EvalDataset | None:
        rows = await self._request("GET", "eval_datasets", params={"select": "*", "id": f"eq.{dataset_id}"})
        return EvalDataset.model_validate(rows[0]) if rows else None

    async def list_datasets(self, skill_id: UUID | None = None) -> list[EvalDataset]:
        params = {"select": "*", "order": "created_at.desc"}
        if skill_id:
            params["skill_id"] = f"eq.{skill_id}"
        rows = await self._request("GET", "eval_datasets", params=params)
        return [EvalDataset.model_validate(row) for row in rows]

    async def lock_dataset(self, dataset_id: UUID) -> EvalDataset:
        rows = await self._request(
            "PATCH", "eval_datasets", params={"id": f"eq.{dataset_id}", "is_locked": "eq.false"}, json={"is_locked": True}, prefer="return=representation"
        )
        if not rows:
            raise RepositoryError("Evaluation dataset was not found or is already locked.")
        return EvalDataset.model_validate(rows[0])

    async def create_eval_case(self, values: dict[str, Any]) -> EvalCase:
        rows = await self._request("POST", "eval_cases", json=values, prefer="return=representation")
        return EvalCase.model_validate(rows[0])

    async def list_eval_cases(self, dataset_id: UUID) -> list[EvalCase]:
        rows = await self._request("GET", "eval_cases", params={"select": "*", "dataset_id": f"eq.{dataset_id}", "order": "created_at"})
        return [EvalCase.model_validate(row) for row in rows]

    async def get_dev_eval_cases(self, dataset_id: UUID) -> list[EvalCase]:
        rows = await self._request("POST", "rpc/get_dev_eval_cases", json={"p_dataset_id": str(dataset_id)})
        return [EvalCase.model_validate(row) for row in rows]

    async def create_lineage(self, parent_version_id: UUID, child_version_id: UUID, relation: str) -> None:
        await self._request(
            "POST", "skill_lineage",
            json={"parent_version_id": str(parent_version_id), "child_version_id": str(child_version_id), "relation": relation},
        )

    async def create_eval_run(self, values: dict[str, Any]) -> EvalRun:
        rows = await self._request("POST", "eval_runs", json=values, prefer="return=representation")
        return EvalRun.model_validate(rows[0])

    async def finish_eval_run(self, run_id: UUID, *, status: str, summary: dict[str, Any]) -> EvalRun:
        rows = await self._request(
            "PATCH", "eval_runs", params={"id": f"eq.{run_id}"}, json={"status": status, "summary": summary, "finished_at": datetime.now(UTC).isoformat()}, prefer="return=representation"
        )
        return EvalRun.model_validate(rows[0])

    async def create_eval_case_result(self, values: dict[str, Any]) -> None:
        await self._request("POST", "eval_case_results", json=values)

    async def create_execution(self, values: dict[str, Any]) -> Execution:
        rows = await self._request("POST", "executions", json=values, prefer="return=representation")
        return Execution.model_validate(rows[0])

    async def get_execution(self, execution_id: UUID) -> Execution | None:
        rows = await self._request("GET", "executions", params={"select": "*", "id": f"eq.{execution_id}"})
        return Execution.model_validate(rows[0]) if rows else None

    async def update_execution_feedback(self, execution_id: UUID, values: dict[str, Any]) -> Execution | None:
        rows = await self._request(
            "PATCH", "executions", params={"id": f"eq.{execution_id}"}, json=values, prefer="return=representation"
        )
        return Execution.model_validate(rows[0]) if rows else None

    async def list_eval_runs_for_version(self, version_id: UUID) -> list[dict[str, Any]]:
        rows = await self._request(
            "GET", "eval_runs",
            params={"select": "id,status,summary,baseline_version_id,dataset:eval_datasets!inner(dataset_type,split,skill_id)", "skill_version_id": f"eq.{version_id}"},
        )
        normalized: list[dict[str, Any]] = []
        for row in rows:
            dataset = row.pop("dataset")
            normalized.append({**row, "dataset_type": dataset["dataset_type"], "split": dataset["split"]})
        return normalized

    async def set_version_status(self, version_id: UUID, status: str) -> SkillVersion:
        rows = await self._request(
            "PATCH", "skill_versions", params={"id": f"eq.{version_id}"}, json={"status": status}, prefer="return=representation"
        )
        return SkillVersion.model_validate(rows[0])

    async def create_gate_decision(self, values: dict[str, Any]) -> EvalGateDecision:
        rows = await self._request("POST", "eval_gate_decisions", json=values, prefer="return=representation")
        return EvalGateDecision.model_validate(rows[0])

    async def get_latest_gate_decision(self, version_id: UUID) -> EvalGateDecision | None:
        rows = await self._request(
            "GET", "eval_gate_decisions", params={"select": "*", "skill_version_id": f"eq.{version_id}", "order": "created_at.desc", "limit": "1"}
        )
        return EvalGateDecision.model_validate(rows[0]) if rows else None

    async def supersede_active_release(self, skill_id: UUID) -> None:
        await self._request(
            "PATCH", "releases", params={"skill_id": f"eq.{skill_id}", "environment": "eq.production", "superseded_at": "is.null"},
            json={"release_state": "superseded", "superseded_at": datetime.now(UTC).isoformat()}, prefer="return=minimal"
        )

    async def create_release(self, values: dict[str, Any]) -> Release:
        rows = await self._request("POST", "releases", json=values, prefer="return=representation")
        return Release.model_validate(rows[0])

    async def promote_version(
        self, version_id: UUID, *, reason: str | None, manual_override: bool, override_reason: str | None
    ) -> Release:
        rows = await self._request(
            "POST",
            "rpc/promote_skill_version",
            json={
                "p_skill_version_id": str(version_id),
                "p_reason": reason,
                "p_manual_override": manual_override,
                "p_override_reason": override_reason,
            },
        )
        return Release.model_validate(rows[0])

    async def rollback_release(self, skill_id: UUID, target_release_id: UUID, reason: str) -> Release:
        rows = await self._request(
            "POST",
            "rpc/rollback_skill_release",
            json={"p_skill_id": str(skill_id), "p_target_release_id": str(target_release_id), "p_reason": reason},
        )
        return Release.model_validate(rows[0])

    async def get_release(self, release_id: UUID) -> Release | None:
        rows = await self._request("GET", "releases", params={"select": "*", "id": f"eq.{release_id}"})
        return Release.model_validate(rows[0]) if rows else None

    async def list_releases(self, skill_id: UUID) -> list[Release]:
        rows = await self._request(
            "GET", "releases", params={"select": "*", "skill_id": f"eq.{skill_id}", "order": "released_at.desc"}
        )
        return [Release.model_validate(row) for row in rows]

    async def create_job(self, values: dict[str, Any]) -> Job:
        rows = await self._request("POST", "jobs", json=values, prefer="return=representation")
        return Job.model_validate(rows[0])

    async def get_job(self, job_id: UUID) -> Job | None:
        rows = await self._request("GET", "jobs", params={"select": "*", "id": f"eq.{job_id}"})
        return Job.model_validate(rows[0]) if rows else None

    async def get_job_by_idempotency_key(self, key: str) -> Job | None:
        rows = await self._request("GET", "jobs", params={"select": "*", "idempotency_key": f"eq.{key}"})
        return Job.model_validate(rows[0]) if rows else None

    async def claim_next_job(self, lease_seconds: int = 300) -> Job | None:
        rows = await self._request("POST", "rpc/claim_next_skill_job", json={"p_lease_seconds": lease_seconds})
        # A Postgres function returning a composite row serializes SQL NULL as one
        # object whose fields are all null, rather than as an empty response.
        return Job.model_validate(rows[0]) if rows and rows[0].get("id") is not None else None

    async def set_job_workspace(self, job_id: UUID, workspace_path: str) -> None:
        await self._request(
            "PATCH", "jobs", params={"id": f"eq.{job_id}"}, json={"workspace_path": workspace_path}, prefer="return=minimal"
        )

    async def finish_job(
        self, job_id: UUID, status: str, *, output: dict[str, Any] | None = None, error: str | None = None
    ) -> Job:
        rows = await self._request(
            "POST", "rpc/finish_skill_job",
            json={"p_job_id": str(job_id), "p_status": status, "p_output": output, "p_error": error},
        )
        return Job.model_validate(rows[0])
