"""Safely reset a forgotten Data Security System master password.

The original vault cannot be decrypted without its original master password.
This utility preserves the old encrypted data in a timestamped archive and
creates a clean vault only after an explicit confirmation token is supplied.

Usage:
    python reset_vault.py --confirm RESET
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FRESH_DATA = ROOT / "data_fresh"
ARCHIVE_ROOT = ROOT / "forgotten_vault_archives"
FRESH_MARKER = ROOT / ".fresh_vault"


def archive_existing_data() -> Path | None:
    if not DATA.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = ARCHIVE_ROOT / f"vault_{timestamp}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DATA, destination)
    return destination


def reset_data() -> Path | None:
    archive = archive_existing_data()
    # OneDrive-managed folders can deny deletion. A separate active data root
    # preserves the original folder while allowing a reliable fresh start.
    if FRESH_DATA.exists():
        shutil.rmtree(FRESH_DATA, ignore_errors=False)
    (FRESH_DATA / "vault").mkdir(parents=True, exist_ok=True)
    FRESH_MARKER.write_text("fresh vault active\n", encoding="utf-8")
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive and reset a forgotten DSS vault.")
    parser.add_argument("--confirm", required=True, help="Type RESET to confirm this irreversible access reset")
    args = parser.parse_args()
    if args.confirm != "RESET":
        print("Reset cancelled. The exact confirmation token is: RESET")
        return 2
    archive = reset_data()
    print("A new empty vault directory was created.")
    if archive:
        print(f"The previous encrypted vault was preserved at: {archive}")
        print("The old data still requires the original master password and cannot be recovered by this reset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
