#!/usr/bin/env python3
"""
Gera flows.json iniciais para cada grupo da turma.
Uso:
  python3 gen_flows.py --turma n21 --grupos 10
"""

import os, json, argparse

ap = argparse.ArgumentParser()
ap.add_argument("--turma", default="n21", help="Identificador da turma (ex.: n21)")
ap.add_argument("--grupos", type=int, default=10, help="Quantidade de grupos de alunos")
args = ap.parse_args()

TURMA = args.turma
N = args.grupos

# Letras reservadas
LETRA_PROF = "p"
LETRA_NOTAS = "n"
reservadas = {LETRA_PROF, LETRA_NOTAS}
letras = [c for c in "abcdefghijklmnopqrstuvwxyz" if c not in reservadas]

if N > len(letras):
    raise SystemExit(f"Máximo de {len(letras)} grupos (letras a-z sem 'p' e 'n').")

grupos_alunos = [f"{TURMA}-{letras[i]}" for i in range(N)]
prof = f"{TURMA}-{LETRA_PROF}"
notas_service = f"{TURMA}-{LETRA_NOTAS}"
todos_servicos = grupos_alunos + [prof, notas_service]

# Flow inicial de exemplo
def flow_inicial(grupo):
    return [
        {
            "id": "tab1",
            "type": "tab",
            "label": "Exemplo MQTT",
            "disabled": False,
            "info": f"Flow inicial para o grupo {grupo}"
        },
        {
            "id": "mqtt_in",
            "type": "mqtt in",
            "z": "tab1",
            "name": "Receber mensagens",
            "topic": f"{grupo}/#",
            "broker": "broker",
            "x": 200,
            "y": 200,
            "wires": [["debug1"]]
        },
        {
            "id": "debug1",
            "type": "debug",
            "z": "tab1",
            "name": "Console",
            "active": True,
            "tosidebar": True,
            "x": 400,
            "y": 200,
            "wires": []
        }
    ]

# Gera flows.json para cada serviço
for g in todos_servicos:
    os.makedirs(f"data/{g}", exist_ok=True)
    with open(f"data/{g}/flows.json", "w", encoding="utf-8") as f:
        json.dump(flow_inicial(g), f, indent=2)
    print(f"📡 Flow inicial criado em data/{g}/flows.json")

print("\n✅ Flows iniciais gerados para todos os grupos, professor e painel de notas.")
