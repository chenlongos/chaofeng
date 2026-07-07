from __future__ import annotations

from common.config import get_section
from common.schemas import ToolCall, ToolType


def route_user_text(text: str) -> tuple[str, ToolCall]:
    """根据用户文本匹配配置里的关键词规则，并生成对应的工具调用。"""
    agent_cfg = get_section("agent")
    normalized = text.lower()
    rules = agent_cfg.get("intent_rules", {})

    for intent, rule in rules.items():
        if intent == "llm.general_qa":
            continue
        keywords = rule.get("keywords", [])
        if any(keyword.lower() in normalized for keyword in keywords):
            return intent, ToolCall(
                tool_type=ToolType.VLA,
                name="execute_skill",
                arguments={"skill_id": rule["skill_id"], "user_text": text},
            )

    return "llm.general_qa", ToolCall(
        tool_type=ToolType.LLM,
        name="generate",
        arguments={"user_text": text},
    )
