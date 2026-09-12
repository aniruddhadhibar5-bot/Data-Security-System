"""Regression tests for cryptographic primitives and vault behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.passwords import PasswordGenerator, PasswordStrength
from core.security import EncryptedValue, SecurityManager
from core.vault import VaultService


class SecurityManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = SecurityManager()
        self.key = self.manager.derive_key("correct horse battery staple", b"0123456789abcdef")

    def test_derived_key_is_32_bytes(self):
        self.assertEqual(len(self.key), 32)

    def test_same_password_and_salt_are_stable(self):
        other = self.manager.derive_key("correct horse battery staple", b"0123456789abcdef")
        self.assertEqual(self.key, other)

    def test_different_salts_are_different(self):
        other = self.manager.derive_key("correct horse battery staple", b"fedcba9876543210")
        self.assertNotEqual(self.key, other)

    def test_encryption_round_trip(self):
        value = self.manager.encrypt(b"classified document", self.key)
        self.assertEqual(self.manager.decrypt(value, self.key), b"classified document")

    def test_encryption_has_unique_nonces(self):
        first = self.manager.encrypt(b"same", self.key)
        second = self.manager.encrypt(b"same", self.key)
        self.assertNotEqual(first.nonce, second.nonce)

    def test_associated_data_is_authenticated(self):
        value = self.manager.encrypt(b"data", self.key, b"record-1")
        with self.assertRaises(Exception):
            self.manager.decrypt(value, self.key, b"record-2")

    def test_packing_preserves_value(self):
        original = self.manager.encrypt(b"payload", self.key)
        restored = self.manager.unpack(self.manager.pack(original))
        self.assertIsInstance(restored, EncryptedValue)
        self.assertEqual(self.manager.decrypt(restored, self.key), b"payload")

    def test_fingerprint_is_sha256(self):
        self.assertEqual(len(self.manager.fingerprint(b"abc")), 64)


class VaultServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "test.db"
        self.database = Database(self.database_path)
        self.vault = VaultService(self.database)

    def tearDown(self):
        self.vault.lock()
        self.database.close()
        self.directory.cleanup()

    def test_new_vault_is_not_configured(self):
        self.assertFalse(self.vault.is_configured)

    def test_configuration_enables_authentication(self):
        self.vault.configure_master("a long master password", "246810")
        self.assertTrue(self.vault.authenticate("a long master password", "246810"))

    def test_wrong_password_fails(self):
        self.vault.configure_master("a long master password", "246810")
        self.assertFalse(self.vault.authenticate("a wrong master password", "246810"))

    def test_wrong_pin_fails(self):
        self.vault.configure_master("a long master password", "246810")
        self.assertFalse(self.vault.authenticate("a long master password", "135790"))

    def test_locked_vault_rejects_writes(self):
        with self.assertRaises(PermissionError):
            self.vault.store_secret("NOTE", "Locked", {"body": "secret"})

    def test_secret_round_trip(self):
        self.vault.configure_master("a long master password", "246810")
        item_id = self.vault.store_secret("NOTE", "Private", {"body": "secret"})
        self.assertEqual(self.vault.read_secret(item_id)["body"], "secret")

    def test_secret_update_keeps_item_key(self):
        self.vault.configure_master("a long master password", "246810")
        item_id = self.vault.store_secret("NOTE", "Private", {"body": "before"})
        key_before = self.vault.recovery_items()[0]["key"]
        self.vault.update_secret(item_id, "Renamed", {"body": "after"})
        key_after = self.vault.recovery_items()[0]["key"]
        self.assertEqual(key_before, key_after)
        self.assertEqual(self.vault.read_secret(item_id)["body"], "after")

    def test_search_is_case_insensitive(self):
        self.vault.configure_master("a long master password", "246810")
        self.vault.store_secret("PASSWORD", "Example Mail", {"password": "secret"})
        self.assertEqual(len(self.vault.search_items("PASSWORD", "example")), 1)

    def test_recovery_lists_unique_keys(self):
        self.vault.configure_master("a long master password", "246810")
        self.vault.store_secret("NOTE", "One", {"body": "1"})
        self.vault.store_secret("NOTE", "Two", {"body": "2"})
        keys = [item["key"] for item in self.vault.recovery_items()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_integrity_sidecar_is_valid(self):
        self.vault.configure_master("a long master password", "246810")
        self.assertTrue(self.database.integrity_ok())


class PasswordTests(unittest.TestCase):
    def test_generated_password_has_requested_length(self):
        self.assertEqual(len(PasswordGenerator().generate(32)), 32)

    def test_generated_password_has_selected_groups(self):
        result = PasswordGenerator().generate(32)
        self.assertTrue(any(character.islower() for character in result))
        self.assertTrue(any(character.isupper() for character in result))
        self.assertTrue(any(character.isdigit() for character in result))

    def test_short_password_is_weak(self):
        self.assertEqual(PasswordStrength().assess("abc").label, "Weak")

    def test_long_mixed_password_is_strong(self):
        assessment = PasswordStrength().assess("A very long and unique 2026! password")
        self.assertIn(assessment.label, ("Strong", "Excellent"))


if __name__ == "__main__":
    unittest.main()
