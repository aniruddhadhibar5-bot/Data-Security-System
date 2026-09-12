"""Input validation rules shared by the desktop views and services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    message: str = ""

    def __bool__(self) -> bool:
        return self.valid


class InputValidator:
    TITLE_LIMIT = 160
    NOTE_LIMIT = 1_000_000
    USERNAME_LIMIT = 320

    def title(self, value: str) -> ValidationResult:
        value = value.strip()
        if not value:
            return ValidationResult(False, "A title is required.")
        if len(value) > self.TITLE_LIMIT:
            return ValidationResult(False, f"Titles must be {self.TITLE_LIMIT} characters or fewer.")
        if any(ord(character) < 32 for character in value):
            return ValidationResult(False, "Titles cannot contain control characters.")
        return ValidationResult(True)

    def username(self, value: str) -> ValidationResult:
        value = value.strip()
        if not value:
            return ValidationResult(False, "A username or email is required.")
        if len(value) > self.USERNAME_LIMIT:
            return ValidationResult(False, "The username is too long.")
        return ValidationResult(True)

    def password(self, value: str) -> ValidationResult:
        if not value:
            return ValidationResult(False, "A password is required.")
        if len(value) < 12:
            return ValidationResult(False, "Passwords must contain at least 12 characters.")
        return ValidationResult(True)

    def pin(self, value: str) -> ValidationResult:
        if not re.fullmatch(r"\d{6}", value):
            return ValidationResult(False, "The verification PIN must contain exactly six digits.")
        if len(set(value)) == 1:
            return ValidationResult(False, "Choose a PIN that is not one repeated digit.")
        return ValidationResult(True)

    def note_body(self, value: str) -> ValidationResult:
        if not value.strip():
            return ValidationResult(False, "A secure note cannot be empty.")
        if len(value) > self.NOTE_LIMIT:
            return ValidationResult(False, "This note is larger than the supported limit.")
        return ValidationResult(True)

    def file(self, path: Path) -> ValidationResult:
        if not path.exists():
            return ValidationResult(False, "The selected file no longer exists.")
        if not path.is_file():
            return ValidationResult(False, "The selected path is not a file.")
        if path.stat().st_size == 0:
            return ValidationResult(False, "Empty files are not accepted.")
        return ValidationResult(True)

    def safe_filename(self, name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
        return cleaned[:180] or "restored-file"


class SearchValidator:
    def normalize(self, query: str) -> str:
        return " ".join(query.casefold().split())

    def matches(self, query: str, *values: str) -> bool:
        normalized = self.normalize(query)
        if not normalized:
            return True
        haystack = " ".join(self.normalize(value) for value in values)
        return normalized in haystack


class RecoveryValidator:
    def item_key(self, value: str) -> ValidationResult:
        if len(value) != 64:
            return ValidationResult(False, "A recovery item key must be 32 bytes in hexadecimal form.")
        try:
            int(value, 16)
        except ValueError:
            return ValidationResult(False, "Recovery keys must use hexadecimal characters.")
        return ValidationResult(True)

    def backup_name(self, value: str) -> ValidationResult:
        if not value.lower().endswith(".dssbackup"):
            return ValidationResult(False, "Backups should use the .dssbackup extension.")
        return ValidationResult(True)
