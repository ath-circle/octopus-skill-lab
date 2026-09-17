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
    skillalchemy_skill_path: str = Field(default="", alias="SKILLALCHEMY_SKILL_PATH")
    skillcreator_agent_bin: str = Field(default="codex", alias="SKILLCREATOR_AGENT_BIN")
    skillcreator_skill_path: str = Field(default="", alias="SKILLCREATOR_SKILL_PATH")
    codex_bin: str = Field(default="codex", alias="CODEX_BIN")
    codex_benchmark_timeout_seconds: int = Field(default=300, alias="CODEX_BENCHMARK_TIMEOUT_SECONDS")
    benchmark_workspace_root: str = Field(default="data/evaluations", alias="BENCHMARK_WORKSPACE_ROOT")
    phoenix_base_url: str = Field(default="http://127.0.0.1:6006", alias="PHOENIX_BASE_URL")
    phoenix_collector_endpoint: str = Field(default="http://127.0.0.1:6006/v1/traces", alias="PHOENIX_COLLECTOR_ENDPOINT")
    phoenix_project_name: str = Field(default="octopus-skill-lab", alias="PHOENIX_PROJECT_NAME")
    promptfoo_bin: str = Field(default="promptfoo", alias="PROMPTFOO_BIN")
    promptfoo_enabled: bool = Field(default=False, alias="PROMPTFOO_ENABLED")

    @property
    def supabase_url(self) -> str:
        return f"https://{self.spb_project_id}.supabase.co"


@lru_cache
def get_settings() -> Settings:
    return Settings()
