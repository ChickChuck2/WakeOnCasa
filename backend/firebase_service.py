import os
import asyncio
import json
import logging
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional

from backend import settings, wol

logger = logging.getLogger("wakeoncasa.firebase")

def get_firebase_config() -> Dict[str, str]:
    """
    Obtém as credenciais do Firebase Realtime Database das configurações ou variáveis de ambiente.
    """
    cfg = settings.get_settings()
    db_url = cfg.get("firebase_database_url", "").strip() or os.getenv("FIREBASE_DATABASE_URL", "").strip()
    auth_secret = cfg.get("firebase_auth_secret", "").strip() or os.getenv("FIREBASE_AUTH_SECRET", "").strip()
    
    # Remove barra final se presente
    if db_url.endswith("/"):
        db_url = db_url[:-1]
        
    return {
        "url": db_url,
        "secret": auth_secret
    }

def is_firebase_enabled() -> bool:
    config = get_firebase_config()
    return bool(config["url"])

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

                    # 1. Executa o disparo do Magic Packet localmente no CasaOS
                    try:
                        wol.send_wake_on_lan(mac)
                        execution_status = "completed"
                    except Exception as err:
                        logger.error(f"Erro ao executar WoL local: {err}")
                        execution_status = f"failed: {str(err)}"

                    # 2. Atualiza o status no Firebase para "completed"
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
    """
    Loop em background rodando no CasaOS para monitorar comandos do Firebase a cada 2 segundos.
    """
    import os
    # Não roda o listener se estiver no ambiente Serverless da Vercel
    if os.getenv("VERCEL"):
        return

    while True:
        try:
            if is_firebase_enabled():
                await asyncio.to_thread(process_pending_commands)
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erro no loop do Firebase Listener: {e}")
            await asyncio.sleep(5)
