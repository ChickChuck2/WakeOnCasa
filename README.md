# WakeOnCasa ⚡

[![CasaOS Compatible](https://img.shields.io/badge/CasaOS-Compatible-blue.svg)](https://casaos.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

**WakeOnCasa** é uma aplicação self-hosted de **Wake-on-LAN (WoL)** e monitoramento em tempo real de ativos de rede local, desenvolvida para rodar perfeitamente no ecossistema **CasaOS** via Docker.

 Ela permite cadastrar seus computadores, servidores NAS, consoles e Smart TVs e ligá-los remotamente com 1 clique através de pacotes UDP Magic Packet, acompanhando o status (Online/Offline) e a latência de rede.

---

## 🌟 Funcionalidades

- ⚡ **Disparo de Magic Packet WoL**: Transmissão em broadcast UDP (portas 7 e 9) para ligar dispositivos remotamente.
- 📡 **Monitoramento de Rede em Tempo Real**: Verificação rápida de disponibilidade (ping ICMP/TCP) e latência em milissegundos.
- 🎨 **Interface Glassmorphism CasaOS**: Painel web moderno em Dark Mode adaptado para a experiência visual do CasaOS.
- 🏷️ **Categorização de Dispositivos**: Suporte para Desktops, Servidores NAS, Smart TVs, Consoles e Roteadores.
- 🐳 **Pronto para CasaOS**: Metadados nativos (`x-casaos:` e labels `com.casaos.app.*`) inclusos no `docker-compose.yml`.
- 🔄 **Sincronização com Servidor Samba**: Script `copiar-servidor.bat` configurado para automatizar o envio via `robocopy` para o destino `\\linux\root\DATA\AppData\WakeOnCasa`.

---

## 🏗️ Estrutura do Projeto

```
WakeOnCasa/
├── backend/
│   ├── main.py              # Servidor FastAPI e rotas REST
│   ├── wol.py               # Motor de geração de Magic Packet UDP
│   ├── ping.py              # Verificador de status de rede
│   └── storage.py           # Gerenciador de persistência em JSON
├── static/
│   ├── css/
│   │   └── style.css        # CSS Glassmorphism no padrão CasaOS
│   ├── js/
│   │   └── app.js           # Lógica do painel interativo frontend
│   └── index.html           # Interface Web responsiva
├── data/
│   └── devices.json         # Base de dados (persistida no volume do container)
├── Dockerfile               # Imagem Docker de produção
├── docker-compose.yml       # Orquestração e metadados CasaOS
├── copiar-servidor.bat      # Script Robocopy para sincronizar no servidor CasaOS
├── README.md                # Documentação principal
├── resumo.md                # Resumo executivo do projeto
├── ROADMAP.md               # Planejamento de etapas de desenvolvimento
└── ARCHITECTURE.md          # Especificação da arquitetura técnica
```

---

## 🚀 Como Instalar e Rodar

### 1. No CasaOS (Servidor)
1. Execute o script `copiar-servidor.bat` na sua máquina local para enviar o projeto para `\\linux\root\DATA\AppData\WakeOnCasa`.
2. Acesse o servidor CasaOS via SSH ou pelo painel do CasaOS.
3. No diretório `/DATA/AppData/WakeOnCasa`, execute:
   ```bash
   docker compose up -d --build
   ```
4. O ícone do **WakeOnCasa** aparecerá automaticamente no seu painel do CasaOS acessível na porta **8089** (ex: `http://ip-do-casaos:8089`).

### 2. Desenvolvimento Local
Para rodar a aplicação localmente no seu computador:
```bash
# Instalar dependências
pip install -r requirements.txt

# Iniciar servidor Uvicorn
uvicorn backend.main:app --reload --port 8089
```
Acesse no navegador: `http://localhost:8089`.

---

## 📡 Endpoints da API REST

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/api/devices` | Retorna a lista de dispositivos cadastrados |
| `POST` | `/api/devices` | Adiciona um novo dispositivo |
| `PUT` | `/api/devices/{id}` | Atualiza um dispositivo existente |
| `DELETE` | `/api/devices/{id}` | Exclui um dispositivo |
| `POST` | `/api/wake/{id}` | Dispara o pacote Magic Packet (WoL) |
| `GET` | `/api/ping/{id}` | Verifica o status instantâneo de ping do dispositivo |
| `GET` | `/api/ping-all` | Atualiza o status de todos os dispositivos cadastrados |

---

## 📄 Licença
Desenvolvido para uso pessoal e integração no ecossistema CasaOS.
