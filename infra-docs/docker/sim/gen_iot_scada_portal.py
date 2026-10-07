#!/usr/bin/env python3
"""Gera o LAB IoT: portal nginx + Node-RED e FUXA por grupo + MQTT + Gitea + MicroBin + ntfy + túnel.

Tudo fica sob UM endereço, em caminhos (sem DNS, sem subdomínios):

    <base>/            portal
    <base>/lab05-a/    Node-RED do grupo A   (… um por grupo)
    <base>/lab05-p/    Node-RED do professor
    <base>/lab05-n/    Node-RED do painel de notas
    <base>/git/        Gitea  (uma organização por grupo)
    <base>/bin/        MicroBin (colar texto/código e enviar arquivos; único)
    <base>/ntfy/       ntfy (notificações push; um tópico por grupo: lab05-a, lab05-a-*)
    <base>/avisos/     página web do ntfy (ler e publicar; texto longo vai para o MicroBin)
    <base>/fuxa/lab05-a/  FUXA (SCADA/HMI) do grupo A  (… um por grupo + professor)

onde <base> é:
    - na rede do laboratório:  http://<IP-do-servidor>      (sem cota, sem internet)
    - de qualquer lugar:       https://iot.adrianoruseler.com   (VPS com Apache)

Os serviços rodam no servidor do laboratório. Um container "tunel" abre um túnel SSH
REVERSO até o VPS (sai do laboratório: não precisa abrir portas na rede da instituição),
e o Apache do VPS encaminha o HTTPS público para esse túnel.

Reservas de letras: 'p' = PROFESSOR (ex.: lab05-p) · 'n' = NOTAS (ex.: lab05-n)

Gera, dentro da pasta de saída (--saida, padrão: <lab>):
  docker-compose.yml, Dockerfile, nginx/, settings/, data/, mosquitto/, mqtt-explorer/,
  gitea/init/, postgres/init/, fuxa/ (dados do FUXA de cada grupo), tunel/ (cliente do túnel + chave SSH),
  vps/ (arquivos para o VPS: proxy do Apache, página offline e setup-vps.sh),
  credenciais.txt e .segredos.json (senhas reaproveitadas entre execuções).

KIT DO GRUPO (--kit): o mesmo ambiente de UM grupo (Node-RED, FUXA, MQTT e ntfy) para o
aluno rodar na própria máquina, com os mesmos caminhos e nomes de serviço do laboratório
(fluxos e telas funcionam sem mudar nada nos dois lugares). Se existir <lab>/.segredos.json,
o kit usa a mesma senha e o mesmo credentialSecret do grupo no laboratório.
  py gen_iot_scada_portal.py --lab lab05 --kit a              # pasta lab05-kits/lab05-a + .zip
  py gen_iot_scada_portal.py --lab lab05 --grupos 10 --kit todos   # um kit (e .zip) por grupo
  py gen_iot_scada_portal.py --kit a --ponte-mqtt 192.168.0.10     # liga o MQTT do kit ao do lab

Uso:
  py gen_iot_scada_portal.py --lab lab05 --grupos 10 --ip 192.168.0.10
  py gen_iot_scada_portal.py --sem-tunel            # só rede local (http://IP/)
  py gen_iot_scada_portal.py --novas-senhas         # sorteia senhas novas para todos
  py gen_iot_scada_portal.py --gitea-db sqlite   # sem PostgreSQL (Gitea em SQLite)
"""
import sys, os, re, secrets, string, argparse, json, shutil, subprocess, base64, hashlib
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
ap.add_argument("--sem-microbin", action="store_true", help="Não inclui o MicroBin (/bin/)")
ap.add_argument("--sem-fuxa", action="store_true",
                help="Não inclui o FUXA (SCADA/HMI por grupo em /fuxa/<grupo>/)")
ap.add_argument("--sem-ntfy", action="store_true",
                help="Não inclui o ntfy (notificações push por grupo em /ntfy/ e /avisos/)")
ap.add_argument("--proteger-http", action="store_true",
                help="Exige login (usuário/senha do grupo) nos dashboards e endpoints HTTP do Node-RED")
ap.add_argument("--novas-senhas", action="store_true",
                help="Sorteia senhas novas para todos os grupos (padrão: mantém as já geradas)")
ap.add_argument("--github-org", default="ELT85B-N21-2026-2",
                help="Organização do GitHub com os repositórios <lab>-grupo-<letra> (para publicar os acessos)")
ap.add_argument("--saida", default=None,
                help="Pasta de saída (padrão: <lab>; com --kit: <lab>-kits/<grupo>; com --kit todos: pasta base)")
ap.add_argument("--kit", default=None, metavar="GRUPO",
                help="Gera o kit de UM grupo para a máquina do aluno (ex.: a ou lab05-a; 'todos' = um por grupo)")
ap.add_argument("--ponte-mqtt", default=None, metavar="HOST[:PORTA]",
                help="Kit: liga (bridge) o broker do kit ao broker do lab, só com os tópicos do grupo")
ap.add_argument("--porta-http", type=int, default=80,
                help="Kit: porta do portal na máquina do aluno (padrão 80; use 8080 se a 80 estiver ocupada)")
ap.add_argument("--segredos", default=None,
                help="Kit: .segredos.json do lab para reaproveitar as senhas (padrão: <lab>/.segredos.json)")
ap.add_argument("--mqtt-explorer-auth", action="store_true", help="Exige login no MQTT Explorer")
ap.add_argument("--mqtt-explorer-usuario", default="admin", help="Usuário do MQTT Explorer")
ap.add_argument("--mqtt-explorer-senha", default=None, help="Senha do MQTT Explorer (gerada se omitida)")
ap.add_argument("--mqtt-explorer-porta", type=int, default=3001, help="Porta do MQTT Explorer")
args = ap.parse_args()

LAB = args.lab.lower()
if not re.fullmatch(r"[a-z][a-z0-9]{1,20}", LAB):
    sys.exit("--lab deve começar com letra e ter só letras/dígitos (ex.: lab05), "
             "pois vira caminho da URL, usuário dos serviços e prefixo MQTT.")
N = args.grupos
IP = args.ip
DOMINIO = args.dominio

# ---------------- kit do grupo (máquina do aluno) ----------------
KIT = None
if args.kit:
    _k = args.kit.lower()
    if _k == "todos":   # um kit por grupo: roda este script de novo para cada letra
        _letras = [c for c in string.ascii_lowercase if c not in ("p", "n")][:N]
        _base = args.saida or f"{LAB}-kits"
        _argv, _pula = [], False
        for _a in sys.argv[1:]:
            if _pula:
                _pula = False
                continue
            if _a in ("--kit", "--saida"):
                _pula = True
                continue
            if _a.startswith(("--kit=", "--saida=")):
                continue
            _argv.append(_a)
        for _l in _letras:
            _r = subprocess.run([sys.executable, os.path.abspath(__file__), *_argv,
                                 "--kit", _l, "--saida", os.path.join(_base, f"{LAB}-{_l}")])
            if _r.returncode:
                sys.exit(_r.returncode)
        print(f"\n📦 {len(_letras)} kits em {os.path.abspath(_base)}  ({LAB}-<letra>.zip para enviar a cada grupo)")
        sys.exit(0)
    _k = _k[len(LAB) + 1:] if _k.startswith(LAB + "-") else _k
    if not re.fullmatch(r"[a-z]", _k) or _k in ("p", "n"):
        sys.exit("--kit deve ser a letra de um grupo de alunos (ex.: a ou lab05-a), ou 'todos'.")
    KIT = f"{LAB}-{_k}"
    # senhas do grupo no laboratório (lidas ANTES de mudar para a pasta do kit)
    _arq = args.segredos or os.path.join(LAB, ".segredos.json")
    try:
        with open(_arq, encoding="utf-8") as _f:
            _lab_seg = json.load(_f)
    except (OSError, ValueError):
        _lab_seg = {}
    SEGREDOS_LAB = {k: v for k, v in _lab_seg.items()
                    if k in (f"senha:{KIT}", f"senha:{KIT}-view", f"credential_secret:{KIT}")}

# ---------------- pasta de saída e segredos persistentes ----------------
SAIDA = args.saida or (os.path.join(f"{LAB}-kits", KIT) if KIT else LAB)
os.makedirs(SAIDA, exist_ok=True)
os.chdir(SAIDA)
SAIDA_ABS = os.getcwd()

ARQ_SEGREDOS = ".segredos.json"
try:
    with open(ARQ_SEGREDOS, encoding="utf-8") as _f:
        SEGREDOS = json.load(_f)
except (OSError, ValueError):
    SEGREDOS = {}
if KIT and SEGREDOS_LAB and not args.novas_senhas:
    SEGREDOS.update(SEGREDOS_LAB)   # mesma senha/credentialSecret do grupo no laboratório


def segredo(nome, gerar, renovar=False):
    """Valor guardado em .segredos.json; só é gerado na primeira vez (ou se renovar)."""
    if renovar or nome not in SEGREDOS:
        SEGREDOS[nome] = gerar()
    return SEGREDOS[nome]


def gerar_senha(tamanho=8):
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))


# ---------------- endereços ----------------
TUNEL = not args.sem_tunel and not KIT
PORTA_HTTP = args.porta_http if KIT else 80
LOCAL_URL = ("http://localhost" if IP.startswith("127.") else f"http://{IP}") + \
    ("" if PORTA_HTTP == 80 else f":{PORTA_HTTP}")
PUBLICO_URL = args.publico_url.rstrip("/")
if TUNEL and (not PUBLICO_URL.startswith("https://") or urlparse(PUBLICO_URL).path not in ("", "/")):
    sys.exit("--publico-url deve ser https://<host> sem caminho (ex.: https://iot.adrianoruseler.com)")
PUBLIC_URL = PUBLICO_URL if TUNEL else LOCAL_URL        # URL "oficial" (links do Gitea)
PUBLIC_HOST = urlparse(PUBLIC_URL).hostname
VPS_HOST = args.vps_host or urlparse(PUBLICO_URL).hostname
VPS_PORTA_TUNEL = args.vps_porta_tunel

# ---------------- serviços opcionais ----------------
WB = not args.sem_microbin and not KIT
MQTTX = not KIT            # MQTT Explorer (imagem local do professor) só no laboratório
WB_IMAGEM = "danielszabo99/microbin:2.1.4"
# MicroBin visto pelo Node-RED: no lab, direto no container; no kit, o do lab (público, com login)
WB_NR = WB or (KIT is not None and not args.sem_microbin)
WB_NR_URL = "http://microbin:8080" if WB else f"{PUBLICO_URL}/bin"
WB_LINK = f"{PUBLICO_URL}/bin" if (KIT or TUNEL) else f"{LOCAL_URL}/bin"   # link para abrir no celular
NTFY = not args.sem_ntfy
NTFY_IMAGEM = "binwiederhier/ntfy:v2.28.0"
NTFY_AVISOS = f"{LAB}-avisos"          # tópico de avisos do professor (todos leem)
FUXA = not args.sem_fuxa
FUXA_IMAGEM = "frangoteam/fuxa:1.3.4"     # versão fixa (BASE_PATH para subcaminho existe desde 1.3.x)

GITEA = not args.sem_gitea and not KIT
# no kit, o Gitea é o do laboratório (público): Projects do Node-RED clona/envia por HTTPS
GITEA_LAB = f"{PUBLICO_URL}/git" if (KIT and not args.sem_gitea) else None
GITEA_REPO = args.gitea_repo.strip()
GITEA_PG = GITEA and args.gitea_db == "postgres"

POSTGRES = GITEA_PG
_pg_senha = lambda: secrets.token_hex(16)
PG_ROOT_SENHA = segredo("postgres_root", _pg_senha) if POSTGRES else None
PG_GITEA_SENHA = segredo("postgres_gitea", _pg_senha) if GITEA_PG else None

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
if KIT:   # só o grupo do kit (sem professor/notas)
    grupos_alunos = [KIT]
    todos_servicos = [KIT]
    N = 1
fuxa_grupos = ((grupos_alunos + [prof]) if not KIT else [KIT]) if FUXA else []   # um FUXA por grupo + professor

C = KIT or LAB  # prefixo dos nomes de container (lab05-portal, ...; no kit: lab05-a-portal, ...)


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
# ntfy/server.yml — UM ntfy para todo o lab, isolado por ACL:
#   cada grupo lê/escreve só em <grupo> e <grupo>-*  (ex.: lab05-a, lab05-a-alarme)
#   todos leem <lab>-avisos; notas lê tudo; professor é admin (lê/escreve tudo)
# Usuários, permissões e tokens são declarativos (re-sincronizados a cada subida).
# =====================================================================
NTFY_TOKEN = {}
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
        if papel == "admin":
            continue                      # admin já pode tudo (e não aceita ACL)
        ny_access += [f"{u}:{u}:rw", f"{u}:{u}-*:rw"]
        if not KIT:
            ny_access.append(f"{u}:{NTFY_AVISOS}:ro")
            if is_notas(u):
                ny_access.append(f"{u}:{LAB}-*:ro")   # avaliação: lê os tópicos de todos
    yml = [f"# server.yml do ntfy — gerado por gen_iot_scada_portal.py ({KIT or LAB})",
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
    f"# LAB IoT {LAB} — gerado por gen_iot_scada_portal.py\n",
    (f"# KIT do grupo {KIT} (máquina do aluno) — mesmos caminhos e nomes do laboratório\n" if KIT else
     f"# {N} grupos + professor ({prof}) + notas ({notas_service})\n"),
    f"# Local:   {LOCAL_URL}/\n",
    (f"# Público: {PUBLICO_URL}/   (túnel SSH -> Apache do VPS)\n" if TUNEL else ""),
    "# Subir:   docker compose up -d --build\n",
    "services:\n",
    "  nginx:\n",
    "    image: nginx:alpine\n",
    f"    container_name: {C}-portal\n",
    "    restart: unless-stopped\n",
    "    ports:\n",
    f'      - "{PORTA_HTTP}:80"\n',
    "    volumes:\n",
    "      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro\n",
    "      - ./nginx/html:/usr/share/nginx/html:ro\n",
    "      - ./nginx/htpasswd:/etc/nginx/htpasswd:ro\n",
    ("      - ./nginx/htpasswd.d:/etc/nginx/htpasswd.d:ro\n" if FUXA and args.proteger_http else ""),
    "    depends_on:\n",
]
c += [f"      - {g}-nodered\n" for g in todos_servicos]
if MQTTX:
    c += ["      - mqtt-explorer\n"]
if GITEA:
    c += ["      - gitea\n"]
if WB:
    c += ["      - microbin\n"]
if NTFY:
    c += ["      - ntfy\n"]
c += [f"      - {g}-fuxa\n" for g in fuxa_grupos]
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
        f"      - GRUPO={g}\n",
    ]
    if NTFY:   # no Node-RED: env.get("NTFY_URL"), env.get("NTFY_TOPIC"), env.get("NTFY_TOKEN")
        c += [
            "      - NTFY_URL=http://ntfy\n",
            f"      - NTFY_TOPIC={g}\n",
            f"      - NTFY_TOKEN={NTFY_TOKEN[g]}\n",
        ]
        if not KIT:
            c += [f"      - NTFY_AVISOS={NTFY_AVISOS}\n"]
    if WB_NR:  # MicroBin: no lab, direto no container; no kit, pelo endereço público (com login)
        c += [
            f"      - MICROBIN_URL={WB_NR_URL}\n",
            f"      - MICROBIN_LINK={WB_LINK}\n",
            f"      - MICROBIN_AUTH=Basic {base64.b64encode(f'{g}:{SENHA[g]}'.encode()).decode()}\n",
        ]
    c += [
        "    depends_on:\n",
        "      - mosquitto\n",
        "    networks:\n",
        "      - labnet\n",
    ]

# MQTT Explorer (único; só na rede local, porta direta — não suporta subcaminho)
_mx = [
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
    _mx += [
        "      - MQTT_EXPLORER_SKIP_AUTH=false\n",
        f"      - MQTT_EXPLORER_USERNAME={MQTTX_USER}\n",
        f"      - MQTT_EXPLORER_PASSWORD={MQTTX_SENHA}\n",
    ]
else:
    _mx += ["      - MQTT_EXPLORER_SKIP_AUTH=true\n"]
_mx += [
    "    volumes:\n",
    "      - ./mqtt-explorer/data:/app/data\n",
    "    depends_on:\n",
    "      - mosquitto\n",
    "    networks:\n",
    "      - labnet\n",
]
if MQTTX:
    c += _mx

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

# MicroBin (único): colar textos/código e enviar arquivos. Roda na raiz do container e
# gera os links com MICROBIN_PUBLIC_PATH=/bin (relativo: vale no IP e no domínio); o nginx
# retira o /bin. Sem login próprio para criar: o nginx exige o usuário/senha de um grupo
# (htpasswd). Painel /bin/admin com o login do professor. Sem telemetria/checagem de versão.
if WB:
    c += [
        "\n  microbin:\n",
        f"    image: {WB_IMAGEM}\n",
        f"    container_name: {C}-microbin\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - MICROBIN_PUBLIC_PATH=/bin\n",
        # links copiados e QR codes: endereço absoluto (abre no celular, fora do lab)
        f"      - MICROBIN_SHORT_PATH={PUBLIC_URL}/bin\n",
        ("      - MICROBIN_QR=true\n" if TUNEL else ""),
        f"      - MICROBIN_TITLE=MicroBin · {LAB.upper()}\n",
        f"      - MICROBIN_ADMIN_USERNAME={prof}\n",
        f"      - MICROBIN_ADMIN_PASSWORD={SENHA[prof]}\n",
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

# ntfy (único): notificações push. Isolamento entre grupos por ACL (ntfy/server.yml).
# O rótulo com o hash do server.yml faz o "docker compose up -d" recriar o container
# quando usuários/senhas/tokens mudam.
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

# FUXA (SCADA/HMI/Dashboard): um por grupo + professor, em /fuxa/<grupo>/ (BASE_PATH).
# Conversa com o Node-RED do grupo pelo broker MQTT (mosquitto:1883, tópicos <grupo>/...).
# Usuários (grupo + professor) e o segredo do token são semeados pelo gerador em
# fuxa/<grupo>/appdata (users.fuxap.db e mysettings.json): não existe o admin/123456 padrão.
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
        "    depends_on:\n",
        "      - mosquitto\n",
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
    f"# nginx.conf — gerado por gen_iot_scada_portal.py ({LAB})\n",
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
    "        listen 80 default_server;\n",
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
    if args.proteger_http:   # também exige o login do grupo antes de abrir (até para ver telas)
        extra += [f'auth_basic "FUXA - {g}";', f"auth_basic_user_file /etc/nginx/htpasswd.d/{g};"]
    n += [f"\n        # FUXA (SCADA/HMI) do {g} -> /fuxa/{g}/\n",
          f"        location = /fuxa/{g} {{ return 301 /fuxa/{g}/; }}\n"]
    n += location(f"/fuxa/{g}/", extra + [f"set $alvo http://{g}-fuxa:1881;", "proxy_pass $alvo;"])
if fuxa_grupos:
    n += ["        location = /fuxa { return 302 /#fuxa; }\n",
          "        location = /fuxa/ { return 302 /#fuxa; }\n"]
if MQTTX:
    n += ["\n        # MQTT Explorer não suporta subcaminho: só na rede local, porta direta\n",
          f"        location /mqtt {{ return 302 http://{IP}:{MQTTX_PORTA}/; }}\n"]
n += ["    }\n", "}\n"]
gravar("nginx/nginx.conf", "".join(n))

# htpasswd do nginx ({SSHA}: SHA-1 com sal, formato aceito pelo auth_basic):
# todos os grupos, o professor e as notas entram com o próprio usuário/senha
def _ssha(senha):
    sal = secrets.token_bytes(8)
    return "{SSHA}" + base64.b64encode(hashlib.sha1(senha.encode() + sal).digest() + sal).decode()


gravar("nginx/htpasswd", "".join(f"{u}:{_ssha(SENHA[u])}\n" for u in todos_servicos))
if FUXA and args.proteger_http:   # FUXA de cada grupo: só o grupo e o professor
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
# fuxa/<grupo>/appdata — usuários (users.fuxap.db) e mysettings.json
# O FUXA só cria o admin/123456 quando o banco de usuários NÃO existe; aqui o banco já
# nasce com o grupo e o professor (administradores, bcrypt) e o admin padrão é removido.
# Re-executar o gerador re-sincroniza as senhas; usuários criados no FUXA são mantidos.
# =====================================================================
import sqlite3


def semear_fuxa(g):
    appdata = f"fuxa/{g}/appdata"
    for sub in ("appdata", "db", "images"):
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
if WB:
    cards.append(
        '      <a class="node node--bin" href="/bin/">\n'
        '        <span class="node__idx">bin · todo o lab</span>\n'
        '        <span class="node__name">MicroBin</span>\n'
        '        <span class="node__topic">colar código e enviar arquivos</span>\n'
        '        <span class="node__go">abrir (login do grupo) &rarr;</span>\n'
        '      </a>\n')
if GITEA:
    cards.append(
        '      <a class="node node--git" href="/git/">\n'
        '        <span class="node__idx">git</span>\n'
        '        <span class="node__name">Gitea</span>\n'
        f'        <span class="node__topic">{LAB}-grupo-&lt;letra&gt;</span>\n'
        '        <span class="node__go">abrir repositórios &rarr;</span>\n'
        '      </a>\n')
if MQTTX:
    cards.append(
        f'      <a class="node node--mqtt" href="{MQTTX_URL}">\n'
        '        <span class="node__idx">mqtt · rede local</span>\n'
        '        <span class="node__name">MQTT Explorer</span>\n'
        '        <span class="node__topic">#  ·  broker do lab</span>\n'
        f'        <span class="node__go">abrir explorer{" (login)" if MQTTX_AUTH else ""} &rarr;</span>\n'
        '      </a>\n')
if GITEA_LAB:   # kit: atalho para a organização do grupo no Gitea do laboratório
    cards.append(
        f'      <a class="node node--git" href="{GITEA_LAB}/{org_de(KIT)}">\n'
        '        <span class="node__idx">git · laboratório</span>\n'
        '        <span class="node__name">Gitea do lab</span>\n'
        f'        <span class="node__topic">{org_de(KIT)}</span>\n'
        '        <span class="node__go">abrir repositórios &rarr;</span>\n'
        '      </a>\n')

mailbox_html = ""
if FUXA and KIT:
    cards.append(
        f'      <a class="node node--fuxa" href="/fuxa/{KIT}/">\n'
        '        <span class="node__idx">scada</span>\n'
        '        <span class="node__name">FUXA (SCADA/HMI)</span>\n'
        '        <span class="node__topic">telas ligadas ao MQTT</span>\n'
        '        <span class="node__go">abrir FUXA &rarr;</span>\n'
        '      </a>\n')
elif FUXA:
    cards.append(
        '      <a class="node node--fuxa" href="#fuxa">\n'
        '        <span class="node__idx">scada · por grupo</span>\n'
        '        <span class="node__name">FUXA (SCADA/HMI)</span>\n'
        '        <span class="node__topic">telas ligadas ao MQTT</span>\n'
        '        <span class="node__go">escolher o grupo &darr;</span>\n'
        '      </a>\n')
    chips = "".join(
        f'        <a class="chip" href="/fuxa/{g}/">{"professor" if is_prof(g) else g}</a>\n'
        for g in fuxa_grupos)
    mailbox_html += ('    <section class="mailbox mailbox--fuxa" id="fuxa">\n'
                     '      <h2>FUXA (SCADA/HMI) de cada grupo</h2>\n'
                     '      <div class="chips">\n' + chips + '      </div>\n'
                     '    </section>\n')
if NTFY:
    cards.append(
        '      <a class="node node--ntfy" href="/avisos/">\n'
        f'        <span class="node__idx">ntfy · {"grupo" if KIT else "por grupo"}</span>\n'
        '        <span class="node__name">Avisos (ntfy)</span>\n'
        f'        <span class="node__topic">{KIT or LAB + "-&lt;letra&gt;"}  ·  celular e Node-RED</span>\n'
        '        <span class="node__go">ler e publicar &rarr;</span>\n'
        '      </a>\n')

rodape = [f"<span>local: {LOCAL_URL}/</span>"]
if TUNEL:
    rodape.append(f"<span>público: {PUBLICO_URL}/</span>")
if KIT:
    rodape += ["<span>MQTT: IP-desta-máquina:1883</span>", f"<span>tópicos: {KIT}/</span>"]
    if PONTE:
        rodape.append(f"<span>ponte MQTT com o lab: {PONTE}</span>")
else:
    rodape += [f"<span>MQTT: {IP}:1883</span>", f"<span>tópico base: {LAB}-&lt;letra&gt;/</span>"]

html = (PORTAL_HTML
        .replace("{{CARDS}}", "".join(cards))
        .replace("{{MAILBOX}}", mailbox_html)
        .replace("{{RODAPE}}", "\n      ".join(rodape))
        .replace("{{LAB}}", LAB))
if KIT:
    html = (html.replace(f"Painel do {LAB}", f"Kit do {KIT}")
            .replace(f"broker online &middot; {LAB}", f"na sua máquina &middot; {KIT}")
            .replace(f"""Selecione seu grupo para abrir o editor Node-RED. Cada grupo
      publica no broker MQTT sob seu próprio tópico, no formato
      <code>{LAB}-&lt;letra&gt;/#</code>.""",
                     f"""O ambiente do grupo rodando no seu computador, com os mesmos
      caminhos e nomes do laboratório: fluxos e telas funcionam nos dois lugares.
      Tópicos MQTT do grupo: <code>{KIT}/#</code>."""))
gravar("nginx/html/index.html", html)
# o laboratório fica público: pede aos robôs de busca/IA que não indexem nada
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
        "grupos": grupos_alunos,
        "notas": None if KIT else notas_service,
        "avisos": None if KIT else NTFY_AVISOS,
        "publico": PUBLICO_URL if TUNEL else None,
        "microbin": WB,                 # o kit não tem MicroBin próprio (CORS): só o Node-RED usa
        "binLink": WB_LINK,
    }
    gravar("nginx/html/avisos/index.html",
           AVISOS_HTML.replace("__CFG__", json.dumps(avisos_cfg, ensure_ascii=False))
           .replace("__LAB__", KIT or LAB).replace("__EXEMPLO__", grupos_alunos[0]))
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
# gitea-init.sh — gerado por gen_iot_scada_portal.py (lab __TURMA__)
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
  for u in repo.code repo.issues repo.pulls repo.releases repo.wiki repo.projects; do
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
    sql = ["-- bancos.sql — gerado por gen_iot_scada_portal.py",
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
# tunel/ (cliente do túnel SSH reverso, roda no laboratório)
# =====================================================================
TUNEL_DOCKERFILE = """FROM alpine:3.20
RUN apk add --no-cache openssh-client bash
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
"""

TUNEL_ENTRYPOINT = r"""#!/bin/bash
# entrypoint.sh do túnel — gerado por gen_iot_scada_portal.py
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
VPS_PROXY_CONF = """# iot-lab — proxy do Apache para o túnel do laboratório (gerado por gen_iot_scada_portal.py)
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

# Todo o resto vai para o túnel (portal, Node-RED, FUXA, Gitea, MicroBin, ntfy), com WebSocket.
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
# setup-vps.sh — gerado por gen_iot_scada_portal.py
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

# Cada editor Node-RED, tela do FUXA, dashboard e assinatura do ntfy mantém uma conexão = 1 thread do Apache.
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
# KIT DO GRUPO: credenciais.txt, LEIA-ME.md, .zip e fim
# =====================================================================
if KIT:
    g, L = KIT, letra_de(KIT).upper()
    U = LOCAL_URL
    gl = GITEA_LAB
    repo_lab = f"{gl}/{org_de(g)}/{GITEA_REPO}.git" if (gl and GITEA_REPO) else None
    cred = [f"=== KIT {g.upper()} (máquina do aluno) ===", "",
            f"Usuário: {g}        Senha: {SENHA[g]}",
            f"Só leitura (Node-RED): {g}-view   Senha: {SENHA[g + '-view']}", "",
            "A mesma senha vale para Node-RED, FUXA e ntfy" +
            (" (e é a do laboratório)." if SEGREDOS_LAB and not args.novas_senhas else "."), "",
            f"Portal:    {U}/", f"Node-RED:  {U}/{g}/", f"Dashboard: {U}/{g}/dashboard"]
    if FUXA:
        cred.append(f"FUXA:      {U}/fuxa/{g}/")
    if NTFY:
        cred.append(f"Avisos:    {U}/avisos/   (ntfy; app no celular: servidor http://IP-desta-máquina/ntfy)")
        cred.append(f"ntfy:      tópicos {g} e {g}-*  ·  token do Node-RED: {NTFY_TOKEN[g]}")
    cred.append(f"MQTT:      mosquitto:1883 (Node-RED/FUXA)  ·  IP-desta-máquina:1883 (ESP32)")
    if PONTE:
        cred.append(f"Ponte MQTT: {g}/# <-> {PONTE} (broker do laboratório)")
    if repo_lab:
        cred.append(f"Gitea do lab: {repo_lab}")
    gravar("credenciais.txt", "\n".join(cred) + "\n")

    def tab(linhas):
        return ["| | |", "|---|---|"] + [f"| {a} | {b} |" for a, b in linhas]

    leia = [f"# Kit do {g.upper()} — LAB IoT na sua máquina", "",
            "Este kit roda **no seu computador** o mesmo ambiente do seu grupo no laboratório:",
            "Node-RED" + (", FUXA (SCADA/HMI)" if FUXA else "") + ", broker MQTT" +
            (" e notificações (ntfy)" if NTFY else "") + ".",
            "Os caminhos e os nomes dos serviços são **iguais aos do laboratório**: um fluxo ou",
            "uma tela feita aqui funciona lá sem mudar nada (e vice-versa).", "",
            "> ⚠️ Esta pasta tem as senhas do grupo. Não publique fora do repositório privado do grupo.", "",
            "## 1. Instalar (uma vez)", "",
            "1. Instale o **Docker Desktop** (Windows 11, com WSL 2) e abra-o.",
            "2. Descompacte este kit numa pasta sem espaços/acentos, ex.: `C:\\iot\\" + g + "`.", "",
            "## 2. Subir", "",
            "No PowerShell, dentro da pasta do kit:", "",
            "```powershell", "docker compose up -d --build", "```", "",
            "A primeira vez demora alguns minutos (monta a imagem do Node-RED).",
            "Depois, o Docker Desktop sobe tudo sozinho quando o computador liga.", "",
            "## 3. Endereços e login", "",
            f"Usuário **`{g}`** · senha **`{SENHA[g]}`** (a mesma em todos)", "",
            "| Serviço | Endereço |", "|---|---|",
            f"| Portal | {U}/ |",
            f"| Node-RED (editor) | {U}/{g}/ |",
            f"| Dashboard | {U}/{g}/dashboard |"]
    if FUXA:
        leia.append(f"| FUXA (SCADA/HMI) | {U}/fuxa/{g}/ |")
    if NTFY:
        leia.append(f"| Avisos (ntfy): ler e publicar | {U}/avisos/ |")
    leia += ["", f"Só leitura no Node-RED (para mostrar sem risco): `{g}-view` · `{SENHA[g + '-view']}`", "",
             "## 4. Configurações (iguais às do laboratório)", ""]
    linhas = [("Nós **mqtt** do Node-RED", f"servidor `mosquitto`, porta `1883`, tópicos `{g}/...`"),
              ("ESP32 / celular na sua rede", "IP do seu PC (`ipconfig`), porta `1883`")]
    if FUXA:
        linhas.append(("FUXA → Conexões → *MQTT client*", "`mqtt://mosquitto:1883`, tópicos `" + g + "/...`"))
    if NTFY:
        linhas.append(("ntfy no Node-RED", f"já configurado: `env.get(\"NTFY_URL\")`, `NTFY_TOPIC` (= `{g}`), `NTFY_TOKEN`"))
        linhas.append(("App ntfy no celular (mesma rede)", f"servidor `http://IP-do-seu-PC/ntfy`, usuário `{g}`, tópico `{g}`"))
        if WB_NR:
            linhas.append(("MicroBin (o do laboratório)", "`MICROBIN_URL`, `MICROBIN_AUTH`, `MICROBIN_LINK` (precisa de internet)"))
    leia += tab(linhas)
    if NTFY:
        leia += ["", f"Exemplo pronto para importar no Node-RED: {U}/avisos/exemplo-node-red.json",
                 "(aviso no ntfy e relatório longo no MicroBin com link no aviso)."]
    leia += ["", "> O ESP32 só alcança o seu PC se o Firewall do Windows permitir a porta 1883",
             "> (na primeira vez o Windows pergunta; marque **Redes privadas**).", "",
             "## 5. Levar o trabalho para o laboratório (e trazer de volta)", ""]
    if repo_lab:
        leia += ["**Node-RED → Gitea do laboratório (recomendado).** No Node-RED: menu → *Projects* →",
                 "*New* → *Clone repository*:", "",
                 f"- URL: `{repo_lab}`",
                 f"- usuário `{g}` e a senha do grupo", "",
                 "Faça *commit* e *push* aqui; no laboratório, *pull* no Node-RED do grupo",
                 f"(lá a URL interna é `http://gitea:3000/{org_de(g)}/{GITEA_REPO}.git`).", ""]
    leia += ["**Node-RED → arquivo.** Menu → *Export* → *All flows* → *Download*; no outro lado, *Import*.", ""]
    if FUXA:
        leia += ["**FUXA → arquivo.** No editor do FUXA: menu → *Salvar projeto como* (gera um `.json`);",
                 "no outro FUXA: *Abrir projeto*. Como os endereços são iguais, as conexões MQTT continuam valendo.", ""]
    if PONTE:
        leia += ["## 6. Ponte MQTT com o laboratório", "",
                 f"O broker do kit está ligado ao broker do laboratório (`{PONTE}`) **só nos tópicos `{g}/#`**,",
                 "nos dois sentidos: o que o seu ESP32 publica aqui aparece no FUXA/Node-RED do grupo no",
                 "laboratório. Funciona quando o seu computador está na rede do laboratório; fora dela o kit",
                 "segue normal (a ponte tenta reconectar sozinha).", ""]
    leia += ["## Comandos úteis", "",
             "| Para | Comando |", "|---|---|",
             "| Ver o que está rodando | `docker compose ps` |",
             f"| Ver erros do Node-RED | `docker compose logs -f {g}-nodered` |",
             "| Parar (os dados ficam) | `docker compose down` |",
             "| Atualizar imagens | `docker compose pull` e `docker compose up -d --build` |", "",
             "Os dados ficam nesta pasta: `data/` (fluxos do Node-RED)" +
             (", `fuxa/` (projeto e históricos do FUXA)" if FUXA else "") + ".",
             f"Se a porta 80 já estiver em uso, troque `\"{PORTA_HTTP}:80\"` por `\"8080:80\"` no",
             "`docker-compose.yml` e use `http://localhost:8080/`.", ""]
    gravar("LEIA-ME.md", "\n".join(leia))

    pasta = os.path.basename(SAIDA_ABS)
    zipf = shutil.make_archive(os.path.join(os.path.dirname(SAIDA_ABS), pasta), "zip",
                               os.path.dirname(SAIDA_ABS), pasta)
    origem = "senha do laboratório" if (SEGREDOS_LAB and not args.novas_senhas) else \
        "senha NOVA (não achei o .segredos.json do lab)" if not SEGREDOS_LAB else "senha NOVA (--novas-senhas)"
    print(f"\n✅ Kit {g}: Node-RED{' + FUXA' if FUXA else ''} + MQTT{' + ntfy' if NTFY else ''}  ({origem})")
    if PONTE:
        print(f"   ponte MQTT {g}/# <-> {PONTE}")
    print(f"📂 {SAIDA_ABS}\n📦 {zipf}   (envie ao grupo; instruções no LEIA-ME.md)")
    sys.exit(0)

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
L_.append("\nA mesma senha do grupo vale para Node-RED, FUXA, Gitea, MicroBin e ntfy.")
L_.append("\n=== ENDEREÇOS ===")
for rot, b in bases():
    L_.append(f"[{rot}]  portal: {b}/")
L_.append("")
for g in todos_servicos:
    L_.append(f"{g:<13} " + "   ".join(f"{b}/{g}/" for _r, b in bases()))
if GITEA:
    L_.append(f"{'gitea':<13} " + "   ".join(f"{b}/git/" for _r, b in bases()))
if WB:
    L_.append(f"{'microbin':<13} " + "   ".join(f"{b}/bin/" for _r, b in bases()))
for g in fuxa_grupos:
    L_.append(f"{'fuxa ' + letra_de(g):<13} " + "   ".join(f"{b}/fuxa/{g}/" for _r, b in bases()))
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
if WB:
    L_.append("\n=== MICROBIN (único para todo o lab) ===")
    L_.append("Login: usuário e senha de qualquer grupo (ou do professor/notas).")
    L_.append(f"Administração: <base>/bin/admin  ·  usuário {prof} e a senha do professor")
    L_.append("API: curl -u <grupo>:<senha> -F content='...' -F expiration=24hour -F privacy=unlisted <base>/bin/upload")
    L_.append("     (resposta 302; o link está no cabeçalho Location: /bin/upload/<id>)")
if NTFY:
    L_.append("\n=== NTFY (avisos push; um serviço, isolado por ACL) ===")
    L_.append(f"Página web: <base>/avisos/   ·   app no celular: servidor <base>/ntfy (login do grupo)")
    L_.append(f"Cada grupo: lê/escreve <grupo> e <grupo>-*  ·  todos leem {NTFY_AVISOS} (só o {prof} publica)")
    L_.append(f"{notas_service} lê todos os tópicos {LAB}-*  ·  {prof} é admin")
    L_.append("Node-RED: variáveis NTFY_URL, NTFY_TOPIC, NTFY_TOKEN (e MICROBIN_URL/AUTH/LINK) já definidas")
    L_.append("Tokens (usados pelo Node-RED; também servem para curl/ESP32):")
    for u in todos_servicos:
        L_.append(f"  {u:<13} {NTFY_TOKEN[u]}")
    L_.append(f"Ex.: curl -H 'Authorization: Bearer <token>' -d 'oi' <base>/ntfy/{grupos_alunos[0]}")
if FUXA:
    L_.append("\n=== FUXA (SCADA/HMI; um por grupo + professor) ===")
    L_.append(f"<base>/fuxa/<grupo>/  · login: usuário e senha do grupo (o {prof} entra em todos)")
    L_.append("Acesso: o navegador pede o login do grupo (--proteger-http) e o FUXA pede de novo para editar."
              if args.proteger_http else "Sem login dá para VER as telas (HMI); editar exige login.")
    L_.append("Não existe o admin/123456 padrão do FUXA.")
    L_.append("Ligação com o Node-RED: no FUXA, Conexões -> novo dispositivo MQTT client,")
    L_.append("  endereço mqtt://mosquitto:1883, tópicos <grupo>/... (os mesmos do Node-RED).")
    L_.append(f"Dados: fuxa/<grupo>/ (appdata = projeto e usuários; db = históricos; images)")
L_.append("\n=== MQTT EXPLORER ===")
L_.append(f"Usuário: {MQTTX_USER}  ·  Senha: {MQTTX_SENHA}" if MQTTX_AUTH else "Acesso sem login")
if POSTGRES:
    L_.append("\n=== POSTGRESQL (interno; só para o professor) ===")
    L_.append(f"postgres: {PG_ROOT_SENHA}")
    if GITEA_PG:
        L_.append(f"gitea:      {PG_GITEA_SENHA}")
gravar("credenciais.txt", "\n".join(L_) + "\n")

# =====================================================================
# acessos/<grupo>.md + publicar-acessos-github.sh
# Página de acesso de cada grupo, injetada no repositório PRIVADO do grupo no GitHub
# ({lab}-grupo-<letra>) pelo script publicar-acessos-github.sh (usa o gh).
# =====================================================================
MARCA_INI = f"<!-- {LAB.upper()}-ACESSO:INICIO (gerado automaticamente; não edite este bloco) -->"
MARCA_FIM = f"<!-- {LAB.upper()}-ACESSO:FIM -->"


def pagina_acesso(g):
    """Página de acesso (Markdown) de um grupo, do professor (lab-p) ou das notas (lab-n)."""
    L = letra_de(g).upper()
    base_pub = PUBLICO_URL if TUNEL else None

    def linha(servico, caminho, so_local=False):
        loc = f"{LOCAL_URL}{caminho}"
        pub = "— (só na rede do lab)" if (so_local or not base_pub) else f"{base_pub}{caminho}"
        return f"| {servico} | {loc} | {pub} |"

    if is_prof(g):
        titulo, quem = "Professor", "do **professor**"
    elif is_notas(g):
        titulo, quem = "Painel de notas", "do **painel de notas**"
    else:
        titulo, quem = f"Grupo {L}", "**somente deste grupo**"

    m = [MARCA_INI,
         f"## 🔑 Acesso ao {LAB.upper()} — {titulo}",
         "",
         f"> ⚠️ Credenciais {quem}. Não copie para fora deste repositório nem compartilhe.",
         "> A mesma senha vale para Node-RED, FUXA, Gitea, MicroBin e ntfy (avisos).",
         "",
         "| | Usuário | Senha |",
         "|---|---|---|",
         f"| Acesso principal | `{g}` | `{SENHA[g]}` |",
         f"| Só leitura no Node-RED (projetor) | `{g}-view` | `{SENHA[g + '-view']}` |"]
    if is_prof(g):
        if MQTTX_AUTH:
            m.append(f"| MQTT Explorer | `{MQTTX_USER}` | `{MQTTX_SENHA}` |")

    m += ["", "### Endereços", "",
          "| Serviço | No laboratório | De qualquer lugar |",
          "|---|---|---|",
          linha("Portal", "/"),
          linha("Node-RED (editor)", f"/{g}/"),
          linha("Dashboard", f"/{g}/dashboard")]
    if FUXA:
        if is_prof(g):
            m.append(linha("FUXA (SCADA/HMI) do professor", f"/fuxa/{g}/"))
            m.append(linha("FUXA dos grupos (mesmo login)", f"/fuxa/{LAB}-<letra>/"))
        elif is_notas(g):
            m.append(linha("FUXA dos grupos (só ver as telas)", f"/fuxa/{LAB}-<letra>/"))
        else:
            m.append(linha("FUXA (SCADA/HMI)", f"/fuxa/{g}/"))
    if WB:
        m.append(linha("MicroBin (colar código e arquivos; todo o lab)", "/bin/"))
    if GITEA:
        if is_prof(g) or is_notas(g):
            m.append(linha("Gitea (todas as organizações)", "/git/explore/organizations"))
        else:
            m.append(linha("Gitea (organização do grupo)", f"/git/{org_de(g)}"))
    if NTFY:
        m.append(linha("Avisos (ntfy): ler e publicar", "/avisos/"))
        m.append(linha("Servidor para o app ntfy (celular)", "/ntfy"))
    m.append(f"| MQTT Explorer | {MQTTX_URL} | — (só na rede do lab) |")

    if is_prof(g):
        m += ["", "### O que só o professor pode fazer", "",
              "| Onde | Permissão |", "|---|---|"]
        if GITEA:
            m.append(f"| Gitea | **administrador** do site; dono de todas as organizações `{LAB}-grupo-*` |")
        if NTFY:
            m.append(f"| ntfy | **admin**: publica em `{NTFY_AVISOS}` (todos recebem) e lê/escreve em todos os tópicos |")
        if WB:
            m.append(f"| MicroBin | painel `/bin/admin` (usuário `{prof}`): lista, apaga e vê estatísticas de tudo |")
        if FUXA:
            m.append(f"| FUXA | **administrador** em todos (`/fuxa/{LAB}-<letra>/`), com o usuário `{g}` |")
        m.append(f"| Node-RED | edita o próprio (`/{g}/`); as senhas de cada grupo estão no `credenciais.txt` do servidor |")
    elif is_notas(g):
        m += ["", "### Para a avaliação", "", "| Onde | Acesso |", "|---|---|",
              f"| Node-RED de notas | lê os fluxos de todos os grupos em `/data_grupos/<grupo>/` |"]
        if GITEA:
            m.append(f"| Gitea | **leitura** em todas as organizações `{LAB}-grupo-*` (time `avaliacao`) |")
        if NTFY:
            m.append(f"| ntfy | **leitura** em todos os tópicos `{LAB}-*` (assine `{LAB}-a,{LAB}-b,...`) |")

    m += ["", "### Configurações para usar no Node-RED", "",
          "| Para | Valor |", "|---|---|",
          f"| Broker MQTT (nós mqtt) | servidor `mosquitto`, porta `1883`, tópicos `{g}/...` |",
          f"| Broker MQTT no ESP32 / PC (só na rede do lab) | `{IP}:1883` |"]
    if NTFY:
        m.append(f"| ntfy (já no Node-RED) | `env.get(\"NTFY_URL\")`, `NTFY_TOPIC` = `{g}`, `NTFY_TOKEN` = `{NTFY_TOKEN[g]}` |")
        m.append(f"| App ntfy no celular | servidor `{(PUBLICO_URL if TUNEL else LOCAL_URL)}/ntfy`, usuário `{g}`, tópicos `{g}`"
                 + (f", `{NTFY_AVISOS}`" if not is_prof(g) else "") + " |")
        m.append(f"| Exemplo para importar | `{(PUBLICO_URL if TUNEL else LOCAL_URL)}/avisos/exemplo-node-red.json` (ntfy + MicroBin) |")
    if GITEA and GITEA_REPO and not (is_prof(g) or is_notas(g)):
        m.append(f"| Projects (clonar repositório) | `http://gitea:3000/{org_de(g)}/{GITEA_REPO}.git` |")
    if FUXA and not is_notas(g):
        alvo = g
        m += ["", "### FUXA (SCADA/HMI) junto com o Node-RED", "",
              "O FUXA e o Node-RED do grupo conversam pelo broker MQTT: o Node-RED publica as",
              "medições e o FUXA mostra/comanda pelas mesmas mensagens.", "",
              "| No FUXA (Conexões → **+** → tipo *MQTT client*) | Valor |", "|---|---|",
              "| Endereço | `mqtt://mosquitto:1883` |",
              f"| Tags (Navegar/Browse ou manual) | tópicos `{alvo}/...` — ex.: `{alvo}/temperatura` |",
              f"| Comando para o Node-RED | tag com *publish* em `{alvo}/cmd/...` (nó *mqtt in* no Node-RED) |",
              f"| Via HTTP (opcional) | dispositivo *WebAPI*: `http://{alvo}-nodered:1880/{alvo}/<endpoint>` |",
              "", ("> Abrir o FUXA pede o login do grupo duas vezes: no navegador (proteção do lab) e no próprio FUXA."
                   if args.proteger_http else
                   "> Telas do FUXA são visíveis sem login (só leitura); editar exige o login do grupo."),
              "> Não use o Node-RED embutido do FUXA: o do grupo já está integrado."]
    m += ["", MARCA_FIM, ""]
    return "\n".join(m)


# grupos + professor + notas (repositórios <lab>-grupo-p e <lab>-grupo-n também recebem)
for g in todos_servicos:
    gravar(f"acessos/{g}.md", pagina_acesso(g))

PUBLICAR_SH = r"""#!/usr/bin/env bash
# publicar-acessos-github.sh — gerado por gen_iot_scada_portal.py (__LAB__)
#
# Injeta a página de acesso de cada grupo (pasta acessos/) no repositório PRIVADO
# do grupo no GitHub:  __ORG__/__LAB__-grupo-<letra>
#
# Modos:
#   (padrão)    seção no topo do README.md, entre marcadores; as execuções seguintes
#               substituem só essa seção (o resto do README fica intacto)
#   --arquivo   arquivo separado ACESSO-__LABU__.md (README intocado)
#   --remover   retira a seção do README e/ou apaga o arquivo (fim do semestre)
# Outras opções:
#   --org NOME        organização do GitHub (padrão: __ORG__)
#   --grupos "a b c"  só esses grupos (padrão: todos de acessos/)
#   --dry-run         mostra o que faria, sem alterar nada
#
# Requisitos: gh (GitHub CLI) autenticado com permissão de escrita nos repositórios:
#   gh auth login        (Windows: rode no Git Bash: bash publicar-acessos-github.sh)
set -euo pipefail

ORG="__ORG__"
LAB="__LAB__"
ARQUIVO="ACESSO-__LABU__.md"
INICIO="__INI__"
FIM="__FIM__"
MODO="readme"
DRY=0
SO_GRUPOS=""
DIR="$(cd "$(dirname "$0")" && pwd)/acessos"

while [ $# -gt 0 ]; do
  case "$1" in
    --arquivo) MODO="arquivo" ;;
    --remover) MODO="remover" ;;
    --dry-run) DRY=1 ;;
    --org)     ORG="$2"; shift ;;
    --grupos)  SO_GRUPOS="$2"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 1 ;;
  esac
  shift
done

command -v gh >/dev/null || { echo "Instale o GitHub CLI: winget install -e --id GitHub.cli" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Faça login antes: gh auth login" >&2; exit 1; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
CHAVE_INI="${INICIO%% (*}"     # parte fixa do marcador (sem o comentário)

b64()  { base64 < "$1" | tr -d '\r\n'; }
sha_de() {  # sha do arquivo no repositório, ou vazio se não existir
  local o
  if o="$(gh api "repos/$ORG/$1/contents/$2" --jq .sha 2>/dev/null)"; then echo "$o"; fi
}
baixar() { gh api -H "Accept: application/vnd.github.raw" "repos/$ORG/$1/contents/$2" > "$3"; }

enviar() {  # repo caminho arquivo_local sha mensagem texto_ok
  if [ "$DRY" = 1 ]; then echo "    (dry-run) $6"; return; fi
  local args=(--method PUT --silent "repos/$ORG/$1/contents/$2"
              -f message="$5" -f content="$(b64 "$3")")
  [ -n "$4" ] && args+=(-f sha="$4")
  gh api "${args[@]}"
  echo "    ✓ $6"
}

apagar() {  # repo caminho sha mensagem texto_ok
  if [ "$DRY" = 1 ]; then echo "    (dry-run) $5"; return; fi
  gh api --method DELETE --silent "repos/$ORG/$1/contents/$2" -f message="$4" -f sha="$3"
  echo "    ✓ $5"
}

# mantém o estilo de quebra de linha do arquivo original (CRLF de templates feitos no Windows)
igualar_fim_de_linha() {  # original arquivo_a_ajustar
  if grep -q $'\r' "$1" 2>/dev/null; then sed -i 's/$/\r/' "$2"; fi
}

# remove o bloco antigo (entre os marcadores) de $1 e grava em $2
sem_bloco() {
  tr -d '\r' < "$1" | awk -v ini="$CHAVE_INI" -v fim="$FIM" '
    index($0, ini) == 1 { dentro = 1; next }
    dentro && index($0, fim) == 1 { dentro = 0; pula = 1; next }
    dentro { next }
    pula && $0 == "" { pula = 0; next }
    { pula = 0; print }' > "$2"
}

ok=0; falhas=0
for f in "$DIR"/"$LAB"-*.md; do
  g="$(basename "$f" .md)"; letra="${g##*-}"
  case "$letra" in p) quem="professor" ;; n) quem="painel de notas" ;; *) quem="grupo ${letra^^}" ;; esac
  if [ -n "$SO_GRUPOS" ] && ! echo " $SO_GRUPOS " | grep -qi " $letra "; then continue; fi
  repo="$LAB-grupo-$letra"
  echo "→ $ORG/$repo"
  if ! gh repo view "$ORG/$repo" >/dev/null 2>&1; then
    echo "    ✗ repositório não encontrado (ou sem acesso)"; falhas=$((falhas+1)); continue
  fi

  case "$MODO" in
    readme)
      sha="$(sha_de "$repo" README.md)"
      if [ -n "$sha" ]; then baixar "$repo" README.md "$TMP/atual"; else : > "$TMP/atual"; fi
      sem_bloco "$TMP/atual" "$TMP/resto"
      { cat "$f"; cat "$TMP/resto"; } > "$TMP/novo"
      igualar_fim_de_linha "$TMP/atual" "$TMP/novo"
      if [ -n "$sha" ] && cmp -s "$TMP/atual" "$TMP/novo"; then
        echo "    = README.md já está atualizado"
      else
        enviar "$repo" README.md "$TMP/novo" "$sha" "$LAB: acesso ($quem) [skip ci]" \
               "README.md atualizado"
      fi ;;
    arquivo)
      sha="$(sha_de "$repo" "$ARQUIVO")"
      if [ -n "$sha" ]; then baixar "$repo" "$ARQUIVO" "$TMP/atual"; fi
      if [ -n "$sha" ] && cmp -s <(tr -d '\r' < "$TMP/atual") "$f"; then
        echo "    = $ARQUIVO já está atualizado"
      else
        enviar "$repo" "$ARQUIVO" "$f" "$sha" "$LAB: acesso ($quem) [skip ci]" \
               "$ARQUIVO publicado"
      fi ;;
    remover)
      sha="$(sha_de "$repo" README.md)"
      if [ -n "$sha" ]; then
        baixar "$repo" README.md "$TMP/atual"; sem_bloco "$TMP/atual" "$TMP/novo"
        igualar_fim_de_linha "$TMP/atual" "$TMP/novo"
        msg="$LAB: remove acesso ($quem) [skip ci]"
        if cmp -s "$TMP/atual" "$TMP/novo"; then
          :
        elif [ -z "$(tr -d '[:space:]' < "$TMP/novo")" ]; then
          apagar "$repo" README.md "$sha" "$msg" "README.md apagado (só continha o acesso)"
        else
          enviar "$repo" README.md "$TMP/novo" "$sha" "$msg" "seção removida do README.md"
        fi
      fi
      sha="$(sha_de "$repo" "$ARQUIVO")"
      if [ -n "$sha" ]; then
        apagar "$repo" "$ARQUIVO" "$sha" "$LAB: remove acesso ($quem) [skip ci]" "$ARQUIVO apagado"
      fi ;;
  esac
  ok=$((ok+1))
done
echo ""
echo "Concluído: $ok repositório(s) processado(s), $falhas com problema."
[ "$falhas" -eq 0 ]
"""

gravar("publicar-acessos-github.sh",
       PUBLICAR_SH.replace("__ORG__", args.github_org).replace("__LABU__", LAB.upper())
       .replace("__LAB__", LAB).replace("__INI__", MARCA_INI).replace("__FIM__", MARCA_FIM),
       executavel=True)
print(f"🐙 acessos/<grupo>.md + publicar-acessos-github.sh (GitHub: {args.github_org})")

# =====================================================================
# relatório
# =====================================================================
print(f"\n✅ {LAB}: {N} grupos ({grupos_alunos[0]}..{grupos_alunos[-1]}) + "
      f"professor ({prof}) + notas ({notas_service})")
print(f"\n  Local:   {LOCAL_URL}/")
if TUNEL:
    print(f"  Público: {PUBLICO_URL}/   (túnel SSH -> Apache do VPS {VPS_HOST})")
print(f"  Grupo A: <base>/{grupos_alunos[0]}/   ·   Gitea: <base>/git/   ·   MicroBin: <base>/bin/")
print(f"  MQTT Explorer: {MQTTX_URL}   ·   MQTT: {IP}:1883  (rede local)")
if FUXA:
    print(f"  FUXA:   <base>/fuxa/{grupos_alunos[0]}/ (SCADA/HMI do grupo; {len(fuxa_grupos)} instâncias)")
if NTFY:
    print(f"  ntfy:   <base>/avisos/ (página)  ·  app: <base>/ntfy  ·  tópicos {grupos_alunos[0]}, {grupos_alunos[0]}-*, {NTFY_AVISOS}")
print("\n🔒 Senhas em credenciais.txt " +
      ("(NOVAS para todos)" if args.novas_senhas else "(mantidas de execuções anteriores, se houver)"))
if IP.startswith("127."):
    print("\n⚠️  --ip é 127.x: alunos na rede não acessam o servidor. Use o IP real (ipconfig).")
if TUNEL:
    print("\n🌍 Publicação em " + PUBLICO_URL + " — passos (uma vez):")
    print("   1) docker compose run --rm --no-deps --build tunel chave   (gera e mostra a chave)")
    print(f"   2) ssh ubuntu@{VPS_HOST} mkdir -p iot-lab")
    print(f"      scp -r vps tunel/chave/id_ed25519.pub ubuntu@{VPS_HOST}:iot-lab/")
    print(f"   3) ssh -t ubuntu@{VPS_HOST} sudo bash iot-lab/vps/setup-vps.sh iot-lab/id_ed25519.pub")
    print("   4) docker compose up -d --build")
print(f"\n🐙 Acessos nos repositórios do GitHub ({args.github_org}/{LAB}-grupo-<letra>):")
print("   bash publicar-acessos-github.sh --dry-run    (confere)   ·   bash publicar-acessos-github.sh")
print(f"\n📂 {SAIDA_ABS}")
print(f"▶  cd {SAIDA_ABS}  e  docker compose up -d --build")
