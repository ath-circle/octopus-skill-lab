from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from apps.api.app.models import Job


@dataclass(frozen=True)
class EngineHealth:
    available: bool
    detail: str


@dataclass(frozen=True)
class EngineResult:
    engine: str
    exit_code: int
    artifact_directory: Path
    stdout_path: Path
    stderr_path: Path
    metadata: dict


class SkillEngineAdapter(Protocol):
    name: str

    async def healthcheck(self) -> EngineHealth: ...

    async def run(self, job: Job, workspace: Path) -> EngineResult: ...
