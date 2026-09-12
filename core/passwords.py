"""Password generation and strength analysis utilities.

This module deliberately has no UI dependencies so it can be tested and reused by
future import/export or command-line tooling.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass


@dataclass(frozen=True)
class PasswordAssessment:
    score: int
    label: str
    color: str
    suggestions: tuple[str, ...]


class PasswordGenerator:
    """Generate passwords using a cryptographically secure random source."""

    LOWER = string.ascii_lowercase
    UPPER = string.ascii_uppercase
    DIGITS = string.digits
    SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"

    def generate(
        self,
        length: int = 24,
        include_lower: bool = True,
        include_upper: bool = True,
        include_digits: bool = True,
        include_symbols: bool = True,
        exclude_ambiguous: bool = False,
    ) -> str:
        if not 12 <= length <= 128:
            raise ValueError("Password length must be between 12 and 128 characters")
        pools = []
        if include_lower:
            pools.append(self.LOWER)
        if include_upper:
            pools.append(self.UPPER)
        if include_digits:
            pools.append(self.DIGITS)
        if include_symbols:
            pools.append(self.SYMBOLS)
        if not pools:
            raise ValueError("Select at least one character group")
        if exclude_ambiguous:
            pools = [pool.translate(str.maketrans("O0Il1|", "      ")) for pool in pools]
            pools = [pool.replace(" ", "") for pool in pools]
        if any(not pool for pool in pools):
            raise ValueError("The selected character groups are empty")
        required = [secrets.choice(pool) for pool in pools]
        alphabet = "".join(pools)
        remaining = [secrets.choice(alphabet) for _ in range(length - len(required))]
        result = required + remaining
        secrets.SystemRandom().shuffle(result)
        return "".join(result)

    def memorable(self, words: list[str], separator: str = "-") -> str:
        if len(words) < 4:
            raise ValueError("Use at least four words")
        chosen = [secrets.choice(words).strip() for _ in range(4)]
        suffix = secrets.randbelow(9000) + 1000
        return separator.join(chosen) + separator + str(suffix)


class PasswordStrength:
    """Small deterministic strength estimator for immediate UI feedback."""

    COMMON = {"password", "password123", "qwerty", "letmein", "welcome", "admin"}

    def assess(self, password: str) -> PasswordAssessment:
        if not password:
            return PasswordAssessment(0, "Empty", "#7f8c95", ("Use a long, unique password.",))
        score = 0
        suggestions: list[str] = []
        lowered = password.lower()
        if len(password) >= 12:
            score += 2
        else:
            suggestions.append("Use at least 12 characters.")
        if len(password) >= 20:
            score += 1
        if any(char.islower() for char in password):
            score += 1
        else:
            suggestions.append("Add lowercase letters.")
        if any(char.isupper() for char in password):
            score += 1
        else:
            suggestions.append("Add uppercase letters.")
        if any(char.isdigit() for char in password):
            score += 1
        else:
            suggestions.append("Add numbers.")
        if any(not char.isalnum() for char in password):
            score += 1
        else:
            suggestions.append("Add symbols.")
        if lowered in self.COMMON or len(set(password)) < max(4, len(password) // 4):
            score = max(0, score - 2)
            suggestions.append("Avoid common or repeated patterns.")
        if score <= 2:
            return PasswordAssessment(score, "Weak", "#cf7777", tuple(suggestions))
        if score <= 4:
            return PasswordAssessment(score, "Fair", "#d8b878", tuple(suggestions))
        if score <= 6:
            return PasswordAssessment(score, "Strong", "#76b7c5", tuple(suggestions))
        return PasswordAssessment(score, "Excellent", "#7fc69a", tuple(suggestions))
