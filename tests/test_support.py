"""Tests for validation, formatting, diagnostics, and audit reporting."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.audit import AuditService
from core.database import Database
from core.diagnostics import DiagnosticsService
from core.formatting import DateFormatter, FileFormatter, TextFormatter
from core.validators import InputValidator, RecoveryValidator, SearchValidator


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = InputValidator()

    def test_valid_title(self):
        self.assertTrue(self.validator.title("Official document"))

    def test_empty_title_fails(self):
        self.assertFalse(self.validator.title(""))

    def test_title_control_character_fails(self):
        self.assertFalse(self.validator.title("bad\nname"))

    def test_valid_pin(self):
        self.assertTrue(self.validator.pin("246810"))

    def test_repeated_pin_fails(self):
        self.assertFalse(self.validator.pin("111111"))

    def test_note_body_is_required(self):
        self.assertFalse(self.validator.note_body("  "))

    def test_safe_filename_removes_path_symbols(self):
        self.assertEqual(self.validator.safe_filename("report:/2026?.pdf"), "report__2026_.pdf")

    def test_recovery_key_validation(self):
        self.assertTrue(RecoveryValidator().item_key("a" * 64))
        self.assertFalse(RecoveryValidator().item_key("not-a-key"))


class SearchTests(unittest.TestCase):
    def test_normalize_collapses_spaces(self):
        self.assertEqual(SearchValidator().normalize("  Secure   Note "), "secure note")

    def test_matches_multiple_values(self):
        self.assertTrue(SearchValidator().matches("mail", "Example Mail", "account"))
        self.assertFalse(SearchValidator().matches("bank", "Example Mail", "account"))


class FormattingTests(unittest.TestCase):
    def test_file_sizes(self):
        formatter = FileFormatter()
        self.assertEqual(formatter.size(0), "0 B")
        self.assertEqual(formatter.size(1024), "1.0 KB")

    def test_digest_shortening(self):
        self.assertEqual(FileFormatter().short_digest("a" * 64, 10), "aaaaa...aaaaa")

    def test_text_truncation(self):
        self.assertEqual(TextFormatter().truncate("one two three", 8), "one t..." )

    def test_multiline_cleanup(self):
        self.assertEqual(TextFormatter().clean_multiline("\n hello  \n"), " hello")

    def test_date_display(self):
        self.assertEqual(DateFormatter().display("2026-09-11"), "11 Sep 2026, 00:00")


class ServiceReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "audit.db"
        self.database = Database(self.path)
        self.database.add_audit("TEST", "A test event")

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_diagnostics_report_contains_status(self):
        report = DiagnosticsService(self.database).report_text()
        self.assertIn("Database integrity", report)
        self.assertIn("[PASS]", report)

    def test_audit_events_are_dicts(self):
        events = AuditService(self.database).events()
        self.assertEqual(events[0]["event"], "TEST")

    def test_audit_counts(self):
        self.assertEqual(AuditService(self.database).event_counts()["TEST"], 1)

    def test_text_rendering(self):
        self.assertIn("A test event", AuditService(self.database).render_text())

    def test_csv_export(self):
        target = Path(self.directory.name) / "audit.csv"
        AuditService(self.database).export_csv(target)
        self.assertIn("TEST", target.read_text(encoding="utf-8"))

    def test_json_export(self):
        target = Path(self.directory.name) / "audit.json"
        AuditService(self.database).export_json(target)
        self.assertIn("A test event", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
