"""Custom Canvas security visuals for the command-center dashboard.

The visual language is deliberately technical and restrained: a perspective vault
object, a perimeter scan, and a risk radar. These are real Canvas primitives,
not external assets, so they remain crisp, local, and dependency-free.
"""

from __future__ import annotations

import importlib
import math
from typing import Any, Callable

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: py -m pip install -r requirements.txt") from error

from ui.design import Surface, THEME
from ui.motion import AnimationHandle, MotionGroup, tween


class VaultPerspective:
    """A lightweight animated perspective vault rendered on a Tk Canvas."""

    def __init__(self, master, size: tuple[int, int] = (430, 230), **kwargs):
        self.frame = ctk.CTkFrame(master, fg_color=THEME.surface, corner_radius=10, **kwargs)
        self.canvas = ctk.CTkCanvas(self.frame, width=size[0], height=size[1], bg=THEME.surface, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.width, self.height = size
        self.angle = 0.0
        self.motion = MotionGroup()
        self.job = None
        self._draw_static()
        self._animate()

    def pack(self, *args, **kwargs):
        return self.frame.pack(*args, **kwargs)

    def grid(self, *args, **kwargs):
        return self.frame.grid(*args, **kwargs)

    def place(self, *args, **kwargs):
        return self.frame.place(*args, **kwargs)

    def _draw_static(self):
        canvas = self.canvas
        canvas.create_text(18, 17, text="ENCRYPTED CORE", fill=THEME.text_subtle, anchor="w", font=("Segoe UI", 9, "bold"))
        canvas.create_text(self.width - 18, 17, text="AES-GCM / 256", fill=THEME.success, anchor="e", font=("Segoe UI", 9))
        for radius, color in ((82, THEME.border), (63, "#294149"), (45, "#335763")):
            canvas.create_oval(self.width / 2 - radius, self.height / 2 - radius + 14, self.width / 2 + radius, self.height / 2 + radius + 14, outline=color, width=1)
        self._draw_vault(0)
        canvas.create_text(self.width / 2, self.height - 20, text="LOCAL VAULT · SESSION PROTECTED", fill=THEME.text_muted, font=("Segoe UI", 9))

    def _draw_vault(self, offset: float):
        canvas = self.canvas
        canvas.delete("vault_dynamic")
        cx, cy = self.width / 2 + offset, self.height / 2 + 16
        width, height, depth = 112, 72, 18
        front = [(cx - width / 2, cy - height / 2), (cx + width / 2, cy - height / 2), (cx + width / 2, cy + height / 2), (cx - width / 2, cy + height / 2)]
        top = [(cx - width / 2, cy - height / 2), (cx - width / 2 + depth, cy - height / 2 - depth), (cx + width / 2 + depth, cy - height / 2 - depth), (cx + width / 2, cy - height / 2)]
        side = [(cx + width / 2, cy - height / 2), (cx + width / 2 + depth, cy - height / 2 - depth), (cx + width / 2 + depth, cy + height / 2 - depth), (cx + width / 2, cy + height / 2)]
        canvas.create_polygon(top, fill="#345863", outline=THEME.accent, tags="vault_dynamic")
        canvas.create_polygon(side, fill="#213b43", outline="#4c8290", tags="vault_dynamic")
        canvas.create_polygon(front, fill="#1a2b31", outline=THEME.accent, width=2, tags="vault_dynamic")
        canvas.create_oval(cx - 25, cy - 25, cx + 25, cy + 25, outline=THEME.success, width=2, tags="vault_dynamic")
        canvas.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, outline=THEME.accent, width=2, tags="vault_dynamic")
        canvas.create_line(cx, cy - 14, cx, cy + 14, fill=THEME.success, width=2, tags="vault_dynamic")
        canvas.create_line(cx - 14, cy, cx + 14, cy, fill=THEME.success, width=2, tags="vault_dynamic")

    def _animate(self):
        self.angle += 0.08
        drift = math.sin(self.angle) * 3
        self._draw_vault(drift)
        self.job = self.canvas.after(45, self._animate)

    def destroy(self):
        if self.job:
            try:
                self.canvas.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        self.motion.cancel_all()
        self.frame.destroy()


class PerimeterRadar:
    """Animated radar sweep for non-sensitive workspace event posture."""

    def __init__(self, master, score: int = 100, on_click: Callable | None = None, **kwargs):
        self.panel = Surface(master, raised=True, **kwargs)
        self.canvas = ctk.CTkCanvas(self.panel, width=270, height=220, bg=THEME.surface_raised, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.score = max(0, min(100, score))
        self.rotation = 0.0
        self.job = None
        self.on_click = on_click
        self._draw()
        self.canvas.bind("<Button-1>", lambda _event: self.on_click() if self.on_click else None)
        self._animate()

    def pack(self, *args, **kwargs):
        return self.panel.pack(*args, **kwargs)

    def grid(self, *args, **kwargs):
        return self.panel.grid(*args, **kwargs)

    def _draw(self):
        canvas = self.canvas
        canvas.delete("all")
        cx, cy = 135, 112
        canvas.create_text(16, 16, text="PERIMETER RADAR", fill=THEME.text_subtle, anchor="w", font=("Segoe UI", 9, "bold"))
        for radius in (82, 62, 42, 22):
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=THEME.border, width=1)
        canvas.create_line(cx - 82, cy, cx + 82, cy, fill=THEME.border)
        canvas.create_line(cx, cy - 82, cx, cy + 82, fill=THEME.border)
        sweep_x = cx + math.cos(self.rotation) * 82
        sweep_y = cy + math.sin(self.rotation) * 82
        canvas.create_line(cx, cy, sweep_x, sweep_y, fill=THEME.accent, width=2)
        color = THEME.success if self.score >= 75 else THEME.warning if self.score >= 50 else THEME.danger
        points = [(cx + math.cos(angle) * (25 + (index % 3) * 17), cy + math.sin(angle) * (25 + (index % 3) * 17)) for index, angle in enumerate((0.3, 2.1, 4.5))]
        for x, y in points:
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="")
        canvas.create_text(cx, cy + 98, text=f"POSTURE {self.score:02d}%  ·  CLICK FOR CENTER", fill=color, font=("Segoe UI", 9, "bold"))

    def _animate(self):
        self.rotation = (self.rotation + 0.06) % (math.pi * 2)
        self._draw()
        self.job = self.canvas.after(55, self._animate)

    def destroy(self):
        if self.job:
            try:
                self.canvas.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        super().destroy()


class SignalStream(Surface):
    """Animated horizontal signal stream for recent operational events."""

    def __init__(self, master, events: list[dict], **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.events = events[:12]
        self.offset = 0
        self.job = None
        ctk.CTkLabel(self, text="LIVE SIGNAL STREAM", text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=16, pady=(14, 5))
        self.canvas = ctk.CTkCanvas(self, height=48, bg=THEME.surface_raised, highlightthickness=0)
        self.canvas.pack(fill="x", padx=12, pady=(0, 13))
        self._draw_stream()
        self._animate()

    def _draw_stream(self):
        self.canvas.delete("all")
        width = max(420, self.winfo_width())
        self.canvas.create_line(0, 24, width, 24, fill=THEME.border, width=2)
        if not self.events:
            self.canvas.create_text(12, 24, text="Waiting for encrypted workspace activity...", anchor="w", fill=THEME.text_muted, font=("Segoe UI", 10))
            return
        spacing = max(42, width / max(1, len(self.events)))
        for index, event in enumerate(self.events):
            x = (index * spacing + self.offset) % (width + spacing) - spacing
            color = THEME.success if event.get("event") in {"LOGIN", "SETUP"} else THEME.warning if event.get("event") == "LOGIN_FAILED" else THEME.accent
            self.canvas.create_oval(x - 5, 19, x + 5, 29, fill=color, outline="")
            self.canvas.create_text(x, 8, text=event.get("event", "EVENT"), fill=THEME.text_subtle, font=("Segoe UI", 8))

    def _animate(self):
        self.offset += 0.7
        self._draw_stream()
        self.job = self.canvas.after(65, self._animate)

    def destroy(self):
        if self.job:
            try:
                self.canvas.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        super().destroy()
