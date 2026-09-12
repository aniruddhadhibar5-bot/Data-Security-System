"""Tests for non-sensitive security reports and recommendations."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.database import Database
from core.reporting import ActivityReport, RecommendationEngine, ReportService
from core.vault import VaultService


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = Database(self.root / "report.db")
        self.vault = VaultService(self.database)
        self.vault.configure_master("A secure and unique master password!2026", "246810")
        self.vault.authenticate("A secure and unique master password!2026", "246810")
        self.vault.store_secret("NOTE", "Report note", {"body": "not exported"})
        self.service = ReportService(self.database)

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_report_has_score_and_health(self):
        report = self.service.build()
        self.assertGreaterEqual(report.score, 0)
        self.assertLessEqual(report.score, 100)
        self.assertIn("Workspace", report.health)

    def test_report_does_not_include_secret_payload(self):
        report = self.service.build()
        self.assertNotIn("not exported", self.service.plain_text(report))
        self.assertNotIn("not exported", str(report.as_dict()))

    def test_recommendation_engine_suggests_backup(self):
        report = self.service.build(backup_recent=False)
        self.assertTrue(any(item.code == "backup" for item in report.recommendations))

    def test_activity_has_requested_days(self):
        activity = ActivityReport(self.service.audit).daily(7)
        self.assertEqual(len(activity), 7)

    def test_activity_clamps_large_day_window(self):
        self.assertEqual(len(ActivityReport(self.service.audit).daily(100)), 31)

    def test_event_breakdown_contains_setup(self):
        self.assertIn("SETUP", self.service.activity.event_breakdown())

    def test_busiest_day(self):
        points = self.service.activity.daily(2)
        busiest = self.service.activity.busiest_day(points)
        self.assertIsNotNone(busiest)

    def test_json_export(self):
        destination = self.root / "report.json"
        self.service.save_json(destination)
        self.assertIn("recommendations", destination.read_text(encoding="utf-8"))
        self.assertNotIn("not exported", destination.read_text(encoding="utf-8"))

    def test_html_export(self):
        destination = self.root / "report.html"
        self.service.save_html(destination)
        self.assertIn("Security posture", destination.read_text(encoding="utf-8"))

    def test_text_export(self):
        destination = self.root / "report.txt"
        self.service.export(destination, "txt")
        self.assertIn("DATA SECURITY SYSTEM REPORT", destination.read_text(encoding="utf-8"))

    def test_invalid_format_defaults_to_json(self):
        destination = self.root / "report.data"
        self.service.export(destination, "unknown")
        self.assertIn("generated_at", destination.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
