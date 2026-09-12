"""Audit analytics and operational review screen."""

from __future__ import annotations

import importlib
from datetime import datetime
from pathlib import Path
from typing import Any
from tkinter import filedialog, messagebox

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: py -m pip install -r requirements.txt") from error

from core.audit import AuditService
from core.database import Database
from core.metrics import MetricsService
from ui.design import Divider, EmptyPanel, MetricTile, PageTitle, StatusPill, Surface, THEME, Toolbar


class AnalyticsView(ctk.CTkFrame):
    def __init__(self, master, database: Database, on_refresh=None, **kwargs):
        super().__init__(master, fg_color=THEME.background, **kwargs)
        self.database = database
        self.audit = AuditService(database)
        self.metrics = MetricsService(database)
        self.on_refresh = on_refresh
        self.event_filter = "All events"
        self._build()
        self.refresh()

    def _build(self):
        PageTitle(self, "Security analytics", "Operational signals, access history, and storage health in one place.", eyebrow="AUDIT & OBSERVABILITY").pack(fill="x", padx=28, pady=(26, 20))
        self.metrics_row = ctk.CTkFrame(self, fg_color="transparent")
        self.metrics_row.pack(fill="x", padx=22)
        for column in range(4):
            self.metrics_row.grid_columnconfigure(column, weight=1)
        tools = Toolbar(self)
        tools.pack(fill="x", padx=28, pady=18)
        ctk.CTkLabel(tools, text="Event filter", text_color=THEME.text_muted).pack(side="left", padx=(12, 5), pady=10)
        self.filter_menu = ctk.CTkOptionMenu(tools, values=["All events"], command=self.set_filter)
        self.filter_menu.pack(side="left", padx=5, pady=10)
        tools.add_button("Refresh", self.refresh, primary=True, width=85)
        tools.add_button("Export CSV", self.export_csv, width=95)
        tools.add_button("Export JSON", self.export_json, width=100)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)
        self.events_panel = Surface(body)
        self.events_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.summary_panel = Surface(body)
        self.summary_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def _clear(self, widget):
        for child in widget.winfo_children():
            child.destroy()

    def refresh(self):
        metrics = self.metrics.collect()
        self._clear(self.metrics_row)
        cards = [
            ("Events", str(metrics.audit_events), "Total operations", "accent"),
            ("Failed logins", str(metrics.failed_logins), "Authentication review", "danger" if metrics.failed_logins else "success"),
            ("Encrypted items", str(metrics.total_items), "Protected records", "info"),
            ("Integrity", "PASS" if metrics.integrity_verified else "FAIL", "Database verification", "success" if metrics.integrity_verified else "danger"),
        ]
        for index, (label, value, detail, tone) in enumerate(cards):
            MetricTile(self.metrics_row, label, value, detail, tone=tone).grid(row=0, column=index, sticky="nsew", padx=5)
        events = self.audit.events(100, None if self.event_filter == "All events" else self.event_filter)
        event_types = sorted(self.audit.event_counts().keys()) or ["All events"]
        self.filter_menu.configure(values=["All events"] + event_types)
        self.filter_menu.set(self.event_filter)
        self._render_events(events)
        self._render_summary(metrics)

    def set_filter(self, value: str):
        self.event_filter = value
        self.refresh()

    def _render_events(self, events):
        self._clear(self.events_panel)
        ctk.CTkLabel(self.events_panel, text="Recent events", text_color=THEME.text, font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(self.events_panel, text=f"Showing {len(events)} recorded operations", text_color=THEME.text_muted).pack(anchor="w", padx=18, pady=(0, 14))
        Divider(self.events_panel).pack(fill="x", padx=18)
        scroll = ctk.CTkScrollableFrame(self.events_panel, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)
        if not events:
            EmptyPanel(scroll, "No audit events", "Activity will appear here after the workspace is used.").pack(fill="x", padx=8, pady=20)
            return
        for event in events:
            self._event_row(scroll, event)

    def _event_row(self, parent, event):
        row = ctk.CTkFrame(parent, fg_color=THEME.surface_raised, corner_radius=7)
        row.pack(fill="x", padx=5, pady=4)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=12, pady=9)
        ctk.CTkLabel(text, text=event["event"], text_color=THEME.text, anchor="w", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(text, text=event["detail"], text_color=THEME.text_muted, anchor="w", wraplength=460, justify="left", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(3, 0))
        ctk.CTkLabel(row, text=event["created_at"], text_color=THEME.text_subtle, font=ctk.CTkFont(size=10)).pack(side="right", padx=12)

    def _render_summary(self, metrics):
        self._clear(self.summary_panel)
        ctk.CTkLabel(self.summary_panel, text="Workspace health", text_color=THEME.text, font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=20, pady=(20, 5))
        healthy = metrics.integrity_verified and metrics.failed_logins < 5
        StatusPill(self.summary_panel, "HEALTHY" if healthy else "REVIEW REQUIRED", "success" if healthy else "warning").pack(anchor="w", padx=20, pady=(5, 16))
        rows = [("Encrypted records", metrics.human_item_summary), ("Password records", str(metrics.password_items)), ("Secure notes", str(metrics.note_items)), ("File records", str(metrics.file_items)), ("File payload bytes", self.metrics._size(metrics.encrypted_file_bytes)), ("Captured", metrics.captured_at)]
        for label, value in rows:
            line = ctk.CTkFrame(self.summary_panel, fg_color="transparent")
            line.pack(fill="x", padx=20, pady=7)
            ctk.CTkLabel(line, text=label, text_color=THEME.text_muted, anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=value, text_color=THEME.text, anchor="e").pack(side="right")
        ctk.CTkLabel(self.summary_panel, text="Failed login events are intentionally counted, not displayed with credential details.", text_color=THEME.text_subtle, wraplength=300, justify="left", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=20, pady=(24, 10))

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Export audit CSV")
        if not path:
            return
        try:
            self.audit.export_csv(Path(path))
            messagebox.showinfo("Audit export", "The audit CSV was exported.")
        except OSError as error:
            messagebox.showerror("Audit export", str(error))

    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")], title="Export audit JSON")
        if not path:
            return
        try:
            self.audit.export_json(Path(path))
            messagebox.showinfo("Audit export", "The audit JSON was exported.")
        except OSError as error:
            messagebox.showerror("Audit export", str(error))
