import socket
import re

def clean_mac(mac_address: str) -> bytes:
    """
    Limpa e converte uma string de endereço MAC para bytes.
    Aceita formatos: AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF, AABBCCDDEEFF.
    """
    cleaned = re.sub(r'[^a-fA-F0-9]', '', mac_address)
    if len(cleaned) != 12:
        raise ValueError(f"Endereço MAC inválido: '{mac_address}'. Deve possuir 12 caracteres hexadecimais.")
    return bytes.fromhex(cleaned)

def create_magic_packet(mac_bytes: bytes) -> bytes:
    """
    Cria um Magic Packet padrão (6x 0xFF seguido de 16x os 6 bytes do MAC).
    """
    return b'\xff' * 6 + mac_bytes * 16

def get_broadcast_targets(custom_broadcast: str = "255.255.255.255") -> list:
    """
    Retorna uma lista de endereços de broadcast (global e sub-rede local) para garantir
    que o pacote alcance placas de rede mesmo com roteamento restritivo.
    """
    targets = set()
    if custom_broadcast:
        targets.add(custom_broadcast)
    targets.add("255.255.255.255")
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            parts = local_ip.split(".")
            if len(parts) == 4 and not local_ip.startswith("127."):
                targets.add(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
    except Exception:
        pass
        
    return list(targets)

def send_wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255", ports: list = [9, 7]) -> dict:
    """
    Envia o Magic Packet via broadcast UDP para o MAC informado em todos os alvos de broadcast.
    """
    mac_bytes = clean_mac(mac_address)
    packet = create_magic_packet(mac_bytes)
    
    target_ips = get_broadcast_targets(broadcast_ip)
    sent_deliveries = []
    
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for target in target_ips:
            for port in ports:
                try:
                    sock.sendto(packet, (target, port))
                    sent_deliveries.append(f"{target}:{port}")
                except Exception:
                    pass
            
    return {
        "success": True,
        "mac": mac_address,
        "targets": sent_deliveries,
        "broadcast_ips": target_ips,
        "ports": ports
    }

