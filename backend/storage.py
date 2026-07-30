import json
import os
import re
import uuid
from threading import Lock
from typing import List, Dict, Any, Optional

DATA_DIR = os.getenv("DATA_DIR", "/tmp/data" if os.getenv("VERCEL") else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
SETTINGS_FILE = os.path.join(DATA_DIR, "devices.json")

file_lock = Lock()

TEST_DEVICE_IDS = {"dev-pc-gamer", "dev-nas-server"}

def format_mac(mac_address: str) -> str:
    if not mac_address:
        return ""
    cleaned = re.sub(r'[^a-fA-F0-9]', '', mac_address).upper()
    if len(cleaned) == 12:
        return ":".join(cleaned[i:i+2] for i in range(0, 12, 2))
    return mac_address.upper()

def purge_legacy_test_devices(devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [d for d in devices if d.get("id") not in TEST_DEVICE_IDS and "AA:BB:CC:11:22:33" not in d.get("mac", "")]

def merge_devices(local_list: List[Dict[str, Any]], cloud_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mescla listas de dispositivos local e nuvem de forma não-destrutiva baseando-se no ID.
    """
    merged_map = {}
    for d in local_list:
        if isinstance(d, dict) and d.get("id"):
            merged_map[d["id"]] = d
    for d in cloud_list:
        if isinstance(d, dict) and d.get("id"):
            merged_map[d["id"]] = d
    return purge_legacy_test_devices(list(merged_map.values()))

def ensure_data_file():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2, ensure_ascii=False)
        else:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cleaned = purge_legacy_test_devices(data)
            if len(cleaned) != len(data):
                save_devices(cleaned)
    except Exception:
        pass

def get_devices() -> List[Dict[str, Any]]:
    ensure_data_file()
    with file_lock:
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return purge_legacy_test_devices(data)
        except Exception:
            return []

def save_devices(devices: List[Dict[str, Any]]) -> None:
    ensure_data_file()
    cleaned = purge_legacy_test_devices(devices)
    with file_lock:
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, indent=2, ensure_ascii=False)
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
        "ip": device_data.get("ip", "").strip(),
        "mac": format_mac(device_data.get("mac", "")),
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
                "ip": device_data.get("ip", dev["ip"]).strip(),
                "mac": format_mac(device_data.get("mac", dev["mac"])),
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
    save_devices(filtered)
    return len(filtered) < len(devices)

def clear_all_devices() -> None:
    save_devices([])
