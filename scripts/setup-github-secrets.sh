#!/usr/bin/env bash
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI 'gh' is required." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not logged in. Run: gh auth login" >&2
  exit 1
fi

if [[ ! -f credentials/google_oauth_client.json ]]; then
  echo "Missing credentials/google_oauth_client.json" >&2
  exit 1
fi

if [[ ! -f data/google_token.json ]]; then
  echo "Missing data/google_token.json" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

n1n_api_key="$(grep -E '^N1N_API_KEY=' .env | sed 's/^N1N_API_KEY=//')"
if [[ -z "$n1n_api_key" ]]; then
  echo "N1N_API_KEY is empty in .env" >&2
  exit 1
fi

base64 -i credentials/google_oauth_client.json | gh secret set GOOGLE_OAUTH_CLIENT_JSON_B64
base64 -i data/google_token.json | gh secret set GOOGLE_OAUTH_TOKEN_JSON_B64
printf '%s' "$n1n_api_key" | gh secret set N1N_API_KEY

echo "GitHub Secrets configured."
