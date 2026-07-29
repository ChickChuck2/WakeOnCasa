import asyncio
import json
import logging
import urllib.request
from typing import Dict, Any, Set
from backend import storage, settings
from backend.ping import check_device_status

logger = logging.getLogger("wakeoncasa.ping_service")

# Cache global de status dos dispositivos {device_id: status_dict}
device_status_cache: Dict[str, Dict[str, Any]] = {}

# Conjunto de filas de clientes conectados via SSE
sse_subscribers: Set[asyncio.Queue] = set()

def send_webhook_notification(device: Dict[str, Any], new_status: Dict[str, Any]):
    """
    Envia uma notificação Webhook (Discord / Generic) quando o status do dispositivo muda.
    """
    config = settings.get_settings()
    webhook_url = config.get("webhook_url", "").strip()
    if not webhook_url:
        return

    is_online = new_status.get("online", False)
    if is_online and not config.get("notify_online", True):
        return
    if not is_online and not config.get("notify_offline", True):
        return

    status_str = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
    color = 65280 if is_online else 16711680  # Verde / Vermelho em Hex decimal para Discord

    payload = {
        "embeds": [{
            "title": f"Dispositivo {status_str}: {device.get('name')}",
            "description": f"O dispositivo **{device.get('name')}** ({device.get('ip')}) mudou de estado para **{status_str}**.",
            "color": color,
            "fields": [
                {"name": "IP", "value": device.get("ip", "N/A"), "inline": True},
                {"name": "MAC", "value": device.get("mac", "N/A"), "inline": True},
                {"name": "Latência", "value": f"{new_status.get('latency_ms')} ms" if is_online else "N/A", "inline": True}
            ],
            "footer": {"text": "WakeOnCasa • CasaOS Energy & Network"}
        }]
    }

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "WakeOnCasa-Bot/1.0"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.error(f"Erro ao enviar webhook: {e}")

async def notify_sse_subscribers(event_data: Dict[str, Any]):
    """
    Transmite um evento SSE para todas as conexões ativas.
    """
    if not sse_subscribers:
        return
    
    formatted_data = f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
    for queue in list(sse_subscribers):
        try:
            await queue.put(formatted_data)
        except Exception:
            sse_subscribers.discard(queue)

async def run_ping_cycle():
    """
    Executa uma rodada de verificação de ping em todos os dispositivos cadastrados.
    """
    devices = storage.get_devices()
    if not devices:
        return

    tasks = [asyncio.to_thread(check_device_status, dev["ip"]) for dev in devices]
    results = await asyncio.gather(*tasks)

    changed_events = []

    for dev, new_status in zip(devices, results):
        dev_id = dev["id"]
        old_status = device_status_cache.get(dev_id)
        
        # Atualiza cache
        device_status_cache[dev_id] = new_status

        # Verifica mudança de estado
        if old_status is not None and old_status.get("online") != new_status.get("online"):
            changed_events.append({
                "type": "status_changed",
                "device_id": dev_id,
                "device": dev,
                "old_status": old_status,
                "new_status": new_status
            })
            # Dispara webhook assincronamente em thread
            asyncio.to_thread(send_webhook_notification, dev, new_status)

    # Notifica via SSE se houver atualizações de status
    await notify_sse_subscribers({
        "type": "ping_update",
        "statuses": device_status_cache,
        "changes": changed_events
    })

async def start_ping_loop():
    """
    Loop de background executado continuamente enquanto o aplicativo estiver rodando.
    """
    while True:
        try:
            cfg = settings.get_settings()
            interval = max(5, int(cfg.get("ping_interval_seconds", 10)))
            await run_ping_cycle()
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erro no loop de ping em background: {e}")
            await asyncio.sleep(10)
