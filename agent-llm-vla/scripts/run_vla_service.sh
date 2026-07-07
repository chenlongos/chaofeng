#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONDA_SH="${CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}"
CONDA_ENV="${CONDA_ENV:-lerobot}"

if [[ -f "$CONDA_SH" ]]; then
  source "$CONDA_SH"
  conda activate "$CONDA_ENV"
fi

cd "$PROJECT_ROOT"
export LEROBOT_HOME="${LEROBOT_HOME:-$HOME/lerobot}"
export AGENT_VLA_CONFIG="${AGENT_VLA_CONFIG:-$PROJECT_ROOT/configs/app.yaml}"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec uvicorn vla_service.main:app --host "${VLA_SERVICE_HOST:-127.0.0.1}" --port "${VLA_SERVICE_PORT:-8011}"
