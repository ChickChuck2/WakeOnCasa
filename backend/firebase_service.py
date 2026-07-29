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

def get_firebase_config() -> Dict[str, str]:
    cfg = settings.get_settings()
    db_url = cfg.get("firebase_database_url", "").strip() or os.getenv("FIREBASE_DATABASE_URL", "").strip()
    auth_secret = cfg.get("firebase_auth_secret", "").strip() or os.getenv("FIREBASE_AUTH_SECRET", "").strip()
    
    if db_url.endswith("/"):
        db_url = db_url[:-1]
        
    return {
        "url": db_url,
        "secret": auth_secret
    }

def is_firebase_enabled() -> bool:
    config = get_firebase_config()
    return bool(config["url"])

def check_firebase_connection() -> bool:
    """
    Testa se o Firebase Realtime Database está acessível.
    """
    config = get_firebase_config()
    if not config["url"]:
        return False
    
    endpoint = f"{config['url']}/.json?shallow=true"
    if config["secret"]:
        endpoint += f"&auth={config['secret']}"

    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "WakeOnCasa-Check/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.status == 200
    except Exception:
        return False

def sync_devices_to_firebase(devices: List[Dict[str, Any]]) -> bool:
    """
    Sincroniza a lista inteira de dispositivos no Firebase (/devices.json).
    """
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
    """
    Busca a lista de dispositivos compartilhada no Firebase (/devices.json).
    """
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

def push_wake_command(mac: str, device_name: str = "Dispositivo") -> Optional[Dict[str, Any]]:
    """
    Disparado pela Vercel/UI: Escreve um comando de "pending" no Firebase Realtime Database.
    """
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
    """
    Disparado no servidor CasaOS local: Verifica comandos "pending" no Firebase,
    executa o Magic Packet UDP localmente e marca como "completed".
    """
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
                # 1. Processa comandos pendentes
                await asyncio.to_thread(process_pending_commands)
                
                # 2. Sincroniza dispositivos da nuvem se disponíveis
                cloud_devs = await asyncio.to_thread(fetch_devices_from_firebase)
                if cloud_devs is not None:
                    local_devs = storage.get_devices()
                    if json.dumps(cloud_devs, sort_keys=True) != json.dumps(local_devs, sort_keys=True):
                        storage.save_devices(cloud_devs)
                        
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erro no loop do Firebase Listener: {e}")
            await asyncio.sleep(5)
