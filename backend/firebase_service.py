import os
import asyncio
import json
import logging
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List

from backend import settings, wol, storage

logger = logging.getLogger("wakeoncasa.firebase")

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "testproject-49566")

def get_firebase_config() -> Dict[str, str]:
    cfg = settings.get_settings()
    db_url = cfg.get("firebase_database_url", "").strip() or os.getenv("FIREBASE_DATABASE_URL", "").strip()
    auth_secret = cfg.get("firebase_auth_secret", "").strip() or os.getenv("FIREBASE_AUTH_SECRET", "").strip()
    
    if not db_url:
        db_url = f"https://{PROJECT_ID}-default-rtdb.firebaseio.com"

    if db_url.endswith("/"):
        db_url = db_url[:-1]
        
    return {
        "url": db_url,
        "secret": auth_secret,
        "project_id": PROJECT_ID
    }

def is_firebase_enabled() -> bool:
    config = get_firebase_config()
    return bool(config["url"] or config["project_id"])

def check_firebase_connection() -> bool:
    config = get_firebase_config()
    
    if config["url"]:
        endpoint = f"{config['url']}/.json?shallow=true"
        if config["secret"]:
            endpoint += f"&auth={config['secret']}"
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "WakeOnCasa-Check/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status in (200, 401, 403):
                    return True
        except urllib.error.HTTPError as err:
            if err.code in (401, 403, 404):
                return True
        except Exception:
            pass

    try:
        firestore_url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
        req = urllib.request.Request(firestore_url, headers={"User-Agent": "WakeOnCasa-Check/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return True
    except urllib.error.HTTPError as err:
        if err.code in (401, 403, 404):
            return True
    except Exception:
        pass

    return False

def sync_devices_to_firebase(devices: List[Dict[str, Any]]) -> bool:
    config = get_firebase_config()
    if not config["url"]:
        return False

    endpoint = f"{config['url']}/devices.json"
    if config["secret"]:
        endpoint += f"?auth={config['secret']}"

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(devices, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info("Lista de dispositivos sincronizada no Firebase com sucesso.")
            return True
    except Exception as e:
        logger.error(f"Erro ao sincronizar dispositivos no Firebase: {e}")
        return False

def fetch_devices_from_firebase() -> Optional[List[Dict[str, Any]]]:
    config = get_firebase_config()
    if not config["url"]:
        return None

    endpoint = f"{config['url']}/devices.json"
    if config["secret"]:
        endpoint += f"?auth={config['secret']}"

    try:
        req = urllib.request.Request(endpoint, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_data = resp.read().decode("utf-8")
            if not raw_data or raw_data == "null":
                return []
            data = json.loads(raw_data)
            if isinstance(data, list):
                return storage.purge_legacy_test_devices(data)
            elif isinstance(data, dict):
                return storage.purge_legacy_test_devices(list(data.values()))
    except Exception as e:
        logger.error(f"Erro ao buscar dispositivos do Firebase: {e}")
    return None

def sync_statuses_to_firebase(statuses: Dict[str, Dict[str, Any]]) -> bool:
    """
    CasaOS publica os status ao vivo (ping) no Firebase (/statuses.json).
    """
    config = get_firebase_config()
    if not config["url"]:
        return False

    endpoint = f"{config['url']}/statuses.json"
    if config["secret"]:
        endpoint += f"?auth={config['secret']}"

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(statuses, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True
    except Exception as e:
        logger.error(f"Erro ao sincronizar status no Firebase: {e}")
        return False

def fetch_statuses_from_firebase() -> Dict[str, Dict[str, Any]]:
    """
    Vercel busca os status ao vivo enviados pelo CasaOS (/statuses.json).
    """
    config = get_firebase_config()
    if not config["url"]:
        return {}

    endpoint = f"{config['url']}/statuses.json"
    if config["secret"]:
        endpoint += f"?auth={config['secret']}"

    try:
        req = urllib.request.Request(endpoint, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw_data = resp.read().decode("utf-8")
            if not raw_data or raw_data == "null":
                return {}
            data = json.loads(raw_data)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.error(f"Erro ao buscar status do Firebase: {e}")
    return {}

def push_wake_command(mac: str, device_name: str = "Dispositivo") -> Optional[Dict[str, Any]]:
    config = get_firebase_config()
    if not config["url"]:
        return None

    endpoint = f"{config['url']}/wake_requests.json"
    if config["secret"]:
        endpoint += f"?auth={config['secret']}"

    payload = {
        "mac": mac,
        "device_name": device_name,
        "status": "pending",
        "timestamp": int(time.time()),
        "source": "Vercel/Cloud-UI"
    }

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            logger.info(f"Comando WoL para {mac} enviado ao Firebase: {data}")
            return data
    except Exception as e:
        logger.error(f"Erro ao enviar comando para o Firebase: {e}")
        return None

def process_pending_commands():
    config = get_firebase_config()
    if not config["url"]:
        return

    endpoint = f"{config['url']}/wake_requests.json"
    if config["secret"]:
        endpoint += f"?auth={config['secret']}"

    try:
        req = urllib.request.Request(endpoint, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_data = resp.read().decode("utf-8")
            if not raw_data or raw_data == "null":
                return

            records = json.loads(raw_data)
            if not isinstance(records, dict):
                return

            for req_id, item in records.items():
                if isinstance(item, dict) and item.get("status") == "pending":
                    mac = item.get("mac")
                    device_name = item.get("device_name", "Dispositivo")
                    logger.info(f"⚡ [Firebase Sync] Comando pendente detectado para {device_name} ({mac}). Disparando WoL...")

                    try:
                        wol.send_wake_on_lan(mac)
                        execution_status = "completed"
                    except Exception as err:
                        logger.error(f"Erro ao executar WoL local: {err}")
                        execution_status = f"failed: {str(err)}"

                    patch_endpoint = f"{config['url']}/wake_requests/{req_id}.json"
                    if config["secret"]:
                        patch_endpoint += f"?auth={config['secret']}"

                    patch_payload = {
                        "status": execution_status,
                        "executed_at": int(time.time())
                    }
                    
                    patch_req = urllib.request.Request(
                        patch_endpoint,
                        data=json.dumps(patch_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="PATCH"
                    )
                    urllib.request.urlopen(patch_req, timeout=5)

    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos do Firebase: {e}")

async def start_firebase_listener_loop():
    if os.getenv("VERCEL"):
        return

    while True:
        try:
            if is_firebase_enabled():
                await asyncio.to_thread(process_pending_commands)
                
                cloud_devs = await asyncio.to_thread(fetch_devices_from_firebase)
                if cloud_devs is not None:
                    local_devs = storage.get_devices()
                    merged = storage.merge_devices(local_devs, cloud_devs)
                    if json.dumps(merged, sort_keys=True) != json.dumps(local_devs, sort_keys=True):
                        storage.save_devices(merged)
                        await asyncio.to_thread(sync_devices_to_firebase, merged)
                        
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erro no loop do Firebase Listener: {e}")
            await asyncio.sleep(5)
