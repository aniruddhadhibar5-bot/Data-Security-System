"""Regression tests for persisted workspace settings."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.settings import (
    SETTING_DEFINITIONS,
    SettingsService,
    WorkspaceSettings,
    serialize_settings,
    setting_definition,
    setting_labels,
)


class SettingsServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.directory.name) / "settings.db")
        self.service = SettingsService(self.database)

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_defaults_are_safe(self):
        settings = self.service.settings
        self.assertEqual(settings.appearance, "Dark")
        self.assertEqual(settings.idle_timeout_seconds, 300)
        self.assertTrue(settings.confirm_deletions)

    def test_update_persists_values(self):
        self.service.update(appearance="Light", compact_audit_view=True)
        reloaded = SettingsService(self.database)
        self.assertEqual(reloaded.get("appearance"), "Light")
        self.assertTrue(reloaded.get("compact_audit_view"))

    def test_invalid_appearance_is_normalized(self):
        self.service.update(appearance="Neon")
        self.assertEqual(self.service.get("appearance"), "Dark")

    def test_timeout_is_clamped(self):
        self.service.update(idle_timeout_seconds=1, clipboard_timeout_seconds=99_999)
        self.assertEqual(self.service.get("idle_timeout_seconds"), 30)
        self.assertEqual(self.service.get("clipboard_timeout_seconds"), 3600)

    def test_backup_extension_gets_dot(self):
        self.service.update(backup_extension="backup")
        self.assertEqual(self.service.get("backup_extension"), ".backup")

    def test_reset_restores_defaults(self):
        self.service.update(appearance="Light", auto_refresh_seconds=90)
        reset = self.service.reset()
        self.assertEqual(reset, WorkspaceSettings())

    def test_unknown_setting_is_ignored(self):
        self.service.update(unknown_value="ignored")
        self.assertIsNone(self.service.get("unknown_value"))

    def test_corrupt_metadata_uses_defaults(self):
        self.database.set_metadata(SettingsService.KEY, "not-json")
        self.assertEqual(SettingsService(self.database).settings, WorkspaceSettings())

    def test_metadata_is_json(self):
        self.service.update(appearance="Light")
        stored = self.database.get_metadata(SettingsService.KEY)
        self.assertEqual(json.loads(stored)["appearance"], "Light")


class SettingsDefinitionTests(unittest.TestCase):
    def test_every_default_has_a_definition(self):
        names = {definition.name for definition in SETTING_DEFINITIONS}
        self.assertEqual(names, set(WorkspaceSettings().__dict__.keys()))

    def test_definition_lookup(self):
        self.assertEqual(setting_definition("appearance").label, "Appearance")
        self.assertIsNone(setting_definition("missing"))

    def test_labels_are_human_readable(self):
        self.assertIn("Idle timeout", setting_labels())

    def test_boolean_parser(self):
        definition = setting_definition("compact_audit_view")
        self.assertTrue(definition.parse("yes"))
        self.assertFalse(definition.parse("no"))

    def test_integer_parser(self):
        definition = setting_definition("auto_refresh_seconds")
        self.assertEqual(definition.parse("60"), 60)

    def test_serialization_is_indented_json(self):
        result = serialize_settings(WorkspaceSettings())
        self.assertIn("\n", result)
        self.assertIn("idle_timeout_seconds", result)


if __name__ == "__main__":
    unittest.main()
