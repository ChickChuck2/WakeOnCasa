import subprocess
import platform
import logging
from typing import Dict, Any

logger = logging.getLogger("wakeoncasa.remote_cmd")

def execute_remote_shutdown(ip: str, method: str = "auto") -> Dict[str, Any]:
    """
    Envia comando de desligamento remoto para uma máquina Windows / Linux via RPC, SSH ou HTTP Webhook.
    """
    if not ip:
        return {"success": False, "message": "Endereço IP inválido."}

    # Tenta desligamento via RPC Windows 'shutdown' se estiver rodando no Windows
    if platform.system().lower() == "windows":
        try:
            cmd = ["shutdown", "/m", f"\\\\{ip}", "/s", "/t", "0", "/f"]
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=5)
            return {"success": True, "message": f"Sinal de desligamento enviado para {ip}", "output": output}
        except Exception as e:
            logger.warning(f"Shutdown RPC no Windows falhou para {ip}: {e}")

    return {
        "success": False,
        "message": f"Não foi possível enviar desligamento remoto direto para {ip}. Requer SSH/WinRM configurado."
    }
