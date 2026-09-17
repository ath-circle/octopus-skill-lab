from apps.api.app.config import Settings

from .arex import ArexDiscoAdapter
from .base import SkillEngineAdapter
from .fixture import FixtureSkillEngine
from .skillalchemy import SkillAlchemyAdapter


def adapter_for(engine: str, settings: Settings) -> SkillEngineAdapter:
    if engine == "fixture" or settings.skill_factory_engine_mode == "fixture":
        return FixtureSkillEngine()
    if engine == "arex":
        return ArexDiscoAdapter(settings.arex_disco_bin)
    if engine == "skillalchemy":
        return SkillAlchemyAdapter(settings.skillalchemy_agent_bin)
    raise ValueError(f"Unsupported engine: {engine}")
