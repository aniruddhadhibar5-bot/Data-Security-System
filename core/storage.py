"""Local storage inspection and file inventory helpers."""

from __future__ import annotations

import hashlib
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

from config import VAULT_DIR


@dataclass(frozen=True)
class FileProfile:
    path: Path
    name: str
    suffix: str
    mime_type: str
    size: int
    digest: str

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")

    @property
    def is_document(self) -> bool:
        return self.mime_type.startswith("text/") or self.suffix in {".pdf", ".doc", ".docx", ".odt", ".xls", ".xlsx"}


class FileInspector:
    def profile(self, path: Path, chunk_size: int = 1024 * 1024) -> FileProfile:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(chunk_size):
                digest.update(chunk)
                size += len(chunk)
        mime_type, _ = mimetypes.guess_type(path.name)
        return FileProfile(path, path.name, path.suffix.lower(), mime_type or "application/octet-stream", size, digest.hexdigest())

    def is_supported(self, path: Path) -> bool:
        return path.is_file() and path.stat().st_size > 0

    def category(self, profile: FileProfile) -> str:
        if profile.is_image:
            return "Image"
        if profile.is_document:
            return "Document"
        if profile.mime_type.startswith("video/"):
            return "Video"
        if profile.mime_type.startswith("audio/"):
            return "Audio"
        return "Other"

    def verify_digest(self, path: Path, expected: str) -> bool:
        return self.profile(path).digest == expected


class VaultInventory:
    def __init__(self, vault_dir: Path = VAULT_DIR):
        self.vault_dir = vault_dir
        self.inspector = FileInspector()

    def files(self) -> list[Path]:
        if not self.vault_dir.exists():
            return []
        return sorted((path for path in self.vault_dir.iterdir() if path.is_file()), key=lambda item: item.stat().st_mtime, reverse=True)

    def total_size(self) -> int:
        return sum(path.stat().st_size for path in self.files())

    def profiles(self) -> list[FileProfile]:
        return [self.inspector.profile(path) for path in self.files()]

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for profile in self.profiles():
            category = self.inspector.category(profile)
            counts[category] = counts.get(category, 0) + 1
        return counts

    def orphaned(self, referenced_paths: set[str]) -> list[Path]:
        return [path for path in self.files() if str(path) not in referenced_paths]

    def remove_orphaned(self, referenced_paths: set[str]) -> int:
        removed = 0
        for path in self.orphaned(referenced_paths):
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    def storage_report(self) -> dict[str, int | dict[str, int]]:
        return {"files": len(self.files()), "bytes": self.total_size(), "categories": self.category_counts()}


class StorageQuota:
    def __init__(self, maximum_bytes: int = 10 * 1024 * 1024 * 1024):
        self.maximum_bytes = maximum_bytes

    def can_add(self, current_bytes: int, incoming_bytes: int) -> bool:
        return current_bytes + incoming_bytes <= self.maximum_bytes

    def remaining(self, current_bytes: int) -> int:
        return max(0, self.maximum_bytes - current_bytes)

    def usage_ratio(self, current_bytes: int) -> float:
        if self.maximum_bytes <= 0:
            return 1.0
        return min(1.0, max(0.0, current_bytes / self.maximum_bytes))
