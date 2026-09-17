import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.api.app.models import PromoteRequest, Release, SkillVersion, VersionStatus
from apps.api.app.services import LifecycleError, LifecycleService


class FakeRepository:
    def __init__(self, version: SkillVersion) -> None:
        self.version = version
        self.superseded = False
        self.events: list[dict] = []

    async def get_version(self, version_id):
        return self.version if version_id == self.version.id else None

    async def promote_version(self, version_id, *, reason, manual_override, override_reason):
        self.superseded = True
        return Release(
            id=uuid4(),
            skill_id=self.version.skill_id,
            skill_version_id=self.version.id,
            environment="production",
            release_state="active",
            reason=reason,
            manual_override=manual_override,
            override_reason=override_reason,
            released_at=datetime.now(UTC),
            superseded_at=None,
            rollback_from_release_id=None,
        )


def version(status: VersionStatus) -> SkillVersion:
    return SkillVersion(
        id=uuid4(), skill_id=uuid4(), version="0.1.0", layer_type="compiled", status=status,
        artifact_storage_path="artifact.zip", artifact_hash="0" * 64, created_by_engine="import",
        created_at=datetime.now(UTC), promoted_at=None,
    )


def test_promotion_requires_pass_or_audited_override() -> None:
    candidate = version(VersionStatus.DRAFT)
    repository = FakeRepository(candidate)
    service = LifecycleService(repository, object(), object())  # type: ignore[arg-type]

    with pytest.raises(LifecycleError, match="passed candidate"):
        asyncio.run(service.promote(candidate.id, PromoteRequest()))
    with pytest.raises(LifecycleError, match="override reason"):
        asyncio.run(service.promote(candidate.id, PromoteRequest(manual_override=True)))

    release = asyncio.run(
        service.promote(candidate.id, PromoteRequest(manual_override=True, override_reason="Foundation fixture"))
    )
    assert release.manual_override is True
    assert repository.superseded is True
