import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from adapters.fixture import FixtureSkillEngine
from apps.api.app.models import Job, JobStatus
from apps.api.app.repository import SupabaseRegistryRepository
from workers.main import JobWorker


def fixture_job() -> Job:
    return Job(
        id=uuid4(), job_type="personalize", engine="fixture", status=JobStatus.RUNNING,
        input={"evidence": [{"title": "Cite source quality"}], "dev_examples": [{"prompt": "dev only"}]},
        attempt_count=1, created_at=datetime.now(UTC),
    )


def test_fixture_personalization_uses_context_not_holdout(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "input" / "baseline").mkdir(parents=True)
    (workspace / "output").mkdir()
    (workspace / "logs").mkdir()
    (workspace / "input" / "baseline" / "SKILL.md").write_text("# Baseline\n")
    (workspace / "input" / "personalization-context.json").write_text(
        json.dumps({"evidence": [{"title": "Cite source quality"}], "dev_examples": [{"prompt": "dev only"}]})
    )
    result = asyncio.run(FixtureSkillEngine().run(fixture_job(), workspace))
    content = (result.artifact_directory / "SKILL.md").read_text()
    assert "Cite source quality" in content
    assert "holdout examples were not provided" in content


def test_next_minor_version_is_monotonic() -> None:
    assert JobWorker._next_minor_version(["0.1.0", "0.2.0", "1.0.0"]) == "1.1.0"


def test_empty_composite_job_result_is_not_a_job() -> None:
    repository = object.__new__(SupabaseRegistryRepository)

    async def fake_request(*args, **kwargs):
        return [{"id": None}]

    repository._request = fake_request  # type: ignore[method-assign]
    assert asyncio.run(repository.claim_next_job()) is None
