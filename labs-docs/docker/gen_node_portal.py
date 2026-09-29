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
  
Uso:
  python3 gen_portal.py       # turma n21, 10 grupos + prof + notas
  python3 gen_portal.py --turma n21 --grupos 10
"""
import sys, os, secrets, string, argparse, json
import bcrypt

ap = argparse.ArgumentParser()
ap.add_argument("--turma", default="n21", help="Identificador da turma (ex.: n21)")
ap.add_argument("--grupos", type=int, default=10, help="Quantidade de grupos de alunos")
ap.add_argument("--dominio", default="node.lab", help="Dominio base do lab (ex.: node.lab)")
ap.add_argument("--ip", default="127.0.0.1", help="IP do servidor (usado no hosts.lab)")
args = ap.parse_args()

TURMA = args.turma
N = args.grupos
DOMINIO = args.dominio
IP = args.ip

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
    f"# Dominio: {DOMINIO}   ·   Portal: http://{DOMINIO}/\n",
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

c += ["\nvolumes:\n", "  mosquitto_data:\n"]
c += ["\nnetworks:\n", "  labnet:\n", "    driver: bridge\n"]
open("docker-compose.yml", "w", encoding="utf-8").write("".join(c))

# ---------------- nginx/nginx.conf ----------------
os.makedirs("nginx/html", exist_ok=True)
n = [
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
    "    }\n",
]
for g in todos_servicos:
    if is_notas(g):
        papel = "avaliador de notas"
    elif is_prof(g):
        papel = "professor"
    else:
        papel = "grupo"

    n += [
        f"\n    # {g} ({papel}) -> editor Node-RED em http://{g}.{DOMINIO}/\n",
        "    server {\n",
        "        listen 80;\n",
        f"        server_name {g}.{DOMINIO};\n",
        "        location / {\n",
        f"            proxy_pass http://{g}-nodered:1880;\n",
        "            proxy_http_version 1.1;\n",
        "            proxy_set_header Upgrade $http_upgrade;\n",
        "            proxy_set_header Connection $connection_upgrade;\n",
        "            proxy_set_header Host $host;\n",
        "            proxy_set_header X-Real-IP $remote_addr;\n",
        "            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n",
        "            proxy_set_header X-Forwarded-Proto $scheme;\n",
        "            proxy_read_timeout 3600s;\n",
        "            proxy_send_timeout 3600s;\n",
        "            proxy_buffering off;\n",
        "        }\n",
        "    }\n",
    ]
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
    // Node-RED vive na raiz do seu proprio subdominio ({g}.<dominio>)
    httpAdminRoot: '/',
    httpNodeRoot: '/',
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
            hash_view=hash_view
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
        '      <a class="{classe}" href="http://{g}.{dominio}/">\n'
        '        <span class="node__idx">{idx}</span>\n'
        '        <span class="node__name">{nome}</span>\n'
        '        <span class="node__topic">{g}/#</span>\n'
        '        <span class="node__go">abrir editor &rarr;</span>\n'
        '      </a>\n'.format(classe=classe, g=g, idx=idx, nome=nome, dominio=DOMINIO))

cards_html = "".join(cards)

html = (PORTAL_HTML
        .replace("{{CARDS}}", cards_html)
        .replace("{{TURMA}}", TURMA))
open("nginx/html/index.html", "w", encoding="utf-8").write(html)

# ---------------- Salvar Credenciais em Arquivo ----------------
with open("credenciais.txt", "w", encoding="utf-8") as f:
    f.write(f"=== CREDENCIAIS TURMA {TURMA.upper()} ===\n\n")
    f.write(f"{'USUÁRIO ADMIN':<13} | {'SENHA ADMIN':<12} | {'USUÁRIO VIEW':<15} | {'SENHA VIEW':<10}\n")
    f.write("-" * 62 + "\n")
    for u_admin, s_admin, u_view, s_view in credenciais_geradas:
        f.write(f"{u_admin:<13} | {s_admin:<12} | {u_view:<15} | {s_view:<10}\n")

print("\n🔒 As credenciais foram salvas em 'credenciais.txt'.")

# ---------------- hosts.lab (resolucao dos subdominios nos clientes) ----------------
with open("hosts.lab", "w", encoding="utf-8") as f:
    f.write("# Cole estas linhas no /etc/hosts dos clientes (Linux/Mac)\n")
    f.write("# ou em C:\\Windows\\System32\\drivers\\etc\\hosts (Windows).\n")
    f.write(f"# Se o IP do servidor mudar, troque {IP} em todas.\n")
    f.write("# Alternativa (wildcard) com dnsmasq:  address=/" + DOMINIO + "/" + IP + "\n\n")
    f.write(f"{IP}\t{DOMINIO}\n")
    for g in todos_servicos:
        f.write(f"{IP}\t{g}.{DOMINIO}\n")
print("🌐 hosts.lab gerado com sucesso.")

# ---------------- Relatório Final ----------------
print(f"OK: turma {TURMA} — {N} grupos ({grupos_alunos[0]}..{grupos_alunos[-1]}) + professor ({prof}) + avaliador ({notas_service}).\n")
print("=== CREDENCIAIS GERADAS ===")
print(f"{'USUÁRIO ADMIN':<13} | {'SENHA ADMIN':<12} | {'USUÁRIO VIEW':<15} | {'SENHA VIEW':<10}")
print("-" * 62)
for u_admin, s_admin, u_view, s_view in credenciais_geradas:
    print(f"{u_admin:<13} | {s_admin:<12} | {u_view:<15} | {s_view:<10}")
print("-" * 62)
print(f"\nPortal: http://{DOMINIO}/")
print("Cada grupo abre em seu subdominio, ex.:")
print(f"  http://{grupos_alunos[0]}.{DOMINIO}/   ·   professor: http://{prof}.{DOMINIO}/   ·   notas: http://{notas_service}.{DOMINIO}/")

# ---------------- Resumo Final ----------------
print("\n📂 Arquivos gerados:")
print("- docker-compose.yml")
print("- nginx/nginx.conf")
print("- nginx/html/index.html")
print("- Dockerfile")
print("- mosquitto/mosquitto.conf")
print("- credenciais.txt")
print("- settings/<grupo>.js (um por serviço)")
print("- data/<grupo>/.gitkeep (um por serviço)")
print("- hosts.lab (nomes dos subdomínios para o /etc/hosts dos clientes)")

print("\n⚠️  Subdomínios exigem resolução de nome: distribua o hosts.lab para os")
print("    clientes OU configure um DNS wildcard *." + DOMINIO + " apontando para o servidor.")
print("    Ajuste o --ip com o IP real antes de distribuir (agora: " + IP + ").")

print("\n✅ Ambiente da turma", TURMA, "configurado com sucesso!")
