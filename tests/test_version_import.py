import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from apps.api.app.models import Skill
from apps.api.app.services import LifecycleService


class ExistingSkillRepository:
    def __init__(self, skill: Skill) -> None:
        self.skill = skill

    async def get_skill(self, skill_id):
        return self.skill if skill_id == self.skill.id else None


def test_import_version_rejects_unknown_skill_before_upload() -> None:
    skill = Skill(
        id=uuid4(), slug="known", name="Known", description="", created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC), archived_at=None,
    )
    service = LifecycleService(ExistingSkillRepository(skill), object(), object())  # type: ignore[arg-type]
    unknown = uuid4()
    try:
        asyncio.run(service.import_version(unknown, "0.2.0", b"not-read", "fixture.zip"))
    except Exception as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("Unknown Skills must not create artifacts.")
