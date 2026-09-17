import io
import json
import zipfile
from uuid import uuid4

import pytest

from apps.api.app.artifacts import ArtifactValidationError, SkillArchiveNormalizer


def archive_with(*entries: tuple[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, value in entries:
            archive.writestr(name, value)
    return buffer.getvalue()


def test_normalizer_adds_factory_metadata_without_changing_skill_markdown() -> None:
    content = b"# Research Skill\n\nDo the work.\n"
    artifact = SkillArchiveNormalizer(1_000_000).normalize(
        archive_with(("SKILL.md", content), ("references/source.md", b"primary source")),
        skill_id=uuid4(), slug="research-skill", name="Research Skill",
    )

    with zipfile.ZipFile(io.BytesIO(artifact.archive)) as archive:
        assert archive.read("SKILL.md") == content
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["skill_slug"] == "research-skill"
        assert json.loads(archive.read("provenance.json")) == {"rules": [], "sources": []}
        assert "CHANGELOG.md" in archive.namelist()
    assert len(artifact.sha256) == 64


@pytest.mark.parametrize("entries", [(), (("nested/SKILL.md", b"x"),), (("../SKILL.md", b"x"),)])
def test_normalizer_rejects_missing_or_unsafe_root_skill(entries: tuple[tuple[str, bytes], ...]) -> None:
    normalizer = SkillArchiveNormalizer(1_000_000)
    with pytest.raises(ArtifactValidationError):
        normalizer.normalize(archive_with(*entries), skill_id=uuid4(), slug="safe", name="Safe")

