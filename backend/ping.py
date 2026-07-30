import os
import re
import socket
import subprocess
import time
import platform
from typing import Dict, Any, Optional

def get_arp_table() -> Dict[str, str]:
    """
    Lê a tabela ARP do sistema (/proc/net/arp no Linux ou `arp -a` no Windows)
    e retorna um mapeamento {mac_normalizado: ip_address}.
    """
    arp_map = {}
    
    # 1. Tenta /proc/net/arp no Linux
    if os.path.exists("/proc/net/arp"):
        try:
            with open("/proc/net/arp", "r", encoding="utf-8") as f:
                lines = f.readlines()[1:] # Pula o cabeçalho
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        ip = parts[0]
                        flags = parts[2]
                        mac = parts[3].upper()
                        if flags != "0x0" and mac != "00:00:00:00:00:00":
                            arp_map[mac] = ip
                            # Normaliza MAC sem dois pontos também
                            clean_mac = re.sub(r'[^A-F0-9]', '', mac)
                            arp_map[clean_mac] = ip
            return arp_map
        except Exception:
            pass

    # 2. Fallback de comando `arp -a`
    try:
        cmd = ["arp", "-a"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    ip_match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', line)
                    mac_match = re.search(r'([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})', line)
                    if ip_match and mac_match:
                        ip = ip_match.group(0)
                        mac = mac_match.group(0).upper().replace("-", ":")
                        arp_map[mac] = ip
                        clean_mac = re.sub(r'[^A-F0-9]', '', mac)
                        arp_map[clean_mac] = ip
    except Exception:
        pass

    return arp_map

def check_device_status(ip: str, mac: str = "", timeout: float = 1.2) -> Dict[str, Any]:
    """
    Verificação de status em 3 estágios:
    1. Ping ICMP do sistema operacional (ping -c 1 / ping -n 1)
    2. Teste de portas TCP comuns de rede (135, 139, 445, 3389, 80, 443, 22, 8080, 53)
    3. Tabela ARP do sistema local (detecta dispositivos ativos na LAN mesmo com firewall ICMP bloqueado)
    """
    start_time = time.time()
    clean_ip = (ip or "").strip()
    clean_mac = re.sub(r'[^A-F0-9]', '', (mac or "").upper())
    
    # Se o IP não foi informado mas o MAC está na tabela ARP local, resolve o IP automaticamente!
    arp_table = get_arp_table()
    resolved_ip = arp_table.get(clean_mac) or arp_table.get(mac.upper())
    
    target_ip = clean_ip if (clean_ip and clean_ip != "0.0.0.0") else resolved_ip

    if not target_ip:
        return {"online": False, "latency_ms": None, "method": "no_ip"}

    # 1. Tenta Ping ICMP Nativo do Sistema Operacional
    try:
        is_win = platform.system() == "Windows"
        cmd = ["ping", "-n", "1", "-w", "1000", target_ip] if is_win else ["ping", "-c", "1", "-W", "1", target_ip]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
        if res.returncode == 0:
            elapsed = (time.time() - start_time) * 1000
            return {
                "online": True,
                "latency_ms": round(max(0.5, elapsed), 1),
                "method": "icmp_ping",
                "resolved_ip": target_ip
            }
    except Exception:
        pass

    # 2. Tenta Conexão TCP em portas de serviços de rede comuns
    common_ports = [135, 445, 139, 3389, 80, 443, 22, 8080, 53]
    for port in common_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.15)
            res_code = s.connect_ex((target_ip, port))
            s.close()
            if res_code == 0:
                elapsed = (time.time() - start_time) * 1000
                return {
                    "online": True,
                    "latency_ms": round(max(0.5, elapsed), 1),
                    "method": f"tcp_port_{port}",
                    "resolved_ip": target_ip
                }
        except Exception:
            pass

    # 3. Tenta checagem na Tabela ARP (se o dispositivo respondeu ARP recentemente no roteador)
    if target_ip in arp_table.values() or clean_mac in arp_table or mac.upper() in arp_table:
        elapsed = (time.time() - start_time) * 1000
        return {
            "online": True,
            "latency_ms": round(max(0.5, elapsed), 1),
            "method": "arp_cache",
            "resolved_ip": target_ip
        }

    return {
        "online": False,
        "latency_ms": None,
        "method": "unreachable"
    }
