# 开发分工和迭代计划

## 第一阶段：框架联调

目标：不接真实机器人、不接真实大模型，先跑通接口。

开发内容：

- Agent 同事开发 `src/agent_api/router.py`。
- VLA 同事维护 `configs/app.yaml` 的 `vla.skills`。
- LLM 同事新增真实 provider 前先使用 mock。

验收：

```bash
bash scripts/smoke_test.sh
```

能看到：

- “帮我把球捡起来” 路由到 `ball_pick_v1`。
- “北京有什么旅游景点” 路由到 LLM。

## 第二阶段：接真实 SmolVLA

目标：VLA Service 调用真实 `lerobot-rollout`。

开发内容：

- 训练并确认 checkpoint 路径。
- 修改 `configs/app.yaml`：

```yaml
vla:
  provider: lerobot_rollout
```

- 将 `policy_path` 改成真实 checkpoint。

验收：

```bash
curl -s -X POST "http://127.0.0.1:8010/v1/chat?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"帮我把球捡起来","session_id":"demo"}'
```

先 dry-run 看命令，再真实执行。

## 第三阶段：接真实 LLM

目标：把 `llm_service` 的 mock provider 替换为真实模型。

推荐做法：

- 新建 `src/llm_service/providers/openai_provider.py` 或 `ollama_provider.py`。
- 保持 `/v1/generate` 接口不变。
- `configs/app.yaml` 只改：

```yaml
llm:
  provider: openai
  model: gpt-4.1-mini
```

## 第四阶段：多技能

目标：增加关灯、放桌子上等技能。

新增技能只改三处：

1. `configs/app.yaml` 的 `agent.intent_rules`。
2. `configs/app.yaml` 的 `vla.skills`。
3. 训练对应的 VLA checkpoint。

Agent 不直接关心 checkpoint 路径。

## 第五阶段：Orange Pi AI Pro

目标：未来把 VLA provider 换成板端推理。

开发内容：

- 新建 `src/vla_service/providers/ascend_vla.py`。
- 内部可以调用 Orange Pi 上的 HTTP 服务、ONNX Runtime CANN、或者 OM 推理进程。
- 对 Agent 仍然暴露同一个 `/v1/execute` 接口。

