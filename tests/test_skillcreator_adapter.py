import asyncio
import sys
from pathlib import Path

from adapters.skillcreator import AnthropicSkillCreatorAdapter


def test_skillcreator_requires_deliberately_installed_package(tmp_path: Path) -> None:
    missing = AnthropicSkillCreatorAdapter(sys.executable, str(tmp_path / "missing"))
    assert asyncio.run(missing.healthcheck()).available is False
    package = tmp_path / "anthropic-skill-creator"; package.mkdir()
    (package / "SKILL.md").write_text("# Skill Creator\n")
    ready = AnthropicSkillCreatorAdapter(sys.executable, str(package))
    assert asyncio.run(ready.healthcheck()).available is True
