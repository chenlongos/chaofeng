from __future__ import annotations

import subprocess

from common.schemas import VLAExecuteRequest, VLAExecuteResponse
from vla_service.providers.base import VLAProvider


class LeRobotRolloutProvider(VLAProvider):
    """通过调用 lerobot-rollout 把 VLA 技能真正下发到机械臂执行。"""

    name = "lerobot_rollout"

    def execute(self, req: VLAExecuteRequest) -> VLAExecuteResponse:
        """根据技能配置拼出 rollout 命令，支持 dry-run 或真实执行。"""
        skill = self.cfg["skills"][req.skill_id]
        robot = self.cfg["robot"]
        runtime = self.cfg["runtime"]
        duration_s = req.duration_s or runtime["duration_s"]
        task_prompt = req.task_prompt or skill["task_prompt"]

        command = [
            "lerobot-rollout",
            f"--robot.type={robot['type']}",
            f"--robot.port={robot['port']}",
            f"--robot.id={robot['id']}",
            f"--robot.cameras={robot['cameras']}",
            f"--policy.path={skill['policy_path']}",
            f"--rename_map={skill['rename_map']}",
            f"--task={task_prompt}",
            f"--fps={runtime['fps']}",
            f"--duration={duration_s}",
            f"--display_data={str(runtime['display_data']).lower()}",
            f"--return_to_initial_position={str(runtime['return_to_initial_position']).lower()}",
        ]

        if req.dry_run:
            return VLAExecuteResponse(
                ok=True,
                skill_id=req.skill_id,
                task_prompt=task_prompt,
                provider=self.name,
                message="Dry run only. Command was built but not executed.",
                command=command,
                metadata={"dry_run": True},
            )

        proc = subprocess.run(
            command,
            cwd=runtime["cwd"],
            text=True,
            capture_output=True,
            timeout=float(duration_s) + 180,
            check=False,
        )
        ok = proc.returncode == 0
        return VLAExecuteResponse(
            ok=ok,
            skill_id=req.skill_id,
            task_prompt=task_prompt,
            provider=self.name,
            message="VLA skill finished." if ok else "VLA skill failed.",
            command=command,
            stdout=proc.stdout[-4000:],
            stderr=proc.stderr[-4000:],
            return_code=proc.returncode,
        )
