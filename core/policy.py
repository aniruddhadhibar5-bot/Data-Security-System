"""Configurable security policy checks.

The policy object keeps authentication and storage requirements in one place.
It can be extended later without scattering magic numbers across UI handlers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.passwords import PasswordStrength
from core.validators import InputValidator, ValidationResult


@dataclass(frozen=True)
class SecurityPolicy:
    minimum_master_length: int = 14
    minimum_password_score: int = 4
    pin_length: int = 6
    lock_timeout_seconds: int = 300
    clipboard_timeout_seconds: int = 15
    maximum_failed_logins: int = 5
    require_mixed_master_password: bool = True

    def validate_master_password(self, password: str) -> ValidationResult:
        if len(password) < self.minimum_master_length:
            return ValidationResult(False, f"Master passwords must contain at least {self.minimum_master_length} characters.")
        if self.require_mixed_master_password:
            groups = [r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"]
            missing = sum(re.search(pattern, password) is None for pattern in groups)
            if missing:
                return ValidationResult(False, "Master passwords must include lowercase, uppercase, numbers, and symbols.")
        assessment = PasswordStrength().assess(password)
        if assessment.score < self.minimum_password_score:
            return ValidationResult(False, f"Choose a stronger master password ({assessment.label.lower()} strength).")
        return ValidationResult(True)

    def validate_pin(self, pin: str) -> ValidationResult:
        result = InputValidator().pin(pin)
        if not result:
            return result
        if pin in {"012345", "123456", "654321", "000000"}:
            return ValidationResult(False, "Choose a less predictable PIN.")
        return ValidationResult(True)

    def settings(self) -> dict[str, int | bool]:
        return {
            "minimum_master_length": self.minimum_master_length,
            "minimum_password_score": self.minimum_password_score,
            "pin_length": self.pin_length,
            "lock_timeout_seconds": self.lock_timeout_seconds,
            "clipboard_timeout_seconds": self.clipboard_timeout_seconds,
            "maximum_failed_logins": self.maximum_failed_logins,
            "require_mixed_master_password": self.require_mixed_master_password,
        }


class RateLimiter:
    def __init__(self, maximum_attempts: int = 5):
        self.maximum_attempts = maximum_attempts
        self.attempts = 0
        self.blocked = False

    def record_failure(self) -> bool:
        self.attempts += 1
        self.blocked = self.attempts >= self.maximum_attempts
        return not self.blocked

    def record_success(self) -> None:
        self.attempts = 0
        self.blocked = False

    def remaining(self) -> int:
        return max(0, self.maximum_attempts - self.attempts)

    def reset(self) -> None:
        self.attempts = 0
        self.blocked = False


class SessionPolicy:
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self.last_activity = None

    def touch(self, timestamp: float) -> None:
        self.last_activity = timestamp

    def elapsed(self, timestamp: float) -> float:
        if self.last_activity is None:
            return 0
        return max(0, timestamp - self.last_activity)

    def should_lock(self, timestamp: float) -> bool:
        return self.last_activity is not None and self.elapsed(timestamp) >= self.policy.lock_timeout_seconds

    def reset(self) -> None:
        self.last_activity = None
