ORG="ELT85B-N21-2026-2"
NLAB=0
LAB=$(printf "%02d" $NLAB)
REPO="lab${LAB}-template"

gh repo create "$ORG/$REPO" \
  --private \
  --description "Template for LAB$LAB" \
  --add-readme

gh api --method PATCH \
  "repos/$ORG/$REPO" \
  -f is_template=true
  