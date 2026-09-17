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
        if job.job_type == "personalize":
            return self._personalize(job, workspace, output)
        if job.job_type == "fuse":
            return self._fuse(job, workspace, output)
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

    def _personalize(self, job: Job, workspace: Path, output: Path) -> EngineResult:
        context = json.loads((workspace / "input" / "personalization-context.json").read_text())
        baseline = (workspace / "input" / "baseline" / "SKILL.md").read_text()
        evidence_titles = [item["title"] for item in context["evidence"]]
        dev_count = len(context["dev_examples"])
        (output / "SKILL.md").write_text(
            baseline.rstrip() + "\n\n## Candidate refinement\n\n"
            "Apply these selected, skill-scoped signals when relevant:\n"
            + "".join(f"- {title}\n" for title in evidence_titles)
            + f"\nThis candidate was shaped against {dev_count} dev evaluation example(s); holdout examples were not provided.\n"
        )
        stdout = workspace / "logs" / "stdout.log"
        stderr = workspace / "logs" / "stderr.log"
        stdout.write_text("Fixture personalization completed without holdout data.\n")
        stderr.write_text("")
        return EngineResult(self.name, 0, output, stdout, stderr, {"mode": "fixture", "operation": "personalize"})

    def _fuse(self, job: Job, workspace: Path, output: Path) -> EngineResult:
        context = json.loads((workspace / "input" / "fusion-context.json").read_text())
        source_sections = []
        for source in context["sources"]:
            skill = (workspace / "input" / "sources" / source["version_id"] / "SKILL.md").read_text().strip()
            source_sections.append(f"## Source version {source['version']}\n\n{skill}")
        title = job.input["skill_name"]
        objective = context.get("objective") or "Combine the source operating guidance without discarding source boundaries."
        (output / "SKILL.md").write_text(
            f"---\nname: {title}\ndescription: Fixture-fused Skill\n---\n\n# {title}\n\n## Fusion objective\n\n{objective}\n\n"
            + "\n\n".join(source_sections) + "\n\n## Fusion boundary\n\nThis candidate preserves provenance; validate conflicts before promotion.\n"
        )
        stdout = workspace / "logs" / "stdout.log"; stderr = workspace / "logs" / "stderr.log"
        stdout.write_text("Fixture fusion completed from immutable source packages.\n"); stderr.write_text("")
        return EngineResult(self.name, 0, output, stdout, stderr, {"mode": "fixture", "operation": "fuse", "source_count": len(context["sources"])})

    @staticmethod
    def _title_from_repo(repo_url: str) -> str:
        stem = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
        return stem.replace("-", " ").title() or "Repository Skill"
