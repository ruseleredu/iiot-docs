#!/usr/bin/env python3
"""Gera um stack MINIMO (apenas nginx) para testar se os subdominios do
hosts.lab resolvem e chegam ao nginx — SEM subir as instancias n8n.

Cada subdominio responde uma pagina de confirmacao ("host acessivel").
O portal na raiz lista todos e faz um auto-teste via /ping (com CORS),
mostrando verde/vermelho para cada host.

Uso:
  python3 gen_test_nginx.py --turma n21 --grupos 10 --dominio n8n.lab --ip 192.168.0.102
  cd test-nginx && docker compose up -d
  # abra http://<dominio>/   (ex.: http://n8n.lab/)
  # para derrubar:  docker compose down

Obs.: usa a porta 80 por padrao. Se o stack principal estiver no ar, derrube-o
antes (docker compose down na pasta dele) ou use --porta 8080.
"""
import sys, os, string, argparse

ap = argparse.ArgumentParser()
ap.add_argument("--turma", default="n21")
ap.add_argument("--grupos", type=int, default=10)
ap.add_argument("--dominio", default="n8n.lab")
ap.add_argument("--ip", default="127.0.0.1", help="IP do servidor (usado no hosts.lab)")
ap.add_argument("--porta", type=int, default=80, help="Porta do host para o nginx de teste")
args = ap.parse_args()

TURMA, N, DOMINIO, IP, PORTA = args.turma, args.grupos, args.dominio, args.ip, args.porta

reservadas = {"p", "n"}
letras = [c for c in string.ascii_lowercase if c not in reservadas]
if N > len(letras):
    sys.exit(f"Maximo de {len(letras)} grupos (letras a-z sem 'p' e 'n').")

grupos = [f"{TURMA}-{letras[i]}" for i in range(N)]
prof = f"{TURMA}-p"
notas = f"{TURMA}-n"
todos = grupos + [prof, notas]

BASE = "test-nginx"
os.makedirs(f"{BASE}/html", exist_ok=True)


def papel(g):
    if g == notas:
        return "notas"
    if g == prof:
        return "professor"
    return "grupo"


# ---------------- docker-compose.yml ----------------
compose = f"""# Stack de TESTE — apenas nginx (sem n8n). Gerado por gen_test_nginx.py
# Testa se os subdominios do hosts.lab resolvem e chegam ao nginx.
services:
  nginx-test:
    image: nginx:alpine
    container_name: lab-nginx-test
    restart: unless-stopped
    ports:
      - "{PORTA}:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./html:/usr/share/nginx/html:ro
"""
open(f"{BASE}/docker-compose.yml", "w", encoding="utf-8").write(compose)

# ---------------- nginx.conf ----------------
# Pagina de confirmacao servida por cada subdominio (usa a variavel $host do nginx).
pagina = (
    "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    "<title>OK - $host</title></head>"
    "<body style='font-family:system-ui,-apple-system,sans-serif;background:#071311;"
    "color:#dcf5ec;display:grid;place-items:center;min-height:100vh;margin:0'>"
    "<div style='text-align:center'>"
    "<div style='font-size:64px'>&#9989;</div>"
    "<h1 style='font-family:ui-monospace,monospace;color:#35e0b0'>$host</h1>"
    "<p>O nginx respondeu. Este host esta <strong>acessivel</strong>.</p>"
    "<p style='color:#6f9a8d;font-size:13px'>(no lab real, aqui abriria o editor n8n)</p>"
    "</div></body></html>"
)

n = [
    "worker_processes auto;\n",
    "events { worker_connections 1024; }\n\n",
    "http {\n",
    "    include       /etc/nginx/mime.types;\n",
    "    default_type  application/octet-stream;\n",
    "    sendfile on;\n\n",
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
    n += [
        f"\n    # {g} ({papel(g)})\n",
        "    server {\n",
        "        listen 80;\n",
        f"        server_name {g}.{DOMINIO};\n",
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

# ---------------- html/index.html (portal com auto-teste) ----------------
hosts_js = ",".join(f'"{g}.{DOMINIO}"' for g in todos)
cards = []
for g in todos:
    host = f"{g}.{DOMINIO}"
    if g == notas:
        nome, cls = "Painel de Notas", "card notas"
    elif g == prof:
        nome, cls = "Professor", "card prof"
    else:
        nome, cls = f"Grupo {g.rsplit('-',1)[-1].upper()}", "card"
    cards.append(
        f'      <a class="{cls}" href="http://{host}/" target="_blank" data-host="{host}">\n'
        f'        <span class="status" data-for="{host}">&#8230;</span>\n'
        f'        <span class="name">{nome}</span>\n'
        f'        <span class="host">{host}</span>\n'
        f'      </a>\n'
    )

html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Teste de rede &middot; __DOMINIO__</title>
<style>
  :root{--bg:#071311;--panel:#0d201c;--line:#17332c;--ink:#dcf5ec;--muted:#6f9a8d;
    --ok:#35e0b0;--fail:#f2545b;--gold:#e0b23a;--purple:#a855f7;
    --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--ink);font-family:var(--sans);min-height:100vh;padding:6vh 5vw}
  .wrap{max-width:1000px;margin:0 auto}
  .eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:var(--ok)}
  h1{font-size:clamp(26px,5vw,40px);font-weight:650;letter-spacing:-.02em;margin:12px 0 8px}
  .sub{color:var(--muted);font-size:15px;line-height:1.5;max-width:62ch}
  .summary{font-family:var(--mono);font-size:13px;color:var(--muted);margin:18px 0 26px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
  .card{position:relative;display:flex;flex-direction:column;gap:4px;background:var(--panel);
    border:1px solid var(--line);border-radius:10px;padding:16px;text-decoration:none;color:var(--ink);
    transition:border-color .15s ease,transform .15s ease}
  .card:hover{transform:translateY(-2px)}
  .card.prof{border-color:var(--gold)} .card.notas{border-color:var(--purple)}
  .status{font-family:var(--mono);font-size:20px;line-height:1}
  .name{font-size:18px;font-weight:600}
  .host{font-family:var(--mono);font-size:12px;color:var(--muted)}
  .card.pass{border-color:var(--ok)} .card.fail{border-color:var(--fail)}
  .card.pass .status{color:var(--ok)} .card.fail .status{color:var(--fail)}
  .foot{margin-top:34px;padding-top:18px;border-top:1px solid var(--line);
    font-family:var(--mono);font-size:12px;color:var(--muted)}
</style>
</head>
<body>
  <div class="wrap">
    <div class="eyebrow">teste de rede &middot; apenas nginx</div>
    <h1>Diagnostico de subdominios</h1>
    <p class="sub">Cada carto testa <code>http://host/ping</code> automaticamente. Verde = o nome
    resolveu e o nginx respondeu. Vermelho = falhou (nome nao resolve, porta bloqueada, ou nginx fora).
    Clique em um carto para abrir a pagina de confirmacao daquele host.</p>
    <div class="summary" id="summary">testando __TOTAL__ hosts&hellip;</div>
    <main class="grid">
__CARDS__    </main>
    <footer class="foot">dominio: __DOMINIO__ &middot; este stack nao sobe o n8n</footer>
  </div>
<script>
  const hosts=[__HOSTS_JS__];
  let ok=0, done=0;
  function finish(){document.getElementById('summary').textContent=
    ok+" de "+hosts.length+" hosts acessiveis";}
  hosts.forEach(function(h){
    fetch("http://"+h+"/ping",{cache:"no-store"})
      .then(function(r){return r.ok?r.text():Promise.reject();})
      .then(function(){mark(h,true);})
      .catch(function(){mark(h,false);});
  });
  function mark(h,pass){
    const card=document.querySelector('[data-host="'+h+'"]');
    const st=document.querySelector('[data-for="'+h+'"]');
    if(card){card.classList.add(pass?"pass":"fail");}
    if(st){st.innerHTML=pass?"&#10003;":"&#10007;";}
    if(pass)ok++; done++; if(done===hosts.length)finish();
  }
</script>
</body>
</html>
"""
html = (html.replace("__CARDS__", "".join(cards))
            .replace("__HOSTS_JS__", hosts_js)
            .replace("__DOMINIO__", DOMINIO)
            .replace("__TOTAL__", str(len(todos))))
open(f"{BASE}/html/index.html", "w", encoding="utf-8").write(html)

# ---------------- hosts.lab (mesmo do stack real) ----------------
with open(f"{BASE}/hosts.lab", "w", encoding="utf-8") as f:
    f.write(f"# Cole no /etc/hosts dos clientes. Troque {IP} pelo IP do servidor se mudar.\n")
    f.write(f"# Wildcard (dnsmasq):  address=/{DOMINIO}/{IP}\n\n")
    f.write(f"{IP}\t{DOMINIO}\n")
    for g in todos:
        f.write(f"{IP}\t{g}.{DOMINIO}\n")

print(f"OK: stack de teste gerado em ./{BASE}/")
print(f"  - {BASE}/docker-compose.yml  (apenas nginx, porta {PORTA})")
print(f"  - {BASE}/nginx.conf          (portal + {len(todos)} subdominios de teste)")
print(f"  - {BASE}/html/index.html     (auto-teste verde/vermelho)")
print(f"  - {BASE}/hosts.lab           ({len(todos)+1} nomes)")
print("\nComo usar:")
if PORTA == 80:
    print("  1) Se o stack principal estiver no ar, derrube-o antes (libera a porta 80).")
print(f"  2) cd {BASE} && docker compose up -d")
sufixo = "" if PORTA == 80 else f":{PORTA}"
print(f"  3) Abra http://{DOMINIO}{sufixo}/  e veja o auto-teste.")
print(f"  4) Para derrubar: docker compose down")
