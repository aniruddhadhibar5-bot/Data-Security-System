"""Encrypted portable backup support.

Backups are encrypted with the already authenticated master key and contain the
SQLite records plus encrypted file payloads. Plaintext secrets never leave the
vault service during export.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

from config import VAULT_DIR
from core.database import Database
from core.security import EncryptedValue, SecurityManager


class BackupService:
    def __init__(self, database: Database, security: SecurityManager):
        self.database = database
        self.security = security

    def create_backup(self, destination: Path, master_key: bytes) -> Path:
        manifest = {
            "format": "dss-backup",
            "version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "database": self.database.path.name,
        }
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
            bundle.writestr("security.db", self.database.path.read_bytes())
            if VAULT_DIR.exists():
                for file_path in VAULT_DIR.iterdir():
                    if file_path.is_file():
                        bundle.writestr(f"vault/{file_path.name}", file_path.read_bytes())
        encrypted = self.security.encrypt(archive.getvalue(), master_key, b"dss-backup-v1")
        destination.write_bytes(encrypted.nonce + encrypted.ciphertext)
        self.database.add_audit("BACKUP", f"Encrypted backup exported: {destination.name}")
        return destination

    def inspect_backup(self, source: Path, master_key: bytes) -> dict:
        raw = source.read_bytes()
        encrypted = EncryptedValue(raw[:12], raw[12:])
        archive = self.security.decrypt(encrypted, master_key, b"dss-backup-v1")
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            manifest["files"] = [name for name in bundle.namelist() if name.startswith("vault/")]
            return manifest

    def decrypt_archive(self, source: Path, master_key: bytes) -> bytes:
        """Decrypt a backup into memory without writing any plaintext to disk."""
        raw = source.read_bytes()
        if len(raw) <= 12:
            raise ValueError("Backup is too small to contain an authenticated payload")
        return self.security.decrypt(EncryptedValue(raw[:12], raw[12:]), master_key, b"dss-backup-v1")

    def list_entries(self, source: Path, master_key: bytes) -> list[str]:
        with zipfile.ZipFile(io.BytesIO(self.decrypt_archive(source, master_key))) as bundle:
            return sorted(bundle.namelist())

    def validate_manifest(self, source: Path, master_key: bytes) -> bool:
        try:
            with zipfile.ZipFile(io.BytesIO(self.decrypt_archive(source, master_key))) as bundle:
                manifest = json.loads(bundle.read("manifest.json"))
                return manifest.get("format") == "dss-backup" and manifest.get("version") == 1
        except Exception:
            return False

    def backup_size(self, source: Path) -> int:
        return source.stat().st_size

    def backup_summary(self, source: Path, master_key: bytes) -> dict[str, int | str]:
        manifest = self.inspect_backup(source, master_key)
        entries = self.list_entries(source, master_key)
        return {"format": manifest["format"], "version": manifest["version"], "files": len(manifest["files"]), "entries": len(entries), "bytes": self.backup_size(source)}
