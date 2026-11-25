#!/bin/bash
# Cria o template de um lab no GitHub, já com o ferramentas/conferir.py daquele lab.
#
# Estrutura esperada:
#   scripts/create-lab-pio-template.sh
#   scripts/gerar_conferir.py
#   labs-docs/LAB01.mdx ... LAB12.mdx
#
# Uso (de qualquer pasta):
#   scripts/create-lab-pio-template.sh 9               cria o lab09-template
#   scripts/create-lab-pio-template.sh 9 --atualizar   só (re)injeta o conferir.py num template que já existe
#
# Variáveis opcionais:
#   ROTEIROS=pasta-dos-.mdx   (padrão: ../labs-docs, a partir da pasta scripts)
#   GERADOR=gerar_conferir.py (padrão: na pasta scripts)
set -euo pipefail

ORG="ELT85B-N21-2026-2"
NLAB="${1:-9}"
MODO="${2:-criar}"
LAB=$(printf "%02d" "$((10#$NLAB))")
REPO="lab${LAB}-template"

BOARD="esp32dev"

DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROTEIROS="${ROTEIROS:-$(cd "$DIR_SCRIPT/.." && pwd)/labs-docs}"
GERADOR="${GERADOR:-$DIR_SCRIPT/gerar_conferir.py}"
MDX="$ROTEIROS/LAB${LAB}.mdx"

# Diretório temporário de trabalho (removido ao final)
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# 0) Gera o conferir.py ANTES de mexer no GitHub: um roteiro com CommitPoint errado
#    para o script aqui, sem deixar um repositório criado pela metade.
[ -f "$GERADOR" ] || { echo "gerador não encontrado: $GERADOR" >&2; exit 1; }
[ -f "$MDX" ]     || { echo "roteiro não encontrado: $MDX (ajuste ROTEIROS=...)" >&2; exit 1; }
python3 "$GERADOR" "$MDX" -o "$WORKDIR/conferir.py"

injetar_conferir() {
  mkdir -p ferramentas
  cp "$WORKDIR/conferir.py" ferramentas/conferir.py
}

# --atualizar: template já existe; troca só o ferramentas/conferir.py
if [ "$MODO" = "--atualizar" ]; then
  cd "$WORKDIR"
  gh repo clone "$ORG/$REPO" "$REPO" -- --quiet
  cd "$REPO"
  injetar_conferir
  git add ferramentas/conferir.py
  if git diff --cached --quiet; then
    echo "conferir.py do $ORG/$REPO já está atualizado."
  else
    git commit -m "Atualiza ferramentas/conferir.py a partir do LAB${LAB}.mdx"
    git push origin HEAD
    echo "conferir.py atualizado em $ORG/$REPO."
    echo "Atenção: repositórios de grupo já criados a partir do template não recebem a mudança."
  fi
  exit 0
fi

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

# 5) Verificador de pastas e arquivos do lab (py ferramentas\conferir.py)
injetar_conferir

# 6) Commit e push
git add -A
git commit -m "Inicializa projeto PlatformIO (ESP32/Arduino), simulação Wokwi e conferir.py"
git push origin HEAD

# 7) Marca o repositório como template
gh api --method PATCH \
  "repos/$ORG/$REPO" \
  -F is_template=true

echo "Template $ORG/$REPO criado com sucesso (com ferramentas/conferir.py do LAB${LAB})."
