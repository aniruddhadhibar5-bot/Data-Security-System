"""Presentation-safe formatting helpers for the desktop application."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class FileFormatter:
    UNITS = ("B", "KB", "MB", "GB", "TB")

    def size(self, value: int | float) -> str:
        amount = float(max(value, 0))
        unit = self.UNITS[0]
        for unit in self.UNITS:
            if amount < 1024 or unit == self.UNITS[-1]:
                break
            amount /= 1024
        decimals = 0 if unit == "B" or amount >= 100 else 1
        return f"{amount:.{decimals}f} {unit}"

    def name(self, path: Path | str, fallback: str = "Untitled file") -> str:
        value = Path(path).name if path else fallback
        return value or fallback

    def extension(self, path: Path | str) -> str:
        suffix = Path(path).suffix.lower().lstrip(".")
        return suffix.upper() if suffix else "FILE"

    def short_digest(self, digest: str, characters: int = 16) -> str:
        if len(digest) <= characters:
            return digest
        half = max(characters // 2, 2)
        return f"{digest[:half]}...{digest[-half:]}"


class DateFormatter:
    INPUT_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")

    def parse(self, value: str) -> datetime | None:
        for format_string in self.INPUT_FORMATS:
            try:
                return datetime.strptime(value, format_string)
            except ValueError:
                continue
        return None

    def display(self, value: str, fallback: str = "Unknown time") -> str:
        parsed = self.parse(value)
        return parsed.strftime("%d %b %Y, %H:%M") if parsed else fallback

    def relative(self, value: str) -> str:
        parsed = self.parse(value)
        if not parsed:
            return "Unknown"
        seconds = max(0, int((datetime.now() - parsed).total_seconds()))
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{seconds // 60} min ago"
        if seconds < 86400:
            return f"{seconds // 3600} hr ago"
        return f"{seconds // 86400} days ago"


class TextFormatter:
    def truncate(self, value: str, length: int = 80) -> str:
        value = " ".join(value.split())
        if len(value) <= length:
            return value
        return value[: max(length - 3, 1)].rstrip() + "..."

    def bullets(self, values: list[str]) -> str:
        return "\n".join(f"• {value}" for value in values)

    def plural(self, count: int, singular: str, plural: str | None = None) -> str:
        word = singular if count == 1 else (plural or f"{singular}s")
        return f"{count} {word}"

    def clean_multiline(self, value: str) -> str:
        lines = [line.rstrip() for line in value.replace("\r\n", "\n").split("\n")]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)
