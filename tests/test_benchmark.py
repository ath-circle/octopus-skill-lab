import asyncio
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.api.app.benchmark import CodexBenchmarkRunner, CodexInvocation, CodexInvocationResult
from apps.api.app.models import EvalCase, EvalRunRequest


def archive(skill_text: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        package.writestr("SKILL.md", skill_text)
    return output.getvalue()


def eval_case(*, checks=None) -> EvalCase:
    return EvalCase(
        id=uuid4(), dataset_id=uuid4(), prompt="Answer the question.", expected_output=None,
        expectations={"rubric": "Prefer a correct, direct answer.", "deterministic_checks": checks or []},
        files=[], tags=[], source_evidence_id=None, created_at=datetime.now(UTC),
    )


class RecordingCodex:
    def __init__(self) -> None:
        self.invocations: list[CodexInvocation] = []
        self.executor_paths: list[Path] = []

    async def invoke(self, invocation: CodexInvocation) -> CodexInvocationResult:
        self.invocations.append(invocation)
        if invocation.output_schema is not None:
            assert not (invocation.workspace / "skill").exists()
            assert all(path != invocation.workspace for path in self.executor_paths)
            assert "candidate" not in invocation.prompt.casefold()
            assert "baseline" not in invocation.prompt.casefold()
            response = json.dumps({
                "winner": "A", "a_pass": True, "b_pass": False,
                "a_score": 1, "b_score": 0, "reason": "A is correct.",
            })
        else:
            self.executor_paths.append(invocation.workspace)
            skill = (invocation.workspace / "skill" / "SKILL.md").read_text()
            other = "BASELINE" if "CANDIDATE" in skill else "CANDIDATE"
            assert other not in skill
            assert "rubric" not in invocation.prompt.casefold()
            response = "correct" if "CANDIDATE" in skill else "wrong"
        logs = invocation.workspace / "fake-logs"
        logs.mkdir()
        stdout, stderr, transcript = logs / "stdout", logs / "stderr", logs / "transcript"
        stdout.write_text("stdout")
        stderr.write_text("")
        transcript.write_text(response)
        return CodexInvocationResult(response, str(stdout), str(stderr), str(transcript))


def test_runner_isolates_executors_and_blinds_grader(tmp_path: Path) -> None:
    client = RecordingCodex()
    runner = CodexBenchmarkRunner(client, tmp_path)
    result = asyncio.run(runner.run_case(
        run_id=uuid4(), case=eval_case(),
        candidate_archive=archive("# CANDIDATE"), baseline_archive=archive("# BASELINE"),
    ))
    assert len(client.invocations) == 3
    assert result.grader_output["grader"] == "blind_codex"
    assert result.winner in {"candidate", "baseline"}
    assert Path(result.candidate_output_path).read_text() == "correct"
    assert Path(result.baseline_output_path).read_text() == "wrong"


def test_deterministic_failure_skips_model_grader(tmp_path: Path) -> None:
    client = RecordingCodex()
    runner = CodexBenchmarkRunner(client, tmp_path)
    result = asyncio.run(runner.run_case(
        run_id=uuid4(), case=eval_case(checks=[{"type": "contains", "value": "correct"}]),
        candidate_archive=archive("# CANDIDATE"), baseline_archive=archive("# BASELINE"),
    ))
    assert len(client.invocations) == 2
    assert result.winner == "candidate"
    assert result.candidate_pass is True
    assert result.baseline_pass is False
    assert result.grader_output["grader"] == "deterministic"


def test_fixture_engine_is_not_an_evaluation_fallback() -> None:
    with pytest.raises(ValidationError):
        EvalRunRequest(
            skill_version_id=uuid4(), dataset_id=uuid4(), baseline_version_id=uuid4(), engine="fixture"
        )
