import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from adapters.fixture import FixtureSkillEngine
from apps.api.app.models import Job


def test_fixture_engine_produces_portable_skill(tmp_path: Path) -> None:
    workspace = tmp_path / "job"
    for directory in ("input", "engine", "output", "logs"):
        (workspace / directory).mkdir(parents=True, exist_ok=True)
    job = Job(
        id=uuid4(), job_type="distill_open_world", engine="fixture", status="running",
        input={"brief": "Select AI creator topics", "skill_name": "Topic Selection"},
        attempt_count=1, created_at=datetime.now(UTC),
    )
    result = asyncio.run(FixtureSkillEngine().run(job, workspace))
    assert result.artifact_directory.joinpath("SKILL.md").is_file()
    assert "Select AI creator topics" in result.artifact_directory.joinpath("SKILL.md").read_text()
