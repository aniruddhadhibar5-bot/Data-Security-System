"""Security Center interface for recommendations and report export."""

from __future__ import annotations

import importlib
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: py -m pip install -r requirements.txt") from error

from core.database import Database
from core.reporting import Recommendation, ReportService, SecurityReport
from ui.design import Divider, EmptyPanel, MetricTile, PageTitle, StatusPill, Surface, THEME, Toolbar
from ui.motion import MotionGroup, stagger


class RecommendationCard(Surface):
    COLORS = {"critical": THEME.danger, "high": THEME.danger, "medium": THEME.warning, "low": THEME.info, "info": THEME.success}

    def __init__(self, master, recommendation: Recommendation, command: Callable | None = None, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        color = self.COLORS.get(recommendation.priority, THEME.info)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        ctk.CTkFrame(row, width=5, height=52, corner_radius=3, fg_color=color).pack(side="left", padx=(0, 12))
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        top = ctk.CTkFrame(text, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=recommendation.title, text_color=THEME.text, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        StatusPill(top, recommendation.priority.upper(), "danger" if recommendation.priority in {"critical", "high"} else "warning" if recommendation.priority == "medium" else "success").pack(side="right")
        ctk.CTkLabel(text, text=recommendation.detail, text_color=THEME.text_muted, anchor="w", wraplength=520, justify="left", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(4, 0))
        if command:
            ctk.CTkButton(row, text=recommendation.action, width=105, fg_color=THEME.surface_hover, command=command).pack(side="right", padx=(12, 0))


class ActivityMiniChart(Surface):
    def __init__(self, master, points, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        ctk.CTkLabel(self, text="7-DAY ACTIVITY", text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=18, pady=(16, 5))
        chart = ctk.CTkFrame(self, fg_color="transparent")
        chart.pack(fill="x", padx=18, pady=(4, 14))
        maximum = max(1, max(point.events for point in points))
        for point in points:
            column = ctk.CTkFrame(chart, fg_color="transparent")
            column.pack(side="left", fill="x", expand=True, padx=3)
            track = ctk.CTkFrame(column, height=90, fg_color=THEME.surface)
            track.pack(fill="x", expand=True)
            amount = max(4, int(82 * point.events / maximum))
            bar = ctk.CTkFrame(track, height=amount, fg_color=THEME.accent, corner_radius=3)
            bar.pack(side="bottom", fill="x", padx=3, pady=3)
            ctk.CTkLabel(column, text=point.label, text_color=THEME.text_subtle, font=ctk.CTkFont(size=9)).pack(pady=(4, 0))


class SecurityCenterView(ctk.CTkFrame):
    def __init__(self, master, database: Database, on_diagnostics: Callable, on_settings: Callable, on_organization: Callable, **kwargs):
        super().__init__(master, fg_color=THEME.background, **kwargs)
        self.database = database
        self.reports = ReportService(database)
        self.callbacks = {"diagnostics": on_diagnostics, "settings": on_settings, "organization": on_organization}
        self.motion = MotionGroup()
        self.current_report: SecurityReport | None = None
        self._build()
        self.refresh()

    def _build(self):
        PageTitle(self, "Security Center", "Understand the posture of your workspace and act on the important signals.", eyebrow="PROTECTION INSIGHTS").pack(fill="x", padx=30, pady=(28, 20))
        toolbar = Toolbar(self)
        toolbar.pack(fill="x", padx=30, pady=(0, 18))
        ctk.CTkLabel(toolbar, text="Reports contain operational data only. Secret payloads stay encrypted.", text_color=THEME.text_muted).pack(side="left", padx=14, pady=10)
        toolbar.add_button("Refresh", self.refresh, primary=True, width=82)
        toolbar.add_button("JSON", lambda: self.export("json"), width=65)
        toolbar.add_button("HTML", lambda: self.export("html"), width=65)
        toolbar.add_button("Text", lambda: self.export("txt"), width=65)
        self.summary = ctk.CTkFrame(self, fg_color="transparent")
        self.summary.pack(fill="x", padx=25)
        for column in range(4):
            self.summary.grid_columnconfigure(column, weight=1)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=30, pady=22)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)
        self.recommendations_panel = Surface(body)
        self.recommendations_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.activity_panel = ctk.CTkFrame(body, fg_color="transparent")
        self.activity_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def _clear(self, widget):
        for child in widget.winfo_children():
            child.destroy()

    def refresh(self):
        self.current_report = self.reports.build(days=7)
        self._render_summary(self.current_report)
        self._render_recommendations(self.current_report)
        self._render_activity(self.current_report)

    def _render_summary(self, report: SecurityReport):
        self._clear(self.summary)
        values = [("Posture score", f"{report.score}/100", report.health, "success" if report.score >= 75 else "warning"), ("Encrypted items", str(report.metrics.total_items), report.metrics.human_item_summary, "accent"), ("Audit events", str(report.metrics.audit_events), "Recorded operations", "info"), ("Login review", str(report.metrics.failed_logins), "Failed attempts", "danger" if report.metrics.failed_logins else "success")]
        callbacks = []
        for index, (label, value, detail, tone) in enumerate(values):
            tile = MetricTile(self.summary, label, value, detail, tone=tone)
            tile.grid(row=0, column=index, sticky="nsew", padx=5)
            tile.grid_remove()
            callbacks.append(lambda target=tile: target.grid())
        self.motion.add(stagger(self, callbacks, 70))

    def _render_recommendations(self, report: SecurityReport):
        self._clear(self.recommendations_panel)
        header = ctk.CTkFrame(self.recommendations_panel, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 10))
        ctk.CTkLabel(header, text="Recommended actions", text_color=THEME.text, font=ctk.CTkFont(size=17, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text=f"{len(report.recommendations)} insight{'s' if len(report.recommendations) != 1 else ''}", text_color=THEME.text_subtle).pack(side="right")
        Divider(self.recommendations_panel).pack(fill="x", padx=20)
        scroll = ctk.CTkScrollableFrame(self.recommendations_panel, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)
        for recommendation in report.recommendations:
            action = self._recommendation_action(recommendation)
            RecommendationCard(scroll, recommendation, action).pack(fill="x", padx=5, pady=5)

    def _recommendation_action(self, recommendation: Recommendation):
        if recommendation.code == "integrity" or recommendation.code == "login-review":
            return self.callbacks["diagnostics"]
        if recommendation.code == "backup":
            return self.callbacks["settings"]
        if recommendation.code in {"first-item", "coverage"}:
            return self.callbacks["organization"]
        return self.refresh

    def _render_activity(self, report: SecurityReport):
        self._clear(self.activity_panel)
        ActivityMiniChart(self.activity_panel, report.activity).pack(fill="x", pady=(0, 12))
        breakdown = Surface(self.activity_panel)
        breakdown.pack(fill="both", expand=True)
        ctk.CTkLabel(breakdown, text="Event breakdown", text_color=THEME.text, font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=18, pady=(18, 12))
        counts = self.reports.activity.event_breakdown()
        if not counts:
            EmptyPanel(breakdown, "No events recorded", "Use the workspace to build an operational history.").pack(fill="x", padx=12, pady=20)
            return
        for event, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]:
            row = ctk.CTkFrame(breakdown, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=6)
            ctk.CTkLabel(row, text=event, text_color=THEME.text_muted, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=str(count), text_color=THEME.text, anchor="e", font=ctk.CTkFont(weight="bold")).pack(side="right")

    def export(self, format_name: str):
        extensions = {"json": (".json", "JSON files", "*.json"), "html": (".html", "HTML files", "*.html"), "txt": (".txt", "Text files", "*.txt")}
        extension, label, pattern = extensions[format_name]
        path = filedialog.asksaveasfilename(defaultextension=extension, filetypes=[(label, pattern)], title=f"Export {format_name.upper()} security report")
        if not path:
            return
        try:
            self.reports.export(Path(path), format_name)
            messagebox.showinfo("Security report", "The report was exported without secret payloads.")
        except OSError as error:
            messagebox.showerror("Security report", str(error))

    def destroy(self):
        self.motion.cancel_all()
        super().destroy()
