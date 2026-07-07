#!/usr/bin/env bash
set -euo pipefail

source /home/czw1/miniforge3/etc/profile.d/conda.sh
conda activate lerobot
cd /home/czw1/ChenLong-Robot-Internship/agent_vla
export AGENT_VLA_CONFIG="${AGENT_VLA_CONFIG:-/home/czw1/ChenLong-Robot-Internship/agent_vla/configs/app.yaml}"
export PYTHONPATH=/home/czw1/ChenLong-Robot-Internship/agent_vla/src
exec uvicorn vla_service.main:app --host "${VLA_SERVICE_HOST:-127.0.0.1}" --port "${VLA_SERVICE_PORT:-8011}"

