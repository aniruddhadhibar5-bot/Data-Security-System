# Data Security System

A local, dark-themed CustomTkinter desktop vault designed and developed by Aniruddha Dhibar.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

On first launch, create a master password of at least 10 characters and a 6-digit PIN. The application stores its encrypted SQLite database and encrypted file payloads under `data/`.

## Security model

- Argon2id derives a 256-bit master key from the password.
- Each stored item receives a random AES-GCM key, wrapped by the master key.
- Passwords, notes, and metadata payloads are encrypted before database storage.
- Files are encrypted into `data/vault/` and can be restored through the File & Photo Vault view.
- A SHA-256 database sidecar is checked at startup and updated after writes.
- The active session locks after five minutes of inactivity.
- Copied password values are cleared from the clipboard after 15 seconds.

This is a local application. Back up the `data/` directory securely; losing the master password means losing access to the vault.
