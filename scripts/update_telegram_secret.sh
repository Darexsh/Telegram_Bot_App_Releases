#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <github-owner>"
  echo "Example: $0 Darexsh"
  exit 1
fi

OWNER="$1"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is not installed."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Please run: gh auth login"
  exit 1
fi

if [[ -z "${NEW_TG_TOKEN:-}" ]]; then
  read -r -s -p "Enter new Telegram bot token: " NEW_TG_TOKEN
  echo
fi

echo "Scanning repositories for .github/workflows/release-telegram.yml ..."

for repo in $(gh repo list "$OWNER" --limit 200 --json name -q '.[].name'); do
  if gh api "repos/$OWNER/$repo/contents/.github/workflows/release-telegram.yml" >/dev/null 2>&1; then
    echo "Updating TELEGRAM_BOT_TOKEN in $OWNER/$repo"
    gh secret set TELEGRAM_BOT_TOKEN \
      --repo "$OWNER/$repo" \
      --body "$NEW_TG_TOKEN"
  fi
done

echo "Done."
