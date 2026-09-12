"""Polished security overview dashboard.

The view is deliberately information-dense without becoming noisy: four key
metrics, a health rail, a recent activity stream, and quick actions occupy the
first screen. Cards reveal in sequence so the interface feels responsive while
SQLite work remains synchronous and predictable.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable
from tkinter import TclError, filedialog, messagebox

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: py -m pip install -r requirements.txt") from error

from core.audit import AuditService
from core.database import Database
from core.metrics import MetricsService
from core.vault import VaultService
from config import IDLE_TIMEOUT_SECONDS
from ui.advanced_motion import AnimatedGauge, ExpandablePanel, LiveClock, NotificationTray, SessionStatus
from ui.design import DistributionBars, Divider, EmptyPanel, InsightPanel, MetricTile, PageTitle, SecurityScore, StatusPill, Surface, THEME, Toolbar, TrendChart
from ui.motion import MotionGroup, PressMotion, stagger
from ui.security_visuals import PerimeterRadar, SignalStream, VaultPerspective


class ActivityRow(ctk.CTkFrame):
    EVENT_TONES = {
        "LOGIN": "success",
        "SETUP": "success",
        "LOGIN_FAILED": "danger",
        "LOCK": "warning",
        "ENCRYPT": "info",
        "DECRYPT": "info",
        "DELETE": "danger",
        "BACKUP": "accent",
        "EXPORT_AUDIT": "accent",
    }

    def __init__(self, master, event: dict, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        tone = self.EVENT_TONES.get(event.get("event", ""), "info")
        color = getattr(THEME, tone, THEME.info)
        marker = ctk.CTkFrame(self, width=7, height=42, corner_radius=4, fg_color=color)
        marker.pack(side="left", padx=(0, 10), pady=8)
        text = ctk.CTkFrame(self, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, pady=7)
        ctk.CTkLabel(text, text=event.get("event", "EVENT"), text_color=THEME.text, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(text, text=event.get("detail", ""), text_color=THEME.text_muted, anchor="w", wraplength=430, justify="left", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(self, text=event.get("created_at", ""), text_color=THEME.text_subtle, font=ctk.CTkFont(size=10)).pack(side="right", padx=(8, 0), pady=9)


class HealthRail(Surface):
    def __init__(self, master, metrics, on_diagnostics: Callable, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        healthy = metrics.integrity_verified and metrics.failed_logins < 5
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(header, text="WORKSPACE HEALTH", text_color=THEME.text_subtle, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
        StatusPill(header, "HEALTHY" if healthy else "REVIEW", "success" if healthy else "warning").pack(side="right")
        Divider(self).pack(fill="x", padx=18)
        checks = [
            ("Database integrity", "Verified" if metrics.integrity_verified else "Needs review", "success" if metrics.integrity_verified else "danger"),
            ("Idle lock", "Active · 5 minutes", "accent"),
            ("Clipboard timer", "Active · 15 seconds", "accent"),
            ("Encrypted storage", "AES-GCM + Argon2id", "success"),
        ]
        for label, value, tone in checks:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=7)
            ctk.CTkLabel(row, text=label, text_color=THEME.text_muted, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, text_color=getattr(THEME, tone), anchor="e", font=ctk.CTkFont(size=11)).pack(side="right")
        ctk.CTkButton(self, text="Open diagnostics", height=34, fg_color=THEME.surface_hover, hover_color=THEME.border, command=on_diagnostics).pack(fill="x", padx=18, pady=(10, 18))


class QuickAction(Surface):
    def __init__(self, master, title: str, detail: str, symbol: str, command: Callable, **kwargs):
        super().__init__(master, raised=True, **kwargs)
        self.configure(cursor="hand2")
        icon = ctk.CTkLabel(self, text=symbol, text_color=THEME.accent, font=ctk.CTkFont(size=22))
        icon.pack(side="left", padx=(16, 10), pady=15)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True, pady=12)
        ctk.CTkLabel(body, text=title, text_color=THEME.text, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(body, text=detail, text_color=THEME.text_muted, anchor="w", font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(3, 0))
        arrow = ctk.CTkLabel(self, text="›", text_color=THEME.text_subtle, font=ctk.CTkFont(size=22))
        arrow.pack(side="right", padx=14)
        for widget in (self, icon, body, arrow):
            widget.bind("<Button-1>", lambda _event: command, add="+")
            widget.bind("<ButtonRelease-1>", lambda _event: command(), add="+")
        PressMotion(self, THEME.accent_dark)


class DashboardView(ctk.CTkScrollableFrame):
    def __init__(self, master, database: Database, service: VaultService, on_files: Callable, on_passwords: Callable, on_notes: Callable, on_organization: Callable, on_diagnostics: Callable, on_lock: Callable | None = None, **kwargs):
        super().__init__(master, fg_color=THEME.background, **kwargs)
        self.database = database
        self.service = service
        self.metrics_service = MetricsService(database)
        self.audit = AuditService(database)
        self.callbacks = {"files": on_files, "passwords": on_passwords, "notes": on_notes, "organization": on_organization, "diagnostics": on_diagnostics, "lock": on_lock or (lambda: None)}
        self.motion = MotionGroup()
        self._build()
        self.refresh()

    def _build(self):
        PageTitle(self, "Security overview", "Everything protected, clearly accounted for.").pack(fill="x", padx=30, pady=(28, 22))
        toolbar = Toolbar(self)
        toolbar.pack(fill="x", padx=30, pady=(0, 18))
        ctk.CTkLabel(toolbar, text="Your local workspace is private by design.", text_color=THEME.text_muted).pack(side="left", padx=14, pady=10)
        LiveClock(toolbar).pack(side="left", padx=14, pady=10)
        toolbar.add_button("Refresh", self.refresh, primary=True, width=82)
        self.metric_row = ctk.CTkFrame(self, fg_color="transparent")
        self.metric_row.pack(fill="x", padx=25)
        for column in range(4):
            self.metric_row.grid_columnconfigure(column, weight=1)
        self.insight_row = ctk.CTkFrame(self, fg_color="transparent")
        self.insight_row.pack(fill="x", padx=25, pady=(16, 0))
        for column in range(3):
            self.insight_row.grid_columnconfigure(column, weight=1)
        self.notice_area = ctk.CTkFrame(self, fg_color="transparent")
        self.notice_area.pack(fill="x", padx=25)
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True, padx=30, pady=22)
        self.main.grid_columnconfigure(0, weight=3)
        self.main.grid_columnconfigure(1, weight=2)
        self.main.grid_rowconfigure(0, weight=1)
        self.activity_panel = Surface(self.main)
        self.activity_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.side_panel = ctk.CTkFrame(self.main, fg_color="transparent")
        self.side_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def _clear(self, widget):
        for child in widget.winfo_children():
            child.destroy()

    def refresh(self):
        metrics = self.metrics_service.collect()
        self._render_metrics(metrics)
        self._render_insights(metrics)
        self._render_activity()
        self._render_side(metrics)

    def _security_score(self, metrics) -> int:
        score = 100
        if not metrics.integrity_verified:
            score -= 45
        score -= min(metrics.failed_logins * 8, 40)
        if metrics.total_items == 0:
            score -= 5
        return max(0, score)

    def _render_insights(self, metrics):
        self._clear(self.insight_row)
        score = self._security_score(metrics)
        SecurityScore(self.insight_row, score).grid(row=0, column=0, sticky="nsew", padx=5)
        DistributionBars(
            self.insight_row,
            {"Credentials": metrics.password_items, "Secure notes": metrics.note_items, "Files": metrics.file_items},
        ).grid(row=0, column=1, sticky="nsew", padx=5)
        events = self.audit.events(7)
        TrendChart(self.insight_row, [1 for _ in events] or [0]).grid(row=0, column=2, sticky="nsew", padx=5)
        self._clear(self.notice_area)
        if not metrics.integrity_verified:
            InsightPanel(self.notice_area, "Database integrity needs attention", "The startup SHA-256 check did not match the current database. Review diagnostics before continuing.", tone="danger", action="Review", command=self.callbacks["diagnostics"]).pack(fill="x", pady=(16, 0))
        elif metrics.failed_logins:
            InsightPanel(self.notice_area, "Review recent access attempts", f"There are {metrics.failed_logins} failed login events in the audit history. Your encrypted records remain protected.", tone="warning", action="Open audit", command=self.callbacks["diagnostics"]).pack(fill="x", pady=(16, 0))

    def _render_metrics(self, metrics):
        self._clear(self.metric_row)
        values = [
            ("Vault items", str(metrics.total_items), metrics.human_item_summary, "accent"),
            ("Credentials", str(metrics.password_items), "Encrypted account records", "info"),
            ("Secure notes", str(metrics.note_items), "Encrypted text records", "info"),
            ("Integrity", "PASS" if metrics.integrity_verified else "REVIEW", "SHA-256 database check", "success" if metrics.integrity_verified else "danger"),
        ]
        callbacks = []
        for index, (label, value, detail, tone) in enumerate(values):
            tile = MetricTile(self.metric_row, label, value, detail, tone=tone)
            tile.grid(row=0, column=index, sticky="nsew", padx=5)
            tile.grid_remove()
            callbacks.append(lambda target=tile: target.grid())
        self.motion.add(stagger(self, callbacks, delay=70))

    def _render_activity(self):
        self._clear(self.activity_panel)
        self._render_optional_visual(self.activity_panel, lambda: VaultPerspective(self.activity_panel, size=(430, 210)).pack(fill="x", padx=12, pady=(12, 4)), "Vault visualization unavailable")
        self._render_optional_visual(self.activity_panel, lambda: SignalStream(self.activity_panel, self.audit.events(12)).pack(fill="x", padx=12, pady=(4, 8)), "Live signal stream unavailable")
        header = ctk.CTkFrame(self.activity_panel, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 10))
        ctk.CTkLabel(header, text="Recent activity", text_color=THEME.text, font=ctk.CTkFont(size=17, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text="Last 8 events", text_color=THEME.text_subtle, font=ctk.CTkFont(size=11)).pack(side="right")
        Divider(self.activity_panel).pack(fill="x", padx=20)
        scroll = ctk.CTkScrollableFrame(self.activity_panel, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=13, pady=8)
        events = self.audit.events(8)
        if not events:
            EmptyPanel(scroll, "No activity yet", "Your encrypted actions will appear here.", "Open organization", self.callbacks["organization"]).pack(fill="x", padx=8, pady=25)
            return
        for event in events:
            ActivityRow(scroll, event).pack(fill="x", padx=5, pady=2)

    def _render_side(self, metrics):
        self._clear(self.side_panel)
        self._render_optional_visual(self.side_panel, lambda: PerimeterRadar(self.side_panel, self._security_score(metrics), self.callbacks["diagnostics"]).pack(fill="x", pady=(0, 12)), "Perimeter radar unavailable")
        HealthRail(self.side_panel, metrics, self.callbacks["diagnostics"]).pack(fill="x", pady=(0, 12))
        self._render_optional_visual(self.side_panel, lambda: SessionStatus(self.side_panel, IDLE_TIMEOUT_SECONDS, self.callbacks["lock"]).pack(fill="x", pady=(0, 12)), "Session status unavailable")
        score = self._security_score(metrics)
        self._render_optional_visual(self.side_panel, lambda: AnimatedGauge(self.side_panel, score, "Posture confidence", "Live workspace protection score", "success" if score >= 75 else "warning").pack(fill="x", pady=(0, 12)), "Posture gauge unavailable")
        notice = NotificationTray(self.side_panel)
        if metrics.failed_logins:
            notice.add("Access review", f"{metrics.failed_logins} failed login event(s) recorded.", "warning")
        if not metrics.integrity_verified:
            notice.add("Integrity review", "Database verification needs attention.", "danger")
        if not metrics.failed_logins and metrics.integrity_verified:
            notice.add("Workspace ready", "No immediate security actions are required.", "success")
        notice.pack(fill="x", pady=(0, 12))
        quick = Surface(self.side_panel)
        quick.pack(fill="both", expand=True)
        ctk.CTkLabel(quick, text="Quick actions", text_color=THEME.text, font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=18, pady=(18, 5))
        ctk.CTkLabel(quick, text="Common tasks, one click away.", text_color=THEME.text_muted).pack(anchor="w", padx=18, pady=(0, 12))
        actions = [
            ("Encrypt a file", "Protect a document or photo", "⇧", self.callbacks["files"]),
            ("Save a password", "Add a secure credential", "▣", self.callbacks["passwords"]),
            ("Write a note", "Keep private information encrypted", "≡", self.callbacks["notes"]),
            ("Organize vault", "Search tags and favorites", "⌕", self.callbacks["organization"]),
        ]
        for title, detail, symbol, callback in actions:
            QuickAction(quick, title, detail, symbol, callback).pack(fill="x", padx=12, pady=4)
        ExpandablePanel(quick, "Why these checks matter", "The dashboard reads metadata and audit counts only. Secret payloads remain behind the authenticated vault service.").pack(fill="x", padx=12, pady=(12, 12))

    def _render_optional_visual(self, parent, render, fallback: str):
        try:
            render()
        except (AttributeError, RuntimeError, TclError, TypeError) as error:
            ctk.CTkLabel(parent, text=fallback, text_color=THEME.text_subtle, font=ctk.CTkFont(size=10)).pack(anchor="w", padx=16, pady=8)

    def destroy(self):
        self.motion.cancel_all()
        super().destroy()
