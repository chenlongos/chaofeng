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
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -m compileall -q src
python - <<'PY'
from agent_api.main import app as agent_app
from vla_service.main import app as vla_app
from llm_service.main import app as llm_app

print("imports ok")
print(agent_app.title, vla_app.title, llm_app.title)
PY
