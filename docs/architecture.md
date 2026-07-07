# 架构设计

## 设计目标

第一版目标是在当前 WSL2 Ubuntu 24 里完成桌面机器人 Demo：

1. 用户输入自然语言。
2. Agent 判断是否属于机器人任务。
3. 如果是机器人任务，调用 VLA 服务执行具身技能。
4. 如果不是机器人任务，调用 LLM 服务回答。
5. 后续更换大语言模型或具身模型时，不改 Agent 主流程，只换 provider 或配置。

## 顶层数据流

```text
User
  |
  v
Agent API /v1/chat
  |
  +-- intent = robot.pick_ball
  |      |
  |      v
  |   VLA Service /v1/execute
  |      |
  |      v
  |   provider = mock / lerobot_rollout / future_ascend_vla
  |      |
  |      v
  |   Robot executes skill
  |
  +-- intent = llm.general_qa
         |
         v
      LLM Service /v1/generate
         |
         v
      provider = mock / openai / ollama / local_llm
```

## 为什么拆成三个服务

Agent、VLA、LLM 三个角色的变化频率不同：

- Agent 侧会频繁改意图识别、任务规划、多轮对话、工具调用策略。
- VLA 侧会频繁改 checkpoint、机器人配置、推理后端、Orange Pi/Ascend 部署。
- LLM 侧会频繁换模型供应商、本地模型、云模型。

如果三者写在一个 Python 进程里，后续替换任意一部分都会牵扯其他模块。拆成 HTTP 服务后，协作者只要遵守接口契约即可。

## 模块边界

### Agent API

路径：

```text
src/agent_api/
```

需要开发：

- `router.py`：把用户输入转成 intent 和 tool call。
- `main.py`：提供 `/v1/chat` 和 `/v1/tools`。
- `tool_clients.py`：调用 VLA Service 和 LLM Service。

后续可以扩展：

- 用 LLM 做意图识别。
- 支持多轮会话状态。
- 支持任务确认，例如“即将控制机械臂捡球，是否执行？”
- 支持安全策略，例如机械臂任务需要白名单 skill。

### VLA Service

路径：

```text
src/vla_service/
```

需要开发：

- 技能注册表：`configs/app.yaml` 里的 `vla.skills`。
- provider：`src/vla_service/providers/`。
- 真实机器人执行：当前已有 `LeRobotRolloutProvider` 骨架。

后续可以扩展 provider：

```text
mock                  本地假执行，用于联调
lerobot_rollout        当前 WSL + LeRobot + SmolVLA
remote_vla             调用另一台机器的 VLA 推理服务
ascend_vla             Orange Pi AI Pro / Ascend NPU 推理
```

### LLM Service

路径：

```text
src/llm_service/
```

需要开发：

- provider：`src/llm_service/providers/`。
- 统一 `/v1/generate` 接口。

后续可以扩展 provider：

```text
mock
openai
ollama
vllm
qwen_api
```

## 技能设计

VLA 技能必须是白名单，不允许 Agent 随意生成任意机器人命令。

示例：

```yaml
skills:
  ball_pick_v1:
    name: Pick up ball
    task_prompt: "Pick up the ball and place it in the target area."
    policy_path: /home/czw1/lerobot/outputs/train/so101_ball_pick_smolvla_v1/checkpoints/002000/pretrained_model
    rename_map: "{ observation.images.front: observation.images.camera1 }"
```

用户说法可以很多：

```text
帮我把球捡起来
拿一下球
抓球
```

但最终传给 VLA 的 task prompt 要尽量固定：

```text
Pick up the ball and place it in the target area.
```

这保证训练和部署时的语言条件一致。

## 后续接 Orange Pi AI Pro

第一版不要直接把 Agent、VLA、LLM 都塞到 Orange Pi。推荐顺序：

1. WSL 内跑通 Agent + VLA + LLM。
2. Orange Pi 只跑 Agent，VLA 仍调用 WSL 服务。
3. Orange Pi 跑 LLM 或调用云 LLM。
4. 单独验证 SmolVLA 到 ONNX/Ascend 的推理链路。
5. 新增 `ascend_vla` provider，保持 `/v1/execute` 接口不变。

只要 `/v1/execute` 不变，Agent 不需要知道底层是 PyTorch、ONNX、CANN 还是 OM。

