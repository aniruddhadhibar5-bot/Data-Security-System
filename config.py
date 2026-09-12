from pathlib import Path

APP_NAME = "Data Security System"
APP_VERSION = "1.0.0"
CREDITS = "Designed and Developed by Aniruddha Dhibar"
BASE_DIR = Path(__file__).resolve().parent
FRESH_VAULT_MARKER = BASE_DIR / ".fresh_vault"
DATA_DIR = BASE_DIR / "data_fresh" if FRESH_VAULT_MARKER.exists() else BASE_DIR / "data"
VAULT_DIR = DATA_DIR / "vault"
DATABASE_PATH = DATA_DIR / "security.db"
INTEGRITY_PATH = DATA_DIR / "security.db.sha256"
IDLE_TIMEOUT_SECONDS = 5 * 60
CLIPBOARD_CLEAR_SECONDS = 15
PBKDF_TIME_COST = 3
PBKDF_MEMORY_COST = 65536
PBKDF_PARALLELISM = 2

for directory in (DATA_DIR, VAULT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
