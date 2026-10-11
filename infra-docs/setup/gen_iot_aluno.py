#!/usr/bin/env python3
"""Gera o LAB IoT COMPLETO na máquina do aluno, sem servidor do laboratório e sem VPS.

Derivado do gen_iot_scada_portal.py (o do laboratório): os mesmos serviços, caminhos e nomes,
para UMA conta (o aluno ou o grupo). Fica só nesta máquina e na rede local (sem túnel, sem VPS).

    <base>/                portal
    <base>/lab05-a/        Node-RED            (dashboard em /lab05-a/dashboard)
    <base>/fuxa/lab05-a/   FUXA (SCADA/HMI)
    <base>/git/            Gitea + Gitea Actions (runner na sua máquina)
    <base>/ntfy/           ntfy (notificações push; app no celular)
    <base>/avisos/         página web do ntfy (ler e publicar)
    <base>/bin/            MicroBin (colar código e enviar arquivos)
    http://localhost:3001  MQTT Explorer (só nesta máquina / rede local)
    <IP-da-máquina>:1883   broker MQTT (Mosquitto) para o ESP32 na mesma rede

onde <base> é:
    - nesta máquina:          http://localhost
    - na mesma rede (Wi-Fi):  http://<IP-da-máquina>   (celular, ESP32, outro PC)

Mesmos caminhos e nomes do laboratório: um fluxo do Node-RED ou uma tela do FUXA feitos aqui
funcionam no LAB IoT sem mudar nada (e vice-versa).

Uso (Windows: "py"; Linux/macOS: "python3"):
  py gen_iot_aluno.py --lab lab05 --grupo a
  py gen_iot_aluno.py --lab lab05 --grupo a --porta-http 8080   # se a porta 80 estiver ocupada
  py gen_iot_aluno.py --segredos ..\\lab05\\.segredos.json       # mesma senha do grupo no laboratório
  py gen_iot_aluno.py --ponte-mqtt 192.168.0.10                  # liga o MQTT ao broker do laboratório
  cd lab05-a  e  docker compose up -d --build

Requisitos: Docker Desktop (Windows/macOS) ou Docker Engine (Linux); Python 3 com "pip install bcrypt".
Para o Gitea pela linha de comando: git e tea (cliente oficial do Gitea).

Rodar de novo é seguro: as senhas ficam em .segredos.json (reaproveitadas) e os dados em data/,
fuxa/ e nos volumes do Docker não são tocados.
"""
import sys, os, re, secrets, string, argparse, json, base64, hashlib, socket
from urllib.parse import urlparse
import bcrypt

for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ap = argparse.ArgumentParser(description="Gera o LAB IoT completo na máquina do aluno (sem servidor e sem VPS).")
ap.add_argument("--lab", default="lab05", help="Nome do lab (ex.: lab05); prefixo de tudo, como no laboratório")
ap.add_argument("--grupo", default="a", help="Letra do grupo (ex.: a ou lab05-a): a conta vira <lab>-<letra>")
ap.add_argument("--ip", default="auto",
                help="IP desta máquina na rede local (ESP32, celular); 'auto' descobre sozinho")
ap.add_argument("--porta-http", type=int, default=80,
                help="Porta do portal nesta máquina (padrão 80; use 8080 se a 80 estiver ocupada)")
ap.add_argument("--saida", default=None, help="Pasta de saída (padrão: <lab>-<letra>)")
ap.add_argument("--segredos", default=None,
                help=".segredos.json do laboratório: reaproveita a senha e o credentialSecret do grupo")
ap.add_argument("--novas-senhas", action="store_true", help="Sorteia senhas novas")
ap.add_argument("--dominio", default="iot.lab", help="Domínio dos e-mails das contas (só no Gitea)")
ap.add_argument("--proteger-http", action="store_true",
                help="Exige login nos dashboards e endpoints HTTP do Node-RED e para ver o FUXA "
                     "(útil se outras pessoas usam a mesma rede)")
# serviços
ap.add_argument("--sem-gitea", action="store_true", help="Não inclui o Gitea (nem o CI)")
ap.add_argument("--gitea-repo", default="nodered", help="Repositório inicial na organização ('' = nenhum)")
ap.add_argument("--gitea-db", choices=["sqlite", "postgres"], default="sqlite",
                help="Banco do Gitea (padrão sqlite: mais leve; postgres como no laboratório)")
ap.add_argument("--sem-runner", action="store_true", help="Gitea sem Actions (sem runner)")
ap.add_argument("--runner-capacidade", type=int, default=1,
                help="Jobs simultâneos no runner (padrão 1; cada job de ESP32 usa ~1 CPU e 2 GB)")
ap.add_argument("--runner-imagem", default="docker.io/gitea/runner:3-dind",
                help="Imagem do runner (Docker-in-Docker)")
ap.add_argument("--ci-rede", choices=["nginx", "ip"], default="nginx",
                help="Como os jobs do CI chegam ao Gitea: 'nginx' (padrão: o runner divide a rede do nginx "
                     "e tudo usa http://localhost) ou 'ip' (como no laboratório: http://<IP-da-máquina>; "
                     "muda se a máquina trocar de rede)")
ap.add_argument("--wokwi-token", default=None,
                help="Seu token do Wokwi CI: vira o secret WOKWI_CLI_TOKEN da organização ('-' remove)")
ap.add_argument("--sem-microbin", action="store_true", help="Não inclui o MicroBin (/bin/)")
ap.add_argument("--sem-fuxa", action="store_true", help="Não inclui o FUXA")
ap.add_argument("--sem-ntfy", action="store_true", help="Não inclui o ntfy (/ntfy/ e /avisos/)")
ap.add_argument("--sem-mqtt-explorer", action="store_true", help="Não inclui o MQTT Explorer")
ap.add_argument("--ponte-mqtt", default=None, metavar="HOST[:PORTA]",
                help="Liga (bridge) o broker desta máquina ao do laboratório, só com os tópicos do grupo")
ap.add_argument("--mqtt-explorer-porta", type=int, default=3001, help="Porta do MQTT Explorer")
args = ap.parse_args()

LAB = args.lab.lower()
if not re.fullmatch(r"[a-z][a-z0-9]{1,20}", LAB):
    sys.exit("--lab deve começar com letra e ter só letras/dígitos (ex.: lab05).")
_k = args.grupo.lower()
_k = _k[len(LAB) + 1:] if _k.startswith(LAB + "-") else _k
if not re.fullmatch(r"[a-z]", _k) or _k in ("p", "n"):
    sys.exit("--grupo deve ser a letra de um grupo (a..z, sem 'p' e 'n'), ex.: a ou lab05-a.")
G = f"{LAB}-{_k}"                    # a conta: usuário, caminho, tópicos, containers
KIT = G                              # (nome usado nos trechos herdados do gerador do laboratório)
DOMINIO = args.dominio


def ip_local():
    """IP desta máquina na rede local (sem enviar pacotes: só consulta a rota)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


IP = ip_local() if args.ip == "auto" else args.ip

# segredos do laboratório (lidos antes de mudar para a pasta de saída)
SEGREDOS_LAB = {}
if args.segredos:
    try:
        with open(args.segredos, encoding="utf-8") as _f:
            _lab_seg = json.load(_f)
        SEGREDOS_LAB = {k: v for k, v in _lab_seg.items()
                        if k in (f"senha:{G}", f"senha:{G}-view", f"credential_secret:{G}")}
        if not SEGREDOS_LAB:
            print(f"⚠️  {args.segredos} não tem a conta {G}: senhas novas")
    except (OSError, ValueError) as e:
        sys.exit(f"--segredos: não consegui ler {args.segredos} ({e})")

SAIDA = args.saida or G
os.makedirs(SAIDA, exist_ok=True)
os.chdir(SAIDA)
SAIDA_ABS = os.getcwd()

ARQ_SEGREDOS = ".segredos.json"
try:
    with open(ARQ_SEGREDOS, encoding="utf-8") as _f:
        SEGREDOS = json.load(_f)
except (OSError, ValueError):
    SEGREDOS = {}
if SEGREDOS_LAB and not args.novas_senhas:
    SEGREDOS.update(SEGREDOS_LAB)


def segredo(nome, gerar, renovar=False):
    """Valor guardado em .segredos.json; só é gerado na primeira vez (ou se renovar)."""
    if renovar or nome not in SEGREDOS:
        SEGREDOS[nome] = gerar()
    return SEGREDOS[nome]


def gerar_senha(tamanho=8):
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))


# versões antigas deste gerador tinham ngrok: some com o token e a configuração antigos
for _k in ("ngrok_authtoken", "ngrok_dominio"):
    SEGREDOS.pop(_k, None)
if os.path.isdir("ngrok"):
    import shutil
    shutil.rmtree("ngrok", ignore_errors=True)
    print("🧹 ngrok/ removido (o ngrok não é mais usado; pare o container antigo com: docker compose up -d --remove-orphans)")

# ---------------- endereços ----------------
PORTA_HTTP = args.porta_http
_porta = "" if PORTA_HTTP == 80 else f":{PORTA_HTTP}"
LOCAL_URL = f"http://localhost{_porta}"          # nesta máquina (e para os jobs do CI)
LAN_URL = f"http://{IP}{_porta}" if not IP.startswith("127.") else None   # celular/PC na mesma rede
# link para abrir FORA desta máquina (QR code, link do MicroBin, servidor do app ntfy)
LINK_BASE = LAN_URL or LOCAL_URL
PROTEGER = args.proteger_http

# ---------------- serviços ----------------
WB = not args.sem_microbin
WB_NR = WB
WB_IMAGEM = "danielszabo99/microbin:latest" # docker pull danielszabo99/microbin:latest
NTFY = not args.sem_ntfy
NTFY_IMAGEM = "binwiederhier/ntfy:latest" # latest
NTFY_AVISOS = None                   # sem professor: não há tópico de avisos da turma
FUXA = not args.sem_fuxa
FUXA_IMAGEM = "frangoteam/fuxa:latest" # docker pull frangoteam/fuxa:latest
MQTTX = not args.sem_mqtt_explorer
MQTTX_IMAGEM = "ghcr.io/thomasnordquist/mqtt-explorer:latest"
MQTTX_PORTA = args.mqtt_explorer_porta
MQTTX_URL = f"http://localhost:{MQTTX_PORTA}/"

GITEA = not args.sem_gitea
GITEA_REPO = args.gitea_repo.strip()
GITEA_PG = GITEA and args.gitea_db == "postgres"
POSTGRES = GITEA_PG
_pg_senha = lambda: secrets.token_hex(16)
PG_ROOT_SENHA = segredo("postgres_root", _pg_senha) if POSTGRES else None
PG_GITEA_SENHA = segredo("postgres_gitea", _pg_senha) if GITEA_PG else None
GITEA_SECRET_KEY = segredo("gitea_secret_key", lambda: secrets.token_hex(32)) if GITEA else None
# Gitea com ROOT_URL = http://localhost/git/: o mesmo endereço vale no navegador desta máquina
# E dentro dos jobs do CI (o runner divide a rede do nginx; ver docker-compose.yml)
CI_IP = args.ci_rede == "ip"
if GITEA and CI_IP and not LAN_URL:
    sys.exit("--ci-rede ip precisa do IP desta máquina na rede local (--ip), não 127.x.")
GITEA_URL = f"{LAN_URL if CI_IP else LOCAL_URL}/git/"

RUNNER = GITEA and not args.sem_runner
RUNNER_IMAGEM = args.runner_imagem
GITEA_RUNNER_TOKEN = segredo("gitea_runner_token", lambda: secrets.token_hex(24)) if RUNNER else None
if args.wokwi_token == "-":
    SEGREDOS.pop("wokwi_cli_token", None)
elif args.wokwi_token:
    SEGREDOS["wokwi_cli_token"] = args.wokwi_token.strip()
WOKWI_TOKEN = SEGREDOS.get("wokwi_cli_token") if RUNNER else None
# os jobs alcançam o nginx em localhost (rede compartilhada) ou pelo IP da máquina (--ci-rede ip)
CI_URL = LAN_URL if CI_IP else LOCAL_URL

# ---------------- conta ----------------
prof = None
notas_service = None
grupos_alunos = [G]
todos_servicos = [G]
N = 1
fuxa_grupos = [G] if FUXA else []
C = G                                # prefixo dos containers


def is_prof(g):
    return False


def is_notas(g):
    return False


def letra_de(g):
    return g.rsplit("-", 1)[-1]


def org_de(g):
    """Organização Gitea do grupo (mesmo nome do laboratório)."""
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


credenciais_geradas = []
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
# ntfy/server.yml — UM ntfy para todo o lab, isolado por ACL:
#   cada grupo lê/escreve só em <grupo> e <grupo>-*  (ex.: lab05-a, lab05-a-alarme)
#   todos leem <lab>-avisos; notas lê tudo; professor é admin (lê/escreve tudo)
# Usuários, permissões e tokens são declarativos (re-sincronizados a cada subida).
# =====================================================================
NTFY_TOKEN = {}
NTFY_TOKEN_CI = {}
NTFY_CFG_HASH = ""
if NTFY:
    import hashlib as _hl

    def _ntfy_hash(u):
        """bcrypt (custo 10) da senha; reaproveitado enquanto a senha não muda."""
        h = SEGREDOS.get(f"ntfy_hash:{u}")
        if not h or not bcrypt.checkpw(SENHA[u].encode(), h.encode()):
            h = bcrypt.hashpw(SENHA[u].encode(), bcrypt.gensalt(10)).decode()
            SEGREDOS[f"ntfy_hash:{u}"] = h
        return h

    _alfa = string.ascii_lowercase + string.digits
    ny_users, ny_access, ny_tokens = [], [], []
    for u in todos_servicos:
        papel = "admin" if is_prof(u) else "user"
        ny_users.append(f"{u}:{_ntfy_hash(u)}:{papel}")
        NTFY_TOKEN[u] = segredo(f"ntfy_token:{u}",
                                lambda: "tk_" + "".join(secrets.choice(_alfa) for _ in range(29)))
        ny_tokens.append(f"{u}:{NTFY_TOKEN[u]}:node-red")
        if RUNNER and not is_prof(u) and not is_notas(u):
            # token separado para o CI (secret NTFY_TOKEN da organização): revogar um não derruba o outro
            NTFY_TOKEN_CI[u] = segredo(f"ntfy_token_ci:{u}",
                                       lambda: "tk_" + "".join(secrets.choice(_alfa) for _ in range(29)))
            ny_tokens.append(f"{u}:{NTFY_TOKEN_CI[u]}:gitea-actions")
        if papel == "admin":
            continue                      # admin já pode tudo (e não aceita ACL)
        ny_access += [f"{u}:{u}:rw", f"{u}:{u}-*:rw"]
        if not KIT:
            ny_access.append(f"{u}:{NTFY_AVISOS}:ro")
            if is_notas(u):
                ny_access.append(f"{u}:{LAB}-*:ro")   # avaliação: lê os tópicos de todos
    yml = [f"# server.yml do ntfy — gerado por gen_iot_aluno.py ({KIT or LAB})",
           "# Alterou? docker compose up -d  (o rótulo com o hash recria o container)",
           'listen-http: ":80"',
           "# atrás do nginx (e do túnel): IP real do cliente vem do X-Forwarded-For",
           "behind-proxy: true",
           'proxy-trusted-hosts: "172.16.0.0/12"',
           "cache-file: /var/lib/ntfy/cache.db",
           'cache-duration: "72h"',
           "auth-file: /var/lib/ntfy/auth.db",
           "auth-default-access: deny-all",
           "# o app web do ntfy não funciona em subcaminho: o portal tem a página /avisos/",
           "web-root: disable",
           "enable-signup: false",
           "visitor-subscription-limit: 100",
           "visitor-request-limit-burst: 120",
           "auth-users:"] + [f'  - "{x}"' for x in ny_users] + \
          ["auth-access:"] + [f'  - "{x}"' for x in ny_access] + \
          ["auth-tokens:"] + [f'  - "{x}"' for x in ny_tokens]
    _yml = "\n".join(yml) + "\n"
    gravar("ntfy/server.yml", _yml)
    NTFY_CFG_HASH = _hl.sha1(_yml.encode()).hexdigest()[:12]
    print("🔔 ntfy/server.yml")

# =====================================================================
# mosquitto/mosquitto.conf
# =====================================================================
mosq = """listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest stdout
"""
PONTE = None
if KIT and args.ponte_mqtt:
    _h, _, _p = args.ponte_mqtt.partition(":")
    PONTE = f"{_h}:{_p or 1883}"
    # ponte (bridge) com o broker do laboratório: só os tópicos do grupo, nos dois sentidos.
    # Funciona na rede do lab (o 1883 do lab não é publicado no VPS); fora dela, tenta de
    # novo a cada minuto sem atrapalhar o kit.
    mosq += f"""
# ponte com o broker do laboratório ({PONTE}): tópicos {KIT}/# nos dois sentidos
connection ponte-{KIT}
address {PONTE}
topic {KIT}/# both 0
cleansession true
start_type automatic
restart_timeout 10 60
notifications false
try_private true
"""
gravar("mosquitto/mosquitto.conf", mosq)
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
    node-red-node-ui-table \\
    node-red-contrib-modbus \\
    node-red-contrib-s7 \\
    node-red-contrib-opcua \\
    && npm cache clean --force
"""

gravar("Dockerfile", dockerfile)
print("📦 Dockerfile")

# =====================================================================
# docker-compose.yml
# =====================================================================
c = [
    f"# LAB IoT do {G} — gerado por gen_iot_aluno.py (na máquina do aluno)\n",
    f"# Nesta máquina: {LOCAL_URL}/\n",
    (f"# Rede local:    {LAN_URL}/\n" if LAN_URL else ""),
    "# Subir:   docker compose up -d --build\n",
    "services:\n",
    "  nginx:\n",
    "    image: nginx:alpine\n",
    f"    container_name: {C}-portal\n",
    "    restart: unless-stopped\n",
    "    ports:\n",
    f'      - "{PORTA_HTTP}:{PORTA_HTTP}"\n',
    "    volumes:\n",
    "      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro\n",
    "      - ./nginx/html:/usr/share/nginx/html:ro\n",
    "      - ./nginx/htpasswd:/etc/nginx/htpasswd:ro\n",
    ("      - ./nginx/htpasswd.d:/etc/nginx/htpasswd.d:ro\n" if FUXA and PROTEGER else ""),
    "    networks:\n",
    "      - labnet\n",
]

c += [
    "\n  mosquitto:\n",
    "    image: eclipse-mosquitto:2\n",
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
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        f"      - GRUPO={g}\n",
    ]
    if NTFY:   # no Node-RED: env.get("NTFY_URL"), env.get("NTFY_TOPIC"), env.get("NTFY_TOKEN")
        c += [
            "      - NTFY_URL=http://ntfy\n",
            f"      - NTFY_TOPIC={g}\n",
            f"      - NTFY_TOKEN={NTFY_TOKEN[g]}\n",
        ]
    if WB:
        c += [
            "      - MICROBIN_URL=http://microbin:8080\n",
            f"      - MICROBIN_LINK={LINK_BASE}/bin\n",
            f"      - MICROBIN_AUTH=Basic {base64.b64encode(f'{g}:{SENHA[g]}'.encode()).decode()}\n",
        ]
    c += [
        "    depends_on:\n",
        "      - mosquitto\n",
        "    networks:\n",
        "      - labnet\n",
    ]

# MQTT Explorer (imagem oficial, modo navegador): só nesta máquina, porta própria
if MQTTX:
    _origens = [f"http://localhost:{MQTTX_PORTA}", f"http://127.0.0.1:{MQTTX_PORTA}"]
    if LAN_URL:
        _origens.append(f"http://{IP}:{MQTTX_PORTA}")
    c += [
        "\n  mqtt-explorer:\n",
        f"    image: {MQTTX_IMAGEM}\n",
        f"    container_name: {C}-mqtt-explorer\n",
        "    restart: unless-stopped\n",
        "    ports:\n",
        f'      - "{MQTTX_PORTA}:3000"\n',
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - PORT=3000\n",
        "      - MQTT_AUTO_CONNECT_HOST=mosquitto\n",
        "      - MQTT_AUTO_CONNECT_PORT=1883\n",
        f"      - ALLOWED_ORIGINS={','.join(_origens)}\n",
        f"      - MQTT_EXPLORER_USERNAME={G}\n",
        f"      - MQTT_EXPLORER_PASSWORD={SENHA[G]}\n",
        "    volumes:\n",
        "      - ./mqtt-explorer/data:/app/data\n",
        "    depends_on:\n",
        "      - mosquitto\n",
        "    networks:\n",
        "      - labnet\n",
    ]

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

if GITEA:
    c += [
        "\n  gitea:\n",
        "    image: gitea/gitea:28\n",
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
        f"      - GITEA__server__DOMAIN={urlparse(GITEA_URL).hostname}\n",
        f"      - GITEA__server__ROOT_URL={GITEA_URL}\n",
        "      - GITEA__server__HTTP_PORT=3000\n",
        "      - GITEA__server__DISABLE_SSH=true\n",
        "      - GITEA__security__INSTALL_LOCK=true\n",
        f"      - GITEA__security__SECRET_KEY={GITEA_SECRET_KEY}\n",
        "      - GITEA__session__COOKIE_SECURE=false\n",
        "      - GITEA__service__DISABLE_REGISTRATION=true\n",
        "      - GITEA__service__REQUIRE_SIGNIN_VIEW=true\n",
        "      - GITEA__service__DEFAULT_ORG_VISIBILITY=private\n",
        "      - GITEA__repository__DEFAULT_PRIVATE=private\n",
        "      - GITEA__repository__DEFAULT_BRANCH=main\n",
        "      - GITEA__ui__DEFAULT_THEME=gitea-auto\n",
        "      - GITEA__time__DEFAULT_UI_LOCATION=America/Sao_Paulo\n",
        f"      - GITEA__actions__ENABLED={'true' if RUNNER else 'false'}\n",
    ]
    if RUNNER:
        c += [
            "      - GITEA__actions__DEFAULT_ACTIONS_URL=github\n",
            f"      - GITEA_RUNNER_REGISTRATION_TOKEN={GITEA_RUNNER_TOKEN}\n",
        ]
    c += [
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
        "    networks:\n", "      - labnet\n",
        "\n  gitea-init:\n",
        "    image: gitea/gitea:28\n",
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

# Gitea Actions: o runner DIVIDE a rede do nginx (network_mode: service:nginx) e os jobs usam
# a rede do runner (container.network: host). Assim, "localhost" dentro de um job é o nginx:
# http://localhost/git/ (o ROOT_URL do Gitea) funciona igual no navegador e no CI, em qualquer
# rede (casa, laboratório, celular roteado), sem depender do IP da máquina.
if RUNNER:
    c += [
        "\n  gitea-runner:\n",
        f"    image: {RUNNER_IMAGEM}\n",
        f"    container_name: {C}-gitea-runner\n",
        "    restart: unless-stopped\n",
        "    privileged: true                # o dockerd embutido (dind) exige\n",
        ('    network_mode: "service:nginx"   # localhost = nginx (para o runner e para os jobs)\n'
         if not CI_IP else ""),
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - GITEA_INSTANCE_URL=http://gitea:3000/\n",
        f"      - GITEA_RUNNER_REGISTRATION_TOKEN={GITEA_RUNNER_TOKEN}\n",
        f"      - GITEA_RUNNER_NAME={G}-runner\n",
        "      - CONFIG_FILE=/config.yaml\n",
        "    volumes:\n",
        "      - ./runner/config.yaml:/config.yaml:ro\n",
        "      - runner_data:/data                # .runner (registro) e cache do actions/cache\n",
        "      - runner_docker:/var/lib/docker    # imagens dos jobs (não baixa de novo a cada job)\n",
        "    depends_on:\n",
        "      nginx:\n",
        "        condition: service_started\n",
        "      gitea:\n",
        "        condition: service_healthy\n",
    ]
    if CI_IP:
        c += ["    networks:\n", "      - labnet\n"]

if WB:
    c += [
        "\n  microbin:\n",
        f"    image: {WB_IMAGEM}\n",
        f"    container_name: {C}-microbin\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - MICROBIN_PUBLIC_PATH=/bin\n",
        f"      - MICROBIN_SHORT_PATH={LINK_BASE}/bin\n",
        ("      - MICROBIN_QR=true\n" if LAN_URL else ""),
        f"      - MICROBIN_TITLE=MicroBin · {G}\n",
        f"      - MICROBIN_ADMIN_USERNAME={G}\n",
        f"      - MICROBIN_ADMIN_PASSWORD={SENHA[G]}\n",
        "      - MICROBIN_HIGHLIGHTSYNTAX=true\n",
        "      - MICROBIN_PRIVATE=true\n",
        "      - MICROBIN_EDITABLE=true\n",
        "      - MICROBIN_ENABLE_BURN_AFTER=true\n",
        "      - MICROBIN_SHOW_READ_STATS=true\n",
        "      - MICROBIN_DEFAULT_EXPIRY=24hour\n",
        "      - MICROBIN_MAX_EXPIRY=1month\n",
        "      - MICROBIN_GC_DAYS=90\n",
        "      - MICROBIN_WIDE=true\n",
        "      - MICROBIN_ENCRYPTION_SERVER_SIDE=true\n",
        "      - MICROBIN_ENCRYPTION_CLIENT_SIDE=true\n",
        "      - MICROBIN_MAX_FILE_SIZE_UNENCRYPTED_MB=50\n",
        "      - MICROBIN_MAX_FILE_SIZE_ENCRYPTED_MB=10\n",
        "      - MICROBIN_DISABLE_TELEMETRY=true\n",
        "      - MICROBIN_DISABLE_UPDATE_CHECKING=true\n",
        "      - MICROBIN_LIST_SERVER=false\n",
        "    volumes:\n",
        "      - microbin_data:/app/microbin_data\n",
        "    networks:\n",
        "      - labnet\n",
    ]

if NTFY:
    c += [
        "\n  ntfy:\n",
        f"    image: {NTFY_IMAGEM}\n",
        f"    container_name: {C}-ntfy\n",
        "    restart: unless-stopped\n",
        '    command: ["serve"]\n',
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "    labels:\n",
        f"      - lab.ntfy-config={NTFY_CFG_HASH}\n",
        "    volumes:\n",
        "      - ./ntfy/server.yml:/etc/ntfy/server.yml:ro\n",
        "      - ntfy_data:/var/lib/ntfy\n",
        "    networks:\n",
        "      - labnet\n",
    ]

for g in fuxa_grupos:
    c += [
        f"\n  {g}-fuxa:\n",
        f"    image: {FUXA_IMAGEM}\n",
        f"    container_name: {g}-fuxa\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - NODE_ENV=production\n",
        f"      - BASE_PATH=/fuxa/{g}\n",
        "    volumes:\n",
        f"      - ./fuxa/{g}/appdata:/usr/src/app/FUXA/server/_appdata\n",
        f"      - ./fuxa/{g}/db:/usr/src/app/FUXA/server/_db\n",
        f"      - ./fuxa/{g}/images:/usr/src/app/FUXA/server/_images\n",
        f"      - ./fuxa/{g}/pkg:/usr/src/app/FUXA/server/_pkg\n",
        "    depends_on:\n",
        "      - mosquitto\n",
        "    networks:\n",
        "      - labnet\n",
    ]

c += ["\nvolumes:\n", "  mosquitto_data:\n"]
if POSTGRES:
    c += ["  postgres_data:\n"]
if GITEA:
    c += ["  gitea_data:\n"]
if RUNNER:
    c += ["  runner_data:\n", "  runner_docker:\n"]
if NTFY:
    c += ["  ntfy_data:\n"]
if WB:
    c += ["  microbin_data:\n"]
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
    f"# nginx.conf — gerado por gen_iot_aluno.py ({LAB})\n",
    "worker_processes auto;\n",
    "events { worker_connections 1024; }\n\n",
    "http {\n",
    "    include       /etc/nginx/mime.types;\n",
    "    default_type  application/octet-stream;\n",
    "    sendfile on;\n",
    "    # redirecionamentos relativos: funcionam em http://IP e no domínio público\n",
    "    absolute_redirect off;\n",
    "    # DNS interno do Docker: os nomes dos containers são resolvidos a cada acesso,\n",
    "    # então recriar um container (novo IP) não exige reiniciar o nginx\n",
    "    resolver 127.0.0.11 valid=10s ipv6=off;\n\n",
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
    f"        listen {PORTA_HTTP} default_server;\n",
    "        server_name _;\n",
    "        root /usr/share/nginx/html;\n",
    "        index index.html;\n",
    "        location / { }\n",
]
for g in todos_servicos:
    n += [f"\n        # {g} ({papel_de(g)}) -> /{g}/\n",
          f"        location = /{g} {{ return 301 /{g}/; }}\n"]
    n += location(f"/{g}/", [f"set $alvo http://{g}-nodered:1880;",
                             "proxy_pass $alvo;"])
if GITEA:
    # Gitea em subcaminho (ROOT_URL = .../git/); receita da documentação oficial
    n += ["\n        # Gitea -> /git/\n",
          "        location = /git { return 301 /git/; }\n"]
    n += location("/git/", ["client_max_body_size 512m;",
                            "rewrite ^ $request_uri;",
                            "rewrite ^/git(/.*) $1 break;",
                            "proxy_pass http://gitea:3000$uri;"])
if WB:
    # MicroBin em /bin/: gera os links com o prefixo (MICROBIN_PUBLIC_PATH=/bin) e o nginx
    # retira o /bin antes de entregar. Acesso com o login de qualquer grupo (htpasswd).
    n += ["\n        # MicroBin (único) -> /bin/  (login: usuário e senha do grupo)\n",
          "        location = /bin { return 301 /bin/; }\n"]
    n += location("/bin/", ["client_max_body_size 55m;",
                            'auth_basic "MicroBin - login do grupo";',
                            "auth_basic_user_file /etc/nginx/htpasswd;",
                            "set $alvo microbin:8080;",
                            "rewrite ^/bin(/.*)$ $1 break;",
                            "proxy_pass http://$alvo;"])
if NTFY:
    # ntfy não suporta subcaminho: o nginx retira o /ntfy (API, WebSocket, JSON stream).
    # Sem auth_basic aqui: o ntfy usa o próprio cabeçalho Authorization (usuário/senha ou token).
    n += ["\n        # ntfy (único) -> /ntfy/  (apps: servidor <base>/ntfy)\n",
          "        location = /ntfy { return 301 /ntfy/; }\n"]
    n += location("/ntfy/", ["client_max_body_size 1m;",
                             "set $alvo ntfy:80;",
                             "rewrite ^/ntfy(/.*)$ $1 break;",
                             "proxy_pass http://$alvo;"])
    n += ["        location = /avisos { return 301 /avisos/; }\n"]
for g in fuxa_grupos:
    # FUXA com BASE_PATH=/fuxa/<grupo>: o prefixo é mantido (sem rewrite); WebSocket em
    # /fuxa/<grupo>/socket.io/. Login próprio do FUXA (usuário/senha do grupo).
    extra = ["client_max_body_size 100m;"]
    if PROTEGER:   # também exige o login do grupo antes de abrir (até para ver telas)
        extra += [f'auth_basic "FUXA - {g}";', f"auth_basic_user_file /etc/nginx/htpasswd.d/{g};"]
    n += [f"\n        # FUXA (SCADA/HMI) do {g} -> /fuxa/{g}/\n",
          f"        location = /fuxa/{g} {{ return 301 /fuxa/{g}/; }}\n"]
    n += location(f"/fuxa/{g}/", extra + [f"set $alvo http://{g}-fuxa:1881;", "proxy_pass $alvo;"])
if fuxa_grupos:
    n += ["        location = /fuxa { return 302 /#fuxa; }\n",
          "        location = /fuxa/ { return 302 /#fuxa; }\n"]
if MQTTX:
    n += ["\n        # MQTT Explorer não suporta subcaminho: só na rede local, porta direta\n",
          f"        location /mqtt {{ return 302 http://$host:{MQTTX_PORTA}/; }}\n"]
n += ["    }\n", "}\n"]
gravar("nginx/nginx.conf", "".join(n))

# htpasswd do nginx ({SSHA}: SHA-1 com sal, formato aceito pelo auth_basic):
# todos os grupos, o professor e as notas entram com o próprio usuário/senha
def _ssha(senha):
    sal = secrets.token_bytes(8)
    return "{SSHA}" + base64.b64encode(hashlib.sha1(senha.encode() + sal).digest() + sal).decode()


gravar("nginx/htpasswd", "".join(f"{u}:{_ssha(SENHA[u])}\n" for u in todos_servicos))
if FUXA and PROTEGER:   # FUXA de cada grupo: só o grupo e o professor
    for g in fuxa_grupos:
        gravar(f"nginx/htpasswd.d/{g}", "".join(f"{u}:{_ssha(SENHA[u])}\n" for u in dict.fromkeys([g] if KIT else [g, prof])))
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
    if PROTEGER:
        http_auth = ("\n    // dashboards e endpoints HTTP exigem login (usuário/senha do grupo)\n"
                     f'    httpNodeAuth: {{ user: "{g}", pass: "{hash_admin}" }},')
    gravar(f"settings/{g}.js", tpl.format(
        g=g,
        # credentialSecret persistente: senão as credenciais salvas nos nós ficam ilegíveis
        cred=segredo(f"credential_secret:{g}", lambda: secrets.token_hex(16)),
        titulo=titulo, hash_admin=hash_admin, hash_view=hash_view, http_auth=http_auth))
print("⚙️  settings/<grupo>.js")

# =====================================================================
# fuxa/<grupo>/appdata — usuários (users.fuxap.db) e mysettings.json
# O FUXA só cria o admin/123456 quando o banco de usuários NÃO existe; aqui o banco já
# nasce com o grupo e o professor (administradores, bcrypt) e o admin padrão é removido.
# Re-executar o gerador re-sincroniza as senhas; usuários criados no FUXA são mantidos.
# =====================================================================
import sqlite3


def semear_fuxa(g):
    appdata = f"fuxa/{g}/appdata"
    for sub in ("appdata", "db", "images", "pkg"):
        os.makedirs(f"fuxa/{g}/{sub}", exist_ok=True)
    db = sqlite3.connect(os.path.join(appdata, "users.fuxap.db"))
    try:
        db.executescript(
            "CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, fullname TEXT, "
            "password TEXT, groups INTEGER, info TEXT);"
            "CREATE TABLE IF NOT EXISTS roles (name TEXT PRIMARY KEY, value TEXT);")
        contas = [(g, f"Grupo {letra_de(g).upper()} ({LAB})")] if not is_prof(g) else []
        if not KIT:   # no kit só o grupo (o professor não tem acesso à máquina do aluno)
            contas.append((prof, f"Professor ({LAB})"))
        for usuario, nome in contas:
            # bcryptjs (FUXA) aceita $2a$; groups = -1 -> administrador (edita o projeto)
            h = bcrypt.hashpw(SENHA[usuario].encode(), bcrypt.gensalt(10)).decode()
            db.execute("INSERT OR REPLACE INTO users (username, fullname, password, groups) "
                       "VALUES (?, ?, ?, -1)", (usuario, nome, h.replace("$2b$", "$2a$", 1)))
        db.execute("DELETE FROM users WHERE username = 'admin'")
        db.commit()
    finally:
        db.close()
    arq = os.path.join(appdata, "mysettings.json")
    try:
        with open(arq, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg.update({
        "secureEnabled": True,       # editar exige login; ver as telas (HMI) não
        "secretCode": segredo(f"fuxa_secret:{g}", lambda: secrets.token_hex(24)),
        "tokenExpiresIn": "12h",
        "language": "pt",
        "nodeRedEnabled": False,     # usa o Node-RED do grupo (MQTT), não o embutido
    })
    gravar(arq, json.dumps(cfg, indent=2, ensure_ascii=False))


for g in fuxa_grupos:
    semear_fuxa(g)
if FUXA:
    print("🏭 fuxa/<grupo>/appdata (usuários e configurações do FUXA)")

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

  /* Card do MicroBin: destaque rosa */
  .node--bin::before { background: var(--pink-dim); }
  .node--bin:hover, .node--bin:focus-visible { border-color: var(--pink); }
  .node--bin:hover::before, .node--bin:focus-visible::before { background: var(--pink); }
  .node--bin .node__topic { color: var(--pink); }

  /* Card do ntfy (avisos): destaque verde-limão */
  .node--ntfy::before { background: #3f5a12; }
  .node--ntfy:hover, .node--ntfy:focus-visible { border-color: #a3e635; }
  .node--ntfy:hover::before, .node--ntfy:focus-visible::before { background: #a3e635; }
  .node--ntfy .node__topic { color: #a3e635; }
  .mailbox { margin-top: 34px; }
  .mailbox h2 { font-family: var(--mono); font-size: 12px; letter-spacing: .2em; text-transform: uppercase;
                color: #a3e635; font-weight: 500; margin-bottom: 12px; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { font-family: var(--mono); font-size: 13px; color: var(--ink); text-decoration: none;
          background: var(--panel); border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px; }
  .chip:hover, .chip:focus-visible { border-color: #a3e635; outline: none; }

  /* FUXA (SCADA/HMI): destaque ciano */
  .node--fuxa::before { background: #155e75; }
  .node--fuxa:hover, .node--fuxa:focus-visible { border-color: #22d3ee; }
  .node--fuxa:hover::before, .node--fuxa:focus-visible::before { background: #22d3ee; }
  .node--fuxa .node__topic { color: #22d3ee; }
  .mailbox--fuxa h2 { color: #22d3ee; }
  .mailbox--fuxa .chip:hover, .mailbox--fuxa .chip:focus-visible { border-color: #22d3ee; }

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
{{MAILBOX}}

    <footer class="foot">
      {{RODAPE}}
    </footer>
  </div>
</body>
</html>
"""

cards = []
for g in todos_servicos:
    cards.append(
        f'      <a class="node" href="/{g}/">\n'
        f'        <span class="node__idx">node-red</span>\n'
        f'        <span class="node__name">{g}</span>\n'
        f'        <span class="node__topic">{g}/#</span>\n'
        '        <span class="node__go">abrir editor &rarr;</span>\n'
        '      </a>\n')
    cards.append(
        f'      <a class="node" href="/{g}/dashboard">\n'
        f'        <span class="node__idx">dashboard</span>\n'
        f'        <span class="node__name">Dashboard</span>\n'
        f'        <span class="node__topic">/{g}/dashboard</span>\n'
        f'        <span class="node__go">abrir{" (login)" if PROTEGER else ""} &rarr;</span>\n'
        '      </a>\n')
if FUXA:
    cards.append(
        f'      <a class="node node--fuxa" href="/fuxa/{G}/">\n'
        '        <span class="node__idx">scada</span>\n'
        '        <span class="node__name">FUXA (SCADA/HMI)</span>\n'
        '        <span class="node__topic">telas ligadas ao MQTT</span>\n'
        '        <span class="node__go">abrir FUXA &rarr;</span>\n'
        '      </a>\n')
if GITEA:
    cards.append(
        f'      <a class="node node--git" href="/git/{org_de(G)}">\n'
        f'        <span class="node__idx">git{" · actions" if RUNNER else ""}</span>\n'
        '        <span class="node__name">Gitea</span>\n'
        f'        <span class="node__topic">{org_de(G)}</span>\n'
        '        <span class="node__go">abrir repositórios &rarr;</span>\n'
        '      </a>\n')
if NTFY:
    cards.append(
        '      <a class="node node--ntfy" href="/avisos/">\n'
        '        <span class="node__idx">ntfy</span>\n'
        '        <span class="node__name">Avisos (ntfy)</span>\n'
        f'        <span class="node__topic">{G}  ·  celular e Node-RED</span>\n'
        '        <span class="node__go">ler e publicar &rarr;</span>\n'
        '      </a>\n')
if WB:
    cards.append(
        '      <a class="node node--bin" href="/bin/">\n'
        '        <span class="node__idx">bin</span>\n'
        '        <span class="node__name">MicroBin</span>\n'
        '        <span class="node__topic">colar código e enviar arquivos</span>\n'
        '        <span class="node__go">abrir (login) &rarr;</span>\n'
        '      </a>\n')
if MQTTX:
    cards.append(
        '      <a class="node node--mqtt" href="/mqtt">\n'
        '        <span class="node__idx">mqtt · só nesta rede</span>\n'
        '        <span class="node__name">MQTT Explorer</span>\n'
        '        <span class="node__topic">#  ·  broker local</span>\n'
        '        <span class="node__go">abrir explorer (login) &rarr;</span>\n'
        '      </a>\n')

rodape = [f"<span>nesta máquina: {LOCAL_URL}/</span>"]
if LAN_URL:
    rodape.append(f"<span>rede local: {LAN_URL}/</span>")
rodape += [f"<span>MQTT: {IP}:1883</span>", f"<span>tópicos: {G}/</span>"]
if PONTE:
    rodape.append(f"<span>ponte MQTT com o lab: {PONTE}</span>")
html = (PORTAL_HTML
        .replace("{{CARDS}}", "".join(cards))
        .replace("{{MAILBOX}}", "")
        .replace("{{RODAPE}}", "\n      ".join(rodape))
        .replace("{{LAB}}", G))
html = (html.replace(f"Painel do {G}", f"LAB IoT do {G}")
        .replace(f"broker online &middot; {G}", f"na sua máquina &middot; {G}")
        .replace(f"""Selecione seu grupo para abrir o editor Node-RED. Cada grupo
      publica no broker MQTT sob seu próprio tópico, no formato
      <code>{G}-&lt;letra&gt;/#</code>.""",
                 f"""O LAB IoT completo rodando no seu computador, com os mesmos caminhos
      e nomes do laboratório: fluxos e telas funcionam nos dois lugares.
      Tópicos MQTT: <code>{G}/#</code>."""))
gravar("nginx/html/index.html", html)
gravar("nginx/html/robots.txt", "User-agent: *\nDisallow: /\n")
print("🏠 nginx/html/index.html")

# =====================================================================
# nginx/html/avisos/index.html — página web do ntfy (o app web do ntfy não roda em
# subcaminho). Lê os tópicos (JSON stream) e publica; texto longo vai para o MicroBin
# e o aviso leva o link (botão "Abrir no MicroBin" também no celular).
# =====================================================================
AVISOS_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Avisos (ntfy) · __LAB__</title>
<style>
  :root {
    --bg: #071311; --panel: #0d201c; --line: #17332c; --ink: #dcf5ec; --muted: #6f9a8d;
    --lime: #a3e635; --lime-dim: #3f5a12; --pink: #f472b6; --gold: #e0b23a; --red: #f87171;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", "Cascadia Code", Menlo, Consolas, monospace;
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--ink); font-family: var(--sans); min-height: 100vh;
         background-image: linear-gradient(var(--line) 1px, transparent 1px),
                           linear-gradient(90deg, var(--line) 1px, transparent 1px);
         background-size: 44px 44px; padding: 5vh 16px; }
  .wrap { max-width: 980px; margin: 0 auto; }
  a { color: var(--lime); }
  .eyebrow { font-family: var(--mono); font-size: 12px; letter-spacing: .22em; text-transform: uppercase;
             color: var(--lime); display: flex; gap: 9px; align-items: center; }
  .eyebrow::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
  .eyebrow.on::before { background: var(--lime); box-shadow: 0 0 10px var(--lime); }
  h1 { font-size: clamp(26px, 5vw, 40px); font-weight: 650; letter-spacing: -.02em; margin: 12px 0 6px; }
  .sub { color: var(--muted); font-size: 15px; line-height: 1.5; max-width: 70ch; }
  .sub code, code { font-family: var(--mono); background: var(--panel); padding: 1px 6px; border-radius: 4px; color: var(--ink); }
  header { border-bottom: 1px solid var(--line); padding-bottom: 20px; margin-bottom: 24px; }
  .voltar { font-family: var(--mono); font-size: 12px; color: var(--muted); text-decoration: none; }
  .box { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 18px; margin-bottom: 16px; }
  .box h2 { font-family: var(--mono); font-size: 12px; letter-spacing: .2em; text-transform: uppercase;
            color: var(--lime); font-weight: 500; margin-bottom: 12px; }
  label { display: block; font-size: 13px; color: var(--muted); margin: 10px 0 4px; }
  input, textarea, select { width: 100%; background: var(--bg); color: var(--ink); border: 1px solid var(--line);
         border-radius: 6px; padding: 8px 10px; font: 14px var(--sans); }
  textarea { font-family: var(--mono); font-size: 13px; min-height: 90px; resize: vertical; }
  input:focus, textarea:focus, select:focus { outline: none; border-color: var(--lime); }
  .linha { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0 12px; }
  button { background: var(--lime-dim); color: var(--ink); border: 1px solid var(--lime); border-radius: 6px;
           padding: 8px 16px; font: 600 14px var(--sans); cursor: pointer; margin-top: 12px; }
  button.sec { background: transparent; border-color: var(--line); color: var(--muted); }
  button:disabled { opacity: .5; cursor: wait; }
  .check { display: flex; align-items: center; gap: 8px; margin-top: 12px; font-size: 14px; color: var(--ink); }
  .check input { width: auto; }
  .erro { color: var(--red); font-size: 14px; margin-top: 10px; min-height: 1em; }
  .ok { color: var(--lime); }
  .msgs { display: flex; flex-direction: column; gap: 10px; }
  .msg { background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--lime-dim);
         border-radius: 8px; padding: 12px 14px; }
  .msg.p4 { border-left-color: var(--gold); } .msg.p5 { border-left-color: var(--red); }
  .msg .meta { font-family: var(--mono); font-size: 12px; color: var(--muted); display: flex; gap: 12px; flex-wrap: wrap; }
  .msg .topico { color: var(--lime); }
  .msg .titulo { font-weight: 600; margin-top: 6px; }
  .msg .texto { margin-top: 4px; white-space: pre-wrap; word-break: break-word; line-height: 1.45; }
  .msg .acoes { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
  .msg .acoes a { font-family: var(--mono); font-size: 12px; border: 1px solid var(--line); border-radius: 999px;
                  padding: 3px 10px; text-decoration: none; }
  .vazio { color: var(--muted); font-size: 14px; }
  .barra { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  .oculto { display: none !important; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  td { border-top: 1px solid var(--line); padding: 6px 4px; vertical-align: top; }
  td:first-child { color: var(--muted); width: 38%; }
  @media (min-width: 860px) { .duas { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; } .duas .box { margin: 0 0 16px; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <a class="voltar" href="../">&larr; portal</a>
    <div class="eyebrow" id="estado" style="margin-top:14px">desconectado</div>
    <h1>Avisos (ntfy)</h1>
    <p class="sub">Notificações do laboratório: o Node-RED do grupo publica, o celular recebe.
    Aqui você acompanha os tópicos, publica mensagens e, se o texto for longo, ele vai para o
    <strong>MicroBin</strong> e o aviso leva o link.</p>
  </header>

  <section class="box" id="caixaLogin">
    <h2>Entrar</h2>
    <form id="fLogin">
      <div class="linha">
        <div><label for="u">Usuário do grupo</label><input id="u" autocomplete="username" placeholder="__EXEMPLO__"></div>
        <div><label for="s">Senha</label><input id="s" type="password" autocomplete="current-password"></div>
      </div>
      <button type="submit">Entrar</button>
      <div class="erro" id="eLogin" role="alert"></div>
    </form>
  </section>

  <div id="area" class="oculto">
    <div class="duas">
      <section class="box">
        <h2>Publicar</h2>
        <form id="fPub">
          <div class="linha">
            <div><label for="pt">Tópico</label><input id="pt" list="ltopicos"></div>
            <div><label for="pp">Prioridade</label>
              <select id="pp"><option value="1">1 · mínima</option><option value="2">2 · baixa</option>
              <option value="3" selected>3 · normal</option><option value="4">4 · alta</option>
              <option value="5">5 · urgente</option></select></div>
          </div>
          <label for="pti">Título</label><input id="pti" placeholder="ex.: Temperatura alta">
          <label for="pm">Mensagem</label><textarea id="pm" placeholder="texto do aviso"></textarea>
          <div id="opWb" class="oculto">
            <label class="check"><input type="checkbox" id="pwb"> Texto longo: guardar no MicroBin e mandar o link</label>
            <div class="linha" id="opWb2">
              <div><label for="pext">Tipo</label><select id="pext"><option value="">texto</option>
                <option value="json">JSON (fluxo Node-RED)</option><option value="js">JavaScript</option>
                <option value="py">Python</option><option value="cpp">C/C++ (ESP32)</option><option value="log">log</option></select></div>
              <div><label for="pexp">Validade</label><select id="pexp"><option value="1hour">1 hora</option>
                <option value="24hour" selected>1 dia</option><option value="1week">7 dias</option></select></div>
            </div>
          </div>
          <button type="submit" id="bPub">Publicar</button>
          <div class="erro" id="ePub" role="status"></div>
        </form>
        <datalist id="ltopicos"></datalist>
      </section>

      <section class="box">
        <h2>Celular e Node-RED</h2>
        <table>
          <tr><td>App ntfy · servidor</td><td><code id="srv"></code></td></tr>
          <tr><td>Login no app</td><td><code id="quem"></code> e a senha do grupo</td></tr>
          <tr><td>Tópicos do grupo</td><td><code id="meus"></code></td></tr>
          <tr><td>Node-RED (já configurado)</td><td><code>env.get("NTFY_URL")</code>, <code>NTFY_TOPIC</code>, <code>NTFY_TOKEN</code></td></tr>
        </table>
        <p class="sub" style="margin-top:10px;font-size:13px">No app (Android/iOS): ⚙ → <em>Usuários</em> → adicionar
        o servidor acima com o login; depois <em>+</em> → assinar o tópico usando esse servidor.</p>
      </section>
    </div>

    <section class="box">
      <div class="barra">
        <h2 style="margin:0">Mensagens (últimas 48 h)</h2>
        <div><button class="sec" id="bSair" type="button">Sair</button></div>
      </div>
      <label for="tt">Tópicos acompanhados (separados por vírgula)</label>
      <input id="tt">
    </section>
    <div class="msgs" id="msgs"><p class="vazio">Nenhuma mensagem ainda.</p></div>
  </div>
</div>

<script>
const CFG = __CFG__;
const $ = id => document.getElementById(id);
let cred = null, conta = null, ctrl = null, vistos = new Set();

const guardar = (k, v) => { try { v === null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch (e) {} };
const ler = k => { try { return sessionStorage.getItem(k); } catch (e) { return null; } };
const auth = () => ({ Authorization: "Basic " + btoa(unescape(encodeURIComponent(cred.u + ":" + cred.s))) });

function topicosPadrao(c) {
  const t = [];
  if (c.role === "admin") {
    if (CFG.avisos) t.push(CFG.avisos);
    t.push(c.username, ...CFG.grupos);
  } else if (CFG.notas && c.username === CFG.notas) {
    if (CFG.avisos) t.push(CFG.avisos);
    t.push(...CFG.grupos);
  } else {
    t.push(c.username);
    if (CFG.avisos) t.push(CFG.avisos);
  }
  return [...new Set(t)];
}

async function entrar(u, s) {
  cred = { u, s };
  const r = await fetch("/ntfy/v1/account", { headers: auth() });
  if (r.status === 401 || r.status === 403) throw new Error("Usuário ou senha incorretos.");
  if (!r.ok) throw new Error("ntfy indisponível (HTTP " + r.status + ").");
  conta = await r.json();
  if (!conta.username || conta.username === "*") throw new Error("Usuário ou senha incorretos.");
  guardar("ntfy_u", u); guardar("ntfy_s", s);
  $("caixaLogin").classList.add("oculto"); $("area").classList.remove("oculto");
  const tops = topicosPadrao(conta);
  $("tt").value = tops.join(", ");
  $("pt").value = conta.role === "admin" && CFG.avisos ? CFG.avisos : conta.username;
  $("ltopicos").innerHTML = "";
  for (const t of [conta.username, conta.username + "-alarme", ...tops]) {
    const o = document.createElement("option"); o.value = t; $("ltopicos").appendChild(o);
  }
  $("srv").textContent = (CFG.publico || location.origin) + "/ntfy";
  $("quem").textContent = conta.username;
  $("meus").textContent = conta.username + ", " + conta.username + "-…" + (CFG.avisos ? "  ·  " + CFG.avisos + " (só leitura)" : "");
  $("opWb").classList.toggle("oculto", !CFG.microbin);
  assinar();
}

function sair() {
  if (ctrl) ctrl.abort();
  cred = conta = null; guardar("ntfy_u", null); guardar("ntfy_s", null);
  $("area").classList.add("oculto"); $("caixaLogin").classList.remove("oculto");
  $("msgs").innerHTML = '<p class="vazio">Nenhuma mensagem ainda.</p>'; vistos = new Set();
  estado(false);
}

function estado(on, txt) {
  $("estado").classList.toggle("on", on);
  $("estado").textContent = txt || (on ? "recebendo · " + (conta ? conta.username : "") : "desconectado");
}

function linkificar(el, texto) {
  const re = /(https?:\/\/[^\s<>"']+)/g; let i = 0, m;
  while ((m = re.exec(texto))) {
    el.appendChild(document.createTextNode(texto.slice(i, m.index)));
    const a = document.createElement("a"); a.href = m[1]; a.textContent = m[1]; a.target = "_blank"; a.rel = "noopener";
    el.appendChild(a); i = m.index + m[1].length;
  }
  el.appendChild(document.createTextNode(texto.slice(i)));
}

function mostrar(m) {
  if (vistos.has(m.id)) return; vistos.add(m.id);
  const v = $("msgs").querySelector(".vazio"); if (v) v.remove();
  const d = document.createElement("article"); d.className = "msg p" + (m.priority || 3);
  const meta = document.createElement("div"); meta.className = "meta";
  const tp = document.createElement("span"); tp.className = "topico"; tp.textContent = m.topic;
  const hr = document.createElement("span"); hr.textContent = new Date(m.time * 1000).toLocaleString("pt-BR");
  meta.append(tp, hr);
  if (m.priority && m.priority !== 3) { const p = document.createElement("span"); p.textContent = "prioridade " + m.priority; meta.append(p); }
  if (m.tags && m.tags.length) { const t = document.createElement("span"); t.textContent = "#" + m.tags.join(" #"); meta.append(t); }
  d.append(meta);
  if (m.title) { const t = document.createElement("div"); t.className = "titulo"; t.textContent = m.title; d.append(t); }
  const tx = document.createElement("div"); tx.className = "texto"; linkificar(tx, m.message || ""); d.append(tx);
  const links = [];
  if (m.click) links.push(["abrir", m.click]);
  for (const a of (m.actions || [])) if (a.action === "view" && a.url) links.push([a.label || "abrir", a.url]);
  if (links.length > 1 && links[0][1] === links[1][1]) links.shift();   // click = mesma URL da ação
  if (links.length) {
    const ac = document.createElement("div"); ac.className = "acoes";
    for (const [rot, url] of links) { const a = document.createElement("a"); a.href = url; a.textContent = rot + " ↗"; a.target = "_blank"; a.rel = "noopener"; ac.append(a); }
    d.append(ac);
  }
  $("msgs").prepend(d);
}

async function assinar() {
  if (ctrl) ctrl.abort();
  const meu = ctrl = new AbortController();
  const tops = $("tt").value.split(",").map(t => t.trim()).filter(Boolean).join(",");
  if (!tops) return;
  while (!meu.signal.aborted) {
    try {
      const r = await fetch("/ntfy/" + tops + "/json?since=48h", { headers: auth(), signal: meu.signal, cache: "no-store" });
      if (r.status === 401 || r.status === 403) { estado(false, "sem permissão em algum tópico: " + tops); return; }
      if (!r.ok) throw new Error("HTTP " + r.status);
      estado(true);
      const rd = r.body.getReader(), dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await rd.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        let k; while ((k = buf.indexOf("\n")) >= 0) {
          const linha = buf.slice(0, k).trim(); buf = buf.slice(k + 1);
          if (!linha) continue;
          try { const ev = JSON.parse(linha); if (ev.event === "message") mostrar(ev); } catch (e) {}
        }
      }
    } catch (e) { if (meu.signal.aborted) return; }
    estado(false, "reconectando…");
    await new Promise(ok => setTimeout(ok, 3000));
  }
}

async function publicar(ev) {
  ev.preventDefault();
  const topic = $("pt").value.trim(), title = $("pti").value.trim();
  let message = $("pm").value;
  if (!topic || !message.trim()) { $("ePub").textContent = "Informe o tópico e a mensagem."; return; }
  $("bPub").disabled = true; $("ePub").className = "erro"; $("ePub").textContent = "";
  try {
    const corpo = { topic, message, priority: +$("pp").value };
    if (title) corpo.title = title;
    const longo = new Blob([message]).size > 3500;
    if (CFG.microbin && ($("pwb").checked || longo)) {
      // MicroBin: formulário multipart em /bin/upload; responde 302 para /bin/upload/<id>
      // (o fetch segue o redirecionamento e r.url traz o id)
      const fd = new FormData();
      fd.append("content", message); fd.append("syntax_highlight", $("pext").value);
      fd.append("expiration", $("pexp").value); fd.append("privacy", "unlisted");
      const r = await fetch("/bin/upload", { method: "POST", headers: auth(), body: fd });
      const id = r.ok ? new URL(r.url).pathname.split("/").filter(Boolean).pop() : "";
      if (!id || id === "upload") throw new Error("MicroBin recusou (HTTP " + r.status + ")");
      const link = CFG.binLink + "/upload/" + id;
      const resumo = message.trim().split("\n")[0].slice(0, 140);
      corpo.message = resumo + (message.length > resumo.length ? " …" : "") + "\n(texto completo no MicroBin)";
      corpo.click = link;
      corpo.actions = [{ action: "view", label: "Abrir no MicroBin", url: link }];
    } else if (longo) {
      throw new Error("Mensagem maior que 4 KB: encurte o texto.");
    }
    const r = await fetch("/ntfy/", { method: "POST", headers: { ...auth(), "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    if (r.status === 401 || r.status === 403) throw new Error("Sem permissão para publicar em " + topic + ".");
    if (!r.ok) throw new Error("ntfy recusou (HTTP " + r.status + "): " + (await r.text()).slice(0, 200));
    $("pm").value = ""; $("pti").value = ""; $("pwb").checked = false;
    $("ePub").className = "erro ok"; $("ePub").textContent = "Publicado em " + topic + (corpo.click ? " (com link do MicroBin)." : ".");
  } catch (e) { $("ePub").textContent = e.message; }
  finally { $("bPub").disabled = false; }
}

$("fLogin").addEventListener("submit", async ev => {
  ev.preventDefault(); $("eLogin").textContent = "";
  try { await entrar($("u").value.trim(), $("s").value); } catch (e) { $("eLogin").textContent = e.message; }
});
$("fPub").addEventListener("submit", publicar);
$("bSair").addEventListener("click", sair);
$("tt").addEventListener("change", () => { $("msgs").innerHTML = ""; vistos = new Set(); assinar(); });

const u0 = ler("ntfy_u"), s0 = ler("ntfy_s");
if (u0 && s0) entrar(u0, s0).catch(() => sair());
</script>
</body>
</html>
"""

if NTFY:
    avisos_cfg = {
        "lab": LAB,
        "grupos": [G],
        "notas": None,
        "avisos": None,
        "publico": LAN_URL,          # servidor do app ntfy no celular (mesma rede)
        "microbin": WB,
        "binLink": f"{LINK_BASE}/bin",
    }
    gravar("nginx/html/avisos/index.html",
           AVISOS_HTML.replace("__CFG__", json.dumps(avisos_cfg, ensure_ascii=False))
           .replace("__LAB__", G).replace("__EXEMPLO__", G))
    print("🔔 nginx/html/avisos/index.html")


# Fluxo de exemplo do Node-RED (importável): avisar no ntfy e "relatório no MicroBin + aviso
# com link". Usa só variáveis de ambiente (NTFY_*, MICROBIN_*): o mesmo fluxo vale para
# todos os grupos, no laboratório e no kit. Baixar em <base>/avisos/exemplo-node-red.json
FN_AVISAR = """// msg.payload = texto do aviso; msg.topic = título (opcional)
msg.url = env.get("NTFY_URL");
msg.method = "POST";
msg.headers = { "Authorization": "Bearer " + env.get("NTFY_TOKEN"),
                "Content-Type": "application/json" };
msg.payload = {
    topic: env.get("NTFY_TOPIC"),          // ex.: lab05-a (ou lab05-a-alarme)
    title: msg.topic || "Aviso",
    message: String(msg.payload),
    priority: 4,                           // 1..5
    tags: ["warning"]
};
return msg;"""
FN_COLAR = """// msg.payload = texto longo (ou objeto) -> MicroBin (formulário multipart)
msg.texto = typeof msg.payload === "string" ? msg.payload : JSON.stringify(msg.payload, null, 2);
msg.url = env.get("MICROBIN_URL") + "/upload";
msg.method = "POST";
msg.followRedirects = false;           // a resposta 302 traz o id no cabeçalho Location
msg.headers = { "Authorization": env.get("MICROBIN_AUTH"), "Content-Type": "multipart/form-data" };
msg.payload = {
    content: msg.texto,
    syntax_highlight: "json",          // "", json, js, py, cpp, log ...
    expiration: "24hour",              // 1hour, 24hour, 1week, 1month
    privacy: "unlisted"                // não aparece na lista pública do MicroBin
};
return msg;"""
FN_LINK = """// resposta do MicroBin: 302, Location: /bin/upload/<id> -> aviso no ntfy com o link
const id = String(msg.headers.location || "").split("/").filter(Boolean).pop();
if (msg.statusCode !== 302 || !id) { node.error("MicroBin recusou: HTTP " + msg.statusCode, msg); return null; }
const link = env.get("MICROBIN_LINK") + "/upload/" + id;
msg.url = env.get("NTFY_URL");
msg.method = "POST";
msg.headers = { "Authorization": "Bearer " + env.get("NTFY_TOKEN"),
                "Content-Type": "application/json" };
msg.payload = {
    topic: env.get("NTFY_TOPIC"),
    title: "Relatório pronto",
    message: "Relatório com " + msg.texto.length + " caracteres no MicroBin.",
    click: link,
    actions: [{ action: "view", label: "Abrir no MicroBin", url: link }]
};
return msg;"""


def fluxo_exemplo():
    ids = iter(secrets.token_hex(8) for _ in range(20))
    nid = {k: next(ids) for k in ("i1", "f1", "h1", "d1", "i2", "f2", "h2", "f3", "h3", "d2", "c1")}

    def http(i, x, y, prox, ret="obj"):
        return {"id": nid[i], "type": "http request", "name": "", "method": "use", "ret": ret,
                "paytoqs": "ignore", "url": "", "tls": "", "persist": False, "proxy": "",
                "insecureHTTPParser": False, "authType": "", "senderr": False, "headers": [],
                "x": x, "y": y, "wires": [prox]}

    def fn(i, nome, codigo, x, y, prox):
        return {"id": nid[i], "type": "function", "name": nome, "func": codigo, "outputs": 1,
                "timeout": 0, "noerr": 0, "initialize": "", "finalize": "", "libs": [],
                "x": x, "y": y, "wires": [prox]}

    def inj(i, nome, payload, topico, x, y, prox):
        return {"id": nid[i], "type": "inject", "name": nome, "props": [{"p": "payload"}, {"p": "topic", "vt": "str"}],
                "repeat": "", "crontab": "", "once": False, "onceDelay": 0.1, "topic": topico,
                "payload": payload, "payloadType": "str", "x": x, "y": y, "wires": [prox]}

    def dbg(i, x, y):
        return {"id": nid[i], "type": "debug", "name": "", "active": True, "tosidebar": True,
                "console": False, "tostatus": True, "complete": "payload", "targetType": "msg",
                "statusVal": "", "statusType": "auto", "x": x, "y": y, "wires": []}

    nos = [
        {"id": nid["c1"], "type": "comment", "name": "ntfy + MicroBin (usa NTFY_* e MICROBIN_* do container)",
         "info": "Tópico, token e endereços vêm das variáveis de ambiente do Node-RED do grupo.",
         "x": 230, "y": 40, "wires": []},
        inj("i1", "aviso de teste", "Temperatura acima de 30 °C", "Temperatura alta", 150, 100, [nid["f1"]]),
        fn("f1", "avisar (ntfy)", FN_AVISAR, 350, 100, [nid["h1"]]),
        http("h1", 530, 100, [nid["d1"]]),
        dbg("d1", 710, 100),
    ]
    if WB_NR:
        nos += [
            inj("i2", "relatório longo", "linha 1\nlinha 2\n(muitas linhas...)", "Relatório do ensaio", 150, 180, [nid["f2"]]),
            fn("f2", "colar no MicroBin", FN_COLAR, 350, 180, [nid["h2"]]),
            http("h2", 530, 180, [nid["f3"]], ret="txt"),
            fn("f3", "avisar com link", FN_LINK, 710, 180, [nid["h3"]]),
            http("h3", 890, 180, [nid["d2"]]),
            dbg("d2", 1070, 180),
        ]
    return nos


if NTFY:
    gravar("nginx/html/avisos/exemplo-node-red.json", json.dumps(fluxo_exemplo(), indent=2, ensure_ascii=False))

# =====================================================================
# mqtt-explorer/data/settings.json
# =====================================================================
conn_id = "-".join(secrets.token_hex(k) for k in (4, 2, 2, 2, 6)) if MQTTX else None
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
if MQTTX:
    gravar("mqtt-explorer/data/settings.json", json.dumps(mqttx_settings, indent=2, ensure_ascii=False))
    print("🔭 mqtt-explorer/data/settings.json")

# =====================================================================
# gitea/init/gitea-init.sh
# =====================================================================
GITEA_INIT_TPL = r"""#!/bin/bash
# gitea-init.sh — gerado por gen_iot_aluno.py (lab __TURMA__)
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
units_map() {  # permissao (read|write) em todas as unidades de repositório
  local u out=""
  for u in repo.code repo.issues repo.pulls repo.releases repo.wiki repo.projects repo.actions repo.packages; do
    out="$out\"$u\":\"$1\","
  done
  echo "\"units_map\":{${out%,}}"
}

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
  local id code create=false UNITS_MAP
  [ "$3" = write ] && create=true
  UNITS_MAP=$(units_map "$3")
  api GET "/orgs/$1/teams/search?q=$2" >/dev/null
  id=$(grep -o '"id":[0-9]*' /tmp/resp | head -1 | cut -d: -f2)
  if [ -z "$id" ]; then
    # só units_map: o Gitea 28+ recusa "units" e "units_map" juntos
    code=$(api POST "/orgs/$1/teams" "{\"name\":\"$2\",\"permission\":\"$3\",\"includes_all_repositories\":true,\"can_create_org_repo\":$create,$UNITS_MAP}")
    if [ "$code" = 201 ]; then
      id=$(grep -o '"id":[0-9]*' /tmp/resp | head -1 | cut -d: -f2)
      log "time $1/$2 ($3) criado"
    fi
  else
    # já existe: reaplica as permissões (corrige times criados com outra configuração)
    code=$(api PATCH "/teams/$id" "{\"name\":\"$2\",\"permission\":\"$3\",\"includes_all_repositories\":true,\"can_create_org_repo\":$create,$UNITS_MAP}")
    [ "$code" = 200 ] && log "time $1/$2 ($3) ja existe: permissoes conferidas" \
                      || log "  ERRO ao atualizar time $1/$2 (HTTP $code): $(cat /tmp/resp)"
  fi
  if [ -n "$id" ]; then
    code=$(api PUT "/teams/$id/members/$4")
    log "  $4 -> $1/$2 (HTTP $code)"
  else
    log "  ERRO ao criar time $1/$2: $(cat /tmp/resp)"
  fi
}

ensure_org_secret() {  # org NOME valor   (PUT cria ou atualiza; o valor nunca mais é exibido)
  local code
  code=$(api PUT "/orgs/$1/actions/secrets/$2" "{\"data\":\"$3\"}")
  case "$code" in 201|204) log "  secret $1/$2 (HTTP $code)" ;;
                  *) log "  ERRO no secret $1/$2 (HTTP $code): $(cat /tmp/resp)" ;; esac
}

ensure_org_var() {  # org NOME valor   (POST cria; se já existe, PUT atualiza)
  local code
  code=$(api POST "/orgs/$1/actions/variables/$2" "{\"value\":\"$3\"}")
  [ "$code" = 201 ] || code=$(api PUT "/orgs/$1/actions/variables/$2" "{\"name\":\"$2\",\"value\":\"$3\"}")
  case "$code" in 201|204) log "  variavel $1/$2 = $3 (HTTP $code)" ;;
                  *) log "  ERRO na variavel $1/$2 (HTTP $code): $(cat /tmp/resp)" ;; esac
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
    org = org_de(G)
    corpo = [f'ensure_org  "{org}" "Grupo {letra_de(G).upper()} - {LAB}"',
             f'ensure_repo "{org}" "$REPO"']
    if RUNNER:
        if NTFY:
            corpo += [
                f'ensure_org_var    "{org}" NTFY_URL "{CI_URL}/ntfy"',
                f'ensure_org_secret "{org}" NTFY_TOPIC "{G}-ci"',
                f'ensure_org_secret "{org}" NTFY_TOKEN "{NTFY_TOKEN_CI[G]}"',
            ]
        if WOKWI_TOKEN:
            corpo += [f'ensure_org_secret "{org}" WOKWI_CLI_TOKEN "{WOKWI_TOKEN}"']
    gravar("gitea/init/gitea-init.sh",
           GITEA_INIT_TPL
           .replace("gerado por gen_iot_aluno.py", "gerado por gen_iot_aluno.py")
           .replace("__TURMA__", G)
           .replace("__ADMIN_USER__", G)
           .replace("__ADMIN_PASS__", SENHA[G])
           .replace("__ADMIN_EMAIL__", f"{G}@{DOMINIO}")
           .replace("__REPO__", GITEA_REPO)
           .replace("__CORPO__", "\n".join(corpo)), executavel=True)
    print("🐙 gitea/init/gitea-init.sh")

if RUNNER:
    REDE_JOB = ('  # rede própria do Docker interno: o job chega ao Gitea e ao ntfy pelo IP da máquina\n'
                '  network: ""') if CI_IP else (
        f'  # "host" = a rede do runner, que é a do nginx: no job, http://localhost{_porta}/git/ é o\n'
        f'  # Gitea e http://localhost{_porta}/ntfy é o ntfy. O job também alcança mosquitto:1883.\n'
        '  network: host')
    gravar("runner/config.yaml", f"""# config.yaml do gitea-runner — gerado por gen_iot_aluno.py ({G})
# Alterou? docker compose up -d --force-recreate gitea-runner
log:
  level: info
runner:
  file: .runner                  # registro (fica no volume runner_data)
  capacity: {args.runner_capacidade}                    # jobs ao mesmo tempo
  timeout: 1h                    # um job que passa disso é cancelado
  shutdown_timeout: 3m
  fetch_interval: 2s
  labels:                        # runs-on: ubuntu-latest  ->  esta imagem
    - "ubuntu-latest:docker://docker.gitea.com/runner-images:ubuntu-latest"
cache:
  enabled: true                  # actions/cache (ex.: ~/.platformio) sem sair da máquina
  dir: /data/cache
container:
{REDE_JOB}
  privileged: false              # os jobs NÃO são privilegiados (o runner é)
  options: "--memory=3g"
  valid_volumes: []              # nenhum job monta pasta desta máquina
  force_pull: false
""")
    print("🏃 runner/config.yaml")

# =====================================================================
# postgres/init/bancos.sql (idempotente; roda a cada subida no db-init)
# =====================================================================
if POSTGRES:
    sql = ["-- bancos.sql — gerado por gen_iot_aluno.py",
           "-- Idempotente: cria usuários/bancos que faltarem e re-sincroniza as senhas.", ""]
    bancos = []
    if GITEA_PG:
        bancos.append(("gitea", PG_GITEA_SENHA,
                       "ENCODING ''UTF8'' LC_COLLATE ''C'' LC_CTYPE ''C'' TEMPLATE template0"))
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
# .segredos.json
# =====================================================================
gravar(ARQ_SEGREDOS, json.dumps(SEGREDOS, indent=2))
try:
    os.chmod(ARQ_SEGREDOS, 0o600)
except OSError:
    pass

# =====================================================================
# credenciais.txt e LEIA-ME.md
# =====================================================================
U = LOCAL_URL
cred = [f"=== LAB IoT do {G} (na sua máquina) ===", "",
        f"Usuário: {G}        Senha: {SENHA[G]}",
        f"Só leitura (Node-RED): {G}-view   Senha: {SENHA[G + '-view']}", "",
        "A mesma senha vale para Node-RED, FUXA, Gitea, MicroBin, ntfy e MQTT Explorer" +
        (" (e é a do laboratório)." if SEGREDOS_LAB and not args.novas_senhas else "."), "",
        f"Nesta máquina:  {U}/"]
if LAN_URL:
    cred.append(f"Rede local:     {LAN_URL}/   (celular/ESP32 no mesmo Wi-Fi)")
cred += ["", f"Node-RED:   <base>/{G}/   ·   dashboard: <base>/{G}/dashboard"]
if FUXA:
    cred.append(f"FUXA:       <base>/fuxa/{G}/")
if GITEA:
    cred.append(f"Gitea:      <base>/git/   ·   organização {org_de(G)}" +
                (f"   ·   repositório {GITEA_REPO}" if GITEA_REPO else ""))
    cred.append(f"  git (nesta máquina): {GITEA_URL}{org_de(G)}/<repo>.git")
    if GITEA_REPO:
        cred.append(f"  Node-RED Projects:   http://gitea:3000/{org_de(G)}/{GITEA_REPO}.git")
if RUNNER:
    cred.append(f"  Actions: runner {G}-runner, {args.runner_capacidade} job(s) por vez, rótulo ubuntu-latest")
    cred.append(f"  Secrets da organização: NTFY_TOPIC={G}-ci, NTFY_TOKEN" +
                (", WOKWI_CLI_TOKEN" if WOKWI_TOKEN else "") + f"  ·  variable NTFY_URL={CI_URL}/ntfy")
if NTFY:
    cred.append(f"ntfy:       <base>/avisos/ (página)  ·  app: servidor {LINK_BASE}/ntfy  ·  tópicos {G}, {G}-*")
    cred.append(f"  token do Node-RED: {NTFY_TOKEN[G]}" + (f"   ·   token do CI: {NTFY_TOKEN_CI[G]}" if RUNNER else ""))
if WB:
    cred.append(f"MicroBin:   <base>/bin/   (administração: <base>/bin/admin)")
if MQTTX:
    cred.append(f"MQTT Explorer: {MQTTX_URL}")
cred.append(f"MQTT:       mosquitto:1883 (Node-RED/FUXA)  ·  {IP}:1883 (ESP32 na mesma rede)")
if PONTE:
    cred.append(f"Ponte MQTT: {G}/# <-> {PONTE} (broker do laboratório)")
gravar("credenciais.txt", "\n".join(cred) + "\n")


def tab(cab, linhas):
    return [f"| {cab[0]} | {cab[1]} |", "|---|---|"] + [f"| {a} | {b} |" for a, b in linhas]


leia = [f"# LAB IoT do {G} — na sua máquina", "",
        "O mesmo LAB IoT do laboratório, completo, rodando **no seu computador**: Node-RED"
        + (", FUXA (SCADA/HMI)" if FUXA else "") + ", broker MQTT"
        + (", Gitea com CI (Gitea Actions)" if GITEA else "")
        + (", notificações (ntfy)" if NTFY else "") + (" e MicroBin" if WB else "") + ".",
        "Os caminhos e os nomes dos serviços são **iguais aos do laboratório**: um fluxo ou uma",
        "tela feita aqui funciona lá sem mudar nada (e vice-versa).", "",
        "> ⚠️ Esta pasta tem as suas senhas. Não a publique (nem em repositório).", "",
        "## 1. Instalar (uma vez)", "",
        "1. **Docker Desktop** (Windows 11 com WSL 2, ou macOS) ou Docker Engine (Linux). Abra-o.",
        "   Em *Settings → Resources*, deixe pelo menos **4 GB** de memória"
        + (" (6 GB com o CI)." if RUNNER else "."),
        "2. Esta pasta num caminho sem espaços nem acentos, ex.: `C:\\iot\\" + G + "`."]
leia += ["", "## 2. Subir", "",
         "No PowerShell (ou terminal), dentro desta pasta:", "",
         "```powershell", "docker compose up -d --build", "```", "",
         "A primeira vez demora (monta a imagem do Node-RED e baixa as outras). Depois, o Docker",
         "Desktop sobe tudo sozinho quando o computador liga. Confira com `docker compose ps`:",
         "tudo `running`" + (", menos o `gitea-init`, que roda uma vez e sai" if GITEA else "") + ".", "",
         "## 3. Endereços e login", "",
         f"Usuário **`{G}`** · senha **`{SENHA[G]}`** (a mesma em todos os serviços)", "",
         "| Serviço | Endereço (nesta máquina) |", "|---|---|",
         f"| Portal | {U}/ |",
         f"| Node-RED (editor) | {U}/{G}/ |",
         f"| Dashboard | {U}/{G}/dashboard |"]
if FUXA:
    leia.append(f"| FUXA (SCADA/HMI) | {U}/fuxa/{G}/ |")
if GITEA:
    leia.append(f"| Gitea | {U}/git/ |")
if NTFY:
    leia.append(f"| Avisos (ntfy): ler e publicar | {U}/avisos/ |")
if WB:
    leia.append(f"| MicroBin | {U}/bin/ |")
if MQTTX:
    leia.append(f"| MQTT Explorer | {MQTTX_URL} |")
leia += ["", f"Só leitura no Node-RED (para mostrar sem risco): `{G}-view` · `{SENHA[G + '-view']}`"]
if LAN_URL:
    leia += ["", f"No celular ou em outro PC **na mesma rede** (Wi-Fi), troque `{U}` por **`{LAN_URL}`**.",
             "O LAB IoT não fica acessível pela internet."]
leia += ["", "## 4. Configurações (iguais às do laboratório)", ""]
linhas = [("Nós **mqtt** do Node-RED", f"servidor `mosquitto`, porta `1883`, tópicos `{G}/...`"),
          ("ESP32 / celular na mesma rede", f"`{IP}:1883` (o IP desta máquina)")]
if FUXA:
    linhas.append(("FUXA → Conexões → *MQTT client*", f"`mqtt://mosquitto:1883`, tópicos `{G}/...`"))
if NTFY:
    linhas.append(("ntfy no Node-RED", f"já configurado: `env.get(\"NTFY_URL\")`, `NTFY_TOPIC` (= `{G}`), `NTFY_TOKEN`"))
    linhas.append(("App ntfy no celular", f"servidor `{LINK_BASE}/ntfy`, usuário `{G}`, tópicos `{G}` e `{G}-ci`"))
if WB:
    linhas.append(("MicroBin no Node-RED", "já configurado: `MICROBIN_URL`, `MICROBIN_AUTH`, `MICROBIN_LINK`"))
if GITEA and GITEA_REPO:
    linhas.append(("Node-RED → *Projects* → *Clone repository*", f"`http://gitea:3000/{org_de(G)}/{GITEA_REPO}.git`"))
leia += tab(("Para", "Valor"), linhas)
if NTFY:
    leia += ["", f"Exemplo para importar no Node-RED: {U}/avisos/exemplo-node-red.json",
             "(aviso no ntfy e relatório longo no MicroBin com o link no aviso)."]
leia += ["", "> O ESP32 e o celular só alcançam esta máquina se o firewall permitir as portas "
         f"{PORTA_HTTP} e 1883", "> (no Windows, na primeira vez, marque **Redes privadas**)."]
if GITEA:
    leia += ["", "## 5. Gitea e CI (Gitea Actions)", "",
             f"Você é o **administrador** do Gitea. A organização `{org_de(G)}` já existe"
             + (f", com o repositório `{GITEA_REPO}`" if GITEA_REPO else "") + ".", "",
             "Pela linha de comando, use o **tea** (cliente oficial do Gitea) junto com o `git`.",
             "Uma vez só: o tea cria um token de acesso e passa a atender o `git` (sem pedir senha):", "",
             "```powershell",
             f"tea login add --name lab --url {GITEA_URL.rstrip('/')} --user {G} --password {SENHA[G]} --git-credentials",
             "tea login default lab",
             "```", "",
             "Criar um repositório na organização, clonar e enviar:", "",
             "```powershell",
             f"tea repos create --owner {org_de(G)} --name meu-projeto --private",
             f"tea clone {org_de(G)}/meu-projeto",
             "cd meu-projeto",
             "git add .",
             "git commit -m \"primeiro commit\"",
             "git push",
             "```", "",
             "Repositório que já existe no PC (ex.: o do GitHub): crie-o vazio com o `tea repos create`",
             "e acrescente o Gitea como segundo remoto:", "",
             "```powershell",
             f"git remote add lab {GITEA_URL}{org_de(G)}/meu-projeto.git",
             "git push lab main",
             "```", "",
             "O guia do aluno (seção *Git no Windows*) explica os avisos do Git Credential Manager",
             "sobre HTTP e o que fazer se o `git` pedir senha."]
    if RUNNER:
        leia += ["",
                 "Os workflows ficam em `.gitea/workflows/` (se a pasta não existir, o Gitea usa",
                 "`.github/workflows/`), com `runs-on: ubuntu-latest`. Os jobs rodam **nesta máquina**,",
                 f"num Docker separado (o runner `{G}-runner`, {args.runner_capacidade} job(s) por vez).", ""]
        leia += tab(("Já pronto na organização", "Valor"), [
            ("variable `NTFY_URL`", f"`{CI_URL}/ntfy`"),
            ("secret `NTFY_TOPIC`", f"`{G}-ci` (assine no app)"),
            ("secret `NTFY_TOKEN`", "token do CI no ntfy"),
            ("secret `WOKWI_CLI_TOKEN`", "o seu token do Wokwi CI" if WOKWI_TOKEN
             else "— (gere de novo com `--wokwi-token`)")])
        leia += [""] + ([
                 f"Dentro de um job, os serviços daqui estão em `{CI_URL}/` (Gitea, ntfy). Se esta",
                 "máquina mudar de rede (outro IP), gere de novo e rode `docker compose up -d`."] if CI_IP else [
                 f"Dentro de um job, `http://localhost{_porta}/` é o portal desta máquina (Gitea, ntfy) e",
                 "`mosquitto:1883` é o broker: o CI pode testar contra os serviços daqui."]) + [
                 "O primeiro job baixa a imagem dos jobs (~1,5 GB); os seguintes já a encontram.", "",
                 "Acompanhar o CI pelo terminal (dentro da pasta do repositório):", "",
                 "```powershell",
                 "tea actions runs list",
                 "tea actions runs logs <id>",
                 "tea actions workflows dispatch diagnostico.yml --ref main   # workflow com workflow_dispatch",
                 "```"]
if PONTE:
    leia += ["", "## Ponte MQTT com o laboratório", "",
             f"O broker daqui está ligado ao do laboratório (`{PONTE}`) **só nos tópicos `{G}/#`**, nos",
             "dois sentidos. Funciona com esta máquina na rede do laboratório; fora dela, tudo segue",
             "normal (a ponte tenta reconectar sozinha)."]
leia += ["", "## Levar o trabalho para o laboratório (e trazer de volta)", "",
         "**Node-RED → arquivo.** Menu → *Export* → *All flows* → *Download*; do outro lado, *Import*.", "",
         "**FUXA → arquivo.** Editor do FUXA: menu → *Salvar projeto como*; do outro lado, *Abrir projeto*.", "",
         "Como os nomes são os mesmos, as conexões (`mosquitto:1883`, tópicos) continuam valendo."]
leia += ["", "## Comandos úteis", "",
         "| Para | Comando |", "|---|---|",
         "| Ver o que está rodando | `docker compose ps` |",
         f"| Erros do Node-RED | `docker compose logs -f {G}-nodered` |"]
if RUNNER:
    leia.append("| Ver o runner do CI | `docker compose logs -f gitea-runner` |")
if GITEA:
    leia.append("| Refazer usuário/organização/secrets do Gitea | `docker compose run --rm gitea-init` |")
leia += ["| Parar (os dados ficam) | `docker compose down` |",
         "| Atualizar imagens | `docker compose pull`, `docker compose build --pull` e `docker compose up -d` |",
         "| Mudou alguma opção | rode o gerador de novo (mesma pasta) e `docker compose up -d --build` |", "",
         "Os dados ficam em `data/` (Node-RED)" + (", `fuxa/` (FUXA)" if FUXA else "")
         + " e nos volumes do Docker" + (" (Gitea, ntfy, MicroBin)" if GITEA else "") + ".",
         "Guarde também o `.segredos.json`: sem ele, uma nova geração sorteia senhas novas.", ""]
gravar("LEIA-ME.md", "\n".join(leia))

# =====================================================================
# relatório
# =====================================================================
print(f"\n✅ LAB IoT do {G}: Node-RED" + (" + FUXA" if FUXA else "") + " + MQTT"
      + (" + Gitea" if GITEA else "") + (" (Actions)" if RUNNER else "")
      + (" + ntfy" if NTFY else "") + (" + MicroBin" if WB else "")
      + (" + MQTT Explorer" if MQTTX else ""))
print(f"\n  Nesta máquina: {LOCAL_URL}/")
if LAN_URL:
    print(f"  Rede local:    {LAN_URL}/   ·   MQTT {IP}:1883")
print(f"\n🔒 Usuário {G} · senha em credenciais.txt" +
      (" (a do laboratório)" if SEGREDOS_LAB and not args.novas_senhas else ""))
print(f"\n📂 {SAIDA_ABS}")
print(f"▶  cd {SAIDA_ABS}  e  docker compose up -d --build   (instruções no LEIA-ME.md)")
