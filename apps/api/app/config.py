from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server-only configuration. No setting is suitable for browser exposure."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    spb_project_id: str = Field(alias="SPB_PROJECT_ID")
    spb_secret_key: str = Field(alias="SPB_SECRET_KEY")
    supabase_artifact_bucket: str = Field(default="skill-artifacts", alias="SUPABASE_ARTIFACT_BUCKET")
    artifact_max_bytes: int = Field(default=50 * 1024 * 1024, alias="ARTIFACT_MAX_BYTES")
    workspace_root: str = Field(default="data/workspaces", alias="WORKSPACE_ROOT")
    job_poll_interval: float = Field(default=2.0, alias="JOB_POLL_INTERVAL")
    skill_factory_engine_mode: str = Field(default="fixture", alias="SKILL_FACTORY_ENGINE_MODE")
    arex_disco_bin: str = Field(default="disco", alias="AREX_DISCO_BIN")
    skillalchemy_agent_bin: str = Field(default="codex", alias="SKILLALCHEMY_AGENT_BIN")

    @property
    def supabase_url(self) -> str:
        return f"https://{self.spb_project_id}.supabase.co"


@lru_cache
def get_settings() -> Settings:
    return Settings()
