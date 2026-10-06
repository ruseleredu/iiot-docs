#!/usr/bin/env python3
"""Gera o LAB IoT: portal nginx + Node-RED por grupo + MQTT + Gitea + chat + túnel público.

Tudo fica sob UM endereço, em caminhos (sem DNS, sem subdomínios):

    <base>/            portal
    <base>/lab05-a/    Node-RED do grupo A   (… um por grupo)
    <base>/lab05-p/    Node-RED do professor
    <base>/lab05-n/    Node-RED do painel de notas
    <base>/git/        Gitea  (uma organização por grupo)
    <base>/chat/       Mattermost (um canal privado por grupo)

onde <base> é:
    - na rede do laboratório:  http://<IP-do-servidor>      (sem cota, sem internet)
    - de qualquer lugar:       https://iot.adrianoruseler.com   (VPS com Apache)

Os serviços rodam no servidor do laboratório. Um container "tunel" abre um túnel SSH
REVERSO até o VPS (sai do laboratório: não precisa abrir portas na rede da instituição),
e o Apache do VPS encaminha o HTTPS público para esse túnel.

Reservas de letras: 'p' = PROFESSOR (ex.: lab05-p) · 'n' = NOTAS (ex.: lab05-n)

Gera, dentro da pasta de saída (--saida, padrão: <lab>):
  docker-compose.yml, Dockerfile, nginx/, settings/, data/, mosquitto/, mqtt-explorer/,
  gitea/init/, mattermost/init/, postgres/init/, tunel/ (cliente do túnel + chave SSH),
  vps/ (arquivos para o VPS: proxy do Apache, página offline e setup-vps.sh),
  credenciais.txt e .segredos.json (senhas reaproveitadas entre execuções).

Uso:
  py gen_iot_portal.py --lab lab05 --grupos 10 --ip 192.168.0.10
  py gen_iot_portal.py --sem-tunel            # só rede local (http://IP/)
  py gen_iot_portal.py --novas-senhas         # sorteia senhas novas para todos
  py gen_iot_portal.py --sem-chat --gitea-db sqlite   # versão enxuta, sem PostgreSQL
"""
import sys, os, re, secrets, string, argparse, json
from urllib.parse import urlparse
import bcrypt

# Console do Windows: garante UTF-8 (acentos e emojis) mesmo com saída redirecionada
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

PUBLICO_URL_PADRAO = "https://iot.adrianoruseler.com"

ap = argparse.ArgumentParser(description="Gera o LAB IoT (caminhos + túnel SSH para o VPS).")
ap.add_argument("--lab", default="lab05", help="Nome do lab (ex.: lab05); prefixo de tudo")
ap.add_argument("--grupos", type=int, default=10, help="Quantidade de grupos de alunos (máx. 24)")
ap.add_argument("--ip", default="127.0.0.1",
                help="IP do servidor na rede do laboratório (acesso local, MQTT e MQTT Explorer)")
ap.add_argument("--dominio", default="iot.lab",
                help="Domínio interno, usado só nos e-mails das contas (ex.: lab05-a@iot.lab)")
ap.add_argument("--publico-url", default=PUBLICO_URL_PADRAO,
                help="URL pública (HTTPS) servida pelo Apache do VPS")
ap.add_argument("--vps-host", default=None,
                help="Host/IP do VPS para o SSH (padrão: o host da --publico-url)")
ap.add_argument("--vps-ssh-porta", type=int, default=22, help="Porta SSH do VPS")
ap.add_argument("--vps-usuario", default="tunel", help="Usuário restrito do túnel no VPS")
ap.add_argument("--vps-porta-tunel", type=int, default=8080,
                help="Porta (só em 127.0.0.1 do VPS) onde o túnel entrega o portal ao Apache")
ap.add_argument("--sem-tunel", action="store_true",
                help="Não inclui o túnel (só rede local, http://IP/)")
ap.add_argument("--sem-gitea", action="store_true", help="Não inclui o Gitea")
ap.add_argument("--gitea-repo", default="nodered",
                help="Repositório inicial criado em cada organização ('' = nenhum)")
ap.add_argument("--gitea-db", choices=["postgres", "sqlite"], default="postgres",
                help="Banco do Gitea: postgres (padrão, compartilhado) ou sqlite")
ap.add_argument("--sem-chat", action="store_true", help="Não inclui o Mattermost")
ap.add_argument("--proteger-http", action="store_true",
                help="Exige login (usuário/senha do grupo) nos dashboards e endpoints HTTP do Node-RED")
ap.add_argument("--novas-senhas", action="store_true",
                help="Sorteia senhas novas para todos os grupos (padrão: mantém as já geradas)")
ap.add_argument("--saida", default=None, help="Pasta de saída (padrão: <lab>)")
ap.add_argument("--mqtt-explorer-auth", action="store_true", help="Exige login no MQTT Explorer")
ap.add_argument("--mqtt-explorer-usuario", default="admin", help="Usuário do MQTT Explorer")
ap.add_argument("--mqtt-explorer-senha", default=None, help="Senha do MQTT Explorer (gerada se omitida)")
ap.add_argument("--mqtt-explorer-porta", type=int, default=3001, help="Porta do MQTT Explorer")
args = ap.parse_args()

LAB = args.lab.lower()
if not re.fullmatch(r"[a-z][a-z0-9]{1,20}", LAB):
    sys.exit("--lab deve começar com letra e ter só letras/dígitos (ex.: lab05), "
             "pois vira caminho da URL, usuário do chat e prefixo MQTT.")
N = args.grupos
IP = args.ip
DOMINIO = args.dominio

# ---------------- pasta de saída e segredos persistentes ----------------
SAIDA = args.saida or LAB
os.makedirs(SAIDA, exist_ok=True)
os.chdir(SAIDA)
SAIDA_ABS = os.getcwd()

ARQ_SEGREDOS = ".segredos.json"
try:
    with open(ARQ_SEGREDOS, encoding="utf-8") as _f:
        SEGREDOS = json.load(_f)
except (OSError, ValueError):
    SEGREDOS = {}


def segredo(nome, gerar, renovar=False):
    """Valor guardado em .segredos.json; só é gerado na primeira vez (ou se renovar)."""
    if renovar or nome not in SEGREDOS:
        SEGREDOS[nome] = gerar()
    return SEGREDOS[nome]


def gerar_senha(tamanho=8):
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))


# ---------------- endereços ----------------
TUNEL = not args.sem_tunel
LOCAL_URL = "http://localhost" if IP.startswith("127.") else f"http://{IP}"
PUBLICO_URL = args.publico_url.rstrip("/")
if TUNEL and (not PUBLICO_URL.startswith("https://") or urlparse(PUBLICO_URL).path not in ("", "/")):
    sys.exit("--publico-url deve ser https://<host> sem caminho (ex.: https://iot.adrianoruseler.com)")
PUBLIC_URL = PUBLICO_URL if TUNEL else LOCAL_URL        # URL "oficial" (Gitea, Mattermost)
PUBLIC_HOST = urlparse(PUBLIC_URL).hostname
VPS_HOST = args.vps_host or urlparse(PUBLICO_URL).hostname
VPS_PORTA_TUNEL = args.vps_porta_tunel

# ---------------- serviços opcionais ----------------
CHAT = not args.sem_chat
CHAT_IMAGEM = "mattermost/mattermost-team-edition:release-11"
CHAT_TEAM = LAB

GITEA = not args.sem_gitea
GITEA_REPO = args.gitea_repo.strip()
GITEA_PG = GITEA and args.gitea_db == "postgres"

POSTGRES = CHAT or GITEA_PG
_pg_senha = lambda: secrets.token_hex(16)
PG_ROOT_SENHA = segredo("postgres_root", _pg_senha) if POSTGRES else None
PG_GITEA_SENHA = segredo("postgres_gitea", _pg_senha) if GITEA_PG else None
PG_MM_SENHA = segredo("postgres_mattermost", _pg_senha) if CHAT else None
GITEA_SECRET_KEY = segredo("gitea_secret_key", lambda: secrets.token_hex(32)) if GITEA else None

MQTTX_PORTA = args.mqtt_explorer_porta
MQTTX_URL = f"{LOCAL_URL}:{MQTTX_PORTA}/"
MQTTX_AUTH = args.mqtt_explorer_auth
MQTTX_USER = args.mqtt_explorer_usuario
MQTTX_SENHA = (args.mqtt_explorer_senha or segredo("mqtt_explorer_senha", lambda: gerar_senha(10))) \
    if MQTTX_AUTH else None

# ---------------- nomes ----------------
LETRA_PROF, LETRA_NOTAS = "p", "n"
letras = [c for c in string.ascii_lowercase if c not in (LETRA_PROF, LETRA_NOTAS)]
if not 1 <= N <= len(letras):
    sys.exit(f"--grupos deve ser entre 1 e {len(letras)} (letras a-z sem 'p' e 'n').")

grupos_alunos = [f"{LAB}-{letras[i]}" for i in range(N)]
prof = f"{LAB}-{LETRA_PROF}"
notas_service = f"{LAB}-{LETRA_NOTAS}"
todos_servicos = grupos_alunos + [prof, notas_service]

C = LAB  # prefixo dos nomes de container (lab05-portal, lab05-postgres, ...)


def is_prof(g):
    return g == prof


def is_notas(g):
    return g == notas_service


def letra_de(g):
    return g.rsplit("-", 1)[-1]


def org_de(g):
    """Organização Gitea do grupo (não pode coincidir com o nome do usuário)."""
    return f"{LAB}-grupo-{letra_de(g)}"


def gravar(caminho, conteudo, executavel=False):
    """Grava sempre em UTF-8 com quebras de linha LF (os containers são Linux)."""
    d = os.path.dirname(caminho)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(conteudo)
    if executavel:
        os.chmod(caminho, 0o755)


# ---------------- credenciais dos grupos (persistentes) ----------------
credenciais_geradas = []   # (usuario, senha_admin, usuario_view, senha_view)
for g in todos_servicos:
    s_admin = segredo(f"senha:{g}", lambda: gerar_senha(8), renovar=args.novas_senhas)
    s_view = segredo(f"senha:{g}-view", lambda: gerar_senha(8), renovar=args.novas_senhas)
    credenciais_geradas.append((g, s_admin, f"{g}-view", s_view))
SENHA = {u: s for (u, s, _uv, _sv) in credenciais_geradas}
SENHA.update({uv: sv for (_u, _s, uv, sv) in credenciais_geradas})

for g in todos_servicos:
    os.makedirs(f"data/{g}", exist_ok=True)
    open(f"data/{g}/.gitkeep", "a").close()

# =====================================================================
# mosquitto/mosquitto.conf
# =====================================================================
gravar("mosquitto/mosquitto.conf", """listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest stdout
""")
print("🐝 mosquitto/mosquitto.conf")

# =====================================================================
# Dockerfile (Node-RED com nós extras)
# =====================================================================
dockerfile = """FROM nodered/node-red:latest
USER root
RUN apk add --no-cache build-base python3
USER node-red
# Install additional Node-RED nodes
RUN npm install --unsafe-perm --no-update-notifier --no-fund \\
    node-red-node-sqlite \\
    @flowfuse/node-red-dashboard \\
    node-red-contrib-bcrypt \\
    node-red-contrib-finite-statemachine \\
    @flowfuse/node-red-dashboard-2-ui-led \\
    node-red-node-serialport \\
    node-red-node-ui-table \\
    && npm cache clean --force
"""

gravar("Dockerfile", dockerfile)
print("📦 Dockerfile")

# =====================================================================
# docker-compose.yml
# =====================================================================
c = [
    f"# LAB IoT {LAB} — gerado por gen_iot_portal.py\n",
    f"# {N} grupos + professor ({prof}) + notas ({notas_service})\n",
    f"# Local:   {LOCAL_URL}/\n",
    (f"# Público: {PUBLICO_URL}/   (túnel SSH -> Apache do VPS)\n" if TUNEL else ""),
    "# Subir:   docker compose up -d --build\n",
    "services:\n",
    "  nginx:\n",
    "    image: nginx:alpine\n",
    f"    container_name: {C}-portal\n",
    "    restart: unless-stopped\n",
    "    ports:\n",
    '      - "80:80"\n',
    "    volumes:\n",
    "      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro\n",
    "      - ./nginx/html:/usr/share/nginx/html:ro\n",
    "    depends_on:\n",
]
c += [f"      - {g}-nodered\n" for g in todos_servicos]
c += ["      - mqtt-explorer\n"]
if GITEA:
    c += ["      - gitea\n"]
if CHAT:
    c += ["      - mattermost\n"]
c += ["    networks:\n", "      - labnet\n"]

c += [
    "\n  mosquitto:\n",
    "    image: eclipse-mosquitto:latest\n",
    f"    container_name: {C}-mosquitto\n",
    "    restart: unless-stopped\n",
    "    ports:\n",
    '      - "1883:1883"\n',
    "    volumes:\n",
    "      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro\n",
    "      - mosquitto_data:/mosquitto/data\n",
    "    networks:\n",
    "      - labnet\n",
]

for g in todos_servicos:
    c += [
        f"\n  {g}-nodered:\n",
        "    build: .\n",
        "    image: lab-nodered:latest\n",
        f"    container_name: {g}-nodered\n",
        "    restart: unless-stopped\n",
        "    volumes:\n",
        f"      - ./data/{g}:/data\n",
        f"      - ./settings/{g}.js:/data/settings.js:ro\n",
    ]
    if is_notas(g):
        c += ["      - ./data:/data_grupos:ro\n"]   # painel de notas lê os fluxos de todos
    c += [
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "    depends_on:\n",
        "      - mosquitto\n",
        "    networks:\n",
        "      - labnet\n",
    ]

# MQTT Explorer (único; só na rede local, porta direta — não suporta subcaminho)
c += [
    "\n  mqtt-explorer:\n",
    "    image: ruseler/mqtt-explorer:local\n",
    f"    container_name: {C}-mqtt-explorer\n",
    "    restart: unless-stopped\n",
    "    ports:\n",
    f'      - "{MQTTX_PORTA}:3000"\n',
    "    environment:\n",
    "      - TZ=America/Sao_Paulo\n",
    "      - PORT=3000\n",
    "      - MQTT_AUTO_CONNECT_HOST=mosquitto\n",
    "      - MQTT_AUTO_CONNECT_PORT=1883\n",
    f"      - ALLOWED_ORIGINS=http://{IP}:{MQTTX_PORTA},http://localhost:{MQTTX_PORTA}\n",
]
if MQTTX_AUTH:
    c += [
        "      - MQTT_EXPLORER_SKIP_AUTH=false\n",
        f"      - MQTT_EXPLORER_USERNAME={MQTTX_USER}\n",
        f"      - MQTT_EXPLORER_PASSWORD={MQTTX_SENHA}\n",
    ]
else:
    c += ["      - MQTT_EXPLORER_SKIP_AUTH=true\n"]
c += [
    "    volumes:\n",
    "      - ./mqtt-explorer/data:/app/data\n",
    "    depends_on:\n",
    "      - mosquitto\n",
    "    networks:\n",
    "      - labnet\n",
]

# PostgreSQL compartilhado + db-init (cria/atualiza bancos e senhas a cada subida)
if POSTGRES:
    c += [
        "\n  postgres:\n",
        "    image: postgres:16-alpine\n",
        f"    container_name: {C}-postgres\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - POSTGRES_USER=postgres\n",
        f"      - POSTGRES_PASSWORD={PG_ROOT_SENHA}\n",
        "    volumes:\n",
        "      - postgres_data:/var/lib/postgresql/data\n",
        "    healthcheck:\n",
        '      test: ["CMD-SHELL", "pg_isready -U postgres"]\n',
        "      interval: 5s\n",
        "      timeout: 5s\n",
        "      retries: 30\n",
        "    networks:\n",
        "      - labnet\n",
        "\n  db-init:\n",
        "    image: postgres:16-alpine\n",
        f"    container_name: {C}-db-init\n",
        '    restart: "no"\n',
        "    environment:\n",
        f"      - PGPASSWORD={PG_ROOT_SENHA}\n",
        '    command: ["psql", "-h", "postgres", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-f", "/init/bancos.sql"]\n',
        "    volumes:\n",
        "      - ./postgres/init:/init:ro\n",
        "    depends_on:\n",
        "      postgres:\n",
        "        condition: service_healthy\n",
        "    networks:\n",
        "      - labnet\n",
    ]

# Gitea (único) + gitea-init
if GITEA:
    c += [
        "\n  gitea:\n",
        "    image: gitea/gitea:latest\n",
        f"    container_name: {C}-gitea\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        "      - USER_UID=1000\n",
        "      - USER_GID=1000\n",
        "      - TZ=America/Sao_Paulo\n",
    ]
    if GITEA_PG:
        c += [
            "      - GITEA__database__DB_TYPE=postgres\n",
            "      - GITEA__database__HOST=postgres:5432\n",
            "      - GITEA__database__NAME=gitea\n",
            "      - GITEA__database__USER=gitea\n",
            f"      - GITEA__database__PASSWD={PG_GITEA_SENHA}\n",
            "      - GITEA__database__SSL_MODE=disable\n",
        ]
    else:
        c += ["      - GITEA__database__DB_TYPE=sqlite3\n"]
    c += [
        f"      - GITEA__server__DOMAIN={PUBLIC_HOST}\n",
        f"      - GITEA__server__ROOT_URL={PUBLIC_URL}/git/\n",
        "      - GITEA__server__HTTP_PORT=3000\n",
        "      - GITEA__server__DISABLE_SSH=true\n",
        "      - GITEA__security__INSTALL_LOCK=true\n",
        f"      - GITEA__security__SECRET_KEY={GITEA_SECRET_KEY}\n",
        # acessível por http://IP (local) e https://VPS: cookie não pode exigir HTTPS
        "      - GITEA__session__COOKIE_SECURE=false\n",
        "      - GITEA__service__DISABLE_REGISTRATION=true\n",
        "      - GITEA__service__REQUIRE_SIGNIN_VIEW=true\n",
        "      - GITEA__service__DEFAULT_ORG_VISIBILITY=private\n",
        "      - GITEA__repository__DEFAULT_PRIVATE=private\n",
        "      - GITEA__repository__DEFAULT_BRANCH=main\n",
        "      - GITEA__ui__DEFAULT_THEME=gitea-auto\n",
        "      - GITEA__time__DEFAULT_UI_LOCATION=America/Sao_Paulo\n",
        "    volumes:\n",
        "      - gitea_data:/data\n",
        "    healthcheck:\n",
        '      test: ["CMD", "curl", "-fsS", "http://localhost:3000/api/healthz"]\n',
        "      interval: 10s\n",
        "      timeout: 5s\n",
        "      retries: 30\n",
    ]
    if GITEA_PG:
        c += [
            "    depends_on:\n",
            "      db-init:\n",
            "        condition: service_completed_successfully\n",
        ]
    c += [
        "    networks:\n",
        "      - labnet\n",
        "\n  gitea-init:\n",
        "    image: gitea/gitea:latest\n",
        f"    container_name: {C}-gitea-init\n",
        '    restart: "no"\n',
        '    entrypoint: ["/bin/bash", "/init/gitea-init.sh"]\n',
        "    volumes:\n",
        "      - gitea_data:/data\n",
        "      - ./gitea/init:/init:ro\n",
        "    depends_on:\n",
        "      gitea:\n",
        "        condition: service_healthy\n",
        "    networks:\n",
        "      - labnet\n",
    ]

# Mattermost (único) + mattermost-init (mmctl em modo local, via socket compartilhado)
if CHAT:
    c += [
        "\n  mattermost:\n",
        f"    image: {CHAT_IMAGEM}\n",
        f"    container_name: {C}-mattermost\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - MM_SQLSETTINGS_DRIVERNAME=postgres\n",
        f"      - MM_SQLSETTINGS_DATASOURCE=postgres://mattermost:{PG_MM_SENHA}@postgres:5432/mattermost?sslmode=disable&connect_timeout=10\n",
        f"      - MM_SERVICESETTINGS_SITEURL={PUBLIC_URL}/chat\n",
        "      - MM_SERVICESETTINGS_LISTENADDRESS=:8065\n",
        "      - MM_SERVICESETTINGS_ENABLELOCALMODE=true\n",
        "      - MM_SERVICESETTINGS_LOCALMODESOCKETLOCATION=/mattermost/data/mmctl.socket\n",
        "      - MMCTL_LOCAL_SOCKET_PATH=/mattermost/data/mmctl.socket\n",
        "      - MM_TEAMSETTINGS_ENABLEOPENSERVER=false\n",
        "      - MM_TEAMSETTINGS_MAXUSERSPERTEAM=200\n",
        "      - MM_EMAILSETTINGS_REQUIREEMAILVERIFICATION=false\n",
        "      - MM_EMAILSETTINGS_SENDEMAILNOTIFICATIONS=false\n",
        "      - MM_EMAILSETTINGS_ENABLESIGNINWITHUSERNAME=true\n",
        "      - MM_LOCALIZATIONSETTINGS_DEFAULTSERVERLOCALE=pt-br\n",
        "      - MM_LOCALIZATIONSETTINGS_DEFAULTCLIENTLOCALE=pt-br\n",
        "      - MM_LOGSETTINGS_ENABLEDIAGNOSTICS=false\n",
        "      - MM_FILESETTINGS_MAXFILESIZE=52428800\n",
        "      - MM_PASSWORDSETTINGS_MINIMUMLENGTH=8\n",
        "      - MM_PASSWORDSETTINGS_LOWERCASE=false\n",
        "      - MM_PASSWORDSETTINGS_UPPERCASE=false\n",
        "      - MM_PASSWORDSETTINGS_NUMBER=false\n",
        "      - MM_PASSWORDSETTINGS_SYMBOL=false\n",
        "    volumes:\n",
        "      - mm_config:/mattermost/config\n",
        "      - mm_data:/mattermost/data\n",
        "      - mm_logs:/mattermost/logs\n",
        "      - mm_plugins:/mattermost/plugins\n",
        "      - mm_client_plugins:/mattermost/client/plugins\n",
        "    healthcheck:\n",
        '      test: ["CMD", "/mattermost/bin/mmctl", "system", "status", "--local"]\n',
        "      interval: 15s\n",
        "      timeout: 10s\n",
        "      retries: 20\n",
        "      start_period: 60s\n",
        "    depends_on:\n",
        "      db-init:\n",
        "        condition: service_completed_successfully\n",
        "    networks:\n",
        "      - labnet\n",
        "\n  mattermost-init:\n",
        "    build:\n",
        "      context: ./mattermost/init\n",
        "      args:\n",
        f"        MM_IMAGE: {CHAT_IMAGEM}\n",
        "    image: lab-mattermost-init:latest\n",
        f"    container_name: {C}-mattermost-init\n",
        '    restart: "no"\n',
        '    user: "2000:2000"\n',
        "    environment:\n",
        "      - HOME=/tmp\n",
        "      - MMCTL_LOCAL_SOCKET_PATH=/mattermost/data/mmctl.socket\n",
        "    volumes:\n",
        "      - mm_data:/mattermost/data\n",
        "      - ./mattermost/init/mattermost-init.sh:/init/mattermost-init.sh:ro\n",
        '    entrypoint: ["/bin/bash", "/init/mattermost-init.sh"]\n',
        "    depends_on:\n",
        "      mattermost:\n",
        "        condition: service_healthy\n",
        "    networks:\n",
        "      - labnet\n",
    ]

# túnel SSH reverso: VPS 127.0.0.1:<porta> -> nginx:80 (sai do lab; reconecta sozinho)
if TUNEL:
    c += [
        "\n  tunel:\n",
        "    build: ./tunel\n",
        "    image: lab-tunel:latest\n",
        f"    container_name: {C}-tunel\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        f"      - VPS_HOST={VPS_HOST}\n",
        f"      - VPS_PORTA={args.vps_ssh_porta}\n",
        f"      - VPS_USUARIO={args.vps_usuario}\n",
        f"      - PORTA_REMOTA={VPS_PORTA_TUNEL}\n",
        "      - DESTINO=nginx:80\n",
        "    volumes:\n",
        "      - ./tunel/chave:/chave\n",
        "    depends_on:\n",
        "      - nginx\n",
        "    networks:\n",
        "      - labnet\n",
    ]

c += ["\nvolumes:\n", "  mosquitto_data:\n"]
if POSTGRES:
    c += ["  postgres_data:\n"]
if GITEA:
    c += ["  gitea_data:\n"]
if CHAT:
    c += ["  mm_config:\n", "  mm_data:\n", "  mm_logs:\n", "  mm_plugins:\n", "  mm_client_plugins:\n"]
c += ["\nnetworks:\n", "  labnet:\n", "    driver: bridge\n"]
gravar("docker-compose.yml", "".join(c))
print("🐳 docker-compose.yml")

# =====================================================================
# nginx/nginx.conf — um único servidor, tudo em caminhos
# =====================================================================
PROXY_OPTS = [
    "proxy_http_version 1.1;",
    "proxy_set_header Upgrade $http_upgrade;",
    "proxy_set_header Connection $connection_upgrade;",
    "proxy_set_header Host $host;",
    "proxy_set_header X-Real-IP $remote_addr;",
    "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    "proxy_set_header X-Forwarded-Proto $encaminhado_proto;",
    "proxy_read_timeout 3600s;",
    "proxy_send_timeout 3600s;",
    "proxy_buffering off;",
]


def location(caminho, linhas_extra, ind="        "):
    out = [f"{ind}location {caminho} {{\n"]
    out += [f"{ind}    {l}\n" for l in linhas_extra]
    out += [f"{ind}    {o}\n" for o in PROXY_OPTS]
    out += [f"{ind}}}\n"]
    return out


def papel_de(g):
    return "avaliador de notas" if is_notas(g) else "professor" if is_prof(g) else "grupo"


n = [
    f"# nginx.conf — gerado por gen_iot_portal.py ({LAB})\n",
    "worker_processes auto;\n",
    "events { worker_connections 1024; }\n\n",
    "http {\n",
    "    include       /etc/nginx/mime.types;\n",
    "    default_type  application/octet-stream;\n",
    "    sendfile on;\n",
    "    # redirecionamentos relativos: funcionam em http://IP e no domínio público\n",
    "    absolute_redirect off;\n\n",
    "    map $http_upgrade $connection_upgrade {\n",
    "        default upgrade;\n",
    "        ''      close;\n",
    "    }\n",
    "    # o Apache do VPS envia X-Forwarded-Proto: https; acesso local é http\n",
    "    map $http_x_forwarded_proto $encaminhado_proto {\n",
    "        default $http_x_forwarded_proto;\n",
    "        ''      $scheme;\n",
    "    }\n\n",
    "    server {\n",
    "        listen 80 default_server;\n",
    "        server_name _;\n",
    "        root /usr/share/nginx/html;\n",
    "        index index.html;\n",
    "        location / { }\n",
]
for g in todos_servicos:
    n += [f"\n        # {g} ({papel_de(g)}) -> /{g}/\n",
          f"        location = /{g} {{ return 301 /{g}/; }}\n"]
    n += location(f"/{g}/", [f"proxy_pass http://{g}-nodered:1880;"])
if GITEA:
    # Gitea em subcaminho (ROOT_URL = .../git/); receita da documentação oficial
    n += ["\n        # Gitea -> /git/\n",
          "        location = /git { return 301 /git/; }\n"]
    n += location("/git/", ["client_max_body_size 512m;",
                            "rewrite ^ $request_uri;",
                            "rewrite ^/git(/.*) $1 break;",
                            "proxy_pass http://gitea:3000$uri;"])
if CHAT:
    # Mattermost em subcaminho (SiteURL = .../chat); prefixo mantido
    n += ["\n        # Mattermost -> /chat/\n",
          "        location = /chat { return 301 /chat/; }\n"]
    n += location("/chat/", ["client_max_body_size 50m;",
                             "proxy_pass http://mattermost:8065;"])
n += ["\n        # MQTT Explorer não suporta subcaminho: só na rede local, porta direta\n",
      f"        location /mqtt {{ return 302 http://{IP}:{MQTTX_PORTA}/; }}\n",
      "    }\n", "}\n"]
gravar("nginx/nginx.conf", "".join(n))
print("🌐 nginx/nginx.conf")

# =====================================================================
# settings/<grupo>.js
# =====================================================================
tpl = """// settings.js do {g} — gerado automaticamente
module.exports = {{
    flowFile: 'flows.json',
    credentialSecret: '{cred}',
    editorTheme: {{
        page: {{ title: "{titulo}" }},
        header: {{ title: "{titulo}" }},
        projects: {{ enabled: true }},
    }},
    adminAuth: {{
        type: "credentials",
        users: [
            {{ username: "{g}",      password: "{hash_admin}", permissions: "*" }},
            {{ username: "{g}-view", password: "{hash_view}",  permissions: "read" }}
        ]
    }},{http_auth}
    // Node-RED vive em <base>/{g}/  (http://IP/{g}/ ou https://<publico>/{g}/)
    httpAdminRoot: '/{g}/',
    httpNodeRoot: '/{g}/',
    uiPort: 1880,
    logging: {{ console: {{ level: 'info' }} }}
}};
"""

for g, s_admin, _uv, s_view in credenciais_geradas:
    if is_notas(g):
        titulo = f"{LAB.upper()} - PAINEL DE NOTAS"
    elif is_prof(g):
        titulo = f"{LAB.upper()} - PROFESSOR"
    else:
        titulo = g.upper()
    hash_admin = bcrypt.hashpw(s_admin.encode(), bcrypt.gensalt(8)).decode()
    hash_view = bcrypt.hashpw(s_view.encode(), bcrypt.gensalt(8)).decode()
    http_auth = ""
    if args.proteger_http:
        http_auth = ("\n    // dashboards e endpoints HTTP exigem login (usuário/senha do grupo)\n"
                     f'    httpNodeAuth: {{ user: "{g}", pass: "{hash_admin}" }},')
    gravar(f"settings/{g}.js", tpl.format(
        g=g,
        # credentialSecret persistente: senão as credenciais salvas nos nós ficam ilegíveis
        cred=segredo(f"credential_secret:{g}", lambda: secrets.token_hex(16)),
        titulo=titulo, hash_admin=hash_admin, hash_view=hash_view, http_auth=http_auth))
print("⚙️  settings/<grupo>.js")

# =====================================================================
# nginx/html/index.html (portal; links RELATIVOS: valem no IP e no domínio público)
# =====================================================================
PORTAL_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LAB IoT · {{LAB}}</title>
<style>
  :root {
    --bg:      #071311;
    --panel:   #0d201c;
    --line:    #17332c;
    --ink:     #dcf5ec;
    --muted:   #6f9a8d;
    --signal:  #35e0b0;
    --signal-dim: #1c6e57;
    --gold:    #e0b23a;
    --gold-dim: #6e5417;
    --purple:  #a855f7;
    --purple-dim: #581c87;
    --blue:    #4aa8ff;
    --blue-dim: #1d4f80;
    --orange:  #f0883e;
    --orange-dim: #7a3f12;
    --pink:    #f472b6;
    --pink-dim: #831843;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", "Cascadia Code", Menlo, Consolas, monospace;
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    background-image:
      linear-gradient(var(--line) 1px, transparent 1px),
      linear-gradient(90deg, var(--line) 1px, transparent 1px);
    background-size: 44px 44px;
    color: var(--ink);
    font-family: var(--sans);
    min-height: 100vh;
    padding: 6vh 5vw;
  }
  .wrap { max-width: 1000px; margin: 0 auto; }
  .head { border-bottom: 1px solid var(--line); padding-bottom: 22px; margin-bottom: 34px; }
  .eyebrow {
    font-family: var(--mono);
    font-size: 12px;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--signal);
    display: flex; align-items: center; gap: 9px;
  }
  .eyebrow::before {
    content: ""; width: 8px; height: 8px; border-radius: 50%;
    background: var(--signal); box-shadow: 0 0 10px var(--signal);
  }
  h1 { font-size: clamp(28px, 5vw, 44px); font-weight: 650; letter-spacing: -0.02em; margin-top: 14px; }
  .sub { color: var(--muted); margin-top: 10px; font-size: 15px; max-width: 60ch; line-height: 1.5; }
  .sub code { font-family: var(--mono); color: var(--ink); background: var(--panel); padding: 1px 6px; border-radius: 4px; }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 14px;
  }
  .node {
    position: relative;
    display: flex; flex-direction: column;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 18px 18px 16px;
    text-decoration: none;
    color: var(--ink);
    overflow: hidden;
    transition: border-color .16s ease, transform .16s ease;
  }
  .node::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: var(--signal-dim); transition: background .16s ease;
  }
  .node:hover, .node:focus-visible {
    border-color: var(--signal);
    transform: translateY(-2px);
    outline: none;
  }
  .node:hover::before, .node:focus-visible::before { background: var(--signal); }
  .node__idx {
    font-family: var(--mono); font-size: 12px; color: var(--muted); letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .node__name { font-size: 19px; font-weight: 600; margin-top: 4px; }
  .node__topic {
    font-family: var(--mono); font-size: 13px; color: var(--signal);
    margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--line);
  }
  .node__go {
    font-family: var(--mono); font-size: 12px; color: var(--muted);
    margin-top: 10px; letter-spacing: 0.03em;
  }
  .node:hover .node__go, .node:focus-visible .node__go { color: var(--ink); }

  /* Card do professor: destaque dourado */
  .node--prof::before { background: var(--gold-dim); }
  .node--prof:hover, .node--prof:focus-visible { border-color: var(--gold); }
  .node--prof:hover::before, .node--prof:focus-visible::before { background: var(--gold); }
  .node--prof .node__topic { color: var(--gold); }

  /* Card de notas: destaque roxo */
  .node--notas::before { background: var(--purple-dim); }
  .node--notas:hover, .node--notas:focus-visible { border-color: var(--purple); }
  .node--notas:hover::before, .node--notas:focus-visible::before { background: var(--purple); }
  .node--notas .node__topic { color: var(--purple); }

  /* Card do MQTT Explorer: destaque azul */
  .node--mqtt::before { background: var(--blue-dim); }
  .node--mqtt:hover, .node--mqtt:focus-visible { border-color: var(--blue); }
  .node--mqtt:hover::before, .node--mqtt:focus-visible::before { background: var(--blue); }
  .node--mqtt .node__topic { color: var(--blue); }

  /* Card do Gitea: destaque laranja */
  .node--git::before { background: var(--orange-dim); }
  .node--git:hover, .node--git:focus-visible { border-color: var(--orange); }
  .node--git:hover::before, .node--git:focus-visible::before { background: var(--orange); }
  .node--git .node__topic { color: var(--orange); }

  /* Card do chat: destaque rosa */
  .node--chat::before { background: var(--pink-dim); }
  .node--chat:hover, .node--chat:focus-visible { border-color: var(--pink); }
  .node--chat:hover::before, .node--chat:focus-visible::before { background: var(--pink); }
  .node--chat .node__topic { color: var(--pink); }

  .foot {
    margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--line);
    font-family: var(--mono); font-size: 12px; color: var(--muted);
    display: flex; flex-wrap: wrap; gap: 6px 22px;
  }
  @media (prefers-reduced-motion: reduce) {
    .node { transition: none; }
    .node:hover, .node:focus-visible { transform: none; }
  }
</style>
</head>
<body>
  <div class="wrap">
    <header class="head">
      <div class="eyebrow">broker online &middot; {{LAB}}</div>
      <h1>Painel do {{LAB}}</h1>
      <p class="sub">Selecione seu grupo para abrir o editor Node-RED. Cada grupo
      publica no broker MQTT sob seu próprio tópico, no formato
      <code>{{LAB}}-&lt;letra&gt;/#</code>.</p>
    </header>

    <main class="grid">
{{CARDS}}    </main>

    <footer class="foot">
      {{RODAPE}}
    </footer>
  </div>
</body>
</html>
"""

cards = []
for g in todos_servicos:
    L = letra_de(g).upper()
    if is_notas(g):
        nome, classe, idx = "Painel de Notas", "node node--notas", "n"
    elif is_prof(g):
        nome, classe, idx = "Professor", "node node--prof", "p"
    else:
        nome, classe, idx = f"Grupo {L}", "node", L
    cards.append(
        f'      <a class="{classe}" href="/{g}/">\n'
        f'        <span class="node__idx">{idx}</span>\n'
        f'        <span class="node__name">{nome}</span>\n'
        f'        <span class="node__topic">{g}/#</span>\n'
        '        <span class="node__go">abrir editor &rarr;</span>\n'
        '      </a>\n')
if CHAT:
    cards.append(
        '      <a class="node node--chat" href="/chat/">\n'
        '        <span class="node__idx">chat</span>\n'
        '        <span class="node__name">Chat do lab</span>\n'
        '        <span class="node__topic">canal privado por grupo</span>\n'
        '        <span class="node__go">abrir Mattermost &rarr;</span>\n'
        '      </a>\n')
if GITEA:
    cards.append(
        '      <a class="node node--git" href="/git/">\n'
        '        <span class="node__idx">git</span>\n'
        '        <span class="node__name">Gitea</span>\n'
        f'        <span class="node__topic">{LAB}-grupo-&lt;letra&gt;</span>\n'
        '        <span class="node__go">abrir repositórios &rarr;</span>\n'
        '      </a>\n')
cards.append(
    f'      <a class="node node--mqtt" href="{MQTTX_URL}">\n'
    '        <span class="node__idx">mqtt · rede local</span>\n'
    '        <span class="node__name">MQTT Explorer</span>\n'
    '        <span class="node__topic">#  ·  broker do lab</span>\n'
    f'        <span class="node__go">abrir explorer{" (login)" if MQTTX_AUTH else ""} &rarr;</span>\n'
    '      </a>\n')

rodape = [f"<span>local: {LOCAL_URL}/</span>"]
if TUNEL:
    rodape.append(f"<span>público: {PUBLICO_URL}/</span>")
rodape += [f"<span>MQTT: {IP}:1883</span>", f"<span>tópico base: {LAB}-&lt;letra&gt;/</span>"]

html = (PORTAL_HTML
        .replace("{{CARDS}}", "".join(cards))
        .replace("{{RODAPE}}", "\n      ".join(rodape))
        .replace("{{LAB}}", LAB))
gravar("nginx/html/index.html", html)
print("🏠 nginx/html/index.html")

# =====================================================================
# mqtt-explorer/data/settings.json
# =====================================================================
conn_id = "-".join(secrets.token_hex(k) for k in (4, 2, 2, 2, 6))
mqttx_settings = {
    "ConnectionManager_connections": {
        conn_id: {
            "configVersion": 1, "certValidation": False,
            "clientId": f"mqtt-explorer-{secrets.token_hex(4)}",
            "id": conn_id, "name": f"{LAB} (mosquitto)", "encryption": False,
            "subscriptions": [{"topic": "#", "qos": 0}, {"topic": "$SYS/#", "qos": 0}],
            "type": "mqtt", "host": "mosquitto", "port": 1883, "protocol": "mqtt",
        }
    },
    "Settings": {
        "timeLocale": "pt-BR", "topicOrder": "none", "highlightTopicUpdates": True,
        "valueRendererDisplayMode": "diff", "selectTopicWithMouseOver": False, "theme": "light",
    },
}
gravar("mqtt-explorer/data/settings.json", json.dumps(mqttx_settings, indent=2, ensure_ascii=False))
print("🔭 mqtt-explorer/data/settings.json")

# =====================================================================
# gitea/init/gitea-init.sh
# =====================================================================
GITEA_INIT_TPL = r"""#!/bin/bash
# gitea-init.sh — gerado por gen_iot_portal.py (lab __TURMA__)
# Cria/atualiza no Gitea os usuarios de credenciais.txt, uma organizacao por grupo,
# os times e o repositorio inicial. Idempotente: pode rodar quantas vezes quiser
# (senhas existentes sao re-sincronizadas com credenciais.txt).
#   Rodar de novo:  docker compose run --rm gitea-init
set -u
BASE=http://gitea:3000
API=$BASE/api/v1
ADMIN_USER="__ADMIN_USER__"
ADMIN_PASS="__ADMIN_PASS__"
ADMIN_EMAIL="__ADMIN_EMAIL__"
REPO="__REPO__"
UNITS='"units":["repo.code","repo.issues","repo.pulls","repo.releases","repo.wiki","repo.projects"]'

log() { echo "[gitea-init] $*"; }

api() {  # api METODO CAMINHO [JSON]  -> imprime o HTTP status; corpo em /tmp/resp
  local a=(-sS -o /tmp/resp -w '%{http_code}' -u "$ADMIN_USER:$ADMIN_PASS"
           -H 'Content-Type: application/json' -X "$1" "$API$2")
  [ -n "${3:-}" ] && a+=(-d "$3")
  curl "${a[@]}"
}

log "aguardando o Gitea..."
for i in $(seq 1 90); do
  curl -fsS "$BASE/api/healthz" >/dev/null 2>&1 && break
  sleep 2
done

# ---- administrador (professor) via CLI ----
if su-exec git gitea admin user list --admin 2>/dev/null | awk 'NR>1{print $2}' | grep -qx "$ADMIN_USER"; then
  log "admin $ADMIN_USER ja existe: sincronizando senha"
  su-exec git gitea admin user change-password --username "$ADMIN_USER" --password "$ADMIN_PASS" \
      --must-change-password=false 2>/dev/null \
    || su-exec git gitea admin user change-password --username "$ADMIN_USER" --password "$ADMIN_PASS"
else
  log "criando admin $ADMIN_USER"
  su-exec git gitea admin user create --admin --username "$ADMIN_USER" --password "$ADMIN_PASS" \
      --email "$ADMIN_EMAIL" --must-change-password=false
fi
api PATCH "/admin/users/$ADMIN_USER" \
  "{\"login_name\":\"$ADMIN_USER\",\"source_id\":0,\"must_change_password\":false}" >/dev/null

ensure_user() {  # usuario senha email nome
  local code
  code=$(api POST /admin/users "{\"username\":\"$1\",\"password\":\"$2\",\"email\":\"$3\",\"full_name\":\"$4\",\"must_change_password\":false}")
  if [ "$code" = 201 ]; then log "usuario $1 criado"
  else
    code=$(api PATCH "/admin/users/$1" "{\"login_name\":\"$1\",\"source_id\":0,\"password\":\"$2\",\"must_change_password\":false}")
    log "usuario $1 ja existe: senha sincronizada (HTTP $code)"
  fi
}

ensure_org() {  # org nome_completo
  local code
  code=$(api POST /orgs "{\"username\":\"$1\",\"full_name\":\"$2\",\"visibility\":\"private\",\"repo_admin_change_team_access\":false}")
  [ "$code" = 201 ] && log "organizacao $1 criada" || log "organizacao $1 ja existe (HTTP $code)"
}

ensure_team() {  # org time permissao(read|write) membro
  local id code create=false
  [ "$3" = write ] && create=true
  api GET "/orgs/$1/teams/search?q=$2" >/dev/null
  id=$(grep -o '"id":[0-9]*' /tmp/resp | head -1 | cut -d: -f2)
  if [ -z "$id" ]; then
    api POST "/orgs/$1/teams" "{\"name\":\"$2\",\"permission\":\"$3\",\"includes_all_repositories\":true,\"can_create_org_repo\":$create,$UNITS,\"units_map\":{\"repo.code\":\"$3\",\"repo.issues\":\"$3\",\"repo.pulls\":\"$3\",\"repo.releases\":\"$3\",\"repo.wiki\":\"$3\",\"repo.projects\":\"$3\"}}" >/dev/null
    id=$(grep -o '"id":[0-9]*' /tmp/resp | head -1 | cut -d: -f2)
    log "time $1/$2 ($3) criado"
  fi
  if [ -n "$id" ]; then
    code=$(api PUT "/teams/$id/members/$4")
    log "  $4 -> $1/$2 (HTTP $code)"
  else
    log "  ERRO ao criar time $1/$2: $(cat /tmp/resp)"
  fi
}

ensure_repo() {  # org repo
  [ -z "$2" ] && return
  local code
  code=$(api POST "/orgs/$1/repos" "{\"name\":\"$2\",\"auto_init\":true,\"private\":true,\"default_branch\":\"main\",\"readme\":\"Default\",\"description\":\"Projeto Node-RED do $1\"}")
  [ "$code" = 201 ] && log "repositorio $1/$2 criado" || log "repositorio $1/$2 ja existe (HTTP $code)"
}

# ---- usuarios, organizacoes e times ----
__CORPO__
log "concluido."
"""

if GITEA:
    corpo = [f'ensure_user "{notas_service}" "{SENHA[notas_service]}" '
             f'"{notas_service}@{DOMINIO}" "Avaliador {LAB}"']
    for g in grupos_alunos:
        org, L = org_de(g), letra_de(g).upper()
        corpo += [
            "",
            f"# ---- {g} -> organizacao {org}",
            f'ensure_user "{g}" "{SENHA[g]}" "{g}@{DOMINIO}" "Grupo {L} ({LAB})"',
            f'ensure_org  "{org}" "Grupo {L} - {LAB}"',
            f'ensure_team "{org}" "grupo" write "{g}"',
            f'ensure_team "{org}" "avaliacao" read "{notas_service}"',
            f'ensure_repo "{org}" "$REPO"',
        ]
    gravar("gitea/init/gitea-init.sh",
           GITEA_INIT_TPL
           .replace("__TURMA__", LAB)
           .replace("__ADMIN_USER__", prof)
           .replace("__ADMIN_PASS__", SENHA[prof])
           .replace("__ADMIN_EMAIL__", f"{prof}@{DOMINIO}")
           .replace("__REPO__", GITEA_REPO)
           .replace("__CORPO__", "\n".join(corpo)), executavel=True)
    print("🐙 gitea/init/gitea-init.sh")

# =====================================================================
# postgres/init/bancos.sql (idempotente; roda a cada subida no db-init)
# =====================================================================
if POSTGRES:
    sql = ["-- bancos.sql — gerado por gen_iot_portal.py",
           "-- Idempotente: cria usuários/bancos que faltarem e re-sincroniza as senhas.", ""]
    bancos = []
    if GITEA_PG:
        bancos.append(("gitea", PG_GITEA_SENHA,
                       "ENCODING ''UTF8'' LC_COLLATE ''C'' LC_CTYPE ''C'' TEMPLATE template0"))
    if CHAT:
        bancos.append(("mattermost", PG_MM_SENHA, "ENCODING ''UTF8'' TEMPLATE template0"))
    for nome, senha, opts in bancos:
        sql += [
            f"-- {nome}",
            f"SELECT 'CREATE ROLE {nome} LOGIN' WHERE NOT EXISTS "
            f"(SELECT FROM pg_roles WHERE rolname = '{nome}')\\gexec",
            f"ALTER ROLE {nome} WITH LOGIN PASSWORD '{senha}';",
            f"SELECT 'CREATE DATABASE {nome} OWNER {nome} {opts}' WHERE NOT EXISTS "
            f"(SELECT FROM pg_database WHERE datname = '{nome}')\\gexec",
            "",
        ]
    gravar("postgres/init/bancos.sql", "\n".join(sql))
    print("🐘 postgres/init/bancos.sql")

# =====================================================================
# mattermost/init (Dockerfile + mattermost-init.sh)
# =====================================================================
MM_INIT_DOCKERFILE = """# Imagem auxiliar: a imagem oficial do Mattermost nao tem shell (distroless),
# entao copiamos o mmctl dela para um Debian minimo com bash.
ARG MM_IMAGE=mattermost/mattermost-team-edition:release-11
FROM ${MM_IMAGE} AS mm
FROM debian:bookworm-slim
COPY --from=mm /mattermost/bin/mmctl /usr/local/bin/mmctl
"""

MM_INIT_TPL = r"""#!/bin/bash
# mattermost-init.sh — gerado por gen_iot_portal.py (lab __TURMA__)
# Cria/atualiza no Mattermost: equipe do lab, usuarios de credenciais.txt,
# canal publico de avisos e um canal PRIVADO por grupo (grupo + professor).
# Idempotente: o que existe e mantido; senhas sao re-sincronizadas.
#   Rodar de novo:  docker compose run --rm mattermost-init
set -u
M="mmctl --local --suppress-warnings"
TEAM="__TEAM__"

log() { echo "[mattermost-init] $*"; }

log "aguardando o Mattermost..."
for i in $(seq 1 100); do
  $M system status >/dev/null 2>&1 && break
  sleep 3
done

# equipe do lab (privada: so entra quem o script adicionar)
if out=$($M team create --name "$TEAM" --display-name "__TEAM_DISPLAY__" --private 2>&1); then
  log "equipe $TEAM criada"
else
  log "equipe $TEAM ja existe"
fi

ensure_user() {  # usuario senha email apelido [admin]
  local out
  if out=$($M user create --username "$1" --password "$2" --email "$3" --nickname "$4" \
             --email-verified --disable-welcome-email 2>&1); then
    log "usuario $1 criado"
  else
    $M user change-password "$1" --password "$2" >/dev/null 2>&1 \
      && log "usuario $1 ja existe: senha sincronizada" \
      || log "  ERRO com usuario $1: $out"
  fi
  [ "${5:-}" = admin ] && $M roles system-admin "$1" >/dev/null 2>&1
  $M team users add "$TEAM" "$1" >/dev/null 2>&1
}

ensure_channel() {  # nome nome_exibicao privado(sim|nao) proposito membros...
  local nome="$1" disp="$2" priv="$3" prop="$4"; shift 4
  local flag=""; [ "$priv" = sim ] && flag="--private"
  if $M channel create --team "$TEAM" --name "$nome" --display-name "$disp" \
        --purpose "$prop" $flag >/dev/null 2>&1; then
    log "canal $nome criado"
  fi
  if [ $# -gt 0 ]; then
    $M channel users add "$TEAM:$nome" "$@" >/dev/null 2>&1 \
      && log "  membros de $nome: $*" \
      || log "  membros de $nome ja estavam no canal (ou erro)"
  fi
}

# ---- usuarios ----
__USUARIOS__

# ---- canais ----
__CANAIS__
log "concluido."
"""

if CHAT:
    usuarios = [f'ensure_user "{prof}" "{SENHA[prof]}" "{prof}@{DOMINIO}" "Professor" admin']
    for g in grupos_alunos:
        usuarios.append(f'ensure_user "{g}" "{SENHA[g]}" "{g}@{DOMINIO}" "Grupo {letra_de(g).upper()}"')
    todos_chat = " ".join(f'"{u}"' for u in [prof] + grupos_alunos)
    canais = [f'ensure_channel "avisos" "Avisos" nao "Avisos do professor para o lab" {todos_chat}']
    for g in grupos_alunos:
        L = letra_de(g).upper()
        canais.append(f'ensure_channel "{g}" "Grupo {L} (privado)" sim '
                      f'"Conversa privada entre o grupo {L} e o professor" "{g}" "{prof}"')
    gravar("mattermost/init/mattermost-init.sh",
           MM_INIT_TPL
           .replace("__TURMA__", LAB)
           .replace("__TEAM__", CHAT_TEAM)
           .replace("__TEAM_DISPLAY__", LAB.upper())
           .replace("__USUARIOS__", "\n".join(usuarios))
           .replace("__CANAIS__", "\n".join(canais)), executavel=True)
    gravar("mattermost/init/Dockerfile", MM_INIT_DOCKERFILE)
    print("💬 mattermost/init/")

# =====================================================================
# tunel/ (cliente do túnel SSH reverso, roda no laboratório)
# =====================================================================
TUNEL_DOCKERFILE = """FROM alpine:3.20
RUN apk add --no-cache openssh-client bash
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
"""

TUNEL_ENTRYPOINT = r"""#!/bin/bash
# entrypoint.sh do túnel — gerado por gen_iot_portal.py
# Mantém o túnel SSH reverso:  VPS 127.0.0.1:$PORTA_REMOTA  ->  $DESTINO (nginx do lab)
#   Ver a chave pública:  docker compose run --rm --no-deps --build tunel chave
set -u
CH=/chave/id_ed25519
mkdir -p /chave ~/.ssh
if [ ! -f "$CH" ]; then
  ssh-keygen -q -t ed25519 -N "" -C "tunel-iot-lab" -f "$CH"
  echo "[tunel] chave nova gerada em tunel/chave/"
fi
# Windows/NTFS: o arquivo montado aparece com permissões abertas e o ssh o recusaria
install -m 600 "$CH" ~/.ssh/id_ed25519

if [ "${1:-}" = chave ]; then
  echo "[tunel] chave pública (vai para o VPS como id_ed25519.pub):"
  cat "$CH.pub"
  exit 0
fi

echo "[tunel] chave pública: $(cat "$CH.pub")"
while true; do
  echo "[tunel] conectando $VPS_USUARIO@$VPS_HOST:$VPS_PORTA  (VPS 127.0.0.1:$PORTA_REMOTA -> $DESTINO)"
  ssh -N -T \
      -i ~/.ssh/id_ed25519 -p "$VPS_PORTA" \
      -o StrictHostKeyChecking=accept-new \
      -o UserKnownHostsFile=/chave/known_hosts \
      -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
      -o ConnectTimeout=15 \
      -R "127.0.0.1:${PORTA_REMOTA}:${DESTINO}" \
      "$VPS_USUARIO@$VPS_HOST"
  echo "[tunel] conexão encerrada (código $?); nova tentativa em 10 s"
  sleep 10
done
"""

# =====================================================================
# vps/ (vai para o VPS: proxy do Apache, página offline e setup)
# =====================================================================
VPS_PROXY_CONF = """# iot-lab — proxy do Apache para o túnel do laboratório (gerado por gen_iot_portal.py)
# Incluído DENTRO do <VirtualHost *:443> de __HOST__ pelo setup-vps.sh.
ProxyRequests Off
ProxyPreserveHost On
ProxyTimeout 3600
AllowEncodedSlashes NoDecode
RequestHeader set X-Forwarded-Proto "https"
RequestHeader set X-Forwarded-Port "443"
Header always set X-Robots-Tag "noindex, nofollow"

# Ficam no próprio VPS: validação do certbot e a página "laboratório desligado"
ProxyPass /.well-known/acme-challenge/ !
ProxyPass /lab-offline.html !
Alias /lab-offline.html /var/www/iot-lab/lab-offline.html
<Directory /var/www/iot-lab>
    Require all granted
</Directory>
ErrorDocument 502 /lab-offline.html
ErrorDocument 503 /lab-offline.html

# Todo o resto vai para o túnel (portal, Node-RED, Gitea, chat), com WebSocket.
# nocanon + AllowEncodedSlashes: o Gitea precisa receber %2F e afins sem alteração.
ProxyPass        / http://127.0.0.1:__PORTA__/ upgrade=websocket nocanon retry=0 timeout=3600
ProxyPassReverse / http://127.0.0.1:__PORTA__/
"""

VPS_OFFLINE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="30">
<title>Laboratório desligado · __LAB__</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center;
         background: #071311; color: #dcf5ec;
         font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 34rem; padding: 2rem; }
  .tag { font-family: ui-monospace, Consolas, monospace; font-size: 12px; letter-spacing: .2em;
         text-transform: uppercase; color: #e0b23a; }
  h1 { font-size: 1.8rem; margin: .6rem 0; }
  p { color: #6f9a8d; line-height: 1.55; }
</style>
</head>
<body>
<main>
  <div class="tag">__LAB__ · offline</div>
  <h1>O laboratório está desligado no momento</h1>
  <p>O servidor do laboratório não está conectado. Isso é normal fora do horário das aulas.
  Esta página tenta de novo sozinha a cada 30 segundos.</p>
  <p>Na rede do laboratório, use o endereço local informado pelo professor.</p>
</main>
</body>
</html>
"""

VPS_SETUP = r"""#!/bin/bash
# setup-vps.sh — gerado por gen_iot_portal.py
# Prepara o VPS para publicar o laboratório em https://__HOST__/
#   Uso:  sudo bash setup-vps.sh caminho/id_ed25519.pub
# Idempotente: pode rodar de novo (ex.: para trocar a chave).
set -euo pipefail
DOMINIO="__HOST__"
USUARIO="__USUARIO__"
PORTA="__PORTA__"
DIR="$(cd "$(dirname "$0")" && pwd)"
PUB="${1:-}"
log()  { echo "[setup-vps] $*"; }
erro() { echo "[setup-vps] ERRO: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || erro "rode com sudo."
[ -n "$PUB" ] && [ -f "$PUB" ] || erro "uso: sudo bash $0 caminho/id_ed25519.pub"
grep -q '^ssh-ed25519 ' "$PUB" || erro "$PUB não parece uma chave pública ed25519."
command -v apache2ctl >/dev/null || erro "Apache (apache2) não encontrado."

# ---- 1) usuário restrito do túnel: só pode abrir 127.0.0.1:$PORTA, sem shell ----
if ! id "$USUARIO" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "$USUARIO"
  log "usuário $USUARIO criado"
fi
usermod -p '*' "$USUARIO"          # sem senha, mas não "bloqueado" (login só por chave)
H="$(getent passwd "$USUARIO" | cut -d: -f6)"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$H/.ssh"
printf 'restrict,port-forwarding,permitlisten="127.0.0.1:%s" %s\n' "$PORTA" "$(head -1 "$PUB")" \
  > "$H/.ssh/authorized_keys"
chown "$USUARIO:$USUARIO" "$H/.ssh/authorized_keys"
chmod 600 "$H/.ssh/authorized_keys"
log "chave do túnel autorizada (só 127.0.0.1:$PORTA)"

# ---- 2) sshd: regras para o usuário do túnel ----
cat > /etc/ssh/sshd_config.d/60-iot-lab.conf <<EOF
# gerado por setup-vps.sh (iot-lab)
Match User $USUARIO
    AllowTcpForwarding remote
    GatewayPorts no
    X11Forwarding no
    AllowAgentForwarding no
    PermitTTY no
    ClientAliveInterval 15
    ClientAliveCountMax 3
EOF
sshd -t || erro "configuração do sshd inválida (veja /etc/ssh/sshd_config.d/60-iot-lab.conf)"
if sshd -T -C "user=$USUARIO,host=lab,addr=192.0.2.1" 2>/dev/null | grep -qi '^allowusers '; then
  log "ATENÇÃO: o sshd usa AllowUsers; inclua '$USUARIO' nessa lista ou o túnel será recusado."
fi
systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || service ssh reload || true
log "sshd recarregado"

# ---- 3) Apache: módulos, arquivos e Include no VirtualHost 443 ----
a2enmod -q proxy proxy_http proxy_wstunnel headers ssl alias >/dev/null
install -D -m 644 "$DIR/proxy.conf"       /etc/apache2/iot-lab/proxy.conf
install -D -m 644 "$DIR/lab-offline.html" /var/www/iot-lab/lab-offline.html

# Cada editor Node-RED, dashboard e chat aberto mantém um WebSocket = 1 thread do Apache.
# MPM event: até 400 conexões simultâneas com pouca memória (8 processos x 50 threads).
MPM="$(apache2ctl -V 2>/dev/null | awk -F': *' '/Server MPM/ {print $2}' | tr -d ' ')"
if [ "$MPM" = "event" ]; then
  cat > /etc/apache2/conf-available/iot-lab-mpm.conf <<'EOF2'
# gerado por setup-vps.sh (iot-lab): mais conexões simultâneas (WebSockets)
<IfModule mpm_event_module>
    ServerLimit            8
    ThreadsPerChild       50
    MaxRequestWorkers    400
    MaxConnectionsPerChild 0
</IfModule>
EOF2
  a2enconf -q iot-lab-mpm >/dev/null
  log "MPM event: limite de conexões simultâneas ajustado para 400"
else
  log "ATENÇÃO: o Apache usa o MPM '${MPM:-?}'. Com 'prefork' (comum com mod_php) cada"
  log "  WebSocket ocupa um processo inteiro e 1 GB de RAM não aguenta a turma."
  log "  Recomendado: PHP-FPM + MPM event (a2dismod php* mpm_prefork; a2enmod mpm_event proxy_fcgi)."
fi

VH=""
for f in /etc/apache2/sites-enabled/*; do
  [ -e "$f" ] || continue
  if grep -qE "ServerName[[:space:]]+$DOMINIO([[:space:]]|$)" "$f" && grep -q ':443' "$f"; then
    VH="$(readlink -f "$f")"; break
  fi
done
[ -n "$VH" ] || erro "não achei o VirtualHost *:443 de $DOMINIO em sites-enabled.
  Gere o certificado antes:  sudo certbot --apache -d $DOMINIO   e rode este script de novo."
log "VirtualHost HTTPS: $VH"

BKP=""
if ! grep -q '/etc/apache2/iot-lab/proxy.conf' "$VH"; then
  BKP="$VH.bak-iot-lab-$(date +%Y%m%d%H%M%S)"
  cp -a "$VH" "$BKP"
  python3 - "$VH" "$DOMINIO" <<'PY'
import re, sys
caminho, dominio = sys.argv[1], sys.argv[2]
s = open(caminho, encoding="utf-8").read()
for m in re.finditer(r"<VirtualHost[^>]*:443[^>]*>.*?</VirtualHost>", s, re.S):
    if re.search(r"ServerName\s+" + re.escape(dominio) + r"(\s|$)", m.group(0)):
        fim = m.end() - len("</VirtualHost>")
        s = s[:fim] + "    Include /etc/apache2/iot-lab/proxy.conf\n" + s[fim:]
        open(caminho, "w", encoding="utf-8").write(s)
        sys.exit(0)
sys.exit(2)
PY
  log "Include inserido (backup: $BKP)"
else
  log "Include já presente"
fi

if ! apache2ctl configtest; then
  [ -n "$BKP" ] && cp -a "$BKP" "$VH" && log "configuração revertida a partir do backup"
  erro "apache2ctl configtest falhou."
fi
systemctl reload apache2 2>/dev/null || apache2ctl graceful
log "Apache recarregado"

# ---- 4) teste ----
codigo="$(curl -sk -o /dev/null -w '%{http_code}' --resolve "$DOMINIO:443:127.0.0.1" "https://$DOMINIO/" || true)"
case "$codigo" in
  200) log "OK: https://$DOMINIO/ já responde pelo túnel." ;;
  502|503) log "OK: Apache pronto; o túnel ainda não está conectado (página 'laboratório desligado')." ;;
  *) log "Resposta inesperada de https://$DOMINIO/: HTTP $codigo" ;;
esac
log "concluído. No laboratório:  docker compose up -d   e   docker compose logs -f tunel"
"""

if TUNEL:
    gravar("tunel/Dockerfile", TUNEL_DOCKERFILE)
    gravar("tunel/entrypoint.sh", TUNEL_ENTRYPOINT, executavel=True)
    os.makedirs("tunel/chave", exist_ok=True)
    gravar("vps/proxy.conf", VPS_PROXY_CONF.replace("__HOST__", PUBLIC_HOST)
           .replace("__PORTA__", str(VPS_PORTA_TUNEL)))
    gravar("vps/lab-offline.html", VPS_OFFLINE_HTML.replace("__LAB__", LAB))
    gravar("vps/setup-vps.sh", VPS_SETUP.replace("__HOST__", PUBLIC_HOST)
           .replace("__USUARIO__", args.vps_usuario).replace("__PORTA__", str(VPS_PORTA_TUNEL)),
           executavel=True)
    print("🔐 tunel/  e  🌍 vps/ (proxy.conf, lab-offline.html, setup-vps.sh)")

# =====================================================================
# .segredos.json
# =====================================================================
gravar(ARQ_SEGREDOS, json.dumps(SEGREDOS, indent=2))
try:
    os.chmod(ARQ_SEGREDOS, 0o600)
except OSError:
    pass

# =====================================================================
# credenciais.txt
# =====================================================================
def bases():
    b = [("local (rede do lab)", LOCAL_URL)]
    if TUNEL:
        b.append(("público (VPS)", PUBLICO_URL))
    return b


L_ = []
L_.append(f"=== CREDENCIAIS {LAB.upper()} ===\n")
L_.append(f"{'USUÁRIO':<13} | {'SENHA':<10} | {'USUÁRIO VIEW':<15} | {'SENHA VIEW':<10}")
L_.append("-" * 58)
for u, s, uv, sv in credenciais_geradas:
    L_.append(f"{u:<13} | {s:<10} | {uv:<15} | {sv:<10}")
L_.append("\nA mesma senha do grupo vale para Node-RED, Gitea e chat.")
L_.append("\n=== ENDEREÇOS ===")
for rot, b in bases():
    L_.append(f"[{rot}]  portal: {b}/")
L_.append("")
for g in todos_servicos:
    L_.append(f"{g:<13} " + "   ".join(f"{b}/{g}/" for _r, b in bases()))
if GITEA:
    L_.append(f"{'gitea':<13} " + "   ".join(f"{b}/git/" for _r, b in bases()))
if CHAT:
    L_.append(f"{'chat':<13} " + "   ".join(f"{b}/chat/" for _r, b in bases()))
L_.append(f"{'mqtt-explorer':<13} {MQTTX_URL}   (só na rede local)")
L_.append(f"{'MQTT broker':<13} {IP}:1883   (só na rede local)")
if GITEA:
    L_.append("\n=== GITEA ===")
    L_.append(f"{prof} = administrador · {notas_service} = leitura em todas as organizações")
    for g in grupos_alunos:
        extra = f"   repo: {org_de(g)}/{GITEA_REPO}" if GITEA_REPO else ""
        L_.append(f"{g:<13} -> org {org_de(g)}{extra}")
    if GITEA_REPO:
        L_.append(f"Dentro do Node-RED (Projects): http://gitea:3000/<org>/{GITEA_REPO}.git")
if CHAT:
    L_.append("\n=== CHAT (Mattermost) ===")
    L_.append(f"{prof} = administrador · equipe {CHAT_TEAM} · canal 'avisos' + "
              f"canal privado por grupo ({grupos_alunos[0]} .. {grupos_alunos[-1]})")
L_.append("\n=== MQTT EXPLORER ===")
L_.append(f"Usuário: {MQTTX_USER}  ·  Senha: {MQTTX_SENHA}" if MQTTX_AUTH else "Acesso sem login")
if POSTGRES:
    L_.append("\n=== POSTGRESQL (interno; só para o professor) ===")
    L_.append(f"postgres: {PG_ROOT_SENHA}")
    if GITEA_PG:
        L_.append(f"gitea:      {PG_GITEA_SENHA}")
    if CHAT:
        L_.append(f"mattermost: {PG_MM_SENHA}")
gravar("credenciais.txt", "\n".join(L_) + "\n")

# =====================================================================
# relatório
# =====================================================================
print(f"\n✅ {LAB}: {N} grupos ({grupos_alunos[0]}..{grupos_alunos[-1]}) + "
      f"professor ({prof}) + notas ({notas_service})")
print(f"\n  Local:   {LOCAL_URL}/")
if TUNEL:
    print(f"  Público: {PUBLICO_URL}/   (túnel SSH -> Apache do VPS {VPS_HOST})")
print(f"  Grupo A: <base>/{grupos_alunos[0]}/   ·   Gitea: <base>/git/   ·   Chat: <base>/chat/")
print(f"  MQTT Explorer: {MQTTX_URL}   ·   MQTT: {IP}:1883  (rede local)")
print("\n🔒 Senhas em credenciais.txt " +
      ("(NOVAS para todos)" if args.novas_senhas else "(mantidas de execuções anteriores, se houver)"))
if IP.startswith("127."):
    print("\n⚠️  --ip é 127.x: alunos na rede não acessam o servidor. Use o IP real (ipconfig).")
if TUNEL:
    print("\n🌍 Publicação em " + PUBLICO_URL + " — passos (uma vez):")
    print("   1) docker compose run --rm --no-deps --build tunel chave   (gera e mostra a chave)")
    print(f"   2) scp -r vps tunel/chave/id_ed25519.pub <seu-usuario>@{VPS_HOST}:~/iot-lab/")
    print("   3) no VPS:  sudo bash ~/iot-lab/vps/setup-vps.sh ~/iot-lab/id_ed25519.pub")
    print("   4) docker compose up -d --build")
print(f"\n📂 {SAIDA_ABS}")
print(f"▶  cd {SAIDA_ABS}  e  docker compose up -d --build")
