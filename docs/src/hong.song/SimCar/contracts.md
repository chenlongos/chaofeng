# 接口契约

## Agent API

### `POST /v1/chat`

入口接口。Agent 根据用户输入路由到 VLA 或 LLM。

请求：

```json
{
  "text": "帮我把球捡起来",
  "session_id": "demo",
  "metadata": {}
}
```

响应：

```json
{
  "session_id": "demo",
  "intent": "robot.pick_ball",
  "tool_call": {
    "tool_type": "vla",
    "name": "execute_skill",
    "arguments": {
      "skill_id": "ball_pick_v1",
      "user_text": "帮我把球捡起来"
    }
  },
  "answer": "...",
  "raw_result": {}
}
```

dry-run：

```bash
POST /v1/chat?dry_run=true
```

用于只生成 VLA 命令，不真正控制机器人。

### `GET /v1/tools`

返回 Agent 当前可以调用的工具。

## VLA Service

### `GET /v1/skills`

返回所有白名单机器人技能。

响应：

```json
{
  "skills": [
    {
      "skill_id": "ball_pick_v1",
      "name": "Pick up ball",
      "task_prompt": "Pick up the ball and place it in the target area.",
      "status": "available",
      "metadata": {
        "policy_path": "$HOME/..."
      }
    }
  ]
}
```

### `POST /v1/execute`

执行一个 VLA 技能。

请求：

```json
{
  "skill_id": "ball_pick_v1",
  "user_text": "帮我把球捡起来",
  "duration_s": 15,
  "dry_run": false,
  "metadata": {}
}
```

响应：

```json
{
  "ok": true,
  "skill_id": "ball_pick_v1",
  "task_prompt": "Pick up the ball and place it in the target area.",
  "provider": "lerobot_rollout",
  "message": "VLA skill finished.",
  "command": ["lerobot-rollout", "..."],
  "stdout": "...",
  "stderr": "",
  "return_code": 0,
  "metadata": {}
}
```

## LLM Service

### `POST /v1/generate`

请求：

```json
{
  "user_text": "北京有什么旅游景点",
  "system_prompt": null,
  "metadata": {}
}
```

响应：

```json
{
  "ok": true,
  "provider": "mock",
  "model": "mock-zh-assistant",
  "answer": "北京常见旅游景点包括...",
  "metadata": {}
}
```

## 兼容性约定

新增 provider 时必须遵守：

- VLA provider 输入固定为 `VLAExecuteRequest`。
- VLA provider 输出固定为 `VLAExecuteResponse`。
- LLM provider 输入固定为 `LLMGenerateRequest`。
- LLM provider 输出固定为 `LLMGenerateResponse`。

Agent 侧只依赖这些 schema，不依赖 provider 内部实现。
