from __future__ import annotations

from common.schemas import VLAExecuteRequest, VLAExecuteResponse
from vla_service.providers.base import VLAProvider


class MockVLAProvider(VLAProvider):
    """提供不控制真实机械臂的 VLA 假实现，方便接口联调。"""

    name = "mock"

    def execute(self, req: VLAExecuteRequest) -> VLAExecuteResponse:
        """模拟执行某个机器人技能，只返回技能信息而不运行 LeRobot。"""
        skill = self.cfg["skills"][req.skill_id]
        task_prompt = req.task_prompt or skill["task_prompt"]
        return VLAExecuteResponse(
            ok=True,
            skill_id=req.skill_id,
            task_prompt=task_prompt,
            provider=self.name,
            message=f"[MOCK] 已选择 VLA 技能 {req.skill_id}: {task_prompt}",
            metadata={"dry_run": req.dry_run},
        )
