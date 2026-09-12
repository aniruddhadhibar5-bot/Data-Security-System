"""Persisted, typed workspace settings.

Settings are metadata rather than secrets. Sensitive values remain in the
vault records and are never copied into this preferences layer.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from typing import Any

from core.database import Database


@dataclass
class WorkspaceSettings:
    appearance: str = "Dark"
    idle_timeout_seconds: int = 300
    clipboard_timeout_seconds: int = 15
    start_on_dashboard: bool = True
    confirm_deletions: bool = True
    show_recovery_keys: bool = False
    auto_refresh_seconds: int = 30
    backup_extension: str = ".dssbackup"
    compact_audit_view: bool = False


class SettingsService:
    KEY = "workspace_settings"

    def __init__(self, database: Database):
        self.database = database
        self.settings = self.load()

    def load(self) -> WorkspaceSettings:
        raw = self.database.get_metadata(self.KEY)
        if not raw:
            return WorkspaceSettings()
        try:
            values = json.loads(raw)
        except json.JSONDecodeError:
            return WorkspaceSettings()
        valid_names = {field.name for field in fields(WorkspaceSettings)}
        clean = {key: value for key, value in values.items() if key in valid_names}
        result = WorkspaceSettings(**clean)
        self._normalize(result)
        return result

    def save(self, settings: WorkspaceSettings | None = None) -> WorkspaceSettings:
        if settings is not None:
            self.settings = settings
        self._normalize(self.settings)
        self.database.set_metadata(self.KEY, json.dumps(asdict(self.settings), sort_keys=True))
        self.database.add_audit("SETTINGS", "Workspace settings saved")
        return self.settings

    def reset(self) -> WorkspaceSettings:
        self.settings = WorkspaceSettings()
        return self.save()

    def update(self, **changes: Any) -> WorkspaceSettings:
        valid_names = {field.name for field in fields(WorkspaceSettings)}
        for key, value in changes.items():
            if key in valid_names:
                setattr(self.settings, key, value)
        return self.save()

    def get(self, name: str, default: Any = None) -> Any:
        return getattr(self.settings, name, default)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self.settings)

    def _normalize(self, settings: WorkspaceSettings) -> None:
        settings.appearance = settings.appearance if settings.appearance in {"Dark", "Light", "System"} else "Dark"
        settings.idle_timeout_seconds = min(max(int(settings.idle_timeout_seconds), 30), 86_400)
        settings.clipboard_timeout_seconds = min(max(int(settings.clipboard_timeout_seconds), 5), 3_600)
        settings.auto_refresh_seconds = min(max(int(settings.auto_refresh_seconds), 5), 3_600)
        if not settings.backup_extension.startswith("."):
            settings.backup_extension = "." + settings.backup_extension


class SettingDefinition:
    def __init__(self, name: str, label: str, description: str, value_type: type):
        self.name = name
        self.label = label
        self.description = description
        self.value_type = value_type

    def parse(self, value: str) -> Any:
        if self.value_type is bool:
            return value.casefold() in {"true", "yes", "1", "on"}
        if self.value_type is int:
            return int(value)
        return value


SETTING_DEFINITIONS = (
    SettingDefinition("appearance", "Appearance", "The visual theme used by the workspace.", str),
    SettingDefinition("idle_timeout_seconds", "Idle timeout", "Seconds before automatic lock.", int),
    SettingDefinition("clipboard_timeout_seconds", "Clipboard timeout", "Seconds before copied secrets are cleared.", int),
    SettingDefinition("start_on_dashboard", "Start on dashboard", "Open the overview after authentication.", bool),
    SettingDefinition("confirm_deletions", "Confirm deletions", "Ask before removing vault records.", bool),
    SettingDefinition("show_recovery_keys", "Show recovery keys", "Permit visible keys in the recovery view.", bool),
    SettingDefinition("auto_refresh_seconds", "Auto refresh", "Refresh interval for operational views.", int),
    SettingDefinition("backup_extension", "Backup extension", "Filename extension used for exported backups.", str),
    SettingDefinition("compact_audit_view", "Compact audit view", "Use denser audit event rows.", bool),
)


def setting_definition(name: str) -> SettingDefinition | None:
    return next((definition for definition in SETTING_DEFINITIONS if definition.name == name), None)


def setting_labels() -> list[str]:
    return [definition.label for definition in SETTING_DEFINITIONS]


def serialize_settings(settings: WorkspaceSettings) -> str:
    return json.dumps(asdict(settings), sort_keys=True, indent=2)
