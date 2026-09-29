#!/usr/bin/env python3
"""Gera um stack MINIMO (apenas nginx) para testar se os subdominios do
hosts.lab resolvem e chegam ao nginx — SEM subir as instancias reais.

Testa 4 servicos por grupo, no formato <servico>.<turma>-<grupo>.lab:

  n8n.<turma>-<grupo>.lab      n21-a, n21-b, ... n21-j
  nodered.<turma>-<grupo>.lab  n21-a, n21-b, ... n21-j
  gitea.<turma>-<grupo>.lab    n21-a, n21-b, ... n21-j
  mqtt.<turma>-<grupo>.lab     n21-a, n21-b, ... n21-j

Cada subdominio responde uma pagina de confirmacao ("host acessivel").
O portal na raiz lista todos, agrupados por grupo, e faz um auto-teste via
/ping (com CORS), mostrando verde/vermelho para cada host.

Uso:
  python3 gen_test_nginx.py --turma n21 --grupos 10 --ip 192.168.0.102
  cd test-nginx && docker compose up -d
  # nos clientes, aponte o DNS para o IP do servidor (dnsmasq resolve *.lab)
  # abra http://lab/   (portal com o auto-teste)
  # para derrubar:  docker compose down

O stack sobe dois containers:
  - dnsmasq (dockurr/dnsmasq): resolve *.<dominio> -> IP do servidor (wildcard,
    funciona em Windows/Linux/Mac). Clientes so precisam apontar o DNS pra ele.
  - nginx: responde uma pagina de confirmacao em cada subdominio + portal.

Alternativa sem DNS: use o hosts.lab gerado (expandido, um nome por linha).

Variacoes:
  --grupo a,c,e     gera so esses grupos (aceita "a", "n21-a", "p", "n")
  --sem-dns         nao inclui o dnsmasq (so nginx; use o hosts.lab)
  --modo path       usa <dominio>/<turma>-<grupo>/<servico> (rotas por caminho)
                    em vez do padrao <servico>.<turma>-<grupo>.<dominio> (subdominio)

Esquemas de mapeamento (--modo):
  subdominio (padrao):  n8n.n21-a.lab, nodered.n21-a.lab, ...   (um host por servico)
  path:                 lab/n21-a/n8n, lab/n21-a/nodered, ...   (um dominio, varios caminhos)

No modo path tudo fica no MESMO dominio (mesma origem): nao precisa de wildcard e o
hosts.lab tem uma unica linha. No modo subdominio cada servico e um host proprio
(precisa do wildcard do dnsmasq ou de uma linha por host no hosts.lab).

O portal usa Bootstrap: o CSS e baixado para html/ (funciona offline). Se nao
houver internet na geracao, cai para o CDN (ai o cliente precisa de internet).

Obs.: usa a porta 80 por padrao. Se o stack principal estiver no ar, derrube-o
antes (docker compose down na pasta dele) ou use --porta 8080.

Obs. MQTT: no lab real o MQTT e um servico TCP (porta 1883), nao HTTP. Aqui ele
e servido por HTTP apenas para o teste de resolucao de nome + alcance do nginx.
"""
import sys, os, string, argparse, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--turma", default="n21")
ap.add_argument("--grupos", type=int, default=10)
ap.add_argument("--dominio", default="lab",
                help="Dominio base (hosts ficam <servico>.<turma>-<grupo>.<dominio>)")
ap.add_argument("--servicos", default="n8n,nodered,gitea,mqtt",
                help="Lista de servicos separados por virgula")
ap.add_argument("--ip", default="127.0.0.1", help="IP do servidor (usado no hosts.lab)")
ap.add_argument("--porta", type=int, default=80, help="Porta do host para o nginx de teste")
ap.add_argument("--dns1", default="1.1.1.1", help="DNS upstream 1 (para nomes fora do lab)")
ap.add_argument("--dns2", default="1.0.0.1", help="DNS upstream 2")
ap.add_argument("--grupo", default=None,
                help="Gera para grupos especificos (lista por virgula: a,c,e ou n21-a,p,n). Ignora --grupos.")
ap.add_argument("--sem-dns", action="store_true",
                help="Nao inclui o dnsmasq no stack (so nginx; use o hosts.lab).")
ap.add_argument("--modo", choices=["subdominio", "path"], default="subdominio",
                help="Esquema de mapeamento: 'subdominio' (<servico>.<turma>-<grupo>.<dominio>) "
                     "ou 'path' (<dominio>/<turma>-<grupo>/<servico>).")
args = ap.parse_args()

TURMA, N, DOMINIO, IP, PORTA = args.turma, args.grupos, args.dominio, args.ip, args.porta
DNS1, DNS2 = args.dns1, args.dns2
SEM_DNS = args.sem_dns
MODO = args.modo
MODO_PATH = MODO == "path"
SERVICOS = [s.strip() for s in args.servicos.split(",") if s.strip()]
if not SERVICOS:
    sys.exit("Informe ao menos um servico em --servicos.")

prof = f"{TURMA}-p"
notas = f"{TURMA}-n"

if args.grupo:
    # Um ou mais grupos: "a", "a,c,e", "n21-a", "p" (professor), "n" (notas).
    todos = []
    for item in args.grupo.split(","):
        g = item.strip()
        if not g:
            continue
        entidade = g if "-" in g else f"{TURMA}-{g}"
        if entidade not in todos:
            todos.append(entidade)
    if not todos:
        sys.exit("Nenhum grupo valido em --grupo.")
else:
    reservadas = {"p", "n"}
    letras = [c for c in string.ascii_lowercase if c not in reservadas]
    if N > len(letras):
        sys.exit(f"Maximo de {len(letras)} grupos (letras a-z sem 'p' e 'n').")
    grupos = [f"{TURMA}-{letras[i]}" for i in range(N)]
    todos = grupos + [prof, notas]

# Todos os hostnames de teste (servico x entidade), modo subdominio
def hostname(servico, entidade):
    return f"{servico}.{entidade}.{DOMINIO}"


# --- Mapeamento dependente do modo (subdominio vs path) ---
# Cada "alvo" (servico x entidade) precisa de: uma chave estavel (usada no
# data-host do portal), a URL da pagina, a URL do /ping e um rotulo de exibicao.
def alvo_chave(servico, entidade):
    # Chave estavel usada no atributo data-host / data-for do portal.
    if MODO_PATH:
        return f"{entidade}/{servico}"          # ex.: n21-a/n8n
    return hostname(servico, entidade)          # ex.: n8n.n21-a.lab


def alvo_url_pagina(servico, entidade):
    # Link que o portal abre. No modo path usamos URL relativa (mesma origem,
    # carrega automaticamente host:porta atual). No subdominio, host absoluto.
    if MODO_PATH:
        return f"/{entidade}/{servico}/"
    return f"http://{hostname(servico, entidade)}/"


def alvo_url_ping(servico, entidade):
    # Endpoint leve consultado pelo auto-teste.
    if MODO_PATH:
        return f"/{entidade}/{servico}/ping"
    return f"http://{hostname(servico, entidade)}/ping"


def alvo_rotulo(servico, entidade):
    # Texto mostrado no card.
    if MODO_PATH:
        return f"{DOMINIO}/{entidade}/{servico}"
    return hostname(servico, entidade)


# Lista de alvos (contagem identica nos dois modos: servicos x entidades).
hosts = [hostname(s, g) for g in todos for s in SERVICOS]

BASE = "test-nginx"
os.makedirs(f"{BASE}/html", exist_ok=True)


def papel(g):
    if g == notas:
        return "notas"
    if g == prof:
        return "professor"
    return "grupo"


def nome_entidade(g):
    if g == notas:
        return "Painel de Notas"
    if g == prof:
        return "Professor"
    return f"Grupo {g.rsplit('-', 1)[-1].upper()}"


# Nomes de exibicao dos servicos (fallback = titulo do proprio nome)
NOMES_SERVICO = {"n8n": "n8n", "nodered": "Node-RED", "gitea": "Gitea", "mqtt": "MQTT"}
def nome_servico(s):
    return NOMES_SERVICO.get(s, s.capitalize())


# ---------------- docker-compose.yml ----------------
nginx_svc = f"""  nginx-test:
    image: nginx:alpine
    container_name: lab-nginx-test
    restart: unless-stopped
    ports:
      - "{PORTA}:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./html:/usr/share/nginx/html:ro
"""

if SEM_DNS:
    compose = (
        "# Stack de TESTE — apenas nginx (sem dnsmasq). Gerado por gen_test_nginx.py\n"
        "# Sem DNS: use o hosts.lab nos clientes para os nomes resolverem.\n"
        "services:\n"
        + nginx_svc
    )
else:
    dnsmasq_svc = f"""  dnsmasq:
    image: dockurr/dnsmasq
    container_name: lab-dnsmasq
    restart: unless-stopped
    environment:
      DNS1: "{DNS1}"          # upstream para nomes fora do lab
      DNS2: "{DNS2}"
    ports:
      - "53:53/udp"
      - "53:53/tcp"
    cap_add:
      - NET_ADMIN
    volumes:
      - ./dnsmasq.d:/etc/dnsmasq.d:ro

"""
    compose = (
        f"# Stack de TESTE — nginx + dnsmasq (sem os servicos reais). Gerado por gen_test_nginx.py\n"
        f"# dnsmasq resolve *.{DOMINIO} -> {IP} (wildcard, funciona em Windows/Linux/Mac).\n"
        f"# nginx responde uma pagina de confirmacao em cada subdominio.\n"
        "services:\n"
        + dnsmasq_svc
        + nginx_svc
    )
open(f"{BASE}/docker-compose.yml", "w", encoding="utf-8").write(compose)

# ---------------- dnsmasq.d/lab.conf (wildcard) ----------------
if not SEM_DNS:
    os.makedirs(f"{BASE}/dnsmasq.d", exist_ok=True)
    dnsmasq_conf = [
        f"# Resolve o dominio do lab para o IP do servidor. Gerado por gen_test_nginx.py\n",
        f"# Estende a config base do dockurr/dnsmasq (upstream vem de DNS1/DNS2 no compose).\n\n",
        f"# Coringa geral: {DOMINIO}, *.{DOMINIO}, *.<grupo>.{DOMINIO},\n",
        f"#               <servico>.<grupo>.{DOMINIO}  -->  {IP}\n",
        f"address=/{DOMINIO}/{IP}\n\n",
        f"# --- Alternativa por grupo (descomente se quiser granularidade) ---\n",
    ]
    for g in todos:
        dnsmasq_conf.append(f"# address=/{g}.{DOMINIO}/{IP}    # {nome_entidade(g)}\n")
    open(f"{BASE}/dnsmasq.d/lab.conf", "w", encoding="utf-8").write("".join(dnsmasq_conf))

# ---------------- nginx.conf ----------------
# Pagina de confirmacao. No modo subdominio o titulo e a variavel $host do nginx;
# no modo path o titulo (dominio/turma-grupo/servico) e embutido em cada location.
def pagina_html(titulo):
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>OK - {titulo}</title></head>"
        "<body style='font-family:system-ui,-apple-system,sans-serif;background:#071311;"
        "color:#dcf5ec;display:grid;place-items:center;min-height:100vh;margin:0'>"
        "<div style='text-align:center'>"
        "<div style='font-size:64px'>&#9989;</div>"
        f"<h1 style='font-family:ui-monospace,monospace;color:#35e0b0'>{titulo}</h1>"
        "<p>O nginx respondeu. Este host esta <strong>acessivel</strong>.</p>"
        "<p style='color:#6f9a8d;font-size:13px'>(no lab real, aqui abriria o servico correspondente)</p>"
        "</div></body></html>"
    )

n = [
    "worker_processes auto;\n",
    "events { worker_connections 1024; }\n\n",
    "http {\n",
    "    include       /etc/nginx/mime.types;\n",
    "    default_type  application/octet-stream;\n",
    "    sendfile on;\n\n",
]

if MODO_PATH:
    # UM unico server: portal na raiz + uma rota por servico/entidade.
    # Mapeamento: <dominio>/<turma>-<grupo>/<servico>
    n += [
        "    # ---- Modo PATH: um dominio, rotas por caminho ----\n",
        "    server {\n",
        "        listen 80 default_server;\n",
        f"        server_name {DOMINIO};\n",
        "        root /usr/share/nginx/html;\n",
        "        index index.html;\n\n",
        "        # portal + assets estaticos (bootstrap.min.css etc.)\n",
        "        location / { }\n",
    ]
    for g in todos:
        n.append(f"\n        # ===== {nome_entidade(g)} ({g}) =====\n")
        for s in SERVICOS:
            base_rota = f"/{g}/{s}"
            pagina = pagina_html(f"{DOMINIO}/{g}/{s}")
            n += [
                f"        # {DOMINIO}{base_rota}/\n",
                "        # endpoint leve para o auto-teste do portal (mesma origem; CORS por garantia)\n",
                f"        location = {base_rota}/ping {{\n",
                "            add_header Access-Control-Allow-Origin *;\n",
                "            default_type text/plain;\n",
                f'            return 200 "{g}/{s} ok\\n";\n',
                "        }\n",
                f"        location {base_rota}/ {{\n",
                "            default_type text/html;\n",
                f'            return 200 "{pagina}";\n',
                "        }\n",
            ]
    n += ["    }\n"]
else:
    # Modo SUBDOMINIO: um server por host <servico>.<turma>-<grupo>.<dominio>.
    pagina = pagina_html("$host")  # nginx substitui $host em cada requisicao
    n += [
        "    # ---- Portal (raiz do dominio) ----\n",
        "    server {\n",
        "        listen 80 default_server;\n",
        f"        server_name {DOMINIO};\n",
        "        root /usr/share/nginx/html;\n",
        "        index index.html;\n",
        "        location / { }\n",
        "    }\n",
    ]
    for g in todos:
        n.append(f"\n    # ===== {nome_entidade(g)} ({g}) =====\n")
        for s in SERVICOS:
            host = hostname(s, g)
            n += [
                f"    # {host}\n",
                "    server {\n",
                "        listen 80;\n",
                f"        server_name {host};\n",
                "        # endpoint leve para o auto-teste do portal (com CORS)\n",
                "        location = /ping {\n",
                "            add_header Access-Control-Allow-Origin *;\n",
                "            default_type text/plain;\n",
                '            return 200 "$host ok\\n";\n',
                "        }\n",
                "        location / {\n",
                "            default_type text/html;\n",
                f'            return 200 "{pagina}";\n',
                "        }\n",
                "    }\n",
            ]
n += ["}\n"]
open(f"{BASE}/nginx.conf", "w", encoding="utf-8").write("".join(n))

# ---------------- html/index.html (portal Bootstrap com auto-teste) ----------------
# Baixa o Bootstrap para servir localmente (lab offline). Fallback: CDN.
BOOTSTRAP_VER = "5.3.3"
BOOTSTRAP_CDN = f"https://cdn.jsdelivr.net/npm/bootstrap@{BOOTSTRAP_VER}/dist/css/bootstrap.min.css"
bootstrap_href = BOOTSTRAP_CDN
try:
    with urllib.request.urlopen(BOOTSTRAP_CDN, timeout=15) as r:
        css_bytes = r.read()
    with open(f"{BASE}/html/bootstrap.min.css", "wb") as f:
        f.write(css_bytes)
    bootstrap_href = "bootstrap.min.css"  # servido pelo proprio nginx (offline-ok)
    bootstrap_msg = f"Bootstrap {BOOTSTRAP_VER} baixado em html/ (funciona offline)."
except Exception as e:
    bootstrap_msg = f"Nao baixou o Bootstrap (usando CDN, requer internet no cliente): {e}"

# Cada alvo vira ["chave", "url_do_ping"] para o auto-teste do portal.
targets_js = ",".join(
    f'["{alvo_chave(s, g)}","{alvo_url_ping(s, g)}"]'
    for g in todos for s in SERVICOS
)

# Cada entidade vira uma secao Bootstrap (heading + grid de cards de servico)
secoes = []
for g in todos:
    if g == prof:
        badge = ' <span class="badge text-bg-warning">professor</span>'
    elif g == notas:
        badge = ' <span class="badge text-bg-info">notas</span>'
    else:
        badge = ""
    cards = []
    for s in SERVICOS:
        chave = alvo_chave(s, g)
        url_pagina = alvo_url_pagina(s, g)
        rotulo = alvo_rotulo(s, g)
        cards.append(
            f'          <div class="col" data-host="{chave}">\n'
            f'            <div class="card h-100 border-secondary-subtle status-card">\n'
            f'              <div class="card-body d-flex flex-column">\n'
            f'                <div class="d-flex justify-content-between align-items-start mb-2">\n'
            f'                  <span class="fw-semibold fs-5">{nome_servico(s)}</span>\n'
            f'                  <span class="badge rounded-pill text-bg-secondary status" data-for="{chave}">&hellip;</span>\n'
            f'                </div>\n'
            f'                <a href="{url_pagina}" target="_blank" rel="noopener"\n'
            f'                   class="stretched-link text-decoration-none font-monospace small text-body-secondary">{rotulo}</a>\n'
            f'              </div>\n'
            f'            </div>\n'
            f'          </div>\n'
        )
    secoes.append(
        f'      <section class="mb-4">\n'
        f'        <div class="d-flex align-items-baseline gap-2 border-bottom border-secondary-subtle pb-2 mb-3">\n'
        f'          <h2 class="h5 mb-0">{nome_entidade(g)}</h2>{badge}\n'
        f'          <span class="ms-auto text-body-secondary font-monospace small">{g}</span>\n'
        f'        </div>\n'
        f'        <div class="row row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-lg-4 g-3">\n'
        f'{"".join(cards)}'
        f'        </div>\n'
        f'      </section>\n'
    )

html = """<!DOCTYPE html>
<html lang="pt-BR" data-bs-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Teste de rede &middot; __DOMINIO__</title>
<link href="__BOOTSTRAP__" rel="stylesheet">
<style>
  body{--bs-body-bg:#071311;--bs-body-color:#dcf5ec;}
  .eyebrow{letter-spacing:.22em;text-transform:uppercase;color:#35e0b0;
    font-size:.75rem;font-family:var(--bs-font-monospace)}
  .status-card{transition:transform .15s ease}
  .status-card:hover{transform:translateY(-2px)}
</style>
</head>
<body>
  <div class="container py-5" style="max-width:1100px">
    <p class="eyebrow mb-1">teste de rede &middot; nginx + dns</p>
    <h1 class="fw-semibold mb-2">Diagnostico de __UNIDADE__</h1>
    <p class="text-body-secondary" style="max-width:64ch">Cada carto testa
      <code>__PING_EXEMPLO__</code> automaticamente. Verde = resolveu e o nginx
      respondeu. Vermelho = falhou (nome nao resolve, porta bloqueada, ou nginx fora).
      Clique num carto para abrir a pagina de confirmacao daquele alvo.</p>
    <div id="summary" class="alert alert-secondary py-2 px-3 d-inline-block font-monospace small">
      testando __TOTAL__ alvos&hellip;</div>
    <main class="mt-3">
__SECOES__    </main>
    <footer class="mt-4 pt-3 border-top border-secondary-subtle text-body-secondary font-monospace small">
      dominio: __DOMINIO__ &middot; modo: __MODO__ &middot; __NSERV__ servicos x __NENT__ entidades = __TOTAL__ __UNIDADE__
      &middot; este stack nao sobe os servicos reais<br>
      obs.: mqtt no lab real e TCP (1883); aqui e servido por HTTP so para o teste de resolucao
    </footer>
  </div>
<script>
  // Cada alvo e um par [chave, urlDoPing]. A chave casa com data-host/data-for.
  const targets=[__TARGETS_JS__];
  let ok=0, done=0;
  function finish(){
    const el=document.getElementById('summary');
    el.textContent=ok+" de "+targets.length+" alvos acessiveis";
    el.classList.remove('alert-secondary');
    el.classList.add(ok===targets.length?'alert-success':(ok===0?'alert-danger':'alert-warning'));
  }
  targets.forEach(function(t){
    const key=t[0], ping=t[1];
    fetch(ping,{cache:"no-store"})
      .then(function(r){return r.ok?r.text():Promise.reject();})
      .then(function(){mark(key,true);})
      .catch(function(){mark(key,false);});
  });
  function mark(key,pass){
    const col=document.querySelector('[data-host="'+key+'"]');
    const card=col?col.querySelector('.card'):null;
    const st=document.querySelector('[data-for="'+key+'"]');
    if(card){card.classList.remove('border-secondary-subtle');
      card.classList.add('border-2',pass?'border-success':'border-danger');}
    if(st){st.classList.remove('text-bg-secondary');
      st.classList.add(pass?'text-bg-success':'text-bg-danger');
      st.textContent=pass?'\\u2713 ok':'\\u2717 falhou';}
    if(pass)ok++; done++; if(done===targets.length)finish();
  }
</script>
</body>
</html>
"""
unidade = "caminhos" if MODO_PATH else "subdominios"
ping_exemplo = (f"http://{DOMINIO}/<turma>-<grupo>/<servico>/ping"
                if MODO_PATH else "http://<servico>.<turma>-<grupo>/ping")
html = (html.replace("__SECOES__", "".join(secoes))
            .replace("__TARGETS_JS__", targets_js)
            .replace("__BOOTSTRAP__", bootstrap_href)
            .replace("__PING_EXEMPLO__", ping_exemplo)
            .replace("__UNIDADE__", unidade)
            .replace("__MODO__", MODO)
            .replace("__DOMINIO__", DOMINIO)
            .replace("__NSERV__", str(len(SERVICOS)))
            .replace("__NENT__", str(len(todos)))
            .replace("__TOTAL__", str(len(hosts))))
open(f"{BASE}/html/index.html", "w", encoding="utf-8").write(html)

# ---------------- hosts.lab (FALLBACK sem DNS, expandido) ----------------
# Use isto SO se o cliente nao puder apontar o DNS para o servidor (dnsmasq).
# Arquivos hosts NAO aceitam wildcard em nenhum SO, entao cada host vai listado.
with open(f"{BASE}/hosts.lab", "w", encoding="utf-8") as f:
    f.write("# FALLBACK sem DNS. Cole no arquivo hosts do cliente:\n")
    f.write("#   Windows: C:\\Windows\\System32\\drivers\\etc\\hosts\n")
    f.write("#   Linux/Mac: /etc/hosts\n")
    f.write(f"# Preferivel: usar o dnsmasq do stack (wildcard). Troque {IP} se o IP mudar.\n\n")
    if MODO_PATH:
        # Modo path: tudo no mesmo dominio -> uma unica linha basta.
        f.write(f"# Modo path: todos os servicos ficam em {DOMINIO}/<turma>-<grupo>/<servico>\n")
        f.write(f"{IP}\t{DOMINIO}\t# dominio unico (portal + todas as rotas)\n")
    else:
        # Modo subdominio: hosts NAO aceitam wildcard -> uma linha por host.
        f.write(f"{IP}\t{DOMINIO}\t# portal\n")
        for g in todos:
            f.write(f"\n# {nome_entidade(g)} ({g})\n")
            for s in SERVICOS:
                f.write(f"{IP}\t{hostname(s, g)}\n")

unidade_cli = "caminhos" if MODO_PATH else "subdominios"
n_hosts_file = 1 if MODO_PATH else len(hosts)
alvo = (f"grupos: {', '.join(todos)}" if args.grupo else f"{len(todos)} entidades")
print(f"OK: stack de teste gerado em ./{BASE}/  ({alvo})  |  modo: {MODO}")
if SEM_DNS:
    print(f"  - {BASE}/docker-compose.yml  (apenas nginx, porta {PORTA})")
else:
    print(f"  - {BASE}/docker-compose.yml  (dnsmasq + nginx, porta {PORTA})")
    if MODO_PATH:
        print(f"  - {BASE}/dnsmasq.d/lab.conf   ({DOMINIO} -> {IP}; wildcard cobre tudo)")
    else:
        print(f"  - {BASE}/dnsmasq.d/lab.conf   (wildcard: *.{DOMINIO} -> {IP})")
print(f"  - {BASE}/nginx.conf          (portal + {len(hosts)} {unidade_cli} de teste)")
print(f"  - {BASE}/html/index.html     (auto-teste verde/vermelho, agrupado)")
if SEM_DNS:
    print(f"  - {BASE}/hosts.lab           (necessario p/ resolver: {n_hosts_file} linha(s))")
else:
    print(f"  - {BASE}/hosts.lab           (fallback sem DNS: {n_hosts_file} linha(s))")
if MODO_PATH:
    print(f"\nMapeamento: {DOMINIO}/<turma>-<grupo>/<servico>  (ex.: {DOMINIO}/{todos[0]}/{SERVICOS[0]})")
else:
    print(f"\nMapeamento: <servico>.<turma>-<grupo>.{DOMINIO}  (ex.: {SERVICOS[0]}.{todos[0]}.{DOMINIO})")
print(f"Servicos: {', '.join(SERVICOS)}  |  Entidades: {len(todos)} ({', '.join(todos)})")
print(f"Bootstrap: {bootstrap_msg}")
print("\nComo usar:")
passo = 1
if PORTA == 80:
    print(f"  {passo}) Se o stack principal estiver no ar, derrube-o antes (libera a porta 80).")
    passo += 1
if not SEM_DNS:
    print(f"  {passo}) Libere a porta 53 no host (no Linux, systemd-resolved costuma ocupa-la:")
    print(f"       sudo sed -i 's/^#\\?DNSStubListener=.*/DNSStubListener=no/' /etc/systemd/resolved.conf")
    print(f"       && sudo systemctl restart systemd-resolved).")
    passo += 1
print(f"  {passo}) cd {BASE} && docker compose up -d")
passo += 1
if SEM_DNS:
    print(f"  {passo}) Nos CLIENTES, cole o {BASE}/hosts.lab no arquivo hosts:")
    print(f"       Windows: C:\\Windows\\System32\\drivers\\etc\\hosts")
    print(f"       Linux/Mac: /etc/hosts")
else:
    print(f"  {passo}) Nos CLIENTES, aponte o DNS para {IP}:")
    print(f"       Windows: Config. do adaptador > IPv4 > DNS preferencial = {IP}")
    print(f"       Linux/Mac: nameserver {IP} (NetworkManager ou /etc/resolv.conf)")
    print(f"       (sem trocar DNS? use o {BASE}/hosts.lab como fallback)")
passo += 1
sufixo = "" if PORTA == 80 else f":{PORTA}"
print(f"  {passo}) Abra http://{DOMINIO}{sufixo}/  e veja o auto-teste.")
passo += 1
print(f"  {passo}) Para derrubar: docker compose down")
