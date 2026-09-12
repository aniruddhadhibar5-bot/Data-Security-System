"""Tests for encrypted single-record packages."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.catalog import CatalogService
from core.database import Database
from core.portable import PortableRecordService
from core.vault import VaultService


class PortableRecordTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = Database(self.root / "portable.db")
        self.vault = VaultService(self.database)
        self.vault.configure_master("A secure and unique master password!2026", "246810")
        self.vault.authenticate("A secure and unique master password!2026", "246810")
        self.catalog = CatalogService(self.database)
        self.portable = PortableRecordService(self.database, self.vault, self.catalog)
        self.item_id = self.vault.store_secret("NOTE", "Portable note", {"body": "private"})
        self.catalog.set_tags(self.item_id, ["shared", "note"])
        self.catalog.toggle_favorite(self.item_id)
        self.destination = self.root / "record.dssrecord"

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_package_contains_catalog_data(self):
        package = self.portable.package(self.item_id)
        self.assertEqual(package.title, "Portable note")
        self.assertEqual(package.tags, ("note", "shared"))
        self.assertTrue(package.favorite)

    def test_export_creates_encrypted_file(self):
        self.portable.export(self.item_id, self.destination)
        self.assertTrue(self.destination.exists())
        self.assertNotIn(b"private", self.destination.read_bytes())

    def test_preview_requires_unlocked_vault(self):
        self.portable.export(self.item_id, self.destination)
        self.vault.lock()
        with self.assertRaises(PermissionError):
            self.portable.preview(self.destination)

    def test_preview_returns_safe_metadata(self):
        self.portable.export(self.item_id, self.destination)
        preview = self.portable.preview(self.destination)
        self.assertEqual(preview["title"], "Portable note")
        self.assertNotIn("private", preview)

    def test_import_creates_new_encrypted_item(self):
        self.portable.export(self.item_id, self.destination)
        imported = self.portable.import_record(self.destination, "Imported note")
        self.assertNotEqual(imported, self.item_id)
        self.assertEqual(self.vault.read_secret(imported)["body"], "private")
        self.assertEqual(self.database.get_item(imported)["title"], "Imported note")

    def test_import_restores_tags(self):
        self.portable.export(self.item_id, self.destination)
        imported = self.portable.import_record(self.destination)
        self.assertEqual(self.catalog.tags_for(imported), ("note", "shared"))
        self.assertTrue(self.catalog.flags_for(imported)["favorite"])

    def test_json_package_is_inspectable_in_memory(self):
        value = self.portable.package_as_json(self.item_id)
        self.assertIn("Portable note", value)
        self.assertNotIn("private", value)

    def test_package_digest_is_stable(self):
        first = self.portable.package_digest(self.item_id)
        second = self.portable.package_digest(self.item_id)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_invalid_package_is_rejected(self):
        with self.assertRaises(ValueError):
            self.portable.validate({"format": "wrong"})

    def test_tampered_package_is_rejected(self):
        self.portable.export(self.item_id, self.destination)
        raw = bytearray(self.destination.read_bytes())
        raw[-1] ^= 1
        self.destination.write_bytes(raw)
        with self.assertRaises(Exception):
            self.portable.preview(self.destination)

    def test_rewrap_keeps_payload_readable(self):
        before = self.vault.read_secret(self.item_id)
        self.portable.rewrap(self.item_id)
        self.assertEqual(self.vault.read_secret(self.item_id), before)


if __name__ == "__main__":
    unittest.main()
