import os
import re
import socket
import subprocess
import time
import uuid
import platform
from typing import Dict, Any, Optional, Tuple, Set

def get_host_interfaces() -> Tuple[Set[str], Set[str]]:
    """
    Retorna (host_ips, host_macs) contendo todos os IPs e MACs do próprio servidor local (Host).
    """
    host_ips = {"127.0.0.1", "localhost"}
    host_macs = set()

    # 1. IPs locais resolvidos via Hostname
    try:
        _, _, ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in ips:
            if ip and not ip.startswith("127."):
                host_ips.add(ip)
    except Exception:
        pass

    # 2. MAC do node
    try:
        node_mac = f"{uuid.getnode():012X}".upper()
        if node_mac != "000000000000":
            host_macs.add(node_mac)
            host_macs.add(":".join(node_mac[i:i+2] for i in range(0, 12, 2)))
    except Exception:
        pass

    # 3. Interfaces de rede físicas do Linux (/sys/class/net/*/address)
    if os.path.exists("/sys/class/net"):
        try:
            for net_dev in os.listdir("/sys/class/net"):
                addr_file = os.path.join("/sys/class/net", net_dev, "address")
                if os.path.exists(addr_file):
                    with open(addr_file, "r") as f:
                        mac_str = f.read().strip().upper()
                        if mac_str and mac_str != "00:00:00:00:00:00":
                            host_macs.add(mac_str)
                            clean_mac = re.sub(r'[^A-F0-9]', '', mac_str)
                            host_macs.add(clean_mac)
        except Exception:
            pass

    return host_ips, host_macs

def get_arp_table() -> Dict[str, str]:
    """
    Lê a tabela ARP do sistema (/proc/net/arp no Linux ou `arp -a` no Windows)
    e retorna um mapeamento {mac_normalizado: ip_address}.
    """
    arp_map = {}
    
    if os.path.exists("/proc/net/arp"):
        try:
            with open("/proc/net/arp", "r", encoding="utf-8") as f:
                lines = f.readlines()[1:]
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        ip = parts[0]
                        flags = parts[2]
                        mac = parts[3].upper()
                        if flags != "0x0" and mac != "00:00:00:00:00:00":
                            arp_map[mac] = ip
                            clean_mac = re.sub(r'[^A-F0-9]', '', mac)
                            arp_map[clean_mac] = ip
            return arp_map
        except Exception:
            pass

    try:
        cmd = ["arp", "-a"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
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
    Verificação de status inteligente em 4 estágios:
    0. Detecção do Próprio Servidor Host (se o MAC ou IP pertence ao servidor que está rodando a aplicação)
    1. Ping ICMP do sistema operacional (ping -c 1 / ping -n 1)
    2. Teste de portas TCP comuns de rede (135, 139, 445, 3389, 80, 443, 22, 8080, 53)
    3. Tabela ARP do sistema local (detecta dispositivos ativos na LAN)
    """
    start_time = time.time()
    clean_ip = (ip or "").strip()
    clean_mac = re.sub(r'[^A-F0-9]', '', (mac or "").upper())
    formatted_mac = ":".join(clean_mac[i:i+2] for i in range(0, 12, 2)) if len(clean_mac) == 12 else (mac or "").upper()

    # 0. Checa se o dispositivo é o Próprio Servidor Host (CasaOS/Linux local)
    host_ips, host_macs = get_host_interfaces()
    if (clean_ip and clean_ip in host_ips) or (clean_mac and clean_mac in host_macs) or (formatted_mac in host_macs):
        main_host_ip = clean_ip if clean_ip else [i for i in host_ips if not i.startswith("127.")][:1]
        resolved_host_ip = main_host_ip[0] if isinstance(main_host_ip, list) and main_host_ip else "127.0.0.1"
        return {
            "online": True,
            "latency_ms": 0.1,
            "method": "local_host_server",
            "resolved_ip": resolved_host_ip
        }

    # Resolve IP via tabela ARP local se o IP foi deixado em branco (N/A)
    arp_table = get_arp_table()
    resolved_ip = arp_table.get(clean_mac) or arp_table.get(formatted_mac)
    target_ip = clean_ip if (clean_ip and clean_ip != "0.0.0.0") else resolved_ip

    if not target_ip:
        return {"online": False, "latency_ms": None, "method": "no_ip"}

    # 1. Tenta Ping ICMP Nativo
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

    # 2. Tenta Conexão TCP em portas comuns
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

    # 3. Tenta Tabela ARP
    if target_ip in arp_table.values() or clean_mac in arp_table or formatted_mac in arp_table:
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
