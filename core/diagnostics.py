"""Operational diagnostics for the local security workspace."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import DATABASE_PATH, VAULT_DIR
from core.database import Database


@dataclass(frozen=True)
class DiagnosticResult:
    name: str
    status: str
    detail: str
    severity: str = "info"


class DiagnosticsService:
    def __init__(self, database: Database):
        self.database = database

    def run_all(self) -> list[DiagnosticResult]:
        return [
            self.database_integrity(),
            self.database_connection(),
            self.vault_directory(),
            self.storage_capacity(),
            self.runtime_details(),
            self.file_manifest(),
        ]

    def database_integrity(self) -> DiagnosticResult:
        passed = self.database.startup_integrity_ok and self.database.integrity_ok()
        return DiagnosticResult("Database integrity", "PASS" if passed else "FAIL", "SHA-256 sidecar matches the current database" if passed else "Database changed outside the application", "success" if passed else "error")

    def database_connection(self) -> DiagnosticResult:
        try:
            self.database.connection.execute("SELECT 1").fetchone()
            return DiagnosticResult("Database connection", "PASS", "SQLite connection is responsive", "success")
        except sqlite3.Error as error:
            return DiagnosticResult("Database connection", "FAIL", str(error), "error")

    def vault_directory(self) -> DiagnosticResult:
        try:
            VAULT_DIR.mkdir(parents=True, exist_ok=True)
            writable = os.access(VAULT_DIR, os.W_OK)
            return DiagnosticResult("Vault directory", "PASS" if writable else "FAIL", str(VAULT_DIR), "success" if writable else "error")
        except OSError as error:
            return DiagnosticResult("Vault directory", "FAIL", str(error), "error")

    def storage_capacity(self) -> DiagnosticResult:
        usage = shutil.disk_usage(DATABASE_PATH.parent)
        free_gb = usage.free / (1024 ** 3)
        return DiagnosticResult("Storage capacity", "PASS" if free_gb > 0.5 else "WARN", f"{free_gb:.2f} GB available", "success" if free_gb > 0.5 else "warning")

    def runtime_details(self) -> DiagnosticResult:
        return DiagnosticResult("Runtime", "INFO", f"Python {sys.version_info.major}.{sys.version_info.minor} · {platform.system()} {platform.release()}")

    def file_manifest(self) -> DiagnosticResult:
        files = [path for path in VAULT_DIR.iterdir() if path.is_file()]
        total = sum(path.stat().st_size for path in files)
        return DiagnosticResult("Encrypted file manifest", "INFO", f"{len(files)} file payloads · {total / 1024:.1f} KB")

    def report_text(self) -> str:
        lines = ["DATA SECURITY SYSTEM DIAGNOSTIC REPORT", f"Generated: {datetime.now().isoformat(timespec='seconds')}", ""]
        for result in self.run_all():
            lines.append(f"[{result.status}] {result.name}: {result.detail}")
        return "\n".join(lines)

    def database_digest(self) -> str:
        if not DATABASE_PATH.exists():
            return ""
        return hashlib.sha256(DATABASE_PATH.read_bytes()).hexdigest()
