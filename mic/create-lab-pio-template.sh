#!/bin/bash
set -euo pipefail

ORG="ELT73A-S22-2026-2"
NLAB=6
LAB=$(printf "%02d" "$NLAB")
REPO="lab${LAB}-template"

BOARD="esp32dev"

# Diretório temporário de trabalho (removido ao final)
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# 1) Cria o repositório (com README) e clona localmente
cd "$WORKDIR"
gh repo create "$ORG/$REPO" \
  --private \
  --description "Template for LAB$LAB" \
  --add-readme \
  --clone

cd "$REPO"

# 2) Inicializa o projeto PlatformIO
pio project init \
  -b "$BOARD" \
  -O "framework=arduino" \
  -O "monitor_speed=115200" \
  --ide vscode \
  --sample-code

# 3) Inicializa a simulação Wokwi
#    'wokwi-cli init' é interativo; em script, geramos os mesmos arquivos
#    diretamente, apontando para o firmware gerado pelo PlatformIO.
#    Para usar o modo interativo, troque o bloco abaixo por:  wokwi-cli init
cat > wokwi.toml <<EOF
[wokwi]
version = 1
firmware = '.pio/build/${BOARD}/firmware.bin'
elf = '.pio/build/${BOARD}/firmware.elf'
EOF

cat > diagram.json <<'EOF'
{
  "version": 1,
  "author": "ELT73A",
  "editor": "wokwi",
  "parts": [
    { "type": "board-esp32-devkit-c-v4", "id": "esp", "top": 0, "left": 0, "attrs": {} }
  ],
  "connections": [
    [ "esp:TX", "$serialMonitor:RX", "", [] ],
    [ "esp:RX", "$serialMonitor:TX", "", [] ]
  ],
  "dependencies": {}
}
EOF

# 4) Configurações do VS Code
mkdir -p .vscode
cat > .vscode/settings.json <<'EOF'
{
  "terminal.integrated.defaultProfile.windows": "Command Prompt"
}
EOF

# 5) Commit e push
git add -A
git commit -m "Inicializa projeto PlatformIO (ESP32/Arduino) e simulação Wokwi"
git push origin HEAD

# 6) Marca o repositório como template
gh api --method PATCH \
  "repos/$ORG/$REPO" \
  -F is_template=true

echo "Template $ORG/$REPO criado com sucesso."
