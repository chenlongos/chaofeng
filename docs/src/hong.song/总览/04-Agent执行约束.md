# 嘲风 AgentOS · Agent 执行约束文档

> 文档性质：**给执行 agent 的代码级约束**。每次动手写/改代码前必读，确保多轮、多 agent 之间开发风格与构建方向一致。
> 与 `AgentOS任务约束手册.md` 分工：约束手册管"任务边界/红线/协作"（宏观）；本文管"写代码时的具体一致性"（微观、可机械核验）。
> 依据：实读 chaofeng 源码 + 26 轮架构讨论 + 架构调研 + CLAUDE.md 全局规则。
> 编写日期：2026-07-09

---

## 〇、执行前自检（每轮改代码前过一遍）

```
□ 我读过要改的文件的当前代码了吗？（先检索后生成，不凭记忆）
□ 这个能力有现成代码/schema/client 可复用吗？（DRY，不造轮子）
□ 我的改动会破坏 (intent, ToolCall) 签名吗？会动下游吗？
□ 我改的文件在"可改"权限内吗？（禁改 vla_service/llm_service/vla.*）
□ 改完我能跑 smoke_test 回归吗？
□ 这轮属于源码改动吗？属于就要在结尾补双轨记录 + 结构化任务清单。
```

任一为"否"或"不确定"→ 停下，先查证或问，不硬写。

---

## 一、契约一致性（最高优先，违反即 FAIL）🔩

1. **签名冻结**：`route_user_text()` 永远返回 `(intent: str, ToolCall)`。无论内部是关键词、LLM 分类、还是 function calling，`main.py` 的解包点 `intent, tool_call = route_user_text(...)` 不得被迫改动。
2. **arguments 键集同构** 🔩：任何路由路径（关键词/LLM）产出的 `ToolCall.arguments` 对 VLA 类必须含 `skill_id`（`main.py` 会读 `arguments["skill_id"]`，少给即 `KeyError` 崩溃）。新增路径前先对齐键集。
3. **schema 仅向后兼容新增**：改 `schemas.py` 只能加**带默认值**的字段，禁止删/改类型/改名。`VLAExecuteRequest/Response`、`LLMGenerate*` 零改动。
4. **优先 raw_result 承载**：成败/尝试次数/判定详情先塞 `AgentResponse.raw_result`；确需强类型暴露才动 schema，且**动 schema 是需二次确认的动作**。
5. **provider 私有信息进 metadata**：不污染通用 schema。A3 的 `confidence/reason/need_clarify` 放 `ToolCall.metadata`，🔩 仅在 OS 层内被 orchestrator 消费，**绝不跨 ③→④ 边界下发 VLA**。

---

## 二、模块职责边界（写代码时的落点纪律）

| 层 | 文件 | 只负责 | 绝不做 |
|---|---|---|---|
| router | `router.py` | 文本 → `(intent, ToolCall)` 纯决策 | 发起执行、调 VLA、管重试 |
| orchestrator | `orchestrator.py`（新增） | 拿 ToolCall → 安全闸门 → 执行 → 判定 → 重试；复合任务里在 route_planner 与 VLA 间交替调度 | 做意图分类、直接碰硬件 |
| route_planner | `route_planner.py`（新增，我的自有模块） | 复合任务中规划行进路线，产出**路径命令**下发底盘（高层路线决策） | 碰轮子低层驱动（前进后退转弯的电机控制归底盘同学 B）；单步任务里空转 |
| main | `main.py` | HTTP 入口、组装 AgentResponse、接线 | 堆业务逻辑（保持薄） |
| client | `tool_clients.py` | 封装 HTTP 调用（VLAClient / 新增 NavClient 底盘 client） | 改既有方法签名 |

**铁律**：
- 执行逻辑**只在 orchestrator**，绝不回落到 router。
- LLM 决定"做什么"（intent+参数）；状态机决定"怎么做"（执行序列）。🔩 **永不让 LLM 控制物理执行序列**。
- 向下只传明确指令（VLA: skill_id+user_text ／ 底盘: 路径命令）；向上只回报执行结果（ok/return_code ／ 移动结果）。

**两个下游黑盒的边界纪律** 🔩（写 route_planner / NavClient 时死守）：
- **机械臂（VLA，同学 A）**：我只发 `skill_id`，不管手臂怎么动。`NavClient` 不得复用 `VLAClient`，二者是独立下游。
- **底盘（同学 B）**：我发**高层路径命令**（route_planner 产出），不管轮子怎么驱动（前进后退转弯的电机控制是 B 的事，绝不在 Agent 层写电机/运动学代码）。
- **route_planner 是「我」的自有模块**，不是黑盒：路线高层规划归我，低层电机驱动归 B。它只在**复合任务**的移动子步骤被状态机调用，单步定点任务（关灯）不触发。
- 🔩 **置信度/理由绝不跨 ③→④ 边界**——无论下发 VLA 还是底盘，只传明确指令，A3 的 `confidence/reason` 仅 OS 层消费。
- ❓ **下发底盘的命令颗粒度未定**（语义目标 / waypoints / 离散指令三选一）：mock 阶段 `NavClient` 只留接口占位、`nav` 意图只留骨架直通桩，**不预设颗粒度**，待与 B 对齐后再实现真实规划算法。

---

## 三、代码风格（与现有代码对齐）

实读现有代码，风格如下，**新代码必须一致**：

1. **文件头**：`from __future__ import annotations`。
2. **类型注解**：全量注解，用 `str | None` 而非 `Optional[str]`（现有 schemas.py 风格）；`tuple[str, ToolCall]` 而非 `Tuple`。
3. **docstring**：每个函数/类一句中文 docstring 说明用途（对齐现有 router.py/main.py/schemas.py）。
4. **Pydantic**：用 V2 语法（`model_dump()` 不用 `.dict()`；`Field(default_factory=...)`）。
5. **命名**：函数/变量 snake_case，类 PascalCase，常量 UPPER_SNAKE；intent 用点分（`robot.turn_off_light`）。
6. **导入顺序**：标准库 → 第三方 → 本地（`common.*` / `agent_api.*`），与现有一致。
7. **配置读取**：一律走 `get_section("agent")`，不重复读 YAML、不硬编码路径/端口/阈值。
8. **HTTP 调用**：复用 `common.http_client` 的 `get_json/post_json`，不自己造 requests 调用。
9. **中文**：注释、docstring、日志面向人的部分用中文；标识符用英文。

---

## 四、构建方向一致性（防跑偏）

写任何新代码前，确认它朝这个方向收敛，而非另起：

1. **local-first**：本地能做的用本地（ASR/决策 LLM/YOLO 判定）；云端仅 `intent=llm.general_qa` 时按需调，且要有断网 fallback。
2. **provider 可插拔**：ASR/LLM/VLA/Judge/**NavClient** 都定义**协议/接口**再给实现；换后端只改 provider+配置。新增能力优先做成"可替换 provider"而非写死。底盘对接与 VLA 同构——`NavClient` 与 `VLAClient` 平级，只封"下发路径命令→收移动结果"的 HTTP，不管 B 内部电机怎么驱动。
3. **配置驱动**：关键词表、重试上限、置信度阈值、prompt 模板、服务 URL —— 全进 YAML，不写死在 .py。prompt 生成逻辑独立成函数（预留 MCP 迁移）。
4. **跨板可移植**：本地 LLM/ASR 都封成 OpenAI 兼容 HTTP 端点；Agent 只调 HTTP。🔩 **绝不在 Agent 层写昇腾 CANN / K3 专属代码**（否则换板重写）。
5. **状态机硬边界**：编排走确定性状态转换（基于返回码/判定结果），不靠 LLM 自由推理决定下一步；RETRY 查表恢复，不让 LLM 重新规划。
6. **安全前置**：动臂前必过 置信度闸门 + dry-run 预演；危险动作分级，high 以上二次确认。

---

## 五、防过度设计（KISS 守则）

调研里有很多高级方案（MCP / SSE / Code as Policies / HIL / 混沌测试），**它们都是后续方向，不是现在就写**。判断标准：

| 想写的东西 | 现在该写吗 | 触发条件 |
|---|---|---|
| MCP 动态发现 | ❌ 先 HTTP | 技能扩到 10+ |
| SSE 状态流 | ❌ 先同步等待 | VLA 任务 >30s / 需实时 UI / 中途取消 |
| Code as Policies + 沙箱 | ❌ 先 JSON 单步 | 进 Phase3 复杂任务 |
| 云端 VLM 语义判定 | ❌ 先本地 YOLO | 做"叠衣服"类语义任务 |
| LLM 重新规划重试 | ❌ 永不 | —（调研明确反对） |
| 多轮会话/唤醒词 | ❌ 后续 | demo 之后 |
| 真实路径规划算法（几何/避障/waypoints） | ❌ 先直通桩 | 复合任务 + 命令颗粒度与底盘同学 B 对齐后 |

**原则**：先用最简方案跑通闭环 demo；插槽可以预留（定义接口/留字段），但**实现留到触发条件满足**。每加一层复杂度前问："这是真问题还是臆想？"

---

## 六、验证纪律

1. **每步回归**：改完 S2/S3/S4 任一步，跑 `bash scripts/smoke_test.sh`，确保原四项（/health、中/英捡球、问答兜底）不回归。
2. **先激活 venv 再跑**：`source .venv/bin/activate` 后再调脚本（脚本对 conda 缺失有兜底，会用当前 shell 的 python）。
3. **越界自证**：改完跑 `git diff --stat`，确认 `vla_service/** llm_service/** configs/app.yaml:vla.*` 无改动。
4. **新增测试**：加能力要加对应测试；判定/重试/fallback 这类分支逻辑必须有覆盖成功+失败两条路径的用例（MockJudge 期望值走 metadata 注入即为此设计）。
5. **不 silence 警告**：不用 `# type: ignore` / `allow` 掩盖问题，修根因。

---

## 七、提交纪律 🔩

1. **只署名本人**：commit / PR 描述**禁止**任何 AI 共同署名或生成标记（`Co-Authored-By: Claude`、`Generated with...` 等一律不加）。
2. **不硬编码密钥**：不提交 .env/credentials；密钥/路径走环境变量与配置。
3. **PR 规范**（若提 PR）：标题 Conventional Commits（`feat(agent_api): ...`），英文标题、中文正文。
4. **收尾双轨**：源码改动轮次结束必补 `任务日志.md`（事实）+ `任务详情.md`（为什么）+ 方案末尾结构化任务清单，只追加不回改。
5. **清理**：删临时文件、废弃代码、未用导入、调试 print。

---

## 八、失败处理纪律

1. **同一方法失败两次 → 停手诊断根因**，不做第三次增量补丁；说清哪里错了、换什么思路，偏离原意图或引入取舍时先确认。
2. **不确定的框架/接口 → 先检索验证**（context7 查库文档 / 实读源码），不凭假设写。
3. **改动范围超出预期 / 发现潜在风险 → 先说明再动**，不闷头扩大改动面。

---

## 附：一句话总纲

**读了再写、能复用就不新造、守住 `(intent,ToolCall)` 和判断在 OS 层两条命脉、先跑通最简闭环再谈高级、动 schema 和动 VLA 领域必先确认、提交只署名本人。**
