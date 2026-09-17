"""Single-process worker for V1 jobs. Run with `python -m workers.main --once`."""

import argparse
import asyncio
import json
import re
from pathlib import Path

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
            adapter = adapter_for(job.engine, self.settings)
            health = await adapter.healthcheck()
            if not health.available:
                raise RuntimeError(f"Engine unavailable: {health.detail}")
            result = await adapter.run(job, workspace)
            archive = self.service.normalizer.archive_directory(str(result.artifact_directory))
            request, source_type, source_uri, repo_ref = self._registration_inputs(job)
            skill, version = await self.service.import_skill(
                request,
                archive,
                filename=result.artifact_directory.name,
                created_by_engine=result.engine,
                source_type=source_type,
                source_uri=source_uri,
                repo_ref=repo_ref,
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
