#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

bash scripts/run_vla_service.sh > /tmp/agent_vla_vla.log 2>&1 &
vla_pid=$!
bash scripts/run_llm_service.sh > /tmp/agent_vla_llm.log 2>&1 &
llm_pid=$!
bash scripts/run_agent_api.sh > /tmp/agent_vla_agent.log 2>&1 &
agent_pid=$!

cleanup() {
  kill "$agent_pid" "$llm_pid" "$vla_pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT

sleep 3
bash scripts/smoke_test.sh
