from pathlib import Path

from apps.api.app.models import Job

from .base import EngineHealth, EngineResult
from .subprocess import SubprocessSkillEngine


class SkillAlchemyAdapter(SubprocessSkillEngine):
    def __init__(self, executable: str = "codex", skill_path: str = "") -> None:
        super().__init__("skillalchemy", executable)
        self.skill_path = Path(skill_path).expanduser()

    async def healthcheck(self) -> EngineHealth:
        executable = await super().healthcheck()
        skill_file = self.skill_path / "SKILL.md"
        if not executable.available:
            return executable
        if not skill_file.is_file():
            return EngineHealth(False, f"SkillAlchemy package missing: {skill_file}")
        return EngineHealth(True, f"{executable.detail}; skill: {skill_file}")

    async def run(self, job: Job, workspace: Path) -> EngineResult:
        if job.job_type == "fuse":
            prompt = (
                f"Read and follow the installed SkillAlchemy workflow at {self.skill_path / 'SKILL.md'}. "
                "Create a new portable Agent Skill by fusing the immutable packages in input/sources, using input/fusion-context.json. "
                "Keep source-specific constraints when they conflict; do not invent unsupported policies. "
                "Write a complete package to output/skill with SKILL.md at its root and do not modify files outside the current workspace."
            )
            return await self._invoke(prompt, job, workspace)
        if job.job_type == "personalize":
            prompt = (
                "Create a candidate revision of input/baseline using only input/personalization-context.json. "
                "That context contains selected evidence and dev examples; it intentionally contains no holdout data. "
                "Preserve useful baseline guidance, implement only supported refinements, and write a complete package to output/skill with SKILL.md at its root. "
                "Do not modify files outside the current workspace."
            )
            return await self._invoke(prompt, job, workspace)
        brief = job.input["brief"]
        constraints = "; ".join(job.input.get("constraints", [])) or "none"
        prompt = (
            f"Read and follow the installed SkillAlchemy workflow at {self.skill_path / 'SKILL.md'} to create an evidence-grounded portable Agent Skill. "
            f"Brief: {brief}\nConstraints: {constraints}\n"
            "Write only the completed portable package to output/skill, including SKILL.md at its root. "
            "Do not modify files outside the current workspace."
        )
        return await self._invoke(prompt, job, workspace)

    async def _invoke(self, prompt: str, job: Job, workspace: Path) -> EngineResult:
        if Path(self.executable).name == "claude":
            command = [self.executable, "--print", "--permission-mode", "acceptEdits", prompt]
        else:
            command = [
                self.executable, "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "--approve-for-me", "-C", str(workspace), prompt,
            ]
        return await self._run_command(command, job, workspace)
