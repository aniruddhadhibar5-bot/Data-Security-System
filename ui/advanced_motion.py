"""Advanced animated controls for the Data Security System interface.

These controls are intentionally small and composable. They use Tkinter's event
loop exclusively, retain no sensitive data, and cancel scheduled callbacks when
their owning view is destroyed.
"""

from __future__ import annotations

import importlib
from datetime import datetime
from typing import Any, Callable

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: py -m pip install -r requirements.txt") from error

from ui.design import Divider, StatusPill, Surface, THEME
from ui.motion import AnimationHandle, MotionGroup, tween


class LiveClock(ctk.CTkLabel):
    """A subtle local-time indicator that updates without blocking the UI."""

    def __init__(self, master, prefix: str = "LOCAL TIME", **kwargs):
        super().__init__(master, text="", text_color=THEME.text_muted, font=ctk.CTkFont(size=11), **kwargs)
        self.prefix = prefix
        self.job = None
        self._tick()

    def _tick(self):
        self.configure(text=f"{self.prefix}  ·  {datetime.now().strftime('%d %b %Y  %H:%M:%S')}")
        self.job = self.after(1000, self._tick)

    def destroy(self):
        if self.job:
            try:
                self.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        super().destroy()


class AnimatedGauge(Surface):
    """Animated percentage gauge suitable for posture and storage summaries."""

    def __init__(self, master, value: int = 0, title: str = "Progress", detail: str = "", tone: str = "accent", **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.value = 0
        self.target = max(0, min(100, value))
        self.tone = tone
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(15, 5))
        ctk.CTkLabel(header, text=title.upper(), text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
        self.percent = ctk.CTkLabel(header, text="0%", text_color=THEME.text, font=ctk.CTkFont(size=12, weight="bold"))
        self.percent.pack(side="right")
        self.bar = ctk.CTkProgressBar(self, height=9, progress_color=getattr(THEME, tone, THEME.accent))
        self.bar.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(self, text=detail, text_color=THEME.text_muted, anchor="w", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=16, pady=(4, 15))
        self.animation: AnimationHandle | None = None
        self.animate_to(self.target)

    def animate_to(self, value: int):
        self.target = max(0, min(100, int(value)))
        if self.animation:
            self.animation.cancel()
        self.animation = tween(self, self.value, self.target, duration=520, steps=20, on_step=self._set_value)

    def _set_value(self, value: float):
        self.value = value
        self.bar.set(value / 100)
        self.percent.configure(text=f"{int(value)}%")

    def destroy(self):
        if self.animation:
            self.animation.cancel()
        super().destroy()


class SessionStatus(Surface):
    """Animated session state and an explicit lock action."""

    def __init__(self, master, seconds: int, on_lock: Callable, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.seconds = max(0, seconds)
        self.on_lock = on_lock
        self.job = None
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(15, 8))
        ctk.CTkLabel(header, text="SESSION STATUS", text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
        StatusPill(header, "UNLOCKED", "success").pack(side="right")
        Divider(self).pack(fill="x", padx=16)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=11)
        self.label = ctk.CTkLabel(body, text="", text_color=THEME.text_muted, anchor="w")
        self.label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(body, text="Lock now", width=82, height=30, fg_color=THEME.surface_hover, command=on_lock).pack(side="right")
        self._tick()

    def _tick(self):
        minutes, seconds = divmod(self.seconds, 60)
        self.label.configure(text=f"Auto-lock in {minutes:02d}:{seconds:02d}")
        self.seconds = max(0, self.seconds - 1)
        self.job = self.after(1000, self._tick)

    def reset(self, seconds: int):
        self.seconds = max(0, seconds)

    def destroy(self):
        if self.job:
            try:
                self.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        super().destroy()


class NotificationTray(Surface):
    """Dismissible, non-sensitive notification stack for dashboard guidance."""

    def __init__(self, master, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.notifications: list[tuple[str, str, str]] = []
        self._render()

    def add(self, title: str, detail: str, tone: str = "info"):
        self.notifications.append((title, detail, tone))
        self.notifications = self.notifications[-4:]
        self._render()

    def clear(self):
        self.notifications.clear()
        self._render()

    def _render(self):
        for child in self.winfo_children():
            child.destroy()
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(header, text="NOTIFICATIONS", text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
        if self.notifications:
            ctk.CTkButton(header, text="Clear", width=52, height=24, fg_color=THEME.surface_hover, command=self.clear).pack(side="right")
        Divider(self).pack(fill="x", padx=16)
        if not self.notifications:
            ctk.CTkLabel(self, text="No new workspace notifications.", text_color=THEME.text_muted, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16, pady=15)
            return
        for title, detail, tone in reversed(self.notifications):
            color = getattr(THEME, tone, THEME.info)
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=7)
            ctk.CTkFrame(row, width=4, height=32, fg_color=color, corner_radius=2).pack(side="left", padx=(0, 9))
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text, text=title, text_color=THEME.text, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(text, text=detail, text_color=THEME.text_muted, anchor="w", font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(2, 0))


class ExpandablePanel(Surface):
    """Animated disclosure panel for secondary dashboard detail."""

    def __init__(self, master, title: str, detail: str, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.expanded = False
        self.title = title
        self.detail = detail
        self._build()

    def _build(self):
        self.header = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        self.header.pack(fill="x", padx=16, pady=12)
        self.arrow = ctk.CTkLabel(self.header, text="›", text_color=THEME.accent, font=ctk.CTkFont(size=20))
        self.arrow.pack(side="left", padx=(0, 9))
        ctk.CTkLabel(self.header, text=self.title, text_color=THEME.text, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.body = ctk.CTkLabel(self, text=self.detail, text_color=THEME.text_muted, anchor="w", justify="left", wraplength=640)
        self.header.bind("<Button-1>", lambda _event: self.toggle(), add="+")
        self.bind("<Button-1>", lambda _event: self.toggle(), add="+")

    def toggle(self):
        self.expanded = not self.expanded
        self.arrow.configure(text="⌄" if self.expanded else "›")
        if self.expanded:
            self.body.pack(fill="x", padx=43, pady=(0, 15))
        else:
            self.body.pack_forget()


class AnimatedCounter(ctk.CTkLabel):
    """Count-up label for dashboard metrics."""

    def __init__(self, master, value: int = 0, suffix: str = "", **kwargs):
        super().__init__(master, text=f"0{suffix}", **kwargs)
        self.current = 0
        self.suffix = suffix
        self.animation: AnimationHandle | None = None
        self.animate_to(value)

    def animate_to(self, value: int):
        if self.animation:
            self.animation.cancel()
        self.animation = tween(self, self.current, max(0, value), duration=460, steps=18, on_step=self._set)

    def _set(self, value: float):
        self.current = int(value)
        self.configure(text=f"{self.current}{self.suffix}")

    def destroy(self):
        if self.animation:
            self.animation.cancel()
        super().destroy()
