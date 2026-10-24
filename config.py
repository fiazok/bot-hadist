# config.py (v2)
# Membaca konfigurasi dari variabel lingkungan atau file .env
# (di folder ini atau satu folder di atasnya). Tanpa dependensi tambahan.
import os
from pathlib import Path


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_HERE = Path(__file__).resolve().parent
_load_env(_HERE / ".env")
_load_env(_HERE.parent / ".env")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
# ID Telegram admin (angka) untuk perintah /perbarui. Kosong = perintah dinonaktifkan.
ADMIN_ID = os.environ.get("ADMIN_ID", "").strip()
