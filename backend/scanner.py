import asyncio
import socket
import re
import platform
import subprocess
from typing import List, Dict, Any

from backend.ping import check_device_status
from backend import storage

def get_local_ip_and_subnet() -> str:
    """
    Tenta descobrir o IP local e a subnet base (ex: 192.168.1).
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}"
    except Exception:
        pass
    return "192.168.1"

def get_mac_from_arp_table(ip: str) -> str:
    """
    Busca o endereço MAC associado ao IP na tabela ARP do sistema (Linux/Windows).
    """
    try:
        # Tenta ler /proc/net/arp no Linux se disponível
        if platform.system().lower() == "linux":
            try:
                with open("/proc/net/arp", "r") as f:
                    for line in f.readlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 4 and parts[0] == ip:
                            mac = parts[3].upper()
                            if mac != "00:00:00:00:00:00":
                                return mac
            except Exception:
                pass

        # Fallback executando o comando 'arp -a'
        cmd = ["arp", "-a", ip] if platform.system().lower() == "windows" else ["arp", "-n", ip]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=2)
        mac_match = re.search(r'([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})', output)
        if mac_match:
            return mac_match.group(1).upper().replace("-", ":")
    except Exception:
        pass
    return "DESCONHECIDO"

def resolve_hostname(ip: str) -> str:
    """
    Tenta resolver o nome do host (Reverse DNS / NetBIOS).
    """
    try:
        host = socket.gethostbyaddr(ip)[0]
        return host.split(".")[0]
    except Exception:
        return f"Dispositivo {ip.split('.')[-1]}"

async def scan_single_ip(ip: str) -> Dict[str, Any]:
    """
    Testa a conectividade de um IP único e recupera o MAC.
    """
    status = await asyncio.to_thread(check_device_status, ip, 0.4)
    if status.get("online"):
        mac = await asyncio.to_thread(get_mac_from_arp_table, ip)
        hostname = await asyncio.to_thread(resolve_hostname, ip)
        return {
            "ip": ip,
            "mac": mac,
            "name": hostname,
            "online": True,
            "latency_ms": status.get("latency_ms")
        }
    return None

async def scan_network(subnet_base: str = None) -> List[Dict[str, Any]]:
    """
    Realiza uma varredura paralela na faixa de IPs 1 a 254 da subnet local.
    """
    if not subnet_base:
        subnet_base = get_local_ip_and_subnet()

    # Gera lista de IPs 1..254
    ip_list = [f"{subnet_base}.{i}" for i in range(1, 255)]
    
    tasks = [scan_single_ip(ip) for ip in ip_list]
    results = await asyncio.gather(*tasks)

    # Filtra apenas os dispositivos ativos encontrados
    active_discovered = [res for res in results if res is not None]

    # Marca quais já estão cadastrados no banco de dados local
    existing_devices = storage.get_devices()
    existing_macs = {d["mac"].upper() for d in existing_devices}
    existing_ips = {d["ip"] for d in existing_devices}

    for item in active_discovered:
        item["already_added"] = (item["mac"] in existing_macs or item["ip"] in existing_ips)

    return active_discovered
