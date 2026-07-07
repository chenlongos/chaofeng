from __future__ import annotations

from common.config import get_section
from common.http_client import get_json, post_json
from common.schemas import LLMGenerateResponse, SkillSpec, VLAExecuteResponse


class VLAClient:
    """封装 Agent 到 VLA Service 的 HTTP 调用。"""

    def __init__(self) -> None:
        """从配置中读取 VLA Service 地址并保存为客户端基础 URL。"""
        self.base_url = get_section("agent")["vla_service_url"].rstrip("/")

    def list_skills(self) -> list[SkillSpec]:
        """向 VLA Service 查询当前可用的机器人技能列表。"""
        data = get_json(f"{self.base_url}/v1/skills")
        return [SkillSpec(**item) for item in data["skills"]]

    def execute_skill(self, skill_id: str, user_text: str, dry_run: bool = False) -> VLAExecuteResponse:
        """请求 VLA Service 执行指定技能，并返回统一的执行结果。"""
        data = post_json(
            f"{self.base_url}/v1/execute",
            {"skill_id": skill_id, "user_text": user_text, "dry_run": dry_run},
            timeout_s=600,
        )
        return VLAExecuteResponse(**data)


class LLMClient:
    """封装 Agent 到 LLM Service 的 HTTP 调用。"""

    def __init__(self) -> None:
        """从配置中读取 LLM Service 地址并保存为客户端基础 URL。"""
        self.base_url = get_section("agent")["llm_service_url"].rstrip("/")

    def generate(self, user_text: str) -> LLMGenerateResponse:
        """请求 LLM Service 根据用户文本生成自然语言回答。"""
        data = post_json(f"{self.base_url}/v1/generate", {"user_text": user_text}, timeout_s=120)
        return LLMGenerateResponse(**data)
