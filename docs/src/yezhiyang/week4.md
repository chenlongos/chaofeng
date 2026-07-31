# 第四周（2026-07-27 ~ 2026-07-31）

## 本周目标

本周工作从上一周的 SG2002 ACT 非 JPU baseline 继续向三个方向收口：

1. 评估 LicheeRV Nano / SG2002 原生 Linux 上的 JPEG 硬解码路线，判断 JPU 是否适合作为当前 ACT 输入链路的短期优化主线。
2. 验证 C906 / SG2002 上 `libjpeg-turbo` 的 RISC-V 向量化可行性，明确 RVV 1.0、RVV 0.7.1 和 C fallback 的边界。
3. 调研并验证 KWS 语音命令识别路线，为后续 Agent/VLA 的语音入口提供可部署方案。

本周没有完成 StarryOS 侧 JPU 硬解码验证，因此这里不把 StarryOS JPU 写成已跑通结果。JPU 相关结论只限于 LicheeRV Nano 原生 Linux 与参考 SDK 路线的可行性评估。

## LicheeRV Nano JPU 路线评估

本周通过原生 Linux 系统和 LicheeRV Nano SDK 参考实现，重新分析了 SG2002 上 JPEG 硬解码是否适合直接接入 ACT 图像输入链路。测试和源码走读后，当前判断是：JPU 方向仍有长期价值，但不适合作为本周继续压缩 ACT 端到端时延的短期主线。

主要原因如下：

1. SDK 示例路径不是一个轻量的“单张 JPEG 到 RGB/YUV buffer”接口，而是绑定了较完整的 CVI/JPU/VDEC buffer 管理、stream submit、frame buffer 注册和输出拷贝流程。
2. 原生 Linux 路线中 `send` / stream 提交阶段开销偏大，短期内难以确认实际慢点来自硬件解码、驱动同步、buffer 管理还是用户态封装。
3. 当前 ACT 链路只需要连续小图 JPEG 解码；如果引入完整 VDEC/VBPool/多 channel 框架，工程范围会明显扩大，且对 StarryOS 迁移帮助有限。
4. JPU 输出通常是 YUV/planar buffer，后续仍需要颜色空间转换、resize、cache 同步和物理连续内存管理；这些开销如果处理不好，可能抵消硬解码收益。
5. StarryOS 侧目前没有完成与 Linux 参考序列一致的硬解码验证，不能把 Linux 示例成功等价看成 StarryOS 已可用。

因此当前 JPU 结论是：保留为后续硬件输入链路优化方向，但本周不再把它作为默认性能优化主线。后续如果继续做，应先实现最小化单帧 path：固定 JPEG bitstream buffer、固定输出 buffer、复刻 Linux `JPU_DecOpen -> JPU_DecGetInitialInfo -> JPU_DecRegisterFrameBuffer -> JPU_DecStartOneFrame -> wait irq/status` 的寄存器序列，再与 `libturbojpeg` 做同图 checksum 和耗时对比。

## RVV0.7 + C 加速 JPEG 解码

本周进一步验证了 `libjpeg-turbo` 在 C906 / SG2002 上的 RISC-V SIMD路线。结论是：不能直接使用当前上游 RVV 1.0 版本，短期可行路线是围绕 RVV 0.7.1 和 C 实现做定向移植。

### RVV 1.0 直接上板失败

尝试替换较新的 `libjpeg-turbo` 动态库后，StarryOS 侧运行出现 `IllegalInstruction`。结合 C906 指令集特性判断，原因是 SG2002 的 C906 核心支持的是 RVV 0.7.1，而不是上游新版本常用的 RVV 1.0 指令编码。因此直接编译最新版 `libjpeg-turbo` 的 RVV 1.0 SIMD 代码不可行。

### RVV rollback 风险

本周也分析了 `rvv-rollback` 和平头哥 GCC 10.2 工具链路线。当前判断是：

- 如果上游 RVV 1.0 代码只使用 LMUL=1/2/4/8 这类 0.7.1 原生支持的分组，自动翻译风险较低；
- 如果热点代码大量依赖 fractional LMUL，自动翻译会引入大量模拟和数据重排，性能可能反而低于纯 C；
- JPEG 解码涉及 8-bit 像素、采样、IDCT、颜色转换和交错/解交错操作，不能假设自动翻译一定有收益。

因此本周选择把可持续路线收敛为：参考早期 RISC-V / C906 RVV 0.7 分支，并保留 C fallback，在热点上手工改造，而不是盲目把 RVV 1.0 整体翻译到 RVV 0.7.1。

### 当前实测结果

在板端部署可运行的 `libturbojpeg.so.0` 后，ACT 同步链路继续采用：

```text
turbojpeg + RVV resize + CVI TPU sync
```

当前稳定 baseline 如下：

| 阶段 | 典型耗时 |
| --- | --- |
| JPEG decode | 约 8.6-9.5 ms |
| RVV resize/interp | 约 3.3-5.0 ms |
| fill inputs | 约 0.3 ms |
| TPU inference | 约 51.6 ms |
| postprocess | 约 0.2 ms |
| pipeline | 约 65 ms/frame |

其中一次 20 帧测试结果为：

| 指标 | 数值 |
| --- | --- |
| `avg_image_decode_ms` | 8.647 ms |
| `avg_resize_interp_ms` | 4.993 ms |
| `avg_inference_ms` | 51.611 ms |
| `avg_fill_inputs_ms` | 0.334 ms |
| `avg_postprocess_ms` | 0.216 ms |
| `avg_pipeline_ms` | 65.801 ms |

100 帧测试中同步路径约为 `avg_eval_wall_ms=65.294 ms`，异步 split 路径约为 `66.585 ms`，说明在当前单核 SG2002 + StarryOS 环境下，继续做 TPU submit/wait overlap 没有收益。当前非 JPU 主线应固定为 `libturbojpeg + RVV + sync`，后续优化空间主要来自更细的 JPEG SIMD、减少内存拷贝和降低推理频率，而不是继续扩大异步调度复杂度。

## KWS 调研与验证

本周围绕“前进、后退、左转、右转”等机器人控制语音命令，完成了三类 KWS 验证：官方 Google Speech Commands 路线、中文 TTS/DS-CNN 路线、SynTTS-Commands 数据集分析。

### Google Speech Commands 路线

为了避开 Sophgo TDL 旧 sound-classification enum 路线的问题，本周实现了直接使用 `cviruntime` 的 KWS probe。该路径在主机侧完成训练和 TPU-MLIR 转换，在板端直接加载 `cvimodel` 推理。

当前四方向英文模型使用：

```text
go, backward, left, right
```

严格四分类模型在验证集上达到约 `92.32%`。板端可加载 BF16 `cv181x` 模型，并通过 `google_kws_runtime_probe` 完成 log-mel 特征和 TPU 推理。测试中 `go/left/right` 能正确识别，但 `backward` 仍容易与 `right` 混淆，说明该模型可作为链路验证，但还不能直接作为最终控制入口。

板端耗时上，当前 C 前端仍是主要瓶颈：

| 阶段 | 典型耗时 |
| --- | --- |
| feature init | 约 42 ms |
| log-mel feature | 约 143 ms |
| TPU inference | 约 0.23 ms |

这说明 KWS 模型本体在 SG2002 TPU 上很轻，真正需要优化的是音频前端。后续应把当前朴素 DFT 改成 FFT/KissFFT 或复用更成熟的音频特征前端，并改成常驻进程，避免每次启动都重新加载模型。

### 中文 DS-CNN 路线

在 `/home/sakura/KWS` 中，本周进一步建立了中文 TTS 数据集和 DS-CNN 训练流程。当前数据配置如下：

| 项目 | 配置 |
| --- | --- |
| 采样率 | 16 kHz |
| 输入时长 | 1.2 s |
| 特征 | 40 mel bins |
| FFT | 512 |
| window / hop | 25 ms / 10 ms |
| 模型 | DS-CNN |
| 参数量 | 约 27k-28k |

当前有两种标签设计：

1. `intent` 八分类：`forward/back/left/right/front_left/front_right/back_left/back_right`；
2. `text` 十五分类：`前进/后退/左转/右转/向前/向后/向左/向右/...`。

主要训练结果如下：

| 任务 | 最佳 epoch | val acc | test acc |
| --- | ---: | ---: | ---: |
| `kws_dscnn_intent_v2_small` | 28 | 70.56% | 74.44% |
| `kws_dscnn_text_v2_small` | 27 | 71.11% | 73.33% |

混淆矩阵显示，短命令之间仍有明显混淆，例如 `向左` 容易被预测成 `右转`，`向后` 容易被预测成 `向右`。一次真实录音测试中，`forward` 被识别为 `front_left`，置信度约 `0.741`。因此当前中文 KWS 已经跑通训练、导出和测试闭环，但还不能直接用于真实控制。

### SynTTS-Commands 数据集分析

本周还分析了 `SynTTS-Commands-Official`。该数据集对我们有架构和训练策略参考价值，但不能直接作为方向命令数据集使用。

原因是它当前公开命令集主要是媒体控制和唤醒词：

- 中文包括：播放、暂停、上一首、下一首、音量控制、接听电话、小爱同学等；
- 英文包括：Play、Pause、Resume、Next track、Volume up、Alexa 等；
- 不包含 `前进/后退/左转/右转` 这类机器人运动命令。

它最有价值的结论是：中文 zero-shot 合成数据迁移到真实语音时召回会明显下降，而每类加入约 50 条真实样本后，真实测试效果会大幅提升。因此后续中文 KWS 不应只依赖 TTS 数据，必须采集目标麦克风、目标环境下的少量真实样本做 fine-tune。

## 当前结论

1. LicheeRV Nano / SG2002 的 JPU 硬解码路线仍值得后续研究，但当前 Linux SDK 路径过重，`send` 和 buffer 管理开销不透明，短期不适合作为 ACT 输入链路优化主线。
2. SG2002/C906 不能直接使用上游 RVV 1.0 `libjpeg-turbo` SIMD；当前应沿 RVV 0.7.1 + C 定向优化路线推进。
3. `libturbojpeg + RVV + sync` 已经是当前 ACT 非 JPU 稳定 baseline，约 65 ms/frame，其中 TPU 推理约 51.6 ms，占主要部分。
4. KWS 侧已经跑通 Google KWS、中文 TTS/DS-CNN 和板端 cviruntime probe，但真实可用性还受音频前端耗时、真实录音样本不足和短命令混淆影响。
5. 后续若要接入 Agent/VLA，推荐优先做“常驻 KWS 进程 + 真实样本 few-shot + FFT 特征前端”，而不是先扩大模型规模。

## 下周计划

1. 继续压缩 KWS 音频前端，把当前朴素 DFT 特征提取替换为 FFT 实现，并测量常驻进程下端到端延迟。
2. 录制每类至少 50 条真实中文方向命令样本，重新训练 DS-CNN，并重点观察 `前进/左转/右转/后退` 的混淆矩阵。
3. 保留 `libturbojpeg + RVV + sync` 作为 SG2002 ACT 默认 baseline，后续只做小范围可量化优化。
4. 如果继续研究 JPU，先在 Linux 侧拆出单帧最小 path，再决定是否迁回 StarryOS，而不是直接移植完整 VDEC/VBPool 框架。
