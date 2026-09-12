"""Search, filtering, and sorting for vault catalog views."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from core.catalog import CatalogItem, CatalogService
from core.database import Database
from core.validators import SearchValidator


class SortMode(str, Enum):
    UPDATED = "updated"
    CREATED = "created"
    TITLE = "title"
    KIND = "kind"
    FAVORITES = "favorites"


@dataclass(frozen=True)
class SearchQuery:
    text: str = ""
    kind: str | None = None
    tag: str | None = None
    favorites_only: bool = False
    include_archived: bool = False
    sort: SortMode = SortMode.UPDATED
    descending: bool = True


@dataclass(frozen=True)
class SearchResult:
    items: tuple[CatalogItem, ...]
    total_matches: int
    available_tags: tuple[str, ...]
    available_kinds: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not self.items

    @property
    def favorite_count(self) -> int:
        return sum(item.favorite for item in self.items)


class VaultSearch:
    def __init__(self, database: Database, catalog: CatalogService | None = None):
        self.database = database
        self.catalog = catalog or CatalogService(database)
        self.validator = SearchValidator()

    def query(self, request: SearchQuery) -> SearchResult:
        items = self.catalog.catalog_items(request.kind, request.tag, request.include_archived)
        if request.favorites_only:
            items = [item for item in items if item.favorite]
        if request.text:
            items = [item for item in items if self.validator.matches(request.text, item.title, item.kind, *item.tags)]
        items = self._sort(items, request.sort, request.descending)
        all_items = self.catalog.catalog_items(include_archived=True)
        return SearchResult(tuple(items), len(items), tuple(self.catalog.all_tags()), tuple(sorted({item.kind for item in all_items})))

    def _sort(self, items: Iterable[CatalogItem], mode: SortMode, descending: bool) -> list[CatalogItem]:
        values = list(items)
        if mode == SortMode.TITLE:
            key = lambda item: item.title.casefold()
        elif mode == SortMode.KIND:
            key = lambda item: (item.kind.casefold(), item.title.casefold())
        elif mode == SortMode.FAVORITES:
            key = lambda item: (item.favorite, item.updated_at)
        elif mode == SortMode.CREATED:
            key = lambda item: item.created_at
        else:
            key = lambda item: item.updated_at
        return sorted(values, key=key, reverse=descending)

    def by_tag(self, tag: str) -> SearchResult:
        return self.query(SearchQuery(tag=tag))

    def favorites(self) -> SearchResult:
        return self.query(SearchQuery(favorites_only=True))

    def recent(self, limit: int = 10) -> SearchResult:
        result = self.query(SearchQuery())
        return SearchResult(result.items[:limit], min(limit, result.total_matches), result.available_tags, result.available_kinds)

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted({row["kind"] for row in self.database.list_items()}))

    def suggest(self, text: str, limit: int = 8) -> list[str]:
        query = self.validator.normalize(text)
        if not query:
            return self.catalog.all_tags()[:limit]
        candidates = self.catalog.all_tags() + [row["title"] for row in self.database.list_items()]
        unique = []
        for candidate in candidates:
            if query in self.validator.normalize(candidate) and candidate not in unique:
                unique.append(candidate)
        return unique[:limit]

    def group_by_kind(self, result: SearchResult) -> dict[str, list[CatalogItem]]:
        groups: dict[str, list[CatalogItem]] = {}
        for item in result.items:
            groups.setdefault(item.kind, []).append(item)
        return groups

    def group_by_tag(self, result: SearchResult) -> dict[str, list[CatalogItem]]:
        groups: dict[str, list[CatalogItem]] = {}
        for item in result.items:
            for tag in item.tags or ("untagged",):
                groups.setdefault(tag, []).append(item)
        return groups

    def export_search(self, result: SearchResult) -> list[dict]:
        return [{"id": item.item_id, "kind": item.kind, "title": item.title, "tags": list(item.tags), "favorite": item.favorite, "archived": item.archived} for item in result.items]
