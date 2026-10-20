#!/bin/bash
# Propaga para os repositórios dos grupos as alterações feitas no template
# depois que eles foram criados.
#
# Uso:
#   ./sync-lab-from-template.sh <commit-base> [commit-final]
#
#   <commit-base>   último commit do template ANTES das alterações
#                   (o estado que os grupos receberam)
#   [commit-final]  até onde aplicar (padrão: HEAD do template)
#
# Variáveis opcionais:
#   USE_PR=1                 abre um Pull Request em vez de dar push direto na main
#   GROUP_LIST="C F"         processa só alguns grupos (útil para refazer os que falharam)
set -euo pipefail
shopt -s nullglob

ORG="ELT73A-S22-2026-2"
GROUP_LIST="${GROUP_LIST:-A B C D E F G H I J K L M P N}"
NLAB=5
LAB=$(printf "lab%02d" "$NLAB")
TEMPLATE="$ORG/${LAB}-template"

BASE="${1:?Uso: $0 <commit-base> [commit-final]}"
FINAL="${2:-HEAD}"
USE_PR="${USE_PR:-0}"
BRANCH="atualiza-template"

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# 1) Gera os patches com as alterações do template
echo "Gerando patches de $TEMPLATE ($BASE..$FINAL)"
gh repo clone "$TEMPLATE" "$WORKDIR/template" -- --quiet
git -C "$WORKDIR/template" format-patch "$BASE..$FINAL" -o "$WORKDIR/patches" >/dev/null

PATCHES=("$WORKDIR"/patches/*.patch)
if [ ${#PATCHES[@]} -eq 0 ]; then
  echo "Nenhuma alteração entre $BASE e $FINAL. Nada a fazer."
  exit 0
fi
echo "${#PATCHES[@]} commit(s) a aplicar:"
git -C "$WORKDIR/template" log --oneline "$BASE..$FINAL"
echo ""

FAILED=()

# 2) Aplica em cada repositório de grupo
for letter in $GROUP_LIST; do
  GROUP_LOWER=$(echo "$letter" | tr '[:upper:]' '[:lower:]')
  REPO="${LAB}-grupo-${GROUP_LOWER}"
  DIR="$WORKDIR/$REPO"

  echo "→ $REPO"

  if ! gh repo clone "$ORG/$REPO" "$DIR" -- --quiet 2>/dev/null; then
    echo "  ✗ falha ao clonar"
    FAILED+=("$letter")
    continue
  fi

  # Traz os objetos do template para que o 'git am -3' consiga montar
  # o ancestral comum (os históricos não são relacionados)
  git -C "$DIR" fetch -q "$WORKDIR/template"

  if [ "$USE_PR" = "1" ]; then
    git -C "$DIR" switch -q -c "$BRANCH"
  fi

  if git -C "$DIR" am -3 --quiet "${PATCHES[@]}"; then
    if [ "$USE_PR" = "1" ]; then
      git -C "$DIR" push -q -u origin "$BRANCH"
      gh pr create -R "$ORG/$REPO" \
        --head "$BRANCH" \
        --title "Atualização do template do LAB$(printf '%02d' "$NLAB")" \
        --body "Alterações propagadas de $TEMPLATE." >/dev/null
      echo "  ✓ PR aberto"
    else
      git -C "$DIR" push -q origin HEAD
      echo "  ✓ atualizado"
    fi
  else
    git -C "$DIR" am --abort || true
    echo "  ✗ falha ao aplicar (veja o erro acima)"
    FAILED+=("$letter")
  fi
done

echo ""
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "Falharam: ${FAILED[*]}"
  echo "Para tentar de novo só esses: GROUP_LIST=\"${FAILED[*]}\" $0 $BASE $FINAL"
  exit 1
fi
echo "Done."
