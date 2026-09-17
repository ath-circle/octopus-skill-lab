import json
from pathlib import Path

from apps.api.app.models import Job

from .base import EngineHealth, EngineResult


class FixtureSkillEngine:
    """Deterministic engine used by automated V1 integration tests."""

    name = "fixture"

    async def healthcheck(self) -> EngineHealth:
        return EngineHealth(available=True, detail="Deterministic fixture adapter")

    async def run(self, job: Job, workspace: Path) -> EngineResult:
        output = workspace / "output" / "skill"
        output.mkdir(parents=True, exist_ok=False)
        brief = job.input.get("brief") or job.input.get("objective") or "Operate the source safely."
        title = job.input.get("skill_name") or self._title_from_repo(job.input.get("repo_url", "Repository Skill"))
        source = job.input.get("repo_url", "operator-provided brief")
        (output / "SKILL.md").write_text(
            f"---\nname: {title}\ndescription: Fixture-generated Skill\n---\n\n"
            f"# {title}\n\n## Objective\n\n{brief}\n\n## Source boundary\n\n"
            f"This fixture was created from: {source}. Validate primary evidence before reuse.\n"
        )
        references = output / "references"
        references.mkdir()
        (references / "source.md").write_text(f"# Source\n\n{source}\n")
        stdout = workspace / "logs" / "stdout.log"
        stderr = workspace / "logs" / "stderr.log"
        stdout.write_text("Fixture engine completed.\n")
        stderr.write_text("")
        (workspace / "output" / "engine-result.json").write_text(json.dumps({"engine": self.name}))
        return EngineResult(self.name, 0, output, stdout, stderr, {"mode": "fixture"})

    @staticmethod
    def _title_from_repo(repo_url: str) -> str:
        stem = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
        return stem.replace("-", " ").title() or "Repository Skill"
