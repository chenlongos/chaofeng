# 端侧大模型驱动的 SimCar 复合任务 MVP

## 能力定位

本模块让端侧 Qwen 负责把自然语言拆成受约束的高层技能计划，再由确定性几何规划器和反馈控制器执行。大模型不直接输出电机命令，也不能编造障碍物坐标。

当前可验证能力：

- 文本或 SenseVoice 音频入口；
- 端侧 Ollama/Qwen 生成白名单 JSON 任务计划；
- 前进、后退、左右转和停车，带距离、角度和分段上限；
- 根据配置中的已知障碍物坐标和尺寸生成左右绕行路径；
- “绕过已知障碍物后捡球”复合执行；
- 每段运动后读取 SimCar 状态；
- 碰撞、断连、超时、未知目标、距离过近和非法计划立即停车并失败；
- SimStateJudge 按运动或捡球任务分别检查终态。

当前不能宣称：

- 从相机图像识别可乐瓶或任意障碍物；
- 对“这个”做真实视觉 grounding；
- 在未知或动态障碍环境自主导航；
- 大模型直接进行安全的低层连续控制。

## 模块

```text
SenseVoice / text
→ agent_api.task_planner（端侧 LLM，白名单 JSON）
→ router / orchestrator（否定拦截、单次执行）
→ simcar_gateway_service.skills.task_plan
→ KnownScene（只接受可验证几何）
→ GeometricAvoidancePlanner（车辆足迹膨胀、左右候选）
→ WaypointNavigator / SafeMotionSkill（分段反馈控制）
→ DirectPickBallSkill
→ SimStateJudge
```

任务计划只允许：

```text
move(direction, distance_cm)
turn(direction, angle_deg)
stop()
navigate_around(target, side, clearance_cm?)
pick_ball()
```

Gateway 会在执行前再次校验整个计划并解析所有目标，避免执行一半后才发现后续目标未知。

## 启动

先打开 <https://simcar.chenlongrobot.com/>，刷新页面，等待 `Connected` 并复制新的 `clientId`。准备无动态障碍场景，测量可乐瓶在 SimCar `x/z` 坐标系中的位置。

```bash
cd /root/chaofeng/.claude/worktrees/simcar-agent-loop/agent-llm-vla

export SIMCAR_CLIENT_ID=car-xxxxxxxxx
export SIMCAR_OBSTACLE_X=0
export SIMCAR_OBSTACLE_Z=-5.4
export SIMCAR_LIVE=1

bash scripts/demo_simcar_agent.sh
```

需要本机 Ollama 已运行并准备 `qwen2.5:1.5b`。首次语音请求会加载 SenseVoice。

文本示例：

```text
dry 绕过前面的可乐瓶，把球捡起来
绕过前面的可乐瓶，把球捡起来
前进10厘米
向右转30度
停车
```

音频文件示例：

```text
@audio /root/sv_rec/avoid_and_pick.wav
```

## 安全约束

- Demo 固定 `max_retries: 1`，碰撞后不盲目恢复；
- 平移动作每段不超过 5 cm；
- 单次自然语言平移不超过 100 cm，转向不超过 180°；
- 30 cm 正方形车辆按半对角线计算旋转扫掠半径；
- 障碍物坐标缺失或别名无法唯一解析时，不发送运动命令；
- 初始位置位于障碍物膨胀安全区内时，只停车并返回 `unsafe_initial_clearance`；
- `stop` 是确定性规则技能，不依赖大模型规划成功；
- 退出 Runner 时尽力发送 `stop`。

## 感知接入点

未来视觉或模拟器对象接口应把检测结果转换为与 `KnownScene` 等价的结构，并带来源、时间戳和置信度：

```json
{
  "name": "coke_bottle",
  "aliases": ["可乐瓶"],
  "x": 0.0,
  "z": -5.4,
  "radius_cm": 3.3,
  "source": "rgbd_detector",
  "timestamp": "...",
  "confidence": 0.93
}
```

在加入真实感知前，演示必须表述为“已知几何绕障”，不能表述为“视觉识别绕障”。
