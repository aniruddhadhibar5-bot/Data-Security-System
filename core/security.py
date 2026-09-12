"""Cryptographic primitives used by the application."""

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import PBKDF_MEMORY_COST, PBKDF_PARALLELISM, PBKDF_TIME_COST


@dataclass(frozen=True)
class EncryptedValue:
    nonce: bytes
    ciphertext: bytes


class SecurityManager:
    """Owns password derivation and authenticated encryption operations."""

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        return hash_secret_raw(
            password.encode("utf-8"), salt, PBKDF_TIME_COST,
            PBKDF_MEMORY_COST, PBKDF_PARALLELISM, 32, Type.ID,
        )

    @staticmethod
    def encrypt(data: bytes, key: bytes, associated_data: bytes = b"") -> EncryptedValue:
        nonce = os.urandom(12)
        return EncryptedValue(nonce, AESGCM(key).encrypt(nonce, data, associated_data))

    @staticmethod
    def decrypt(value: EncryptedValue, key: bytes, associated_data: bytes = b"") -> bytes:
        return AESGCM(key).decrypt(value.nonce, value.ciphertext, associated_data)

    @staticmethod
    def pack(value: EncryptedValue) -> str:
        return base64.urlsafe_b64encode(value.nonce + value.ciphertext).decode("ascii")

    @staticmethod
    def unpack(value: str) -> EncryptedValue:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        return EncryptedValue(raw[:12], raw[12:])

    @staticmethod
    def fingerprint(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def verify_password(key: bytes, stored: str) -> bool:
        probe = SecurityManager.encrypt(b"master-password-check", key)
        return hmac.compare_digest(SecurityManager.pack(probe), stored)
