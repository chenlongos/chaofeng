# 05 - 意图识别 LLM 兜底路由

> 日期：2026-07-14
> 模块：AgentOS 编排层 · 意图识别增强
> 分支：worktree-tests-scaffold

## 一、背景动机

嘲风桌面机器人的语音指令，先经 ASR 转文本，再由 AgentOS 编排层的 route_user_text()
做意图识别，命中则下发对应 VLA 技能（捡球、关灯），未命中落通用问答。

在此之前，意图识别是纯规则的两级匹配：

1. keywords 子串匹配——精确关键词（如"关灯""捡球"）直接命中。
2. signals 动作×对象组合匹配（S2 增强）——动作词与对象词同时出现即判定，
   解决中文语序灵活、动宾隔断的问题（"把灯关了" = 对象"灯" + 动作"关"）。

纯规则快、稳、可解释，但有三个已知痛点：

- 痛点#1 同义/口语漏召回：用户说"帮我把地上那个圆的东西弄起来"，规则词表里
  没有这些说法，漏判。
- 痛点#2 否定/劝阻误触：用户说"别关灯"，signals 层里"关"和"灯"都是子串，
  规则误命中 robot.turn_off_light——把"别做"当成"去做"，这是危险的假阳性。
- 痛点#3 技能硬编码：候选意图写死在规则里，新增技能要手工维护词表。

本次任务落地 HANDOFF 中的方案 B：规则命中的走规则（保留快/稳/可解释），
只有规则未命中时才交给 LLM 分类。模型选定 Qwen2.5:1.5B，先用 Ollama 做演示
（方案 A），后续可零代码切 llama.cpp 做边缘部署（方案 B）——两者同为 OpenAI 兼容
端点，切换只改配置。

## 二、做了什么

采用测试先行（先写红测试、再实现到绿）推进，全程守住黄金契约
route_user_text() 返回 (intent, ToolCall) 不变。

### 1. LLM 兜底路由（方案 B 主体）

- 新增 _llm_fallback_intent()：规则全未命中时，才调 LLM 做意图分类。
- 候选意图从 config 的 intent_rules 动态构建——新增技能自动纳入候选，
  无需手写词表（解决痛点#3）。
- 分类提示（_build_classify_prompt）采用 few-shot 示例而非硬 schema 约束
  （遵循"reason free, constrain late"：小模型上硬约束反而语义退化）。1.5B 小模型
  对抽象规则遵循弱，对具体输入→输出示范学得好——这一点在验证中被实测反复确认。
- 白名单校验兜底幻觉：LLM 输出经 strip 后必须精确命中某个机器人意图 key，
  否则（判 general_qa、幻觉出白名单外意图、空答案）一律回落通用问答，不信任
  LLM 自由文本。
- 关键路径守护：LLM 服务不可达/超时（ServiceCallError）→ 回落 general_qa，
  绝不让整条链 503。
- 开关默认 off：读 agent.intent_llm_fallback.enabled，committed 配置走纯规则，
  既有行为零回归；真实演示经 demo_llm_ollama.yaml 覆盖开启。

### 2. OllamaProvider（真实小模型接入）

- 新增 src/llm_service/providers/ollama.py：通过 Ollama 的 OpenAI 兼容端点
  /v1/chat/completions 调用本地 qwen2.5:1.5b，走 HTTP 而非进程内加载
  （llm_service 保持轻依赖，模型常驻 Ollama 侧）。
- main.py 加 provider 分支，懒加载（import 放函数内，照 sensevoice 模式）。
- 切 llama.cpp 只需改 base_url/model，本类零改动。

### 3. 否定词否决（痛点#2 的源头堵截）

这是本次最关键的一个发现驱动的改动（详见"遇到的问题"）。

- 新增模块级默认否定词表 _DEFAULT_NEGATION_MARKERS（别/不要/不用/不想/无需/甭/先不）
  + _has_negation() 辅助函数。
- 在 route_user_text 命中意图前先算否定标记：含否定词时，命中的机器人意图一律
  否决，继续找其他意图，最终落兜底/通用问答——堵在规则误触的源头。
- config 驱动：agent.negation_markers 可覆盖内置表，新增否定词无需改代码。
- 诚实边界：只否决明确的否定/劝阻词，不碰疑问句——"能不能关灯""帮我关下灯"
  是真实执行意图，一刀切否决会误伤召回。

### 4. 顺带修复的链路断点

- LLMClient.generate 原本只收 user_text，不传 system_prompt，router 兜底调用
  会 TypeError、且分类提示送不到 provider。已向后兼容加可选参数（空则不进 payload，
  既有 general_qa 调用不受影响）。

## 三、产出清单

新增：
- src/llm_service/providers/ollama.py — OllamaProvider（OpenAI 兼容端点）
- configs/demo_llm_ollama.yaml — 真实演示覆盖配置（兜底 on + provider=ollama，
  vla 仍 mock 不触真实机器人）
- tests/unit/test_router_llm_fallback.py — LLM 兜底单测 10 项
- tests/unit/test_router_negation.py — 否定否决单测 18 项（含 config 驱动、
  疑问句召回不误伤）

修改：
- src/agent_api/router.py — 兜底分类逻辑 + few-shot 提示 + 白名单校验 + 否定否决
- src/agent_api/tool_clients.py — LLMClient.generate 加 system_prompt（向后兼容）
- src/llm_service/main.py — provider 分支加 ollama 懒加载
- configs/app.yaml — 加 intent_llm_fallback（默认 off）+ llm.ollama 段（provider 仍 mock）
- tests/conftest.py — FakeLLMClient 加 system_prompt 记录、router 命名空间注入

## 四、关键数字成果

- 全量回归：219 passed, 9 skipped，零回归。
- 新增测试：LLM 兜底 10 项 + 否定否决 18 项 = 28 项，全绿。
- 真实 qwen2.5:1.5b 隔离分类：同义/口语/疑问句 6/6 命中。
- 完整 HTTP 链路端到端（router → LLMClient → HTTP → OllamaProvider → Ollama）：
  跨进程传参、分类、白名单、VLA ToolCall 组装全通。
- 真实端到端复验（否定否决 + LLM 兜底同时启用）：7/7 全对——否定句正确否决、
  肯定句正常执行、规则漏正确兜底、闲聊正确落通用问答。

## 五、遇到的问题与解决

### 问题1：方案 B 架构盲区——LLM 兜底救不了规则误触

隔离测试 LLM 分类器时，"别关灯"6/6 里能正确判 general_qa，我一度以为痛点#2 也
被 LLM 解决了。但在完整链路里，"别关灯"又稳定误判为 turn_off_light。

用代码逐步定位根因："别关灯"在规则 signals 层就命中了（action"关" + object"灯"
都是子串），route_user_text 在规则层就返回了意图，LLM 兜底根本没机会触发。
之前的隔离测试是直接调 LLM、绕过了规则层，所以被"骗"过了。

一句话总结这个边界：LLM 兜底只在规则未命中时触发，所以它只能救"规则漏"
（false negative），救不了"规则误触"（false positive）。痛点#2 本质是误触，
是方案 B 的天然盲区。

解决：如实向用户说明这个发现，用户决策"规则层加否定词否决"。据此实现了
否定否决逻辑，堵在规则命中的源头，零 LLM 成本。真实链路复验后否定句全部正确落
通用问答，且不误伤肯定句。

### 问题2：1.5B 小模型对抽象规则遵循弱

第一版分类提示用抽象规则描述（"否定句、疑问句不是执行指令"），实测否定句仍误判。
改成具体 few-shot 示例（输入→输出配对，含否定句示范）后，6/6 全对。印证小模型
"学示范优于学规则"。

### 问题3：测试文件重复

收尾时发现 test_router_negation.py 与压缩后新建的 test_router_negation_veto.py
测同一功能（DRY 红线）。前者设计更全（含 config 驱动 + 疑问句召回测试），保留前者、
删后者，并对齐 config key（negation_markers）。

### 问题4：UNC 路径写入静默失败反复出现

多次 Edit 报成功但内容未落盘（记忆中的 UNC 陷阱）。全程用 grep/字面绝对路径复核
每次写入，发现静默失败即重写，确保产物真实落地。

## 六、守的规范

- 契约不破：route_user_text() 返回 (intent, ToolCall) 始终不变；schema 只做向后
  兼容新增（system_prompt 早已在 schema 中，零 schema 风险）。
- 分层红线：agent_api 层不 import 重模型，LLM 调用一律走 HTTP 到 llm_service。
- 零回归优先：所有新能力默认 off，committed 配置行为不变，队友/CI 不触真实 LLM。
- 测试先行：先写红测试，再实现到绿。
- 诚实边界：不假装解决了没解决的问题（疑问句处理明确标注留待后续）；发现方案
  盲区第一时间如实说明，交用户决策。
- 精确提交：只 git add 本次真实产物的显式路径，绝不 git add -A（仓库有大量
  CRLF↔LF 假 diff）。

## 七、下一步

- 疑问句的显式处理（"你会关灯吗"当前靠 signals 不命中自然落 general_qa，非否决
  功劳，是巧合边界，值得显式化）。
- 方案 B 边缘部署：Ollama → llama.cpp 切换（改配置即可，代码零改动）验证。
- 兜底分类的置信度信号：当前白名单是二值校验，未来可结合 S8 置信度闸门做更细的
  低置信反问。
- 意图命中率基线补否定/疑问样本，把否决能力纳入回归基线。
