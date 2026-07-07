from __future__ import annotations

from fastapi import FastAPI, HTTPException

from common.config import get_section
from common.schemas import HealthResponse, SkillSpec, VLAExecuteRequest, VLAExecuteResponse
from vla_service.providers.lerobot_rollout import LeRobotRolloutProvider
from vla_service.providers.mock import MockVLAProvider


app = FastAPI(title="VLA Service", version="0.1.0")


def get_provider():
    """根据配置选择当前 VLA 后端，例如 mock 或 lerobot_rollout。"""
    cfg = get_section("vla")
    provider = cfg.get("provider", "mock")
    if provider == "mock":
        return MockVLAProvider(cfg)
    if provider == "lerobot_rollout":
        return LeRobotRolloutProvider(cfg)
    raise RuntimeError(f"Unsupported VLA provider: {provider}")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """返回 VLA Service 的健康状态和当前 provider 名称。"""
    return HealthResponse(service="vla_service", status="ok", detail=f"provider={get_section('vla').get('provider')}")


@app.get("/v1/skills")
def skills() -> dict[str, list[SkillSpec]]:
    """从配置中读取并返回当前注册的 VLA 技能列表。"""
    cfg = get_section("vla")
    return {
        "skills": [
            SkillSpec(
                skill_id=skill_id,
                name=skill["name"],
                task_prompt=skill["task_prompt"],
                metadata={"policy_path": skill["policy_path"]},
            )
            for skill_id, skill in cfg.get("skills", {}).items()
        ]
    }


@app.post("/v1/execute", response_model=VLAExecuteResponse)
def execute(req: VLAExecuteRequest) -> VLAExecuteResponse:
    """校验技能 ID 后，把执行请求交给当前 VLA provider 处理。"""
    cfg = get_section("vla")
    if req.skill_id not in cfg.get("skills", {}):
        raise HTTPException(status_code=404, detail=f"Unknown skill_id: {req.skill_id}")
    try:
        return get_provider().execute(req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
