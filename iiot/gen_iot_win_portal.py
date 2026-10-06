#!/usr/bin/env python3
"""Gera o LAB local com portal nginx na frente dos Node-RED.

Reservas de letras:
  - 'p' para o PROFESSOR  (ex.: n21-p)
  - 'n' para NOTAS        (ex.: n21-n)

Gera:
  - docker-compose.yml       (nginx + Node-RED por grupo + prof + avaliador de notas)
  - nginx/nginx.conf         (portal em / + proxy reverso)
  - nginx/html/index.html    (pagina inicial listando os grupos e o painel de notas)
  - settings/<grupo>.js      (configurações de autenticação e rotas)
  - data/<grupo>/            (pasta bind-montada; guarda flows.json)
  - mqtt-explorer/data/settings.json (MQTT Explorer único, já conectado ao broker)
  - gitea/init/gitea-init.sh (Gitea único: usuários de credenciais.txt + organização por grupo)
  - mattermost/init/mattermost-init.sh (chat único: equipe da turma + canal privado por grupo)
  - postgres/init/bancos.sql  (bancos do Gitea e do Mattermost no PostgreSQL compartilhado)
  - dnsmasq/dnsmasq.conf      (DNS do lab: *.<dominio> -> IP do servidor)
  - .segredos.json            (senhas internas reaproveitadas entre execuções)

Todos os arquivos são gravados dentro da pasta de saída (--saida, padrão: lab_<turma>).

Uso:
  python3 gen_iot_win_portal.py       # turma n21, 10 grupos + prof + notas
  python3 gen_iot_win_portal.py --turma n21 --grupos 10
  python3 gen_iot_win_portal.py --mqtt-explorer-auth                       # login com senha gerada
  python3 gen_iot_win_portal.py --mqtt-explorer-auth --mqtt-explorer-senha minhaSenha
  python3 gen_iot_win_portal.py --modo path       # um dominio, varios caminhos (node.lab/n21-a/)
  python3 gen_iot_win_portal.py --sem-gitea       # sem o servidor Git
  python3 gen_iot_win_portal.py --sem-chat        # sem o Mattermost
  python3 gen_iot_win_portal.py --sem-dns         # sem o dnsmasq (use hosts.lab)
  python3 gen_iot_win_portal.py --gitea-db sqlite # Gitea com SQLite em vez de PostgreSQL

Modos (--modo):
  subdominio (padrao): um host por servico  -> http://n21-a.node.lab/
  path:                um dominio, varios caminhos -> http://node.lab/n21-a/
                       (MQTT Explorer fica na porta direta, ex.: http://node.lab:3001/)
"""
import sys, os, re, secrets, string, argparse, json
import bcrypt

# Console do Windows: garante UTF-8 (acentos e emojis) mesmo com saída redirecionada
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ap = argparse.ArgumentParser()
ap.add_argument("--turma", default="n21", help="Identificador da turma (ex.: n21)")
ap.add_argument("--grupos", type=int, default=10, help="Quantidade de grupos de alunos")
ap.add_argument("--dominio", default="node.lab", help="Dominio base do lab (ex.: node.lab)")
ap.add_argument("--ip", default="127.0.0.1", help="IP do servidor (usado no hosts.lab)")
ap.add_argument("--modo", choices=["subdominio", "path"], default="subdominio",
                help="subdominio (padrao): um host por servico (n21-a.node.lab); "
                     "path: um dominio, varios caminhos (node.lab/n21-a/)")
ap.add_argument("--sem-gitea", action="store_true",
                help="Nao inclui o Gitea (servidor Git unico da turma)")
ap.add_argument("--gitea-repo", default="nodered",
                help="Nome do repositorio inicial criado em cada organizacao ('' = nenhum)")
ap.add_argument("--gitea-db", choices=["postgres", "sqlite"], default="postgres",
                help="Banco do Gitea: postgres (padrao, PostgreSQL compartilhado) ou sqlite")
ap.add_argument("--sem-chat", action="store_true",
                help="Nao inclui o Mattermost (chat da turma)")
ap.add_argument("--sem-dns", action="store_true",
                help="Nao inclui o dnsmasq (servidor DNS do lab)")
ap.add_argument("--dns-upstream", default="1.1.1.1,8.8.8.8",
                help="Servidores DNS externos usados pelo dnsmasq (separados por virgula)")
ap.add_argument("--saida", default=None,
                help="Pasta onde os arquivos serão gerados (padrão: lab_<turma>)")
ap.add_argument("--mqtt-explorer-auth", action="store_true",
                help="Exige login (usuário/senha) para acessar o MQTT Explorer")
ap.add_argument("--mqtt-explorer-usuario", default="admin",
                help="Usuário do MQTT Explorer (com --mqtt-explorer-auth)")
ap.add_argument("--mqtt-explorer-senha", default=None,
                help="Senha do MQTT Explorer (se omitida, é gerada aleatoriamente)")
ap.add_argument("--mqtt-explorer-porta", type=int, default=3001,
                help="Porta direta do MQTT Explorer no host (além do subdomínio)")
args = ap.parse_args()

TURMA = args.turma.lower()
if not re.fullmatch(r"[a-z][a-z0-9]{1,20}", TURMA):
    sys.exit("--turma deve comecar com letra e ter so letras/digitos (ex.: n21), "
             "pois vira nome de host, usuario do chat e prefixo MQTT.")
N = args.grupos
DOMINIO = args.dominio
IP = args.ip

# Pasta de saída: tudo é gerado dentro dela
SAIDA = args.saida or f"lab_{TURMA}"
os.makedirs(SAIDA, exist_ok=True)
os.chdir(SAIDA)
SAIDA_ABS = os.getcwd()

# Segredos internos (banco de dados, chaves) — reaproveitados entre execuções,
# pois o PostgreSQL e o Gitea guardam esses valores na primeira subida.
ARQ_SEGREDOS = ".segredos.json"
try:
    with open(ARQ_SEGREDOS, encoding="utf-8") as _f:
        SEGREDOS = json.load(_f)
except (OSError, ValueError):
    SEGREDOS = {}


def segredo(nome, gerar):
    if nome not in SEGREDOS:
        SEGREDOS[nome] = gerar()
    return SEGREDOS[nome]

MODO = args.modo

# MQTT Explorer (serviço único para toda a turma)
MQTTX_HOST = f"mqtt.{DOMINIO}"
MQTTX_PORTA = args.mqtt_explorer_porta
# No modo path o MQTT Explorer é acessado pela porta direta (não suporta subcaminho)
MQTTX_URL = f"http://{MQTTX_HOST}/" if MODO == "subdominio" else f"http://{DOMINIO}:{MQTTX_PORTA}/"


# Mattermost (chat único; canal privado por grupo)
CHAT = not args.sem_chat
CHAT_HOST = f"chat.{DOMINIO}"
CHAT_URL = f"http://{CHAT_HOST}/" if MODO == "subdominio" else f"http://{DOMINIO}/chat/"
CHAT_SITEURL = CHAT_URL.rstrip("/")
CHAT_IMAGEM = "mattermost/mattermost-team-edition:release-11"
CHAT_TEAM = TURMA

# DNS do laboratório (dnsmasq)
DNS = not args.sem_dns
DNS_UPSTREAM = [x.strip() for x in args.dns_upstream.split(",") if x.strip()]

# Gitea (serviço único; organizações por grupo)
GITEA = not args.sem_gitea
GITEA_REPO = args.gitea_repo.strip()
GITEA_HOST = f"git.{DOMINIO}"
GITEA_URL = f"http://{GITEA_HOST}/" if MODO == "subdominio" else f"http://{DOMINIO}/git/"
GITEA_DOMAIN = GITEA_HOST if MODO == "subdominio" else DOMINIO
GITEA_PG = GITEA and args.gitea_db == "postgres"

# PostgreSQL compartilhado: existe se o chat ou o Gitea (em postgres) precisarem
POSTGRES = CHAT or GITEA_PG
_pg_senha = lambda: secrets.token_hex(16)
PG_ROOT_SENHA = segredo("postgres_root", _pg_senha) if POSTGRES else None
PG_GITEA_SENHA = segredo("postgres_gitea", _pg_senha) if GITEA_PG else None
PG_MM_SENHA = segredo("postgres_mattermost", _pg_senha) if CHAT else None
GITEA_SECRET_KEY = segredo("gitea_secret_key", lambda: secrets.token_hex(32)) if GITEA else None


def org_de(g):
    """Nome da organização Gitea do grupo (não pode coincidir com o nome do usuário)."""
    return f"{TURMA}-grupo-{letra_de(g)}"


def url_de(g):
    """URL pública do Node-RED de um serviço, conforme o modo."""
    if MODO == "path":
        return f"http://{DOMINIO}/{g}/"
    return f"http://{g}.{DOMINIO}/"
MQTTX_AUTH = args.mqtt_explorer_auth
MQTTX_USER = args.mqtt_explorer_usuario
MQTTX_SENHA = None  # definida mais abaixo (depois de gerar_senha existir)

# Letras reservadas
LETRA_PROF = "p"
LETRA_NOTAS = "n"

# Monta alfabeto de alunos pulando 'p' e 'n'
reservadas = {LETRA_PROF, LETRA_NOTAS}
letras = [c for c in string.ascii_lowercase if c not in reservadas]

if N > len(letras):
    sys.exit(f"Máximo de {len(letras)} grupos (letras a-z sem 'p' e 'n').")

# Definição dos nomes dos serviços
grupos_alunos = [f"{TURMA}-{letras[i]}" for i in range(N)]
prof = f"{TURMA}-{LETRA_PROF}"
notas_service = f"{TURMA}-{LETRA_NOTAS}"

todos_servicos = grupos_alunos + [prof, notas_service]


def is_prof(g):
    return g == prof


def is_notas(g):
    return g == notas_service


def letra_de(g):
    if is_notas(g):
        return "n"
    if is_prof(g):
        return "p"
    return g.rsplit("-", 1)[-1]


def gerar_senha(tamanho=8):
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))


if MQTTX_AUTH:
    MQTTX_SENHA = args.mqtt_explorer_senha or gerar_senha(10)


# Pré-cria diretórios e .gitkeep
for g in todos_servicos:
    os.makedirs(f"data/{g}", exist_ok=True)
    open(f"data/{g}/.gitkeep", "a").close()


PORTAL_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LAB IoT · Turma {{TURMA}}</title>
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
      <div class="eyebrow">broker online &middot; turma {{TURMA}}</div>
      <h1>Painel da Turma {{TURMA}}</h1>
      <p class="sub">Selecione seu grupo para abrir o editor Node-RED. Cada grupo
      publica no broker MQTT sob seu próprio tópico, no formato
      <code>{{TURMA}}-&lt;letra&gt;/#</code>.</p>
    </header>

    <main class="grid">
{{CARDS}}    </main>

    <footer class="foot">
      <span>MQTT: porta 1883</span>
      <span>MQTT Explorer: <a href="{{MQTTX_URL}}" style="color:inherit">{{MQTTX_LABEL}}</a></span>
      <span>tópico base: {{TURMA}}-&lt;letra&gt;/</span>
      <span>banco: SQLite por grupo</span>
    </footer>
  </div>
</body>
</html>
"""

# ---------------- mosquitto/mosquitto.conf ----------------
os.makedirs("mosquitto", exist_ok=True)

mosquitto_conf = """listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest stdout
"""

open("mosquitto/mosquitto.conf", "w", encoding="utf-8", newline="\n").write(mosquitto_conf)
print("🐝 mosquitto.conf gerado com sucesso.")

# ---------------- Dockerfile ----------------
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

open("Dockerfile", "w", encoding="utf-8", newline="\n").write(dockerfile)
print("📦 Dockerfile gerado com sucesso.")

# ---------------- docker-compose.yml ----------------
c = [
    "# LAB local com portal nginx — gerado por gen_iot_win_portal.py\n",
    f"# Turma {TURMA} · {N} grupos + professor ({prof}) + avaliador ({notas_service})\n",
    f"# Dominio: {DOMINIO}   ·   Portal: http://{DOMINIO}/   ·   Modo: {MODO}\n",
    "# Subir:  docker compose up -d --build   ->  acesse http://" + DOMINIO + "/\n",
    "services:\n",
    "  nginx:\n",
    "    image: nginx:alpine\n",
    "    container_name: lab-portal\n",
    "    restart: unless-stopped\n",
    "    ports:\n",
    '      - "80:80"\n',
    "    volumes:\n",
    "      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro\n",
    "      - ./nginx/html:/usr/share/nginx/html:ro\n",
    "    depends_on:\n",
]
for g in todos_servicos:
    c.append(f"      - {g}-nodered\n")
c.append("      - mqtt-explorer\n")
if GITEA:
    c.append("      - gitea\n")
if CHAT:
    c.append("      - mattermost\n")

c += ["    networks:\n", "      - labnet\n",
      "\n  mosquitto:\n",
      "    image: eclipse-mosquitto:latest\n",
      "    container_name: lab-mosquitto\n",
      "    restart: unless-stopped\n",
      "    ports:\n",
      '      - "1883:1883"\n',
      "    volumes:\n",
      "      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro\n",
      "      - mosquitto_data:/mosquitto/data\n",
      "    networks:\n",
      "      - labnet\n"]

# Containers dos grupos de alunos e professor
for g in grupos_alunos + [prof]:
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
        "    depends_on:\n",
        "      - mosquitto\n",
        "    networks:\n",
        "      - labnet\n",
    ]

# Container de Notas (Mapeia a pasta global de dados em modo leitura)
c += [
    f"\n  {notas_service}-nodered:\n",
    "    build: .\n",
    "    image: lab-nodered:latest\n",
    f"    container_name: {notas_service}-nodered\n",
    "    restart: unless-stopped\n",
    "    volumes:\n",
    f"      - ./data/{notas_service}:/data\n",
    f"      - ./settings/{notas_service}.js:/data/settings.js:ro\n",
    "      - ./data:/data_grupos:ro\n",
    "    environment:\n",
    "      - TZ=America/Sao_Paulo\n",
    "    depends_on:\n",
    "      - mosquitto\n",
    "    networks:\n",
    "      - labnet\n",
]

# Container do MQTT Explorer (único para todos)
mqttx_env = [
    "      - TZ=America/Sao_Paulo\n",
    "      - PORT=3000\n",
    "      - MQTT_AUTO_CONNECT_HOST=mosquitto\n",
    '      - MQTT_AUTO_CONNECT_PORT=1883\n',
    f"      - ALLOWED_ORIGINS=http://{MQTTX_HOST},http://{DOMINIO}:{MQTTX_PORTA},http://{IP}:{MQTTX_PORTA},http://localhost:{MQTTX_PORTA}\n",
]
if MQTTX_AUTH:
    mqttx_env += [
        "      - MQTT_EXPLORER_SKIP_AUTH=false\n",
        f"      - MQTT_EXPLORER_USERNAME={MQTTX_USER}\n",
        f"      - MQTT_EXPLORER_PASSWORD={MQTTX_SENHA}\n",
    ]
else:
    mqttx_env += ["      - MQTT_EXPLORER_SKIP_AUTH=true\n"]

c += [
    "\n  mqtt-explorer:\n",
    "    image: ruseler/mqtt-explorer:local\n",
    "    container_name: lab-mqtt-explorer\n",
    "    restart: unless-stopped\n",
    "    ports:\n",
    f'      - "{MQTTX_PORTA}:3000"\n',
    "    environment:\n",
    *mqttx_env,
    "    volumes:\n",
    "      - ./mqtt-explorer/data:/app/data\n",
    "    depends_on:\n",
    "      - mosquitto\n",
    "    networks:\n",
    "      - labnet\n",
]

# Gitea (unico) + container de inicializacao (roda uma vez e termina)
if GITEA:
    c += [
        "\n  gitea:\n",
        "    image: gitea/gitea:latest\n",
        "    container_name: lab-gitea\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        "      - USER_UID=1000\n",
        "      - USER_GID=1000\n",
        "      - TZ=America/Sao_Paulo\n",
        *([
            "      - GITEA__database__DB_TYPE=postgres\n",
            "      - GITEA__database__HOST=postgres:5432\n",
            "      - GITEA__database__NAME=gitea\n",
            "      - GITEA__database__USER=gitea\n",
            f"      - GITEA__database__PASSWD={PG_GITEA_SENHA}\n",
            "      - GITEA__database__SSL_MODE=disable\n",
        ] if GITEA_PG else ["      - GITEA__database__DB_TYPE=sqlite3\n"]),
        f"      - GITEA__server__DOMAIN={GITEA_DOMAIN}\n",
        f"      - GITEA__server__ROOT_URL={GITEA_URL}\n",
        "      - GITEA__server__HTTP_PORT=3000\n",
        "      - GITEA__server__DISABLE_SSH=true\n",
        "      - GITEA__security__INSTALL_LOCK=true\n",
        f"      - GITEA__security__SECRET_KEY={GITEA_SECRET_KEY}\n",
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
        *([
            "    depends_on:\n",
            "      db-init:\n",
            "        condition: service_completed_successfully\n",
        ] if GITEA_PG else []),
        "    networks:\n",
        "      - labnet\n",
        "\n  gitea-init:\n",
        "    image: gitea/gitea:latest\n",
        "    container_name: lab-gitea-init\n",
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

# PostgreSQL compartilhado + db-init (cria/atualiza bancos e senhas a cada subida)
if POSTGRES:
    c += [
        "\n  postgres:\n",
        "    image: postgres:16-alpine\n",
        "    container_name: lab-postgres\n",
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
        "    container_name: lab-db-init\n",
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

# Mattermost (chat unico) + mattermost-init (mmctl em modo local, via socket compartilhado)
if CHAT:
    c += [
        "\n  mattermost:\n",
        f"    image: {CHAT_IMAGEM}\n",
        "    container_name: lab-mattermost\n",
        "    restart: unless-stopped\n",
        "    environment:\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - MM_SQLSETTINGS_DRIVERNAME=postgres\n",
        f"      - MM_SQLSETTINGS_DATASOURCE=postgres://mattermost:{PG_MM_SENHA}@postgres:5432/mattermost?sslmode=disable&connect_timeout=10\n",
        f"      - MM_SERVICESETTINGS_SITEURL={CHAT_SITEURL}\n",
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
        # senhas geradas tem 8 caracteres alfanumericos: fixa a politica compativel
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
        "    container_name: lab-mattermost-init\n",
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

# dnsmasq (DNS do laboratorio): *.<dominio> -> IP do servidor; resto -> upstream
if DNS:
    c += [
        "\n  dns:\n",
        "    build: ./dnsmasq\n",
        "    image: lab-dnsmasq:latest\n",
        "    container_name: lab-dns\n",
        "    restart: unless-stopped\n",
        "    ports:\n",
        f'      - "{IP}:53:53/udp"\n',
        f'      - "{IP}:53:53/tcp"\n',
        "    volumes:\n",
        "      - ./dnsmasq/dnsmasq.conf:/etc/dnsmasq.conf:ro\n",
        "    networks:\n",
        "      - labnet\n",
    ]

c += ["\nvolumes:\n", "  mosquitto_data:\n"]
if GITEA:
    c += ["  gitea_data:\n"]
if POSTGRES:
    c += ["  postgres_data:\n"]
if CHAT:
    c += ["  mm_config:\n", "  mm_data:\n", "  mm_logs:\n", "  mm_plugins:\n", "  mm_client_plugins:\n"]
c += ["\nnetworks:\n", "  labnet:\n", "    driver: bridge\n"]
open("docker-compose.yml", "w", encoding="utf-8", newline="\n").write("".join(c))

# ---------------- nginx/nginx.conf ----------------
os.makedirs("nginx/html", exist_ok=True)

PROXY_OPTS = [
    "proxy_http_version 1.1;",
    "proxy_set_header Upgrade $http_upgrade;",
    "proxy_set_header Connection $connection_upgrade;",
    "proxy_set_header Host $host;",
    "proxy_set_header X-Real-IP $remote_addr;",
    "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    "proxy_set_header X-Forwarded-Proto $scheme;",
    "proxy_read_timeout 3600s;",
    "proxy_send_timeout 3600s;",
    "proxy_buffering off;",
]


def bloco_location(caminho, upstream, ind="        "):
    """Gera um bloco 'location <caminho> { proxy_pass ...; }' com suporte a WebSocket."""
    linhas = [f"{ind}location {caminho} {{\n", f"{ind}    proxy_pass {upstream};\n"]
    linhas += [f"{ind}    {o}\n" for o in PROXY_OPTS]
    linhas += [f"{ind}}}\n"]
    return linhas


def papel_de(g):
    if is_notas(g):
        return "avaliador de notas"
    if is_prof(g):
        return "professor"
    return "grupo"


n = [
    f"# nginx.conf — gerado por gen_iot_win_portal.py (modo: {MODO})\n",
    "worker_processes auto;\n",
    "events { worker_connections 1024; }\n\n",
    "http {\n",
    "    include       /etc/nginx/mime.types;\n",
    "    default_type  application/octet-stream;\n",
    "    sendfile on;\n\n",
    "    map $http_upgrade $connection_upgrade {\n",
    "        default upgrade;\n",
    "        ''      close;\n",
    "    }\n\n",
    "    # ---- Portal (raiz do dominio) ----\n",
    "    server {\n",
    "        listen 80 default_server;\n",
    f"        server_name {DOMINIO};\n",
    "        root /usr/share/nginx/html;\n",
    "        index index.html;\n",
    "        location / { }\n",
]

if MODO == "path":
    # Um unico dominio; cada servico em /<servico>/ (o prefixo e mantido:
    # o Node-RED ja roda com httpAdminRoot = '/<servico>/').
    for g in todos_servicos:
        n += [f"\n        # {g} ({papel_de(g)}) -> http://{DOMINIO}/{g}/\n",
              f"        location = /{g} {{ return 301 /{g}/; }}\n"]
        n += bloco_location(f"/{g}/", f"http://{g}-nodered:1880")
    # MQTT Explorer nao suporta subcaminho: /mqtt/ redireciona para a porta direta
    if GITEA:
        # Gitea suporta subcaminho (ROOT_URL = http://<dominio>/git/); receita da doc oficial
        n += ["\n        # Gitea (unico) -> http://" + DOMINIO + "/git/\n",
              "        location = /git { return 301 /git/; }\n",
              "        location /git/ {\n",
              "            client_max_body_size 512m;\n",
              "            rewrite ^ $request_uri;\n",
              "            rewrite ^/git(/.*) $1 break;\n",
              "            proxy_pass http://gitea:3000$uri;\n"]
        n += [f"            {o}\n" for o in PROXY_OPTS]
        n += ["        }\n"]
    if CHAT:
        # Mattermost suporta subcaminho (SiteURL = http://<dominio>/chat); prefixo mantido
        n += ["\n        # Mattermost (chat unico) -> http://" + DOMINIO + "/chat/\n",
              "        location = /chat { return 301 /chat/; }\n",
              "        location /chat/ {\n",
              "            client_max_body_size 50m;\n",
              "            proxy_pass http://mattermost:8065;\n"]
        n += [f"            {o}\n" for o in PROXY_OPTS]
        n += ["        }\n"]
    n += ["\n        # MQTT Explorer (unico) nao suporta subcaminho -> porta direta\n",
          f"        location /mqtt {{ return 302 http://$host:{MQTTX_PORTA}/; }}\n"]
    n += ["    }\n"]
else:
    n += ["    }\n"]
    for g in todos_servicos:
        n += [f"\n    # {g} ({papel_de(g)}) -> editor Node-RED em http://{g}.{DOMINIO}/\n",
              "    server {\n",
              "        listen 80;\n",
              f"        server_name {g}.{DOMINIO};\n"]
        n += bloco_location("/", f"http://{g}-nodered:1880")
        n += ["    }\n"]
    # MQTT Explorer (unico) -> http://mqtt.<dominio>/  (usa WebSocket/socket.io)
    n += [f"\n    # MQTT Explorer (unico para todos) -> http://{MQTTX_HOST}/\n",
          "    server {\n",
          "        listen 80;\n",
          f"        server_name {MQTTX_HOST};\n"]
    n += bloco_location("/", "http://mqtt-explorer:3000")
    n += ["    }\n"]

if MODO == "subdominio" and GITEA:
    n += [f"\n    # Gitea (unico para todos) -> {GITEA_URL}\n",
          "    server {\n",
          "        listen 80;\n",
          f"        server_name {GITEA_HOST};\n",
          "        client_max_body_size 512m;\n"]
    n += bloco_location("/", "http://gitea:3000")
    n += ["    }\n"]

if MODO == "subdominio" and CHAT:
    n += [f"\n    # Mattermost (chat unico) -> {CHAT_URL}\n",
          "    server {\n",
          "        listen 80;\n",
          f"        server_name {CHAT_HOST};\n",
          "        client_max_body_size 50m;\n"]
    n += bloco_location("/", "http://mattermost:8065")
    n += ["    }\n"]

n += ["}\n"]
open("nginx/nginx.conf", "w", encoding="utf-8", newline="\n").write("".join(n))

# ---------------- settings/<grupo>.js ----------------
os.makedirs("settings", exist_ok=True)
tpl = """// settings.js do {g} — gerado automaticamente
module.exports = {{
    flowFile: 'flows.json',
    credentialSecret: '{cred}',
    editorTheme: {{
        page: {{
            title: "{titulo}",
        }},
        header: {{
            title: "{titulo}",
        }},
        projects: {{
            enabled: true,
        }},
    }},
    adminAuth: {{
        type: "credentials",
        users: [
            {{
                username: "{g}",
                password: "{hash_admin}",
                permissions: "*"
            }},
            {{
                username: "{g}-view",
                password: "{hash_view}",
                permissions: "read"
            }}
        ]
    }},
    // {comentario_raiz}
    httpAdminRoot: '{raiz}',
    httpNodeRoot: '{raiz}',
    uiPort: 1880,
    logging: {{ console: {{ level: 'info' }} }}
}};
"""

credenciais_geradas = []

for g in todos_servicos:
    senha_admin = gerar_senha(8)
    senha_view = gerar_senha(8)
    
    if is_notas(g):
        titulo = f"{TURMA.upper()} - PAINEL DE NOTAS"
    elif is_prof(g):
        titulo = f"{TURMA.upper()} - PROFESSOR"
    else:
        titulo = g.upper()
    
    hash_admin = bcrypt.hashpw(senha_admin.encode('utf-8'), bcrypt.gensalt(8)).decode('utf-8')
    hash_view = bcrypt.hashpw(senha_view.encode('utf-8'), bcrypt.gensalt(8)).decode('utf-8')
    
    open(f"settings/{g}.js", "w", encoding="utf-8", newline="\n").write(
        tpl.format(
            g=g, 
            cred=secrets.token_hex(16), 
            titulo=titulo,
            hash_admin=hash_admin, 
            hash_view=hash_view,
            raiz=(f"/{g}/" if MODO == "path" else "/"),
            comentario_raiz=(f"Node-RED vive em http://<dominio>/{g}/ (modo path)" if MODO == "path"
                             else f"Node-RED vive na raiz do seu proprio subdominio ({g}.<dominio>)"),
        )
    )
    
    credenciais_geradas.append((g, senha_admin, f"{g}-view", senha_view))

# ---------------- nginx/html/index.html ----------------
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
        '      <a class="{classe}" href="{url}">\n'
        '        <span class="node__idx">{idx}</span>\n'
        '        <span class="node__name">{nome}</span>\n'
        '        <span class="node__topic">{g}/#</span>\n'
        '        <span class="node__go">abrir editor &rarr;</span>\n'
        '      </a>\n'.format(classe=classe, g=g, idx=idx, nome=nome, url=url_de(g)))

cards.append(
    '      <a class="node node--mqtt" href="{h}">\n'
    '        <span class="node__idx">mqtt</span>\n'
    '        <span class="node__name">MQTT Explorer</span>\n'
    '        <span class="node__topic">#  ·  broker da turma</span>\n'
    '        <span class="node__go">{go} &rarr;</span>\n'
    '      </a>\n'.format(h=MQTTX_URL,
                         go="abrir explorer (login)" if MQTTX_AUTH else "abrir explorer"))

if GITEA:
    cards.append(
        '      <a class="node node--git" href="{u}">\n'
        '        <span class="node__idx">git</span>\n'
        '        <span class="node__name">Gitea</span>\n'
        '        <span class="node__topic">{t}-grupo-&lt;letra&gt;</span>\n'
        '        <span class="node__go">abrir repositórios &rarr;</span>\n'
        '      </a>\n'.format(u=GITEA_URL, t=TURMA))

if CHAT:
    cards.append(
        '      <a class="node node--chat" href="{u}">\n'
        '        <span class="node__idx">chat</span>\n'
        '        <span class="node__name">Chat da turma</span>\n'
        '        <span class="node__topic">canal privado por grupo</span>\n'
        '        <span class="node__go">abrir Mattermost &rarr;</span>\n'
        '      </a>\n'.format(u=CHAT_URL))

cards_html = "".join(cards)

html = (PORTAL_HTML
        .replace("{{CARDS}}", cards_html)
        .replace("{{MQTTX_URL}}", MQTTX_URL)
        .replace("{{MQTTX_LABEL}}", MQTTX_URL.split("//", 1)[1].rstrip("/"))
        .replace("{{TURMA}}", TURMA))
open("nginx/html/index.html", "w", encoding="utf-8", newline="\n").write(html)

# ---------------- mqtt-explorer/data/settings.json ----------------
os.makedirs("mqtt-explorer/data", exist_ok=True)
conn_id = secrets.token_hex(4) + "-" + secrets.token_hex(2) + "-" + secrets.token_hex(2) \
    + "-" + secrets.token_hex(2) + "-" + secrets.token_hex(6)
mqttx_settings = {
    "ConnectionManager_connections": {
        conn_id: {
            "configVersion": 1,
            "certValidation": False,
            "clientId": f"mqtt-explorer-{secrets.token_hex(4)}",
            "id": conn_id,
            "name": f"LAB {TURMA} (mosquitto)",
            "encryption": False,
            "subscriptions": [
                {"topic": "#", "qos": 0},
                {"topic": "$SYS/#", "qos": 0},
            ],
            "type": "mqtt",
            "host": "mosquitto",
            "port": 1883,
            "protocol": "mqtt",
        }
    },
    "Settings": {
        "timeLocale": "pt-BR",
        "topicOrder": "none",
        "highlightTopicUpdates": True,
        "valueRendererDisplayMode": "diff",
        "selectTopicWithMouseOver": False,
        "theme": "light",
    },
}
with open("mqtt-explorer/data/settings.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(mqttx_settings, f, indent=2, ensure_ascii=False)
print("🔭 mqtt-explorer/data/settings.json gerado com sucesso.")

# ---------------- gitea/init/gitea-init.sh ----------------
GITEA_INIT_TPL = r"""#!/bin/bash
# gitea-init.sh — gerado por gen_iot_win_portal.py (turma __TURMA__)
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
    os.makedirs("gitea/init", exist_ok=True)
    senhas = {u: s for (u, s, _uv, _sv) in credenciais_geradas}
    corpo = []
    corpo.append(f'ensure_user "{notas_service}" "{senhas[notas_service]}" '
                 f'"{notas_service}@{DOMINIO}" "Avaliador {TURMA}"')
    for g in grupos_alunos:
        org = org_de(g)
        L = letra_de(g).upper()
        corpo += [
            "",
            f"# ---- {g} -> organizacao {org}",
            f'ensure_user "{g}" "{senhas[g]}" "{g}@{DOMINIO}" "Grupo {L} ({TURMA})"',
            f'ensure_org  "{org}" "Grupo {L} - Turma {TURMA}"',
            f'ensure_team "{org}" "grupo" write "{g}"',
            f'ensure_team "{org}" "avaliacao" read "{notas_service}"',
            f'ensure_repo "{org}" "$REPO"',
        ]
    script = (GITEA_INIT_TPL
              .replace("__TURMA__", TURMA)
              .replace("__ADMIN_USER__", prof)
              .replace("__ADMIN_PASS__", senhas[prof])
              .replace("__ADMIN_EMAIL__", f"{prof}@{DOMINIO}")
              .replace("__REPO__", GITEA_REPO)
              .replace("__CORPO__", "\n".join(corpo)))
    with open("gitea/init/gitea-init.sh", "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    os.chmod("gitea/init/gitea-init.sh", 0o755)
    print("🐙 gitea/init/gitea-init.sh gerado com sucesso.")

# ---------------- postgres/init/bancos.sql ----------------
if POSTGRES:
    os.makedirs("postgres/init", exist_ok=True)
    sql = ["-- bancos.sql — gerado por gen_iot_win_portal.py",
           "-- Idempotente: roda a cada 'docker compose up' (servico db-init).",
           "-- Cria usuarios/bancos que faltarem e re-sincroniza as senhas.", ""]
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
    with open("postgres/init/bancos.sql", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sql))
    print("🐘 postgres/init/bancos.sql gerado com sucesso.")

# ---------------- mattermost/init (Dockerfile + mattermost-init.sh) ----------------
MM_INIT_DOCKERFILE = """# Imagem auxiliar: a imagem oficial do Mattermost nao tem shell (distroless),
# entao copiamos o mmctl dela para um Debian minimo com bash.
ARG MM_IMAGE=mattermost/mattermost-team-edition:release-11
FROM ${MM_IMAGE} AS mm
FROM debian:bookworm-slim
COPY --from=mm /mattermost/bin/mmctl /usr/local/bin/mmctl
"""

MM_INIT_TPL = r"""#!/bin/bash
# mattermost-init.sh — gerado por gen_iot_win_portal.py (turma __TURMA__)
# Cria/atualiza no Mattermost: equipe da turma, usuarios de credenciais.txt,
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

# equipe da turma (privada: so entra quem o script adicionar)
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
    os.makedirs("mattermost/init", exist_ok=True)
    senhas_mm = {u: s for (u, s, _uv, _sv) in credenciais_geradas}
    usuarios = [f'ensure_user "{prof}" "{senhas_mm[prof]}" "{prof}@{DOMINIO}" "Professor" admin']
    for g in grupos_alunos:
        L = letra_de(g).upper()
        usuarios.append(f'ensure_user "{g}" "{senhas_mm[g]}" "{g}@{DOMINIO}" "Grupo {L}"')
    todos_chat = " ".join(f'"{u}"' for u in [prof] + grupos_alunos)
    canais = [f'ensure_channel "avisos" "Avisos" nao "Avisos do professor para a turma" {todos_chat}']
    for g in grupos_alunos:
        L = letra_de(g).upper()
        canais.append(f'ensure_channel "{g}" "Grupo {L} (privado)" sim '
                      f'"Conversa privada entre o grupo {L} e o professor" "{g}" "{prof}"')
    script = (MM_INIT_TPL
              .replace("__TURMA__", TURMA)
              .replace("__TEAM__", CHAT_TEAM)
              .replace("__TEAM_DISPLAY__", f"Turma {TURMA.upper()}")
              .replace("__USUARIOS__", "\n".join(usuarios))
              .replace("__CANAIS__", "\n".join(canais)))
    with open("mattermost/init/mattermost-init.sh", "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    os.chmod("mattermost/init/mattermost-init.sh", 0o755)
    with open("mattermost/init/Dockerfile", "w", encoding="utf-8", newline="\n") as f:
        f.write(MM_INIT_DOCKERFILE)
    print("💬 mattermost/init/mattermost-init.sh gerado com sucesso.")

# ---------------- dnsmasq ----------------
if DNS:
    os.makedirs("dnsmasq", exist_ok=True)
    with open("dnsmasq/Dockerfile", "w", encoding="utf-8", newline="\n") as f:
        f.write("FROM alpine:3.20\n"
                "RUN apk add --no-cache dnsmasq\n"
                "EXPOSE 53/udp 53/tcp\n"
                'ENTRYPOINT ["dnsmasq", "-k", "--conf-file=/etc/dnsmasq.conf"]\n')
    conf = [
        "# dnsmasq.conf — gerado por gen_iot_win_portal.py",
        f"# Resolve {DOMINIO} e TODOS os subdominios (*.{DOMINIO}) para {IP};",
        "# o resto e encaminhado aos servidores externos (server=).",
        "no-resolv",
        "no-hosts",
        "domain-needed",
        "bogus-priv",
        "cache-size=1000",
        "log-facility=-",
        "# log-queries        # descomente para ver cada consulta nos logs",
    ]
    conf += [f"server={u}" for u in DNS_UPSTREAM]
    conf += [f"address=/{DOMINIO}/{IP}", ""]
    with open("dnsmasq/dnsmasq.conf", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(conf))
    print("🧭 dnsmasq/dnsmasq.conf gerado com sucesso.")

# ---------------- .segredos.json ----------------
with open(ARQ_SEGREDOS, "w", encoding="utf-8", newline="\n") as f:
    json.dump(SEGREDOS, f, indent=2)
try:
    os.chmod(ARQ_SEGREDOS, 0o600)
except OSError:
    pass

# ---------------- Salvar Credenciais em Arquivo ----------------
with open("credenciais.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write(f"=== CREDENCIAIS TURMA {TURMA.upper()} ===\n\n")
    f.write(f"{'USUÁRIO ADMIN':<13} | {'SENHA ADMIN':<12} | {'USUÁRIO VIEW':<15} | {'SENHA VIEW':<10}\n")
    f.write("-" * 62 + "\n")
    for u_admin, s_admin, u_view, s_view in credenciais_geradas:
        f.write(f"{u_admin:<13} | {s_admin:<12} | {u_view:<15} | {s_view:<10}\n")
    f.write("\n=== MQTT EXPLORER (único para todos) ===\n")
    f.write(f"URL: {MQTTX_URL}   (ou http://{IP}:{MQTTX_PORTA}/)\n")
    if GITEA:
        f.write("\n=== GITEA (único para todos) ===\n")
        f.write(f"URL: {GITEA_URL}\n")
        f.write("Login: mesmo USUÁRIO ADMIN / SENHA ADMIN da tabela acima.\n")
        f.write(f"{prof} = administrador do Gitea (dono de todas as organizações)\n")
        f.write(f"{notas_service} = leitura em todas as organizações (time 'avaliacao')\n")
        for g in grupos_alunos:
            extra = f"   repo: {GITEA_URL}{org_de(g)}/{GITEA_REPO}.git" if GITEA_REPO else ""
            f.write(f"{g:<13} -> org {org_de(g)}{extra}\n")
        if GITEA_REPO:
            f.write(f"Clone de dentro do Node-RED (Projects): http://gitea:3000/<org>/{GITEA_REPO}.git\n")
    if CHAT:
        f.write("\n=== CHAT — MATTERMOST (único para todos) ===\n")
        f.write(f"URL: {CHAT_URL}\n")
        f.write("Login: mesmo USUÁRIO ADMIN / SENHA ADMIN da tabela acima (contas por grupo).\n")
        f.write(f"{prof} = administrador do sistema; participa de todos os canais.\n")
        f.write(f"Equipe: {CHAT_TEAM}   ·   canal público: avisos   ·   "
                f"canais privados: {grupos_alunos[0]} .. {grupos_alunos[-1]}\n")
    if POSTGRES:
        f.write("\n=== POSTGRESQL (interno; só para o professor) ===\n")
        f.write(f"postgres (superusuário): {PG_ROOT_SENHA}\n")
        if GITEA_PG:
            f.write(f"gitea:      {PG_GITEA_SENHA}\n")
        if CHAT:
            f.write(f"mattermost: {PG_MM_SENHA}\n")
        f.write("(valores guardados em .segredos.json e reaproveitados ao regerar)\n")
    if DNS:
        f.write("\n=== DNS (dnsmasq) ===\n")
        f.write(f"Servidor DNS do lab: {IP}   ·   *.{DOMINIO} -> {IP}\n")
    f.write("\n=== ENDEREÇOS (modo " + MODO + ") ===\n")
    f.write(f"Portal: http://{DOMINIO}/\n")
    for g in todos_servicos:
        f.write(f"{g:<13} {url_de(g)}\n")
    if MQTTX_AUTH:
        f.write(f"Usuário: {MQTTX_USER}\nSenha:   {MQTTX_SENHA}\n")
    else:
        f.write("Acesso sem login (MQTT_EXPLORER_SKIP_AUTH=true)\n")

print("\n🔒 As credenciais foram salvas em 'credenciais.txt'.")

# ---------------- hosts.lab (resolucao dos subdominios nos clientes) ----------------
with open("hosts.lab", "w", encoding="utf-8", newline="\n") as f:
    f.write("# Cole estas linhas no /etc/hosts dos clientes (Linux/Mac)\n")
    f.write("# ou em C:\\Windows\\System32\\drivers\\etc\\hosts (Windows).\n")
    if DNS:
        f.write(f"# (Desnecessario se os clientes usarem o DNS do lab: {IP})\n")
    f.write(f"# Se o IP do servidor mudar, troque {IP} em todas.\n")
    if MODO == "subdominio":
        f.write("# Alternativa (wildcard) com dnsmasq:  address=/" + DOMINIO + "/" + IP + "\n")
    else:
        f.write("# Modo path: basta o dominio base (todos os servicos sao caminhos dele).\n")
    f.write("\n")
    f.write(f"{IP}\t{DOMINIO}\n")
    if MODO == "subdominio":
        for g in todos_servicos:
            f.write(f"{IP}\t{g}.{DOMINIO}\n")
        f.write(f"{IP}\t{MQTTX_HOST}\n")
        if GITEA:
            f.write(f"{IP}\t{GITEA_HOST}\n")
        if CHAT:
            f.write(f"{IP}\t{CHAT_HOST}\n")
print("🌐 hosts.lab gerado com sucesso.")

# ---------------- Relatório Final ----------------
print(f"OK: turma {TURMA} — {N} grupos ({grupos_alunos[0]}..{grupos_alunos[-1]}) + professor ({prof}) + avaliador ({notas_service}).\n")
print("=== CREDENCIAIS GERADAS ===")
print(f"{'USUÁRIO ADMIN':<13} | {'SENHA ADMIN':<12} | {'USUÁRIO VIEW':<15} | {'SENHA VIEW':<10}")
print("-" * 62)
for u_admin, s_admin, u_view, s_view in credenciais_geradas:
    print(f"{u_admin:<13} | {s_admin:<12} | {u_view:<15} | {s_view:<10}")
print("-" * 62)
print(f"\nModo: {MODO}   ·   Portal: http://{DOMINIO}/")
print("Cada grupo abre em seu " + ("caminho" if MODO == "path" else "subdominio") + ", ex.:")
print(f"  {url_de(grupos_alunos[0])}   ·   professor: {url_de(prof)}   ·   notas: {url_de(notas_service)}")
if GITEA:
    print(f"\nGitea (único): {GITEA_URL}   (login = credenciais Node-RED admin; admin: {prof})")
    print(f"  organizações: {org_de(grupos_alunos[0])} .. {org_de(grupos_alunos[-1])}"
          + (f"   ·   repo inicial: {GITEA_REPO}" if GITEA_REPO else ""))
if CHAT:
    print(f"\nChat (Mattermost): {CHAT_URL}   (login = credenciais Node-RED admin; admin: {prof})")
    print(f"  equipe {CHAT_TEAM}: canal 'avisos' + canal privado por grupo")
if GITEA:
    print(f"  Gitea usando: {'PostgreSQL' if GITEA_PG else 'SQLite'}")
if DNS:
    print(f"\nDNS do lab (dnsmasq): {IP}:53  ->  *.{DOMINIO} = {IP}")
print(f"\nMQTT Explorer (único): {MQTTX_URL}  ou  http://{IP}:{MQTTX_PORTA}/")
if MQTTX_AUTH:
    print(f"  login: {MQTTX_USER} / {MQTTX_SENHA}")
else:
    print("  acesso sem login (use --mqtt-explorer-auth para exigir credenciais)")

# ---------------- Resumo Final ----------------
print(f"\n📂 Arquivos gerados em: {SAIDA_ABS}")
print("- docker-compose.yml")
print("- nginx/nginx.conf")
print("- nginx/html/index.html")
print("- Dockerfile")
print("- mosquitto/mosquitto.conf")
print("- credenciais.txt")
print("- settings/<grupo>.js (um por serviço)")
print("- data/<grupo>/.gitkeep (um por serviço)")
print("- mqtt-explorer/data/settings.json (conexão pré-configurada ao mosquitto)")
if GITEA:
    print("- gitea/init/gitea-init.sh (usuários, organizações e times; roda no container gitea-init)")
if CHAT:
    print("- mattermost/init/ (Dockerfile + mattermost-init.sh: equipe, usuários e canais)")
if POSTGRES:
    print("- postgres/init/bancos.sql (bancos e usuários do PostgreSQL)")
if DNS:
    print("- dnsmasq/ (Dockerfile + dnsmasq.conf)")
print("- .segredos.json (senhas internas; reaproveitadas ao regerar — não apague)")
print("- hosts.lab (nomes para o /etc/hosts dos clientes)")
print(f"\n▶  Para subir:  cd {SAIDA_ABS} && docker compose up -d --build")

if DNS:
    print(f"\n🧭 DNS incluído: configure os clientes (ou o DHCP do lab) com DNS = {IP}.")
    print("    Libere a porta 53 (udp/tcp) no firewall. O hosts.lab continua como alternativa.")
    if IP.startswith("127."):
        print("    ⚠️  Com --ip 127.x o DNS só atende o próprio servidor: use o IP real da rede.")
elif MODO == "subdominio":
    print("\n⚠️  Subdomínios exigem resolução de nome: distribua o hosts.lab para os")
    print("    clientes OU configure um DNS wildcard *." + DOMINIO + " apontando para o servidor.")
else:
    print("\n⚠️  Modo path: os clientes só precisam resolver " + DOMINIO + " (uma linha no hosts.lab).")
    print(f"    O MQTT Explorer não suporta subcaminho: usa a porta {MQTTX_PORTA} (libere no firewall).")
print("    Ajuste o --ip com o IP real antes de distribuir (agora: " + IP + ").")

print("\n✅ Ambiente da turma", TURMA, "configurado com sucesso!")
