"""Regression tests for encrypted portable backup behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.backup import BackupService
from core.database import Database
from core.security import SecurityManager
from core.vault import VaultService


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = Database(self.root / "security.db")
        self.vault = VaultService(self.database)
        self.vault.configure_master("A secure and unique master password!2026", "246810")
        self.vault.authenticate("A secure and unique master password!2026", "246810")
        self.vault.store_secret("NOTE", "Backup note", {"body": "private backup content"})
        self.service = BackupService(self.database, SecurityManager())
        self.destination = self.root / "workspace.dssbackup"

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_create_backup(self):
        self.service.create_backup(self.destination, self.vault.master_key)
        self.assertTrue(self.destination.exists())
        self.assertGreater(self.service.backup_size(self.destination), 12)

    def test_manifest_is_valid(self):
        self.service.create_backup(self.destination, self.vault.master_key)
        self.assertTrue(self.service.validate_manifest(self.destination, self.vault.master_key))

    def test_manifest_contains_database(self):
        self.service.create_backup(self.destination, self.vault.master_key)
        manifest = self.service.inspect_backup(self.destination, self.vault.master_key)
        self.assertEqual(manifest["format"], "dss-backup")
        self.assertIn("security.db", self.service.list_entries(self.destination, self.vault.master_key))

    def test_backup_summary_reports_entries(self):
        self.service.create_backup(self.destination, self.vault.master_key)
        summary = self.service.backup_summary(self.destination, self.vault.master_key)
        self.assertGreaterEqual(summary["entries"], 2)
        self.assertEqual(summary["version"], 1)

    def test_wrong_key_cannot_inspect(self):
        self.service.create_backup(self.destination, self.vault.master_key)
        wrong_key = SecurityManager().derive_key("wrong password", b"0123456789abcdef")
        with self.assertRaises(Exception):
            self.service.inspect_backup(self.destination, wrong_key)

    def test_tampered_backup_is_rejected(self):
        self.service.create_backup(self.destination, self.vault.master_key)
        raw = bytearray(self.destination.read_bytes())
        raw[-1] ^= 1
        self.destination.write_bytes(raw)
        self.assertFalse(self.service.validate_manifest(self.destination, self.vault.master_key))

    def test_invalid_small_file_is_rejected(self):
        self.destination.write_bytes(b"too-small")
        self.assertFalse(self.service.validate_manifest(self.destination, self.vault.master_key))

    def test_decrypted_archive_is_not_written_by_service(self):
        self.service.create_backup(self.destination, self.vault.master_key)
        archive = self.service.decrypt_archive(self.destination, self.vault.master_key)
        self.assertIn(b"manifest.json", archive)
        self.assertFalse((self.root / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()