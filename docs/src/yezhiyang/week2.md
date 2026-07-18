# 第二周

## 本周目标

本周围绕 SmolVLA 在端侧的完整推理部署继续推进，重点验证 Ascend 310B 与 RK3588 两条路线的性能、数值对齐和工程可接入性。接口契约本周保持不变，后续再把当前推理服务改造成适配项目统一接口的形式。

## 主要工作

1. 完成 Ascend 310B 侧 full-chain 推理链路的持续测试，覆盖 vision encoder、prefix、denoise、action unnormalize 等关键阶段。
2. 对 denoise loop-OM 调度进行验证，尝试使用 s4 + s4 + s2 的分段调度替代原来的 10 次 denoise step + update 循环。
3. 增加服务侧 instrumentation 设计，计划统计 `load_inputs_ms`、`tokenize/lang_ms`、`save_outputs_ms`、`json_response_ms`、`request_wall_ms`、`core_total_ms` 等分段耗时。
4. 分析 310B 上 attention core、Softmax、GELU、LayerNorm、RoPE/RMSNorm 等算子路径，确认哪些可以继续尝试平台内置算子替换，哪些暂时不适合作为主线。
5. 对 W8A8、W8A16、W4A16 等量化方向做分组分析，重点区分 activation INT8 误差和 weight-only 量化误差。
6. 在 RK3588 上推进 SmolVLA 子图部署，完成 vision、connector、prefix、denoise 等 RKNN 子图的导出、转换和数值验证。
7. 定位 RK3588 prefix RKNN 的数值漂移问题，并验证 CPU/ONNXRuntime fallback 与部分 prefix 层 RKNN 混合执行的可行性。
8. 梳理后续接入真实硬件图像、状态、Agent 和语音输入时需要的请求结构和常驻推理服务形态。

## 当前效果

Ascend 310B 侧推理链路已经可以跑通完整 action 输出，当前粗略耗时量级如下：

| 阶段 | 当前耗时 |
| --- | --- |
| vision encoder 0-12 | 约 205-210 ms |
| prefix | 约 62 ms |
| denoise step path | 约 156 ms |
| 端到端 | 约 450 ms 量级 |

denoise loop-OM 的 s4 + s4 + s2 调度可以让 denoise 阶段稳定减少约 8-9 ms，但 loop OM 常驻后会让 vision 侧变慢约 14-16 ms，抵消 denoise 收益。因此后续需要在常驻进程内做 repeated inference benchmark，避免模型加载、GE 资源状态和 vision 波动干扰结论。

RK3588 侧已经完成多个子图验证：

| 子图 | 结果 |
| --- | --- |
| vision encoder | 通过 canonical tanh-GELU rewrite 后，monolithic RKNN 与 ONNX 对齐，cos 约 0.999108，单次 latency 约 995.8 ms |
| vision connector | 输出形状 `[1,64,960]`，cos 约 0.999999968，median latency 约 42 ms |
| denoise RKNN | 在输入 ONNX prefix KV 时，action_unnorm_7 cos 约 0.999999744，max_abs 约 0.001160 |
| prefix RKNN | full prefix RKNN 仍不可用，action_unnorm_7 cos 约 0.924520644 |

## 已排除或暂不作为主线的路径

1. Ascend 310B 自定义 FlashAttention 暂不作为主线。当前平台上未找到稳定可用的官方 PFA/IFA 路线，attention core 单层已经是个位数毫秒，继续手写 kernel 的收益风险比不高。
2. W8A8 全量 activation 量化暂不作为主线。已有单层结果显示主要误差来自 activation INT8，而不是 weight INT8：layer0 MLP W8A8 cosine mean 约 0.994554，act16+w8 cosine mean 约 0.999334。
3. INT4 不适合直接全量铺开。只有在 W4A16 能带来至少 10-15 ms encoder latency 收益，并且 action drift 接近 W8A16 时才值得继续。
4. RK3588 full prefix RKNN 暂不能用于端到端主链路。prefix 的 hidden-state fp16 误差会在后续层放大，`optimization_level=0` 与 level3 表现接近，说明不是单纯全局融合开关导致。
5. RK3588 prefix CPU/ONNXRuntime fallback 数值正确，但延迟过高；prefix ORT 约 1000 ms，denoise RKNN x10 约 1841 ms，端到端接近 3 s，不满足实时目标。

## 下一步计划

1. 固定 Ascend benchmark 方法，改为同一常驻进程内 warmup 3 次、repeat 20 次，输出 total、vision、prefix、denoise 的 median 和 p95。
2. 优先优化 runtime 层面的内存与输入管理，包括 `aclrtMalloc/free` 池化、静态输入 device 常驻、denoise time embedding 预计算、连续内存 view 替代冗余 D2D copy。
3. 对 vision encoder 做小范围受控算子实验，优先验证 GELU/GeluV2 或 NPUFastGelu 替换是否能稳定编译、profile 变快并通过 full-chain action drift。
4. 量化继续沿 weight-only / A16W8 方向推进，先做 MLP only、projection only、MLP + projection 的小 A/B，不再盲目扩大 W8A8。
5. RK3588 暂定位为功能集成和接口验证平台。后续如要实时化，需要模型结构压缩、蒸馏或减少 prefix/vision 计算量。
6. 保持当前接口契约不变，后续新增适配层把 VLA request、图像/state 采集、Agent 文本输入、语音识别输入接入常驻推理 worker。
