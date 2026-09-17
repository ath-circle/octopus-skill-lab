from apps.api.app.config import Settings

from .arex import ArexDiscoAdapter
from .base import SkillEngineAdapter
from .fixture import FixtureSkillEngine
from .skillalchemy import SkillAlchemyAdapter
from .skillcreator import AnthropicSkillCreatorAdapter


def adapter_for(engine: str, settings: Settings) -> SkillEngineAdapter:
    if engine == "fixture" or settings.skill_factory_engine_mode == "fixture":
        return FixtureSkillEngine()
    if engine == "arex":
        return ArexDiscoAdapter(settings.arex_disco_bin, settings.engine_timeout_seconds)
    if engine == "skillalchemy":
        return SkillAlchemyAdapter(settings.skillalchemy_agent_bin, settings.skillalchemy_skill_path, settings.engine_timeout_seconds)
    if engine == "skillcreator":
        return AnthropicSkillCreatorAdapter(settings.skillcreator_agent_bin, settings.skillcreator_skill_path, settings.engine_timeout_seconds)
    raise ValueError(f"Unsupported engine: {engine}")
