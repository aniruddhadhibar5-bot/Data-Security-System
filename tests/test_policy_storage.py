"""Tests for policy, storage inventory, and maintenance behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.maintenance import MaintenanceService
from core.policy import RateLimiter, SecurityPolicy, SessionPolicy
from core.storage import FileInspector, StorageQuota, VaultInventory


class PolicyTests(unittest.TestCase):
    def test_strong_master_password_passes(self):
        policy = SecurityPolicy()
        self.assertTrue(policy.validate_master_password("LongMaster!Password2026"))

    def test_short_master_password_fails(self):
        self.assertFalse(SecurityPolicy().validate_master_password("short"))

    def test_predictable_pin_fails(self):
        self.assertFalse(SecurityPolicy().validate_pin("123456"))

    def test_random_pin_passes(self):
        self.assertTrue(SecurityPolicy().validate_pin("246810"))

    def test_rate_limiter_blocks_after_limit(self):
        limiter = RateLimiter(3)
        self.assertTrue(limiter.record_failure())
        self.assertTrue(limiter.record_failure())
        self.assertFalse(limiter.record_failure())
        self.assertTrue(limiter.blocked)

    def test_rate_limiter_success_resets(self):
        limiter = RateLimiter(2)
        limiter.record_failure()
        limiter.record_success()
        self.assertEqual(limiter.remaining(), 2)

    def test_session_policy_locks_after_timeout(self):
        policy = SessionPolicy(SecurityPolicy(lock_timeout_seconds=20))
        policy.touch(100)
        self.assertFalse(policy.should_lock(119))
        self.assertTrue(policy.should_lock(120))

    def test_session_policy_reset(self):
        policy = SessionPolicy(SecurityPolicy())
        policy.touch(100)
        policy.reset()
        self.assertFalse(policy.should_lock(1000))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.file = self.root / "document.txt"
        self.file.write_text("private content", encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def test_profile_has_digest(self):
        profile = FileInspector().profile(self.file)
        self.assertEqual(len(profile.digest), 64)
        self.assertEqual(profile.category if hasattr(profile, "category") else "", "")

    def test_profile_detects_document(self):
        self.assertTrue(FileInspector().profile(self.file).is_document)

    def test_digest_verification(self):
        inspector = FileInspector()
        digest = inspector.profile(self.file).digest
        self.assertTrue(inspector.verify_digest(self.file, digest))
        self.assertFalse(inspector.verify_digest(self.file, "0" * 64))

    def test_inventory_reports_files(self):
        inventory = VaultInventory(self.root)
        report = inventory.storage_report()
        self.assertEqual(report["files"], 1)
        self.assertGreater(report["bytes"], 0)

    def test_inventory_categories(self):
        self.assertEqual(VaultInventory(self.root).category_counts()["Document"], 1)

    def test_orphan_detection(self):
        inventory = VaultInventory(self.root)
        self.assertEqual(inventory.orphaned(set()), [self.file])
        self.assertEqual(inventory.orphaned({str(self.file)}), [])

    def test_orphan_removal(self):
        inventory = VaultInventory(self.root)
        self.assertEqual(inventory.remove_orphaned(set()), 1)
        self.assertFalse(self.file.exists())

    def test_quota(self):
        quota = StorageQuota(100)
        self.assertTrue(quota.can_add(50, 50))
        self.assertFalse(quota.can_add(50, 51))
        self.assertEqual(quota.remaining(25), 75)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = Database(self.root / "security.db")
        self.inventory = VaultInventory(self.root / "vault")
        self.inventory.vault_dir.mkdir()
        self.maintenance = MaintenanceService(self.database, self.inventory)

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_snapshot_contains_digest(self):
        snapshot = self.maintenance.integrity_snapshot()
        self.assertEqual(len(snapshot["database_digest"]), 64)

    def test_orphaned_payloads_are_reported(self):
        orphan = self.inventory.vault_dir / "unused.dsv"
        orphan.write_bytes(b"encrypted")
        self.assertEqual(self.maintenance.orphaned_payloads(), [orphan])

    def test_orphaned_payloads_can_be_cleaned(self):
        orphan = self.inventory.vault_dir / "unused.dsv"
        orphan.write_bytes(b"encrypted")
        result = self.maintenance.clean_orphaned_payloads()
        self.assertEqual(result.changed, 1)
        self.assertFalse(orphan.exists())

    def test_maintenance_report_has_database_entry(self):
        names = [item.name for item in self.maintenance.maintenance_report()]
        self.assertIn("Database", names)


if __name__ == "__main__":
    unittest.main()
