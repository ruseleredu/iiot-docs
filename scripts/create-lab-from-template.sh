#!/bin/bash
set -e

ORG="ELT85B-N21-2026-2"
GROUP_LIST="A B C D E F G H I J K L M P"   # ← not GROUPS
NLAB=1
LAB=$(printf "lab%02d" "$NLAB")
TEMPLATE="$ORG/${LAB}-template"

echo "GROUP_LIST=[$GROUP_LIST]"
echo "Creating ${LAB}-grupo-* from $TEMPLATE"
echo ""

for letter in $GROUP_LIST; do
  GROUP_LOWER=$(echo "$letter" | tr '[:upper:]' '[:lower:]')
  TEAM_SLUG="grupo-${GROUP_LOWER}"
  REPO="${LAB}-grupo-${GROUP_LOWER}"

  echo "→ $REPO  (team: $TEAM_SLUG)"

  if gh repo view "$ORG/$REPO" &>/dev/null; then
    echo "  ⚠ already exists, skipping create"
  else
    gh repo create "$ORG/$REPO" \
      --private \
      --template "$TEMPLATE" \
      --description "LAB$(printf '%02d' "$NLAB") - Grupo $letter"
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
