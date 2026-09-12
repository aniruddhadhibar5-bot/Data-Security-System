"""Organization view for tags, favorites, archive state, and search."""

from __future__ import annotations

import importlib
from typing import Any

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: python -m pip install -r requirements.txt") from error

from core.catalog import CatalogItem, CatalogService
from core.search import SearchQuery, SortMode, VaultSearch
from ui.widgets import COLORS, EmptyState, Panel, SearchBar, StatusBadge


class CatalogView(ctk.CTkFrame):
    """A reusable item browser that can be embedded in the main window."""

    def __init__(self, master, database, on_open, **kwargs):
        super().__init__(master, fg_color=COLORS["background"], **kwargs)
        self.database = database
        self.catalog = CatalogService(database)
        self.search = VaultSearch(database, self.catalog)
        self.on_open = on_open
        self.query = ""
        self.kind = None
        self.tag = None
        self.favorite_only = False
        self.include_archived = False
        self.sort_mode = SortMode.UPDATED
        self.sort_descending = True
        self._build()
        self.refresh()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkLabel(header, text="Vault organization", font=ctk.CTkFont(size=24, weight="bold"), text_color=COLORS["text"]).pack(anchor="w")
        ctk.CTkLabel(header, text="Search across encrypted records and organize them with local labels.", text_color=COLORS["muted"]).pack(anchor="w", pady=(4, 0))
        SearchBar(self, "Search titles, types, or tags", self.set_query).pack(fill="x", padx=24, pady=8)
        controls = Panel(self); controls.pack(fill="x", padx=24, pady=(4, 12))
        self.kind_menu = ctk.CTkOptionMenu(controls, values=["All types"], command=self.set_kind); self.kind_menu.pack(side="left", padx=12, pady=12)
        self.tag_menu = ctk.CTkOptionMenu(controls, values=["All tags"], command=self.set_tag); self.tag_menu.pack(side="left", padx=4, pady=12)
        self.sort_menu = ctk.CTkOptionMenu(controls, values=["Recently updated", "Recently created", "Title", "Type", "Favorites"], command=self.set_sort); self.sort_menu.set("Recently updated"); self.sort_menu.pack(side="left", padx=4, pady=12)
        self.favorite_button = ctk.CTkButton(controls, text="Favorites only", width=120, fg_color=COLORS["panel_alt"], command=self.toggle_favorites); self.favorite_button.pack(side="left", padx=12, pady=12)
        self.archive_button = ctk.CTkButton(controls, text="Show archived", width=120, fg_color=COLORS["panel_alt"], command=self.toggle_archived); self.archive_button.pack(side="left", padx=4, pady=12)
        self.count_label = ctk.CTkLabel(controls, text="", text_color=COLORS["muted"]); self.count_label.pack(side="right", padx=16)
        self.list_box = ctk.CTkScrollableFrame(self, fg_color=COLORS["panel"], corner_radius=10); self.list_box.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def set_query(self, value: str):
        self.query = value
        self.refresh()

    def set_kind(self, value: str):
        self.kind = None if value == "All types" else value
        self.refresh()

    def set_tag(self, value: str):
        self.tag = None if value == "All tags" else value
        self.refresh()

    def set_sort(self, value: str):
        self.sort_mode = {"Recently updated": SortMode.UPDATED, "Recently created": SortMode.CREATED, "Title": SortMode.TITLE, "Type": SortMode.KIND, "Favorites": SortMode.FAVORITES}[value]
        self.refresh()

    def toggle_favorites(self):
        self.favorite_only = not self.favorite_only
        self.favorite_button.configure(fg_color=COLORS["accent"] if self.favorite_only else COLORS["panel_alt"], text_color=COLORS["background"] if self.favorite_only else COLORS["text"])
        self.refresh()

    def toggle_archived(self):
        self.include_archived = not self.include_archived
        self.archive_button.configure(fg_color=COLORS["accent"] if self.include_archived else COLORS["panel_alt"], text_color=COLORS["background"] if self.include_archived else COLORS["text"])
        self.refresh()

    def refresh(self):
        if not hasattr(self, "list_box"):
            return
        result = self.search.query(SearchQuery(self.query, self.kind, self.tag, self.favorite_only, self.include_archived, self.sort_mode, self.sort_descending))
        self._refresh_filters(result.available_kinds, result.available_tags)
        self.count_label.configure(text=f"{result.total_matches} result{'s' if result.total_matches != 1 else ''}")
        for child in self.list_box.winfo_children():
            child.destroy()
        if result.empty:
            EmptyState(self.list_box, "No matching records", "Try another search or clear one of the filters.").pack(fill="x", pady=45)
            return
        for item in result.items:
            self._render_item(item)

    def _refresh_filters(self, kinds, tags):
        kind_values = ["All types"] + list(kinds)
        tag_values = ["All tags"] + list(tags)
        self.kind_menu.configure(values=kind_values)
        self.tag_menu.configure(values=tag_values)
        self.kind_menu.set(self.kind or "All types")
        self.tag_menu.set(self.tag or "All tags")

    def _render_item(self, item: CatalogItem):
        row = ctk.CTkFrame(self.list_box, fg_color=COLORS["panel_alt"], corner_radius=7)
        row.pack(fill="x", padx=10, pady=5)
        text = ctk.CTkFrame(row, fg_color="transparent"); text.pack(side="left", fill="x", expand=True, padx=14, pady=10)
        ctk.CTkLabel(text, text=item.title, anchor="w", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        labels = ", ".join(item.tags) if item.tags else "No labels"
        ctk.CTkLabel(text, text=f"{item.kind}  ·  {labels}", anchor="w", text_color=COLORS["muted"], font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(3, 0))
        if item.favorite:
            StatusBadge(row, "FAVORITE").pack(side="right", padx=8)
        if item.archived:
            StatusBadge(row, "ARCHIVED").pack(side="right", padx=8)
        ctk.CTkButton(row, text="Open", width=68, command=lambda selected=item: self.on_open(selected.item_id)).pack(side="right", padx=6)
        ctk.CTkButton(row, text="★" if item.favorite else "☆", width=38, fg_color=COLORS["panel"], command=lambda selected=item: self._toggle_favorite(selected.item_id)).pack(side="right", padx=2)
        ctk.CTkButton(row, text="Archive" if not item.archived else "Restore", width=80, fg_color=COLORS["panel"], command=lambda selected=item: self._toggle_archive(selected.item_id)).pack(side="right", padx=4)

    def _toggle_favorite(self, item_id: int):
        self.catalog.toggle_favorite(item_id)
        self.refresh()

    def _toggle_archive(self, item_id: int):
        self.catalog.toggle_archive(item_id)
        self.refresh()

    def selected_filter(self) -> dict[str, str | bool | None]:
        return {"query": self.query, "kind": self.kind, "tag": self.tag, "favorites_only": self.favorite_only, "include_archived": self.include_archived}

    def clear_filters(self):
        self.query = ""
        self.kind = None
        self.tag = None
        self.favorite_only = False
        self.include_archived = False
        self.favorite_button.configure(fg_color=COLORS["panel_alt"], text_color=COLORS["text"])
        self.archive_button.configure(fg_color=COLORS["panel_alt"], text_color=COLORS["text"])
        self.refresh()
