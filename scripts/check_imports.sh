#!/usr/bin/env bash
set -euo pipefail

source /home/czw1/miniforge3/etc/profile.d/conda.sh
conda activate lerobot
cd /home/czw1/ChenLong-Robot-Internship/agent_vla
export PYTHONPATH=/home/czw1/ChenLong-Robot-Internship/agent_vla/src

python -m compileall -q src
python - <<'PY'
from agent_api.main import app as agent_app
from vla_service.main import app as vla_app
from llm_service.main import app as llm_app

print("imports ok")
print(agent_app.title, vla_app.title, llm_app.title)
PY

