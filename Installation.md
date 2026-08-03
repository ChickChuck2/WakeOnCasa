# 📖 Guia de Instalação e Configuração — WakeOnCasa ⚡

O WakeOnCasa utiliza uma arquitetura de comunicação em 3 pilares:
1. **Painel Cloud na Vercel (Acesso Remoto via Internet)**: Interface web acessível de qualquer lugar (celular/PC externo) sem necessidade de abrir portas no roteador (sem Port Forwarding).
2. **Firebase Firestore (Ponte de Comunicação)**: Relé de dados que recebe as ordens disparadas pela Vercel e envia os status em tempo real.
3. **Agente Local no CasaOS / Docker (Rede LAN)**: Roda dentro da sua rede local, escuta os comandos do Firebase, dispara o pacote Magic Packet UDP físico para ligar os computadores e monitora a latência por ICMP Ping.

---

## 🛠️ Ferramentas Necessárias & Pré-requisitos

- 📦 **Git**: Para clonar o repositório da aplicação.
- 📐 **Conta na Vercel**: Para hospedar a interface web pública e acessar os controles de qualquer lugar pela internet.
- 🔥 **Projeto no Firebase (Firestore Database)**: Para atuar como ponte de comunicação (relé de comandos e status) entre a Vercel e o seu servidor local.
- 🐳 **Servidor CasaOS ou Docker (Linux)**: Conectado na mesma rede local (LAN) dos computadores que serão ligados via Wake-on-LAN.
- 🔌 **Computadores Alvo (Dispositivos a Serem Ligados)**: Devem estar conectados obrigatoriamente por **cabo Ethernet (RJ45)** na placa-mãe e devidamente configurados na BIOS/UEFI e no Sistema Operacional para aceitar o pacote **Magic Packet (Wake-on-LAN)**.

---

## 📥 1º Passo: Baixar o Código

Abra o terminal ou prompt de comando na sua máquina de desenvolvimento e clone o repositório oficial:

```bash
git clone https://github.com/ChickChuck2/WakeOnCasa.git
cd WakeOnCasa
```

---

## 🔥 2º Passo: Configurar o Firebase (Sincronização Nuvem ↔ Local)

Para permitir que a Vercel controle as máquinas da sua casa sem precisar expor portas no seu roteador (sem Port Forwarding / sem IP público), o WakeOnCasa utiliza o **Firebase Firestore REST API** como um relé de dados seguro.

1. Acesse o [Firebase Console](https://console.firebase.google.com/) e clique em **Adicionar projeto**.
2. Defina um nome para o projeto (ex: `wakeoncasa-home`) e conclua a criação.
3. No menu lateral esquerdo, vá em **Criação** -> **Firestore Database** e clique em **Criar banco de dados**.
4. Selecione a localização (ex: `nam5 (us-central)`) e escolha iniciar em **Modo de Teste** (ou configure as regras para permitir leitura/escrita REST).
5. Copie o **ID do Projeto** (exibido em *Configurações do Projeto*).
6. *(Nota)* Por padrão, a aplicação utiliza a variável de ambiente `FIREBASE_PROJECT_ID`. Se nenhuma for definida, o valor padrão `testproject-49566` é utilizado.

---

## 📐 3º Passo: Criar e Publicar o Projeto na Vercel

A Vercel hospedará o dashboard web responsivo com suporte às Serverless Functions do FastAPI (`/api/index.py` configurado via `vercel.json`).

> [!NOTE]
> **É necessário fazer Fork do repositório?**
> - **Se o repositório no GitHub já é seu**: **Não**. Você pode importá-lo diretamente na Vercel.
> - **Se outra pessoa for instalar a partir do repositório original**: **Sim**. É necessário fazer um **Fork** do projeto no GitHub para a própria conta antes, pois a Vercel exige que o repositório pertença ao usuário logado para conectar os deploys automáticos.

1. Acesse o painel da [Vercel](https://vercel.com/) e faça login.
2. Clique em **Add New...** -> **Project** e importe o repositório `WakeOnCasa` da sua conta do GitHub.
3. Em **Environment Variables** (Variáveis de Ambiente), adicione:
   - **Key**: `FIREBASE_PROJECT_ID`
   - **Value**: O ID do seu projeto Firebase criado no 2º Passo.
4. Clique em **Deploy**.
5. Após a conclusão, a Vercel fornecerá um link público (ex: `https://wakeoncasa.vercel.app`).
6. Através dessa URL, você poderá visualizar o status dos seus dispositivos e disparar o comando de ligar de qualquer lugar do mundo!

---

## 🏠 4º Passo: Configurar e Rodar o Agente Local (CasaOS / Docker)

O servidor local (seja CasaOS ou qualquer servidor Linux rodando Docker) é o agente responsável por receber os comandos da nuvem, enviar o pacote **Magic Packet UDP** físico e monitorar os **Pings ICMP** dos seus computadores.

> [!IMPORTANT]
> O container Docker **precisa obrigatoriamente** rodar em modo host (`network_mode: host`) para conseguir enviar pacotes broadcast UDP (portas 7 e 9) diretamente para a placa de rede da sua subrede local.

1. Abra o **Terminal** do seu servidor (seja diretamente na interface/painel da máquina ou via SSH):

2. Crie o diretório da aplicação no servidor (no CasaOS, o caminho padrão de apps é `/DATA/AppData/WakeOnCasa`):
   ```bash
   mkdir -p /DATA/AppData/WakeOnCasa
   cd /DATA/AppData/WakeOnCasa
   ```

3. Transfira os arquivos do repositório para essa pasta.

4. Defina a variável `FIREBASE_PROJECT_ID` com o ID do seu projeto Firebase (criado no 2º Passo) no arquivo `docker-compose.yml`:
   ```yaml
       environment:
         - DATA_DIR=/app/data
         - FIREBASE_PROJECT_ID=seu-projeto-firebase
         - TZ=America/Sao_Paulo
   ```

5. Construa e inicie o container:
   ```bash
   docker compose up -d --build
   ```

*(No CasaOS, o ícone do **WakeOnCasa** surgirá automaticamente no seu painel principal na porta `8089`).*

---

## ⚡ 5º Passo: Configurar o Wake-on-LAN nas Máquinas Alvo

Para que o seu computador ligue ao receber o comando do WakeOnCasa, ele precisa estar devidamente configurado:

> [!IMPORTANT]
> O recurso Wake-on-LAN exige **obrigatoriamente conexão via cabo de rede (Ethernet RJ45)** ligado à placa-mãe. Conexões Wi-Fi não funcionam para ligar o computador quando desligado (estado S5). Além disso, a BIOS/UEFI e a placa de rede no Windows/Linux precisam ser configuradas para aceitar o **Magic Packet**.

1. **Na BIOS / UEFI da Máquina Alvo**:
   - Ligue a máquina e pressione `DEL` ou `F2` para entrar na BIOS.
   - Busque por **Power Management** ou **Advanced**.
   - **Ative**: `Wake on LAN`, `Power On by PCI-E/PME` ou `Resume by LAN`.
   - **Desative**: `ErP Ready` ou `EuP Lot 6` (para manter a placa de rede energizada em standby).

2. **No Windows da Máquina Alvo**:
   - Abra o *Gerenciador de Dispositivos* -> *Adaptadores de rede*.
   - Clique com o botão direito na sua placa Ethernet -> *Propriedades*.
   - Aba *Avançado*: Habilite `Wake on Magic Packet` e `Habilitar Magic Packet`.
   - Aba *Gerenciamento de Energia*: Marque `Permitir que este dispositivo acorde o computador`.

3. **No Linux da Máquina Alvo**:
   - Execute: `sudo ethtool -s eth0 wol g` (substitua `eth0` pelo nome da sua interface de rede).

---

## 🔍 6º Passo: Validação e Testes

1. **Testar API Healthcheck**:
   Acesse no navegador: `http://<IP_DO_CASAOS>:8089/api/health` ou `https://seu-projeto.vercel.app/api/health`
   Deve retornar: `{"status": "ok", "service": "WakeOnCasa"}`

2. **Cadastrar Dispositivo**:
   No painel web, cadastre seu PC informando o Nome, IP local (ex: `192.168.1.50`) e o Endereço MAC (ex: `AA:BB:CC:DD:EE:FF`).

3. **Testar Envio de Magic Packet**:
   Desligue a máquina de teste. Clique no botão **Ligar / Wake** no painel da Vercel ou do CasaOS. O sinal será transmitido e o computador deverá ligar em poucos segundos!

---

## 🛠️ Solução de Problemas (Troubleshooting)

| Problema | Causa Provável | Solução |
| :--- | :--- | :--- |
| **PC não liga via Vercel** | O container no CasaOS não está rodando ou sem conexão com o Firebase. | Verifique se o container no CasaOS está rodando (`docker compose ps`) e se a variável `FIREBASE_PROJECT_ID` é igual na Vercel e no CasaOS. |
| **Magic Packet é enviado mas nada acontece** | WoL desativado na BIOS ou Docker sem rede host. | Certifique-se de que o container rodou com `network_mode: host` ou `--net host`. Verifique a BIOS do PC alvo. |
| **Ping sempre "Offline"** | Firewall do Windows bloqueando o ping ICMP. | No Windows alvo, abra o Firewall e habilite a regra de entrada *Compartilhamento de Arquivos e Impressoras (Requisição de Eco - ICMPv4-In)*. |

---

> [!TIP]
> Para mais detalhes sobre a arquitetura e componentes internos da aplicação, consulte o arquivo [ARCHITECTURE.md](file:///b:/Repos/WakeOnCasa/ARCHITECTURE.md).

