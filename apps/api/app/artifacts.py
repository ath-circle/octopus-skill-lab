import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

import httpx

from .config import Settings


class ArtifactValidationError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedArtifact:
    archive: bytes
    sha256: str


class SkillArchiveNormalizer:
    """Validates packages without ever executing an imported script."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes

    def normalize(
        self,
        archive: bytes,
        *,
        skill_id: UUID,
        slug: str,
        name: str,
        version: str = "0.1.0",
    ) -> NormalizedArtifact:
        if not archive:
            raise ArtifactValidationError("The uploaded archive is empty.")
        if len(archive) > self.max_bytes:
            raise ArtifactValidationError("The uploaded archive exceeds the configured size limit.")

        try:
            source = zipfile.ZipFile(io.BytesIO(archive))
        except zipfile.BadZipFile as exc:
            raise ArtifactValidationError("Expected a valid .zip Skill package.") from exc

        entries: dict[str, bytes] = {}
        with source:
            if len(source.infolist()) > 2_000:
                raise ArtifactValidationError("The archive contains too many files.")
            expanded = 0
            for info in source.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or not info.filename:
                    raise ArtifactValidationError("The archive contains an unsafe file path.")
                if info.is_dir():
                    continue
                if info.file_size > self.max_bytes or (
                    info.compress_size and info.file_size / info.compress_size > 150
                ):
                    raise ArtifactValidationError("The archive contains a suspiciously compressed file.")
                expanded += info.file_size
                if expanded > self.max_bytes:
                    raise ArtifactValidationError("The expanded archive exceeds the configured size limit.")
                entries[info.filename] = source.read(info)

        if "SKILL.md" not in entries:
            raise ArtifactValidationError("A Skill package must contain SKILL.md at its root.")

        manifest = self._read_json(entries.get("manifest.json"), "manifest.json")
        manifest.update(
            {
                "schema_version": "1.0",
                "skill_id": str(skill_id),
                "skill_slug": slug,
                "version": version,
                "name": name,
                "layer_type": manifest.get("layer_type", "compiled"),
                "status": "draft",
                "created_by_engine": manifest.get("created_by_engine", "import"),
            }
        )
        entries["manifest.json"] = self._json_bytes(manifest)

        provenance = self._read_json(entries.get("provenance.json"), "provenance.json")
        provenance.setdefault("sources", [])
        provenance.setdefault("rules", [])
        entries["provenance.json"] = self._json_bytes(provenance)
        entries.setdefault("CHANGELOG.md", b"# Changelog\n\n## 0.1.0\n\n- Imported into Skill Factory.\n")

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as destination:
            for filename in sorted(entries):
                destination.writestr(filename, entries[filename])
        normalized = output.getvalue()
        return NormalizedArtifact(normalized, hashlib.sha256(normalized).hexdigest())

    def archive_directory(self, directory: str) -> bytes:
        """Package a generated directory before the same normalizer validates it."""
        root = PurePosixPath(directory)
        # This path is used only by the local worker; pathlib keeps symlink checks below explicit.
        from pathlib import Path

        filesystem_root = Path(root)
        if not filesystem_root.is_dir():
            raise ArtifactValidationError("Engine did not produce a Skill directory.")
        output = io.BytesIO()
        expanded = 0
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(filesystem_root.rglob("*")):
                if not path.is_file():
                    continue
                if path.is_symlink():
                    raise ArtifactValidationError("Generated artifact contains a symbolic link.")
                relative = path.relative_to(filesystem_root).as_posix()
                if relative.startswith("../") or path.stat().st_size > self.max_bytes:
                    raise ArtifactValidationError("Generated artifact contains an unsafe file.")
                expanded += path.stat().st_size
                if expanded > self.max_bytes:
                    raise ArtifactValidationError("Generated artifact exceeds the configured size limit.")
                archive.write(path, relative)
        return output.getvalue()

    @staticmethod
    def filename_to_slug(filename: str) -> str:
        value = re.sub(r"[^a-z0-9]+", "-", filename.lower()).strip("-")
        return value or "imported-skill"

    @staticmethod
    def _read_json(value: bytes | None, label: str) -> dict:
        if value is None:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ArtifactValidationError(f"{label} is not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise ArtifactValidationError(f"{label} must contain a JSON object.")
        return parsed

    @staticmethod
    def _json_bytes(value: dict) -> bytes:
        return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


class SupabaseArtifactStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = {
            "apikey": settings.spb_secret_key,
            "Authorization": f"Bearer {settings.spb_secret_key}",
        }

    async def put(self, path: str, payload: bytes) -> None:
        url = f"{self.settings.supabase_url}/storage/v1/object/{self.settings.supabase_artifact_bucket}/{path}"
        headers = {**self.headers, "Content-Type": "application/zip", "x-upsert": "false"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, content=payload)
        response.raise_for_status()

    async def get(self, path: str) -> bytes:
        url = f"{self.settings.supabase_url}/storage/v1/object/{self.settings.supabase_artifact_bucket}/{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self.headers)
        response.raise_for_status()
        return response.content
