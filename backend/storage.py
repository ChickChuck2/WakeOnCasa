import json
import os
import uuid
from threading import Lock
from typing import List, Dict, Any, Optional

DATA_DIR = os.getenv("DATA_DIR", "/tmp/data" if os.getenv("VERCEL") else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
DEVICES_FILE = os.path.join(DATA_DIR, "devices.json")

file_lock = Lock()

# Inicia com lista vazia para produção
INITIAL_DEVICES: List[Dict[str, Any]] = []

def ensure_data_file():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(DEVICES_FILE):
            with open(DEVICES_FILE, "w", encoding="utf-8") as f:
                json.dump(INITIAL_DEVICES, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_devices() -> List[Dict[str, Any]]:
    ensure_data_file()
    with file_lock:
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

def save_devices(devices: List[Dict[str, Any]]) -> None:
    ensure_data_file()
    with file_lock:
        try:
            with open(DEVICES_FILE, "w", encoding="utf-8") as f:
                json.dump(devices, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

def get_device_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    devices = get_devices()
    for dev in devices:
        if dev["id"] == device_id:
            return dev
    return None

def add_device(device_data: Dict[str, Any]) -> Dict[str, Any]:
    devices = get_devices()
    new_device = {
        "id": f"dev-{uuid.uuid4().hex[:8]}",
        "name": device_data.get("name", "Novo Dispositivo"),
        "ip": device_data.get("ip", ""),
        "mac": device_data.get("mac", "").upper(),
        "category": device_data.get("category", "desktop"),
        "notes": device_data.get("notes", ""),
    }
    devices.append(new_device)
    save_devices(devices)
    return new_device

def update_device(device_id: str, device_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    devices = get_devices()
    for i, dev in enumerate(devices):
        if dev["id"] == device_id:
            updated = {
                **dev,
                "name": device_data.get("name", dev["name"]),
                "ip": device_data.get("ip", dev["ip"]),
                "mac": device_data.get("mac", dev["mac"]).upper(),
                "category": device_data.get("category", dev["category"]),
                "notes": device_data.get("notes", dev.get("notes", "")),
            }
            devices[i] = updated
            save_devices(devices)
            return updated
    return None

def delete_device(device_id: str) -> bool:
    devices = get_devices()
    filtered = [dev for dev in devices if dev["id"] != device_id]
    if len(filtered) < len(devices):
        save_devices(filtered)
        return True
    return False
