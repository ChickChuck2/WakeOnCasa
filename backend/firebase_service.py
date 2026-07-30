import os
import asyncio
import json
import logging
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

from backend import settings, wol, storage

logger = logging.getLogger("wakeoncasa.firebase")

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "testproject-49566")
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

def is_firebase_enabled() -> bool:
    return True

def check_firebase_connection() -> bool:
    """
    Testa a conexão com o Firebase Firestore REST API (testproject-49566).
    """
    url = f"{FIRESTORE_BASE_URL}/wakeoncasa_devices/config"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WakeOnCasa-Check/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as err:
        if err.code in (200, 404):
            return True
        return False
    except Exception:
        return False

def sync_devices_to_firebase(devices: List[Dict[str, Any]]) -> bool:
    """
    Sincroniza a lista completa de dispositivos no Firestore (wakeoncasa_devices/config).
    """
    url = f"{FIRESTORE_BASE_URL}/wakeoncasa_devices/config"
    cleaned = storage.purge_legacy_test_devices(devices)
    
    payload = {
        "fields": {
            "devices_json": {
                "stringValue": json.dumps(cleaned, ensure_ascii=False)
            },
            "updated_at": {
                "integerValue": str(int(time.time()))
            }
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PATCH"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info("Lista de dispositivos sincronizada com sucesso no Firestore.")
            return True
    except Exception as e:
        logger.error(f"Erro ao sincronizar dispositivos no Firestore: {e}")
        return False

def fetch_devices_from_firebase() -> Optional[List[Dict[str, Any]]]:
    """
    Busca a lista de dispositivos compartilhada no Firestore (wakeoncasa_devices/config).
    """
    url = f"{FIRESTORE_BASE_URL}/wakeoncasa_devices/config"
    try:
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            fields = data.get("fields", {})
            dev_json_str = fields.get("devices_json", {}).get("stringValue", "[]")
            raw_list = json.loads(dev_json_str)
            if isinstance(raw_list, list):
                return storage.purge_legacy_test_devices(raw_list)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return []
        logger.error(f"HTTP error ao buscar dispositivos do Firestore: {err}")
    except Exception as e:
        logger.error(f"Erro ao buscar dispositivos do Firestore: {e}")
    return None

def sync_statuses_to_firebase(statuses: Dict[str, Dict[str, Any]]) -> bool:
    """
    CasaOS publica os status dos pings (online/latency) no Firestore (wakeoncasa_statuses/config).
    """
    url = f"{FIRESTORE_BASE_URL}/wakeoncasa_statuses/config"
    payload = {
        "fields": {
            "statuses_json": {
                "stringValue": json.dumps(statuses, ensure_ascii=False)
            },
            "updated_at": {
                "integerValue": str(int(time.time()))
            }
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PATCH"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True
    except Exception as e:
        logger.error(f"Erro ao sincronizar status no Firestore: {e}")
        return False

def fetch_statuses_from_firebase() -> Dict[str, Dict[str, Any]]:
    """
    Vercel busca os status ao vivo gravados pelo CasaOS no Firestore (wakeoncasa_statuses/config).
    """
    url = f"{FIRESTORE_BASE_URL}/wakeoncasa_statuses/config"
    try:
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            fields = data.get("fields", {})
            stat_json_str = fields.get("statuses_json", {}).get("stringValue", "{}")
            raw_dict = json.loads(stat_json_str)
            if isinstance(raw_dict, dict):
                return raw_dict
    except Exception:
        pass
    return {}

def push_wake_command(mac: str, device_name: str = "Dispositivo") -> Optional[Dict[str, Any]]:
    """
    Vercel envia um comando de ligar (WoL) salvando um documento pendente em wakeoncasa_requests.
    """
    url = f"{FIRESTORE_BASE_URL}/wakeoncasa_requests"
    payload = {
        "fields": {
            "mac": { "stringValue": mac },
            "device_name": { "stringValue": device_name },
            "status": { "stringValue": "pending" },
            "timestamp": { "integerValue": str(int(time.time())) },
            "source": { "stringValue": "Vercel/Cloud-UI" }
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            logger.info(f"Comando WoL enviado ao Firestore: {data.get('name')}")
            return data
    except Exception as e:
        logger.error(f"Erro ao enviar comando de WoL para o Firestore: {e}")
        return None

def process_pending_commands():
    """
    CasaOS verifica comandos 'pending' no Firestore, dispara o Magic Packet UDP localmente e atualiza para 'completed'.
    """
    url = f"{FIRESTORE_BASE_URL}/wakeoncasa_requests"
    try:
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            documents = data.get("documents", [])

            for doc in documents:
                doc_name = doc.get("name")
                fields = doc.get("fields", {})
                status = fields.get("status", {}).get("stringValue")

                if status == "pending":
                    mac = fields.get("mac", {}).get("stringValue", "")
                    dev_name = fields.get("device_name", {}).get("stringValue", "Dispositivo")
                    
                    logger.info(f"⚡ [Firestore Sync] Comando pendente detectado para {dev_name} ({mac}). Disparando WoL...")

                    try:
                        wol.send_wake_on_lan(mac)
                        exec_status = "completed"
                    except Exception as err:
                        logger.error(f"Erro ao executar WoL local: {err}")
                        exec_status = f"failed: {str(err)}"

                    patch_payload = {
                        "fields": {
                            "status": { "stringValue": exec_status },
                            "executed_at": { "integerValue": str(int(time.time())) }
                        }
                    }

                    patch_req = urllib.request.Request(
                        f"https://firestore.googleapis.com/v1/{doc_name}?updateMask.fieldPaths=status&updateMask.fieldPaths=executed_at",
                        data=json.dumps(patch_payload, ensure_ascii=False).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="PATCH"
                    )
                    urllib.request.urlopen(patch_req, timeout=5)

    except Exception as e:
        pass

async def start_firebase_listener_loop():
    if os.getenv("VERCEL"):
        return

    while True:
        try:
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
