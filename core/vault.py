"""High-level encrypted vault operations."""

import json
import os
import secrets
import base64
from pathlib import Path

from config import VAULT_DIR
from core.database import Database
from core.security import EncryptedValue, SecurityManager


class VaultService:
    def __init__(self, database: Database):
        self.database = database
        self.security = SecurityManager()
        self.master_key: bytes | None = None

    @property
    def is_configured(self) -> bool:
        return self.database.get_metadata("salt") is not None

    def configure_master(self, password: str, pin: str) -> None:
        salt = os.urandom(16)
        key = self.security.derive_key(password, salt)
        self.database.set_metadata("salt", base64.urlsafe_b64encode(salt).decode("ascii"))
        self.database.set_metadata("password_check", self.security.pack(self.security.encrypt(b"master-password-check", key)))
        self.database.set_metadata("pin", self.security.pack(self.security.encrypt(pin.encode(), key)))
        self.master_key = key
        self.database.add_audit("SETUP", "Master password and simulated 2FA PIN configured")

    def authenticate(self, password: str, pin: str) -> bool:
        try:
            salt = base64.urlsafe_b64decode((self.database.get_metadata("salt") or "").encode("ascii"))
            key = self.security.derive_key(password, salt)
            check = self.security.unpack(self.database.get_metadata("password_check") or "")
            stored_pin = self.security.unpack(self.database.get_metadata("pin") or "")
            valid = self.security.decrypt(check, key) == b"master-password-check"
            valid = valid and self.security.decrypt(stored_pin, key).decode() == pin
            if valid:
                self.master_key = key
                self.database.add_audit("LOGIN", "Master password and PIN verified")
            else:
                self.database.add_audit("LOGIN_FAILED", "Invalid password or PIN")
            return valid
        except Exception:
            self.database.add_audit("LOGIN_FAILED", "Invalid authentication material")
            return False

    def lock(self) -> None:
        self.master_key = None

    def _require_key(self) -> bytes:
        if self.master_key is None:
            raise PermissionError("Vault is locked")
        return self.master_key

    def _store_payload(self, kind: str, title: str, payload: bytes) -> int:
        master_key = self._require_key()
        item_key = os.urandom(32)
        encrypted = self.security.encrypt(payload, item_key)
        wrapped = self.security.encrypt(item_key, master_key)
        return self.database.add_item(kind, title, self.security.pack(encrypted), self.security.pack(wrapped))

    def _read_payload(self, row) -> bytes:
        master_key = self._require_key()
        item_key = self.security.decrypt(self.security.unpack(row["wrapped_key"]), master_key)
        return self.security.decrypt(self.security.unpack(row["payload"]), item_key)

    def store_secret(self, kind: str, title: str, values: dict) -> int:
        item_id = self._store_payload(kind, title, json.dumps(values).encode("utf-8"))
        self.database.add_audit("STORE", f"Encrypted {kind.lower()}: {title}")
        return item_id

    def read_secret(self, item_id: int) -> dict:
        row = self.database.get_item(item_id)
        if row is None:
            raise KeyError(f"Unknown vault item: {item_id}")
        return json.loads(self._read_payload(row).decode("utf-8"))

    def update_secret(self, item_id: int, title: str, values: dict) -> None:
        row = self.database.get_item(item_id)
        if row is None or row["kind"] == "FILE":
            raise KeyError(f"Unknown editable item: {item_id}")
        master_key = self._require_key()
        item_key = self.security.decrypt(self.security.unpack(row["wrapped_key"]), master_key)
        encrypted = self.security.encrypt(json.dumps(values).encode("utf-8"), item_key)
        self.database.update_item(item_id, title, self.security.pack(encrypted))
        self.database.add_audit("UPDATE", f"Updated {row['kind'].lower()}: {title}")

    def search_items(self, kind: str | None = None, query: str = "") -> list:
        query = query.casefold().strip()
        return [row for row in self.database.list_items(kind) if not query or query in row["title"].casefold()]

    def store_file(self, source: Path) -> int:
        item_key = os.urandom(32)
        encrypted = self.security.encrypt(source.read_bytes(), item_key)
        destination = VAULT_DIR / f"{secrets.token_hex(12)}.dsv"
        destination.write_bytes(encrypted.nonce + encrypted.ciphertext)
        master_key = self._require_key()
        wrapped = self.security.pack(self.security.encrypt(item_key, master_key))
        item_id = self.database.add_item("FILE", source.name, str(destination), wrapped)
        self.database.add_audit("ENCRYPT", f"Encrypted file: {source.name}")
        return item_id

    def decrypt_file(self, item_id: int, destination: Path) -> None:
        row = next(row for row in self.database.list_items("FILE") if row["id"] == item_id)
        item_key = self.security.decrypt(self.security.unpack(row["wrapped_key"]), self._require_key())
        raw = Path(row["payload"]).read_bytes()
        decrypted = self.security.decrypt(EncryptedValue(raw[:12], raw[12:]), item_key)
        destination.write_bytes(decrypted)
        self.database.add_audit("DECRYPT", f"Restored file: {row['title']}")

    def recovery_items(self) -> list[dict]:
        self._require_key()
        result = []
        for row in self.database.list_items():
            item_key = self.security.decrypt(self.security.unpack(row["wrapped_key"]), self.master_key)
            result.append({"id": row["id"], "kind": row["kind"], "title": row["title"], "key": item_key.hex()})
        return result

    def export_backup(self, destination: Path) -> Path:
        from core.backup import BackupService
        return BackupService(self.database, self.security).create_backup(destination, self._require_key())

    def remove_item(self, item_id: int) -> None:
        rows = self.database.list_items()
        row = next(row for row in rows if row["id"] == item_id)
        if row["kind"] == "FILE":
            Path(row["payload"]).unlink(missing_ok=True)
        self.database.delete_item(item_id)
        self.database.add_audit("DELETE", f"Deleted {row['kind'].lower()}: {row['title']}")
