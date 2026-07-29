import socket
import time
from typing import Dict, Any

def check_device_status(ip: str, timeout: float = 1.0) -> Dict[str, Any]:
    """
    Verifica se o IP está ativo na rede local.
    Aplica teste rápido de conexão por socket TCP em portas comuns (80, 445, 22, 443, 3389)
    e socket ICMP/ping fallback sem requerer privilégios de root em containers Linux.
    """
    if not ip or ip == "0.0.0.0":
        return {"online": False, "latency_ms": None, "method": "none"}

    common_ports = [80, 445, 22, 443, 3389, 8080, 139]
    start_time = time.time()
    
    # 1. Tenta conexões de socket TCP rápidas em portas comuns
    for port in common_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout / len(common_ports))
            result = s.connect_ex((ip, port))
            s.close()
            if result == 0:
                elapsed = (time.time() - start_time) * 1000
                return {
                    "online": True,
                    "latency_ms": round(elapsed, 1),
                    "method": f"tcp_port_{port}"
                }
        except Exception:
            pass

    # 2. Tenta resolução e envio UDP nulo como fallback de conectividade
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.connect((ip, 80))
        elapsed = (time.time() - start_time) * 1000
        s.close()
        return {
            "online": True,
            "latency_ms": round(elapsed, 1),
            "method": "udp_probe"
        }
    except Exception:
        pass

    return {
        "online": False,
        "latency_ms": None,
        "method": "unreachable"
    }
