"""Reusable CustomTkinter widgets used by Data Security System views."""

from __future__ import annotations

from collections.abc import Callable
import importlib
from typing import Any

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: python -m pip install -r requirements.txt") from error


COLORS = {
    "background": "#101418",
    "panel": "#171d22",
    "panel_alt": "#20282e",
    "border": "#2b3840",
    "text": "#f1f4f6",
    "muted": "#8e9aa4",
    "subtle": "#68747d",
    "accent": "#76b7c5",
    "success": "#7fc69a",
    "warning": "#d8b878",
    "danger": "#cf7777",
}


class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=title, text_color=COLORS["text"], font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(self, text=subtitle, text_color=COLORS["muted"], font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(5, 0))


class Panel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["panel"], corner_radius=10, **kwargs)


class MetricCard(Panel):
    def __init__(self, master, title: str, value: str, detail: str, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text=title.upper(), text_color=COLORS["subtle"], font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=18, pady=(18, 7))
        ctk.CTkLabel(self, text=value, text_color=COLORS["text"], font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=18)
        ctk.CTkLabel(self, text=detail, text_color=COLORS["accent"], font=ctk.CTkFont(size=11)).pack(anchor="w", padx=18, pady=(4, 18))


class StatusBadge(ctk.CTkLabel):
    def __init__(self, master, status: str, detail: str = "", **kwargs):
        color = COLORS["success"] if status.upper() in {"PASS", "READY", "ACTIVE"} else COLORS["warning"] if status.upper() in {"WARN", "REVIEW"} else COLORS["danger"] if status.upper() in {"FAIL", "ERROR"} else COLORS["accent"]
        text = f"{status}  ·  {detail}" if detail else status
        super().__init__(master, text=text, text_color=color, anchor="w", **kwargs)


class EmptyState(ctk.CTkFrame):
    def __init__(self, master, title: str, detail: str, action: str | None = None, command: Callable | None = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=title, text_color=COLORS["text"], font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(35, 6))
        ctk.CTkLabel(self, text=detail, text_color=COLORS["muted"], wraplength=500, justify="center").pack(pady=4)
        if action and command:
            ctk.CTkButton(self, text=action, command=command).pack(pady=16)


class SearchBar(ctk.CTkFrame):
    def __init__(self, master, placeholder: str = "Search", on_change: Callable[[str], None] | None = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_change = on_change
        self.entry = ctk.CTkEntry(self, placeholder_text=placeholder, height=38)
        self.entry.pack(side="left", fill="x", expand=True)
        self.clear_button = ctk.CTkButton(self, text="Clear", width=64, fg_color=COLORS["panel_alt"], command=self.clear)
        self.clear_button.pack(side="left", padx=(8, 0))
        self.entry.bind("<KeyRelease>", self._changed)

    def _changed(self, _event=None):
        if self.on_change:
            self.on_change(self.entry.get())

    def clear(self):
        self.entry.delete(0, "end")
        self._changed()

    def value(self) -> str:
        return self.entry.get()


class ActionRow(ctk.CTkFrame):
    def __init__(self, master, title: str, detail: str, action: str, command: Callable, danger: bool = False, **kwargs):
        super().__init__(master, fg_color=COLORS["panel_alt"], corner_radius=7, **kwargs)
        text = ctk.CTkFrame(self, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=14, pady=11)
        ctk.CTkLabel(text, text=title, anchor="w", text_color=COLORS["text"], font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(text, text=detail, anchor="w", text_color=COLORS["muted"], font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(3, 0))
        ctk.CTkButton(self, text=action, width=90, command=command, fg_color="#593034" if danger else COLORS["accent"], text_color="#101418" if not danger else COLORS["text"]).pack(side="right", padx=10)


class PasswordMeter(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.bar = ctk.CTkProgressBar(self, height=8)
        self.bar.pack(fill="x")
        self.label = ctk.CTkLabel(self, text="", anchor="w", font=ctk.CTkFont(size=11))
        self.label.pack(anchor="w", pady=(4, 0))

    def set_score(self, score: int, label: str, color: str):
        self.bar.set(min(max(score / 7, 0), 1))
        self.bar.configure(progress_color=color)
        self.label.configure(text=label, text_color=color)


class Toast(ctk.CTkToplevel):
    def __init__(self, master, message: str, success: bool = True, duration: int = 2400):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLORS["panel"])
        ctk.CTkLabel(self, text=message, text_color=COLORS["success"] if success else COLORS["danger"], padx=18, pady=12).pack()
        self.update_idletasks()
        x = master.winfo_rootx() + master.winfo_width() - self.winfo_width() - 24
        y = master.winfo_rooty() + 24
        self.geometry(f"+{x}+{y}")
        self.after(duration, self.destroy)


class ScrollableList(ctk.CTkScrollableFrame):
    def clear(self):
        for child in self.winfo_children():
            child.destroy()

    def add_divider(self):
        ctk.CTkFrame(self, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=12, pady=4)

    def add_empty(self, title: str, detail: str):
        EmptyState(self, title, detail).pack(fill="x", expand=True)
