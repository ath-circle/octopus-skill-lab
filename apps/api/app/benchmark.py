"""Isolated, blind candidate-versus-baseline benchmarks driven by Codex."""

from __future__ import annotations

import asyncio
import io
import json
import re
import secrets
import shutil
import stat
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol
from uuid import UUID

from .models import EvalCase


class BenchmarkError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodexInvocation:
    prompt: str
    workspace: Path
    output_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class CodexInvocationResult:
    response: str
    stdout_path: str
    stderr_path: str
    transcript_path: str


class CodexClient(Protocol):
    async def invoke(self, invocation: CodexInvocation) -> CodexInvocationResult: ...


@dataclass(frozen=True)
class BenchmarkCaseResult:
    candidate_output: str
    baseline_output: str
    candidate_output_path: str
    baseline_output_path: str
    candidate_pass: bool
    baseline_pass: bool
    candidate_score: float
    baseline_score: float
    winner: Literal["candidate", "baseline", "tie"]
    grader_output: dict[str, Any]
    latency_ms: int


class BenchmarkRunner(Protocol):
    @property
    def metadata(self) -> dict[str, Any]: ...

    async def run_case(
        self,
        *,
        run_id: UUID,
        case: EvalCase,
        candidate_archive: bytes,
        baseline_archive: bytes,
    ) -> BenchmarkCaseResult: ...


class CodexCliClient:
    """One fresh, ephemeral Codex process per benchmark role."""

    def __init__(self, executable: str, *, model: str | None, timeout_seconds: float) -> None:
        self.executable = executable
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def invoke(self, invocation: CodexInvocation) -> CodexInvocationResult:
        executable = shutil.which(self.executable)
        if executable is None:
            raise BenchmarkError(f"Codex executable is unavailable: {self.executable}")

        response_path = invocation.workspace / ".codex-final-response"
        command = [
            executable,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--approve-for-me",
            "--color",
            "never",
            "-C",
            str(invocation.workspace),
            "-o",
            str(response_path),
        ]
        if self.model:
            command.extend(["-m", self.model])
        if invocation.output_schema is not None:
            schema_path = invocation.workspace / ".grader-output-schema.json"
            schema_path.write_text(json.dumps(invocation.output_schema, sort_keys=True) + "\n")
            command.extend(["--output-schema", str(schema_path)])
        command.append(invocation.prompt)

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=invocation.workspace,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise BenchmarkError("Codex benchmark role timed out.") from exc
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()[-1_000:]
            raise BenchmarkError(f"Codex benchmark role failed with code {process.returncode}: {detail}")
        if not response_path.is_file():
            raise BenchmarkError("Codex completed without a final response.")
        response = response_path.read_text(errors="replace").strip()
        if not response:
            raise BenchmarkError("Codex returned an empty final response.")
        logs = invocation.workspace / "logs"
        logs.mkdir(exist_ok=True)
        stdout_path, stderr_path = logs / "stdout.log", logs / "stderr.log"
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        return CodexInvocationResult(response, str(stdout_path), str(stderr_path), str(response_path))


class CodexBenchmarkRunner:
    """Executes two Skills separately, then gives anonymous outputs to a third Codex."""

    _GRADER_SCHEMA: dict[str, Any] = {
        "type": "object",
        "properties": {
            "winner": {"type": "string", "enum": ["A", "B", "tie"]},
            "a_pass": {"type": "boolean"},
            "b_pass": {"type": "boolean"},
            "a_score": {"type": "number", "minimum": 0, "maximum": 1},
            "b_score": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["winner", "a_pass", "b_pass", "a_score", "b_score", "reason"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        client: CodexClient,
        workspace_root: Path,
        *,
        executor_model: str | None = None,
        grader_model: str | None = None,
    ) -> None:
        self.client = client
        self.workspace_root = workspace_root.resolve()
        self.executor_model = executor_model
        self.grader_model = grader_model

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "mode": "isolated-blind-codex",
            "executor_model": self.executor_model or "codex-default",
            "grader_model": self.grader_model or self.executor_model or "codex-default",
            "grader_prompt_version": "blind-pairwise-v1",
            "deterministic_check_version": "v1",
        }

    async def run_case(
        self,
        *,
        run_id: UUID,
        case: EvalCase,
        candidate_archive: bytes,
        baseline_archive: bytes,
    ) -> BenchmarkCaseResult:
        started = time.monotonic()
        self.workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        task = self._task(case)

        # Temporary role roots are created and removed one at a time. Neither
        # executor can discover the other Skill or output, and the grader cannot
        # discover either executor workspace.
        candidate_output, candidate_evidence = await self._execute(candidate_archive, task, "candidate")
        baseline_output, baseline_evidence = await self._execute(baseline_archive, task, "baseline")

        candidate_checks = self._run_deterministic_checks(candidate_output, case)
        baseline_checks = self._run_deterministic_checks(baseline_output, case)
        deterministic = self._deterministic_verdict(candidate_checks, baseline_checks)
        if deterministic is None:
            rubric = self._rubric(case)
            blind, grader_evidence = await self._judge(task, rubric, candidate_output, baseline_output)
            verdict = self._normalize_blind_verdict(blind)
            mode = "blind_codex"
        else:
            verdict = deterministic
            blind, grader_evidence = None, None
            mode = "deterministic"

        case_root = self.workspace_root / str(run_id) / str(case.id)
        case_root.mkdir(parents=True, exist_ok=False, mode=0o700)
        candidate_path = case_root / "candidate" / "output.md"
        baseline_path = case_root / "baseline" / "output.md"
        candidate_path.parent.mkdir(mode=0o700)
        baseline_path.parent.mkdir(mode=0o700)
        candidate_path.write_text(candidate_output)
        baseline_path.write_text(baseline_output)
        candidate_path.chmod(0o600)
        baseline_path.chmod(0o600)
        candidate_evidence = self._persist_evidence(candidate_path.parent, candidate_evidence)
        baseline_evidence = self._persist_evidence(baseline_path.parent, baseline_evidence)
        if grader_evidence is not None:
            grader_evidence = self._persist_evidence(case_root / "grader", grader_evidence)

        grader_output = {
            "grader": mode,
            "winner": verdict["winner"],
            "candidate_pass": verdict["candidate_pass"],
            "baseline_pass": verdict["baseline_pass"],
            "candidate_score": verdict["candidate_score"],
            "baseline_score": verdict["baseline_score"],
            "deterministic_checks": {
                "candidate": candidate_checks,
                "baseline": baseline_checks,
            },
            "executor_evidence": {"candidate": candidate_evidence, "baseline": baseline_evidence},
        }
        if blind is not None:
            # Store the audit mapping only after grading. It was never part of the
            # grader prompt and cannot influence the blind decision.
            grader_output["blind_judgment"] = blind["judgment"]
            grader_output["blind_order"] = blind["order"]
            grader_output["grader_evidence"] = grader_evidence

        return BenchmarkCaseResult(
            candidate_output=candidate_output,
            baseline_output=baseline_output,
            candidate_output_path=str(candidate_path),
            baseline_output_path=str(baseline_path),
            candidate_pass=verdict["candidate_pass"],
            baseline_pass=verdict["baseline_pass"],
            candidate_score=verdict["candidate_score"],
            baseline_score=verdict["baseline_score"],
            winner=verdict["winner"],
            grader_output=grader_output,
            latency_ms=round((time.monotonic() - started) * 1_000),
        )

    async def _execute(self, archive: bytes, task: dict[str, Any], role: str) -> tuple[str, dict[str, bytes]]:
        with tempfile.TemporaryDirectory(prefix=f"skill-eval-{role}-") as temporary:
            workspace = Path(temporary)
            self._extract_skill(archive, workspace / "skill")
            prompt = (
                "You are an execution agent, not a grader. Read and follow skill/SKILL.md and its bundled "
                "references as the only Skill package for this run. Complete the task below. Do not evaluate "
                "your answer, compare variants, or mention this benchmark. Return only the task answer.\n\n"
                f"TASK\n{json.dumps(task, ensure_ascii=False, sort_keys=True)}"
            )
            result = await self.client.invoke(CodexInvocation(prompt=prompt, workspace=workspace))
            return result.response, self._read_evidence(result)

    async def _judge(
        self,
        task: dict[str, Any],
        rubric: dict[str, Any],
        candidate_output: str,
        baseline_output: str,
    ) -> tuple[dict[str, Any], dict[str, bytes]]:
        candidate_is_a = bool(secrets.randbits(1))
        outputs = (
            {"A": candidate_output, "B": baseline_output}
            if candidate_is_a
            else {"A": baseline_output, "B": candidate_output}
        )
        prompt = (
            "You are an independent blind grader. You did not produce either response. Grade only the task, "
            "rubric, and anonymous responses A and B below. Do not infer authorship. Decide whether each response "
            "passes the rubric, score each from 0 to 1, and choose A, B, or tie. Return only the required JSON.\n\n"
            f"TASK\n{json.dumps(task, ensure_ascii=False, sort_keys=True)}\n\n"
            f"RUBRIC\n{json.dumps(rubric, ensure_ascii=False, sort_keys=True)}\n\n"
            f"RESPONSE A\n{outputs['A']}\n\nRESPONSE B\n{outputs['B']}"
        )
        with tempfile.TemporaryDirectory(prefix="skill-eval-grader-") as temporary:
            result = await self.client.invoke(
                CodexInvocation(prompt=prompt, workspace=Path(temporary), output_schema=self._GRADER_SCHEMA)
            )
            try:
                judgment = json.loads(result.response)
            except json.JSONDecodeError as exc:
                raise BenchmarkError("Codex grader returned invalid JSON.") from exc
            self._validate_judgment(judgment)
            evidence = self._read_evidence(result)
        return {
            "judgment": judgment,
            "order": {"candidate": "A" if candidate_is_a else "B", "baseline": "B" if candidate_is_a else "A"},
        }, evidence

    @staticmethod
    def _read_evidence(result: CodexInvocationResult) -> dict[str, bytes]:
        return {
            "stdout": Path(result.stdout_path).read_bytes(),
            "stderr": Path(result.stderr_path).read_bytes(),
            "transcript": Path(result.transcript_path).read_bytes(),
        }

    @staticmethod
    def _persist_evidence(destination: Path, evidence: dict[str, bytes]) -> dict[str, str]:
        logs = destination / "logs"
        logs.mkdir(parents=True, exist_ok=True, mode=0o700)
        paths = {
            "stdout_path": logs / "stdout.log",
            "stderr_path": logs / "stderr.log",
            "transcript_path": logs / "transcript.txt",
        }
        paths["stdout_path"].write_bytes(evidence["stdout"])
        paths["stderr_path"].write_bytes(evidence["stderr"])
        paths["transcript_path"].write_bytes(evidence["transcript"])
        for path in paths.values():
            path.chmod(0o600)
        return {key: str(path) for key, path in paths.items()}

    @staticmethod
    def _task(case: EvalCase) -> dict[str, Any]:
        return {"prompt": case.prompt, "files": case.files}

    @staticmethod
    def _rubric(case: EvalCase) -> dict[str, Any]:
        rubric = case.expectations.get("rubric")
        if rubric is None and case.expected_output is None:
            raise BenchmarkError("A Codex-graded case requires expectations.rubric or expected_output.")
        return {"criteria": rubric, "expected_output": case.expected_output}

    @staticmethod
    def _run_deterministic_checks(output: str, case: EvalCase) -> list[dict[str, Any]]:
        configured = case.expectations.get("deterministic_checks")
        if configured is None:
            contains_all = case.expectations.get("contains_all", [])
            not_contains = case.expectations.get("not_contains", [])
            if not isinstance(contains_all, list) or not isinstance(not_contains, list):
                raise BenchmarkError("expectations.contains_all and not_contains must be lists.")
            configured = [
                *({"type": "contains", "value": value} for value in contains_all),
                *({"type": "not_contains", "value": value} for value in not_contains),
            ]
        if not isinstance(configured, list):
            raise BenchmarkError("expectations.deterministic_checks must be a list.")
        results: list[dict[str, Any]] = []
        for index, check in enumerate(configured):
            if not isinstance(check, dict) or not isinstance(check.get("type"), str):
                raise BenchmarkError(f"Deterministic check {index} must be an object with a type.")
            kind = check["type"]
            value = check.get("value")
            case_sensitive = bool(check.get("case_sensitive", True))
            actual = output if case_sensitive else output.casefold()
            expected = value if case_sensitive or not isinstance(value, str) else value.casefold()
            try:
                if kind == "contains" and isinstance(expected, str):
                    passed = expected in actual
                elif kind == "not_contains" and isinstance(expected, str):
                    passed = expected not in actual
                elif kind == "equals" and isinstance(expected, str):
                    passed = actual.strip() == expected.strip()
                elif kind == "regex" and isinstance(value, str):
                    flags = 0 if case_sensitive else re.IGNORECASE
                    passed = re.search(value, output, flags) is not None
                elif kind == "valid_json":
                    json.loads(output)
                    passed = True
                elif kind == "min_length" and isinstance(value, int):
                    passed = len(output) >= value
                elif kind == "max_length" and isinstance(value, int):
                    passed = len(output) <= value
                else:
                    raise BenchmarkError(f"Unsupported or invalid deterministic check: {kind}")
            except (json.JSONDecodeError, re.error):
                passed = False
            results.append({"type": kind, "passed": passed})
        return results

    @staticmethod
    def _deterministic_verdict(
        candidate_checks: list[dict[str, Any]], baseline_checks: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        if not candidate_checks:
            return None
        candidate_pass = all(item["passed"] for item in candidate_checks)
        baseline_pass = all(item["passed"] for item in baseline_checks)
        if candidate_pass and baseline_pass:
            return None
        winner: Literal["candidate", "baseline", "tie"]
        if candidate_pass:
            winner = "candidate"
        elif baseline_pass:
            winner = "baseline"
        else:
            winner = "tie"
        return {
            "candidate_pass": candidate_pass,
            "baseline_pass": baseline_pass,
            "candidate_score": float(candidate_pass),
            "baseline_score": float(baseline_pass),
            "winner": winner,
        }

    @staticmethod
    def _normalize_blind_verdict(blind: dict[str, Any]) -> dict[str, Any]:
        judgment = blind["judgment"]
        order = blind["order"]
        candidate_label = order["candidate"]
        baseline_label = order["baseline"]
        winner_label = judgment["winner"]
        if winner_label == "tie":
            winner = "tie"
        elif winner_label == candidate_label:
            winner = "candidate"
        else:
            winner = "baseline"
        return {
            "candidate_pass": judgment[f"{candidate_label.lower()}_pass"],
            "baseline_pass": judgment[f"{baseline_label.lower()}_pass"],
            "candidate_score": float(judgment[f"{candidate_label.lower()}_score"]),
            "baseline_score": float(judgment[f"{baseline_label.lower()}_score"]),
            "winner": winner,
        }

    @staticmethod
    def _validate_judgment(value: Any) -> None:
        if not isinstance(value, dict) or value.get("winner") not in {"A", "B", "tie"}:
            raise BenchmarkError("Codex grader returned an invalid winner.")
        for label in ("a", "b"):
            if not isinstance(value.get(f"{label}_pass"), bool):
                raise BenchmarkError("Codex grader returned an invalid pass decision.")
            score = value.get(f"{label}_score")
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
                raise BenchmarkError("Codex grader returned an invalid score.")
        if not isinstance(value.get("reason"), str):
            raise BenchmarkError("Codex grader returned an invalid reason.")

    @staticmethod
    def _extract_skill(archive: bytes, destination: Path) -> None:
        try:
            package = zipfile.ZipFile(io.BytesIO(archive))
        except zipfile.BadZipFile as exc:
            raise BenchmarkError("Benchmark artifact is not a valid zip archive.") from exc
        with package:
            for item in package.infolist():
                relative = PurePosixPath(item.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise BenchmarkError("Benchmark artifact contains an unsafe path.")
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise BenchmarkError("Benchmark artifact contains a symbolic link.")
                path = destination.joinpath(*relative.parts)
                if item.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(package.read(item))
        if not (destination / "SKILL.md").is_file():
            raise BenchmarkError("Benchmark artifact is missing SKILL.md.")
