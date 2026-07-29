import json
import os
from threading import Lock
from typing import Dict, Any

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

file_lock = Lock()

DEFAULT_SETTINGS = {
    "ping_interval_seconds": 10,
    "webhook_url": "",
    "notify_online": True,
    "notify_offline": True
}

def ensure_settings_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2, ensure_ascii=False)

def get_settings() -> Dict[str, Any]:
    ensure_settings_file()
    with file_lock:
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_SETTINGS, **data}
        except Exception:
            return DEFAULT_SETTINGS.copy()

def update_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    current = get_settings()
    updated = {**current, **new_settings}
    ensure_settings_file()
    with file_lock:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(updated, f, indent=2, ensure_ascii=False)
    return updated
