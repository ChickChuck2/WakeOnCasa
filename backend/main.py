import os
import asyncio
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List

from backend.wol import send_wake_on_lan
from backend.ping import check_device_status
from backend import storage

app = FastAPI(
    title="WakeOnCasa API",
    description="API de Wake-on-LAN e monitoramento de dispositivos para CasaOS",
    version="1.0.0"
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

class DeviceSchema(BaseModel):
    name: str = Field(..., example="PC Gamer")
    ip: str = Field(..., example="192.168.1.100")
    mac: str = Field(..., example="AA:BB:CC:11:22:33")
    category: Optional[str] = Field("desktop", example="desktop")
    notes: Optional[str] = Field("", example="Quarto principal")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "WakeOnCasa", "version": "1.0.0"}

@app.get("/api/devices")
def list_devices():
    devices = storage.get_devices()
    return {"devices": devices}

@app.post("/api/devices")
def create_device(device: DeviceSchema):
    created = storage.add_device(device.model_dump())
    return {"message": "Dispositivo adicionado com sucesso", "device": created}

@app.get("/api/devices/{device_id}")
def get_device(device_id: str):
    dev = storage.get_device_by_id(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    return dev

@app.put("/api/devices/{device_id}")
def update_device(device_id: str, device: DeviceSchema):
    updated = storage.update_device(device_id, device.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    return {"message": "Dispositivo atualizado com sucesso", "device": updated}

@app.delete("/api/devices/{device_id}")
def delete_device(device_id: str):
    success = storage.delete_device(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    return {"message": "Dispositivo removido com sucesso"}

@app.post("/api/wake/{device_id}")
def wake_device(device_id: str):
    dev = storage.get_device_by_id(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    
    try:
        result = send_wake_on_lan(dev["mac"])
        return {
            "message": f"Sinal Wake-on-LAN enviado para {dev['name']} ({dev['mac']})",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar sinal WoL: {str(e)}")

@app.get("/api/ping/{device_id}")
def ping_device(device_id: str):
    dev = storage.get_device_by_id(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    
    status = check_device_status(dev["ip"])
    return {
        "device_id": device_id,
        "name": dev["name"],
        "ip": dev["ip"],
        "status": status
    }

@app.get("/api/ping-all")
async def ping_all_devices():
    devices = storage.get_devices()
    tasks = [asyncio.to_thread(check_device_status, dev["ip"]) for dev in devices]
    results = await asyncio.gather(*tasks)
    
    status_map = {}
    for dev, status in zip(devices, results):
        status_map[dev["id"]] = status
        
    return {"statuses": status_map}

# Servidor de arquivos estáticos da Dashboard Frontend
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def serve_dashboard():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
