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

def send_wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255", ports: list = [9, 7]) -> dict:
    """
    Envia o Magic Packet via broadcast UDP para o MAC informado.
    """
    mac_bytes = clean_mac(mac_address)
    packet = create_magic_packet(mac_bytes)
    
    sent_ports = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for port in ports:
            sock.sendto(packet, (broadcast_ip, port))
            sent_ports.append(port)
            
    return {
        "success": True,
        "mac": mac_address,
        "broadcast_ip": broadcast_ip,
        "ports": sent_ports
    }
