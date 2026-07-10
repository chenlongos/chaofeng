# AgentOS 编排层

> 宋泓 · AgentOS 编排层技术文档
> 代码位置：`agent-llm-vla/src/agent_api/`
> 配套约束：`D:\THU\BeiJing\嘲风\AgentOS任务约束手册.md`

## 一、职责定位

AgentOS 编排层是"嘲风"桌面机器人的**决策中枢**，负责：

| 能力 | 现状 | 待补 |
| --- | --- | --- |
| 意图识别 | 关键词硬匹配（28行） | 语义/LLM 分类，支持说法多样化 |
| 指令下发 | 已有 `VLAClient.execute_skill()` | 复用，不重写 |
| 环境交互反馈 | 无 | 解析执行状态 + 视觉判定任务成败 |
| 失败检测与重试 | 无 | 编排状态机：DISPATCH→EXECUTE→JUDGE→RETRY/REPORT |
| 多轮会话 | 无（session_id 仅透传） | 维护 session 上下文 |

**核心文件：**

- `router.py` — 意图识别与工具路由（主战场）
- `main.py` — Agent 服务入口与编排流程
- `tool_clients.py` — 调用 VLA/LLM 服务的客户端

## 二、系统架构

```
                    ┌─────────────┐
                    │  用户语音/文本 │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   ASR 模块   │  SenseVoice-Small (254MB, CER~8%)
                    │  (音频→文本)  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Agent API   │  ← 我的主战场 (8010端口)
                    │  编排状态机   │
                    └──┬──────┬───┘
                       │      │
            ┌──────────▼┐    ┌▼──────────┐
            │ VLA Service│    │ LLM Service│
            │  (8011端口) │    │  (8012端口) │
            └──────┬─────┘    └───────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
   ┌────▼────┐ ┌──▼───┐ ┌───▼────┐
   │机械臂(VLA)│ │底盘(Nav)│ │视觉判定 │
   │  同学A   │ │ 同学B  │ │(YOLO等)│
   └─────────┘ └──────┘ └────────┘
```

**三服务解耦架构（已跑通）：**
- Agent API: 8010 — 编排中枢
- VLA Service: 8011 — 视觉语言动作（机械臂技能）
- LLM Service: 8012 — 大语言模型（通用问答）

## 三、编排状态机（方案02，已审核通过）

```
DISPATCH（意图识别）
    │
    ├─ 安全检查：置信度 < 0.75 → REPORT_FAIL
    │
    ▼
EXECUTE（调用执行）
    │
    ├─ dry-run 预演 → 碰撞/边界检查
    │
    ▼
JUDGE（视觉判定）
    │
    ├─ 成功 → DONE
    │
    └─ 失败 → RETRY（≤ max_retries 次）
                  │
                  └─ 超限 → REPORT_FAIL → TTS 报告
```

**关键设计决策：**

1. **router 只做纯决策**：`(intent, ToolCall)` 输出签名不变，下游零改动
2. **orchestrator 管执行编排**：抽成独立 `orchestrator.py`，main.py 保持薄
3. **MockJudge 走 metadata 注入**：smoke_test 可覆盖"一次过"与"失败重试"两条路径
4. **Judge 契约**：`{success, detail, evidence}`，mock 阶段 evidence 恒 `{}`

## 四、两个下游黑盒

| 下游 | 负责人 | 我下发什么 | 我不关心什么 |
| --- | --- | --- | --- |
| 机械臂（VLA） | 同学A | `skill_id`（如 `ball_pick_v1`） | 手臂怎么动 |
| 底盘移动 | 同学B | 高层路径/路线命令 | 轮子怎么驱动 |

**路线规划是自有模块**（route_planner）：高层路线决策归我，轮子低层电机驱动归同学B。复合任务中 orchestrator 交替调度 VLA 和底盘。

## 五、技术选型

| 组件 | 选型 | 理由 |
| --- | --- | --- |
| ASR | SenseVoice-Small (254MB) | 中文 CER~8%，20x 实时，纯 CPU |
| 意图识别（规则层） | 文本归一化 + 扩充同义词 | mock 阶段即见效 |
| 意图识别（LLM兜底） | Qwen2.5-1.5B/3B | 默认关闭，预留插槽 |
| 视觉判定（简单） | YOLO-small | 本地 CPU 实时，灯灭/球进桶 |
| 视觉判定（语义） | 云端 VLM | 叠衣服整齐度等，低频 |
| 边缘部署 | 昇腾310B (4GB) → K3 (8GB) | 310B 先演示，K3 后落地 |
| 推理后端 | llama.cpp + CANN/Q4_K_M | 社区成熟，310B 适配 |

## 六、开发阶段规划

```
第一月(mock)：  S1 ✅ → S2 → S3 → S4 → S5 → S6
第二月(仿真)：  S7 真实VLA仿真 → S8 本地LLM决策脑 → S9 关灯闭环
进阶：          S10 边缘部署 → S11 决策引擎Phase3 → S12 MCP/SSE/多轮
路线规划(SR)：  SR1 接口占位 → SR2 骨架 → SR3 复合任务状态机
```

**当前进度**：S1 已完成，方案02（S2-S4）已 PASS，待进入 EXECUTE。

## 七、约束与红线

- 不破坏三服务解耦架构
- 不破坏 `schemas.py` 契约（只允许向后兼容新增）
- 不改 VLA/LLM 同事的 provider 内部代码
- 不在 agent 层 import lerobot / 绑定具体大模型 SDK
- 真机动作前必须 dry-run；危险动作需安全确认
- commit/PR 只署名本人，不添加任何 AI 共同署名

详见 `D:\THU\BeiJing\嘲风\AgentOS任务约束手册.md`。
