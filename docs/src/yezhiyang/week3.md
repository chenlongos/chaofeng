# 第三周

## 本周目标

本周实际没有继续大规模推进 Ascend 310B 的算子级优化，主要工作转向两件事：

1. 复查远端仓库中已经存在但个人周报里没有展开的 Agent/VLA/LLM 接口接入基础，明确后续 SmolVLA 推理服务应如何适配现有契约。
2. 调研 `llama.cpp` 与更适合 VLA 推理移植的 `vla.cpp` 路线，判断是否可以作为后续 RK3588、Orange Pi 或其他端侧平台的长期部署方向。

接口契约本周仍不修改。后续改造方式应是在现有 `/v1/execute` 外围新增 provider 或 bridge，把当前 SmolVLA resident worker 适配进去，而不是直接改 `common/schemas.py`。

## 远端仓库已有但此前未展开的工作

远端仓库里已经有一套 Agent、VLA、LLM 解耦框架，个人周报之前只简单提到“接口接入”，没有把可复用部分写清楚。本周重新梳理后，后续 SmolVLA 部署可以直接复用以下设计。

### 三服务拆分

当前架构把系统拆成三个 HTTP 服务：

| 服务 | 职责 | 后续与 SmolVLA 的关系 |
| --- | --- | --- |
| Agent API | 接收用户文本，判断机器人任务或通用问答 | 后续接语音识别结果、Web/Socket 文本输入、任务路由 |
| VLA Service | 暴露机器人技能列表并执行指定技能 | 后续新增 `ascend_vla`、`rknn_vla` 或 `remote_vla` provider |
| LLM Service | 提供通用语言生成能力 | 后续可接 Ollama、llama.cpp server 或云端模型 |

这个拆分对当前部署工作很关键：VLA 侧可以频繁替换 PyTorch、ONNX、OM、RKNN、C++ runtime，而 Agent 侧只依赖统一接口，不需要知道底层推理后端。

### 当前 VLA 契约

VLA Service 目前已经定义：

- `GET /v1/skills`：返回白名单技能。
- `POST /v1/execute`：执行一个 VLA 技能。

请求字段目前包括：

```json
{
  "skill_id": "ball_pick_v1",
  "user_text": "帮我把球捡起来",
  "duration_s": 15,
  "dry_run": false,
  "metadata": {}
}
```

这和我们之前单独设计的 `VLARequest(prompt, images, state, timestamp, episode_id, reset, seed/noise)` 不完全一致。因此下一步不应直接改契约，而应在 VLA provider 内做适配：

1. `skill_id` 查 `configs/app.yaml`，拿到固定 task prompt 和 policy 配置。
2. `user_text` 只作为上层用户原始输入保留，真正喂给模型的 prompt 优先使用技能固定 prompt。
3. `metadata` 暂时承载图像路径、base64 图像、机器人 state、episode_id、reset、timestamp 等扩展字段。
4. provider 内部把这些字段转换成 resident worker 需要的输入 bundle。
5. 返回时把 `action_unnorm_7`、分段耗时和后端信息放入 `metadata` 或 `raw_result`，保持外层响应结构不变。

### 已有 provider 与可扩展点

仓库里已经有：

- `mock` provider：用于不控制真实机械臂的接口联调。
- `lerobot_rollout` provider：通过 `lerobot-rollout` 调真实 SmolVLA/LeRobot。
- 文档中预留的 `remote_vla`、`ascend_vla` provider：适合接板端常驻推理服务。

因此后续最小改造路径是新增 provider，而不是重写 Agent：

```text
Agent /v1/chat
  -> VLA Service /v1/execute
  -> ascend_vla provider
  -> resident SmolVLA worker
  -> action_unnorm_7 + latency metadata
```

### 与语音和 Agent 的关系

远端文档中已有语音、AgentOS、多轮对话和工具调用相关内容。对本人的 SmolVLA 部署任务来说，需要对齐的是输入输出边界：

- 语音识别模块只需输出文本，进入 Agent 的 `/v1/chat`。
- Agent 只负责选择技能和生成受约束 tool call，不直接拼模型 tensor。
- VLA provider 负责采集或接收图像/state，并调用真实推理后端。
- 真实执行结果不能只看 `ok=true`，还需要后续视觉反馈或机器人状态确认。

这说明后续 VLA 侧最重要的是补齐常驻 worker 的服务化接口和耗时 instrumentation，而不是先修改全局 schema。

## RK3588 侧进展补充

本周将 RK3588 路线进一步收敛为“功能集成与接口验证平台”，而不是主实时推理平台。已有实验结论如下：

| 模块 | 当前状态 | 结论 |
| --- | --- | --- |
| vision encoder RKNN | canonical tanh-GELU rewrite 后 monolithic RKNN 与 ONNX 对齐，cos 约 0.999108 | 数值问题可修，但 latency 约 995.8 ms |
| connector RKNN | cos 约 0.999999968，median latency 约 42 ms | 可用于 image-to-prefix 闭环 |
| denoise RKNN | 输入 ONNX prefix KV 时 action_unnorm_7 cos 约 0.999999744 | 子图本身可用 |
| prefix RKNN | full prefix RKNN 最终 action cos 约 0.924520644 | hidden fp16 误差会逐层放大，不适合主链路 |

已经排除的路径包括：

1. full prefix monolithic RKNN：数值漂移不可接受。
2. 仅调整 RKNN `optimization_level`：level0 与 level3 表现接近，不能解决 drift。
3. 使用 RKNN float32、tfloat32、bfloat16：工具链不支持或转换失败。
4. prefix CPU/ONNXRuntime fallback：数值正确但端到端接近 3 s。
5. prefix 前 2 层 RKNN + 后 30 层 ORT：数值可接受但没有实际时延收益。

因此 RK3588 后续更适合用于验证：

- 图像输入格式；
- state 输入格式；
- skill/prompt 到 action 输出的接口闭环；
- Agent/语音/前端服务联调；
- 简化模型或蒸馏模型的部署可行性。

## SenseVoice 310B1 基准测试补充

虽然本周没有继续深入 SmolVLA 在 Ascend 310B1 上的算子优化，但远端语音链路已经有可用于后续 Agent/VLA 接入的实测基线：SenseVoiceSmall FP16 OM 已经能在 Ascend 310B1 上通过 PyACL `acl.mdl.execute` 成功执行，并完成了基础内存和时延测试。

### 测试条件

| 项目 | 配置 |
| --- | --- |
| 模型 | SenseVoiceSmall FP16 OM |
| 固定输入 | `1 x 100 x 560`，约支持 6 秒语音 |
| 测试音频 | 官方 5.616 秒中文样例 |
| 推理接口 | PyACL `acl.mdl.execute` |
| 预热 | 5 次 |
| 正式测量 | 30 次 |
| OM 文件大小 | 466.54 MiB |

### 时延结果

| 指标 | 结果 |
| --- | --- |
| 未预热首次推理 | 约 39.36 ms |
| 预热后平均时延 | 约 33.07 ms |
| P50 | 约 33.09 ms |
| P90 | 约 33.13 ms |
| 最低时延 | 约 32.89 ms |
| 最高时延 | 约 33.21 ms |
| 模型加载时间 | 约 3.45-3.51 s |

对于 5.616 秒中文音频，纯 NPU 神经网络推理约 33 ms，相当于约 170 倍实时速度。这说明语音识别模型本体在 310B1 上不是主要瓶颈，后续真正需要关注的是端到端链路。

### NPU 内存结果

| 指标 | 结果 |
| --- | --- |
| NPU 内存增量 | 约 920-921 MB |
| 加载后 NPU 内存 | 约 2687 MB |
| 预热后 NPU 内存 | 约 2687 MB |
| 退出后 NPU 内存 | 约 1731-1732 MB |

预热后没有发现额外 NPU 内存增长，因此当前可以把 SenseVoiceSmall FP16 OM 的实际运行内存按约 0.9 GB 估算，占 310B1 约 11.6 GB NPU 内存的 7.95%。从内存角度看，不需要为了部署 SenseVoiceSmall 立即做 INT8 量化。

### 端到端影响

上述 33 ms 只包含 OM 推理，不包含以下开销：

- 音频录制和 VAD；
- fbank/LFR/CMVN 特征提取；
- H2D/D2H 数据拷贝；
- CTC 和 SentencePiece 解码；
- 中文指令理解；
- HTTP 控车或 VLA 服务调用。

因此完整语音到动作链路的端到端延迟一定高于 33 ms。当前估计语音前后处理和解码会额外增加几十毫秒，后续需要在完整 Ascend 后端中实测，不能直接用纯 OM 推理时延代表最终交互时延。

### 风险说明

板端 `NPU Health` 仍显示 `Alarm`，系统仍存在 17 个 D 状态驱动线程和 LPM 异常。虽然 FP16 OM 当前可以正常加载、推理，并且退出后 NPU 内存能基本释放，但生产部署前仍应优先解决驱动健康告警，避免长时间运行时出现资源泄漏、推理阻塞或设备不可恢复。

当前结论是：SenseVoiceSmall FP16 OM 可以在这块 310B1 上运行，纯模型推理约 33 ms，实际占用约 920 MB NPU 内存；它适合作为后续语音输入入口接入 Agent/VLA 链路，暂时没有必要为了内存占用立即投入 INT8 量化。

## llama.cpp 调研

本地 `Embodied.cpp/third_party/llama.cpp` 已经存在，并且处于有本地修改的状态，说明此前已经开始围绕 GGUF/ggml runtime 做迁移准备。`llama.cpp` 的主要价值是：

1. C/C++ 推理栈成熟，适合减少 Python、PyTorch、Transformers 等运行时依赖。
2. GGUF 模型格式和 ggml kernel 体系适合做权重量化、CPU fallback 和跨平台部署。
3. 可以作为 LLM Service 的本地 provider，替换 Ollama 或云端 LLM。
4. 其多模态相关代码可以为 vision encoder、token/image adapter 的 C++ 化提供参考。

但 `llama.cpp` 本身不是完整 VLA runtime，直接迁移 SmolVLA 有几个风险：

| 风险 | 影响 |
| --- | --- |
| 缺少 VLA action head 原生流程 | SmolVLA 的 prefix cache、cross-attention、flow/diffusion denoise loop 仍需手工实现 |
| 多模态路径主要面向 VLM，不等同于机器人 action 输出 | 不能只把语言模型跑起来就认为 VLA 已迁移 |
| Ascend 310B / RK3588 NPU 后端不是 llama.cpp 主线 | 很可能只能先跑 CPU，端侧 latency 未必优于 ONNX/RKNN/OM |
| 模型转换工作量大 | 需要确认权重命名、tensor layout、tokenizer、image preprocessing、action normalization 全部一致 |
| 数值验收复杂 | 必须逐层或逐阶段对齐 PyTorch/ONNX reference，不能只看最终动作能否输出 |

因此 `llama.cpp` 更适合作为底层 runtime 参考和本地 LLM provider，不建议直接作为 SmolVLA 主迁移入口。

### Orange Pi / Ascend 上的 llama.cpp 相关线索

本周额外阅读了几条与 Orange Pi AIpro / Ascend NPU 上部署 Llama/ggml 相关的公开资料。只保留能从仓库或官方文档中确认的信息，结论是：这条路线可以作为 LLM provider 或 C++ runtime 参考，但不能直接证明 SmolVLA 可以低成本迁移。

| 来源 | 可确认信息 | 对当前项目的意义 |
| --- | --- | --- |
| `lenLRX/llama_orangepi` | 该仓库基于 Meta Llama 代码做 OrangePi 20T 推理实验；README 明确写到直接推理会 OOM，需要额外开启约 24G swap；还提到 `cann_kb_init` 需要用 `cann_patch` 替换；7B 测试结论是“仅仅是能跑” | 说明早期 torch_npu/PyTorch 路线依赖重、内存压力大，不适合作为低延迟常驻服务主线 |
| `Burtinsaw/GGML-CANN` | 该仓库目标是给 ggml 添加 CANN backend，README 直接面向 OrangePi AI Pro 20T / Ascend 310B1，并给出动态 shape MatMul、CANN context、kernel bin、kernel meta、静态 buffer、backend 注册等实现说明；同时作者说明测试板 NPU health 处于 alarm，实际端到端示例只验证了 CPU fallback | 这是比纯 PyTorch 路线更接近我们需求的 C++/ggml/CANN 参考，但当前还不能当作“310B1 NPU 已稳定跑通 llama.cpp”的证据 |
| llama.cpp CANN backend 文档 | 官方 `llama.cpp` 已有 CANN backend，使用 AscendC/ACLNN；支持 Linux，文档列出 910B、310P 支持情况，模型格式支持 FP16/Q4_0/Q8_0；同时有 CANN memory pool、ACL graph、operator fusion、prefill graph 等环境变量 | 对我们有参考价值，尤其是常驻内存池、ACL graph、算子融合开关；但文档中没有把 Orange Pi AIpro 20T / Ascend 310B1 列为已验证目标，因此不能直接假设可稳定复用 |

这里最重要的判断是：`llama_orangepi` 更像是“PyTorch/torch_npu 能跑通 Llama2 7B”的验证，不是轻量 C++ runtime；`GGML-CANN` 更接近我们想要的 C++/ggml/CANN 改造方向，但它自己也明确受 NPU health alarm 影响，尚未给出可靠的 310B1 NPU 端到端 LLM benchmark；官方 `llama.cpp CANN backend` 更工程化，但公开验证目标主要是 910B/310P。因此如果后续要把本地 LLM 放到 Orange Pi 上，推荐顺序是：

1. 先在 x86 或板端 CPU 上跑通 `llama.cpp` GGUF 小模型，接入 LLM Service。
2. 单独复现 `GGML-CANN` 的最小 ggml backend 测试，确认本机 310B1 在 NPU health 正常时能否进入 CANN backend，而不是落到 CPU fallback。
3. 再尝试官方 `llama.cpp` 的 `GGML_CANN=on` 路线，记录能否编译、加载、生成、释放内存。
4. 对比 CPU、CANN backend、Ollama/MindIE 的首 token、decode token/s、NPU 内存和长期稳定性。
5. 只有在 LLM provider 稳定后，再考虑把相关 runtime 经验迁移到 VLA，而不是把 SmolVLA 直接塞进 Llama 官方 PyTorch 代码路径。

## vla.cpp 调研

相比 `llama.cpp`，`vla.cpp` 与当前任务更贴近。它是基于 `llama.cpp`/ggml 的 VLA 推理 runtime，目标就是把 VLA 从 Python/PyTorch 栈迁到 C++ 推理栈中。公开 README 中已经说明支持 SmolVLA、π0、BitVLA、Evo-1、GR00T N1.x 等 VLA，并以单个 GGUF bundle 方式部署；推理时不依赖 Python 或 PyTorch。

它对当前项目有几个直接参考价值：

1. **模型组织方式**：把 vision-language prefix、cross-attention KV cache、action head 和 denoise/flow step 放进统一 runtime，而不是把每个子图拆成多个 ONNX/OM/RKNN 文件。
2. **服务形态**：提供常驻 server，一次加载模型，多次接收请求，这与我们在 310B 上想做的 resident worker 一致。
3. **输入协议**：CLI/server 接收图像、tokenized instruction、state，然后输出 action chunk；这和我们计划的 VLARequest 很接近。
4. **GGUF 打包**：SmolVLA 可以转换成自包含 GGUF，便于部署、版本管理和模型文件分发。
5. **量化路线**：支持对 LM backbone weight 做 GGUF 量化，如 Q8_0、Q4_0；vision tower、norm、action expert 可以选择保留浮点，符合我们此前“activation INT8 误差大，优先 weight-only”的判断。
6. **benchmark 方式**：常驻 server + client 重复请求的模式可以借鉴，用来替代当前容易受加载和资源状态影响的单次进程 benchmark。

公开 benchmark 显示，`vla.cpp` 的 SmolVLA 在不同平台上已经做过端侧测试，例如 RTX 3090、Jetson AGX Orin、Jetson Orin Nano、Apple M4。这个对 RK3588/Orange Pi 没有直接保证，但说明它至少比单纯 `llama.cpp` 更接近我们的部署问题。

### vla.cpp 的主要风险

| 风险 | 影响 | 应对计划 |
| --- | --- | --- |
| 仓库较新，接口和格式可能变化 | 直接接主线可能频繁返工 | 先 pin commit，做独立实验目录，不污染当前服务契约 |
| 没有 Ascend 310B / RKNN 后端 | 可能只能跑 CPU，无法直接利用 NPU | 先在 x86/RK3588 CPU 跑正确性和接口，再评估 ggml 后端扩展 |
| SmolVLA checkpoint 兼容性未知 | 我们训练/导出的 checkpoint 可能不能直接转换 | 先用公开 `smolvla-libero` GGUF smoke test，再试自有 checkpoint 转换 |
| tokenizer 和 prompt 输入形式不同 | Agent 输出文本到 token ids 之间需要桥接 | provider 内固定 tokenizer，不把 token ids 暴露到 Agent 契约 |
| action normalization/statistics 必须一致 | 输出 action 可能数值对齐但物理尺度错误 | 把 dataset statistics、action_mean/std 纳入 drift 测试 |
| 端侧 CPU latency 仍可能偏高 | RK3588/310B CPU 不能满足实时 | 只把它作为 C++ 化和模型压缩方向，不替代当前 310B OM 主线 |

## 下一步计划

1. 新增 `ascend_vla` 或 `remote_vla` provider 草案，但不修改 `VLAExecuteRequest` / `VLAExecuteResponse` 契约。
2. 将 SmolVLA resident worker 包成服务模式，接收 prompt、image、state，返回 `action_unnorm_7` 与分段耗时。
3. 从远端现有 `/v1/execute` 的 `metadata` 字段接入图像/state，先完成 mock 请求到真实 worker 的闭环。
4. 对 `vla.cpp` 做最小 A/B：
   - 拉取并固定一个 commit；
   - 下载公开 SmolVLA GGUF；
   - 跑 `vla-cli` 单张图像 smoke test；
   - 对比输出 shape、action statistics、latency；
   - 再判断是否转换自有 checkpoint。
5. `llama.cpp` 暂作为 LLM 本地 provider 和 ggml/GGUF runtime 参考，不直接承担 SmolVLA 全链路迁移。
6. RK3588 继续用于端到端接口和硬件输入验证；若要追求实时，优先考虑模型结构压缩、prefix 蒸馏和 denoise step 减少。

## 参考资料

- `agent-llm-vla/docs/architecture.md`
- `agent-llm-vla/docs/contracts.md`
- `agent-llm-vla/docs/development_plan.md`
- `/home/sakura/OrangePi/rk3588_smolvla/README.md`
- `https://github.com/lenLRX/llama_orangepi`
- `https://github.com/Burtinsaw/GGML-CANN`
- `https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/CANN.md`
- `https://github.com/VinRobotics/vla.cpp`
- `https://arxiv.org/abs/2606.08094`
