#!/bin/bash
set -e

ORG="ELT85B-N21-2026-2"
GROUP_LIST="A B C D E F G H I J K L M X P N"   # ← not GROUPS
#GROUP_LIST="A B C D E F G H I J X P N"   # ← Populated GROUPS
#GROUP_LIST="X"   # ← Populated GROUPS
PJT="projeto"
TEMPLATE="$ORG/${PJT}-template"

echo "GROUP_LIST=[$GROUP_LIST]"
echo "Creating ${PJT}-grupo-* from $TEMPLATE"
echo ""

if ! gh repo view "$TEMPLATE" &>/dev/null; then
  echo "✗ Template $TEMPLATE não encontrado. Rode create-pjt-pio-template.sh antes."
  exit 1
fi

for letter in $GROUP_LIST; do
  GROUP_LOWER=$(echo "$letter" | tr '[:upper:]' '[:lower:]')
  TEAM_SLUG="grupo-${GROUP_LOWER}"
  REPO="${PJT}-grupo-${GROUP_LOWER}"

  echo "→ $REPO  (team: $TEAM_SLUG)"

  if gh repo view "$ORG/$REPO" &>/dev/null; then
    echo "  ⚠ already exists, skipping create"
  else
    gh repo create "$ORG/$REPO" \
      --private \
      --template "$TEMPLATE" \
      --description "Projeto Final - Grupo $letter"
  fi

  if gh api --method PUT --silent \
      "orgs/$ORG/teams/$TEAM_SLUG/repos/$ORG/$REPO" \
      -f permission=push; then
    echo "  ✓ https://github.com/$ORG/$REPO"
  else
    echo "  ✗ Failed to add team $TEAM_SLUG"
  fi
done

echo ""
echo "Done."
