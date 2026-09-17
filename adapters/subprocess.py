import asyncio
import shutil
from pathlib import Path

from apps.api.app.models import Job

from .base import EngineHealth, EngineResult


class SubprocessSkillEngine:
    """Base adapter for engines that write a Skill directory to workspace/output/skill."""

    def __init__(self, name: str, executable: str) -> None:
        self.name = name
        self.executable = executable

    async def healthcheck(self) -> EngineHealth:
        path = shutil.which(self.executable)
        return EngineHealth(bool(path), f"{self.executable}: {path or 'not found'}")

    async def _run_command(self, command: list[str], job: Job, workspace: Path) -> EngineResult:
        logs = workspace / "logs"
        stdout_path, stderr_path = logs / "stdout.log", logs / "stderr.log"
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        artifact = workspace / "output" / "skill"
        if process.returncode != 0:
            raise RuntimeError(f"{self.name} exited with code {process.returncode}")
        if not (artifact / "SKILL.md").is_file():
            raise RuntimeError(f"{self.name} completed without output/skill/SKILL.md")
        return EngineResult(self.name, process.returncode, artifact, stdout_path, stderr_path, {"command": command})
