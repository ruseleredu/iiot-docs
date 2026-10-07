#!/usr/bin/env python3
"""
Professor: gera um docker-compose com UMA câmara simulada por grupo, ligada à rede do
LAB IoT criado por gen_iot_scada_portal.py (mesmo --lab e --grupos).

    py gerar_compose_lab.py --lab lab05 --grupos 10
    docker compose -f docker-compose.camaras.yml up -d --build

Cada grupo ganha o serviço "<lab>-<letra>-camara" (ex.: lab05-a-camara) na rede
"<lab>_labnet", publicando em <lab>-<letra>/camara/... no broker "mosquitto".
Node-RED e FUXA do grupo acessam Modbus/S7/OPC-UA por esse nome; nenhuma porta é
aberta no servidor (não há conflito entre grupos).
"""
import argparse
import re
import string

ap = argparse.ArgumentParser(description="Compose das câmaras simuladas do LAB IoT")
ap.add_argument("--lab", default="lab05")
ap.add_argument("--grupos", type=int, default=10)
ap.add_argument("--rede", default=None, help="rede Docker do lab (padrão: <lab>_labnet)")
ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--professor", action="store_true", help="inclui também a câmara do professor (<lab>-p)")
ap.add_argument("--saida", default="docker-compose.camaras.yml")
a = ap.parse_args()

lab = a.lab.lower()
if not re.fullmatch(r"[a-z][a-z0-9]{1,20}", lab):
    raise SystemExit("--lab deve ser igual ao do gen_iot_scada_portal.py (ex.: lab05)")
letras = [c for c in string.ascii_lowercase if c not in ("p", "n")]   # 'p' e 'n' reservadas
if not 1 <= a.grupos <= len(letras):
    raise SystemExit(f"--grupos entre 1 e {len(letras)}")
grupos = [f"{lab}-{letras[i]}" for i in range(a.grupos)] + ([f"{lab}-p"] if a.professor else [])
rede = a.rede or f"{lab}_labnet"

y = [f"# Câmaras simuladas do {lab.upper()} — gerado por gerar_compose_lab.py",
     f"# Subir:  docker compose -f {a.saida} up -d --build   (depois do LAB IoT estar no ar)",
     f"name: {lab}-camaras", "", "services:"]
for g in grupos:
    y += [f"  {g}-camara:",
          "    build: .",
          "    image: camara-sim:local",
          f"    container_name: {g}-camara",
          f"    hostname: {g}-camara",
          "    restart: unless-stopped",
          "    environment:",
          "      - TZ=America/Sao_Paulo",
          f"      - GRUPO={g}",
          "      - MQTT_HOST=mosquitto",
          f"      - SIM_SPEED={a.speed:g}",
          "    networks:",
          "      - labnet",
          ""]
y += ["networks:", "  labnet:", f"    name: {rede}", "    external: true", ""]
with open(a.saida, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(y))
print(f"✅ {a.saida}: {len(grupos)} câmaras na rede {rede}")
for g in grupos:
    print(f"   {g}-camara   MQTT {g}/camara/#")
