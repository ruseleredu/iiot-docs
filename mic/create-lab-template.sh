#!/bin/bash
set -e

ORG="ELT73A-S22-2026-2"
NLAB=2
LAB=$(printf "%02d" "$NLAB")
REPO="lab${LAB}-template"

gh repo create "$ORG/$REPO" \
  --private \
  --description "Template for LAB$LAB" \
  --add-readme

gh api --method PATCH \
  "repos/$ORG/$REPO" \
  -f is_template=true