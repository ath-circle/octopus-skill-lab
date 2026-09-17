from pathlib import Path

from apps.api.app.models import Job

from .base import EngineResult
from .subprocess import SubprocessSkillEngine


class ArexDiscoAdapter(SubprocessSkillEngine):
    def __init__(self, executable: str = "disco", timeout_seconds: int = 300) -> None:
        super().__init__("arex", executable, timeout_seconds)

    async def run(self, job: Job, workspace: Path) -> EngineResult:
        repo_url = job.input["repo_url"]
        objective = job.input.get("objective") or "Distill a verified operating Skill."
        ref = job.input.get("ref")
        ref_clause = f" at ref {ref}" if ref else ""
        prompt = (
            f"Use DisCo Creator to distill {repo_url}{ref_clause} into an executable Skill. "
            f"Objective: {objective} Write the final portable package to output/skill with SKILL.md at its root."
        )
        return await self._run_command([self.executable, "--creator", "-p", prompt], job, workspace)
