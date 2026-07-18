# 23 · S5-B 真实 SenseVoice 语音接入落地与本地语音到决策全链路演示

日期：2026-07-14
分支：worktree-tests-scaffold（git worktree 隔离副本）
提交：c65a786 feat(agent_api): S5-B 真实 SenseVoice 语音接入落地 + 打字/语音双演示脚本

## 一、背景与动机

嘲风 AgentOS 编排层的周任务是「先在电脑上把整条语音到决策链路跑通，尽快向老师演示本地语音到决策的过程」，NPU（310B）移植留到后面。此前 S5-A 已把语音接入骨架接好（asr_service 服务壳 + /v1/chat_audio 入口 + ASRClient + mock 转写），但真实的 SenseVoiceProvider 还是占位的 NotImplementedError，语音链路只能走假转写。本次要落地的核心是：把真实 SenseVoice 语音识别接进来，用真人录音端到端验证「语音→文本→意图→决策」，并产出可直接演示的工具，同时妥善解决「测试要 mock、演示要真实模型、提交的配置又必须安全」这个三方冲突。

## 二、做了什么

1. 落地真实 SenseVoiceProvider（src/asr_service/providers/sensevoice.py）
   - 用 funasr 的 AutoModel 加载 SenseVoice-Small（CPU，254MB 权重，中文字错率约 8%，实测 RTF 0.1~0.22，比实时快 5~10 倍）。
   - 模块级单例缓存 + 双检锁：get_provider() 每个请求都新建 provider 实例，若模型不做模块级缓存会每次请求重载 254MB 权重，故用全局单例 + threading.Lock 双检锁只加载一次。
   - 守红线：funasr / torch 的 import 只写在 asr_service 的函数内部（懒加载），Agent 编排进程绝不 import 重依赖。
   - 内置重采样：真人录音是 48kHz 立体声，SenseVoice 要 16kHz 单声道，provider 内用 soundfile 读 + 声道求均值 + librosa 重采样，避免依赖 ffmpeg（走纯 wav 路径）。

2. 解决「测试 mock / 演示真实 / 提交安全」三方冲突（C+B 策略）
   - configs/app.yaml 里新增 asr 段，provider 默认 mock：这是提交进仓库的默认档，全量测试 / CI / 队友拉代码都走假转写，不加载 254MB 权重、不触真实模型。
   - 同时给 agent 段补 asr_service_url，否则 ASRClient 读不到会 KeyError。
   - 新建 configs/demo_sensevoice.yaml 演示覆盖档：只含 asr 段（provider: sensevoice），演示时经环境变量 AGENT_VLA_CONFIG 覆盖，仅对 asr_service 进程生效，不污染提交的默认配置。

3. 产出两个演示脚本
   - scripts/demo_voice_link.sh：真实语音批量版。起 5 服务栈（vla/llm/judge/agent 走默认 mock，asr 经 demo_sensevoice.yaml 切真实 SenseVoice），逐条把真人录音 POST /v1/chat_audio（dry_run=true），一屏打印全链路轨迹。
   - scripts/demo_chat_repl.sh：打字交互版（应老师现场演示需求）。起 4 服务栈（不含 asr，纯文本入口 /v1/chat），秒级启动无需加载模型；现场打一句话回车，当场打印「意图→路由到哪个 API/技能→回答」，输入 q 退出。
   - scripts/run_asr_service.sh：asr 服务标准启动脚本（端口 8014）。

4. 补测试与契约
   - tests/conftest.py 加 FakeASRClient fixture（假转写，可控 next_text / next_exc，记录调用入参）。
   - tests/contract/test_schema_compat.py 加 ASR 契约测试（ASRRequest/ASRResponse 字段冻结 + 向后兼容默认值）。
   - src/common/schemas.py 加 ASRRequest / ASRResponse / AudioChatRequest 三个 schema。

## 三、产出清单（提交 c65a786，14 文件，+613 行）

- src/asr_service/**（真实 SenseVoice provider + mock + 服务骨架）
- src/common/schemas.py（ASR 三 schema）
- configs/app.yaml（加 asr 段默认 mock + agent.asr_service_url）
- configs/demo_sensevoice.yaml（演示覆盖档）
- scripts/demo_voice_link.sh、demo_chat_repl.sh、run_asr_service.sh
- tests/conftest.py（FakeASRClient）、tests/contract/test_schema_compat.py（ASR 契约）

## 四、关键数字成果

- 真实 SenseVoice 转写 6 条真人录音全部正确：关灯→关灯。、帮我把球捡起来→帮我把球捡起来。、北京有什么好玩的地方→北京有什么好玩的地方？等。
- 全链路端到端演示 6 条录音，三类意图路由全部正确：turn_off_light（关灯/帮我把灯关了）→ VLA light_switch_v1；pick_ball（帮我把球捡起来/把球抓一下）→ VLA ball_pick_v1；general_qa（今天天气/北京好玩）→ LLM generate。
- 提交前 28 个 ASR/audio/schema 相关测试全绿。
- SenseVoice 实测 RTF 0.1~0.22（比实时快 5~10 倍）。

## 五、遇到的问题与解决

1. 环境定位（核心卡点）：worktree 无独立 .venv；唯一装了 funasr/torch 的环境是主仓 .venv（/root/chaofeng/agent-llm-vla/.venv）；各服务启动脚本里的 conda activate lerobot 是死代码（conda 根本不存在，if 判断直接跳过）。解决：演示脚本显式用主仓 .venv 的 uvicorn（有 funasr）+ PYTHONPATH 指向本 worktree 的 src（有新代码），二者组合自包含跑通，不依赖调用者预先 activate。

2. git author 回落 root：worktree 里 git 没读到用户配置，首次提交 author 变成 root@DESKTOP，与历史一贯的 SongShiQ<1006769560@qq.com> 不一致。解决：git commit --amend --reset-author 修正（仅改本地未 push 提交，安全）。提醒：本 worktree 后续提交可能再次回落，可给 worktree 配本地 git user 一劳永逸。

3. 提交前脏 git status：session 中途 git status 冒出几十个 modified（vla_service/llm_service/docs 等），排查确认全是 CRLF↔LF 行尾符噪音（整文件翻转，内容一字未改），并非真实改动。解决：绝不用 git add -A，显式列 14 个本次真实产物路径精确提交，把红线区和行尾噪音全部挡在外面。__pycache__/*.pyc 已被 .gitignore 挡住，未混入。

4. 录音格式不匹配：真人录音 48kHz 立体声，SenseVoice 要 16kHz 单声道。解决：provider 内置重采样（soundfile + librosa）。

5. Windows/WSL 执行摩擦：Git Bash 反复吃 shell 变量、把 /root/... 翻译成 D:/Program Files/Git/root/...。解决：改用 wsl.exe -e bash -lc 包裹执行，或用字面绝对路径零变量。

## 六、守的规范

- 红线未破：vla_service/** llm_service/** 与 app.yaml 的 vla.* 段未被本次提交触碰；funasr/torch 只在 asr_service 内懒加载，Agent 进程不 import 重依赖。
- 提交只署名用户本人 SongShiQ，无任何 AI 共同署名 / 生成标记。
- 未 push 云端（origin 是团队共享仓）。
- schema 只做向后兼容新增。
- 全程 dry_run=true，真机前预演，不动机械臂。

## 七、下一步

- LLM 兜底路由（用户已认可方向）：当前意图路由是人工词表 + 子串匹配（keywords 精确匹配 + signals 动作×对象组合），只认列进表里的词，同义词/口语说法会漏、signals 任一动作+任一对象命中有误触风险、加新技能要手写整套词表。计划做「规则命中走规则（快、稳、可解释），没命中才交 LLM 兜底判意图（灵活）」，两者互补且不破坏现有可解释性。用户要求先保存当前成果、之后再做 LLM 兜底——本次已完成保存（提交 c65a786）。
- 交接文档 HANDOFF.md 已放在 worktree 项目根，新 session 读它即可接手。
