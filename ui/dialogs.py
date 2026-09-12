"""Focused modal dialogs for sensitive actions and reusable form flows."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from core.passwords import PasswordGenerator, PasswordStrength
from core.validators import InputValidator
from ui.widgets import COLORS, PasswordMeter


class Modal(ctk.CTkToplevel):
    def __init__(self, master, title: str, width: int = 460, height: int = 330):
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.minsize(width, height)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=COLORS["background"])

    def close(self):
        self.grab_release()
        self.destroy()


class ConfirmDialog(Modal):
    def __init__(self, master, title: str, message: str, on_confirm: Callable, danger: bool = False):
        super().__init__(master, title, 440, 210)
        ctk.CTkLabel(self, text=message, wraplength=360, justify="left", text_color=COLORS["muted"]).pack(fill="x", padx=30, pady=(34, 24))
        actions = ctk.CTkFrame(self, fg_color="transparent"); actions.pack(fill="x", padx=30)
        ctk.CTkButton(actions, text="Cancel", fg_color=COLORS["panel_alt"], command=self.close).pack(side="right", padx=(8, 0))
        def confirm():
            on_confirm(); self.close()
        ctk.CTkButton(actions, text="Confirm", fg_color="#593034" if danger else COLORS["accent"], text_color=COLORS["text"] if danger else COLORS["background"], command=confirm).pack(side="right")


class PasswordGeneratorDialog(Modal):
    def __init__(self, master, on_accept: Callable[[str], None]):
        super().__init__(master, "Generate password", 500, 410)
        self.on_accept = on_accept
        self.generator = PasswordGenerator()
        self.strength = PasswordStrength()
        self.output = ctk.CTkEntry(self, height=40)
        self.output.pack(fill="x", padx=28, pady=(30, 8))
        self.meter = PasswordMeter(self); self.meter.pack(fill="x", padx=28, pady=(0, 16))
        settings = ctk.CTkFrame(self, fg_color=COLORS["panel"]); settings.pack(fill="x", padx=28, pady=4)
        self.length = ctk.CTkSlider(settings, from_=12, to=64, number_of_steps=52, command=self._generate)
        self.length.set(24); self.length.pack(side="left", fill="x", expand=True, padx=14, pady=18)
        self.length_label = ctk.CTkLabel(settings, text="24", width=32); self.length_label.pack(side="right", padx=14)
        self.symbols = ctk.CTkCheckBox(self, text="Include symbols", command=self._generate); self.symbols.select(); self.symbols.pack(anchor="w", padx=28, pady=10)
        self.ambiguous = ctk.CTkCheckBox(self, text="Exclude ambiguous characters", command=self._generate); self.ambiguous.pack(anchor="w", padx=28, pady=4)
        actions = ctk.CTkFrame(self, fg_color="transparent"); actions.pack(fill="x", padx=28, pady=22)
        ctk.CTkButton(actions, text="Regenerate", fg_color=COLORS["panel_alt"], command=self._generate).pack(side="left")
        ctk.CTkButton(actions, text="Use password", command=self._accept).pack(side="right")
        self._generate(24)

    def _generate(self, value=None):
        length = int(float(value if value is not None else self.length.get()))
        self.length_label.configure(text=str(length))
        password = self.generator.generate(length=length, include_symbols=bool(self.symbols.get()), exclude_ambiguous=bool(self.ambiguous.get()))
        self.output.delete(0, "end"); self.output.insert(0, password)
        assessment = self.strength.assess(password); self.meter.set_score(assessment.score, f"{assessment.label} · {assessment.score}/7", assessment.color)

    def _accept(self):
        self.on_accept(self.output.get()); self.close()


class RecoveryKeyDialog(Modal):
    def __init__(self, master, item: dict, on_copy: Callable[[str], None]):
        super().__init__(master, "Recovery key", 620, 280)
        ctk.CTkLabel(self, text=f"{item['kind']} · {item['title']}", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=28, pady=(28, 6))
        ctk.CTkLabel(self, text="This key is revealed only because the current master session is unlocked.", text_color=COLORS["warning"], wraplength=550, justify="left").pack(anchor="w", padx=28, pady=4)
        key = ctk.CTkEntry(self); key.pack(fill="x", padx=28, pady=18); key.insert(0, item["key"]); key.configure(state="readonly")
        actions = ctk.CTkFrame(self, fg_color="transparent"); actions.pack(fill="x", padx=28)
        ctk.CTkButton(actions, text="Copy key", command=lambda: on_copy(item["key"])).pack(side="left")
        ctk.CTkButton(actions, text="Close", fg_color=COLORS["panel_alt"], command=self.close).pack(side="right")


class TextPreviewDialog(Modal):
    def __init__(self, master, title: str, text: str, readonly: bool = True):
        super().__init__(master, title, 720, 520)
        viewer = ctk.CTkTextbox(self); viewer.pack(fill="both", expand=True, padx=24, pady=24); viewer.insert("1.0", text)
        if readonly:
            viewer.configure(state="disabled")
        ctk.CTkButton(self, text="Close", command=self.close).pack(anchor="e", padx=24, pady=(0, 20))


class PinConfirmDialog(Modal):
    def __init__(self, master, on_submit: Callable[[str], None]):
        super().__init__(master, "Confirm security PIN", 420, 240)
        self.on_submit = on_submit
        ctk.CTkLabel(self, text="Enter your six-digit PIN to continue.", text_color=COLORS["muted"]).pack(anchor="w", padx=28, pady=(30, 12))
        self.pin = ctk.CTkEntry(self, show="*", placeholder_text="6-digit PIN"); self.pin.pack(fill="x", padx=28, pady=8)
        ctk.CTkButton(self, text="Verify", command=self._submit).pack(anchor="e", padx=28, pady=20)

    def _submit(self):
        result = InputValidator().pin(self.pin.get())
        if result:
            self.on_submit(self.pin.get()); self.close()
        else:
            self.pin.configure(border_color=COLORS["danger"], placeholder_text=result.message)
