"""Audit log analysis and export helpers."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from core.database import Database


class AuditService:
    def __init__(self, database: Database):
        self.database = database

    def events(self, limit: int = 100, event: str | None = None) -> list[dict]:
        rows = self.database.recent_audit(limit)
        if event:
            rows = [row for row in rows if row["event"] == event]
        return [dict(row) for row in rows]

    def events_today(self) -> list[dict]:
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        end = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        return [dict(row) for row in self.database.audit_between(start, end)]

    def event_counts(self, limit: int = 500) -> dict[str, int]:
        return dict(Counter(item["event"] for item in self.events(limit)))

    def failed_logins(self, limit: int = 500) -> int:
        return self.event_counts(limit).get("LOGIN_FAILED", 0)

    def security_summary(self) -> dict[str, str | int]:
        counts = self.event_counts()
        return {
            "events": sum(counts.values()),
            "today": len(self.events_today()),
            "failed_logins": counts.get("LOGIN_FAILED", 0),
            "encrypted_items": self.database.count_items(),
            "last_event": self.events(1)[0]["created_at"] if self.events(1) else "No activity",
        }

    def export_csv(self, destination: Path) -> Path:
        rows = self.events(10_000)
        with destination.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("id", "event", "detail", "created_at"))
            writer.writeheader()
            writer.writerows(rows)
        self.database.add_audit("EXPORT_AUDIT", f"Audit log exported: {destination.name}")
        return destination

    def export_json(self, destination: Path) -> Path:
        destination.write_text(json.dumps(self.events(10_000), indent=2), encoding="utf-8")
        self.database.add_audit("EXPORT_AUDIT", f"Audit JSON exported: {destination.name}")
        return destination

    def render_text(self, limit: int = 50) -> str:
        lines = ["AUDIT LOG", "=" * 72]
        for event in self.events(limit):
            lines.append(f"{event['created_at']}  {event['event']:<16}  {event['detail']}")
        return "\n".join(lines)

    def render_summary(self) -> str:
        summary = self.security_summary()
        return "\n".join([f"{key.replace('_', ' ').title()}: {value}" for key, value in summary.items()])
