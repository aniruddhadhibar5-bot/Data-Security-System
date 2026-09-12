"""Tests for catalog organization and advanced search."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.catalog import CatalogService
from core.database import Database
from core.search import SearchQuery, SortMode, VaultSearch
from core.vault import VaultService


class CatalogSearchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.directory.name) / "catalog.db")
        self.vault = VaultService(self.database)
        self.vault.configure_master("A secure and unique master password!2026", "246810")
        self.vault.authenticate("A secure and unique master password!2026", "246810")
        self.catalog = CatalogService(self.database)
        self.search = VaultSearch(self.database, self.catalog)
        self.first = self.vault.store_secret("NOTE", "Travel plans", {"body": "private"})
        self.second = self.vault.store_secret("PASSWORD", "Mail account", {"password": "private"})

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_normalize_tags(self):
        self.assertEqual(self.catalog.normalize_tags([" Work ", "work", "Client/One"]), ("client-one", "work"))

    def test_set_and_read_tags(self):
        self.assertEqual(self.catalog.set_tags(self.first, ["Travel", "Personal"]), ("personal", "travel"))
        self.assertEqual(self.catalog.tags_for(self.first), ("personal", "travel"))

    def test_add_and_remove_tag(self):
        self.catalog.add_tag(self.first, "important")
        self.assertIn("important", self.catalog.tags_for(self.first))
        self.catalog.remove_tag(self.first, "important")
        self.assertNotIn("important", self.catalog.tags_for(self.first))

    def test_all_tags_are_sorted(self):
        self.catalog.set_tags(self.first, ["zeta", "alpha"])
        self.catalog.set_tags(self.second, ["beta"])
        self.assertEqual(self.catalog.all_tags(), ["alpha", "beta", "zeta"])

    def test_favorite_toggle(self):
        self.assertTrue(self.catalog.toggle_favorite(self.first))
        self.assertTrue(self.catalog.flags_for(self.first)["favorite"])
        self.assertFalse(self.catalog.toggle_favorite(self.first))

    def test_archive_toggle_hides_item_by_default(self):
        self.catalog.toggle_archive(self.first)
        self.assertEqual(len(self.catalog.catalog_items()), 1)
        self.assertEqual(len(self.catalog.catalog_items(include_archived=True)), 2)

    def test_summary_counts_flags_and_tags(self):
        self.catalog.set_tags(self.first, ["one"])
        self.catalog.toggle_favorite(self.first)
        summary = self.catalog.summary()
        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.favorites, 1)
        self.assertEqual(summary.tagged, 1)
        self.assertEqual(summary.tag_counts["one"], 1)

    def test_catalog_export_and_import(self):
        self.catalog.set_tags(self.first, ["exported"])
        self.catalog.toggle_favorite(self.first)
        records = self.catalog.export_catalog()
        self.catalog.clear_item(self.first)
        self.assertEqual(self.catalog.import_catalog(records), 2)
        self.assertEqual(self.catalog.tags_for(self.first), ("exported",))

    def test_search_text_matches_tags(self):
        self.catalog.set_tags(self.first, ["holiday"])
        result = self.search.query(SearchQuery(text="holiday"))
        self.assertEqual([item.item_id for item in result.items], [self.first])

    def test_search_kind_filter(self):
        result = self.search.query(SearchQuery(kind="PASSWORD"))
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].item_id, self.second)

    def test_search_tag_filter(self):
        self.catalog.set_tags(self.first, ["private"])
        result = self.search.by_tag("private")
        self.assertEqual(len(result.items), 1)

    def test_favorites_search(self):
        self.catalog.toggle_favorite(self.second)
        result = self.search.favorites()
        self.assertEqual([item.item_id for item in result.items], [self.second])

    def test_title_sort(self):
        result = self.search.query(SearchQuery(sort=SortMode.TITLE, descending=False))
        self.assertEqual(result.items[0].title, "Mail account")

    def test_group_by_kind(self):
        groups = self.search.group_by_kind(self.search.query(SearchQuery()))
        self.assertEqual(len(groups["NOTE"]), 1)
        self.assertEqual(len(groups["PASSWORD"]), 1)

    def test_group_by_tag_includes_untagged(self):
        groups = self.search.group_by_tag(self.search.query(SearchQuery()))
        self.assertEqual(len(groups["untagged"]), 2)

    def test_suggestions(self):
        self.catalog.set_tags(self.first, ["holiday"])
        self.assertIn("holiday", self.search.suggest("hol"))

    def test_recent_limit(self):
        self.assertEqual(len(self.search.recent(1).items), 1)

    def test_deleted_catalog_metadata_can_be_cleaned(self):
        self.catalog.set_tags(self.first, ["orphan"])
        self.database.delete_item(self.first)
        self.assertEqual(self.catalog.remove_deleted_items(), 1)


if __name__ == "__main__":
    unittest.main()
