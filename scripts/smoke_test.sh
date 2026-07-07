#!/usr/bin/env bash
set -euo pipefail

curl -s http://127.0.0.1:8010/health
printf '\n'
curl -s -X POST "http://127.0.0.1:8010/v1/chat?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"帮我把球捡起来","session_id":"demo"}'
printf '\n'
curl -s -X POST "http://127.0.0.1:8010/v1/chat?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"pick ball","session_id":"demo"}'
printf '\n'
curl -s -X POST "http://127.0.0.1:8010/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"text":"北京有什么旅游景点","session_id":"demo"}'
printf '\n'
