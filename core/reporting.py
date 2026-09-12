"""Non-sensitive security reporting and recommendation engine.

This module produces operational insight without decrypting or exporting secret
payloads. Reports contain counts, status, timestamps, and recommendations only.
That makes them useful for maintenance while preserving vault confidentiality.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Iterable

from core.audit import AuditService
from core.database import Database
from core.metrics import MetricsService, WorkspaceMetrics
from core.storage import VaultInventory


@dataclass(frozen=True)
class Recommendation:
    code: str
    title: str
    detail: str
    priority: str
    action: str


@dataclass(frozen=True)
class ActivityPoint:
    label: str
    events: int
    failed_logins: int
    encryption_events: int


@dataclass(frozen=True)
class SecurityReport:
    generated_at: str
    score: int
    health: str
    metrics: WorkspaceMetrics
    recommendations: tuple[Recommendation, ...]
    activity: tuple[ActivityPoint, ...]

    def as_dict(self) -> dict:
        value = asdict(self)
        value["metrics"] = asdict(self.metrics)
        value["recommendations"] = [asdict(item) for item in self.recommendations]
        value["activity"] = [asdict(item) for item in self.activity]
        return value


class RecommendationEngine:
    def evaluate(self, metrics: WorkspaceMetrics, backup_recent: bool = False) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        if not metrics.integrity_verified:
            recommendations.append(Recommendation("integrity", "Review database integrity", "The database digest does not match its startup sidecar.", "critical", "Open diagnostics"))
        if metrics.failed_logins:
            priority = "high" if metrics.failed_logins >= 3 else "medium"
            recommendations.append(Recommendation("login-review", "Review failed access attempts", f"There are {metrics.failed_logins} failed login events in the audit history.", priority, "Open audit"))
        if metrics.total_items == 0:
            recommendations.append(Recommendation("first-item", "Create your first protected item", "The workspace is ready but does not contain any encrypted records yet.", "low", "Open organization"))
        if metrics.password_items > 0 and metrics.password_items < 3:
            recommendations.append(Recommendation("coverage", "Add more credential coverage", "Consider moving frequently used accounts into the encrypted password manager.", "low", "Open passwords"))
        if not backup_recent and metrics.total_items > 0:
            recommendations.append(Recommendation("backup", "Create an encrypted backup", "A portable encrypted backup protects against local storage loss.", "medium", "Open settings"))
        if not recommendations:
            recommendations.append(Recommendation("healthy", "Workspace is in good shape", "No immediate operational recommendations were detected.", "info", "Refresh report"))
        return recommendations


class ActivityReport:
    def __init__(self, audit: AuditService):
        self.audit = audit

    def daily(self, days: int = 7) -> list[ActivityPoint]:
        days = min(max(days, 1), 31)
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        all_events = self.audit.events(10_000)
        points = []
        for offset in range(days - 1, -1, -1):
            date = now - timedelta(days=offset)
            label = date.strftime("%d %b")
            prefix = date.strftime("%Y-%m-%d")
            events = [event for event in all_events if event["created_at"].startswith(prefix)]
            points.append(ActivityPoint(label, len(events), sum(event["event"] == "LOGIN_FAILED" for event in events), sum(event["event"] in {"ENCRYPT", "STORE"} for event in events)))
        return points

    def event_breakdown(self) -> dict[str, int]:
        return self.audit.event_counts(10_000)

    def busiest_day(self, points: Iterable[ActivityPoint]) -> ActivityPoint | None:
        values = list(points)
        return max(values, key=lambda item: item.events) if values else None


class ReportService:
    def __init__(self, database: Database, inventory: VaultInventory | None = None):
        self.database = database
        self.metrics = MetricsService(database, inventory)
        self.audit = AuditService(database)
        self.recommendations = RecommendationEngine()
        self.activity = ActivityReport(self.audit)

    def score(self, metrics: WorkspaceMetrics | None = None) -> int:
        metrics = metrics or self.metrics.collect()
        score = 100
        score -= 45 if not metrics.integrity_verified else 0
        score -= min(metrics.failed_logins * 8, 40)
        score -= 5 if metrics.total_items == 0 else 0
        return max(0, score)

    def build(self, backup_recent: bool = False, days: int = 7) -> SecurityReport:
        metrics = self.metrics.collect()
        points = tuple(self.activity.daily(days))
        return SecurityReport(datetime.now().isoformat(timespec="seconds"), self.score(metrics), self.metrics.health(), metrics, tuple(self.recommendations.evaluate(metrics, backup_recent)), points)

    def save_json(self, destination: Path, report: SecurityReport | None = None) -> Path:
        report = report or self.build()
        destination.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
        self.database.add_audit("EXPORT_REPORT", f"Security report exported: {destination.name}")
        return destination

    def save_html(self, destination: Path, report: SecurityReport | None = None) -> Path:
        report = report or self.build()
        recommendation_rows = "".join(f"<tr><td>{escape(item.priority.upper())}</td><td>{escape(item.title)}</td><td>{escape(item.detail)}</td></tr>" for item in report.recommendations)
        activity_rows = "".join(f"<tr><td>{escape(point.label)}</td><td>{point.events}</td><td>{point.failed_logins}</td><td>{point.encryption_events}</td></tr>" for point in report.activity)
        html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Data Security System Report</title>
<style>body{{font-family:Segoe UI,sans-serif;background:#101418;color:#f1f4f6;max-width:960px;margin:40px auto;padding:0 24px}}section{{background:#171d22;border-radius:10px;padding:22px;margin:18px 0}}h1{{color:#80c5d2}}h2{{font-size:16px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #304049;text-align:left}}.score{{font-size:42px;color:#85c99a}}.muted{{color:#9aa7ae}}</style></head>
<body><h1>Data Security System</h1><p class="muted">Operational security report · {escape(report.generated_at)}</p>
<section><h2>Security posture</h2><div class="score">{report.score} / 100</div><p>{escape(report.health)}</p><p>{report.metrics.total_items} encrypted items · {report.metrics.audit_events} audit events · integrity {'verified' if report.metrics.integrity_verified else 'requires review'}</p></section>
<section><h2>Recommendations</h2><table><tr><th>Priority</th><th>Recommendation</th><th>Detail</th></tr>{recommendation_rows}</table></section>
<section><h2>Activity by day</h2><table><tr><th>Day</th><th>Events</th><th>Failed logins</th><th>Encryption events</th></tr>{activity_rows}</table></section></body></html>"""
        destination.write_text(html, encoding="utf-8")
        self.database.add_audit("EXPORT_REPORT", f"HTML security report exported: {destination.name}")
        return destination

    def plain_text(self, report: SecurityReport | None = None) -> str:
        report = report or self.build()
        lines = ["DATA SECURITY SYSTEM REPORT", f"Generated: {report.generated_at}", f"Security score: {report.score}/100", f"Health: {report.health}", "", "RECOMMENDATIONS"]
        lines.extend(f"[{item.priority.upper()}] {item.title}: {item.detail}" for item in report.recommendations)
        lines.append("\nACTIVITY")
        lines.extend(f"{point.label}: {point.events} events, {point.failed_logins} failed logins, {point.encryption_events} encryption events" for point in report.activity)
        return "\n".join(lines)

    def export(self, destination: Path, format_name: str = "json") -> Path:
        if format_name == "html":
            return self.save_html(destination)
        if format_name == "txt":
            destination.write_text(self.plain_text(), encoding="utf-8")
            self.database.add_audit("EXPORT_REPORT", f"Text security report exported: {destination.name}")
            return destination
        return self.save_json(destination)
