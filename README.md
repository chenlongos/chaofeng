# Agent + VLA + LLM 桌面机器人 Demo 框架

这个项目是第一版桌面机器人 Demo 的解耦框架。目标是在当前 WSL2 Ubuntu 24 环境里，把用户输入路由到两类能力：

- VLA 具身模型：执行捡球、放到桌子上、关灯等机器人技能。
- LLM 语言模型：回答旅游景点、常识问答、聊天等非机器人任务。

框架默认使用 mock provider，可以先不接真实机器人、不接真实大模型就跑通接口。后续只需要替换 provider 或配置，就可以换成真实 SmolVLA、Orange Pi Ascend NPU 推理服务、OpenAI、Ollama、本地大模型等。

## 一、整体架构

```text
用户输入
  |
  v
Agent API
  |
  +-- 判断为机器人任务
  |      |
  |      v
  |   VLA Service
  |      |
  |      +-- mock provider
  |      +-- lerobot_rollout provider
  |      +-- future ascend_vla provider
  |      |
  |      v
  |   机械臂执行技能
  |
  +-- 判断为通用问答
         |
         v
      LLM Service
         |
         +-- mock provider
         +-- future openai provider
         +-- future ollama provider
         +-- future local_llm provider
         |
         v
      返回自然语言答案
```

设计原则：

- Agent 不直接 import LeRobot。
- Agent 不直接操作机械臂串口。
- Agent 不直接绑定某个大模型 SDK。
- VLA 模型、LLM 模型都作为 Agent 可调用的外部工具。
- 后续换 VLA 或 LLM 时，尽量只改 provider 和配置，不改 Agent 主流程。

## 二、目录结构

```text
agent_vla/
  configs/
    app.yaml

  docs/
    architecture.md
    contracts.md
    development_plan.md

  scripts/
    check_imports.sh
    run_agent_api.sh
    run_vla_service.sh
    run_llm_service.sh
    run_mock_stack_test.sh
    smoke_test.sh

  src/
    common/
      __init__.py
      config.py
      http_client.py
      schemas.py

    agent_api/
      __init__.py
      main.py
      router.py
      tool_clients.py

    vla_service/
      __init__.py
      main.py
      providers/
        __init__.py
        base.py
        mock.py
        lerobot_rollout.py

    llm_service/
      __init__.py
      main.py
      providers/
        __init__.py
        base.py
        mock.py
```

顶层职责：

```text
common        三方共享协议、配置读取、HTTP 工具
agent_api     Agent 入口，负责理解用户输入、路由、调用工具
vla_service   VLA 服务，封装 SmolVLA、LeRobot、未来 Ascend NPU 推理
llm_service   LLM 服务，封装 OpenAI、Ollama、本地大模型等
```

## 三、src 每个文件的职责

### 1. common

`src/common/config.py`

作用：读取全局配置文件。

默认读取：

```text
/home/czw1/ChenLong-Robot-Internship/agent_vla/configs/app.yaml
```

主要函数：

```python
load_config()
get_section(name)
```

开发者一般不用改。后续如果要支持环境变量覆盖配置、多个 profile、远程配置中心，可以从这里扩展。

`src/common/http_client.py`

作用：封装最小 HTTP 调用能力。

主要函数：

```python
post_json()
get_json()
```

Agent 调用 VLA Service / LLM Service 时会用这里。后续如果要加鉴权、trace_id、重试、统一 timeout，可以改这里。

`src/common/schemas.py`

作用：全项目最重要的接口协议定义。

里面定义：

```python
HealthResponse
UserRequest
ToolType
ToolCall
AgentResponse
SkillSpec
VLAExecuteRequest
VLAExecuteResponse
LLMGenerateRequest
LLMGenerateResponse
```

开发规则：

- 新增字段尽量给默认值，避免破坏旧接口。
- 不要随便删除字段。
- provider 私有信息放到 `metadata`，不要污染通用 schema。
- Agent、VLA、LLM 三方都以这里的 schema 为契约。

### 2. agent_api

`src/agent_api/main.py`

作用：Agent 服务入口。

提供接口：

```text
GET  /health
GET  /v1/tools
POST /v1/chat
```

核心流程：

```text
接收用户输入
  |
  v
route_user_text()
  |
  +-- ToolType.VLA
  |      |
  |      v
  |   VLAClient.execute_skill()
  |
  +-- ToolType.LLM
         |
         v
      LLMClient.generate()
  |
  v
返回 AgentResponse
```

做 Agent 的开发者主要会改这里和 `router.py`。

`src/agent_api/router.py`

作用：意图识别和工具选择。

当前实现是关键词规则：

```python
def route_user_text(text: str) -> tuple[str, ToolCall]:
```

例子：

```text
帮我把球捡起来
  -> intent = robot.pick_ball
  -> tool_type = vla
  -> skill_id = ball_pick_v1

北京有什么旅游景点
  -> intent = llm.general_qa
  -> tool_type = llm
```

Agent 开发者最应该从这里开始。后续可以升级为：

- LLM intent classifier
- function calling
- LangGraph / AutoGen / 自研 planner
- 多轮会话状态
- 任务安全确认
- 机器人技能白名单检查

但建议输出仍保持为：

```python
intent, ToolCall
```

这样下游 VLA/LLM 服务不用改。

`src/agent_api/tool_clients.py`

作用：Agent 调用外部工具服务的客户端。

里面有：

```python
class VLAClient:
    list_skills()
    execute_skill()

class LLMClient:
    generate()
```

Agent 开发者不要在业务代码里到处手写 HTTP 请求，统一通过这里调用 VLA/LLM。

### 3. vla_service

`src/vla_service/main.py`

作用：VLA 服务入口。

提供接口：

```text
GET  /health
GET  /v1/skills
POST /v1/execute
```

核心流程：

```text
接收 skill_id
  |
  v
检查 skill_id 是否存在于 configs/app.yaml
  |
  v
get_provider()
  |
  v
provider.execute(req)
  |
  v
返回 VLAExecuteResponse
```

机器人/VLA 开发者一般只需要在这里加 provider 分支，不要把具体推理逻辑写进 `main.py`。

`src/vla_service/providers/base.py`

作用：VLA provider 抽象接口。

```python
class VLAProvider(ABC):
    def execute(self, req: VLAExecuteRequest) -> VLAExecuteResponse:
```

所有 VLA 后端都必须实现这个接口。

未来可以扩展：

```text
mock               假执行，用于联调
lerobot_rollout    当前 WSL + LeRobot + SmolVLA
remote_vla         调用远程 VLA 推理服务
ascend_vla         Orange Pi AI Pro / Ascend NPU 推理
```

`src/vla_service/providers/mock.py`

作用：假 VLA。

不会控制机械臂，只返回类似：

```text
[MOCK] 已选择 VLA 技能 ball_pick_v1
```

Agent 联调阶段默认使用它。

`src/vla_service/providers/lerobot_rollout.py`

作用：真实调用 LeRobot 的 `lerobot-rollout`。

它会根据 `configs/app.yaml` 组装命令：

```bash
lerobot-rollout \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=follower \
  --robot.cameras="..." \
  --policy.path="..." \
  --rename_map="..." \
  --task="..." \
  --fps=1 \
  --duration=15
```

VLA/机器人开发者后续主要从这里扩展：

- 接真实 SmolVLA checkpoint。
- 增加不同机器人配置。
- 增加更多 rollout 参数。
- 增加执行状态回传。
- 增加异常处理和安全停止。
- 未来新增 Orange Pi / Ascend NPU provider。

### 4. llm_service

`src/llm_service/main.py`

作用：LLM 服务入口。

提供接口：

```text
GET  /health
POST /v1/generate
```

核心流程：

```text
接收 user_text
  |
  v
get_provider()
  |
  v
provider.generate(req)
  |
  v
返回 LLMGenerateResponse
```

LLM 开发者一般只需要在这里加 provider 分支。

`src/llm_service/providers/base.py`

作用：LLM provider 抽象接口。

```python
class LLMProvider(ABC):
    def generate(self, req: LLMGenerateRequest) -> LLMGenerateResponse:
```

所有大模型后端都实现它。

未来可以扩展：

```text
mock
openai
ollama
qwen
vllm
local_transformers
```

`src/llm_service/providers/mock.py`

作用：假 LLM。

当前逻辑：

```python
if "北京" in text and "景点" in text:
    answer = "北京常见旅游景点包括..."
else:
    answer = "[MOCK LLM] 我收到了你的问题..."
```

真实接大模型时，不建议直接改这个文件。建议新增：

```text
src/llm_service/providers/openai_provider.py
src/llm_service/providers/ollama_provider.py
src/llm_service/providers/qwen_provider.py
```

然后在 `src/llm_service/main.py` 的 `get_provider()` 里加分支。

## 四、接口设计

### 1. Agent API

#### `POST /v1/chat`

Agent 的统一入口。

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

```text
POST /v1/chat?dry_run=true
```

用于只生成 VLA 调用，不真正控制机器人。

#### `GET /v1/tools`

返回 Agent 当前可调用工具。

### 2. VLA Service

#### `GET /v1/skills`

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
        "policy_path": "/home/czw1/..."
      }
    }
  ]
}
```

#### `POST /v1/execute`

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

### 3. LLM Service

#### `POST /v1/generate`

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
  "answer": "北京常见旅游景点包括故宫、天安门广场、颐和园、长城、天坛、北海公园、什刹海和国家博物馆。",
  "metadata": {}
}
```

## 五、数据流转链条

### 1. 用户让机器人捡球

```text
用户输入：
帮我把球捡起来

1. Agent API 收到 POST /v1/chat
   UserRequest.text = "帮我把球捡起来"

2. Agent 调用 route_user_text()
   匹配关键词：捡起来 / 把球捡起来 / pick ball

3. Agent 生成 ToolCall
   intent = robot.pick_ball
   tool_type = vla
   skill_id = ball_pick_v1

4. Agent 调用 VLA Service
   POST /v1/execute

5. VLA Service 查询 configs/app.yaml
   找到 ball_pick_v1:
     task_prompt = "Pick up the ball and place it in the target area."
     policy_path = "/home/czw1/lerobot/outputs/train/..."

6. VLA provider 执行
   mock provider：返回假执行结果
   lerobot_rollout provider：调用 lerobot-rollout 控制机器人

7. VLA Service 返回 VLAExecuteResponse

8. Agent API 包装成 AgentResponse 返回给用户
```

### 2. 用户问北京旅游景点

```text
用户输入：
北京有什么旅游景点

1. Agent API 收到 POST /v1/chat

2. Agent 调用 route_user_text()
   没有匹配机器人技能

3. Agent 生成 ToolCall
   intent = llm.general_qa
   tool_type = llm

4. Agent 调用 LLM Service
   POST /v1/generate

5. LLM provider 推理
   mock provider：返回固定示例答案
   future openai/ollama provider：调用真实大模型

6. LLM Service 返回 LLMGenerateResponse

7. Agent API 包装成 AgentResponse 返回给用户
```

## 六、开发者应该从哪里开始

### Agent 开发者

主要开发：

```text
src/agent_api/router.py
src/agent_api/main.py
```

需要了解：

```text
src/agent_api/tool_clients.py
src/common/schemas.py
configs/app.yaml
```

重点任务：

- 把用户自然语言映射到 `intent`。
- 把机器人任务映射到固定 `skill_id`。
- 把非机器人问题路由到 LLM。
- 后续加入多轮对话、任务确认、安全策略。

### VLA / 机器人开发者

主要开发：

```text
configs/app.yaml
src/vla_service/providers/lerobot_rollout.py
src/vla_service/providers/ascend_vla.py    # 后续新增
```

需要了解：

```text
src/vla_service/main.py
src/common/schemas.py
```

重点任务：

- 训练 SmolVLA checkpoint。
- 在 `configs/app.yaml` 注册技能。
- 保证 `skill_id -> task_prompt -> policy_path` 稳定。
- 接入真实 LeRobot rollout。
- 后续接 Orange Pi AI Pro / Ascend NPU 推理。

### LLM 开发者

主要开发：

```text
src/llm_service/providers/openai_provider.py
src/llm_service/providers/ollama_provider.py
src/llm_service/providers/qwen_provider.py
src/llm_service/main.py
```

需要了解：

```text
src/common/schemas.py
configs/app.yaml
```

重点任务：

- 实现新的 `LLMProvider`。
- 在 `get_provider()` 里注册 provider。
- 从 `configs/app.yaml` 读取模型名、API 地址、密钥等配置。

### 全局接口设计者

主要开发：

```text
src/common/schemas.py
docs/contracts.md
```

重点任务：

- 维护 Agent / VLA / LLM 之间的接口契约。
- 确保新增字段向后兼容。
- 避免 provider 私有细节泄漏到通用协议。

## 七、配置说明

全局配置在：

```text
configs/app.yaml
```

关键配置：

```yaml
agent:
  vla_service_url: http://127.0.0.1:8011
  llm_service_url: http://127.0.0.1:8012
  intent_rules:
    robot.pick_ball:
      keywords: ["捡球", "拿球", "抓球", "捡起来", "把球捡起来", "把球拿起来", "pick ball"]
      skill_id: ball_pick_v1

vla:
  provider: mock
  skills:
    ball_pick_v1:
      task_prompt: "Pick up the ball and place it in the target area."
      policy_path: /home/czw1/lerobot/outputs/train/so101_ball_pick_smolvla_v1/checkpoints/002000/pretrained_model

llm:
  provider: mock
  model: mock-zh-assistant
```

切换真实 VLA：

```yaml
vla:
  provider: lerobot_rollout
```

切换真实 LLM 时，新增 provider 后再改：

```yaml
llm:
  provider: openai
  model: your-model-name
```

## 八、启动和测试

### 1. 检查导入

```bash
cd /home/czw1/ChenLong-Robot-Internship/agent_vla
bash scripts/check_imports.sh
```

### 2. 分别启动三个服务

终端 1：

```bash
cd /home/czw1/ChenLong-Robot-Internship/agent_vla
bash scripts/run_vla_service.sh
```

终端 2：

```bash
cd /home/czw1/ChenLong-Robot-Internship/agent_vla
bash scripts/run_llm_service.sh
```

终端 3：

```bash
cd /home/czw1/ChenLong-Robot-Internship/agent_vla
bash scripts/run_agent_api.sh
```

### 3. 冒烟测试

```bash
cd /home/czw1/ChenLong-Robot-Internship/agent_vla
bash scripts/smoke_test.sh
```

或者一次性启动 mock 栈并测试：

```bash
cd /home/czw1/ChenLong-Robot-Internship/agent_vla
bash scripts/run_mock_stack_test.sh
```

### 4. curl 示例

机器人任务 dry-run：

```bash
curl -s -X POST "http://127.0.0.1:8010/v1/chat?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"帮我把球捡起来","session_id":"demo"}'
```

通用问答：

```bash
curl -s -X POST "http://127.0.0.1:8010/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"text":"北京有什么旅游景点","session_id":"demo"}'
```

## 九、后续扩展方式

### 新增一个机器人技能

1. 在 `configs/app.yaml` 的 `vla.skills` 添加技能。
2. 在 `configs/app.yaml` 的 `agent.intent_rules` 添加触发词和 `skill_id`。
3. 训练对应的 VLA checkpoint。
4. 不需要改 Agent 主流程。

### 新增一个 LLM provider

1. 新建 `src/llm_service/providers/xxx_provider.py`。
2. 继承 `LLMProvider`。
3. 实现 `generate()`。
4. 在 `src/llm_service/main.py` 的 `get_provider()` 里注册。
5. 修改 `configs/app.yaml` 的 `llm.provider`。

### 新增一个 VLA provider

1. 新建 `src/vla_service/providers/xxx_vla.py`。
2. 继承 `VLAProvider`。
3. 实现 `execute()`。
4. 在 `src/vla_service/main.py` 的 `get_provider()` 里注册。
5. 修改 `configs/app.yaml` 的 `vla.provider`。

未来接 Orange Pi AI Pro / Ascend NPU 时，建议新增：

```text
src/vla_service/providers/ascend_vla.py
```

只要它仍然输入 `VLAExecuteRequest`、输出 `VLAExecuteResponse`，Agent 不需要知道底层是 PyTorch、ONNX、CANN 还是 OM。
