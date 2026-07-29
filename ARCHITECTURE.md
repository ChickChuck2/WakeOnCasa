# WakeOnCasa - Especificação de Arquitetura Técnica

Este documento apresenta a arquitetura de software, estrutura de diretórios, API REST e modelo de empacotamento em container para a aplicação **WakeOnCasa**.

---

## 🏗️ Visão Geral da Arquitetura

O WakeOnCasa é construído usando uma arquitetura modular em Python (FastAPI) servindo uma interface web responsiva e integrada ao ecossistema do **CasaOS**.

```mermaid
graph TD
    User["💻 Usuário / Navegador / CasaOS UI"] -->|HTTP / REST API| WebUI["🎨 Dashboard Frontend (CasaOS Glass UI)"]
    WebUI -->|POST /api/wake/{id}| Backend["⚙️ Backend FastAPI (Python)"]
    WebUI -->|GET /api/devices| Backend
    Backend -->|UDP Broadcast :7 / :9| Network["🌐 Rede Local (Subnet LAN)"]
    Network -->|Magic Packet| TargetPC["🖥️ Computador Alvo (WoL habilitado)"]
    Backend -->|ICMP Ping| TargetPC
    Backend -->|Leitura / Escrita| Storage["📁 Volume Persistent (/app/data/devices.json)"]
```

---

## 📂 Estrutura de Diretórios

```
WakeOnCasa/
├── backend/
│   ├── main.py              # Aplicação FastAPI e rotas da API
│   ├── wol.py               # Engine de envio de Magic Packet UDP
│   ├── ping.py              # Monitor de status de rede (ICMP/TCP)
│   └── storage.py           # Gerenciador de armazenamento em JSON
├── static/
│   ├── css/
│   │   └── style.css        # CSS Glassmorphism no padrão CasaOS
│   ├── js/
│   │   └── app.js           # Lógica interativa do painel frontend
│   └── index.html           # Dashboard HTML5 responsivo
├── data/
│   └── devices.json         # Banco de dados em JSON (mapeado via volume)
├── Dockerfile               # Dockerfile de produção em Python
├── docker-compose.yml       # Especificação com bloco x-casaos e labels
├── copiar-servidor.bat      # Script Robocopy para sincronizar com o servidor
├── infos.md                 # Especificações do ambiente de deploy
├── resumo.md                # Resumo executivo do projeto
├── ROADMAP.md               # Roadmap detalhado de fases
└── ARCHITECTURE.md          # Este documento de arquitetura
```

---

## 📡 Especificação da API REST

| Método | Endpoint | Descrição | Payload Exemplo |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/devices` | Lista todos os dispositivos cadastrados | N/A |
| `POST` | `/api/devices` | Cadastra um novo dispositivo | `{"name": "PC Gamer", "ip": "192.168.1.50", "mac": "AA:BB:CC:DD:EE:FF", "icon": "desktop"}` |
| `PUT` | `/api/devices/{id}` | Atualiza informações de um dispositivo | `{"name": "PC Gamer Novo", "ip": "192.168.1.50", "mac": "AA:BB:CC:DD:EE:FF"}` |
| `DELETE` | `/api/devices/{id}` | Remove um dispositivo | N/A |
| `POST` | `/api/wake/{id}` | Envia o Magic Packet WoL para o dispositivo | N/A |
| `GET` | `/api/ping/{id}` | Verifica o status instantâneo de ping | N/A |

---

## 🐳 Containerização & Padrão CasaOS

### Bloco `x-casaos` em `docker-compose.yml`
```yaml
x-casaos:
  architectures:
    - amd64
    - arm64
  main: wakeoncasa
  icon: "https://cdn-icons-png.flaticon.com/512/3659/3659899.png"
  title:
    en_us: "WakeOnCasa"
    pt_br: "WakeOnCasa"
  description:
    en_us: "Painel de Wake-on-LAN e monitoramento de dispositivos para CasaOS"
    pt_br: "Painel de Wake-on-LAN e monitoramento de dispositivos para CasaOS"
  index: /
  port_map: "8089"
  scheme: http
  category: "Utilities"
```

### Configuração do Robocopy (`copiar-servidor.bat`)
- Destino Samba: `\\linux\root\DATA\AppData\WakeOnCasa`
- Filtros de Exclusão: `/XD .git __pycache__ logs /XF *.log *.tmp`
