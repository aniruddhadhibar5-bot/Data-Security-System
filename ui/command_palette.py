"""Keyboard-first command palette for the desktop application."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: py -m pip install -r requirements.txt") from error

from ui.design import THEME


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    action: Callable[[], None]
    keywords: tuple[str, ...] = ()

    def matches(self, query: str) -> bool:
        query = query.casefold().strip()
        if not query:
            return True
        text = " ".join((self.name, self.description, *self.keywords)).casefold()
        return query in text


class CommandRegistry:
    def __init__(self):
        self.commands: list[Command] = []

    def register(self, name: str, description: str, action: Callable[[], None], *keywords: str):
        self.commands.append(Command(name, description, action, tuple(keywords)))

    def search(self, query: str, limit: int = 12) -> list[Command]:
        return [command for command in self.commands if command.matches(query)][:limit]

    def names(self) -> list[str]:
        return [command.name for command in self.commands]


class CommandPalette(ctk.CTkToplevel):
    def __init__(self, master, registry: CommandRegistry):
        super().__init__(master)
        self.registry = registry
        self.results: list[Command] = []
        self.selected_index = 0
        self.title("Command palette")
        self.geometry("660x470")
        self.minsize(560, 360)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=THEME.background)
        self._build()
        self._refresh()

    def _build(self):
        ctk.CTkLabel(self, text="COMMAND PALETTE", text_color=THEME.accent, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=24, pady=(24, 6))
        ctk.CTkLabel(self, text="What would you like to do?", text_color=THEME.text, font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=24, pady=(0, 16))
        self.entry = ctk.CTkEntry(self, height=42, placeholder_text="Search commands")
        self.entry.pack(fill="x", padx=24)
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Down>", self._move_down)
        self.entry.bind("<Up>", self._move_up)
        self.entry.bind("<Return>", self._run_selected)
        self.entry.bind("<Escape>", lambda _event: self.close())
        self.list_box = ctk.CTkScrollableFrame(self, fg_color=THEME.surface, corner_radius=8)
        self.list_box.pack(fill="both", expand=True, padx=24, pady=18)
        ctk.CTkLabel(self, text="↑ ↓  Navigate     Enter  Run     Esc  Close", text_color=THEME.text_subtle, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=24, pady=(0, 18))
        self.entry.focus_set()

    def _on_key(self, event):
        if event.keysym in {"Up", "Down", "Return", "Escape"}:
            return
        self.selected_index = 0
        self._refresh()

    def _refresh(self):
        self.results = self.registry.search(self.entry.get() if hasattr(self, "entry") else "")
        for child in self.list_box.winfo_children():
            child.destroy()
        if not self.results:
            ctk.CTkLabel(self.list_box, text="No commands match this search.", text_color=THEME.text_muted).pack(pady=30)
            return
        for index, command in enumerate(self.results):
            self._render_command(index, command)

    def _render_command(self, index: int, command: Command):
        active = index == self.selected_index
        row = ctk.CTkFrame(self.list_box, fg_color=THEME.surface_hover if active else "transparent", corner_radius=6)
        row.pack(fill="x", padx=8, pady=3)
        row.bind("<Button-1>", lambda _event, selected=index: self._choose(selected))
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=12, pady=9)
        ctk.CTkLabel(text, text=command.name, text_color=THEME.text, anchor="w", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(text, text=command.description, text_color=THEME.text_muted, anchor="w", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(2, 0))

    def _choose(self, index: int):
        self.selected_index = index
        self._run_selected()

    def _move_down(self, _event=None):
        if self.results:
            self.selected_index = min(self.selected_index + 1, len(self.results) - 1)
            self._refresh()
        return "break"

    def _move_up(self, _event=None):
        if self.results:
            self.selected_index = max(self.selected_index - 1, 0)
            self._refresh()
        return "break"

    def _run_selected(self, _event=None):
        if not self.results:
            return "break"
        action = self.results[self.selected_index].action
        self.close()
        action()
        return "break"

    def close(self):
        self.grab_release()
        self.destroy()


def bind_palette(master, registry: CommandRegistry):
    root = master.winfo_toplevel()

    def open_palette(_event=None):
        CommandPalette(master, registry)
        return "break"

    binding_id = root.bind("<Control-k>", open_palette, add="+")

    def unbind():
        if binding_id:
            try:
                root.unbind("<Control-k>", binding_id)
            except (AttributeError, RuntimeError):
                pass

    return unbind
