"""Optional Promptfoo regression-suite adapter.

Promptfoo is not the canonical release gate in V1; the blind Codex benchmark is.
This adapter exists so selected repeatable suites can be enabled explicitly without
coupling their native JSON format to registry records.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from .base import EngineHealth


class PromptfooAdapter:
    name = "promptfoo"

    def __init__(self, executable: str, enabled: bool) -> None:
        self.executable = executable
        self.enabled = enabled

    async def healthcheck(self) -> EngineHealth:
        if not self.enabled:
            return EngineHealth(False, "disabled by PROMPTFOO_ENABLED")
        path = shutil.which(self.executable)
        return EngineHealth(bool(path), f"{self.executable}: {path or 'not found'}")

    async def run_suite(self, config_path: Path, output_path: Path) -> dict[str, Any]:
        health = await self.healthcheck()
        if not health.available:
            raise RuntimeError(f"Promptfoo is unavailable ({health.detail}).")
        if not config_path.is_file():
            raise ValueError("Promptfoo config does not exist.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        process = await asyncio.create_subprocess_exec(
            self.executable, "eval", "-c", str(config_path), "--output", str(output_path),
            cwd=config_path.parent, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"Promptfoo exited with code {process.returncode}: {stderr.decode(errors='replace')[-1000:]}")
        if not output_path.is_file():
            raise RuntimeError("Promptfoo completed without a JSON output file.")
        try:
            result = json.loads(output_path.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError("Promptfoo output was not valid JSON.") from exc
        return {"result": result, "stdout": stdout.decode(errors="replace"), "stderr": stderr.decode(errors="replace")}
