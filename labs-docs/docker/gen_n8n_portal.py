#!/usr/bin/env python3
"""Gera o LAB local com portal nginx na frente das instancias n8n.

Arquitetura (opcao A): UMA instancia n8n por grupo, isoladas fisicamente
(banco SQLite proprio e login proprio por container). Roteamento por
SUBDOMINIO — cada n8n roda na raiz do seu proprio subdominio, evitando os
problemas conhecidos do n8n atras de proxy reverso em subpath.

Reservas de letras:
  - 'p' para o PROFESSOR  (ex.: n21-p)
  - 'n' para NOTAS        (ex.: n21-n)

Gera:
  - docker-compose.yml       (nginx + n8n por grupo + prof + avaliador de notas + mosquitto)
  - nginx/nginx.conf         (portal em / + proxy reverso por subdominio)
  - nginx/html/index.html    (pagina inicial listando os grupos e o painel de notas)
  - mosquitto/mosquitto.conf (broker MQTT)
  - data/<grupo>/            (pasta bind-montada em /home/node/.n8n; guarda o banco do n8n)
  - hosts.lab                (linhas prontas para /etc/hosts dos clientes)
  - credenciais.txt          (email + senha do owner de cada instancia)

Autenticacao no n8n:
  A partir do n8n v1/v2, basic auth foi removido. Cada instancia usa "user
  management" com um OWNER pre-provisionado por variaveis de ambiente
  (N8N_INSTANCE_OWNER_MANAGED_BY_ENV). O login e por EMAIL + SENHA.
  Nao existe papel "somente-leitura" (o antigo usuario -view) na edicao
  Community — isso exigiria RBAC/Projects (plano pago), entao foi omitido.

Uso:
  python3 gen_n8n_portal.py
  python3 gen_n8n_portal.py --turma n21 --grupos 10 --dominio n8n.lab --ip 192.168.0.10
"""
import sys, os, secrets, string, argparse, json
import bcrypt

ap = argparse.ArgumentParser()
ap.add_argument("--turma", default="n21", help="Identificador da turma (ex.: n21)")
ap.add_argument("--grupos", type=int, default=10, help="Quantidade de grupos de alunos")
ap.add_argument("--dominio", default="n8n.lab", help="Dominio base do lab (ex.: n8n.local)")
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
    sys.exit(f"Maximo de {len(letras)} grupos (letras a-z sem 'p' e 'n').")

# Definicao dos nomes dos servicos
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


def gerar_senha(tamanho=10):
    """Senha que satisfaz a politica do n8n: >=8 chars, com maiuscula, minuscula e digito."""
    alfabeto = string.ascii_letters + string.digits
    while True:
        s = ''.join(secrets.choice(alfabeto) for _ in range(tamanho))
        if (any(c.islower() for c in s)
                and any(c.isupper() for c in s)
                and any(c.isdigit() for c in s)):
            return s


# ---------------- Segredos persistentes (idempotencia) ----------------
# A N8N_ENCRYPTION_KEY e gravada pelo n8n em data/<g>/config no primeiro boot.
# Se ela mudar entre execucoes, o n8n se recusa a subir ("Mismatching
# encryption keys"). Por isso guardamos senha/hash/chave em .lab_secrets.json
# e reutilizamos nas proximas execucoes, tornando o gerador idempotente.
# ATENCAO: este arquivo contem segredos — nao versione (adicione ao .gitignore).
SECRETS_FILE = ".lab_secrets.json"
try:
    with open(SECRETS_FILE, encoding="utf-8") as _f:
        _saved = json.load(_f)
except (FileNotFoundError, json.JSONDecodeError):
    _saved = {}


# ---------------- Pre-gera configuracao/credenciais por instancia ----------------
# (precisa vir antes do compose, pois o hash e a chave de criptografia vao no compose)
cfg = {}
for g in todos_servicos:
    if is_notas(g):
        titulo = f"{TURMA.upper()} - PAINEL DE NOTAS"
        first, last = "Notas", TURMA
    elif is_prof(g):
        titulo = f"{TURMA.upper()} - PROFESSOR"
        first, last = "Professor", TURMA
    else:
        titulo = g.upper()
        first, last = f"Grupo {letra_de(g).upper()}", TURMA

    prev = _saved.get(g, {})
    senha = prev.get("senha") or gerar_senha()
    hash_bcrypt = prev.get("hash") or \
        bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")
    enc_key = prev.get("enc_key") or secrets.token_hex(16)  # = credentialSecret do Node-RED

    cfg[g] = {
        "email": f"{g}@{DOMINIO}",
        "senha": senha,
        "hash": hash_bcrypt,
        "enc_key": enc_key,
        "titulo": titulo,
        "first": first,
        "last": last,
        "url": f"http://{g}.{DOMINIO}/",
    }

# Persiste os segredos para que as proximas execucoes reutilizem as mesmas chaves.
with open(SECRETS_FILE, "w", encoding="utf-8") as _f:
    json.dump(
        {g: {"senha": cfg[g]["senha"], "hash": cfg[g]["hash"], "enc_key": cfg[g]["enc_key"]}
         for g in todos_servicos},
        _f, indent=2,
    )
try:
    if hasattr(os, "chmod"):
        os.chmod(SECRETS_FILE, 0o600)
except OSError:
    pass


# ---------------- Pre-cria diretorios e .gitkeep ----------------
# n8n roda como uid 1000 (usuario 'node') e grava em /home/node/.n8n.
# Em Linux/Mac a pasta bind-montada precisa pertencer ao uid 1000, senao o
# n8n nao escreve. No Windows os.chown nao existe (o Docker Desktop cuida
# das permissoes do mount), entao pulamos essa etapa.
chown_suportado = hasattr(os, "chown")
chown_ok = True
for g in todos_servicos:
    d = f"data/{g}"
    os.makedirs(d, exist_ok=True)
    open(f"{d}/.gitkeep", "a").close()
    if chown_suportado:
        try:
            os.chown(d, 1000, 1000)
            os.chown(f"{d}/.gitkeep", 1000, 1000)
        except (PermissionError, OSError):
            chown_ok = False


# ---------------- mosquitto/mosquitto.conf ----------------
os.makedirs("mosquitto", exist_ok=True)
mosquitto_conf = """listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest stdout
"""
open("mosquitto/mosquitto.conf", "w", encoding="utf-8").write(mosquitto_conf)
print("mosquitto.conf gerado.")


# ---------------- docker-compose.yml ----------------
def env_n8n(g):
    """Bloco de variaveis de ambiente do n8n para o servico g.

    OBS: o hash bcrypt contem '$', que o docker compose interpreta como
    interpolacao de variavel. Por isso os '$' sao dobrados ('$$') aqui —
    o compose os converte de volta para '$' dentro do container.
    """
    c = cfg[g]
    hash_compose = c["hash"].replace("$", "$$")
    linhas = [
        "    environment:\n",
        f"      - N8N_HOST={g}.{DOMINIO}\n",
        "      - N8N_PORT=5678\n",
        "      - N8N_PROTOCOL=http\n",
        "      - N8N_SECURE_COOKIE=false\n",
        f"      - N8N_EDITOR_BASE_URL=http://{g}.{DOMINIO}/\n",
        f"      - N8N_WEBHOOK_URL=http://{g}.{DOMINIO}/\n",
        "      - N8N_PROXY_HOPS=1\n",
        f"      - N8N_ENCRYPTION_KEY={c['enc_key']}\n",
        "      - N8N_INSTANCE_OWNER_MANAGED_BY_ENV=true\n",
        f"      - N8N_INSTANCE_OWNER_EMAIL={c['email']}\n",
        f"      - N8N_INSTANCE_OWNER_FIRST_NAME={c['first']}\n",
        f"      - N8N_INSTANCE_OWNER_LAST_NAME={c['last']}\n",
        f"      - N8N_INSTANCE_OWNER_PASSWORD_HASH={hash_compose}\n",
        "      - GENERIC_TIMEZONE=America/Sao_Paulo\n",
        "      - TZ=America/Sao_Paulo\n",
        "      - N8N_RUNNERS_ENABLED=true\n",
        "      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true\n",
        "      - N8N_DIAGNOSTICS_ENABLED=false\n",
        "      - N8N_VERSION_NOTIFICATIONS_ENABLED=false\n",
        "      - N8N_PERSONALIZATION_ENABLED=false\n",
        "      - N8N_TEMPLATES_ENABLED=false\n",
    ]
    return linhas


c = [
    "# LAB local com portal nginx — gerado por gen_n8n_portal.py\n",
    f"# Turma {TURMA} · {N} grupos + professor ({prof}) + avaliador ({notas_service})\n",
    f"# Dominio: {DOMINIO}   ·   Portal: http://{DOMINIO}/\n",
    "# Subir:  docker compose up -d   ->  acesse http://" + DOMINIO + "/\n",
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
    c.append(f"      - {g}-n8n\n")

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
        f"\n  {g}-n8n:\n",
        "    image: n8nio/n8n:latest\n",
        f"    container_name: {g}-n8n\n",
        "    restart: unless-stopped\n",
        "    volumes:\n",
        f"      - ./data/{g}:/home/node/.n8n\n",
    ]
    c += env_n8n(g)
    c += [
        "    depends_on:\n",
        "      - mosquitto\n",
        "    networks:\n",
        "      - labnet\n",
    ]

# Container de Notas (monta a pasta global de dados em modo leitura)
c += [
    f"\n  {notas_service}-n8n:\n",
    "    image: n8nio/n8n:latest\n",
    f"    container_name: {notas_service}-n8n\n",
    "    restart: unless-stopped\n",
    "    volumes:\n",
    f"      - ./data/{notas_service}:/home/node/.n8n\n",
    "      - ./data:/data_grupos:ro\n",
]
c += env_n8n(notas_service)
c += [
    "    depends_on:\n",
    "      - mosquitto\n",
    "    networks:\n",
    "      - labnet\n",
]

c += ["\nvolumes:\n", "  mosquitto_data:\n"]
c += ["\nnetworks:\n", "  labnet:\n", "    driver: bridge\n"]
open("docker-compose.yml", "w", encoding="utf-8").write("".join(c))
print("docker-compose.yml gerado.")


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
        f"\n    # {g} ({papel}) -> instancia n8n em http://{g}.{DOMINIO}/\n",
        "    server {\n",
        "        listen 80;\n",
        f"        server_name {g}.{DOMINIO};\n",
        "        location / {\n",
        f"            proxy_pass http://{g}-n8n:5678;\n",
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
print("nginx/nginx.conf gerado.")


# ---------------- nginx/html/index.html ----------------
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
      <p class="sub">Selecione seu grupo para abrir o editor n8n. Cada grupo
      publica no broker MQTT sob seu proprio topico, no formato
      <code>{{TURMA}}-&lt;letra&gt;/#</code>. O login e por e-mail (veja
      <code>credenciais.txt</code>).</p>
    </header>

    <main class="grid">
{{CARDS}}    </main>

    <footer class="foot">
      <span>MQTT: porta 1883</span>
      <span>topico base: {{TURMA}}-&lt;letra&gt;/</span>
      <span>banco: SQLite por instancia n8n</span>
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
        '      <a class="{classe}" href="{url}">\n'
        '        <span class="node__idx">{idx}</span>\n'
        '        <span class="node__name">{nome}</span>\n'
        '        <span class="node__topic">{g}/#</span>\n'
        '        <span class="node__go">abrir editor &rarr;</span>\n'
        '      </a>\n'.format(classe=classe, g=g, idx=idx, nome=nome, url=cfg[g]["url"]))

html = (PORTAL_HTML
        .replace("{{CARDS}}", "".join(cards))
        .replace("{{TURMA}}", TURMA))
open("nginx/html/index.html", "w", encoding="utf-8").write(html)
print("nginx/html/index.html gerado.")


# ---------------- hosts.lab (resolucao dos subdominios nos clientes) ----------------
with open("hosts.lab", "w", encoding="utf-8") as f:
    f.write("# Cole estas linhas no /etc/hosts dos clientes (Linux/Mac)\n")
    f.write("# ou em C:\\Windows\\System32\\drivers\\etc\\hosts (Windows).\n")
    f.write(f"# Se o IP do servidor mudar, troque {IP} por todos.\n")
    f.write("# Alternativa (wildcard) com dnsmasq:  address=/" + DOMINIO + "/" + IP + "\n\n")
    f.write(f"{IP}\t{DOMINIO}\n")
    for g in todos_servicos:
        f.write(f"{IP}\t{g}.{DOMINIO}\n")
print("hosts.lab gerado.")


# ---------------- credenciais.txt ----------------
with open("credenciais.txt", "w", encoding="utf-8") as f:
    f.write(f"=== CREDENCIAIS TURMA {TURMA.upper()} (n8n) ===\n\n")
    f.write(f"Portal: http://{DOMINIO}/\n")
    f.write("Login em cada instancia e por E-MAIL + SENHA (owner pre-provisionado).\n\n")
    f.write(f"{'SERVICO':<10} | {'URL':<28} | {'EMAIL (login)':<22} | {'SENHA':<10}\n")
    f.write("-" * 82 + "\n")
    for g in todos_servicos:
        d = cfg[g]
        f.write(f"{g:<10} | {d['url']:<28} | {d['email']:<22} | {d['senha']:<10}\n")
print("credenciais.txt gerado.")


# ---------------- Relatorio Final ----------------
print(f"\nOK: turma {TURMA} — {N} grupos ({grupos_alunos[0]}..{grupos_alunos[-1]}) "
      f"+ professor ({prof}) + avaliador ({notas_service}).")
print(f"Portal: http://{DOMINIO}/\n")

print(f"{'SERVICO':<10} | {'URL':<28} | {'EMAIL (login)':<22} | {'SENHA':<10}")
print("-" * 82)
for g in todos_servicos:
    d = cfg[g]
    print(f"{g:<10} | {d['url']:<28} | {d['email']:<22} | {d['senha']:<10}")
print("-" * 82)

print("\nArquivos gerados:")
print("- docker-compose.yml")
print("- nginx/nginx.conf")
print("- nginx/html/index.html")
print("- mosquitto/mosquitto.conf")
print("- hosts.lab")
print("- credenciais.txt")
print("- data/<grupo>/ (bind-mount de /home/node/.n8n por instancia)")

print("\nPassos para subir:")
print("  1) Ajuste o --ip (ou edite hosts.lab) com o IP real do servidor.")
print("  2) Distribua as linhas de hosts.lab para os clientes, OU configure")
print("     um DNS wildcard *." + DOMINIO + " apontando para o servidor.")
print("  3) docker compose up -d")
print("  4) Acesse http://" + DOMINIO + "/  (o n8n leva alguns segundos para subir).")

if not chown_suportado:
    print("\n[INFO] Windows detectado: os.chown nao se aplica. O Docker Desktop")
    print("  cuida das permissoes do bind mount. Se algum n8n reclamar de")
    print("  permissao (EACCES) em /home/node/.n8n, verifique o File Sharing")
    print("  do Docker Desktop (Settings > Resources > File Sharing).")
elif not chown_ok:
    print("\n[ATENCAO] Nao consegui ajustar o dono das pastas data/ para uid 1000.")
    print("  O n8n roda como uid 1000 e precisa gravar em /home/node/.n8n.")
    print("  Rode antes de subir:  sudo chown -R 1000:1000 data/")

print("\nObservacoes n8n (diferencas em relacao ao Node-RED):")
print("- Nao ha usuario 'somente-leitura' (o antigo -view): isso exige RBAC/Projects (pago).")
print("- 'notas' monta ./data:/data_grupos:ro para inspecionar arquivos dos grupos.")
print("  Para visao ao vivo entre grupos, prefira o MQTT: assine  " + TURMA + "-+/#  no mosquitto.")
print("- Cada instancia n8n consome ~300-500 MB de RAM. " + str(len(todos_servicos))
      + " instancias => reserve memoria no servidor.")
print("\nAmbiente da turma", TURMA, "configurado.")
