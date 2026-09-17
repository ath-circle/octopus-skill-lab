"""Single-process worker for V1 jobs. Run with `python -m workers.main --once`."""

import argparse
import asyncio
import io
import json
import re
import zipfile
from pathlib import Path
from uuid import UUID

from adapters.factory import adapter_for
from apps.api.app.artifacts import SkillArchiveNormalizer, SupabaseArtifactStore
from apps.api.app.config import get_settings
from apps.api.app.models import SkillCreate
from apps.api.app.repository import SupabaseRegistryRepository
from apps.api.app.services import LifecycleService


def redact(text: str) -> str:
    """Never copy likely credential material into a persistent job error."""
    return re.sub(r"(?:sb_[a-z]+_|sk-|ghp_)[A-Za-z0-9_-]+", "[REDACTED]", text)[:4_000]


class JobWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.repository = SupabaseRegistryRepository(self.settings)
        self.service = LifecycleService(
            self.repository,
            SupabaseArtifactStore(self.settings),
            SkillArchiveNormalizer(self.settings.artifact_max_bytes),
        )
        self.workspace_root = Path(self.settings.workspace_root).resolve()

    async def run_once(self) -> bool:
        job = await self.repository.claim_next_job()
        if job is None:
            return False
        workspace = self.workspace_root / str(job.id) / f"attempt-{job.attempt_count}"
        workspace.mkdir(parents=True, exist_ok=False, mode=0o700)
        for directory in ("input", "engine", "output", "logs"):
            (workspace / directory).mkdir(mode=0o700)
        (workspace / "input" / "job.json").write_text(json.dumps(job.input, indent=2, sort_keys=True) + "\n")
        await self.repository.set_job_workspace(job.id, str(workspace))

        try:
            if job.job_type == "personalize":
                await self._prepare_personalization_input(job, workspace)
            elif job.job_type == "fuse":
                await self._prepare_fusion_input(job, workspace)
            adapter = adapter_for(job.engine, self.settings)
            health = await adapter.healthcheck()
            if not health.available:
                raise RuntimeError(f"Engine unavailable: {health.detail}")
            result = await adapter.run(job, workspace)
            archive = self.service.normalizer.archive_directory(str(result.artifact_directory))
            if job.job_type == "personalize":
                skill, version = await self._register_personalized_candidate(job, archive, result.engine)
            elif job.job_type == "fuse":
                skill, version = await self._register_fusion(job, archive, result.engine)
            else:
                request, source_type, source_uri, repo_ref = self._registration_inputs(job)
                skill, version = await self.service.import_skill(
                    request, archive, filename=result.artifact_directory.name, created_by_engine=result.engine,
                    source_type=source_type, source_uri=source_uri, repo_ref=repo_ref,
                )
            await self.repository.finish_job(
                job.id,
                "succeeded",
                output={
                    "skill_id": str(skill.id),
                    "skill_version_id": str(version.id),
                    "artifact_hash": version.artifact_hash,
                    "engine": result.engine,
                    "logs": {"stdout": str(result.stdout_path), "stderr": str(result.stderr_path)},
                },
            )
        except Exception as exc:
            await self.repository.finish_job(job.id, "failed", error=redact(str(exc)))
        return True

    async def _prepare_personalization_input(self, job, workspace: Path) -> None:
        baseline = await self.repository.get_version(UUID(job.input["baseline_version_id"]))
        if baseline is None:
            raise ValueError("Baseline version disappeared before the job ran.")
        archive = await self.service.artifacts.get(baseline.artifact_storage_path)
        destination = workspace / "input" / "baseline"
        self._safe_extract(archive, destination)
        context = {"baseline_version": baseline.version, "evidence": job.input["evidence"], "dev_examples": job.input["dev_examples"]}
        (workspace / "input" / "personalization-context.json").write_text(json.dumps(context, indent=2, sort_keys=True) + "\n")

    async def _register_personalized_candidate(self, job, archive: bytes, engine: str):
        baseline_id = UUID(job.input["baseline_version_id"])
        baseline = await self.repository.get_version(baseline_id)
        if baseline is None:
            raise ValueError("Baseline version disappeared before registration.")
        versions = await self.repository.list_versions(baseline.skill_id)
        next_version = self._next_minor_version([item.version for item in versions])
        skill, candidate = await self.service.import_version(
            baseline.skill_id, next_version, archive, "personalized-candidate",
            created_by_engine=engine, source_uri=f"personalization-job:{job.id}",
        )
        await self.repository.create_lineage(baseline.id, candidate.id, "personalized_from")
        await self.repository.create_audit_event(
            {"aggregate_type": "skill_version", "aggregate_id": str(candidate.id), "event_type": "skill.personalized",
             "payload": {"baseline_version_id": str(baseline.id), "job_id": str(job.id), "evidence_count": len(job.input["evidence"]), "dev_case_count": len(job.input["dev_examples"])}}
        )
        return skill, candidate

    async def _prepare_fusion_input(self, job, workspace: Path) -> None:
        sources = []
        for version_id in job.input["source_version_ids"]:
            version = await self.repository.get_version(UUID(version_id))
            if version is None:
                raise ValueError("Fusion source disappeared before the job ran.")
            destination = workspace / "input" / "sources" / str(version.id)
            self._safe_extract(await self.service.artifacts.get(version.artifact_storage_path), destination)
            sources.append({"version_id": str(version.id), "skill_id": str(version.skill_id), "version": version.version, "artifact_hash": version.artifact_hash})
        (workspace / "input" / "fusion-context.json").write_text(json.dumps({"objective": job.input.get("objective"), "sources": sources}, indent=2, sort_keys=True) + "\n")

    async def _register_fusion(self, job, archive: bytes, engine: str):
        request = SkillCreate(slug=job.input["skill_slug"], name=job.input["skill_name"], description=job.input["description"])
        skill, fused = await self.service.import_skill(
            request, archive, "fused-candidate", created_by_engine=engine,
            source_type="existing_skill", source_uri=f"fusion-job:{job.id}",
        )
        for version_id in job.input["source_version_ids"]:
            await self.repository.create_lineage(UUID(version_id), fused.id, "fused_from")
        await self.repository.create_audit_event(
            {"aggregate_type": "skill_version", "aggregate_id": str(fused.id), "event_type": "skill.fused",
             "payload": {"job_id": str(job.id), "source_version_ids": job.input["source_version_ids"]}}
        )
        return skill, fused

    @staticmethod
    def _next_minor_version(versions: list[str]) -> str:
        parsed = [tuple(int(part) for part in value.split(".")) for value in versions]
        major, minor, _ = max(parsed)
        return f"{major}.{minor + 1}.0"

    @staticmethod
    def _safe_extract(archive: bytes, destination: Path) -> None:
        with zipfile.ZipFile(io.BytesIO(archive)) as package:
            for item in package.infolist():
                path = (destination / item.filename).resolve()
                if destination.resolve() not in path.parents and path != destination.resolve():
                    raise ValueError("Baseline package contains an unsafe path.")
                if item.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(package.read(item))
        if not (destination / "SKILL.md").is_file():
            raise ValueError("Baseline package is missing SKILL.md.")

    @staticmethod
    def _registration_inputs(job):
        if job.job_type == "distill_open_world":
            return (
                SkillCreate(slug=job.input["skill_slug"], name=job.input["skill_name"], description=job.input["brief"]),
                "manual",
                "operator-provided brief",
                None,
            )
        if job.job_type == "distill_repo":
            repo_url = job.input["repo_url"]
            stem = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
            slug = SkillArchiveNormalizer.filename_to_slug(stem)
            return (
                SkillCreate(slug=slug, name=stem.replace("-", " ").title(), description=job.input.get("objective") or ""),
                "github_repo",
                repo_url,
                job.input.get("ref"),
            )
        raise ValueError(f"Unsupported job type: {job.job_type}")


async def main(poll: bool) -> None:
    worker = JobWorker()
    while True:
        worked = await worker.run_once()
        if not poll:
            return
        if not worked:
            await asyncio.sleep(worker.settings.job_poll_interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Claim at most one job (the default).")
    parser.add_argument("--poll", action="store_true", help="Run continuously instead of claiming one job.")
    args = parser.parse_args()
    if args.once and args.poll:
        parser.error("--once and --poll cannot be used together")
    asyncio.run(main(args.poll))
