from pathlib import Path

from apps.api.app.models import Job

from .base import EngineHealth, EngineResult
from .subprocess import SubprocessSkillEngine


class AnthropicSkillCreatorAdapter(SubprocessSkillEngine):
    """Adapter boundary for the upstream Anthropic Skill Creator workflow.

    The upstream project is a Skill, not a library. It must be deliberately installed
    and its absolute directory configured; otherwise this engine remains unavailable.
    """

    def __init__(self, executable: str, skill_path: str) -> None:
        super().__init__("skillcreator", executable)
        self.skill_path = Path(skill_path).expanduser()

    async def healthcheck(self) -> EngineHealth:
        executable = await super().healthcheck()
        skill_file = self.skill_path / "SKILL.md"
        if not executable.available:
            return executable
        if not skill_file.is_file():
            return EngineHealth(False, f"Skill Creator package missing: {skill_file}")
        return EngineHealth(True, f"{executable.detail}; skill: {skill_file}")

    async def run(self, job: Job, workspace: Path) -> EngineResult:
        if job.job_type != "personalize":
            raise RuntimeError("Skill Creator is reserved for personalize/improve jobs.")
        prompt = (
            f"Read and follow the installed Anthropic Skill Creator at {self.skill_path / 'SKILL.md'}. "
            "Improve input/baseline using only input/personalization-context.json. "
            "Compare candidate guidance to the baseline and preserve useful constraints. "
            "The context has selected evidence and dev examples only; do not seek or infer holdout data. "
            "Write the completed candidate package to output/skill with SKILL.md at its root. "
            "Do not modify files outside the current workspace."
        )
        if Path(self.executable).name == "claude":
            command = [self.executable, "--print", "--permission-mode", "acceptEdits", prompt]
        else:
            command = [self.executable, "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "--approve-for-me", "-C", str(workspace), prompt]
        return await self._run_command(command, job, workspace)
