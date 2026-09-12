"""Design-system primitives for a calm, consistent security workspace.

The application intentionally uses a restrained palette, predictable spacing, and
high-contrast status colors. These helpers keep view modules from repeating visual
constants and make future theme changes local and safe.
"""

from __future__ import annotations

import importlib
import math
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: py -m pip install -r requirements.txt") from error


@dataclass(frozen=True)
class Theme:
    background: str = "#0f1418"
    surface: str = "#151c21"
    surface_raised: str = "#1d272e"
    surface_hover: str = "#26343c"
    border: str = "#304049"
    text: str = "#f4f6f7"
    text_muted: str = "#9aa7ae"
    text_subtle: str = "#6f7c84"
    accent: str = "#80c5d2"
    accent_dark: str = "#376c78"
    success: str = "#85c99a"
    warning: str = "#e0bd78"
    danger: str = "#dc8282"
    info: str = "#92b9e3"


THEME = Theme()
SPACING = {"xs": 4, "sm": 8, "md": 14, "lg": 22, "xl": 32, "xxl": 44}


class Surface(ctk.CTkFrame):
    def __init__(self, master, raised: bool = False, **kwargs):
        super().__init__(master, fg_color=THEME.surface_raised if raised else THEME.surface, corner_radius=10, **kwargs)


class PageTitle(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = "", eyebrow: str = "SECURE WORKSPACE", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=eyebrow.upper(), text_color=THEME.accent, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text=title, text_color=THEME.text, font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", pady=(5, 0))
        if subtitle:
            ctk.CTkLabel(self, text=subtitle, text_color=THEME.text_muted, font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(5, 0))


class MetricTile(Surface):
    def __init__(self, master, label: str, value: str, detail: str, tone: str = "accent", **kwargs):
        super().__init__(master, **kwargs)
        color = getattr(THEME, tone, THEME.accent)
        ctk.CTkLabel(self, text=label.upper(), text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=18, pady=(17, 6))
        ctk.CTkLabel(self, text=value, text_color=THEME.text, font=ctk.CTkFont(size=23, weight="bold")).pack(anchor="w", padx=18)
        ctk.CTkLabel(self, text=detail, text_color=color, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=18, pady=(4, 17))


class StatusPill(ctk.CTkLabel):
    def __init__(self, master, text: str, tone: str = "info", **kwargs):
        color = getattr(THEME, tone, THEME.info)
        super().__init__(master, text=f"  {text}  ", text_color=color, fg_color=THEME.surface_raised, corner_radius=6, padx=7, pady=4, **kwargs)


class Divider(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, height=1, fg_color=THEME.border, **kwargs)


class EmptyPanel(Surface):
    def __init__(self, master, title: str, detail: str, action: str | None = None, command: Callable | None = None, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="○", text_color=THEME.accent, font=ctk.CTkFont(size=30)).pack(pady=(30, 8))
        ctk.CTkLabel(self, text=title, text_color=THEME.text, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=3)
        ctk.CTkLabel(self, text=detail, text_color=THEME.text_muted, wraplength=500, justify="center").pack(pady=4)
        if action and command:
            ctk.CTkButton(self, text=action, command=command, fg_color=THEME.accent, text_color=THEME.background).pack(pady=(12, 26))


class LoadingPanel(Surface):
    def __init__(self, master, message: str = "Loading secure workspace...", **kwargs):
        super().__init__(master, **kwargs)
        self.label = ctk.CTkLabel(self, text=message, text_color=THEME.text_muted)
        self.label.pack(pady=32)
        self.progress = ctk.CTkProgressBar(self, mode="indeterminate", width=240, progress_color=THEME.accent)
        self.progress.pack(pady=(0, 28))
        self.progress.start()

    def stop(self):
        self.progress.stop()


class InlineNotice(Surface):
    def __init__(self, master, message: str, tone: str = "info", action: str | None = None, command: Callable | None = None, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        color = getattr(THEME, tone, THEME.info)
        ctk.CTkLabel(self, text=message, text_color=color, anchor="w", justify="left", wraplength=540).pack(side="left", fill="x", expand=True, padx=14, pady=12)
        if action and command:
            ctk.CTkButton(self, text=action, width=80, fg_color=THEME.surface_hover, command=command).pack(side="right", padx=10)


class Toolbar(Surface):
    def __init__(self, master, **kwargs):
        super().__init__(master, raised=True, **kwargs)

    def add_button(self, text: str, command: Callable, primary: bool = False, width: int = 100):
        button = ctk.CTkButton(self, text=text, width=width, command=command, fg_color=THEME.accent if primary else THEME.surface_hover, text_color=THEME.background if primary else THEME.text)
        button.pack(side="left", padx=5, pady=10)
        return button


class FormLabel(ctk.CTkLabel):
    def __init__(self, master, text: str, **kwargs):
        super().__init__(master, text=text, text_color=THEME.text_muted, anchor="w", font=ctk.CTkFont(size=11), **kwargs)


class SafeEntry(ctk.CTkEntry):
    def set_value(self, value: str):
        self.delete(0, "end")
        self.insert(0, value)

    def value(self) -> str:
        return self.get().strip()


class ToggleRow(Surface):
    def __init__(self, master, title: str, detail: str, value: bool = False, on_change: Callable[[bool], None] | None = None, **kwargs):
        super().__init__(master, **kwargs)
        text = ctk.CTkFrame(self, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=16, pady=12)
        ctk.CTkLabel(text, text=title, text_color=THEME.text, anchor="w", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(text, text=detail, text_color=THEME.text_muted, anchor="w", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(3, 0))
        self.switch = ctk.CTkSwitch(self, text="", command=self._changed, width=42)
        self.switch.pack(side="right", padx=16)
        if value:
            self.switch.select()
        self.on_change = on_change

    def _changed(self):
        if self.on_change:
            self.on_change(bool(self.switch.get()))

    def value(self) -> bool:
        return bool(self.switch.get())


class SecurityScore(Surface):
    """Compact visual posture score with a stable, accessible text fallback."""

    def __init__(self, master, score: int, title: str = "Security posture", **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.score = max(0, min(100, int(score)))
        self._build(title)

    def _build(self, title: str):
        ctk.CTkLabel(self, text=title.upper(), text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=18, pady=(16, 0))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(12, 16))
        self.canvas = tk.Canvas(body, width=104, height=104, highlightthickness=0, bg=THEME.surface_raised)
        self.canvas.pack(side="left")
        self.canvas.create_oval(10, 10, 94, 94, outline=THEME.border, width=8)
        color = THEME.success if self.score >= 80 else THEME.warning if self.score >= 55 else THEME.danger
        self.arc = self.canvas.create_arc(10, 10, 94, 94, start=90, extent=-self.score * 3.6, outline=color, width=8, style="arc")
        self.canvas.create_text(52, 47, text=str(self.score), fill=THEME.text, font=("Segoe UI", 22, "bold"))
        self.canvas.create_text(52, 70, text="/ 100", fill=THEME.text_muted, font=("Segoe UI", 9))
        details = ctk.CTkFrame(body, fg_color="transparent")
        details.pack(side="left", fill="both", expand=True, padx=(16, 0))
        label = "Excellent" if self.score >= 90 else "Strong" if self.score >= 75 else "Fair" if self.score >= 55 else "Review"
        ctk.CTkLabel(details, text=label, text_color=color, font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(details, text="Based on integrity,\nlogin activity, and\nencryption state.", text_color=THEME.text_muted, justify="left", anchor="w", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(5, 0))


class DistributionBars(Surface):
    """Simple horizontal distribution chart that remains legible at small sizes."""

    def __init__(self, master, values: dict[str, int], title: str = "Vault composition", **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.values = values
        self._build(title)

    def _build(self, title: str):
        ctk.CTkLabel(self, text=title.upper(), text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=18, pady=(16, 5))
        total = max(1, sum(self.values.values()))
        palette = [THEME.accent, THEME.info, THEME.success, THEME.warning, THEME.danger]
        for index, (label, value) in enumerate(self.values.items()):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=5)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(top, text=label, text_color=THEME.text_muted, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left")
            ctk.CTkLabel(top, text=str(value), text_color=THEME.text, anchor="e", font=ctk.CTkFont(size=11, weight="bold")).pack(side="right")
            bar = ctk.CTkProgressBar(row, height=7, progress_color=palette[index % len(palette)])
            bar.pack(fill="x", pady=(4, 0))
            bar.set(value / total)
        ctk.CTkLabel(self, text=f"{sum(self.values.values())} protected records", text_color=THEME.text_subtle, font=ctk.CTkFont(size=10)).pack(anchor="w", padx=18, pady=(8, 16))


class TrendChart(Surface):
    """Small seven-point audit activity chart with no external plotting dependency."""

    def __init__(self, master, points: list[int], title: str = "Activity trend", **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.points = points[-7:] or [0]
        self._build(title)

    def _build(self, title: str):
        ctk.CTkLabel(self, text=title.upper(), text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=18, pady=(16, 5))
        canvas = tk.Canvas(self, height=112, highlightthickness=0, bg=THEME.surface_raised)
        canvas.pack(fill="x", padx=18, pady=(2, 8))
        width = 440
        canvas.configure(width=width)
        maximum = max(1, max(self.points))
        for y in (20, 52, 84):
            canvas.create_line(0, y, width, y, fill=THEME.border)
        if len(self.points) == 1:
            coordinates = [(width / 2, 100 - self.points[0] / maximum * 72)]
        else:
            step = width / (len(self.points) - 1)
            coordinates = [(index * step, 100 - value / maximum * 72) for index, value in enumerate(self.points)]
        if len(coordinates) > 1:
            canvas.create_line(coordinates, fill=THEME.accent, width=3, smooth=True)
        for x, y in coordinates:
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=THEME.accent, outline=THEME.surface_raised)
        ctk.CTkLabel(self, text=f"{sum(self.points)} operations in the recent activity window", text_color=THEME.text_subtle, font=ctk.CTkFont(size=10)).pack(anchor="w", padx=18, pady=(0, 16))


class InsightPanel(Surface):
    """A concise recommendation panel driven by non-sensitive workspace metrics."""

    def __init__(self, master, headline: str, detail: str, tone: str = "accent", action: str | None = None, command: Callable | None = None, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        color = getattr(THEME, tone, THEME.accent)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=14)
        ctk.CTkFrame(row, width=5, height=48, fg_color=color, corner_radius=3).pack(side="left", padx=(0, 12))
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text, text=headline, text_color=THEME.text, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(text, text=detail, text_color=THEME.text_muted, anchor="w", wraplength=620, justify="left", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(3, 0))
        if action and command:
            ctk.CTkButton(row, text=action, width=95, fg_color=THEME.surface_hover, command=command).pack(side="right", padx=(12, 0))
