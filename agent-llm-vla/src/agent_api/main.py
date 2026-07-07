from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from agent_api.router import route_user_text
from agent_api.tool_clients import LLMClient, VLAClient
from common.schemas import AgentResponse, HealthResponse, ToolType, UserRequest


app = FastAPI(title="Agent API", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """返回 Agent API 的健康状态，供启动检查和监控使用。"""
    return HealthResponse(service="agent_api", status="ok")


@app.get("/v1/tools")
def tools() -> dict:
    """聚合 VLA 技能和通用 LLM 能力，返回 Agent 当前可调用工具。"""
    vla = VLAClient()
    try:
        skills = vla.list_skills()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "tools": [
            {"tool_type": "vla", "name": skill.skill_id, "description": skill.task_prompt}
            for skill in skills
        ]
        + [{"tool_type": "llm", "name": "general_qa", "description": "General language model QA"}]
    }


@app.post("/v1/chat", response_model=AgentResponse)
def chat(req: UserRequest, dry_run: bool = Query(False)) -> AgentResponse:
    """处理用户输入，路由到 VLA 或 LLM，并返回统一 Agent 响应。"""
    intent, tool_call = route_user_text(req.text)

    if tool_call.tool_type == ToolType.VLA:
        client = VLAClient()
        try:
            result = client.execute_skill(
                skill_id=tool_call.arguments["skill_id"],
                user_text=req.text,
                dry_run=dry_run,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        answer = result.message
        raw_result = result.model_dump()
    else:
        client = LLMClient()
        try:
            result = client.generate(req.text)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        answer = result.answer
        raw_result = result.model_dump()

    return AgentResponse(
        session_id=req.session_id,
        intent=intent,
        tool_call=tool_call,
        answer=answer,
        raw_result=raw_result,
    )
