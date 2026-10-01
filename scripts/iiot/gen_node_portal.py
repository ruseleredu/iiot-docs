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

Todos os arquivos são gravados dentro da pasta de saída (--saida, padrão: lab_<turma>).

Uso:
  python3 gen_portal.py       # turma n21, 10 grupos + prof + notas
  python3 gen_portal.py --turma n21 --grupos 10
  python3 gen_portal.py --mqtt-explorer-auth                       # login com senha gerada
  python3 gen_portal.py --mqtt-explorer-auth --mqtt-explorer-senha minhaSenha
  python3 gen_portal.py --modo path       # um dominio, varios caminhos (node.lab/n21-a/)
  python3 gen_portal.py --sem-gitea       # sem o servidor Git

Modos (--modo):
  subdominio (padrao): um host por servico  -> http://n21-a.node.lab/
  path:                um dominio, varios caminhos -> http://node.lab/n21-a/
                       (MQTT Explorer fica na porta direta, ex.: http://node.lab:3001/)
"""
import sys, os, secrets, string, argparse, json
import bcrypt

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

TURMA = args.turma
N = args.grupos
DOMINIO = args.dominio
IP = args.ip

# Pasta de saída: tudo é gerado dentro dela
SAIDA = args.saida or f"lab_{TURMA}"
os.makedirs(SAIDA, exist_ok=True)
os.chdir(SAIDA)
SAIDA_ABS = os.getcwd()

MODO = args.modo

# MQTT Explorer (serviço único para toda a turma)
MQTTX_HOST = f"mqtt.{DOMINIO}"
MQTTX_PORTA = args.mqtt_explorer_porta
# No modo path o MQTT Explorer é acessado pela porta direta (não suporta subcaminho)
MQTTX_URL = f"http://{MQTTX_HOST}/" if MODO == "subdominio" else f"http://{DOMINIO}:{MQTTX_PORTA}/"


# Gitea (serviço único; organizações por grupo)
GITEA = not args.sem_gitea
GITEA_REPO = args.gitea_repo.strip()
GITEA_HOST = f"git.{DOMINIO}"
GITEA_URL = f"http://{GITEA_HOST}/" if MODO == "subdominio" else f"http://{DOMINIO}/git/"
GITEA_DOMAIN = GITEA_HOST if MODO == "subdominio" else DOMINIO


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

open("mosquitto/mosquitto.conf", "w", encoding="utf-8").write(mosquitto_conf)
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

open("Dockerfile", "w", encoding="utf-8").write(dockerfile)
print("📦 Dockerfile gerado com sucesso.")

# ---------------- docker-compose.yml ----------------
c = [
    "# LAB local com portal nginx — gerado por gen_portal.py\n",
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
        "      - GITEA__database__DB_TYPE=sqlite3\n",
        f"      - GITEA__server__DOMAIN={GITEA_DOMAIN}\n",
        f"      - GITEA__server__ROOT_URL={GITEA_URL}\n",
        "      - GITEA__server__HTTP_PORT=3000\n",
        "      - GITEA__server__DISABLE_SSH=true\n",
        "      - GITEA__security__INSTALL_LOCK=true\n",
        f"      - GITEA__security__SECRET_KEY={secrets.token_hex(32)}\n",
        "      - GITEA__service__DISABLE_REGISTRATION=true\n",
        "      - GITEA__service__REQUIRE_SIGNIN_VIEW=true\n",
        "      - GITEA__service__DEFAULT_ORG_VISIBILITY=private\n",
        "      - GITEA__repository__DEFAULT_PRIVATE=private\n",
        "      - GITEA__repository__DEFAULT_BRANCH=main\n",
        "      - GITEA__ui__DEFAULT_THEME=gitea-auto\n",
        "      - GITEA__time__DEFAULT_UI_LOCATION=America/Sao_Paulo\n",
        "    volumes:\n",
        "      - ./gitea/data:/data\n",
        "    healthcheck:\n",
        '      test: ["CMD", "curl", "-fsS", "http://localhost:3000/api/healthz"]\n',
        "      interval: 10s\n",
        "      timeout: 5s\n",
        "      retries: 30\n",
        "    networks:\n",
        "      - labnet\n",
        "\n  gitea-init:\n",
        "    image: gitea/gitea:latest\n",
        "    container_name: lab-gitea-init\n",
        '    restart: "no"\n',
        '    entrypoint: ["/bin/bash", "/init/gitea-init.sh"]\n',
        "    volumes:\n",
        "      - ./gitea/data:/data\n",
        "      - ./gitea/init:/init:ro\n",
        "    depends_on:\n",
        "      gitea:\n",
        "        condition: service_healthy\n",
        "    networks:\n",
        "      - labnet\n",
    ]

c += ["\nvolumes:\n", "  mosquitto_data:\n"]
c += ["\nnetworks:\n", "  labnet:\n", "    driver: bridge\n"]
open("docker-compose.yml", "w", encoding="utf-8").write("".join(c))

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
    f"# nginx.conf — gerado por gen_portal.py (modo: {MODO})\n",
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

n += ["}\n"]
open("nginx/nginx.conf", "w", encoding="utf-8").write("".join(n))

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
    
    open(f"settings/{g}.js", "w", encoding="utf-8").write(
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

cards_html = "".join(cards)

html = (PORTAL_HTML
        .replace("{{CARDS}}", cards_html)
        .replace("{{MQTTX_URL}}", MQTTX_URL)
        .replace("{{MQTTX_LABEL}}", MQTTX_URL.split("//", 1)[1].rstrip("/"))
        .replace("{{TURMA}}", TURMA))
open("nginx/html/index.html", "w", encoding="utf-8").write(html)

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
with open("mqtt-explorer/data/settings.json", "w", encoding="utf-8") as f:
    json.dump(mqttx_settings, f, indent=2, ensure_ascii=False)
print("🔭 mqtt-explorer/data/settings.json gerado com sucesso.")

# ---------------- gitea/init/gitea-init.sh ----------------
GITEA_INIT_TPL = r"""#!/bin/bash
# gitea-init.sh — gerado por gen_portal.py (turma __TURMA__)
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
    os.makedirs("gitea/data", exist_ok=True)
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

# ---------------- Salvar Credenciais em Arquivo ----------------
with open("credenciais.txt", "w", encoding="utf-8") as f:
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
with open("hosts.lab", "w", encoding="utf-8") as f:
    f.write("# Cole estas linhas no /etc/hosts dos clientes (Linux/Mac)\n")
    f.write("# ou em C:\\Windows\\System32\\drivers\\etc\\hosts (Windows).\n")
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
print("- hosts.lab (nomes para o /etc/hosts dos clientes)")
print(f"\n▶  Para subir:  cd {SAIDA_ABS} && docker compose up -d --build")

if MODO == "subdominio":
    print("\n⚠️  Subdomínios exigem resolução de nome: distribua o hosts.lab para os")
    print("    clientes OU configure um DNS wildcard *." + DOMINIO + " apontando para o servidor.")
else:
    print("\n⚠️  Modo path: os clientes só precisam resolver " + DOMINIO + " (uma linha no hosts.lab).")
    print(f"    O MQTT Explorer não suporta subcaminho: usa a porta {MQTTX_PORTA} (libere no firewall).")
print("    Ajuste o --ip com o IP real antes de distribuir (agora: " + IP + ").")

print("\n✅ Ambiente da turma", TURMA, "configurado com sucesso!")
