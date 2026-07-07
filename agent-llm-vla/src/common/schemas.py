from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """描述服务健康检查返回的服务名、状态和可选说明。"""

    service: str
    status: Literal["ok", "degraded", "error"]
    detail: str | None = None


class UserRequest(BaseModel):
    """描述用户发给 Agent 的原始输入和会话信息。"""

    text: str = Field(..., description="Original user input.")
    session_id: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolType(str, Enum):
    """枚举 Agent 当前可以调用的工具类别。"""

    VLA = "vla"
    LLM = "llm"


class ToolCall(BaseModel):
    """描述 Agent 决定调用哪个工具以及传入哪些参数。"""

    tool_type: ToolType
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """描述 Agent 对用户请求的统一响应格式。"""

    session_id: str
    intent: str
    tool_call: ToolCall
    answer: str
    raw_result: dict[str, Any] = Field(default_factory=dict)


class SkillSpec(BaseModel):
    """描述一个 VLA 机器人技能的公开信息。"""

    skill_id: str
    name: str
    task_prompt: str
    status: Literal["available", "unavailable"] = "available"
    metadata: dict[str, Any] = Field(default_factory=dict)


class VLAExecuteRequest(BaseModel):
    """描述请求 VLA 服务执行某个机器人技能时需要的输入。"""

    skill_id: str
    user_text: str | None = None
    task_prompt: str | None = None
    duration_s: float | None = None
    dry_run: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class VLAExecuteResponse(BaseModel):
    """描述 VLA 服务执行机器人技能后的统一返回结果。"""

    ok: bool
    skill_id: str
    task_prompt: str
    provider: str
    message: str
    command: list[str] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    return_code: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMGenerateRequest(BaseModel):
    """描述请求 LLM 服务生成回答时需要的输入。"""

    user_text: str
    system_prompt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMGenerateResponse(BaseModel):
    """描述 LLM 服务生成回答后的统一返回结果。"""

    ok: bool
    provider: str
    model: str
    answer: str
    metadata: dict[str, Any] = Field(default_factory=dict)
