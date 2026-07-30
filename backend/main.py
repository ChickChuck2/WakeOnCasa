import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from backend.wol import send_wake_on_lan
from backend.ping import check_device_status
from backend import storage, settings, ping_service, firebase_service, scanner, remote_cmd

IS_VERCEL = bool(os.getenv("VERCEL"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    if IS_VERCEL:
        yield
        return

    ping_task = asyncio.create_task(ping_service.start_ping_loop())
    firebase_task = asyncio.create_task(firebase_service.start_firebase_listener_loop())
    yield
    ping_task.cancel()
    firebase_task.cancel()
    try:
        await asyncio.gather(ping_task, firebase_task, return_exceptions=True)
    except Exception:
        pass

app = FastAPI(
    title="WakeOnCasa API",
    description="API de Wake-on-LAN, Varredura de Rede e Sincronização Nuvem para CasaOS & Vercel",
    version="1.5.0",
    lifespan=lifespan
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

class DeviceSchema(BaseModel):
    name: str = Field(..., example="PC Gamer")
    ip: Optional[str] = Field("", example="192.168.1.100")
    mac: str = Field(..., example="AA:BB:CC:11:22:33")
    category: Optional[str] = Field("desktop", example="desktop")
    notes: Optional[str] = Field("", example="Quarto principal")

class SettingsSchema(BaseModel):
    ping_interval_seconds: int = Field(10, ge=5, le=300)
    webhook_url: Optional[str] = Field("")
    remote_agent_url: Optional[str] = Field("")
    firebase_database_url: Optional[str] = Field("")
    firebase_auth_secret: Optional[str] = Field("")
    notify_online: bool = Field(True)
    notify_offline: bool = Field(True)

@app.get("/api/health")
def health_check():
    fb_connected = firebase_service.check_firebase_connection() if firebase_service.is_firebase_enabled() else False
    return {
        "status": "ok",
        "app": "WakeOnCasa",
        "version": "1.5.0",
        "environment": "vercel" if IS_VERCEL else "casaos",
        "firebase_enabled": firebase_service.is_firebase_enabled(),
        "firebase_connected": fb_connected
    }

@app.get("/api/devices")
def list_devices():
    local_devs = storage.get_devices()
    if firebase_service.is_firebase_enabled():
        cloud_devs = firebase_service.fetch_devices_from_firebase()
        if cloud_devs is not None:
            if not cloud_devs and local_devs:
                firebase_service.sync_devices_to_firebase(local_devs)
                devices = local_devs
            else:
                merged = storage.merge_devices(local_devs, cloud_devs)
                storage.save_devices(merged)
                devices = merged
        else:
            devices = local_devs
    else:
        devices = local_devs

    cloud_statuses = {}
    if IS_VERCEL and firebase_service.is_firebase_enabled():
        cloud_statuses = firebase_service.fetch_statuses_from_firebase()

    for dev in devices:
        dev_id = dev["id"]
        if dev_id in ping_service.device_status_cache:
            dev["status"] = ping_service.device_status_cache[dev_id]
        elif dev_id in cloud_statuses:
            dev["status"] = cloud_statuses[dev_id]
        else:
            dev["status"] = {"online": False, "latency_ms": None}

        # Se o IP estava em branco mas o detector resolveu o IP, preenche automaticamente na exibição!
        if not dev.get("ip") and dev.get("status", {}).get("resolved_ip"):
            dev["ip"] = dev["status"]["resolved_ip"]
            
    return {"devices": devices}

def find_device_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    dev = storage.get_device_by_id(device_id)
    if dev:
        return dev
    devices_data = list_devices()
    for d in devices_data.get("devices", []):
        if d.get("id") == device_id:
            return d
    return None

@app.post("/api/devices")
def create_device(device: DeviceSchema):
    dev_dict = device.model_dump()
    if not dev_dict.get("ip"):
        resolved_status = check_device_status("", dev_dict.get("mac", ""))
        if resolved_status.get("resolved_ip"):
            dev_dict["ip"] = resolved_status["resolved_ip"]

    created = storage.add_device(dev_dict)
    if firebase_service.is_firebase_enabled():
        firebase_service.sync_devices_to_firebase(storage.get_devices())
    return {"message": "Dispositivo adicionado com sucesso", "device": created}

@app.get("/api/devices/{device_id}")
def get_device(device_id: str):
    dev = find_device_by_id(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    dev["status"] = ping_service.device_status_cache.get(device_id, {"online": False, "latency_ms": None})
    return dev

@app.put("/api/devices/{device_id}")
def update_device(device_id: str, device: DeviceSchema):
    dev_dict = device.model_dump()
    if not dev_dict.get("ip"):
        resolved_status = check_device_status("", dev_dict.get("mac", ""))
        if resolved_status.get("resolved_ip"):
            dev_dict["ip"] = resolved_status["resolved_ip"]

    updated = storage.update_device(device_id, dev_dict)
    if firebase_service.is_firebase_enabled():
        firebase_service.sync_devices_to_firebase(storage.get_devices())
    return {"message": "Dispositivo atualizado com sucesso", "device": updated or dev_dict}

@app.delete("/api/devices/{device_id}")
def delete_device(device_id: str):
    storage.delete_device(device_id)
    if firebase_service.is_firebase_enabled():
        firebase_service.sync_devices_to_firebase(storage.get_devices())
    return {"message": "Dispositivo removido com sucesso"}

@app.post("/api/wake/{device_id}")
def wake_device(device_id: str):
    dev = find_device_by_id(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    
    if IS_VERCEL or firebase_service.is_firebase_enabled():
        fb_result = firebase_service.push_wake_command(dev["mac"], dev["name"])
        return {
            "message": f"Sinal Wake-on-LAN enviado via Firebase Sync para {dev['name']} ({dev['mac']})",
            "firebase": fb_result or True
        }

    try:
        result = send_wake_on_lan(dev["mac"])
        return {
            "message": f"Sinal Wake-on-LAN enviado localmente para {dev['name']} ({dev['mac']})",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar sinal WoL: {str(e)}")

@app.post("/api/shutdown/{device_id}")
def shutdown_device(device_id: str):
    dev = find_device_by_id(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    
    target_ip = dev.get("ip", "").strip()
    if not target_ip:
        status_res = check_device_status("", dev.get("mac", ""))
        target_ip = status_res.get("resolved_ip", "")

    if not target_ip:
        return {"success": False, "message": f"Não foi possível identificar o IP do dispositivo {dev['name']}. Adicione o IP no cadastro."}

    res = remote_cmd.execute_remote_shutdown(target_ip)
    return res

@app.get("/api/scan-network")
async def scan_network_devices(subnet: Optional[str] = Query(None, description="Subnet IP ex: 192.168.1")):
    discovered = await scanner.scan_network(subnet)
    return {"discovered": discovered}

@app.get("/api/ping/{device_id}")
def ping_device(device_id: str):
    dev = find_device_by_id(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    
    status = check_device_status(dev.get("ip", ""), dev.get("mac", ""))
    ping_service.device_status_cache[device_id] = status
    if firebase_service.is_firebase_enabled():
        firebase_service.sync_statuses_to_firebase(ping_service.device_status_cache)
    return {
        "device_id": device_id,
        "name": dev["name"],
        "ip": dev["ip"],
        "status": status
    }

@app.get("/api/ping-all")
async def ping_all_devices():
    await ping_service.run_ping_cycle()
    return {"statuses": ping_service.device_status_cache}

@app.get("/api/settings")
def get_app_settings():
    return settings.get_settings()

@app.put("/api/settings")
def update_app_settings(config: SettingsSchema):
    updated = settings.update_settings(config.model_dump())
    return {"message": "Configurações salvas com sucesso", "settings": updated}

@app.get("/api/stream-status")
async def stream_status():
    queue: asyncio.Queue = asyncio.Queue()
    ping_service.sse_subscribers.add(queue)

    async def event_generator():
        initial_payload = {
            "type": "ping_update",
            "statuses": ping_service.device_status_cache
        }
        yield f"data: {json.dumps(initial_payload, ensure_ascii=False)}\n\n"
        
        try:
            while True:
                data = await queue.get()
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            ping_service.sse_subscribers.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def serve_dashboard():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
