#!/usr/bin/env bash
set -euo pipefail

cd /home/czw1/ChenLong-Robot-Internship/agent_vla
source /home/czw1/miniforge3/etc/profile.d/conda.sh
conda activate lerobot
export AGENT_VLA_CONFIG="${AGENT_VLA_CONFIG:-/home/czw1/ChenLong-Robot-Internship/agent_vla/configs/app.yaml}"
export PYTHONPATH=/home/czw1/ChenLong-Robot-Internship/agent_vla/src
exec uvicorn llm_service.main:app --host "${LLM_SERVICE_HOST:-127.0.0.1}" --port "${LLM_SERVICE_PORT:-8012}"
