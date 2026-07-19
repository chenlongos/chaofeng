# AgentOS 编排层 · 项目设计与推进计划

> 本文是嘲风双臂机器人 AgentOS 编排层的正式设计文档，覆盖：总体架构定位、与老师框架（OMiniX / Octos / World Model / dora-rs / StarryOS）的对接策略、责任划分、接下来的全部工作、进度控制与每周任务。
>
> 文档里"我们的对应物"均为本仓已落地并通过测试的真实代码；涉及 Octos / dora / OMiniX 的外部判断基于公开资料与老师提供的调研文档。

---

## 〇、一句话定位

> **我们不是"要不要用这套框架"，而是"已经用 Python 独立实现了这套框架最上面三层（交互 / 决策 / 判定）的一个可运行垂直切片"。接下来的工作是：把每层的 mock 换成真实内核、补齐两个缺失层（Memory / World Model）、并在协议边界上与框架对接——而不是推倒重写。**

---

## 一、总体架构（现状 · 真实代码）

### 1.1 已跑通的闭环

```
音频/文本入口 (/v1/chat, /v1/chat_audio)
  │
  ├─ S5  ASR：asr_service:8014   provider=mock | sensevoice(SenseVoice-Small)
  │
route_user_text()  意图路由
  │   keywords + signals(动作×对象) + 否定否决 + LLM 兜底分类
  │
orchestrate()  十态状态机
  ├─ S8 置信度闸门：conf<0.75 → CONFIRMING 反问；反问满 3 轮仍低 → CANCELLED 降级(不派发)
  ├─ VLA 分支：DISPATCH→EXECUTE→JUDGE→(RETRY×N)→COMPLETE/REPORT_FAIL   ← S4 失败重试
  ├─ LLM 分支：问答直接 COMPLETE
  └─ dry_run 全程贯穿（真机前预演）
  │
  ├─ 执行   vla_service:8011    provider=mock | lerobot_rollout(SmolVLA + so101 机械臂)
  ├─ 问答   llm_service:8012    provider=mock | ollama(qwen2.5:1.5b)
  ├─ 判定   judge_service:8013  provider=mock | reward_classifier(RewardClassifier)  ← S6
  └─ 底盘   route_planner: NavClient 与 VLAClient 平级独立（mock 桩，颗粒度待与底盘同学对齐）
  │
成/败终态
```

### 1.2 工程属性（这些是我们的护城河）

- **五服务 HTTP 解耦**：agent_api / asr_service / vla_service / llm_service / judge_service 各自独立进程，`curl` 任意端点即可调试。
- **Pydantic schema 作契约**：`ToolCall / VLAExecuteRequest / JudgeRequest / ASRRequest …`，schema 只向后兼容新增。
- **provider 可插拔**：每层 `mock ↔ 真实` 切换只改配置，编排代码零改动。
- **红线守护**：Agent 永不 import lerobot / torch；真实内核都在下游服务进程内。
- **可观测性**：orchestrator 结构化 key=value 日志埋点（意图 / attempt / 状态 / 成败 / 终态）。
- **测试基线**：单元 / 契约 / 集成 / e2e 分层覆盖，主干测试常绿。

---

## 二、与老师框架的对接策略（六项已敲定的决策）

### 决策一：语言——不重写 Rust，复用发生在"协议边界"

Octos/dora 通过 MCP / 数据流消息集成，与语言无关。就算改成 Rust，它们调我们照样过协议层，"同语言=直接调用"的收益在分层架构里不存在。而我们的决策/判定层依赖的 LeRobot / SmolVLA / SenseVoice 是 Python 具身生态，Rust 侧无对等替代。

> **结论**：编排层保持 Python，是与"层的特性（秒级、IO 密集、依赖 ML 生态）"匹配的正确选型，不是将就。

### 决策二：Octos——旁路集成，吸收设计而非搬运源码

Octos 是通用对话 Agent OS，18 crate / 91 端点，产品边界远大于我们两技能 demo 的需求边界。整体搬运 = 超配 + 断 Python 生态 + 用别人的运行时盖掉自己已跑通的决策层 + 从建造者变粘合者。

> **结论**：路线 C 折中。保留我们的编排层为主体，Octos（若上）作为可插拔高层后端**旁路**接入做对照，永不并入内核、永不让底层依赖 Octos 数据结构。
>
> **真正值得吸收的两样**：① Memory 分层（我们的缺口）；② MCP 作为对外工具协议（互操作标准）。安全等级 / 资源锁概念留给双臂阶段。

### 决策三：OMiniX——参考其设计，整合边缘推理层（边缘部署时才做）

OMiniX 的价值是"边缘多模态推理的统一运行时"，不是某个可复用的仓库（目前无公开仓库可拿）。我们后续可参考它，把已有的 ASR / TTS / llama.cpp 收拢成一个共享运行时。

> **关键分寸**：**契约不动，运行时合并**。`ASRResponse / LLMGenerateResponse` 等 schema 保持不变，底下换成共享的边缘推理运行时托管 SenseVoice + llama.cpp + TTS。agent_api 的 client 一行不改，只改 base_url。
>
> **时机**：真机边缘部署（310B）撞到显存/延迟墙时才做；现在只出设计。**TTS 目前尚未实现，整合这一步顺带补 TTS。**

### 决策四：dora——四层混合，编排层保持 HTTP

不是"HTTP 还是 dora"二选一，而是分层混合：

| 层 | 通信方式 | 模块 | 归属 |
|---|---|---|---|
| ① 外部/模型服务 | **HTTP（保持不动）** | ASR、TTS、llama.cpp、Octos、任务入口 | **编排层（宋泓）** |
| ② AI/感知数据流 | **dora 优先** | 相机、检测、位姿、World Model 更新、任务事件、录制回放 | 新同学（World Model 阶段） |
| ③ 任务级控制 | dora Action / ROS2 Action | pick/place/搬运 | 机械臂同学 |
| ④ 实时控制 | 现有控制栈，**不碰** | 关节环、力矩、急停、EtherCAT | 硬件同学 |

> **结论**：dora 的优势（零拷贝高频流、一对多发布、记录回放）在第②层的高频感知链才兑现，那不是编排层。编排层是事件驱动的低频请求-响应链，HTTP 是正确选型。**dora 的实际动手划给新同学的 World Model 阶段；编排层现在一行 dora 代码不写。**

### 决策五：Robot Gateway——我们已有雏形，未来接 dora 是加适配器不是重写

老师框架强调一个中间边界 Robot Gateway：对上 HTTP/MCP、对内 dora、对底层 ROS2，负责 ID / 校验 / 权限 / 资源锁 / 超时 / 错误码转换 / 审计。

> **我们的现状**：`agent_api` + `tool_clients(VLAClient/NavClient/JudgeClient/ASRClient)` 就是 Robot Gateway 的雏形；Pydantic schema 就是老师说的"传输无关领域对象（TaskRequest/TaskFeedback/TaskResult）"。
>
> **结论**：把已有结构显式命名为 Robot Gateway。未来接 dora = 在 gateway 里加一个 dora adapter，业务代码只认领域对象、不认 dora Event，天然防锁死。

### 决策六：判定闭环（S6）——架构已完成，内核归新同学

判定闭环的架构、契约、真实内核接入口（`image_ref` + `RewardClassifierProvider` 占位）已全部就位，剩下是"往占位里填真东西"。

> **三条边界**：
> 1. 内核走 **RewardClassifier**（与 SmolVLA 同生态），是新同学的活；编排层只维护已写好的 `RemoteJudge` HTTP 对接（换 provider 内核时编排零改动）。
> 2. **红线：判定服务答"世界现在什么状态"（报事实），编排层答"那怎么办"（判成败/要不要重试）。** 防止判定侵入 orchestrate。
> 3. `evidence` 现在留空，约定将来装检测框 / 置信度 / 帧引用，新同学做真实内核时填。

---

## 三、责任划分（三层边界，一句话划清）

> **决策层（宋泓）答"用户想做什么、下一步调哪个能力、要不要重试"；世界状态服务（新同学）答"世界现在什么状态、动作结果如何"；三层通过冻结的契约通信，谁都不碰谁的内部。**

### 3.1 宋泓（编排层 + Memory）

| 模块 | 状态 | 说明 |
|---|---|---|
| 意图路由 route_user_text | 已完成 | 规则+信号+否定否决+LLM 兜底 |
| 编排状态机 orchestrate | 已完成 | 十态、S8 闸门、S4 重试、故障/失败切分 |
| Robot Gateway（agent_api + clients） | 已有雏形 | 显式命名 + 补 request_id |
| 判定 HTTP 对接 RemoteJudge | 已完成 | 换内核零改动 |
| **Memory 层** | **待建** | 会话/情节/长期偏好，编排状态外置 |
| ASR/LLM/TTS 边缘运行时整合 | 后期 | 边缘部署时做，顺带补 TTS |

### 3.2 新同学（World Model + 视觉事实服务）

| 任务包 | 对应框架层 | 说明 |
|---|---|---|
| **World Model 服务** | 世界状态层 | 对象/位姿/状态/置信度/lastseen 的结构化记忆；高频感知链可用 dora |
| **视觉事实服务（判定内核）** | 判定闭环 S6 | judge_service 里实现 RewardClassifier/YOLO，只报图像事实 |

### 3.3 其他同学（不重叠）

- 机械臂同学：双臂任务规划、MoveIt、双臂协调、碰撞检查
- 底盘同学：底盘导航颗粒度（NavClient 已留平级接口待对接）
- 硬件/控制同学：ros2_control、实时闭环、急停、StarryOS 底层平台

### 3.4 Memory vs World Model 边界（防混淆，写死）

| | Memory（宋泓） | World Model（新同学） |
|---|---|---|
| 存什么 | 对话过程、用户偏好、历史经验 | 物体坐标、双臂状态、碰撞、任务阶段 |
| 例子 | "用户偏好右侧篮子""上次右臂抓失败过" | "球在 (0.48,0.25)、被左夹爪夹住、置信度 0.91" |
| 更新频率 | 事件级 | 10Hz~事件 |
| 归属 | 编排层内部 | 独立世界状态层 |

---

## 四、接下来的全部工作（按优先级分级）

### A 级 · 近期该做（真增量）

1. **Memory 层**（宋泓）：给 orchestrator 加会话/情节/长期记忆模块。会话记忆收编现在散在 metadata 里的 clarify_round/上下文；长期记忆存用户偏好。
2. **三 ID + 审计链**（宋泓）：`session_id / task_id / request_id` 串联，补进 schema 和日志。真机排障刚需，成本低。
3. **Robot Gateway 显式化**（宋泓）：把 agent_api + clients 命名为 Robot Gateway，补 `request_id`、幂等、结构化错误码。
4. **World Model 服务**（新同学）：独立状态层，从最小实体集起步（左臂/右臂/球/篮子）。
5. **视觉事实服务真实内核**（新同学）：judge_service 的 RewardClassifier/YOLO，替换 mock。
6. **MCP 对外协议一个点**（宋泓，可作下阶段）：把 judge_service 暴露成 MCP 工具，证明"与框架互通"。

### B 级 · 双臂/边缘阶段再做（现在写进设计，不落地）

7. Policy 扩展成双臂资源模型：left_arm/right_arm/shared_workspace 资源锁、Coordinated 同步等级。
8. 失败重规划深化：从"重试同一技能"到"换臂/换策略"。
9. 结构化错误协议：`{code, recoverable, allowed_recovery}` 供 Agent 可靠重规划。
10. ASR/TTS/llama.cpp 边缘推理层整合（参考 OMiniX）+ 补 TTS。
11. dora 感知链试点（渐进式五阶段，见 §6）。

### C 级 · 现在别做（避免过度设计）

- token 预算、mid-task 取消、跨重启持久化（mock/单步技能阶段是臆想需求）
- DOT 任务图 / Pipeline（单任务链够用，多步复合出现了再说）
- 多租户 / 多渠道 / 沙箱 / Web 后台（远超当前需求边界）

---

## 五、进度控制（八周基线，避免"月一堆料、月二摸鱼"）

> 原则：编排层主体已完成，八周节奏是"收口已有 + 长出两个缺口层 + 与框架对接一个点 + 留出联调缓冲"，均匀铺开、每周都有可演示交付物。

| 周 | 主线交付物 | 可演示 |
|---|---|---|
| W1 | Robot Gateway 显式化 + 三 ID 贯通 schema 与日志 | 一次请求全链路 ID 可追踪 |
| W2 | Memory 层骨架：会话记忆收编 clarify 状态 | 多轮对话上下文不丢 |
| W3 | Memory 长期偏好 + 结构化错误码接入 | "记住用户偏好"可演示 |
| W4 | 与新同学联调 World Model 查询接口（契约冻结） | Gateway 能查 World Model（mock） |
| W5 | MCP 对外协议一个点（judge 暴露成 MCP 工具） | Octos/外部可调我们的判定 |
| W6 | 判定闭环真实内核联调（配合新同学 RewardClassifier） | 真实视觉判定接入 mock 替换 |
| W7 | dora 感知链 POC 评审 + A/B 基线数据（配合新同学） | 一条感知链 HTTP vs dora 对照 |
| W8 | 单臂低风险真机动作 + 整体联调 + 汇报材料 | move_to_named_pose 真机跑通 |

> 缓冲说明：每周主线之外留半天做测试/文档/应对联调阻塞。真机相关（W8）依赖硬件到位，若延后则顺延，不强行压缩前序。

---

## 六、dora 渐进式引入路线（写进计划，动手在未来）

> 归属：新同学 World Model 阶段主导，编排层只出 Robot Gateway 的 dora adapter 接口。**现阶段只做设计与 POC 评审，不整体迁移。**

- **阶段 1**：HTTP 基线测清（延迟 / P95 / 吞吐 / CPU / 失败率）——没有基准无法证明 dora 收益。
- **阶段 2**：只迁一条最有代表性的数据流：`相机 → 检测 → World Model → 可视化/录制`。不碰实机。
- **阶段 3**：同一业务接口做 A/B（HTTP 版 vs dora 版），比延迟/抖动/CPU/丢帧/恢复/代码量/调试时间。
- **阶段 4**：迁任务反馈链，先用 Mock 双臂执行器（Goal/Feedback/Result/Cancel）。
- **阶段 5**：最后接现有控制栈（dora Action → ROS2 Action），失败可回退 HTTP。

---

## 七、给老师的汇报口径（可直接照读）

> 这套 AgentOS 是一套分层集成架构。我们已经用 Python 独立实现了它**最上面三层（交互 / 决策 / 判定）的一个可运行垂直切片**：五服务 HTTP 解耦、Pydantic 契约冻结、每层 mock↔真实可插拔、Agent 永不 import 重依赖。意图理解、十态状态机、置信度闸门、失败重试、动作后判定闭环，都已跑通并有测试覆盖。
>
> 对这套框架，我们**不建议整体照搬或推倒重写**。理由：Octos 是 Rust 的通用对话 OS，产品边界远大于我们的需求，且整体搬运会切断我们依赖的 Python 具身智能生态（LeRobot/SmolVLA/SenseVoice）；而 Rust 的性能优势在我们这层（秒级、IO 密集）几乎无法兑现——系统瓶颈在模型推理和机械臂执行，不在编排框架。
>
> 最合理的路径是**"高层接入、底层保留"的旁路集成**：以我们已跑通的编排层为顶层大脑，通过协议边界（HTTP/MCP）与框架对接；把每层 mock 逐步换成真实内核（ASR→SenseVoice、VLA→SmolVLA、判定→RewardClassifier）；补齐 Memory 与 World Model 两个缺口层；dora 用在感知高频数据流试点，通过 Robot Gateway 桥接，不替换现有控制栈。我们的 Robot Gateway 雏形和传输无关的领域契约都已就位，所以未来接 dora 是加适配器，不是重写。
>
> 当前最大风险不在自然语言理解，而在高层大脑与底层控制之间的语义、安全、时序边界——我们已用"契约冻结 + dry_run 预演 + 置信度闸门 + 系统故障/任务失败切分"守住了这条边界。下一步先接单臂低风险真机动作，最后验证双臂/底盘协同。

---

## 八、仍需向老师确认的信息

1. 课程总仓库 / 锁定的 Octos、dora commit 或 release（dora 官网宣传 1.0，仓库 Release 仍 v0.5.0，版本需锁定）
2. OMiniX-API 的准确仓库、版本、API 文档与许可证
3. World Model 是否有现成实现，还是课程待开发模块
4. StarryOS 与辰龙硬件的准确型号、驱动协议、计算平台
5. dora ROS2 Bridge 稳定性（仓库标实验性）
6. 我们双臂的硬件型号、ROS 版本、控制频率、MoveIt 配置
7. "跟组式"具体指主从遥操作、示教跟随、编队，还是双臂协同控制

> 在这些拿到前，我们能给的是**架构级可行性判断 + 已实现切片的实测**，还不能做最终代码级复用承诺——这本身就是严谨的工程态度。

---

*本文技术判断中，涉及 dora/Octos/OMiniX/StarryOS 的外部事实基于公开资料与老师提供的调研文档；"我们的对应物"均为本仓已落地并通过测试的真实代码。板端 310B/StarryOS 的具体算子与框架支持，建议以昇腾 CANN 文档与实机实测为准。*
