from pathlib import Path

from apps.api.app.models import Job

from .base import EngineResult
from .subprocess import SubprocessSkillEngine


class SkillAlchemyAdapter(SubprocessSkillEngine):
    def __init__(self, executable: str = "codex") -> None:
        super().__init__("skillalchemy", executable)

    async def run(self, job: Job, workspace: Path) -> EngineResult:
        brief = job.input["brief"]
        constraints = "; ".join(job.input.get("constraints", [])) or "none"
        prompt = (
            "Use the installed SkillAlchemy workflow to create an evidence-grounded portable Agent Skill. "
            f"Brief: {brief}\nConstraints: {constraints}\n"
            "Write only the completed portable package to output/skill, including SKILL.md at its root. "
            "Do not modify files outside the current workspace."
        )
        if Path(self.executable).name == "claude":
            command = [self.executable, "--print", "--permission-mode", "acceptEdits", prompt]
        else:
            command = [
                self.executable, "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "--approve-for-me", "-C", str(workspace), prompt,
            ]
        return await self._run_command(command, job, workspace)
