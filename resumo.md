# WakeOnCasa - Resumo do Projeto

## Visão Geral
O **WakeOnCasa** é uma solução de **Wake-on-LAN (WoL)** e monitoramento de ativos de rede local desenvolvida especificamente para rodar como container nativo no **CasaOS**.

Ele permite aos usuários ligar computadores, servidores e outros dispositivos de sua rede doméstica remotamente através de um clique na interface web do CasaOS, além de monitorar a disponibilidade (status Online/Offline e latência de ping) de cada dispositivo cadastrado.

---

## Padrões de Implantação e Servidor (CasaOS)

Conforme estabelecido nas especificações do ambiente (`infos.md`), o projeto atende rigorosamente aos seguintes padrões:

1. **Destino de Hospedagem no Servidor**:
   - Diretório remoto: `\\linux\root\DATA\AppData\WakeOnCasa`
2. **Sincronização Automatizada via Robocopy**:
   - O projeto inclui o script `copiar-servidor.bat` que executa o `robocopy` da máquina local para o servidor remoto, preservando estrutura de pastas, ignorando arquivos temporários/caches e prevenindo bloqueio de arquivos NTFS.
3. **Padrões de Integração CasaOS**:
   - `docker-compose.yml` estruturado com o bloco de metadados `x-casaos:` (título, descrição em pt-BR/en-US, porta web 8089, categoria Utilities e ícone customizado).
   - Labels nativas `com.casaos.app.*` no container de dashboard para auto-descoberta no painel do CasaOS.
   - `Dockerfile` otimizado em Python com permissões de rede UDP broadcast para transmissão do Magic Packet.

---

## Estrutura dos Documentos do Repositório

- **[infos.md](file:///b:/Repos/WakeOnCasa/infos.md)**: Parâmetros do servidor Samba e caminhos de deploy.
- **[resumo.md](file:///b:/Repos/WakeOnCasa/resumo.md)**: Este documento com o resumo executivo e especificações.
- **[ROADMAP.md](file:///b:/Repos/WakeOnCasa/ROADMAP.md)**: Planejamento detalhado das etapas e funcionalidades do WakeOnCasa.
- **[ARCHITECTURE.md](file:///b:/Repos/WakeOnCasa/ARCHITECTURE.md)**: Detalhamento da arquitetura técnica, API REST e modelo do container.